"""Offline geometry facts used by the bounded M14.8 opening experiment."""
from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.m14_geometry import M14OpeningGeometrySearch


def test_parallel_opening_routes_have_no_shared_tiles_but_plume_can_range_interact_with_both():
    search = M14OpeningGeometrySearch(
        adapter=ApproximateRealSimulationAdapter(GameDataRepository("data/ArknightsGameData")),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(), budget=1,
    )
    engine = search._engine(opening=True)
    geometry = search._geometry(engine)
    assert geometry["route_0_2_shared_tiles"] == []
    assert geometry["route_0_2_minimum_grid_distance"] == 1
    graph, _ = search._interaction_graph(engine, geometry)
    plume = next(item for item in graph if item["operator_id"] == "char_192_falco" and item["tile"] == (2, 3) and item["direction"] == "DOWN")
    assert plume["routes"]["route-0"]["ground_intersection"] is True
    assert plume["routes"]["route-2"]["range_cells"] == [(2, 4)]
