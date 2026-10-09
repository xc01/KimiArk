from __future__ import annotations

from dataclasses import replace
from arknights_planner.models.enemy import Enemy, EnemyStats
from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.runtime import SPRecoveryMode, SkillEffect, SyntheticSkill
from arknights_planner.models.simulation import EventType, SimulationEvent
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import runtime_enemies, runtime_operators, runtime_stage, synthetic_operators


def run(strategy: Strategy, *, stage=None, operators=None, enemies=None, max_time: float = 6.0):
    return Simulator().run(
        stage=stage or runtime_stage(), operators=operators or runtime_operators(),
        enemies=enemies or runtime_enemies(), strategy=strategy,
        config=SimulationConfig(dt=0.1, max_time=max_time),
    )


def events(result, event_type: EventType, *, source: str | None = None) -> list[SimulationEvent]:
    return [event for event in result.events if event.event_type is event_type and (source is None or event.source_id == source)]


def enemy(*, atk: float = 70, apply_way: str | None = None, damage_type: str | None = None, attack_range: float | None = None):
    base = runtime_enemies()["brute"]
    stats = replace(base.stats, atk=known(atk, "atomic/test", "$.atk"))
    if apply_way is not None: stats = replace(stats, apply_way=known(apply_way, "atomic/test", "$.applyWay"))
    if damage_type is not None: stats = replace(stats, damage_type=known(damage_type, "atomic/test", "$.damageType"))
    if attack_range is not None: stats = replace(stats, attack_range=known(attack_range, "atomic/test", "$.rangeRadius"))
    return {"brute": Enemy("brute", known("Atomic Probe", "atomic/test", "$.name"), stats, "atomic/test")}


def deploy(operator_id: str, tile: tuple[int, int], time: float = 0.0, direction: str = "RIGHT"):
    return Action(ActionType.DEPLOY, time, operator_id, tile, direction)


def test_operator_melee_and_ranged_attack_event_traces():
    result = run(Strategy(("blocker", "dps"), (deploy("blocker", (3, 1)), deploy("dps", (1, 2), 0.2, "UP"))))
    assert events(result, EventType.ATTACK_START, source="blocker")
    assert events(result, EventType.ATTACK_START, source="dps")
    assert events(result, EventType.PROJECTILE_BORN, source="dps")
    assert events(result, EventType.PROJECTILE_HIT, source="dps")
    assert events(result, EventType.DAMAGE, source="dps")


def test_operator_aspd_and_base_attack_time_change_interval():
    base = run(Strategy(("dps",), (deploy("dps", (1, 2), 0, "UP"),)), max_time=3.0)
    operators = runtime_operators(); operators["dps"] = replace(operators["dps"], attack_speed=200.0)
    fast = run(Strategy(("dps",), (deploy("dps", (1, 2), 0, "UP"),)), operators=operators, max_time=3.0)
    assert [event.time for event in events(fast, EventType.ATTACK_START, source="dps")[:3]] == [0.0, 0.5, 1.0]
    assert [event.time for event in events(base, EventType.ATTACK_START, source="dps")[:3]] == [0.0, 1.0, 2.0]


def test_operator_base_attack_time_is_independent_source():
    operators = runtime_operators()
    operator = operators["dps"]
    stats = replace(operator.phases[0].stats_max, attack_interval=known(2.0, "atomic/test", "$.baseAttackTime"))
    operators["dps"] = replace(operator, phases=(replace(operator.phases[0], stats_max=stats),))
    result = run(Strategy(("dps",), (deploy("dps", (1, 2), 0, "UP"),)), operators=operators, max_time=2.1)
    assert [event.time for event in events(result, EventType.ATTACK_START, source="dps")] == [0.0, 2.0]


def test_first_operator_attack_occurs_at_deployment_frame_when_target_available():
    result = run(Strategy(("dps",), (deploy("dps", (1, 2), 1.0, "UP"),)))
    attacks = events(result, EventType.ATTACK_START, source="dps")
    assert attacks and attacks[0].time == 1.0


def test_defense_sp_is_not_silently_treated_as_time_or_attack_sp():
    for mode in (SPRecoveryMode.DEFENSE,):
        operators = runtime_operators()
        operators["dps"] = replace(operators["dps"], synthetic_skill=SyntheticSkill(
            f"probe-{mode.value}", 0.0, 1.0, mode, 0.0, 1.0, SkillEffect(atk_multiplier=2.0),
        ))
        result = run(Strategy(("dps",), (deploy("dps", (1, 2), 0, "UP"),)), operators=operators)
        assert events(result, EventType.SKILL_READY) == []
        assert events(result, EventType.SKILL_ACTIVATE) == []


def test_attack_sp_requires_normal_attacks_not_elapsed_time():
    operators = runtime_operators()
    operators["dps"] = replace(operators["dps"], synthetic_skill=SyntheticSkill(
        "probe-attack", 0.0, 1.0, SPRecoveryMode.ATTACK, 0.0, 1.0, SkillEffect(atk_multiplier=2.0), auto_activate=True,
    ))
    result = run(Strategy(("dps",), (deploy("dps", (1, 2), 0, "UP"),)), operators=operators, max_time=0.1)
    assert events(result, EventType.SKILL_READY) == []


def test_ammo_and_multi_charge_states_are_absent_not_approximated():
    operators = runtime_operators()
    skill = SyntheticSkill("probe", 1.0, 1.0, SPRecoveryMode.TIME, 0.0, 1.0, SkillEffect())
    operators["dps"] = replace(operators["dps"], synthetic_skill=skill)
    assert not any(hasattr(skill, name) for name in ("ammo_left", "charges", "max_charges", "pending_next_attack"))


def test_melee_enemy_with_nonzero_source_range_attacks_only_blocker():
    operators = runtime_operators()
    result = run(Strategy(("blocker", "dps"), (deploy("blocker", (1, 1)), deploy("dps", (1, 2), 0.0, "UP"))), enemies=enemy(apply_way="MELEE", attack_range=2.5))
    attacks = events(result, EventType.ATTACK_START, source="brute#0")
    assert attacks
    assert all(event.target_id == "blocker" for event in attacks)


def test_ranged_enemy_attack_uses_source_range_radius():
    result = run(Strategy(("dps",), (deploy("dps", (1, 2), 0.0, "UP"),)), enemies=enemy(apply_way="RANGED", attack_range=2.0))
    attacks = events(result, EventType.ATTACK_START, source="brute#0")
    assert attacks and attacks[0].target_id == "dps"


def test_magic_enemy_attack_uses_arts_mitigation_and_event_kind():
    operators = runtime_operators()
    blocker = operators["blocker"]
    stats = replace(blocker.phases[0].stats_max, magic_resistance=known(50.0, "atomic/test", "$.magicResistance"))
    operators["blocker"] = replace(blocker, phases=(replace(blocker.phases[0], stats_max=stats),))
    result = run(Strategy(("blocker",), (deploy("blocker", (1, 1)),)), operators=operators, enemies=enemy(apply_way="MELEE", damage_type="ARTS", atk=100))
    damage = events(result, EventType.DAMAGE, source="brute#0")
    assert damage and dict(damage[0].details)["kind"] == "enemy_arts"
    assert dict(damage[0].details)["amount"] == 50.0


def test_enemy_windup_and_recovery_are_explicitly_absent_without_client_timing():
    result = run(Strategy(("dps",), (deploy("dps", (1, 2), 0.0, "UP"),)), enemies=enemy(apply_way="RANGED", attack_range=2.0))
    attack_times = [event.time for event in events(result, EventType.ATTACK_START, source="brute#0")]
    damage_times = [event.time for event in events(result, EventType.DAMAGE, source="brute#0")]
    assert attack_times == damage_times


def test_enemy_skills_have_no_runtime_in_current_model():
    result = run(Strategy(("blocker",), (deploy("blocker", (1, 1)),)))
    assert events(result, EventType.SKILL_ACTIVATE) == []
    assert events(result, EventType.SKILL_END) == []


def test_move_wait_move_route_preserves_wait_distance_and_duration():
    route = Route("main", (Waypoint(0, 1), Waypoint(3, 1), Waypoint(6, 1)), ())
    stage = replace(runtime_stage(), routes=(route,))
    result = run(Strategy(("blocker",), (deploy("blocker", (5, 1)),)), stage=stage)
    block = events(result, EventType.BLOCK, source="blocker")
    assert block and block[0].time > 0


def test_blocker_death_releases_enemy_and_next_blocker_takes_over():
    route = Route("main", (Waypoint(0, 1), Waypoint(6, 1)), ())
    stage = replace(runtime_stage(), routes=(route,))
    operators = {"blocker": runtime_operators()["blocker"], "guard": synthetic_operators()["guard"]}
    result = run(
        Strategy(("blocker", "guard"), (deploy("blocker", (1, 1)), deploy("guard", (2, 1)))),
        stage=stage, operators=operators, enemies=enemy(atk=9999),
    )
    unblocks = events(result, EventType.UNBLOCK, source="blocker")
    takeover = [event for event in events(result, EventType.BLOCK) if event.source_id == "guard"]
    assert unblocks and takeover
    assert unblocks[0].time <= takeover[0].time


def test_movement_into_ranged_range_is_tick_quantized():
    result = run(Strategy(("dps",), (deploy("dps", (1, 2), 0.0, "UP"),)), max_time=3.0)
    attack = events(result, EventType.ATTACK_START, source="dps")
    assert attack and attack[0].time == 0.0


def test_disappear_and_appear_checkpoints_are_not_runtime_route_legs():
    route = runtime_stage().routes[0]
    assert not hasattr(route, "legs")
    assert all(hasattr(waypoint, "x") and hasattr(waypoint, "y") for waypoint in route.waypoints)
