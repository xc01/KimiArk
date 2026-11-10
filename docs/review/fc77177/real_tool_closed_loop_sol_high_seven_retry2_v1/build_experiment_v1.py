#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import gzip
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry2_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-retry2-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("independent retry2 experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE / "input_bundle", BUNDLE, dirs_exist_ok=True)
    shutil.copyfile(SOURCE / "service_fault_report_v1.json", BUNDLE / "prior_start_fault_report_v1.json")
    shutil.copyfile(SOURCE / "zero_model_handshake_root_cause_v1.json", BUNDLE / "prior_start_root_cause_v1.json")

    manifest_files = []
    for path in sorted(path for path in BUNDLE.rglob("*") if path.is_file() and path.name != "bundle_manifest_v1.json"):
        entry = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        if path.suffix == ".gz":
            entry["restored_sha256"] = restored_digest(path)
        manifest_files.append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY2_INPUT_BUNDLE_MANIFEST_V1",
        "files": manifest_files,
    })

    config_path = DEST / "session_config_v1.json"
    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R94_SOL_HIGH_SEVEN_RETRY2_",
        "plan_label": "SOL_HIGH_SEVEN_RETRY2",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "facts_source_dir": BUNDLE.as_posix(),
        "session_root": (DEST / "session").as_posix(),
        "budget_path": (DEST / "simulation_budget_v1.json").as_posix(),
        "candidate_ledger_path": (DEST / "candidate_ledger_v1.json").as_posix(),
        "authorization_config_path": (DEST / "model_authorization_v1.json").as_posix(),
        "max_unique_deployed_operators": 7,
        "max_candidates": 2,
        "max_check_calls": 10,
        "max_real_cli_starts": 1,
        "simulation_timeout_seconds": 3600,
        "execution_backend": "CONTROLLED_RUNNER",
        "allow_fake_execution": False,
    }
    write_json(config_path, config)
    write_json(DEST / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": "main_08-07",
        "max_stage_simulations": 2,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(DEST / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "max_check_calls": 10,
        "used_check_calls": 0,
        "max_candidates": 2,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    })

    extra = [
        "features.apps=false",
        f'mcp_servers.kimiark.command="{ROOT / ".venv/bin/python"}"',
        f'mcp_servers.kimiark.args=["{ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"}","{config_path}"]',
        "mcp_servers.kimiark.required=true",
        'mcp_servers.kimiark.default_tools_approval_mode="approve"',
        'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]',
    ]
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "budget_boundary": "User authorized one fresh retry2 Sol CLI with two complete simulations; prior CLI failure and budgets remain closed.",
        "provider": "openai",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "real_cli_starts": {
            "authorized_real_cli_starts": 1,
            "used_real_cli_starts": 0,
            "automatic_retry": False,
            "automatic_resume": False,
            "model_change_or_tier_change_forbidden": True,
        },
        "extra_config_values": extra,
    })

    prompt_text = (SOURCE / "session/codex_cli/sol_prompt_v1.txt").read_text()
    prompt_text = prompt_text.replace(
        "real_tool_closed_loop_sol_high_seven_retry_v1",
        "real_tool_closed_loop_sol_high_seven_retry2_v1",
    )
    prompt_text += """

Prior start recovery boundary: retry1 failed before any tactical request because Codex `mcp_servers.kimiark.args` omitted the service script path; the JSON config was interpreted as Python. This retry2 session uses corrected args and is a fresh ledger. Evidence is under `input_bundle/prior_start_fault_report_v1.json` and `input_bundle/prior_start_root_cause_v1.json`. Do not troubleshoot network or reuse old budget.
"""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")


if __name__ == "__main__":
    main()
