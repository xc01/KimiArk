from __future__ import annotations

import hashlib
from math import floor
import json
from pathlib import Path
import sys
from typing import Any

from kimi_readonly_tools import ReadOnlyQueryEngine, json_tile_to_runtime


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_lowstar_c2_compact_tool_revision_v2"
FRAMES_PER_SECOND = 30.0


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_json_at(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    try:
        relative_path = path.relative_to(ROOT)
    except ValueError:
        relative_path = path
    return {"bytes": path.stat().st_size, "path": str(relative_path), "sha256": sha256(path)}


def operator_map(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["operator_id"]: row for row in evidence["normal_low_star_catalog"]}


def support_map(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["operator_id"]: row.get("runtime_support") or {}
        for row in evidence["normal_low_star_catalog"]
    }


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
    return (operator.get("selected_skills") or [None])[0]


def uncovered_declared_targets(range_result: dict[str, Any]) -> list[Any]:
    return [
        row["tile_json_row_col"]
        for row in range_result.get("targets") or []
        if row.get("covered") is False
    ]


def declared_target_objects(declared: dict[str, Any]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for index, target in enumerate(declared.get("targets") or []):
        if isinstance(target, list):
            objects.append({"label": f"declared_{index}", "tile": target})
        elif isinstance(target, dict) and isinstance(target.get("tile"), list):
            objects.append(target)
        else:
            raise ValueError("declared target must be [row,col] or {label,tile}")
    return objects


def supported_auto_dp_skill(operator: dict[str, Any]) -> dict[str, Any] | None:
    skill = first_skill(operator)
    support = next((
        row for row in (operator.get("runtime_support", {}).get("skills") or [])
        if skill is not None and row.get("skill_id") == skill.get("skill_id")
    ), None)
    values = (skill or {}).get("blackboard") or {}
    if (
        skill is not None
        and skill.get("skill_type") == "AUTO"
        and skill.get("sp_type") == "INCREASE_WITH_TIME"
        and float(skill.get("duration") or 0.0) == 0.0
        and isinstance(values.get("cost"), (int, float))
        and support is not None and support.get("status") == "EXECUTABLE_APPROXIMATED"
    ):
        return skill
    return None


def automatic_dp_skill_events(
    plan: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    supports: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    for action_index, action in enumerate(plan["action_timeline"]):
        frame = int(action["frame"])
        operator_id = action.get("operator_id")
        action_type = action.get("action_type")
        for skill_state in active.values():
            while skill_state["next_frame"] < frame:
                trigger_frame = skill_state["next_frame"]
                skill = skill_state["skill"]
                events.append({
                    "action_index": action_index, "frame": trigger_frame,
                    "operator_id": skill_state["operator_id"],
                    "amount": float(skill["blackboard"]["cost"]),
                    "ordering": "BEFORE_ACTIONS",
                    "cycle": skill_state["cycle"],
                })
                skill_state["next_frame"] = trigger_frame + round(float(skill["sp_cost"]) * FRAMES_PER_SECOND)
                skill_state["cycle"] += 1
        if action_type == "DEPLOY":
            skill = supported_auto_dp_skill(catalog.get(operator_id, {}))
            if skill is None:
                continue
            deployment_bonus = float(supports[operator_id].get("deployment_sp_bonus") or 0.0)
            initial_sp = float(skill.get("initial_sp") or 0.0)
            sp_cost = float(skill["sp_cost"])
            ready_delta = max(0.0, sp_cost - min(initial_sp + deployment_bonus, sp_cost))
            next_frame = frame + round(ready_delta * FRAMES_PER_SECOND)
            state = {"operator_id": operator_id, "skill": skill, "next_frame": next_frame, "cycle": 0}
            active[operator_id] = state
            if next_frame <= frame:
                events.append({
                    "action_index": action_index, "frame": frame,
                    "operator_id": operator_id, "amount": float(skill["blackboard"]["cost"]),
                    "ordering": "AFTER_DEPLOY_SAME_FRAME", "cycle": 0,
                })
                state["next_frame"] = frame + round(sp_cost * FRAMES_PER_SECOND)
                state["cycle"] = 1
        elif action_type == "RETREAT":
            active.pop(operator_id, None)
    return events


def structured_range_checks(plan: dict[str, Any], action: dict[str, Any]) -> list[dict[str, Any]]:
    rows = plan.get("declared_range_checks") or []
    return [
        row for row in rows
        if row.get("operator_id") == action.get("operator_id")
        and list(row.get("tile") or []) == list(action.get("tile") or [])
        and row.get("direction") == action.get("direction")
    ]


def evidence_stage_initial_dp(input_dir: Path) -> float:
    return float(evidence_stage_options(input_dir)["initial_cost"])


def compile_plan(input_dir: Path = OUT) -> dict[str, Any]:
    evidence = load(input_dir / "llm_evidence_context.json")
    parsed = load(input_dir / "llm_structured_output.json")
    plans = parsed.get("revised_operational_plans", [])
    plan = plans[0]
    catalog = operator_map(evidence)
    supports = support_map(evidence)
    engine = ReadOnlyQueryEngine(evidence_path=input_dir / "llm_evidence_context.json")
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
    deployment_slot_count = 0
    deployment_limit = int(evidence["stage_options"]["deployment_limit"])
    deployment_limit_conflicts: list[dict[str, Any]] = []
    tile_conflicts: list[dict[str, Any]] = []
    conditional_redeploys: list[dict[str, Any]] = []

    for index, action in enumerate(actions):
        action_type = action.get("action_type")
        frame = int(action.get("frame", -1))
        operator_id = action.get("operator_id")
        if action_type == "DEPLOY":
            operator = catalog.get(operator_id, {})
            identity = operator.get("identity", {})
            raw_rarity = identity.get("rarity")
            try:
                rarity = int(raw_rarity)
                has_valid_rarity = True
            except (TypeError, ValueError):
                rarity = 0
                has_valid_rarity = False
            occupies_normal_deployment_slot = has_valid_rarity and rarity >= 2
            if occupies_normal_deployment_slot and deployment_slot_count >= deployment_limit:
                deployment_limit_conflicts.append({"frame": frame, "deployed_count": deployment_slot_count, "limit": deployment_limit})
            tile_json = action.get("tile")
            direction = action.get("direction")
            runtime_tile = json_tile_to_runtime(tile_json, f"action[{index}].tile")
            marker = (operator_id, tuple(tile_json or []), direction)
            declaration_match = marker in deployment_positions
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
            if not has_valid_rarity:
                status = "CONFLICT"; reasons.append("MISSING_OR_INVALID_RARITY")
            if has_valid_rarity and not 1 <= rarity <= 3:
                status = "CONFLICT"; reasons.append("RARITY_OUTSIDE_1_TO_3")
            if not declaration_match:
                status = "CONFLICT"; reasons.append("DEPLOYMENT_DECLARATION_MISMATCH")
            if roadblock:
                status = "CONFLICT"; reasons.append("ACTIVE_ROADBLOCK_TILE")
            elif not legal_tile:
                status = "CONFLICT"; reasons.append("TILE_NOT_LEGAL_FOR_POSITION")
            if not not_already_deployed:
                reasons.append("CONDITIONAL_REDEPLOY_AWAITING_EXIT")
                observed_occupant = tile_occupancy.get(runtime_tile)
                if observed_occupant not in {None, operator_id}:
                    status = "CONFLICT"
                    reasons.append("TILE_OCCUPIED_BY_ANOTHER_OPERATOR")
                else:
                    cooldown_frame = redeploy_available.get(operator_id)
                    conditional_redeploys.append({
                        "action_index": index,
                        "operator_id": operator_id,
                        "frame": frame,
                        "tile_runtime_col_row": list(runtime_tile),
                        "exit_condition": "RETREAT_OR_DEATH_BEFORE_DEPLOY",
                        "exit_deadline_frame": frame,
                        "cooldown_start_frame": "UNKNOWN_RETREAT_OR_DEATH_TIME",
                        "cooldown_end_frame": cooldown_frame,
                        "cooldown_end_frame_status": (
                            "KNOWN_AFTER_EXPLICIT_RETREAT"
                            if cooldown_frame is not None
                            else "UNKNOWN_UNTIL_RUNTIME_EXIT"
                        ),
                        "base_redeploy_cost": actual_cost(operator, support),
                        "cost_growth_and_special_rules": "UNKNOWN_REQUIRES_RUNTIME_VERIFICATION",
                        "tile_condition": (
                            "SELF_OCCUPIED_TILE_MUST_RELEASE"
                            if observed_occupant == operator_id
                            else "TARGET_TILE_MUST_BE_FREE"
                        ),
                        "deployment_slot_condition": "PRIOR_DEPLOYMENT_MUST_RELEASE_SLOT",
                        "generation_state": "HP_SP_SKILL_AND_COOLDOWN_RESET_REQUIRES_RUNTIME_VERIFICATION",
                        "dp_ledger_status": "CONDITIONAL_REDEPLOY_DP_RESERVED",
                    })
            else:
                if occupied:
                    status = "CONFLICT"; reasons.append("TILE_OCCUPIED")
                if not redeploy_ready:
                    status = "CONFLICT"; reasons.append("REDEPLOY_COOLDOWN_ACTIVE")
            deployment_checks.append({
                "action_index": index, "operator_id": operator_id, "frame": frame,
                "tile_json_row_col": tile_json, "tile_runtime_col_row": list(runtime_tile),
                "direction": direction, "declaration_match": declaration_match,
                "position": position, "active_roadblock": roadblock,
                "tile_legal_for_position": legal_tile, "tile_occupied": occupied,
                "tile_occupied_by_other": occupied and tile_occupancy.get(runtime_tile) != operator_id,
                "tile_occupant": tile_occupancy.get(runtime_tile),
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
            if (
                has_valid_rarity
                and legal_tile
                and not roadblock
                and not occupied
                and not_already_deployed
                and redeploy_ready
            ):
                deployed[operator_id] = frame
                tile_occupancy[runtime_tile] = operator_id
                if rarity >= 2:
                    deployment_slot_count += 1
            declared_rows = structured_range_checks(plan, action)
            if not declared_rows:
                range_checks.append({
                    "action_index": index, "operator_id": operator_id, "frame": frame,
                    "tile_json_row_col": tile_json, "direction": direction,
                    "status": "UNKNOWN_NO_STRUCTURED_RANGE_RESPONSIBILITY",
                    "evidence_status": "UNKNOWN",
                })
            for declared_index, declared in enumerate(declared_rows):
                unknown_reason = declared.get("unknown_reason")
                try:
                    targets = declared_target_objects(declared)
                except ValueError as exc:
                    targets = []
                    unknown_reason = str(exc)
                if unknown_reason or not targets:
                    range_checks.append({
                        "action_index": index, "declared_index": declared_index,
                        "operator_id": operator_id, "frame": frame,
                        "tile_json_row_col": tile_json, "direction": direction,
                        "responsibility_kind": declared.get("responsibility_kind"),
                        "unknown_reason": unknown_reason or "NO_TARGETS",
                        "status": "UNKNOWN",
                        "evidence_status": "UNKNOWN",
                    })
                    continue
                query = {
                    "operator_id": operator_id,
                    "configuration": operator.get("debug_configuration"),
                    "tile": tile_json,
                    "direction": direction,
                    "targets": targets,
                }
                try:
                    result = engine.query_range_coverage(query)
                    uncovered = uncovered_declared_targets(result)
                    range_status = "PASS_WITH_CONDITIONS" if not uncovered else "CONFLICT"
                    range_checks.append({
                        "action_index": index, "declared_index": declared_index,
                        "operator_id": operator_id, "frame": frame,
                        "tile_json_row_col": tile_json, "direction": direction,
                        "responsibility_kind": declared.get("responsibility_kind"),
                        "range_id": result.get("range_id"),
                        "covered_tiles_json_row_col": result.get("covered_tiles_json_row_col"),
                        "declared_targets_json_row_col": [row.get("tile") for row in targets],
                        "uncovered_declared_targets": uncovered,
                        "status": range_status,
                        "evidence_status": "CONDITIONAL_RANGE_MODEL_NOT_CLIENT_GEOMETRY_PROOF",
                    })
                except Exception as exc:
                    range_checks.append({
                        "action_index": index, "declared_index": declared_index,
                        "operator_id": operator_id, "frame": frame,
                        "tile_json_row_col": tile_json, "direction": direction,
                        "status": "UNKNOWN", "error": str(exc),
                        "evidence_status": "UNKNOWN",
                    })
        elif action_type == "RETREAT":
            if operator_id in deployed:
                redeploy_time = float(catalog[operator_id]["stats"]["redeploy_time"])
                tile_runtime = next((tile for tile, occupant in tile_occupancy.items() if occupant == operator_id), None)
                if tile_runtime is not None:
                    tile_occupancy.pop(tile_runtime, None)
                deployed.pop(operator_id, None)
                if int(catalog[operator_id].get("identity", {}).get("rarity", 0)) >= 2:
                    deployment_slot_count = max(0, deployment_slot_count - 1)
                redeploy_available[operator_id] = frame + round(redeploy_time * FRAMES_PER_SECOND)

    ledger = build_dp_ledger(plan, catalog, supports, input_dir)
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
        "STATIC_CONTRACT_CHECKED_CONDITIONAL_REDEPLOY" if conditional_redeploys else (
            "STATIC_CONTRACT_CHECKED_CONDITIONAL" if unknowns else "STATIC_CONTRACT_CHECKED_NO_RANGE_TARGET_UNKNOWN"
        )
    )
    operational_verified = not conflicts and not unknowns
    certificate = {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_STATIC_FIDELITY_CHECK_V1",
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
            "conditional_redeploys": conditional_redeploys,
        },
        "dp_ledger": ledger,
        "conflicts": conflicts,
        "unknowns": unknowns,
        "conditional_redeploys": conditional_redeploys,
        "phase_semantics": {
            "status": "UNKNOWN_NOT_PROVEN_FROM_ACTIONS",
            "limitations": [
                "Phase handover, route ownership, damage cooperation, pathing, blocking duration and healing timing are not proven by this static check.",
                "Structured range checks cover only explicit declared target tiles; absent or conditional declarations remain UNKNOWN.",
            ],
        },
        "source_manifest": {
            "evidence": file_record(input_dir / "llm_evidence_context.json"),
            "plan": file_record(input_dir / "llm_structured_output.json"),
            "compiler": file_record(Path(__file__)),
        },
    }
    action_candidate = {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_DIRECTION_COMPLETE_ACTION_CANDIDATE_V1",
        "operational_plan_id": plan.get("operational_plan_id"),
        "actions": actions,
        "classification": classification,
        "operationally_verified": False,
        "no_stage_simulation": True,
    }
    write_json_at(input_dir / "static_compile_results.json", certificate)
    write_json_at(input_dir / "direction_complete_action_candidate.json", action_candidate)
    write_json_at(input_dir / "static_compile_final_status.json", {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_STATIC_COMPILE_FINAL_STATUS_V1",
        "plan_id": plan.get("operational_plan_id"),
        "classification": classification,
        "conflict_count": len(conflicts),
        "unknown_count": len(unknowns),
        "stage_simulations": 0,
        "tactical_search_expansions": 0,
        "faithful_certificate": None,
    })
    return certificate


def evidence_stage_options(input_dir: Path) -> dict[str, Any]:
    return load(input_dir / "llm_evidence_context.json")["stage_options"]


def build_dp_ledger(
    plan: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    supports: dict[str, dict[str, Any]],
    input_dir: Path,
) -> dict[str, Any]:
    readiness: dict[str, Any] = {}
    dp = float(evidence_stage_initial_dp(input_dir))
    rows: list[dict[str, Any]] = [{"frame": 0, "event": "STAGE_INITIAL_DP", "delta": dp,
                                  "balance_before": 0.0, "balance_after": dp,
                                  "source": "stage_options.initial_cost; natural DP model +1/s"}]
    conflicts: list[dict[str, Any]] = []
    auto_events = automatic_dp_skill_events(plan, catalog, supports)
    auto_before: dict[int, list[dict[str, Any]]] = {}
    auto_after: dict[int, list[dict[str, Any]]] = {}
    for row in auto_events:
        target = auto_before if row["ordering"] == "BEFORE_ACTIONS" else auto_after
        target.setdefault(int(row["frame"]), []).append(row)
    scheduled_frames = sorted({int(action["frame"]) for action in plan["action_timeline"]}
                              | set(auto_before) | set(auto_after))
    actions_by_frame: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for index, action in enumerate(plan["action_timeline"]):
        actions_by_frame.setdefault(int(action["frame"]), []).append((index, action))
    deployed_at: dict[str, int] = {}
    active_generations: dict[str, int] = {}
    active_operators: set[str] = set()
    previous_ready: dict[str, int] = {}
    deployment_slot_count = 0
    stage_options = evidence_stage_options(input_dir)
    max_dp = float(stage_options.get("max_cost") or 99)
    deployment_limit = int(stage_options.get("deployment_limit") or 99)
    previous_frame = 0
    conditional_dp_reservations: list[dict[str, Any]] = []
    for frame in scheduled_frames:
        if frame < previous_frame:
            conflicts.append({"frame": frame, "conflict": "ACTION_FRAME_OUT_OF_ORDER"})
        if frame > previous_frame:
            before = dp
            dp = min(max_dp, dp + (frame - previous_frame) / FRAMES_PER_SECOND)
            rows.append({"frame": frame, "event": "NATURAL_DP", "delta": dp - before,
                         "balance_before": before, "balance_after": dp,
                         "source": "stage costIncreaseTime=1 second; 30 FPS action clock"})
            previous_frame = frame
        for event in auto_before.get(frame, []):
            before = dp
            dp = min(max_dp, dp + float(event["amount"]))
            rows.append({"frame": frame, "event": "AUTO_SKILL_DP_INCOME", "operator_id": event["operator_id"],
                         "cycle": event["cycle"], "delta": dp - before, "balance_before": before,
                         "balance_after": dp, "status": "CONDITIONAL_ON_SURVIVAL_AND_CONTINUOUS_DEPLOYMENT",
                         "source": "AUTO INCREASE_WITH_TIME duration=0 cost pattern; same public adapter timing model"})
        for _, action in actions_by_frame.get(frame, []):
            action_type = action.get("action_type")
            operator_id = action.get("operator_id")
            if action_type == "DEPLOY":
                rarity = int((catalog.get(operator_id, {}).get("identity") or {}).get("rarity") or 1)
                if operator_id in active_operators:
                    base_cost = actual_cost(catalog[operator_id], supports[operator_id])
                    reservation_status = "CONDITIONAL_ON_EXIT_COOLDOWN_TILE_AND_DP"
                    if dp + 1e-9 < base_cost:
                        reservation_status = "CONFLICT"
                        conflicts.append({
                            "frame": frame, "operator_id": operator_id,
                            "conflict": "CONDITIONAL_REDEPLOY_BASE_COST_UNAVAILABLE",
                            "balance_before": dp, "base_cost": base_cost,
                        })
                    row = {
                        "frame": frame, "event": "CONDITIONAL_REDEPLOY_DP_RESERVATION",
                        "operator_id": operator_id, "base_cost": base_cost,
                        "balance_before": dp, "balance_after": dp,
                        "status": reservation_status,
                        "cost_growth_and_special_rules": "UNKNOWN_REQUIRES_RUNTIME_VERIFICATION",
                        "conditions": [
                            "operator exits by retreat or death before this frame",
                            "redeploy cooldown has elapsed",
                            "target tile and deployment slot are free",
                            "actual redeploy cost is paid; growth and special rules UNKNOWN",
                        ],
                    }
                    rows.append(row)
                    if reservation_status != "CONFLICT":
                        conditional_dp_reservations.append(row)
                    continue
                if rarity >= 2 and deployment_slot_count >= deployment_limit:
                    conflicts.append({"frame": frame, "operator_id": operator_id,
                                      "conflict": "DEPLOYMENT_LIMIT_REACHED"})
                    rows.append({"frame": frame, "event": "DEPLOY_REJECTED", "operator_id": operator_id,
                                 "status": "CONFLICT"})
                    continue
                cost = actual_cost(catalog[operator_id], supports[operator_id])
                before = dp
                if dp + 1e-9 < cost:
                    conflicts.append({"frame": frame, "operator_id": operator_id,
                                      "conflict": "INSUFFICIENT_DP", "balance_before": before, "cost": cost})
                    rows.append({"frame": frame, "event": "DEPLOY_COST_REJECTED", "operator_id": operator_id,
                                 "cost": cost, "balance_before": before, "balance_after": before,
                                 "status": "CONFLICT"})
                    continue
                dp -= cost
                deployed_at[operator_id] = frame
                active_generations[operator_id] = active_generations.get(operator_id, 0) + 1
                active_operators.add(operator_id)
                if rarity >= 2:
                    deployment_slot_count += 1
                previous_ready.pop(operator_id, None)
                rows.append({"frame": frame, "event": "DEPLOY_COST", "operator_id": operator_id,
                             "cost": cost, "balance_before": before, "balance_after": dp,
                             "status": "PAID", "generation": active_generations[operator_id]})
            elif action_type == "RETREAT":
                if operator_id not in active_operators:
                    continue
                cost = actual_cost(catalog[operator_id], supports[operator_id])
                refund = floor(cost * 0.5)
                before = dp
                dp = min(max_dp, dp + refund)
                active_operators.remove(operator_id)
                if int((catalog.get(operator_id, {}).get("identity") or {}).get("rarity") or 1) >= 2:
                    deployment_slot_count -= 1
                rows.append({"frame": frame, "event": "RETREAT_REFUND", "operator_id": operator_id,
                             "delta": refund, "balance_before": before, "balance_after": dp,
                             "status": "CONDITIONAL_ON_OPERATOR_SURVIVAL"})
            elif action_type == "ACTIVATE_SKILL":
                key = f"{operator_id}@{frame}"
                if operator_id not in active_operators:
                    readiness[key] = {"status": "CONFLICT", "reason": "ACTIVATE_SKILL_BEFORE_DEPLOY"}
                    continue
                skill = first_skill(catalog[operator_id])
                if skill is None:
                    readiness[key] = {"status": "CONFLICT", "reason": "NO_SKILL_AT_DEBUG_CONFIGURATION"}
                    continue
                deploy_frame = deployed_at[operator_id]
                initial_sp = float(skill.get("initial_sp") or 0.0)
                sp_cost = float(skill.get("sp_cost") or 0.0)
                deployment_bonus = float(supports[operator_id].get("deployment_sp_bonus") or 0.0)
                available_sp = initial_sp + deployment_bonus + max(0.0, (frame - deploy_frame) / FRAMES_PER_SECOND)
                if frame < previous_ready.get(operator_id, 0) or available_sp + 1e-9 < sp_cost:
                    readiness[key] = {"status": "CONFLICT", "reason": "SP_NOT_READY",
                                      "available_sp_model": available_sp, "required_sp": sp_cost,
                                      "generation": active_generations[operator_id]}
                    continue
                duration_frames = round(float(skill.get("duration") or 0.0) * FRAMES_PER_SECOND)
                active_until = frame + duration_frames
                previous_ready[operator_id] = active_until + round(sp_cost * FRAMES_PER_SECOND)
                readiness[key] = {"status": "PASS_WITH_CONDITIONS", "available_sp_model": available_sp,
                                  "required_sp": sp_cost, "active_until_frame": active_until,
                                  "next_model_ready_frame": previous_ready[operator_id],
                                  "generation": active_generations[operator_id]}
                skill_dp = float(skill.get("blackboard", {}).get("cost", 0.0) or 0.0)
                if skill_dp:
                    before = dp
                    dp = min(max_dp, dp + skill_dp)
                    rows.append({"frame": frame, "event": "SKILL_DP_INCOME", "operator_id": operator_id,
                                 "delta": dp - before, "balance_before": before, "balance_after": dp,
                                 "source": "skill blackboard cost; readiness is conditional on current model"})
        for event in auto_after.get(frame, []):
            before = dp
            dp = min(max_dp, dp + float(event["amount"]))
            rows.append({"frame": frame, "event": "AUTO_SKILL_DP_INCOME", "operator_id": event["operator_id"],
                         "cycle": event["cycle"], "delta": dp - before, "balance_before": before,
                         "balance_after": dp, "status": "CONDITIONAL_ON_SURVIVAL_AND_CONTINUOUS_DEPLOYMENT",
                         "source": "initial-SP auto trigger immediately after deploy; public adapter timing model"})
    return {
        "schema_version": "R8_1_LOWSTAR_C2_STATIC_DP_LEDGER_V2",
        "initial_dp": float(evidence_stage_initial_dp(input_dir)),
        "natural_dp_per_second": 1.0,
        "max_dp": max_dp,
        "deployment_limit": deployment_limit,
        "automatic_skill_income_model": {
            "trigger_rule": "Initial trigger after (sp_cost - min(initial_sp + deployment_sp_bonus, sp_cost)) seconds; recurrence after sp_cost seconds for duration=0 AUTO TIME skills.",
            "conditions": ["operator survives", "operator remains deployed", "normal time-SP recovery",
                           "same retreat-frame trigger is not counted"],
            "evidence_status": "CONFIRMED_FROM_CURRENT_PUBLIC_RUNTIME_PATTERN_AND_FIXED_GAME_DATA",
            "events": auto_events,
        },
        "retreat_refund": {"value": "HALF_DEPLOYMENT_COST_FLOOR",
                           "condition": "manual retreat of a surviving deployed operator",
                           "status": "CONFIRMED_FROM_CODE_RUNTIME_MATCH"},
        "merchant_upkeep": "NOT_APPLICABLE_UNLESS_MERCHANT_DEPLOYED",
        "skill_readiness": readiness,
        "entries": rows,
        "final_balance": dp,
        "final_balance_status": (
            "UNKNOWN_UNTIL_CONDITIONAL_REDEPLOY_DP_RESOLVED"
            if conditional_dp_reservations else "KNOWN_WITH_STATIC_MODEL_ASSUMPTIONS"
        ),
        "conditional_dp_reservations": conditional_dp_reservations,
        "conflicts": conflicts,
    }


if __name__ == "__main__":
    compile_plan(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
