from arknights_planner.adapters import ApproximateRealSimulationAdapter, M13LoadoutPolicy
from arknights_planner.benchmark.census import low_rarity_census
from arknights_planner.gamedata.repository import GameDataRepository


def test_m13_loadout_uses_highest_phase_exact_keyframe():
    repo = GameDataRepository("data/ArknightsGameData")
    cfg = M13LoadoutPolicy.highest_legal().configuration(repo, "char_120_hibisc")
    assert (cfg.phase_index, cfg.level) == (1, 55)


def test_m13_pool_is_derived_from_full_census():
    repo = GameDataRepository("data/ArknightsGameData")
    census = low_rarity_census(repo)
    pool = ApproximateRealSimulationAdapter(repo).m13_low_rarity_configurations()
    eligible = {r.operator_id for r in census if r.runtime_status.value.startswith("EXECUTABLE")}
    assert len(census) == 34
    assert {item.operator_id for item in pool} == eligible
    assert len(pool) > 4
