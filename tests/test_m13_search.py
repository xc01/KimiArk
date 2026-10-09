from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search import M13LayeredSearch, M13SearchConfig


def test_m13_composition_coverage_is_complete_for_executable_pool():
    repo = GameDataRepository("data/ArknightsGameData")
    out = M13LayeredSearch(
        adapter=ApproximateRealSimulationAdapter(repo), stage_id_or_code="6-8",
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        config=M13SearchConfig(max_tactical_teams_k2=1),
    ).search()
    n = len(out.executable_pool)
    assert out.metrics.k1_possible == n
    assert out.metrics.k1_compositions_generated == n
    assert out.metrics.k2_possible == n * (n - 1) // 2
    assert out.metrics.k2_compositions_generated == out.metrics.k2_possible


def test_m13_team_features_are_deterministic():
    repo = GameDataRepository("data/ArknightsGameData")
    search = M13LayeredSearch(adapter=ApproximateRealSimulationAdapter(repo), stage_id_or_code="6-8", policy=RealSimulationApproximationPolicy.m11_second_quantized(), config=M13SearchConfig(max_tactical_teams_k2=1))
    assert search.features == search.features
    assert all(item.operator_ids == tuple(sorted(item.operator_ids)) for item in search.features)
