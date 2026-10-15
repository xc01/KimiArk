from __future__ import annotations

from dataclasses import replace

import pytest

from arknights_planner.models.enemy import Enemy, EnemyStats
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.adapters.approximate_real import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.runtime import SPRecoveryMode, SkillEffect, SyntheticSkill
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage
from arknights_planner.simulator.simulator import SimulationConfig, Simulator


_SOURCE = "test/deep-mechanism"


def _enemy(enemy_id: str, *, speed: float = 1.0, block_requirement: int = 1, movement_mode: str = "WALK") -> Enemy:
    stats = EnemyStats(
        max_hp=known(100, _SOURCE, f"{enemy_id}.hp"),
        atk=known(0, _SOURCE, f"{enemy_id}.atk"),
        defense=known(0, _SOURCE, f"{enemy_id}.def"),
        magic_resistance=known(0, _SOURCE, f"{enemy_id}.res"),
        move_speed=known(speed, _SOURCE, f"{enemy_id}.speed"),
        attack_interval=known(10, _SOURCE, f"{enemy_id}.interval"),
        weight=known(0, _SOURCE, f"{enemy_id}.weight"),
        life_point_reduce=known(1, _SOURCE, f"{enemy_id}.life"),
        block_requirement=known(block_requirement, _SOURCE, f"{enemy_id}.blockRequirement"),
        movement_mode=known(movement_mode, _SOURCE, f"{enemy_id}.motion"),
    )
    return Enemy(enemy_id, known(enemy_id, _SOURCE, f"{enemy_id}.name"), stats, _SOURCE)


def _run(stage, operators, enemies, strategy, *, max_time=20.0):
    return Simulator().run(
        stage=stage, operators=operators, enemies=enemies, strategy=strategy,
        config=SimulationConfig(dt=0.1, max_time=max_time),
    )


def test_stage_move_multiplier_is_applied_once():
    stage = replace(
        synthetic_stage(),
        move_multiplier=known(0.5, _SOURCE, "$.options.moveMultiplier"),
        spawn_events=(SpawnEvent(1.0, "slug", "main"),),
    )
    result = _run(stage, synthetic_operators(), synthetic_enemies(), Strategy((), ()))
    leak = next(event for event in result.events if event.event_type.name == "ENEMY_LEAK")
    assert leak.time == pytest.approx(13.0, abs=0.2)


def test_stage_max_dp_caps_regeneration_and_skill_gain():
    stage = replace(
        synthetic_stage(),
        max_dp=known(12.0, _SOURCE, "$.options.maxCost"),
        dp_per_second=2.0,
        spawn_events=(SpawnEvent(100.0, "slug", "main"),),
    )
    result = _run(stage, synthetic_operators(), synthetic_enemies(), Strategy((), ()), max_time=2.0)
    assert result.final_dp == pytest.approx(12.0)


def test_manual_retreat_refunds_half_deployment_cost():
    stage = replace(
        synthetic_stage(),
        spawn_events=(SpawnEvent(100.0, "slug", "main"),),
        dp_per_second=0.0,
    )
    strategy = Strategy(
        ("guard",),
        (
            Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),
            Action(ActionType.RETREAT, 1.0, "guard"),
        ),
    )
    result = _run(stage, synthetic_operators(), synthetic_enemies(), strategy, max_time=2.0)
    refunds = [
        event for event in result.events
        if event.event_type.name == "DP_CHANGE" and dict(event.details).get("reason") == "retreat_refund"
    ]
    assert [(event.time, dict(event.details)["amount"]) for event in refunds] == [(1.0, 2.0)]


def test_one_star_operator_does_not_occupy_deployment_limit():
    stage = replace(
        synthetic_stage(),
        deployment_limit=known(1, _SOURCE, "$.options.characterLimit"),
        initial_dp=known(20, _SOURCE, "$.options.initialCost"),
        spawn_events=(SpawnEvent(100.0, "slug", "main"),),
        dp_per_second=0.0,
    )
    three_star = replace(synthetic_operators()["guard"], star_rarity=known(3, _SOURCE, "$.rarity"))
    strategy = Strategy(
        ("guard", "rookie"),
        (
            Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),
            Action(ActionType.DEPLOY, 0.0, "rookie", (2, 1), "RIGHT"),
        ),
    )
    result = _run(stage, {"guard": three_star, **synthetic_operators()}, synthetic_enemies(), strategy, max_time=0.1)
    deploys = [event for event in result.events if event.event_type.name == "DEPLOY"]
    assert [(event.source_id, dict(event.details)["legal"]) for event in deploys] == [("guard", True), ("rookie", True)]


def test_two_one_star_operators_do_not_exhaust_normal_deployment_limit():
    stage = replace(
        synthetic_stage(),
        deployment_limit=known(1, _SOURCE, "$.options.characterLimit"),
        initial_dp=known(20, _SOURCE, "$.options.initialCost"),
        spawn_events=(SpawnEvent(100.0, "slug", "main"),),
        dp_per_second=0.0,
    )
    three_star = replace(synthetic_operators()["guard"], star_rarity=known(3, _SOURCE, "$.rarity"))
    strategy = Strategy(
        ("rookie", "archer", "guard"),
        (
            Action(ActionType.DEPLOY, 0.0, "rookie", (2, 1), "RIGHT"),
            Action(ActionType.DEPLOY, 0.0, "archer", (1, 2), "UP"),
            Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),
        ),
    )
    result = _run(stage, {**synthetic_operators(), "guard": three_star}, synthetic_enemies(), strategy, max_time=0.1)
    deploys = [event for event in result.events if event.event_type.name == "DEPLOY"]
    assert [(event.source_id, dict(event.details)["legal"]) for event in deploys] == [
        ("rookie", True), ("archer", True), ("guard", True),
    ]


def test_redeployment_uses_fresh_sp_generation():
    skill = SyntheticSkill(
        "test-skill", initial_sp=0.0, sp_cost=2.0, recovery_mode=SPRecoveryMode.TIME,
        sp_per_second=1.0, duration=1.0, effect=SkillEffect(),
    )
    operator = replace(synthetic_operators()["guard"], synthetic_skill=skill, redeploy_time=known(0.2, _SOURCE, "$.redeploy"))
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(100.0, "slug", "main"),), dp_per_second=0.0)
    strategy = Strategy(
        ("guard",),
        (
            Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),
            Action(ActionType.RETREAT, 1.0, "guard"),
            Action(ActionType.DEPLOY, 1.3, "guard", (3, 1), "RIGHT"),
        ),
    )
    result = _run(stage, {"guard": operator}, synthetic_enemies(), strategy, max_time=2.0)
    assert result.final_dp == pytest.approx(2.0)


def test_two_block_requirement_requires_block_capacity_but_occupies_one_slot():
    enemy = _enemy("heavy", block_requirement=2)
    operator_stats = replace(synthetic_operators()["guard"].phases[0].stats_max, block_count=known(2, _SOURCE, "$.block"))
    operator = replace(synthetic_operators()["guard"], phases=(replace(synthetic_operators()["guard"].phases[0], stats_min=operator_stats, stats_max=operator_stats),))
    stage = replace(
        synthetic_stage(),
        spawn_events=(SpawnEvent(1.0, "heavy", "main"), SpawnEvent(1.0, "heavy", "main")),
        dp_per_second=0.0,
    )
    result = _run(stage, {"guard": operator}, {"heavy": enemy}, Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),)), max_time=5.0)
    blocks = [event for event in result.events if event.event_type.name == "BLOCK"]
    assert [event.target_id for event in blocks] == ["heavy#0", "heavy#1"]


def test_roadblock_radius_blocks_civilian_off_center():
    from arknights_planner.models.stage import BattleDevice
    civilian = _enemy("civilian")
    civilian = replace(
        civilian,
        stats=replace(civilian.stats, is_neutral=known(True, _SOURCE, "$.isNeutral")),
    )

    stage = replace(
        synthetic_stage(),
        routes=(Route("main", (Waypoint(0, 1), Waypoint(3, 2))),),
        spawn_events=(SpawnEvent(0.0, "civilian", "main"),),
        dp_per_second=0.0,
    )
    strategy = Strategy((), ())
    result = _run(stage, synthetic_operators(), {"civilian": civilian}, strategy, max_time=10.0)
    blocks = [event for event in result.events if event.event_type.name == "BLOCK" and event.source_id == "roadblock#0"]
    assert not blocks

    with_device = replace(
        stage,
        devices=(BattleDevice("roadblock#0", "trap_020_roadblock", (2, 2), 8000.0, 0.0, 0.0, -1, True),),
    )
    result = _run(with_device, synthetic_operators(), {"civilian": civilian}, strategy, max_time=10.0)
    blocks = [event for event in result.events if event.event_type.name == "BLOCK" and event.source_id == "roadblock#0"]
    assert len(blocks) == 1
    assert not [event for event in result.events if event.event_type.name == "ENEMY_LEAK"]
    assert dict(blocks[0].details)["blocking_radius"] == pytest.approx(0.4472)


def test_melee_cannot_attack_flying_but_ranged_can():
    enemy = _enemy("drone", movement_mode="FLY")
    stage = replace(
        synthetic_stage(),
        spawn_events=(SpawnEvent(1.0, "drone", "main"),),
        dp_per_second=0.0,
    )
    melee = Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),))
    melee_result = _run(stage, synthetic_operators(), {"drone": enemy}, melee, max_time=2.0)
    assert not any(event.event_type.name == "DAMAGE" for event in melee_result.events)

    ranged = Strategy(("archer",), (Action(ActionType.DEPLOY, 0.0, "archer", (1, 2), "UP"),))
    ranged_result = _run(stage, synthetic_operators(), {"drone": enemy}, ranged, max_time=2.0)
    assert any(event.event_type.name == "DAMAGE" for event in ranged_result.events)


def test_r8_3_5_6_special_routes_are_structurally_executable():
    adapter = GameDataRepository("data/ArknightsGameData")
    fixture_builder = ApproximateRealSimulationAdapter(adapter)
    for stage_id, hidden_count in (("R8-3", 2), ("R8-5", 3), ("R8-6", 0)):
        fixture = fixture_builder.build_pool_fixture(
            stage_id_or_code=stage_id, configurations=(),
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        )
        hidden_midpoints = 0
        for route in fixture.stage.routes:
            for start, end in route.hidden_spans:
                assert route.hidden_at(start)
                assert route.hidden_at(end)
                assert route.hidden_at((start + end) / 2)
                hidden_midpoints += 1
        assert hidden_midpoints == hidden_count
