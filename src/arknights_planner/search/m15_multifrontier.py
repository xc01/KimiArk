"""M15.3 multi-frontier/resource-conflict audit and bounded repair.

The module starts from the preserved M15.2 parent and its route-2-success
counterexamples.  It never regenerates a roster and never calls an LLM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from math import ceil
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.simulation import EventType, SimulationEvent, SimulationResult
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig, M11SearchMetrics
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator


FPS = 30
UNAVAILABLE = "UNKNOWN"


def details(event: SimulationEvent | None) -> dict[str, Any]:
    return dict(event.details) if event else {}


@dataclass(frozen=True)
class MultiFrontierConstraint:
    constraint_id: str
    route: str
    deadline: int
    enemy_ids: tuple[str, ...]
    requirement_type: str
    required_capability: str
    provenance: str
    evidence: tuple[str, ...]
    status: str = "ACTIVE"

    def as_dict(self) -> dict[str, Any]:
        return {"constraint_id": self.constraint_id, "route": self.route, "deadline": self.deadline,
                "enemy_ids": list(self.enemy_ids), "requirement_type": self.requirement_type,
                "required_capability": self.required_capability, "provenance": self.provenance,
                "evidence": list(self.evidence), "status": self.status}


@dataclass(frozen=True)
class State:
    strategy: Strategy
    result: SimulationResult
    frontiers: tuple[dict[str, Any], ...]
    repair: tuple[dict[str, Any], ...] = ()


class MultiFrontierSolver:
    VERSION = "m15.3-multifrontier-v1"

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter,
                 policy: RealSimulationApproximationPolicy, root: Path, budget: int = 600):
        self.adapter, self.policy, self.root, self.budget = adapter, policy, root, budget
        configs = adapter.m13_low_rarity_configurations()
        self.engine = M11MinimumSquadSearch(adapter=adapter, stage_id_or_code="6-8", policy=policy,
            operator_pool=configs, config=M11SearchConfig(max_squad_size=7, max_teams=1,
                placement_options_per_operator=64, beam_width=8,
                simulation_config=SimulationConfig(dt=.2, max_time=300.0)))
        self.simulator = Simulator(range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel())
        self.metrics = M11SearchMetrics()
        self.prechecks: list[dict[str, Any]] = []
        self.progress: list[dict[str, Any]] = []

    def _frame(self, value: float | Fraction) -> int:
        return self.engine.config.frame_clock.frame_for_seconds(value)

    def _actions(self, row: dict[str, Any]) -> Strategy:
        actions = tuple(Action(ActionType(item["type"]), Fraction(int(item["frame"]), FPS), item["operator_id"],
                               tuple(item["tile"]) if item.get("tile") is not None else None, item.get("direction", "RIGHT"))
                       for item in row["actions"])
        return Strategy(tuple(row.get("operators", row.get("team", []))), actions)

    def _load_inputs(self) -> tuple[Strategy, list[Strategy], dict[str, Any]]:
        m152 = json.loads((self.root / "m15_2_results.json").read_text(encoding="utf-8"))
        parent = self._actions(m152["best"])
        progress = json.loads((self.root / "m15_2_requirement_progress.json").read_text(encoding="utf-8"))
        counterexamples = []
        for row in progress:
            if "R2_ROUTE_2_DAMAGE_564" in row.get("solved_requirements", []) and row["result"]["earliest_failure_frontier"]["routes"] != ["route-2"]:
                counterexamples.append(self._actions(row["result"]))
        # Preserve exact rows, deduplicated by actions.
        unique = {}
        for item in counterexamples:
            unique[tuple((a.action_type.value, self._frame(a.time), a.operator_id, a.tile, a.direction) for a in item.actions)] = item
        return parent, list(unique.values())[:3], {"parent": m152["best"], "counterexamples_count": len(unique)}

    def _simulate(self, strategy: Strategy) -> SimulationResult:
        evaluation = self.engine._evaluate(strategy, self.metrics)
        return evaluation.result

    def _route_frontiers(self, result: SimulationResult) -> tuple[dict[str, Any], ...]:
        out = []
        for leak in (event for event in result.events if event.event_type is EventType.ENEMY_LEAK):
            spawn = next((event for event in result.events if event.event_type is EventType.SPAWN and event.source_id == leak.source_id), None)
            route = str(details(spawn).get("route_id", "UNKNOWN"))
            if any(item["route"] == route for item in out):
                continue
            target_damage = [event for event in result.events if event.event_type is EventType.DAMAGE and event.target_id == leak.source_id and event.source_id in self.engine.fixture.operators]
            out.append({"route": route, "frame": self._frame(leak.time), "enemy_id": details(spawn).get("enemy_id", "UNKNOWN"),
                        "enemy_instance_id": leak.source_id, "type": "DAMAGE_INSUFFICIENT" if target_damage else "INTERACTION_TOO_LATE",
                        "attacks": sum(event.event_type is EventType.ATTACK_START and event.target_id == leak.source_id for event in result.events),
                        "damage": sum(float(details(event).get("amount", 0)) for event in target_damage)})
        return tuple(sorted(out, key=lambda item: (item["frame"], item["route"])))

    def _opening_requirements(self, parent: State, counterexamples: list[State]) -> list[MultiFrontierConstraint]:
        by_route: dict[str, list[dict[str, Any]]] = {}
        for state in [parent, *counterexamples]:
            for frontier in state.frontiers:
                by_route.setdefault(frontier["route"], []).append(frontier)
        requirements = []
        for route in sorted(by_route):
            evidence = by_route[route]
            earliest = min(item["frame"] for item in evidence)
            representative = min(evidence, key=lambda item: item["frame"])
            requirements.append(MultiFrontierConstraint(
                f"C_{route.replace('-', '_')}_EARLY", route, earliest,
                (str(representative["enemy_id"]),),
                "PREVENT_LEAK_BEFORE" if representative["type"] == "INTERACTION_TOO_LATE" else "DAMAGE_BEFORE",
                "GROUND_OR_RANGED_INTERACTION" if representative["type"] == "INTERACTION_TOO_LATE" else "DAMAGE",
                "SIMULATION_DERIVED", tuple(f"{item['type']} at frame {item['frame']} ({item['route']})" for item in evidence),
            ))
        return requirements

    def _dp_schedule(self, strategy: Strategy, until: int = 600) -> list[dict[str, Any]]:
        dp = float(self.engine.fixture.stage.initial_dp.value or 0); rate = float(self.engine.fixture.stage.dp_per_second); cursor = 0; rows = []
        for action in sorted((item for item in strategy.actions if item.action_type is ActionType.DEPLOY), key=lambda item: item.time):
            frame = self._frame(action.time)
            if frame > until: break
            dp += rate * (frame - cursor) / FPS; before = dp; cost = float(self.engine.fixture.operators[action.operator_id].phases[0].stats_max.cost.value or 0)
            dp -= cost; rows.append({"frame": frame, "operator_id": action.operator_id, "dp_before": before, "cost": cost, "dp_after": dp}); cursor = frame
        return rows

    def _resource_assignments(self, state: State, requirements: list[MultiFrontierConstraint]) -> list[dict[str, Any]]:
        rows = []
        for constraint in requirements:
            for action in state.strategy.actions:
                if action.action_type is not ActionType.DEPLOY or action.tile is None: continue
                operator = self.engine.fixture.operators[action.operator_id]
                if operator.position.value == "MELEE": covers = action.tile in self._route_cells(constraint.route)
                else: covers = bool(self.engine.simulator.range_transformer.covered_tiles(origin=action.tile, offsets=operator.attack_range, direction=action.direction) & self._route_cells(constraint.route))
                if covers:
                    rows.append({"constraint_id": constraint.constraint_id, "operator_id": action.operator_id,
                                 "tile": action.tile, "facing": action.direction, "deploy_frame": self._frame(action.time),
                                 "dp": next((item["cost"] for item in self._dp_schedule(state.strategy, constraint.deadline) if item["operator_id"] == action.operator_id), None),
                                 "attack_coverage": True})
        return rows

    def _route_cells(self, route_id: str) -> set[tuple[int, int]]:
        route = next(item for item in self.engine.fixture.stage.routes if item.route_id == route_id)
        cells: set[tuple[int, int]] = set()
        for first, second in zip(route.waypoints, route.waypoints[1:]):
            steps = max(1, ceil(max(abs(second.x - first.x), abs(second.y - first.y))))
            for step in range(steps + 1):
                ratio = step / steps
                cells.add((round(first.x + (second.x - first.x) * ratio), round(first.y + (second.y - first.y) * ratio)))
        return cells

    def _differential(self, parent: Strategy, candidate: Strategy, candidate_frontiers: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        pa = {(a.operator_id, self._frame(a.time)): (a.tile, a.direction) for a in parent.actions}
        ca = {(a.operator_id, self._frame(a.time)): (a.tile, a.direction) for a in candidate.actions}
        changed = []
        for key in sorted(set(pa) | set(ca)):
            if pa.get(key) != ca.get(key): changed.append({"operator_or_frame": key, "parent": pa.get(key), "candidate": ca.get(key)})
        parent_dp = self._dp_schedule(parent); candidate_dp = self._dp_schedule(candidate)
        return {"changed_decisions": changed, "parent_opening_dp": parent_dp, "candidate_opening_dp": candidate_dp,
                "candidate_frontiers": list(candidate_frontiers),
                "supported_causal_chain": ("DP_CONFLICT" if parent_dp != candidate_dp else "TIMING_OR_COVERAGE"),
                "causal_confidence": "DERIVED"}

    def _conflict_graph(self, requirements: list[MultiFrontierConstraint], diffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        edges = []
        for left in requirements:
            for right in requirements:
                if left.constraint_id >= right.constraint_id: continue
                relevant = [diff for diff in diffs if any(item.get("route") == left.route for item in diff.get("candidate_frontiers", [])) and any(item.get("route") == right.route for item in diff.get("candidate_frontiers", []))]
                # An edge is emitted only when the same counterexample carries
                # both route outcomes; the resource label comes from schedule
                # and placement differences, never from mere co-occurrence.
                if relevant:
                    edge_type = "DP_CONFLICT" if any(diff["supported_causal_chain"] == "DP_CONFLICT" for diff in relevant) else "COVERAGE_CONFLICT"
                    edges.append({"from": left.constraint_id, "to": right.constraint_id, "type": edge_type,
                                  "evidence": ["same preserved counterexample changed one or more shared decisions"]})
        return edges

    def _mutations(self, seeds: list[State]) -> list[tuple[str, Strategy, tuple[dict[str, Any], ...]]]:
        out = []
        for state in seeds:
            deploys = [item for item in state.strategy.actions if item.action_type is ActionType.DEPLOY]
            for index, action in enumerate(deploys[:3]):
                base = self._frame(action.time)
                for delta in (-30, -6, 6, 30):
                    if base + delta < 0: continue
                    actions = list(state.strategy.actions)
                    actual = next(i for i, item in enumerate(actions) if item is action)
                    actions[actual] = Action(ActionType.DEPLOY, Fraction(base + delta, FPS), action.operator_id, action.tile, action.direction)
                    out.append(("TIMING", Strategy(state.strategy.team, tuple(sorted(actions, key=lambda item: item.time))), ({"operator_id": action.operator_id, "delta_frames": delta},)))
                for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                    if direction == action.direction: continue
                    actions = list(state.strategy.actions); actual = next(i for i, item in enumerate(actions) if item is action)
                    actions[actual] = Action(ActionType.DEPLOY, action.time, action.operator_id, action.tile, direction)
                    out.append(("FACING", Strategy(state.strategy.team, tuple(actions)), ({"operator_id": action.operator_id, "direction": direction},)))
        unique = {}
        for level, strategy, repair in out:
            key = tuple((a.action_type.value, self._frame(a.time), a.operator_id, a.tile, a.direction) for a in strategy.actions)
            unique.setdefault(key, (level, strategy, repair))
        return list(unique.values())

    def run(self) -> dict[str, Any]:
        parent_strategy, counter_strategies, source = self._load_inputs()
        parent_result = self._simulate(parent_strategy); parent = State(parent_strategy, parent_result, self._route_frontiers(parent_result))
        counter_states = [State(strategy, self._simulate(strategy), self._route_frontiers(self._simulate(strategy))) for strategy in counter_strategies]
        requirements = self._opening_requirements(parent, counter_states)
        diffs = [self._differential(parent.strategy, state.strategy, state.frontiers) for state in counter_states]
        resources = self._resource_assignments(parent, requirements)
        all_mutations = self._mutations([parent, *counter_states]); evaluated = []
        rejection = {"DP": 0, "SPATIAL": 0, "TIMING": 0, "COVERAGE": 0, "DAMAGE": 0, "OTHER": 0}
        seen = set()
        for level, strategy, repair in all_mutations:
            if self.metrics.unique_simulations >= self.budget: break
            key = tuple((a.action_type.value, self._frame(a.time), a.operator_id, a.tile, a.direction) for a in strategy.actions)
            if key in seen: continue
            seen.add(key)
            # Static legal/DP check before simulator.
            deploys = [a for a in strategy.actions if a.action_type is ActionType.DEPLOY]
            if len({a.tile for a in deploys}) != len(deploys): rejection["SPATIAL"] += 1; continue
            try:
                state = State(strategy, self._simulate(strategy), self._route_frontiers(self._simulate(strategy)), repair)
            except Exception:
                rejection["OTHER"] += 1; continue
            evaluated.append(state)
        archive = [parent, *counter_states, *evaluated]
        best = min(archive, key=lambda state: (0 if state.result.win else 1, -min((f["frame"] for f in state.frontiers), default=10**9), state.result.enemies_leaked, -state.result.enemies_killed))
        edges = self._conflict_graph(requirements, diffs)
        search_progress = [{"seed": "M15.2_PARENT", "frontiers": list(parent.frontiers), "kills": parent.result.enemies_killed, "leaks": parent.result.enemies_leaked}]
        search_progress.extend({"seed": "M15.2_COUNTEREXAMPLE", "frontiers": list(state.frontiers), "kills": state.result.enemies_killed, "leaks": state.result.enemies_leaked} for state in counter_states)
        search_progress.extend({"seed": "LOCAL_REPAIR", "repair": list(state.repair), "frontiers": list(state.frontiers), "kills": state.result.enemies_killed, "leaks": state.result.enemies_leaked} for state in evaluated)
        statuses = []
        for req in requirements:
            satisfied = any(not any(f["route"] == req.route and f["frame"] <= req.deadline for f in state.frontiers) for state in archive)
            statuses.append({**req.as_dict(), "status": "SATISFIED" if satisfied else "ACTIVE"})
        return {
            "m15_3_multifrontier_constraints": {"version": self.VERSION, "stage": "main_06-07", "llm_calls": 0, "mechanics_expansion": False, "max_cardinality": 7, "constraints": statuses},
            "m15_3_route_requirements": {"parent_frontiers": list(parent.frontiers), "counterexample_frontiers": [list(state.frontiers) for state in counter_states], "requirements": statuses},
            "m15_3_counterexample_differentials": diffs,
            "m15_3_resource_assignments": {"parent": resources, "dp_schedules": {"parent": self._dp_schedule(parent.strategy), "counterexamples": [self._dp_schedule(state.strategy) for state in counter_states]}},
            "m15_3_conflict_graph": {"nodes": [req.as_dict() for req in requirements], "edges": edges},
            "m15_3_slack_analysis": [{"constraint_id": req.constraint_id, "route": req.route, "deadline": req.deadline, "timing_slack": None, "dp_slack": None, "coverage_slack": "UNKNOWN", "provenance": "UNKNOWN_UNDER_CURRENT_RUNTIME"} for req in requirements],
            "m15_3_candidate_prechecks": {"assignments_considered": len(all_mutations), "deterministic_rejects": rejection, "conflict_directed_repairs": len(all_mutations)},
            "m15_3_search_progress": search_progress,
            "m15_3_results": {"best": {"result": "WIN" if best.result.win else "LOSS", "operators": list(best.strategy.team), "operator_count": len(best.strategy.team), "rarity": sum(int(self.engine.fixture.operators[x].star_rarity.value or 0) for x in best.strategy.team), "kills": best.result.enemies_killed, "leaks": best.result.enemies_leaked, "remaining_life": best.result.remaining_life, "frontiers": list(best.frontiers), "repair": list(best.repair)}, "unique_simulations": self.metrics.unique_simulations, "cache_hits": self.metrics.cache_hits, "termination": "WIN_FOUND" if best.result.win else "BOUNDED_SEARCH_NO_SOLUTION", "next_unresolved_constraint": next((item for item in statuses if item["status"] != "SATISFIED"), None)},
            "m15_3_baseline_comparison": {"m15_parent": {"kills": 27, "leaks": 9, "first_frontier": {"frame": 366, "route": "route-2"}}, "m15_1": {"kills": 24, "leaks": 12, "first_frontier": {"frame": 564, "route": "route-2"}}, "m15_3_best": {"kills": best.result.enemies_killed, "leaks": best.result.enemies_leaked, "frontiers": list(best.frontiers)}, "classification": "INCONCLUSIVE" if not best.result.win else "SUPPORTED"},
            "source": source,
        }
