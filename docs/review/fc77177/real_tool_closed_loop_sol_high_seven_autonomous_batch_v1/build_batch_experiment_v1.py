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
R108_DETERMINISTIC = ROOT / "docs/review/fc77177/real_tool_closed_loop_deterministic_seven_melanha_timing_v1"
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_autonomous_batch_v1"
BUNDLE = EXPERIMENT / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-autonomous-batch-v1"
PLAN_PREFIX = "R109_SOL_HIGH_SEVEN_AUTONOMOUS_BATCH_"
GOAL = "Legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN; autonomously build and revise up to five candidates while preserving verified route/artillery/protected/central duties where evidence supports them"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if any(EXPERIMENT.rglob("cli_process_attempt.json")) or (BUNDLE / "bundle_manifest_v1.json").exists():
        raise RuntimeError("R109 autonomous batch experiment already exists")
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
    shutil.copyfile(R108_DETERMINISTIC / "static_semantics_diagnosis_v1.json", BUNDLE / "r108_static_semantics_diagnosis_v1.json")
    shutil.copyfile(R108_DETERMINISTIC / "derived_stable_sort/normalized_stable_sort_candidate_plan_v1.json", BUNDLE / "r108_normalized_stable_sort_candidate_plan_v1.json")

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
        "schema_version": "KIMIARK_R109_AUTONOMOUS_BATCH_FACT_PACK_V1",
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
        "known_local_branches": {
            "R104": "Seven-ID artillery-closed deterministic branch; complete LOSS but reusable as evidence.",
            "R106": "Seven-ID route+artillery local-success branch; complete LOSS with #14@3911 and four central leaks.",
            "R107_recovery": "Seven-ID #14-safety and #11/#13 closure branch; Steward/artillery/#3/central failures.",
            "M70": "Eight-ID complete fixed-simulator WIN; reduction reference only, never report as seven-ID candidate."
        },
        "r108_static_precheck": {
            "two_frame_pair": "Melanha DEPLOY 901->1261 and ACTIVATE_SKILL 2102->2462 was rejected before candidate creation.",
            "stable_sort_fact": "Frame ordering is a real semantic contract; stable sorting resolves it without changing action objects.",
            "sp_fact": "At 3903, actual post-activation SP was 28.0667 while the static display 88.0667 was cumulative since deploy; the cooldown branch also refused it.",
            "coupled_phase_option": "Shifting all seven Melanha skills +360 preserves relative intervals and is one possible, untested candidate; it is not presumed tactically effective."
        },
        "open_unknowns": [
            "Whether any static-legal Melanha phase shift preserves lower-lane duties and changes heal competition.",
            "How to combine route closure, roadblock4/#14 safety, Steward/artillery support, #3, and central closure within seven IDs.",
            "Exact HP and continuous positions remain UNKNOWN unless events record them."
        ]
    }
    write_json(BUNDLE / "r109_autonomous_batch_fact_pack_v1.json", fact_pack)

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
        byte_limit=32_000,
    )
    context_path = BUNDLE / "experience_selector_context_v1.json"
    context_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    selector_state = {
        "schema_version": "KIMIARK_R109_SELECTOR_STATE_V1",
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

    prompt = f"""You are running one autonomous closed-loop batch. Verify the fixed cold-start parent `R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001:candidate-001` from `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_autonomous_batch_v1/input_bundle/parent_R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001/` using `input_bundle/parent_identity_manifest_v1.json`. Read the selector context, batch fact pack, catalog evidence, R106/R107 comparison, R107 recovery audit, and R108 static-semantics diagnosis.

Your objective is a legal ordinary-mode 1-3-star, selected/deployed union <=7, zero-leak, dual-protected-target, all-enemies-settled complete fixed-simulator WIN. You may freely revise the parent's roles, tiles, directions, timings, skills, retreats/redeploys, and action list as long as K<=7 and every action is legal. Do not splice untested windows as proof. Keep established duties only where evidence supports them; explicitly record any trade-off.

Use only production MCP tools: get_session_status, check_plan, run_simulation, query_events. Budget is one CLI, up to 30 checks, 5 candidates, and 5 complete simulations. A failed check consumes only a check; only PASS creates/consumes a candidate slot. Read status before and after calls, never reset or fake counters. Candidate plan IDs are `{PLAN_PREFIX}001` through `{PLAN_PREFIX}005` in order.

For each candidate: record a short validation card and experience_selector_decision_record, choose/justify parent lineage, state the mechanism hypothesis and expected events, make a concrete diff, then check. If a contract/static error occurs, read the full error, correct serialization/SP/cooldown/cost/tile/plan-ID fields, stable-sort when needed, and check again in this same CLI. After each PASS, run exactly one complete simulation and query the earliest and independent failures, route/roadblock/#14, #11/#13, Steward/artillery, protected #3, and central closure. Preserve partial evidence and choose the next candidate from actual events; you may return to a better earlier parent instead of compounding a loss.

Before every check, separate prediction from observation and do not claim WIN before full settlement. If evidence supports a complete seven-ID WIN, stop immediately. If the budget is exhausted, the CLI would have to end, or no distinct testable mechanism remains, close with a concise result report and explicit remaining UNKNOWNs. Do not report M70 as a seven-ID candidate; it is only an eight-ID WIN reference. Do not claim real-game, faithful, robust, probabilistic WIN, seven-ID impossibility, or global minimality.
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
        "max_check_calls": 30,
        "max_candidates": 5,
        "max_unique_deployed_operators": 7,
        "simulation_timeout_seconds": 3600,
        "plan_id_prefix": PLAN_PREFIX,
        "plan_label": "SOL_HIGH_SEVEN_AUTONOMOUS_BATCH",
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
        "budget_boundary": "User authorized one fresh Sol CLI with up to thirty checks, five candidates, and five complete simulations; prior ledgers remain closed.",
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
        "max_stage_simulations": 5,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(EXPERIMENT / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "max_check_calls": 30,
        "max_candidates": 5,
        "used_check_calls": 0,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    })

    manifest = {"schema_version": "KIMIARK_R109_INPUT_BUNDLE_MANIFEST_V1", "files": []}
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
