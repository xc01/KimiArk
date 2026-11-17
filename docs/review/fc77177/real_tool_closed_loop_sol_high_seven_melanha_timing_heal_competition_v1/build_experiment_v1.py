#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import codex_experience_selector_v1 as selector


R107_RECOVERY = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_recovery_v1"
R107_SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_v1"
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_melanha_timing_heal_competition_v1"
BUNDLE = EXPERIMENT / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-melanha-timing-heal-competition-v1"
PLAN_PREFIX = "R108_SOL_HIGH_SEVEN_MELANHA_TIMING_HEAL_COMPETITION_"
GOAL = "Legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN; shift Melanha timing to test whether lower-lane heal competition can be reduced without losing roadblock4 clearance, #11/#13 closure, artillery closure, or #14 safety"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if any(EXPERIMENT.rglob("cli_process_attempt.json")) or (BUNDLE / "bundle_manifest_v1.json").exists():
        raise RuntimeError("R108 experiment already exists")
    BUNDLE.mkdir(parents=True)

    parent_sim = R107_RECOVERY / "session/candidates/candidate-001/simulation"
    parent_dest = BUNDLE / "parent_R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001"
    parent_dest.mkdir()
    for name in ("plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "final_status.json"):
        shutil.copyfile(parent_sim / name, parent_dest / name)

    shutil.copyfile(R107_SOURCE / "input_bundle/llm_evidence_context.json", BUNDLE / "llm_evidence_context.json")
    shutil.copyfile(R107_SOURCE / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")
    shutil.copyfile(R107_RECOVERY / "post_run_audit_v1.md", BUNDLE / "r107_recovery_post_run_audit_v1.md")
    shutil.copyfile(ROOT / "docs/review/fc77177/r106_r107_complementary_branch_comparison_v1.md", BUNDLE / "r106_r107_complementary_branch_comparison_v1.md")

    parent_identity = {
        "schema_version": "KIMIARK_R108_FIXED_PARENT_IDENTITY_MANIFEST_V1",
        "lineage_policy": "User explicitly selected the verified R107 recovery candidate as the single primary parent; R106 is evidence only.",
        "parent_candidates": [{
            "record_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001:candidate-001",
            "declared_plan_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001",
            "final_status_plan_id": "R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001",
            "plan_sha256": digest(parent_dest / "plan_snapshot.json"),
            "action_sha256": digest(parent_dest / "action_snapshot.json"),
            "events_gz_sha256": digest(parent_dest / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(parent_dest / "diagnostic_events.json.gz"),
            "operator_union_count": 7,
            "archive_status": "VERIFIED",
        }],
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", parent_identity)

    fact_pack = {
        "schema_version": "KIMIARK_R108_MELANHA_TIMING_FACT_PACK_V1",
        "boundary": "Observed fixed-simulator events only. No continuous positions, exact HP, complete heal candidate ordering, or causal necessity is asserted. Old frames are not universal deadlines.",
        "parent_r107_recovery": {
            **parent_identity["parent_candidates"][0],
            "result": {"kills": 20, "leaks": 13, "remaining_life": -11, "win": False},
            "operator_union": ["char_120_hibisc", "char_123_fang", "char_208_melan", "char_210_stward", "char_212_ansel", "char_283_midn", "char_4093_frston"],
            "validated_local_success": {
                "route_11": {"block": 2738, "death": 2881},
                "route_13": {"block": 3098, "death": 3311},
                "protected_14": {"roadblock4_block": None, "damage": None, "death": None, "reach": 12448},
            },
            "failed_local_surface": {
                "steward_death": 3970,
                "artillery_hits": {"count": 38, "damage": 11035.13, "first": 2161, "last": 3937},
                "artillery_death": None,
                "artillery_leak": 5759,
                "planned_retreat_4280": "ILLEGAL_BECAUSE_STEWARD_WAS_DEAD",
                "protected_3": {"officer23_hits": [5264, 5324, 5384], "death": 5384},
                "central_leaks": {"enemy_1110_uamord#21": 5046, "enemy_1110_uamord#22": 5359, "enemy_1110_uamord#33": 6846, "enemy_1110_uamord#34": 6996},
            },
        },
        "single_candidate_change": {
            "change": "Melanha DEPLOY 901 -> 1261; Melanha ACTIVATE_SKILL 2102 -> 2462.",
            "purpose": "Delay lower-lane deployment to reduce Melanha's early damage/heal competition while still attempting roadblock4 clearance before #14's 3030 spawn/3251 restraint window.",
            "all_other_actions": "MUST remain unchanged.",
        },
        "open_unknowns": [
            "Whether delayed Melanha still kills #5/#9 and clears roadblock4 before #14 arrives.",
            "Whether reduced Melanha heal competition changes Steward's 3970 death.",
            "Exact HP and continuous positions remain UNKNOWN.",
        ],
    }
    write_json(BUNDLE / "r108_melanha_timing_fact_pack_v1.json", fact_pack)

    store = ROOT / "output/codex_experience_selector_v1/experience_records.jsonl"
    records = selector.load_store(store)
    if len(records) != 24:
        raise RuntimeError(f"expected verified 24-record store, got {len(records)}")
    rebuild = BUNDLE / "experience_records.rebuild_check.jsonl"
    report = selector.rebuild_store(store, rebuild)
    if report["missing_from_rebuild"] or any(item.get("error") for item in report["issues"]):
        raise RuntimeError(f"selector rebuild failed: {report}")
    if selector.load_store(rebuild) != records:
        raise RuntimeError("selector rebuild is not record identical")
    payload, omitted = selector.build_context(
        records,
        goal=GOAL,
        k=7,
        target_tags={"ARTILLERY_KILL", "PROTECTED_ROUTE", "ROADBLOCK_CLEARANCE", "SUPPORT_DELIVERY", "CENTRAL_INTERCEPT"},
        byte_limit=28_000,
    )
    context_path = BUNDLE / "experience_selector_context_v1.json"
    context_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    selector_state = {
        "schema_version": "KIMIARK_R108_SELECTOR_STATE_V1",
        "selector_code_sha256": digest(ROOT / "scripts/codex_experience_selector_v1.py"),
        "selector_store_sha256": digest(store),
        "selector_import_report_sha256": digest(ROOT / "output/codex_experience_selector_v1/experience_records.import_report.json"),
        "rebuild_report": report,
        "record_count": len(records),
        "goal": GOAL,
        "requested_k": 7,
        "context_sha256": digest(context_path),
        "context_bytes": context_path.stat().st_size,
        "context_omitted": omitted,
    }
    write_json(BUNDLE / "experience_selector_state_v1.json", selector_state)

    prompt = f"""Use the fixed parent `R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001:candidate-001` from `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_melanha_timing_heal_competition_v1/input_bundle/parent_R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001/`. Verify its plan/action/events hashes from `input_bundle/parent_identity_manifest_v1.json`. Read the fact pack, selector context, catalog evidence, R106/R107 comparison, and R107 recovery audit. The proven parent preserves #11/#13 and #14 safety but loses Steward@3970, artillery closure, and #3.

Primary question: test one concrete timing change. Change only Melanha DEPLOY 901 -> 1261 and Melanha ACTIVATE_SKILL 2102 -> 2462. Keep every other operator, tile, direction, frame, skill, retreat, deploy, roster, parent identity, and validation-card semantic unchanged. Do not add an eighth operator. Do not splice success windows.

The candidate must use plan id `{PLAN_PREFIX}001`. K remains selected/deployed union <=7, robots included, same-ID redeploy counted once. Use only production MCP tools: get_session_status, check_plan, run_simulation, query_events. Run one check and one complete simulation. Do not create a second candidate. Query earliest failures and all relevant chains before closing.

Before check, write a visible validation card and experience_selector_decision_record in the revised plan. Record the verified R107 recovery parent hashes, referenced and non-applicable experiences, the exact two-frame diff, expected roadblock4/#5/#9/#14/Steward/artillery/#3/central outcomes, and regression risks. Separate prediction from observation. Do not claim WIN before complete settlement. If the delayed Melanha misses roadblock4 or creates an earlier leak, report that as event evidence, not a general statement that seven IDs are impossible. M70 remains the eight-ID WIN; seven-or-fewer feasibility remains UNKNOWN unless this run proves a complete simulator WIN.
"""
    attempt_dir = EXPERIMENT / "session/codex_cli"
    attempt_dir.mkdir(parents=True)
    prompt_path = attempt_dir / "sol_prompt_v1.txt"
    prompt_path.write_text(prompt + "\n", encoding="utf-8")

    session_config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "execution_backend": "CONTROLLED_RUNNER",
        "allow_fake_execution": False,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "max_real_cli_starts": 1,
        "max_check_calls": 5,
        "max_candidates": 1,
        "max_unique_deployed_operators": 7,
        "simulation_timeout_seconds": 3600,
        "plan_id_prefix": PLAN_PREFIX,
        "plan_label": "SOL_HIGH_SEVEN_MELANHA_TIMING_HEAL_COMPETITION",
        "authorization_config_path": str(EXPERIMENT / "model_authorization_v1.json"),
        "budget_path": str(EXPERIMENT / "simulation_budget_v1.json"),
        "candidate_ledger_path": str(EXPERIMENT / "candidate_ledger_v1.json"),
        "facts_source_dir": str(BUNDLE),
        "session_root": str(EXPERIMENT / "session"),
    }
    write_json(EXPERIMENT / "session_config_v1.json", session_config)

    authorization = {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "provider": "openai",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "budget_boundary": "User authorized one fresh Sol CLI with up to five checks, one candidate, and one complete simulation; prior ledgers remain closed.",
        "extra_config_values": [
            f'mcp_servers.kimiark.command="{ROOT / ".venv/bin/python"}"',
            f'mcp_servers.kimiark.args=["{ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"}", "{EXPERIMENT / "session_config_v1.json"}"]',
            'mcp_servers.kimiark.enabled=true',
            'mcp_servers.kimiark.required=true',
            'mcp_servers.kimiark.default_tools_approval_mode="approve"',
            'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]',
        ],
        "real_cli_starts": {
            "authorized_real_cli_starts": 1,
            "used_real_cli_starts": 0,
            "automatic_retry": False,
            "automatic_resume": False,
            "model_change_or_tier_change_forbidden": True,
        },
    }
    write_json(EXPERIMENT / "model_authorization_v1.json", authorization)
    write_json(EXPERIMENT / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": "main_08-07",
        "max_stage_simulations": 1,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(EXPERIMENT / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "max_check_calls": 5,
        "max_candidates": 1,
        "used_check_calls": 0,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    })

    manifest = {"schema_version": "KIMIARK_R108_INPUT_BUNDLE_MANIFEST_V1", "files": []}
    for path in sorted(path for path in BUNDLE.rglob("*") if path.is_file() and path.name != "bundle_manifest_v1.json"):
        entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = restored_digest(path)
        manifest["files"].append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", manifest)

    run_script = EXPERIMENT / "run_real_cli_v1.py"
    source = R107_SOURCE / "run_real_cli_v1.py"
    text = source.read_text(encoding="utf-8")
    text = text.replace("real_tool_closed_loop_sol_high_seven_protected14_late_release_v1", EXPERIMENT.name)
    run_script.write_text(text, encoding="utf-8")
    run_script.chmod(0o755)

    print(json.dumps({
        "experiment": EXPERIMENT.name,
        "parent": parent_identity["parent_candidates"][0]["record_id"],
        "records": len(records),
        "context_bytes": selector_state["context_bytes"],
        "omitted": omitted,
        "prompt_bytes": prompt_path.stat().st_size,
        "suggested_parent_ids": [item["record_id"] for item in payload["parent_candidates"]],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
