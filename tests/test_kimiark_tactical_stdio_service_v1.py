from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import kimiark_tactical_stdio_service_v1 as service


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_SOURCE = REPO_ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m74_open_reduction_feedback_v1/candidate_v4"


@pytest.fixture(autouse=True)
def _block_real_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("real controlled runner must not run in fake tests")
    monkeypatch.setattr(service, "_executor", forbidden)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _support_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, model: str = "gpt-test", effort: str = "medium"
) -> dict[str, Path]:
    monkeypatch.setattr(service, "ROOT", tmp_path)
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
        "config": config,
        "config_path": config_path,
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


def _prepare_cold_start_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, used_candidates: int = 0
) -> tuple[dict[str, Any], dict[str, Path], str]:
    paths = _support_files(tmp_path, monkeypatch)
    root_plan_id = "COLD_ROOT"
    _write_json(paths["facts"] / "llm_evidence_context.json", {
        "cold_start_task_root": {
            "schema_version": "KIMIARK_COLD_START_TASK_ROOT_V1",
            "root_plan_id": root_plan_id,
            "root_experience_id": "COLD_ROOT_EXPERIENCE",
        },
        "m58_open_roster_policy": True,
    })
    _write_json(paths["ledger"], {
        "schema_version": service.CANDIDATE_LEDGER_SCHEMA_VERSION,
        "session_id": "test-session", "max_candidates": 2,
        "used_candidates": used_candidates,
        "attempts": [
            {"candidate_id": f"candidate-{index:03d}", "simulation_status": "COMPLETED"}
            for index in range(1, used_candidates + 1)
        ],
    })
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    monkeypatch.setattr(service, "validate_plan_payload", lambda plan, evidence, schema: _pass_layers()[0])
    monkeypatch.setattr(service, "validate_execution_input", lambda evidence, plan: [])
    monkeypatch.setattr(service, "validate_normal_low_star_capability_source", lambda evidence: {})
    monkeypatch.setattr(service, "validate_open_roster_contract", lambda plan, evidence, limit: [])
    return paths, {"ledger": paths["ledger"]}, root_plan_id


def test_cold_start_root_parent_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, _ledger, root_plan_id = _prepare_cold_start_check(tmp_path, monkeypatch)
    plan = _plan("PLAN_A")
    plan["revised_operational_plans"][0]["action_timeline"] = [
        {"action_type": "DEPLOY", "operator_id": "op_a", "frame": 1, "tile": [0, 0]},
    ]
    plan["revised_operational_plans"][0]["selected_low_star_operator_ids"] = ["op_a"]
    plan["revised_operational_plans"][0]["parent_hypothesis_id"] = "ROOT_HYPOTHESIS"
    plan["revised_operational_plans"][0]["parent_plan_id"] = root_plan_id
    plan["revised_operational_plans"][0]["referenced_experience_ids"] = ["COLD_ROOT_EXPERIENCE"]
    plan["revision_hypothesis"]["parent_plan_id"] = root_plan_id
    plan["revised_strategic_hypotheses"] = [{"hypothesis_id": "ROOT_HYPOTHESIS"}]
    result = service.check_plan(paths["config"], {"plan": plan})
    assert result["status"] == "PASS", result["errors"]


def test_cold_start_revision_requires_completed_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, handles, root_plan_id = _prepare_cold_start_check(tmp_path, monkeypatch, used_candidates=1)
    plan = _plan("PLAN_B")
    plan["revised_operational_plans"][0]["action_timeline"] = [
        {"action_type": "DEPLOY", "operator_id": "op_a", "frame": 1, "tile": [0, 0]},
    ]
    plan["revised_operational_plans"][0]["selected_low_star_operator_ids"] = ["op_a"]
    plan["revised_operational_plans"][0]["parent_hypothesis_id"] = "ROOT_HYPOTHESIS"
    plan["revised_operational_plans"][0]["parent_plan_id"] = "FORGED_PARENT"
    plan["revised_operational_plans"][0]["revision_hypothesis"] = {"parent_plan_id": "FORGED_PARENT"}
    plan["revised_operational_plans"][0]["referenced_experience_ids"] = ["COLD_ROOT_EXPERIENCE"]
    plan["revision_hypothesis"]["parent_plan_id"] = "FORGED_PARENT"
    plan["revised_strategic_hypotheses"] = [{"hypothesis_id": "ROOT_HYPOTHESIS"}]
    result = service.check_plan(paths["config"], {"plan": plan})
    assert result["status"] == "FAIL"
    assert any("must reference a completed candidate" in error for error in result["errors"])


def test_cold_start_revision_missing_parent_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, _handles, root_plan_id = _prepare_cold_start_check(tmp_path, monkeypatch, used_candidates=1)
    plan = _plan("PLAN_B")
    plan["revised_operational_plans"][0]["action_timeline"] = [
        {"action_type": "DEPLOY", "operator_id": "op_a", "frame": 1, "tile": [0, 0]},
    ]
    plan["revised_operational_plans"][0]["selected_low_star_operator_ids"] = ["op_a"]
    plan["revised_operational_plans"][0]["parent_hypothesis_id"] = "ROOT_HYPOTHESIS"
    plan["revised_operational_plans"][0].pop("parent_plan_id", None)
    plan["revised_operational_plans"][0]["revision_hypothesis"] = {}
    plan["revised_operational_plans"][0]["referenced_experience_ids"] = [root_plan_id]
    plan["revision_hypothesis"] = {}
    plan["revised_strategic_hypotheses"] = [{"hypothesis_id": "ROOT_HYPOTHESIS"}]
    result = service.check_plan(paths["config"], {"plan": plan})
    assert result["status"] == "FAIL"
    assert any("must declare parent_plan_id" in error for error in result["errors"])


def test_check_plan_counts_invalid_candidate_without_simulation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
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
    with pytest.raises(RuntimeError, match="candidate (ledger )?hash mismatch"):
        service.run_simulation(paths["config"], {
            "candidate_id": check["candidate_id"], "candidate_sha256": "f" * 64,
        })
    with pytest.raises(RuntimeError, match="invalid candidate_id"):
        service.query_events(paths["config"], {"candidate_id": "../../secret", "candidate_sha256": "a" * 64, "event_type": "DEPLOY"})


def test_event_query_filters_aggregates_and_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_fake_backend_requires_explicit_test_only_authorization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    config_path = paths["config_path"]
    config = service.load_json(config_path)
    config["execution_backend"] = "TEST_ONLY_FAKE"
    service.atomic_write_json(config_path, config)
    with pytest.raises(RuntimeError, match="allow_fake_execution"):
        service.load_session_config(config_path)
    config["allow_fake_execution"] = True
    config["session_id"] = "production-session"
    service.atomic_write_json(config_path, config)
    with pytest.raises(RuntimeError, match="TEST_ONLY-"):
        service.load_session_config(config_path)
    config["session_id"] = "TEST_ONLY-fake"
    config["stage_id"] = "real-stage"
    service.atomic_write_json(config_path, config)
    with pytest.raises(RuntimeError, match="FAKE_TEST-"):
        service.load_session_config(config_path)
    config["stage_id"] = "FAKE_TEST-stage"
    service.atomic_write_json(config_path, config)
    budget = service.load_json(paths["budget"])
    budget["stage_id"] = "FAKE_TEST-stage"
    service.atomic_write_json(paths["budget"], budget)
    ledger = service.load_json(paths["ledger"])
    ledger["session_id"] = "TEST_ONLY-fake"
    service.atomic_write_json(paths["ledger"], ledger)
    loaded = service.load_session_config(config_path)
    assert loaded.execution_backend == "TEST_ONLY_FAKE"


def test_candidate_quota_recheck_and_third_candidate_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    first = service.check_plan(paths["config"], {"plan": _plan("PLAN_A")})
    assert first["status"] == "PASS"
    recheck = service.check_plan(paths["config"], {"plan": _plan("PLAN_A")})
    assert recheck["status"] == "IDEMPOTENT_RECHECK"
    assert recheck["candidate_id"] == first["candidate_id"]
    second = service.check_plan(paths["config"], {"plan": _plan("PLAN_B")})
    assert second["status"] == "PASS"
    third = service.check_plan(paths["config"], {"plan": _plan("PLAN_C")})
    assert third == {
        "status": "BUDGET_EXHAUSTED", "resource": "candidates",
        "candidate_ledger": {"max_candidates": 2, "used_candidates": 2},
        "candidate_counted": False, "simulation_started": False,
    }


def test_changed_controlled_code_rejects_frozen_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    check = service.check_plan(paths["config"], {"plan": _plan()})
    candidate_root = paths["session_root"] / "candidates" / check["candidate_id"]
    record_path = candidate_root / "candidate_record.json"
    record = service.load_json(record_path)
    record["controlled_code_sha256"] = {"code": "1" * 64}
    service.atomic_write_json(record_path, record)
    with pytest.raises(RuntimeError, match="controlled execution code changed"):
        service.run_simulation(paths["config"], {
            "candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"],
        })


def test_changed_facts_source_rejects_frozen_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    check = service.check_plan(paths["config"], {"plan": _plan()})
    _write_json(paths["facts"] / "llm_evidence_context.json", {"m58_open_roster_policy": False, "changed": True})
    with pytest.raises(RuntimeError, match="facts source changed"):
        service.run_simulation(paths["config"], {
            "candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"],
        })


def test_started_unknown_output_is_not_rerun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    check = service.check_plan(paths["config"], {"plan": _plan()})
    candidate_root = paths["session_root"] / "candidates" / check["candidate_id"]
    output_dir = candidate_root / "simulation"
    _write_json(output_dir / "simulation_attempt.json", {"status": "STARTED"})
    _write_json(output_dir.with_name(output_dir.name + ".simulation_reservation.json"), {"status": "RESERVED"})
    result = service.run_simulation(paths["config"], {
        "candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"],
    })
    assert result["status"] == "STARTED_UNKNOWN"
    assert result["simulation_started_counted"] == "UNKNOWN"
    assert result["retry"] is False
    assert not (output_dir / "manifest.json").exists()


def test_executor_timeout_before_start_is_not_counted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _support_files(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    monkeypatch.setattr(service, "_validation_layers", lambda *args, **kwargs: _pass_layers())
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})
    check = service.check_plan(paths["config"], {"plan": _plan()})
    def timeout(*args: Any, **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(cmd="FAKE_TEST", timeout=1)
    result = service.run_simulation(paths["config"], {
        "candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"],
    }, executor=timeout)
    assert result["status"] == "EXECUTION_EXCEPTION"
    assert result["simulation_started_counted"] is False
    ledger = service.load_json(paths["ledger"])
    assert ledger["attempts"][0]["simulation_started_counted"] is False
    assert service.load_json(paths["budget"])["started_stage_simulations"] == 0


def test_simulation_run_lock_blocks_duplicate_start(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    root.mkdir()
    with service.simulation_run_lock(root) as first:
        assert first is True
        with service.simulation_run_lock(root) as second:
            assert second is False


def test_complete_event_log_reports_event_not_observed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        {"frame": 1, "event_type": "OTHER", "source_id": "a", "target_id": None, "details": {}}
    ]})
    _write_json(candidate_root / "simulation" / "manifest.json", {"FAKE_TEST": True})
    _write_json(candidate_root / "simulation" / "simulation_attempt.json", {"status": "COMPLETED", "result_saved": True})
    result = service.query_events(paths["config"], {
        "candidate_id": "candidate-001", "candidate_sha256": "a" * 64,
        "event_type": "OPERATOR_DEATH", "earliest_frame": 0, "latest_frame": 10,
    })
    assert "status" not in result
    assert result["events"] == []
    assert result["observation_coverage"] == "COMPLETE"
    assert result["zero_match_status"] == "EVENT_NOT_OBSERVED"
    assert result["pagination"]["byte_budget_truncated"] is False


def _write_fake_stdio_files(temp_dir: Path) -> tuple[Path, Path, dict[str, Any]]:
    facts_dir = temp_dir / "facts"
    facts_dir.mkdir()
    for name in ("llm_evidence_context.json", "revision_output_schema.json", "llm_structured_output.json"):
        shutil.copyfile(VALID_SOURCE / name, facts_dir / name)
    plan = service.load_json(facts_dir / "llm_structured_output.json")
    selected_plan = plan["revised_operational_plans"][0]
    plan_id = selected_plan["operational_plan_id"]
    distinct_ids = set(selected_plan.get("selected_low_star_operator_ids") or [])
    distinct_ids.update(
        action.get("operator_id") for action in selected_plan["action_timeline"]
        if action.get("action_type") == "DEPLOY"
    )
    stage_id = f"FAKE_TEST-{service.load_json(facts_dir / 'llm_evidence_context.json').get('stage_id', 'stage')}"
    budget_path = temp_dir / "budget.json"
    ledger_path = temp_dir / "candidates.json"
    authorization_path = temp_dir / "authorization.json"
    config_path = temp_dir / "session-config.json"
    _write_json(budget_path, {
        "schema_version": service.gate.BUDGET_SCHEMA_VERSION,
        "stage_id": stage_id, "max_stage_simulations": 2,
        "prior_stage_simulations": 0, "started_stage_simulations": 0,
    })
    _write_json(ledger_path, {
        "schema_version": service.CANDIDATE_LEDGER_SCHEMA_VERSION,
        "session_id": "TEST_ONLY-stdio", "max_candidates": 2,
        "used_candidates": 0, "attempts": [],
    })
    _write_json(authorization_path, {"model": "TEST_ONLY_MODEL", "reasoning_effort": "medium"})
    _write_json(config_path, {
        "schema_version": service.CONFIG_SCHEMA_VERSION,
        "session_id": "TEST_ONLY-stdio", "stage_id": stage_id,
        "plan_id_prefix": plan_id, "plan_label": plan_id,
        "model": "TEST_ONLY_MODEL", "reasoning_effort": "medium",
        "features_apps": False, "mechanics_version": service.ACTIVE_MECHANICS_VERSION,
        "facts_source_dir": str(facts_dir.relative_to(REPO_ROOT)),
        "session_root": str(temp_dir.relative_to(REPO_ROOT)),
        "budget_path": str(budget_path.relative_to(REPO_ROOT)),
        "candidate_ledger_path": str(ledger_path.relative_to(REPO_ROOT)),
        "authorization_config_path": str(authorization_path.relative_to(REPO_ROOT)),
        "max_unique_deployed_operators": len(distinct_ids), "max_candidates": 2,
        "simulation_timeout_seconds": 60,
        "execution_backend": "TEST_ONLY_FAKE", "allow_fake_execution": True,
    })
    return config_path, facts_dir, plan


def _rpc(proc: subprocess.Popen[str], payload: dict[str, Any], transcript: list[dict[str, Any]]) -> dict[str, Any] | None:
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    transcript.append({"direction": "request", "payload": payload})
    assert proc.stdin is not None
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    if "id" not in payload:
        return None
    assert proc.stdout is not None
    response_line = proc.stdout.readline()
    if not response_line:
        raise AssertionError("stdio service closed before response")
    response = json.loads(response_line)
    transcript.append({"direction": "response", "payload": response})
    return response


def test_stdio_mcp_fake_closed_loop(tmp_path: Path) -> None:
    if not VALID_SOURCE.is_dir():
        pytest.skip("valid fixture source is unavailable")
    temp_dir = REPO_ROOT / "output" / f"test-kimiark-stdio-{tmp_path.name}"
    temp_dir.mkdir(parents=True)
    try:
        config_path, _, plan = _write_fake_stdio_files(temp_dir)
        transcript: list[dict[str, Any]] = [{"FAKE_TEST": True}]
        process = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"), str(config_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        try:
            initialize = _rpc(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}, transcript)
            assert initialize and initialize["result"]["serverInfo"]["name"] == "kimiark-closed-loop-tools"
            _rpc(process, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, transcript)
            tools = _rpc(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, transcript)
            assert tools and {item["name"] for item in tools["result"]["tools"]} == {
                "get_session_status", "check_plan", "run_simulation", "query_events"
            }
            status = _rpc(process, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_session_status", "arguments": {}}}, transcript)
            assert status and status["result"]["structuredContent"]["budget"]["remaining_stage_simulations"] == 2
            check = _rpc(process, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "check_plan", "arguments": {"plan": plan}}}, transcript)
            assert check and check["result"].get("structuredContent"), check
            first_structured = check["result"]["structuredContent"]
            assert first_structured.get("status") == "PASS", {
                "errors": first_structured.get("errors"),
                "execution_input_gate": first_structured.get("execution_input_gate"),
            }
            first = first_structured
            run = _rpc(process, {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "run_simulation", "arguments": {
                "candidate_id": first["candidate_id"], "candidate_sha256": first["candidate_sha256"],
            }}}, transcript)
            assert run and run["result"]["structuredContent"]["status"] == "COMPLETED"
            query = _rpc(process, {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "query_events", "arguments": {
                "candidate_id": first["candidate_id"], "candidate_sha256": first["candidate_sha256"],
                "event_type": "DEPLOY", "source_id": "fake_operator", "target_id": "fake_tile",
                "earliest_frame": 200, "latest_frame": 200,
            }}}, transcript)
            structured = query["result"]["structuredContent"]
            assert structured["events"][0]["details"]["legal"] is False
            assert structured["boundary"].startswith("Raw matches")
            revised = json.loads(json.dumps(plan))
            revised["revised_operational_plans"][0]["tactical_thesis"] += " [FAKE_TEST_REVISION]"
            revision_check = _rpc(process, {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "check_plan", "arguments": {"plan": revised}}}, transcript)
            assert revision_check and revision_check["result"].get("structuredContent"), revision_check
            second_structured = revision_check["result"]["structuredContent"]
            assert second_structured.get("status") == "PASS", {
                "errors": second_structured.get("errors"),
                "execution_input_gate": second_structured.get("execution_input_gate"),
            }
            second = second_structured
            second_run = _rpc(process, {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "run_simulation", "arguments": {
                "candidate_id": second["candidate_id"], "candidate_sha256": second["candidate_sha256"],
            }}}, transcript)
            assert second_run and second_run["result"]["structuredContent"]["status"] == "COMPLETED"
            cached = _rpc(process, {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "run_simulation", "arguments": {
                "candidate_id": second["candidate_id"], "candidate_sha256": second["candidate_sha256"],
            }}}, transcript)
            assert cached and cached["result"]["structuredContent"]["status"] == "IDEMPOTENT_COMPLETED"
            third = _rpc(process, {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "check_plan", "arguments": {"plan": _plan("PLAN_C")}}}, transcript)
            assert third and third["result"]["structuredContent"]["status"] == "BUDGET_EXHAUSTED"
        finally:
            assert process.stdin is not None
            process.stdin.close()
            process.wait(timeout=10)
            stderr = process.stderr.read() if process.stderr else ""
            assert process.returncode == 0, stderr
            assert stderr == ""
        assert transcript[0]["FAKE_TEST"] is True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
