from __future__ import annotations

import json
import tempfile
from pathlib import Path

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
    original = runner.PLAN_LABEL
    try:
        runner.PLAN_LABEL = "R8-2-V6"
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
        assert "R8-2-V6 must retain the zero-leak result" in prompt
        assert "every protected target arrives" in prompt
    finally:
        runner.PLAN_LABEL = original


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
    (tmp_path / "final_status.json").write_text(json.dumps({"plan_id": "R8_2_GPT_V10"}))
    feedback = runner.compact_diagnostic_feedback(summary_path)
    encoded = json.dumps(feedback)

    assert feedback["result_metrics"]["enemies_leaked"] == 10
    assert feedback["source_plan_id"] == "R8_2_GPT_V10"
    assert feedback["leaking_route_summaries"][0]["block_count"] == 1
    assert feedback["leaking_route_summaries"][0]["kill_count"] == 1
    assert feedback["clean_route_count"] == 1
    assert "DAMAGE" not in encoded
    assert len(encoded) < 140000


def test_prompt_injects_structural_tactical_feedback_without_changing_plan_identity() -> None:
    original = (runner.PLAN_ID, runner.PLAN_LABEL)
    try:
        runner.PLAN_ID = "R8_2_GPT_V9"
        runner.PLAN_LABEL = "R8-2-V9"
        prompt = runner.build_prompt({
            "stage_active_facts": {"roadblock_plan_tiles_row_col": [[2, 5], [4, 7]]},
            "prior_tactical_feedback": {
                "causal_interpretation": "opening survival failure broke the conditional economic dependency",
                "design_freedom": "GPT may change any tactical decision",
            },
        })
        assert "prior_tactical_feedback is the verified causal history" in prompt
        assert "survival/handoff failures, not arithmetic bugs" in prompt
        assert '"operational_plan_id": "R8_2_GPT_V9"' in prompt
    finally:
        runner.PLAN_ID, runner.PLAN_LABEL = original


def test_static_conflict_feedback_is_structured_and_not_battle_result(tmp_path: Path) -> None:
    revision_source = tmp_path / "candidate"
    revision_source.mkdir()
    (revision_source / "llm_structured_output.json").write_text(json.dumps({
        "revised_operational_plans": [{"operational_plan_id": "R8_2_GPT_V13"}]
    }))
    static_path = tmp_path / "static_compile_results.json"
    static_path.write_text(json.dumps({
        "conflicts": [{
            "conflict": "INSUFFICIENT_DP", "frame": 2823,
            "operator_id": "char_283_midn", "cost": 16, "balance_before": 15.1,
        }],
        "checks": {"deployment": [{"action_index": 4, "frame": 2823, "operator_id": "char_283_midn"}]},
        "dp_ledger": {
            "entries": [{"event": "NATURAL_DP", "frame": 1500, "delta": 1.0}],
            "automatic_skill_income_model": {"conditions": ["operator survives"]},
        },
    }))
    feedback = runner.build_static_feedback(revision_source, static_path)

    assert feedback["source_plan_id"] == "R8_2_GPT_V13"
    assert feedback["simulation_status"] == "NO_SIMULATION"
    conflict = feedback["conflicts"][0]
    assert conflict["candidate_plan_id"] == "R8_2_GPT_V13"
    assert conflict["action_index"] == 4
    assert conflict["required_value"] == 16
    assert conflict["available_value"] == 15.1
    assert conflict["previous_economic_events"][0]["frame"] == 1500
    assert conflict["battle_result_status"] == "NO_SIMULATION"


def test_missing_branch_state_does_not_block_completed_result_postprocessing(tmp_path: Path) -> None:
    original = runner.STAGE_ID
    runner.STAGE_ID = "main_test"
    try:
        path = tmp_path / "missing.json"
        state = runner.load_or_init_branch_state(path)
        assert state["schema_version"] == runner.experience.BRANCH_SCHEMA_VERSION
        assert state["stage_id"] == "main_test"
        assert state["candidates"] == []
    finally:
        runner.STAGE_ID = original


def test_prompt_keeps_static_and_battle_feedback_sources_distinct() -> None:
    prompt = runner.build_prompt({
        "stage_active_facts": {"roadblock_plan_tiles_row_col": [[2, 5], [4, 7]]},
        "prior_diagnostic_feedback": {"source_plan_id": "R8_2_GPT_V10", "result_metrics": {}},
        "prior_tactical_feedback": {
            "source_plan_id": "R8_2_GPT_V10",
            "causal_interpretation": "late blocker death shifted route pressure",
        },
        "prior_static_feedback": {
            "source_plan_id": "R8_2_GPT_V12",
            "battle_feedback_source_plan_id": "R8_2_GPT_V10",
            "simulation_status": "NO_SIMULATION",
            "conflicts": [{
                "candidate_plan_id": "R8_2_GPT_V12", "action_index": 4,
                "frame": 2823, "operator_id": "char_283_midn",
                "required_value": 16, "available_value": 15.1,
            }],
        },
    })
    assert '"candidate_plan_id":"R8_2_GPT_V12"' in prompt
    assert '"required_value":16' in prompt
    assert '"available_value":15.1' in prompt
    assert '"source_plan_id":"R8_2_GPT_V10"' in prompt
    assert '"battle_feedback_source_plan_id":"R8_2_GPT_V10"' in prompt
    assert '"battle_result_status":"NO_SIMULATION"' not in prompt
    assert "NO_SIMULATION" in prompt
