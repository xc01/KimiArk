"""Offline invariants for M14.7 constrained opening-economy repair."""
from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.m14_economy import M14OpeningEconomyRepair


def test_opening_economy_signatures_are_full_pool_and_report_only_supported_dp_skills():
    search = M14OpeningEconomyRepair(
        adapter=ApproximateRealSimulationAdapter(GameDataRepository("data/ArknightsGameData")),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(), budget=1,
    )
    engine = search._engine(tuple(search.configurations), opening=True)
    signatures = search._operator_signatures(engine)
    assert len(signatures) == 22
    dp_enabled = {item["operator_id"] for item in signatures if item["dp_generation_runtime_supported"]}
    assert dp_enabled == {"char_123_fang", "char_240_wyvern"}
    nblade = next(item for item in signatures if item["operator_id"] == "char_502_nblade")
    assert nblade["deployment_cost"] == 7 and nblade["earliest_deployment_frame"] == 0


def test_economy_repair_keeps_exactly_seven_operators_in_candidate_generation():
    search = M14OpeningEconomyRepair(
        adapter=ApproximateRealSimulationAdapter(GameDataRepository("data/ArknightsGameData")),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(), budget=1,
    )
    team = ("char_122_beagle", "char_124_kroos", "char_209_ardign", "char_192_falco", "char_211_adnach", "char_501_durin", "char_212_ansel")
    helper = search._helper(); engine = helper._engine(team, opening=True)
    candidates = search._opening_candidates(helper, engine, team)
    assert candidates and all(len(item.team) == 7 for item in candidates)
