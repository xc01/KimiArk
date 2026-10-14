from __future__ import annotations

from run_r8_1_low_star_full_tactical_closure_v1 import validate_operational_plan_output


def evidence(roadblocks: list[list[int]]) -> dict:
    return {
        "stage_active_facts": {
            "roadblock_tiles_col_row": roadblocks,
            "active_device_tiles_col_row": roadblocks,
            "deployable_ground_tiles_col_row": [[5, 3]],
            "deployable_high_ground_tiles_col_row": [],
        },
        "normal_low_star_catalog": [{
            "operator_id": "char_123_fang",
            "identity": {"rarity": 3, "position": "MELEE"},
            "qualification": {"normal_mode": True},
        }],
    }


def plan(tile: list[int]) -> dict:
    return {
        "revised_strategic_hypotheses": [{"hypothesis_id": "H"}],
        "revised_operational_plans": [{
            "operational_plan_id": "P", "parent_hypothesis_id": "H",
            "tactical_thesis": "test", "selected_low_star_operator_ids": ["char_123_fang"],
            "deployment_positions_and_directions": [], "formation_structure": {},
            "formation_transitions": [], "corridor_responsibilities": [],
            "pressure_window_responsibilities": [], "skill_intents": [],
            "mandatory_tactical_invariants": [],
            "action_timeline": [{"action_type": "DEPLOY", "frame": 0, "operator_id": "char_123_fang", "tile": tile, "direction": "UP"}],
        }],
    }


def test_same_plan_tile_legality_changes_by_stage_roadblock_evidence() -> None:
    assert validate_operational_plan_output(plan([3, 5]), evidence([[5, 3]])) != []
    assert validate_operational_plan_output(plan([3, 5]), evidence([[9, 4]])) == []


def test_missing_current_stage_roadblocks_do_not_fall_back_to_r8_1() -> None:
    current = evidence([[5, 2]])
    del current["stage_active_facts"]["roadblock_tiles_col_row"]
    errors = validate_operational_plan_output(plan([3, 5]), current)
    assert "stage_active_facts.roadblock_tiles_col_row is required" in errors
