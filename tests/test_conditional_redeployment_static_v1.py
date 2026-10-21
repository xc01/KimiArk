from __future__ import annotations

import json
from pathlib import Path
import sys

from compile_r8_1_lowstar_c2_plan_v1 import compile_plan


ROOT = Path(__file__).resolve().parents[1]


def _catalog(operator_id: str = "op", cost: int = 10) -> dict:
    return {
        "operator_id": operator_id,
        "identity": {"rarity": 3, "position": "MELEE"},
        "qualification": {"normal_mode": True},
        "stats": {"cost": cost, "redeploy_time": 70},
        "selected_skills": [],
    }


def _evidence(*operators: dict) -> dict:
    return {
        "stage_options": {"initial_cost": 99, "max_cost": 99, "deployment_limit": 8},
        "stage_active_facts": {
            "roadblock_tiles_col_row": [],
            "deployable_ground_tiles_col_row": [[1, 1], [1, 2], [2, 1]],
            "deployable_high_ground_tiles_col_row": [],
        },
        "normal_low_star_catalog": list(operators),
    }


def _write(tmp_path: Path, evidence: dict, plan: dict) -> None:
    (tmp_path / "llm_evidence_context.json").write_text(json.dumps(evidence), encoding="utf-8")
    (tmp_path / "llm_structured_output.json").write_text(json.dumps(plan), encoding="utf-8")


def test_conditional_redeploy_is_not_a_static_tactical_conflict(tmp_path):
    evidence = _evidence(_catalog())
    plan = {
        "revised_operational_plans": [{
            "operational_plan_id": "conditional-redeploy-test",
            "deployment_positions_and_directions": [
                {"operator_id": "op", "tile": [1, 1], "direction": "RIGHT"},
                {"operator_id": "op", "tile": [2, 1], "direction": "RIGHT"},
            ],
            "action_timeline": [
                {"action_type": "DEPLOY", "operator_id": "op", "frame": 0, "tile": [1, 1], "direction": "RIGHT"},
                {"action_type": "DEPLOY", "operator_id": "op", "frame": 2400, "tile": [2, 1], "direction": "RIGHT"},
            ],
        }],
    }
    _write(tmp_path, evidence, plan)
    result = compile_plan(tmp_path)
    conflict_reasons = [reason for row in result["checks"]["deployment"] for reason in row.get("reasons", [])]
    assert "CONDITIONAL_REDEPLOY_AWAITING_EXIT" in conflict_reasons
    assert "OPERATOR_ALREADY_DEPLOYED" not in conflict_reasons
    assert result["dp_ledger"]["conflicts"] == []


def test_conditional_redeploy_to_tile_occupied_by_another_operator_conflicts(tmp_path):
    evidence = _evidence(_catalog("holder"), _catalog("mover"))
    plan = {
        "revised_operational_plans": [{
            "operational_plan_id": "other-occupant-test",
            "deployment_positions_and_directions": [
                {"operator_id": "holder", "tile": [1, 1], "direction": "RIGHT"},
                {"operator_id": "mover", "tile": [1, 2], "direction": "RIGHT"},
                {"operator_id": "mover", "tile": [1, 1], "direction": "RIGHT"},
            ],
            "action_timeline": [
                {"action_type": "DEPLOY", "operator_id": "holder", "frame": 0, "tile": [1, 1], "direction": "RIGHT"},
                {"action_type": "DEPLOY", "operator_id": "mover", "frame": 30, "tile": [1, 2], "direction": "RIGHT"},
                {"action_type": "DEPLOY", "operator_id": "mover", "frame": 2400, "tile": [1, 1], "direction": "RIGHT"},
            ],
        }],
    }
    _write(tmp_path, evidence, plan)
    result = compile_plan(tmp_path)
    redeploy = result["checks"]["deployment"][2]
    assert redeploy["status"] == "CONFLICT"
    assert "TILE_OCCUPIED_BY_ANOTHER_OPERATOR" in redeploy["reasons"]
    assert redeploy["tile_occupied_by_other"] is True


def test_explicit_retreat_redeploy_uses_cooldown_boundary_and_new_generation(tmp_path):
    evidence = _evidence(_catalog())
    plan = {
        "revised_operational_plans": [{
            "operational_plan_id": "cooldown-boundary-test",
            "deployment_positions_and_directions": [
                {"operator_id": "op", "tile": [1, 1], "direction": "RIGHT"},
                {"operator_id": "op", "tile": [1, 2], "direction": "RIGHT"},
            ],
            "action_timeline": [
                {"action_type": "DEPLOY", "operator_id": "op", "frame": 0, "tile": [1, 1], "direction": "RIGHT"},
                {"action_type": "RETREAT", "operator_id": "op", "frame": 0},
                {"action_type": "DEPLOY", "operator_id": "op", "frame": 2100, "tile": [1, 2], "direction": "RIGHT"},
            ],
        }],
    }
    _write(tmp_path, evidence, plan)
    result = compile_plan(tmp_path)
    assert result["checks"]["deployment"][1]["status"] == "PASS_WITH_CONDITIONS"
    assert result["classification"] != "STATIC_CONFLICT"
    assert not result["conditional_redeploys"]
    deploy_rows = [row for row in result["dp_ledger"]["entries"] if row.get("event") == "DEPLOY_COST"]
    assert [row["generation"] for row in deploy_rows] == [1, 2]


def test_redeploy_one_frame_before_cooldown_is_a_conflict(tmp_path):
    evidence = _evidence(_catalog())
    plan = {
        "revised_operational_plans": [{
            "operational_plan_id": "cooldown-conflict-test",
            "deployment_positions_and_directions": [
                {"operator_id": "op", "tile": [1, 1], "direction": "RIGHT"},
                {"operator_id": "op", "tile": [1, 2], "direction": "RIGHT"},
            ],
            "action_timeline": [
                {"action_type": "DEPLOY", "operator_id": "op", "frame": 0, "tile": [1, 1], "direction": "RIGHT"},
                {"action_type": "RETREAT", "operator_id": "op", "frame": 0},
                {"action_type": "DEPLOY", "operator_id": "op", "frame": 2099, "tile": [1, 2], "direction": "RIGHT"},
            ],
        }],
    }
    _write(tmp_path, evidence, plan)
    result = compile_plan(tmp_path)
    assert result["checks"]["deployment"][1]["reasons"] == ["REDEPLOY_COOLDOWN_ACTIVE"]


def test_conditional_redeploy_does_not_bypass_base_cost(tmp_path):
    evidence = _evidence(_catalog(cost=10))
    evidence["stage_options"]["initial_cost"] = 10
    evidence["stage_options"]["max_cost"] = 10
    plan = {
        "revised_operational_plans": [{
            "operational_plan_id": "conditional-dp-test",
            "deployment_positions_and_directions": [
                {"operator_id": "op", "tile": [1, 1], "direction": "RIGHT"},
            ],
            "action_timeline": [
                    {"action_type": "DEPLOY", "operator_id": "op", "frame": 0, "tile": [1, 1], "direction": "RIGHT"},
                    {"action_type": "DEPLOY", "operator_id": "op", "frame": 30, "tile": [1, 1], "direction": "RIGHT"},
            ],
        }],
    }
    _write(tmp_path, evidence, plan)
    result = compile_plan(tmp_path)
    assert result["classification"] == "STATIC_CONFLICT"
    assert {
        "frame": 2400,
        "operator_id": "op",
        "conflict": "CONDITIONAL_REDEPLOY_BASE_COST_UNAVAILABLE",
    } not in result["dp_ledger"]["conflicts"]
    assert {
        "frame": 30,
        "operator_id": "op",
        "conflict": "CONDITIONAL_REDEPLOY_BASE_COST_UNAVAILABLE",
        "balance_before": 1.0,
        "base_cost": 10.0,
    } in result["dp_ledger"]["conflicts"]
