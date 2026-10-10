from dataclasses import replace
from types import SimpleNamespace

from arknights_planner.adapters.approximate_real import ApproximateRealSimulationAdapter

from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.simulation import EventType, SimulationState
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage


def test_source_route_coordinate_is_not_a_serialized_map_array_row():
    coordinate = SimpleNamespace(row=known(1, "source/review", "$.row"), col=known(9, "source/review", "$.col"))
    point = ApproximateRealSimulationAdapter._coordinate(coordinate, map_height=7)
    assert (point.x, point.y) == (9, 1)


def test_predefined_device_uses_field_coordinates_without_a_second_row_flip():
    payload = {
        "mapData": {"map": [[0] * 11 for _ in range(7)]},
        "predefines": {"tokenInsts": [{"inst": {"characterKey": "trap_020_roadblock"}, "position": {"row": 4, "col": 9}}]},
    }
    source_character = {"trap_020_roadblock": {"phases": [{"attributesKeyFrames": [{"data": {"maxHp": 8000, "def": 200, "magicResistance": 20, "tauntLevel": -1}}]}]}}
    repository = SimpleNamespace(
        get_stage_level_document=lambda _: (None, None, None, payload),
        _table=lambda _: source_character,
    )
    adapted = SimpleNamespace(stage=SimpleNamespace(stage_id="coordinate-fixture"))
    devices = ApproximateRealSimulationAdapter(repository)._devices(adapted)
    assert devices[0].tile == (9, 4)


def test_thirty_fps_clock_dispatches_action_at_frame_90_not_91():
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(100.0, "slug", "main"),))
    result = Simulator().run(
        stage=stage, operators=synthetic_operators(), enemies=synthetic_enemies(),
        strategy=Strategy(("guard",), (Action(ActionType.DEPLOY, 3.0, "guard", (3, 1)),)),
        config=SimulationConfig(dt=1 / 30, max_time=3.0),
    )
    deployments = [event for event in result.events if event.event_type is EventType.DEPLOY]
    assert [event.time for event in deployments] == [3.0]


def test_high_ground_unit_with_nonzero_block_stat_does_not_hold_ground_enemy():
    stage = replace(synthetic_stage(), routes=(Route("main", (Waypoint(0, 2), Waypoint(6, 2))),))
    operators = synthetic_operators()
    archer = operators["archer"]
    phase = archer.phases[0]
    stats = replace(phase.stats_max, block_count=known(1, "synthetic/review", "$.block"))
    operators["archer"] = replace(archer, phases=(replace(phase, stats_max=stats, stats_min=stats),))
    state = SimulationState(0, 10, 3)
    simulator = Simulator()
    strategy = Strategy(("archer",), (Action(ActionType.DEPLOY, 0, "archer", (3, 2)),))
    simulator._deploy(state, stage, operators, strategy, strategy.actions[0])
    assert not state.deployment_errors
    assert state.deployed_operators["archer"].base_block_count == 1
    simulator._spawn(state, synthetic_enemies(), enemy_id="slug", route_id="main", spawn_index=0)
    simulator._advance_enemies(state, stage, 4.0)
    assert state.active_enemies["slug#0"].blocked_by is None
    assert state.active_enemies["slug#0"].distance == 4.0
