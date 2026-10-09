"""Offline checks for the bounded M14.6 opening audit."""
from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.m14_opening import M14OpeningRepairSearch, R4_IDS


def _search():
    return M14OpeningRepairSearch(
        adapter=ApproximateRealSimulationAdapter(GameDataRepository("data/ArknightsGameData")),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(), budget=10, horizon_frame=900,
    )


def test_opening_schedule_respects_exact_dp_for_two_r4_blockers():
    search = _search()
    engine = search._engine(R4_IDS, opening=True)
    actions = search._schedule(engine, (
        ("char_122_beagle", (4, 3), "DOWN"),
        ("char_209_ardign", (4, 4), "DOWN"),
    ))
    assert [engine.config.frame_clock.frame_for_seconds(item.time) for item in actions] == [240, 780]
    assert search._static(engine, R4_IDS, actions) == (True, None)


def test_opening_arrival_report_records_route_margins_and_single_substitution():
    search = _search()
    engine = search._engine(R4_IDS, opening=True)
    report = search._arrival_report(engine)
    first = report["early_enemy_arrivals"][0]["arrivals"][0]
    assert first["tile"] == (4, 3)
    assert first["arrival_frame"] == 244
    assert first["opening_margin_frames"] == 4
    team, rationale = search._single_substitution()
    assert len(team) == 7 and "char_502_nblade" in team and "char_210_stward" not in team
    assert rationale["cost_difference"] == -11
