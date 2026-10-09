from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealOperatorConfiguration,
    RealSimulationApproximationPolicy,
)
from arknights_planner.cli.plan_cli import main
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.strategy import Strategy
from arknights_planner.search import (
    ApproximateRealBeamSearch,
    RealFailureCategory,
    RealSearchConfig,
    analyze_real_failure,
)


@pytest.fixture(scope="module")
def local_gamedata_root() -> Path:
    root = Path(__file__).resolve().parents[1] / "data/ArknightsGameData"
    if not (root / "zh_CN/gamedata/excel/character_table.json").is_file():
        pytest.skip("locally supplied ArknightsGameData is not available")
    return root


@pytest.fixture(scope="module")
def adapter(local_gamedata_root: Path) -> ApproximateRealSimulationAdapter:
    return ApproximateRealSimulationAdapter(GameDataRepository(local_gamedata_root))


@pytest.fixture(scope="module")
def policy() -> RealSimulationApproximationPolicy:
    return RealSimulationApproximationPolicy.main_00_01()


@pytest.fixture(scope="module")
def search(adapter, policy) -> ApproximateRealBeamSearch:
    return ApproximateRealBeamSearch(adapter=adapter, policy=policy)


@pytest.fixture(scope="module")
def search_result(search):
    return search.search()


def test_real_operator_pool_is_fixed_exact_keyframe_configs(adapter, policy):
    pool = adapter.default_main_00_01_search_pool()
    assert pool == (
        RealOperatorConfiguration("char_129_bluep", 2, 80),
        RealOperatorConfiguration("char_010_chen", 2, 90),
        RealOperatorConfiguration("char_002_amiya", 2, 80),
        RealOperatorConfiguration("char_017_huang", 2, 90),
    )
    fixture = adapter.build_pool_fixture(stage_id_or_code="0-1", configurations=pool, policy=policy)
    assert {operator_id: (operator.position.value, operator.phases[0].stats_max.cost.value) for operator_id, operator in fixture.operators.items()} == {
        "char_129_bluep": ("RANGED", 13),
        "char_010_chen": ("MELEE", 23),
        "char_002_amiya": ("RANGED", 20),
        "char_017_huang": ("MELEE", 24),
    }


def test_candidate_generation_is_legal_pruned_and_deterministic(search):
    first = search.deployment_options()
    assert first == search.deployment_options()
    assert first
    tiles = {(tile.x, tile.y): tile for tile in search.fixture.stage.stage_map.tiles}
    for option in first:
        operator = search.fixture.operators[option.operator_id]
        assert option.route_coverage > 0
        assert tiles[option.tile].buildable
        assert tiles[option.tile].tile_kind == ("GROUND" if operator.position.value == "MELEE" else "HIGH_GROUND")

    candidates = search.generate_candidates(Strategy((), ()))
    assert candidates == search.generate_candidates(Strategy((), ()))
    assert candidates
    assert all(candidate.actions[0].time in search.timing_candidates() for candidate in candidates)
    # Blue Poison costs 13 while 0.0 seconds only has the source-backed initial 10 DP.
    assert not any(candidate.actions[0].operator_id == "char_129_bluep" and candidate.actions[0].time == 0.0 for candidate in candidates)


def test_real_score_prefers_win_and_failure_analysis_uses_observable_events(search, search_result):
    empty = search._evaluate(Strategy((), ()), metrics=search_result.metrics)
    assert search_result.best.result.win is True
    assert search_result.best.score > empty.score
    analysis = analyze_real_failure(empty)
    assert RealFailureCategory.LEAK_BEFORE_DEPLOYMENT in analysis.categories
    assert RealFailureCategory.POOR_TILE_COVERAGE in analysis.categories
    assert RealFailureCategory.EXCESS_UNUSED_DEPLOYMENT_CAPACITY in analysis.categories


def test_real_cache_key_includes_explicit_approximation_policy(search, policy):
    key = search._cache_key(Strategy((), ()))
    assert policy.cache_identity in key
    assert key[0] == "approximate-real-search-v1"
    assert search._strategy_key(Strategy(("char_129_bluep",), ())) == search._strategy_key(Strategy(("char_129_bluep",), ()))


def test_search_evaluates_approximate_real_runs_and_discovers_a_win(search_result):
    result = search_result.best.result
    assert result.run_metadata is not None
    assert result.run_metadata.mode == "APPROXIMATE_REAL"
    assert result.win is True
    assert result.enemies_killed == 11
    assert result.enemies_leaked == 0
    assert search_result.metrics.simulations_to_first_win is not None
    assert search_result.metrics.winning_candidates > 0
    assert search_result.timeline is not None
    assert search_result.timeline.actions[0].frame == 90
    assert search_result.timeline.frame_clock.status.value == "APPROXIMATED"
    assert search_result.timeline.actions[0].action_type.value == "DEPLOY"


def test_frame_candidate_generation_is_integer_and_coarse(search):
    frames = search.timing_frame_candidates()
    assert frames == (0, 120, 240, 360, 480, 600, 720, 840)
    assert all(isinstance(frame, int) and frame >= 0 for frame in frames)


def test_search_does_not_return_the_calibration_sequence(adapter, search, search_result):
    calibration = adapter.fixed_main_00_01_strategy()
    assert 3.0 not in search.config.coarse_times
    assert 26.0 not in search.config.coarse_times
    assert search_result.best.strategy != calibration
    assert len(search_result.best.strategy.actions) == 1


def test_same_configuration_produces_same_search_output(adapter, policy, search_result):
    repeated = ApproximateRealBeamSearch(adapter=adapter, policy=policy).search()
    assert repeated.best.strategy == search_result.best.strategy
    assert repeated.best.score == search_result.best.score
    assert repeated.best.result.win == search_result.best.result.win
    assert [(item.strategy, item.score) for item in repeated.ranked] == [(item.strategy, item.score) for item in search_result.ranked]


def test_local_refinement_never_worsens_best_score(adapter, policy, search_result):
    coarse = ApproximateRealBeamSearch(
        adapter=adapter,
        policy=policy,
        config=replace(RealSearchConfig(), refine_timing=False),
    ).search()
    assert search_result.best.score >= coarse.best.score
    assert search_result.metrics.local_refinements > 0


def test_real_search_cli_identifies_approximate_mode_and_metrics(local_gamedata_root, capsys):
    main(["real-search", "0-1", "--data-root", str(local_gamedata_root)])
    output = capsys.readouterr().out
    assert "Mode: APPROXIMATE_REAL" in output
    assert "Operator pool:" in output
    assert "Metrics:" in output
    assert "Result: WIN" in output
