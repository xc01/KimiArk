from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealOperatorConfiguration,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.strategy import Strategy
from arknights_planner.search.operator_assignment import OperatorAssignmentEngine
from arknights_planner.search.scope import ExperimentScope
from arknights_planner.search.stage_understanding import (
    StageUnderstandingAnalyzer,
    derive_tactical_requirements,
)
from arknights_planner.search.top_down import DeterministicHypothesisGenerator, TopDownPlanner
from arknights_planner.search.top_down_validation import TopDownValidation


ROOT = Path(__file__).resolve().parents[1]


def fixture_0_1():
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    return adapter.build_pool_fixture(
        stage_id_or_code="0-1",
        configurations=(
            RealOperatorConfiguration("char_122_beagle", 0, 40),
            RealOperatorConfiguration("char_124_kroos", 0, 40),
        ),
        policy=RealSimulationApproximationPolicy.main_00_01(),
    )


def test_stage_understanding_uses_only_spawn_timeline_routes():
    fixture = fixture_0_1()
    inactive_route = Route("inactive-test-route", (Waypoint(99.0, 99.0), Waypoint(98.0, 99.0)))
    fixture = SimpleNamespace(
        stage=replace(fixture.stage, routes=(*fixture.stage.routes, inactive_route)),
        spawn_timeline=fixture.spawn_timeline,
        operators=fixture.operators,
        enemies=fixture.enemies,
        approximations_used=fixture.approximations_used,
    )
    understanding = StageUnderstandingAnalyzer().analyze(fixture)
    active_route_ids = {spawn.route_id for spawn in fixture.spawn_timeline}
    assert {route.route_id for route in understanding.routes} == active_route_ids
    assert "inactive-test-route" not in {route.route_id for route in understanding.routes}


def test_stage_understanding_preserves_derivation_provenance():
    understanding = StageUnderstandingAnalyzer().analyze(fixture_0_1())
    assert understanding.provenance
    assert all(value for value in understanding.provenance.values())
    assert understanding.aerial_threat_status == "UNKNOWN_NOT_REPRESENTED_IN_CURRENT_GAME_DATA_MODEL"
    assert understanding.approximations


def test_tactical_requirements_are_grounded_and_hypothesized():
    fixture = fixture_0_1()
    understanding = StageUnderstandingAnalyzer().analyze(fixture)
    requirements = derive_tactical_requirements(understanding)
    assert requirements
    for requirement in requirements:
        assert requirement.evidence
        assert requirement.pressure_window
        assert requirement.affected_routes
        assert requirement.hardness in {"HARD", "SOFT", "HYPOTHESIZED"}
        assert 0.0 <= requirement.confidence <= 1.0
        assert requirement.capability
        assert requirement.provenance


def test_operator_assignment_is_capability_based_and_source_backed():
    fixture = fixture_0_1()
    understanding = StageUnderstandingAnalyzer().analyze(fixture)
    requirements = derive_tactical_requirements(understanding)
    assignment = OperatorAssignmentEngine().assign(
        understanding,
        requirements,
        fixture.operators,
        max_cardinality=3,
    )
    assert assignment.provenance
    assert assignment.capability_evidence
    assert assignment.assignments
    for row in assignment.assignments:
        assert all(candidate.evidence for candidate in row.candidates)
        if row.selected_operator_id is not None:
            assert row.candidates
            assert row.selected_operator_id in {candidate.operator_id for candidate in row.candidates}

    block_row = next(row for row in assignment.assignments if row.capability == "BLOCK")
    assert block_row.selected_operator_id is not None
    blocker = fixture.operators[block_row.selected_operator_id]
    assert blocker.position.value == "MELEE"
    assert (blocker.phases[0].stats_max.block_count.value or 0) > 0

    source = (ROOT / "src/arknights_planner/search/operator_assignment.py").read_text(encoding="utf-8")
    assert "char_" not in source


def test_plan_hypotheses_respond_to_stage_structure():
    generator = DeterministicHypothesisGenerator()
    base_context = {
        "stage_understanding": {
            "blocking_pressure": {"lane_count": 1},
            "coverage_opportunities": (),
        },
        "operator_assignment": {
            "preferred_operator_ids": ("blocker", "ranged"),
            "deployment_order": ("blocker", "ranged"),
            "assignments": (
                {"capability": "BLOCK", "selected_operator_id": "blocker", "candidates": ()},
                {"capability": "RANGED_DPS", "selected_operator_id": "ranged", "candidates": ()},
            ),
        },
    }
    single_lane = generator.generate_hypotheses(base_context, max_hypotheses=1)
    assert single_lane[0].tactical_archetype == "SINGLE_CHOKE_HOLD"

    multi_lane_context = {
        **base_context,
        "stage_understanding": {
            "blocking_pressure": {"lane_count": 2},
            "coverage_opportunities": ({"tile": (1, 1), "tile_kind": "HIGH_GROUND", "route_ids": ("a", "b"), "shared": True},),
        },
    }
    multi_lane = generator.generate_hypotheses(multi_lane_context, max_hypotheses=4)
    archetypes = {hypothesis.tactical_archetype for hypothesis in multi_lane}
    assert "DUAL_LANE_HOLD" in archetypes
    assert "SHARED_HIGH_GROUND_COVERAGE" in archetypes


def test_top_down_runtime_integrates_mechanics_gates():
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
    assert result["mechanics_gates"]["registry_used_in_runtime_path"] is True
    assert result["mechanics_gates"]["unknown_gate_used"] is True
    assert result["mechanics_gates"]["mechanics_work_gate_used"] is True
    assert result["mechanics_gates"]["human_calibration_gate_used"] is True
    assert result["mechanics_gates"]["result"] == "NO_MECHANICS_WORK_REQUIRED"
    assert result["mechanics_gates"]["human_calibration_result"] == "NO_HUMAN_CALIBRATION_REQUIRED"
    assert result["llm_calls"] == 0


def test_failure_revision_prefers_high_level_layers_over_local_repair():
    fixture = fixture_0_1()
    understanding = StageUnderstandingAnalyzer().analyze(fixture)
    requirements = derive_tactical_requirements(understanding)
    assignment = OperatorAssignmentEngine().assign(
        understanding,
        requirements,
        fixture.operators,
        max_cardinality=3,
    )
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    planner = TopDownPlanner(
        adapter=ApproximateRealSimulationAdapter(repository),
        policy=RealSimulationApproximationPolicy.main_00_01(),
        scope=ExperimentScope.main_0_1_smoke(
            operator_pool=("char_122_beagle", "char_124_kroos"),
            max_cardinality=2,
            simulation_budget=24,
        ),
    )
    failed_result = SimpleNamespace(
        events=(),
        deployment_errors=(),
        operator_deaths=2,
        enemies_killed=0,
        enemies_remaining=0,
    )
    diagnosis = planner._failure_diagnosis(
        failed_result,
        understanding,
        assignment,
        Strategy(assignment.preferred_operator_ids, ()),
        fixture.operators,
    )
    assert diagnosis["primary_layer"] == "OPERATOR_ASSIGNMENT_ISSUE"
    assert diagnosis["high_level_revision_before_local_repair"] is True
    assert diagnosis["local_repair_eligible"] is False


def test_generic_planner_modules_do_not_embed_6_8_literals():
    modules = (
        "src/arknights_planner/search/stage_understanding.py",
        "src/arknights_planner/search/operator_assignment.py",
        "src/arknights_planner/search/top_down.py",
    )
    forbidden = ("6-8", "route-2", "564", "Falco", "Kroos", "Noir Corne", "char_192_falco", "char_124_kroos", "char_500_noirc")
    for module in modules:
        source = (ROOT / module).read_text(encoding="utf-8")
        for literal in forbidden:
            assert literal not in source, f"{literal} leaked into {module}"


def test_experiment_scope_accepts_a_non_6_8_real_stage():
    scope = ExperimentScope(
        stage_id="main_11-17",
        operator_pool=("operator-a", "operator-b"),
        max_cardinality=2,
        simulation_budget=3,
        search_policy="CROSS_STAGE_TOP_DOWN_SMOKE",
    )
    assert scope.stage_id == "main_11-17"
    assert scope.conclusion_scope()["global_claim_valid"] is False


def test_top_down_validation_selects_three_supported_real_stage_categories():
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    suite = TopDownValidation(
        repository=repository,
        adapter=ApproximateRealSimulationAdapter(repository),
        root=ROOT,
    ).select_suite()
    assert [stage.category for stage in suite.stages] == [
        "SIMPLE_SINGLE_LANE",
        "MULTI_LANE_PRESSURE",
        "SHARED_RANGED_COVERAGE",
    ]
    assert all(stage.stage_id != "main_06-07" for stage in suite.stages)
    assert all(
        set(stage.source_tile_keys).issubset({
            "tile_start", "tile_floor", "tile_road", "tile_end", "tile_wall",
            "tile_forbidden", "tile_fence", "tile_fence_bound",
        })
        for stage in suite.stages
    )
