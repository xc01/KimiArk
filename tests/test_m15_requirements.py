"""Offline M15.2 requirement-boundary checks; no strategy search is run."""
from arknights_planner.search.m15_requirements import FrontierRequirement


def test_observed_damage_requirement_keeps_candidate_specific_evidence():
    requirement = FrontierRequirement(
        "R2", "DAMAGE_REQUIREMENT", "route-2", 564, "enemy#1", "SIMULATION_EXACT", ("trace",), 1119.0, 2031.0, 6,
    )
    row = requirement.as_dict()
    assert row["observed_remaining_hp"] == 1119.0
    assert "not an invariant" in row["semantic_requirement"]
