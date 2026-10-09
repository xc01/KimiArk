from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig
from arknights_planner.search.operator_assignment import OperatorAssignmentEngine
from arknights_planner.search.spatial_timing import (
    SpatialTimingConfig,
    SpatialTimingSearch,
)
from arknights_planner.search.stage_understanding import (
    StageUnderstandingAnalyzer,
    derive_tactical_requirements,
)
from arknights_planner.search.top_down import DeterministicHypothesisGenerator


ROOT = Path(__file__).resolve().parents[1]


@lru_cache
def spatial_fixture():
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    policy = RealSimulationApproximationPolicy.m11_second_quantized()
    configurations = adapter.m13_low_rarity_configurations()
    engine = M11MinimumSquadSearch(
        adapter=adapter,
        stage_id_or_code="main_11-17",
        policy=policy,
        operator_pool=configurations,
        config=M11SearchConfig(max_squad_size=7, placement_options_per_operator=8),
    )
    understanding = StageUnderstandingAnalyzer().analyze(engine.fixture)
    requirements = derive_tactical_requirements(understanding)
    assignment = OperatorAssignmentEngine().assign(
        understanding,
        requirements,
        engine.fixture.operators,
        max_cardinality=7,
    )
    hypotheses = DeterministicHypothesisGenerator().generate_hypotheses(
        {
            "stage_understanding": understanding.to_dict(),
            "operator_assignment": assignment.to_dict(),
        },
        max_hypotheses=10,
    )
    search = SpatialTimingSearch(engine=engine, understanding=understanding)
    return engine, understanding, assignment, hypotheses, search


def test_tactical_regions_are_generated_from_stage_understanding():
    _, understanding, _, _, search = spatial_fixture()
    regions = search.regions()

    assert regions
    assert {region.region_type for region in regions} >= {
        "CHOKE_POINT_BLOCK",
        "RANGED_SUPPORT_COVERAGE",
    }
    assert all(region.provenance for region in regions)
    assert all(region.tiles for region in regions)
    assert {
        tile for region in regions if region.tile_kind == "GROUND" for tile in region.tiles
    } <= set(understanding.deployable_ground)
    assert {
        tile for region in regions if region.tile_kind == "HIGH_GROUND" for tile in region.tiles
    } <= set(understanding.deployable_high_ground)


def test_skeletons_preserve_semantic_diversity():
    _, _, _, _, search = spatial_fixture()
    audit: dict = {}
    skeletons = search.generate_skeletons(
        hypothesis_id="test-hypothesis",
        hypothesis_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
        team=("char_502_nblade", "char_501_durin"),
        deployment_order=("char_502_nblade", "char_501_durin"),
        roles={"char_502_nblade": "BLOCK", "char_501_durin": "RANGED_DPS"},
        audit=audit,
    )

    assert len(skeletons) >= 2
    assert len({item.semantic_fingerprint for item in skeletons}) == len(skeletons)
    assert len({item.region_signature for item in skeletons}) >= 2
    assert all(all(placement.relations for placement in item.placements) for item in skeletons)


def test_facing_candidates_are_coverage_aware():
    engine, _, _, _, search = spatial_fixture()
    candidates = search.tile_candidates(
        "char_501_durin",
        "RANGED_DPS",
    )

    assert candidates
    assert len({item.direction for item in candidates}) >= 2
    assert len({frozenset(item.covered_cells) for item in candidates}) >= 2
    assert all(engine.fixture.operators[item.operator_id].position.value == "RANGED" for item in candidates)


def test_timing_candidates_use_event_relative_integer_frames():
    _, _, _, _, search = spatial_fixture()
    audit: dict = {}
    skeleton = search.generate_skeletons(
        hypothesis_id="test-hypothesis",
        hypothesis_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
        team=("char_502_nblade", "char_501_durin"),
        deployment_order=("char_502_nblade", "char_501_durin"),
        roles={"char_502_nblade": "BLOCK", "char_501_durin": "RANGED_DPS"},
        audit=audit,
    )[0]
    candidates = search.generate_timing_candidates(skeleton, audit=audit)

    assert candidates
    for candidate in candidates:
        assert all(isinstance(frame, int) and frame >= 0 for frame in candidate.deploy_frames)
        assert candidate.deploy_frames == tuple(sorted(candidate.deploy_frames))
        assert candidate.anchors
        assert all(anchor.event_type for anchor in candidate.anchors)
        assert all(action.action_type is ActionType.DEPLOY for action in candidate.actions)


def test_coarse_to_fine_timing_is_bounded():
    _, _, _, _, search = spatial_fixture()
    audit: dict = {}
    skeleton = search.generate_skeletons(
        hypothesis_id="test-hypothesis",
        hypothesis_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
        team=("char_502_nblade", "char_501_durin"),
        deployment_order=("char_502_nblade", "char_501_durin"),
        roles={"char_502_nblade": "BLOCK", "char_501_durin": "RANGED_DPS"},
        audit=audit,
    )[0]
    coarse = search.generate_timing_candidates(skeleton, audit=audit)[0]
    refined = search._timing_refinement_candidates(coarse)

    assert search.config.refinement_offsets == (-30, -10, -3, 3, 10, 30)
    assert len(refined) <= len(coarse.actions) * len(search.config.refinement_offsets)
    assert all(item.source == "LOCAL_TIMING_REFINEMENT" for item in refined)
    assert all(item.deploy_frames != coarse.deploy_frames for item in refined)


def test_dp_legality_rejects_infeasible_or_duplicate_deployments():
    _, _, _, _, search = spatial_fixture()
    audit: dict = {}
    skeleton = search.generate_skeletons(
        hypothesis_id="test-hypothesis",
        hypothesis_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
        team=("char_502_nblade", "char_501_durin"),
        deployment_order=("char_502_nblade", "char_501_durin"),
        roles={"char_502_nblade": "BLOCK", "char_501_durin": "RANGED_DPS"},
        audit=audit,
    )[0]
    candidate = search.generate_timing_candidates(skeleton, audit=audit)[0]
    assert candidate.dp_feasible

    first = candidate.actions[0]
    too_early = Strategy(
        candidate.strategy.team,
        (Action(ActionType.DEPLOY, 0.0, first.operator_id, first.tile, first.direction), *candidate.actions[1:]),
    )
    feasible, reasons = search.dp_legality(too_early)
    assert feasible is False
    assert "INSUFFICIENT_DP" in reasons

    duplicate_tile = Strategy(
        candidate.strategy.team,
        tuple(Action(action.action_type, action.time, action.operator_id, candidate.actions[0].tile, action.direction) for action in candidate.actions),
    )
    feasible, reasons = search.dp_legality(duplicate_tile)
    assert feasible is False
    assert "DUPLICATE_TILE" in reasons


def test_assignment_to_skeleton_to_timing_reaches_simulator():
    _, _, _, hypotheses, search = spatial_fixture()
    outcome = search.search(hypotheses, simulation_budget=2)

    assert outcome.spatial_metrics.skeletons_reaching_timing >= 2
    assert outcome.spatial_metrics.timing_candidates_generated >= 2
    assert outcome.metrics.unique_simulations == 2
    assert outcome.metrics.unique_simulations <= 2


def test_generic_logic_has_no_stage_or_operator_literals():
    source = (ROOT / "src/arknights_planner/search/spatial_timing.py").read_text(encoding="utf-8")
    assert "main_11" not in source
    assert "char_" not in source
    assert "RealLLM" not in source
    assert "for tile in self.engine.fixture.stage.stage_map.tiles" not in source
    assert "range(" not in source.split("def _timing_refinement_candidates", 1)[1].split("def search", 1)[0]


def test_experiment_bounds_and_timing_are_not_broadened():
    config = SpatialTimingConfig()

    assert config.max_timing_candidates_per_skeleton <= 8
    assert len(config.refinement_offsets) <= 8
    assert config.max_refinement_fraction <= 0.30
