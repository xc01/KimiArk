"""M15.1 bounded closed-loop repair from the preserved M15 6-8 parent.

This module deliberately operates on one recorded partial strategy.  It does
not enumerate rosters, add mechanics, or call an LLM.  Each repair starts with
the first simulator-observed failure, limits mutations to its dependencies, and
only broadens the mutation level after the narrower level plateaus.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
from time import perf_counter

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.simulation import EventType, SimulationResult
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig, M11SearchMetrics
from arknights_planner.search.m15 import AssignedPlacement, ConstraintGuidedFeasibilityPlanner, FailureFrontier, FailureType
from arknights_planner.simulator import SimulationConfig
from arknights_planner.timing import strategy_to_timeline


REPAIR_LEVELS = ("TIMING", "SPATIAL_FACING", "ORDER", "OPERATOR_REASSIGNMENT", "ROLE_RESTRUCTURING")


@dataclass(frozen=True)
class RepairState:
    strategy: Strategy
    result: SimulationResult
    frontier: FailureFrontier
    frozen_actions: tuple[tuple, ...] = ()
    frozen_until_frame: int = 0


def _details(event) -> dict:
    return dict(event.details)


class FailureFrontierRepair:
    """A small failure-directed repair loop plus an unguided control."""

    VERSION = "m15.1-frontier-repair-v1"

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter,
                 policy: RealSimulationApproximationPolicy, parent_path: Path,
                 guided_budget: int = 600, control_budget: int = 200):
        self.adapter, self.policy = adapter, policy
        self.parent_path = parent_path
        self.guided_budget, self.control_budget = guided_budget, control_budget
        configs = adapter.m13_low_rarity_configurations()
        self.engine = M11MinimumSquadSearch(
            adapter=adapter, stage_id_or_code="6-8", policy=policy, operator_pool=configs,
            config=M11SearchConfig(max_squad_size=7, max_teams=1, placement_options_per_operator=64,
                                   beam_width=8, simulation_config=SimulationConfig(dt=.2, max_time=300.0)),
        )
        self.constraint_helper = ConstraintGuidedFeasibilityPlanner(
            adapter=adapter, policy=policy, beam_width=8, simulation_budget=1, max_cardinality=7,
        )
        self.metrics = M11SearchMetrics()
        self.generated_constraints: list[dict] = []
        self.prefix_dependencies: list[dict] = []
        self.progress: list[dict] = []

    def _frame(self, value) -> int:
        return self.engine.config.frame_clock.frame_for_seconds(value)

    def _parent_strategy(self) -> tuple[Strategy, dict]:
        payload = json.loads(self.parent_path.read_text(encoding="utf-8"))
        row = payload["best"]
        actions = tuple(
            Action(ActionType(item["type"]), Fraction(int(item["frame"]), 30), item["operator_id"],
                   tuple(item["tile"]) if item["tile"] is not None else None, item["direction"])
            for item in row["actions"]
        )
        return Strategy(tuple(row["team"]), actions), row

    def _frontier(self, strategy: Strategy, result: SimulationResult) -> FailureFrontier:
        # Reuse M15's supported event-only classification and provenance.
        assignments = tuple(
            AssignedPlacement("M15_1_PARENT", action.operator_id, action.tile, action.direction, ())
            for action in strategy.actions if action.action_type is ActionType.DEPLOY
        )
        from arknights_planner.search.m15 import PartialStrategy
        return self.constraint_helper._frontier(PartialStrategy(assignments=assignments, actions=strategy.actions), result)

    def _evaluate(self, strategy: Strategy) -> RepairState | None:
        if not self._static_legal(strategy):
            return None
        evaluation = self.engine._evaluate(strategy, self.metrics)
        return RepairState(strategy, evaluation.result, self._frontier(strategy, evaluation.result))

    def _static_legal(self, strategy: Strategy) -> bool:
        deploys = tuple(item for item in strategy.actions if item.action_type is ActionType.DEPLOY)
        if len(deploys) > 7 or len({item.operator_id for item in deploys}) != len(deploys):
            return False
        if len({item.tile for item in deploys}) != len(deploys):
            return False
        dp = float(self.engine.fixture.stage.initial_dp.value or 0)
        rate = float(self.engine.fixture.stage.dp_per_second)
        cursor = 0
        for action in sorted(deploys, key=lambda item: (item.time, item.operator_id)):
            frame = self._frame(action.time)
            if frame < cursor:
                return False
            operator = self.engine.fixture.operators.get(action.operator_id)
            if operator is None or self.engine.simulator._deployment_tile_reason(operator, self.engine.fixture.stage, action.tile):
                return False
            dp += rate * (frame - cursor) / 30.0
            cost = self.constraint_helper._effective_cost(action.operator_id)
            if dp + 1e-9 < cost:
                return False
            dp -= cost; cursor = frame
        return True

    @staticmethod
    def _state_key(state: RepairState) -> tuple:
        return tuple((item.action_type.value, item.operator_id, item.time, item.tile, item.direction) for item in state.strategy.actions)

    def _rank(self, state: RepairState) -> tuple:
        result, frontier = state.result, state.frontier
        return (0 if result.win else 1, -frontier.frame, result.enemies_leaked,
                -result.enemies_killed, -result.remaining_life, self._state_key(state))

    def _nondominated(self, states: list[RepairState], width: int = 8) -> list[RepairState]:
        selected: list[RepairState] = []
        seen = set()
        for item in sorted(states, key=self._rank):
            key = (item.frontier.frame, item.frontier.failure_type.value, item.frontier.routes,
                   item.result.enemies_leaked, item.result.enemies_killed,
                   tuple(sorted(item.strategy.team)))
            if key in seen:
                continue
            seen.add(key); selected.append(item)
            if len(selected) == width:
                break
        return selected

    def _route_cells(self, route_id: str) -> set[tuple[int, int]]:
        route = next(item for item in self.engine.fixture.stage.routes if item.route_id == route_id)
        return set(self.constraint_helper._route_cells(route))

    def _action_covers_route(self, action: Action, route_id: str) -> bool:
        if action.action_type is not ActionType.DEPLOY:
            return False
        op = self.engine.fixture.operators[action.operator_id]
        if op.position.value == "MELEE" and action.tile in self._route_cells(route_id):
            return True
        covered = self.engine.simulator.range_transformer.covered_tiles(
            origin=action.tile, offsets=op.attack_range, direction=action.direction,
        )
        return bool(covered & self._route_cells(route_id))

    def _causal_trace(self, state: RepairState) -> dict:
        result, frontier = state.result, state.frontier
        leak = next((item for item in result.events if item.event_type is EventType.ENEMY_LEAK), None)
        if leak is None:
            return {"classification": ["UNKNOWN"], "reason": "no leak event available"}
        spawn_by_instance = {item.source_id: item for item in result.events if item.event_type is EventType.SPAWN}
        spawn = spawn_by_instance.get(leak.source_id)
        spawn_data = _details(spawn) if spawn else {}
        route_id = str(spawn_data.get("route_id", "UNKNOWN"))
        enemy_id = str(spawn_data.get("enemy_id", "UNKNOWN"))
        damage = [item for item in result.events if item.event_type is EventType.DAMAGE and item.target_id == leak.source_id]
        attacks = [item for item in result.events if item.event_type is EventType.ATTACK_START and item.target_id == leak.source_id]
        enemy = self.engine.fixture.enemies.get(enemy_id)
        total_damage = sum(float(_details(item).get("amount", 0)) for item in damage if item.source_id in self.engine.fixture.operators)
        hp = float(enemy.stats.max_hp.value) if enemy else None
        legal_deployments = [item for item in result.events if item.event_type is EventType.DEPLOY and _details(item).get("legal") is True]
        deployed_before = [item for item in state.strategy.actions if item.action_type is ActionType.DEPLOY and self._frame(item.time) <= frontier.frame]
        capable = [item for item in deployed_before if self._action_covers_route(item, route_id)]
        actual = sorted({item.source_id for item in attacks if item.source_id in self.engine.fixture.operators})
        dp_events = []
        current_dp = float(self.engine.fixture.stage.initial_dp.value or 0)
        cursor = 0
        for action in sorted(state.strategy.actions, key=lambda item: (item.time, item.action_type.value)):
            frame = self._frame(action.time)
            if frame > frontier.frame:
                break
            current_dp += float(self.engine.fixture.stage.dp_per_second) * (frame - cursor) / 30.0
            before = current_dp
            if action.action_type is ActionType.DEPLOY:
                current_dp -= self.constraint_helper._effective_cost(action.operator_id)
            dp_events.append({"frame": frame, "action": action.action_type.value, "operator_id": action.operator_id,
                              "dp_before": before, "dp_after": current_dp})
            cursor = frame
        current_dp += float(self.engine.fixture.stage.dp_per_second) * (frontier.frame - cursor) / 30.0
        unused = []
        used = set(state.strategy.team)
        for operator_id, operator in self.engine.fixture.operators.items():
            if operator_id in used:
                continue
            cost = self.constraint_helper._effective_cost(operator_id)
            if cost > current_dp + 1e-9:
                continue
            placements = self._placements_for_route(operator_id, route_id, excluded_tiles={item.tile for item in deployed_before})
            if placements:
                unused.append({"operator_id": operator_id, "effective_cost": cost, "placements": placements[:2]})
        tags: list[str] = []
        if not capable:
            tags.append("NO_INTERACTION")
            if unused:
                tags.append("DP_INFEASIBLE")
            else:
                tags.append("SPATIAL_INFEASIBLE")
        elif not actual:
            tags.append("INTERACTION_TOO_LATE")
        elif total_damage <= 0:
            tags.append("DAMAGE_INSUFFICIENT")
        elif hp is not None and total_damage < hp:
            tags.append("DAMAGE_INSUFFICIENT")
        else:
            tags.append("UNKNOWN")
        route = next((item for item in self.engine.fixture.stage.routes if item.route_id == route_id), None)
        progression = []
        if route and spawn:
            for cell in self.constraint_helper._route_cells(route):
                frame = self.constraint_helper._entry_frame(route, self.engine.fixture.stage.spawn_events[
                    next(i for i, item in enumerate(self.engine.fixture.stage.spawn_events)
                         if item.route_id == route_id and item.enemy_id == enemy_id)
                ], cell)
                if frame is not None and frame <= frontier.frame:
                    progression.append({"tile": cell, "entry_frame": frame})
        return {
            "frontier": self._frontier_dict(frontier), "enemy_instance_id": leak.source_id, "enemy_id": enemy_id,
            "spawn_frame": self._frame(spawn.time) if spawn else "UNKNOWN", "route_progression": progression,
            "leak_frame": self._frame(leak.time), "enemy_hp": hp if hp is not None else "UNKNOWN",
            "damage_received": total_damage, "hp_at_leak": max(0.0, hp - total_damage) if hp is not None else "UNKNOWN",
            "attacks_received": len(attacks), "damage_events": len(damage), "operators_capable_of_interacting": [item.operator_id for item in capable],
            "operators_actually_interacting": actual, "dp_timeline": dp_events,
            "dp_at_leak": current_dp, "deployment_state": [{"operator_id": item.operator_id, "frame": self._frame(item.time), "tile": item.tile, "direction": item.direction} for item in deployed_before],
            "successful_deployments": [item.source_id for item in legal_deployments], "legal_unused_placements": unused[:12],
            "classification": tags,
        }

    def _frontier_constraints(self, trace: dict) -> list[dict]:
        frontier = trace["frontier"]
        route = frontier["routes"][0] if frontier["routes"] else "UNKNOWN"
        out = [{"constraint_type": "INTERACT_WITH_ROUTE_BEFORE", "route": route, "frame": frontier["frame"],
                "provenance": "EXACT_EVENT", "evidence": ["first leaked enemy route and leak frame"]}]
        if trace["damage_received"] > 0 and trace["hp_at_leak"] != "UNKNOWN":
            out.append({"constraint_type": "DAMAGE_ROUTE_BEFORE", "route": route, "frame": frontier["frame"],
                        "minimum_additional_damage": trace["hp_at_leak"], "provenance": "DERIVED_FROM_DAMAGE_EVENTS",
                        "evidence": ["source HP minus observed damage to leaked enemy"]})
        elif "NO_INTERACTION" in trace["classification"]:
            out.append({"constraint_type": "HAVE_GROUND_OR_RANGE_INTERACTION_BY", "route": route, "frame": frontier["frame"],
                        "provenance": "EXACT_EVENT_PLUS_GEOMETRY", "evidence": ["no deployed operator could interact with leaked route"]})
        return out

    def _frontier_dict(self, item: FailureFrontier) -> dict:
        return {"frame": item.frame, "failure_type": item.failure_type.value, "routes": list(item.routes),
                "enemy_ids": list(item.enemy_ids), "required_capabilities": list(item.required_capabilities),
                "evidence": list(item.evidence), "confidence": item.confidence}

    def _placements_for_route(self, operator_id: str, route_id: str, excluded_tiles: set[tuple[int, int]] = set()) -> list[dict]:
        op = self.engine.fixture.operators[operator_id]
        kind = "GROUND" if op.position.value == "MELEE" else "HIGH_GROUND"
        out = []
        for tile in self.engine.fixture.stage.stage_map.tiles:
            if not tile.buildable or tile.tile_kind != kind or (tile.x, tile.y) in excluded_tiles:
                continue
            for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                action = Action(ActionType.DEPLOY, 0, operator_id, (tile.x, tile.y), direction)
                if self._action_covers_route(action, route_id):
                    out.append({"tile": (tile.x, tile.y), "direction": direction})
        return out

    def _dependency_actions(self, state: RepairState, trace: dict, *, guided: bool) -> tuple[int, ...]:
        deploys = [item for item in state.strategy.actions if item.action_type is ActionType.DEPLOY]
        if not guided:
            return tuple(range(len(deploys)))
        route = trace["frontier"]["routes"][0] if trace["frontier"]["routes"] else "UNKNOWN"
        limit = trace["frontier"]["frame"]
        targets = []
        frozen = set(state.frozen_actions)
        for index, action in enumerate(deploys):
            action_key = (action.action_type.value, self._frame(action.time), action.operator_id, action.tile, action.direction)
            if action_key in frozen:
                continue
            reasons = []
            if self._frame(action.time) <= limit:
                reasons.append("DP_CONSUMER_BEFORE_FRONTIER")
                if self._action_covers_route(action, route):
                    reasons.append("ROUTE_COVERAGE")
            elif self._action_covers_route(action, route):
                # A later route-capable deployment is a direct explanation of
                # an INTERACTION_TOO_LATE trace.  It must be mutable even
                # though it occurs after the current failure frontier.
                reasons.append("INTERACTION_AVAILABLE_AFTER_FRONTIER")
            if reasons:
                targets.append(index)
                self.prefix_dependencies.append({"action": self._action_dict(action), "frontier": trace["frontier"], "dependency_reasons": reasons})
        return tuple(targets) or (0,)

    def _action_dict(self, action: Action) -> dict:
        return {"type": action.action_type.value, "operator_id": action.operator_id, "frame": self._frame(action.time),
                "tile": action.tile, "direction": action.direction}

    def _reschedule(self, deploys: tuple[Action, ...]) -> Strategy | None:
        assignments = tuple(AssignedPlacement("M15_1_REPAIR", item.operator_id, item.tile, item.direction, ()) for item in deploys)
        actions = self.constraint_helper._schedule(assignments)
        if actions is None:
            return None
        return Strategy(tuple(item.operator_id for item in deploys), actions)

    def _direct_change(self, strategy: Strategy, index: int, *, frame: int | None = None,
                       tile: tuple[int, int] | None = None, direction: str | None = None,
                       operator_id: str | None = None) -> Strategy:
        deploys = [item for item in strategy.actions if item.action_type is ActionType.DEPLOY]
        old = deploys[index]
        deploys[index] = Action(ActionType.DEPLOY, self.engine.config.frame_clock.seconds_for_frame(frame if frame is not None else self._frame(old.time)),
                                operator_id or old.operator_id, tile or old.tile, direction or old.direction)
        return Strategy(tuple(item.operator_id for item in deploys), tuple(sorted(deploys, key=lambda item: (item.time, item.operator_id))))

    def _repair_candidates(self, state: RepairState, trace: dict, level: str, *, guided: bool) -> list[tuple[str, Strategy, list[dict]]]:
        deploys = [item for item in state.strategy.actions if item.action_type is ActionType.DEPLOY]
        focus = self._dependency_actions(state, trace, guided=guided)
        route = trace["frontier"]["routes"][0] if guided and trace["frontier"]["routes"] else "route-0"
        out: list[tuple[str, Strategy, list[dict]]] = []
        if level == "TIMING":
            for index in focus:
                old = deploys[index]; base = self._frame(old.time)
                for delta in (-90, -30, -10, 10, 30, 90):
                    candidate = self._direct_change(state.strategy, index, frame=max(0, base + delta))
                    out.append(("TIMING", candidate, [{"action": self._action_dict(old), "reason": "frontier timing dependency" if guided else "unguided timing mutation"}]))
        elif level == "SPATIAL_FACING":
            for index in focus:
                old = deploys[index]; occupied = {item.tile for offset, item in enumerate(deploys) if offset != index}
                for placement in self._placements_for_route(old.operator_id, route, occupied)[:4]:
                    if (placement["tile"], placement["direction"]) == (old.tile, old.direction):
                        continue
                    candidate = self._direct_change(state.strategy, index, tile=placement["tile"], direction=placement["direction"])
                    out.append(("SPATIAL_FACING", candidate, [{"action": self._action_dict(old), "reason": "route coverage dependency" if guided else "unguided spatial mutation"}]))
        elif level == "ORDER":
            order_indices = focus if guided else tuple(range(len(deploys)))
            for index in order_indices:
                if index + 1 >= len(deploys):
                    continue
                revised = list(deploys); revised[index], revised[index + 1] = revised[index + 1], revised[index]
                scheduled = self._reschedule(tuple(revised))
                if scheduled:
                    out.append(("ORDER", scheduled, [{"action": self._action_dict(deploys[index]), "reason": "DP order dependency" if guided else "unguided order mutation"}]))
        elif level == "OPERATOR_REASSIGNMENT":
            for index in focus:
                old = deploys[index]; current = self.engine.fixture.operators[old.operator_id]
                alternatives = []
                for candidate_id, candidate in self.engine.fixture.operators.items():
                    if candidate_id in state.strategy.team or candidate.position.value != current.position.value:
                        continue
                    if not self._placements_for_route(candidate_id, route, {item.tile for offset, item in enumerate(deploys) if offset != index}):
                        continue
                    alternatives.append(candidate_id)
                alternatives.sort(key=lambda item: (self.constraint_helper._effective_cost(item), -self.constraint_helper._damage_value(item), item))
                for candidate_id in alternatives[:6]:
                    placements = self._placements_for_route(candidate_id, route, {item.tile for offset, item in enumerate(deploys) if offset != index})[:2]
                    for placement in placements:
                        revised = list(deploys)
                        revised[index] = Action(ActionType.DEPLOY, old.time, candidate_id, placement["tile"], placement["direction"])
                        scheduled = self._reschedule(tuple(revised))
                        if scheduled:
                            out.append(("OPERATOR_REASSIGNMENT", scheduled, [{"action": self._action_dict(old), "reason": "frontier role replacement" if guided else "unguided reassignment"}]))
        elif level == "ROLE_RESTRUCTURING":
            # Two early positions may jointly satisfy the two parallel lanes.
            # This is a bounded role change, not a fresh roster construction.
            if len(deploys) >= 2:
                first, second = deploys[0], deploys[1]
                protected_later = {item.operator_id for item in deploys[2:]}
                route0 = [(item, self._placements_for_route(item, "route-0")[:1]) for item in self.engine.fixture.operators if item not in protected_later]
                route2 = [(item, self._placements_for_route(item, "route-2")[:1]) for item in self.engine.fixture.operators if item not in protected_later]
                left = sorted((item for item in route0 if item[1]), key=lambda item: (self.constraint_helper._effective_cost(item[0]), -self.constraint_helper._damage_value(item[0]), item[0]))[:5]
                right = sorted((item for item in route2 if item[1]), key=lambda item: (self.constraint_helper._effective_cost(item[0]), -self.constraint_helper._damage_value(item[0]), item[0]))[:5]
                for left_id, left_places in left:
                    for right_id, right_places in right:
                        if left_id == right_id or left_places[0]["tile"] == right_places[0]["tile"]:
                            continue
                        revised = list(deploys)
                        revised[0] = Action(ActionType.DEPLOY, first.time, left_id, left_places[0]["tile"], left_places[0]["direction"])
                        revised[1] = Action(ActionType.DEPLOY, second.time, right_id, right_places[0]["tile"], right_places[0]["direction"])
                        scheduled = self._reschedule(tuple(revised))
                        if scheduled:
                            out.append(("ROLE_RESTRUCTURING", scheduled, [
                                {"action": self._action_dict(first), "reason": "route-0 early-role restructure"},
                                {"action": self._action_dict(second), "reason": "route-2 early-role restructure"},
                            ]))
        unique = {}
        for mutation, candidate, invalidations in out:
            key = tuple((item.action_type.value, item.operator_id, item.time, item.tile, item.direction) for item in candidate.actions)
            unique.setdefault(key, (mutation, candidate, invalidations))
        return list(unique.values())

    def _freeze_after_progress(self, state: RepairState, previous: FailureFrontier) -> RepairState:
        if state.frontier.frame <= previous.frame:
            return state
        boundary = previous.frame - 30
        route = state.frontier.routes[0] if state.frontier.routes else "UNKNOWN"
        frozen = tuple(
            (item.action_type.value, self._frame(item.time), item.operator_id, item.tile, item.direction)
            for item in state.strategy.actions
            if self._frame(item.time) <= boundary and not self._action_covers_route(item, route)
        )
        return RepairState(state.strategy, state.result, state.frontier, frozen, boundary)

    def _state_row(self, state: RepairState, *, label: str) -> dict:
        return {"label": label, "result": "WIN" if state.result.win else "LOSS", "operators": list(state.strategy.team),
                "operator_count": len(state.strategy.team),
                "rarity": sum(int(self.engine.fixture.operators[item].star_rarity.value or 0) for item in state.strategy.team),
                "actions": [self._action_dict(item) for item in state.strategy.actions],
                "kills": state.result.enemies_killed, "leaks": state.result.enemies_leaked,
                "remaining_life": state.result.remaining_life, "earliest_failure_frontier": self._frontier_dict(state.frontier),
                "frozen_until_frame": state.frozen_until_frame, "frozen_actions": list(state.frozen_actions)}

    def _run_mode(self, initial: RepairState, trace: dict, *, guided: bool, budget: int) -> dict:
        frontier = [initial]; archive = [initial]; visited = {self._state_key(initial)}
        before = self.metrics.unique_simulations
        cache_before = self.metrics.cache_hits
        transitions = []
        accepted = 0
        level_rows = []
        for level in REPAIR_LEVELS:
            if self.metrics.unique_simulations - before >= budget or any(item.result.win for item in frontier):
                break
            children: list[RepairState] = []
            attempts = simulated = pre_rejected = improvements = 0
            for parent in frontier:
                parent_trace = self._causal_trace(parent) if guided else trace
                for _, candidate, invalidations in self._repair_candidates(parent, parent_trace, level, guided=guided):
                    if self.metrics.unique_simulations - before >= budget:
                        break
                    key = tuple((item.action_type.value, item.operator_id, item.time, item.tile, item.direction) for item in candidate.actions)
                    if key in visited:
                        continue
                    visited.add(key); attempts += 1
                    if not self._static_legal(candidate):
                        pre_rejected += 1
                        continue
                    count = self.metrics.unique_simulations
                    child = self._evaluate(candidate)
                    simulated += self.metrics.unique_simulations - count
                    if child is None:
                        pre_rejected += 1
                        continue
                    if child.frontier.frame > parent.frontier.frame:
                        child = self._freeze_after_progress(child, parent.frontier)
                        transitions.append({"from": self._frontier_dict(parent.frontier), "to": self._frontier_dict(child.frontier),
                                            "level": level, "invalidated_actions": invalidations,
                                            "freeze": {"until_frame": child.frozen_until_frame, "actions": list(child.frozen_actions)}})
                        improvements += 1; accepted += 1
                    children.append(child); archive.append(child)
                    if child.result.win:
                        break
                if any(item.result.win for item in children):
                    break
            level_rows.append({"level": level, "attempts": attempts, "simulations": simulated,
                               "accepted_improvements": improvements, "rejected_pre_simulation": pre_rejected})
            # Continue only from the nondominated results of the current local
            # level, preserving the parent where all repairs regressed.
            frontier = self._nondominated(children + frontier)
            best = min(archive, key=self._rank)
            self.progress.append({"mode": "FRONTIER_REPAIR" if guided else "LOCAL_UNGUIDED_CONTROL", "level": level,
                                  "simulations_used": self.metrics.unique_simulations - before,
                                  "best": self._state_row(best, label="best_after_" + level)})
            if best.result.win:
                break
        best = min(archive, key=self._rank)
        return {"best": best, "archive": archive, "frontier_transitions": transitions, "level_rows": level_rows,
                "unique_simulations": self.metrics.unique_simulations - before,
                "cache_hits": self.metrics.cache_hits - cache_before,
                "accepted_improvements": accepted}

    def run(self) -> dict:
        started = perf_counter()
        strategy, parent_row = self._parent_strategy()
        parent = self._evaluate(strategy)
        if parent is None:
            raise RuntimeError("preserved M15 parent is structurally illegal under current runtime")
        trace = self._causal_trace(parent)
        constraints = self._frontier_constraints(trace)
        self.generated_constraints.extend(constraints)
        guided = self._run_mode(parent, trace, guided=True, budget=self.guided_budget)
        control = self._run_mode(parent, trace, guided=False, budget=self.control_budget)
        best_guided, best_control = guided["best"], control["best"]
        guided_progress = best_guided.frontier.frame > parent.frontier.frame
        control_progress = best_control.frontier.frame > parent.frontier.frame
        # The comparison is an architecture experiment, not a loss score.  A
        # guided run is supported only when it reaches a strictly later frontier
        # than control, or reaches any progress while control does not.  Equal
        # progress with a larger guided budget is not evidence for guidance.
        if guided_progress and (not control_progress or best_guided.frontier.frame > best_control.frontier.frame):
            classification = "SUPPORTED"
        elif control_progress and best_guided.frontier.frame <= best_control.frontier.frame:
            classification = "NOT_SUPPORTED"
        else:
            classification = "INCONCLUSIVE"
        winner = best_guided if best_guided.result.win else (best_control if best_control.result.win else None)
        timeline = robustness = human = None
        if winner:
            evaluation = self.engine._evaluate(winner.strategy, self.metrics)
            robustness = self.engine._robustness(evaluation, self.metrics)
            timeline_object = strategy_to_timeline(winner.strategy, stage_id=self.engine.fixture.stage.stage_id,
                                                   frame_clock=self.engine.config.frame_clock,
                                                   simulator_mode="APPROXIMATE_REAL",
                                                   approximation_policy_version=self.policy.cache_identity[0])
            timeline = timeline_object.to_dict()
            human = "FEASIBLE_NOT_MINIMAL\n" + "UNTESTED\n" + "\n".join(
                f"{item.frame:04d} {item.action_type.value} {item.operator_id}" for item in timeline_object.actions
            )
        return {
            "m15_1_initial_parent": {"source": str(self.parent_path), "preserved_row": parent_row,
                                      "reconstructed": self._state_row(parent, label="initial_parent")},
            "m15_1_frontier_causal_trace": trace,
            "m15_1_generated_constraints": constraints,
            "m15_1_repair_progress": self.progress,
            "m15_1_prefix_dependencies": self.prefix_dependencies,
            "m15_1_repair_level_stats": {
                "guided": guided["level_rows"],
                "control": control["level_rows"],
            },
            "m15_1_unguided_control": {"budget": self.control_budget, "result": self._state_row(best_control, label="control_best"),
                                         "unique_simulations": control["unique_simulations"], "frontier_transitions": control["frontier_transitions"],
                                         "level_rows": control["level_rows"]},
            "m15_1_results": {"guided": self._state_row(best_guided, label="guided_best"), "guided_unique_simulations": guided["unique_simulations"],
                                "guided_cache_hits": guided["cache_hits"],
                                "guided_frontier_transitions": guided["frontier_transitions"],
                                "control_unique_simulations": control["unique_simulations"],
                                "control_cache_hits": control["cache_hits"],
                                "control_frontier_transitions": control["frontier_transitions"],
                                "termination": "WIN_FOUND" if winner else "NO_WIN_FOUND_BOUNDED",
                                "timeline": timeline, "robustness": robustness, "human_timeline": human},
            "m15_1_comparison": {"initial_parent": self._state_row(parent, label="initial_parent"),
                                   "guided": self._state_row(best_guided, label="guided_best"),
                                   "control": self._state_row(best_control, label="control_best"),
                                   "classification": classification,
                                   "reason": (
                                       "guided repair reached a later frontier than the local control"
                                       if classification == "SUPPORTED" else
                                       "local unguided control matched or exceeded guided frontier progress"
                                       if classification == "NOT_SUPPORTED" else
                                       "bounded comparison did not isolate a frontier-guidance advantage"
                                   ),
                                   "llm_calls": 0, "mechanics_expansion": False, "elapsed_seconds": perf_counter() - started},
        }
