from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pytest

import run_gpt_tactical_stage_session_v1 as runner
import run_r8_1_gpt_c4_codex_cli_v1 as codex_runner
from codex_model_authorization_v1 import validate_cli_authorization


M49_AUTHORIZATION_CONFIG = "docs/review/fc77177/m49_roster_reduction_win_v1/m49_model_authorization_v1.json"


@pytest.fixture()
def runner_module_state():
    tracked_runner_globals = {
        name: getattr(runner, name)
        for name in (
            "OUT", "DIAGNOSTIC_OUT", "SOURCE", "STAGE_ID", "PLAN_ID", "PLAN_PREFIX",
            "PLAN_LABEL", "SAVED_INPUT_DIR", "MAX_UNIQUE_DEPLOYED_OPERATORS",
            "AUTHORIZATION_CONFIG_PATH", "SIMULATION_BUDGET_PATH",
        )
    }
    tracked_codex_globals = {
        name: getattr(codex_runner, name)
        for name in ("OUT", "MODEL", "REASONING_EFFORT", "AUTHORIZATION_CONFIG_PATH")
    }
    yield
    for name, value in tracked_runner_globals.items():
        setattr(runner, name, value)
    for name, value in tracked_codex_globals.items():
        setattr(codex_runner, name, value)


def make_arguments(tmp_path: Path, *, saved_input_dir: str | None = None, max_unique: int | None = None) -> argparse.Namespace:
    output_dir = str(tmp_path / "output")
    diagnostic_dir = str(tmp_path / "diagnostic")
    return argparse.Namespace(
        stage_id="main_test_stage", facts_dir=str(tmp_path / "facts"),
        output_dir=output_dir, diagnostic_output_dir=diagnostic_dir,
        plan_id="TEST_GPT_V1", plan_label="TEST-V1", plan_id_prefix="TEST_GPT_V",
        cli_attempt=1, prior_cli_starts=0, extra_config=["features.apps=false"],
        revision_source=None, diagnostic_summary=None, tactical_feedback=None,
        static_conflict_summary=None, saved_input_dir=saved_input_dir,
        experience_store=None, branch_state=None,
        max_unique_deployed_operators=max_unique,
        authorization_config=M49_AUTHORIZATION_CONFIG,
        simulation_budget_path="docs/review/fc77177/m28_simulation_budget_v1.json",
    )


def make_catalog() -> list[dict]:
    ordinary = [
        {
            "operator_id": "char_test",
            "identity": {"rarity": 2, "position": "MELEE"},
            "qualification": {"normal_mode": True},
        }
    ]
    ordinary.extend(
        {
            "operator_id": f"char_ordinary_{index}",
            "identity": {"rarity": 2, "position": "MELEE"},
            "qualification": {"normal_mode": True},
        }
        for index in range(16)
    )
    ordinary.extend(
        {
            "operator_id": f"char_three_star_{index}",
            "identity": {"rarity": 3, "position": "MELEE"},
            "qualification": {"normal_mode": True},
        }
        for index in range(17)
    )
    return ordinary


def make_stage_evidence(stage_id: str) -> dict:
    catalog = make_catalog()
    return {
        "stage_id": stage_id,
        "normal_low_star_catalog": catalog,
        "source_routes": [{"route": "route-1"}],
        "source_wave_schedule": [{"frame": 1}],
        "stage_mechanism_support": {"runtime_adapter_status": "SUPPORTED"},
        "stage_active_facts": {"roadblock_plan_tiles_row_col": [[1, 2]]},
        "output_schema": {},
    }


def make_saved_input(root: Path, *, include_limit: bool, limit: int | None = 10) -> Path:
    saved = root / "saved_input"
    saved.mkdir()
    evidence = {
        "stage_id": "main_saved_stage",
        "normal_low_star_catalog": make_catalog(),
        "stage_active_facts": {
            "roadblock_tiles_col_row": [], "active_device_tiles_col_row": [],
            "deployable_ground_tiles_col_row": [(0, 0)],
        },
    }
    if include_limit:
        evidence["milestone_constraints"] = {"max_unique_deployed_operator_ids": limit}
    evidence_path = saved / "llm_evidence_context.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    (saved / "codex_prompt.txt").write_text("SAVED PROMPT\n", encoding="utf-8")
    (saved / "revision_output_schema.json").write_text("{}", encoding="utf-8")
    (saved / "evidence_completeness.json").write_text("{}", encoding="utf-8")
    return saved


def make_execution() -> dict:
    return {"trajectory": {"session_ids": ["test-session"], "thread_ids": [], "usage_records": []}}


def make_response(plan_id: str, operator_ids: list[str]) -> dict:
    return {
        "revised_operational_plans": [{
            "operational_plan_id": plan_id,
            "parent_hypothesis_id": "hyp",
            "tactical_thesis": "test",
            "selected_low_star_operator_ids": operator_ids,
            "deployment_positions_and_directions": [],
            "formation_structure": [],
            "formation_transitions": [],
            "corridor_responsibilities": [],
            "pressure_window_responsibilities": [],
            "skill_intents": [],
            "mandatory_tactical_invariants": [],
            "battle_phases": [],
            "action_timeline": [{
                "action_type": "DEPLOY", "frame": 100, "operator_id": operator_ids[0],
                "tile": [0, 0], "direction": "UP",
            }],
        }],
        "revised_stage_understanding": {},
        "revised_tactical_requirements": [],
        "revised_strategic_hypotheses": [{"hypothesis_id": "hyp"}],
        "revision_hypothesis": {"operational_plan_id": plan_id},
    }


def test_saved_input_roster_limit_completes_prepare_prompt_and_final_validation(
    tmp_path: Path, runner_module_state
) -> None:
    saved = make_saved_input(tmp_path, include_limit=False)
    runner.configure(make_arguments(tmp_path, saved_input_dir=str(saved), max_unique=10))
    prepared = runner.prepare()
    evidence = runner.load(codex_runner.OUT / "llm_evidence_context.json")
    resolution = runner.load(codex_runner.OUT / "milestone_constraints_resolution.json")
    command = codex_runner.build_command(codex_runner.OUT / "codex_final_message.txt")

    assert runner.MAX_UNIQUE_DEPLOYED_OPERATORS == 10
    assert evidence["milestone_constraints"]["max_unique_deployed_operator_ids"] == 10
    assert resolution["source"] == "CONFIGURED_ARGUMENT"
    assert resolution["saved_input_limit"] is None
    assert resolution["prompt_regenerated"] is True
    assert runner.roster_prompt_instruction(10) in prepared["prompt"]
    assert runner.roster_prompt_instruction(10) in (codex_runner.OUT / "codex_prompt.txt").read_text(encoding="utf-8")
    assert (saved / "codex_prompt.txt").read_bytes() == (codex_runner.OUT / "codex_prompt.txt").read_bytes().split(b"\n\n", 1)[1]
    assert validate_cli_authorization(codex_runner.AUTHORIZATION_CONFIG_PATH, command)["status"] == "AUTHORIZED"

    passing = make_response("TEST_GPT_V1", ["char_test"])
    validation = runner.validate_final(passing, make_execution())
    assert validation["status"] == "PASS"

    failing = make_response("TEST_GPT_V1", [f"char_extra_{index}" for index in range(11)])
    with pytest.raises(SystemExit, match="hard limit is 10"):
        runner.validate_final(failing, make_execution())


def test_saved_input_limit_conflicts_are_rejected(tmp_path: Path, runner_module_state) -> None:
    saved = make_saved_input(tmp_path, include_limit=True, limit=11)
    runner.configure(make_arguments(tmp_path, saved_input_dir=str(saved), max_unique=10))
    with pytest.raises(RuntimeError, match="roster-limit conflict"):
        runner.prepare()


def test_saved_input_limit_without_configured_limit_is_rejected(tmp_path: Path, runner_module_state) -> None:
    saved = make_saved_input(tmp_path, include_limit=True, limit=10)
    runner.configure(make_arguments(tmp_path, saved_input_dir=str(saved), max_unique=None))
    with pytest.raises(RuntimeError, match="pass the same --max-unique-deployed-operators"):
        runner.prepare()


def test_saved_prompt_limit_without_effective_limit_is_rejected(tmp_path: Path, runner_module_state) -> None:
    saved = make_saved_input(tmp_path, include_limit=False)
    (saved / "codex_prompt.txt").write_text("HARD ROSTER LIMIT: at most 10\n\nSAVED PROMPT\n", encoding="utf-8")
    runner.configure(make_arguments(tmp_path, saved_input_dir=str(saved), max_unique=None))
    with pytest.raises(RuntimeError, match="no configured or evidence limit"):
        runner.prepare()


def test_normal_input_defaults_to_no_roster_constraint(tmp_path: Path, runner_module_state) -> None:
    source = tmp_path / "facts"
    source.mkdir()
    evidence = make_stage_evidence("main_test_stage")
    (source / "llm_evidence_context.json").write_text(json.dumps(evidence), encoding="utf-8")
    runner.configure(make_arguments(tmp_path, max_unique=None))
    prepared = runner.prepare()
    prepared_evidence = runner.load(codex_runner.OUT / "llm_evidence_context.json")
    resolution = runner.load(codex_runner.OUT / "milestone_constraints_resolution.json")

    assert runner.MAX_UNIQUE_DEPLOYED_OPERATORS is None
    assert "milestone_constraints" not in prepared_evidence
    assert resolution["effective_limit"] is None
    assert "HARD ROSTER LIMIT:" not in prepared["prompt"]


def test_selected_and_deploy_union_counts_redeployment_once() -> None:
    plan = {
        "selected_low_star_operator_ids": ["char_a"],
        "action_timeline": [
            {"action_type": "DEPLOY", "operator_id": "char_b"},
            {"action_type": "RETREAT", "operator_id": "char_b"},
            {"action_type": "DEPLOY", "operator_id": "char_b"},
        ],
    }
    assert runner.distinct_deployed_operator_ids(plan) == {"char_a", "char_b"}


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
