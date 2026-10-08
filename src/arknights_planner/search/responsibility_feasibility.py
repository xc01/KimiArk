"""Exact route-aware responsibility and geometry feasibility certificates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Iterable

from .operator_assignment import CoverageAssignmentAlternative
from .spatial_timing import SpatialTimingSearch, TileCandidate
from .temporal_assignment import (
    EarlyPressureResponsibility,
    TemporalAssignmentFrontier,
    TemporalResponsibility,
)
from arknights_planner.simulator import ApproximateRealRangeTransformer


@dataclass(frozen=True)
class RouteSpawnThreat:
    route_id: str
    lane_id: str
    enemy_id: str
    enemy_speed: float
    spawn_frames: tuple[int, ...]
    route_length: float
    legal_interception_tiles: tuple[tuple[int, int], ...]
    earliest_operator_contact_distance: float | None
    earliest_operator_contact_frame: int | None
    latest_interception_tile: tuple[int, int] | None
    latest_interception_distance: float | None
    latest_safe_blocker_frame: int | None
    contact_to_leak_seconds: float | None


@dataclass(frozen=True)
class EarlyThreatModel:
    frame_clock: str
    routes: tuple[RouteSpawnThreat, ...]
    ranged_windows: tuple[dict[str, Any], ...]
    observed_fresh_best_leak_routes: tuple[str, ...]
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class ResponsibilityFeasibilityCertificate:
    hypothesis_id: str
    assignment_id: str
    responsibility_id: str
    operator: str
    tactical_role: str
    lane_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    pressure_window: str
    first_relevant_enemy: str | None
    enemy_arrival_frame: int | None
    latest_safe_deployment_frame: int | None
    earliest_affordable_deployment_frame: int | None
    required_tile_region: str
    required_facing: str | None
    required_attack_coverage: tuple[tuple[int, int], ...]
    required_block_contact_position: tuple[int, int] | None
    dp_feasible: bool
    tile_feasible: bool
    coverage_feasible: bool
    timing_feasible: bool
    conflicts: tuple[str, ...]
    final_status: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeometryFeasibilityCertificate:
    skeleton_id: str
    hypothesis_id: str
    assignment_id: str
    operator: str
    tactical_role: str
    assigned_tile: tuple[int, int]
    facing: str
    lane_intersection: tuple[str, ...]
    route_intersection: tuple[str, ...]
    attack_coverage: tuple[tuple[int, int], ...]
    healing_coverage: tuple[tuple[int, int], ...]
    block_contact_point: tuple[int, int] | None
    tile_conflicts: tuple[str, ...]
    deployment_legality: str
    roadblock_interaction: str
    responsibility_coverage: tuple[str, ...]
    final_status: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpatialResponsibility:
    responsibility_id: str
    hypothesis_id: str
    assignment_id: str
    operator: str
    tactical_role: str
    required_kind: str
    route_ids: tuple[str, ...]
    pressure_window: str
    required_region_types: tuple[str, ...]
    minimum_coverage: int
    block_contact_required: bool
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _frame(seconds: float, fps: int) -> int:
    return max(0, int(math.floor(seconds * fps + 0.5)))


def build_early_threat_model(
    engine,
    understanding: StageUnderstanding,
    *,
    early_window: EarlyPressureResponsibility,
    fps: int = 30,
    observed_leak_routes: Iterable[str] = (),
) -> EarlyThreatModel:
    stage = engine.fixture.stage
    routes = {route.route_id: route for route in stage.routes}
    exact_cells = {route.route_id: route.exact_cells for route in understanding.routes}
    lane_by_route = {route.route_id: route.lane_id for route in understanding.routes}
    deployable_ground = set(understanding.deployable_ground)
    route_rows: list[RouteSpawnThreat] = []
    for route_id in sorted(set(early_window.route_ids) | set(observed_leak_routes)):
        route = routes.get(route_id)
        if route is None:
            continue
        spawns = [row for row in engine.fixture.spawn_timeline if row.route_id == route_id]
        if not spawns:
            continue
        spawn_rows: list[tuple[float, str]] = []
        for spawn in spawns:
            for index in range(int(spawn.count)):
                spawn_rows.append((spawn.time + index * spawn.interval, spawn.enemy_id))
        speeds = [
            float(engine.fixture.enemies[enemy_id].stats.move_speed.value or 0)
            for _, enemy_id in spawn_rows
            if float(engine.fixture.enemies[enemy_id].stats.move_speed.value or 0) > 0
        ]
        speed = min(speeds) if speeds else 0.0
        route_cells = sorted(
            ((cell, route.distance_at(cell)) for cell in exact_cells.get(route_id, ())),
            key=lambda item: (item[1] if item[1] is not None else math.inf, item[0]),
        )
        contact_rows = [
            (distance, cell) for cell, distance in route_cells
            if distance is not None and cell in deployable_ground
        ]
        first_spawn, first_enemy = min(spawn_rows, key=lambda item: item[0])
        contact_distance = min((item[0] for item in contact_rows), default=None)
        latest_distance, latest_tile = max(contact_rows, key=lambda item: item[0]) if contact_rows else (None, None)
        contact_frame = (
            _frame(first_spawn + contact_distance / speed, fps)
            if contact_distance is not None and speed > 0 else None
        )
        latest_frame = (
            _frame(first_spawn + latest_distance / speed, fps)
            if latest_distance is not None and speed > 0 else None
        )
        route_rows.append(RouteSpawnThreat(
            route_id=route_id,
            lane_id=lane_by_route.get(route_id, "unknown"),
            enemy_id=first_enemy,
            enemy_speed=speed,
            spawn_frames=tuple(_frame(item[0], fps) for item in sorted(spawn_rows, key=lambda row: row[0])),
            route_length=route.length,
            legal_interception_tiles=tuple(
                sorted(cell for distance, cell in contact_rows)
            ),
            earliest_operator_contact_distance=contact_distance,
            earliest_operator_contact_frame=contact_frame,
            latest_interception_tile=latest_tile,
            latest_interception_distance=latest_distance,
            latest_safe_blocker_frame=latest_frame,
            contact_to_leak_seconds=(
                (route.length - contact_distance) / speed
                if contact_distance is not None and speed > 0 else None
            ),
        ))

    transformer = ApproximateRealRangeTransformer()
    ranged_windows = []
    for operator_id, operator in engine.fixture.operators.items():
        if operator.position.value != "RANGED":
            continue
        for tile in understanding.deployable_high_ground:
            for direction in ("UP", "RIGHT", "DOWN", "LEFT"):
                coverage = set(transformer.covered_tiles(
                    origin=tile,
                    offsets=operator.attack_range,
                    direction=direction,
                ))
                windows = []
                for route_id, route in routes.items():
                    distances = [route.distance_at(cell) for cell in coverage if route.distance_at(cell) is not None]
                    if not distances:
                        continue
                    entry_distance = min(distances)
                    for threat in route_rows:
                        if threat.route_id != route_id or not threat.earliest_operator_contact_distance:
                            continue
                        windows.append({
                            "route_id": route_id,
                            "entry_distance": entry_distance,
                            "contact_distance": threat.earliest_operator_contact_distance,
                            "pre_contact_seconds": max(
                                0.0,
                                (threat.earliest_operator_contact_distance - entry_distance) / max(0.001, threat.enemy_speed),
                            ),
                        })
                if windows:
                    ranged_windows.append({
                        "operator_id": operator_id, "tile": tile, "tile_kind": "HIGH_GROUND",
                        "facing": direction, "windows": windows,
                    })
    return EarlyThreatModel(
        frame_clock=f"configured_frame_{fps}fps",
        routes=tuple(route_rows),
        ranged_windows=tuple(ranged_windows),
        observed_fresh_best_leak_routes=tuple(sorted(set(observed_leak_routes))),
        provenance=(
            "GameData stage routes, exact tile-centre distance_at, expanded spawn timeline, enemy move speed, and buildable tile model",
            "No visual lane approximation is used.",
        ),
    )


def _cost_order_frame(engine, operator_id: str, deployment_order: tuple[str, ...], fps: int = 30) -> int:
    initial = float(engine.fixture.stage.initial_dp.value or 0)
    rate = float(engine.fixture.stage.dp_per_second)
    spent = 0.0
    for current in deployment_order:
        cost = float(engine.fixture.operators[current].phases[0].stats_max.cost.value or 0)
        if current == operator_id:
            needed = max(0.0, (spent + cost - initial) / rate) if rate > 0 else 0.0
            return _frame(needed, fps)
        spent += cost
    return 10**9


def _spatial_role(capability: str) -> str:
    return {
        "BLOCK_CAPACITY": "BLOCK", "EARLY_DEPLOYMENT": "BLOCK", "HEAL": "HEAL",
        "MULTI_LANE_COVERAGE": "MULTI_LANE_COVERAGE", "MELEE_DPS": "MELEE_DPS",
        "RANGED_DPS": "RANGED_DPS", "ARTS_DAMAGE": "RANGED_DPS", "SKILL": "SKILL",
    }.get(capability, capability)


def spatial_responsibilities(
    hypothesis,
    alternative: CoverageAssignmentAlternative,
    responsibilities: tuple[TemporalResponsibility, ...],
) -> tuple[SpatialResponsibility, ...]:
    requirement_to_temporal = {item.requirement_id: item for item in responsibilities}
    output = []
    for coverage in alternative.operator_coverage:
        for requirement_id in coverage.covered_requirement_ids:
            temporal = requirement_to_temporal.get(requirement_id)
            output.append(SpatialResponsibility(
                responsibility_id=f"{alternative.assignment_id}:{coverage.operator_id}:{requirement_id}",
                hypothesis_id=hypothesis.hypothesis_id,
                assignment_id=alternative.assignment_id,
                operator=coverage.operator_id,
                tactical_role=_spatial_role(coverage.primary_capability),
                required_kind=(
                    "BLOCK_CONTACT" if coverage.primary_capability in {"BLOCK", "BLOCK_CAPACITY"}
                    else "SUPPORT" if coverage.primary_capability == "HEAL"
                    else "ATTACK_COVERAGE"
                ),
                route_ids=temporal.route_ids if temporal else (),
                pressure_window=temporal.pressure_window if temporal else "UNKNOWN",
                required_region_types=(
                    ("CHOKE_POINT_BLOCK", "EARLY_TEMPORARY_INTERCEPTION")
                    if coverage.primary_capability in {"BLOCK", "BLOCK_CAPACITY"}
                    else ("SHARED_HIGH_GROUND_COVERAGE", "UPSTREAM_RANGED_INTERCEPTION")
                    if coverage.primary_capability == "MULTI_LANE_COVERAGE"
                    else ("RANGED_SUPPORT_COVERAGE",)
                ),
                minimum_coverage=1,
                block_contact_required=coverage.primary_capability in {"BLOCK", "BLOCK_CAPACITY"},
                provenance=f"TemporalResponsibility:{requirement_id} -> AssignmentCoverage:{coverage.operator_id}",
            ))
    return tuple(output)


def build_responsibility_certificates(
    engine,
    understanding: StageUnderstanding,
    frontier: tuple[TemporalAssignmentFrontier, ...],
    coverage_alternatives: tuple[CoverageAssignmentAlternative, ...],
    hypotheses: Iterable[Any],
    threat: EarlyThreatModel,
    spatial_search: SpatialTimingSearch,
    *,
    fps: int = 30,
) -> tuple[ResponsibilityFeasibilityCertificate, ...]:
    hypotheses_by_id = {item.hypothesis_id: item for item in hypotheses}
    alternatives = {item.assignment_id: item for item in coverage_alternatives}
    output = []
    for temporal in frontier:
        for hypothesis_id, hypothesis in hypotheses_by_id.items():
            if temporal.assignment_id not in hypothesis.hypothesis_id:
                continue
            alternative = alternatives.get(temporal.assignment_id)
            if alternative is None:
                continue
            deployment_order = temporal.deployment_order
            for temporal_row in temporal.temporal_responsibilities:
                links = [
                    coverage for coverage in alternative.operator_coverage
                    if temporal_row.requirement_id in coverage.covered_requirement_ids
                ]
                if not links:
                    links = [
                        coverage for coverage in alternative.operator_coverage
                        if coverage.primary_capability == temporal_row.required_capability
                    ]
                role = _spatial_role(temporal_row.required_capability)
                relevant_threats = [
                    row for row in threat.routes
                    if row.route_id in set(temporal_row.route_ids) and row.earliest_operator_contact_frame is not None
                ]
                relevant_threats.sort(key=lambda row: row.earliest_operator_contact_frame or 10**9)
                first_threat = relevant_threats[0] if relevant_threats else None
                candidates: list[TileCandidate] = []
                for link in links:
                    candidates.extend(spatial_search.tile_candidates(link.operator_id, role))
                required_routes = set(temporal_row.route_ids)
                matching = [
                    candidate for candidate in candidates
                    if required_routes.intersection(
                        set(candidate.block_route_ids) | set(candidate.covered_route_ids)
                    )
                ]
                dp_frame = min(
                    _cost_order_frame(engine, link.operator_id, deployment_order, fps)
                    for link in links
                ) if links else 10**9
                deadline = first_threat.latest_safe_blocker_frame if first_threat else None
                tile_feasible = bool(candidates)
                coverage_feasible = bool(matching)
                timing_feasible = bool(deadline is not None and dp_frame <= deadline)
                conflicts = []
                if not links:
                    conflicts.append("NO_ASSIGNED_OPERATOR")
                if tile_feasible and not coverage_feasible:
                    conflicts.append("NO_REQUIRED_ROUTE_COVERAGE")
                if not timing_feasible and dp_frame > 10**8:
                    conflicts.append("OPERATOR_BEYOND_DEPLOYMENT_LIMIT")
                if not timing_feasible and deadline is not None and dp_frame < 10**8:
                    conflicts.append("DP_DEPLOYMENT_AFTER_LATEST_SAFE_CONTACT")
                if len({link.operator_id for link in links}) < 1:
                    conflicts.append("SIMULTANEITY_CONFLICT")
                if not tile_feasible:
                    status = "TILE_INFEASIBLE"
                elif not coverage_feasible:
                    status = "COVERAGE_INFEASIBLE"
                elif not timing_feasible:
                    status = "DP_INFEASIBLE" if dp_frame > 10**8 else "CONTACT_TOO_LATE"
                else:
                    status = "REALIZABLE"
                best = sorted(
                    matching,
                    key=lambda item: (
                        -item.features["role_satisfaction"],
                        item.first_contact_seconds or 10**9,
                        item.tile,
                        item.direction,
                    ),
                )[0] if matching else None
                output.append(ResponsibilityFeasibilityCertificate(
                    hypothesis_id=hypothesis.hypothesis_id,
                    assignment_id=temporal.assignment_id,
                    responsibility_id=temporal_row.responsibility_id,
                    operator=",".join(sorted({link.operator_id for link in links})) or "UNASSIGNED",
                    tactical_role=role,
                    lane_ids=temporal_row.lane_ids,
                    route_ids=temporal_row.route_ids,
                    pressure_window=temporal_row.pressure_window,
                    first_relevant_enemy=first_threat.enemy_id if first_threat else None,
                    enemy_arrival_frame=first_threat.earliest_operator_contact_frame if first_threat else None,
                    latest_safe_deployment_frame=deadline,
                    earliest_affordable_deployment_frame=dp_frame if dp_frame < 10**8 else None,
                    required_tile_region=best.region_type if best else "NO_MATCHING_REGION",
                    required_facing=best.direction if best else None,
                    required_attack_coverage=tuple(sorted(best.covered_cells)) if best else (),
                    required_block_contact_position=best.tile if best and role == "BLOCK" else None,
                    dp_feasible=timing_feasible,
                    tile_feasible=tile_feasible,
                    coverage_feasible=coverage_feasible,
                    timing_feasible=timing_feasible,
                    conflicts=tuple(conflicts),
                    final_status=status,
                    evidence=(
                        f"candidates={len(candidates)}",
                        f"coverage_matches={len(matching)}",
                        f"dp_frame={dp_frame}",
                        f"latest_safe={deadline}",
                    ),
                ))
    return tuple(output)


def build_geometry_certificates(
    engine,
    understanding: StageUnderstanding,
    skeleton,
    *,
    assignment_id: str,
    threat: EarlyThreatModel,
    spatial_search: SpatialTimingSearch,
    spatial_rows: tuple[SpatialResponsibility, ...],
) -> tuple[GeometryFeasibilityCertificate, ...]:
    route_by_lane = {route.route_id: route.lane_id for route in understanding.routes}
    devices_by_tile = {device.tile: device for device in engine.fixture.stage.devices}
    output = []
    tiles_used = set()
    for placement in skeleton.placements:
        candidate = placement.candidate
        tile_conflicts = []
        if candidate.tile in tiles_used:
            tile_conflicts.append("DUPLICATE_TILE")
        tiles_used.add(candidate.tile)
        block_routes = set(candidate.block_route_ids)
        coverage_routes = set(candidate.covered_route_ids)
        relevant = [row for row in spatial_rows if row.operator == candidate.operator_id]
        responsibility_coverage = []
        for row in relevant:
            if row.required_kind == "BLOCK_CONTACT" and block_routes:
                responsibility_coverage.append(f"{row.responsibility_id}:COVERED")
            elif row.required_kind in {"ATTACK_COVERAGE", "SUPPORT"} and coverage_routes:
                responsibility_coverage.append(f"{row.responsibility_id}:COVERED")
            else:
                responsibility_coverage.append(f"{row.responsibility_id}:NOT_COVERED")
        supported = bool(relevant) and any(item.endswith(":COVERED") for item in responsibility_coverage)
        output.append(GeometryFeasibilityCertificate(
            skeleton_id=skeleton.skeleton_id,
            hypothesis_id=skeleton.hypothesis_id,
            assignment_id=assignment_id,
            operator=candidate.operator_id,
            tactical_role=candidate.intended_role,
            assigned_tile=candidate.tile,
            facing=candidate.direction,
            lane_intersection=tuple(sorted({route_by_lane[item] for item in coverage_routes | block_routes})),
            route_intersection=tuple(sorted(coverage_routes | block_routes)),
            attack_coverage=tuple(sorted(candidate.covered_cells)),
            healing_coverage=tuple(sorted(candidate.support_target_tiles)),
            block_contact_point=candidate.tile if block_routes else None,
            tile_conflicts=tuple(tile_conflicts),
            deployment_legality="LEGAL_TILE_AND_POSITION" if not tile_conflicts else "TILE_CONFLICT",
            roadblock_interaction=(
                f"DEVICE_AT_TILE:{devices_by_tile[candidate.tile].device_id}"
                if candidate.tile in devices_by_tile else "NONE"
            ),
            responsibility_coverage=tuple(responsibility_coverage),
            final_status=(
                "REALIZABLE" if supported and not tile_conflicts
                else "SPATIAL_COLLISION" if tile_conflicts
                else "COVERAGE_INFEASIBLE"
            ),
            evidence=tuple(placement.relations) or ("NO_RELATIONS",),
        ))
    return tuple(output)
