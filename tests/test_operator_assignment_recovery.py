from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.strategy import Strategy
from arknights_planner.search.operator_assignment import OperatorAssignmentEngine
from arknights_planner.search.scope import ExperimentScope
from arknights_planner.search.stage_understanding import (
    StageUnderstandingAnalyzer,
    derive_tactical_requirements,
)
from arknights_planner.search.top_down import (
    DeterministicHypothesisGenerator,
    TopDownPlanner,
)


ROOT = Path(__file__).resolve().parents[1]


@lru_cache
def analysis_11_19():
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    fixture = adapter.build_pool_fixture(
        stage_id_or_code="main_11-17",
        configurations=adapter.m13_low_rarity_configurations(),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
    )
    understanding = StageUnderstandingAnalyzer().analyze(fixture)
    requirements = derive_tactical_requirements(understanding)
    assignment = OperatorAssignmentEngine().assign(
        understanding,
        requirements,
        fixture.operators,
        max_cardinality=7,
    )
    return fixture, understanding, requirements, assignment


def test_tactical_requirements_do_not_claim_dedicated_operator_slots():
    _, _, requirements, assignment = analysis_11_19()
    requirement_by_id = {item.requirement_id: item for item in requirements}

    assert requirement_by_id["R-EARLY-DEPLOY"].hardness == "HYPOTHESIZED"
    assert requirement_by_id["R-SINGLE-LANE"].hardness == "HYPOTHESIZED"
    assert all(item.independent_satisfaction_required is False for item in assignment.requirement_coverage)
    assert all(item.dedicated_operator_required is False for item in assignment.requirement_coverage)

    all_requirement_ids = set(requirement_by_id)
    assert any(
        set(alternative.covered_requirement_ids) != all_requirement_ids
        for alternative in assignment.coverage_alternatives
    )


def test_one_operator_can_cover_multiple_requirements():
    fixture, understanding, _, assignment = analysis_11_19()
    engine = OperatorAssignmentEngine()
    noirc = engine.capability_catalog(fixture.operators["char_500_noirc"], understanding)
    fcee = engine.capability_catalog(fixture.operators["char_009_12fce"], understanding)

    noirc_capabilities = {item.capability for item in noirc}
    fcee_capabilities = {item.capability for item in fcee}
    assert {"EARLY_DEPLOYMENT", "BLOCK", "BLOCK_CAPACITY", "MELEE_DPS"} <= noirc_capabilities
    assert {"RANGED_DPS", "MULTI_LANE_COVERAGE", "ARTS_DAMAGE"} <= fcee_capabilities

    early = next(item for item in assignment.coverage_alternatives if item.archetype == "EARLY_CHEAP_INTERCEPTION")
    noirc_coverage = next(item for item in early.operator_coverage if item.operator_id == "char_500_noirc")
    assert {"R-EARLY-DEPLOY", "R-SINGLE-LANE"} <= set(noirc_coverage.covered_requirement_ids)

    arts = next(item for item in assignment.coverage_alternatives if item.archetype == "ARTS_INTERCEPTION")
    fcee_coverage = next(item for item in arts.operator_coverage if item.operator_id == "char_009_12fce")
    assert {"R-ARTS", "R-RANGED-DPS"} <= set(fcee_coverage.covered_requirement_ids)


def test_conditional_capabilities_preserve_placement_timing_and_skill_conditions():
    fixture, understanding, _, assignment = analysis_11_19()
    engine = OperatorAssignmentEngine()
    noirc = {
        item.capability: item
        for item in engine.capability_catalog(fixture.operators["char_500_noirc"], understanding)
    }
    fcee = {
        item.capability: item
        for item in engine.capability_catalog(fixture.operators["char_009_12fce"], understanding)
    }

    assert noirc["EARLY_DEPLOYMENT"].status == "CONDITIONAL"
    assert any("DP accumulation" in condition for condition in noirc["EARLY_DEPLOYMENT"].conditions)
    assert noirc["BLOCK"].status == "CONDITIONAL"
    assert any("route" in condition for condition in noirc["BLOCK"].conditions)
    assert fcee["RANGED_DPS"].status == "CONDITIONAL"
    assert any("coverage tile" in condition for condition in fcee["RANGED_DPS"].conditions)

    for coverage in assignment.requirement_coverage:
        for provider in coverage.providers:
            assert provider.evidence
            if provider.status == "CONDITIONAL":
                assert provider.conditions


def test_multiple_operators_can_jointly_cover_block_capacity():
    _, _, _, assignment = analysis_11_19()
    alternative = next(
        item for item in assignment.coverage_alternatives
        if item.archetype == "DUAL_BLOCK_FRONTLINE"
    )
    block_providers = {
        item.operator_id
        for item in alternative.operator_coverage
        if {"BLOCK", "BLOCK_CAPACITY"}.intersection(
            (item.primary_capability, *item.secondary_capabilities)
        )
    }

    assert "R-BLOCK-CAPACITY" in alternative.covered_requirement_ids
    assert len(block_providers) >= 2


def test_assignment_alternatives_preserve_semantic_diversity():
    _, _, _, assignment = analysis_11_19()
    alternatives = assignment.coverage_alternatives

    assert len(alternatives) >= 10
    assert len({item.archetype for item in alternatives}) == len(alternatives)
    assert len({item.operator_ids for item in alternatives}) == len(alternatives)
    assert len({item.semantic_fingerprint for item in alternatives}) == len(alternatives)
    assert len({item.simulation_fingerprint for item in alternatives}) == len(alternatives)
    assert all(item.operator_count <= 7 for item in alternatives)
    assert len({item.operator_count for item in alternatives}) >= 2


def test_hypotheses_follow_coverage_alternatives_without_llm():
    _, understanding, _, assignment = analysis_11_19()
    hypotheses = DeterministicHypothesisGenerator().generate_hypotheses(
        {"stage_understanding": understanding, "operator_assignment": assignment},
        max_hypotheses=10,
    )

    assert len(hypotheses) == len(assignment.coverage_alternatives)
    assert {item.tactical_archetype for item in hypotheses} == {
        item.archetype for item in assignment.coverage_alternatives
    }
    assert all(item.preferred_operator_ids for item in hypotheses)


def test_high_level_failure_revision_precedes_local_repair():
    fixture, understanding, _, assignment = analysis_11_19()
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    planner = TopDownPlanner(
        adapter=ApproximateRealSimulationAdapter(repository),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        scope=ExperimentScope(
            stage_id="main_11-17",
            operator_pool=tuple(fixture.operators),
            max_cardinality=7,
            simulation_budget=0,
            search_policy="REGRESSION_DIAGNOSIS_ONLY",
        ),
        root=ROOT,
    )
    failed_result = SimpleNamespace(
        events=(),
        deployment_errors=(),
        operator_deaths=0,
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


def test_recorded_round_two_used_no_local_repair_budget():
    payload = json.loads(
        (ROOT / "output/operator_assignment_recovery/first_win_round2_results.json").read_text(encoding="utf-8")
    )
    funnel = payload["candidate_funnel"]
    search = payload["search"]

    assert funnel["plan_hypotheses_generated"] == 10
    assert funnel["operator_assignments_generated"] == 10
    assert funnel["unique_full_simulations"] == 62
    assert funnel["local_repair_simulations"] == 0
    assert search["top_down_exploration_simulations"] == 62
    assert search["local_repair_simulations"] == 0
    assert search["budget_split_respected"] is True
