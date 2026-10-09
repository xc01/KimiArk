"""Offline regression tests for the bounded M15 feasibility planner."""
from __future__ import annotations

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.m15 import ConstraintGuidedFeasibilityPlanner, FailureFrontier, FailureType, PartialStrategy


def _planner(*, beam_width: int = 12, budget: int = 2000):
    adapter = ApproximateRealSimulationAdapter(GameDataRepository("data/ArknightsGameData"))
    return ConstraintGuidedFeasibilityPlanner(
        adapter=adapter,
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        beam_width=beam_width,
        simulation_budget=budget,
        max_cardinality=7,
    )


def test_initial_constraints_are_source_derived_hard_opening_deadlines():
    planner = _planner()
    constraints = planner.initial_constraints()
    assert [(item.routes, item.deadline_frame, item.hard_deadline) for item in constraints] == [
        (("route-0",), 244, True),
        (("route-2",), 274, True),
    ]
    assert all(item.provenance == "DERIVED" for item in constraints)


def test_one_placement_can_satisfy_both_parallel_opening_constraints():
    planner = _planner()
    constraints = planner.initial_constraints()
    root = PartialStrategy(constraints=constraints)
    children = planner._expand(root, constraints[0])
    expected = {item.constraint_id for item in constraints}
    assert any(len(item.assignments) == 1 and set(item.satisfied_constraints) == expected for item in children)


def test_frontier_damage_constraint_is_a_repair_request_not_an_unproven_hard_deadline():
    planner = _planner()
    frontier = FailureFrontier(
        frame=366, failure_type=FailureType.EARLY_LEAK, routes=("route-2",), enemy_ids=("enemy_1065_snwolf",),
        affected_operator_ids=(), relevant_tiles=(), required_capabilities=("DAMAGE",), dp_state="UNKNOWN",
        deployment_slots=6, evidence=("observed early leak",), confidence="DERIVED",
    )
    constraint = planner._constraint_from_frontier(frontier, 1)
    assert constraint.constraint_type == "PROVIDE_DAMAGE_BEFORE"
    assert constraint.hard_deadline is False
    assert constraint.provenance == "DERIVED"


def test_m15_runs_without_llm_and_reaches_the_allowed_cardinality_layer():
    report = _planner(beam_width=12).run()
    rows = report["m15_search_progress"]
    assert report["m15_stage_constraints"]["llm_calls"] == 0
    assert len(report["m15_stage_constraints"]["operator_pool"]) == 22
    assert any(item["best"]["operator_count"] == 7 for item in rows)
    assert report["m15_results"]["termination"] in {"WIN_FOUND", "NO_WIN_FOUND_BOUNDED"}
