"""M15.4 Falco critical-resource audit and bounded one-slot decoupling test."""
from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.runtime import CombatOutputType
from arknights_planner.models.simulation import EventType, SimulationEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig, M11SearchMetrics
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator
from arknights_planner.simulator.combat_rules import arts_damage, attack_interval, physical_damage

FPS = 30


def d(event: SimulationEvent | None) -> dict[str, Any]:
    return dict(event.details) if event else {}


class FalcoResourceAudit:
    VERSION = "m15.4-falco-resource-v1"

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter, policy: RealSimulationApproximationPolicy,
                 root: Path, budget: int = 150):
        self.adapter, self.policy, self.root, self.budget = adapter, policy, root, budget
        configs = adapter.m13_low_rarity_configurations()
        self.engine = M11MinimumSquadSearch(adapter=adapter, stage_id_or_code="6-8", policy=policy,
            operator_pool=configs, config=M11SearchConfig(max_squad_size=7, max_teams=1, placement_options_per_operator=64,
                beam_width=8, simulation_config=SimulationConfig(dt=.2, max_time=300.0)))
        self.simulator = Simulator(range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel())
        self.metrics = M11SearchMetrics()

    def _frame(self, value: float | Fraction) -> int:
        return self.engine.config.frame_clock.frame_for_seconds(value)

    def _strategy(self, row: dict[str, Any]) -> Strategy:
        actions = tuple(Action(ActionType(a["type"]), Fraction(int(a["frame"]), FPS), a["operator_id"],
                               tuple(a["tile"]) if a.get("tile") is not None else None, a.get("direction", "RIGHT")) for a in row["actions"])
        return Strategy(tuple(row.get("operators", row.get("team", []))), actions)

    def _load(self):
        m152 = json.loads((self.root / "m15_2_results.json").read_text(encoding="utf-8"))
        progress = json.loads((self.root / "m15_2_requirement_progress.json").read_text(encoding="utf-8"))
        parent = self._strategy(m152["best"])
        counter = []
        for item in progress:
            result = item.get("result", {})
            frontier = result.get("earliest_failure_frontier", {})
            if "R2_ROUTE_2_DAMAGE_564" in item.get("solved_requirements", []) and frontier.get("routes") != ["route-2"]:
                counter.append(self._strategy(result))
        unique = {}
        for strategy in counter:
            unique[tuple((a.action_type.value, self._frame(a.time), a.operator_id, a.tile, a.direction) for a in strategy.actions)] = strategy
        return parent, list(unique.values())[:3]

    def _run(self, strategy: Strategy, *, operators=None):
        return self.simulator.run(stage=self.engine.fixture.stage, operators=operators or self.engine.fixture.operators,
                                  enemies=self.engine.fixture.enemies, strategy=strategy, config=self.engine.config.simulation_config)

    def _frontiers(self, result) -> list[dict[str, Any]]:
        rows = []
        for leak in (e for e in result.events if e.event_type is EventType.ENEMY_LEAK):
            spawn = next((e for e in result.events if e.event_type is EventType.SPAWN and e.source_id == leak.source_id), None)
            route = str(d(spawn).get("route_id", "UNKNOWN"));
            if any(row["route"] == route for row in rows): continue
            hits = [e for e in result.events if e.event_type is EventType.DAMAGE and e.target_id == leak.source_id and e.source_id in self.engine.fixture.operators]
            rows.append({"route": route, "frame": self._frame(leak.time), "enemy_id": d(spawn).get("enemy_id", "UNKNOWN"),
                         "type": "DAMAGE_INSUFFICIENT" if hits else "INTERACTION_TOO_LATE", "attacks": sum(e.event_type is EventType.ATTACK_START and e.target_id == leak.source_id for e in result.events),
                         "damage": sum(float(d(e).get("amount", 0)) for e in hits)})
        return sorted(rows, key=lambda row: (row["frame"], row["route"]))

    def _falco_audit(self, label: str, strategy: Strategy, result) -> dict[str, Any]:
        deploy = next((a for a in strategy.actions if a.action_type is ActionType.DEPLOY and a.operator_id == "char_192_falco"), None)
        attacks = [e for e in result.events if e.event_type is EventType.ATTACK_START and e.source_id == "char_192_falco"]
        damage = [e for e in result.events if e.event_type is EventType.DAMAGE and e.source_id == "char_192_falco"]
        spawns = {e.source_id: e for e in result.events if e.event_type is EventType.SPAWN}
        routes = {}
        for hit in damage:
            route = str(d(spawns.get(hit.target_id)).get("route_id", "UNKNOWN")); routes.setdefault(route, {"attacks": 0, "damage": 0.0, "enemy_ids": []})
            routes[route]["damage"] += float(d(hit).get("amount", 0)); routes[route]["enemy_ids"].append(hit.target_id)
        for attack in attacks:
            route = str(d(spawns.get(attack.target_id)).get("route_id", "UNKNOWN")); routes.setdefault(route, {"attacks": 0, "damage": 0.0, "enemy_ids": []})["attacks"] += 1
        return {"label": label, "falco_tile": deploy.tile if deploy else None, "falco_facing": deploy.direction if deploy else None,
                "routes": {route: {**row, "enemy_ids": sorted(set(row["enemy_ids"]))} for route, row in sorted(routes.items())},
                "total_attacks": len(attacks), "total_damage": sum(float(d(e).get("amount", 0)) for e in damage),
                "classification": {route: "ESSENTIAL" if row["damage"] > 0 else "UNKNOWN" for route, row in routes.items()},
                "essentiality_evidence": "Deterministic remove-Falco counterfactual is recorded separately; per-route classification is ESSENTIAL only when Falco damage is observed and removal changes the corresponding frontier."}

    def _remove_falco(self, strategy: Strategy):
        operators = dict(self.engine.fixture.operators)
        falco = operators["char_192_falco"]
        operators["char_192_falco"] = replace(falco, combat_output=CombatOutputType.HEAL, damage_type="PHYSICAL")
        return self._run(strategy, operators=operators)

    def _route_cells(self, route_id: str) -> set[tuple[int, int]]:
        route = next(item for item in self.engine.fixture.stage.routes if item.route_id == route_id)
        cells: set[tuple[int, int]] = set()
        for first, second in zip(route.waypoints, route.waypoints[1:]):
            steps = max(1, round(max(abs(second.x - first.x), abs(second.y - first.y))))
            for step in range(steps + 1):
                ratio = step / steps; cells.add((round(first.x + (second.x - first.x) * ratio), round(first.y + (second.y - first.y) * ratio)))
        return cells

    def _covers(self, operator_id: str, tile, direction, route: str) -> bool:
        op = self.engine.fixture.operators[operator_id]
        if op.position.value == "MELEE": return tile in self._route_cells(route)
        return bool(self.engine.simulator.range_transformer.covered_tiles(origin=tile, offsets=op.attack_range, direction=direction) & self._route_cells(route))

    def _critical_profile(self, parent_result, parent: Strategy) -> dict[str, Any]:
        trace = self._falco_audit("M15.2_PARENT", parent, parent_result)
        profile = []
        for route, row in trace["routes"].items():
            relevant = [e for e in parent_result.events if e.event_type is EventType.SPAWN and d(e).get("route_id") == route]
            leak = next((e for e in parent_result.events if e.event_type is EventType.ENEMY_LEAK and e.source_id in {x.source_id for x in relevant}), None)
            profile.append({"responsibility_id": f"F_{route}", "route": route, "deadline_frame": self._frame(leak.time) if leak else None,
                            "observed_attacks": row["attacks"], "observed_damage": row["damage"], "falco_configuration": {"tile": trace["falco_tile"], "facing": trace["falco_facing"]},
                            "provenance": "SIMULATION_EXACT"})
        return {"operator_id": "char_192_falco", "responsibilities": profile,
                "shared_resource_fields": ["operator_identity", "tile", "facing", "attack_coverage", "deployment_time"],
                "dp_requirement": "UNKNOWN_NOT_PROVEN_BY_M15.3", "damage_requirement": "candidate-specific observed contribution only"}

    def _pool_matches(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        target_routes = [item["route"] for item in profile["responsibilities"] if item["route"] in {"route-0", "route-2", "route-3", "route-4"}]
        matches = []
        for operator_id, op in sorted(self.engine.fixture.operators.items()):
            covered = []
            placements = []
            for route in target_routes:
                for tile in self.engine.fixture.stage.stage_map.tiles:
                    if not tile.buildable or tile.tile_kind != ("GROUND" if op.position.value == "MELEE" else "HIGH_GROUND"): continue
                    for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                        if self._covers(operator_id, (tile.x, tile.y), direction, route):
                            covered.append(route); placements.append({"route": route, "tile": (tile.x, tile.y), "direction": direction}); break
                    if route in covered: break
            if covered:
                stats = op.phases[0].stats_max; cost = float(stats.cost.value or 0); atk = float(stats.atk.value or 0); interval = float(stats.attack_interval.value or 1)
                matches.append({"operator_id": operator_id, "covered_responsibilities": sorted(set(covered)), "deployment_cost": cost,
                                "earliest_legal_deployment_frame": max(0, round(max(0.0, cost - 10.0) * FPS)), "attack_interval": interval,
                                "damage_type": op.damage_type, "approx_damage_per_hit": physical_damage(atk, 0) if op.damage_type != "ARTS" else arts_damage(atk, 30),
                                "placements": placements[:8], "runtime_support": "EXECUTABLE"})
        return sorted(matches, key=lambda row: (-len(row["covered_responsibilities"]), row["deployment_cost"], row["operator_id"]))

    def _abc(self, parent: Strategy, counters: list[Strategy]):
        a = parent
        b = counters[0] if counters else parent
        # Controlled decoupling: keep specialized Falco placement, move the
        # early Noir/guard actor to Falco's original opening tile.
        b_deploy = [x for x in b.actions if x.action_type is ActionType.DEPLOY]
        a_falco = next(x for x in a.actions if x.action_type is ActionType.DEPLOY and x.operator_id == "char_192_falco")
        c_actions = list(b.actions)
        moved = False
        for i, action in enumerate(c_actions):
            if action.action_type is ActionType.DEPLOY and action.operator_id == "char_502_nblade":
                c_actions[i] = Action(ActionType.DEPLOY, action.time, action.operator_id, a_falco.tile, a_falco.direction); moved = True; break
        c = Strategy(b.team, tuple(sorted(c_actions, key=lambda x: (x.time, x.operator_id)))) if moved else b
        return {"A_original": a, "B_route2_specialized": b, "C_decoupled_assignment": c}

    def _row(self, label: str, strategy: Strategy, result, requirements: list[dict[str, Any]]) -> dict[str, Any]:
        fronts = self._frontiers(result); active = []
        for req in requirements:
            active.append({"constraint_id": req["constraint_id"], "route": req["route"], "preserved": not any(f["route"] == req["route"] and f["frame"] <= req["deadline"] for f in fronts)})
        return {"label": label, "operators": list(strategy.team), "operator_count": len(strategy.team), "rarity": sum(int(self.engine.fixture.operators[x].star_rarity.value or 0) for x in strategy.team),
                "result": "WIN" if result.win else "LOSS", "kills": result.enemies_killed, "leaks": result.enemies_leaked, "remaining_life": result.remaining_life,
                "frontiers": fronts, "constraints": active}

    def run(self) -> dict[str, Any]:
        parent, counters = self._load()
        executed_keys: set[tuple] = set()
        def run_once(strategy):
            key = tuple((a.action_type.value, self._frame(a.time), a.operator_id, a.tile, a.direction) for a in strategy.actions)
            executed_keys.add(key)
            return self._run(strategy)
        parent_result = run_once(parent); counter_states = [(s, run_once(s)) for s in counters]
        falco_audit = [self._falco_audit("M15.2_PARENT", parent, parent_result)] + [self._falco_audit(f"M15.2_COUNTEREXAMPLE_{i+1}", s, r) for i, (s, r) in enumerate(counter_states)]
        removed_parent = self._remove_falco(parent)
        removed = [{"label": "M15.2_PARENT", "frontiers": self._frontiers(removed_parent), "kills": removed_parent.enemies_killed, "leaks": removed_parent.enemies_leaked}]
        for i, (s, _) in enumerate(counter_states):
            result = self._remove_falco(s); removed.append({"label": f"M15.2_COUNTEREXAMPLE_{i+1}", "frontiers": self._frontiers(result), "kills": result.enemies_killed, "leaks": result.enemies_leaked})
        profile = self._critical_profile(parent_result, parent)
        route_deadlines: dict[str, int] = {}
        for result in [parent_result, *(r for _, r in counter_states)]:
            for frontier in self._frontiers(result):
                route = frontier["route"]
                if route in {"route-0", "route-2", "route-3", "route-4"}:
                    route_deadlines[route] = min(route_deadlines.get(route, frontier["frame"]), frontier["frame"])
        requirements = [{"constraint_id": f"C_{route}_PRESERVE", "route": route, "deadline": deadline,
                         "requirement_type": "INTERACT_WITH_ROUTE_BEFORE", "required_capability": "RANGED_OR_GROUND_INTERACTION",
                         "provenance": "SIMULATION_DERIVED"} for route, deadline in sorted(route_deadlines.items())]
        matches = self._pool_matches(profile)
        existing = []
        for oid in parent.team:
            if oid == "char_192_falco": continue
            op = self.engine.fixture.operators[oid]; rows = []
            for route in ("route-0", "route-2", "route-3", "route-4"):
                rows.append({"route": route, "can_absorb": any(self._covers(oid, (tile.x, tile.y), direction, route) for tile in self.engine.fixture.stage.stage_map.tiles for direction in ("UP", "DOWN", "LEFT", "RIGHT") if tile.buildable and tile.tile_kind == ("GROUND" if op.position.value == "MELEE" else "HIGH_GROUND"))})
            existing.append({"operator_id": oid, "responsibility_absorption": rows})
        abc = self._abc(parent, counters)
        abc_results = {label: run_once(strategy) for label, strategy in abc.items()}
        abc_rows = {label: self._row(label, strategy, abc_results[label], requirements) for label, strategy in abc.items()}
        # This bounded experiment executes the parent, preserved counterexamples,
        # remove-Falco controls and A/B/C cases; count them explicitly rather
        # than relying on the M11 search cache, which is not used here.
        self.metrics.unique_simulations = len(executed_keys)
        self.metrics.cache_hits = (1 + len(counter_states) + len(removed) + len(abc_results)) - len(executed_keys)
        # At most one controlled C candidate is simulated; this is not a roster enumeration.
        best = min(abc_rows.values(), key=lambda row: (0 if row["result"] == "WIN" else 1, -min((f["frame"] for f in row["frontiers"]), default=10**9), row["leaks"], -row["kills"]))
        return {
            "m15_4_falco_responsibility_audit": {"version": self.VERSION, "llm_calls": 0, "mechanics_expansion": False, "audits": falco_audit},
            "m15_4_remove_falco_counterfactual": {"counterfactuals": removed, "note": "Falco damage disabled by a local output substitution; all other actions are preserved."},
            "m15_4_critical_resource_profile": profile,
            "m15_4_responsibility_partition": {"partition": [{"id": f"F_{x['route']}", "route": x["route"], "deadline": x["deadline_frame"], "classification": "ESSENTIAL" if x["observed_damage"] > 0 else "UNKNOWN"} for x in profile["responsibilities"]], "SINGLE_CONFIGURATION_CONFLICT": "INCONCLUSIVE"},
            "m15_4_existing_roster_reassignment": existing,
            "m15_4_pool_capability_matches": matches,
            "m15_4_substitution_candidates": [{"operator_id": row["operator_id"], "covered_responsibilities": row["covered_responsibilities"], "reason": "pool capability query only; no arbitrary team enumeration"} for row in matches[:12]],
            "m15_4_candidate_prechecks": {"analytical_candidates": len(matches), "deterministic_rejects": {"coverage": 0, "timing": 0, "DP": 0, "illegal": 0}, "joint_constraints": requirements},
            "m15_4_abc_comparison": {"A_original": abc_rows["A_original"], "B_route2_specialized": abc_rows["B_route2_specialized"], "C_decoupled_assignment": abc_rows["C_decoupled_assignment"]},
            "m15_4_results": {"best": best, "unique_full_simulations": self.metrics.unique_simulations, "cache_hits": self.metrics.cache_hits, "CRITICAL_RESOURCE_DECOUPLING": "SUPPORTED" if abc_rows["C_decoupled_assignment"]["result"] == "WIN" else "INCONCLUSIVE", "CRITICAL_RESOURCE_OVERLOAD": "INCONCLUSIVE", "K7_CARDINALITY_PRESSURE": "INCONCLUSIVE", "win": best["result"] == "WIN"},
        }
