from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION, artifact_mechanics_status
from arknights_planner.mechanics_registry import MechanicsEvidence, MechanicsEvidenceRegistry
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.simulation import RuntimeDevice, RuntimeEnemy, RuntimeOperator, SimulationState
from arknights_planner.models.stage import BattleDevice
from arknights_planner.search.m15 import FailureFrontier, FailureType, TacticalConstraint
from arknights_planner.search.m17_causal_temporal import CausalTemporalConstraint
from arknights_planner.search.m23_calibration import M23CalibrationPacket
from arknights_planner.search.scope import ExperimentScope
from arknights_planner.search.top_down import TopDownPlanner
from arknights_planner.simulator import Simulator
from arknights_planner.simulator.synthetic import runtime_stage


ROOT = Path(__file__).resolve().parents[1]


def runtime_enemy(instance_id: str, *, route_id: str, distance: float, spawn_index: int) -> RuntimeEnemy:
    return RuntimeEnemy(
        instance_id=instance_id,
        enemy_id=instance_id.split("#", 1)[0],
        route_id=route_id,
        hp=100.0,
        speed=1.0,
        life_point_reduce=1,
        distance=distance,
        spawn_index=spawn_index,
    )


def runtime_operator(*, position: str = "MELEE", attack_range=((0, 0),), blocked=()) -> RuntimeOperator:
    return RuntimeOperator(
        operator_id="operator",
        tile=(3, 1),
        direction="RIGHT",
        hp=100.0,
        max_hp=100.0,
        base_atk=10.0,
        base_block_count=1,
        base_attack_interval=1.0,
        base_attack_range=attack_range,
        defense=0.0,
        magic_resistance=0.0,
        combat_output="DAMAGE",
        redeploy_time=1.0,
        position=position,
        blocked_enemy_ids=list(blocked),
    )

def test_q1_unique_path_distance_is_contextually_resolved_and_not_unknown():
    registry = MechanicsEvidenceRegistry(ROOT)
    gate = registry.unknown_gate(
        "Q1",
        {"candidate_remaining_route_distances": [3.0, 5.0], "has_taunt_or_special_filter": False},
        topic="targeting",
        terms=("remaining", "path", "stable"),
    )
    assert gate["unknown_status"] == "KNOWN"
    assert gate["concrete_context_resolved"] is True
    assert gate["unknown_declaration_valid"] is False
    assert gate["evidence_retrieval_performed"] is True


def test_q2_cached_sandbox_evidence_resolves_ordinary_melee_blocked_priority():
    registry = MechanicsEvidenceRegistry(ROOT)
    gate = registry.unknown_gate(
        "Q2",
        {"operator_position": "MELEE", "blocked_candidate_ids": ["blocked#0"]},
        topic="targeting",
        terms=("blocked", "melee"),
    )
    assert gate["unknown_status"] == "KNOWN"
    assert gate["unknown_declaration_valid"] is False
    assert any(hit["subtopic"] == "blocked_priority" for hit in gate["hits"])


def test_q3_remains_unknown_only_after_evidence_retrieval():
    registry = MechanicsEvidenceRegistry(ROOT)
    gate = registry.unknown_gate(
        "Q3",
        {"lifecycle": "RETARGET_AFTER_TARGET_DISAPPEARANCE"},
        topic="targeting",
        terms=("retarget", "attack", "lock"),
    )
    assert gate["unknown_status"] == "UNKNOWN"
    assert gate["unknown_declaration_valid"] is True
    assert gate["evidence_retrieval_performed"] is True
    assert any(hit["subtopic"] == "retarget_timing" for hit in gate["hits"])


def test_unsupported_mechanic_can_be_unknown_after_retrieval():
    registry = MechanicsEvidenceRegistry(ROOT)
    gate = registry.unknown_gate("displacement force", {"mechanic": "force"}, topic="displacement", terms=("force",))
    assert gate["hit_count"] == 0
    assert gate["unknown_status"] == "NO_APPLICABLE_EVIDENCE"
    assert gate["unknown_declaration_valid"] is True


def test_conflicting_evidence_remains_explicit_and_blocks_unknown():
    conflict = MechanicsEvidence(
        "test_conflict", "synthetic", "conflicting claim", "synthetic test", "SYNTHETIC_TEST",
        "tests/test_architecture.py", "deterministic regression", "HIGH", "UNKNOWN",
        ["conflicts with baseline claim"], {}, ACTIVE_MECHANICS_VERSION,
    )
    registry = MechanicsEvidenceRegistry(ROOT, extra_entries=(conflict,))
    gate = registry.unknown_gate("conflicting claim", {}, topic="test_conflict", terms=("conflicting",))
    assert gate["conflicts"]
    assert gate["unknown_declaration_valid"] is False


def test_mechanics_version_dependency_marks_old_artifacts_stale():
    assert artifact_mechanics_status(ACTIVE_MECHANICS_VERSION) == "CURRENT"
    assert artifact_mechanics_status("m18.1-target-distance-v2") == "STALE_REQUIRES_DETERMINISTIC_REPLAY"
    assert artifact_mechanics_status("never-recorded") == "UNKNOWN_VERSION_TREAT_AS_STALE"


def test_experiment_scope_makes_benchmark_bounds_non_global():
    scope = ExperimentScope.main_6_8_low_rarity(operator_pool=("a", "b"), max_cardinality=2, simulation_budget=3)
    conclusion = scope.conclusion_scope()
    assert scope.stage_id == "6-8"
    assert scope.max_cardinality == 2
    assert conclusion["global_claim_valid"] is False
    assert scope.pool_policy == "BENCHMARK_LOW_RARITY_1_3_STAR"


def test_melee_operator_prioritizes_self_blocked_enemy_even_outside_range():
    stage = replace(runtime_stage(), routes=(Route("blocked", (Waypoint(0, 1), Waypoint(6, 1))),))
    state = SimulationState(time=0.0, dp=10.0, remaining_life=1)
    state.active_enemies["blocked#0"] = runtime_enemy("blocked#0", route_id="blocked", distance=4.0, spawn_index=0)
    state.active_enemies["near#1"] = runtime_enemy("near#1", route_id="blocked", distance=3.0, spawn_index=1)
    operator = runtime_operator(attack_range=((0, 0),), blocked=("blocked#0",))
    selected = Simulator()._target_enemy_for(stage, state, operator)
    assert selected.instance_id == "blocked#0"
    details = dict(state.events[-1].details)
    assert details["rule"] == "SELF_BLOCKED_FIRST_THEN_REMAINING_PATH_DISTANCE_THEN_CREATION_ORDER"
    assert details["blocked_candidate_ids"] == ("blocked#0",)


def test_looping_route_uses_remaining_path_not_euclidean_exit_distance():
    route = Route("loop", (Waypoint(0, 1), Waypoint(1, 1), Waypoint(1, 3), Waypoint(0, 3), Waypoint(0, 1)))
    stage = replace(runtime_stage(), routes=(route,))
    state = SimulationState(time=0.0, dp=10.0, remaining_life=1)
    state.active_enemies["near-exit#0"] = runtime_enemy("near-exit#0", route_id="loop", distance=1.0, spawn_index=0)
    state.active_enemies["shorter-remaining#1"] = runtime_enemy("shorter-remaining#1", route_id="loop", distance=2.0, spawn_index=1)
    operator = runtime_operator(attack_range=((0, 0), (0, 1)))
    operator = replace(operator, tile=(1, 1))
    selected = Simulator()._target_enemy_for(stage, state, operator)
    assert selected.instance_id == "shorter-remaining#1"


def test_equal_remaining_path_uses_stable_creation_order():
    route = Route("main", (Waypoint(0, 1), Waypoint(6, 1)))
    stage = replace(runtime_stage(), routes=(route,))
    state = SimulationState(time=0.0, dp=10.0, remaining_life=1)
    state.active_enemies["later-created#1"] = runtime_enemy("later-created#1", route_id="main", distance=2.0, spawn_index=1)
    state.active_enemies["earlier-created#0"] = runtime_enemy("earlier-created#0", route_id="main", distance=2.0, spawn_index=0)
    selected = Simulator()._target_enemy_for(stage, state, runtime_operator(attack_range=((0, 0), (-1, 0))))
    assert selected.instance_id == "earlier-created#0"


def test_device_targeting_does_not_displace_enemy_targets():
    stage = replace(
        runtime_stage(),
        devices=(BattleDevice("device#0", "trap_020_roadblock", (3, 1), 8000.0, 200.0, 20.0, -1, True, "ENEMY"),),
    )
    state = SimulationState(time=0.0, dp=10.0, remaining_life=1)
    state.active_devices[stage.devices[0].device_id] = RuntimeDevice(
        stage.devices[0].device_id, stage.devices[0].template_id, stage.devices[0].tile,
        stage.devices[0].hp, stage.devices[0].hp, stage.devices[0].defense,
        stage.devices[0].magic_resistance, stage.devices[0].taunt_level,
    )
    state.active_enemies["enemy#0"] = runtime_enemy("enemy#0", route_id="main", distance=5.0, spawn_index=0)
    operator = runtime_operator(attack_range=((0, 0),))
    selected = Simulator()._target_device_for(state, operator)
    assert selected is None


def test_device_is_targeted_when_no_enemy_is_available_and_is_destroyed():
    stage = replace(
        runtime_stage(),
        devices=(BattleDevice("device#1", "trap_020_roadblock", (3, 1), 35.0, 200.0, 20.0, -1, True, "ENEMY"),),
    )
    state = SimulationState(time=0.0, dp=10.0, remaining_life=1)
    state.active_devices[stage.devices[0].device_id] = RuntimeDevice(
        stage.devices[0].device_id, stage.devices[0].template_id, stage.devices[0].tile,
        stage.devices[0].hp, stage.devices[0].hp, stage.devices[0].defense,
        stage.devices[0].magic_resistance, stage.devices[0].taunt_level,
    )
    operator = runtime_operator(attack_range=((0, 0),))
    selected = Simulator()._target_device_for(state, operator)
    assert selected.device_id == "device#1"
    assert selected.hp == 35.0


def test_core_repair_abstractions_accept_non_6_8_synthetic_context():
    frontier = FailureFrontier(12, FailureType.EARLY_LEAK, ("alpha",), ("enemy-a",), (), ((1, 2),), ("BLOCK",), "DP_OK", 2, ("synthetic",), "HIGH")
    constraint = TacticalConstraint("C1", "COVER", ("alpha",), 12, ("BLOCK",), ((1, 2),), True, "SYNTHETIC", ("synthetic",))
    causal = CausalTemporalConstraint("CT1", "enemy-a", "alpha", {"latest_required_frame": 12}, "DO_NOT_LEAK", {}, {}, {}, [], "SYNTHETIC", "HIGH")
    assert "6-8" not in str(asdict(frontier) | asdict(constraint) | asdict(causal))


def test_top_down_smoke_wires_external_timeline_within_scope():
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    scope = ExperimentScope.main_0_1_smoke(
        operator_pool=("char_122_beagle", "char_124_kroos"),
        max_cardinality=2,
        simulation_budget=24,
    )
    result = TopDownPlanner(
        adapter=adapter,
        policy=RealSimulationApproximationPolicy.main_00_01(),
        scope=scope,
    ).run()
    assert result["pipeline"][:2] == ["GameData", "GameUnderstanding"]
    assert result["stage_understanding"]["provenance"]["routes"]
    assert result["tactical_requirements"][0]["provenance"]
    assert result["operator_assignment"]["provenance"]
    assert result["mechanics_gates"]["registry_used_in_runtime_path"] is True
    assert result["llm_calls"] == 0
    assert result["causal_repair_role"] == "SUPPORTING_LAYER"
    assert result["search"]["budget_respected"] is True
    for action in result["external_timeline"]["actions"]:
        assert action["type"] in {"DEPLOY", "ACTIVATE_SKILL", "RETREAT"}
        if action["type"] == "DEPLOY":
            assert action["tile"] is not None and action["direction"] is not None


def test_m23_does_not_request_human_calibration_when_gate_fails():
    report = M23CalibrationPacket(ROOT).run()
    assert report["m23_calibration_questions"]["questions"] == []
    assert report["m23_results"]["HUMAN_CALIBRATION_REQUIRED"] is False
    assert "NO_HUMAN_CALIBRATION_REQUIRED" in M23CalibrationPacket(ROOT).instructions()
