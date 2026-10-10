from __future__ import annotations

from dataclasses import replace

from arknights_planner.models.runtime import CombatOutputType, SkillEffect, SPRecoveryMode, SyntheticSkill
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.models.enemy import EnemyStats
from arknights_planner.models.provenance import known
from tests.simulator.test_combat_runtime import events, runtime_enemies, runtime_operators, runtime_run
from tests.simulator.test_low_rarity_runtime_closure import stationary_brute


def test_deployment_sp_bonus_can_complete_skill_ready_state():
    operators = runtime_operators()
    operators["dps"] = replace(
        operators["dps"],
        synthetic_skill=SyntheticSkill("sp_talent", 0.0, 15.0, SPRecoveryMode.TIME, 1.0, 2.0, SkillEffect()),
        deployment_sp_bonus=15.0,
    )
    result = runtime_run(
        Strategy(("dps",), (Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP"),)),
        operators=operators, enemies=stationary_brute(), max_time=0.1,
    )
    assert events(result, EventType.SKILL_READY, source="dps")
    assert not events(result, EventType.SKILL_ACTIVATE, source="dps")


def test_deployment_global_heal_hits_all_deployed_allies():
    operators = runtime_operators()
    operators["blocker"] = replace(operators["blocker"], deployment_heal_all_value=30.0)
    operators["healer"] = replace(operators["healer"], deployment_heal_all_value=30.0)
    brute = runtime_enemies()["brute"]
    gentle_brute = {
        "brute": replace(
            brute,
            stats=replace(brute.stats, atk=known(10.0, "synthetic/test", "$.brute.atk")),
        )
    }
    result = runtime_run(
        Strategy(("blocker", "healer"), (
            Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT"),
            Action(ActionType.DEPLOY, 6.0, "healer", (3, 2), "UP"),
        )),
        operators=operators,
        enemies=gentle_brute,
        max_time=6.1,
    )
    heals = [
        event
        for event in events(result, EventType.HEAL)
        if dict(event.details).get("reason") == "deployment_heal_all"
    ]
    assert [(event.time, event.source_id, event.target_id) for event in heals] == [
        (0.0, "blocker", "blocker"),
        (6.0, "healer", "blocker"),
        (6.0, "healer", "healer"),
    ]
    assert [dict(event.details)["amount"] for event in heals] == [0.0, 15.0, 0.0]


def test_redeploy_time_delta_shortens_actual_cooldown():
    operators = runtime_operators()
    operators["blocker"] = replace(
        operators["blocker"],
        redeploy_time=known(40.0, "synthetic/test", "$.blocker.redeploy"),
        redeploy_time_delta=-30.0,
    )
    first = Strategy(("blocker",), (
        Action(ActionType.DEPLOY, 0.0, "blocker", (1, 1), "RIGHT"),
        Action(ActionType.RETREAT, 0.0, "blocker"),
        Action(ActionType.DEPLOY, 9.9, "blocker", (1, 1), "RIGHT"),
        Action(ActionType.DEPLOY, 10.0, "blocker", (1, 1), "RIGHT"),
    ))
    result = runtime_run(first, operators=operators, enemies=stationary_brute(), max_time=10.1)
    deploys = [dict(event.details)["legal"] for event in events(result, EventType.DEPLOY, source="blocker")]
    assert deploys == [True, False, True]
