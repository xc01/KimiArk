from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_gpt_tactical_stage_session_v1 as runner
import run_gpt_tactical_stage_diagnostic_v1 as run_gpt_tactical_stage_diagnostic_module
import run_r8_1_gpt_c4_codex_cli_v1 as codex_runner


ROOT = Path(__file__).resolve().parents[1]
REPAIR_DIR = ROOT / (
    "output/r8_1_r8_7_batch_v1/main_08-07/m61_m60_static_revision_v1/execution_ready_v1"
)


def execution_context() -> dict:
    return json.loads((REPAIR_DIR / "llm_evidence_context.json").read_text())


def parsed_plan() -> dict:
    return json.loads((REPAIR_DIR / "llm_structured_output.json").read_text())


def configure_output(tmp_path: Path, evidence: dict, parsed: dict) -> None:
    (tmp_path / "llm_evidence_context.json").write_text(json.dumps(evidence), encoding="utf-8")
    (tmp_path / "llm_structured_output.json").write_text(json.dumps(parsed), encoding="utf-8")
    (tmp_path / "static_compile_results.json").write_text(json.dumps({"conflicts": []}), encoding="utf-8")
    runner.OUT = tmp_path
    codex_runner.OUT = tmp_path
    runner.PLAN_LABEL = "M61-V1"


def test_repaired_m61_context_passes_execution_preflight() -> None:
    errors = runner.validate_execution_input(execution_context(), parsed_plan())

    assert errors == []


def test_compact_m61_catalog_fails_before_model_input_validation() -> None:
    compact_context = json.loads((ROOT / (
        "output/r8_1_r8_7_batch_v1/main_08-07/m61_m60_static_revision_v1/attempt_01_cli/llm_evidence_context.json"
    )).read_text())

    errors = runner.validate_execution_input(compact_context, require_all_catalog=True)

    assert any("debug_configuration is missing" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "expected_path"),
    [
        ("debug_configuration", "normal_low_star_catalog[7].debug_configuration"),
        ("phase_index", "normal_low_star_catalog[7].debug_configuration.phase_index"),
        ("level", "normal_low_star_catalog[7].debug_configuration.level"),
    ],
)
def test_missing_execution_fields_are_reported_by_path(field: str, expected_path: str) -> None:
    evidence = execution_context()
    if field == "debug_configuration":
        del evidence["normal_low_star_catalog"][7]["debug_configuration"]
    else:
        del evidence["normal_low_star_catalog"][7]["debug_configuration"][field]

    errors = runner.validate_execution_input(evidence, parsed_plan())

    assert expected_path in errors[0]


@pytest.mark.parametrize(("mode", "rarity"), [("normal_mode", 4), ("other_mode", 3)])
def test_illegal_mode_or_star_is_rejected(mode: str, rarity: int) -> None:
    evidence = execution_context()
    evidence["normal_low_star_catalog"][7]["identity"]["rarity"] = rarity
    evidence["normal_low_star_catalog"][7]["qualification"]["normal_mode"] = mode == "normal_mode"

    errors = runner.validate_execution_input(evidence, parsed_plan())

    assert any("normal_low_star_catalog[7]" in error for error in errors)


def test_missing_or_ambiguous_catalog_entry_is_rejected() -> None:
    evidence = execution_context()
    removed = evidence["normal_low_star_catalog"].pop(7)
    assert runner.validate_execution_input(evidence, parsed_plan())
    evidence["normal_low_star_catalog"].insert(7, removed)
    evidence["normal_low_star_catalog"].insert(8, copy.deepcopy(removed))

    errors = runner.validate_execution_input(evidence, parsed_plan())

    assert any("duplicate operator_id" in error for error in errors)


def test_simulate_preflight_fails_before_evaluation_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_output(tmp_path, execution_context(), parsed_plan())
    evidence = execution_context()
    del evidence["normal_low_star_catalog"][7]["debug_configuration"]
    (runner.OUT / "llm_evidence_context.json").write_text(json.dumps(evidence), encoding="utf-8")
    budget_path = tmp_path / "budget.json"
    budget_path.write_text(json.dumps({"started_stage_simulations": 0}), encoding="utf-8")
    reservation_path = tmp_path.parent / "reservation.json"
    runner.SIMULATION_BUDGET_PATH = budget_path

    def forbidden_gate(**_kwargs):
        raise AssertionError("evaluation gate must not run before execution input validation")

    monkeypatch.setattr(runner.gate, "consume_evaluation", forbidden_gate)

    with pytest.raises(SystemExit, match="execution input errors block diagnostic reservation"):
        runner.simulate()

    gate_result = runner.load(runner.OUT / "execution_input_gate.json")
    assert gate_result["status"] == "BLOCKED_EXECUTION_INPUT"
    assert "normal_low_star_catalog[7].debug_configuration" in gate_result["errors"][0]
    assert not reservation_path.exists()
    assert json.loads(budget_path.read_text())["started_stage_simulations"] == 0


def test_simulate_preflight_passes_without_starting_the_simulator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_output(tmp_path, execution_context(), parsed_plan())
    runner.SIMULATION_BUDGET_PATH = tmp_path / "budget.json"

    def exhausted_gate(**_kwargs):
        class Gate:
            def __enter__(self):
                return {"status": "BUDGET_EXHAUSTED"}

            def __exit__(self, exc_type, exc, traceback):
                return False

        return Gate()

    def forbidden_diagnostic(**_kwargs):
        raise RuntimeError("test must not reach the diagnostic runner")

    monkeypatch.setattr(runner.gate, "consume_evaluation", exhausted_gate)
    monkeypatch.setattr(run_gpt_tactical_stage_diagnostic_module, "run_full_diagnostic", forbidden_diagnostic)

    assert runner.simulate() == {"status": "BUDGET_EXHAUSTED"}

    assert runner.load(runner.OUT / "execution_input_gate.json")["status"] == "PASS"
