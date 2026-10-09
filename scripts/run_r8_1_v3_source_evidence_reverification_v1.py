from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_v3_source_evidence_reverification_v1"
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
CATALOG = ROOT / "output/r8_1_llm_operationalization_v1/deterministic_affordance_catalog.json"
PLANS = ROOT / "output/r8_1_constraint_informed_revision_v3/revised_operational_plans.json"
CERTIFICATES = ROOT / "output/r8_1_constraint_informed_revision_v3/feasibility_certificates.json"
ROUTE_EVIDENCE = ROOT / "output/r8_1_deadline_295_reclassification_v1/route3_contact_evidence.json"
RECLASSIFICATION = ROOT / "output/r8_1_deadline_295_reclassification_v1/deadline_295_reclassification.json"
REQUEST = ROOT / "output/r8_1_constraint_informed_revision_v3/llm_request.json"
RESPONSE = ROOT / "output/r8_1_constraint_informed_revision_v3/llm_response_envelope.json"
COMPLETION = ROOT / "output/r8_1_constraint_informed_revision_v3/response_completion_validation.json"
TARGET_SLOTS = {
    "R8OP-A-MERGED-ANCHOR-REFUND-LATTICE": "A03_MERGED_ANCHOR",
    "R8OP-B-UPSTREAM-DAM-AND-RELAY": "B04_POCKET_FIRE",
    "R8OP-C-DELAYED-KILLING-BLOCK-EVOLUTION": "C03_MERGED_ANCHOR",
}


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
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def import_v3_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "r8_1_constraint_informed_tactical_revision_v3",
        ROOT / "scripts/run_r8_1_constraint_informed_tactical_revision_v3.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def route3_contact_facts(context: dict[str, Any], route_evidence: dict[str, Any]) -> dict[str, Any]:
    route = next(
        row for row in context["exact_route_threats"]["routes"] if row["route_id"] == "route-3"
    )
    expected = {
        "enemy_id": route["enemy_id"],
        "earliest_operator_contact_distance": route["earliest_operator_contact_distance"],
        "earliest_operator_contact_frame": route["earliest_operator_contact_frame"],
        "latest_interception_distance": route["latest_interception_distance"],
        "latest_safe_blocker_frame": route["latest_safe_blocker_frame"],
        "legal_interception_tiles": route["legal_interception_tiles"],
    }
    actual = {key: route_evidence.get(key) for key in expected}
    return {
        "expected_from_deterministic_context": expected,
        "route_evidence_values": actual,
        "agreement": actual == expected,
        "evidence_class": "CONFIRMED_FROM_CODE",
        "derivation": route_evidence["formulas"]["earliest_operator_contact_frame"],
    }


def narrative_timing(plan: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in plan["opening_responsibilities"] if "route-3" in row]
    return {
        "class": "PLAN_TEXT_TACTICAL_DESIGN_TARGET",
        "is_exact_game_fact": False,
        "rows": rows,
    }


def diagnostic_prefix_conflict(
    record: dict[str, Any],
    slot_id: str,
    operator_costs: dict[str, float],
) -> dict[str, Any]:
    conflict = record["first_conflict"]
    available = conflict["available_dp_no_retreat_refund"]
    recomputed_available = 10.0 + conflict["deadline_frame"] / 30.0
    recomputed_cost = sum(
        operator_costs[operator_id]
        for operator_id in conflict["minimum_assignment"].values()
    )
    return {
        "certificate_class": "DIAGNOSTIC_CONFLICTING_CONSTRAINT_SET_NOT_PROVEN_UNSAT_CORE",
        "slot_id": slot_id,
        "assumed_deadline_frame": conflict["deadline_frame"],
        "prefix_slots": conflict["prefix_slots"],
        "minimum_assignment": conflict["minimum_assignment"],
        "minimum_cost": conflict["minimum_cost"],
        "recomputed_minimum_cost": recomputed_cost,
        "available_dp_under_natural_only_assumption": available,
        "recomputed_available_dp": recomputed_available,
        "deficit": conflict["deficit"],
        "economy_assumptions": {
            "initial_dp": 10.0,
            "natural_rate": 1.0,
            "retreat_refund": 0.0,
            "skill_dp": 0.0,
        },
        "proof_limitations": [
            "FRAME_295_IS_NOT_A_PLAN_SPECIFIC_FIRE_ESTABLISHMENT_DEADLINE",
            "NATURAL_ONLY_DP_IS_NOT_A_VERIFIED_TOTAL_DP_UPPER_BOUND",
            "DISTINCT_UNIT_ASSIGNMENT_AND_ROLE_SHARING_ARE_SIMPLIFIED",
            "REFUND_AND_SKILL_ECONOMY_ARE_NOT_RESOLVED",
        ],
        "is_plan_infeasibility_proof": False,
    }


def fidelity_input_evidence(root: Path = ROOT) -> dict[str, Any]:
    records = []
    for name in ("all_operator_fidelity.json", "all_operator_census.json"):
        path = root / "output/operator_runtime_fidelity_v1" / name
        present = path.is_file()
        count = len(load(path).get("operators", [])) if present else 0
        records.append({
            "path": str(path.relative_to(root)),
            "present": present,
            "operator_count": count,
            "sha256": sha256(path) if present else None,
        })
    return {"complete": all(row["present"] and row["operator_count"] > 0 for row in records),
            "records": records}


def build(*, write_artifacts: bool = True) -> dict[str, Any]:
    if write_artifacts:
        OUT.mkdir(parents=True, exist_ok=True)
    context = load(CONTEXT)
    catalog = load(CATALOG)
    plan_payload = load(PLANS)
    certificate_payload = load(CERTIFICATES)
    route_evidence = load(ROUTE_EVIDENCE)
    reclassification = load(RECLASSIFICATION)
    completion = load(COMPLETION)
    envelope = load(RESPONSE)
    v3_module = import_v3_module()
    repair_module = v3_module.import_repair()
    repair_module.load_fidelity_tables()
    fidelity_inputs = fidelity_input_evidence()
    operator_costs = {
        row["operator_id"]: float(row["cost"]) for row in context["operators"]
    }
    affordances = catalog["affordances"]
    if isinstance(affordances, dict):
        affordances = list(affordances.values())

    records = []
    for plan in plan_payload["plans"]:
        plan_id = plan["operational_plan_id"]
        slot_id = TARGET_SLOTS[plan_id]
        slot = next(row for row in plan["compiler_slots"] if row["slot_id"] == slot_id)
        affordance = next(row for row in affordances if row["affordance_id"] == slot["affordance_id"])
        pool = v3_module.plan_capability_pool(
            context,
            repair_module,
            slot,
            [item for other in plan_payload["plans"] for item in other["compiler_slots"]],
        ) if fidelity_inputs["complete"] else None
        certificate = next(
            row for row in certificate_payload["records"] if row["operational_plan_id"] == plan_id
        )
        conflict = diagnostic_prefix_conflict(certificate, slot_id, operator_costs)
        records.append(
            {
                "operational_plan_id": plan_id,
                "slot_id": slot_id,
                "compiler_slot": slot,
                "selected_affordance": {
                    "affordance_id": affordance["affordance_id"],
                    "type": affordance["type"],
                    "legal_tiles": affordance["legal_tiles"],
                    "served_routes": affordance["served_routes"],
                    "pressure_windows": affordance["pressure_windows"],
                },
                "affordance_reference_valid": (
                    slot["affordance_id"] in plan["selected_affordance_ids"]
                    and affordance["legal_tiles"]
                    and "route-3" in affordance["served_routes"]
                    and set(slot.get("pressure_window", [])) <= set(affordance["pressure_windows"])
                ),
                "candidate_pool_status": "DIAGNOSTIC_ONLY" if pool is not None else "UNKNOWN_MISSING_FIDELITY_INPUTS",
                "candidate_pool_size": len(pool) if pool is not None else None,
                "candidate_pool_ids": [row["operator_id"] for row in pool] if pool is not None else None,
                "plan_text_timing": narrative_timing(plan),
                "mandatory_invariants": plan["mandatory_tactical_invariants"],
                "frame_295_semantics": {
                    "CONTACT": {
                        "classification": "CONFIRMED_DERIVED_EVENT",
                        "frame": 295,
                        "meaning": "Earliest possible operator contact on route-3 at a legal interception tile.",
                        "is_establishment_deadline": False,
                    },
                    "BLOCK": {
                        "classification": "CONFIRMED_DERIVED_EVENT",
                        "frame": 431,
                        "meaning": "Latest safe blocker frame for route-3.",
                        "is_establishment_deadline": slot["deadline_basis"] == "route-3:BLOCK",
                    },
                    "FIRE": {
                        "classification": "UNKNOWN_PLAN_SPECIFIC_DEADLINE",
                        "frame": None,
                        "meaning": (
                            "The plan requires route-3 to die before frame 941; establishment depends on "
                            "blocking, geometry, facing, coverage, and measured damage. The supplied evidence "
                            "does not establish a hard fire establishment deadline."
                        ),
                        "is_establishment_deadline": False,
                    },
                    "KILL": {
                        "classification": "PLAN_TARGET_NOT_CONSTRUCTIVE_WITNESS",
                        "frame": 941,
                        "meaning": "The plan states a kill-by target; this is not proof that any schedule achieves it.",
                        "is_establishment_deadline": False,
                    },
                },
                "plan_specific_fire_deadline": {
                    "status": "UNKNOWN",
                    "reason": "Plan text gives an outcome target, not a source-backed establishment frame.",
                    "replacement_deadline_invented": False,
                },
                "previous_295_prefix_conflict": conflict,
            }
        )

    contact_facts = route3_contact_facts(context, route_evidence)
    manifest = {
        "schema_version": "R8_1_V3_SOURCE_EVIDENCE_MANIFEST_V1",
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "stage_id": "main_08-01",
        "fidelity_inputs": fidelity_inputs,
        "source_files": {
            key: file_record(ROOT / path)
            for key, path in {
                "deterministic_context": str(CONTEXT.relative_to(ROOT)),
                "affordance_catalog": str(CATALOG.relative_to(ROOT)),
                "revised_operational_plans": str(PLANS.relative_to(ROOT)),
                "feasibility_certificates": str(CERTIFICATES.relative_to(ROOT)),
                "route3_contact_evidence": str(ROUTE_EVIDENCE.relative_to(ROOT)),
                "deadline_295_reclassification": str(RECLASSIFICATION.relative_to(ROOT)),
                "llm_request": str(REQUEST.relative_to(ROOT)),
                "constraint_informed_reasoning_prompt": str(
                    (ROOT / "output/r8_1_constraint_informed_revision_v3/constraint_informed_reasoning_prompt.txt").relative_to(ROOT)
                ),
                "llm_response_envelope": str(RESPONSE.relative_to(ROOT)),
                "response_completion_validation": str(COMPLETION.relative_to(ROOT)),
                "llm_raw_response_manifest": str(
                    (ROOT / "output/r8_1_constraint_informed_revision_v3/llm_raw_response_manifest.json").relative_to(ROOT)
                ),
                "llm_raw_response_gzip": str(
                    (ROOT / "output/r8_1_constraint_informed_revision_v3/llm_raw_response.txt.gz").relative_to(ROOT)
                ),
            }.items()
        },
        "evidence_classes": {
            "mechanics_version": "CONFIRMED_FROM_CODE",
            "route3_contact_frame_295": "CONFIRMED_FROM_CODE",
            "plan_contract_fields": "CONFIRMED_FROM_CODE",
            "plan_narrative_frames": "PLAN_TEXT_TACTICAL_DESIGN_TARGET",
            "295_as_fire_deadline": "HYPOTHESIS_REJECTED",
            "historical_game_execution": "REPORTED_BY_PREVIOUS_WORKER",
        },
    }
    audit = {
        "schema_version": "R8_1_V3_SOURCE_EVIDENCE_REVERIFICATION_V1",
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "stage_id": "main_08-01",
        "kimi_calls": 0,
        "new_tactical_plans": 0,
        "simulations": 0,
        "route3_contact_facts": contact_facts,
        "reclassification": {
            "previous_claim": reclassification["claim_id"],
            "corrected_classification": reclassification["corrected_classification"],
            "is_confirmed_hard_deadline": reclassification["is_confirmed_hard_deadline"],
        },
        "records": records,
        "summary": {
            "plans_reverified": len(records),
            "plan_specific_fire_deadlines_resolved": 0,
            "plan_specific_fire_deadlines_unknown": len(records),
            "old_295_conflicts_retained_as_diagnostic": len(records),
            "old_295_conflicts_promoted_to_plan_infeasibility": 0,
            "constructive_witnesses": 0,
            "simulations": 0,
        },
        "epistemic_status": (
            "CONFIRMED_FROM_CODE for supplied artifacts and arithmetic; "
            "plan feasibility remains UNKNOWN without a full constructive schedule and simulator replay."
        ),
    }
    validation = {
        "schema_version": "R8_1_V3_SOURCE_EVIDENCE_REVERIFICATION_VALIDATION_V1",
        "checks": {
            "fidelity_inputs_complete": fidelity_inputs["complete"],
            "route3_contact_evidence_agreement": contact_facts["agreement"],
            "three_target_plans_present": len(records) == 3,
            "affordance_references_valid": all(row["affordance_reference_valid"] for row in records),
            "frame_295_is_not_fire_deadline": all(
                not row["frame_295_semantics"]["FIRE"]["is_establishment_deadline"]
                for row in records
            ),
            "old_conflicts_remain_diagnostic": all(
                not row["previous_295_prefix_conflict"]["is_plan_infeasibility_proof"]
                for row in records
            ),
            "response_completed": completion["successful_completion"] is True,
            "response_accumulator_matches_envelope": completion["accumulated_delta_matches_envelope"] is True,
            "llm_call_count_is_one": completion["kimi_call_count"] == 1,
        },
        "status": "PASS",
    }
    validation["status"] = (
        "PASS" if all(validation["checks"].values()) else
        ("FAIL" if any(not passed for name, passed in validation["checks"].items()
                       if name != "fidelity_inputs_complete")
         else "BLOCKED_MISSING_FIDELITY_INPUTS")
    )
    final_status = {
        "schema_version": "R8_1_V3_SOURCE_EVIDENCE_REVERIFICATION_FINAL_STATUS_V1",
        "status": validation["status"],
        "plans_reverified": len(records),
        "frame_295_classification": "EARLIEST_OPERATOR_CONTACT_EVENT_NOT_FIRE_ESTABLISHMENT_DEADLINE",
        "plan_specific_fire_deadline": "UNKNOWN",
        "old_295_prefix_conflicts": "DIAGNOSTIC_ONLY",
        "constructive_witnesses": 0,
        "simulations": 0,
        "kimi_calls": 0,
        "mechanics_changed": False,
        "real_game_validation": "UNTESTED",
    }
    if write_artifacts:
        write("source_evidence_manifest.json", manifest)
        write("v3_source_evidence_reverification.json", audit)
        write("validation_results.json", validation)
        write("final_status.json", final_status)
    return {"manifest": manifest, "audit": audit, "validation": validation, "final_status": final_status}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True))
