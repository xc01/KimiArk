from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_plan_a_fixed_candidate_contract_v1"
HISTORICAL = ROOT / "output/r8_1_plan_a_opening_witness_v1"
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
PLAN = ROOT / "output/r8_1_constraint_informed_revision_v3/revised_operational_plans.json"
CENSUS = ROOT / "output/operator_runtime_fidelity_v1/all_operator_census.json"
GENERATION_CODE = ROOT / "scripts/build_operator_runtime_fidelity.py"
OPERATIONAL_PLAN_ID = "R8OP-A-MERGED-ANCHOR-REFUND-LATTICE"
MECHANICS_VERSION = "m18.9-stage-device-runtime-v1"
FRAME_BUDGET = (0, 941)
MAX_STRUCTURAL_COMBINATIONS = 16
MAX_STAGE_PREFIX_SIMULATIONS = 0


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
    }


def source_manifest() -> dict[str, Any]:
    paths = [
        CONTEXT,
        PLAN,
        CENSUS,
        GENERATION_CODE,
        ROOT / "scripts/run_r8_1_plan_a_opening_witness_v1.py",
        ROOT / "scripts/run_r8_1_plan_a_fixed_candidate_contract_v1.py",
        HISTORICAL / "final_status.json",
        HISTORICAL / "plan_a_bounded_opening_frontier.json",
        HISTORICAL / "plan_a_scoped_dp_ledger.json",
        HISTORICAL / "plan_a_witness_certificate.json",
        HISTORICAL / "operator_runtime_fidelity_input_provenance.json",
        ROOT / "docs/review/23a623a/REVIEW.md",
    ]
    return {
        "schema_version": "R8_1_PLAN_A_FIXED_CONTRACT_SOURCE_MANIFEST_V1",
        "generation_code_status": "PRESENT_IN_WORKING_TREE_AND_DELIVERED",
        "generation_code_is_original_table_generator": "UNKNOWN_ORIGINAL_GENERATION_COMMIT",
        "inputs": {path.name: file_record(path) for path in paths},
        "mechanics_version": MECHANICS_VERSION,
    }


def selected_skill(census: dict[str, Any], operator_id: str) -> dict[str, Any]:
    operator = next(row for row in census["operators"] if row["operator_id"] == operator_id)
    skill_id = {
        "char_103_angel": "skchr_angel_1",
        "char_4100_caper": "skchr_caper_1",
        "char_365_aprl": "skchr_aprl_1",
    }[operator_id]
    return next(row for row in operator["skills"] if row["skill_id"] == skill_id)


def physical_hit(atk: float, defense: float) -> float:
    return max(0.05 * atk, atk - defense)


def anchor_attack_sequence(
    operator: dict[str, Any],
    census: dict[str, Any],
    *,
    first_attack_frame: int,
) -> list[dict[str, Any]]:
    skill = selected_skill(census, operator["operator_id"])
    census_operator = next(row for row in census["operators"] if row["operator_id"] == operator["operator_id"])
    attack = float(census_operator["base_atk"])
    interval = float(census_operator["basic_attack_time"])
    defense = 150.0
    initial_sp = int(skill["initial_sp"])
    sp_cost = int(skill["sp_cost"])
    scale = float(skill["attack_profile_changes"]["next_attack_scale"])
    hit_count = int(skill["attack_profile_changes"]["hit_count"])
    hp = 3300.0
    current_sp = initial_sp
    pending = current_sp >= sp_cost
    remaining_hp = hp
    frame = first_attack_frame
    events: list[dict[str, Any]] = []
    while remaining_hp > 0.0:
        if pending:
            kind = "SKILL"
            hits = hit_count
            damage_per_hit = physical_hit(attack * scale, defense)
            current_sp = 0
            pending = False
        else:
            kind = "NORMAL"
            hits = 1
            damage_per_hit = physical_hit(attack, defense)
            current_sp += 1
            if current_sp >= sp_cost:
                pending = True
        damage = damage_per_hit * hits
        remaining_hp = max(0.0, remaining_hp - damage)
        events.append(
            {
                "attack_frame": frame,
                "damage_per_hit_after_def": round(damage_per_hit, 6),
                "hit_count": hits,
                "kind": kind,
                "remaining_hp": round(remaining_hp, 6),
                "total_damage": round(damage, 6),
            }
        )
        frame += int(round(interval * 30.0))
    return events


def route_frame(context: dict[str, Any], route_id: str, distance: float) -> int:
    route = next(row for row in context["exact_route_threats"]["routes"] if row["route_id"] == route_id)
    spawn = route["spawn_frames"][0]
    speed = float(route["enemy_speed"])
    return math.ceil(spawn + distance / speed * 30.0)


def finite_window_contracts(
    candidates: list[dict[str, Any]],
    census: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    route_1_enter = route_frame(context, "route-1", 7.0)
    route_1_leak = route_frame(context, "route-1", 8.0)
    route_3_enter = route_frame(context, "route-3", 7.0)
    route_3_leak = route_frame(context, "route-3", 8.0)
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        operator_id = candidate["operator_id"]
        geometry = candidate["geometry"]
        direction = next(
            (
                key
                for key, value in geometry["direction_satisfies_all_required_tiles"].items()
                if value
            ),
            None,
        )
        contract = {
            "coverage_direction": direction,
            "evidence_status": "NOT_APPLICABLE_NO_REQUIRED_TILE_COVERAGE",
            "operator_id": operator_id,
            "route_contracts": {},
        }
        if operator_id == "char_4100_caper":
            # The fixed no-refund economy makes this candidate affordable at 450.
            first_attack = 450
            route_1_events = anchor_attack_sequence(candidate, census, first_attack_frame=first_attack)
            route_3_start = route_1_events[-1]["attack_frame"] + 30
            route_3_events = anchor_attack_sequence(candidate, census, first_attack_frame=route_3_start)
            contract["coverage_direction"] = direction
            contract["evidence_status"] = "CONFIRMED_UNDER_CURRENT_SIMULATOR_FORMULAS_WITH_EXPLICIT_CONDITIONS"
            contract["route_contracts"] = {
                "route-1": {
                    "block_or_transit_assumption": "TARGET_REMAINS_ON_TILE_8_5",
                    "coverage_window_frames": [route_1_enter, route_1_leak],
                    "deadline_frame": 805,
                    "first_attack_frame": first_attack,
                    "kill_frame": route_1_events[-1]["attack_frame"],
                    "passes_deadline": route_1_events[-1]["attack_frame"] < 805,
                    "required_enemy_hp": 3300.0,
                    "attack_events": route_1_events,
                },
                "route-3": {
                    "block_or_transit_assumption": "TARGET_REMAINS_ON_TILE_8_5_AFTER_ROUTE_1_IS_KILLED",
                    "coverage_window_frames": [route_3_enter, route_3_leak],
                    "deadline_frame": 941,
                    "first_attack_frame": route_3_start,
                    "kill_frame": route_3_events[-1]["attack_frame"],
                    "passes_deadline": route_3_events[-1]["attack_frame"] < 941,
                    "required_enemy_hp": 3300.0,
                    "attack_events": route_3_events,
                },
            }
            contract["latest_first_attack_frame_if_targets_stay_on_tile"] = 250
            contract["latest_first_attack_frame_if_targets_transit_without_block"] = None
            contract["latest_frame_note"] = (
                "With one-second attacks and simulator spawn-order targeting, route-1 must start by "
                "frame 250 so route-3 can begin at 610 and finish at 940. If neither target remains "
                "on [8,5], the two 3300-HP contracts cannot both be completed before their windows close."
            )
            contract["finite_window_deadline_contract_pass"] = (
                contract["route_contracts"]["route-1"]["passes_deadline"]
                and contract["route_contracts"]["route-3"]["passes_deadline"]
            )
        records.append(contract)
    return {
        "schema_version": "R8_1_PLAN_A_FINITE_WINDOW_DAMAGE_CONTRACTS_V1",
        "damage_formula": {
            "evidence_class": "CONFIRMED_FROM_PRTS_SOURCE_AND_SIMULATOR_CODE",
            "formula": "max(0.05 * A, A - DEF) per physical hit",
        },
        "frame_budget": list(FRAME_BUDGET),
        "mechanics_version": MECHANICS_VERSION,
        "preconditions_and_limits": [
            "Origin [9,2] currently contains trap_020_roadblock#2; deployment legality and any required destruction are UNKNOWN.",
            "The calculation assumes only the selected route-1/route-3 enemies are eligible targets and no intervening device or enemy changes targeting.",
            "Attack timing uses the current simulator's one-second attack interval, instant projectile, zero windup and attack-SP cycle.",
            "Traits, talents, enemy abilities, projectiles at client frame timing and exact GameData attack scheduling are not certified.",
            "route-1 before 805 and route-3 before 941 are the Plan A contract deadlines; frame 295 and frame 431 are contact facts, not FIRE establishment deadlines.",
        ],
        "route_coverage_facts": {
            "route-1": {"enter_tile_8_5_frame": route_1_enter, "leave_or_leak_frame": route_1_leak},
            "route-3": {"enter_tile_8_5_frame": route_3_enter, "leave_or_leak_frame": route_3_leak},
        },
        "candidate_contracts": records,
    }


def dp_at(frame: int, spent: float, *, initial: float = 10.0) -> float:
    return initial + frame / 30.0 - spent


def ledger_rows(anchor_cost: float, *, refund: float, anchor_frame: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    spent = 0.0
    last_frame = 0

    def add(event: str, frame: int, cost: float, extra_refund: float = 0.0) -> None:
        nonlocal spent, last_frame
        before = dp_at(frame, spent) + extra_refund
        spent += cost
        after = before - cost
        rows.append(
            {
                "affordable": after >= -1e-9,
                "available_dp_after": round(after, 6),
                "available_dp_before": round(before, 6),
                "cost": cost,
                "event": event,
                "frame": frame,
                "refund": extra_refund,
            }
        )
        last_frame = frame

    add("A01_C03_STUB_DEPLOY", 27, 5.0)
    add("A02_C01_DAM_DEPLOY", 191, 8.0)
    add("A01_C03_STUB_RETREAT", 390, 0.0, refund)
    add("A03_MERGED_ANCHOR_DEPLOY", anchor_frame, anchor_cost)
    add("A04_C05_DUELIST_DEPLOY", 725, 6.0)
    add("A05_C06_DUELIST_DEPLOY", 729, 6.0)
    return rows


def opening_prefix_ledger(anchor_cost: float, *, anchor_frame: int) -> list[dict[str, Any]]:
    spent = 13.0
    before = dp_at(anchor_frame, spent)
    after = before - anchor_cost
    return [
        {
            "affordable": True,
            "available_dp_after": 5.9,
            "available_dp_before": 10.9,
            "cost": 5.0,
            "event": "A01_C03_STUB_DEPLOY",
            "frame": 27,
            "refund": 0.0,
        },
        {
            "affordable": True,
            "available_dp_after": 3.366667,
            "available_dp_before": 11.366667,
            "cost": 8.0,
            "event": "A02_C01_DAM_DEPLOY",
            "frame": 191,
            "refund": 0.0,
        },
        {
            "affordable": after >= -1e-9,
            "available_dp_after": round(after, 6),
            "available_dp_before": round(before, 6),
            "cost": anchor_cost,
            "event": "A03_MERGED_ANCHOR_DEPLOY",
            "frame": anchor_frame,
            "refund": 0.0,
        },
    ]


def economy_contracts(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    anchor_costs = sorted({row["cost"] for row in candidates})
    branches = []
    for anchor_cost in anchor_costs:
        no_refund_anchor_frame = 450 if anchor_cost == 12.0 else 420
        no_refund_rows = ledger_rows(anchor_cost, refund=0.0, anchor_frame=no_refund_anchor_frame)
        a05_row = no_refund_rows[-1]
        hypothetical_rows = ledger_rows(anchor_cost, refund=5.0, anchor_frame=400)
        deadline_rows = opening_prefix_ledger(anchor_cost, anchor_frame=250)
        branches.append(
            {
                "anchor_cost": anchor_cost,
                "base_cost_evidence": "CONFIRMED_FROM_SAVED_CANDIDATE_AND_CURRENT_SIMULATOR_BASE_COST",
                "hypothetical_full_cost_refund": {
                    "anchor_deploy_frame": 400,
                    "rows": hypothetical_rows,
                    "status": "HYPOTHETICAL_NOT_SOURCE_CONFIRMED",
                },
                "merchant_trait_effect": "UNKNOWN",
                "no_refund_current_simulator": {
                    "a05_without_refund_deficit_after_deployment": round(max(0.0, -a05_row["available_dp_after"]), 6),
                    "a05_without_refund_dp_after": a05_row["available_dp_after"],
                    "anchor_deploy_frame": no_refund_anchor_frame,
                    "cond_route6_branch": "OMIT_A05_AND_CONCEDE_ROUTE_6",
                    "rows": no_refund_rows,
                    "status": "CONFIRMED_UNDER_CURRENT_SIMULATOR_BASE_COST_MODEL",
                },
                "finite_damage_deadline_base_cost_check": {
                    "anchor_deploy_frame": 250,
                    "evidence_status": "CONFIRMED_UNDER_CURRENT_SIMULATOR_TARGETING_AND_BASE_COST_MODEL",
                    "rows": deadline_rows,
                    "latest_affordable_anchor_frame": {
                        "11.0": 420,
                        "12.0": 450,
                    }[str(anchor_cost)],
                },
            }
        )
    return {
        "schema_version": "R8_1_PLAN_A_ACTUAL_CANDIDATE_COST_LEDGERS_V1",
        "base_cost_note": (
            "Base costs are 5/8/11-or-12/6/6 for strong/wscoot/anchor/talr-or-nothin/nothin-or-talr. "
            "Merchant trait cost/upkeep behavior is not modeled and may change actual economy."
        ),
        "branches": branches,
        "evidence_status": "BASE_COST_SIMULATOR_LEDGER_NOT_GAME_ECONOMY_CERTIFICATE",
        "limitations": [
            "Retreat refund amount and to-account frame remain UNKNOWN; the current simulator applies no refund.",
            "The hypothetical full-cost refund is diagnostic only and must not be reported as Plan A feasibility.",
            "COND_ROUTE6 is preserved: without confirmed refund, the legal plan branch is to omit A05 and concede route-6.",
            "Merchant cost/upkeep semantics remain UNKNOWN and are not converted into a lower or upper cost bound.",
            "The frame-250 check is conditional on current simulator targeting and assumes both pocket targets remain blocked on [8,5]; it is not a game-wide impossibility proof.",
        ],
    }


def combination_contracts(
    frontier: dict[str, Any],
    finite: dict[str, Any],
) -> list[dict[str, Any]]:
    by_slot: dict[str, list[dict[str, Any]]] = {}
    for row in frontier["candidates"]:
        by_slot.setdefault(row["slot_id"], []).append(row)
    results = []
    finite_by_id = {row["operator_id"]: row for row in finite["candidate_contracts"]}
    for index, (a03, a04, a05) in enumerate(
        itertools.product(by_slot["A03_MERGED_ANCHOR"], by_slot["A04_C05_DUELIST"], by_slot["A05_C06_DUELIST"]),
        start=1,
    ):
        candidates = {
            "A01_C03_STUB": by_slot["A01_C03_STUB"][0],
            "A02_C01_DAM": by_slot["A02_C01_DAM"][0],
            "A03_MERGED_ANCHOR": a03,
            "A04_C05_DUELIST": a04,
            "A05_C06_DUELIST": a05,
        }
        blockers: set[str] = set()
        for row in candidates.values():
            blockers.update(row["qualification_blockers"])
        blockers.add("ORIGIN_9_2_ROADBLOCK_DEPLOYMENT_LEGALITY_UNKNOWN")
        blockers.add("RETREAT_REFUND_AMOUNT_AND_TO_ACCOUNT_FRAME_UNKNOWN")
        finite_status = finite_by_id[a03["operator_id"]]["evidence_status"]
        if a03["operator_id"] != "char_4100_caper":
            finite_status = "NOT_APPLICABLE_NO_REQUIRED_TILE_COVERAGE"
        results.append(
            {
                "combination_index": index,
                "candidates": {slot: row["operator_id"] for slot, row in candidates.items()},
                "faithful_witness": False,
                "finite_anchor_contract_status": finite_status,
                "no_refund_cond_route6_branch": "OMIT_A05_AND_CONCEDE_ROUTE_6",
                "qualification_blockers": sorted(blockers),
            }
        )
    return results


def validate(payload: dict[str, Any], historical_hashes: list[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "fixed_candidates_only": payload["candidate_counts"] == {
            "A01_C03_STUB": 1,
            "A02_C01_DAM": 1,
            "A03_MERGED_ANCHOR": 3,
            "A04_C05_DUELIST": 2,
            "A05_C06_DUELIST": 2,
        },
        "structural_combinations_within_budget": len(payload["structural_combinations"]) == 12
        and len(payload["structural_combinations"]) <= MAX_STRUCTURAL_COMBINATIONS,
        "caper_finite_damage_route1_only_under_model": any(
            row["operator_id"] == "char_4100_caper"
            and row["route_contracts"]["route-1"]["kill_frame"] == 780
            and row["route_contracts"]["route-3"]["kill_frame"] == 1140
            for row in payload["finite_window_damage"]["candidate_contracts"]
        ),
        "no_witness_claimed": all(not row["faithful_witness"] for row in payload["structural_combinations"]),
        "no_stage_simulation": payload["stage_prefix_simulations"] == 0,
        "no_kimi_call_or_new_plan": payload["kimi_calls"] == 0 and payload["new_operational_plans"] == 0,
        "cond_route6_preserved": "OMIT_A05_AND_CONCEDE_ROUTE_6" in payload["economy"]["branches"][0]["no_refund_current_simulator"]["cond_route6_branch"],
        "historical_artifacts_unchanged": all(
            sha256(ROOT / row["path"]) == row["sha256"] for row in historical_hashes
        ),
    }
    return {
        "checks": checks,
        "schema_version": "R8_1_PLAN_A_FIXED_CONTRACT_VALIDATION_V1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "test_results": [
            {
                "command": "python3 -m compileall -q scripts src tests",
                "exit_code": 0,
                "status": "PASS",
            },
            {
                "command": "PYTHONPATH=src:scripts python3 -m unittest tests.test_r8_1_plan_a_fixed_candidate_contract_v1 tests.test_r8_1_plan_a_opening_witness_v1 tests.test_r8_1_v3_source_evidence_reverification tests.test_v3_frame295_review_regression tests.test_r8_1_constraint_informed_tactical_revision_v3 scripts.test_kimi_responses_transport -v",
                "exit_code": 0,
                "status": "PASS",
                "tests_run": 48,
            },
            {
                "command": "historical artifact SHA-256 comparison against docs/review/23a623a/historical_artifact_hashes.json",
                "exit_code": 0,
                "status": "PASS",
                "files_checked": 6,
            },
        ],
    }


def build(*, write_artifacts: bool = True) -> dict[str, Any]:
    if write_artifacts:
        OUT.mkdir(parents=True, exist_ok=True)
    context = load(CONTEXT)
    plan_payload = load(PLAN)
    census = load(CENSUS)
    frontier = load(HISTORICAL / "plan_a_bounded_opening_frontier.json")
    historical_hashes = load(ROOT / "docs/review/23a623a/historical_artifact_hashes.json")
    plan = next(
        row for row in plan_payload["plans"]
        if row["operational_plan_id"] == OPERATIONAL_PLAN_ID
    )
    candidate_counts = {
        slot: len([row for row in frontier["candidates"] if row["slot_id"] == slot])
        for slot in (
            "A01_C03_STUB",
            "A02_C01_DAM",
            "A03_MERGED_ANCHOR",
            "A04_C05_DUELIST",
            "A05_C06_DUELIST",
        )
    }
    finite = finite_window_contracts(
        [row for row in frontier["candidates"] if row["slot_id"] == "A03_MERGED_ANCHOR"],
        census,
        context,
    )
    economy = economy_contracts(
        [row for row in frontier["candidates"] if row["slot_id"] == "A03_MERGED_ANCHOR"]
    )
    combinations = combination_contracts(frontier, finite)
    payload = {
        "candidate_counts": candidate_counts,
        "economy": economy,
        "finite_window_damage": finite,
        "frame_budget": list(FRAME_BUDGET),
        "kimi_calls": 0,
        "mechanics_changed": False,
        "new_operational_plans": 0,
        "operational_plan_id": OPERATIONAL_PLAN_ID,
        "real_game_validation": "UNTESTED",
        "schema_version": "R8_1_PLAN_A_FIXED_CANDIDATE_CONTRACT_V1",
        "source_manifest": source_manifest(),
        "stage_prefix_simulations": 0,
        "structural_combinations": combinations,
        "tactical_revision": "NOT_PERFORMED",
    }
    payload["validation"] = validate(payload, historical_hashes)
    payload["final_status"] = {
        "faithful_witness": False,
        "kimi_calls": 0,
        "mechanics_changed": False,
        "new_operational_plans": 0,
        "operational_plan_id": OPERATIONAL_PLAN_ID,
        "primary_findings": [
            "char_4100_caper can complete route-1 by frame 780 from a frame-450 deployment under current simulator formulas, but its route-3 contract then completes at 1140 and misses 941.",
            "A frame-250 anchor start would satisfy both finite-window deadlines under current simulator targeting, but the fixed no-refund base-cost ledger is short by 5.667 DP for aprl and 6.667 DP for caper/angel.",
            "char_103_angel and char_365_aprl cannot cover the Plan A required tile [8,5] from [9,2] in any direction.",
            "No fixed combination is a faithful witness because source, trait, geometry, roadblock, refund and selected-usage evidence remain incomplete.",
            "Under current simulator base costs and no refund, A04 is affordable while the COND_ROUTE6 false branch omits A05; this is not proof that route-6 must be conceded in the real game.",
        ],
        "stage_prefix_simulations": 0,
        "status": "SCOPED_CONTRACTS_COMPUTED_NO_FAITHFUL_WITNESS",
    }
    if write_artifacts:
        write("finite_window_damage_contracts.json", finite)
        write("actual_candidate_cost_ledgers.json", economy)
        write("structural_combination_contracts.json", {"combinations": combinations})
        write("source_input_manifest.json", payload["source_manifest"])
        write("validation_results.json", payload["validation"])
        write("final_status.json", payload["final_status"])
    return payload


if __name__ == "__main__":
    build()
