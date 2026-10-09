"""Offline regression checks for M15.1 failure-frontier repair."""
from __future__ import annotations

from pathlib import Path

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.m15_repair import FailureFrontierRepair


def _repair() -> FailureFrontierRepair:
    root = Path("output/m15/main_06-07")
    return FailureFrontierRepair(
        adapter=ApproximateRealSimulationAdapter(GameDataRepository("data/ArknightsGameData")),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        parent_path=root / "m15_results.json",
        guided_budget=1,
        control_budget=1,
    )


def test_m15_1_preserved_parent_has_supported_route_2_interaction_timing_trace():
    repair = _repair()
    strategy, _ = repair._parent_strategy()
    parent = repair._evaluate(strategy)
    assert parent is not None
    trace = repair._causal_trace(parent)
    assert trace["enemy_id"] == "enemy_1065_snwolf"
    assert trace["route_progression"]
    assert trace["leak_frame"] == 366
    assert trace["damage_received"] == 0
    assert "INTERACTION_TOO_LATE" in trace["classification"]


def test_m15_1_route_capable_late_deployment_is_a_frontier_dependency():
    repair = _repair()
    strategy, _ = repair._parent_strategy()
    parent = repair._evaluate(strategy)
    assert parent is not None
    trace = repair._causal_trace(parent)
    focus = repair._dependency_actions(parent, trace, guided=True)
    deploys = [item for item in parent.strategy.actions if item.action_type.value == "DEPLOY"]
    assert any(deploys[index].operator_id == "char_283_midn" for index in focus)
    assert any(
        row["action"]["operator_id"] == "char_283_midn"
        and "INTERACTION_AVAILABLE_AFTER_FRONTIER" in row["dependency_reasons"]
        for row in repair.prefix_dependencies
    )


def test_m15_1_reassignment_generates_same_position_operator_replacements():
    repair = _repair()
    strategy, _ = repair._parent_strategy()
    parent = repair._evaluate(strategy)
    assert parent is not None
    trace = repair._causal_trace(parent)
    candidates = repair._repair_candidates(parent, trace, "OPERATOR_REASSIGNMENT", guided=True)
    assert candidates
    assert all(mutation == "OPERATOR_REASSIGNMENT" for mutation, _, _ in candidates)
