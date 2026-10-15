from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from dataclasses import replace

import pytest

from compile_r8_1_lowstar_c2_plan_v1 import build_dp_ledger

from arknights_planner.models.enemy import Enemy, EnemyAbility, EnemyStats
from arknights_planner.models.stage import BattleDevice
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.adapters.approximate_real import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.runtime import SPRecoveryMode, SkillEffect, SyntheticSkill
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage
from arknights_planner.simulator.simulator import SimulationConfig, Simulator
from tests.simulator.test_neutral_protected_target import _neutral


_SOURCE = "test/deep-mechanism"
ROOT = Path(__file__).resolve().parents[2]


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


def test_roadblock_restraint_and_block_radii_are_distinct():
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
    assert dict(blocks[0].details)["blocking_radius"] == pytest.approx(0.6)
    assert dict(blocks[0].details)["rule"] == "PRTS_ROADBLOCK_PROTECTED_RESTRAINT_RADIUS_0_6"

    ordinary = _enemy("walker")
    ordinary_stage = replace(
        synthetic_stage(),
        routes=(Route("main", (Waypoint(0, 1), Waypoint(3, 2))),),
        spawn_events=(SpawnEvent(0.0, "walker", "main"),),
        dp_per_second=0.0,
    )
    ordinary_result = _run(ordinary_stage, synthetic_operators(), {"walker": ordinary}, strategy, max_time=10.0)
    ordinary_blocks = [event for event in ordinary_result.events if event.event_type.name == "BLOCK"]
    assert not ordinary_blocks


def test_blocking_windows_use_unclamped_line_projection_and_clip_to_segment():
    route = Route("main", (Waypoint(0, 0), Waypoint(1, 0)))
    assert route.blocking_windows((1.3, 0), radius=0.4472) == ((0.8528, 1.0),)
    assert route.blocking_windows((-0.3, 0), radius=0.4472) == ((0.0, 0.1472),)
    assert route.blocking_windows((0.5, 0.4472), radius=0.4472) == ((0.5, 0.5),)
    assert route.blocking_windows((0.5, 0.5), radius=0.4472) == ()


def test_blocking_windows_handle_zero_length_and_repeated_segments():
    route = Route(
        "main",
        (Waypoint(0, 0), Waypoint(0, 0), Waypoint(1, 0), Waypoint(0, 0), Waypoint(1, 0)),
    )
    windows = route.blocking_windows((1.3, 0), radius=0.4472)
    assert len(windows) == 2
    assert windows[0][0] == pytest.approx(0.8528)
    assert windows[0][1] == pytest.approx(1.1472)
    assert windows[1][0] == pytest.approx(2.8528)
    assert windows[1][1] == pytest.approx(3.0)


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


def test_static_dp_ledger_uses_deployment_generations_for_sp():
    input_dir = Path("/tmp/kimiark-dp-ledger-v12-regression")
    input_dir.mkdir(exist_ok=True)
    (input_dir / "llm_evidence_context.json").write_text(json.dumps({
        "stage_options": {"initial_cost": 20, "max_cost": 99, "deployment_limit": 8},
    }), encoding="utf-8")
    catalog = {"feater": {
        "identity": {"rarity": 2},
        "stats": {"cost": 18},
        "selected_skills": [{"skill_id": "s", "initial_sp": 20, "sp_cost": 30,
                             "duration": 10, "blackboard": {"cost": 6}}],
    }}
    plan = {"action_timeline": [
        {"action_type": "DEPLOY", "operator_id": "feater", "frame": 2418},
        {"action_type": "ACTIVATE_SKILL", "operator_id": "feater", "frame": 2721},
        {"action_type": "RETREAT", "operator_id": "feater", "frame": 3375},
        {"action_type": "DEPLOY", "operator_id": "feater", "frame": 5478},
        {"action_type": "ACTIVATE_SKILL", "operator_id": "feater", "frame": 5490},
    ]}
    ledger = build_dp_ledger(plan, catalog, {"feater": {}}, input_dir)
    first = ledger["skill_readiness"]["feater@2721"]
    second = ledger["skill_readiness"]["feater@5490"]
    assert first["status"] == "PASS_WITH_CONDITIONS" and first["generation"] == 1
    assert second["status"] == "CONFLICT" and second["reason"] == "SP_NOT_READY"
    assert second["generation"] == 2
    assert second["available_sp_model"] == pytest.approx(20.4)
    assert next(row for row in ledger["entries"] if row["event"] == "RETREAT_REFUND")["delta"] == 9


def test_compiler_cli_entry_reads_optional_input_directory(tmp_path):
    (tmp_path / "llm_evidence_context.json").write_text(json.dumps({
        "stage_options": {"initial_cost": 10, "max_cost": 99, "deployment_limit": 8},
        "stage_active_facts": {
            "roadblock_tiles_col_row": [],
            "deployable_ground_tiles_col_row": [],
            "deployable_high_ground_tiles_col_row": [],
        },
        "normal_low_star_catalog": [],
    }), encoding="utf-8")
    (tmp_path / "llm_structured_output.json").write_text(json.dumps({
        "revised_operational_plans": [{
            "operational_plan_id": "cli-entry-regression",
            "action_timeline": [{"action_type": "RETREAT", "operator_id": "x", "frame": 0}],
        }],
    }), encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(["src", "scripts", environment.get("PYTHONPATH", "")])
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/compile_r8_1_lowstar_c2_plan_v1.py"), str(tmp_path)],
        cwd=ROOT, env=environment, check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "static_compile_final_status.json").exists()


def test_zero_duration_auto_skill_does_not_lose_a_tick_between_cycles():
    from arknights_planner.models.runtime import SkillEffect, SyntheticSkill
    skill = SyntheticSkill(
        "zero_dp", initial_sp=1.0, sp_cost=2.0, recovery_mode=SPRecoveryMode.TIME,
        sp_per_second=1.0, duration=0.0,
        effect=SkillEffect(dp_immediate=3.0), auto_activate=True,
    )
    operator = replace(synthetic_operators()["archer"], synthetic_skill=skill)
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(100.0, "slug", "main"),), dp_per_second=0.0)
    result = _run(stage, {"dp": operator}, synthetic_enemies(), Strategy(("dp",), (Action(ActionType.DEPLOY, 0.0, "dp", (1, 2), "UP"),)), max_time=6.0)
    incomes = [
        event.time for event in result.events
        if event.event_type.name == "DP_CHANGE" and dict(event.details).get("reason") == "skill_activation"
    ]
    assert incomes == [1.0, 3.0, 5.0]


def test_emp_point_locks_protected_target_and_hits_area_after_delay():
    artillery = replace(_enemy("enemy_1112_emppnt", movement_mode="FLY"), abilities=(
        EnemyAbility("artillery", "DELAYED_LOCKED_AREA_ATTACK", 5.0, 0.0, 1.2, 1.0,
                     damage_type="PHYSICAL", delay_seconds=3.0, protected_target_priority=True),
    ))
    artillery = replace(artillery, stats=replace(artillery.stats, atk=known(50, _SOURCE, "artillery.atk")))
    civilian = replace(_neutral(), stats=replace(_neutral().stats, move_speed=known(0.0, _SOURCE, "civilian.speed")))
    stage = replace(
        synthetic_stage(),
        spawn_events=(SpawnEvent(0.0, "enemy_1112_emppnt", "main"), SpawnEvent(0.0, "civilian", "main")),
        dp_per_second=0.0,
    )
    strategy = Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"),))
    result = _run(stage, synthetic_operators(), {"enemy_1112_emppnt": artillery, "civilian": civilian}, strategy, max_time=4.0)
    starts = [event for event in result.events if event.event_type.name == "ENEMY_ABILITY_START"]
    hits = [event for event in result.events if event.event_type.name == "DAMAGE"]
    assert len(starts) == 1 and dict(starts[0].details)["delay"] == 3.0
    assert len(hits) == 1 and hits[0].time == pytest.approx(3.0)


def test_friendly_ice_and_altar_devices_execute_source_skills():
    stage = replace(
        synthetic_stage(),
        spawn_events=(SpawnEvent(0.0, "slug", "main"),),
        dp_per_second=0.0,
        devices=(
            BattleDevice("ice", "trap_022_frosts_friend", (1, 1), 100.0, 0.0, 0.0, 0, False, "FRIENDLY"),
            BattleDevice("altar", "trap_023_ore_friend", (1, 1), 100.0, 0.0, 0.0, 0, False, "FRIENDLY"),
        ),
    )
    slug = replace(synthetic_enemies()["slug"], stats=replace(synthetic_enemies()["slug"].stats, move_speed=known(0.05, _SOURCE, "$.speed")))
    result = _run(stage, synthetic_operators(), {"slug": slug}, Strategy((), ()), max_time=15.1)
    assert any(event.event_type.name == "ENEMY_STATUS_HIT" and event.source_id == "ice" for event in result.events)
    assert any(event.event_type.name == "ENEMY_DEATH" and event.source_id == "altar" for event in result.events)
