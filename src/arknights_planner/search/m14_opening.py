"""M14.6 bounded opening-feasibility audit for the fixed R4 K=7 structure.

This is intentionally narrower than :mod:`m14_repair`: it searches only the
opening (default frame 0..900), keeps the R4 operator count fixed, and uses
the full simulator only for a few opening structures that demonstrably improve
the early loss.  It makes no LLM calls and is not a minimisation search.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import ceil

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.simulation import EventType, SimulationResult
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig, M11SearchMetrics
from arknights_planner.simulator import ApproximateRealRangeTransformer, SimulationConfig


R4_IDS = (
    "char_122_beagle", "char_124_kroos", "char_209_ardign",
    "char_210_stward", "char_211_adnach", "char_501_durin", "char_212_ansel",
)
R4_PARENT_ORDER = R4_IDS
R4_PARENT_PLACEMENTS = {
    "char_122_beagle": ((2, 4), "DOWN"),
    "char_124_kroos": ((4, 1), "DOWN"),
    "char_209_ardign": ((2, 3), "DOWN"),
    "char_210_stward": ((6, 6), "UP"),
    "char_211_adnach": ((4, 2), "DOWN"),
    "char_501_durin": ((6, 5), "UP"),
    "char_212_ansel": ((4, 5), "UP"),
}
R4_PARENT_FRAMES = {
    "char_122_beagle": 240, "char_124_kroos": 600, "char_209_ardign": 1170,
    "char_210_stward": 1740, "char_211_adnach": 2100, "char_501_durin": 2490,
    "char_212_ansel": 3030,
}


@dataclass(frozen=True)
class OpeningCandidate:
    label: str
    team: tuple[str, ...]
    actions: tuple[Action, ...]
    structural: dict


def _frame(engine: M11MinimumSquadSearch, seconds) -> int:
    return engine.config.frame_clock.frame_for_seconds(seconds)


def _arrival_frame(seconds: float) -> int:
    """Continuous route-arrival estimate rounded up to its first usable frame."""
    return ceil(seconds * 30.0)


def _first(result: SimulationResult, kind: EventType):
    return next((event for event in result.events if event.event_type is kind), None)


class M14OpeningRepairSearch:
    """Opening-only repair followed by a handful of full R4 evaluations."""

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter,
                 policy: RealSimulationApproximationPolicy, budget: int = 500,
                 horizon_frame: int = 900):
        self.adapter, self.policy = adapter, policy
        self.budget, self.horizon_frame = budget, horizon_frame
        self.configurations = {item.operator_id: item for item in adapter.m13_low_rarity_configurations()}
        self.opening_metrics = M11SearchMetrics()
        self.full_metrics = M11SearchMetrics()
        self.generated = self.structural_rejections = 0

    def _engine(self, team: tuple[str, ...], *, opening: bool) -> M11MinimumSquadSearch:
        return M11MinimumSquadSearch(
            adapter=self.adapter, stage_id_or_code="6-8", policy=self.policy,
            operator_pool=tuple(self.configurations[item] for item in team),
            config=M11SearchConfig(
                max_squad_size=len(team), max_teams=1, placement_options_per_operator=48,
                beam_width=2,
                simulation_config=SimulationConfig(dt=0.2, max_time=(float(self.horizon_frame) / 30.0 if opening else 300.0)),
            ),
        )

    def _early_routes(self, engine: M11MinimumSquadSearch) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.route_id for item in engine.fixture.stage.spawn_events
                                   if _frame(engine, item.time) <= self.horizon_frame))

    def _route_cells(self, route) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for first, second in zip(route.waypoints, route.waypoints[1:]):
            steps = max(1, ceil(max(abs(second.x - first.x), abs(second.y - first.y))))
            for step in range(steps + 1):
                cells.add((round(first.x + (second.x - first.x) * step / steps),
                           round(first.y + (second.y - first.y) * step / steps)))
        return cells

    def _placement_options(self, engine: M11MinimumSquadSearch, operator_id: str) -> tuple[tuple[tuple[int, int], str], ...]:
        """Small geometry-derived opening set: route-row blockers and two ranged lanes."""
        operator = engine.fixture.operators[operator_id]
        if operator.position.value == "MELEE":
            wanted = {(4, 3), (4, 4), (6, 3), (6, 4)}
            found = []
            seen: set[tuple[int, int]] = set()
            for item in engine.deployment_options():
                if item.operator_id != operator_id or item.tile not in wanted or item.tile in seen:
                    continue
                # A defender's base range is its own tile, so its four facing
                # values are spatially equivalent here. Keep one stable
                # representative rather than spending opening budget on them.
                found.append((item.tile, item.direction)); seen.add(item.tile)
        else:
            found = []
            seen: set[tuple[int, int]] = set()
            for item in engine.deployment_options():
                if item.operator_id != operator_id or item.tile in seen:
                    continue
                found.append((item.tile, item.direction)); seen.add(item.tile)
                if len(found) == 2:
                    break
        return tuple(dict.fromkeys(found))

    def _schedule(self, engine: M11MinimumSquadSearch,
                  ordered: tuple[tuple[str, tuple[int, int], str], ...], *, delay: int = 0) -> tuple[Action, ...]:
        dp = float(engine.fixture.stage.initial_dp.value or 0)
        rate = float(engine.fixture.stage.dp_per_second)
        current_frame = 0
        actions: list[Action] = []
        for operator_id, tile, direction in ordered:
            cost = float(engine.fixture.operators[operator_id].phases[0].stats_max.cost.value or 0)
            # Actions cannot share a frame, but natural DP accrues during that
            # one-frame separation. Account for it before finding the next
            # exact legal deployment frame.
            next_frame = current_frame + (1 if actions else 0)
            dp += rate * (next_frame - current_frame) / 30.0
            required_frames = ceil(max(0.0, cost - dp) / rate * 30.0) if rate else 10**9
            deploy_frame = max(next_frame + required_frames, delay)
            dp += rate * (deploy_frame - next_frame) / 30.0
            dp -= cost
            actions.append(Action(ActionType.DEPLOY, engine.config.frame_clock.seconds_for_frame(deploy_frame), operator_id, tile, direction))
            current_frame = deploy_frame
        return tuple(actions)

    def _static(self, engine: M11MinimumSquadSearch, team: tuple[str, ...], actions: tuple[Action, ...]) -> tuple[bool, str | None]:
        if len(actions) > int(engine.fixture.stage.deployment_limit.value or 0):
            return False, "DEPLOYMENT_LIMIT"
        if len({item.operator_id for item in actions}) != len(actions) or len({item.tile for item in actions}) != len(actions):
            return False, "DUPLICATE_DEPLOYMENT"
        dp = float(engine.fixture.stage.initial_dp.value or 0); prior = 0.0
        for action in actions:
            operator = engine.fixture.operators.get(action.operator_id)
            if action.operator_id not in team or operator is None:
                return False, "UNKNOWN_OPERATOR"
            if engine.simulator._deployment_tile_reason(operator, engine.fixture.stage, action.tile):
                return False, "ILLEGAL_TILE"
            dp += engine.fixture.stage.dp_per_second * (float(action.time) - prior); prior = float(action.time)
            cost = float(operator.phases[0].stats_max.cost.value or 0)
            if dp + 1e-9 < cost:
                return False, "INSUFFICIENT_DP"
            dp -= cost
        return True, None

    def _structural(self, engine: M11MinimumSquadSearch, actions: tuple[Action, ...]) -> dict:
        early_routes = self._early_routes(engine)
        routes = {route.route_id: route for route in engine.fixture.stage.routes}
        transformer = ApproximateRealRangeTransformer()
        report = {route_id: {"blocker_ready_frame": None, "ranged_interaction_ready_frame": None} for route_id in early_routes}
        for action in actions:
            operator = engine.fixture.operators[action.operator_id]
            action_frame = _frame(engine, action.time)
            coverage = transformer.covered_tiles(origin=action.tile, offsets=operator.attack_range, direction=action.direction)
            for route_id in early_routes:
                route = routes[route_id]
                if operator.position.value == "MELEE" and route.distance_at(action.tile) is not None:
                    old = report[route_id]["blocker_ready_frame"]
                    report[route_id]["blocker_ready_frame"] = action_frame if old is None else min(old, action_frame)
                if coverage & self._route_cells(route):
                    old = report[route_id]["ranged_interaction_ready_frame"]
                    report[route_id]["ranged_interaction_ready_frame"] = action_frame if old is None else min(old, action_frame)
        return {"early_routes": report, "any_route_interaction": any(
            item["blocker_ready_frame"] is not None or item["ranged_interaction_ready_frame"] is not None
            for item in report.values())}

    def _row(self, candidate: OpeningCandidate, result: SimulationResult, engine: M11MinimumSquadSearch) -> dict:
        events = result.events
        first_leak = _first(result, EventType.ENEMY_LEAK)
        damage = sum(float(dict(event.details).get("amount", 0)) for event in events
                     if event.event_type is EventType.DAMAGE and event.source_id in engine.fixture.operators)
        return {
            "label": candidate.label, "team": candidate.team,
            "actions": [{"type": action.action_type.value, "operator_id": action.operator_id,
                         "frame": _frame(engine, action.time), "tile": action.tile, "direction": action.direction}
                        for action in candidate.actions],
            "opening_result": "WIN" if result.win else "LOSS", "opening_kills": result.enemies_killed,
            "opening_leaks": result.enemies_leaked, "opening_damage": damage, "opening_final_dp": result.final_dp,
            "first_leak_frame": _frame(engine, first_leak.time) if first_leak else None,
            "attacks": sum(event.event_type is EventType.ATTACK_START and event.source_id in engine.fixture.operators for event in events),
            "structural": candidate.structural,
        }

    @staticmethod
    def _rank(row: dict) -> tuple:
        return (row["opening_leaks"], -(row["first_leak_frame"] if row["first_leak_frame"] is not None else 10**9),
                -row["opening_kills"], -row["opening_damage"], -row["opening_final_dp"], len(row["actions"]), row["label"])

    def _candidates(self, engine: M11MinimumSquadSearch, team: tuple[str, ...]) -> tuple[OpeningCandidate, ...]:
        ground = tuple(item for item in team if engine.fixture.operators[item].position.value == "MELEE")
        ranged = tuple(item for item in team if engine.fixture.operators[item].position.value == "RANGED" and item != "char_212_ansel")
        templates = [(item,) for item in (*ground, *ranged)]
        templates += [(ground[0], ground[1]), (ground[1], ground[0])]
        for attacker in ranged[:3]:
            templates += [(ground[0], attacker), (attacker, ground[0])]
        if "char_502_nblade" in team:
            cheap = "char_502_nblade"
            templates += [(cheap, ground[0]), (ground[0], cheap), (cheap, ranged[0]), (ranged[0], cheap)]
        out: list[OpeningCandidate] = []
        seen = set()
        for sequence in templates:
            options = [self._placement_options(engine, item) for item in sequence]
            if not all(options):
                continue
            for placement in product(*options):
                if len({tile for tile, _ in placement}) != len(placement):
                    continue
                ordered = tuple((operator_id, tile, direction) for operator_id, (tile, direction) in zip(sequence, placement))
                for delay in (0, 30):
                    actions = self._schedule(engine, ordered, delay=delay)
                    key = tuple((item.operator_id, item.time, item.tile, item.direction) for item in actions)
                    if key in seen:
                        continue
                    seen.add(key); self.generated += 1
                    legal, reason = self._static(engine, team, actions)
                    structural = self._structural(engine, actions)
                    if not legal or not structural["any_route_interaction"]:
                        self.structural_rejections += 1
                        continue
                    out.append(OpeningCandidate("->".join(sequence), team, actions, structural))
        return tuple(out)

    def _run_opening(self, engine: M11MinimumSquadSearch, candidates: tuple[OpeningCandidate, ...], *, limit: int) -> tuple[list[dict], list[OpeningCandidate]]:
        rows: list[dict] = []; usable: list[OpeningCandidate] = []
        for candidate in candidates:
            if self.opening_metrics.unique_simulations >= limit:
                break
            evaluation = engine._evaluate(Strategy(candidate.team, candidate.actions), self.opening_metrics)
            rows.append(self._row(candidate, evaluation.result, engine)); usable.append(candidate)
            if rows[-1]["opening_leaks"] == 0:
                # All remaining rows cannot improve the diagnostic opening objective.
                break
        return rows, usable

    def _dp_timeline(self, engine: M11MinimumSquadSearch, actions: tuple[Action, ...]) -> list[dict]:
        dp = float(engine.fixture.stage.initial_dp.value or 0); rate = float(engine.fixture.stage.dp_per_second); prior = 0
        rows = []
        for operator_id in R4_IDS:
            cost = float(engine.fixture.operators[operator_id].phases[0].stats_max.cost.value or 0)
            rows.append({"operator_id": operator_id, "cost": cost, "earliest_individual_legal_frame": max(0, ceil((cost - dp) / rate * 30))})
        actual = {item.operator_id: item for item in actions if item.action_type is ActionType.DEPLOY}
        for row in rows:
            action = actual.get(row["operator_id"])
            if action is None:
                row.update({"actual_deployment_frame": None, "dp_before": None, "dp_after": None})
                continue
            frame = _frame(engine, action.time); current = frame / 30.0
            dp += rate * (current - prior / 30.0); before = dp; dp -= row["cost"]; prior = frame
            row.update({"actual_deployment_frame": frame, "dp_before": before, "dp_after": dp})
        return rows

    def _arrival_report(self, engine: M11MinimumSquadSearch) -> dict:
        routes = {item.route_id: item for item in engine.fixture.stage.routes}
        records = []
        for spawn in engine.fixture.stage.spawn_events:
            if _frame(engine, spawn.time) > self.horizon_frame or spawn.route_id not in {"route-0", "route-2", "route-3", "route-4"}:
                continue
            enemy = engine.fixture.enemies[spawn.enemy_id]; route = routes[spawn.route_id]
            defence_tiles = [(4, int(route.waypoints[0].y)), (6, int(route.waypoints[0].y))]
            arrivals = []
            for tile in defence_tiles:
                distance = route.distance_at(tile)
                if distance is None:
                    continue
                pauses = sum(wait.duration for wait in route.waits if wait.distance <= distance)
                arrival = spawn.time + distance / float(enemy.stats.move_speed.value) + pauses
                arrival_frame = _arrival_frame(arrival)
                arrivals.append({"tile": tile, "arrival_frame": arrival_frame, "arrival_seconds": arrival,
                                 "earliest_r4_blocker_frame": 240, "opening_margin_frames": arrival_frame - 240})
            records.append({"enemy_id": spawn.enemy_id, "route_id": spawn.route_id,
                            "spawn_frame": _frame(engine, spawn.time), "arrivals": arrivals})
        return {"starting_dp": engine.fixture.stage.initial_dp.value, "dp_per_second": engine.fixture.stage.dp_per_second,
                "deployment_limit": engine.fixture.stage.deployment_limit.value, "early_enemy_arrivals": records,
                "two_18_cost_blockers": {"first_legal_frame": 240, "second_legal_frame_after_first": 780}}

    def _full_strategy(self, full_engine: M11MinimumSquadSearch, opening: OpeningCandidate) -> Strategy:
        by_id = {item.operator_id: item for item in opening.actions}; actions = list(opening.actions)
        dp = float(full_engine.fixture.stage.initial_dp.value or 0); previous = 0
        for action in sorted(actions, key=lambda item: item.time):
            frame = _frame(full_engine, action.time); dp += full_engine.fixture.stage.dp_per_second * (frame - previous) / 30.0
            dp -= float(full_engine.fixture.operators[action.operator_id].phases[0].stats_max.cost.value or 0); previous = frame
        used_tiles = {item.tile for item in actions}
        for operator_id in opening.team:
            if operator_id in by_id:
                continue
            base_frame = R4_PARENT_FRAMES.get(operator_id, previous + 30)
            cost = float(full_engine.fixture.operators[operator_id].phases[0].stats_max.cost.value or 0)
            required = ceil(max(0.0, (cost - dp) / full_engine.fixture.stage.dp_per_second) * 30)
            frame = max(base_frame, previous + 1, previous + required)
            dp += full_engine.fixture.stage.dp_per_second * (frame - previous) / 30.0; dp -= cost; previous = frame
            tile, direction = R4_PARENT_PLACEMENTS.get(operator_id, (None, "DOWN"))
            if tile in used_tiles or full_engine.simulator._deployment_tile_reason(full_engine.fixture.operators[operator_id], full_engine.fixture.stage, tile):
                option = next(item for item in full_engine.deployment_options() if item.operator_id == operator_id and item.tile not in used_tiles)
                tile, direction = option.tile, option.direction
            used_tiles.add(tile)
            actions.append(Action(ActionType.DEPLOY, full_engine.config.frame_clock.seconds_for_frame(frame), operator_id, tile, direction))
        # Keep the known R4 manual skill suffix only when this exact operator remains.
        if "char_211_adnach" in opening.team:
            actions.append(Action(ActionType.ACTIVATE_SKILL, full_engine.config.frame_clock.seconds_for_frame(max(3300, previous + 1)), "char_211_adnach"))
        return Strategy(opening.team, tuple(sorted(actions, key=lambda item: (item.time, item.operator_id))))

    def _full_row(self, opening_row: dict, result: SimulationResult, engine: M11MinimumSquadSearch) -> dict:
        first_leak = _first(result, EventType.ENEMY_LEAK)
        return {"opening_label": opening_row["label"], "result": "WIN" if result.win else "LOSS",
                "operator_count": len(opening_row["team"]), "rarity": sum(int(self.adapter.repository.get_operator(item).star_rarity.value or 0) for item in opening_row["team"]),
                "kills": result.enemies_killed, "leaks": result.enemies_leaked, "remaining_life": result.remaining_life,
                "first_leak_frame": _frame(engine, first_leak.time) if first_leak else None,
                "attacks": sum(event.event_type is EventType.ATTACK_START and event.source_id in engine.fixture.operators for event in result.events),
                "damage_events": sum(event.event_type is EventType.DAMAGE and event.source_id in engine.fixture.operators for event in result.events)}

    def _single_substitution(self) -> tuple[tuple[str, ...], dict]:
        # Stward is the redundant higher-cost Arts role; Durin remains so this
        # exact-one replacement specifically tests inexpensive opening blocking.
        team = tuple("char_502_nblade" if item == "char_210_stward" else item for item in R4_IDS)
        return team, {"removed_operator": "char_210_stward", "added_operator": "char_502_nblade",
                      "capability_reason": "source-backed cost 7/block 2 early ground deployment versus cost 18 ranged Arts; Durin retains the existing Arts role",
                      "cost_difference": -11}

    def _first_leak_trace(self, engine: M11MinimumSquadSearch, result: SimulationResult,
                          baseline_row: dict, arrival_report: dict) -> dict:
        leak = _first(result, EventType.ENEMY_LEAK)
        if leak is None:
            return {"classification": "NO_OPENING_LEAK"}
        spawns = {event.source_id: event for event in result.events if event.event_type is EventType.SPAWN}
        spawn = spawns.get(leak.source_id)
        spawn_data = dict(spawn.details) if spawn else {}
        route_id = spawn_data.get("route_id", "UNKNOWN")
        deployed = [item for item in baseline_row["actions"] if item["frame"] <= _frame(engine, leak.time)]
        dp = float(engine.fixture.stage.initial_dp.value or 0) + engine.fixture.stage.dp_per_second * float(leak.time)
        for action in deployed:
            dp -= float(engine.fixture.operators[action["operator_id"]].phases[0].stats_max.cost.value or 0)
        route_arrivals = next((item["arrivals"] for item in arrival_report["early_enemy_arrivals"] if item["route_id"] == route_id), [])
        return {
            "enemy_instance_id": leak.source_id, "enemy_id": spawn_data.get("enemy_id", "UNKNOWN"),
            "route_id": route_id, "spawn_frame": _frame(engine, spawn.time) if spawn else "UNKNOWN",
            "relevant_defense_tile_arrivals": route_arrivals,
            "available_dp_at_leak": dp, "deployed_operators_at_leak": deployed,
            "route_coverage_at_leak": baseline_row["structural"]["early_routes"].get(route_id, "UNKNOWN"),
            "leak_frame": _frame(engine, leak.time),
            "causal_reading": "The preserved R4 prefix fields Beagle on route-2 row 4 at frame 240; route-0 has no blocker or ranged interaction before its frame-336 leak. The fixed-R4 opening candidate with Beagle on route-0 row 3 moves the first leak to frame 366.",
        }

    def run(self) -> dict:
        opening_engine = self._engine(R4_IDS, opening=True)
        candidates = self._candidates(opening_engine, R4_IDS)
        # Reserve one exact evaluation for the preserved M14.5 prefix; this
        # makes the documented opening budget a hard total bound.
        rows, usable = self._run_opening(opening_engine, candidates, limit=max(0, self.budget - 1))
        rows.sort(key=self._rank)
        baseline_actions = tuple(Action(ActionType.DEPLOY, opening_engine.config.frame_clock.seconds_for_frame(R4_PARENT_FRAMES[item]), item, *R4_PARENT_PLACEMENTS[item]) for item in R4_IDS if R4_PARENT_FRAMES[item] <= self.horizon_frame)
        baseline = OpeningCandidate("M14.5_R4_PREFIX", R4_IDS, baseline_actions, self._structural(opening_engine, baseline_actions))
        baseline_eval = opening_engine._evaluate(Strategy(R4_IDS, baseline_actions), self.opening_metrics)
        baseline_row = self._row(baseline, baseline_eval.result, opening_engine)
        arrival_report = self._arrival_report(opening_engine)
        base_opening_metrics = {"candidates_generated": len(candidates), "unique_simulations": self.opening_metrics.unique_simulations,
                                "cache_hits": self.opening_metrics.cache_hits}
        all_rows = [baseline_row, *rows]; all_rows.sort(key=self._rank)
        best_opening = all_rows[0] if all_rows else baseline_row
        zero = best_opening["opening_leaks"] == 0
        pressure = "NOT_SUPPORTED" if zero else "SUPPORTED"
        pressure_reason = ("A zero-leak opening was found with the fixed R4 roster." if zero else
                           "No bounded fixed-R4 opening achieved zero leaks; two separate 18-DP blockers cannot both be fielded before the route-0/2 wolf arrival windows under the modeled 10 starting DP and 1 DP/s economy.")
        full_engine = self._engine(R4_IDS, opening=False)
        promoted: list[dict] = []
        baseline_full_strategy = self._full_strategy(full_engine, baseline)
        baseline_full_eval = full_engine._evaluate(baseline_full_strategy, self.full_metrics)
        baseline_full = self._full_row(baseline_row, baseline_full_eval.result, full_engine)
        baseline_full["actions"] = [{"type": item.action_type.value, "operator_id": item.operator_id,
                                     "frame": _frame(full_engine, item.time), "tile": item.tile,
                                     "direction": item.direction} for item in baseline_full_strategy.actions]
        candidate_by_key = {tuple((item.operator_id, _frame(opening_engine, item.time), item.tile, item.direction) for item in candidate.actions): candidate for candidate in usable}
        diverse = []
        seen = set()
        for row in all_rows:
            key = tuple((item["operator_id"], tuple(item["tile"]), item["direction"]) for item in row["actions"])
            if key in seen or row["label"] == "M14.5_R4_PREFIX":
                continue
            seen.add(key); diverse.append(row)
            if len(diverse) == 6:
                break
        for row in diverse:
            key = tuple((item["operator_id"], item["frame"], tuple(item["tile"]), item["direction"]) for item in row["actions"])
            candidate = candidate_by_key.get(key)
            if candidate is None:
                continue
            strategy = self._full_strategy(full_engine, candidate)
            evaluation = full_engine._evaluate(strategy, self.full_metrics)
            promoted.append({**self._full_row(row, evaluation.result, full_engine), "opening": row, "actions": [
                {"type": item.action_type.value, "operator_id": item.operator_id, "frame": _frame(full_engine, item.time), "tile": item.tile, "direction": item.direction} for item in strategy.actions]})
        substitution = None
        if pressure == "SUPPORTED":
            team, rationale = self._single_substitution(); sub_engine = self._engine(team, opening=True)
            sub_rows, sub_candidates = self._run_opening(sub_engine, self._candidates(sub_engine, team), limit=self.budget)
            sub_rows.sort(key=self._rank)
            sub_full_engine = self._engine(team, opening=False)
            by_key = {tuple((item.operator_id, _frame(sub_engine, item.time), item.tile, item.direction) for item in candidate.actions): candidate for candidate in sub_candidates}
            sub_promoted = []
            seen = set()
            for row in sub_rows:
                spatial = tuple((item["operator_id"], tuple(item["tile"]), item["direction"]) for item in row["actions"])
                if spatial in seen:
                    continue
                seen.add(spatial)
                key = tuple((item["operator_id"], item["frame"], tuple(item["tile"]), item["direction"]) for item in row["actions"])
                candidate = by_key[key]
                strategy = self._full_strategy(sub_full_engine, candidate)
                evaluation = sub_full_engine._evaluate(strategy, self.full_metrics)
                sub_promoted.append({**self._full_row(row, evaluation.result, sub_full_engine), "opening": row})
                if len(sub_promoted) == 4:
                    break
            substitution = {"team": team, "rationale": rationale, "opening_results": sub_rows[:12],
                            "best_opening": sub_rows[0] if sub_rows else None,
                            "promoted_full_battle_results": sub_promoted,
                            "candidates_generated": self.generated - base_opening_metrics["candidates_generated"],
                            "unique_simulations": self.opening_metrics.unique_simulations - base_opening_metrics["unique_simulations"]}
        return {
            "opening_failure_analysis": {"baseline": baseline_row,
                                         "first_leak_causal_trace": self._first_leak_trace(opening_engine, baseline_eval.result, baseline_row, arrival_report),
                                         "first_leak_preventability": "PREVENTABLE_WITH_CURRENT_ROSTER" if any(row["first_leak_frame"] is None or row["first_leak_frame"] > 336 for row in all_rows) else "DP_INFEASIBLE",
                                         "classification_basis": "A legal R4 blocker can be deployed at frame 240 on route-0 row 3, which can move the original route-0 frame-336 leak; simultaneous route-0/2 full opening coverage is assessed separately by the bounded opening search and DP timeline."},
            "opening_dp_timeline": {"baseline_deployments": self._dp_timeline(opening_engine, baseline_actions), "arrival_and_margin": arrival_report},
            "opening_search_results": {"horizon_frame": self.horizon_frame, "budget": self.budget, "candidates_generated": self.generated,
                                        "structural_rejections": self.structural_rejections, "unique_simulations": self.opening_metrics.unique_simulations,
                                        "cache_hits": self.opening_metrics.cache_hits, "fixed_r4_metrics": base_opening_metrics, "results": all_rows},
            "opening_progress": [{"rank": index + 1, "label": row["label"], "leaks": row["opening_leaks"], "first_leak_frame": row["first_leak_frame"], "kills": row["opening_kills"], "damage": row["opening_damage"]} for index, row in enumerate(all_rows[:12])],
            "promoted_full_battle_results": {"baseline_full": baseline_full, "promoted": promoted, "unique_simulations": self.full_metrics.unique_simulations, "cache_hits": self.full_metrics.cache_hits},
            "opening_capability_pressure": {"classification": pressure, "reason": pressure_reason},
            "opening_substitution_results": substitution,
        }
