#!/usr/bin/env python3
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_deterministic_seven_c2_coupled_retreat_v1"
PARENT_EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_selector_feedback_v1"
PARENT = PARENT_EXPERIMENT / "session/candidates/candidate-002"
R103_EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_c2_retreat_window_v1"
INPUT = EXPERIMENT / "input_bundle"

EXPECTED_PARENT = {
    "plan_sha256": "044eb9eb90254934cc4767dbd1070ee91ccbdf349380ec258bbdd488098b146b",
    "action_sha256": "d5a07b4dca4f05cee428875165d3c59ee0c388e9b950623cd62fc8c60d83fc8f",
    "events_gz_sha256": "d971d1fe5a69c2ea5a4ae3c98f44ab023b3e48ee1e3eb3f1dc6168808930a065",
    "events_restored_sha256": "25f3a184f572bee142c9d5d1a6ee0807db0e2e28df26d5dee26fcea7691f9ed7",
}
PLAN_ID = "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001"
HYPOTHESIS_ID = "R104_DETERMINISTIC_COUPLED_RETREAT"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    actual = {
        "plan_sha256": digest(PARENT / "simulation/plan_snapshot.json"),
        "action_sha256": digest(PARENT / "simulation/action_snapshot.json"),
        "events_gz_sha256": digest(PARENT / "simulation/diagnostic_events.json.gz"),
        "events_restored_sha256": restored_digest(PARENT / "simulation/diagnostic_events.json.gz"),
    }
    if actual != EXPECTED_PARENT:
        raise SystemExit(f"parent identity mismatch: expected={EXPECTED_PARENT}, actual={actual}")
    parent_events = json.loads(gzip.decompress((PARENT / "simulation/diagnostic_events.json.gz").read_bytes()))["events"]
    parent_plan = json.loads((PARENT / "source/original_request.json").read_text())["plan"]
    parent_actions = parent_plan["revised_operational_plans"][0]["action_timeline"]
    retreat_indexes = [index for index, action in enumerate(parent_actions) if action == {"action_type": "RETREAT", "frame": 4200, "operator_id": "char_210_stward"}]
    deploy_indexes = [index for index, action in enumerate(parent_actions) if action == {"action_type": "DEPLOY", "frame": 6301, "direction": "UP", "operator_id": "char_210_stward", "tile": [2, 5]}]
    if len(retreat_indexes) != 1 or len(deploy_indexes) != 1:
        raise SystemExit(f"unique action match failed: retreat={retreat_indexes}, deploy={deploy_indexes}")

    shutil.copyfile(R103_EXPERIMENT / "input_bundle/revision_output_schema.json", INPUT / "revision_output_schema.json")
    context = json.loads((R103_EXPERIMENT / "input_bundle/llm_evidence_context.json").read_text())
    fact_pack = context.setdefault("retreat_window_fact_pack_v1", {})
    fact_pack["schema_version"] = "KIMIARK_COUPLED_RETREAT_TIMING_FACT_PACK_V1"
    fact_pack["fps"] = {"frames_per_second": 30, "source": "RUNTIME_SIMULATION_PARAMETERS frames_per_second=30.0"}
    fact_pack["steward_redeploy"] = {
        "seconds": 70,
        "frames": 2100,
        "cost": 18,
        "source": "normal_low_star_facts.json operators[char_210_stward].stats",
    }
    fact_pack["coupled_counterfactual"] = {
        "retreat_old_frame": 4200,
        "retreat_new_frame": 4280,
        "deploy_old_frame": 6301,
        "deploy_new_frame": 6381,
        "retained_interval_frames": 2101,
        "minimum_legal_redeploy_after_4280": 6380,
        "cooldown_at_6381": "AVAILABLE",
        "boundary": "Static legality only; survival and extra output are not asserted.",
    }
    fact_pack["prior_error_correction"] = {
        "old_declared_steward_redeploy_time_frames": 70,
        "old_declared_available_at_if_retreat_4280": 4350,
        "corrected_redeploy_time_frames": 2100,
        "corrected_minimum_redeploy_after_4280": 6380,
    }
    fact_pack["path"] = "input_bundle/retreat_window_fact_pack_v1.json"
    context["deterministic_counterfactual_policy"] = {
        "schema_version": "KIMIARK_DETERMINISTIC_COUNTERFACTUAL_POLICY_V1",
        "model_generation": False,
        "parent_record_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002",
        "parent_plan_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002",
        "parent_plan_sha256": EXPECTED_PARENT["plan_sha256"],
        "parent_action_sha256": EXPECTED_PARENT["action_sha256"],
        "parent_events_gz_sha256": EXPECTED_PARENT["events_gz_sha256"],
        "parent_events_restored_sha256": EXPECTED_PARENT["events_restored_sha256"],
        "allowed_action_changes": [
            {"action_index": retreat_indexes[0], "field": "frame", "old": 4200, "new": 4280, "action_type": "RETREAT", "operator_id": "char_210_stward"},
            {"action_index": deploy_indexes[0], "field": "frame", "old": 6301, "new": 6381, "action_type": "DEPLOY", "operator_id": "char_210_stward"},
        ],
        "authorization": "USER_PROMPT_AUTHORIZED_EXACT_TWO_FRAME_COUPLED_RETIMING",
    }
    context["parent_identity_manifest"]["candidate_plan_ids"] = ["R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002"]
    context["parent_identity_manifest"]["selection_policy"] = "Parent is fixed to R101 C2 for this deterministic coupled-retiming control; no selector override."
    write_json(INPUT / "retreat_window_fact_pack_v1.json", fact_pack)
    fact_pack["sha256"] = digest(INPUT / "retreat_window_fact_pack_v1.json")
    write_json(INPUT / "llm_evidence_context.json", context)

    plan = copy.deepcopy(parent_plan)
    selected_plan = plan["revised_operational_plans"][0]
    selected_plan["operational_plan_id"] = PLAN_ID
    selected_plan["parent_hypothesis_id"] = HYPOTHESIS_ID
    selected_plan["action_timeline"][retreat_indexes[0]]["frame"] = 4280
    selected_plan["action_timeline"][deploy_indexes[0]]["frame"] = 6381
    selected_plan["validation_card"] = {
        "schema_version": "KIMIARK_DETERMINISTIC_COUNTERFACTUAL_VALIDATION_CARD_V1",
        "generation": "SCRIPT_FROM_FROZEN_PARENT_ACTIONS",
        "model_generation": False,
        "parent_record_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002",
        "parent_hashes": EXPECTED_PARENT,
        "single_change_policy": {
            "allowed_changes": [
                {"action_index": retreat_indexes[0], "action_type": "RETREAT", "operator_id": "char_210_stward", "frame": {"old": 4200, "new": 4280}},
                {"action_index": deploy_indexes[0], "action_type": "DEPLOY", "operator_id": "char_210_stward", "frame": {"old": 6301, "new": 6381}},
            ],
            "changed_action_count": 2,
            "all_other_actions": "IDENTICAL",
        },
        "timing_calculation": {
            "frames_per_second": 30,
            "steward_redeploy_seconds": 70,
            "steward_redeploy_frames": 2100,
            "retained_retreat_to_return_interval_frames": 2101,
            "cooldown_ready_after_4280": 6380,
            "scheduled_return": 6381,
            "result": "LEGAL_BY_COOLDOWN",
        },
        "expected_observable_events": [
            "Events before 4200 remain comparable to the parent.",
            "Steward remains deployed through 4200-4280 unless killed; observe all target selection, damage, heals, enemy ability hits and deaths in that window.",
            "Any extra Steward-to-artillery DAMAGE must be recorded as actual DAMAGE, not inferred from position.",
            "The unchanged later return shifts from 6301 to 6381; central consequences must be separately observed and are not attributed solely to retreat.",
        ],
        "refutation_conditions": [
            "Pre-4200 event mismatch invalidates control comparability.",
            "Static action error or unexpected illegal action.",
            "No extra artillery hit means the tested 4200-4280 segment did not produce output; it does not prove every later window is worthless.",
            "Death, no candidate, or target transfer must be distinguished from successful extra output.",
        ],
        "unknowns": [
            "Exact HP and continuous positions are UNKNOWN unless recorded.",
            "Survival after 4200 is UNKNOWN before simulation.",
            "In-flight projectile effects after 4200 require runtime evidence.",
        ],
    }
    plan["revision_hypothesis"] = {
        "hypothesis_id": HYPOTHESIS_ID,
        "operational_plan_id": PLAN_ID,
        "parent_plan_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002",
        "changed_responsibilities": [
            "Exactly two frames change: Steward retreat 4200->4280 and same-ID deploy 6301->6381. The retreat-to-return interval remains 2101 frames.",
            "No role, tile, direction, skill, roster, or other action changes.",
        ],
        "expected_first_observable_event": copy.deepcopy(plan["revision_hypothesis"]["expected_first_observable_event"]),
        "if_expected_event_absent": copy.deepcopy(plan["revision_hypothesis"]["if_expected_event_absent"]),
        "referenced_experience_ids": ["R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002"],
        "tactical_hypothesis": "Observe whether the frozen R101 C2 platform produces additional actual artillery output when Steward stays through 4280, and separately observe the cost of returning at 6381.",
    }
    plan["revised_strategic_hypotheses"] = [{
        "hypothesis_id": HYPOTHESIS_ID,
        "deterministic_counterfactual": True,
        "model_generated": False,
        "parent_plan_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002",
        "summary": "Mechanically derive the authorized two-frame coupled retiming from R101 C2 and test its observable consequences.",
    }]
    write_json(INPUT / "candidate_plan.json", plan)

    candidate_actions = selected_plan["action_timeline"]
    diff = [
        {"action_index": index, "parent": parent, "candidate": candidate}
        for index, (parent, candidate) in enumerate(zip(parent_actions, candidate_actions))
        if parent != candidate
    ]
    if len(diff) != 2 or [item["action_index"] for item in diff] != [retreat_indexes[0], deploy_indexes[0]]:
        raise SystemExit(f"unexpected action diff: {diff}")
    if candidate_actions[retreat_indexes[0]]["frame"] - candidate_actions[deploy_indexes[0]]["frame"] != -2101:
        raise SystemExit("retreat-to-return interval is not 2101 frames")
    transformed_record = {
        "schema_version": "KIMIARK_DETERMINISTIC_ACTION_TRANSFORMATION_RECORD_V1",
        "plan_id": PLAN_ID,
        "parent_identity": {"record_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002", **EXPECTED_PARENT},
        "parent_action_sha256": EXPECTED_PARENT["action_sha256"],
        "candidate_action_sha256": None,
        "changed_action_count": len(diff),
        "changes": diff,
        "unit_derivation": {
            "fps": 30,
            "redeploy_seconds": 70,
            "redeploy_frames": 70 * 30,
            "minimum_redeploy_after_4280": 4280 + 70 * 30,
            "scheduled_redeploy": 6381,
        },
        "model_generation": False,
    }
    write_json(INPUT / "transformation_record_v1.json", transformed_record)

    parent_artifacts = [
        "plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "final_status.json", "manifest.json",
    ]
    parent_bundle = INPUT / "parent_R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002"
    parent_bundle.mkdir(parents=True, exist_ok=True)
    for name in parent_artifacts:
        shutil.copyfile(PARENT / "simulation" / name, parent_bundle / name)
    shutil.copyfile(PARENT / "candidate_record.json", parent_bundle / "candidate_record.json")

    manifest = {
        "schema_version": "KIMIARK_DETERMINISTIC_EXPERIMENT_MANIFEST_V1",
        "experiment": "real_tool_closed_loop_deterministic_seven_c2_coupled_retreat_v1",
        "model_cli_starts_authorized": 0,
        "model_generation": False,
        "max_candidates": 1,
        "max_complete_simulations": 1,
        "parent_identity": EXPECTED_PARENT,
        "plan_id": PLAN_ID,
        "facts_source_files": {
            "candidate_plan.json": digest(INPUT / "candidate_plan.json"),
            "llm_evidence_context.json": digest(INPUT / "llm_evidence_context.json"),
            "revision_output_schema.json": digest(INPUT / "revision_output_schema.json"),
            "transformation_record_v1.json": digest(INPUT / "transformation_record_v1.json"),
        },
    }
    write_json(INPUT / "experiment_manifest_v1.json", manifest)

    session_config = {
        "authorization_config_path": str(EXPERIMENT / "deterministic_authorization_v1.json"),
        "allow_fake_execution": False,
        "budget_path": str(EXPERIMENT / "simulation_budget_v1.json"),
        "candidate_ledger_path": str(EXPERIMENT / "candidate_ledger_v1.json"),
        "features_apps": False,
        "facts_source_dir": str(INPUT),
        "execution_backend": "CONTROLLED_RUNNER",
        "max_candidates": 1,
        "max_check_calls": 5,
        "max_real_cli_starts": 0,
        "max_stage_simulations": 1,
        "max_unique_deployed_operators": 7,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "model": "DETERMINISTIC_COUNTERFACTUAL",
        "reasoning_effort": "NONE",
        "plan_id_prefix": "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_",
        "plan_label": "DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT",
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": "deterministic-seven-c2-coupled-retreat-v1",
        "session_root": str(EXPERIMENT / "session"),
        "simulation_timeout_seconds": 3600,
        "stage_id": "main_08-07",
    }
    if not (EXPERIMENT / "session_config_v1.json").exists():
        write_json(EXPERIMENT / "session_config_v1.json", session_config)
    authorization = {
        "schema_version": "KIMIARK_DETERMINISTIC_COUNTERFACTUAL_AUTHORIZATION_V1",
        "authorization_status": "USER_AUTHORIZED_NO_MODEL_ONE_SIMULATION",
        "model": "DETERMINISTIC_COUNTERFACTUAL",
        "reasoning_effort": "NONE",
        "real_cli_starts": {"authorized_real_cli_starts": 0, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False},
        "model_generation": False,
        "max_candidates": 1,
        "max_stage_simulations": 1,
    }
    if not (EXPERIMENT / "deterministic_authorization_v1.json").exists():
        write_json(EXPERIMENT / "deterministic_authorization_v1.json", authorization)
    if not (EXPERIMENT / "simulation_budget_v1.json").exists():
        write_json(EXPERIMENT / "simulation_budget_v1.json", {"max_stage_simulations": 1, "prior_stage_simulations": 0, "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1", "stage_id": "main_08-07", "started_stage_simulations": 0})
    if not (EXPERIMENT / "candidate_ledger_v1.json").exists():
        write_json(EXPERIMENT / "candidate_ledger_v1.json", {"schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2", "session_id": session_config["session_id"], "max_candidates": 1, "used_candidates": 0, "attempts": [], "max_check_calls": 5, "used_check_calls": 0, "checks": []})
    transformed_record["candidate_action_sha256"] = hashlib.sha256(json.dumps(candidate_actions, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    write_json(INPUT / "transformation_record_v1.json", transformed_record)
    print(json.dumps({"plan_id": PLAN_ID, "parent_hashes": EXPECTED_PARENT, "diff_count": len(diff), "diff": diff}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
