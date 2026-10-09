"""M15.2 quantified, current-mechanics frontier requirement repair.

This is intentionally a local feasibility tool.  It replays the preserved
M15.1 strategy, derives requirements from its exact event trace, then mutates
only actions that can affect that trace.  It never enumerates rosters or uses
an LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
from math import ceil
from pathlib import Path
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.benchmark import render_human_timeline
from arknights_planner.models.runtime import CombatOutputType
from arknights_planner.models.simulation import EventType, SimulationEvent, SimulationResult
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig, M11SearchMetrics
from arknights_planner.search.m15 import AssignedPlacement, ConstraintGuidedFeasibilityPlanner, FailureFrontier, FailureType, PartialStrategy
from arknights_planner.simulator import SimulationConfig
from arknights_planner.simulator.combat_rules import arts_damage, attack_interval, physical_damage
from arknights_planner.timing import strategy_to_timeline


FPS = 30
MECHANICS_PROVENANCE = (
    "PRTS physical damage formula",
    "PRTS Arts damage formula",
    "PRTS 5% minimum physical/Arts damage",
    "PRTS attack-speed formula",
    "PRTS ATK additive-before-multiplicative ordering",
)


def _details(event: SimulationEvent | None) -> dict[str, Any]:
    return dict(event.details) if event else {}


@dataclass(frozen=True)
class FrontierRequirement:
    requirement_id: str
    requirement_type: str
    route_id: str
    deadline_frame: int
    enemy_instance_id: str
    provenance: str
    evidence: tuple[str, ...]
    observed_remaining_hp: float | None = None
    observed_damage: float | None = None
    observed_attacks: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id, "requirement_type": self.requirement_type,
            "route_id": self.route_id, "deadline_frame": self.deadline_frame,
            "enemy_instance_id": self.enemy_instance_id, "provenance": self.provenance,
            "evidence": list(self.evidence), "observed_remaining_hp": self.observed_remaining_hp,
            "observed_damage": self.observed_damage, "observed_attacks": self.observed_attacks,
            "semantic_requirement": "prevent this enemy leaking by its current deadline; observed damage is candidate-specific, not an invariant additive threshold",
        }


@dataclass(frozen=True)
class RequirementState:
    strategy: Strategy
    result: SimulationResult
    frontier: FailureFrontier
    solved_requirements: tuple[str, ...]
    repair_level: str
    repair: tuple[dict[str, Any], ...]


class FrontierRequirementSolver:
    """Bounded M15.2 closed loop with accumulated earlier-frontier constraints."""

    VERSION = "m15.2-frontier-requirement-v1"

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter,
                 policy: RealSimulationApproximationPolicy, parent_path: Path,
                 simulation_budget: int = 400):
        self.adapter, self.policy, self.parent_path = adapter, policy, parent_path
        self.simulation_budget = simulation_budget
        configurations = adapter.m13_low_rarity_configurations()
        self.engine = M11MinimumSquadSearch(
            adapter=adapter, stage_id_or_code="6-8", policy=policy, operator_pool=configurations,
            config=M11SearchConfig(max_squad_size=7, max_teams=1, placement_options_per_operator=64,
                                   beam_width=8, simulation_config=SimulationConfig(dt=.2, max_time=300.0)),
        )
        self.helper = ConstraintGuidedFeasibilityPlanner(
            adapter=adapter, policy=policy, beam_width=8, simulation_budget=1, max_cardinality=7,
        )
        self.metrics = M11SearchMetrics()
        self.prechecks: list[dict[str, Any]] = []
        self.history: list[dict[str, Any]] = []
        self.progress: list[dict[str, Any]] = []
        self.cache_hits_at_start = 0

    def _frame(self, value: float | Fraction) -> int:
        return self.engine.config.frame_clock.frame_for_seconds(value)

    def _parent(self) -> Strategy:
        row = json.loads(self.parent_path.read_text(encoding="utf-8"))["guided"]
        actions = tuple(
            Action(ActionType(item["type"]), Fraction(int(item["frame"]), FPS), item["operator_id"],
                   tuple(item["tile"]) if item.get("tile") is not None else None, item.get("direction", "RIGHT"))
            for item in row["actions"]
        )
        return Strategy(tuple(row["operators"]), actions)

    def _frontier(self, strategy: Strategy, result: SimulationResult) -> FailureFrontier:
        assigned = tuple(AssignedPlacement("M15_2", item.operator_id, item.tile, item.direction, ())
                         for item in strategy.actions if item.action_type is ActionType.DEPLOY)
        frontier = self.helper._frontier(PartialStrategy(assignments=assigned, actions=strategy.actions), result)
        # The generic M15 frontier classifies every leak as EARLY_LEAK.  For
        # M15.2 the preserved frame-564 wolf has positive, sub-lethal damage;
        # retain that supported causal distinction without treating its
        # observed HP remainder as a universal threshold.
        if frontier.routes:
            leak = next((item for item in result.events if item.event_type is EventType.ENEMY_LEAK), None)
            if leak:
                received = sum(float(_details(item).get("amount", 0.0)) for item in result.events
                                if item.event_type is EventType.DAMAGE and item.target_id == leak.source_id
                                and item.source_id in self.engine.fixture.operators)
                spawn = next((item for item in result.events if item.event_type is EventType.SPAWN and item.source_id == leak.source_id), None)
                enemy_id = str(_details(spawn).get("enemy_id", ""))
                enemy = self.engine.fixture.enemies.get(enemy_id)
                max_hp = float(enemy.stats.max_hp.value) if enemy and enemy.stats.max_hp.value is not None else None
                if received > 0 and max_hp is not None and received < max_hp:
                    frontier = FailureFrontier(frontier.frame, FailureType.DAMAGE_INSUFFICIENT,
                                               frontier.routes, frontier.enemy_ids, frontier.affected_operator_ids,
                                               frontier.relevant_tiles, ("DAMAGE",), frontier.dp_state,
                                               frontier.deployment_slots, frontier.evidence, frontier.confidence)
        return frontier

    def _evaluate(self, strategy: Strategy, *, repair_level: str, repair: tuple[dict[str, Any], ...], solved: tuple[str, ...]) -> RequirementState | None:
        if not self._basic_static_legal(strategy):
            return None
        evaluation = self.engine._evaluate(strategy, self.metrics)
        return RequirementState(strategy, evaluation.result, self._frontier(strategy, evaluation.result), solved, repair_level, repair)

    def _cost(self, operator_id: str) -> float:
        operator = self.engine.fixture.operators[operator_id]
        return max(0.0, float(operator.phases[0].stats_max.cost.value or 0) + operator.deployment_cost_delta)

    def _basic_static_legal(self, strategy: Strategy) -> bool:
        deploys = [item for item in strategy.actions if item.action_type is ActionType.DEPLOY]
        if len(deploys) > 7 or len({item.operator_id for item in deploys}) != len(deploys):
            return False
        if len({item.tile for item in deploys}) != len(deploys):
            return False
        dp = float(self.engine.fixture.stage.initial_dp.value or 0); cursor = 0
        rate = float(self.engine.fixture.stage.dp_per_second)
        for action in sorted(deploys, key=lambda item: (item.time, item.operator_id)):
            frame = self._frame(action.time); operator = self.engine.fixture.operators.get(action.operator_id)
            if operator is None or frame < cursor or self.engine.simulator._deployment_tile_reason(operator, self.engine.fixture.stage, action.tile):
                return False
            dp += rate * (frame - cursor) / FPS
            if dp + 1e-9 < self._cost(action.operator_id):
                return False
            dp -= self._cost(action.operator_id); cursor = frame
        return True

    def _route_cells(self, route_id: str) -> set[tuple[int, int]]:
        route = next(item for item in self.engine.fixture.stage.routes if item.route_id == route_id)
        return set(self.helper._route_cells(route))

    def _covers_route(self, operator_id: str, tile: tuple[int, int], direction: str, route_id: str) -> bool:
        operator = self.engine.fixture.operators[operator_id]
        if operator.position.value == "MELEE" and tile in self._route_cells(route_id):
            return True
        covered = self.engine.simulator.range_transformer.covered_tiles(origin=tile, offsets=operator.attack_range, direction=direction)
        return bool(covered & self._route_cells(route_id))

    def _route_spawn(self, route_id: str, enemy_id: str):
        return next(item for item in self.engine.fixture.stage.spawn_events if item.route_id == route_id and item.enemy_id == enemy_id)

    def _target_trace(self, result: SimulationResult, *, route_id: str = "route-2", preferred_instance: str | None = None) -> dict[str, Any]:
        spawns = [item for item in result.events if item.event_type is EventType.SPAWN and _details(item).get("route_id") == route_id]
        if preferred_instance:
            spawn = next((item for item in spawns if item.source_id == preferred_instance), None)
        else:
            spawn = spawns[0] if spawns else None
        if spawn is None:
            return {"status": "UNKNOWN", "reason": "route spawn missing"}
        instance = spawn.source_id; data = _details(spawn); enemy_id = str(data.get("enemy_id", "UNKNOWN"))
        enemy = self.engine.fixture.enemies.get(enemy_id)
        attacks = [item for item in result.events if item.event_type is EventType.ATTACK_START and item.target_id == instance]
        damage = [item for item in result.events if item.event_type is EventType.DAMAGE and item.target_id == instance]
        leak = next((item for item in result.events if item.event_type is EventType.ENEMY_LEAK and item.source_id == instance), None)
        death = next((item for item in result.events if item.event_type is EventType.ENEMY_DEATH and item.target_id == instance), None)
        max_hp = float(enemy.stats.max_hp.value) if enemy and enemy.stats.max_hp.value is not None else None
        total = sum(float(_details(item).get("amount", 0.0)) for item in damage)
        return {
            "enemy_instance_id": instance, "enemy_id": enemy_id, "route": route_id, "spawn_frame": self._frame(spawn.time),
            "max_hp": max_hp, "defense": float(enemy.stats.defense.value) if enemy and enemy.stats.defense.value is not None else None,
            "magic_resistance": float(enemy.stats.magic_resistance.value) if enemy and enemy.stats.magic_resistance.value is not None else None,
            "first_interaction_frame": self._frame(attacks[0].time) if attacks else None,
            "attack_frames": [self._frame(item.time) for item in attacks], "attackers": sorted({item.source_id for item in attacks}),
            "damage_hits": [{"frame": self._frame(item.time), "attacker": item.source_id, "damage_type": _details(item).get("kind", "UNKNOWN"), "damage": float(_details(item).get("amount", 0.0))} for item in damage],
            "observed_damage": total, "observed_attacks": len(attacks), "hp_at_terminal": max(0.0, max_hp - total) if max_hp is not None else None,
            "leak_frame": self._frame(leak.time) if leak else None, "death_frame": self._frame(death.time) if death else None,
        }

    @staticmethod
    def _frontier_dict(item: FailureFrontier) -> dict[str, Any]:
        return {"frame": item.frame, "failure_type": item.failure_type.value, "routes": list(item.routes),
                "enemy_ids": list(item.enemy_ids), "required_capabilities": list(item.required_capabilities),
                "evidence": list(item.evidence), "confidence": item.confidence}

    def _requirements(self, trace: dict) -> tuple[FrontierRequirement, FrontierRequirement]:
        instance = str(trace["enemy_instance_id"])
        interaction = FrontierRequirement(
            "R1_ROUTE_2_INTERACTION_366", "INTERACTION_REQUIREMENT", "route-2", 366, instance,
            "SIMULATION_DERIVED", ("M15 parent leaked route-2 at frame 366 before interaction.",
                                   "M15.1 parent is accepted only if it retains pre-366 interaction and avoids that leak."),
        )
        damage = FrontierRequirement(
            "R2_ROUTE_2_DAMAGE_564", "DAMAGE_REQUIREMENT", "route-2", 564, instance,
            "SIMULATION_EXACT", ("Current replay of preserved M15.1 guided candidate leaked this exact instance at frame 564.",
                                   "Observed remaining HP is candidate-specific and is not an invariant additive-damage target."),
            trace.get("hp_at_terminal"), trace.get("observed_damage"), trace.get("observed_attacks"),
        )
        return interaction, damage

    def _requirement_status(self, state: RequirementState, requirements: tuple[FrontierRequirement, ...]) -> tuple[tuple[str, ...], list[dict[str, Any]]]:
        trace = self._target_trace(state.result, preferred_instance=requirements[0].enemy_instance_id)
        attacks = trace.get("attack_frames", [])
        leak = trace.get("leak_frame")
        solved: list[str] = []; conflicts: list[dict[str, Any]] = []
        r1, r2 = requirements
        if any(frame <= r1.deadline_frame for frame in attacks) and (leak is None or leak > r1.deadline_frame):
            solved.append(r1.requirement_id)
        else:
            conflicts.append({"type": "CONSTRAINT_CONFLICT", "requirement": r1.requirement_id, "resource_cause": "target interaction", "trace": trace})
        if leak is None or leak > r2.deadline_frame:
            solved.append(r2.requirement_id)
        return tuple(solved), conflicts

    def _damage_per_hit(self, operator_id: str, trace: dict[str, Any]) -> float | None:
        operator = self.engine.fixture.operators[operator_id]
        stats = operator.phases[0].stats_max
        atk = stats.atk.value
        if atk is None or trace.get("defense") is None or trace.get("magic_resistance") is None:
            return None
        if operator.combat_output is CombatOutputType.HEAL:
            return None
        return arts_damage(float(atk), float(trace["magic_resistance"])) if operator.damage_type == "ARTS" else physical_damage(float(atk), float(trace["defense"]))

    def _candidate_placements(self, operator_id: str, *, route_id: str, excluded: set[tuple[int, int]], limit: int = 6) -> list[dict[str, Any]]:
        operator = self.engine.fixture.operators[operator_id]
        kind = "GROUND" if operator.position.value == "MELEE" else "HIGH_GROUND"
        out = []
        for tile in self.engine.fixture.stage.stage_map.tiles:
            coordinate = (tile.x, tile.y)
            if not tile.buildable or tile.tile_kind != kind or coordinate in excluded:
                continue
            for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                if self._covers_route(operator_id, coordinate, direction, route_id):
                    out.append({"tile": coordinate, "direction": direction})
        return sorted(out, key=lambda item: (item["tile"], item["direction"]))[:limit]

    def _earliest_contact_frame(self, operator_id: str, tile: tuple[int, int], direction: str, trace: dict[str, Any]) -> int | None:
        try:
            spawn = self._route_spawn(str(trace["route"]), str(trace["enemy_id"]))
        except StopIteration:
            return None
        route = next(item for item in self.engine.fixture.stage.routes if item.route_id == trace["route"])
        operator = self.engine.fixture.operators[operator_id]
        if operator.position.value == "MELEE" and tile in self._route_cells(trace["route"]):
            return self.helper._entry_frame(route, spawn, tile)
        covered = self.engine.simulator.range_transformer.covered_tiles(origin=tile, offsets=operator.attack_range, direction=direction)
        frames = [self.helper._entry_frame(route, spawn, cell) for cell in covered & self._route_cells(trace["route"])]
        finite = [frame for frame in frames if frame is not None]
        return min(finite) if finite else None

    def _contribution_opportunities(self, trace: dict[str, Any], deadline: int) -> list[dict[str, Any]]:
        rows = []
        initial_dp = float(self.engine.fixture.stage.initial_dp.value or 0); rate = float(self.engine.fixture.stage.dp_per_second)
        for operator_id in sorted(self.engine.fixture.operators):
            operator = self.engine.fixture.operators[operator_id]
            cost = self._cost(operator_id)
            earliest_deploy = max(0, ceil(max(0.0, cost - initial_dp) / rate * FPS)) if rate else None
            placements = self._candidate_placements(operator_id, route_id="route-2", excluded=set(), limit=64)
            possibilities = []
            for placement in placements:
                contact = self._earliest_contact_frame(operator_id, placement["tile"], placement["direction"], trace)
                if contact is None or earliest_deploy is None:
                    continue
                first = max(earliest_deploy, contact)
                interval = attack_interval(float(operator.phases[0].stats_max.attack_interval.value or 1.0))
                frames = list(range(first, deadline + 1, max(1, round(interval * FPS))))
                possibilities.append({"tile": placement["tile"], "direction": placement["direction"], "earliest_possible_interaction_frame": first, "possible_attack_frames_before_deadline_estimate": frames})
            rows.append({"operator_id": operator_id, "deployment_cost": cost, "earliest_legal_deployment_frame_from_initial_economy": earliest_deploy,
                         "tile_type": operator.position.value, "damage_type": operator.damage_type, "attack_interval": float(operator.phases[0].stats_max.attack_interval.value or 0),
                         "damage_per_hit_against_frontier_enemy": self._damage_per_hit(operator_id, trace),
                         "supported_skill": operator.synthetic_skill.skill_id if operator.synthetic_skill else None,
                         "route_2_opportunities": possibilities[:6], "causally_capable": bool(possibilities)})
        return rows

    def _action_dict(self, item: Action) -> dict[str, Any]:
        return {"type": item.action_type.value, "operator_id": item.operator_id, "frame": self._frame(item.time), "tile": item.tile, "direction": item.direction}

    def _replace_deploy(self, strategy: Strategy, index: int, *, frame: int | None = None, tile: tuple[int, int] | None = None,
                        direction: str | None = None, operator_id: str | None = None) -> Strategy:
        actions = list(strategy.actions); deploy_indices = [i for i, action in enumerate(actions) if action.action_type is ActionType.DEPLOY]
        real_index = deploy_indices[index]; old = actions[real_index]
        actions[real_index] = Action(ActionType.DEPLOY, Fraction(frame if frame is not None else self._frame(old.time), FPS),
                                    operator_id or old.operator_id, tile or old.tile, direction or old.direction)
        team = tuple(dict.fromkeys(item.operator_id for item in actions if item.action_type is ActionType.DEPLOY))
        return Strategy(team, tuple(sorted(actions, key=lambda item: (item.time, item.action_type.value, item.operator_id))))

    def _relevant_deploy_indices(self, state: RequirementState, trace: dict[str, Any]) -> list[int]:
        deploys = [item for item in state.strategy.actions if item.action_type is ActionType.DEPLOY]
        direct = {item.source_id for item in state.result.events if item.event_type is EventType.ATTACK_START and item.target_id == trace["enemy_instance_id"]}
        indices = [index for index, item in enumerate(deploys) if item.operator_id in direct]
        for index, item in enumerate(deploys):
            if self._frame(item.time) <= 564 and self._covers_route(item.operator_id, item.tile, item.direction, "route-2") and index not in indices:
                indices.append(index)
        return sorted(indices)

    def _counterfactuals(self, parent: RequirementState, trace: dict[str, Any]) -> list[dict[str, Any]]:
        by_attacker: dict[str, list[float]] = {}
        for hit in trace["damage_hits"]:
            by_attacker.setdefault(hit["attacker"], []).append(float(hit["damage"]))
        deficits = []
        for operator_id, hits in sorted(by_attacker.items()):
            damage = hits[0]; remaining = float(trace["hp_at_terminal"])
            deficits.append({"operator_id": operator_id, "damage_per_hit": damage, "one_additional_hit_kills": damage >= remaining,
                             "additional_hits_required": ceil(remaining / damage)})
        local = []
        for index in self._relevant_deploy_indices(parent, trace):
            action = [item for item in parent.strategy.actions if item.action_type is ActionType.DEPLOY][index]
            for delta in (-90, -60, -30, -6):
                frame = max(0, self._frame(action.time) + delta)
                candidate = self._replace_deploy(parent.strategy, index, frame=frame)
                if not self._basic_static_legal(candidate):
                    local.append({"operator_id": action.operator_id, "delta_frames": delta, "precheck": "DP_OR_LEGALITY_REJECT"})
                    continue
                state = self._evaluate(candidate, repair_level="COUNTERFACTUAL", repair=(), solved=())
                changed = self._target_trace(state.result, preferred_instance=trace["enemy_instance_id"]) if state else {}
                local.append({"operator_id": action.operator_id, "delta_frames": delta, "precheck": "ACCEPTED", "target": changed})
        later = []
        for attacker in sorted(by_attacker):
            next_event = next((item for item in parent.result.events if item.event_type is EventType.ATTACK_START and item.source_id == attacker and self._frame(item.time) > 564), None)
            later.append({"operator_id": attacker, "next_attack_after_deadline": self._frame(next_event.time) if next_event else None,
                          "note": "No event targeting the leaked instance can occur after its leak; this is the attacker's next other-target event."})
        return [{"exact_observed_damage": trace["observed_damage"], "exact_observed_remaining_hp": trace["hp_at_terminal"],
                 "exact_observed_attacks": trace["observed_attacks"], "attacker_hit_requirements": deficits,
                 "post_deadline_schedule": later, "earlier_deployment_counterfactuals": local}]

    def _precheck(self, strategy: Strategy, *, trace: dict[str, Any], label: str) -> tuple[bool, str | None]:
        deploys = [item for item in strategy.actions if item.action_type is ActionType.DEPLOY]
        if not self._basic_static_legal(strategy):
            return False, "DP_OR_LEGALITY"
        relevant = [item for item in deploys if self._frame(item.time) <= 564 and self._covers_route(item.operator_id, item.tile, item.direction, "route-2")]
        if not relevant:
            return False, "NO_ROUTE_2_COVERAGE"
        if all((self._earliest_contact_frame(item.operator_id, item.tile, item.direction, trace) or 10**9) > 564 for item in relevant):
            return False, "INTERACTION_AFTER_DEADLINE"
        return True, None

    def _candidate_specs(self, parent: RequirementState, trace: dict[str, Any], opportunities: list[dict[str, Any]]) -> list[tuple[str, Strategy, tuple[dict[str, Any], ...]]]:
        deploys = [item for item in parent.strategy.actions if item.action_type is ActionType.DEPLOY]
        relevant = self._relevant_deploy_indices(parent, trace); out = []
        # Level A: timing and local facing/placement for direct frontier actors.
        for index in relevant:
            old = deploys[index]
            for delta in (-90, -60, -30, -6, 6, 30):
                if self._frame(old.time) + delta >= 0:
                    out.append(("A_TIMING", self._replace_deploy(parent.strategy, index, frame=self._frame(old.time) + delta),
                                ({"kind": "TIMING", "operator_id": old.operator_id, "delta_frames": delta},)))
            occupied = {item.tile for pos, item in enumerate(deploys) if pos != index}
            for placement in self._candidate_placements(old.operator_id, route_id="route-2", excluded=occupied, limit=5):
                if (placement["tile"], placement["direction"]) != (old.tile, old.direction):
                    out.append(("A_SPATIAL_FACING", self._replace_deploy(parent.strategy, index, tile=placement["tile"], direction=placement["direction"]),
                                ({"kind": "SPATIAL_FACING", "operator_id": old.operator_id, **placement},)))
        # Level B: only adjacent early actions; swapping preserves every later intent.
        for index in relevant:
            if index + 1 < len(deploys) and self._frame(deploys[index + 1].time) <= 564:
                first, second = deploys[index], deploys[index + 1]
                candidate = self._replace_deploy(parent.strategy, index, frame=self._frame(second.time))
                candidate = self._replace_deploy(candidate, index + 1, frame=self._frame(first.time))
                out.append(("B_ORDER", candidate, ({"kind": "ORDER_SWAP", "operators": [first.operator_id, second.operator_id]},)))
        # Level C: one operator replacement. Candidates are only same-position,
        # route-capable operators with an equal/better per-hit contribution or lower cost.
        by_id = {row["operator_id"]: row for row in opportunities}
        used = set(parent.strategy.team)
        for index in relevant:
            old = deploys[index]; old_operator = self.engine.fixture.operators[old.operator_id]
            old_damage = self._damage_per_hit(old.operator_id, trace) or 0.0
            alternatives = []
            for operator_id, operator in self.engine.fixture.operators.items():
                if operator_id in used or operator.position.value != old_operator.position.value:
                    continue
                row = by_id[operator_id]
                if not row["causally_capable"]:
                    continue
                damage = row["damage_per_hit_against_frontier_enemy"] or 0.0
                if damage < old_damage and self._cost(operator_id) >= self._cost(old.operator_id):
                    continue
                alternatives.append((-(damage - old_damage), self._cost(operator_id), operator_id))
            for _, _, operator_id in sorted(alternatives)[:6]:
                occupied = {item.tile for pos, item in enumerate(deploys) if pos != index}
                for placement in self._candidate_placements(operator_id, route_id="route-2", excluded=occupied, limit=2):
                    out.append(("C_SUBSTITUTION", self._replace_deploy(parent.strategy, index, operator_id=operator_id, tile=placement["tile"], direction=placement["direction"]),
                                ({"kind": "SUBSTITUTION", "removed": old.operator_id, "added": operator_id, **placement},)))
        unique = {}
        for level, strategy, repair in out:
            key = tuple((item.action_type.value, self._frame(item.time), item.operator_id, item.tile, item.direction) for item in strategy.actions)
            unique.setdefault(key, (level, strategy, repair))
        return list(unique.values())

    @staticmethod
    def _rank(state: RequirementState) -> tuple:
        result, frontier = state.result, state.frontier
        return (0 if result.win else 1, -frontier.frame, result.enemies_leaked, -result.enemies_killed, -result.remaining_life,
                tuple((item.operator_id, item.time, item.tile, item.direction) for item in state.strategy.actions))

    def _row(self, state: RequirementState) -> dict[str, Any]:
        return {"result": "WIN" if state.result.win else "LOSS", "operators": list(state.strategy.team), "operator_count": len(state.strategy.team),
                "rarity": sum(int(self.engine.fixture.operators[item].star_rarity.value or 0) for item in state.strategy.team),
                "actions": [self._action_dict(item) for item in state.strategy.actions], "kills": state.result.enemies_killed,
                "leaks": state.result.enemies_leaked, "remaining_life": state.result.remaining_life,
                "earliest_failure_frontier": self._frontier_dict(state.frontier), "repair_level": state.repair_level,
                "repair": list(state.repair), "solved_requirements": list(state.solved_requirements)}

    def _two_change_specs(self, parents: list[RequirementState], trace: dict[str, Any]) -> list[tuple[str, Strategy, tuple[dict[str, Any], ...]]]:
        out = []
        for parent in parents[:6]:
            # Add one small timing repair to a spatial/substitution repair. The
            # second change stays in the same route-2 causal neighborhood.
            for index in self._relevant_deploy_indices(parent, trace)[:2]:
                old = [item for item in parent.strategy.actions if item.action_type is ActionType.DEPLOY][index]
                for delta in (-30, -6, 6, 30):
                    frame = self._frame(old.time) + delta
                    if frame >= 0:
                        candidate = self._replace_deploy(parent.strategy, index, frame=frame)
                        out.append(("D_TWO_LOCAL_CHANGES", candidate, (*parent.repair, {"kind": "TIMING", "operator_id": old.operator_id, "delta_frames": delta})))
        unique = {}
        for level, strategy, repair in out:
            key = tuple((item.action_type.value, self._frame(item.time), item.operator_id, item.tile, item.direction) for item in strategy.actions)
            unique.setdefault(key, (level, strategy, repair))
        return list(unique.values())

    def run(self) -> dict[str, Any]:
        parent = self._evaluate(self._parent(), repair_level="PRESERVED_PARENT", repair=(), solved=())
        if parent is None:
            raise RuntimeError("preserved M15.1 parent is illegal under current runtime")
        trace = self._target_trace(parent.result)
        requirements = self._requirements(trace)
        solved, conflicts = self._requirement_status(parent, requirements)
        parent = RequirementState(parent.strategy, parent.result, parent.frontier, solved, parent.repair_level, parent.repair)
        opportunities = self._contribution_opportunities(trace, 564)
        counterfactuals = self._counterfactuals(parent, trace)
        analytical = self._candidate_specs(parent, trace, opportunities)
        accepted: list[RequirementState] = [parent]; archive: list[RequirementState] = [parent]
        precheck_counts: dict[str, int] = {}
        for level, candidate, repair in analytical:
            if self.metrics.unique_simulations >= self.simulation_budget:
                break
            legal, reason = self._precheck(candidate, trace=trace, label=level)
            self.prechecks.append({"level": level, "repair": list(repair), "accepted": legal, "reason": reason})
            if not legal:
                precheck_counts[reason or "OTHER"] = precheck_counts.get(reason or "OTHER", 0) + 1
                continue
            state = self._evaluate(candidate, repair_level=level, repair=repair, solved=())
            if state is None:
                precheck_counts["OTHER"] = precheck_counts.get("OTHER", 0) + 1
                continue
            solved, conflicts = self._requirement_status(state, requirements)
            if requirements[0].requirement_id not in solved:
                self.history.extend(conflicts)
                continue
            state = RequirementState(state.strategy, state.result, state.frontier, solved, level, repair)
            accepted.append(state); archive.append(state)
            self.progress.append({"level": level, "repair": list(repair), "solved_requirements": list(solved),
                                  "next_frontier": self._frontier_dict(state.frontier), "result": self._row(state)})
            if state.result.win:
                break
        # Level D only composes repairs already verified against R1, never an
        # unrelated fresh mutation.
        if not any(item.result.win for item in accepted) and self.metrics.unique_simulations < self.simulation_budget:
            promising = sorted(accepted, key=self._rank)
            for level, candidate, repair in self._two_change_specs(promising, trace):
                if self.metrics.unique_simulations >= self.simulation_budget:
                    break
                legal, reason = self._precheck(candidate, trace=trace, label=level)
                self.prechecks.append({"level": level, "repair": list(repair), "accepted": legal, "reason": reason})
                if not legal:
                    precheck_counts[reason or "OTHER"] = precheck_counts.get(reason or "OTHER", 0) + 1
                    continue
                state = self._evaluate(candidate, repair_level=level, repair=repair, solved=())
                if state is None:
                    continue
                solved, conflicts = self._requirement_status(state, requirements)
                if requirements[0].requirement_id not in solved:
                    self.history.extend(conflicts); continue
                state = RequirementState(state.strategy, state.result, state.frontier, solved, level, repair)
                accepted.append(state); archive.append(state)
                self.progress.append({"level": level, "repair": list(repair), "solved_requirements": list(solved),
                                      "next_frontier": self._frontier_dict(state.frontier), "result": self._row(state)})
                if state.result.win:
                    break
        best = min(archive, key=self._rank)
        r2_solved = [item for item in archive if requirements[1].requirement_id in item.solved_requirements]
        termination = "WIN_FOUND" if best.result.win else "BOUNDED_SEARCH_NO_SOLUTION"
        # We intentionally never claim deterministic infeasibility: the local
        # opportunity filter proves only candidate irrelevance, not all possible
        # K<=7 strategies.
        unresolved = requirements[1].as_dict() if not r2_solved else {
            "derived_from": "next earliest frontier after route-2 requirement",
            "frontier": self._frontier_dict(best.frontier),
            "provenance": "SIMULATION_DERIVED",
        }
        timeline = human = robustness = None
        if best.result.win:
            timeline_obj = strategy_to_timeline(best.strategy, stage_id=self.engine.fixture.stage.stage_id, frame_clock=self.engine.config.frame_clock,
                                                simulator_mode="APPROXIMATE_REAL", approximation_policy_version=self.policy.cache_identity[0])
            robustness = self.engine._robustness(self.engine._evaluate(best.strategy, self.metrics), self.metrics)
            timeline = timeline_obj.to_dict()
            human = render_human_timeline(timeline=timeline_obj, repository=self.adapter.repository, simulator_result="WIN",
                                          robustness=str(robustness), approximation_warnings=self.engine.fixture.approximations_used)
        return {
            "m15_2_frontier_enemy_trace": trace,
            "m15_2_frontier_requirements": {"requirements": [item.as_dict() for item in requirements], "mechanics_provenance": list(MECHANICS_PROVENANCE)},
            "m15_2_counterfactual_damage": counterfactuals,
            "m15_2_contribution_opportunities": opportunities,
            "m15_2_candidate_prechecks": {"records": self.prechecks, "rejection_counts": precheck_counts,
                                             "analytical_candidates": len(analytical), "counterfactual_simulations": len([item for item in counterfactuals[0]["earlier_deployment_counterfactuals"] if item.get("precheck") == "ACCEPTED"])},
            "m15_2_constraint_history": self.history,
            "m15_2_requirement_progress": self.progress,
            "m15_2_results": {"best": self._row(best), "termination": termination, "unresolved_requirement": unresolved,
                                 "full_battle_unique_simulations": self.metrics.unique_simulations, "cache_hits": self.metrics.cache_hits,
                                 "r2_solved_candidates": len(r2_solved), "timeline": timeline, "robustness": robustness, "human_timeline": human},
            "m15_2_baseline_comparison": {"m15_parent": {"kills": 27, "leaks": 9, "first_frontier_frame": 366},
                                           "m15_1_guided": {"kills": 24, "leaks": 12, "first_frontier_frame": 564},
                                           "m15_2_best": self._row(best),
                                           "classification": "SUPPORTED" if best.result.win or best.frontier.frame > 564 else "NOT_SUPPORTED" if not r2_solved else "INCONCLUSIVE"},
        }
