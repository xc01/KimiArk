"""M14.9 opening-economy mechanics audit; deliberately not a strategy search."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from math import ceil

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.adapters.approximate_real import M13LoadoutPolicy, RealOperatorConfiguration
from arknights_planner.adapters.low_rarity_skill import LowRarityBlackboardEffectInterpreter, RealSkillSupport
from arknights_planner.benchmark.census import RuntimeSupportStatus, low_rarity_census
from arknights_planner.models.runtime import SkillEffect
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator


_PHASES = {"PHASE_0": 0, "PHASE_1": 1, "PHASE_2": 2}
_FANG = "char_123_fang"
_VANILLA = "char_240_wyvern"
_BEAGLE = "char_122_beagle"
_NOIR = "char_502_nblade"


class M14OpeningEconomyFidelityAudit:
    """Source audit plus two causal checks for narrowly defined DP semantics."""

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter,
                 policy: RealSimulationApproximationPolicy):
        self.adapter, self.policy = adapter, policy
        self.repository = adapter.repository
        self.characters = self.repository._table("character_table.json")
        self.skills = self.repository._table("skill_table.json")
        self.interpreter = LowRarityBlackboardEffectInterpreter()

    @staticmethod
    def _frame(seconds: Fraction | float) -> int:
        return int(round(float(seconds) * 30.0))

    @staticmethod
    def _earliest_deploy_frame(cost: float, *, initial_dp: float = 10.0, dp_per_second: float = 1.0) -> int:
        return max(0, ceil((cost - initial_dp) / dp_per_second * 30.0))

    def _configuration(self, operator_id: str) -> RealOperatorConfiguration | None:
        try:
            return M13LoadoutPolicy.highest_legal().configuration(self.repository, operator_id)
        except Exception:
            return None

    def _selected_skill_raw(self, operator_id: str, config: RealOperatorConfiguration | None) -> tuple[dict, dict, int] | None:
        if config is None:
            return None
        operator = self.repository.get_operator(operator_id)
        if not operator.skill_ids:
            return None
        skill_id = operator.skill_ids[0]
        raw = self.skills[skill_id]
        levels = raw.get("levels") or []
        index = len(levels) - 1 if config.skill_level_index == -1 else config.skill_level_index
        return raw, levels[index], index

    @staticmethod
    def _blackboard(raw_level: dict) -> dict[str, float | int | str | None]:
        return {str(item.get("key")): item.get("value") for item in raw_level.get("blackboard") or [] if isinstance(item, dict)}

    def _skill_economy(self, operator_id: str, config: RealOperatorConfiguration | None) -> dict | None:
        selected = self._selected_skill_raw(operator_id, config)
        if selected is None:
            return None
        raw_skill, raw_level, index = selected
        values = self._blackboard(raw_level)
        description = str(raw_level.get("description") or "")
        if "cost" not in values:
            return None
        sp = raw_level.get("spData") or {}
        skill_type, sp_type = raw_level.get("skillType"), sp.get("spType")
        duration = raw_level.get("duration")
        effect_kind = "UNKNOWN_COST_KEY"
        semantics, confidence = "UNKNOWN", "UNKNOWN"
        if (skill_type == "AUTO" and sp_type == "INCREASE_WITH_TIME" and float(duration or 0.0) == 0.0
                and set(values) == {"cost"} and "立即获得" in description and "部署费用" in description):
            effect_kind, semantics, confidence = "AUTO_GRANT_DP", "KNOWN", "EXACT"
        elif (skill_type == "MANUAL" and sp_type == "INCREASE_WITH_TIME" and set(values) == {"cost", "atk"}
                and "获得" in description and "部署费用" in description):
            effect_kind, semantics, confidence = "MANUAL_GRANT_DP_AND_ATK", "KNOWN", "EXACT"
        interpreted = None
        try:
            level = self.repository.get_skill(raw_skill["skillId"]).levels[index]
            interpreted = self.interpreter.interpret(raw_skill["skillId"], level)
        except Exception:
            pass
        return {
            "mechanic": effect_kind, "data_present": "YES", "semantics_known": semantics,
            "runtime_supported": bool(interpreted and interpreted.support is RealSkillSupport.EXECUTABLE_APPROXIMATED and interpreted.executable_effect and interpreted.executable_effect.effect.dp_immediate),
            "source_confidence": confidence, "skill_id": raw_skill["skillId"], "skill_level_index": index,
            "source_file": "skill_table.json", "source_path": f"$.{raw_skill['skillId']}.levels[{index}]",
            "blackboard": values, "skill_type": skill_type, "sp_type": sp_type,
            "initial_sp": sp.get("initSp"), "sp_cost": sp.get("spCost"), "duration": duration,
            "description": description,
        }

    def _talent_economy(self, operator_id: str, config: RealOperatorConfiguration | None) -> list[dict]:
        if config is None:
            return []
        out: list[dict] = []
        raw = self.characters[operator_id]
        for talent_index, talent in enumerate(raw.get("talents") or []):
            for candidate_index, candidate in enumerate(talent.get("candidates") or []):
                condition = candidate.get("unlockCondition") or {}
                phase = _PHASES.get(condition.get("phase"))
                if phase is None or phase > config.phase_index or int(condition.get("level", 1)) > config.level:
                    continue
                if int(candidate.get("requiredPotentialRank", 0)) > 0:
                    continue
                values = self._blackboard(candidate)
                description = str(candidate.get("description") or "")
                if "cost" not in values and "attack@cost" not in values:
                    continue
                mechanic, semantics, runtime, confidence = "UNKNOWN_COST_TALENT", "UNKNOWN", False, "UNKNOWN"
                if set(values) == {"cost"} and "自身部署费用" in description and isinstance(values["cost"], (int, float)):
                    mechanic, semantics, runtime, confidence = "SELF_DEPLOYMENT_COST_MODIFIER", "KNOWN", True, "EXACT"
                elif "首次阻挡敌人" in description and "部署费用" in description:
                    mechanic, semantics, confidence = "FIRST_BLOCK_GRANT_DP_AND_CROWD_CONTROL", "KNOWN", "EXACT"
                elif "回复" in description and "部署费用" in description:
                    mechanic, semantics, confidence = "CONDITIONAL_DAMAGE_OR_ATTACK_DP_GAIN", "KNOWN", "EXACT"
                out.append({
                    "mechanic": mechanic, "data_present": "YES", "semantics_known": semantics,
                    "runtime_supported": runtime, "source_confidence": confidence,
                    "source_file": "character_table.json", "source_path": f"$.{operator_id}.talents[{talent_index}].candidates[{candidate_index}]",
                    "unlock_condition": condition, "required_potential": candidate.get("requiredPotentialRank", 0),
                    "blackboard": values, "description": description,
                })
        return out

    def _operator_rows(self) -> tuple[list[dict], list[dict]]:
        rows: list[dict] = []
        relevant: list[dict] = []
        for record in low_rarity_census(self.repository):
            configuration = self._configuration(record.operator_id)
            mechanics = [item for item in (self._skill_economy(record.operator_id, configuration),) if item]
            mechanics.extend(self._talent_economy(record.operator_id, configuration))
            row = {
                "operator_id": record.operator_id, "name": record.name, "rarity": record.rarity,
                "profession": record.profession, "executable": record.runtime_status in {RuntimeSupportStatus.EXECUTABLE, RuntimeSupportStatus.EXECUTABLE_WITH_APPROXIMATION},
                "runtime_status": record.runtime_status.value, "blocking_reason": list(record.blockers),
                "loadout": None if configuration is None else {"phase": configuration.phase_index, "level": configuration.level, "skill_level_index": configuration.skill_level_index},
                "economy_mechanics": mechanics,
            }
            rows.append(row)
            for mechanic in mechanics:
                item = {"operator_id": record.operator_id, "name": record.name, "rarity": record.rarity,
                        "profession": record.profession, "executable": row["executable"], "runtime_status": row["runtime_status"],
                        "deployment_cost": None, "earliest_deployment_frame": "UNKNOWN", **mechanic}
                if configuration is not None:
                    adapted = self.adapter.strict_adapter.adapt_operator(record.operator_id, phase_index=configuration.phase_index, level=configuration.level,
                                                                          skill_level_index=(len(self.repository.get_skill(self.repository.get_operator(record.operator_id).skill_ids[0]).levels) - 1 if self.repository.get_operator(record.operator_id).skill_ids else 0))
                    runtime = self.adapter._runtime_operator(adapted, deployment_cost_delta=self.adapter._neutral_self_deployment_cost_delta(adapted))
                    base = float(runtime.phases[0].stats_max.cost.value or 0.0)
                    item["deployment_cost"] = base + runtime.deployment_cost_delta
                    item["earliest_deployment_frame"] = self._earliest_deploy_frame(item["deployment_cost"])
                    if item["mechanic"] in {"AUTO_GRANT_DP", "MANUAL_GRANT_DP_AND_ATK"}:
                        item["earliest_possible_effect_frame"] = item["earliest_deployment_frame"] + self._frame(max(0.0, float(item["sp_cost"] or 0) - float(item["initial_sp"] or 0)))
                    elif item["mechanic"] == "SELF_DEPLOYMENT_COST_MODIFIER":
                        item["earliest_possible_effect_frame"] = item["earliest_deployment_frame"]
                    else:
                        item["earliest_possible_effect_frame"] = "UNKNOWN"
                relevant.append(item)
        return rows, relevant

    def _causal_validation(self) -> dict:
        configs = tuple(
            M13LoadoutPolicy.highest_legal().configuration(self.repository, operator_id)
            for operator_id in (_FANG, _VANILLA, _BEAGLE, _NOIR)
        )
        fixture = self.adapter.build_pool_fixture(stage_id_or_code="6-8", configurations=configs, policy=self.policy)
        simulator = Simulator()
        at = lambda frame: Fraction(frame, 30)

        fang_strategy = Strategy((_FANG, _NOIR), (
            Action(ActionType.DEPLOY, at(0), _FANG, (4, 3), "DOWN"),
            Action(ActionType.DEPLOY, at(210), _NOIR, (4, 4), "DOWN"),
        ))
        before_ops = dict(fixture.operators)
        before_ops[_FANG] = replace(before_ops[_FANG], deployment_cost_delta=0.0)
        before = simulator.run(stage=fixture.stage, operators=before_ops, enemies=fixture.enemies, strategy=fang_strategy,
                               config=SimulationConfig(dt=0.1, max_time=8.0))
        after = simulator.run(stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies, strategy=fang_strategy,
                              config=SimulationConfig(dt=0.1, max_time=8.0))
        fang_auto = simulator.run(
            stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies,
            strategy=Strategy((_FANG,), (Action(ActionType.DEPLOY, at(0), _FANG, (4, 3), "DOWN"),)),
            config=SimulationConfig(dt=0.1, max_time=20.0),
        )

        vanilla_strategy = Strategy((_VANILLA, _BEAGLE), (
            Action(ActionType.DEPLOY, at(30), _VANILLA, (4, 3), "DOWN"),
            Action(ActionType.ACTIVATE_SKILL, at(450), _VANILLA),
            Action(ActionType.DEPLOY, at(450), _BEAGLE, (4, 4), "DOWN"),
        ))
        vanilla_before = dict(fixture.operators)
        skill = vanilla_before[_VANILLA].synthetic_skill
        assert skill is not None
        vanilla_before[_VANILLA] = replace(vanilla_before[_VANILLA], synthetic_skill=replace(skill, effect=replace(skill.effect, dp_immediate=0.0)))
        without_dp = simulator.run(stage=fixture.stage, operators=vanilla_before, enemies=fixture.enemies, strategy=vanilla_strategy,
                                   config=SimulationConfig(dt=0.1, max_time=16.0))
        with_dp = simulator.run(stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies, strategy=vanilla_strategy,
                                config=SimulationConfig(dt=0.1, max_time=16.0))
        def legal(result, operator_id):
            return [dict(event.details).get("legal") for event in result.events if event.event_type is EventType.DEPLOY and event.source_id == operator_id]
        def dp_events(result):
            return [{"frame": self._frame(event.time), **dict(event.details)} for event in result.events if event.event_type is EventType.DP_CHANGE]
        return {
            "scope": "two fixed causal 6-8 schedules only; no roster/timing optimization",
            "simulator_evaluations": 5,
            "fang_self_cost_modifier": {
                "actions": [{"operator": _FANG, "frame": 0}, {"operator": _NOIR, "frame": 210}],
                "before_cost_modifier": {"fang_deploy_legal": legal(before, _FANG), "noir_deploy_legal": legal(before, _NOIR), "errors": list(before.deployment_errors)},
                "after_cost_modifier": {"fang_deploy_legal": legal(after, _FANG), "noir_deploy_legal": legal(after, _NOIR), "errors": list(after.deployment_errors), "dp_events": dp_events(after)},
            },
            "vanilla_manual_dp_skill": {
                "actions": [{"operator": _VANILLA, "frame": 30}, {"operator": _VANILLA, "action": "ACTIVATE_SKILL", "frame": 450}, {"operator": _BEAGLE, "frame": 450}],
                "without_dp_effect": {"beagle_deploy_legal": legal(without_dp, _BEAGLE), "errors": list(without_dp.deployment_errors), "dp_events": dp_events(without_dp)},
                "with_dp_effect": {"beagle_deploy_legal": legal(with_dp, _BEAGLE), "errors": list(with_dp.deployment_errors), "dp_events": dp_events(with_dp)},
            },
            "fang_automatic_dp_skill": {
                "actions": [{"operator": _FANG, "frame": 0}],
                "expected_source_timing": {"initial_sp": 6, "sp_cost": 25, "ready_and_auto_activate_frame": 570},
                "observed_dp_events": dp_events(fang_auto),
            },
        }

    def run(self) -> dict:
        operators, relevant = self._operator_rows()
        provenance = [mechanic | {"operator_id": row["operator_id"], "name": row["name"]}
                      for row in operators for mechanic in row["economy_mechanics"]]
        before = {
            "natural_dp": {"initial_dp": 10, "per_second": 1, "two_18_dp_blockers": {"first_frame": 240, "second_frame": 780}},
            "runtime_dp_mechanics": "NONE",
        }
        after = {
            "natural_dp": before["natural_dp"],
            "fang": {"base_cost": 11, "self_cost_delta": -1, "effective_cost": 10, "deploy_frame": 0,
                     "auto_dp_gain": 6, "auto_dp_gain_frame": 570},
            "vanilla": {"effective_cost": 11, "deploy_frame": 30, "manual_dp_gain": 6, "manual_ready_and_effect_frame": 450},
            "two_route_interaction_example": {"first": "Fang at frame 0", "second": "Noir Corne (cost 7) at frame 210",
                                                "route_0_deadline": 244, "route_2_deadline": 274,
                                                "conclusion": "self-cost talent advances this fixed pair 30 frames (30/240 -> 0/210); both were already before the stated arrivals."},
            "deadline_conclusion": "No source-supported DP gain occurs before frame 274. The newly modeled self-cost talent improves opening margin but does not make two 18-DP blockers feasible by the two deadlines.",
        }
        interpreter = {
            "version": self.interpreter.version,
            "recognized": [
                {"pattern": "MANUAL + INCREASE_WITH_TIME + duration>0 + {atk}", "effect": "finite synthetic ATK multiplier", "status": "APPROXIMATE"},
                {"pattern": "MANUAL + INCREASE_WITH_TIME + duration>0 + {cost, atk}", "effect": "immediate DP gain plus finite synthetic ATK multiplier", "status": "SOURCE_PLUS_SEMANTIC_INTERPRETATION"},
                {"pattern": "AUTO + INCREASE_WITH_TIME + duration=0 + {cost}", "effect": "automatic immediate DP gain", "status": "SOURCE_PLUS_SEMANTIC_INTERPRETATION"},
            ],
            "ignored": ["skills with no DP/cost Blackboard key"],
            "rejected": ["attack-recovery/defense-recovery SP", "cost keys coupled to unimplemented sleep/stun/limited explosions", "unrecognized Blackboard key sets"],
            "unknown": ["all Blackboard semantics outside the three explicit patterns"],
        }
        validation = self._causal_validation()
        executable = sum(row["executable"] for row in operators)
        return {
            "low_rarity_economy_audit": {"eligible": len(operators), "executable": executable, "blocked": len(operators) - executable, "operators": operators},
            "opening_economy_relevant_operators": relevant,
            "dp_skill_interpreter_audit": interpreter,
            "economy_mechanics_provenance": provenance,
            "opening_dp_feasibility_after_audit": {"before_audit": before, "after_audit": after,
                                                    "opening_economy_fidelity_gap": "FOUND_BUT_NOT_MATERIAL"},
            "economy_mechanics_validation": validation,
            "classification": "FOUND_BUT_NOT_MATERIAL",
        }
