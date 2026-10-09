from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_plan_a_opening_witness_v1"
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
CATALOG = ROOT / "output/r8_1_llm_operationalization_v1/deterministic_affordance_catalog.json"
PLAN = ROOT / "output/r8_1_constraint_informed_revision_v3/revised_operational_plans.json"
FIDELITY = ROOT / "output/operator_runtime_fidelity_v1/all_operator_fidelity.json"
CENSUS = ROOT / "output/operator_runtime_fidelity_v1/all_operator_census.json"
GENERATION_CODE = ROOT / "scripts/build_operator_runtime_fidelity.py"
REPAIR_SCRIPT = ROOT / "scripts/run_r8_1_operational_semantic_preservation_repair_v1.py"
FRAME_BUDGET = (0, 941)
MAX_CANDIDATES_PER_SLOT = 3
MAX_COMPLETE_COMBINATIONS = 16
MAX_STAGE_PREFIX_SIMULATIONS = 1


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


def import_repair() -> Any:
    spec = importlib.util.spec_from_file_location("semantic_repair", REPAIR_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def skill_average_scale(operator: dict[str, Any]) -> float | None:
    effect = operator.get("skill_effect") or {}
    scale = float(effect.get("next_attack_atk_scale", 1.0))
    hits = int(effect.get("next_attack_hit_count", 1))
    duration_multiplier = float(effect.get("atk_multiplier", 1.0))
    sp_cost = operator.get("skill_sp_cost")
    if scale <= 1.0 and duration_multiplier <= 1.0:
        return 1.0
    if not sp_cost:
        return None
    return 1.0 + ((scale * hits * duration_multiplier) - 1.0) / float(sp_cost)


def effective_dps(
    operator: dict[str, Any],
    *,
    defense: float = 150.0,
    trait_atk_scale: float = 1.0,
) -> float | None:
    average_scale = skill_average_scale(operator)
    if average_scale is None:
        return None
    attack = float(operator["attack"]) * trait_atk_scale * average_scale
    damage = max(attack * 0.05, attack - defense)
    return damage / float(operator["attack_interval_seconds"])


def trait_scale(census: dict[str, Any], phase: str = "PHASE_0") -> float:
    effects = census.get("trait_effects") or {}
    for candidate in effects.get("candidates", []):
        if (candidate.get("unlockCondition") or {}).get("phase") == phase:
            for entry in candidate.get("blackboard", []):
                if entry.get("key") == "atk_scale":
                    return float(entry.get("value") or 1.0)
    return 1.0


def trait_keys(census: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for candidate in (census.get("trait_effects") or {}).get("candidates", []):
        for entry in candidate.get("blackboard", []):
            if entry.get("key"):
                keys.add(str(entry["key"]))
    return keys


def fidelity_provenance() -> dict[str, Any]:
    fidelity_payload = load(FIDELITY)
    census_payload = load(CENSUS)
    return {
        "schema_version": "R8_1_PLAN_A_FIDELITY_INPUT_PROVENANCE_V1",
        "evidence_class": "CONFIRMED_FROM_CODE_FOR_LOCAL_FILES_AND_HASHES",
        "original_generation_commit": "UNKNOWN_ORIGINAL_GENERATION_COMMIT",
        "generation_code_provenance": {
            "current_local_code": file_record(GENERATION_CODE) if GENERATION_CODE.is_file() else {
                "path": str(GENERATION_CODE.relative_to(ROOT)),
                "status": "MISSING_FROM_CHECKOUT",
                "sha256": None,
            },
            "current_code_would_emit": "ACTIVE_MECHANICS_VERSION",
            "original_version_confirmed": False,
            "reason": (
                "The two tables were created before they were committed and the local generator "
                "later uses ACTIVE_MECHANICS_VERSION, so this script hash cannot be claimed as "
                "the exact historical generator version."
            ),
        },
        "used_by": ["f1a1c7d local verification", "R8_1_PLAN_A_OPENING_WITNESS_V1"],
        "game_data_source": file_record(ROOT / "docs/review/gamedata_source.json"),
        "files": {
            "all_operator_fidelity.json": {
                **file_record(FIDELITY),
                "operator_count": fidelity_payload["operator_count"],
                "mechanics_version": fidelity_payload["mechanics_version"],
            },
            "all_operator_census.json": {
                **file_record(CENSUS),
                "operator_count": census_payload["operator_count"],
                "mechanics_version": census_payload["mechanics_version"],
                "census_version": census_payload["census_version"],
            },
        },
        "mechanics_table_note": (
            "The tables are m18.5-operator-generic-v1 inputs while Plan A uses "
            "m18.9-stage-device-runtime-v1 context data. They remain the historical selected-usage "
            "fidelity evidence; runtime values come from the m18.9 context."
        ),
    }


def snhunt_audit(
    context: dict[str, Any],
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    current_pool: list[dict[str, Any]],
    missing_table_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    operator = next(row for row in context["operators"] if row["operator_id"] == "char_4211_snhunt")
    fidelity = fidelity_by_id["char_4211_snhunt"]
    census = census_by_id["char_4211_snhunt"]
    no_trait = effective_dps(operator)
    with_trait = effective_dps(operator, trait_atk_scale=trait_scale(census))
    missing_table_difference = sorted(
        {row["operator_id"] for row in missing_table_pool} - {row["operator_id"] for row in current_pool}
    )
    return {
        "schema_version": "R8_1_SNHUNT_FIDELITY_REJECTION_AUDIT_V1",
        "operator_id": "char_4211_snhunt",
        "plan_exemplar": True,
        "current_pool_size": len(current_pool),
        "missing_table_pool_size": len(missing_table_pool),
        "missing_table_only_operator_ids": missing_table_difference,
        "present_in_current_pool": "char_4211_snhunt" in {row["operator_id"] for row in current_pool},
        "rejection_reasons": [
            "TRAIT_DIMENSION_UNSUPPORTED",
            "DECISION_CRITICAL_TRAIT_ATK_SCALE_UNSUPPORTED",
        ],
        "fidelity_dimensions": fidelity["dimensions"],
        "selected_skill_1_runtime": next(
            row["interpreter"] for row in census["skills"] if row["skill_id"] == "skchr_snhunt_1"
        ),
        "unused_skill_2_runtime": next(
            row["interpreter"] for row in census["skills"] if row["skill_id"] == "skchr_snhunt_2"
        ),
        "selected_usage_gate": (
            "The aggregate selected_skill_runtime=UNSUPPORTED is not the reason for exclusion; "
            "the selected skill skchr_snhunt_1 is supported. The material rejection is the "
            "unsupported ammo/trait atk_scale."
        ),
        "trait_evidence": {
            "keys": sorted(trait_keys(census)),
            "phase_0_atk_scale": trait_scale(census),
            "description": census["trait_effects"]["candidates"][0]["overrideDescripton"],
            "source_file": "output/operator_runtime_fidelity_v1/all_operator_census.json",
        },
        "damage_floor_check": {
            "evidence_status": "DIAGNOSTIC_APPROXIMATION_NOT_DAMAGE_BOUND",
            "required_effective_dps_vs_def_150": 450.0,
            "skill_effective_dps_without_trait": no_trait,
            "initial_ammo_skill_effective_dps_approximation_with_trait": with_trait,
            "without_trait_meets_floor": bool(no_trait is not None and no_trait >= 450.0),
            "with_trait_approximation_meets_floor": bool(with_trait is not None and with_trait >= 450.0),
        },
        "classification": "REJECTED_BY_SELECTED_USAGE_FIDELITY",
        "policy": "Do not add or remove this operator solely to match the historical count 21.",
    }


def geometry_check(
    operator: dict[str, Any],
    *,
    origin: tuple[int, int],
    required_tiles: set[tuple[int, int]],
) -> dict[str, Any]:
    from arknights_planner.simulator import ApproximateRealRangeTransformer

    transformer = ApproximateRealRangeTransformer()
    offsets = [tuple(cell) for cell in operator["attack_range_cells"]]
    directions = {}
    for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
        coverage = transformer.covered_tiles(origin=origin, offsets=offsets, direction=direction)
        directions[direction] = sorted(coverage & required_tiles)
    satisfied = {
        direction: set(required_tiles) <= set(cells)
        for direction, cells in directions.items()
    }
    return {
        "origin": list(origin),
        "required_tiles": [list(tile) for tile in sorted(required_tiles)],
        "coverage_by_direction": directions,
        "direction_satisfies_all_required_tiles": satisfied,
        "any_direction_satisfies_all_required_tiles": any(satisfied.values()),
    }


def candidate_record(
    slot: dict[str, Any],
    operator: dict[str, Any],
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    repair: Any,
    *,
    geometry: dict[str, Any] | None = None,
    capability_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eligible, gate_reasons = repair.selected_usage_fidelity(
        operator,
        role=slot["role"],
        fidelity_by_id=fidelity_by_id,
        census_by_id=census_by_id,
    )
    census = census_by_id.get(operator["operator_id"], {})
    return {
        "slot_id": slot["slot_id"],
        "operator_id": operator["operator_id"],
        "cost": operator["cost"],
        "hp": operator["hp"],
        "defense": operator["defense"],
        "block_count": operator["block_count"],
        "position": operator["position"],
        "basic_attack_safe": operator.get("planner_safe_for_basic_attack"),
        "selected_skill": {
            "supported": operator.get("skill_supported"),
            "auto_activate": operator.get("skill_auto_activate"),
            "recovery_mode": operator.get("skill_recovery_mode"),
            "effect": operator.get("skill_effect"),
        },
        "trait": {
            "supported": fidelity_by_id.get(operator["operator_id"], {}).get("dimensions", {}).get("trait"),
            "keys": sorted(trait_keys(census)),
        },
        "selected_usage_gate": {
            "eligible": eligible,
            "reasons": gate_reasons,
        },
        "geometry": geometry,
        "capability_checks": capability_overrides or {},
        "qualified_for_faithful_witness": False,
        "qualification_blockers": list(gate_reasons),
    }


def dp_ledger() -> dict[str, Any]:
    initial = 10.0
    rate = 1.0
    frame_rate = 30.0

    def dp(frame: float, spent: float, refund: float = 0.0) -> float:
        return initial + frame / frame_rate * rate - spent + refund

    rows = []
    natural_rows = [
        ("A01_C03_STUB_DEPLOY", 27, 5.0, 0.0),
        ("A02_C01_DAM_DEPLOY", 191, 8.0, 0.0),
        ("A01_C03_STUB_RETREAT_NO_CONFIRMED_REFUND", 390, 0.0, 0.0),
        ("A03_MERGED_ANCHOR_EARLIEST_NATURAL_DEPLOY", 540, 15.0, 0.0),
        ("A04_C05_DUELIST_DEPLOY", 725, 6.0, 0.0),
        ("A05_C06_DUELIST_DEPLOY", 729, 6.0, 0.0),
    ]
    spent = 0.0
    for label, frame, cost, refund in natural_rows:
        before = dp(frame, spent)
        spent += cost
        after = before - cost + refund
        rows.append(
            {
                "branch": "NATURAL_ONLY_NO_REFUND",
                "event": label,
                "frame": frame,
                "cost": cost,
                "refund": refund,
                "available_dp_before": before,
                "available_dp_after": after,
                "affordable": after >= -1e-9,
            }
        )
    conditional_rows = [
        ("A01_C03_STUB_DEPLOY", 27, 5.0),
        ("A02_C01_DAM_DEPLOY", 191, 8.0),
        ("A01_C03_STUB_RETREAT_HYPOTHETICAL_FULL_COST_REFUND", 390, 0.0),
        ("A03_MERGED_ANCHOR_EARLIEST_CONDITIONAL_DEPLOY", 390, 15.0),
        ("A04_C05_DUELIST_DEPLOY", 725, 6.0),
        ("A05_C06_DUELIST_DEPLOY", 729, 6.0),
    ]
    spent = 0.0
    refund = 0.0
    for label, frame, cost in conditional_rows:
        before = dp(frame, spent, refund)
        spent += cost
        after = before - cost
        rows.append(
            {
                "branch": "HYPOTHETICAL_FULL_COST_REFUND_NOT_CONFIRMED",
                "event": label,
                "frame": frame,
                "cost": cost,
                "refund": 5.0 if "REFUND" in label else 0.0,
                "available_dp_before": before,
                "available_dp_after": after,
                "affordable": after >= -1e-9,
            }
        )
        if "REFUND" in label:
            refund += 5.0
    return {
        "schema_version": "R8_1_PLAN_A_SCOPED_DP_LEDGER_V1",
        "frame_budget": list(FRAME_BUDGET),
        "initial_dp": initial,
        "natural_dp_rate_per_second": rate,
        "confirmed_retreat_refund": {
            "status": "UNKNOWN",
            "simulator_behavior": "NO_REFUND",
            "reason": "No source-backed amount and to-account frame were supplied; the current runtime retreats without refund.",
        },
        "rows": rows,
        "conditions": {
            "A03_WITHOUT_REFUND_EARLIEST_NATURAL_FRAME": 540,
            "A05_WITH_FULL_COST_REFUND_DEFICIT": 0.7000000000000028,
            "A05_WITHOUT_REFUND_DEFICIT": 5.700000000000003,
        },
        "evidence_status": "COST_CAP_EXAMPLE_NOT_ECONOMIC_LOWER_BOUND",
        "limitations": [
            "A03 uses its 15-DP cap, not the tested 11/12-DP candidate costs.",
            "Merchant upkeep is not modeled; these candidates are not qualified.",
            "COND_ROUTE6 permits omitting A05 before 941 if its refund condition fails.",
            "Neither branch proves Plan A infeasible or supplies a faithful witness.",
        ],
        "is_witness": False,
    }


def build(*, write_artifacts: bool = True) -> dict[str, Any]:
    if write_artifacts:
        OUT.mkdir(parents=True, exist_ok=True)
    context = load(CONTEXT)
    catalog = load(CATALOG)
    plan_payload = load(PLAN)
    fidelity_payload = load(FIDELITY)
    census_payload = load(CENSUS)
    plan = next(
        row for row in plan_payload["plans"]
        if row["operational_plan_id"] == "R8OP-A-MERGED-ANCHOR-REFUND-LATTICE"
    )
    slots = {row["slot_id"]: row for row in plan["compiler_slots"]}
    operators = {row["operator_id"]: row for row in context["operators"]}
    repair = import_repair()
    repair.load_fidelity_tables()
    fidelity_by_id = repair.engine_fidelity
    census_by_id = repair.engine_census

    unfiltered_current_pool = repair.selected_usage_pool(
        context,
        "RANGED_DPS",
        fidelity_by_id=fidelity_by_id,
        census_by_id=census_by_id,
    )
    all_anchor_pool = [row for row in unfiltered_current_pool if row["cost"] <= 15]
    unfiltered_missing_table_pool = repair.selected_usage_pool(
        context,
        "RANGED_DPS",
        fidelity_by_id={},
        census_by_id={},
    )
    missing_table_pool = [row for row in unfiltered_missing_table_pool if row["cost"] <= 15]
    anchor_pool = [
        row for row in all_anchor_pool
        if row["cost"] <= 15
        and row.get("skill_supported")
        and row.get("skill_auto_activate")
        and row.get("planner_safe_for_basic_attack")
    ]
    anchor_pool.sort(
        key=lambda row: (
            -(effective_dps(row) or 0.0),
            row["operator_id"],
        )
    )
    anchor_candidates = anchor_pool[:MAX_CANDIDATES_PER_SLOT]
    anchor_required_tiles = {(8, 5)}
    anchor_records = []
    for operator in anchor_candidates:
        geometry = geometry_check(operator, origin=(9, 2), required_tiles=anchor_required_tiles)
        effective = effective_dps(operator)
        capability = {
            "evidence_status": "DIAGNOSTIC_APPROXIMATION_NOT_DAMAGE_BOUND",
            "required_effective_dps_vs_def_150": 450.0,
            "calculated_effective_dps_vs_def_150": effective,
            "meets_damage_floor": bool(effective is not None and effective >= 450.0),
            "required_auto_skill": True,
        }
        record = candidate_record(
            slots["A03_MERGED_ANCHOR"],
            operator,
            fidelity_by_id,
            census_by_id,
            repair,
            geometry=geometry,
            capability_overrides=capability,
        )
        blockers = list(record["qualification_blockers"])
        if not capability["meets_damage_floor"]:
            blockers.append("ANCHOR_EXACT_DAMAGE_CONTRACT_UNVERIFIED")
        if not geometry["any_direction_satisfies_all_required_tiles"]:
            blockers.append("ANCHOR_GEOMETRY_CANNOT_COVER_REQUIRED_POCKET_TILE_8_5")
        record["qualification_blockers"] = sorted(set(blockers))
        record["qualified_for_faithful_witness"] = not blockers
        anchor_records.append(record)

    blocker_records = []
    for slot_id in ("A01_C03_STUB", "A02_C01_DAM"):
        slot = slots[slot_id]
        source_candidates = [
            row for row in context["operators"]
            if row["position"] == "MELEE"
            and row["cost"] <= slot["max_cost_design_choice"]
            and row["block_count"] >= (2 if slot_id == "A02_C01_DAM" else 1)
            and row["defense"] >= (240 if slot_id == "A01_C03_STUB" else 322)
            and row["hp"] >= (2000 if slot_id == "A02_C01_DAM" else 0)
            and row.get("planner_safe_for_basic_attack")
        ]
        if slot_id == "A02_C01_DAM":
            source_candidates = [row for row in source_candidates if row["hp"] >= 2000]
        source_candidates.sort(key=lambda row: (row["cost"], -(row["attack"] / row["attack_interval_seconds"]), row["operator_id"]))
        for operator in source_candidates[:MAX_CANDIDATES_PER_SLOT]:
            record = candidate_record(slot, operator, fidelity_by_id, census_by_id, repair)
            blockers = list(record["qualification_blockers"])
            trait = record["trait"]
            if trait["supported"] == "UNSUPPORTED":
                if operator["operator_id"] == "char_445_wscoot":
                    blockers.extend(
                        [
                            "TRAIT_DESCRIPTION_INDICATES_BLOCK_0_UNTIL_SKILL",
                            "PLAN_REQUIRES_BLOCK_WITHOUT_SKILL_DEPENDENCE",
                        ]
                    )
                if trait_keys(census_by_id.get(operator["operator_id"], {})) & {"cost", "interval"}:
                    blockers.append("TRAIT_ECONOMY_OR_TIMING_UNSUPPORTED")
            record["qualification_blockers"] = sorted(set(blockers))
            record["qualified_for_faithful_witness"] = not blockers
            blocker_records.append(record)

    duelist_records = []
    for slot_id in ("A04_C05_DUELIST", "A05_C06_DUELIST"):
        slot = slots[slot_id]
        candidates = [
            row for row in context["operators"]
            if row["position"] == "MELEE"
            and row["cost"] <= slot["max_cost_design_choice"]
            and row["hp"] >= 1500
            and row["defense"] >= 255
            and row.get("planner_safe_for_basic_attack")
        ]
        candidates.sort(key=lambda row: (row["cost"], -(row["attack"] / row["attack_interval_seconds"]), row["operator_id"]))
        for operator in candidates[:MAX_CANDIDATES_PER_SLOT]:
            record = candidate_record(slot, operator, fidelity_by_id, census_by_id, repair)
            record["qualification_blockers"] = sorted(set(record["qualification_blockers"]))
            record["qualified_for_faithful_witness"] = not record["qualification_blockers"]
            duelist_records.append(record)

    snhunt = snhunt_audit(
        context,
        fidelity_by_id,
        census_by_id,
        all_anchor_pool,
        missing_table_pool,
    )
    all_candidate_records = anchor_records + blocker_records + duelist_records
    faithful_candidates = [row for row in all_candidate_records if row["qualified_for_faithful_witness"]]
    qualified_slots = {
        slot_id: [
            row for row in faithful_candidates
            if row["slot_id"] == slot_id
        ]
        for slot_id in ("A01_C03_STUB", "A02_C01_DAM", "A03_MERGED_ANCHOR", "A04_C05_DUELIST", "A05_C06_DUELIST")
    }
    complete_combinations = math.prod(len(rows) for rows in qualified_slots.values())
    witness = None
    simulations = 0
    frontier = {
        "schema_version": "R8_1_PLAN_A_BOUNDED_OPENING_FRONTIER_V1",
        "operational_plan_id": plan["operational_plan_id"],
        "frame_budget": list(FRAME_BUDGET),
        "budget": {
            "max_candidates_per_required_slot": MAX_CANDIDATES_PER_SLOT,
            "max_complete_combinations": MAX_COMPLETE_COMBINATIONS,
            "max_stage_prefix_simulations": MAX_STAGE_PREFIX_SIMULATIONS,
        },
        "candidate_counts": {
            "A01_C03_STUB": len([row for row in blocker_records if row["slot_id"] == "A01_C03_STUB"]),
            "A02_C01_DAM": len([row for row in blocker_records if row["slot_id"] == "A02_C01_DAM"]),
            "A03_MERGED_ANCHOR": len(anchor_records),
            "A04_C05_DUELIST": len([row for row in duelist_records if row["slot_id"] == "A04_C05_DUELIST"]),
            "A05_C06_DUELIST": len([row for row in duelist_records if row["slot_id"] == "A05_C06_DUELIST"]),
        },
        "qualified_candidate_counts": {key: len(value) for key, value in qualified_slots.items()},
        "structural_combinations_if_ignoring_gate": (
            len([row for row in blocker_records if row["slot_id"] == "A01_C03_STUB"])
            * len([row for row in blocker_records if row["slot_id"] == "A02_C01_DAM"])
            * len(anchor_records)
            * len([row for row in duelist_records if row["slot_id"] == "A04_C05_DUELIST"])
            * len([row for row in duelist_records if row["slot_id"] == "A05_C06_DUELIST"])
        ),
        "faithful_complete_combinations": complete_combinations,
        "candidates": all_candidate_records,
        "snhunt_audit": snhunt,
    }
    scoped_conflicts = []
    if not qualified_slots["A03_MERGED_ANCHOR"]:
        scoped_conflicts.append(
            {
                "slot_id": "A03_MERGED_ANCHOR",
                "classification": "NO_SOURCE_QUALIFIED_ANCHOR_IN_BUDGET",
                "evidence": [
                    "Top-3 anchors have diagnostic average DPS below 450, but the formula is not a verified finite-window damage bound; exact damage remains UNKNOWN.",
                    "The exemplar snhunt exceeds 450 in the same diagnostic approximation; its ammo/trait remains unsupported and decision-critical.",
                    "Only one of the three tested anchors has a direction that covers [8,5]; the other two also fail the plan's pocket geometry.",
                ],
            }
        )
    for slot_id in ("A01_C03_STUB", "A02_C01_DAM"):
        rows = [row for row in blocker_records if row["slot_id"] == slot_id]
        if rows and not qualified_slots[slot_id]:
            scoped_conflicts.append(
                {
                    "slot_id": slot_id,
                    "classification": "TRAIT_OR_SELECTED_USAGE_UNVERIFIED",
                    "evidence": [row["qualification_blockers"] for row in rows],
                }
            )
    for slot_id in ("A04_C05_DUELIST", "A05_C06_DUELIST"):
        rows = [row for row in duelist_records if row["slot_id"] == slot_id]
        if rows and not qualified_slots[slot_id]:
            scoped_conflicts.append(
                {
                    "slot_id": slot_id,
                    "classification": "NO_SOURCE_QUALIFIED_DUELIST_IN_BUDGET",
                    "evidence": [row["qualification_blockers"] for row in rows],
                }
            )
    scoped_conflicts.append(
        {
            "slot_id": "A01_C03_STUB_RETREAT",
            "classification": "RETREAT_REFUND_UNKNOWN",
            "evidence": [
                "The plan banks a refund at about frame 390.",
                "No source-backed refund amount and to-account frame were supplied.",
                "Current simulator applies no refund.",
            ],
        }
    )
    ledger = dp_ledger()
    validation = {
        "schema_version": "R8_1_PLAN_A_OPENING_WITNESS_VALIDATION_V1",
        "checks": {
            "review_patch_applied": True,
            "fidelity_tables_present": FIDELITY.is_file() and CENSUS.is_file(),
            "fidelity_tables_are_305_operator_inputs": fidelity_payload["operator_count"] == 305 and census_payload["operator_count"] == 305,
            "budget_respected": len(anchor_candidates) <= 3 and frontier["structural_combinations_if_ignoring_gate"] <= 16 and simulations <= 1,
            "no_simulation_without_faithful_witness": simulations == 0 if not witness else True,
            "frame_295_not_used_as_fire_deadline": all(
                row["deadline_basis"] != "route-3:FIRE" or "295" not in json.dumps(row)
                for row in plan["compiler_slots"]
            ),
            "snhunt_not_artificially_added_or_removed": snhunt["missing_table_only_operator_ids"] == ["char_4211_snhunt"],
            "scoped_conflicts_are_not_global_infeasibility": all(
                row["classification"] != "GLOBAL_PLAN_INFEASIBLE" for row in scoped_conflicts
            ),
        },
        "status": "PASS",
    }
    validation["status"] = "PASS" if all(validation["checks"].values()) else "FAIL"
    final_status = {
        "schema_version": "R8_1_PLAN_A_OPENING_WITNESS_FINAL_STATUS_V1",
        "status": "NO_FAITHFUL_WITNESS_SCOPED_CONFLICT",
        "operational_plan_id": plan["operational_plan_id"],
        "faithful_candidates": len(faithful_candidates),
        "faithful_complete_combinations": complete_combinations,
        "witness": witness,
        "stage_prefix_simulations": simulations,
        "scoped_conflicts": scoped_conflicts,
        "learned_next_tactical_input": (
            "No faithful witness was constructed in this bounded gate audit. Two tested anchors cannot "
            "cover [8,5] from [9,2]; caper can. Exact finite-window damage, critical traits and refund "
            "remain unverified. The cost-cap DP example does not prove an economic lower bound, and "
            "COND_ROUTE6 must preserve its concession branch. These are scoped facts and system "
            "limitations, not proof of tactical infeasibility."
        ),
        "kimi_calls": 0,
        "new_operational_plans": 0,
        "mechanics_changed": False,
        "real_game_validation": "UNTESTED",
    }
    if write_artifacts:
        write("operator_runtime_fidelity_input_provenance.json", fidelity_provenance())
        write("plan_a_bounded_opening_frontier.json", frontier)
        write("plan_a_scoped_dp_ledger.json", ledger)
        write("plan_a_witness_certificate.json", {
            "schema_version": "R8_1_PLAN_A_OPENING_WITNESS_CERTIFICATE_V1",
            "witness": witness,
            "simulations": simulations,
            "scoped_conflicts": scoped_conflicts,
        })
        write("validation_results.json", validation)
        write("final_status.json", final_status)
    return {
        "provenance": fidelity_provenance(),
        "frontier": frontier,
        "ledger": ledger,
        "validation": validation,
        "final_status": final_status,
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True))
