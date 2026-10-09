from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/ch6_11_enemy_runtime_fidelity_v1"


def load(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_unique_ch6_11_enemy_execution_is_per_enemy_not_deployment_only():
    coverage = load("ch6_11_enemy_execution_coverage.json")
    unique = load("ch6_11_unique_enemies.json")
    no_attack = {
        record["enemy_id"] for record in unique["records"]
        if record["apply_way"]["value"] == "NONE" or not record["stats"]["atk"]["value"]
    }
    assert coverage["coverage"] == "50/50"
    assert all(result["exercised"]["spawn"] and result["exercised"]["movement"] for result in coverage["results"])
    assert all(
        result["enemy_id"] in no_attack or result["exercised"]["normal_attack"]
        for result in coverage["results"]
    )
    assert all(not result["deployment_errors"] for result in coverage["results"])


def test_stage_fidelity_recheck_has_24_runnable_normal_stages():
    recheck = load("runtime_stage_recheck.json")
    stage_fidelity = load("ch6_11_stage_runtime_fidelity.json")
    assert recheck["runtime_runnable_count"] == 24
    assert recheck["runtime_blocked_count"] == 0
    assert len(stage_fidelity["stages"]) == 24
    assert stage_fidelity["counts"] == {
        "PARTIAL_RUNTIME": 23,
        "PLANNING_SAFE_WITH_KNOWN_APPROXIMATIONS": 1,
    }


def test_no_ch6_11_enemy_ability_is_claimed_safe_without_semantics():
    ability = load("ch6_11_ability_semantic_coverage.json")
    assert ability["planner_safe_claimed"] == 0
    assert ability["tested"] == 0
    assert ability["coverage"] == "0/0"
