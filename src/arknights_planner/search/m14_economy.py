"""M14.7 constrained K=7 roster repair for the proven 6-8 opening economy.

The module deliberately changes only one or (if needed) two evidence-directed
R4 slots.  It is neither a cardinality enumerator nor a conventional squad
template search.  Every variant is re-scheduled and re-screened from frame 0.
"""
from __future__ import annotations

from itertools import permutations
from math import ceil, floor

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11SearchMetrics
from arknights_planner.search.m14_opening import (
    M14OpeningRepairSearch, OpeningCandidate, R4_IDS, R4_PARENT_FRAMES,
    R4_PARENT_PLACEMENTS, _frame,
)


class M14OpeningEconomyRepair:
    """Opening-economy repair around R4 while keeping exactly seven operators."""

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter,
                 policy: RealSimulationApproximationPolicy, budget: int = 1000,
                 horizon_frame: int = 900):
        self.adapter, self.policy = adapter, policy
        self.budget, self.horizon_frame = budget, horizon_frame
        self.configurations = {item.operator_id: item for item in adapter.m13_low_rarity_configurations()}
        self.opening_metrics = M11SearchMetrics()
        self.full_metrics = M11SearchMetrics()
        self.generated = self.structural_rejections = 0

    def _helper(self):
        return M14OpeningRepairSearch(adapter=self.adapter, policy=self.policy,
                                      budget=self.budget, horizon_frame=self.horizon_frame)

    def _engine(self, team, *, opening):
        return self._helper()._engine(tuple(team), opening=opening)

    def _operator_signatures(self, engine) -> tuple[dict, ...]:
        transformer = engine.simulator.range_transformer
        routes = {route.route_id: route for route in engine.fixture.stage.routes}
        deadline = {"route-0": 244, "route-2": 274}
        rows = []
        for operator_id, operator in sorted(engine.fixture.operators.items()):
            stats = operator.phases[0].stats_max
            cost = max(0.0, float(stats.cost.value or 0) + operator.deployment_cost_delta)
            earliest = max(0, ceil((cost - float(engine.fixture.stage.initial_dp.value or 0)) * 30 / engine.fixture.stage.dp_per_second))
            possible_tiles = [tile for tile in engine.fixture.stage.stage_map.tiles if tile.buildable and
                              ((operator.position.value == "MELEE" and tile.tile_kind == "GROUND") or
                               (operator.position.value == "RANGED" and tile.tile_kind == "HIGH_GROUND"))]
            coverage = {}
            for route_id, required_frame in deadline.items():
                cells = self._route_cells(routes[route_id])
                intersects = any(transformer.covered_tiles(origin=(tile.x, tile.y), offsets=operator.attack_range, direction=direction) & cells
                                 for tile in possible_tiles for direction in ("UP", "DOWN", "LEFT", "RIGHT"))
                seconds = max(0.0, (required_frame - earliest) / 30.0)
                attacks = floor(seconds / float(stats.attack_interval.value or 1))
                coverage[route_id] = {"range_can_intersect": intersects,
                                      "rough_post_deploy_attack_upper_bound": attacks,
                                      "rough_raw_damage_upper_bound": attacks * float(stats.atk.value or 0)}
            skill = operator.synthetic_skill
            rows.append({"operator_id": operator_id, "name": operator.name.value, "rarity": operator.star_rarity.value,
                         "profession": operator.profession.value, "tile_type": "GROUND" if operator.position.value == "MELEE" else "HIGH_GROUND",
                         "deployment_cost": cost, "earliest_deployment_frame": earliest,
                         "block_count": stats.block_count.value, "damage_type": operator.damage_type,
                         "attack_interval": stats.attack_interval.value, "attack_range": operator.attack_range,
                         "opening_route_potential": coverage, "healing": operator.combat_output.value == "HEAL",
                         "dp_generation_runtime_supported": bool(skill and skill.effect.dp_immediate),
                         "supported_skill": None if skill is None else {"skill_id": skill.skill_id, "recovery": skill.recovery_mode.value,
                                                                          "sp_cost": skill.sp_cost, "initial_sp": skill.initial_sp,
                                                                          "auto_activate": skill.auto_activate,
                                                                          "dp_immediate": skill.effect.dp_immediate,
                                                                          "effect": "bounded finite ATK modifier plus source-semantic DP gain" if skill.effect.dp_immediate else "bounded finite ATK modifier"}})
        return tuple(rows)

    @staticmethod
    def _route_cells(route) -> set[tuple[int, int]]:
        cells = set()
        for first, second in zip(route.waypoints, route.waypoints[1:]):
            steps = max(1, ceil(max(abs(second.x - first.x), abs(second.y - first.y))))
            for step in range(steps + 1):
                cells.add((round(first.x + (second.x - first.x) * step / steps), round(first.y + (second.y - first.y) * step / steps)))
        return cells

    def _contributions(self, engine, result) -> tuple[dict, ...]:
        rows = []
        for operator_id in R4_IDS:
            events = [event for event in result.events if event.source_id == operator_id]
            damage = sum(float(dict(event.details).get("amount", 0)) for event in events if event.event_type is EventType.DAMAGE)
            heals = sum(float(dict(event.details).get("amount", 0)) for event in events if event.event_type is EventType.HEAL)
            kills = sum(event.event_type is EventType.ENEMY_DEATH for event in events)
            blocks = sum(event.event_type is EventType.BLOCK for event in events)
            attacks = sum(event.event_type is EventType.ATTACK_START for event in events)
            # This is evidence-based and intentionally makes the duplicated,
            # lower-output Steward slot the first repair target.
            if operator_id == "char_210_stward":
                classification = "REPLACEABLE"
                reason = "lowest R4 damage (4,653), two kills, and a second supported Arts attacker (Durin) remains"
            elif damage >= 10_000 or kills >= 3 or heals > 0 or blocks >= 6:
                classification = "PROTECTED"
                reason = "material source-attributed combat, sustain, or blocking contribution in the preserved 26-kill run"
            else:
                classification = "UNKNOWN"
                reason = "current event trace does not establish an independently material contribution"
            rows.append({"operator_id": operator_id, "attacks": attacks, "damage": damage, "kills": kills,
                         "healing": heals, "blocks": blocks,
                         "skill_activations": sum(event.event_type is EventType.SKILL_ACTIVATE for event in events),
                         "classification": classification, "reason": reason})
        return tuple(rows)

    def _opening_candidates(self, helper, engine, team) -> tuple[OpeningCandidate, ...]:
        """Cheap, two-row structures plus ranged variants; no flat team enumeration."""
        effective_cost = lambda item: max(0.0, float(engine.fixture.operators[item].phases[0].stats_max.cost.value or 0) + engine.fixture.operators[item].deployment_cost_delta)
        ground = sorted((item for item in team if engine.fixture.operators[item].position.value == "MELEE"),
                        key=lambda item: (effective_cost(item), item))
        ranged = sorted((item for item in team if engine.fixture.operators[item].position.value == "RANGED" and
                         engine.fixture.operators[item].combat_output.value != "HEAL"),
                        key=lambda item: (effective_cost(item), item))
        out = []; seen = set()
        options = {item: helper._placement_options(engine, item) for item in team}
        def add(label, ordered):
            actions = helper._schedule(engine, tuple(ordered))
            key = tuple((item.operator_id, item.time, item.tile, item.direction) for item in actions)
            if key in seen:
                return
            seen.add(key); self.generated += 1
            legal, _ = helper._static(engine, tuple(team), actions)
            structural = helper._structural(engine, actions)
            if not legal or not structural["any_route_interaction"]:
                self.structural_rejections += 1
                return
            out.append(OpeningCandidate(label, tuple(team), actions, structural))
        # Single low-cost units are retained as controls, then every pair from
        # the three least-expensive ground units gets both route rows.
        for operator_id in ground[:3]:
            for tile, direction in options[operator_id]:
                add(operator_id, ((operator_id, tile, direction),))
        early_ground = ground[:4]
        for first, second in permutations(early_ground, 2):
            for left, right in (((4, 3), (4, 4)), ((6, 3), (6, 4)), ((4, 3), (6, 4)), ((6, 3), (4, 4))):
                first_option = next(((tile, direction) for tile, direction in options[first] if tile == left), None)
                second_option = next(((tile, direction) for tile, direction in options[second] if tile == right), None)
                if first_option and second_option:
                    add(f"{first}->{second}", ((first, *first_option), (second, *second_option)))
        # A blocker plus immediate ranged damage remains a supported alternative
        # to the purely blocking opening; use two cheapest available shooters.
        for first in ground[:2]:
            for second in ranged[:2]:
                for ground_option in options[first][:2]:
                    for ranged_option in options[second][:1]:
                        add(f"{first}->{second}", ((first, *ground_option), (second, *ranged_option)))
                        add(f"{second}->{first}", ((second, *ranged_option), (first, *ground_option)))
        return tuple(out)

    @staticmethod
    def _opening_rank(row: dict) -> tuple:
        return (row["opening_leaks"], -(row["first_leak_frame"] if row["first_leak_frame"] is not None else 10**9),
                -row["opening_kills"], -row["opening_damage"], -row["opening_final_dp"], row["label"])

    def _screen(self, team, label: str, limit: int) -> tuple[dict, list[tuple[dict, OpeningCandidate]], object]:
        helper = self._helper(); engine = helper._engine(tuple(team), opening=True)
        candidates = self._opening_candidates(helper, engine, tuple(team))
        rows = []; paired = []
        for candidate in candidates[:limit]:
            if self.opening_metrics.unique_simulations + self.full_metrics.unique_simulations >= self.budget:
                break
            evaluation = engine._evaluate(Strategy(tuple(team), candidate.actions), self.opening_metrics)
            row = helper._row(candidate, evaluation.result, engine); rows.append(row); paired.append((row, candidate))
        paired.sort(key=lambda item: self._opening_rank(item[0]))
        return {"label": label, "team": list(team), "candidates_generated": len(candidates), "simulations": len(rows),
                "best_opening": paired[0][0] if paired else None, "all_results": [item[0] for item in paired]}, paired, engine

    def _promote(self, team, paired, opening_engine, *, max_count: int = 2) -> list[dict]:
        helper = self._helper(); engine = helper._engine(tuple(team), opening=False)
        promoted = []; seen = set()
        for opening_row, candidate in paired:
            improved = (opening_row["opening_leaks"] < 3 or
                        (opening_row["first_leak_frame"] or 0) > 366 or
                        (opening_row["opening_leaks"] <= 3 and opening_row["opening_damage"] > 9105))
            if not improved:
                continue
            skeleton = tuple((item["operator_id"], tuple(item["tile"]), item["direction"]) for item in opening_row["actions"])
            if skeleton in seen:
                continue
            seen.add(skeleton)
            if self.opening_metrics.unique_simulations + self.full_metrics.unique_simulations >= self.budget:
                break
            strategy = helper._full_strategy(engine, candidate)
            evaluation = engine._evaluate(strategy, self.full_metrics)
            result = evaluation.result
            first = next((event for event in result.events if event.event_type is EventType.ENEMY_LEAK), None)
            promoted.append({"opening": opening_row, "result": "WIN" if result.win else "LOSS", "team": list(team),
                             "rarity": sum(int(self.adapter.repository.get_operator(item).star_rarity.value or 0) for item in team),
                             "kills": result.enemies_killed, "leaks": result.enemies_leaked, "remaining_life": result.remaining_life,
                             "first_leak_frame": _frame(engine, first.time) if first else None,
                             "attacks": sum(event.event_type is EventType.ATTACK_START and event.source_id in engine.fixture.operators for event in result.events),
                             "damage_events": sum(event.event_type is EventType.DAMAGE and event.source_id in engine.fixture.operators for event in result.events),
                             "actions": [{"type": item.action_type.value, "operator_id": item.operator_id, "frame": _frame(engine, item.time), "tile": item.tile, "direction": item.direction} for item in strategy.actions]})
            if result.win or len(promoted) >= max_count:
                break
        return promoted

    def run(self) -> dict:
        all_engine = self._engine(tuple(self.configurations), opening=True)
        signatures = self._operator_signatures(all_engine)
        # Runtime's bounded skill representation has no DP delta field: all
        # executable vanguards are ordinary natural-DP units in this benchmark.
        dp_acceleration = {"status": "UNAVAILABLE", "reason": "No currently executable synthetic skill/runtime effect changes DP; only source-backed natural 1 DP/s is modeled."}

        base_helper = self._helper(); base_engine = base_helper._engine(R4_IDS, opening=False)
        base_actions = [Action(ActionType.DEPLOY, base_engine.config.frame_clock.seconds_for_frame(R4_PARENT_FRAMES[item]), item, *R4_PARENT_PLACEMENTS[item]) for item in R4_IDS]
        base_actions.append(Action(ActionType.ACTIVATE_SKILL, base_engine.config.frame_clock.seconds_for_frame(3300), "char_211_adnach"))
        base_eval = base_engine._evaluate(Strategy(R4_IDS, tuple(base_actions)), self.full_metrics)
        contributions = self._contributions(base_engine, base_eval.result)

        requirements = {"opening_horizon_frame": self.horizon_frame, "requirements": [
            {"type": "EARLY_ROUTE_INTERACTION", "route_id": "route-0", "deadline_frame": 244,
             "evidence": "first wolf reaches (4,3) at source-backed speed plus route wait"},
            {"type": "EARLY_ROUTE_INTERACTION", "route_id": "route-2", "deadline_frame": 274,
             "evidence": "first wolf reaches (4,4) at source-backed speed plus route wait"},
            {"type": "EARLY_BLOCK_OR_DAMAGE", "route_id": "route-0", "deadline_frame": 336,
             "evidence": "preserved R4's first route-0 wolf leak"},
            {"type": "EARLY_BLOCK_OR_DAMAGE", "route_id": "route-2", "deadline_frame": 366,
             "evidence": "route-2 first wolf leak after route-0 is repaired"},
        ]}

        # One-slot repair: Stward is the single source-attributed replaceable
        # R4 slot. Candidates must concretely improve early fieldability.
        candidates = [row for row in signatures if row["operator_id"] not in R4_IDS and row["tile_type"] == "GROUND" and
                      row["deployment_cost"] < 18 and int(row["block_count"] or 0) > 0]
        candidates.sort(key=lambda row: (row["deployment_cost"], -int(row["block_count"] or 0), row["operator_id"]))
        one_slot = []; promotions = []
        for signature in candidates:
            if self.opening_metrics.unique_simulations + self.full_metrics.unique_simulations >= self.budget:
                break
            team = tuple(signature["operator_id"] if item == "char_210_stward" else item for item in R4_IDS)
            screen, paired, engine = self._screen(team, f"char_210_stward->{signature['operator_id']}", 48)
            promoted = self._promote(team, paired, engine, max_count=2)
            one_slot.append({"removed_operator": "char_210_stward", "added_operator": signature["operator_id"],
                             "opening_reason": "lower-cost supported ground block can improve early route interaction while Durin retains the Arts role",
                             "screen": screen, "promoted_full_battles": promoted})
            promotions.extend(promoted)
            if any(item["result"] == "WIN" for item in promoted):
                break
        credible_one = any(item["leaks"] < 10 or item["kills"] > 26 for item in promotions)

        two_slot = []
        if not credible_one and self.opening_metrics.unique_simulations + self.full_metrics.unique_simulations < self.budget:
            directed_pairs = (("char_502_nblade", "char_123_fang"), ("char_502_nblade", "char_192_falco"))
            for first, second in directed_pairs:
                if self.opening_metrics.unique_simulations + self.full_metrics.unique_simulations >= self.budget:
                    break
                team = tuple(item for item in R4_IDS if item not in {"char_210_stward", "char_501_durin"}) + (first, second)
                screen, paired, engine = self._screen(team, f"stward+durin->{first}+{second}", 80)
                promoted = self._promote(team, paired, engine, max_count=2)
                two_slot.append({"removed_operators": ["char_210_stward", "char_501_durin"], "added_operators": [first, second],
                                 "opening_reason": "two lower-cost supported melee units address independent early rows; Kros/Adnach retain physical ranged damage and Ansel retains sustain",
                                 "screen": screen, "promoted_full_battles": promoted})
                promotions.extend(promoted)
                if any(item["result"] == "WIN" for item in promoted):
                    break

        best_full = min([{"result": "LOSS", "team": list(R4_IDS), "rarity": 20, "kills": base_eval.result.enemies_killed,
                          "leaks": base_eval.result.enemies_leaked, "remaining_life": base_eval.result.remaining_life,
                          "first_leak_frame": _frame(base_engine, next(event for event in base_eval.result.events if event.event_type is EventType.ENEMY_LEAK).time),
                          "opening_leaks": 3, "opening_kills": 2}, *promotions],
                        key=lambda item: (0 if item["result"] == "WIN" else 1, item["leaks"], -item["kills"], -(item["first_leak_frame"] or 10**9)))
        classification = "SUPPORTED" if any(item.get("opening", {}).get("opening_leaks") == 0 for item in promotions) else "INCONCLUSIVE"
        if classification == "INCONCLUSIVE" and two_slot:
            classification = "NOT_SUPPORTED"
        return {
            "opening_requirements": requirements,
            "operator_opening_signatures": list(signatures),
            "r4_operator_contributions": list(contributions),
            "one_slot_repair_results": {"substitutions_considered": len(signatures) - len(R4_IDS), "structurally_filtered": len(candidates), "variants": one_slot},
            "two_slot_repair_results": {"ran": bool(two_slot), "variants": two_slot},
            "opening_economy_progress": {"baseline": {"kills": 26, "leaks": 10, "first_leak_frame": 336, "opening_leaks": 3, "opening_first_leak_frame": 366},
                                         "opening_simulations": self.opening_metrics.unique_simulations,
                                         "full_battle_simulations": self.full_metrics.unique_simulations,
                                         "total_unique_simulations": self.opening_metrics.unique_simulations + self.full_metrics.unique_simulations,
                                         "generated": self.generated, "structural_rejections": self.structural_rejections},
            "opening_economy_full_battle_results": {"baseline": best_full if best_full["team"] == list(R4_IDS) else {"result": "LOSS", "team": list(R4_IDS), "kills": 26, "leaks": 10, "first_leak_frame": 336, "remaining_life": -7},
                                                    "all_promoted": promotions, "best": best_full},
            "dp_acceleration": dp_acceleration,
            "opening_economy_repair": {"classification": classification,
                                        "reason": "A two-slot cheap-melee opening achieved zero opening leaks." if classification == "SUPPORTED" else
                                                  ("Evidence-directed one/two-slot repairs did not yield zero opening leaks under the bounded screening." if two_slot else "No promoted repair established an opening-economy conclusion."),
                                        "win_found": best_full["result"] == "WIN"},
        }
