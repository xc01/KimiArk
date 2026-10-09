from __future__ import annotations

from dataclasses import replace

from arknights_planner.adapters.low_rarity_skill import LowRarityBlackboardEffectInterpreter
from arknights_planner.models.provenance import known
from arknights_planner.models.runtime import SPRecoveryMode, SkillEffect, SyntheticSkill
from arknights_planner.models.simulation import EventType
from arknights_planner.simulator import Simulator
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.models.simulation import RuntimeOperator
from arknights_planner.simulator.synthetic import runtime_operators

from tests.simulator.test_combat_runtime import events, runtime_run, stationary_brute


def _skill(effect: SkillEffect, mode: SPRecoveryMode = SPRecoveryMode.TIME, auto: bool = False, cost: float = 0.0, duration: float = 1.0) -> SyntheticSkill:
    return SyntheticSkill("generic", 0.0, cost, mode, 0.0, duration, effect, auto_activate=auto)


def test_attack_sp_next_attack_skill_consumes_on_next_attack():
    operators = runtime_operators()
    operators["dps"] = replace(operators["dps"], synthetic_skill=_skill(
        SkillEffect(next_attack_atk_scale=2.0, next_attack_hit_count=2), SPRecoveryMode.ATTACK, True, cost=2.0,
    ))
    result = runtime_run(
        Strategy(("dps",), (Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP"),)),
        operators=operators, enemies=stationary_brute(), max_time=2.1,
    )
    activation = events(result, EventType.SKILL_ACTIVATE, source="dps")
    damages = [dict(event.details) for event in events(result, EventType.DAMAGE, source="dps") if event.time == 2.0]
    assert [(event.time, dict(event.details).get("next_attack")) for event in activation] == [(2.0, True)]
    assert damages == [{"amount": 70.0, "kind": "physical"}, {"amount": 70.0, "kind": "physical"}]


def test_defense_buff_reduces_incoming_physical_damage():
    operators = runtime_operators()
    operators["blocker"] = replace(operators["blocker"], synthetic_skill=_skill(
        SkillEffect(defense_additive_ratio=12.0), duration=2.0,
    ))
    result = runtime_run(
        Strategy(("blocker",), (Action(ActionType.DEPLOY, 0.0, "blocker", (1, 1), "RIGHT"), Action(ActionType.ACTIVATE_SKILL, 0.0, "blocker"))),
        operators=operators, max_time=1.0,
    )
    damage = events(result, EventType.DAMAGE, source="brute#0")
    assert damage and dict(damage[0].details)["amount"] == 5.0


def test_aspd_additive_shortens_attack_interval():
    operators = runtime_operators()
    operators["dps"] = replace(operators["dps"], synthetic_skill=_skill(SkillEffect(attack_speed_additive=100.0)))
    result = runtime_run(
        Strategy(("dps",), (Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP"), Action(ActionType.ACTIVATE_SKILL, 0.0, "dps"))),
        operators=operators, enemies=stationary_brute(), max_time=1.1,
    )
    assert [event.time for event in events(result, EventType.ATTACK_START, source="dps")] == [0.0, 0.5, 1.0]


def test_forward_range_extension_adds_right_facing_cells():
    simulator = Simulator()
    base = runtime_operators()["dps"]
    operator = RuntimeOperator(
        "dps", (1, 2), "UP", 100.0, 100.0, 70.0, 0, 1.0, base.attack_range, 0.0, 0.0, "DAMAGE", 3.0,
        position="RANGED", skill=_skill(SkillEffect(range_forward_extend=2)), skill_active=True,
    )
    assert simulator._effective_range(operator) == (*operator.base_attack_range, (0, 1), (0, 2))


def test_low_rarity_blackboard_patterns_map_to_generic_effects():
    interpreter = LowRarityBlackboardEffectInterpreter()
    from arknights_planner.models.skill import SkillLevel

    def level(skill_type: str, sp_type: str, blackboard: dict[str, float], duration: float = 0.0):
        return SkillLevel(0, known("probe", "test", "$.name"), known(None, "test", "$.range"), known(skill_type, "test", "$.type"),
                          known("NONE", "test", "$.durationType"), known(sp_type, "test", "$.spType"), known(0, "test", "$.cost"),
                          known(0, "test", "$.init"), known(0, "test", "$.charges"), known(duration, "test", "$.duration"),
                          tuple(blackboard.items()))

    assert interpreter.interpret("def", level("MANUAL", "INCREASE_WITH_TIME", {"def": 0.5}, 30.0)).executable_effect.effect.defense_additive_ratio == 0.5
    assert interpreter.interpret("aspd", level("MANUAL", "INCREASE_WITH_TIME", {"attack_speed": 50.0}, 20.0)).executable_effect.effect.attack_speed_additive == 50.0
    assert interpreter.interpret("range", level("MANUAL", "INCREASE_WITH_TIME", {"atk": 0.4, "ability_range_forward_extend": 2.0}, 25.0)).executable_effect.effect.range_forward_extend == 2
    scaled = interpreter.interpret("next", level("AUTO", "INCREASE_WHEN_ATTACK", {"atk_scale": 1.4, "times": 2.0}))
    assert (scaled.executable_effect.effect.next_attack_atk_scale, scaled.executable_effect.effect.next_attack_hit_count) == (1.4, 2)
    single = interpreter.interpret("single", level("AUTO", "INCREASE_WHEN_ATTACK", {"atk_scale": 1.9}))
    assert (single.executable_effect.effect.next_attack_atk_scale, single.executable_effect.effect.next_attack_hit_count) == (1.9, 1)
