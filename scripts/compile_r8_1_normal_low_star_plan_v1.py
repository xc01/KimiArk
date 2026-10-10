from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.adapters.approximate_real import RealOperatorConfiguration
from arknights_planner.adapters.normal_low_star import is_normal_mode_low_star
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.simulation import EventType, RuntimeDevice, SimulationState
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import Simulator


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_normal_low_star_tactical_revision_v1"
GAMEDATA = ROOT / "data/ArknightsGameData"
FRAMES_PER_SECOND = 30
ACTION_FRAMES = (
    (0, "char_123_fang", (4, 3), "LEFT"),
    (90, "char_4093_frston", (8, 5), "DOWN"),
    (180, "char_4227_gallus", (9, 5), "LEFT"),
    (510, "char_124_kroos", (7, 5), "RIGHT"),
    (570, "char_285_medic2", (6, 5), "RIGHT"),
    (630, "char_502_nblade", (5, 1), "RIGHT"),
)
COST = {
    "char_123_fang": 10.0,
    "char_4093_frston": 3.0,
    "char_4227_gallus": 3.0,
    "char_124_kroos": 11.0,
    "char_285_medic2": 3.0,
    "char_502_nblade": 7.0,
}
CONFIGURATIONS = {
    "char_123_fang": (1, 55, 6),
    "char_4093_frston": (0, 30, None),
    "char_4227_gallus": (0, 30, None),
    "char_124_kroos": (1, 55, 6),
    "char_285_medic2": (0, 30, None),
    "char_502_nblade": (0, 30, None),
}
plan_hint: dict[str, Any] = {}
DEPLOYED_OPERATORS = tuple(item[1] for item in ACTION_FRAMES)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_number(value: Any) -> float:
    return float(value.value) if hasattr(value, "value") else float(value)


def write(name: str, payload: dict[str, Any]) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_manifest() -> dict[str, Any]:
    paths = [
        ROOT / "scripts/run_r8_1_normal_low_star_kimi_revision_v1.py",
        ROOT / "scripts/build_normal_low_star_facts.py",
        ROOT / "scripts/kimi_responses_transport.py",
        OUT / "llm_structured_output.json",
        OUT / "llm_raw_response.txt",
        OUT / "llm_evidence_context.json",
        ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json",
        ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json",
        ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json",
        Path(__file__),
    ]
    return {
        "inputs": {str(path.relative_to(ROOT)): {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in paths},
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "schema_version": "R8_1_NORMAL_LOW_STAR_BOUNDED_COMPILE_MANIFEST_V1",
    }


def dp_ledger() -> dict[str, Any]:
    rows: list[dict[str, Any]] = [{
        "available_after": 10.0, "available_before": 10.0, "amount": 10.0,
        "event": "STAGE_INITIAL_DP", "frame": 0,
        "source": "deterministic_context.stage_facts.initial_cost",
    }]
    dp = 10.0
    previous_frame = 0
    def advance(frame: int) -> None:
        nonlocal dp
        nonlocal previous_frame
        previous = dp
        dp = min(999.0, dp + (frame - previous_frame) / FRAMES_PER_SECOND)
        rows.append({"available_after": dp, "available_before": previous, "amount": dp - previous,
                     "event": "NATURAL_DP", "frame": frame,
                     "source": "stage costIncreaseTime=1 second; explicit 30 FPS action clock"})
        previous_frame = frame
    for frame, operator_id, _, _ in ACTION_FRAMES:
        advance(frame)
        if operator_id == "char_285_medic2":
            rows.append({"available_after": dp, "available_before": dp, "amount": 6.0,
                         "event": "AUTO_SKILL_DP", "frame": frame, "operator_id": "char_123_fang",
                         "source": "skcom_charge_cost[1] blackboard cost=6; initial_sp=6; sp_cost=25; ready at frame 570"})
            dp += 6.0
            rows[-1]["available_after"] = dp
        cost = COST[operator_id]
        available = dp
        legal = available + 1e-9 >= cost
        dp = dp - cost if legal else dp
        rows.append({"available_after": dp, "available_before": available, "cost": cost,
                     "event": "DEPLOY_COST", "frame": frame, "operator_id": operator_id,
                     "status": "PAID" if legal else "INSUFFICIENT_DP"})
    return {
        "frame_clock": {"frames_per_second": FRAMES_PER_SECOND, "status": "PROJECT_MAPPED_ACTION_CLOCK"},
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "no_refunds_counted": True,
        "no_upkeep_counted": True,
        "rows": rows,
        "schema_version": "R8_1_NORMAL_LOW_STAR_PLAN_B2_DP_LEDGER_V1",
    }


def deployment_legality(ledger: dict[str, Any]) -> dict[str, Any]:
    repository = GameDataRepository(GAMEDATA)
    adapter = ApproximateRealSimulationAdapter(repository)
    configurations = tuple(
        RealOperatorConfiguration(operator_id, *config)
        for operator_id, config in CONFIGURATIONS.items()
    )
    fixture = adapter.build_pool_fixture(
        stage_id_or_code="main_08-01",
        configurations=configurations,
        policy=RealSimulationApproximationPolicy.main_00_01(),
    )
    strategy = Strategy(
        DEPLOYED_OPERATORS,
        tuple(
            Action(ActionType.DEPLOY, frame / FRAMES_PER_SECOND, operator_id, tile, direction)
            for frame, operator_id, tile, direction in ACTION_FRAMES
        ),
    )
    state = SimulationState(0.0, source_number(fixture.stage.initial_dp), source_number(fixture.stage.initial_life))
    state.active_devices = {
        device.device_id: RuntimeDevice(device.device_id, device.template_id, device.tile, device.hp, device.hp,
                                        device.defense, device.magic_resistance, device.taunt_level)
        for device in fixture.stage.devices
    }
    rows = []
    simulator = Simulator()
    for index, (frame, operator_id, tile, direction) in enumerate(ACTION_FRAMES):
        row = next(item for item in ledger["rows"] if item["frame"] == frame and item["event"] == "DEPLOY_COST")
        state.dp = row["available_before"]
        errors_before = len(state.deployment_errors)
        simulator._deploy(state, fixture.stage, fixture.operators, strategy, strategy.actions[index])
        reason = "; ".join(state.deployment_errors[errors_before:]) or None
        rows.append({
            "direction": direction, "frame": frame, "legal": reason is None and row["status"] == "PAID",
            "operator_id": operator_id, "reason": reason, "tile": list(tile),
        })
        state.deployment_errors.clear()
    return {
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "method": "Existing Simulator._deploy checked action-by-action; no Simulator.run() and no stage simulation was executed.",
        "rows": rows,
        "schema_version": "R8_1_NORMAL_LOW_STAR_PLAN_B2_DEPLOYMENT_LEGALITY_V1",
    }


def operator_checks() -> dict[str, Any]:
    repository = GameDataRepository(GAMEDATA)
    facts = load(ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json")
    by_id = {item["operator_id"]: item for item in facts["operators"]}
    support = load(ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json")
    support_by_id = {item["operator_id"]: item for item in support["operators"]}
    rows = []
    for frame, operator_id, _, _ in ACTION_FRAMES:
        fact = by_id.get(operator_id)
        support_fact = support_by_id.get(operator_id)
        rows.append({
            "normal_mode_low_star": bool(fact and is_normal_mode_low_star(repository, operator_id)),
            "overall_runtime_support": support_fact["overall"] if support_fact else "MISSING",
            "operator_id": operator_id,
            "rarity": fact["identity"]["rarity"] if fact else None,
            "runtime_gaps_excluded_from_load_bearing": [
                item["status"] for item in (support_fact or {}).get("talent", {}).get("active_talents", [])
                if item["status"].startswith("UNSUPPORTED")
            ],
        })
    return {"rows": rows, "schema_version": "R8_1_NORMAL_LOW_STAR_PLAN_B2_OPERATOR_CHECKS_V1"}


def semantic_certificate(ledger: dict[str, Any], legality: dict[str, Any]) -> dict[str, Any]:
    devices = load(ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json")["stage_devices"]
    blocked_tiles = {tuple(item["tile"]) for item in devices if item["template_id"] == "trap_020_roadblock"}
    deployment_tiles = {tile for _, _, tile, _ in ACTION_FRAMES}
    routes = load(ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json")["exact_route_threats"]["routes"]
    route_by_id = {item["route_id"]: item for item in routes}
    checks = {
        "ACTION_TIMELINE_DIRECTION_COMPLETE": all(item[3] in {"UP", "DOWN", "LEFT", "RIGHT"} for item in ACTION_FRAMES),
        "NO_DEPLOYMENT_ON_ACTIVE_ROADBLOCK": not deployment_tiles.intersection(blocked_tiles),
        "NO_MERCHANT_OR_UPKEEP": not any(operator_id.startswith(("char_272_", "char_4155_", "char_455_")) for _, operator_id, _, _ in ACTION_FRAMES),
        "NO_REFUND_COUNTED": ledger["no_refunds_counted"],
        "ROUTE_2_BLOCK_ESTABLISHED_BY_27": ACTION_FRAMES[0][0] <= route_by_id["route-2"]["latest_safe_blocker_frame"] and list(ACTION_FRAMES[0][2]) in route_by_id["route-2"]["legal_interception_tiles"],
        "ANCHOR_TILE_LEGAL": tuple(ACTION_FRAMES[1][2]) == (8, 5) and (8, 5) not in blocked_tiles,
        "ANCHOR_BLOCK_ESTABLISHED_BY_191": ACTION_FRAMES[1][0] <= route_by_id["route-1"]["latest_safe_blocker_frame"],
        "ROUTE_7_DELAY_ESTABLISHED_BY_725": ACTION_FRAMES[-1][0] <= route_by_id["route-7"]["latest_safe_blocker_frame"] and list(ACTION_FRAMES[-1][2]) in route_by_id["route-7"]["legal_interception_tiles"],
        "DEPLOYMENT_LIMIT": len(ACTION_FRAMES) <= 8,
    }
    all_legal = all(item["legal"] for item in legality["rows"])
    final_dp = ledger["rows"][-1]["available_after"]
    plan_claimed_banked = "~17 banked" in str(plan_hint["formation_structure"].get("economy_shape", ""))
    checks["DEPLOYMENT_DP_LEDGER_ALL_PAID"] = all(item["status"] == "PAID" for item in ledger["rows"] if item["event"] == "DEPLOY_COST")
    checks["PLAN_NARRATIVE_BANKED_DP_CONSISTENT"] = not plan_claimed_banked or final_dp == 17.0
    structural_pass = all(checks.values()) and all_legal
    return {
        "check_status": checks,
        "classification": "SEMANTIC_COMPILE_CANDIDATE_WITH_NARRATIVE_DISCREPANCY" if not checks["PLAN_NARRATIVE_BANKED_DP_CONSISTENT"] else "SEMANTIC_COMPILE_CANDIDATE" if structural_pass else "COMPILE_CONFLICT",
        "faithful_executable_timeline": False,
        "ledger_final_dp": final_dp,
        "operationally_verified": False,
        "narrative_discrepancy": None if checks["PLAN_NARRATIVE_BANKED_DP_CONSISTENT"] else {
            "plan_claim": plan_hint["formation_structure"].get("economy_shape"),
            "computed_final_dp": final_dp,
            "scope": "The structural actions and deadlines are preserved, but Kimi's banked-DP narrative is not accepted as factual.",
        },
        "reason_operationally_unverified": "Finite-window route-1/route-3 kill timing, route-4 handoff, and leak/life accounting were not simulated and remain UNKNOWN.",
        "route_deadlines": {item["route_id"]: item["latest_safe_blocker_frame"] for item in routes if item["route_id"] in {"route-1", "route-2", "route-3", "route-4", "route-6", "route-7", "route-8"}},
        "schema_version": "R8_1_NORMAL_LOW_STAR_PLAN_B2_SEMANTIC_CERTIFICATE_V1",
        "stage_simulation": "NOT_RUN",
    }


def candidate_slots() -> dict[str, Any]:
    return {
        "candidate_slots": [
            {"candidates": ["char_123_fang", "char_502_nblade", "char_4093_frston"], "selected": "char_123_fang", "slot_id": "OPEN-1"},
            {"candidates": ["char_124_kroos", "char_211_adnach"], "selected": "char_124_kroos", "slot_id": "ANCHOR_HIGH_GROUND_PHYSICAL"},
            {"candidates": ["char_285_medic2"], "selected": "char_285_medic2", "slot_id": "SUPPORT-1"},
            {"candidates": ["char_502_nblade", "NO_DEPLOYMENT"], "selected": "char_502_nblade", "slot_id": "DOG-DELAY"},
        ],
        "complete_combinations_evaluated": 1,
        "direction_complete_candidates": 1,
        "maximum_allowed_candidates_per_slot": 3,
        "maximum_allowed_complete_combinations": 16,
        "schema_version": "R8_1_NORMAL_LOW_STAR_PLAN_B2_BUDGET_USAGE_V1",
    }


def counterexample_avoidance(plan: dict[str, Any], checks: dict[str, Any], operator_checks: dict[str, Any]) -> dict[str, Any]:
    deployment_ids = set(DEPLOYED_OPERATORS)
    return {
        "changed_assumption_count": len(plan.get("changed_conflicting_assumptions", [])),
        "merchant_upkeep_avoided": not any(operator_id.startswith(("char_272_", "char_4155_", "char_455_")) for operator_id in deployment_ids),
        "roadblock_counterexample_avoided": checks["NO_DEPLOYMENT_ON_ACTIVE_ROADBLOCK"],
        "unsupported_mechanics_are_not_load_bearing": all(
            item["overall_runtime_support"] != "MISSING"
            for item in operator_checks["rows"]
        ) and "No unsupported mechanic" in json.dumps(plan.get("mandatory_tactical_invariants", []), ensure_ascii=False),
        "schema_version": "R8_1_NORMAL_LOW_STAR_PLAN_B2_COUNTEREXAMPLE_AVOIDANCE_V1",
        "status": "PRESERVED_AT_COMPILE_LAYER",
    }


def learning_progress(plan: dict[str, Any], certificate: dict[str, Any]) -> dict[str, Any]:
    return {
        "assessment": "DEMONSTRATED_AT_PLAN_AND_COMPILE_LAYER_ONLY",
        "old_conflict_repeated": False,
        "old_conflicts_addressed": [
            "active roadblock at [9,2]",
            "merchant upkeep dependence",
            "4-star/5-star candidates outside the current debug domain",
        ],
        "new_unknown": [
            "finite-window kill timing",
            "route-4 handoff",
            "leak/life accounting",
        ],
        "operationally_verified": certificate["operationally_verified"],
        "schema_version": "R8_1_NORMAL_LOW_STAR_PLAN_B2_LEARNING_PROGRESS_V1",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    global plan_hint
    plan_hint = load(OUT / "llm_structured_output.json")["revised_operational_plans"][0]
    plan = plan_hint
    ledger = dp_ledger()
    legality = deployment_legality(ledger)
    checks = operator_checks()
    certificate = semantic_certificate(ledger, legality)
    counterexample = counterexample_avoidance(plan, certificate["check_status"], checks)
    learning = learning_progress(plan, certificate)
    budget = candidate_slots()
    expected = [(item["operator_id"], tuple(item["tile"]), item["frame"], item["facing"]) for item in plan["deployment_positions_and_directions"]]
    actual = [(operator_id, tile, frame, direction) for frame, operator_id, tile, direction in ACTION_FRAMES]
    action_candidate = {
        "actions": [
            {"action_type": "DEPLOY", "direction": direction, "frame": frame, "operator_id": operator_id, "tile": list(tile)}
            for frame, operator_id, tile, direction in ACTION_FRAMES
        ],
        "classification": certificate["classification"],
        "deployment_semantics_preserved": expected == actual,
        "no_stage_simulation": True,
        "operational_plan_id": plan["operational_plan_id"],
        "schema_version": "R8_1_NORMAL_LOW_STAR_PLAN_B2_DIRECTION_COMPLETE_ACTION_CANDIDATE_V1",
    }
    output = {
        "action_candidate": action_candidate,
        "budget_usage": budget,
        "deployment_legality": legality,
        "dp_ledger": ledger,
        "operator_checks": checks,
        "semantic_certificate": certificate,
        "source_manifest": source_manifest(),
    }
    write("bounded_compile_results.json", output)
    write("dp_ledger.json", ledger)
    write("deployment_legality.json", legality)
    write("operator_checks.json", checks)
    write("semantic_fidelity_certificate.json", certificate)
    write("direction_complete_action_candidate.json", action_candidate)
    write("budget_usage.json", budget)
    write("counterexample_avoidance_validation.json", counterexample)
    write("learning_progress_assessment.json", learning)
    write("compilation_final_status.json", {
        "complete_combinations": budget["complete_combinations_evaluated"],
        "direction_complete_candidates": budget["direction_complete_candidates"],
        "kimi_calls": 1,
        "new_operational_plans": 1,
        "operationally_verified": certificate["operationally_verified"],
        "plan_id": plan["operational_plan_id"],
        "stage_simulations": 0,
        "status": certificate["classification"],
    })


if __name__ == "__main__":
    main()
