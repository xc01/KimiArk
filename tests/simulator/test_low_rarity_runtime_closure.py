from __future__ import annotations

from dataclasses import replace

from arknights_planner.models.runtime import SkillEffect, SPRecoveryMode, SyntheticSkill
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import Simulator
from arknights_planner.simulator.synthetic import runtime_operators, runtime_stage

from tests.simulator.test_combat_runtime import events, runtime_run, stationary_brute


def _dps_skill(effect: SkillEffect, duration: float = 1.2) -> SyntheticSkill:
    return SyntheticSkill("closure", 0.0, 0.0, SPRecoveryMode.TIME, 0.0, duration, effect)


def test_base_attack_time_override_controls_attack_timestamps():
    operators = runtime_operators()
    operators["dps"] = replace(operators["dps"], synthetic_skill=_dps_skill(SkillEffect(base_attack_time_override=2.0), 5.0))
    result = runtime_run(
        Strategy(("dps",), (Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP"), Action(ActionType.ACTIVATE_SKILL, 0.0, "dps"))),
        operators=operators, enemies=stationary_brute(), max_time=2.1,
    )
    assert [event.time for event in events(result, EventType.ATTACK_START, source="dps")] == [0.0, 2.0]


def test_base_attack_time_and_aspd_are_composable():
    operators = runtime_operators()
    effect = SkillEffect(base_attack_time_override=2.0, attack_speed_additive=100.0)
    operators["dps"] = replace(operators["dps"], synthetic_skill=_dps_skill(effect, 5.0))
    result = runtime_run(
        Strategy(("dps",), (Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP"), Action(ActionType.ACTIVATE_SKILL, 0.0, "dps"))),
        operators=operators, enemies=stationary_brute(), max_time=2.1,
    )
    assert [event.time for event in events(result, EventType.ATTACK_START, source="dps")] == [0.0, 1.0, 2.0]


def test_base_attack_time_override_is_restored_after_skill_end():
    operators = runtime_operators()
    operators["dps"] = replace(operators["dps"], synthetic_skill=_dps_skill(SkillEffect(base_attack_time_override=2.0), 1.0))
    result = runtime_run(
        Strategy(("dps",), (Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP"), Action(ActionType.ACTIVATE_SKILL, 0.0, "dps"))),
        operators=operators, enemies=stationary_brute(), max_time=2.1,
    )
    assert [event.time for event in events(result, EventType.ATTACK_START, source="dps")] == [0.0, 2.0]
    assert events(result, EventType.SKILL_END, source="dps")[0].time == 1.0


def test_immediate_self_heal_uses_max_hp_ratio():
    operators = runtime_operators()
    operators["blocker"] = replace(operators["blocker"], synthetic_skill=SyntheticSkill(
        "self_heal", 20.0, 20.0, SPRecoveryMode.TIME, 0.0, 0.0,
        SkillEffect(immediate_self_heal_ratio=0.4),
    ))
    result = runtime_run(
        Strategy(("blocker",), (Action(ActionType.DEPLOY, 0.0, "blocker", (1, 1), "RIGHT"), Action(ActionType.ACTIVATE_SKILL, 1.1, "blocker"))),
        operators=operators, max_time=1.1,
    )
    heals = events(result, EventType.HEAL, source="blocker")
    assert heals and dict(heals[0].details)["amount"] == 64.0


def test_heal_mode_stops_damage_and_heals_injured_ally():
    operators = runtime_operators()
    operators["dps"] = replace(operators["dps"], synthetic_skill=SyntheticSkill(
        "heal_mode", 20.0, 20.0, SPRecoveryMode.TIME, 0.0, 3.0,
        SkillEffect(atk_multiplier=1.45, base_attack_time_override=1.3, heal_mode=True),
    ))
    result = runtime_run(
        Strategy(("blocker", "dps"), (
            Action(ActionType.DEPLOY, 0.0, "blocker", (1, 1), "RIGHT"),
            Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP"),
            Action(ActionType.ACTIVATE_SKILL, 0.1, "dps"),
        )), operators=operators, max_time=1.4,
    )
    heal = [event for event in events(result, EventType.HEAL, source="dps") if event.time == 1.0]
    assert heal and dict(heal[0].details)["amount"] == 50.75
