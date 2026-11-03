from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import kimiark_tactical_stdio_service_v1 as service
import run_kimiark_real_tool_closed_loop_v1 as closed_loop


REPO_ROOT = Path(__file__).resolve().parents[1]
V3_DIR = REPO_ROOT / "docs/review/fc77177/real_tool_closed_loop_terra_v3"


def test_terra_v3_has_separate_20_check_and_5_run_quotas() -> None:
    config = service.load_session_config(V3_DIR / "session_config_v1.json")
    budget = service.load_json(V3_DIR / "simulation_budget_v1.json")
    ledger = service.load_json(V3_DIR / "candidate_ledger_v1.json")

    assert config.session_id == "real-tool-loop-terra-v3"
    assert config.model == "gpt-6.1-terra"
    assert config.reasoning_effort == "medium"
    assert config.max_unique_deployed_operators == 7
    assert config.max_check_calls == 20
    assert config.max_candidates == 5
    assert config.execution_backend == "CONTROLLED_RUNNER"
    assert config.allow_fake_execution is False
    assert budget["max_stage_simulations"] == 5
    assert budget["started_stage_simulations"] == 0
    assert ledger["max_check_calls"] == 20
    assert ledger["used_check_calls"] == 0
    assert ledger["max_candidates"] == 5
    assert ledger["used_candidates"] == 0


def test_terra_v3_cli_uses_verified_scoped_mcp_registration() -> None:
    command = closed_loop.build_command(
        V3_DIR / "model_authorization_v1.json",
        V3_DIR / "session" / "codex_cli" / "codex_final_message.txt",
    )
    overrides = {
        command[index + 1].split("=", 1)[0]: command[index + 1].split("=", 1)[1]
        for index, value in enumerate(command)
        if value == "-c" and index + 1 < len(command)
    }
    assert overrides["mcp_servers.kimiark.default_tools_approval_mode"] == '"approve"'
    assert overrides["mcp_servers.kimiark.enabled_tools"] == '["get_session_status","check_plan","run_simulation","query_events"]'
    assert "--approve-for-me" not in command
    assert command[command.index("--sandbox") + 1] == "read-only"
