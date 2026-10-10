from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import compile_r8_1_normal_low_star_plan_v1 as compiler


OUT = Path(compiler.OUT)


def saved(name):
    return json.loads((OUT / name).read_text())


def test_dp_comparison_uses_the_claimed_window_endpoint():
    ledger = compiler.dp_ledger()
    last_deploy = [row for row in ledger["rows"] if row["event"] == "DEPLOY_COST"][-1]
    assert last_deploy["frame"] == 630 and last_deploy["available_after"] == 0
    assert ledger["rows"][-1]["frame"] == 941
    assert ledger["rows"][-1]["available_after"] == pytest.approx(311 / 30)
    assert sum(row["cost"] for row in ledger["rows"] if row["event"] == "DEPLOY_COST") == 37


def test_narrative_discrepancy_cannot_mask_a_deployment_conflict(monkeypatch):
    plan = saved("llm_structured_output.json")["revised_operational_plans"][0]
    monkeypatch.setattr(compiler, "plan_hint", plan)
    legality = copy.deepcopy(saved("deployment_legality.json"))
    legality["rows"][0]["legal"] = False
    certificate = compiler.semantic_certificate(compiler.dp_ledger(), legality)
    assert certificate["classification"] == "COMPILE_CONFLICT"
    assert certificate["ledger_final_frame"] == 941
    assert certificate["narrative_discrepancy"]["computed_final_dp"] == pytest.approx(311 / 30)


def test_a_plan_declaration_does_not_certify_unsupported_effect_independence():
    plan = saved("llm_structured_output.json")["revised_operational_plans"][0]
    result = compiler.counterexample_avoidance(
        plan, saved("semantic_fidelity_certificate.json")["check_status"], saved("operator_checks.json")
    )
    assert result["unsupported_mechanics_are_not_load_bearing"] is None
    assert result["unsupported_mechanics_dependency_status"] == "UNKNOWN"
