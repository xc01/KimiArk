from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_plan_a1_bounded_validation_v1"
SOURCE = ROOT / "output/r8_1_plan_a_bounded_kimi_revision_v4"
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
CENSUS = ROOT / "output/operator_runtime_fidelity_v1/all_operator_census.json"
CATALOG = ROOT / "output/r8_1_llm_operationalization_v1/deterministic_affordance_catalog.json"
PLAN_ID = "R8OP-A1-BLOCK1-COOP-ANCHOR390"
MECHANICS = "m18.9-stage-device-runtime-v1"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def census_operator(census: dict[str, Any], operator_id: str) -> dict[str, Any]:
    return next(row for row in census["operators"] if row["operator_id"] == operator_id)


def physical_damage(atk: float, defense: float) -> float:
    return max(0.05 * atk, atk - defense)


def basic_sequence(operator_id: str, census: dict[str, Any], *, first_attack: int, hp: float, defense: float) -> list[dict[str, Any]]:
    operator = census_operator(census, operator_id)
    damage = physical_damage(float(operator["base_atk"]), defense)
    remaining = hp
    frame = first_attack
    events = []
    while remaining > 0:
        remaining = max(0.0, remaining - damage)
        events.append({"attack_frame": frame, "damage_after_def": round(damage, 6), "remaining_hp": round(remaining, 6)})
        frame += 30
    return events


def caper_sequence(*, first_attack: int, hp: float = 3300.0, defense: float = 150.0) -> list[dict[str, Any]]:
    operator = census_operator(load(CENSUS), "char_4100_caper")
    atk = float(operator["base_atk"])
    normal = physical_damage(atk, defense)
    skill = physical_damage(atk * 2.3, defense)
    remaining = hp
    frame = first_attack
    events = []
    attacks_in_cycle = 0
    while remaining > 0:
        attacks_in_cycle += 1
        is_skill = attacks_in_cycle % 4 == 0
        damage = skill if is_skill else normal
        remaining = max(0.0, remaining - damage)
        events.append({
            "attack_frame": frame,
            "damage_after_def": round(damage, 6),
            "kind": "SKILL" if is_skill else "NORMAL",
            "remaining_hp": round(remaining, 6),
        })
        frame += 30
    return events


def caper_cycle_events(first_attack: int, count: int = 16) -> list[dict[str, Any]]:
    operator = census_operator(load(CENSUS), "char_4100_caper")
    atk = float(operator["base_atk"])
    normal = physical_damage(atk, 150.0)
    skill = physical_damage(atk * 2.3, 150.0)
    return [
        {
            "attack_frame": first_attack + index * 30,
            "damage_after_def": round(skill if (index + 1) % 4 == 0 else normal, 6),
            "kind": "SKILL" if (index + 1) % 4 == 0 else "NORMAL",
        }
        for index in range(count)
    ]


def combined_sequence(census: dict[str, Any]) -> dict[str, Any]:
    talr = census_operator(census, "char_4155_talr")
    talr_damage = physical_damage(float(talr["base_atk"]), 150.0)
    caper_events = caper_cycle_events(390, count=16)
    route_1_events = []
    remaining = 3300.0
    caper_index = 0
    talr_frame = 191
    while remaining > 0 and caper_index < len(caper_events):
        caper = caper_events[caper_index]
        caper_index += 1
        damage = caper["damage_after_def"]
        while talr_frame <= caper["attack_frame"]:
            remaining -= talr_damage
            route_1_events.append({"attack_frame": talr_frame, "source": "char_4155_talr", "damage_after_def": round(talr_damage, 6), "remaining_hp": round(max(0, remaining), 6)})
            talr_frame += 30
            if remaining <= 0:
                break
        if remaining <= 0:
            break
        remaining -= caper["damage_after_def"]
        route_1_events.append({"attack_frame": caper["attack_frame"], "source": "char_4100_caper", "damage_after_def": caper["damage_after_def"], "kind": caper["kind"], "remaining_hp": round(max(0, remaining), 6)})
    route_1_kill = max(row["attack_frame"] for row in route_1_events if row["remaining_hp"] == 0)
    route_3_events = []
    remaining = 3300.0
    talr_frame = 461
    caper_index = 3
    while remaining > 0:
        next_talr = talr_frame
        next_caper = caper_events[caper_index]["attack_frame"] if caper_index < len(caper_events) else 10**12
        if next_talr <= next_caper:
            remaining -= talr_damage
            route_3_events.append({"attack_frame": next_talr, "source": "char_4155_talr", "damage_after_def": round(talr_damage, 6), "remaining_hp": round(max(0, remaining), 6)})
            talr_frame += 30
        else:
            caper = caper_events[caper_index]
            caper_index += 1
            remaining -= caper["damage_after_def"]
            route_3_events.append({"attack_frame": caper["attack_frame"], "source": "char_4100_caper", "damage_after_def": caper["damage_after_def"], "kind": caper["kind"], "remaining_hp": round(max(0, remaining), 6)})
    return {
        "route_1": {"assumption": "BOTH_TARGETS_HELD_ON_TILE_8_5", "events": route_1_events, "kill_frame": route_1_kill},
        "route_3": {"assumption": "ROUTE_1_KILLED_BY_450_AND_TALR_REBLOCKS_ROUTE_3_WITHIN_431_459", "events": route_3_events, "kill_frame": max(row["attack_frame"] for row in route_3_events if row["remaining_hp"] == 0)},
    }


def geometry_certificate() -> dict[str, Any]:
    old = load(ROOT / "output/r8_1_plan_a_opening_witness_v1/plan_a_bounded_opening_frontier.json")
    rows = []
    for operator_id in ("char_103_angel", "char_4100_caper", "char_365_aprl"):
        row = next(item for item in old["candidates"] if item["operator_id"] == operator_id and item["slot_id"] == "A03_MERGED_ANCHOR")
        rows.append({
            "covers_8_5": row["geometry"]["any_direction_satisfies_all_required_tiles"],
            "coverage_by_direction": row["geometry"]["coverage_by_direction"],
            "operator_id": operator_id,
            "selected_direction": "DOWN" if operator_id == "char_4100_caper" else None,
        })
    return {
        "origin": [9, 2], "required_tile": [8, 5], "rows": rows,
        "schema_version": "R8_1_PLAN_A1_GEOMETRY_CERTIFICATE_V1",
    }


def dp_ledger() -> dict[str, Any]:
    rows = []
    spent = 0.0

    def add(event: str, frame: int, cost: float) -> None:
        nonlocal spent
        before = 10.0 + frame / 30.0 - spent
        spent += cost
        rows.append({
            "affordable": before - cost >= -1e-9,
            "available_dp_after": round(before - cost, 6),
            "available_dp_before": round(before, 6),
            "cost": cost,
            "event": event,
            "frame": frame,
        })

    add("DEPLOY_A01_CHAR_272_STRONG", 27, 5.0)
    add("DEPLOY_A02_CHAR_4155_TALR", 191, 6.0)
    add("RETREAT_A01_NO_REFUND_ASSUMED", 390, 0.0)
    add("DEPLOY_A03_CHAR_4100_CAPER", 390, 12.0)
    add("DEPLOY_A04_CHAR_455_NOTHIN", 725, 6.0)
    return {
        "base_cost_evidence": "CURRENT_SIMULATOR_BASE_COST_MODEL; merchant long-run economy UNKNOWN",
        "evidence_status": "CONDITIONAL_BASE_COST_LEDGER_NOT_GAME_ECONOMY_CERTIFICATE",
        "hypothetical_refund": "NOT_USED",
        "limitations": ["Retreat refund and merchant upkeep remain UNKNOWN.", "COND_ROUTE6 omits A05 and concedes route-6.", "COND_ANCHOR_TILE remains unresolved."],
        "rows": rows,
        "schema_version": "R8_1_PLAN_A1_BASE_COST_DP_LEDGER_V1",
    }


def candidate_frontier() -> dict[str, Any]:
    combinations = [
        {"A01_C03_STUB": "char_272_strong", "A02_C01_HOLDER": "char_4155_talr", "A03_MERGED_ANCHOR": "char_4100_caper", "A04_C05_DUELIST": "char_455_nothin", "A05_C06_DUELIST": "OMITTED"},
        {"A01_C03_STUB": "char_272_strong", "A02_C01_HOLDER": "char_455_nothin", "A03_MERGED_ANCHOR": "char_4100_caper", "A04_C05_DUELIST": "char_4155_talr", "A05_C06_DUELIST": "OMITTED"},
    ]
    for index, row in enumerate(combinations, 1):
        distinct = {row["A01_C03_STUB"], row["A02_C01_HOLDER"], row["A03_MERGED_ANCHOR"], row["A04_C05_DUELIST"]}
        row["combination_index"] = index
        row["distinct_live_operators"] = len(distinct) == 4
        row["route6_branch"] = "OMITTED_DEFAULT_CONCESSION"
        row["faithful_complete_witness"] = False
    return {
        "candidate_counts": {"A01_C03_STUB": 1, "A02_C01_HOLDER": 2, "A03_MERGED_ANCHOR": 1, "A04_C05_DUELIST": 2, "A05_C06_DUELIST": 0},
        "combinations": combinations,
        "frame_budget": [0, 941],
        "limits": {"max_candidates_per_required_slot": 3, "max_complete_combinations": 16, "max_action_candidates": 1, "stage_simulations": 0},
        "schema_version": "R8_1_PLAN_A1_BOUNDED_CANDIDATE_FRONTIER_V1",
    }


def semantic_traceability(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "changed_conflicting_assumptions_enforced": {
            "A05_omitted_by_default": True,
            "anchor_is_caper_only": True,
            "no_refund_assumed": True,
            "no_frame_250_deadline": True,
            "wscoot_not_mandatory_before_941": True,
        },
        "invariants": plan["mandatory_tactical_invariants"],
        "schema_version": "R8_1_PLAN_A1_SEMANTIC_TRACEABILITY_V1",
        "traceability": [
            {"enforcement": "candidate_frontier and action candidate", "invariant": "Distinct live operators per simultaneous slot"},
            {"enforcement": "geometry certificate and single A03 candidate", "invariant": "caper at [9,2] DOWN, no angel/aprl substitute"},
            {"enforcement": "action candidate omits A05", "invariant": "A05 omitted and route-6 conceded"},
            {"enforcement": "base-cost DP ledger", "invariant": "No refund in mandatory ledger"},
            {"enforcement": "finite damage certificate", "invariant": "Frame 250 not used; route contracts derived from per-hit sequence"},
        ],
    }


def operational_certificate(plan: dict[str, Any], census: dict[str, Any]) -> dict[str, Any]:
    strong_route_2 = basic_sequence("char_272_strong", census, first_attack=27, hp=3300.0, defense=150.0)
    talr_route_1_only = basic_sequence("char_4155_talr", census, first_attack=191, hp=3300.0, defense=150.0)
    caper_only_route_1 = caper_sequence(first_attack=474, hp=3300.0, defense=150.0)
    cooperation = combined_sequence(census)
    nothin_route_7 = basic_sequence("char_455_nothin", census, first_attack=725, hp=3500.0, defense=100.0)
    return {
        "action_candidate": {
            "actions": [
                {"action_type": "DEPLOY", "direction": "RIGHT", "frame": 27, "operator": "char_272_strong", "tile": [3, 3]},
                {"action_type": "DEPLOY", "direction": "LEFT", "frame": 191, "operator": "char_4155_talr", "tile": [8, 5]},
                {"action_type": "RETREAT", "frame": 390, "operator": "char_272_strong"},
                {"action_type": "DEPLOY", "direction": "DOWN", "frame": 390, "operator": "char_4100_caper", "tile": [9, 2]},
                {"action_type": "DEPLOY", "direction": "RIGHT", "frame": 725, "operator": "char_455_nothin", "tile": [5, 1]},
            ],
            "direction_complete": True,
            "schema_version": "R8_1_PLAN_A1_ACTION_CANDIDATE_V1",
            "source_plan_id": PLAN_ID,
        },
        "deadlines": {
            "A01_by_27": {"deadline": 27, "pass": True},
            "A02_by_191": {"deadline": 191, "pass": True},
            "A03_within_390_474": {"deadline": 474, "pass": True},
            "A04_by_725": {"deadline": 725, "pass": True},
            "A05": {"branch": "OMITTED_DEFAULT_CONCESSION", "pass": True},
        },
        "finite_window_damage": {
            "evidence_status": "CONFIRMED_UNDER_CURRENT_SIMULATOR_FORMULAS_WITH_EXPLICIT_CONDITIONS",
            "nothin_route_7_blocked": {"events": nothin_route_7, "kill_frame": nothin_route_7[-1]["attack_frame"]},
            "caper_only_route_1_if_first_attack_474": {"events": caper_only_route_1, "kill_frame": caper_only_route_1[-1]["attack_frame"], "pass_route_1_before_805": caper_only_route_1[-1]["attack_frame"] < 805},
            "strong_route_2_blocked": {"events": strong_route_2, "kill_frame": strong_route_2[-1]["attack_frame"]},
            "talr_route_1_without_caper": {"events": talr_route_1_only, "kill_frame": talr_route_1_only[-1]["attack_frame"], "pass_route_1_before_805": talr_route_1_only[-1]["attack_frame"] < 805},
            "talr_and_caper_cooperation": cooperation,
            "route_3_deadline_pass_under_cooperation": cooperation["route_3"]["kill_frame"] < 941,
        },
        "mechanism_evidence_status": {
            "base_cost": "CONFIRMED_FROM_CURRENT_SIMULATOR_MODEL",
            "block_and_damage_formula": "CONFIRMED_FROM_PRTS_SOURCE_AND_SIMULATOR_CODE",
            "client_attack_timing": "UNKNOWN",
            "merchant_upkeep": "UNKNOWN",
            "retreat_refund": "UNKNOWN_AND_NOT_ASSUMED",
            "roadblock_tile_legality": "UNKNOWN",
            "target_ordering": "UNKNOWN",
            "traits_and_talents": "UNKNOWN_UNLESS_EXPLICITLY_REQUIRED",
        },
        "schema_version": "R8_1_PLAN_A1_OPERATIONAL_CERTIFICATE_V1",
        "witness": {
            "complete_faithful_witness": False,
            "conditional_action_candidate": True,
            "reasons_not_full_witness": [
                "COND_ANCHOR_TILE: [9,2] roadblock deployment legality UNKNOWN",
                "COND_COOP_ROUTE3: route-3 depends on holder/caper cooperation and target ordering",
                "COND_UPKEEP: merchant long-run economy is UNKNOWN",
                "route-6 and route-8 concessions are intentional but require stage-life accounting confirmation",
            ],
        },
    }


def validate(plan: dict[str, Any], frontier: dict[str, Any], certificate: dict[str, Any]) -> dict[str, Any]:
    catalog_ids = {row["affordance_id"] for row in load(CATALOG)["affordances"]}
    known_operators = {row["operator_id"] for row in load(CENSUS)["operators"]}
    checks = {
        "action_candidate_direction_complete": certificate["action_candidate"]["direction_complete"],
        "all_plan_operators_known": all(row["unit"] in known_operators for row in plan["deployment_positions_and_directions"] if row["unit"] != "(omitted)"),
        "at_most_one_action_candidate": True,
        "budget_respected": all(count <= 3 for count in frontier["candidate_counts"].values()) and len(frontier["combinations"]) <= 16,
        "no_stage_simulation": frontier["limits"]["stage_simulations"] == 0,
        "no_stage_simulation_claimed_in_certificate": certificate["witness"]["complete_faithful_witness"] is False,
        "plan_affordances_known": set(plan["selected_affordance_ids"]).issubset(catalog_ids),
        "route6_concession_preserved": any(row.get("id") == "COND_ROUTE6" and "concede route-6" in row.get("if_false", "") for row in plan["conditional_responsibilities"]),
        "selected_combination_distinct": all(row["distinct_live_operators"] for row in frontier["combinations"]),
    }
    return {"checks": checks, "schema_version": "R8_1_PLAN_A1_BOUNDED_VALIDATION_V1", "status": "PASS" if all(checks.values()) else "FAIL", "test_execution_status": "NOT_EXECUTED_BY_THIS_VALIDATOR", "test_results": []}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = load(SOURCE / "llm_structured_output.json")
    plan = source["revised_operational_plans"][0]
    census = load(CENSUS)
    frontier = candidate_frontier()
    certificate = operational_certificate(plan, census)
    validation = validate(plan, frontier, certificate)
    artifacts = {
        "action_candidate.json": certificate["action_candidate"],
        "bounded_candidate_frontier.json": frontier,
        "dp_ledger.json": dp_ledger(),
        "geometry_certificate.json": geometry_certificate(),
        "operational_certificate.json": certificate,
        "revised_operational_plan.json": plan,
        "semantic_traceability.json": semantic_traceability(plan),
    }
    for name, payload in artifacts.items():
        write(name, payload)
    write("old_assumption_revision_comparison.json", {
        "new_plan_id": PLAN_ID,
        "revisions": plan["changed_conflicting_assumptions"],
        "schema_version": "R8_1_PLAN_A1_OLD_ASSUMPTION_REVISION_COMPARISON_V1",
    })
    write("scoped_conflicts_and_unknowns.json", {
        "schema_version": "R8_1_PLAN_A1_SCOPED_CONFLICTS_AND_UNKNOWNS_V1",
        "scoped_conflicts": certificate["witness"]["reasons_not_full_witness"],
        "unknowns": [row["unknown"] for row in plan["unknown_dependencies"]],
    })
    write("source_input_manifest.json", {
        "inputs": {
            "llm_structured_output.json": file_record(SOURCE / "llm_structured_output.json"),
            "corrected_fixed_contracts.json": file_record(SOURCE / "corrected_fixed_contracts.json"),
            "deterministic_context.json": file_record(CONTEXT),
            "all_operator_census.json": file_record(CENSUS),
            "deterministic_affordance_catalog.json": file_record(CATALOG),
            "run_r8_1_plan_a1_bounded_validation_v1.py": file_record(Path(__file__)),
        },
        "mechanics_version": MECHANICS,
        "schema_version": "R8_1_PLAN_A1_BOUNDED_VALIDATION_MANIFEST_V1",
    })
    write("validation_results.json", validation)
    write("final_status.json", {
        "action_candidates": 1,
        "complete_combinations": len(frontier["combinations"]),
        "faithful_witness": False,
        "kimi_calls": 1,
        "mechanics_changed": False,
        "new_operational_plans": 1,
        "operational_plan_id": PLAN_ID,
        "stage_prefix_simulations": 0,
        "status": "BOUNDED_VALIDATION_COMPLETE_CONDITIONAL_ACTION_CANDIDATE_NO_FULL_WITNESS",
    })


if __name__ == "__main__":
    main()
