from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

import tactical_evaluation_gate_v1 as gate


def _setup(tmp_path: Path, remaining: int = 1) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "llm_evidence_context.json").write_text("{}")
    (source / "llm_plan_validation.json").write_text(json.dumps({"status": "PASS"}))
    (source / "static_compile_results.json").write_text(json.dumps({"conflicts": []}))
    (source / "llm_structured_output.json").write_text(json.dumps({
        "revised_operational_plans": [{"operational_plan_id": "PLAN"}]
    }))
    budget_path = tmp_path / "budget.json"
    budget_path.write_text(json.dumps({
        "schema_version": gate.BUDGET_SCHEMA_VERSION,
        "stage_id": "main_test",
        "max_stage_simulations": remaining,
        "started_stage_simulations": 0,
        "prior_stage_simulations": 0,
    }))
    return source, tmp_path / "diagnostic", budget_path


def test_completed_gate_requires_manifest_summary_and_saved_result(tmp_path: Path) -> None:
    source, diagnostic, budget_path = _setup(tmp_path)
    with mock.patch.object(gate, "ROOT", tmp_path):
        with gate.consume_evaluation(
            source_dir=source, diagnostic_output_dir=diagnostic, budget_path=budget_path,
            stage_id="main_test", expected_plan_id="PLAN",
        ):
            (diagnostic / "manifest.json").write_text("{}")
            (diagnostic / "diagnostic_summary.json").write_text("{}")
            (diagnostic / "simulation_attempt.json").write_text(json.dumps({
                "status": "COMPLETED", "result_saved": True
            }))
        reservation = json.loads(diagnostic.with_name(diagnostic.name + ".simulation_reservation.json").read_text())
    assert reservation["status"] == "COMPLETED"
    assert reservation["result_saved"] is True


def test_failed_reservation_distinguishes_before_and_after_start(tmp_path: Path) -> None:
    source, diagnostic, budget_path = _setup(tmp_path, remaining=2)
    with mock.patch.object(gate, "ROOT", tmp_path):
        with pytest.raises(RuntimeError, match="before start"):
            with gate.consume_evaluation(
                source_dir=source, diagnostic_output_dir=diagnostic,
                budget_path=budget_path, stage_id="main_test",
            ):
                raise RuntimeError("failed before start")
        before = json.loads(diagnostic.with_name(diagnostic.name + ".simulation_reservation.json").read_text())
        assert before["status"] == "FAILED"
        assert before["failure_outcome"] == "FAILED_BEFORE_START"

        with pytest.raises(RuntimeError, match="after start"):
            with gate.consume_evaluation(
                source_dir=source, diagnostic_output_dir=diagnostic,
                budget_path=budget_path, stage_id="main_test",
            ):
                (diagnostic / "simulation_attempt.json").write_text(json.dumps({"status": "STARTED"}))
                raise RuntimeError("failed after start")
        after = json.loads(diagnostic.with_name(diagnostic.name + ".simulation_reservation.json").read_text())
    assert after["status"] == "FAILED"
    assert after["failure_outcome"] == "FAILED_AFTER_START_WITHOUT_SAVED_RESULT"
    assert json.loads(budget_path.read_text())["started_stage_simulations"] == 2
