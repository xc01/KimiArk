#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_recovery_v1"
ORIGINAL_PATH = SOURCE / "session/checks/check-001/source/llm_structured_output.json"
NORMALIZED_PATH = DEST / "normalized_llm_structured_output.json"
ORIGINAL_ID = "R107_SOL_HIGH_SEVEN_LOWER_RELEASE_001"
CORRECT_ID = "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001"
SESSION_ID = "real-tool-loop-sol-high-seven-protected14-recovery-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    if NORMALIZED_PATH.exists() or (DEST / "session/candidates").exists():
        raise RuntimeError("R107 recovery already exists")
    plan = json.loads(ORIGINAL_PATH.read_text())
    if len(plan.get("revised_operational_plans", [])) != 1:
        raise RuntimeError("recovery requires exactly one operational plan")
    selected = plan["revised_operational_plans"][0]
    hypothesis = plan["revision_hypothesis"]
    if selected.get("operational_plan_id") != ORIGINAL_ID or hypothesis.get("operational_plan_id") != ORIGINAL_ID:
        raise RuntimeError("original plan identity refs differ from expected")
    if hypothesis.get("parent_plan_id") != "R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001":
        raise RuntimeError("parent identity must remain unchanged")
    normalized = json.loads(json.dumps(plan))
    normalized["revised_operational_plans"][0]["operational_plan_id"] = CORRECT_ID
    normalized["revision_hypothesis"]["operational_plan_id"] = CORRECT_ID
    occurrences_old = sum(1 for _ in json.dumps(plan, ensure_ascii=False).split(ORIGINAL_ID)) - 1
    occurrences_new = sum(1 for _ in json.dumps(normalized, ensure_ascii=False).split(ORIGINAL_ID)) - 1
    if occurrences_old != 2 or occurrences_new != 0:
        raise RuntimeError(f"unexpected old-ID refs before={occurrences_old}, after={occurrences_new}")
    normalized_selected = normalized["revised_operational_plans"][0]
    normalized_selected["operational_plan_id"] = ORIGINAL_ID
    normalized["revision_hypothesis"]["operational_plan_id"] = ORIGINAL_ID
    if normalized != plan:
        raise RuntimeError("deep equality failed after temporary identity rollback")
    normalized_selected["operational_plan_id"] = CORRECT_ID
    normalized["revision_hypothesis"]["operational_plan_id"] = CORRECT_ID
    normalized_path = NORMALIZED_PATH
    normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    mapping = {
        "schema_version": "KIMIARK_R107_PROTOCOL_RECOVERY_MAPPING_V1",
        "recovery_class": "MODEL_ORIGINAL_OUTPUT_LOSSLESS_PROTOCOL_RECOVERY",
        "source_type": "MODEL_OUTPUT",
        "source_experiment": SOURCE.name,
        "source_path": ORIGINAL_PATH.relative_to(ROOT).as_posix(),
        "original_sha256": digest(ORIGINAL_PATH),
        "normalized_sha256": digest(NORMALIZED_PATH),
        "original_operational_plan_id": ORIGINAL_ID,
        "correct_operational_plan_id": CORRECT_ID,
        "correct_id_authority": "session_config_v1.json plan_id_prefix plus deterministic 001 suffix",
        "correct_id_authority_sha256": digest(SOURCE / "session_config_v1.json"),
        "changed_json_paths": [
            "$.revised_operational_plans[0].operational_plan_id",
            "$.revision_hypothesis.operational_plan_id",
        ],
        "deep_equality_check": "PASS_WITH_ONLY_DECLARED_ID_FIELDS_RESTORED",
        "old_id_ref_count_before": 2,
        "old_id_ref_count_after": 0,
        "boundary": "No operator, tile, direction, frame, skill, roster, parent, hypothesis semantics, or validation-card content changed.",
    }
    (DEST / "protocol_recovery_mapping_v1.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    authorization = {
        "schema_version": "KIMIARK_NO_MODEL_PROTOCOL_RECOVERY_AUTHORIZATION_V1",
        "provider": "NO_MODEL",
        "model": "NO_MODEL_PROTOCOL_RECOVERY",
        "reasoning_effort": "NONE",
        "features_apps": False,
        "real_cli_starts": {"authorized": 0, "used": 0},
        "model_generation": {"authorized": 0, "used": 0},
        "budget_boundary": "This authorization permits zero CLI/model requests, up to five production checks, one candidate, and one complete simulation.",
    }
    (DEST / "authorization_v1.json").write_text(json.dumps(authorization, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_",
        "plan_label": "SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE",
        "model": "NO_MODEL_PROTOCOL_RECOVERY",
        "reasoning_effort": "NONE",
        "features_apps": False,
        "execution_backend": "CONTROLLED_RUNNER",
        "allow_fake_execution": False,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "max_unique_deployed_operators": 7,
        "max_candidates": 1,
        "max_check_calls": 5,
        "simulation_timeout_seconds": 3600,
        "authorization_config_path": str((DEST / "authorization_v1.json").relative_to(ROOT)),
        "budget_path": str((DEST / "simulation_budget_v1.json").relative_to(ROOT)),
        "candidate_ledger_path": str((DEST / "candidate_ledger_v1.json").relative_to(ROOT)),
        "facts_source_dir": str((SOURCE / "input_bundle").relative_to(ROOT)),
        "session_root": str((DEST / "session").relative_to(ROOT)),
    }
    (DEST / "session_config_v1.json").write_text(json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    (DEST / "simulation_budget_v1.json").write_text(json.dumps({
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": "main_08-07",
        "max_stage_simulations": 1,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    (DEST / "candidate_ledger_v1.json").write_text(json.dumps({
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "max_candidates": 1,
        "max_check_calls": 5,
        "used_check_calls": 0,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"original_sha256": mapping["original_sha256"], "normalized_sha256": mapping["normalized_sha256"], "correct_id": CORRECT_ID}, sort_keys=True))


if __name__ == "__main__":
    main()
