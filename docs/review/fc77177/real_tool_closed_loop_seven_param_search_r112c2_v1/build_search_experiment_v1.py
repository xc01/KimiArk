#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_window_mechanism_v1"
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_seven_param_search_r112c2_v1"
SESSION_ID = "real-tool-loop-seven-param-search-r112c2-v1"
PLAN_PREFIX = "R113_SEVEN_PARAM_SEARCH_R112C2_"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if EXPERIMENT.exists() and (EXPERIMENT / "session_config_v1.json").exists():
        raise RuntimeError("R113 search experiment already exists")
    (EXPERIMENT / "input_bundle").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / "input_bundle/llm_evidence_context.json", EXPERIMENT / "input_bundle/llm_evidence_context.json")
    shutil.copyfile(SOURCE / "input_bundle/revision_output_schema.json", EXPERIMENT / "input_bundle/revision_output_schema.json")
    shutil.copyfile(SOURCE / "session/candidates/candidate-002/source/llm_structured_output.json", EXPERIMENT / "input_bundle/r112_c002_structured_plan.json")
    shutil.copyfile(SOURCE / "session/candidates/candidate-002/simulation/plan_snapshot.json", EXPERIMENT / "input_bundle/r112_c002_plan_snapshot.json")
    shutil.copyfile(SOURCE / "session/candidates/candidate-002/simulation/action_snapshot.json", EXPERIMENT / "input_bundle/r112_c002_action_snapshot.json")
    shutil.copyfile(SOURCE / "session/candidates/candidate-002/simulation/final_status.json", EXPERIMENT / "input_bundle/r112_c002_final_status.json")
    shutil.copyfile(SOURCE / "input_bundle/bundle_manifest_v1.json", EXPERIMENT / "input_bundle/r112_source_bundle_manifest_v1.json")
    session_config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "execution_backend": "CONTROLLED_RUNNER",
        "allow_fake_execution": False,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "max_real_cli_starts": 0,
        "max_check_calls": 100,
        "max_candidates": 100,
        "max_unique_deployed_operators": 7,
        "simulation_timeout_seconds": 3600,
        "plan_id_prefix": PLAN_PREFIX,
        "plan_label": "SEVEN_PARAM_SEARCH_R112C2",
        "authorization_config_path": str(EXPERIMENT / "model_authorization_v1.json"),
        "budget_path": str(EXPERIMENT / "simulation_budget_v1.json"),
        "candidate_ledger_path": str(EXPERIMENT / "candidate_ledger_v1.json"),
        "facts_source_dir": str(EXPERIMENT / "input_bundle"),
        "session_root": str(EXPERIMENT / "session"),
    }
    write_json(EXPERIMENT / "session_config_v1.json", session_config)
    write_json(EXPERIMENT / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "provider": "openai",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "budget_boundary": "User authorized zero tactical CLI and up to 100 complete fixed simulations including baseline rerun and final verification; R112 balances remain closed.",
        "real_cli_starts": {"authorized_real_cli_starts": 0, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True},
    })
    write_json(EXPERIMENT / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": "main_08-07",
        "max_stage_simulations": 100,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(EXPERIMENT / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "max_check_calls": 100,
        "max_candidates": 100,
        "used_check_calls": 0,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    })


if __name__ == "__main__":
    main()
