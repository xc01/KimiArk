"""GameData-derived stage understanding and tactical requirement synthesis."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import ceil, hypot
from statistics import mean, pstdev
from typing import Any, Iterable

from arknights_planner.simulator import ApproximateRealRangeTransformer


@dataclass(frozen=True)
class RouteUnderstanding:
    route_id: str
    length: float
    waypoints: tuple[tuple[float, float], ...]
    start: tuple[float, float]
    end: tuple[float, float]
    cells: tuple[tuple[int, int], ...]
    exact_cells: tuple[tuple[int, int], ...]
    blockable: bool
    block_tiles: tuple[tuple[int, int], ...]
    spawn_count: int
    enemy_ids: tuple[str, ...]
    lane_id: str


@dataclass(frozen=True)
class LaneUnderstanding:
    lane_id: str
    route_ids: tuple[str, ...]
    cells: tuple[tuple[int, int], ...]
    entry_points: tuple[tuple[int, int], ...]
    exit_points: tuple[tuple[int, int], ...]
    spawn_count: int
    blockable: bool
    block_tiles: tuple[tuple[int, int], ...]
    blockable_route_ids: tuple[str, ...]
    non_blockable_route_ids: tuple[str, ...]
    actionability: str


@dataclass(frozen=True)
class RouteRelationship:
    first_route_id: str
    second_route_id: str
    shared_cells: tuple[tuple[int, int], ...]
    overlap_ratio: float
    relationship: str


@dataclass(frozen=True)
class WaveUnderstanding:
    wave_index: int
    fragment_count: int
    spawn_count: int
    start_time: float
    end_time: float
    route_ids: tuple[str, ...]
    enemy_ids: tuple[str, ...]


@dataclass(frozen=True)
class PressureWindow:
    window_id: str
    phase: str
    start_time: float
    end_time: float
    route_ids: tuple[str, ...]
    enemy_ids: tuple[str, ...]
    spawn_count: int
    simultaneous_lane_count: int
    high_risk: bool
    evidence: str
    provenance: str


@dataclass(frozen=True)
class CoverageOpportunity:
    tile: tuple[int, int]
    tile_kind: str
    route_ids: tuple[str, ...]
    covered_cells: tuple[tuple[int, int], ...]
    operator_ids: tuple[str, ...]
    shared: bool
    score: float


@dataclass(frozen=True)
class EnemyArchetype:
    enemy_id: str
    spawn_count: int
    max_hp: float
    atk: float
    defense: float
    magic_resistance: float
    speed: float
    attack_range: float | None
    threat_tags: tuple[str, ...]


@dataclass(frozen=True)
class StageUnderstanding:
    stage_id: str
    stage_code: str | None
    map_dimensions: tuple[int, int]
    deployable_ground: tuple[tuple[int, int], ...]
    deployable_high_ground: tuple[tuple[int, int], ...]
    routes: tuple[RouteUnderstanding, ...]
    lanes: tuple[LaneUnderstanding, ...]
    route_relationships: tuple[RouteRelationship, ...]
    interception_points: tuple[tuple[int, int], ...]
    coverage_opportunities: tuple[CoverageOpportunity, ...]
    waves: tuple[WaveUnderstanding, ...]
    pressure_windows: tuple[PressureWindow, ...]
    enemy_archetypes: tuple[EnemyArchetype, ...]
    spawn_count: int
    initial_dp: int
    deployment_limit: int
    squad_size_limit: int
    dp_per_second: float
    aerial_threat_status: str
    physical_pressure: dict[str, Any]
    arts_pressure: dict[str, Any]
    blocking_pressure: dict[str, Any]
    tactical_actionability: dict[str, Any]
    sustain_pressure: dict[str, Any]
    dp_economy_pressure: dict[str, Any]
    provenance: dict[str, str]
    approximations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TacticalRequirementModel:
    requirement_id: str
    requirement_type: str
    evidence: str
    pressure_window: str
    affected_routes: tuple[str, ...]
    hardness: str
    confidence: float
    capability: str
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cells(route) -> tuple[tuple[int, int], ...]:
    cells: list[tuple[int, int]] = []
    for first, second in zip(route.waypoints, route.waypoints[1:]):
        steps = max(1, ceil(max(abs(second.x - first.x), abs(second.y - first.y))))
        for step in range(steps + 1):
            ratio = step / steps
            cells.append((
                round(first.x + (second.x - first.x) * ratio),
                round(first.y + (second.y - first.y) * ratio),
            ))
    return tuple(dict.fromkeys(cells))


def _exact_cells(route, width: int, height: int) -> tuple[tuple[int, int], ...]:
    if width <= 0 or height <= 0:
        coordinates = [
            (round(point.x), round(point.y))
            for point in route.waypoints
        ]
        width = max((item[0] for item in coordinates), default=0) + 2
        height = max((item[1] for item in coordinates), default=0) + 2
    return tuple(sorted(
        (x, y)
        for x in range(width)
        for y in range(height)
        if route.distance_at((x, y)) is not None
    ))


def _union_find(items: list[str]) -> dict[str, str]:
    parent = {item: item for item in items}
    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item
    def union(first: str, second: str) -> None:
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parent[max(first_root, second_root)] = min(first_root, second_root)
    return {"parent": parent, "find": find, "union": union}


class StageUnderstandingAnalyzer:
    """Derive tactical stage structure without stage-specific constants."""

    def analyze(self, fixture) -> StageUnderstanding:
        stage = fixture.stage
        active_route_ids = tuple(dict.fromkeys(item.route_id for item in fixture.spawn_timeline))
        routes_by_id = {route.route_id: route for route in stage.routes if route.route_id in active_route_ids}
        spawn_counts: dict[str, int] = defaultdict(int)
        enemies_by_route: dict[str, set[str]] = defaultdict(set)
        for spawn in fixture.spawn_timeline:
            spawn_counts[spawn.route_id] += int(spawn.count)
            enemies_by_route[spawn.route_id].add(spawn.enemy_id)

        route_cells = {route_id: _cells(route) for route_id, route in routes_by_id.items()}
        map_width = int(stage.map_width.value or 0)
        map_height = int(stage.map_height.value or 0)
        exact_route_cells = {
            route_id: _exact_cells(route, map_width, map_height)
            for route_id, route in routes_by_id.items()
        }
        lane_for_route = self._lane_decomposition(routes_by_id, route_cells)
        ground = tuple((tile.x, tile.y) for tile in stage.stage_map.tiles if tile.buildable and tile.tile_kind == "GROUND")
        high_ground = tuple((tile.x, tile.y) for tile in stage.stage_map.tiles if tile.buildable and tile.tile_kind == "HIGH_GROUND")
        ground_set = set(ground)
        route_block_tiles = {
            route_id: tuple(sorted(set(cells) & ground_set))
            for route_id, cells in exact_route_cells.items()
        }
        lanes = self._lanes(
            active_route_ids,
            route_cells,
            exact_route_cells,
            route_block_tiles,
            lane_for_route,
            spawn_counts,
        )
        relationships = self._relationships(routes_by_id, route_cells)
        waves = self._waves(fixture.spawn_timeline)
        expanded_spawns = self._expanded_spawns(fixture.spawn_timeline)
        pressure_windows = self._pressure_windows(expanded_spawns)
        enemy_archetypes = self._enemy_archetypes(fixture, expanded_spawns)
        coverage = self._coverage_opportunities(fixture, exact_route_cells)
        route_understandings = tuple(
            RouteUnderstanding(
                route_id=route_id,
                length=float(route.length),
                waypoints=tuple((waypoint.x, waypoint.y) for waypoint in route.waypoints),
                start=(route.waypoints[0].x, route.waypoints[0].y),
                end=(route.waypoints[-1].x, route.waypoints[-1].y),
                cells=route_cells[route_id],
                exact_cells=exact_route_cells[route_id],
                blockable=bool(route_block_tiles[route_id]),
                block_tiles=route_block_tiles[route_id],
                spawn_count=spawn_counts[route_id],
                enemy_ids=tuple(sorted(enemies_by_route[route_id])),
                lane_id=lane_for_route[route_id],
            )
            for route_id, route in sorted(routes_by_id.items())
        )
        all_cells = tuple(sorted({cell for cells in route_cells.values() for cell in cells}))
        initial_dp = int(stage.initial_dp.value or 0)
        dp_per_second = float(stage.dp_per_second)
        cheapest_operator_cost = min(
            (float(operator.phases[0].stats_max.cost.value or 0) for operator in fixture.operators.values()),
            default=0.0,
        )
        return StageUnderstanding(
            stage_id=stage.stage_id,
            stage_code=stage.code.value if stage.code.value else None,
            map_dimensions=(int(stage.map_width.value or 0), int(stage.map_height.value or 0)),
            deployable_ground=ground,
            deployable_high_ground=high_ground,
            routes=route_understandings,
            lanes=lanes,
            route_relationships=relationships,
            interception_points=self._interception_points(exact_route_cells, ground, spawn_counts),
            coverage_opportunities=coverage,
            waves=waves,
            pressure_windows=pressure_windows,
            enemy_archetypes=enemy_archetypes,
            spawn_count=sum(spawn_counts.values()),
            initial_dp=initial_dp,
            deployment_limit=int(stage.deployment_limit.value or 0),
            squad_size_limit=int(stage.squad_size_limit.value or 0),
            dp_per_second=dp_per_second,
            aerial_threat_status="UNKNOWN_NOT_REPRESENTED_IN_CURRENT_GAME_DATA_MODEL",
            physical_pressure=self._physical_pressure(enemy_archetypes),
            arts_pressure=self._arts_pressure(enemy_archetypes),
            blocking_pressure=self._blocking_pressure(lanes, pressure_windows, enemy_archetypes),
            tactical_actionability={
                "blockable_lane_ids": tuple(lane.lane_id for lane in lanes if lane.blockable),
                "non_blockable_lane_ids": tuple(lane.lane_id for lane in lanes if not lane.blockable),
                "pre_contact_damage_required": tuple(
                    route_id
                    for lane in lanes
                    if not lane.blockable
                    for route_id in lane.route_ids
                ),
                "interception_opportunities": self._interception_points(exact_route_cells, ground, spawn_counts),
                "ranged_coverage_opportunities": tuple(
                    item.tile for item in coverage if item.tile_kind == "HIGH_GROUND"
                ),
                "shared_coverage_opportunities": tuple(
                    item.tile for item in coverage if item.shared
                ),
                "sustain_position_opportunities": tuple(
                    item.tile for item in coverage if item.tile_kind == "HIGH_GROUND"
                ),
                "temporary_hold_opportunities": tuple(
                    lane.block_tiles for lane in lanes if lane.blockable
                ),
                "provenance": "Exact Route.distance_at tile-centre geometry crossed with legal deployment tiles",
            },
            sustain_pressure=self._sustain_pressure(enemy_archetypes, fixture.operators),
            dp_economy_pressure={
                "initial_dp": initial_dp,
                "dp_per_second": dp_per_second,
                "cheapest_operator_cost": cheapest_operator_cost,
                "earliest_pressure_time": min((item["time"] for item in expanded_spawns), default=0.0),
                "classification": "EARLY_TIGHT" if expanded_spawns and cheapest_operator_cost > initial_dp else "STANDARD",
                "provenance": "GameData initialCost, costIncreaseTime, operator keyframes, and approximate spawn schedule",
            },
            provenance={
                "map": "GameData mapData via ApproximateRealSimulationAdapter",
                "routes": "GameData routes; only route IDs referenced by the approximate spawn timeline are active",
                "waves": "GameData wave/fragment hierarchy under the explicit spawn-schedule approximation",
                "enemies": "GameData enemy database stats referenced by this stage",
                "coverage": "Deployable tiles crossed with operator GameData attack ranges",
                "aerial": "Not derived because the current Enemy model has no flying field",
                "pressure": "Deterministic aggregate statistics; not a claim of exact client damage timing",
            },
            approximations=tuple(fixture.approximations_used),
        )

    @staticmethod
    def _lane_decomposition(routes_by_id, route_cells) -> dict[str, str]:
        route_ids = sorted(routes_by_id)
        disjoint = _union_find(route_ids)
        for index, first in enumerate(route_ids):
            for second in route_ids[index + 1:]:
                first_cells, second_cells = set(route_cells[first]), set(route_cells[second])
                shared = first_cells & second_cells
                overlap = len(shared) / max(1, min(len(first_cells), len(second_cells)))
                same_entry = routes_by_id[first].waypoints[0] == routes_by_id[second].waypoints[0]
                same_exit = routes_by_id[first].waypoints[-1] == routes_by_id[second].waypoints[-1]
                if overlap >= 0.35 or (overlap >= 0.15 and (same_entry or same_exit)):
                    disjoint["union"](first, second)
        roots = {disjoint["find"](route_id): index for index, route_id in enumerate(sorted({disjoint["find"](item) for item in route_ids}))}
        return {route_id: f"lane-{roots[disjoint['find'](route_id)] + 1:02d}" for route_id in route_ids}

    @staticmethod
    def _lanes(
        route_ids,
        route_cells,
        exact_route_cells,
        route_block_tiles,
        lane_for_route,
        spawn_counts,
    ) -> tuple[LaneUnderstanding, ...]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for route_id in route_ids:
            grouped[lane_for_route[route_id]].append(route_id)
        output = []
        for lane_id in sorted(grouped):
            route_ids_in_lane = tuple(sorted(grouped[lane_id]))
            cells = tuple(sorted({cell for route_id in route_ids_in_lane for cell in route_cells[route_id]}))
            block_tiles = tuple(sorted({
                tile
                for route_id in route_ids_in_lane
                for tile in route_block_tiles[route_id]
            }))
            blockable_route_ids = tuple(
                route_id for route_id in route_ids_in_lane if route_block_tiles[route_id]
            )
            non_blockable_route_ids = tuple(
                route_id for route_id in route_ids_in_lane if not route_block_tiles[route_id]
            )
            if blockable_route_ids and not non_blockable_route_ids:
                actionability = "BLOCKABLE_LANE"
            elif blockable_route_ids:
                actionability = "PARTIALLY_BLOCKABLE_LANE"
            elif any(exact_route_cells[route_id] for route_id in route_ids_in_lane):
                actionability = "NON_BLOCKABLE_PRE_CONTACT_DAMAGE_REQUIRED"
            else:
                actionability = "NO_EXACT_TILE_INTERSECTION"
            output.append(LaneUnderstanding(
                lane_id=lane_id,
                route_ids=route_ids_in_lane,
                cells=cells,
                entry_points=tuple(sorted({route_cells[route_id][0] for route_id in route_ids_in_lane if route_cells[route_id]})),
                exit_points=tuple(sorted({route_cells[route_id][-1] for route_id in route_ids_in_lane if route_cells[route_id]})),
                spawn_count=sum(spawn_counts[route_id] for route_id in route_ids_in_lane),
                blockable=bool(blockable_route_ids),
                block_tiles=block_tiles,
                blockable_route_ids=blockable_route_ids,
                non_blockable_route_ids=non_blockable_route_ids,
                actionability=actionability,
            ))
        return tuple(output)

    @staticmethod
    def _relationships(routes_by_id, route_cells) -> tuple[RouteRelationship, ...]:
        output = []
        route_ids = sorted(routes_by_id)
        for index, first in enumerate(route_ids):
            for second in route_ids[index + 1:]:
                first_cells, second_cells = set(route_cells[first]), set(route_cells[second])
                shared = tuple(sorted(first_cells & second_cells))
                overlap = len(shared) / max(1, min(len(first_cells), len(second_cells)))
                same_entry = routes_by_id[first].waypoints[0] == routes_by_id[second].waypoints[0]
                same_exit = routes_by_id[first].waypoints[-1] == routes_by_id[second].waypoints[-1]
                relationship = "DISJOINT"
                if shared:
                    if same_entry and not same_exit:
                        relationship = "DIVERGENT"
                    elif not same_entry and same_exit:
                        relationship = "CONVERGENT"
                    else:
                        relationship = "OVERLAPPING"
                output.append(RouteRelationship(first, second, shared, overlap, relationship))
        return tuple(output)

    @staticmethod
    def _interception_points(route_cells, ground, spawn_counts) -> tuple[tuple[int, int], ...]:
        ground_set = set(ground)
        scores: dict[tuple[int, int], float] = defaultdict(float)
        for route_id, cells in route_cells.items():
            for cell in cells:
                if cell in ground_set:
                    scores[cell] += 1.0 + min(3.0, spawn_counts[route_id] / 10.0)
        return tuple(sorted(scores, key=lambda item: (-scores[item], item))[:16])

    @staticmethod
    def _coverage_opportunities(fixture, route_cells) -> tuple[CoverageOpportunity, ...]:
        stage = fixture.stage
        route_sets = {route_id: set(cells) for route_id, cells in route_cells.items()}
        transformer = ApproximateRealRangeTransformer()
        opportunities = []
        for tile in stage.stage_map.tiles:
            if not tile.buildable:
                continue
            kind = tile.tile_kind
            operator_ids = []
            covered = set()
            for operator_id, operator in fixture.operators.items():
                expected_kind = "GROUND" if operator.position.value == "MELEE" else "HIGH_GROUND"
                if kind != expected_kind:
                    continue
                best_for_operator = set()
                for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                    direction_coverage = transformer.covered_tiles(
                        origin=(tile.x, tile.y), offsets=operator.attack_range, direction=direction
                    ) & set().union(*route_sets.values()) if route_sets else set()
                    if len(direction_coverage) > len(best_for_operator):
                        best_for_operator = direction_coverage
                if best_for_operator:
                    operator_ids.append(operator_id)
                    covered |= best_for_operator
            covered_routes = tuple(sorted(route_id for route_id, cells in route_sets.items() if cells & covered))
            if covered_routes:
                opportunities.append(CoverageOpportunity(
                    tile=(tile.x, tile.y), tile_kind=kind, route_ids=covered_routes,
                    covered_cells=tuple(sorted(covered)), operator_ids=tuple(sorted(operator_ids)),
                    shared=len(covered_routes) > 1,
                    score=float(len(covered_routes) * 10 + len(covered)),
                ))
        return tuple(sorted(opportunities, key=lambda item: (-item.score, item.tile))[:32])

    @staticmethod
    def _waves(spawn_timeline) -> tuple[WaveUnderstanding, ...]:
        grouped: dict[int, list] = defaultdict(list)
        for spawn in spawn_timeline:
            grouped[spawn.wave_index].append(spawn)
        output = []
        for wave_index in sorted(grouped):
            rows = grouped[wave_index]
            output.append(WaveUnderstanding(
                wave_index=wave_index,
                fragment_count=len({row.fragment_index for row in rows}),
                spawn_count=sum(int(row.count) for row in rows),
                start_time=min(row.time for row in rows),
                end_time=max(row.time + (int(row.count) - 1) * row.interval for row in rows),
                route_ids=tuple(sorted({row.route_id for row in rows})),
                enemy_ids=tuple(sorted({row.enemy_id for row in rows})),
            ))
        return tuple(output)

    @staticmethod
    def _expanded_spawns(spawn_timeline) -> list[dict[str, Any]]:
        output = []
        for spawn in spawn_timeline:
            for index in range(int(spawn.count)):
                output.append({
                    "time": float(spawn.time + index * spawn.interval),
                    "route_id": spawn.route_id,
                    "enemy_id": spawn.enemy_id,
                    "wave_index": spawn.wave_index,
                })
        return sorted(output, key=lambda item: (item["time"], item["route_id"], item["enemy_id"]))

    @classmethod
    def _pressure_windows(cls, expanded_spawns) -> tuple[PressureWindow, ...]:
        if not expanded_spawns:
            return ()
        times = [item["time"] for item in expanded_spawns]
        start, end = min(times), max(times)
        boundaries = [start, start + (end - start) / 3, start + 2 * (end - start) / 3, end]
        phases = ("EARLY", "MIDDLE", "LATE")
        phase_rows: list[list[dict[str, Any]]] = []
        output = []
        for index, phase in enumerate(phases):
            lower, upper = boundaries[index], boundaries[index + 1]
            rows = [item for item in expanded_spawns if lower <= item["time"] <= upper or (index == 2 and item["time"] == end)]
            phase_rows.append(rows)
        counts = [len(rows) for rows in phase_rows]
        average = mean(counts)
        spread = pstdev(counts) if len(counts) > 1 else 0.0
        for index, phase in enumerate(phases):
            rows = phase_rows[index]
            lower, upper = boundaries[index], boundaries[index + 1]
            route_ids = tuple(sorted({item["route_id"] for item in rows}))
            output.append(PressureWindow(
                window_id=f"{phase.lower()}-pressure",
                phase=phase,
                start_time=float(lower),
                end_time=float(upper),
                route_ids=route_ids,
                enemy_ids=tuple(sorted({item["enemy_id"] for item in rows})),
                spawn_count=len(rows),
                simultaneous_lane_count=len(route_ids),
                high_risk=len(rows) >= max(2.0, average + spread) or len(route_ids) > 1,
                evidence=f"{len(rows)} expanded spawns on {len(route_ids)} active route records",
                provenance="Approximate spawn schedule derived from GameData wave fragments",
            ))
        return tuple(output)

    @staticmethod
    def _enemy_archetypes(fixture, expanded_spawns) -> tuple[EnemyArchetype, ...]:
        counts: dict[str, int] = defaultdict(int)
        for item in expanded_spawns:
            counts[item["enemy_id"]] += 1
        output = []
        for enemy_id in sorted(counts):
            enemy = fixture.enemies[enemy_id]
            stats = enemy.stats
            hp, atk, defense = float(stats.max_hp.value or 0), float(stats.atk.value or 0), float(stats.defense.value or 0)
            resistance, speed = float(stats.magic_resistance.value or 0), float(stats.move_speed.value or 0)
            tags = []
            if hp >= 5000:
                tags.append("HIGH_HP")
            if defense >= 300:
                tags.append("HIGH_DEFENSE")
            if atk >= 500:
                tags.append("HIGH_ATTACK")
            if speed >= 1.2:
                tags.append("FAST")
            output.append(EnemyArchetype(enemy_id, counts[enemy_id], hp, atk, defense, resistance, speed, stats.attack_range.value, tuple(tags)))
        return tuple(output)

    @staticmethod
    def _physical_pressure(enemy_archetypes) -> dict[str, Any]:
        return {
            "max_attack": max((item.atk for item in enemy_archetypes), default=0.0),
            "max_defense": max((item.defense for item in enemy_archetypes), default=0.0),
            "high_defense_enemy_count": sum(item.defense >= 300 for item in enemy_archetypes),
            "classification": "HIGH_DEFENSIVE_PRESSURE" if any(item.defense >= 300 for item in enemy_archetypes) else "STANDARD",
            "boundary": "Enemy attack damage type is not represented; these are source-stat aggregates, not exact damage-type claims",
        }

    @staticmethod
    def _arts_pressure(enemy_archetypes) -> dict[str, Any]:
        return {
            "low_resistance_high_defense_enemy_count": sum(item.defense >= 300 and item.magic_resistance <= 20 for item in enemy_archetypes),
            "classification": "ARTS_MAY_BE_EFFECTIVE" if any(item.defense >= 300 and item.magic_resistance <= 20 for item in enemy_archetypes) else "NOT_INDICATED",
            "status": "HYPOTHESIZED_FROM_DEFENSE_AND_RESISTANCE",
        }

    @staticmethod
    def _blocking_pressure(lanes, pressure_windows, enemy_archetypes) -> dict[str, Any]:
        simultaneous = max((window.simultaneous_lane_count for window in pressure_windows), default=0)
        fast_count = sum(item.spawn_count for item in enemy_archetypes if "FAST" in item.threat_tags)
        blockable_lanes = tuple(lane for lane in lanes if lane.blockable)
        return {
            "lane_count": len(blockable_lanes),
            "topological_lane_count": len(lanes),
            "blockable_lane_ids": tuple(lane.lane_id for lane in blockable_lanes),
            "non_blockable_lane_ids": tuple(lane.lane_id for lane in lanes if not lane.blockable),
            "max_simultaneous_route_records": simultaneous,
            "fast_enemy_count": fast_count,
            "classification": "DUAL_LANE_PRESSURE" if len(blockable_lanes) >= 2 else "SINGLE_LANE_PRESSURE",
        }

    @staticmethod
    def _sustain_pressure(enemy_archetypes, operators) -> dict[str, Any]:
        max_enemy_atk = max((item.atk for item in enemy_archetypes), default=0.0)
        blocker_hp = max((float(operator.phases[0].stats_max.max_hp.value or 0) for operator in operators.values()), default=0.0)
        return {
            "max_enemy_attack": max_enemy_atk,
            "highest_available_blocker_hp": blocker_hp,
            "classification": "SUSTAIN_RISK" if blocker_hp and max_enemy_atk * 10 >= blocker_hp else "STANDARD",
            "boundary": "Derived from source stats; exact enemy attack timing and damage type remain approximated",
        }


def derive_tactical_requirements(understanding: StageUnderstanding) -> tuple[TacticalRequirementModel, ...]:
    requirements = []
    early = next((window for window in understanding.pressure_windows if window.phase == "EARLY"), None)
    high_risk_windows = tuple(window for window in understanding.pressure_windows if window.high_risk)
    requirements.append(TacticalRequirementModel(
        "R-EARLY-DEPLOY", "EARLY_CHEAP_DEPLOYMENT",
        f"first pressure at {early.start_time if early else 0:.1f}s; initial DP {understanding.initial_dp}",
        early.window_id if early else "no-spawn", tuple(route.route_id for route in understanding.routes),
        "HYPOTHESIZED", 0.8,
        "EARLY_DEPLOYMENT", "StageUnderstanding.dp_economy_pressure",
    ))
    blockable_lanes = tuple(lane for lane in understanding.lanes if lane.blockable)
    non_blockable_lanes = tuple(lane for lane in understanding.lanes if not lane.blockable)
    blockable_route_ids = tuple(
        route_id
        for lane in blockable_lanes
        for route_id in lane.blockable_route_ids
    )
    if understanding.blocking_pressure["lane_count"] <= 1:
        requirements.append(TacticalRequirementModel(
            "R-SINGLE-LANE", "SINGLE_LANE_BLOCKING", "one lane cluster contains all active route records",
            early.window_id if early else "no-spawn", blockable_route_ids,
            "HYPOTHESIZED", 0.85, "BLOCK", "StageUnderstanding.lanes",
        ))
    else:
        requirements.append(TacticalRequirementModel(
            "R-DUAL-LANE", "DUAL_LANE_BLOCKING", f"{len(blockable_lanes)} exactly blockable lane clusters and simultaneous pressure detected",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            blockable_route_ids,
            "HYPOTHESIZED", 0.8, "BLOCK", "StageUnderstanding.blocking_pressure",
        ))
    for lane in non_blockable_lanes:
        requirements.append(TacticalRequirementModel(
            f"R-PRE-CONTACT-{lane.lane_id.upper()}", "PRE_CONTACT_DAMAGE",
            f"{lane.lane_id} has no exact legal ground interception tile; enemies must be damaged before exit or contact-free",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            lane.route_ids, "HYPOTHESIZED", 0.75, "RANGED_DPS",
            "StageUnderstanding.tactical_actionability",
        ))
    if understanding.coverage_opportunities:
        requirements.append(TacticalRequirementModel(
            "R-RANGED-DPS", "RANGED_DPS", f"{len(understanding.coverage_opportunities)} ranked legal coverage opportunities",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            tuple(sorted({route for item in understanding.coverage_opportunities for route in item.route_ids})),
            "SOFT", 0.75, "RANGED_DPS", "StageUnderstanding.coverage_opportunities",
        ))
    shared = tuple(item for item in understanding.coverage_opportunities if item.shared)
    if shared:
        requirements.append(TacticalRequirementModel(
            "R-SHARED-COVERAGE", "MULTI_LANE_RANGED_COVERAGE", f"{len(shared)} tiles cover multiple active route records",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            tuple(sorted({route for item in shared for route in item.route_ids})), "HYPOTHESIZED", 0.7,
            "MULTI_LANE_COVERAGE", "StageUnderstanding.coverage_opportunities",
        ))
    if understanding.arts_pressure["classification"] == "ARTS_MAY_BE_EFFECTIVE":
        requirements.append(TacticalRequirementModel(
            "R-ARTS", "ARTS_DAMAGE", "high-defense and low-resistance enemy archetypes are present",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            tuple(route.route_id for route in understanding.routes), "HYPOTHESIZED", 0.65,
            "ARTS_DAMAGE", "StageUnderstanding.arts_pressure",
        ))
    if understanding.sustain_pressure["classification"] == "SUSTAIN_RISK":
        requirements.append(TacticalRequirementModel(
            "R-SUSTAIN", "HEALING_SUSTAIN", "enemy attack aggregate is high relative to available blocker HP",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            tuple(route.route_id for route in understanding.routes), "HYPOTHESIZED", 0.6,
            "HEAL", "StageUnderstanding.sustain_pressure",
        ))
    if understanding.interception_points:
        requirements.append(TacticalRequirementModel(
            "R-INTERCEPT", "STALL_INTERCEPTION", f"{len(understanding.interception_points)} legal route-crossing ground tiles",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            blockable_route_ids, "SOFT", 0.75,
            "BLOCK", "StageUnderstanding.interception_points",
        ))
    if understanding.spawn_count >= 8 or any(window.high_risk for window in understanding.pressure_windows):
        requirements.append(TacticalRequirementModel(
            "R-BLOCK-CAPACITY", "SUFFICIENT_BLOCK_CAPACITY",
            f"{understanding.spawn_count} expanded spawns and high-risk pressure windows require spare block capacity",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            blockable_route_ids, "HYPOTHESIZED", 0.7,
            "BLOCK_CAPACITY", "StageUnderstanding.pressure_windows",
        ))
    if len(understanding.deployable_high_ground) <= 2 and understanding.spawn_count >= 8:
        requirements.append(TacticalRequirementModel(
            "R-MELEE-DPS", "MELEE_DPS",
            f"only {len(understanding.deployable_high_ground)} legal high-ground tiles exist for {understanding.spawn_count} spawns",
            high_risk_windows[0].window_id if high_risk_windows else "all-pressure",
            tuple(route.route_id for route in understanding.routes), "HYPOTHESIZED", 0.65,
            "MELEE_DPS", "StageUnderstanding.deployable_high_ground",
        ))
    return tuple(requirements)
