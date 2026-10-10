from __future__ import annotations

from dataclasses import replace
import unittest

from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.simulation import EventType
from arknights_planner.models.simulation import RuntimeDevice, SimulationState
from arknights_planner.models.stage import BattleDevice, SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage


def run(strategy: Strategy, *, stage=None, max_time: float = 20.0):
    return Simulator().run(
        stage=stage or synthetic_stage(), operators=synthetic_operators(), enemies=synthetic_enemies(),
        strategy=strategy, config=SimulationConfig(dt=0.1, max_time=max_time),
    )


def events(result, kind: EventType):
    return [event for event in result.events if event.event_type is kind]


def test_route_position_is_continuous_and_piecewise_linear():
    route = Route("turn", (Waypoint(0, 0), Waypoint(3, 0), Waypoint(3, 4)))
    assert route.length == 7.0
    assert route.position_at(1.5) == (1.5, 0.0)
    assert route.position_at(5.0) == (3.0, 2.0)
    assert route.distance_at((3, 2)) == 5.0


def test_spawn_schedule_uses_explicit_synthetic_times():
    result = run(Strategy((), ()), max_time=20.0)
    assert [event.time for event in events(result, EventType.SPAWN)] == [1.0, 2.0, 3.0, 4.0]


def test_natural_dp_generation_is_deterministic():
    result = run(Strategy((), ()), max_time=20.0)
    assert result.final_dp > 10.0
    assert round(result.final_dp, 1) == 20.0


def test_deployment_legality_and_dp_cost():
    strategy = Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),))
    result = run(strategy)
    deployment = events(result, EventType.DEPLOY)[0]
    assert ("legal", True) in deployment.details
    assert result.deployment_errors == ()

    illegal = run(Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (0, 1), "RIGHT"),)))
    assert "tile is not buildable" in illegal.deployment_errors[0]


def test_deployment_limit_rejects_third_operator_when_dp_is_available():
    stage = replace(synthetic_stage(), initial_dp=known(20, "synthetic/test", "$.initialDp"))
    strategy = Strategy(
        ("guard", "archer", "rookie"),
        (
            Action(ActionType.DEPLOY, 0.0, "guard", (3, 1)),
            Action(ActionType.DEPLOY, 0.0, "archer", (1, 2), "UP"),
            Action(ActionType.DEPLOY, 0.0, "rookie", (4, 2)),
        ),
    )
    result = run(strategy, stage=stage)
    assert any("deployment limit reached" in error for error in result.deployment_errors)


def test_active_stage_device_blocks_tile_until_removed():
    simulator = Simulator()
    stage = replace(synthetic_stage(), devices=(
        BattleDevice("roadblock#1", "trap_020_roadblock", (3, 1), 8000.0, 200.0, 20.0, -1, True, "ENEMY"),
    ))
    state = SimulationState(0.0, 10.0, 1)
    state.active_devices["roadblock#1"] = RuntimeDevice("roadblock#1", "trap_020_roadblock", (3, 1), 8000.0, 8000.0, 200.0, 20.0, -1)
    strategy = Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),))
    simulator._deploy(state, stage, synthetic_operators(), strategy, strategy.actions[0])
    assert state.deployment_errors == ["guard@0.0: tile is occupied by active stage device"]

    del state.active_devices["roadblock#1"]
    state.deployment_errors.clear()
    simulator._deploy(state, stage, synthetic_operators(), strategy, strategy.actions[0])
    assert state.deployment_errors == ()
    assert state.deployed_operators["guard"].tile == (3, 1)


def test_merchant_maintenance_charges_after_interval_and_stops_on_retreat():
    operator = replace(synthetic_operators()["guard"], maintenance_cost=3.0, maintenance_interval=3.0)
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(100.0, "slug", "main"),), dp_per_second=0.0)
    strategy = Strategy(
        ("guard",),
        (
            Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),
            Action(ActionType.RETREAT, 3.5, "guard"),
        ),
    )
    result = Simulator().run(
        stage=stage, operators={"guard": operator}, enemies=synthetic_enemies(),
        strategy=strategy, config=SimulationConfig(dt=0.01, max_time=4.0),
    )
    charges = [event for event in result.events if event.event_type is EventType.DP_CHANGE]
    assert [(event.time, event.source_id, dict(event.details)["amount"]) for event in charges] == [(3.0, "guard", -3.0)]
    assert abs(result.final_dp - 2.0) < 1e-9
    assert not any(event.event_type is EventType.RETREAT and dict(event.details).get("auto") for event in result.events)


def test_merchant_auto_retreats_when_maintenance_cannot_be_paid():
    guard = synthetic_operators()["guard"]
    stats = replace(guard.phases[0].stats_max, cost=known(0, "synthetic/test", "$.cost"))
    phase = replace(guard.phases[0], stats_min=stats, stats_max=stats)
    operator = replace(guard, phases=(phase,), maintenance_cost=3.0, maintenance_interval=3.0)
    stage = replace(
        synthetic_stage(), spawn_events=(SpawnEvent(100.0, "slug", "main"),), dp_per_second=0.0,
        initial_dp=known(2, "synthetic/test", "$.initialDp"),
    )
    strategy = Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),))
    result = Simulator().run(
        stage=stage, operators={"guard": operator}, enemies=synthetic_enemies(),
        strategy=strategy, config=SimulationConfig(dt=0.01, max_time=4.0),
    )
    retreat = next(event for event in result.events if event.event_type is EventType.RETREAT and dict(event.details).get("auto"))
    assert dict(retreat.details)["auto"] is True
    assert dict(retreat.details)["reason"] == "merchant_upkeep_insufficient"
    assert abs(result.final_dp - 2.0) < 1e-9


def test_synthetic_range_transform_and_target_acquisition():
    strategy = Strategy(("archer",), (Action(ActionType.DEPLOY, 0.0, "archer", (1, 2), "UP"),))
    result = run(strategy)
    attacks = events(result, EventType.ATTACK_START)
    assert attacks
    assert attacks[0].target_id == "slug#0"
    assert attacks[0].time >= 1.5  # The enemy enters the explicitly synthetic UP range after moving.


def test_attack_events_preserve_logical_order_with_instant_projectile():
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(0.0, "slug", "main"),))
    strategy = Strategy(("archer",), (Action(ActionType.DEPLOY, 0.0, "archer", (0, 2), "UP"),))
    result = run(strategy, stage=stage)
    lifecycle = {EventType.DEPLOY, EventType.ATTACK_START, EventType.PROJECTILE_BORN, EventType.PROJECTILE_HIT, EventType.DAMAGE}
    chain = [event.event_type for event in result.events if event.source_id == "archer" and event.event_type in lifecycle]
    assert chain[:4] == [EventType.DEPLOY, EventType.ATTACK_START, EventType.PROJECTILE_BORN, EventType.PROJECTILE_HIT]
    assert EventType.DAMAGE in chain


def test_physical_damage_and_enemy_death_are_deterministic():
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(0.0, "slug", "main"),))
    strategy = Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),))
    result = run(strategy, stage=stage)
    damage = events(result, EventType.DAMAGE)
    assert ("amount", 30.0) in damage[0].details
    assert len(events(result, EventType.ENEMY_DEATH)) == 1
    assert result.enemies_killed == 1


def test_blocking_and_unblocking_follow_enemy_death():
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(0.0, "slug", "main"),))
    strategy = Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),))
    result = run(strategy, stage=stage)
    assert len(events(result, EventType.BLOCK)) == 1
    assert len(events(result, EventType.UNBLOCK)) == 1


def test_leak_reduces_life_when_no_strategy_is_deployed():
    result = run(Strategy((), ()), max_time=20.0)
    assert result.enemies_leaked == 4
    assert result.remaining_life == -1
    assert len(events(result, EventType.ENEMY_LEAK)) == 4


def test_fixed_hand_authored_synthetic_strategy_produces_deterministic_win():
    strategy = Strategy(
        ("guard", "archer"),
        (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"), Action(ActionType.DEPLOY, 0.0, "archer", (1, 2), "UP")),
    )
    first = run(strategy)
    second = run(strategy)
    assert first.win is True
    assert first.enemies_killed == 4
    assert first.enemies_leaked == 0
    assert first == second


class ExecutionPrerequisiteRegressionTests(unittest.TestCase):
    def test_device_occupancy_and_merchant_maintenance(self):
        simulator = Simulator()
        stage = replace(synthetic_stage(), devices=(
            BattleDevice("roadblock#1", "trap_020_roadblock", (3, 1), 8000.0, 200.0, 20.0, -1, True, "ENEMY"),
        ))
        state = SimulationState(0.0, 10.0, 1)
        state.active_devices["roadblock#1"] = RuntimeDevice("roadblock#1", "trap_020_roadblock", (3, 1), 8000.0, 8000.0, 200.0, 20.0, -1)
        strategy = Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),))
        simulator._deploy(state, stage, synthetic_operators(), strategy, strategy.actions[0])
        self.assertEqual(state.deployment_errors, ["guard@0.0: tile is occupied by active stage device"])
        del state.active_devices["roadblock#1"]
        state.deployment_errors.clear()
        simulator._deploy(state, stage, synthetic_operators(), strategy, strategy.actions[0])
        self.assertEqual(state.deployment_errors, [])
        test_merchant_maintenance_charges_after_interval_and_stops_on_retreat()
        test_merchant_auto_retreats_when_maintenance_cannot_be_paid()
