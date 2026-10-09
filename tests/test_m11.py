from __future__ import annotations

from pathlib import Path

import pytest

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealOperatorConfiguration, RealSimulationApproximationPolicy
from arknights_planner.benchmark import chapter_mid_late_census
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search import M11MinimumSquadSearch, M11SearchConfig, M11SearchStop
from arknights_planner.simulator import SimulationConfig


@pytest.fixture(scope="module")
def repository() -> GameDataRepository:
    root = Path(__file__).resolve().parents[1] / "data/ArknightsGameData"
    if not (root / "zh_CN/gamedata/excel/character_table.json").is_file():
        pytest.skip("locally supplied ArknightsGameData is not available")
    return GameDataRepository(root)


def test_stage_code_prefers_normal_main_story_variant(repository):
    stage = repository.get_stage("9-5")
    assert stage.stage_id == "main_09-04"
    assert stage.level_structure is not None


def test_m11_stage_census_uses_within_chapter_progression_not_chapter_number(repository):
    census = chapter_mid_late_census(repository, chapters=(6, 7))
    seven_ten = next(item for item in census if item.code == "7-10")
    six_eight = next(item for item in census if item.code == "6-8")
    assert seven_ten.progression_band == "MID"
    assert six_eight.progression_band == "MID"
    assert seven_ten.structurally_loadable is True


def test_m11_bottom_left_coordinates_preserve_move_and_wait_checkpoint_types(repository):
    adapter = ApproximateRealSimulationAdapter(repository)
    fixture = adapter.build_pool_fixture(
        stage_id_or_code="6-8",
        configurations=(RealOperatorConfiguration("char_122_beagle", 0, 40),),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
    )
    route = fixture.stage.routes[0]
    # Source (row=3,col=10) in a seven-row map becomes (10,3); the following
    # MOVE position is (row=3,col=9).  WAIT is retained separately, not moved to
    # its source placeholder position.
    assert [(point.x, point.y) for point in route.waypoints][:2] == [(0.0, 3.0), (1.0, 3.0)]
    assert fixture.stage.stage_map.tile_at((0, 7)).tile_kind == "NON_DEPLOYABLE"


def test_m11_second_quantized_hierarchy_is_explicit_and_deterministic(repository):
    adapter = ApproximateRealSimulationAdapter(repository)
    policy = RealSimulationApproximationPolicy.m11_second_quantized()
    args = dict(
        stage_id_or_code="6-8",
        configurations=(RealOperatorConfiguration("char_122_beagle", 0, 40),),
        policy=policy,
    )
    first = adapter.build_pool_fixture(**args)
    second = adapter.build_pool_fixture(**args)
    assert first.spawn_timeline == second.spawn_timeline
    assert "HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED" in first.approximations_used
    assert all(item.time == int(item.time) for item in first.spawn_timeline)
    assert len(first.spawn_timeline) == 22


def test_m11_bounded_cardinality_search_runs_real_fixture_and_is_honest_about_no_win(repository):
    search = M11MinimumSquadSearch(
        adapter=ApproximateRealSimulationAdapter(repository),
        stage_id_or_code="6-8",
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        operator_pool=M11MinimumSquadSearch.default_m11_pool(),
        config=M11SearchConfig(
            max_squad_size=2, beam_width=2, placement_options_per_operator=2,
            coarse_deployment_frames=(0, 180, 360, 540),
            simulation_config=SimulationConfig(dt=0.2, max_time=300.0),
        ),
    )
    first = search.search()
    second = M11MinimumSquadSearch(
        adapter=ApproximateRealSimulationAdapter(repository), stage_id_or_code="6-8",
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        operator_pool=M11MinimumSquadSearch.default_m11_pool(), config=search.config,
    ).search()
    assert first.stop is M11SearchStop.NO_WIN_FOUND
    assert first.timeline is None
    assert first.metrics.unique_simulations > 0
    assert first.metrics.unique_simulations == second.metrics.unique_simulations
    assert first.metrics.strategies_generated == second.metrics.strategies_generated
