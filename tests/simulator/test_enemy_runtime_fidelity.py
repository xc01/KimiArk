from __future__ import annotations

from dataclasses import replace

from arknights_planner.models.enemy import EnemyAbility, EnemyAttackTiming
from arknights_planner.models.provenance import known
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import runtime_enemies, runtime_operators, runtime_stage
from tests.simulator.test_combat_runtime import events


def enemy_events(result, event_type, *, source, target=None):
    return [
        event for event in events(result, event_type, source=source)
        if target is None or event.target_id == target
    ]


def deploy(operator_id: str, tile: tuple[int, int], *, time: float = 0.0, direction: str = "RIGHT") -> Action:
    return Action(ActionType.DEPLOY, time, operator_id, tile, direction)


def run(*, operators=None, enemies=None, stage=None, strategy=None, max_time: float = 10.0):
    return Simulator().run(
        stage=stage or runtime_stage(),
        operators=operators or runtime_operators(),
        enemies=enemies or runtime_enemies(),
        strategy=strategy or Strategy(("blocker",), (deploy("blocker", (3, 1)),)),
        config=SimulationConfig(dt=0.1, max_time=max_time),
    )


def test_melee_enemy_moves_blocks_and_attacks_with_event_trace():
    result = run(
        strategy=Strategy(("blocker",), (deploy("blocker", (3, 1)),)),
        max_time=6.0,
    )
    enemy = "brute#0"
    assert events(result, EventType.SPAWN, source=enemy)
    assert enemy_events(result, EventType.BLOCK, source="blocker", target=enemy)
    assert [event.event_type.value for event in events(result, EventType.ATTACK_START, source=enemy)]
    assert enemy_events(result, EventType.DAMAGE, source=enemy, target="blocker")
    assert events(result, EventType.ATTACK_START, source="blocker")


def test_enemy_dies_after_operator_strike_with_event_trace():
    blocker = runtime_operators()["blocker"]
    blocker_stats = replace(blocker.phases[0].stats_max, atk=known(1_000.0, "enemy/test", "$.blocker.atk"))
    blocker = replace(blocker, phases=(replace(blocker.phases[0], stats_min=blocker_stats, stats_max=blocker_stats),))
    result = run(
        operators={"blocker": blocker},
        strategy=Strategy(("blocker",), (deploy("blocker", (3, 1)),)),
        max_time=6.0,
    )
    assert events(result, EventType.ATTACK_START, source="blocker")
    assert enemy_events(result, EventType.ENEMY_DEATH, source="blocker", target="brute#0")


def test_ranged_enemy_attacks_without_being_blocked():
    operators = runtime_operators()
    enemy = runtime_enemies()["brute"]
    enemy = replace(
        enemy,
        stats=replace(
            enemy.stats,
            max_hp=known(1_000_000.0, "enemy/test", "$.hp"),
            apply_way=known("RANGED", "enemy/test", "$.applyWay"),
            attack_range=known(1.5, "enemy/test", "$.range"),
        ),
    )
    result = run(
        strategy=Strategy(("dps",), (deploy("dps", (1, 2), direction="UP"),)),
        operators=operators,
        enemies={"brute": enemy},
        max_time=2.1,
    )
    assert not events(result, EventType.BLOCK)
    assert [event.time for event in events(result, EventType.ATTACK_START, source="brute#0")] == [0.0, 1.0, 2.0]
    assert enemy_events(result, EventType.DAMAGE, source="brute#0", target="dps")


def test_arts_enemy_uses_arts_mitigation_not_defense():
    operators = runtime_operators()
    enemy = runtime_enemies()["brute"]
    enemy = replace(
        enemy,
        stats=replace(
            enemy.stats,
            atk=known(100.0, "enemy/test", "$.atk"),
            damage_type=known("ARTS", "enemy/test", "$.damageType"),
        ),
    )
    result = run(
        strategy=Strategy(("blocker",), (deploy("blocker", (3, 1)),)),
        operators=operators,
        enemies={"brute": enemy},
        max_time=4.0,
    )
    damage = enemy_events(result, EventType.DAMAGE, source="brute#0", target="blocker")[0]
    assert dict(damage.details)["kind"] == "enemy_arts"
    assert dict(damage.details)["amount"] == 100.0


def test_client_derived_windup_strike_and_recovery_event_trace():
    enemies = runtime_enemies()
    enemies["brute"] = replace(
        enemies["brute"],
        stats=replace(enemies["brute"].stats, apply_way=known("RANGED", "enemy/test", "$.applyWay"), attack_range=known(2.0, "enemy/test", "$.range")),
        attack_timing=EnemyAttackTiming("Attack", 1.0, 0.4, 0.6, "EXACT_CLIENT_DERIVED", "client/test.skel"),
    )
    result = run(enemies=enemies, strategy=Strategy(("dps",), (deploy("dps", (1, 2), time=0.0, direction="UP"),)), max_time=2.2)
    assert [event.time for event in events(result, EventType.ATTACK_WINDUP, source="brute#0")] == [0.0, 0.6, 1.6]
    assert [event.time for event in events(result, EventType.ATTACK_START, source="brute#0")] == [0.0, 1.0, 2.0]
    assert [event.time for event in events(result, EventType.ATTACK_STRIKE, source="brute#0")] == [0.0, 1.0, 2.0]
    assert [event.time for event in events(result, EventType.DAMAGE, source="brute#0")] == [0.0, 1.0, 2.0]
    assert [event.time for event in events(result, EventType.ATTACK_RECOVERY_END, source="brute#0")] == [0.6, 1.6]


def test_target_death_before_strike_prevents_ghost_damage():
    operators = runtime_operators()
    operator = operators["dps"]
    frail_stats = replace(operator.phases[0].stats_max, max_hp=known(1.0, "enemy/test", "$.hp"))
    operators["dps"] = replace(operator, phases=(replace(operator.phases[0], stats_min=frail_stats, stats_max=frail_stats),))
    enemies = runtime_enemies()
    enemies["brute"] = replace(
        enemies["brute"],
        stats=replace(enemies["brute"].stats, apply_way=known("RANGED", "enemy/test", "$.applyWay"), attack_range=known(2.0, "enemy/test", "$.range")),
        attack_timing=EnemyAttackTiming("Attack", 1.0, 0.4, 0.6, "EXACT_CLIENT_DERIVED", "client/test.skel"),
    )
    result = run(enemies=enemies, strategy=Strategy(("dps",), (deploy("dps", (1, 2), time=0.0, direction="UP"),)), operators=operators, max_time=1.2)
    assert events(result, EventType.DAMAGE, source="brute#0")
    windup = [event for event in events(result, EventType.ATTACK_WINDUP, source="brute#0") if event.time > 0.0]
    assert windup
    assert not [event for event in events(result, EventType.DAMAGE, source="brute#0") if event.time > 0.0]


def test_route_wait_advances_route_distance_by_source_wait_duration():
    from arknights_planner.models.route import Route, RouteWait, Waypoint
    from arknights_planner.models.stage import StageMap, Tile
    stage = replace(
        runtime_stage(),
        stage_map=StageMap(7, 3, tuple(Tile(x, y, True, "GROUND") for y in range(3) for x in range(7))),
        routes=(Route("main", (Waypoint(0, 1), Waypoint(6, 1)), (RouteWait(1.0, 2.0),)),),
    )
    result = run(stage=stage, strategy=Strategy((), ()), max_time=8.1)
    leak = events(result, EventType.ENEMY_LEAK, source="brute#0")[0]
    assert abs(leak.time - 8.0) <= 0.1


def test_independent_enemy_ability_clock_does_not_use_normal_attack_interval():
    enemy = runtime_enemies()["brute"]
    blocker = runtime_operators()["blocker"]
    blocker_stats = replace(blocker.phases[0].stats_max, max_hp=known(10_000.0, "enemy/test", "$.blocker.hp"))
    blocker = replace(
        blocker,
        phases=(replace(blocker.phases[0], stats_min=blocker_stats, stats_max=blocker_stats),),
    )
    enemy = replace(
        enemy,
        stats=replace(enemy.stats, max_hp=known(1_000_000.0, "enemy/test", "$.hp")),
        abilities=(EnemyAbility("probe_burst", "PERIODIC_AREA_ATTACK", 5.0, 3.0, 2.0, 1.0, "ARTS"),),
    )
    result = run(
        strategy=Strategy(("blocker",), (deploy("blocker", (3, 1)),)),
        operators={"blocker": blocker},
        enemies={"brute": enemy},
        max_time=8.1,
    )
    ability_starts = [event.time for event in events(result, EventType.ENEMY_ABILITY_START, source="brute#0")]
    assert ability_starts == [3.0, 8.0]
    assert [dict(event.details)["ability"] for event in events(result, EventType.ENEMY_ABILITY_HIT, source="brute#0")] == ["probe_burst", "probe_burst"]
    assert enemy_events(result, EventType.DAMAGE, source="brute#0", target="blocker")
