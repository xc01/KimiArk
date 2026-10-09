"""Stage-derived spatiotemporal tactical demand reconstruction."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
import math
from typing import Any

from ..agent.tactical import PlanHypothesis
from .stage_understanding import StageUnderstanding


@dataclass(frozen=True)
class RoutePressureCluster:
    cluster_id: str
    member_route_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    enemy_ids: tuple[str, ...]
    path_signature: tuple[tuple[float, float], ...]
    path_segments: tuple[tuple[tuple[int, int], ...], ...]
    candidate_interception_regions: tuple[dict[str, Any], ...]
    candidate_precontact_coverage_regions: tuple[dict[str, Any], ...]
    leak_destination: tuple[int, int]
    spawn_windows: tuple[dict[str, Any], ...]
    pressure_window_ids: tuple[str, ...]
    one_resource_plausible: bool
    overlap_with_clusters: tuple[dict[str, Any], ...]
    rationale: str
    provenance: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TacticalDemandWindow:
    window_id: str
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    active_clusters: tuple[str, ...]
    route_ids: tuple[str, ...]
    enemy_ids: tuple[str, ...]
    enemy_count: int
    aerial_composition: str
    ground_composition: str
    physical_or_arts_evidence: str
    block_demand: dict[str, Any]
    incoming_damage_pressure: dict[str, Any]
    damage_requirement: str
    sustain_requirement: str
    simultaneous_responsibilities: tuple[str, ...]
    previous_window_id: str | None
    next_window_id: str | None
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TacticalRequirementAtom:
    requirement_id: str
    family: str
    clusters: tuple[str, ...]
    pressure_windows: tuple[str, ...]
    route_ids: tuple[str, ...]
    required_by_frame: int | None
    persistence_until_frame: int | None
    required_region_kind: str
    required_region_tiles: tuple[tuple[int, int], ...]
    concurrency_group: str | None
    shareable: str
    necessity: str
    capability: str
    why: str
    evidence: tuple[str, ...]
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RequirementConcurrencyEdge:
    first_requirement_id: str
    second_requirement_id: str
    relation: str
    pressure_window: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisRequirementCoverageCertificate:
    hypothesis_id: str
    hard_requirements_total: int
    hard_requirements_covered: int
    uncovered_hard_requirements: tuple[str, ...]
    conditional_requirements_selected: tuple[str, ...]
    intentionally_uncovered: tuple[str, ...]
    concurrency_violations: tuple[dict[str, str], ...]
    temporal_conflicts: tuple[str, ...]
    spatial_sharing_assumptions: tuple[str, ...]
    opening_economy_feasible: bool
    opening_economy_evidence: str
    admissible: bool
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _expanded_spawn_events(fixture) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in fixture.spawn_timeline:
        for index in range(int(row.count)):
            output.append({
                "route_id": row.route_id,
                "enemy_id": row.enemy_id,
                "time": float(row.time) + index * float(row.interval),
            })
    return sorted(output, key=lambda item: (item["time"], item["route_id"], item["enemy_id"]))


def build_route_pressure_clusters(
    understanding: StageUnderstanding,
    *,
    coverage_opportunities: tuple[Any, ...] = (),
) -> tuple[RoutePressureCluster, ...]:
    grouped: dict[tuple[tuple[float, float], ...], list[Any]] = {}
    for route in understanding.routes:
        grouped.setdefault(route.waypoints, []).append(route)

    ordered = sorted(grouped.values(), key=lambda rows: (
        rows[0].lane_id,
        rows[0].waypoints,
        min(item.route_id for item in rows),
    ))
    coverage_by_tile: dict[tuple[int, int], set[str]] = {}
    for opportunity in coverage_opportunities:
        if opportunity.tile_kind != "HIGH_GROUND":
            continue
        coverage_by_tile.setdefault(opportunity.tile, set()).update(opportunity.route_ids)

    clusters: list[RoutePressureCluster] = []
    for index, rows in enumerate(ordered, start=1):
        rows.sort(key=lambda item: item.route_id)
        primary = rows[0]
        route_ids = tuple(item.route_id for item in rows)
        interception_regions = [
            {"tile": tile, "routes": route_ids, "kind": "GROUND_INTERCEPTION"}
            for tile in sorted(set(primary.block_tiles))
        ]
        coverage_regions = [
            {
                "tile": tile,
                "routes": tuple(sorted(set(route_ids) & covered_routes)),
                "kind": "HIGH_GROUND_PRECONTACT",
            }
            for tile, covered_routes in sorted(coverage_by_tile.items())
            if set(route_ids).intersection(covered_routes)
        ]
        clusters.append(RoutePressureCluster(
            cluster_id=f"C{index:02d}",
            member_route_ids=route_ids,
            lane_ids=(primary.lane_id,),
            enemy_ids=tuple(sorted({enemy for item in rows for enemy in item.enemy_ids})),
            path_signature=primary.waypoints,
            path_segments=(tuple(primary.exact_cells),),
            candidate_interception_regions=tuple(interception_regions),
            candidate_precontact_coverage_regions=tuple(coverage_regions),
            leak_destination=(int(primary.end[0]), int(primary.end[1])),
            spawn_windows=(),
            pressure_window_ids=(),
            one_resource_plausible=bool(len({item["tile"] for item in interception_regions}) <= 1 and coverage_regions),
            overlap_with_clusters=(),
            rationale=(
                "Routes share the complete exact waypoint path, source lane, leak destination, and interception geometry; "
                "distinct waypoint detours remain distinct tactical corridors."
            ),
            provenance=(
                "GameData route waypoints, buildable tile model, enemy references, and exact ranged coverage opportunities",
            ),
        ))

    updated: list[RoutePressureCluster] = []
    for cluster in clusters:
        own_cells = set(cluster.path_segments[0])
        overlaps = []
        for other in clusters:
            if other.cluster_id == cluster.cluster_id:
                continue
            other_cells = set(other.path_segments[0])
            shared_cells = sorted(own_cells & other_cells)
            shared_interception = sorted({
                item["tile"] for item in cluster.candidate_interception_regions
            } & {
                item["tile"] for item in other.candidate_interception_regions
            })
            shared_coverage = sorted(
                tile for tile, covered_routes in coverage_by_tile.items()
                if set(cluster.member_route_ids) & covered_routes and set(other.member_route_ids) & covered_routes
            )
            overlaps.append({
                "cluster_id": other.cluster_id,
                "shared_path_cells": shared_cells,
                "shared_interception_tiles": shared_interception,
                "shared_precontact_coverage_tiles": shared_coverage,
            })
        updated.append(RoutePressureCluster(
            **{
                **cluster.__dict__,
                "overlap_with_clusters": tuple(overlaps),
            }
        ))
    return tuple(updated)


def build_pressure_windows(
    understanding: StageUnderstanding,
    clusters: tuple[RoutePressureCluster, ...],
    fixture,
    *,
    fps: int = 30,
) -> tuple[TacticalDemandWindow, ...]:
    route_to_cluster = {
        route_id: cluster.cluster_id
        for cluster in clusters
        for route_id in cluster.member_route_ids
    }
    spawn_rows = sorted(fixture.spawn_timeline, key=lambda item: (item.time, item.route_id, item.enemy_id))
    if not spawn_rows:
        return ()

    route_length_by_id = {route.route_id: route.length for route in understanding.routes}
    speed_by_enemy = {item.enemy_id: item.speed for item in understanding.enemy_archetypes}
    travel_times = []
    for row in spawn_rows:
        length = route_length_by_id.get(row.route_id)
        speed = speed_by_enemy.get(row.enemy_id, 0.0)
        if length and speed > 0:
            travel_times.append(length / speed)
    max_travel = max(travel_times, default=10.0)
    window_gap = math.ceil(max_travel * 1.25)

    groups: list[list[Any]] = [[spawn_rows[0]]]
    for row in spawn_rows[1:]:
        if row.time - groups[-1][-1].time > window_gap:
            groups.append([row])
        else:
            groups[-1].append(row)

    windows: list[TacticalDemandWindow] = []
    for index, group in enumerate(groups, start=1):
        window_id = f"W{index:02d}"
        route_ids = tuple(sorted({item.route_id for item in group}))
        enemy_ids = tuple(sorted({item.enemy_id for item in group}))
        active_clusters = tuple(dict.fromkeys(
            route_to_cluster[item] for item in route_ids if item in route_to_cluster
        ))
        blockable_clusters = tuple(
            cluster_id for cluster_id in active_clusters
            if next(cluster for cluster in clusters if cluster.cluster_id == cluster_id).candidate_interception_regions
        )
        max_attack = max((
            item.atk for item in understanding.enemy_archetypes if item.enemy_id in enemy_ids
        ), default=0.0)
        total_hp = sum((
            next(item.max_hp for item in understanding.enemy_archetypes if item.enemy_id == row.enemy_id)
            * int(row.count)
            for row in group
        ), 0.0)
        windows.append(TacticalDemandWindow(
            window_id=window_id,
            start_frame=int(math.floor(group[0].time * fps)),
            end_frame=int(math.ceil(max(
                row.time + max(0, int(row.count) - 1) * float(row.interval) for row in group
            ) * fps)),
            start_time=group[0].time,
            end_time=max(row.time + max(0, int(row.count) - 1) * float(row.interval) for row in group),
            active_clusters=active_clusters,
            route_ids=route_ids,
            enemy_ids=enemy_ids,
            enemy_count=sum(int(row.count) for row in group),
            aerial_composition="UNKNOWN_NOT_REPRESENTED_IN_CURRENT_GAME_DATA_MODEL",
            ground_composition=", ".join(enemy_ids),
            physical_or_arts_evidence=(
                f"HP aggregate={total_hp:.1f}; max attack={max_attack:.1f}; damage type is not represented in current source model"
            ),
            block_demand={
                "blockable_clusters": blockable_clusters,
                "distinct_blockable_corridors": len(blockable_clusters),
                "unblockable_clusters": tuple(sorted(set(active_clusters) - set(blockable_clusters))),
            },
            incoming_damage_pressure={
                "max_enemy_attack": max_attack,
                "basis": "source enemy stats; exact attack timing remains runtime-derived",
            },
            damage_requirement=(
                "BLOCK_PHASE_DAMAGE_AND_PRECONTACT_DAMAGE" if blockable_clusters else "PRECONTACT_DAMAGE"
            ),
            sustain_requirement="CONDITIONAL_FRONTLINE_SUSTAIN" if blockable_clusters else "NOT_STRUCTURALLY_REQUIRED",
            simultaneous_responsibilities=tuple(dict.fromkeys((
                *(f"INTERCEPT:{item}" for item in blockable_clusters),
                *(f"PRECONTACT:{item}" for item in active_clusters if item not in blockable_clusters),
            ))),
            previous_window_id=f"W{index - 1:02d}" if index > 1 else None,
            next_window_id=f"W{index + 1:02d}" if index < len(groups) else None,
            evidence=(
                f"spawn-row batch {group[0].time:.3f}-{max(row.time + max(0, int(row.count) - 1) * float(row.interval) for row in group):.3f}s",
                f"grouping gap threshold={window_gap:.3f}s (125% of slowest full-corridor traversal)",
                "no fixed time bucket was imposed",
            ),
        ))
    return tuple(windows)


def _frame(value: float | None, fps: int = 30) -> int | None:
    return None if value is None else int(math.floor(value * fps + 0.5))


def build_tactical_requirement_atoms(
    understanding: StageUnderstanding,
    clusters: tuple[RoutePressureCluster, ...],
    windows: tuple[TacticalDemandWindow, ...],
    *,
    fps: int = 30,
) -> tuple[TacticalRequirementAtom, ...]:
    cluster_by_id = {item.cluster_id: item for item in clusters}
    output: list[TacticalRequirementAtom] = []
    first_window = windows[0] if windows else None

    if first_window:
        opening_clusters = first_window.active_clusters
        output.append(TacticalRequirementAtom(
            requirement_id="A-OPENING-ECONOMY",
            family="OPENING_DP",
            clusters=opening_clusters,
            pressure_windows=(first_window.window_id,),
            route_ids=tuple(sorted({
                route for cluster_id in opening_clusters
                for route in cluster_by_id[cluster_id].member_route_ids
            })),
            required_by_frame=first_window.start_frame,
            persistence_until_frame=first_window.end_frame,
            required_region_kind="DEPLOYABLE_STRUCTURE",
            required_region_tiles=tuple(sorted({
                item["tile"] for cluster_id in opening_clusters
                for item in cluster_by_id[cluster_id].candidate_interception_regions
            })),
            concurrency_group=f"CONCURRENCY-{first_window.window_id}",
            shareable="MAY_SHARE_RESOURCE",
            necessity="HARD",
            capability="EARLY_DEPLOYMENT",
            why="The opening structure must be affordable and legally placed before first contact in the opening corridor.",
            evidence=(
                f"initial_dp={understanding.initial_dp}",
                f"dp_per_second={understanding.dp_per_second}",
                first_window.evidence[0],
            ),
            provenance="GameData initial DP, natural DP rate, operator costs, spawn timeline, and exact deployable tiles",
        ))

    for cluster in clusters:
        cluster_windows = tuple(
            window for window in windows if cluster.cluster_id in window.active_clusters
        )
        if not cluster_windows:
            continue
        if cluster.candidate_interception_regions:
            first_cluster_window = cluster_windows[0]
            necessity = "HARD" if first_cluster_window is first_window else "CONDITIONAL"
            output.append(TacticalRequirementAtom(
                requirement_id=f"A-INTERCEPT-{cluster.cluster_id}",
                family="EARLY_INTERCEPTION" if necessity == "HARD" else "SUSTAINED_BLOCK",
                clusters=(cluster.cluster_id,),
                pressure_windows=tuple(item.window_id for item in cluster_windows),
                route_ids=cluster.member_route_ids,
                required_by_frame=_frame(first_cluster_window.start_time, fps),
                persistence_until_frame=_frame(cluster_windows[-1].end_time, fps),
                required_region_kind="GROUND_INTERCEPTION",
                required_region_tiles=tuple(item["tile"] for item in cluster.candidate_interception_regions),
                concurrency_group=f"CONCURRENCY-{first_cluster_window.window_id}",
                shareable=(
                    "NO" if len(cluster.candidate_interception_regions) == 1
                    else "SHARE_IF_GEOMETRY_ALLOWS"
                ),
                necessity=necessity,
                capability="BLOCK",
                why=(
                    "The exact route intersects a deployable ground tile; an unblocked enemy can reach the leak corridor."
                    if necessity == "HARD"
                    else "The corridor has a legal block tile, but pre-contact damage may substitute for a dedicated blocker under this thesis."
                ),
                evidence=(
                    f"exact interception tiles={cluster.candidate_interception_regions}",
                    *(item.evidence[0] for item in cluster_windows),
                ),
                provenance="GameData route geometry, buildable ground tiles, and expanded spawn timeline",
            ))
        else:
            output.append(TacticalRequirementAtom(
                requirement_id=f"A-PRECONTACT-{cluster.cluster_id}",
                family="PRECONTACT_DAMAGE",
                clusters=(cluster.cluster_id,),
                pressure_windows=tuple(item.window_id for item in cluster_windows),
                route_ids=cluster.member_route_ids,
                required_by_frame=_frame(cluster_windows[0].start_time, fps),
                persistence_until_frame=_frame(cluster_windows[-1].end_time, fps),
                required_region_kind="HIGH_GROUND_PRECONTACT",
                required_region_tiles=tuple(item["tile"] for item in cluster.candidate_precontact_coverage_regions),
                concurrency_group=f"CONCURRENCY-{cluster_windows[0].window_id}",
                shareable="SHARE_IF_GEOMETRY_ALLOWS",
                necessity="HARD",
                capability="RANGED_DPS",
                why="No deployable ground tile intersects this exact route; pre-contact damage is the only supported interception mechanism.",
                evidence=(
                    "no exact route-crossing buildable ground tile",
                    *(item.evidence[0] for item in cluster_windows),
                ),
                provenance="GameData route geometry, buildable ground tiles, and expanded spawn timeline",
            ))

    lane_one = tuple(item.cluster_id for item in clusters if item.lane_ids == ("lane-01",))
    lane_two = tuple(item.cluster_id for item in clusters if item.lane_ids == ("lane-02",))
    for index, group in enumerate((lane_one, lane_two), start=1):
        if not group:
            continue
        output.append(TacticalRequirementAtom(
            requirement_id=f"A-SHARED-COVERAGE-{index}",
            family="SHARED_RANGED_COVERAGE",
            clusters=group,
            pressure_windows=tuple(
                item.window_id for item in windows if set(group) & set(item.active_clusters)
            ),
            route_ids=tuple(sorted({
                route for cluster_id in group for route in cluster_by_id[cluster_id].member_route_ids
            })),
            required_by_frame=None,
            persistence_until_frame=None,
            required_region_kind="HIGH_GROUND_SHARED_COVERAGE",
            required_region_tiles=(),
            concurrency_group=None,
            shareable="SHARE_IF_GEOMETRY_ALLOWS",
            necessity="CONDITIONAL",
            capability="MULTI_LANE_COVERAGE",
            why="Multiple same-lane corridors converge toward a common leak destination and may share ranged coverage if exact geometry permits.",
            evidence=("GameData exact route coverage opportunities",),
            provenance="Exact ranged range model and route pressure clusters",
        ))

    late_window = windows[-1] if windows else None
    if late_window:
        active = late_window.active_clusters
        output.extend((
            TacticalRequirementAtom(
                requirement_id="A-LATE-BURST",
                family="BURST_DAMAGE",
                clusters=active,
                pressure_windows=(late_window.window_id,),
                route_ids=late_window.route_ids,
                required_by_frame=late_window.start_frame,
                persistence_until_frame=late_window.end_frame,
                required_region_kind="PRESSURE_CORRIDOR",
                required_region_tiles=(),
                concurrency_group=f"CONCURRENCY-{late_window.window_id}",
                shareable="MAY_SHARE_RESOURCE",
                necessity="CONDITIONAL",
                capability="RANGED_DPS",
                why="The late window concentrates repeated ground pressure and may require burst beyond sustained DPS.",
                evidence=(late_window.physical_or_arts_evidence, late_window.evidence[0]),
                provenance="Expanded spawn timeline and source enemy stats",
            ),
            TacticalRequirementAtom(
                requirement_id="A-LATE-SKILL",
                family="PRESSURE_WINDOW_SKILL",
                clusters=active,
                pressure_windows=(late_window.window_id,),
                route_ids=late_window.route_ids,
                required_by_frame=late_window.start_frame,
                persistence_until_frame=late_window.end_frame,
                required_region_kind="PRESSURE_CORRIDOR",
                required_region_tiles=(),
                concurrency_group=f"CONCURRENCY-{late_window.window_id}",
                shareable="MAY_SHARE_RESOURCE",
                necessity="CONDITIONAL",
                capability="SKILL",
                why="A concentrated late spawn group is a bounded pressure window, not a constant all-stage DPS demand.",
                evidence=(late_window.evidence[0],),
                provenance="Expanded spawn timeline",
            ),
        ))
    return tuple(output)


def build_requirement_concurrency_graph(
    atoms: tuple[TacticalRequirementAtom, ...],
) -> tuple[RequirementConcurrencyEdge, ...]:
    output: list[RequirementConcurrencyEdge] = []
    for first, second in combinations(atoms, 2):
        shared_windows = tuple(set(first.pressure_windows) & set(second.pressure_windows))
        if not shared_windows:
            output.append(RequirementConcurrencyEdge(
                first.requirement_id,
                second.requirement_id,
                "TEMPORALLY_SEPARATE",
                None,
                "The requirements do not share a pressure window.",
            ))
            continue
        region_overlap = bool(set(first.required_region_tiles) & set(second.required_region_tiles))
        first_blocking = first.capability in {"BLOCK", "BLOCK_CAPACITY"}
        second_blocking = second.capability in {"BLOCK", "BLOCK_CAPACITY"}
        first_ranged = first.capability in {"RANGED_DPS", "MULTI_LANE_COVERAGE"}
        second_ranged = second.capability in {"RANGED_DPS", "MULTI_LANE_COVERAGE"}
        if (first_blocking ^ second_blocking) or (
            first_blocking and second_blocking and not region_overlap
        ):
            relation = "MUST_BE_DISTINCT"
            reason = "Distinct exact placement regions or tile kinds are required."
        elif first_ranged and second_ranged:
            relation = "SHARE_IF_GEOMETRY_ALLOWS"
            reason = "A ranged resource may satisfy both only if one exact facing covers both route sets."
        else:
            relation = "MAY_SHARE_RESOURCE"
            reason = "Temporal overlap exists; resource sharing requires compatibility beyond this graph."
        output.append(RequirementConcurrencyEdge(
            first.requirement_id,
            second.requirement_id,
            relation,
            shared_windows[0],
            reason,
        ))
    return tuple(output)


def build_responsibility_lower_bounds(
    understanding: StageUnderstanding,
    clusters: tuple[RoutePressureCluster, ...],
    windows: tuple[TacticalDemandWindow, ...],
) -> tuple[dict[str, Any], ...]:
    cluster_by_id = {item.cluster_id: item for item in clusters}
    opportunities = [
        item for item in understanding.coverage_opportunities if item.tile_kind == "HIGH_GROUND"
    ]
    output = []
    for window in windows:
        routes = set(window.route_ids)
        selected: set[tuple[int, int]] = set()
        remaining = set(routes)
        while remaining:
            best = max(opportunities, key=lambda item: (len(remaining & set(item.route_ids)), -item.tile[0], -item.tile[1]))
            covered = remaining & set(best.route_ids)
            if not covered:
                break
            selected.add(best.tile)
            remaining -= covered
        output.append({
            "pressure_window": window.window_id,
            "minimum_simultaneous_interception_responsibilities": len(window.block_demand["blockable_clusters"]),
            "minimum_independent_coverage_regions": len(selected),
            "minimum_sustain_domains": 1 if window.block_demand["blockable_clusters"] else 0,
            "minimum_aerial_response_responsibilities": 0,
            "blockable_clusters": window.block_demand["blockable_clusters"],
            "unblockable_clusters": window.block_demand["unblockable_clusters"],
            "coverage_tiles": sorted(selected),
            "uncovered_routes_for_lower_bound": sorted(remaining),
            "basis": "Structural corridor and exact-coverage lower bounds; not an operator-count requirement.",
        })
    return tuple(output)


def build_pressure_transitions(
    atoms: tuple[TacticalRequirementAtom, ...],
    windows: tuple[TacticalDemandWindow, ...],
) -> tuple[dict[str, Any], ...]:
    output = []
    for current, next_window in zip(windows, windows[1:]):
        persisted = tuple(sorted(set(current.active_clusters) & set(next_window.active_clusters)))
        ended = tuple(sorted(set(current.active_clusters) - set(next_window.active_clusters)))
        new = tuple(sorted(set(next_window.active_clusters) - set(current.active_clusters)))
        persisting_requirements = tuple(
            item.requirement_id for item in atoms
            if set(persisted) & set(item.clusters)
            and current.window_id in item.pressure_windows
            and next_window.window_id in item.pressure_windows
        )
        ending_requirements = tuple(
            item.requirement_id for item in atoms
            if set(ended) & set(item.clusters)
            and current.window_id in item.pressure_windows
            and next_window.window_id not in item.pressure_windows
        )
        new_requirements = tuple(
            item.requirement_id for item in atoms
            if set(new) & set(item.clusters)
            and next_window.window_id in item.pressure_windows
            and current.window_id not in item.pressure_windows
        )
        output.append({
            "from_window": current.window_id,
            "to_window": next_window.window_id,
            "persisting_clusters": persisted,
            "ending_clusters": ended,
            "new_clusters": new,
            "persisting_requirements": persisting_requirements,
            "ending_requirements": ending_requirements,
            "new_requirements": new_requirements,
            "reusable_resource_families": sorted({
                item.capability for item in atoms if item.requirement_id in persisting_requirements
            }),
            "stranded_resource_risk": "CURRENT_THESIS_DEPENDENT",
            "reserve_activation_opportunity": bool(new or next_window.enemy_count >= current.enemy_count),
            "evidence": (current.evidence[0], next_window.evidence[0]),
        })
    return tuple(output)


def build_requirement_sharing(
    clusters: tuple[RoutePressureCluster, ...],
    atoms: tuple[TacticalRequirementAtom, ...],
) -> tuple[dict[str, Any], ...]:
    output = []
    atom_by_cluster = {
        cluster.cluster_id: tuple(item for item in atoms if cluster.cluster_id in item.clusters)
        for cluster in clusters
    }
    for first, second in combinations(clusters, 2):
        overlap = next(item for item in first.overlap_with_clusters if item["cluster_id"] == second.cluster_id)
        shared_requirement_pairs = [
            {
                "first_requirement_id": first_atom.requirement_id,
                "second_requirement_id": second_atom.requirement_id,
            }
            for first_atom in atom_by_cluster[first.cluster_id]
            for second_atom in atom_by_cluster[second.cluster_id]
            if first_atom.capability == second_atom.capability
        ]
        if overlap["shared_interception_tiles"] or overlap["shared_precontact_coverage_tiles"]:
            verdict = "SHARED"
        elif overlap["shared_path_cells"]:
            verdict = "CONDITIONALLY_SHARED"
        else:
            verdict = "DISTINCT"
        output.append({
            "cluster_pair": (first.cluster_id, second.cluster_id),
            "verdict": verdict,
            **overlap,
            "compatible_requirement_pairs": shared_requirement_pairs,
        })
    return tuple(output)


_CAPABILITY_ALIASES = {
    "OPENING_DP": {"EARLY_DEPLOYMENT"},
    "EARLY_INTERCEPTION": {"BLOCK"},
    "SUSTAINED_BLOCK": {"BLOCK", "BLOCK_CAPACITY"},
    "PRECONTACT_DAMAGE": {"RANGED_DPS", "MULTI_LANE_COVERAGE"},
    "SHARED_RANGED_COVERAGE": {"MULTI_LANE_COVERAGE", "RANGED_DPS"},
    "BURST_DAMAGE": {"RANGED_DPS"},
    "PRESSURE_WINDOW_SKILL": {"SKILL"},
    "SUSTAIN": {"HEAL"},
    "LANE_REINFORCEMENT": {"BLOCK", "RANGED_DPS"},
    "REPLACEMENT_FRONTLINE": {"BLOCK"},
    "RESERVE_RESPONSE": {"BLOCK", "RANGED_DPS"},
}


def build_hypothesis_requirement_certificates(
    hypotheses: tuple[PlanHypothesis, ...],
    atoms: tuple[TacticalRequirementAtom, ...],
    *,
    opening_feasibility_by_hypothesis: dict[str, bool] | None = None,
) -> tuple[HypothesisRequirementCoverageCertificate, ...]:
    output = []
    hard_atoms = tuple(item for item in atoms if item.necessity == "HARD")
    for hypothesis in hypotheses:
        capabilities = set(hypothesis.required_capabilities) | {
            item.get("capability")
            for item in hypothesis.operator_responsibilities
            if isinstance(item, dict) and item.get("capability")
        }
        covered = tuple(
            item.requirement_id for item in hard_atoms
            if capabilities & _CAPABILITY_ALIASES.get(item.family, {item.capability})
        )
        uncovered = tuple(item.requirement_id for item in hard_atoms if item.requirement_id not in covered)
        conditional_selected = tuple(
            item.requirement_id for item in atoms
            if item.necessity == "CONDITIONAL"
            and capabilities & _CAPABILITY_ALIASES.get(item.family, {item.capability})
        )
        violations = []
        for requirement_id in (*covered, *uncovered):
            atom = next(item for item in atoms if item.requirement_id == requirement_id)
            assigned = tuple(
                item.get("operator_id") for item in hypothesis.operator_responsibilities
                if isinstance(item, dict)
                and item.get("capability") in _CAPABILITY_ALIASES.get(atom.family, set())
            )
            if atom.shareable == "NO" and len(set(assigned)) > 1:
                violations.append({
                    "requirement_id": requirement_id,
                    "violation": "MULTIPLE_RESOURCES_FOR_NON_SHAREABLE_ATOM",
                    "operators": ", ".join(sorted(set(assigned))),
                })
        opening_feasible = bool((opening_feasibility_by_hypothesis or {}).get(hypothesis.hypothesis_id, True))
        rejections = []
        if uncovered:
            rejections.append(f"UNCOVERED_HARD_REQUIREMENTS:{','.join(uncovered)}")
        if violations:
            rejections.append("CONCURRENCY_VIOLATION")
        if not opening_feasible:
            rejections.append("OPENING_ECONOMY_INFEASIBLE")
        output.append(HypothesisRequirementCoverageCertificate(
            hypothesis_id=hypothesis.hypothesis_id,
            hard_requirements_total=len(hard_atoms),
            hard_requirements_covered=len(covered),
            uncovered_hard_requirements=uncovered,
            conditional_requirements_selected=conditional_selected,
            intentionally_uncovered=tuple(
                item.requirement_id for item in atoms
                if item.necessity == "OPTIONAL" and item.requirement_id not in conditional_selected
            ),
            concurrency_violations=tuple(violations),
            temporal_conflicts=(),
            spatial_sharing_assumptions=tuple(sorted({
                item.family for item in atoms
                if item.shareable == "SHARE_IF_GEOMETRY_ALLOWS"
                and capabilities & _CAPABILITY_ALIASES.get(item.family, set())
            })),
            opening_economy_feasible=opening_feasible,
            opening_economy_evidence=(
                "Supplied temporal-assignment DP precheck result"
                if opening_feasibility_by_hypothesis else
                "Capabilities only; exact DP feasibility is checked by the unchanged temporal assignment layer."
            ),
            admissible=not rejections,
            rejection_reasons=tuple(rejections),
        ))
    return tuple(output)


def build_failure_trace_requirement_alignment(
    leak_records: tuple[dict[str, Any], ...],
    clusters: tuple[RoutePressureCluster, ...],
    windows: tuple[TacticalDemandWindow, ...],
    atoms: tuple[TacticalRequirementAtom, ...],
) -> tuple[dict[str, Any], ...]:
    route_to_cluster = {
        route_id: cluster.cluster_id
        for cluster in clusters for route_id in cluster.member_route_ids
    }
    route_to_windows = {
        route_id: tuple(window.window_id for window in windows if route_id in window.route_ids)
        for route_id in route_to_cluster
    }
    output = []
    for record in leak_records:
        record_id = record.get("record_id") or record.get("timing_id") or record.get("hypothesis_id")
        rows = []
        for route_id in record.get("leak_routes", ()):
            cluster_id = route_to_cluster.get(route_id)
            if cluster_id is None:
                rows.append({
                    "route_id": route_id,
                    "cluster_id": None,
                    "status": "NOT_EXPLAINED_BY_REQUIREMENT_MODEL",
                    "requirement_id": None,
                })
                continue
            requirement = next((
                item for item in atoms if cluster_id in item.clusters
                and item.family in {"SUSTAINED_BLOCK", "EARLY_INTERCEPTION", "PRECONTACT_DAMAGE"}
            ), None)
            rows.append({
                "route_id": route_id,
                "cluster_id": cluster_id,
                "pressure_windows": route_to_windows.get(route_id, ()),
                "requirement_id": requirement.requirement_id if requirement else None,
                "status": (
                    "REQUIREMENT_PRESENT_BUT_NOT_REALIZED"
                    if requirement and requirement.capability == "BLOCK"
                    else "REQUIREMENT_MISSING" if requirement is None
                    else "REQUIREMENT_PRESENT_BUT_NOT_REALIZED"
                ),
                "old_model_status": (
                    "REQUIREMENT_PRESENT_BUT_NOT_REALIZED"
                    if requirement and requirement.capability == "BLOCK"
                    else "NOT_EXPLAINED_BY_REQUIREMENT_MODEL"
                ),
            })
        output.append({
            "record_id": record_id,
            "hypothesis_id": record.get("hypothesis_id"),
            "first_leak_seconds": record.get("first_leak_seconds"),
            "route_alignments": rows,
        })
    return tuple(output)


def build_tactical_motifs(
    atoms: tuple[TacticalRequirementAtom, ...],
    clusters: tuple[RoutePressureCluster, ...],
) -> tuple[dict[str, Any], ...]:
    hard = tuple(item for item in atoms if item.necessity == "HARD")
    motifs = []
    if sum(item.family in {"EARLY_INTERCEPTION", "SUSTAINED_BLOCK"} for item in hard) >= 2:
        motifs.append({
            "motif_id": "DUAL_EARLY_INTERCEPTION",
            "supported_requirements": tuple(item.requirement_id for item in hard if item.family in {"EARLY_INTERCEPTION", "SUSTAINED_BLOCK"}),
            "reason": "Multiple exact opening corridors have disjoint interception regions.",
        })
    if any(item.family == "PRECONTACT_DAMAGE" for item in hard):
        motifs.append({
            "motif_id": "FORWARD_PRECONTACT_DAMAGE",
            "supported_requirements": tuple(item.requirement_id for item in hard if item.family == "PRECONTACT_DAMAGE"),
            "reason": "At least one exact corridor has no legal blocker, making pre-contact damage structural.",
        })
    if any(item.family == "SHARED_RANGED_COVERAGE" for item in atoms):
        motifs.append({
            "motif_id": "SHARED_CENTRAL_DAMAGE",
            "supported_requirements": tuple(item.requirement_id for item in atoms if item.family == "SHARED_RANGED_COVERAGE"),
            "reason": "Same-lane corridors converge and exact high-ground opportunities may share coverage.",
        })
    if any(item.family in {"BLOCK", "BLOCK"} for item in atoms) and any(item.family == "PRECONTACT_DAMAGE" for item in atoms):
        motifs.append({
            "motif_id": "BLOCK_AND_BURN",
            "supported_requirements": tuple(item.requirement_id for item in atoms if item.family in {"EARLY_INTERCEPTION", "SUSTAINED_BLOCK", "PRECONTACT_DAMAGE"}),
            "reason": "Blockable and unblockable corridor families coexist.",
        })
    if any(item.family in {"PRESSURE_WINDOW_SKILL", "BURST_DAMAGE"} for item in atoms):
        motifs.append({
            "motif_id": "LATE_CONVERGENCE",
            "supported_requirements": tuple(item.requirement_id for item in atoms if item.family in {"PRESSURE_WINDOW_SKILL", "BURST_DAMAGE"}),
            "reason": "The final spawn group is concentrated relative to preceding event-gap windows.",
        })
    return tuple(motifs)
