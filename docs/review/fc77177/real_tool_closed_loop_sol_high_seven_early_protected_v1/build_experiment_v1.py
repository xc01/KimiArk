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

R104 = ROOT / "docs/review/fc77177/real_tool_closed_loop_deterministic_seven_c2_coupled_retreat_v1"
M70 = ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic"
R101 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_selector_feedback_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_early_protected_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-early-protected-v1"
PLAN_PREFIX = "R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_"
GOAL = "Legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN; preserve R104 artillery closure while repairing the earliest route and protected-#3 failures"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def selector_context() -> dict:
    store = ROOT / "output/codex_experience_selector_v1/experience_records.jsonl"
    records = selector.load_store(store)
    if len(records) != 20:
        raise RuntimeError(f"expected verified 20-record store, got {len(records)}")
    rebuild = BUNDLE / "experience_records.rebuild_check.jsonl"
    report = selector.rebuild_store(store, rebuild)
    if report["missing_from_rebuild"] or any(item.get("error") for item in report["issues"]):
        raise RuntimeError(f"selector rebuild failed: {report}")
    rebuilt = selector.load_store(rebuild)
    if rebuilt != records:
        raise RuntimeError("selector rebuild is not record identical")
    payload, omitted = selector.build_context(
        records,
        goal=GOAL,
        k=7,
        target_tags={"ARTILLERY_KILL", "PROTECTED_ROUTE", "ROADBLOCK_CLEARANCE", "SUPPORT_DELIVERY", "CENTRAL_INTERCEPT"},
        byte_limit=28_000,
    )
    return {"records": records, "rebuild_report": report, "context": payload, "context_omitted": omitted, "context_bytes": len(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode())}


def fact_pack() -> dict:
    return {
        "schema_version": "KIMIARK_R105_EARLY_ROUTE_PROTECTED_FACT_PACK_V1",
        "boundary": "Observed fixed-simulator events only. Old frames are not new deadlines and no operator is mandatory.",
        "parent_r104": {
            "record_id": "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001:candidate-001",
            "plan_sha256": "d91955b06f7bf4145b355152ce2bcd203b3973b469ff4889c6d6d83a1d87048b",
            "action_sha256": "816ec7a9ce93591c5c21c7fea6f811374f0df25238082b483a8a1919c9e7e847",
            "events_gz_sha256": "5b3e33285108938e844cb82cc4d7274494ac16887fd3071087d309c09c424052",
            "events_restored_sha256": "46a72b6dd5f86feef0538897fc773a2e4726154f535fd2b6adb75b007beee1a4",
            "result": {"kills": 21, "leaks": 12, "remaining_life": -10, "win": False},
            "operator_union": ["char_120_hibisc", "char_123_fang", "char_210_stward", "char_212_ansel", "char_283_midn", "char_284_spot", "char_4093_frston"],
        },
        "early_routes": {
            "route_11": {"route_id": "route-11", "start_row_col": [4, 9], "end_row_col": [5, 0], "checkpoints": [[4, 1], [5, 1]], "motion_mode": "WALK", "spawn_frame": 2520, "enemy_id": "enemy_1107_uoffcr", "max_hp": 3300, "atk": 330},
            "route_14": {"route_id": "route-14", "start_row_col": [4, 9], "end_row_col": [5, 0], "checkpoints": [[4, 1], [5, 1]], "motion_mode": "WALK", "spawn_frame": 2880, "enemy_id": "enemy_1107_uoffcr", "max_hp": 3300, "atk": 330},
            "r104_enemy_11": {
                "spawn_frame": 2520, "block": None, "unblock": None, "death": None, "leak": 3065,
                "damage_received": [
                    {"frame": 2721, "source_id": "char_123_fang", "amount": 175.0, "kind": "physical"},
                    {"frame": 2753, "source_id": "char_123_fang", "amount": 175.0, "kind": "physical"},
                    {"frame": 2756, "source_id": "char_283_midn", "amount": 536.76, "kind": "arts"},
                ],
            },
            "r104_enemy_13": {
                "spawn_frame": 2880, "block": None, "unblock": None, "death": None, "leak": 3425,
                "damage_received": [{"frame": 3116, "source_id": "char_283_midn", "amount": 347.0, "kind": "physical"}],
            },
            "m70_enemy_11": {
                "spawn_frame": 2520, "block": {"frame": 2738, "source_id": "char_4093_frston"},
                "unblock": {"frame": 2881, "source_id": "char_4093_frston"}, "death": {"frame": 2881, "source_id": "char_123_fang", "kill_counted": True},
                "damage_received_totals": {"char_4093_frston": 240.0, "char_123_fang": 1050.0, "char_283_midn": 2147.04},
            },
            "m70_enemy_13": {
                "spawn_frame": 2880, "block": {"frame": 3098, "source_id": "char_4093_frston"},
                "unblock": {"frame": 3311, "source_id": "char_4093_frston"}, "death": {"frame": 3311, "source_id": "char_283_midn", "kill_counted": True},
                "damage_received_totals": {"char_4093_frston": 336.0, "char_123_fang": 1050.0, "char_283_midn": 2082.0},
            },
            "difference_context": "M70 used an eighth Melantha and deployed Midnight at row/col [1,5] UP; R104 has Spot at [1,5] and Midnight at [6,5] DOWN. This is positional evidence, not proof of a unique role or tile.",
        },
        "protected_3": {
            "identity": "enemy_3001_upeopl#3", "route_id": "route-2", "spawn_frame": 540, "max_hp": 3500,
            "roadblock_3": {"block_frame": 761, "r104_destroyed_frame": 11917, "m70_destroyed_frame": 2404},
            "r104_damage": [
                {"frame": 1296, "source_id": "enemy_1107_uoffcr#8", "amount": 280.0},
                {"frame": 1356, "source_id": "enemy_1107_uoffcr#8", "amount": 280.0},
                {"frame": 1416, "source_id": "enemy_1107_uoffcr#8", "amount": 280.0},
                {"frame": 3011, "source_id": "enemy_1112_emppnt#0", "amount": 950.0},
                {"frame": 3161, "source_id": "enemy_1112_emppnt#0", "amount": 950.0},
                {"frame": 3311, "source_id": "enemy_1112_emppnt#0", "amount": 950.0, "death": True},
            ],
            "m70_outcome": {"roadblock_1_block_frame": 2773, "roadblock_1_release_frame": 11017, "protected_3_reached_frame": 11349, "additional_damage_events": 0},
            "dependency_boundary": "The early officer #11/#13 leaks and protected-#3 death are separate observed failures; killing one does not prove the other is repaired.",
        },
        "r104_artillery_closure": {
            "steward_tile_row_col": [5, 7], "runtime_tile_x_y": [7, 5], "direction": "DOWN",
            "hit_count": 45, "total_damage": 13227.21, "last_parent_hit_before_change": 4177,
            "extra_hits": [{"frame": 4225, "amount": 249.10}, {"frame": 4273, "amount": 473.29}],
            "artillery_death": {"frame": 4273, "source_id": "char_210_stward", "target_id": "enemy_1112_emppnt#0", "kill_counted": True},
            "support_window": {
                "shell_hit_steward": {"frame": 4211, "amount": 910.0},
                "ansel_heal": {"frame": 4213, "amount": 506.8},
                "hibiscus_heal": {"frame": 4277, "amount": 433.8},
                "in_flight_shell_after_death": {"born_frame": 4271, "hit_frame": 4361, "target_id": "char_120_hibisc", "amount": 890.0},
            },
            "retreat_redeploy": {"retreat_frame": 4280, "refund": 9, "redeploy_frame": 6381, "cost": 18, "redeploy_tile_row_col": [2, 5], "minimum_frame_at_30fps": 6380},
        },
        "r104_vs_r101": {
            "parent_leaks": 13, "r104_leaks": 12,
            "artillery_leak_removed": {"enemy_id": "enemy_1112_emppnt#0", "parent_frame": 5759},
            "armor_21_delayed_not_closed": {"parent_frame": 5101, "r104_frame": 5353},
            "all_other_leak_id_frames_unchanged": True,
            "parent_operator_deaths": ["char_4093_frston@2111", "char_120_hibisc@4511", "char_123_fang@4702", "char_210_stward@6569"],
            "r104_operator_deaths": ["char_4093_frston@2111", "char_123_fang@4954"],
        },
    }


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("R105 experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (DEST / "session/codex_cli").mkdir(parents=True, exist_ok=True)

    parent = BUNDLE / "parent_R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001"
    parent.mkdir(parents=True, exist_ok=True)
    parent_sources = R104 / "session/candidates/candidate-001/simulation"
    for name in ("plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "final_status.json"):
        shutil.copyfile(parent_sources / name, parent / name)
    parent_manifest = {
        "schema_version": "KIMIARK_R105_FIXED_PARENT_IDENTITY_MANIFEST_V1",
        "parent_candidates": [{
            "record_id": "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001:candidate-001",
            "declared_plan_id": "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001",
            "final_status_plan_id": "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001",
            "plan_sha256": digest(parent / "plan_snapshot.json"),
            "action_sha256": digest(parent / "action_snapshot.json"),
            "events_gz_sha256": digest(parent / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(parent / "diagnostic_events.json.gz"),
            "operator_union_count": 7,
            "archive_status": "VERIFIED",
        }],
        "lineage_policy": "User explicitly selected R104 as the single primary parent; no splicing different plans' successful windows.",
    }
    expected = fact_pack()["parent_r104"]
    actual = parent_manifest["parent_candidates"][0]
    for key in ("plan_sha256", "action_sha256", "events_gz_sha256", "events_restored_sha256"):
        if actual[key] != expected[key]:
            raise RuntimeError(f"R104 parent hash mismatch: {key}")
    write_json(BUNDLE / "parent_identity_manifest_v1.json", parent_manifest)

    selected = selector_context()
    store_path = BUNDLE / "experience_records.jsonl"
    store_path.write_bytes((ROOT / "output/codex_experience_selector_v1/experience_records.jsonl").read_bytes())
    report_path = BUNDLE / "experience_import_report_v1.json"
    report_path.write_bytes((ROOT / "output/codex_experience_selector_v1/experience_records.import_report.json").read_bytes())
    write_json(BUNDLE / "experience_selector_state_v1.json", {
        "schema_version": "KIMIARK_EXPERIENCE_SELECTOR_STATE_V1",
        "selector_code_sha256": digest(ROOT / "scripts/codex_experience_selector_v1.py"),
        "selector_store_sha256": digest(store_path),
        "selector_import_report_sha256": digest(report_path),
        "rebuild_report": selected["rebuild_report"],
        "context_omitted": selected["context_omitted"],
        "context_bytes": selected["context_bytes"],
        "context_sha256": hashlib.sha256(json.dumps(selected["context"], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "selection_policy": "Deterministic tag/branch retrieval; advisory only. R104 is the user-selected primary parent, not assumed to be the selector's top result.",
    })
    write_json(BUNDLE / "experience_selector_context_v1.json", selected["context"])
    write_json(BUNDLE / "r105_early_route_protected_fact_pack_v1.json", fact_pack())
    shutil.copyfile(R104 / "post_run_audit_v1.md", BUNDLE / "r104_post_run_audit_corrected_v1.md")

    evidence = json.loads((R101 / "input_bundle/llm_evidence_context.json").read_text())
    for key in ("r100_experience_usage_fact_pack_v1", "r97_next_prompt_suggestion", "r98_closeout", "roadblock_clearance_evidence"):
        evidence.pop(key, None)
    evidence["revision_entry_mode"] = "FIXED_PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {
        "path": "input_bundle/parent_identity_manifest_v1.json",
        "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"),
        "candidate_plan_ids": ["R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001"],
        "selection_policy": "R104 is the user-selected primary parent; other records are evidence references only.",
    }
    evidence["experience_selector_context_v1"] = {
        "path": "input_bundle/experience_selector_context_v1.json",
        "sha256": digest(BUNDLE / "experience_selector_context_v1.json"),
        "advisory_status": "SUGGESTIONS_AND_CONDITIONAL_EVIDENCE_ONLY",
    }
    evidence["r105_early_route_protected_fact_pack_v1"] = {
        "path": "input_bundle/r105_early_route_protected_fact_pack_v1.json",
        "sha256": digest(BUNDLE / "r105_early_route_protected_fact_pack_v1.json"),
        "boundary": "Verified observed windows and explicit UNKNOWN boundaries; no role is mandatory.",
    }
    evidence["experience_selector_decision_record_policy"] = {
        "maximum_context_observations_cited": 3,
        "required_fields": ["selected_parent", "adopted_observations", "non_applicable_experiences", "similar_prior_failure_change", "override_reason_if_any"],
        "placement": "validation_card.experience_selector_decision_record",
        "constraint": "Visible structured record; hidden reasoning is not required.",
    }
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    shutil.copyfile(R101 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")

    extra = [
        "mcp_servers.kimiark.command=\"/home/bigdata/Desktop/arknights-auto-planner/.venv/bin/python\"",
        "mcp_servers.kimiark.args=[\"/home/bigdata/Desktop/arknights-auto-planner/scripts/kimiark_tactical_stdio_service_v1.py\",\"/home/bigdata/Desktop/arknights-auto-planner/docs/review/fc77177/real_tool_closed_loop_sol_high_seven_early_protected_v1/session_config_v1.json\"]",
        "mcp_servers.kimiark.enabled=true",
        "mcp_servers.kimiark.required=true",
        "mcp_servers.kimiark.default_tools_approval_mode=\"approve\"",
        "mcp_servers.kimiark.enabled_tools=[\"get_session_status\",\"check_plan\",\"run_simulation\",\"query_events\"]",
    ]
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "budget_boundary": "User authorized one fresh Sol CLI with 10 checks, 2 candidates, and 2 complete simulations; prior ledgers remain closed.",
        "provider": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high", "features_apps": False,
        "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True},
        "extra_config_values": extra,
    })
    write_json(DEST / "session_config_v1.json", {
        "allow_fake_execution": False,
        "authorization_config_path": str(DEST / "model_authorization_v1.json"),
        "budget_path": str(DEST / "simulation_budget_v1.json"),
        "candidate_ledger_path": str(DEST / "candidate_ledger_v1.json"),
        "execution_backend": "CONTROLLED_RUNNER",
        "facts_source_dir": str(BUNDLE),
        "features_apps": False,
        "max_candidates": 2,
        "max_check_calls": 10,
        "max_real_cli_starts": 1,
        "max_unique_deployed_operators": 7,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "model": "gpt-6.1-sol",
        "plan_id_prefix": PLAN_PREFIX,
        "plan_label": "SOL_HIGH_SEVEN_EARLY_PROTECTED",
        "reasoning_effort": "high",
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "session_root": str(DEST / "session"),
        "simulation_timeout_seconds": 3600,
        "stage_id": "main_08-07",
    })
    write_json(DEST / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": "main_08-07",
        "max_stage_simulations": 2,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(DEST / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "max_candidates": 2,
        "max_check_calls": 10,
        "used_candidates": 0,
        "used_check_calls": 0,
        "attempts": [],
        "checks": [],
    })

    prompt = """You are gpt-6.1-sol (reasoning high) in one authorized KimiArk Codex CLI session. Work only in the current repository and use only the local MCP server `kimiark`. First call `get_session_status` and confirm gpt-6.1-sol/high, features.apps=false, K=7, mechanics `m38b-2781-animation-speed-v1`, max_real_cli_starts 1, 10 checks, 2 candidates, and 2 complete simulations. This is an independent ledger; do not resume, transfer, or reset old budgets.

Only `get_session_status`, `check_plan`, `run_simulation`, and `query_events` are permitted. Read-only shell may inspect supplied evidence. Do not use another model/agent, web service, tactical search, or shell simulation. Do not modify code, mechanics, budgets, authorization, or result files. All tactical choices are yours.

M70 remains the eight-operator fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN. The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_early_protected_v1/input_bundle/`. Read `experience_selector_context_v1.json` first, then `r105_early_route_protected_fact_pack_v1.json`, and verify the single R104 parent through `parent_identity_manifest_v1.json`. R104 is the user-selected primary parent, not merely a retrieval suggestion. You may use M70 and other archived records as conditional evidence, but do not splice successful windows from different plans.

The goal is legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN while preserving R104's observed 4200-4280 artillery closure. R104 additionally observed: officer #11 was damaged by Fang@2721/2753 and Midnight@2756 but not blocked/killed and leaked@3065; officer #13 was damaged by Midnight@3116 but not blocked/killed and leaked@3425; protected #3 died@3311 after three officer-#8 hits and three 950 artillery-shell hits while roadblock #3 remained intact. This early-route and protected-#3 repair is the first target; complete settlement still requires every other duty. Do not assume killing #11/#13 repairs protected #3, and do not assume artillery closure repairs either.

Before C1, add `experience_selector_decision_record` to your validation card with the verified R104 parent ID/hash; at most 3 concrete context observations with record IDs; experiences you did not apply and why; any similar prior failure and what materially changes; override reason if any; your falsifiable question and expected/refuting events. State how each change affects route #11/#14 interception, protected #3, artillery closure, shell exposure, healer survival, roadblocks, both protected routes, and central #21/#22/#33/#34. If a role/tile/cost is shared, resolve the timing conflict explicitly. First BLOCK is intermediate evidence; routes need kill or live replacement with no leak.

All 34 legal ordinary-mode 1-3-star IDs are open; union of selected and deployed IDs must be <=7, robots count, same-ID redeployment counts once. No operator is mandatory or forbidden. Allowed mechanisms include faster kills, changed shell exposure, rotating output/damage duty, replacement, retreat/redeployment, and accounted sacrifice. Exact HP, full eligible-candidate order, and continuous positions are UNKNOWN where unrecorded; old frames are not new deadlines.

After check_plan passes, freeze the exact candidate/hash and run once. Query the earliest failure first, then targeted #11/#13, protected #3, artillery, and central chains. Distinguish injured, eligible, selected, blocked, healed, output alive, attacked artillery, artillery killed, route blocked, route leaked, and central held/killed. The host may supply C1 raw feedback to this same CLI; no selector restart or algorithm change is allowed. Run C2 only for a materially different repair supported by C1 evidence; otherwise stop. If a complete seven-operator WIN occurs, freeze and stop; do not explore six.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and reached, every enemy settled with no active enemy, and complete settlement. Report exact kills/leaks/life, death events versus unique dead IDs, protected outcomes, key enemy settlement, action errors, configured model, visible usage, UNKNOWN_CLI_INTERNAL, and budget counts. `cached_input` is an input subset. Fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum."""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.write_text(prompt + "\n")

    files = [path for path in BUNDLE.rglob("*") if path.is_file() and path.name != "bundle_manifest_v1.json"]
    manifest = {
        "schema_version": "KIMIARK_R105_INPUT_BUNDLE_MANIFEST_V1",
        "files": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)} for path in sorted(files)],
    }
    write_json(BUNDLE / "bundle_manifest_v1.json", manifest)


if __name__ == "__main__":
    main()
