from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

import kimiark_mcp_server as server
import tactical_evaluation_gate_v1 as gate


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = "output/r8_1_r8_7_batch_v1/main_08-07/m26_tactical_revision_v1/attempt_04_cli"


def _budget_path(name: str) -> Path:
    directory = ROOT / "output" / name
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    path = directory / "budget.json"
    path.write_text(json.dumps({
        "schema_version": gate.BUDGET_SCHEMA_VERSION,
        "stage_id": "main_08-07", "max_stage_simulations": 0,
        "prior_stage_simulations": 0, "started_stage_simulations": 0,
    }))
    return path


def _rpc(message: dict) -> str:
    return json.dumps(message, separators=(",", ":"))


def test_mcp_stdio_handshake_tools_and_experience_call() -> None:
    input_text = "\n".join([
        _rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        _rpc({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
        _rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        _rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "query_applicable_experience",
            "arguments": {
                "experience_store": "docs/review/fc77177/m26_tactical_experience_records_v1.json",
                "stage_id": "main_08-07",
                "mechanics_version": "m23-behavioral-mechanics-v1",
                "failure_category": "LEGAL_BATTLE_LOSS",
                "responsibility_tags": ["protected_target"],
            },
        }}),
    ]) + "\n"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/kimiark_mcp_server.py")],
        input=input_text, text=True, capture_output=True, check=True, cwd=ROOT,
    )
    lines = [json.loads(line) for line in completed.stdout.splitlines()]
    assert lines[0]["result"]["serverInfo"]["name"] == "kimiark-tactical-loop"
    assert {tool["name"] for tool in lines[1]["result"]["tools"]} >= {
        "get_mechanism_facts", "query_applicable_experience", "check_plan_contract",
        "prepare_frozen_plan_evaluation", "evaluate_frozen_plan", "get_status_and_feedback",
    }
    structured = lines[2]["result"]["structuredContent"]
    assert structured["limit"] == 3
    assert len(structured["records"]) <= 3
    assert all(record["status"] != "INVALIDATED" for record in structured["records"])


def test_frozen_evaluation_budget_gate_is_enforced(tmp_path: Path) -> None:
    budget_path = _budget_path("test_mcp_budget_gate")
    result = server.prepare_frozen_plan_evaluation({
        "source_dir": SOURCE_DIR,
        "diagnostic_output_dir": str((budget_path.parent / "diagnostic").relative_to(ROOT)),
        "budget_path": str(budget_path.relative_to(ROOT)),
    })
    assert result["status"] == "BUDGET_EXHAUSTED"
    assert result["remaining_stage_simulations"] == 0


def test_evaluate_frozen_plan_rejects_without_subprocess(tmp_path: Path) -> None:
    budget_path = _budget_path("test_mcp_budget_evaluate")
    with mock.patch.object(server.subprocess, "run") as run:
        result = server.evaluate_frozen_plan({
            "source_dir": SOURCE_DIR,
            "diagnostic_output_dir": str((budget_path.parent / "diagnostic").relative_to(ROOT)),
            "budget_path": str(budget_path.relative_to(ROOT)),
            "stage_id": "main_08-07", "plan_id": "PLAN", "plan_label": "PLAN", "plan_id_prefix": "PLAN",
        })
        assert result["status"] == "BUDGET_EXHAUSTED"
        assert result["simulation_started"] is False
        assert run.call_count == 0
