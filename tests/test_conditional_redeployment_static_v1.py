from __future__ import annotations

import json
from pathlib import Path
import sys

from compile_r8_1_lowstar_c2_plan_v1 import compile_plan


ROOT = Path(__file__).resolve().parents[1]


def _write(tmp_path: Path, evidence: dict, plan: dict) -> None:
    (tmp_path / "llm_evidence_context.json").write_text(json.dumps(evidence), encoding="utf-8")
    (tmp_path / "llm_structured_output.json").write_text(json.dumps(plan), encoding="utf-8")


def test_conditional_redeploy_is_not_a_static_tactical_conflict(tmp_path):
    evidence = {
        "stage_options": {"initial_cost": 99, "max_cost": 99, "deployment_limit": 8},
        "stage_active_facts": {
            "roadblock_tiles_col_row": [],
            "deployable_ground_tiles_col_row": [[1, 1], [2, 1]],
            "deployable_high_ground_tiles_col_row": [],
        },
        "normal_low_star_catalog": [{
            "operator_id": "op",
            "identity": {"rarity": 3, "position": "MELEE"},
            "qualification": {"normal_mode": True},
            "stats": {"cost": 10, "redeploy_time": 70},
            "selected_skills": [],
        }],
    }
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
