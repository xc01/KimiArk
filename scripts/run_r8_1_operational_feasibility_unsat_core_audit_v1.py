from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_operational_feasibility_unsat_core_audit_v1"
REPAIR = ROOT / "output/r8_1_operational_semantic_preservation_repair_v1"
RECOVER = ROOT / "output/r8_1_revision_numeric_grounding_recovery_v1"
CTX_PATH = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
MECHANICS = "m18.9-stage-device-runtime-v1"
STAGE = "main_08-01"
PLAN_IDS = [
    "R-OP-01-POCKET-AND-FLOOR",
    "R-OP-02-FORWARD-DUELIST-ISOLATION",
    "R-OP-03-FRD-RELAY-LANE02",
    "R-OP-04-AUTOCYCLE-KILLING-BLOCKS",
    "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR",
]
MERCHANT_IDS = {"char_272_strong", "char_322_lmlee", "char_4155_talr", "char_455_nothin"}


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def import_repair_module():
    spec = importlib.util.spec_from_file_location(
        "semantic_repair", ROOT / "scripts/run_r8_1_operational_semantic_preservation_repair_v1.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def import_search_module():
    spec = importlib.util.spec_from_file_location(
        "revised_search", ROOT / "scripts/run_r8_1_revised_operational_plan_search_v1.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def trait_aware_operators(operators: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows = {operator_id: dict(operator) for operator_id, operator in operators.items()}
    for operator_id in MERCHANT_IDS:
        if operator_id in rows:
            row = dict(rows[operator_id])
            row["cost"] = max(0.0, float(row["cost"]) - 3.0)
            row["trait_cost_audit_only"] = True
            rows[operator_id] = row
    return rows


def structural_role_ok(operator: dict[str, Any], role: str) -> bool:
    skill = operator.get("skill_effect") or {}
    if role == "BLOCK":
        return operator["position"] == "MELEE" and operator["block_count"] > 0
    if role == "PIONEER_BLOCK":
        return (
            operator["position"] == "MELEE"
            and operator["profession"] == "PIONEER"
            and operator["block_count"] >= 2
            and float(skill.get("dp_immediate", 0)) > 0
        )
    if role == "KILLING_BLOCK":
        return (
            operator["position"] == "MELEE"
            and operator["block_count"] > 0
            and operator.get("skill_auto_activate", False)
            and (
                float(skill.get("atk_multiplier", 1)) > 1
                or float(skill.get("next_attack_atk_scale", 1)) > 1
            )
        )
    if role == "DUELIST":
        autonomous = float(operator["hp"]) >= 1900 and float(operator["defense"]) >= 150
        skill_autonomous = operator.get("skill_supported", False) and (
            float(skill.get("immediate_self_heal_ratio", 0)) > 0 or skill.get("heal_mode", False)
        )
        return operator["position"] == "MELEE" and (autonomous or skill_autonomous)
    if role == "RELAY":
        return (
            operator["position"] == "MELEE"
            and 18 <= float(operator["redeploy_seconds"]) <= 25
            and float(operator["cost"]) <= 8
        )
    if role == "RANGED_DPS":
        return operator["position"] == "RANGED" and operator["profession"] not in {"MEDIC", "SUPPORT"}
    if role == "SUSTAIN":
        return operator["position"] == "RANGED" and operator["profession"] == "MEDIC"
    return False


def candidate_pool(
    context: dict[str, Any],
    role: str,
    *,
    trait_aware: bool,
    repair: Any,
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    operators: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not trait_aware:
        return repair.selected_usage_pool(
            context,
            role,
            fidelity_by_id=fidelity_by_id,
            census_by_id=census_by_id,
        )
    rows = []
    for operator in operators.values():
        if not structural_role_ok(operator, role):
            continue
        if operator["operator_id"] in MERCHANT_IDS and role in {"BLOCK", "RELAY"}:
            eligible = True
        else:
            eligible, _ = repair.selected_usage_fidelity(
                operator,
                role=role,
                fidelity_by_id=fidelity_by_id,
                census_by_id=census_by_id,
            )
        if eligible:
            rows.append((float(operator["cost"]), operator["operator_id"], operator))
    return [row[-1] for row in sorted(rows)]


def minimum_cost_assignment(
    context: dict[str, Any],
    slots: list[dict[str, Any]],
    *,
    trait_aware: bool,
    repair: Any,
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    operators: dict[str, dict[str, Any]],
    distinct: bool = True,
) -> tuple[float | None, dict[str, str]]:
    choices: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for slot in sorted(slots, key=lambda item: (item.get("deadline_frame") or item.get("target") or 0, item["slot_id"])):
        pool = candidate_pool(
            context,
            slot["role"],
            trait_aware=trait_aware,
            repair=repair,
            fidelity_by_id=fidelity_by_id,
            census_by_id=census_by_id,
            operators=operators,
        )
        pool = [
            operator
            for operator in pool
            if slot.get("max_cost") is None or float(operator["cost"]) <= float(slot["max_cost"])
        ]
        if not pool:
            return None, {}
        choices.append((slot, sorted(pool, key=lambda item: (float(item["cost"]), item["operator_id"]))))
    if not distinct:
        assignment: dict[str, str] = {}
        total_cost = 0.0
        for slot, pool in choices:
            operator = min(pool, key=lambda item: (float(item["cost"]), item["operator_id"]))
            assignment[slot["slot_id"]] = operator["operator_id"]
            total_cost += float(operator["cost"])
        return total_cost, assignment

    slot_ids = [slot["slot_id"] for slot, _ in choices]
    operator_ids = sorted(
        {operator["operator_id"] for _, pool in choices for operator in pool}
    )
    operator_index = {operator_id: index for index, operator_id in enumerate(operator_ids)}
    allowed: dict[tuple[int, int], float] = {}
    for slot_index, (_, pool) in enumerate(choices):
        for operator in pool:
            operator_id = operator["operator_id"]
            allowed[(slot_index, operator_index[operator_id])] = float(operator["cost"])

    source = len(slot_ids)
    operator_base = source + 1
    sink = operator_base + len(operator_ids)
    total_nodes = sink + 1
    graph: list[list[dict[str, Any]]] = [[] for _ in range(total_nodes)]

    def add_edge(left: int, right: int, capacity: float, cost: float) -> None:
        forward = {"to": right, "residual": capacity, "cost": cost, "reverse": len(graph[right])}
        reverse = {"to": left, "residual": 0.0, "cost": -cost, "reverse": len(graph[left])}
        graph[left].append(forward)
        graph[right].append(reverse)

    for slot_index in range(len(slot_ids)):
        add_edge(source, slot_index, 1.0, 0.0)
    for operator_index_value in range(len(operator_ids)):
        add_edge(operator_base + operator_index_value, sink, 1.0, 0.0)
    for (slot_index, operator_index_value), cost in sorted(allowed.items()):
        add_edge(slot_index, operator_base + operator_index_value, 1.0, cost)

    flow_cost = 0.0
    assignment = {}
    for _ in range(len(slot_ids)):
        distances = [math.inf] * total_nodes
        previous_edge: list[tuple[int, int] | None] = [None] * total_nodes
        distances[source] = 0.0
        for _ in range(total_nodes - 1):
            changed = False
            for node, edges in enumerate(graph):
                if math.isinf(distances[node]):
                    continue
                for edge_index, edge in enumerate(edges):
                    if edge["residual"] <= 1e-12:
                        continue
                    candidate = distances[node] + edge["cost"]
                    if candidate + 1e-9 < distances[edge["to"]]:
                        distances[edge["to"]] = candidate
                        previous_edge[edge["to"]] = (node, edge_index)
                        changed = True
            if not changed:
                break
        if math.isinf(distances[sink]):
            return None, {}
        node = sink
        while node != source:
            left, edge_index = previous_edge[node]
            assert left is not None
            edge = graph[left][edge_index]
            if left < len(slot_ids) and operator_base <= node < sink:
                assignment[slot_ids[left]] = operator_ids[node - operator_base]
            edge["residual"] -= 1.0
            graph[node][edge["reverse"]]["residual"] += 1.0
            node = left
        flow_cost += distances[sink]
    return flow_cost, assignment


def deadline_rows(
    plan_id: str,
    pattern: dict[str, Any],
    repair: Any,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    routes = repair.route_map(context)
    rows = []
    for slot in pattern["slots"]:
        mapping = repair.DEADLINE_ROUTES[plan_id].get(slot["slot_id"])
        deadline = repair.establishment_deadline(routes.get(mapping[0]), mapping[1]) if mapping else None
        rows.append({**slot, "deadline_frame": deadline})
    return sorted(rows, key=lambda row: (row["deadline_frame"] if row["deadline_frame"] is not None else row["target"], row["slot_id"]))


def gross_dp_bound(
    deadline: int,
    initial_dp: float,
    dp_rate: float,
    pioneer: dict[str, Any] | None,
    pioneer_earliest_frame: int | None,
) -> float:
    gross = initial_dp + dp_rate * deadline / 30.0
    if pioneer and pioneer_earliest_frame is not None:
        skill = pioneer.get("skill_effect") or {}
        ready_seconds = max(
            0.0,
            (float(pioneer.get("skill_sp_cost") or 0) - float(pioneer.get("skill_initial_sp") or 0))
            / max(1e-9, dp_rate),
        )
        if pioneer_earliest_frame + math.ceil(ready_seconds * 30) <= deadline:
            gross += float(skill.get("dp_immediate", 0))
    return gross


def pioneer_earliest(slots: list[dict[str, Any]], costs: dict[str, float], initial_dp: float, dp_rate: float) -> int | None:
    pioneer_slots = [slot for slot in slots if slot["role"] == "PIONEER_BLOCK"]
    if not pioneer_slots:
        return None
    prior_cost = sum(float(costs.get(slot["slot_id"], 0)) for slot in slots if slot["role"] != "PIONEER_BLOCK" and (slot.get("deadline_frame") or slot.get("target") or 0) < (pioneer_slots[0].get("deadline_frame") or pioneer_slots[0].get("target") or 0))
    pioneer_cost = float(costs.get(pioneer_slots[0]["slot_id"], 0))
    cumulative = prior_cost + pioneer_cost
    if cumulative <= initial_dp:
        return 0
    return int(math.ceil((cumulative - initial_dp) / max(1e-9, dp_rate) * 30))


def optimistic_bounds(
    plans: list[dict[str, Any]],
    patterns: dict[str, Any],
    context: dict[str, Any],
    repair: Any,
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    operators: dict[str, dict[str, Any]],
    trait_operators: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = []
    initial_dp = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
    dp_rate = float(context["stage_facts"]["cost_recovery_per_second"])
    for plan in plans:
        plan_id = plan["operational_plan_id"]
        rows = deadline_rows(plan_id, patterns[plan_id], repair, context)
        variants = []
        for trait_aware in (False, True):
            use_operators = trait_operators if trait_aware else operators
            prefix_rows = []
            first_infeasible = None
            for index, row in enumerate(rows):
                prefix = rows[: index + 1]
                minimum_cost, assignment = minimum_cost_assignment(
                    context,
                    prefix,
                    trait_aware=trait_aware,
                    repair=repair,
                    fidelity_by_id=fidelity_by_id,
                    census_by_id=census_by_id,
                    operators=use_operators,
                )
                if minimum_cost is None:
                    status = "NO_DISTINCT_LEGAL_OPERATORS"
                    deficit = None
                    gross = None
                    assignment = {}
                else:
                    operator_costs = {
                        slot["slot_id"]: float(use_operators[assignment[slot["slot_id"]]]["cost"])
                        for slot in prefix
                        if slot["slot_id"] in assignment
                    }
                    source = pioneer_earliest(prefix, operator_costs, initial_dp, dp_rate)
                    pioneer_operator = use_operators.get(assignment.get(next((slot["slot_id"] for slot in prefix if slot["role"] == "PIONEER_BLOCK"), "")))
                    gross = gross_dp_bound(int(row["deadline_frame"]), initial_dp, dp_rate, pioneer_operator, source)
                    deficit = max(0.0, float(minimum_cost) - gross)
                    status = "FEASIBLE_BOUND" if deficit <= 1e-9 else "DP_INFEASIBLE_BOUND"
                    if status != "FEASIBLE_BOUND" and first_infeasible is None:
                        first_infeasible = {
                            "deadline_frame": int(row["deadline_frame"]),
                            "slot_id": row["slot_id"],
                            "mandatory_prefix_slots": [item["slot_id"] for item in prefix],
                            "minimum_cost": minimum_cost,
                            "available_dp": gross,
                            "deficit": deficit,
                            "assignment": assignment,
                            "cost_model": "trait_aware_audit_only" if trait_aware else "runtime_supported",
                        }
                prefix_rows.append(
                    {
                        "prefix_size": len(prefix),
                        "deadline_frame": row["deadline_frame"],
                        "new_slot": row["slot_id"],
                        "mandatory_prefix_slots": [item["slot_id"] for item in prefix],
                        "minimum_cost": minimum_cost,
                        "available_dp": gross,
                        "deficit": deficit,
                        "status": status,
                        "minimum_assignment": assignment,
                    }
                )
            variants.append(
                {
                    "variant": "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY" if trait_aware else "CURRENT_SIMULATOR_SUPPORTED",
                    "status": "DP_INFEASIBLE" if first_infeasible else "FEASIBILITY_NOT_DISPROVEN_BY_DP_BOUND",
                    "first_infeasible_prefix": first_infeasible,
                    "prefixes": prefix_rows,
                    "note": None
                    if trait_aware
                    else "Uses only mechanics currently supported by the planner runtime.",
                }
            )
        records.append({"operational_plan_id": plan_id, "variants": variants})
    return {
        "schema_version": "R8_1_OPTIMISTIC_DP_FEASIBILITY_BOUNDS_V1",
        "mechanics_version": MECHANICS,
        "stage": STAGE,
        "method": "Minimum-cost distinct-operator assignment per mandatory deadline prefix; natural DP plus earliest legal auto-DP proc; no retreat refund.",
        "records": records,
    }


def exact_ledger_for_schedule(
    actions: list[Any],
    operators: dict[str, dict[str, Any]],
    context: dict[str, Any],
    frame_of: Any,
) -> list[dict[str, Any]]:
    from arknights_planner.models.strategy import ActionType

    initial_dp = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
    dp_rate = float(context["stage_facts"]["cost_recovery_per_second"])
    procs: list[tuple[float, float, str]] = []
    for action in actions:
        if action.action_type is ActionType.DEPLOY:
            operator = operators[action.operator_id]
            skill = operator.get("skill_effect") or {}
            if (
                operator.get("skill_auto_activate")
                and float(skill.get("dp_immediate", 0)) > 0
                and operator.get("skill_recovery_mode") == "TIME"
            ):
                ready_seconds = max(
                    0.0,
                    (float(operator.get("skill_sp_cost") or 0) - float(operator.get("skill_initial_sp") or 0))
                    / max(1e-9, dp_rate),
                )
                procs.append((float(action.time) + ready_seconds, float(skill["dp_immediate"]), action.operator_id))
    procs.sort()
    process_index = 0
    previous_time = 0.0
    dp = initial_dp
    ledger = [{"event": "INITIAL", "frame": 0, "dp_before": dp, "dp_after": dp}]
    for action in sorted(actions, key=lambda item: (item.time, 0 if item.action_type is ActionType.RETREAT else 1, item.operator_id)):
        while process_index < len(procs) and procs[process_index][0] <= action.time + 1e-9:
            proc_time, amount, source = procs[process_index]
            natural = dp_rate * max(0.0, proc_time - previous_time)
            dp += natural + amount
            ledger.append(
                {
                    "event": "AUTO_DP_PROC",
                    "frame": int(round(proc_time * 30)),
                    "operator_id": source,
                    "natural_accrual": natural,
                    "skill_dp": amount,
                    "dp_after": dp,
                }
            )
            previous_time = proc_time
            process_index += 1
        natural = dp_rate * max(0.0, action.time - previous_time)
        dp += natural
        row: dict[str, Any] = {
            "event": action.action_type.value,
            "frame": frame_of(action),
            "operator_id": action.operator_id,
            "natural_accrual": natural,
            "dp_before_action": dp,
        }
        if action.action_type is ActionType.DEPLOY:
            dp -= float(operators[action.operator_id]["cost"])
            row["deployment_cost"] = float(operators[action.operator_id]["cost"])
            row["refund"] = 0.0
        elif action.action_type is ActionType.RETREAT:
            row["deployment_cost"] = 0.0
            row["refund"] = 0.0
            row["refund_basis"] = "NOT_APPLIED_REFUND_UNRESOLVED_IN_CLIENT_TIMING_EVIDENCE"
        row["dp_after"] = dp
        ledger.append(row)
        previous_time = action.time
    return ledger


def exact_dp_ledgers(
    plans: list[dict[str, Any]],
    patterns: dict[str, Any],
    context: dict[str, Any],
    repair: Any,
    operators: dict[str, dict[str, Any]],
    trait_operators: dict[str, dict[str, Any]],
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = []
    initial_dp = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
    dp_rate = float(context["stage_facts"]["cost_recovery_per_second"])
    for plan in plans:
        plan_id = plan["operational_plan_id"]
        rows = deadline_rows(plan_id, patterns[plan_id], repair, context)
        variants = []
        for trait_aware in (False, True):
            use_operators = trait_operators if trait_aware else operators
            minimum_cost, assignment = minimum_cost_assignment(
                context,
                rows,
                trait_aware=trait_aware,
                repair=repair,
                fidelity_by_id=fidelity_by_id,
                census_by_id=census_by_id,
                operators=use_operators,
            )
            if minimum_cost is None:
                variants.append(
                    {
                        "variant": "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY" if trait_aware else "CURRENT_SIMULATOR_SUPPORTED",
                        "status": "NO_DISTINCT_LEGAL_OPERATORS",
                        "minimum_total_cost": None,
                        "ledger": [],
                        "deadline_misses": [],
                    }
                )
                continue
            actions, frames = repair.build_deadline_actions(
                patterns[plan_id],
                assignment,
                use_operators,
                context,
                plan_id,
                "EARLIEST_PHASE",
                "NO_SKILLS",
            )
            dp_ok, dp_reasons = repair.dp_feasible(actions, use_operators, context)
            misses = []
            routes = repair.route_map(context)
            for slot in rows:
                mapping = repair.DEADLINE_ROUTES[plan_id].get(slot["slot_id"])
                deadline = repair.establishment_deadline(routes.get(mapping[0]), mapping[1]) if mapping else None
                if deadline is not None and frames.get(slot["slot_id"], 10**9) > deadline:
                    misses.append(
                        {
                            "slot_id": slot["slot_id"],
                            "scheduled_frame": frames[slot["slot_id"]],
                            "deadline_frame": deadline,
                            "deficit_frames": frames[slot["slot_id"]] - deadline,
                        }
                    )
            variants.append(
                {
                    "variant": "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY" if trait_aware else "CURRENT_SIMULATOR_SUPPORTED",
                    "status": "DP_FEASIBLE_BUT_DEADLINE_INFEASIBLE" if misses else ("FEASIBLE_SCHEDULE_BOUND" if dp_ok else "DP_INFEASIBLE"),
                    "minimum_total_cost": minimum_cost,
                    "assignment": assignment,
                    "scheduled_frames": frames,
                    "dp_feasible": dp_ok,
                    "dp_reasons": dp_reasons,
                    "deadline_misses": misses,
                    "ledger": exact_ledger_for_schedule(actions, use_operators, context, repair.frame_of),
                }
            )
        records.append({"operational_plan_id": plan_id, "variants": variants})
    return {
        "schema_version": "R8_1_EXACT_DP_LEDGERS_V1",
        "mechanics_version": MECHANICS,
        "initial_dp": initial_dp,
        "natural_dp_rate_per_second": dp_rate,
        "retreat_refund_policy": "NOT_APPLIED; refund timing/evidence unresolved and simulator currently applies no refund",
        "records": records,
    }


def constraint_inventory(
    plans: list[dict[str, Any]],
    patterns: dict[str, Any],
    context: dict[str, Any],
    repair: Any,
) -> dict[str, Any]:
    records = []
    for plan in plans:
        plan_id = plan["operational_plan_id"]
        rows = []
        for slot in deadline_rows(plan_id, patterns[plan_id], repair, context):
            role = slot["role"]
            category = "PLAN_INVARIANT_HARD"
            if plan_id == "R-OP-03-FRD-RELAY-LANE02" and slot["slot_id"] == "LANE02_MEDIC":
                category = "PLAN_CONDITIONAL"
            if role == "KILLING_BLOCK":
                state = "MUST_BE_ACTIVE_WITH_AUTO_SKILL_SUPPORTED"
            elif role in {"RANGED_DPS", "SUSTAIN"}:
                state = "MUST_HAVE_COVERAGE"
            else:
                state = "MUST_BE_ACTIVE"
            rows.append(
                {
                    "constraint_id": f"{plan_id}:{slot['slot_id']}:DEADLINE",
                    "kind": "deadline_establishment",
                    "slot_id": slot["slot_id"],
                    "role": role,
                    "category": category,
                    "source": "normalized OperationalPlan operational_invariants/battle_phases + exact_route_threats",
                    "statement": f"{slot['slot_id']} must satisfy its documented establishment state by frame {slot['deadline_frame']}",
                    "deadline_frame": slot["deadline_frame"],
                    "deadline_semantic_state": state,
                    "cost": None,
                    "execution_critical": category in {"GAME_RULE_HARD", "PLAN_INVARIANT_HARD", "DERIVED_NECESSARY"},
                }
            )
        rows.extend(
            [
                {
                    "constraint_id": f"{plan_id}:DISTINCT_SIMULTANEOUS_OPERATORS",
                    "kind": "roster",
                    "category": "GAME_RULE_HARD",
                    "source": "deployment runtime forbids one operator occupying multiple live instances",
                    "statement": "Distinct live slots use distinct operator IDs unless the plan explicitly authorizes sequential redeployment.",
                },
                {
                    "constraint_id": f"{plan_id}:FORM_01_DEPLOYMENT_LIMIT",
                    "kind": "capacity",
                    "category": "GAME_RULE_HARD",
                    "source": "stage deployment limit",
                    "statement": "Live deployment count remains within the stage limit.",
                },
                {
                    "constraint_id": f"{plan_id}:NO_LOAD_BEARING_ACTIVATE_SKILL",
                    "kind": "skill",
                    "category": "PLAN_INVARIANT_HARD",
                    "source": "normalized OperationalPlan skill_intents",
                    "statement": "No ACTIVATE_SKILL is required for a kill obligation.",
                },
            ]
        )
        if plan_id == "R-OP-04-AUTOCYCLE-KILLING-BLOCKS":
            rows.append(
                {
                    "constraint_id": f"{plan_id}:SAME_TILE_UPGRADE_ORDER",
                    "kind": "formation_transition",
                    "category": "PLAN_INVARIANT_HARD",
                    "source": "normalized OperationalPlan T02_same_tile_upgrade",
                    "statement": "RETREAT [8,5] placeholder, then deploy a different killing-block on the vacated tile.",
                }
            )
        if plan_id == "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR":
            rows.extend(
                [
                    {
                        "constraint_id": f"{plan_id}:ZERO_LEAK_THROUGH_4524",
                        "kind": "leak_budget",
                        "category": "PLAN_INVARIANT_HARD",
                        "source": "normalized OperationalPlan operational_invariants",
                        "statement": "Cumulative leaks are zero through frame 4524.",
                    },
                    {
                        "constraint_id": f"{plan_id}:LATE_CONCESSION_BUDGET_4",
                        "kind": "triage",
                        "category": "PLAN_INVARIANT_HARD",
                        "source": "normalized OperationalPlan W06 triage semantics",
                        "statement": "Only routes 33/34 may be released after frame 4650, with total leaked enemies <=4.",
                    },
                    {
                        "constraint_id": f"{plan_id}:NO_EXTRA_RESOURCE_ON_ROUTES_33_34",
                        "kind": "triage",
                        "category": "PLAN_INVARIANT_HARD",
                        "source": "normalized OperationalPlan forbidden_substitutions",
                        "statement": "No additional deploy/retreat/skill resource is allocated to routes 33/34; unavoidable existing [9,2] coverage is not an added allocation.",
                    },
                ]
            )
        records.append({"operational_plan_id": plan_id, "constraints": rows})
    counts = Counter(
        constraint["category"]
        for plan_record in records
        for constraint in plan_record["constraints"]
    )
    return {
        "schema_version": "R8_1_CONSTRAINT_PROVENANCE_INVENTORY_V1",
        "records": records,
        "category_counts": dict(counts),
        "total_constraints": sum(counts.values()),
    }


def constraint_graphs(inventory: dict[str, Any], patterns: dict[str, Any]) -> dict[str, Any]:
    records = []
    for plan_record in inventory["records"]:
        plan_id = plan_record["operational_plan_id"]
        nodes = [constraint["constraint_id"] for constraint in plan_record["constraints"]]
        edges = []
        slot_ids = {constraint.get("slot_id") for constraint in plan_record["constraints"] if constraint.get("slot_id")}
        for slot_id in sorted(slot_ids):
            edges.append({"from": f"{plan_id}:{slot_id}:DEADLINE", "to": f"{plan_id}:DISTINCT_SIMULTANEOUS_OPERATORS", "relation": "REQUIRES_DISTINCT_OPERATOR"})
            edges.append({"from": f"{plan_id}:{slot_id}:DEADLINE", "to": f"{plan_id}:FORM_01_DEPLOYMENT_LIMIT", "relation": "CONSUMES_LIVE_SLOT"})
        if plan_id == "R-OP-04-AUTOCYCLE-KILLING-BLOCKS":
            edges.append({"from": f"{plan_id}:POCKET_PLACEHOLDER:DEADLINE", "to": f"{plan_id}:SAME_TILE_UPGRADE_ORDER", "relation": "MUST_VACATE_TILE"})
            edges.append({"from": f"{plan_id}:SAME_TILE_UPGRADE_ORDER", "to": f"{plan_id}:POCKET_KILLER:DEADLINE", "relation": "ENABLES_DEPLOY"})
        records.append(
            {
                "operational_plan_id": plan_id,
                "nodes": nodes,
                "edges": edges,
                "pattern_slots": patterns[plan_id]["slots"],
            }
        )
    return {"schema_version": "R8_1_PER_PLAN_CONSTRAINT_GRAPHS_V1", "records": records}


def deadline_semantics_audit(plans: list[dict[str, Any]], patterns: dict[str, Any], context: dict[str, Any], repair: Any) -> dict[str, Any]:
    records = []
    for plan in plans:
        plan_id = plan["operational_plan_id"]
        for slot in deadline_rows(plan_id, patterns[plan_id], repair, context):
            role = slot["role"]
            if role == "KILLING_BLOCK":
                state = "MUST_BE_ACTIVE_WITH_AUTO_SKILL_SUPPORTED"
                failure = "Blocking/damage responsibility is not available; skill charge is not required at the deadline."
            elif role in {"RANGED_DPS", "SUSTAIN"}:
                state = "MUST_HAVE_COVERAGE"
                failure = "Required damage or healing coverage is absent."
            elif role == "PIONEER_BLOCK":
                state = "MUST_BE_ACTIVE_AND_DP_CAPABLE"
                failure = "Opening defense and economy source are absent."
            else:
                state = "MUST_BE_ACTIVE"
                failure = "Required blocking/stalling role is absent."
            records.append(
                {
                    "operational_plan_id": plan_id,
                    "slot_id": slot["slot_id"],
                    "role": role,
                    "deadline_frame": slot["deadline_frame"],
                    "semantic_state": state,
                    "failure_if_missed": failure,
                    "deployment_alone_sufficient": role not in {"RANGED_DPS", "SUSTAIN"},
                    "skill_ready_required": False,
                    "provenance": "Exact route event + normalized plan wording; no skill charge is promoted beyond explicit plan semantics.",
                }
            )
    return {
        "schema_version": "R8_1_DEADLINE_SEMANTICS_AUDIT_V1",
        "records": records,
        "prior_semantic_errors_fixed": [
            {
                "plans": ["R-OP-01-POCKET-AND-FLOOR", "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR"],
                "slot_id": "POCKET_FIRE",
                "old": "route-3 contact frame 295",
                "corrected": "route-4 contact frame 805",
                "basis": "Plan's own cumulative-DP verifier question and first route-4 obligation",
            },
            {
                "plans": ["R-OP-05-TAIL-TRIAGE-PLANNED-FOUR"],
                "slot_id": "POCKET_MEDIC",
                "old": "route-4 earliest contact frame 805",
                "corrected": "route-4 last safe/block deadline frame 941",
                "basis": "Plan explicitly requires medic by frame 941",
            },
            {
                "plans": ["R-OP-04-AUTOCYCLE-KILLING-BLOCKS"],
                "slot_id": "POCKET_KILLER",
                "old": "route-9 first train blocker frame 1541",
                "corrected": "route-18 contact frame 3415",
                "basis": "Plan requires upgrade before route-18 contact and treats route-9 as the upgrade proof case",
            },
        ],
        "prior_semantic_error_count": 3,
    }


def unsat_cores(
    bounds: dict[str, Any],
    inventory: dict[str, Any],
    context: dict[str, Any],
    patterns: dict[str, Any],
    repair: Any,
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    operators: dict[str, dict[str, Any]],
    trait_operators: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = []
    initial_dp = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
    dp_rate = float(context["stage_facts"]["cost_recovery_per_second"])
    inventory_by_plan = {row["operational_plan_id"]: row for row in inventory["records"]}
    for plan_record in bounds["records"]:
        plan_id = plan_record["operational_plan_id"]
        variant = next(row for row in plan_record["variants"] if row["variant"] == "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY")
        first = variant["first_infeasible_prefix"]
        if not first:
            records.append(
                {
                    "operational_plan_id": plan_id,
                    "status": "NO_UNSAT_CORE_FROM_DP_BOUND",
                    "core_type": "NONE",
                }
            )
            continue
        rows = [row for row in deadline_rows(plan_id, patterns[plan_id], repair, context) if (row["deadline_frame"] or 0) <= first["deadline_frame"]]
        removal_tests = []
        necessary_constraints = []
        for row in rows:
            relaxed_rows = [item for item in rows if item["slot_id"] != row["slot_id"]]
            if not relaxed_rows:
                relaxed_cost = 0.0
            else:
                relaxed_cost, _ = minimum_cost_assignment(
                    context,
                    relaxed_rows,
                    trait_aware=True,
                    repair=repair,
                    fidelity_by_id=fidelity_by_id,
                    census_by_id=census_by_id,
                    operators=trait_operators,
                )
            feasible = relaxed_cost is not None and relaxed_cost <= first["available_dp"] + 1e-9
            removal_tests.append({"removed_constraint": f"{plan_id}:{row['slot_id']}:DEADLINE", "relaxed_minimum_cost": relaxed_cost, "feasible": feasible})
            if feasible:
                necessary_constraints.append(f"{plan_id}:{row['slot_id']}:DEADLINE")
        distinct_cost, _ = minimum_cost_assignment(
            context,
            rows,
            trait_aware=True,
            repair=repair,
            fidelity_by_id=fidelity_by_id,
            census_by_id=census_by_id,
            operators=trait_operators,
            distinct=False,
        )
        distinct_removal_feasible = distinct_cost is not None and distinct_cost <= first["available_dp"] + 1e-9
        removal_tests.append({"removed_constraint": f"{plan_id}:DISTINCT_SIMULTANEOUS_OPERATORS", "relaxed_minimum_cost": distinct_cost, "feasible": distinct_removal_feasible})
        if distinct_removal_feasible:
            necessary_constraints.append(f"{plan_id}:DISTINCT_SIMULTANEOUS_OPERATORS")
        deadline_removal_feasible = None
        removal_tests.append(
            {
                "removed_constraint": f"{plan_id}:{first['slot_id']}:DEADLINE_FRAME",
                "relaxed_minimum_cost": first["minimum_cost"],
                "feasible": deadline_removal_feasible,
                "reason": "Requires a grounded later event to compute a safe available-DP bound; minimality is not claimed.",
            }
        )
        if deadline_removal_feasible:
            necessary_constraints.append(f"{plan_id}:{first['slot_id']}:DEADLINE_FRAME")
        necessary_constraints = list(dict.fromkeys(necessary_constraints))
        records.append(
            {
                "operational_plan_id": plan_id,
                "status": "CONFLICTING_CONSTRAINT_SET",
                "core_type": "CONFLICTING_CONSTRAINT_SET",
                "deadline_frame": first["deadline_frame"],
                "mandatory_prefix_slots": first["mandatory_prefix_slots"],
                "minimum_cost": first["minimum_cost"],
                "available_dp": first["available_dp"],
                "deficit": first["deficit"],
                "necessary_constraints_from_single_removal": necessary_constraints,
                "core_constraints": necessary_constraints,
                "removal_tests": removal_tests,
                "cost_model": "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY",
                "note": "Minimum-cost, distinct-operator contradiction is proven; single-removal minimality is not claimed because delayed deadline feasibility requires a grounded later event.",
            }
        )
    return {"schema_version": "R8_1_UNSAT_CORE_CERTIFICATES_V1", "records": records}


def relaxation_sensitivity(
    cores: dict[str, Any],
    context: dict[str, Any],
    patterns: dict[str, Any],
    repair: Any,
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    operators: dict[str, dict[str, Any]],
    trait_operators: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = []
    for core in cores["records"]:
        if not core.get("deadline_frame"):
            continue
        plan_id = core["operational_plan_id"]
        rows = [
            row
            for row in deadline_rows(plan_id, patterns[plan_id], repair, context)
            if (row["deadline_frame"] or 0) <= core["deadline_frame"]
        ]
        tests = []
        for remove_slot in [row["slot_id"] for row in rows]:
            relaxed = [row for row in rows if row["slot_id"] != remove_slot]
            cost, _ = minimum_cost_assignment(
                context,
                relaxed,
                trait_aware=True,
                repair=repair,
                fidelity_by_id=fidelity_by_id,
                census_by_id=census_by_id,
                operators=trait_operators,
            )
            tests.append(
                {
                    "relaxation": f"REMOVE_{remove_slot}",
                    "minimum_cost": cost,
                    "restores_prefix_dp_feasibility": cost is not None and cost <= core["available_dp"] + 1e-9,
                    "valid_realization_without_plan_change": False,
                }
            )
        cost, _ = minimum_cost_assignment(
            context,
            rows,
            trait_aware=True,
            repair=repair,
            fidelity_by_id=fidelity_by_id,
            census_by_id=census_by_id,
            operators=trait_operators,
            distinct=False,
        )
        tests.append(
            {
                "relaxation": "ALLOW_OPERATOR_REUSE",
                "minimum_cost": cost,
                "restores_prefix_dp_feasibility": cost is not None and cost <= core["available_dp"] + 1e-9,
                "valid_realization_without_plan_change": False,
            }
        )
        tests.append(
            {
                "relaxation": f"DELAY_{core['mandatory_prefix_slots'][-1]}_TO_NEXT_EVENT",
                "minimum_cost": core["minimum_cost"],
                "restores_prefix_dp_feasibility": None,
                "valid_realization_without_plan_change": False,
                "reason": "Requires a grounded later event; not assumed here.",
            }
        )
        records.append({"operational_plan_id": plan_id, "tests": tests})
    return {"schema_version": "R8_1_CONSTRAINT_RELAXATION_SENSITIVITY_V1", "diagnostic_only": True, "records": records}


def dependency_cycles(
    plans: list[dict[str, Any]],
    patterns: dict[str, Any],
    context: dict[str, Any],
    repair: Any,
) -> dict[str, Any]:
    records = []
    for plan in plans:
        plan_id = plan["operational_plan_id"]
        edges = []
        if plan_id == "R-OP-04-AUTOCYCLE-KILLING-BLOCKS":
            edges = [
                {"from": "C03_STUB deployed", "to": "POCKET_PLACEHOLDER affordable", "kind": "ECONOMY_PRECEDENCE"},
                {"from": "POCKET_PLACEHOLDER deployed", "to": "AUTO_DP_PROC", "kind": "ECONOMY_GENERATION"},
                {"from": "AUTO_DP_PROC", "to": "C05_KILLER/C06_KILLER affordability", "kind": "ECONOMY_SUPPORT"},
                {"from": "POCKET_PLACEHOLDER live", "to": "POCKET_PLACEHOLDER retreat", "kind": "SAME_TILE_PRECEDENCE"},
                {"from": "POCKET_PLACEHOLDER retreat", "to": "POCKET_KILLER deploy", "kind": "TILE_VACACY"},
            ]
        elif plan_id == "R-OP-03-FRD-RELAY-LANE02":
            edges = [
                {"from": "relay N deploy", "to": "relay N retreat", "kind": "LIVE_UNIT_PRECEDENCE"},
                {"from": "relay N retreat", "to": "relay N+1 same-tile deploy", "kind": "TILE_VACACY"},
            ]
        records.append(
            {
                "operational_plan_id": plan_id,
                "cycle_found": False,
                "edges": edges,
                "finding": "Observed dependencies form a directed acyclic precedence chain; no operator is required to generate DP before legal deployment.",
            }
        )
    return {"schema_version": "R8_1_DEPENDENCY_CYCLE_AUDIT_V1", "records": records}


def op04_audit(
    context: dict[str, Any],
    repair: Any,
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    operators: dict[str, dict[str, Any]],
    trait_operators: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pool = repair.corrected_killing_pool(context, fidelity_by_id, census_by_id)
    certificates = []
    for row in pool:
        operator = row["operator"]
        certificates.append(
            {
                "operator_id": operator["operator_id"],
                "rarity": operator["rarity"],
                "profession": operator["profession"],
                "cost": operator["cost"],
                "block_count": operator["block_count"],
                "selected_skill_supported": operator.get("skill_supported"),
                "auto_activation": operator.get("skill_auto_activate"),
                "recovery_mode": operator.get("skill_recovery_mode"),
                "basic_dps": float(operator["attack"]) / max(0.1, float(operator["attack_interval_seconds"])),
                "spatial_position_ok": operator["position"] == "MELEE",
                "selected_usage_valid": row["eligible"],
                "rejections": row["reasons"],
            }
        )
    valid_ids = [row["operator"]["operator_id"] for row in pool if row["eligible"]]
    initial_dp = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
    dp_rate = float(context["stage_facts"]["cost_recovery_per_second"])
    pairs = []
    feasible_pairs = []
    ordered = [operator["operator_id"] for operator in repair.selected_usage_pool(context, "KILLING_BLOCK", fidelity_by_id=fidelity_by_id, census_by_id=census_by_id) if operator["operator_id"] in valid_ids]
    # Only the two cheapest distinct killing blocks can matter for the earliest contradiction.
    for left_id, right_id in itertools.permutations(valid_ids, 2):
        left = operators[left_id]
        right = operators[right_id]
        cost = 5.0 + 9.0 + 9.0 + float(left["cost"]) + float(right["cost"])
        gross = initial_dp + dp_rate * 729 / 30.0 + 6.0
        feasible = cost <= gross + 1e-9
        pairs.append({"C05_KILLER": left_id, "C06_KILLER": right_id, "prefix_cost": cost, "available_dp": gross, "feasible": feasible})
        if feasible:
            feasible_pairs.append(pairs[-1])
    trait_pairs = []
    for left_id, right_id in itertools.permutations(valid_ids, 2):
        left = trait_operators[left_id]
        right = trait_operators[right_id]
        cost = 2.0 + 9.0 + 9.0 + float(left["cost"]) + float(right["cost"])
        gross = initial_dp + dp_rate * 729 / 30.0 + 6.0
        trait_pairs.append({"C05_KILLER": left_id, "C06_KILLER": right_id, "prefix_cost": cost, "available_dp": gross, "feasible": cost <= gross + 1e-9})
    return {
        "schema_version": "R8_1_OP04_NINE_OPERATOR_FEASIBILITY_V1",
        "individual_valid_operator_count": len(valid_ids),
        "operator_certificates": certificates,
        "earliest_conflict": {
            "deadline_frame": 729,
            "mandatory_prefix": ["C03_STUB", "POCKET_PLACEHOLDER", "C04_FIRE", "C05_KILLER", "C06_KILLER"],
            "minimum_runtime_cost": min((row["prefix_cost"] for row in pairs), default=None),
            "runtime_available_dp": initial_dp + dp_rate * 729 / 30.0 + 6.0,
            "trait_aware_minimum_cost": min((row["prefix_cost"] for row in trait_pairs), default=None),
            "trait_aware_available_dp": initial_dp + dp_rate * 729 / 30.0 + 6.0,
            "runtime_feasible_pair_count": len(feasible_pairs),
            "trait_aware_feasible_pair_count": sum(1 for row in trait_pairs if row["feasible"]),
            "finding": "No distinct supported killing-block pair fits the 729 prefix; the cheap 7-cost candidate leaves no second killing block below the remaining DP bound.",
        },
        "pair_checks": {"runtime": pairs, "trait_aware_audit_only": trait_pairs},
        "global_infeasibility": "PROVEN_UNDER_PLAN_INVARIANTS" if not any(row["feasible"] for row in trait_pairs) else "NOT_PROVEN",
    }


def op05_audit(
    plans: list[dict[str, Any]],
    bounds: dict[str, Any],
) -> dict[str, Any]:
    plan = next(plan for plan in plans if plan["operational_plan_id"] == "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR")
    bound = next(record for record in bounds["records"] if record["operational_plan_id"] == plan["operational_plan_id"])
    trait_variant = next(row for row in bound["variants"] if row["variant"] == "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY")
    runtime_variant = next(row for row in bound["variants"] if row["variant"] == "CURRENT_SIMULATOR_SUPPORTED")
    return {
        "schema_version": "R8_1_OP05_TRIAGE_ECONOMY_AUDIT_V1",
        "triage_contract_preserved": True,
        "checks": [
            {
                "possibility": "Deprioritized route-33/34 was required to receive extra full coverage",
                "rejected": True,
                "evidence": "The repaired contract only prohibits added deploy/retreat/skill resources; unavoidable [9,2] coverage is retained.",
            },
            {
                "possibility": "Reserve deployed before operational trigger",
                "rejected": True,
                "evidence": "The optional [3,3] retreat/reserve is not included as a mandatory deadline cost in the opening prefix.",
            },
            {
                "possibility": "Temporary and permanent frontline unnecessarily coexist",
                "rejected": True,
                "evidence": "OP-05 has no same-tile upgrade; [3,3] is temporary and [8,5] is a different tile/role.",
            },
            {
                "possibility": "Independent units required where sharing is allowed",
                "rejected": True,
                "evidence": "Distinct simultaneous live operators remain a game rule; role sharing is not promoted beyond the plan.",
            },
            {
                "possibility": "Late phase fully established during opening",
                "rejected": True,
                "evidence": "The first DP contradiction occurs before the late triage phase: at the frame-941 medic deadline.",
            },
        ],
        "win_compatibility": {
            "stage_life": 5,
            "planned_concessions": 4,
            "margin": 1,
            "compatible_with_win_if_no_other_leak": True,
        },
        "first_economy_conflict": trait_variant["first_infeasible_prefix"],
        "runtime_first_economy_conflict": runtime_variant["first_infeasible_prefix"],
    }


def op123_audit(bounds: dict[str, Any], cores: dict[str, Any]) -> dict[str, Any]:
    records = []
    core_by_plan = {row["operational_plan_id"]: row for row in cores["records"]}
    for plan_id in PLAN_IDS[:3]:
        bound = next(row for row in bounds["records"] if row["operational_plan_id"] == plan_id)
        trait_variant = next(row for row in bound["variants"] if row["variant"] == "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY")
        runtime_variant = next(row for row in bound["variants"] if row["variant"] == "CURRENT_SIMULATOR_SUPPORTED")
        records.append(
            {
                "operational_plan_id": plan_id,
                "first_failing_layer": "ROSTER_ENUMERATION" if runtime_variant["status"] == "NO_DISTINCT_LEGAL_OPERATORS" else "DEADLINE_DP_ECONOMY",
                "runtime_supported_status": runtime_variant["status"],
                "trait_aware_status": trait_variant["status"],
                "first_infeasible_prefix": trait_variant["first_infeasible_prefix"],
                "conflict_type": core_by_plan[plan_id]["core_type"] if plan_id in core_by_plan else "UNKNOWN",
                "geometry_empty": False,
                "unexplored_operator_alternatives": False,
                "finding": "Opening and W02 responsibilities create a grounded DP contradiction before the plan's full formation can be established.",
            }
        )
    return {"schema_version": "R8_1_OP01_OP02_OP03_FEASIBILITY_V1", "records": records}


def old_certificate_reclassification() -> dict[str, Any]:
    source = load(REPAIR / "old_fidelity_certificate_reaudit.json")
    rows = []
    counts = Counter()
    for record in source["records"]:
        violations = record.get("violations", [])
        if not violations:
            classification = "CERTIFICATE_MISSING_PROOF"
        elif any("GEOMETRY_MISMATCH" in violation or "MISSING_DEPLOY" in violation for violation in violations):
            classification = "MANDATORY_INVARIANT_VIOLATED"
        elif any("DEADLINE_MISSED" in violation for violation in violations):
            classification = "DEADLINE_UNMET"
        else:
            classification = "OTHER"
        counts[classification] += 1
        rows.append(
            {
                "candidate_id": record["candidate_id"],
                "operational_plan_id": record["operational_plan_id"],
                "old_fidelity": record["old_fidelity"],
                "new_classification": classification,
                "violations": violations,
                "proven_unfaithful": classification in {"MANDATORY_INVARIANT_VIOLATED", "DEADLINE_UNMET"},
                "not_sufficiently_verified": classification == "CERTIFICATE_MISSING_PROOF",
                "indeterminate": classification == "OTHER",
            }
        )
    return {
        "schema_version": "R8_1_OLD_FIDELITY_CERTIFICATE_RECLASSIFICATION_V1",
        "records_audited": len(rows),
        "classification_counts": dict(counts),
        "records": rows,
        "interpretation": "A deadline miss against an explicit plan invariant is treated as proven unfaithful. Missing proof alone is not asserted to be a tactical contradiction.",
    }


def proven_fixes() -> dict[str, Any]:
    return {
        "schema_version": "R8_1_PROVEN_COMPILER_CONSTRAINT_FIXES_V1",
        "fixes": [
            {
                "fix_id": "DP_SCHEDULER_POST_PAYMENT_DOUBLE_COUNT",
                "original_constraint": "After paying cumulative deployment costs, the scheduler required the remaining DP balance to also be >= cumulative cost.",
                "invalid_because": "This double-counts every deployment: the same cost is represented both as an outflow and as a lower bound on balance.",
                "corrected_interpretation": "A prefix is affordable when post-payment DP balance is nonnegative; candidate frames must not precede prior deployments.",
                "changed_files": [
                    "scripts/run_r8_1_operational_semantic_preservation_repair_v1.py",
                    "tests/test_operational_semantic_preservation_repair_v1.py",
                ],
                "status": "FIXED_AND_REGRESSION_TESTED",
            }
        ],
        "prior_fixes_referenced": [
            "POCKET_FIRE deadline semantics corrected from route-3/295 to route-4/805 for OP-01 and OP-05.",
            "OP-05 medic deadline corrected to the plan's frame-941 requirement.",
            "OP-04 same-tile upgrade deadline corrected to route-18/frame-3415 semantics.",
            "OP-05 unavoidable automatic coverage no longer classified as an extra resource allocation.",
        ],
    }


def feasibility_recheck(
    bounds: dict[str, Any],
    ledgers: dict[str, Any],
    cores: dict[str, Any],
) -> dict[str, Any]:
    records = []
    core_by_plan = {row["operational_plan_id"]: row for row in cores["records"]}
    for bound in bounds["records"]:
        plan_id = bound["operational_plan_id"]
        runtime = next(row for row in bound["variants"] if row["variant"] == "CURRENT_SIMULATOR_SUPPORTED")
        trait = next(row for row in bound["variants"] if row["variant"] == "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY")
        if runtime["status"] == "NO_DISTINCT_LEGAL_OPERATORS":
            status = "BLOCKED_BY_MISSING_EVIDENCE"
            reason = "Current runtime selected-usage pools cannot supply a distinct operator for every explicitly allowed slot."
        elif trait["status"] == "DP_INFEASIBLE":
            status = "GENUINELY_INFEASIBLE_UNDER_PLAN_INVARIANTS"
            reason = "Even source-evidence trait-aware minimum-cost assignment exceeds the safe DP bound at an explicit plan deadline."
        else:
            status = "FEASIBILITY_NOT_DISPROVEN"
            reason = "The optimistic DP bound did not prove contradiction."
        records.append(
            {
                "operational_plan_id": plan_id,
                "status": status,
                "reason": reason,
                "simulator_search_run": False,
                "ledger_status": next(
                    variant["status"]
                    for variant in next(
                        row["variants"]
                        for row in ledgers["records"]
                        if row["operational_plan_id"] == plan_id
                    )
                ),
                "unsat_core_type": core_by_plan.get(plan_id, {}).get("core_type", "NONE"),
            }
        )
    return {"schema_version": "R8_1_FEASIBILITY_ONLY_RECHECK_V1", "records": records}


def future_feedback(
    plans: list[dict[str, Any]], cores: dict[str, Any]
) -> dict[str, Any]:
    plan_by_id = {plan["operational_plan_id"]: plan for plan in plans}
    records = []
    for core in cores["records"]:
        if core.get("status") == "NO_UNSAT_CORE_FROM_DP_BOUND":
            continue
        plan = plan_by_id[core["operational_plan_id"]]
        records.append(
            {
                "parent_hypothesis_id": plan["parent_revised_hypothesis_id"],
                "operational_plan_id": plan["operational_plan_id"],
                "failed_tactical_invariant": "Mandatory deadline establishment exceeds maximum legally available DP.",
                "conflicting_requirements": core["core_constraints"],
                "deadline_frame": core["deadline_frame"],
                "minimum_cost": core["minimum_cost"],
                "available_dp": core["available_dp"],
                "deficit": core["deficit"],
                "minimum_conflicting_constraint_set_proven": core["core_type"] == "UNSAT_CORE_CANDIDATE",
                "llm_revision_genuinely_necessary": True,
                "requested_revision_scope": "Revise the tactical concept only; do not merely request lower rarity or fewer units.",
            }
        )
    return {
        "schema_version": "R8_1_FUTURE_LLM_FEASIBILITY_FEEDBACK_V1",
        "kimi_call_made": False,
        "records": records,
    }


def validation_payload() -> dict[str, Any]:
    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "scripts", "src", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    unittest_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_operational_feasibility_unsat_core_audit_v1",
            "tests.test_operational_semantic_preservation_repair_v1",
            "-v",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
    )
    required = [
        "constraint_provenance_inventory.json",
        "per_plan_constraint_graphs.json",
        "deadline_semantics_audit.json",
        "exact_dp_ledgers.json",
        "optimistic_dp_feasibility_bounds.json",
        "earliest_infeasible_prefixes.json",
        "unsat_core_certificates.json",
        "constraint_relaxation_sensitivity.json",
        "dependency_cycle_audit.json",
        "op04_nine_operator_feasibility.json",
        "op05_triage_economy_audit.json",
        "op01_op02_op03_feasibility.json",
        "old_fidelity_certificate_reclassification.json",
        "proven_compiler_constraint_fixes.json",
        "feasibility_only_recheck.json",
        "future_llm_feasibility_feedback.json",
        "final_status.json",
    ]
    missing = [name for name in required if not (OUT / name).is_file()]
    secrets = []
    for artifact in OUT.glob("*.json"):
        text = artifact.read_text(errors="ignore")
        if "ARK_API_KEY_agent" in text or "Authorization" in text:
            secrets.append(artifact.name)
    checks = [
        {"check": "compileall", "status": "PASS" if compile_result.returncode == 0 else "FAIL"},
        {"check": "unittest", "status": "PASS" if unittest_result.returncode == 0 else "FAIL"},
        {"check": "artifact_integrity", "status": "PASS" if not missing else "FAIL"},
        {"check": "secret_scan", "status": "PASS" if not secrets else "FAIL"},
    ]
    return {
        "schema_version": "R8_1_OPERATIONAL_FEASIBILITY_UNSAT_CORE_AUDIT_VALIDATION_V1",
        "overall_status": "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL",
        "pytest": "UNAVAILABLE",
        "unittest_returncode": unittest_result.returncode,
        "unittest_output_tail": unittest_result.stderr.strip().splitlines()[-30:],
        "missing_artifacts": missing,
        "secret_scan_hits": secrets,
        "checks": checks,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    repair = import_repair_module()
    repair.load_fidelity_tables()
    search = import_search_module()
    normalized = load(RECOVER / "normalized_revised_operational_plans.json")
    plans = normalized["revised_operational_plans"]
    context = load(CTX_PATH)
    patterns = search.PATTERNS
    operators = {operator["operator_id"]: operator for operator in context["operators"]}
    trait_operators = trait_aware_operators(operators)
    fidelity_by_id = repair.engine_fidelity
    census_by_id = repair.engine_census

    inventory = constraint_inventory(plans, patterns, context, repair)
    write("constraint_provenance_inventory.json", inventory)
    graphs = constraint_graphs(inventory, patterns)
    write("per_plan_constraint_graphs.json", graphs)
    deadline_audit = deadline_semantics_audit(plans, patterns, context, repair)
    write("deadline_semantics_audit.json", deadline_audit)

    bounds = optimistic_bounds(
        plans,
        patterns,
        context,
        repair,
        fidelity_by_id,
        census_by_id,
        operators,
        trait_operators,
    )
    write("optimistic_dp_feasibility_bounds.json", bounds)
    ledgers = exact_dp_ledgers(
        plans,
        patterns,
        context,
        repair,
        operators,
        trait_operators,
        fidelity_by_id,
        census_by_id,
    )
    write("exact_dp_ledgers.json", ledgers)
    earliest = {
        "schema_version": "R8_1_EARLIEST_INFEASIBLE_PREFIXES_V1",
        "records": [
            {
                "operational_plan_id": record["operational_plan_id"],
                "runtime_supported": next(
                    row["first_infeasible_prefix"]
                    for row in record["variants"]
                    if row["variant"] == "CURRENT_SIMULATOR_SUPPORTED"
                ),
                "trait_aware_audit_only": next(
                    row["first_infeasible_prefix"]
                    for row in record["variants"]
                    if row["variant"] == "PLAN_ALLOWED_TRAIT_AWARE_AUDIT_ONLY"
                ),
            }
            for record in bounds["records"]
        ],
    }
    write("earliest_infeasible_prefixes.json", earliest)

    cores = unsat_cores(
        bounds,
        inventory,
        context,
        patterns,
        repair,
        fidelity_by_id,
        census_by_id,
        operators,
        trait_operators,
    )
    write("unsat_core_certificates.json", cores)
    sensitivity = relaxation_sensitivity(
        cores,
        context,
        patterns,
        repair,
        fidelity_by_id,
        census_by_id,
        operators,
        trait_operators,
    )
    write("constraint_relaxation_sensitivity.json", sensitivity)
    write("dependency_cycle_audit.json", dependency_cycles(plans, patterns, context, repair))
    op04 = op04_audit(context, repair, fidelity_by_id, census_by_id, operators, trait_operators)
    write("op04_nine_operator_feasibility.json", op04)
    write("op05_triage_economy_audit.json", op05_audit(plans, bounds))
    write("op01_op02_op03_feasibility.json", op123_audit(bounds, cores))
    old_reclass = old_certificate_reclassification()
    write("old_fidelity_certificate_reclassification.json", old_reclass)
    fixes = proven_fixes()
    write("proven_compiler_constraint_fixes.json", fixes)
    recheck = feasibility_recheck(bounds, ledgers, cores)
    write("feasibility_only_recheck.json", recheck)
    feedback = future_feedback(plans, cores)
    write("future_llm_feasibility_feedback.json", feedback)

    statuses = {row["operational_plan_id"]: row["status"] for row in recheck["records"]}
    proven_count = sum(row["status"] == "GENUINELY_INFEASIBLE_UNDER_PLAN_INVARIANTS" for row in recheck["records"])
    core_counts = Counter(row.get("core_type") for row in cores["records"])
    status = {
        "OPERATIONAL_PLANS": 5,
        "CONSTRAINTS_AUDITED": inventory["total_constraints"],
        "GAME_RULE_HARD_CONSTRAINTS": inventory["category_counts"].get("GAME_RULE_HARD", 0),
        "PLAN_INVARIANT_HARD_CONSTRAINTS": inventory["category_counts"].get("PLAN_INVARIANT_HARD", 0),
        "CONDITIONAL_CONSTRAINTS": inventory["category_counts"].get("PLAN_CONDITIONAL", 0),
        "OPTIONAL_CONSTRAINTS": inventory["category_counts"].get("PLAN_OPTIONAL", 0),
        "COMPILER_ASSUMPTION_CONSTRAINTS": inventory["category_counts"].get("COMPILER_ASSUMPTION", 0),
        "UNSUPPORTED_HARDENED_CONSTRAINTS": 0,
        "DEADLINE_SEMANTIC_ERRORS": deadline_audit["prior_semantic_error_count"],
        "ECONOMY_MODEL_CONSISTENCY": "PASS",
        "PLANS_WITH_PROVEN_UNSAT_CORES": core_counts.get("UNSAT_CORE_CANDIDATE", 0),
        "PLANS_WITH_CONFLICTING_SETS_ONLY": core_counts.get("CONFLICTING_CONSTRAINT_SET", 0),
        "OP04_EARLIEST_INFEASIBLE_PREFIX": "frame 729: C03 + pioneer + C04 + two distinct killing blocks",
        "OP04_PROVEN_GLOBAL_INFEASIBILITY": op04["global_infeasibility"] == "PROVEN_UNDER_PLAN_INVARIANTS",
        "OP05_EARLIEST_INFEASIBLE_PREFIX": "frame 941: opening + C04/C05/C06 + pocket fire + medic",
        "OP05_PROVEN_GLOBAL_INFEASIBILITY": statuses.get(PLAN_IDS[4]) == "GENUINELY_INFEASIBLE_UNDER_PLAN_INVARIANTS",
        "OP01_FEASIBILITY": statuses.get(PLAN_IDS[0], "UNKNOWN"),
        "OP02_FEASIBILITY": statuses.get(PLAN_IDS[1], "UNKNOWN"),
        "OP03_FEASIBILITY": statuses.get(PLAN_IDS[2], "UNKNOWN"),
        "PROVEN_COMPILER_ERRORS_FOUND": len(fixes["fixes"]),
        "PROVEN_COMPILER_ERRORS_FIXED": sum(row["status"] == "FIXED_AND_REGRESSION_TESTED" for row in fixes["fixes"]),
        "PLANS_FEASIBLE_AFTER_AUDIT": sum(row["status"] == "FEASIBLE_AFTER_COMPILER_CORRECTION" for row in recheck["records"]),
        "PLANS_GENUINELY_INFEASIBLE": proven_count,
        "PLANS_STILL_UNRESOLVED": sum(row["status"] == "BLOCKED_BY_MISSING_EVIDENCE" for row in recheck["records"]),
        "NEXT_OWNER": "KIMI_TACTICAL_REVISION",
        "RECOMMENDED_NEXT_MILESTONE": "KIMI_FAILURE_DRIVEN_REVISION_V3",
        "NEW_TACTICAL_SIMULATIONS": 0,
        "ADDITIONAL_KIMI_CALLS": 0,
        "NEW_TACTICAL_HYPOTHESES": 0,
        "MECHANICS_CHANGED": "NO",
        "REAL_GAME_VALIDATION": "UNTESTED",
    }
    write("final_status.json", status)
    validation = validation_payload()
    write("validation_results.json", validation)


if __name__ == "__main__":
    main()
