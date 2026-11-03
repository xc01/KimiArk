from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import kimiark_tactical_stdio_service_v1 as service
import tactical_experience_v1 as experience


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_SOURCE = REPO_ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m74_open_reduction_feedback_v1/candidate_v4"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture
def v2_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setattr(service, "ROOT", tmp_path)
    monkeypatch.setattr(service.gate, "ROOT", tmp_path)
    monkeypatch.setattr(service, "controlled_code_hashes", lambda: {"code": "0" * 64})
    facts = tmp_path / "facts"
    budget = tmp_path / "budget.json"
    ledger = tmp_path / "ledger.json"
    authorization = tmp_path / "authorization.json"
    config_path = tmp_path / "session-config.json"
    _write_json(facts / "llm_evidence_context.json", {"m58_open_roster_policy": False})
    _write_json(facts / "revision_output_schema.json", {"type": "object"})
    _write_json(authorization, {"model": "gpt-test", "reasoning_effort": "medium"})
    _write_json(budget, {
        "schema_version": service.gate.BUDGET_SCHEMA_VERSION, "stage_id": "FAKE_TEST-stage",
        "max_stage_simulations": 5, "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    _write_json(ledger, {
        "schema_version": service.CANDIDATE_LEDGER_SCHEMA_V2,
        "session_id": "TEST_ONLY-v2", "max_check_calls": 20, "used_check_calls": 0,
        "checks": [], "max_candidates": 5, "used_candidates": 0, "attempts": [],
    })
    _write_json(config_path, {
        "schema_version": service.CONFIG_SCHEMA_VERSION, "session_id": "TEST_ONLY-v2",
        "stage_id": "FAKE_TEST-stage", "plan_id_prefix": "PLAN_", "plan_label": "PLAN",
        "model": "gpt-test", "reasoning_effort": "medium", "features_apps": False,
        "mechanics_version": service.ACTIVE_MECHANICS_VERSION, "facts_source_dir": "facts",
        "session_root": "session", "budget_path": "budget.json",
        "candidate_ledger_path": "ledger.json", "authorization_config_path": "authorization.json",
        "max_unique_deployed_operators": 7, "max_candidates": 5, "max_check_calls": 20,
        "simulation_timeout_seconds": 60, "execution_backend": "TEST_ONLY_FAKE",
        "allow_fake_execution": True,
    })
    return {
        "config_path": config_path, "ledger": ledger, "root": tmp_path,
        "session_root": tmp_path / "session",
    }


def _plan(operation_id: str = "PLAN_A") -> dict[str, Any]:
    return {
        "revised_operational_plans": [{
            "operational_plan_id": operation_id, "parent_plan_id": "PARENT",
            "action_timeline": [{"action_type": "ACTIVATE_SKILL", "operator_id": "op", "frame": 1}],
            "selected_low_star_operator_ids": ["op"],
        }],
        "revision_hypothesis": {
            "parent_plan_id": "PARENT", "operational_plan_id": operation_id,
            "expected_first_observable_event": {
                "event_type": "ACTIVATE_SKILL", "source_id": "op", "target_id": None,
                "earliest_frame": 1, "latest_frame": 1,
            },
        },
    }


def _set_validation(
    monkeypatch: pytest.MonkeyPatch, *, status: str, errors: list[str] | None = None
) -> None:
    errors = errors or []
    layered = {
        "schema_errors": [], "semantic_errors": [], "event_query_errors": [],
        "lineage_errors": [],
    }
    execution = {
        "schema_version": "TEST", "status": status, "checked_operator_ids": ["op"],
        "errors": errors, "roster_errors": [],
    }
    monkeypatch.setattr(service, "_validation_layers", lambda *_: (layered, list(errors), execution))
    monkeypatch.setattr(service, "compile_plan", lambda source: {"conflicts": []})


def test_failed_checks_preserved_and_pass_becomes_first_real_candidate(
    v2_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = service.load_session_config(v2_paths["config_path"])
    _set_validation(monkeypatch, status="FAIL", errors=["STATIC_FAILURE"])
    failed = service.check_plan(config, {"plan": _plan("PLAN_A")})
    assert failed["status"] == "FAIL"
    assert failed["check_id"] == "check-001"
    assert failed["check_call_counted"] is True
    assert failed["candidate_counted"] is False
    assert failed["errors"] == ["STATIC_FAILURE"]

    _set_validation(monkeypatch, status="PASS")
    passed = service.check_plan(config, {"plan": _plan("PLAN_B")})
    assert passed["status"] == "PASS"
    assert passed["check_id"] == "check-002"
    assert passed["candidate_id"] == "candidate-001"
    assert passed["candidate_counted"] is True
    assert (v2_paths["session_root"] / "checks/check-001/check_record.json").is_file()
    assert (v2_paths["session_root"] / "candidates/candidate-001/candidate_record.json").is_file()
    ledger = service.load_json(v2_paths["ledger"])
    assert ledger["used_check_calls"] == 2
    assert ledger["used_candidates"] == 1
    assert [item["kind"] for item in ledger["checks"]] == ["FAILED_CHECK", "PASS"]


def test_check_call_budget_is_enforced_without_candidate_consumption(
    v2_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = service.load_session_config(v2_paths["config_path"])
    _set_validation(monkeypatch, status="FAIL", errors=["STATIC_FAILURE"])
    for number in range(20):
        result = service.check_plan(config, {"plan": _plan(f"PLAN_{number:02d}")})
        assert result["check_id"] == f"check-{number + 1:03d}"
    exhausted = service.check_plan(config, {"plan": _plan("PLAN_EXHAUSTED")})
    assert exhausted["status"] == "CHECK_BUDGET_EXHAUSTED"
    assert exhausted["check_call_counted"] is False
    ledger = service.load_json(v2_paths["ledger"])
    assert ledger["used_check_calls"] == 20
    assert ledger["used_candidates"] == 0


def test_query_alias_and_unknown_event_are_precise(v2_paths: dict[str, Path]) -> None:
    normalized = experience.normalize_event_query({
        "event_type": "ACTIVATE_SKILL", "source_id": "op", "target_id": None,
        "earliest_frame": 1, "latest_frame": 1,
    })
    assert normalized["status"] == "VALID_QUERY"
    assert normalized["declared_event_type" if "declared_event_type" in normalized else "event_type_declared"] == "ACTIVATE_SKILL"
    assert normalized["event_type"] == "SKILL_ACTIVATE"
    assert experience._event_matches(
        {"event_type": "SKILL_ACTIVATE", "source_id": "op", "target_id": None, "frame": 1,
         "details": {"legal": False}},
        normalized,
    ) is False
    assert experience._event_matches(
        {"event_type": "SKILL_ACTIVATE", "source_id": "op", "target_id": None, "frame": 1,
         "details": {"legal": True}},
        normalized,
    ) is True
    assert "ACTIVATE_SKILL" in next(
        tool["inputSchema"]["properties"]["event_type"]["enum"]
        for tool in service.TOOLS if tool["name"] == "query_events"
    )


def test_status_exposes_vocabulary_and_v2_budget(v2_paths: dict[str, Path]) -> None:
    config = service.load_session_config(v2_paths["config_path"])
    status = service.session_status(config)
    assert status["interface_vocab"]["action_type_names"] == ["ACTIVATE_SKILL", "DEPLOY", "RETREAT"]
    assert status["interface_vocab"]["event_type_names"] == service.SUPPORTED_EVENT_TYPE_NAMES
    assert status["check_call_ledger"] == {
        "max_check_calls": 20, "used_check_calls": 0, "remaining_check_calls": 20
    }


def test_frozen_candidate_hash_change_requires_new_check(
    v2_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = service.load_session_config(v2_paths["config_path"])
    _set_validation(monkeypatch, status="PASS")
    check = service.check_plan(config, {"plan": _plan("PLAN_A")})
    candidate_root = v2_paths["session_root"] / "candidates" / check["candidate_id"]
    plan_path = candidate_root / "source" / "llm_structured_output.json"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    arguments = {"candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"]}
    with pytest.raises(RuntimeError, match="frozen candidate input changed"):
        service.run_simulation(config, arguments)
    ledger = service.load_json(v2_paths["ledger"])
    assert ledger["used_candidates"] == 1
