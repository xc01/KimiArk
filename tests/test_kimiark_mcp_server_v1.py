from __future__ import annotations

import json
import shutil
import hashlib
import subprocess
import sys
import pytest
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
        "stage_id": "main_08-07", "plan_id": "R8_7_GPT_M26_V3",
    })
    assert result["status"] == "BUDGET_EXHAUSTED"
    assert result["remaining_stage_simulations"] == 0


def test_mcp_plan_contract_runs_schema_semantic_event_and_static_layers() -> None:
    result = server.check_plan_contract({"source_dir": SOURCE_DIR})
    assert result["status"] == "PASS"
    assert result["layers"]["schema_errors"] == []
    assert result["layers"]["semantic_errors"] == []
    assert result["layers"]["event_query_errors"] == []
    assert result["layers"]["static_errors"] == []
    for name, digest in result["input_sha256"].items():
        assert digest == hashlib.sha256((ROOT / SOURCE_DIR / name).read_bytes()).hexdigest()


def test_mcp_plan_contract_rejects_missing_revision_hypothesis() -> None:
    source = ROOT / "output/test_mcp_contract_missing_revision"
    shutil.rmtree(source, ignore_errors=True)
    source.mkdir(parents=True)
    for name in ("llm_structured_output.json", "llm_evidence_context.json", "revision_output_schema.json"):
        (source / name).write_bytes((ROOT / SOURCE_DIR / name).read_bytes())
    structured = json.loads((source / "llm_structured_output.json").read_text())
    structured.pop("revision_hypothesis", None)
    (source / "llm_structured_output.json").write_text(json.dumps(structured))
    result = server.check_plan_contract({"source_dir": str(source.relative_to(ROOT))})
    assert result["status"] == "FAIL"
    assert result["layers"]["schema_errors"]
    assert result["layers"]["semantic_errors"] == []
    shutil.rmtree(source)


def test_shared_gate_binds_plan_and_stage_and_rejects_used_output() -> None:
    budget_path = _budget_path("test_shared_gate_binding")
    source = ROOT / "output/test_shared_gate_source"
    output = ROOT / "output/test_shared_gate_output"
    shutil.rmtree(source, ignore_errors=True)
    shutil.rmtree(output, ignore_errors=True)
    source.mkdir(parents=True)
    (source / "llm_plan_validation.json").write_text(json.dumps({"status": "PASS"}))
    (source / "static_compile_results.json").write_text(json.dumps({"conflicts": []}))
    (source / "llm_structured_output.json").write_text(json.dumps({
        "revised_operational_plans": [{"operational_plan_id": "PLAN_A"}]
    }))
    (source / "llm_evidence_context.json").write_text(json.dumps({
        "model_spawn_timeline": {"events": [
            {"enemy_id": "enemy_3001_upeopl"}, {"enemy_id": "enemy_3001_upeopl"}
        ]}
    }))
    budget = json.loads(budget_path.read_text())
    budget.update({"max_stage_simulations": 1, "prior_stage_simulations": 0, "started_stage_simulations": 0})
    budget_path.write_text(json.dumps(budget))
    with pytest.raises(RuntimeError, match="frozen plan identity mismatch"):
        gate.prepare_evaluation(
            source_dir=source, diagnostic_output_dir=output, budget_path=budget_path,
            stage_id="main_08-07", expected_plan_id="PLAN_B",
        )
    result = gate.prepare_evaluation(
        source_dir=source, diagnostic_output_dir=output, budget_path=budget_path,
        stage_id="main_08-07", expected_plan_id="PLAN_A",
    )
    assert result["expected_protected_target_count"] == 2
    output.mkdir()
    (output / "simulation_reservation.json").write_text(json.dumps({"status": "RESERVED"}))
    with pytest.raises(RuntimeError, match="non-empty diagnostic output"):
        gate.prepare_evaluation(
            source_dir=source, diagnostic_output_dir=output, budget_path=budget_path,
            stage_id="main_08-07", expected_plan_id="PLAN_A",
        )
    shutil.rmtree(source)
    shutil.rmtree(output)


def test_evaluate_frozen_plan_rejects_without_subprocess(tmp_path: Path) -> None:
    budget_path = _budget_path("test_mcp_budget_evaluate")
    with mock.patch.object(server.subprocess, "run") as run:
        result = server.evaluate_frozen_plan({
            "source_dir": SOURCE_DIR,
            "diagnostic_output_dir": str((budget_path.parent / "diagnostic").relative_to(ROOT)),
            "budget_path": str(budget_path.relative_to(ROOT)),
            "stage_id": "main_08-07", "plan_id": "R8_7_GPT_M26_V3",
            "plan_label": "PLAN", "plan_id_prefix": "PLAN",
        })
        assert result["status"] == "BUDGET_EXHAUSTED"
        assert result["simulation_started"] is False
        assert run.call_count == 0
