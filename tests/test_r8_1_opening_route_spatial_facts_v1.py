from __future__ import annotations

import json
from pathlib import Path

from arknights_planner.models.route import Route, RouteWait, Waypoint
from arknights_planner.simulator import ApproximateRealRangeTransformer, CanonicalSyntheticRangeTransformer


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_opening_route_spatial_facts_v1"


def load(name: str):
    return json.loads((OUT / name).read_text())


def test_route_time_includes_waits_before_but_not_at_the_target():
    route = Route(
        "waited",
        (Waypoint(0, 0), Waypoint(4, 0)),
        (RouteWait(0.0, 2.0), RouteWait(4.0, 3.0)),
    )
    assert route.time_at_distance(1.0, speed=1.0) == 3.0
    assert route.time_at_distance(4.0, speed=1.0) == 6.0


def test_route_repeated_tile_visits_are_preserved():
    route = Route("there-and-back", (Waypoint(0, 0), Waypoint(2, 0), Waypoint(0, 0), Waypoint(4, 0)))
    assert route.distances_at((0, 0)) == (0.0, 4.0)
    assert route.distances_at((2, 0)) == (2.0, 6.0)
    assert route.times_at_point((0, 0), speed=1.0) == (0.0, 4.0)


def test_real_range_transformer_uses_bottom_left_field_orientation():
    transformer = ApproximateRealRangeTransformer()
    offsets = ((0, 1), (1, 0), (-1, 0))
    assert transformer.covered_tiles(origin=(5, 5), offsets=offsets, direction="RIGHT") == {
        (6, 5), (5, 6), (5, 4),
    }
    assert transformer.covered_tiles(origin=(5, 5), offsets=offsets, direction="DOWN") == {
        (5, 4), (6, 5), (4, 5),
    }
    assert transformer.covered_tiles(origin=(5, 5), offsets=offsets, direction="LEFT") == {
        (4, 5), (5, 4), (5, 6),
    }
    assert transformer.covered_tiles(origin=(5, 5), offsets=offsets, direction="UP") == {
        (5, 6), (4, 5), (6, 5),
    }


def test_synthetic_range_transformer_remains_y_down():
    transformer = CanonicalSyntheticRangeTransformer()
    offsets = ((1, 0),)
    assert transformer.covered_tiles(origin=(0, 0), offsets=offsets, direction="DOWN") == {(0, 1)}
    assert transformer.covered_tiles(origin=(0, 0), offsets=offsets, direction="UP") == {(0, -1)}


def test_source_endpoints_roadblocks_and_route6_inconsistency_are_recorded():
    facts = load("opening_route_spatial_timing_facts.json")
    assert facts["route_facts"]["route-3"]["start"]["field_col_row"] == [1, 1]
    assert facts["route_facts"]["route-3"]["end"]["field_col_row"] == [9, 1]
    assert facts["route_facts"]["route-6"]["start"]["field_col_row"] == [0, 5]
    assert facts["route_facts"]["route-6"]["end"]["field_col_row"] == [8, 6]
    roadblocks = {item["alias"]: item["field_col_row"] for item in facts["roadblocks"]}
    assert roadblocks == {
        "trap_020_roadblock#1": [5, 3],
        "trap_020_roadblock#2": [9, 4],
        "trap_020_roadblock#3": [7, 2],
        "trap_020_roadblock#4": [1, 2],
        "trap_020_roadblock#5": [3, 5],
    }
    route6 = facts["route_facts"]["route-6"]
    assert route6["motion_mode"] == "WALK"
    assert route6["path_cell_consistency"]["walk_fly_only_tile_candidates"]


def test_wait_aware_opening_deadline_facts_are_derived_from_public_route():
    facts = load("opening_route_spatial_timing_facts.json")["early_threat_model"]
    rows = {item["route_id"]: item for item in facts["routes"]}
    assert rows["route-1"]["latest_safe_blocker_frame"] == 461
    assert rows["route-3"]["latest_safe_blocker_frame"] == 431
    assert rows["route-4"]["latest_safe_blocker_frame"] == 941
    assert sum(item["duration"] for item in rows["route-1"]["wait_schedule"]) == 9.0
    assert rows["route-1"]["blocked_post_contact_timing"] == "CONDITIONAL_UNKNOWN_AFTER_CONTACT"


def test_b2_spatial_mismatches_are_explicit_without_changing_actions():
    mismatch = load("b2_plan_mismatch.json")
    actions = {item["operator_id"]: item for item in mismatch["actions"]}
    assert actions["char_4093_frston"]["exact_route_path_intersection"] == []
    assert actions["char_502_nblade"]["exact_route_path_intersection"] == ["route-1", "route-3", "route-4"]
    invalid = {item["old_input"]: item["status"] for item in mismatch["invalidated_plan_inputs"]}
    assert invalid["route-1 latest_safe_blocker_frame=191 at [8,5]"] == "OLD_INPUT_INVALID"
    assert invalid["route-7 blocked at [5,1] by 725"] == "OLD_INPUT_INVALID"
