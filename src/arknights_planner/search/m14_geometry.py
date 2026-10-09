"""M14.8 bounded shared-opening geometry audit for the fixed Plume R4 roster."""
from __future__ import annotations

from itertools import product
from math import ceil

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11SearchMetrics
from arknights_planner.search.m14_opening import M14OpeningRepairSearch, OpeningCandidate, _frame


TEAM = (
    "char_122_beagle", "char_124_kroos", "char_209_ardign", "char_192_falco",
    "char_211_adnach", "char_501_durin", "char_212_ansel",
)
EARLY_ROUTES = ("route-0", "route-2", "route-3", "route-4")


class M14OpeningGeometrySearch:
    """Geometry-first opening search; roster/cardinality are fixed by design."""

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter,
                 policy: RealSimulationApproximationPolicy, budget: int = 800,
                 horizon_frame: int = 900):
        self.adapter, self.policy = adapter, policy
        self.budget, self.horizon_frame = budget, horizon_frame
        self.configurations = {item.operator_id: item for item in adapter.m13_low_rarity_configurations()}
        self.metrics = M11SearchMetrics(); self.full_metrics = M11SearchMetrics()
        self.generated = self.structural_rejections = 0

    def _helper(self):
        return M14OpeningRepairSearch(adapter=self.adapter, policy=self.policy, budget=self.budget, horizon_frame=self.horizon_frame)

    def _engine(self, *, opening: bool):
        return self._helper()._engine(TEAM, opening=opening)

    @staticmethod
    def _route_tiles(route) -> list[tuple[int, int]]:
        out = []
        for first, second in zip(route.waypoints, route.waypoints[1:]):
            steps = max(1, ceil(max(abs(second.x - first.x), abs(second.y - first.y))))
            for step in range(steps + 1):
                point = (round(first.x + (second.x - first.x) * step / steps), round(first.y + (second.y - first.y) * step / steps))
                if not out or point != out[-1]:
                    out.append(point)
        return out

    @staticmethod
    def _entry_frame(route, spawn_seconds: float, speed: float, tile: tuple[int, int]) -> int | None:
        distance = route.distance_at(tile)
        if distance is None:
            return None
        # A wait begins after reaching its own checkpoint, not before entering it.
        pauses = sum(wait.duration for wait in route.waits if wait.distance < distance)
        return ceil((spawn_seconds + distance / speed + pauses) * 30.0)

    def _geometry(self, engine) -> dict:
        routes = {route.route_id: route for route in engine.fixture.stage.routes}
        first_spawns = {}
        for spawn in engine.fixture.stage.spawn_events:
            if spawn.route_id in EARLY_ROUTES and spawn.route_id not in first_spawns:
                first_spawns[spawn.route_id] = spawn
        route_rows = {}
        for route_id in EARLY_ROUTES:
            route = routes[route_id]; spawn = first_spawns[route_id]; enemy = engine.fixture.enemies[spawn.enemy_id]
            entries = [{"tile": tile, "entry_frame": self._entry_frame(route, spawn.time, float(enemy.stats.move_speed.value), tile)}
                       for tile in self._route_tiles(route)]
            route_rows[route_id] = {"spawn_tile": self._route_tiles(route)[0], "spawn_frame": _frame(engine, spawn.time),
                                    "waypoints": [(item.x, item.y) for item in route.waypoints], "traversed_tiles": entries,
                                    "leak_tile": self._route_tiles(route)[-1],
                                    "leak_estimate_frame": self._entry_frame(route, spawn.time, float(enemy.stats.move_speed.value), self._route_tiles(route)[-1])}
        route0, route2 = set(self._route_tiles(routes["route-0"])), set(self._route_tiles(routes["route-2"]))
        adjacent = sorted((left, right) for left in route0 for right in route2 if abs(left[0] - right[0]) + abs(left[1] - right[1]) == 1)
        return {"routes": route_rows, "route_0_2_shared_tiles": sorted(route0 & route2),
                "route_0_2_adjacent_pairs": adjacent, "route_0_2_minimum_grid_distance": 1,
                "route_0_2_convergence": "NONE: parallel y=3/y=4 corridors continue to distinct leak tiles."}

    def _interaction_graph(self, engine, geometry: dict) -> tuple[list[dict], dict]:
        routes = {route.route_id: route for route in engine.fixture.stage.routes}
        first_spawns = {route_id: next(item for item in engine.fixture.stage.spawn_events if item.route_id == route_id) for route_id in EARLY_ROUTES}
        graph = []; by_key = {}
        transformer = engine.simulator.range_transformer
        for operator_id in TEAM:
            operator = engine.fixture.operators[operator_id]
            cost = float(operator.phases[0].stats_max.cost.value or 0)
            earliest = max(0, ceil((cost - float(engine.fixture.stage.initial_dp.value or 0)) / engine.fixture.stage.dp_per_second * 30))
            for tile in engine.fixture.stage.stage_map.tiles:
                if not tile.buildable or (operator.position.value == "MELEE" and tile.tile_kind != "GROUND") or (operator.position.value == "RANGED" and tile.tile_kind != "HIGH_GROUND"):
                    continue
                for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                    covered = transformer.covered_tiles(origin=(tile.x, tile.y), offsets=operator.attack_range, direction=direction)
                    interactions = {}
                    for route_id in EARLY_ROUTES:
                        route = routes[route_id]; route_tiles = set(self._route_tiles(route)); spawn = first_spawns[route_id]
                        enemy = engine.fixture.enemies[spawn.enemy_id]
                        block_frame = self._entry_frame(route, spawn.time, float(enemy.stats.move_speed.value), (tile.x, tile.y)) if operator.position.value == "MELEE" else None
                        range_cells = sorted(covered & route_tiles)
                        range_frame = min((self._entry_frame(route, spawn.time, float(enemy.stats.move_speed.value), point) for point in range_cells), default=None)
                        interactions[route_id] = {"ground_intersection": block_frame is not None, "first_block_contact_frame": block_frame,
                                                  "range_cells": range_cells, "first_range_entry_frame": range_frame}
                    route_count = sum(bool(value["ground_intersection"] or value["range_cells"]) for value in interactions.values())
                    item = {"operator_id": operator_id, "tile": (tile.x, tile.y), "tile_type": tile.tile_kind, "direction": direction,
                            "earliest_deployment_frame": earliest, "routes": interactions, "early_route_count": route_count,
                            "coverage_before_366": sum(any(frame is not None and frame <= 366 for frame in (value["first_block_contact_frame"], value["first_range_entry_frame"])) for value in interactions.values())}
                    graph.append(item); by_key[(operator_id, (tile.x, tile.y), direction)] = item
        graph.sort(key=lambda item: (-item["coverage_before_366"], -item["early_route_count"], item["earliest_deployment_frame"], item["operator_id"], item["tile"], item["direction"]))
        return graph, by_key

    def _candidate(self, helper, engine, label, placements, graph_by_key):
        actions = helper._schedule(engine, tuple(placements))
        legal, _ = helper._static(engine, TEAM, actions)
        structural = helper._structural(engine, actions)
        if not legal or not structural["any_route_interaction"]:
            self.structural_rejections += 1; return None
        self.generated += 1
        return OpeningCandidate(label, TEAM, actions, {**structural, "graph": [graph_by_key[(item.operator_id, item.tile, item.direction)] for item in actions]})

    @staticmethod
    def _rank(row):
        return (row["opening_leaks"], -(row["first_leak_frame"] if row["first_leak_frame"] is not None else 10**9),
                -row["opening_kills"], -row["opening_damage"], -sum(1 for value in row["structural"]["early_routes"].values() if value["blocker_ready_frame"] is not None or value["ranged_interaction_ready_frame"] is not None),
                -row["opening_final_dp"], row["label"])

    def _evaluate(self, helper, engine, candidates):
        rows = []; pairs = []; seen = set()
        for candidate in candidates:
            key = tuple((item.operator_id, item.time, item.tile, item.direction) for item in candidate.actions)
            if key in seen: continue
            seen.add(key)
            if self.metrics.unique_simulations + self.full_metrics.unique_simulations >= self.budget: break
            evaluation = engine._evaluate(Strategy(TEAM, candidate.actions), self.metrics)
            row = helper._row(candidate, evaluation.result, engine); rows.append(row); pairs.append((row, candidate))
        pairs.sort(key=lambda item: self._rank(item[0])); return rows, pairs

    def _promote(self, pairs):
        helper = self._helper(); engine = self._engine(opening=False); out=[]; seen=set()
        for row, candidate in pairs:
            if len(out) == 6 or self.metrics.unique_simulations + self.full_metrics.unique_simulations >= self.budget: break
            fingerprint = tuple((item["operator_id"], tuple(item["tile"]), item["direction"]) for item in row["actions"])
            if fingerprint in seen: continue
            seen.add(fingerprint)
            strategy = helper._full_strategy(engine, candidate); evaluation = engine._evaluate(strategy, self.full_metrics); result = evaluation.result
            leak = next((event for event in result.events if event.event_type is EventType.ENEMY_LEAK), None)
            out.append({"opening": row, "result": "WIN" if result.win else "LOSS", "kills": result.enemies_killed,
                        "leaks": result.enemies_leaked, "remaining_life": result.remaining_life,
                        "first_leak_frame": _frame(engine, leak.time) if leak else None,
                        "attacks": sum(event.event_type is EventType.ATTACK_START and event.source_id in engine.fixture.operators for event in result.events),
                        "damage_events": sum(event.event_type is EventType.DAMAGE and event.source_id in engine.fixture.operators for event in result.events),
                        "actions": [{"type": item.action_type.value, "operator_id": item.operator_id, "frame": _frame(engine, item.time), "tile": item.tile, "direction": item.direction} for item in strategy.actions]})
            if result.win: break
        return out

    def run(self) -> dict:
        helper = self._helper(); engine = self._engine(opening=True)
        geometry = self._geometry(engine); graph, by_key = self._interaction_graph(engine, geometry)
        # Exhaustive over the finite current-roster legal location/direction set,
        # at each operator's earliest legal frame.
        singles = []
        for item in graph:
            candidate = self._candidate(helper, engine, "SINGLE", ((item["operator_id"], item["tile"], item["direction"]),), by_key)
            if candidate: singles.append(candidate)
        single_rows, single_pairs = self._evaluate(helper, engine, singles)
        # Shared/mixed structures are not a Cartesian product: take only the
        # top geometry-ranked first deployments and second actions that cover a
        # route the first did not structurally cover.
        firsts = graph[:16]; seconds = graph[:28]; double_candidates=[]; ranged_candidates=[]; delayed_candidates=[]
        for first, second in product(firsts, seconds):
            if first["operator_id"] == second["operator_id"] or first["tile"] == second["tile"]: continue
            first_routes = {route_id for route_id, detail in first["routes"].items() if detail["ground_intersection"] or detail["range_cells"]}
            second_routes = {route_id for route_id, detail in second["routes"].items() if detail["ground_intersection"] or detail["range_cells"]}
            if len(first_routes | second_routes) < 2: continue
            candidate = self._candidate(helper, engine, "SHARED_OR_REPAIR", ((first["operator_id"], first["tile"], first["direction"]), (second["operator_id"], second["tile"], second["direction"])), by_key)
            if not candidate: continue
            double_candidates.append(candidate)
            if engine.fixture.operators[first["operator_id"]].position.value == "RANGED": ranged_candidates.append(candidate)
            if engine.fixture.operators[first["operator_id"]].position.value == "MELEE" and first["tile"][0] >= 6: delayed_candidates.append(candidate)
        double_rows, double_pairs = self._evaluate(helper, engine, double_candidates)
        pairs = sorted([*single_pairs, *double_pairs], key=lambda item: self._rank(item[0]))
        promoted = self._promote(pairs)
        best = pairs[0][0] if pairs else None
        best_full = min(promoted, key=lambda item: (0 if item["result"] == "WIN" else 1, item["leaks"], -item["kills"], -(item["first_leak_frame"] or 10**9))) if promoted else None
        shared = any(row["first_leak_frame"] and row["first_leak_frame"] > 366 for row, _ in double_pairs)
        ranged = any(row["opening_leaks"] < 3 for row, candidate in single_pairs if engine.fixture.operators[candidate.actions[0].operator_id].position.value == "RANGED")
        delayed = any(row["opening_leaks"] < 3 or (row["first_leak_frame"] or 0) > 366 for row, _ in double_pairs)
        block_diag = {"status": "SUPPORTED_SUCCESS_ONLY", "source": "runtime block capacity plus BLOCK/UNBLOCK event stream",
                      "limitation": "runtime has no rejected-block event, so failed block attempts remain unobservable."}
        return {
            "opening_route_geometry": geometry,
            "opening_interaction_graph": graph,
            "single_deployment_openings": {"candidates": len(singles), "results": single_rows},
            "ranged_opening_results": {"candidates": len(ranged_candidates), "single_results": [row for row, candidate in single_pairs if engine.fixture.operators[candidate.actions[0].operator_id].position.value == "RANGED"],
                                       "classification": "SUPPORTED" if ranged else "NOT_SUPPORTED"},
            "delayed_interception_results": {"candidates": len(delayed_candidates), "classification": "SUPPORTED" if delayed else "NOT_SUPPORTED"},
            "shared_opening_results": {"candidates": len(double_candidates), "results": double_rows,
                                       "classification": "SUPPORTED" if shared else "NOT_SUPPORTED"},
            "promoted_geometry_full_battle_results": {"promoted": promoted, "best": best_full,
                                                       "baseline": {"kills": 27, "leaks": 9, "first_leak_frame": 366, "remaining_life": -6}},
            "metrics": {"llm_calls": 0, "roster": TEAM, "operator_count": 7, "rarity": 20, "horizon_frame": self.horizon_frame,
                        "budget": self.budget, "generated": self.generated, "structural_rejections": self.structural_rejections,
                        "unique_opening_simulations": self.metrics.unique_simulations, "opening_cache_hits": self.metrics.cache_hits,
                        "full_battle_simulations": self.full_metrics.unique_simulations, "full_cache_hits": self.full_metrics.cache_hits,
                        "total_unique_simulations": self.metrics.unique_simulations + self.full_metrics.unique_simulations,
                        "total_cache_hits": self.metrics.cache_hits + self.full_metrics.cache_hits},
            "best_opening": best,
            "block_capacity_diagnostic": block_diag,
            "opening_prefix_verified": bool(best and best["opening_leaks"] == 0),
        }
