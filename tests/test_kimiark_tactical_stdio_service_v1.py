from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import kimiark_tactical_stdio_service_v1 as service


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _support_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, model: str = "gpt-test", effort: str = "medium"
) -> dict[str, Path]:
    service.ROOT = tmp_path
    monkeypatch.setattr(service.gate, "ROOT", tmp_path)
    facts = tmp_path / "facts"
    budget = tmp_path / "budget.json"
    ledger = tmp_path / "candidates.json"
    authorization = tmp_path / "authorization.json"
    config_path = tmp_path / "session-config.json"
    session_root = tmp_path / "session"
    _write_json(facts / "llm_evidence_context.json", {"m58_open_roster_policy": False})
    _write_json(facts / "revision_output_schema.json", {"type": "object"})
    _write_json(authorization, {"model": model, "reasoning_effort": effort})
    _write_json(budget, {
        "schema_version": service.gate.BUDGET_SCHEMA_VERSION,
        "stage_id": "stage", "max_stage_simulations": 1,
        "prior_stage_simulations": 0, "started_stage_simulations": 0,
    })
    _write_json(ledger, {
        "schema_version": service.CANDIDATE_LEDGER_SCHEMA_VERSION,
        "session_id": "test-session", "max_candidates": 2,
        "used_candidates": 0, "attempts": [],
    })
    _write_json(config_path, {
        "schema_version": service.CONFIG_SCHEMA_VERSION,
        "session_id": "test-session", "stage_id": "stage",
        "plan_id_prefix": "PLAN_", "plan_label": "PLAN", "model": model,
        "reasoning_effort": effort, "features_apps": False,
        "mechanics_version": service.ACTIVE_MECHANICS_VERSION,
        "facts_source_dir": "facts", "session_root": "session",
        "budget_path": "budget.json", "candidate_ledger_path": "candidates.json",
        "authorization_config_path": "authorization.json",
        "max_unique_deployed_operators": 1, "max_candidates": 2,
        "simulation_timeout_seconds": 60,
    })
    config = service.load_session_config(config_path)
    return {
        "config": config_path,
        "facts": facts,
        "budget": budget,
        "ledger": ledger,
        "authorization": authorization,
        "session_root": session_root,
    }


def _plan(operation_id: str = "PLAN_A") -> dict[str, Any]:
    return {
        "revised_operational_plans": [{
            "operational_plan_id": operation_id,
            "parent_plan_id": "PARENT",
            "action_timeline": [
                {"action_type": "DEPLOY", "operator_id": "op_a", "frame": 1, "tile": [0, 0]},
                {"action_type": "DEPLOY", "operator_id": "op_b", "frame": 2, "tile": [1, 0]},
            ],
            "selected_low_star_operator_ids": ["op_a", "op_b"],
        }],
        "revision_hypothesis": {"parent_plan_id": "PARENT", "operational_plan_id": operation_id},
    }


def _pass_layers() -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    return {
        "schema_errors": [], "semantic_errors": [], "event_query_errors": [],
    }, [], {
        "schema_version": "TEST", "status": "PASS", "checked_operator_ids": [],
        "errors": [], "roster_errors": [],
    }


def test_check_plan_counts_invalid_candidate_without_simulation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    result = service.check_plan(paths["config"], {"plan": {"revised_operational_plans": [{"operational_plan_id": "BAD"}]}})
    assert result["status"] == "FAIL"
    assert result["candidate_counted"] is True
    assert result["simulation_started"] is False
    ledger = service.load_json(paths["ledger"])
    assert ledger["used_candidates"] == 1
    assert ledger["attempts"][0]["simulation_status"] == "NOT_STARTED"


def test_roster_limit_rejects_before_static_result_can_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "validate_plan_payload", lambda plan, evidence, schema: {"schema_errors": [], "semantic_errors": [], "event_query_errors": []})
    monkeypatch.setattr(service, "validate_parent_hypothesis_reference", lambda plan: [])
    monkeypatch.setattr(service, "validate_normal_low_star_capability_source", lambda evidence: [])
    monkeypatch.setattr(service, "validate_execution_input", lambda evidence, parsed: [])
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    result = service.check_plan(paths["config"], {"plan": _plan()})
    assert result["status"] == "FAIL"
    assert any("hard limit is 1" in error for error in result["errors"])


def test_run_simulation_uses_injected_controlled_executor_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    check = service.check_plan(paths["config"], {"plan": _plan()})
    assert check["status"] == "PASS"
    calls: list[tuple[Path, Path, str]] = []

    def fake_executor(config, source_dir, output_dir, plan_id):
        calls.append((source_dir, output_dir, plan_id))
        output_dir.mkdir(parents=True, exist_ok=True)
        service.atomic_write_json(output_dir / "simulation_attempt.json", {"status": "COMPLETED", "result_saved": True})
        service.atomic_write_json(output_dir / "manifest.json", {"plan_id": plan_id})
        service.atomic_write_json(output_dir / "diagnostic_summary.json", {"result": {"win": True}})
        service.atomic_write_json(output_dir.with_name(output_dir.name + ".simulation_reservation.json"), {"status": "COMPLETED"})
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    result = service.run_simulation(paths["config"], {
        "candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"],
    }, executor=fake_executor)
    assert result["status"] == "COMPLETED"
    assert result["simulation_started_counted"] is True
    assert len(calls) == 1
    repeat = service.run_simulation(paths["config"], {
        "candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"],
    }, executor=fake_executor)
    assert repeat["status"] == "IDEMPOTENT_COMPLETED"
    assert len(calls) == 1


def test_preflight_failure_does_not_mark_started_or_count_simulation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    check = service.check_plan(paths["config"], {"plan": _plan()})
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("static gate failure")
    monkeypatch.setattr(service.gate, "prepare_evaluation", fail)
    result = service.run_simulation(paths["config"], {
        "candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"],
    })
    assert result["status"] == "PREFLIGHT_FAILED"
    assert result["simulation_started_counted"] is False
    candidate_root = paths["session_root"] / "candidates" / check["candidate_id"]
    assert not (candidate_root / "simulation" / "simulation_attempt.json").exists()
    ledger = service.load_json(paths["ledger"])
    assert ledger["attempts"][0]["simulation_started_counted"] is False


def test_hash_and_identifier_guards_reject_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    check = service.check_plan(paths["config"], {"plan": _plan()})
    with pytest.raises(RuntimeError, match="candidate hash mismatch"):
        service.run_simulation(paths["config"], {
            "candidate_id": check["candidate_id"], "candidate_sha256": "f" * 64,
        })
    with pytest.raises(RuntimeError, match="invalid candidate_id"):
        service.query_events(paths["config"], {"candidate_id": "../../secret", "event_type": "DEPLOY"})


def test_event_query_filters_aggregates_and_pages(tmp_path: Path) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    candidate_root = paths["session_root"] / "candidates" / "candidate-001"
    _write_json(candidate_root / "candidate_record.json", {
        "schema_version": service.CANDIDATE_RECORD_SCHEMA_VERSION, "session_id": "test-session",
        "candidate_id": "candidate-001", "candidate_sha256": "a" * 64,
        "check_status": "PASS", "simulation_status": "COMPLETED",
    })
    _write_json(paths["ledger"], {
        "schema_version": service.CANDIDATE_LEDGER_SCHEMA_VERSION,
        "session_id": "test-session", "max_candidates": 2,
        "used_candidates": 1, "attempts": [{
            "candidate_id": "candidate-001", "candidate_sha256": "a" * 64,
            "check_status": "PASS", "simulation_status": "COMPLETED",
        }],
    })
    _write_json(candidate_root / "simulation" / "diagnostic_events.json", {"events": [
        {"frame": 10, "event_type": "DAMAGE", "source_id": "a", "target_id": None, "details": {"amount": 10}},
        {"frame": 20, "event_type": "DAMAGE", "source_id": "a", "target_id": "b", "details": {"amount": 30}},
        {"frame": 30, "event_type": "DAMAGE", "source_id": "b", "target_id": None, "details": {"legal": False, "amount": 5}},
    ]})
    result = service.query_events(paths["config"], {
        "candidate_id": "candidate-001", "candidate_sha256": "a" * 64,
        "event_type": "DAMAGE", "target_id": None,
        "earliest_frame": 0, "latest_frame": 35, "limit": 1, "offset": 1,
        "aggregate": {"field": "details.amount"},
    })
    assert result["pagination"]["total_matches"] == 2
    assert result["events"][0]["frame"] == 30
    assert result["aggregate"]["sum"] == 15
    assert result["observation_coverage"] == "UNKNOWN"
    assert result["events"][0]["details"]["legal"] is False


def test_service_does_not_call_simulator_directly() -> None:
    source = (SCRIPTS / "kimiark_tactical_stdio_service_v1.py").read_text(encoding="utf-8")
    assert "from arknights_planner.simulator" not in source
    assert "Simulator(" not in source
    assert "scripts/run_gpt_tactical_stage_session_v1.py" in source
    assert "consume_evaluation" not in source
