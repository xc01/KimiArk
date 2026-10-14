from __future__ import annotations

import json

import run_gpt_tactical_stage_session_v1 as runner


def test_stage_prompt_pins_plan_identity_and_roadblock_coordinate_conversion() -> None:
    original = (runner.STAGE_ID, runner.PLAN_ID, runner.PLAN_LABEL)
    try:
        runner.STAGE_ID = "main_08-02"
        runner.PLAN_ID = "R8_2_GPT_V3"
        runner.PLAN_LABEL = "R8-2-V3"
        prompt = runner.build_prompt({
            "stage_active_facts": {
                "roadblock_tiles_col_row": [[5, 2], [7, 4]],
                "roadblock_plan_tiles_row_col": [[2, 5], [4, 7]],
            }
        })
        assert '"operational_plan_id": "R8_2_GPT_V3"' in prompt
        assert "roadblock_tiles_col_row` is [col,row]" in prompt
        assert "roadblock_plan_tiles_row_col" in prompt
        assert "[3,5]" not in prompt.split("EVIDENCE_JSON", 1)[0]
    finally:
        runner.STAGE_ID, runner.PLAN_ID, runner.PLAN_LABEL = original


def test_stage_prompt_requires_protected_target_zero_loss_after_v5() -> None:
    prompt = runner.build_prompt({
        "stage_active_facts": {"roadblock_plan_tiles_row_col": [[2, 5], [4, 7]]},
        "roadblock_clearance_evidence": {
            "roadblock_2": {"device_id": "trap_020_roadblock#2", "tile_json_row_col": [4, 7]},
            "v1_v3_common_events": {
                    "civilian_11": {"spawn": {}, "first_roadblock_2_block": {"frame": 2330}, "last_roadblock_2_block": {"frame": 18000}},
                "civilian_6": {"death": {"frame": 4604}},
            },
            "v5_result_feedback": {
                "remaining_perfect_completion_failure": {
                    "civilian_6": {"death": {"frame": 4604}, "officer_attack_count": 13}
                }
            },
        },
    })
    assert "V6 must retain the zero-leak result" in prompt
    assert "every protected target arrives" in prompt


def test_compact_diagnostic_feedback_excludes_full_event_timeline(tmp_path) -> None:
    summary_path = tmp_path / "diagnostic_summary.json"
    summary_path.write_text(json.dumps({
        "classification": "PARTIAL_MECHANICS_DIAGNOSTIC_LOSS",
        "result": {
            "win": False,
            "enemies_killed": 44,
            "enemies_leaked": 10,
            "operator_deaths": 2,
            "remaining_life": -8,
            "final_dp": 1.5,
            "events": [{"event_type": "DAMAGE", "frame": frame} for frame in range(100000)],
        },
        "event_summaries": {
            "route_summaries": {
                "route-1": {
                    "spawn_count": 2,
                    "blocks": [{"frame": 1, "event_type": "BLOCK"}],
                    "kills": [{"frame": 2, "event_type": "ENEMY_DEATH"}],
                    "leaks": [{"frame": 3, "event_type": "ENEMY_LEAK", "source_id": "enemy#1"}],
                },
                "route-2": {"spawn_count": 1, "blocks": [], "kills": [], "leaks": []},
            },
            "operator_death_events": [{"frame": 4, "event_type": "OPERATOR_DEATH", "source_id": "char"}],
            "deployment_errors": [],
        },
        "first_failure": {"first_leak": {"frame": 3}},
    }))
    feedback = runner.compact_diagnostic_feedback(summary_path)
    encoded = json.dumps(feedback)

    assert feedback["result_metrics"]["enemies_leaked"] == 10
    assert feedback["leaking_route_summaries"][0]["block_count"] == 1
    assert feedback["leaking_route_summaries"][0]["kill_count"] == 1
    assert feedback["clean_route_count"] == 1
    assert "DAMAGE" not in encoded
    assert len(encoded) < 140000
