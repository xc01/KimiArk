#!/usr/bin/env python3
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FACTS = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m74_open_reduction_feedback_v1/candidate_v4"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_cold_start_v1/cold_start_input_bundle"
ROOT_PLAN_ID = "KIMIARK_COLD_START_ASTRA_HIGH_MAIN_08_07_V1"
ROOT_EXPERIENCE_ID = "KIMIARK_COLD_START_ASTRA_HIGH_MAIN_08_07_ROOT_V1"


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def file_record(path: Path) -> dict:
    return {
        "bytes": path.stat().st_size,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    evidence = json.loads((SOURCE_FACTS / "llm_evidence_context.json").read_text(encoding="utf-8"))
    for key in (
        "previous_plan_to_revise",
        "prior_diagnostic_feedback",
        "prior_execution_interruptions",
        "prior_static_feedback",
        "prior_tactical_feedback",
        "tactical_experience",
    ):
        evidence.pop(key, None)

    evidence["milestone"] = "MAIN_08_07_ASTRA_HIGH_COLD_START_V1"
    evidence["m58_open_roster_policy"]["max_unique_deployed_operator_ids"] = 7
    evidence["m58_open_roster_policy"]["simulation_policy"] = (
        "AT_MOST_ONE_FIXED_FULL_STAGE_SIMULATION_PER_CHECKED_CANDIDATE_VIA_MCP_RUN_SIMULATION"
    )
    evidence["codex_cli_run_policy"] = {
        "automatic_resume": False,
        "automatic_retry": False,
        "process_starts": 1,
        "readonly_query_helpers": True,
        "source_modification": "FORBIDDEN",
        "shell_stage_simulation": "FORBIDDEN",
        "mcp_stage_simulation": "AUTHORIZED_CONTROLLED_RUNNER_ONLY_AFTER_CHECK_PASS",
    }
    evidence["decision_task"] = {
        "deliverable": "one compact OperationalPlan JSON only",
        "forbidden": "No default roster, prior action timeline, automatic controller, mechanism rewrite, unverified pre-swing lock, instant redeploy, death refund, or hidden action repair.",
        "must_cover": "all routes, simultaneous coverage demands, protected passage, key enemy closure, and final WIN condition",
        "objective": "build a complete fixed-simulator WIN with at most 7 distinct deployed operator IDs from the ordinary 1-3-star catalog",
        "priorities": [
            "derive required simultaneous tasks from routes, enemies, and economy",
            "compare at least three substantive structures before selecting one",
            "assign explicit roles, replacements, resource sources, and survival dependencies",
            "recompute every target, projectile, healing, blocking, and survival window from supplied facts"
        ],
    }
    evidence["cold_start_context_policy"] = {
        "schema_version": "KIMIARK_COLD_START_CONTEXT_POLICY_V1",
        "bundled_prior_tactical_plans": [],
        "bundled_prior_failure_summaries": [],
        "bundled_default_rosters": [],
        "historical_access": "Use only history_access_index_v1.json records; proactive reading is allowed and must be logged.",
        "historical_use_boundary": "Historical material is evidence, not a default solution or a current deadline.",
    }
    evidence["cold_start_task_root"] = {
        "schema_version": "KIMIARK_COLD_START_TASK_ROOT_V1",
        "root_plan_id": ROOT_PLAN_ID,
        "root_experience_id": ROOT_EXPERIENCE_ID,
        "stage_id": evidence["stage_id"],
        "mechanics_version": evidence["mechanics_version"],
        "source": "user-authorized independent cold-start experiment",
        "prior_tactical_parent": None,
    }
    evidence["tactical_experience"] = {
        "schema_version": "KIMIARK_TACTICAL_EXPERIENCE_RECORD_V2",
        "records": [{
            "experience_id": ROOT_EXPERIENCE_ID,
            "scope": {
                "mechanics_version": evidence["mechanics_version"],
                "stage_id": evidence["stage_id"],
            },
            "summary": "Authorized cold-start task root; contains no prior tactical plan, roster, action, or outcome.",
            "source": "cold_start_input_bundle/llm_evidence_context.json",
        }],
        "retrieval_limit": 0,
        "usage_policy": [
            "Use only experience_id values listed in records.",
            "This is a task-root authorization, not prior battle evidence.",
            "A VERIFIED prediction only confirms its declared observable event; it does not prove the full plan."
        ],
    }
    evidence["provenance"] = {
        "generator": "scripts/build_astra_high_cold_start_bundle_v1.py",
        "active_facts_source": file_record(SOURCE_FACTS / "llm_evidence_context.json"),
        "omitted_source_fields": [
            "previous_plan_to_revise",
            "prior_diagnostic_feedback",
            "prior_execution_interruptions",
            "prior_static_feedback",
            "prior_tactical_feedback",
        ],
        "operator_facts": file_record(ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json"),
        "operator_support": file_record(ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json"),
        "raw_level": file_record(ROOT / "data/ArknightsGameData/zh_CN/gamedata/levels/obt/main/level_main_08-07.json"),
    }

    history_index = {
        "schema_version": "KIMIARK_NEUTRAL_HISTORY_ACCESS_INDEX_V1",
        "usage_policy": [
            "Reading is optional.",
            "Records provide no roster, action, comparison, or outcome summary here.",
            "If used for a new revision, record which record was read and what evidence supports the change.",
        ],
        "records": [
            {"record_id": "m70_full_roster_attempt_01", "path": "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic"},
            {"record_id": "real_tool_astra_high_v1", "path": "docs/review/fc77177/real_tool_closed_loop_astra_high_v1"},
            {"record_id": "real_tool_sol_high_v1", "path": "docs/review/fc77177/real_tool_closed_loop_sol_high_v1"},
            {"record_id": "real_tool_terra_v3", "path": "docs/review/fc77177/real_tool_closed_loop_terra_v3"},
        ],
    }

    write_json(DEST / "llm_evidence_context.json", evidence)
    write_json(DEST / "history_access_index_v1.json", history_index)
    shutil.copyfile(SOURCE_FACTS / "revision_output_schema.json", DEST / "revision_output_schema.json")
    write_json(DEST / "bundle_manifest_v1.json", {
        "schema_version": "KIMIARK_COLD_START_BUNDLE_MANIFEST_V1",
        "files": [
            file_record(DEST / "llm_evidence_context.json"),
            file_record(DEST / "history_access_index_v1.json"),
            file_record(SOURCE_FACTS / "revision_output_schema.json"),
        ],
        "root_plan_id": ROOT_PLAN_ID,
        "root_experience_id": ROOT_EXPERIENCE_ID,
    })
    print(json.dumps({"dest": str(DEST), "root_plan_id": ROOT_PLAN_ID}))


if __name__ == "__main__":
    main()
