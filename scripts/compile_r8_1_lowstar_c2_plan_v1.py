from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from kimi_readonly_tools import ReadOnlyQueryEngine, json_tile_to_runtime


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_lowstar_c2_tool_revision_v1"
FRAMES_PER_SECOND = 30.0


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operator_map(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["operator_id"]: row for row in evidence["normal_low_star_catalog"]}


def support_map(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["operator_id"]: row for row in evidence["normal_low_star_mechanism_support"]}


def actual_cost(operator: dict[str, Any], support: dict[str, Any]) -> float:
    cost = float(operator["stats"]["cost"])
    for talent in support.get("talent", {}).get("active_talents", []):
        if talent.get("status") != "RUNTIME_SUPPORTED_SELF_COST":
            continue
        for item in talent.get("blackboard", []):
            if item.get("key") == "cost":
                cost += float(item.get("value", 0.0))
    return max(0.0, cost)


def first_skill(operator: dict[str, Any]) -> dict[str, Any] | None:
    return (operator.get("skills") or [None])[0]


def extract_declared_targets(plan: dict[str, Any], operator_id: str) -> list[list[int]]:
    rows: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    keys = (
        "deployment_positions_and_directions", "corridor_responsibilities",
        "pressure_window_responsibilities", "opening_responsibilities",
        "optional_responsibilities", "conditional_responsibilities", "skill_intents",
    )
    for key in keys:
        for item in plan.get(key) or []:
            text = json.dumps(item, ensure_ascii=False)
            if operator_id not in text:
                continue
            for row, col in re.findall(r"\[(\d+),\s*(\d+)\]", text):
                coordinate = [int(row), int(col)]
                marker = (int(row), int(col))
                if marker not in seen:
                    rows.append(coordinate)
                    seen.add(marker)
    return rows


def build_dp_ledger(plan: dict[str, Any], catalog: dict[str, dict[str, Any]], supports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evidence_status_by_operator: dict[str, str] = {}
    readiness: dict[str, Any] = {}
    deployed_at: dict[str, int] = {}
    active_until: dict[str, int] = {}
    previous_ready: dict[str, int] = {}
    for action in plan["action_timeline"]:
        if action.get("action_type") != "DEPLOY":
            continue
        deployed_at[action["operator_id"]] = int(action["frame"])
    for action in plan["action_timeline"]:
        if action.get("action_type") != "ACTIVATE_SKILL":
            continue
        operator_id = action["operator_id"]
        if operator_id not in deployed_at:
            readiness[f"{operator_id}@{action['frame']}"] = {
                "status": "CONFLICT", "reason": "ACTIVATE_SKILL_BEFORE_DEPLOY",
            }
            continue
        skill = first_skill(catalog[operator_id])
        if skill is None:
            readiness[f"{operator_id}@{action['frame']}"] = {
                "status": "CONFLICT", "reason": "NO_SKILL_AT_DEBUG_CONFIGURATION",
            }
            continue
        frame = int(action["frame"])
        initial_sp = float(skill.get("initial_sp") or 0.0)
        sp_cost = float(skill.get("sp_cost") or 0.0)
        deployment_bonus = float(supports[operator_id].get("deployment_sp_bonus") or 0.0)
        available_sp = initial_sp + deployment_bonus + max(0.0, (frame - deployed_at[operator_id]) / FRAMES_PER_SECOND)
        if frame < previous_ready.get(operator_id, 0):
            readiness[f"{operator_id}@{frame}"] = {
                "status": "CONFLICT", "reason": "SP_NOT_READY", "available_sp_model": available_sp,
                "required_sp": sp_cost,
            }
            continue
        if available_sp + 1e-9 < sp_cost:
            readiness[f"{operator_id}@{frame}"] = {
                "status": "CONFLICT", "reason": "SP_NOT_READY", "available_sp_model": available_sp,
                "required_sp": sp_cost,
            }
            continue
        duration_frames = round(float(skill.get("duration") or 0.0) * FRAMES_PER_SECOND)
        active_until[operator_id] = frame + duration_frames
        previous_ready[operator_id] = active_until[operator_id] + round(sp_cost * FRAMES_PER_SECOND)
        readiness[f"{operator_id}@{frame}"] = {
            "status": "PASS_WITH_CONDITIONS", "available_sp_model": available_sp,
            "required_sp": sp_cost, "active_until_frame": active_until[operator_id],
            "next_model_ready_frame": previous_ready[operator_id],
        }

    dp = float(evidence_stage_initial_dp())
    rows = [{
        "frame": 0, "event": "STAGE_INITIAL_DP", "delta": dp,
        "balance_before": 0.0, "balance_after": dp,
        "source": "stage_options.initial_cost; natural DP model +1/s",
    }]
    previous_frame = 0
    conflicts: list[dict[str, Any]] = []
    for action in plan["action_timeline"]:
        frame = int(action["frame"])
        if frame < previous_frame:
            conflicts.append({"frame": frame, "conflict": "ACTION_FRAME_OUT_OF_ORDER"})
            continue
        if frame > previous_frame:
            before = dp
            dp = min(999.0, dp + (frame - previous_frame) / FRAMES_PER_SECOND)
            rows.append({"frame": frame, "event": "NATURAL_DP", "delta": dp - before,
                         "balance_before": before, "balance_after": dp,
                         "source": "stage costIncreaseTime=1 second; 30 FPS action clock"})
            previous_frame = frame
        action_type = action.get("action_type")
        operator_id = action.get("operator_id")
        if action_type == "ACTIVATE_SKILL":
            key = f"{operator_id}@{frame}"
            check = readiness.get(key, {"status": "UNKNOWN", "reason": "READINESS_CHECK_MISSING"})
            skill = first_skill(catalog[operator_id]) if operator_id in catalog else None
            skill_dp = float((skill or {}).get("blackboard", {}).get("cost", 0.0) or 0.0)
            if check.get("status") == "PASS_WITH_CONDITIONS" and skill_dp:
                before = dp
                dp = min(999.0, dp + skill_dp)
                rows.append({"frame": frame, "event": "SKILL_DP_INCOME", "operator_id": operator_id,
                             "delta": dp - before, "balance_before": before, "balance_after": dp,
                             "source": "skill blackboard cost; readiness is conditional on current model"})
        elif action_type == "DEPLOY":
            cost = actual_cost(catalog[operator_id], supports[operator_id])
            before = dp
            if dp + 1e-9 < cost:
                conflicts.append({"frame": frame, "operator_id": operator_id, "conflict": "INSUFFICIENT_DP",
                                  "balance_before": before, "cost": cost})
                rows.append({"frame": frame, "event": "DEPLOY_COST_REJECTED", "operator_id": operator_id,
                             "cost": cost, "balance_before": before, "balance_after": before,
                             "status": "CONFLICT"})
            else:
                dp -= cost
                rows.append({"frame": frame, "event": "DEPLOY_COST", "operator_id": operator_id,
                             "cost": cost, "balance_before": before, "balance_after": dp,
                             "status": "PAID"})
    return {
        "schema_version": "R8_1_LOWSTAR_C2_STATIC_DP_LEDGER_V1",
        "initial_dp": evidence_stage_initial_dp(),
        "natural_dp_per_second": 1.0,
        "retreat_refund": "UNKNOWN_NOT_COUNTED",
        "merchant_upkeep": "NOT_APPLICABLE_UNLESS_MERCHANT_DEPLOYED",
        "skill_readiness": readiness,
        "entries": rows,
        "final_balance": dp,
        "conflicts": conflicts,
    }


def evidence_stage_initial_dp() -> float:
    # The compiler is invoked only after the prepared evidence exists.
    stage_options = load(OUT / "llm_evidence_context.json")["stage_options"]
    return float(stage_options["initial_cost"])


def compile_plan() -> dict[str, Any]:
    evidence = load(OUT / "llm_evidence_context.json")
    parsed = load(OUT / "llm_structured_output.json")
    plans = parsed.get("revised_operational_plans", [])
    plan = plans[0]
    catalog = operator_map(evidence)
    supports = support_map(evidence)
    engine = ReadOnlyQueryEngine(evidence_path=OUT / "llm_evidence_context.json")
    active = evidence["stage_active_facts"]
    roadblocks = {tuple(item) for item in active["roadblock_tiles_col_row"]}
    ground = {tuple(item) for item in active["deployable_ground_tiles_col_row"]}
    high = {tuple(item) for item in active["deployable_high_ground_tiles_col_row"]}
    actions = plan["action_timeline"]

    deployment_checks: list[dict[str, Any]] = []
    range_checks: list[dict[str, Any]] = []
    qualification_checks: list[dict[str, Any]] = []
    deployment_positions = {(row.get("operator_id"), tuple(row.get("tile") or []), row.get("direction"))
                            for row in plan.get("deployment_positions_and_directions") or []}
    deployed: dict[str, int] = {}
    tile_occupancy: dict[tuple[int, int], str] = {}
    redeploy_available: dict[str, int] = {}
    deployment_limit = int(evidence["stage_options"]["deployment_limit"])
    deployment_limit_conflicts: list[dict[str, Any]] = []
    tile_conflicts: list[dict[str, Any]] = []

    for index, action in enumerate(actions):
        action_type = action.get("action_type")
        frame = int(action.get("frame", -1))
        operator_id = action.get("operator_id")
        if action_type == "DEPLOY":
            if len(deployed) >= deployment_limit:
                deployment_limit_conflicts.append({"frame": frame, "deployed_count": len(deployed), "limit": deployment_limit})
            tile_json = action.get("tile")
            direction = action.get("direction")
            runtime_tile = json_tile_to_runtime(tile_json, f"action[{index}].tile")
            marker = (operator_id, tuple(tile_json or []), direction)
            declaration_match = marker in deployment_positions
            operator = catalog.get(operator_id, {})
            support = supports.get(operator_id, {})
            position = operator.get("identity", {}).get("position")
            qualification = operator.get("qualification", {})
            expected_tile_kind = ground if position == "MELEE" else high if position == "RANGED" else set()
            legal_tile = runtime_tile in expected_tile_kind
            roadblock = runtime_tile in roadblocks
            occupied = runtime_tile in tile_occupancy
            redeploy_ready = frame >= redeploy_available.get(operator_id, 0)
            not_already_deployed = operator_id not in deployed
            status = "PASS_WITH_CONDITIONS"
            reasons: list[str] = []
            if not qualification.get("normal_mode"):
                status = "CONFLICT"; reasons.append("NOT_NORMAL_MODE")
            if not 1 <= int(operator.get("identity", {}).get("rarity", 0)) <= 3:
                status = "CONFLICT"; reasons.append("RARITY_OUTSIDE_1_TO_3")
            if not declaration_match:
                status = "CONFLICT"; reasons.append("DEPLOYMENT_DECLARATION_MISMATCH")
            if roadblock:
                status = "CONFLICT"; reasons.append("ACTIVE_ROADBLOCK_TILE")
            elif not legal_tile:
                status = "CONFLICT"; reasons.append("TILE_NOT_LEGAL_FOR_POSITION")
            if occupied:
                status = "CONFLICT"; reasons.append("TILE_OCCUPIED")
            if not redeploy_ready:
                status = "CONFLICT"; reasons.append("REDEPLOY_COOLDOWN_ACTIVE")
            if not not_already_deployed:
                status = "CONFLICT"; reasons.append("OPERATOR_ALREADY_DEPLOYED")
            deployment_checks.append({
                "action_index": index, "operator_id": operator_id, "frame": frame,
                "tile_json_row_col": tile_json, "tile_runtime_col_row": list(runtime_tile),
                "direction": direction, "declaration_match": declaration_match,
                "position": position, "active_roadblock": roadblock,
                "tile_legal_for_position": legal_tile, "tile_occupied": occupied,
                "redeploy_available": redeploy_ready, "status": status,
                "reasons": reasons,
            })
            qualification_checks.append({
                "operator_id": operator_id,
                "qualification": qualification,
                "identity": operator.get("identity"),
                "configuration": support.get("debug_configuration"),
                "status": "PASS_WITH_CONDITIONS" if status != "CONFLICT" or all(
                    reason in {"ACTIVE_ROADBLOCK_TILE", "TILE_NOT_LEGAL_FOR_POSITION", "TILE_OCCUPIED",
                               "REDEPLOY_COOLDOWN_ACTIVE", "OPERATOR_ALREADY_DEPLOYED", "DEPLOYMENT_DECLARATION_MISMATCH"}
                    for reason in reasons
                ) else "CONFLICT",
            })
            if status == "CONFLICT" and any(reason in {"ACTIVE_ROADBLOCK_TILE", "TILE_NOT_LEGAL_FOR_POSITION", "TILE_OCCUPIED"} for reason in reasons):
                tile_conflicts.append(deployment_checks[-1])
                continue
            if legal_tile and not roadblock and not occupied and not_already_deployed and redeploy_ready:
                deployed[operator_id] = frame
                tile_occupancy[runtime_tile] = operator_id
            declared_targets = extract_declared_targets(plan, operator_id)
            query = {
                "operator_id": operator_id,
                "configuration": support.get("debug_configuration"),
                "tile": tile_json,
                "direction": direction,
                "targets": [{"label": f"declared_{index}", "tile": target} for index, target in enumerate(declared_targets)],
            }
            try:
                result = engine.query_range_coverage(query)
                uncovered = [row["tile"] for row in result["targets"] if not row["covered"]]
                range_status = "PASS_WITH_CONDITIONS" if not uncovered else "CONFLICT"
                if not declared_targets:
                    range_status = "UNKNOWN_NO_DECLARED_TARGET_TILES"
                range_checks.append({
                    "action_index": index, "operator_id": operator_id, "frame": frame,
                    "tile_json_row_col": tile_json, "direction": direction,
                    "range_id": result.get("range_id"),
                    "covered_tiles_json_row_col": result.get("covered_tiles_json_row_col"),
                    "declared_targets_json_row_col": declared_targets,
                    "uncovered_declared_targets": uncovered,
                    "status": range_status,
                    "evidence_status": "CONDITIONAL_RANGE_MODEL_NOT_CLIENT_GEOMETRY_PROOF",
                })
            except Exception as exc:
                range_checks.append({
                    "action_index": index, "operator_id": operator_id, "frame": frame,
                    "status": "UNKNOWN", "error": str(exc),
                })
        elif action_type == "RETREAT":
            if operator_id in deployed:
                redeploy_time = float(catalog[operator_id]["stats"]["redeploy_time"])
                tile_runtime = next((tile for tile, occupant in tile_occupancy.items() if occupant == operator_id), None)
                if tile_runtime is not None:
                    tile_occupancy.pop(tile_runtime, None)
                deployed.pop(operator_id, None)
                redeploy_available[operator_id] = frame + round(redeploy_time * FRAMES_PER_SECOND)

    ledger = build_dp_ledger(plan, catalog, supports)
    skill_conflicts = [
        {"operator_id": key.split("@")[0], "frame": int(key.split("@")[1]), **row}
        for key, row in ledger["skill_readiness"].items() if row.get("status") == "CONFLICT"
    ]
    conflicts = []
    conflicts.extend(tile_conflicts)
    conflicts.extend(deployment_limit_conflicts)
    conflicts.extend(ledger["conflicts"])
    conflicts.extend(skill_conflicts)
    conflicts.extend([row for row in deployment_checks if row["status"] == "CONFLICT"])
    conflicts.extend([row for row in range_checks if row["status"] == "CONFLICT"])
    conflicts.extend([
        {"action_index": index, "conflict": "ACTION_FRAME_OUT_OF_ORDER"}
        for index in range(1, len(actions)) if int(actions[index]["frame"]) < int(actions[index - 1]["frame"])
    ])
    unknowns = [row for row in range_checks if row.get("status") == "UNKNOWN"]
    classification = "STATIC_CONFLICT" if conflicts else (
        "STATIC_CONTRACT_CHECKED_CONDITIONAL" if unknowns else "STATIC_CONTRACT_CHECKED_NO_RANGE_TARGET_UNKNOWN"
    )
    operational_verified = not conflicts and not unknowns
    certificate = {
        "schema_version": "R8_1_LOWSTAR_C2_STATIC_FIDELITY_CHECK_V1",
        "classification": classification,
        "operationally_verified": False,
        "faithful_certificate": None,
        "battle_feasibility": "UNKNOWN_NO_SIMULATION",
        "scope": "Original fixed actions only; no automatic action repair, search or simulation.",
        "checks": {
            "qualification": qualification_checks,
            "deployment": deployment_checks,
            "range_and_declared_responsibility": range_checks,
            "deployment_limit": {
                "limit": deployment_limit,
                "conflicts": deployment_limit_conflicts,
            },
            "retreat_semantics": {
                "processed_actions": len([row for row in actions if row.get("action_type") == "RETREAT"]),
                "redeploy_cooldown_model": "redeploy_time * 30 frames; refund UNKNOWN and not counted",
            },
        },
        "dp_ledger": ledger,
        "conflicts": conflicts,
        "unknowns": unknowns,
        "phase_semantics": {
            "status": "STRUCTURAL_DECLARATION_CHECK_ONLY",
            "battle_phase_objects": len(plan.get("battle_phases") or []),
            "formation_transitions": len(plan.get("formation_transitions") or []),
            "corridor_responsibilities": len(plan.get("corridor_responsibilities") or []),
            "pressure_window_responsibilities": len(plan.get("pressure_window_responsibilities") or []),
            "limitations": ["This check cannot prove enemy survival, damage cooperation, pathing or handover timing."],
        },
        "source_manifest": {
            "evidence": file_record(OUT / "llm_evidence_context.json"),
            "plan": file_record(OUT / "llm_structured_output.json"),
            "compiler": file_record(Path(__file__)),
        },
    }
    action_candidate = {
        "schema_version": "R8_1_LOWSTAR_C2_DIRECTION_COMPLETE_ACTION_CANDIDATE_V1",
        "operational_plan_id": plan.get("operational_plan_id"),
        "actions": actions,
        "classification": classification,
        "operationally_verified": False,
        "no_stage_simulation": True,
    }
    write_json("static_compile_results.json", certificate)
    write_json("direction_complete_action_candidate.json", action_candidate)
    write_json("static_compile_final_status.json", {
        "schema_version": "R8_1_LOWSTAR_C2_STATIC_COMPILE_FINAL_STATUS_V1",
        "plan_id": plan.get("operational_plan_id"),
        "classification": classification,
        "conflict_count": len(conflicts),
        "unknown_count": len(unknowns),
        "stage_simulations": 0,
        "tactical_search_expansions": 0,
        "faithful_certificate": None,
    })
    return certificate


if __name__ == "__main__":
    compile_plan()
