"""Focused tests for the deliberately synthetic combat-runtime milestone."""
from __future__ import annotations

from dataclasses import replace

from arknights_planner.models.provenance import known
from arknights_planner.models.runtime import SPRecoveryMode, SkillEffect, SyntheticSkill
from arknights_planner.models.simulation import EventType
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import runtime_enemies, runtime_operators, runtime_stage, synthetic_enemies, synthetic_operators, synthetic_stage


def runtime_run(
    strategy: Strategy,
    *,
    stage=None,
    operators=None,
    enemies=None,
    max_time: float = 12.0,
):
    return Simulator().run(
        stage=stage or runtime_stage(),
        operators=operators or runtime_operators(),
        enemies=enemies or runtime_enemies(),
        strategy=strategy,
        config=SimulationConfig(dt=0.1, max_time=max_time),
    )


def events(result, event_type: EventType, *, source: str | None = None):
    result_events = [event for event in result.events if event.event_type is event_type]
    return [event for event in result_events if source is None or event.source_id == source]


def stationary_brute(*, hp: float = 10_000.0, atk: float = 0.0):
    """Keep one synthetic enemy in range to observe skill timing deterministically."""
    brute = runtime_enemies()["brute"]
    return {
        "brute": replace(
            brute,
            stats=replace(
                brute.stats,
                max_hp=known(hp, "synthetic/test", "$.brute.hp"),
                move_speed=known(0.0, "synthetic/test", "$.brute.speed"),
                atk=known(atk, "synthetic/test", "$.brute.atk"),
            ),
        )
    }


def dps_deployment() -> Action:
    return Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP")


def test_time_sp_recovery_marks_skill_ready_at_known_synthetic_time():
    result = runtime_run(Strategy(("dps",), (dps_deployment(),)), enemies=stationary_brute(), max_time=3.1)
    ready = events(result, EventType.SKILL_READY, source="dps")
    assert [(event.time, dict(event.details).get("skill")) for event in ready] == [(3.0, "burst")]


def test_insufficient_sp_rejects_manual_skill_activation():
    result = runtime_run(Strategy(("dps",), (dps_deployment(), Action(ActionType.ACTIVATE_SKILL, 0.0, "dps"))), enemies=stationary_brute())
    activation = events(result, EventType.SKILL_ACTIVATE, source="dps")[0]
    assert dict(activation.details)["legal"] is False
    assert "insufficient SP" in result.deployment_errors[0]


def test_skill_modifies_attack_then_reverts_after_duration():
    result = runtime_run(
        Strategy(("dps",), (dps_deployment(), Action(ActionType.ACTIVATE_SKILL, 3.0, "dps"))),
        enemies=stationary_brute(),
        max_time=6.6,
    )
    damages = {
        event.time: dict(event.details)["amount"]
        for event in events(result, EventType.DAMAGE, source="dps")
    }
    attack_times = [event.time for event in events(result, EventType.ATTACK_START, source="dps")]

    assert damages[2.0] == 35.0
    assert damages[3.0] == 70.0  # Synthetic burst multiplier.
    assert damages[5.5] == 35.0  # SKILL_END is processed before this output.
    assert [time for time in attack_times if 3.0 <= time <= 5.0] == [3.0, 3.5, 4.0, 4.5, 5.0]
    assert events(result, EventType.SKILL_END, source="dps")[0].time == 5.5


def test_additive_attack_modifier_is_composable_with_multiplier():
    operators = runtime_operators()
    operators["dps"] = replace(
        operators["dps"],
        synthetic_skill=SyntheticSkill(
            "test_atk", initial_sp=1.0, sp_cost=1.0, recovery_mode=SPRecoveryMode.TIME,
            sp_per_second=0.0, duration=1.0, effect=SkillEffect(atk_multiplier=2.0, atk_additive=5.0),
        ),
    )
    result = runtime_run(
        Strategy(("dps",), (dps_deployment(), Action(ActionType.ACTIVATE_SKILL, 0.0, "dps"))),
        operators=operators,
        enemies=stationary_brute(),
        max_time=1.1,
    )
    first_damage = events(result, EventType.DAMAGE, source="dps")[0]
    assert dict(first_damage.details)["amount"] == 80.0


def test_active_range_override_reaches_enemy_outside_base_range():
    base = (dps_deployment(),)
    without_skill = runtime_run(Strategy(("dps",), base), max_time=3.1)
    with_skill = runtime_run(Strategy(("dps",), (*base, Action(ActionType.ACTIVATE_SKILL, 3.0, "dps"))), max_time=3.1)

    assert not any(event.time == 3.0 for event in events(without_skill, EventType.DAMAGE, source="dps"))
    assert any(event.time == 3.0 for event in events(with_skill, EventType.DAMAGE, source="dps"))


def test_block_count_modifier_allows_two_synthetic_enemies_to_block():
    operators = runtime_operators()
    operators["blocker"] = replace(
        operators["blocker"],
        synthetic_skill=SyntheticSkill(
            "expand_block", initial_sp=1.0, sp_cost=1.0, recovery_mode=SPRecoveryMode.TIME,
            sp_per_second=0.0, duration=4.0, effect=SkillEffect(block_count_delta=1),
        ),
    )
    stage = replace(runtime_stage(), spawn_events=(SpawnEvent(0.0, "brute", "main"), SpawnEvent(0.0, "brute", "main")))
    result = runtime_run(
        Strategy(("blocker",), (Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT"), Action(ActionType.ACTIVATE_SKILL, 0.0, "blocker"))),
        stage=stage,
        operators=operators,
        max_time=3.0,
    )
    assert len(events(result, EventType.BLOCK, source="blocker")) == 2


def test_healing_is_an_explicit_output_and_caps_at_max_hp():
    brute = runtime_enemies()["brute"]
    gentle_enemies = {
        "brute": replace(brute, stats=replace(brute.stats, atk=known(10.0, "synthetic/test", "$.brute.atk")))
    }
    result = runtime_run(
        Strategy(
            ("blocker", "healer"),
            (Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT"), Action(ActionType.DEPLOY, 0.0, "healer", (3, 2), "UP")),
        ),
        enemies=gentle_enemies,
        max_time=3.1,
    )
    heal = events(result, EventType.HEAL, source="healer")[0]
    assert heal.target_id == "blocker"
    assert dict(heal.details)["amount"] == 5.0  # raw 25 healing is capped to missing HP.


def test_enemy_attack_kills_operator_and_releases_blocked_enemy():
    result = runtime_run(
        Strategy(("blocker",), (Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT"),)),
        max_time=5.1,
    )
    enemy_damage = events(result, EventType.DAMAGE, source="brute#0")[0]
    death = events(result, EventType.OPERATOR_DEATH, source="blocker")[0]
    unblock = events(result, EventType.UNBLOCK, source="blocker")[-1]
    assert dict(enemy_damage.details)["amount"] == 65.0
    assert result.operator_deaths == 1
    assert unblock.time == death.time == 5.0
    assert result.events.index(unblock) < result.events.index(death)


def test_retreat_releases_blocked_enemy():
    result = runtime_run(
        Strategy(
            ("blocker",),
            (Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT"), Action(ActionType.RETREAT, 3.0, "blocker")),
        ),
        max_time=3.1,
    )
    retreat = events(result, EventType.RETREAT, source="blocker")[0]
    unblock = events(result, EventType.UNBLOCK, source="blocker")[0]
    assert retreat.time == unblock.time == 3.0
    assert result.operator_deaths == 0


def test_redeploy_cooldown_rejects_then_allows_later_deployment():
    strategy = Strategy(
        ("guard",),
        (
            Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),
            Action(ActionType.RETREAT, 0.2, "guard"),
            Action(ActionType.DEPLOY, 1.0, "guard", (3, 1), "RIGHT"),
            Action(ActionType.DEPLOY, 3.2, "guard", (3, 1), "RIGHT"),
        ),
    )
    result = Simulator().run(
        stage=synthetic_stage(), operators=synthetic_operators(), enemies=synthetic_enemies(), strategy=strategy,
        config=SimulationConfig(dt=0.1, max_time=3.3),
    )
    deploy_legal = [dict(event.details)["legal"] for event in events(result, EventType.DEPLOY, source="guard")]
    assert deploy_legal == [True, False, True]
    assert any("redeploy cooldown active" in error for error in result.deployment_errors)


def test_ground_and_high_ground_legality_are_position_specific():
    melee = runtime_run(Strategy(("blocker",), (Action(ActionType.DEPLOY, 0.0, "blocker", (1, 2), "RIGHT"),)))
    ranged = runtime_run(Strategy(("dps",), (Action(ActionType.DEPLOY, 0.0, "dps", (1, 1), "UP"),)))
    assert "MELEE operator requires GROUND tile" in melee.deployment_errors[0]
    assert "RANGED operator requires HIGH_GROUND tile" in ranged.deployment_errors[0]


def test_end_to_end_runtime_strategy_requires_blocker_dps_healer_and_skill():
    base_actions = (
        Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT"),
        dps_deployment(),
        Action(ActionType.DEPLOY, 0.0, "healer", (3, 2), "UP"),
    )
    winning = runtime_run(Strategy(("blocker", "dps", "healer"), (*base_actions, Action(ActionType.ACTIVATE_SKILL, 3.0, "dps"))))
    no_skill = runtime_run(Strategy(("blocker", "dps", "healer"), base_actions))
    no_healer = runtime_run(Strategy(("blocker", "dps"), (*base_actions[:-1], Action(ActionType.ACTIVATE_SKILL, 3.0, "dps"))))

    assert winning.win is True
    assert winning.enemies_killed == 1
    assert winning.operator_deaths == 0
    assert events(winning, EventType.HEAL, source="healer")
    assert events(winning, EventType.SKILL_ACTIVATE, source="dps")
    assert no_skill.win is False
    assert no_healer.win is False
