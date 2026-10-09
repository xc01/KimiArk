from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.agent.tactical import PlanHypothesis
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig
from arknights_planner.search.spatial_timing import SpatialTimingSearch
from arknights_planner.search.stage_understanding import StageUnderstandingAnalyzer

from tests.test_spatial_timing import spatial_fixture


ROOT = Path(__file__).resolve().parents[1]


@lru_cache
def main_01_01_spatial_fixture():
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    configurations = adapter.all_executable_phase_zero_configurations()
    engine = M11MinimumSquadSearch(
        adapter=adapter,
        stage_id_or_code="main_01-01",
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        operator_pool=configurations,
        config=M11SearchConfig(max_squad_size=12),
    )
    understanding = StageUnderstandingAnalyzer().analyze(engine.fixture)
    return engine, understanding, SpatialTimingSearch(engine=engine, understanding=understanding)


def _geometry(skeleton):
    return tuple(
        (placement.candidate.operator_id, placement.candidate.tile, placement.candidate.direction)
        for placement in skeleton.placements
    )


def test_block_routes_use_exact_simulator_geometry_not_rasterized_cells():
    engine, understanding, search = main_01_01_spatial_fixture()
    route_4 = next(route for route in engine.fixture.stage.routes if route.route_id == "route-4")
    false_block_tile = (4, 3)

    assert false_block_tile in {
        cell
        for route in understanding.routes
        if route.route_id == "route-4"
        for cell in route.cells
    }
    assert route_4.distance_at(false_block_tile) is None

    blocker = next(
        operator_id
        for operator_id, operator in engine.fixture.operators.items()
        if operator.position.value == "MELEE"
    )
    candidates = search.tile_candidates(blocker, "BLOCK")
    assert all(
        "route-4" not in candidate.block_route_ids
        for candidate in candidates
        if candidate.tile == false_block_tile
    )


def test_semantic_skeletons_preserve_distinct_executable_geometry():
    _, _, _, _, search = spatial_fixture()
    audit = {}
    skeletons = search.generate_skeletons(
        hypothesis_id="lowering",
        hypothesis_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
        team=("char_502_nblade", "char_501_durin"),
        deployment_order=("char_502_nblade", "char_501_durin"),
        roles={"char_502_nblade": "BLOCK", "char_501_durin": "RANGED_DPS"},
        audit=audit,
    )
    geometries = {_geometry(skeleton) for skeleton in skeletons}
    assert len(geometries) == len(skeletons)
    assert all("tile" in skeleton.to_dict()["placements"][0]["candidate"] for skeleton in skeletons)


def test_timing_preserves_desired_frame_unless_legality_requires_later():
    _, _, _, _, search = spatial_fixture()
    audit = {}
    skeleton = search.generate_skeletons(
        hypothesis_id="lowering",
        hypothesis_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
        team=("char_502_nblade", "char_501_durin"),
        deployment_order=("char_502_nblade", "char_501_durin"),
        roles={"char_502_nblade": "BLOCK", "char_501_durin": "RANGED_DPS"},
        audit=audit,
    )[0]
    candidates = search.generate_timing_candidates(skeleton, audit=audit)
    assert candidates
    for candidate in candidates:
        for anchor in candidate.anchors:
            assert anchor.final_frame >= anchor.desired_frame
            assert anchor.final_frame >= anchor.earliest_frame
            if anchor.desired_frame >= anchor.earliest_frame and not anchor.ordering_constraint_applied:
                assert anchor.final_frame == anchor.desired_frame
                assert not anchor.clamped_by_dp


def test_timing_refinement_can_survive_to_a_changed_timeline():
    _, _, _, _, search = spatial_fixture()
    audit = {}
    skeleton = search.generate_skeletons(
        hypothesis_id="lowering",
        hypothesis_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
        team=("char_502_nblade", "char_501_durin"),
        deployment_order=("char_502_nblade", "char_501_durin"),
        roles={"char_502_nblade": "BLOCK", "char_501_durin": "RANGED_DPS"},
        audit=audit,
    )[0]
    candidate = search.generate_timing_candidates(skeleton, audit=audit)[0]
    refined = search._timing_refinement_candidates(candidate)
    assert any(
        item.dp_feasible and item.deploy_frames != candidate.deploy_frames
        for item in refined
    )


def test_responsibility_audit_separates_reachable_and_executed_frames():
    _, _, _, _, search = spatial_fixture()
    hypothesis = PlanHypothesis(
        hypothesis_id="responsibility-lowering",
        summary="Responsibility execution regression",
        target_cardinality=2,
        tactical_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
        preferred_operator_ids=("char_502_nblade", "char_501_durin"),
        deployment_order=("char_502_nblade", "char_501_durin"),
    )
    outcome = search.search((hypothesis,), simulation_budget=1)
    rows = outcome.audit["hypotheses"][hypothesis.hypothesis_id]["operator_responsibility_execution"]
    assert outcome.best is not None
    assert rows
    for row in rows:
        assert len(row["deploy_frames"]) <= 1
        assert row["best_candidate_actions"]
        assert isinstance(row["reachable_deploy_frames"], list)


def test_executable_timeline_fingerprint_ignores_semantic_parent_only():
    _, _, _, _, search = spatial_fixture()
    strategy = Strategy(
        ("a",),
        (Action(ActionType.DEPLOY, 1.0, "a", (1, 1), "RIGHT"),),
    )
    same_actions = Strategy(
        ("a",),
        (Action(ActionType.DEPLOY, 1.0, "a", (1, 1), "RIGHT"),),
    )
    different_frame = Strategy(
        ("a",),
        (Action(ActionType.DEPLOY, 2.0, "a", (1, 1), "RIGHT"),),
    )
    assert search._executable_timeline_fingerprint(strategy) == search._executable_timeline_fingerprint(same_actions)
    assert search._executable_timeline_fingerprint(strategy) != search._executable_timeline_fingerprint(different_frame)
