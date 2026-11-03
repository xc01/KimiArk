from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import kimiark_tactical_stdio_service_v1 as service
import run_kimiark_real_tool_closed_loop_v1 as closed_loop


REPO_ROOT = Path(__file__).resolve().parents[1]
V2_DIR = REPO_ROOT / "docs/review/fc77177/real_tool_closed_loop_terra_v2"


def test_terra_v2_caps_precheck_and_final_usage() -> None:
    config = service.load_session_config(V2_DIR / "session_config_v1.json")
    budget = service.load_json(V2_DIR / "simulation_budget_v1.json")
    ledger = service.load_json(V2_DIR / "candidate_ledger_v1.json")
    precheck = service.load_json(V2_DIR / "mcp_no_model_status_transcript_v1.json")

    assert config.session_id == "real-tool-loop-terra-v2"
    assert config.model == "gpt-6.1-terra"
    assert config.reasoning_effort == "medium"
    assert config.max_unique_deployed_operators == 7
    assert config.max_candidates == 2
    assert config.execution_backend == "CONTROLLED_RUNNER"
    assert config.allow_fake_execution is False
    assert budget["max_stage_simulations"] == 2
    assert ledger["max_candidates"] == 2
    assert precheck[-1]["summary"]["remaining_candidates"] == 2
    assert precheck[-1]["summary"]["remaining_simulations"] == 2
    assert budget["started_stage_simulations"] == 1
    assert ledger["used_candidates"] == 2
    assert [(item["check_status"], item["simulation_status"]) for item in ledger["attempts"]] == [
        ("PASS", "COMPLETED"),
        ("FAIL", "NOT_STARTED"),
    ]


def test_terra_v2_cli_registers_only_four_preapproved_mcp_tools() -> None:
    command = closed_loop.build_command(
        V2_DIR / "model_authorization_v1.json",
        V2_DIR / "session" / "codex_cli" / "codex_final_message.txt",
    )
    overrides = {
        command[index + 1].split("=", 1)[0]: command[index + 1].split("=", 1)[1]
        for index, value in enumerate(command)
        if value == "-c" and index + 1 < len(command)
    }

    assert overrides["model_provider"] == '"openai"'
    assert overrides["features.apps"] == "false"
    assert overrides["mcp_servers.kimiark.required"] == "true"
    assert overrides["mcp_servers.kimiark.default_tools_approval_mode"] == '"approve"'
    assert overrides["mcp_servers.kimiark.enabled_tools"] == '["get_session_status","check_plan","run_simulation","query_events"]'
    assert "--approve-for-me" not in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert command[command.index("--sandbox") + 1] == "read-only"
