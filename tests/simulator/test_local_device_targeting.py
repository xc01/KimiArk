from __future__ import annotations

from dataclasses import replace

from arknights_planner.models.enemy import Enemy, EnemyStats
from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.simulation import EventType
from arknights_planner.models.stage import BattleDevice, SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import runtime_operators, runtime_stage


_SOURCE = "tests/simulator/test_local_device_targeting.py"


def _stationary_enemy() -> Enemy:
    stats = EnemyStats(
        max_hp=known(1_000, _SOURCE, "$.enemy.hp"), atk=known(0, _SOURCE, "$.enemy.atk"),
        defense=known(0, _SOURCE, "$.enemy.def"), magic_resistance=known(0, _SOURCE, "$.enemy.res"),
        move_speed=known(0.0, _SOURCE, "$.enemy.speed"), attack_interval=known(10, _SOURCE, "$.enemy.interval"),
        weight=known(0, _SOURCE, "$.enemy.mass"), life_point_reduce=known(1, _SOURCE, "$.enemy.life"),
        apply_way=known("MELEE", _SOURCE, "$.enemy.applyWay"), damage_type=known("PHYSICAL", _SOURCE, "$.enemy.damage"),
    )
    return Enemy("stationary", known("Stationary Enemy", _SOURCE, "$.enemy.name"), stats, _SOURCE)


def _run(*, device_tile: tuple[int, int], ordinary_targetable: bool = True, enemy: bool = False, enemy_route: str = "remote"):
    device = BattleDevice(
        "roadblock#0", "trap_020_roadblock", device_tile, 50.0, 0.0, 0.0, -1,
        ordinary_targetable=ordinary_targetable,
    )
    routes = (
        Route("main", (Waypoint(1, 1), Waypoint(6, 1))),
        Route("remote", (Waypoint(6, 1), Waypoint(6, 0))),
    )
    stage = replace(
        runtime_stage(), routes=routes, devices=(device,),
        spawn_events=(SpawnEvent(0.0, "stationary", enemy_route),) if enemy else (SpawnEvent(100.0, "stationary", "remote"),),
    )
    return Simulator().run(
        stage=stage,
        operators=runtime_operators(),
        enemies={"stationary": _stationary_enemy()},
        strategy=Strategy(("dps",), (Action(ActionType.DEPLOY, 0.0, "dps", (1, 2), "UP"),)),
        config=SimulationConfig(dt=0.1, max_time=2.0),
    )


def test_remote_enemy_does_not_prevent_local_roadblock_targeting():
    result = _run(device_tile=(1, 1), enemy=True, enemy_route="remote")
    assert [event for event in result.events if event.event_type is EventType.SPAWN and event.source_id == "stationary#0"]
    assert not [event for event in result.events if event.event_type is EventType.ENEMY_DEATH and event.target_id == "stationary#0"]
    attacks = [event for event in result.events if event.event_type is EventType.ATTACK_START and event.target_id == "roadblock#0"]
    assert attacks
    assert [event for event in result.events if event.event_type is EventType.DEVICE_DESTROYED]
    assert result.enemies_killed == 0


def test_optional_local_enemy_has_priority_over_device():
    result = _run(device_tile=(1, 1), enemy=True, enemy_route="main")
    selections = [event for event in result.events if event.event_type is EventType.TARGET_SELECTION and event.source_id == "dps"]
    assert selections
    assert all(event.target_id == "stationary#0" for event in selections)
    assert not [event for event in result.events if event.event_type is EventType.DEVICE_TARGET_SELECTION]
    assert not [event for event in result.events if event.event_type is EventType.DEVICE_DAMAGE]


def test_device_outside_operator_range_is_not_targeted():
    result = _run(device_tile=(6, 1))
    assert not [event for event in result.events if event.event_type is EventType.ATTACK_START and event.target_id == "roadblock#0"]
    assert not [event for event in result.events if event.event_type is EventType.DEVICE_DAMAGE]


def test_non_ordinary_device_is_not_targeted():
    result = _run(device_tile=(1, 1), ordinary_targetable=False)
    assert not [event for event in result.events if event.event_type is EventType.ATTACK_START and event.target_id == "roadblock#0"]
    assert not [event for event in result.events if event.event_type is EventType.DEVICE_DAMAGE]
