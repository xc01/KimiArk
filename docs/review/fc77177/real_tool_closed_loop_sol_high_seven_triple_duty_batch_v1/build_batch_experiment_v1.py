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


R106 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1"
R107_RECOVERY = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_recovery_v1"
R109 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_autonomous_batch_v1"
R107_SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_v1"
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_triple_duty_batch_v1"
BUNDLE = EXPERIMENT / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-triple-duty-batch-v1"
PLAN_PREFIX = "R110_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_"
GOAL = "Legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN while first proving the joint #11/#13 closure, protected #14 reach, and real artillery kill without artillery leak"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def copy_parent(source: Path, destination: Path) -> None:
    destination.mkdir(exist_ok=True)
    for name in ("plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "final_status.json"):
        shutil.copyfile(source / name, destination / name)


def parent_entry(label: str, source: Path, archive: Path) -> dict:
    return {
        "role": label,
        "plan_id": None,
        "record_id": None,
        "plan_sha256": digest(source / "plan_snapshot.json"),
        "action_sha256": digest(source / "action_snapshot.json"),
        "events_gz_sha256": digest(source / "diagnostic_events.json.gz"),
        "events_restored_sha256": restored_digest(source / "diagnostic_events.json.gz"),
        "relative_archive": archive.relative_to(BUNDLE).as_posix(),
    }


def main() -> None:
    if any(EXPERIMENT.rglob("cli_process_attempt.json")) or (BUNDLE / "bundle_manifest_v1.json").exists():
        raise RuntimeError("R110 triple-duty batch experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)

    r106_dest = BUNDLE / "parent_R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001"
    c5_dest = BUNDLE / "reference_R109_SOL_HIGH_SEVEN_AUTONOMOUS_BATCH_005"
    r107_dest = BUNDLE / "reference_R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_001"
    copy_parent(R106 / "session/candidates/candidate-001/simulation", r106_dest)
    copy_parent(R109 / "session/candidates/candidate-005/simulation", c5_dest)
    copy_parent(R107_RECOVERY / "session/candidates/candidate-001/simulation", r107_dest)

    r106_plan = r106_dest / "plan_snapshot.json"
    c5_plan = c5_dest / "plan_snapshot.json"
    r107_plan = r107_dest / "plan_snapshot.json"
    r106_payload = __import__("json").loads(r106_plan.read_text())
    c5_payload = __import__("json").loads(c5_plan.read_text())
    r107_payload = __import__("json").loads(r107_plan.read_text())
    r106_entry = parent_entry("DEFAULT_PRIMARY", r106_dest, r106_dest)
    c5_entry = parent_entry("REFERENCE", c5_dest, c5_dest)
    r107_entry = parent_entry("REFERENCE", r107_dest, r107_dest)
    r106_entry.update(plan_id=r106_payload["operational_plan_id"], record_id=f"{r106_payload['operational_plan_id']}:candidate-001")
    c5_entry.update(plan_id=c5_payload["operational_plan_id"], record_id=f"{c5_payload['operational_plan_id']}:candidate-005")
    r107_entry.update(plan_id=r107_payload["operational_plan_id"], record_id=f"{r107_payload['operational_plan_id']}:candidate-001")
    parent_identity = {
        "schema_version": "KIMIARK_R110_DUAL_PARENT_IDENTITY_MANIFEST_V1",
        "selection_policy": "R106 is the default primary parent because it observed route+artillery closure. C5 may replace it only when event evidence supports rebuilding artillery more directly; R107 recovery is a route/#14 reference.",
        "default_primary_parent": r106_entry,
        "reference_parents": [c5_entry, r107_entry],
        "identity_boundary": "Hashes verify archived identity, not remote-model identity or causal sufficiency.",
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", parent_identity)

    shutil.copyfile(R106 / "input_bundle/llm_evidence_context.json", BUNDLE / "llm_evidence_context.json")
    shutil.copyfile(R106 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")
    shutil.copyfile(R106 / "closeout_report_v1.json", BUNDLE / "r106_closeout_report_v1.json")
    shutil.copyfile(ROOT / "docs/review/fc77177/r106_r107_complementary_branch_comparison_v1.md", BUNDLE / "r106_r107_complementary_branch_comparison_v1.md")
    shutil.copyfile(R107_RECOVERY / "post_run_audit_v1.md", BUNDLE / "r107_recovery_post_run_audit_v1.md")
    shutil.copyfile(R109 / "closeout_report_v1.json", BUNDLE / "r109_closeout_report_v1.json")

    fact_pack = {
        "schema_version": "KIMIARK_R110_TRIPLE_DUTY_FACT_PACK_V1",
        "boundary": "Observed fixed-simulator events only. No continuous positions, exact HP, complete heal ordering, or causal necessity is asserted. Old frames are not universal deadlines.",
        "question": "Can one legal K<=7 plan preserve #11/#13 interception kills, protected #14 reach, and a real artillery kill with no artillery leak?",
        "r106_default_parent": {
            **r106_entry,
            "selected_operator_ids": r106_payload["selected_low_star_operator_ids"],
            "result": {"kills": 22, "leaks": 11, "remaining_life": -9, "win": False},
            "observed_local_success": {
                "route_11": {"block": 2738, "death": 2881},
                "route_13": {"block": 3098, "death": 3311},
                "steward_survived_3911": True,
                "retreat_4280": "OBSERVED_LEGAL",
                "artillery_death": 4273,
                "artillery_hits": 45,
                "artillery_damage": 13227.21,
            },
            "observed_failures": {
                "protected_14_death": 3911,
                "protected_3_reach": 15549,
                "central_leaks": {"enemy_1110_uamord#21": 6697, "enemy_1110_uamord#22": 6661, "enemy_1110_uamord#33": 6846, "enemy_1110_uamord#34": 6996},
            },
        },
        "r109_c5_reference": {
            **c5_entry,
            "selected_operator_ids": c5_payload["selected_low_star_operator_ids"],
            "result": {"kills": 20, "leaks": 13, "remaining_life": -10, "win": False},
            "observed_local_success": {
                "route_11_died": True,
                "route_13_died": True,
                "protected_14_reach": 12448,
            },
            "observed_failures": {
                "friston_death": 1479,
                "steward_death": 2923,
                "fang_death": 4751,
                "midnight_death": 4903,
                "spot_death": 5003,
                "artillery_death": None,
                "artillery_steward_hits": 16,
                "artillery_steward_damage": 4658.17,
                "artillery_leak": 5759,
                "protected_3_death": 5353,
                "central_leaks": {"enemy_1110_uamord#21": 5150, "enemy_1110_uamord#22": 5336, "enemy_1110_uamord#33": 6846, "enemy_1110_uamord#34": 6996},
            },
        },
        "r107_recovery_reference": {
            **r107_entry,
            "selected_operator_ids": r107_payload["selected_low_star_operator_ids"],
            "result": {"kills": 20, "leaks": 13, "remaining_life": -11, "win": False},
            "observed_local_success": {"route_11": {"block": 2738, "death": 2881}, "route_13": {"block": 3098, "death": 3311}, "protected_14_reach": 12448},
            "observed_failures": {"steward_death": 3970, "artillery_leak": 5759, "protected_3_death": 5384},
        },
        "mandatory_final_verification": "Even if the named triple succeeds, complete WIN requires zero leaks, both protected targets safe/reached, all enemies settled, no active enemies, and simulator WIN.",
        "open_unknowns": ["Exact HP, continuous positions, complete heal candidate ordering, and causal necessity remain UNKNOWN unless recorded by events."],
    }
    write_json(BUNDLE / "r110_triple_duty_fact_pack_v1.json", fact_pack)

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
        "schema_version": "KIMIARK_R110_SELECTOR_STATE_V1",
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

    prompt = f"""You are running one autonomous closed-loop batch for the narrow triple-duty question. Verify archived identities from `input_bundle/parent_identity_manifest_v1.json`: default primary R106 `{r106_entry['record_id']}`, reference C5 `{c5_entry['record_id']}`, and reference R107 recovery `{r107_entry['record_id']}`. Read the selector context, fact pack, catalog evidence, R106 closeout, R109 closeout, R106/R107 comparison, and R107 recovery audit. Compare R106 and C5 actions/events before designing the first candidate; identify the earliest observed duty divergence and state why each retained success should still hold in the new geometry.

The objective is legal ordinary-mode 1-3-star, selected/deployed union <=7, zero-leak, dual-protected-target, all-enemies-settled complete fixed-simulator WIN. The required intermediate target is: #11 and #13 blocked and killed, protected #14 reached, and artillery actually killed rather than leaked. Default from R106 and preserve its observed artillery chain while fixing protected #14's route/exposure. If C5 provides a more direct path to rebuild artillery, you may switch parent, but must justify it from actions/events and preserve route/#14 duties.

Use only production MCP tools: get_session_status, check_plan, run_simulation, query_events. Budget is one CLI, up to 20 checks, 3 candidates, and 3 complete simulations. A failed check consumes only a check; only PASS creates/consumes a candidate slot. Read status before and after calls, never reset or fake counters. Candidate plan IDs are `{PLAN_PREFIX}001` through `{PLAN_PREFIX}003` in order.

For each candidate: write a short validation card and experience_selector_decision_record, state the parent/hash, the event to change, the local successes to preserve, mechanism hypothesis, concrete diff, and expected observables. If contract/static errors occur, read the full error and correct serialization/frame order/plan ID/DP/SP/cooldown/cost/tile/deploy-retreat coupling in this same CLI. After each PASS, run exactly one complete simulation and query the earliest and independent failures, #11/#13, roadblock4/#14, Steward/artillery, #3, and central #21/#22/#33/#34. Candidate 2 and 3 must target the previous run's earliest acceptance-breaking event and explain the transmission path; you may return to a better parent rather than compounding a loss.

Separate prediction from observation; do not call the triple proven until all named events are observed. Do not treat #3@5353 as a new fixed deadline. If evidence supports a complete seven-ID WIN, stop immediately. If budget is exhausted or no distinct testable mechanism remains, close concisely and explicitly. M70 is only an eight-ID WIN reference. Do not claim real-game, faithful, robust, probabilistic WIN, seven-ID impossibility, or global minimality.
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
        "max_check_calls": 20,
        "max_candidates": 3,
        "max_unique_deployed_operators": 7,
        "simulation_timeout_seconds": 3600,
        "plan_id_prefix": PLAN_PREFIX,
        "plan_label": "SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH",
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
        "budget_boundary": "User authorized one fresh Sol CLI with up to twenty checks, three candidates, and three complete simulations; prior ledgers remain closed.",
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
        "max_stage_simulations": 3,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(EXPERIMENT / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "max_check_calls": 20,
        "max_candidates": 3,
        "used_check_calls": 0,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    })

    manifest = {"schema_version": "KIMIARK_R110_INPUT_BUNDLE_MANIFEST_V1", "files": []}
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

    print(__import__("json").dumps({
        "experiment": EXPERIMENT.name,
        "default_parent": r106_entry["record_id"],
        "reference_parents": [c5_entry["record_id"], r107_entry["record_id"]],
        "records": len(records),
        "context_bytes": selector_state["context_bytes"],
        "omitted": omitted,
        "prompt_bytes": prompt_path.stat().st_size,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
