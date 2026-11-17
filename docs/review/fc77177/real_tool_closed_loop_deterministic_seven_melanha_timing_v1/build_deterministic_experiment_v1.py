#!/usr/bin/env python3
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_deterministic_seven_melanha_timing_v1"
R108_EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_melanha_timing_heal_competition_v1"
R107_RECOVERY = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_recovery_v1"
PARENT = R107_RECOVERY / "session/candidates/candidate-001"
INPUT = EXPERIMENT / "input_bundle"

EXPECTED_PARENT = {
    "plan_sha256": "a66ebae929cf36d5653a138d05191daea4acd1c94ebef54b8bca965e46a9d8ea",
    "action_sha256": "d21a4bf139e96199faf9b80eebfaab04e1fdb5845e1e8df57336e2f674ca0f9e",
    "events_gz_sha256": "3ef5e9aba8bd510dbb90d1c484b1f7d823b17e15c37235a99b18e10772caaca5",
    "events_restored_sha256": "3404a7062adc5d4dc135bb5716418bc23ab5d90b28908302f09766c1eba485f4",
}
PLAN_ID = "R108_DETERMINISTIC_SEVEN_MELANHA_TIMING_001"
HYPOTHESIS_ID = "R108_DETERMINISTIC_MELANHA_TIMING"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    INPUT.mkdir(parents=True, exist_ok=True)
    actual = {
        "plan_sha256": digest(PARENT / "simulation/plan_snapshot.json"),
        "action_sha256": digest(PARENT / "simulation/action_snapshot.json"),
        "events_gz_sha256": digest(PARENT / "simulation/diagnostic_events.json.gz"),
        "events_restored_sha256": restored_digest(PARENT / "simulation/diagnostic_events.json.gz"),
    }
    if actual != EXPECTED_PARENT:
        raise SystemExit(f"parent identity mismatch: expected={EXPECTED_PARENT}, actual={actual}")
    parent_events = json.loads(gzip.decompress((R108_EXPERIMENT / "input_bundle/parent_R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001/diagnostic_events.json.gz").read_bytes()))["events"]
    parent_plan = json.loads((PARENT / "source/original_request.json").read_text())["plan"]
    parent_actions = parent_plan["revised_operational_plans"][0]["action_timeline"]
    deploy_indexes = [index for index, action in enumerate(parent_actions) if action == {"action_type": "DEPLOY", "frame": 901, "direction": "RIGHT", "operator_id": "char_208_melan", "tile": [6, 5]}]
    skill_indexes = [index for index, action in enumerate(parent_actions) if action == {"action_type": "ACTIVATE_SKILL", "frame": 2102, "operator_id": "char_208_melan"}]
    if len(deploy_indexes) != 1 or len(skill_indexes) != 1:
        raise SystemExit(f"unique action match failed: deploy={deploy_indexes}, skill={skill_indexes}")

    shutil.copyfile(R108_EXPERIMENT / "input_bundle/revision_output_schema.json", INPUT / "revision_output_schema.json")
    shutil.copyfile(R108_EXPERIMENT / "input_bundle/r108_melanha_timing_fact_pack_v1.json", INPUT / "r108_melanha_timing_fact_pack_v1.json")
    context = json.loads((R108_EXPERIMENT / "input_bundle/llm_evidence_context.json").read_text())
    fact_pack = json.loads((INPUT / "r108_melanha_timing_fact_pack_v1.json").read_text())
    fact_pack["fps"] = {"frames_per_second": 30, "source": "RUNTIME_SIMULATION_PARAMETERS frames_per_second=30.0"}
    fact_pack["deterministic_counterfactual"] = {
        "deploy_old_frame": 901,
        "deploy_new_frame": 1261,
        "skill_old_frame": 2102,
        "skill_new_frame": 2462,
        "skill_delay_frames": 360,
        "boundary": "Frame-only paired retiming; no safety, heal competition, or outcome is asserted.",
    }
    fact_pack["path"] = "input_bundle/r108_melanha_timing_fact_pack_v1.json"
    context["deterministic_counterfactual_policy"] = {
        "schema_version": "KIMIARK_DETERMINISTIC_COUNTERFACTUAL_POLICY_V1",
        "model_generation": False,
        "parent_record_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001:candidate-001",
        "parent_plan_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001",
        "parent_plan_sha256": EXPECTED_PARENT["plan_sha256"],
        "parent_action_sha256": EXPECTED_PARENT["action_sha256"],
        "parent_events_gz_sha256": EXPECTED_PARENT["events_gz_sha256"],
        "parent_events_restored_sha256": EXPECTED_PARENT["events_restored_sha256"],
        "allowed_action_changes": [
            {"action_index": deploy_indexes[0], "field": "frame", "old": 901, "new": 1261, "action_type": "DEPLOY", "operator_id": "char_208_melan"},
            {"action_index": skill_indexes[0], "field": "frame", "old": 2102, "new": 2462, "action_type": "ACTIVATE_SKILL", "operator_id": "char_208_melan"},
        ],
        "authorization": "USER_PROMPT_AUTHORIZED_EXACT_TWO_FRAME_MELANHA_DELAY",
    }
    context["parent_identity_manifest"]["candidate_plan_ids"] = ["R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001"]
    context["parent_identity_manifest"]["selection_policy"] = "Parent is fixed to the verified R107 recovery candidate for this deterministic Melanha-timing control; no selector override."
    write_json(INPUT / "r108_melanha_timing_fact_pack_v1.json", fact_pack)
    fact_pack["sha256"] = digest(INPUT / "r108_melanha_timing_fact_pack_v1.json")
    write_json(INPUT / "llm_evidence_context.json", context)

    plan = copy.deepcopy(parent_plan)
    selected_plan = plan["revised_operational_plans"][0]
    selected_plan["operational_plan_id"] = PLAN_ID
    selected_plan["parent_hypothesis_id"] = HYPOTHESIS_ID
    selected_plan["action_timeline"][deploy_indexes[0]]["frame"] = 1261
    selected_plan["action_timeline"][skill_indexes[0]]["frame"] = 2462
    selected_plan["validation_card"] = {
        "schema_version": "KIMIARK_DETERMINISTIC_COUNTERFACTUAL_VALIDATION_CARD_V1",
        "generation": "SCRIPT_FROM_FROZEN_PARENT_ACTIONS",
        "model_generation": False,
        "parent_record_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001:candidate-001",
        "parent_hashes": EXPECTED_PARENT,
        "single_change_policy": {
            "allowed_changes": [
                {"action_index": deploy_indexes[0], "action_type": "DEPLOY", "operator_id": "char_208_melan", "frame": {"old": 901, "new": 1261}},
                {"action_index": skill_indexes[0], "action_type": "ACTIVATE_SKILL", "operator_id": "char_208_melan", "frame": {"old": 2102, "new": 2462}},
            ],
            "changed_action_count": 2,
            "all_other_actions": "IDENTICAL",
        },
        "timing_calculation": {
            "frames_per_second": 30,
            "deploy_old_frame": 901,
            "deploy_new_frame": 1261,
            "skill_old_frame": 2102,
            "skill_new_frame": 2462,
            "paired_skill_delay_frames": 360,
            "result": "STATIC_PAIR_ONLY",
        },
        "expected_observable_events": [
            "Events before 901 remain comparable to the parent.",
            "Observe whether any lower-lane enemy that the original 901 deployment blocked or damaged leaks, hits a roadblock, or remains alive during 901-1261.",
            "Observe roadblock4 damage/destruction, #14 damage/restraint/reach, and all related target-selection events independently; delayed deployment does not guarantee proportional delay.",
            "Observe heal targets and quantities around 2102-2462 and the unchanged prior Steward death window, without treating net-difference as exact HP proof.",
            "Observe #11/#13, Steward/artillery, protected #3, and central #21/#22/#33/#34 separately.",
        ],
        "refutation_conditions": [
            "Pre-901 event mismatch invalidates control comparability.",
            "Static action error or unexpected illegal action.",
            "An earlier lower-lane leak, roadblock destruction, or #14 failure refutes the frozen timing premise for this parent.",
            "No heal-distribution change means the timing change did not produce the hypothesized support effect.",
        ],
        "unknowns": [
            "Exact HP and continuous positions are UNKNOWN unless recorded.",
            "Whether delayed Melanha is alive/positioned enough for roadblock4 is UNKNOWN before simulation.",
            "Exact HP, continuous positions, complete heal candidate ordering, and pre-swing state are UNKNOWN unless recorded.",
        ],
    }
    plan["revision_hypothesis"] = {
        "hypothesis_id": HYPOTHESIS_ID,
        "operational_plan_id": PLAN_ID,
        "parent_plan_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001",
        "changed_responsibilities": [
            "Exactly two frames change: Melanha deploy 901->1261 and its paired first skill activation 2102->2462.",
            "No role, tile, direction, skill, roster, or other action changes.",
        ],
        "expected_first_observable_event": copy.deepcopy(plan["revision_hypothesis"]["expected_first_observable_event"]),
        "if_expected_event_absent": copy.deepcopy(plan["revision_hypothesis"]["if_expected_event_absent"]),
        "referenced_experience_ids": ["R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001:candidate-001"],
        "tactical_hypothesis": "Observe whether delaying Melanha deployment and its paired skill changes lower-lane blocking, roadblock4/#14 timing, and heal competition without asserting that the hypothesis is beneficial.",
    }
    plan["revised_strategic_hypotheses"] = [{
        "hypothesis_id": HYPOTHESIS_ID,
        "deterministic_counterfactual": True,
        "model_generated": False,
        "parent_plan_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001",
        "summary": "Mechanically derive the authorized two-frame Melanha delay from the verified R107 recovery candidate and test its observable consequences.",
    }]
    write_json(INPUT / "candidate_plan.json", plan)

    candidate_actions = selected_plan["action_timeline"]
    diff = [
        {"action_index": index, "parent": parent, "candidate": candidate}
        for index, (parent, candidate) in enumerate(zip(parent_actions, candidate_actions))
        if parent != candidate
    ]
    if len(diff) != 2 or [item["action_index"] for item in diff] != [deploy_indexes[0], skill_indexes[0]]:
        raise SystemExit(f"unexpected action diff: {diff}")
    if candidate_actions[deploy_indexes[0]]["frame"] != 1261 or candidate_actions[skill_indexes[0]]["frame"] != 2462:
        raise SystemExit("paired Melanha frame transformation did not apply")
    if candidate_actions[skill_indexes[0]]["frame"] - candidate_actions[deploy_indexes[0]]["frame"] != 1201:
        raise SystemExit("deploy-to-skill interval is not 1201 frames")
    transformed_record = {
        "schema_version": "KIMIARK_DETERMINISTIC_ACTION_TRANSFORMATION_RECORD_V1",
        "plan_id": PLAN_ID,
        "parent_identity": {"record_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001:candidate-001", **EXPECTED_PARENT},
        "parent_action_sha256": EXPECTED_PARENT["action_sha256"],
        "candidate_action_sha256": None,
        "changed_action_count": len(diff),
        "changes": diff,
        "unit_derivation": {
            "fps": 30,
            "deploy_frame_old": 901,
            "deploy_frame_new": 1261,
            "skill_frame_old": 2102,
            "skill_frame_new": 2462,
            "skill_delay_seconds": 12,
            "skill_delay_frames": 360,
            "boundary": "The 360-frame skill shift is an explicitly authorized paired delay, not a recomputation of SP availability.",
        },
        "model_generation": False,
    }
    write_json(INPUT / "transformation_record_v1.json", transformed_record)

    parent_artifacts = [
        "plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "final_status.json",
    ]
    parent_bundle = INPUT / "parent_R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001"
    parent_bundle.mkdir(parents=True, exist_ok=True)
    for name in parent_artifacts:
        shutil.copyfile(PARENT / "simulation" / name, parent_bundle / name)
    shutil.copyfile(PARENT / "candidate_record.json", parent_bundle / "candidate_record.json")

    manifest = {
        "schema_version": "KIMIARK_DETERMINISTIC_EXPERIMENT_MANIFEST_V1",
        "experiment": "real_tool_closed_loop_deterministic_seven_melanha_timing_v1",
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
        "plan_id_prefix": "R108_DETERMINISTIC_SEVEN_MELANHA_TIMING_",
        "plan_label": "DETERMINISTIC_SEVEN_MELANHA_TIMING",
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": "deterministic-seven-melanha-timing-v1",
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
