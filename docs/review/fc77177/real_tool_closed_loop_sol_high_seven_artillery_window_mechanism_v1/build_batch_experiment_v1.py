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


R106_BUNDLE = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_triple_duty_batch_v1/input_bundle/parent_R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001"
R106_SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1/session/candidates/candidate-001/simulation"
R110 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_triple_duty_batch_v1"
R110_C1 = R110 / "session/candidates/candidate-001/simulation"
R110_C2 = R110 / "session/candidates/candidate-002/simulation"
R110_C2_SOURCE = R110 / "session/candidates/candidate-002/source"
R111_ARTILLERY = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_gap_v1"
R111_C1 = R111_ARTILLERY / "session/candidates/candidate-001/simulation"
R107_SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_v1"
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_window_mechanism_v1"
BUNDLE = EXPERIMENT / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-artillery-window-mechanism-v1"
PLAN_PREFIX = "R112_SOL_HIGH_SEVEN_ARTILLERY_WINDOW_"
GOAL = "Legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN; first prove #11/#13 plus roadblock4 plus protected #14 reach plus real artillery kill with no artillery leak"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def copy_candidate(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "diagnostic_summary.json.gz", "final_status.json"):
        shutil.copyfile(source / name, destination / name)


def parent_entry(role: str, source: Path, record_id: str) -> dict:
    plan = json.loads((source / "plan_snapshot.json").read_text())
    return {
        "role": role,
        "record_id": record_id,
        "plan_id": plan["operational_plan_id"],
        "plan_sha256": digest(source / "plan_snapshot.json"),
        "action_sha256": digest(source / "action_snapshot.json"),
        "events_gz_sha256": digest(source / "diagnostic_events.json.gz"),
        "events_restored_sha256": restored_digest(source / "diagnostic_events.json.gz"),
        "summary_gz_sha256": digest(source / "diagnostic_summary.json.gz"),
        "summary_restored_sha256": restored_digest(source / "diagnostic_summary.json.gz"),
        "selected_operator_ids": plan["selected_low_star_operator_ids"],
        "relative_archive": source.relative_to(BUNDLE).as_posix(),
    }


def main() -> None:
    if any(EXPERIMENT.rglob("cli_process_attempt.json")) or (BUNDLE / "bundle_manifest_v1.json").exists():
        raise RuntimeError("R112 artillery-window batch experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)

    if not (R106_BUNDLE / "diagnostic_summary.json.gz").exists():
        shutil.copyfile(R106_SOURCE / "diagnostic_summary.json.gz", R106_BUNDLE / "diagnostic_summary.json.gz")

    r106_dest = BUNDLE / "reference_R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001"
    c1_dest = BUNDLE / "reference_R110_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_001"
    c2_dest = BUNDLE / "default_parent_R110_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_002"
    copy_candidate(R106_BUNDLE, r106_dest)
    copy_candidate(R110_C1, c1_dest)
    copy_candidate(R110_C2, c2_dest)
    r111_dest = BUNDLE / "reference_R111_SOL_HIGH_SEVEN_ARTILLERY_GAP_001"
    copy_candidate(R111_C1, r111_dest)

    r106_entry = parent_entry("REFERENCE", r106_dest, "R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001:candidate-001")
    c1_entry = parent_entry("REFERENCE", c1_dest, "R110_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_001:candidate-001")
    c2_entry = parent_entry("DEFAULT_PRIMARY", c2_dest, "R110_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_002:candidate-002")
    r111_entry = parent_entry("REFERENCE", r111_dest, "R111_SOL_HIGH_SEVEN_ARTILLERY_GAP_001:candidate-001")
    parent_identity = {
        "schema_version": "KIMIARK_R112_ARTILLERY_WINDOW_PARENT_IDENTITY_V1",
        "selection_policy": "R110 C2 is the default primary parent because it preserves #11/#13, roadblock4, and #14; R110 C1, R106, and R111 C001 are event references for shell-by-shell Steward/artillery alignment.",
        "default_primary_parent": c2_entry,
        "reference_parents": [c1_entry, r106_entry, r111_entry],
        "identity_boundary": "Hashes verify archived identity, not remote-model identity or causal sufficiency.",
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", parent_identity)

    shutil.copyfile(R110_C2_SOURCE / "llm_evidence_context.json", BUNDLE / "llm_evidence_context.json")
    shutil.copyfile(R110_C2_SOURCE / "revision_output_schema.json", BUNDLE / "revision_output_schema.json")
    r110_closeout = json.loads((R110 / "closeout_report_v1.json").read_text())
    r106_closeout = json.loads((ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1/closeout_report_v1.json").read_text())
    write_json(BUNDLE / "r106_closeout_v1.json", r106_closeout)
    write_json(BUNDLE / "r110_closeout_v1.json", r110_closeout)
    shutil.copyfile(ROOT / "docs/review/fc77177/r106_r107_complementary_branch_comparison_v1.md", BUNDLE / "r106_r107_complementary_branch_comparison_v1.md")

    fact_pack = {
        "schema_version": "KIMIARK_R112_ARTILLERY_WINDOW_FACT_PACK_V1",
        "boundary": "Observed fixed-simulator events only. No continuous positions, exact HP, complete heal candidate ordering, or causal necessity is asserted unless directly recorded. Old frames are not universal deadlines.",
        "question": "Preserve R110 C2's #11/#13 kills and protected #14 reach while actually killing artillery with no artillery leak.",
        "r110_c2_default_parent": {
            **c2_entry,
            "result": {"kills": 21, "leaks": 12, "remaining_life": -10, "win": False},
            "retained_successes": {
                "route_11": {"block": 2738, "death": 2881},
                "route_13": {"block": 3098, "death": 3311},
                "roadblock4_destroy": 2026,
                "protected_14_reach": 12448,
            },
            "artillery_gap": {
                "steward_first_artillery_damage": 2161,
                "steward_last_artillery_damage": 3889,
                "steward_hit_count": 37,
                "steward_damage_total": 10786.03,
                "steward_death": 3911,
                "steward_death_shell": {"frame": 3911, "amount": 910, "locked_position": [7, 5]},
                "artillery_death": None,
                "artillery_leak": 5759,
                "no_retreat_or_target_switch_before_death": True,
            },
            "observed_heal_and_exposure_chain": {
                "hibiscus_deaths_in_r110": {"c1": 3311, "c2": 3461},
                "hibiscus_shell_frames": [3011, 3161, 3311, 3461],
                "c1_heal_at_3288": {"target": "char_123_fang", "amount": 420.0, "hibiscus_death": 3311},
                "c2_heal_at_3288": {"target": "char_120_hibisc", "amount": 475.9, "hibiscus_survived_3311": True},
                "c2_heal_at_3460": {"target": "char_123_fang", "amount": 420.0, "hibiscus_death": 3461},
                "late_steward_heals_before_death": {
                    "r106": [{"frame": 3611, "source": "char_212_ansel"}, {"frame": 3697, "source": "char_212_ansel"}, {"frame": 3783, "source": "char_212_ansel"}, {"frame": 3804, "source": "char_120_hibisc"}, {"frame": 3869, "source": "char_212_ansel"}],
                    "r110_c1": [{"frame": 3692, "source": "char_212_ansel"}, {"frame": 3778, "source": "char_212_ansel"}, {"frame": 3864, "source": "char_212_ansel"}, {"frame": 3950, "source": "char_212_ansel", "note": "after Steward@3970 death? frame ordering must be interpreted against recorded death@3970"}],
                    "r110_c2": [{"frame": 3611, "source": "char_212_ansel"}, {"frame": 3697, "source": "char_212_ansel"}, {"frame": 3783, "source": "char_212_ansel"}, {"frame": 3869, "source": "char_212_ansel"}],
                },
                "c1_vs_c2_other_effect": {"c1_enemy_19_leak": 4507, "c2_enemy_19_death": 4403},
            },
        },
        "r110_c1_reference": {
            **c1_entry,
            "result": {"kills": 20, "leaks": 13, "remaining_life": -10, "win": False},
            "retained_successes": {"route_11": {"block": 2738, "death": 2881}, "route_13": {"block": 3098, "death": 3311}, "roadblock4_destroy": 2026, "protected_14_reach": 12448},
            "artillery_gap": {"steward_first_artillery_damage": 2161, "steward_last_artillery_damage": 3937, "steward_hit_count": 38, "steward_damage_total": 11035.13, "steward_death": 3970, "artillery_leak": 5759},
        },
        "r106_reference": {
            **r106_entry,
            "result": {"kills": 22, "leaks": 11, "remaining_life": -9, "win": False},
            "retained_successes": {"route_11": {"block": 2738, "death": 2881}, "route_13": {"block": 3098, "death": 3311}},
            "artillery_success": {"steward_first_artillery_damage": 2161, "last_artillery_damage_and_kill": 4273, "steward_hit_count": 45, "steward_damage_total": 13227.21, "steward_death": None, "artillery_leak": None},
            "r106_failures": {"protected_14_death": 3911, "protected_3_reach": 15549, "central_leaks": {"enemy_1110_uamord#21": 6697, "enemy_1110_uamord#22": 6661, "enemy_1110_uamord#33": 6846, "enemy_1110_uamord#34": 6996}},
        },
        "r111_c001_reference": {
            **r111_entry,
            "result": {"kills": 20, "leaks": 13, "remaining_life": -11, "win": False},
            "retained_successes": {"route_11": {"block": 2738, "death": 2881}, "route_13": {"block": 3098, "death": 3311}, "roadblock4_destroy": 2026, "protected_14_reach": 12448},
            "artillery_gap": {"steward_first_artillery_damage": 2161, "steward_last_artillery_damage": 3937, "steward_hit_count": 38, "steward_damage_total": 11035.13, "steward_death": 3970, "artillery_leak": 5759, "hibiscus_death": 3161},
        },
        "mandatory_final_verification": "Even if the named triple succeeds, complete WIN requires zero leaks, both protected targets safe/reached, all enemies settled, no active enemies, and simulator WIN.",
        "open_unknowns": ["Exact HP, continuous positions, complete heal candidate ordering, and causal necessity remain UNKNOWN unless recorded by events."],
    }
    write_json(BUNDLE / "r112_artillery_window_fact_pack_v1.json", fact_pack)

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
        "schema_version": "KIMIARK_R112_SELECTOR_STATE_V1",
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

    prompt = f"""You are running one autonomous closed-loop batch with the narrow artillery-window question. Verify hashes in `input_bundle/parent_identity_manifest_v1.json`: default primary `{c2_entry['record_id']}`, references `{c1_entry['record_id']}`, `{r106_entry['record_id']}`, and `{r111_entry['record_id']}`. Read the fact pack, selector context, catalog evidence, R110 closeout, R106 closeout, and R111 closeout. Before designing actions, align original events shell-by-shell across R110 C2, R110 C1, R106, and R111 C001; record the earliest relevant difference in shell birth lock, actual Steward hit, healer target, or exposure. Do not treat 3911, 3970, or 4273 as fixed deadlines for a new axis. Treat treatment competition as a hypothesis unless events support it.

The objective is legal ordinary-mode 1-3-star, selected/deployed union <=7, zero-leak, dual-protected-target, all-enemies-settled complete fixed-simulator WIN. The intermediate target is to preserve #11/#13 kills, roadblock4 destruction, protected #14 reach, and change the earliest actionable Steward/artillery window mechanism so artillery is actually killed and does not leak. Default parent is C2. The first version tests one event-supported mechanism with the smallest coherent mechanism; if Steward is alive but cannot hit, do not add healing. If the evidence points to shell death, state which exposure or delivered heal must change. You may replace a role or switch parent only with event evidence, and must specify who retains route/#4/#14 duties.

Use only production MCP tools: get_session_status, check_plan, run_simulation, query_events. Budget is one CLI, up to 10 checks, 2 candidates, and 2 complete simulations. A failed check consumes only a check; only PASS creates/consumes a candidate slot. Read status before and after calls, never reset or fake counters. Candidate plan IDs are `{PLAN_PREFIX}001` and `{PLAN_PREFIX}002` in order.

For each candidate: write a short validation card and experience_selector_decision_record with parent/hash, the exact event to change, successes to preserve, mechanism hypothesis, concrete diff, expected observables, and risks. Correct contract/static errors (plan ID, lineage, frame ordering, DP/SP, cooldown, tile, deploy/retreat coupling) in this same CLI. After each PASS, run exactly one complete simulation and query earliest/independent failures plus #11/#13, roadblock4/#14, Steward/artillery, #3, and central #21/#22/#33/#34. Candidate 2 must be chosen from candidate 1's actual events: if artillery output returns but another duty regresses, repair the earliest regression; if no predicted relevant event changes, switch to a different evidence-supported mechanism rather than tuning frames blindly. Stop after two candidates or when no distinct hypothesis remains.

Separate prediction from observation; 5759 is an old leak frame, not a deadline. Do not call the intermediate triple proven until all events are observed. If evidence supports a complete seven-ID WIN, stop immediately. Close concisely with the earliest divergence, confirmed/refuted hypotheses, preserved/regressed duties, and counters. M70 is only an eight-ID WIN reference. Do not claim real-game, faithful, robust, probabilistic WIN, seven-ID impossibility, or global minimality.
"""
    attempt_dir = EXPERIMENT / "session/codex_cli"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = attempt_dir / "sol_prompt_v1.txt"
    prompt_path.write_text(prompt.rstrip("\n") + "\n", encoding="utf-8")

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
        "max_check_calls": 10,
        "max_candidates": 2,
        "max_unique_deployed_operators": 7,
        "simulation_timeout_seconds": 3600,
        "plan_id_prefix": PLAN_PREFIX,
        "plan_label": "SOL_HIGH_SEVEN_ARTILLERY_GAP",
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
        "budget_boundary": "User authorized one fresh Sol CLI with up to ten checks, two candidates, and two complete simulations; prior ledgers remain closed.",
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
        "max_stage_simulations": 2,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(EXPERIMENT / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "max_check_calls": 10,
        "max_candidates": 2,
        "used_check_calls": 0,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    })

    manifest = {"schema_version": "KIMIARK_R112_INPUT_BUNDLE_MANIFEST_V1", "files": []}
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
        "default_parent": c2_entry["record_id"],
            "reference_parents": [c1_entry["record_id"], r106_entry["record_id"], r111_entry["record_id"]],
        "records": len(records),
        "context_bytes": selector_state["context_bytes"],
        "omitted": omitted,
        "prompt_bytes": prompt_path.stat().st_size,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
