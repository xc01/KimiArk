from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_normal_low_star_tactical_revision_v1"


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_exactly_one_successful_kimi_call_and_low_star_plan():
    record = load("llm_call_record.json")
    completion = load("response_completion_validation.json")
    output = load("llm_structured_output.json")
    assert record["http_status"] == 200 and record["model"] == "kimi-k3"
    assert completion["complete"] is True and completion["kimi_call_count"] == 1
    assert len(output["revised_operational_plans"]) == 1


def test_selected_ids_are_sourced_from_normal_low_star_catalog():
    catalog = load("../normal_low_star_facts_v1/normal_low_star_facts.json")
    known = {item["operator_id"] for item in catalog["operators"]}
    plan = load("llm_structured_output.json")["revised_operational_plans"][0]
    assert set(plan["selected_low_star_operator_ids"]) <= known
    assert "char_272_strong" not in known and "char_607_cspec" not in known


def test_bounded_compile_is_legal_but_not_operationally_verified():
    result = load("bounded_compile_results.json")
    status = load("compilation_final_status.json")
    assert all(item["legal"] for item in result["deployment_legality"]["rows"])
    assert all(item["status"] == "PAID" for item in result["dp_ledger"]["rows"] if item["event"] == "DEPLOY_COST")
    assert result["semantic_certificate"]["faithful_executable_timeline"] is False
    assert result["semantic_certificate"]["operationally_verified"] is False
    assert result["semantic_certificate"]["classification"] == "SEMANTIC_COMPILE_CANDIDATE_WITH_NARRATIVE_DISCREPANCY"
    assert status["complete_combinations"] == 1 and status["direction_complete_candidates"] == 1
    assert status["stage_simulations"] == 0


def test_counterexamples_are_explicitly_avoided_and_narrative_error_is_not_hidden():
    counterexample = load("counterexample_avoidance_validation.json")
    result = load("bounded_compile_results.json")
    assert counterexample["merchant_upkeep_avoided"] is True
    assert counterexample["roadblock_counterexample_avoided"] is True
    assert counterexample["unsupported_mechanics_are_not_load_bearing"] is True
    assert result["semantic_certificate"]["narrative_discrepancy"]["computed_final_dp"] == 0.0


def test_validation_artifacts_are_hashed_in_milestone_manifest():
    manifest = load("milestone_manifest.json")
    for relative_path, record in manifest["files"].items():
        path = ROOT / relative_path
        assert record["bytes"] == path.stat().st_size
        assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
