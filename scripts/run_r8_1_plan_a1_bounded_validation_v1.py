from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from arknights_planner.adapters.approximate_real import (
    ApproximateRealSimulationAdapter,
    RealOperatorConfiguration,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.simulation import RuntimeDevice, SimulationState
from arknights_planner.models.stage import BattleDevice
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import Simulator


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_plan_a1_bounded_validation_v1"
PREREQUISITE_OUT = ROOT / "output/r8_1_plan_a1_execution_prerequisites_v1"
SOURCE = ROOT / "output/r8_1_plan_a_bounded_kimi_revision_v4"
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
CENSUS = ROOT / "output/operator_runtime_fidelity_v1/all_operator_census.json"
CATALOG = ROOT / "output/r8_1_llm_operationalization_v1/deterministic_affordance_catalog.json"
GAMEDATA = ROOT / "data/ArknightsGameData"
PLAN_ID = "R8OP-A1-BLOCK1-COOP-ANCHOR390"
MECHANICS = "m18.9-stage-device-runtime-v1"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_out(directory: Path, name: str, payload: Any) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    """Conditional arithmetic: continuous targets, instant hits, fixed cooldowns.

    Retain every actual attack/SP cycle across the target handoff. This is not
    an execution trace from the stage simulator or proof of blocking legality.
    """
    talr = census_operator(census, "char_4155_talr")
    damage = physical_damage(float(talr["base_atk"]), 150.0)
    events = [
        {"attack_frame": frame, "source": "char_4155_talr", "damage_after_def": round(damage, 6)}
        for frame in range(191, 942, 30)
    ] + [dict(event, source="char_4100_caper") for event in caper_cycle_events(390, count=19)]
    events.sort(key=lambda event: (event["attack_frame"], event["source"]))
    route_index = 0
    remaining = 3300.0
    traces: list[list[dict[str, Any]]] = [[], []]
    for event in events:
        if route_index == 1 and event["attack_frame"] < 431:
            continue
        remaining = max(0.0, remaining - event["damage_after_def"])
        traces[route_index].append(dict(event, remaining_hp=round(remaining, 6)))
        if remaining <= 0:
            route_index += 1
            if route_index == 2:
                break
            remaining = 3300.0
    return {
        "route_1": {"assumption": "ROUTE_1_HELD_ON_TILE_8_5", "events": traces[0], "kill_frame": traces[0][-1]["attack_frame"]},
        "route_3": {"assumption": "ROUTE_1_DEAD_AND_ROUTE_3_REBLOCKED_AT_431; CONTINUOUS_TARGET_HANDOFF", "events": traces[1], "kill_frame": traces[1][-1]["attack_frame"]},
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


def _frame_ledger_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(frame: int, event: str, cost: float, *, forced_available: float | None = None) -> None:
        previous = rows[-1]
        elapsed = frame - previous["frame"]
        before = forced_available if forced_available is not None else previous["available_dp_after"] + elapsed / 30.0
        rows.append({
            "available_dp_after": round(before - cost, 6),
            "available_dp_before": round(before, 6),
            "cost": cost,
            "event": event,
            "frame": frame,
        })

    rows.append({"available_dp_after": 10.0, "available_dp_before": 10.0, "cost": 0.0, "event": "STAGE_INITIAL_DP", "frame": 0})
    add(27, "DEPLOY_CHAR_272_STRONG", 5.0)
    add(117, "MERCHANT_UPKEEP_CHAR_272_STRONG", 3.0)
    add(191, "DEPLOY_CHAR_4155_TALR", 6.0)
    add(207, "MERCHANT_UPKEEP_CHAR_272_STRONG", 0.0, forced_available=2.9)
    rows[-1].update({
        "available_dp_after": 2.9,
        "available_dp_before": 2.9,
        "required_cost": 3.0,
        "shortfall": 0.1,
        "status": "INSUFFICIENT_AUTO_RETREAT_NO_DEBIT",
    })
    add(281, "MERCHANT_UPKEEP_CHAR_4155_TALR", 3.0)
    add(371, "MERCHANT_UPKEEP_CHAR_4155_TALR", 3.0)
    add(390, "PLANNED_STRONG_RETREAT_ALREADY_ABSENT_NO_REFUND", 0.0)
    add(390, "DEPLOY_CHAR_4100_CAPER", 12.0)
    rows[-1].update({
        "roadblock_legality": "REJECTED_ACTIVE_STAGE_DEVICE_OCCUPANCY",
        "status": "INSUFFICIENT_DP_AND_ACTIVE_ROADBLOCK",
    })
    return rows


def _merchant_source_record(repo: GameDataRepository, operator_id: str) -> dict[str, Any]:
    operator = repo.get_operator(operator_id)
    return {
        "maintenance_cost": operator.maintenance_cost,
        "maintenance_interval": operator.maintenance_interval,
        "operator_id": operator_id,
        "source_path": f"$.{operator_id}.description and $.{operator_id}.trait.candidates[0].blackboard",
    }


def execution_prerequisites() -> dict[str, Any]:
    repository = GameDataRepository(GAMEDATA)
    adapter = ApproximateRealSimulationAdapter(repository)
    operators = (
        ("char_272_strong", 45),
        ("char_4155_talr", 50),
        ("char_4100_caper", 45),
        ("char_455_nothin", 50),
    )
    fixture = adapter.build_pool_fixture(
        stage_id_or_code="main_08-01",
        configurations=tuple(RealOperatorConfiguration(operator_id, 0, level) for operator_id, level in operators),
        policy=RealSimulationApproximationPolicy.main_00_01(),
    )
    actions = [
        ("DEPLOY", 27, "char_272_strong", (3, 3), "RIGHT"),
        ("DEPLOY", 191, "char_4155_talr", (8, 5), "LEFT"),
        ("RETREAT", 390, "char_272_strong", None, None),
        ("DEPLOY", 390, "char_4100_caper", (9, 2), "DOWN"),
        ("DEPLOY", 725, "char_455_nothin", (5, 1), "RIGHT"),
    ]
    strategy = Strategy(
        tuple(operator_id for operator_id, _ in operators),
        tuple(
            Action(ActionType(kind), frame / 30.0, operator_id, tile, direction or "RIGHT")
            for kind, frame, operator_id, tile, direction in actions
        ),
    )
    state = SimulationState(0.0, 1000.0, fixture.stage.initial_life)
    state.active_devices = {
        device.device_id: RuntimeDevice(
            device.device_id, device.template_id, device.tile, device.hp, device.hp,
            device.defense, device.magic_resistance, device.taunt_level,
        )
        for device in fixture.stage.devices
    }
    simulator = Simulator()
    legality: list[dict[str, Any]] = []
    for action_index, (kind, frame, operator_id, tile, direction) in enumerate(actions):
        action = strategy.actions[action_index]
        error_count = len(state.deployment_errors)
        if kind == "DEPLOY":
            simulator._deploy(state, fixture.stage, fixture.operators, strategy, action)
            reason = "; ".join(state.deployment_errors[error_count:]) or None
            legality.append({"action_type": kind, "frame": frame, "legal": not reason, "operator_id": operator_id, "reason": reason, "tile": tile})
        else:
            was_deployed = operator_id in state.deployed_operators
            simulator._retreat(state, action)
            reason = "; ".join(state.deployment_errors[error_count:]) or None if was_deployed else None
            legality.append({"action_type": kind, "frame": frame, "legal": reason is None, "operator_id": operator_id, "reason": reason, "tile": tile})
        state.deployment_errors.clear()
    device = next(item for item in fixture.stage.devices if item.device_id == "trap_020_roadblock#2")
    merchants = [_merchant_source_record(repository, operator_id) for operator_id in ("char_272_strong", "char_4155_talr", "char_455_nothin")]
    caper_legality = next(row for row in legality if row["operator_id"] == "char_4100_caper")
    ledger_rows = _frame_ledger_rows()
    return {
        "conditions": {
            "COND_ANCHOR_TILE": {
                "status": "FALSE",
                "basis": "trap_020_roadblock#2 is active at [9,2]; current corrected deployment rule rejects caper before destruction.",
            },
            "COND_UPKEEP": {
                "status": "FALSE",
                "basis": "Confirmed positive upkeep makes the fixed long-held strong/talr prefix unaffordable before caper deployment; auto-retreat changes the planned timeline.",
            },
        },
        "deployment_legality": legality,
        "evidence_status": {
            "active_device_occupancy_rule": "CONFIRMED_FROM_CODE_AND_PRTS_DEVICE_DOCUMENTATION",
            "first_charge_timing": "UNKNOWN; arithmetic uses deploy+interval and infeasibility holds for any positive charge before frame 191",
            "merchant_cost_and_interval": "CONFIRMED_FROM_GAMEDATA_DESCRIPTION_AND_TRAIT_BLACKBOARD",
            "merchant_insufficient_dp_auto_retreat": "CONFIRMED_BY_DESCRIPTION; negative-cost edge behavior remains PARTIAL",
            "stage_simulation": "NOT_RUN",
        },
        "fixed_action_budget": {
            "complete_combinations": 0,
            "new_operational_plans": 0,
            "new_operators": 0,
            "stage_simulations": 0,
        },
        "fixed_timeline_status": "INFEASIBLE_UNDER_CONFIRMED_EXECUTION_PREREQUISITES",
        "mechanics_version": MECHANICS,
        "merchant_upkeep": {
            "cost_per_tick": 3.0,
            "evidence": merchants,
            "frame_390_caper_deficit_auto_retreat_branch": 9.0,
            "interval_seconds": 3.0,
            "negative_debit_sensitivity_before_caper": -6.0,
            "negative_debit_sensitivity_caper_deficit": 18.0,
            "first_charge_timing": "UNKNOWN",
            "implementation_policy_for_arithmetic": "deploy_frame + interval; insufficient DP emits no debit and auto-retreats",
        },
        "operational_plan_id": PLAN_ID,
        "roadblock": {
            "device_id": device.device_id,
            "faction": device.faction,
            "hp": device.hp,
            "template_id": device.template_id,
            "tile": device.tile,
            "deployment_rule": "ACTIVE_STAGE_DEVICE_OCCUPIES_TILE",
            "deployment_position_released_when": "RuntimeDevice is removed from SimulationState.active_devices after hp <= 0",
            "caper_legality": caper_legality,
            "prts_evidence": "https://prts.wiki/w/道路障碍物 and https://prts.wiki/w/障碍物",
        },
        "schema_version": "R8_1_PLAN_A1_EXECUTION_PREREQUISITES_V1",
        "upkeep_ledger": {
            "rows": ledger_rows,
            "earliest_fixed_timeline_divergence": ledger_rows[4],
            "earliest_unaffordable_merchant_tick": ledger_rows[4],
            "schema_version": "R8_1_PLAN_A1_UPKEEP_LEDGER_V1",
        },
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
            "evidence_status": "CONDITIONAL_ARITHMETIC_NOT_STAGE_EXECUTION_CERTIFICATE",
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
            "prefix_simulation_ready": False,
            "unresolved_execution_guards": ["COND_ANCHOR_TILE", "COND_UPKEEP", "COND_COOP_ROUTE3", "COND_MEDIC"],
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
    actions = certificate["action_candidate"]["actions"]
    deployments = [row for row in actions if row["action_type"] == "DEPLOY"]
    plan_deployments = [row for row in plan["deployment_positions_and_directions"] if row["unit"] != "(omitted)"]
    checks = {
        "selected_actions_match_plan_default_units_and_tiles": [
            (row["operator"], row["tile"]) for row in deployments
        ] == [(row["unit"], row["tile"]) for row in plan_deployments],
        "unresolved_guards_block_prefix_simulation": not certificate["witness"]["prefix_simulation_ready"],
        "action_candidate_direction_complete": all(row.get("direction") in {"UP", "DOWN", "LEFT", "RIGHT"} for row in deployments),
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-prerequisites-only", action="store_true")
    args = parser.parse_args()
    if args.execution_prerequisites_only:
        payload = execution_prerequisites()
        write_out(PREREQUISITE_OUT, "execution_prerequisites.json", payload)
        write_out(PREREQUISITE_OUT, "final_status.json", {
            "cond_anchor_tile": payload["conditions"]["COND_ANCHOR_TILE"]["status"],
            "cond_upkeep": payload["conditions"]["COND_UPKEEP"]["status"],
            "fixed_timeline_status": payload["fixed_timeline_status"],
            "kimi_calls": 0,
            "mechanics_version": MECHANICS,
            "mechanics_version_unchanged": True,
            "new_operational_plans": 0,
            "runtime_repairs_applied": ["ACTIVE_STAGE_DEVICE_OCCUPANCY", "MERCHANT_UPKEEP"],
            "stage_simulations": 0,
            "status": "FIXED_CANDIDATE_BLOCKED_BY_UPKEEP_AND_ROADBLOCK",
        })
        inputs = {
            "all_operator_census.json": file_record(CENSUS),
            "character_table.json": file_record(GAMEDATA / "zh_CN/gamedata/excel/character_table.json"),
            "gamedata_source.json": file_record(ROOT / "docs/review/gamedata_source.json"),
            "mechanics.py": file_record(ROOT / "src/arknights_planner/mechanics.py"),
            "level_main_08-01.json": file_record(GAMEDATA / "zh_CN/gamedata/levels/obt/main/level_main_08-01.json"),
            "llm_structured_output.json": file_record(SOURCE / "llm_structured_output.json"),
            "run_r8_1_plan_a1_bounded_validation_v1.py": file_record(Path(__file__)),
            "simulator.py": file_record(ROOT / "src/arknights_planner/simulator/simulator.py"),
        }
        write_out(PREREQUISITE_OUT, "source_input_manifest.json", {
            "external_references": [
                "https://prts.wiki/w/游戏数据基础",
                "https://prts.wiki/w/作战机制",
                "https://prts.wiki/w/部署费用",
                "https://prts.wiki/w/道路障碍物",
                "https://prts.wiki/w/障碍物",
            ],
            "inputs": inputs,
            "mechanics_version": MECHANICS,
            "schema_version": "R8_1_PLAN_A1_EXECUTION_PREREQUISITES_MANIFEST_V1",
        })
        return
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
