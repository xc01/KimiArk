#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE_EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_selector_feedback_v1"
SOURCE = SOURCE_EXPERIMENT / "session/candidates/candidate-002/simulation"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_c2_retreat_window_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-c2-retreat-window-v1"
PLAN_PREFIX = "R103_SOL_HIGH_SEVEN_C2_RETREAT_WINDOW_"
EXPECTED_PARENT = {
    "plan_sha256": "044eb9eb90254934cc4767dbd1070ee91ccbdf349380ec258bbdd488098b146b",
    "action_sha256": "d5a07b4dca4f05cee428875165d3c59ee0c388e9b950623cd62fc8c60d83fc8f",
    "events_gz_sha256": "d971d1fe5a69c2ea5a4ae3c98f44ab023b3e48ee1e3eb3f1dc6168808930a065",
    "events_restored_sha256": "25f3a184f572bee142c9d5d1a6ee0807db0e2e28df26d5dee26fcea7691f9ed7",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def retreat_window_fact_pack() -> dict:
    return {
        "schema_version": "KIMIARK_C2_RETREAT_WINDOW_FACT_PACK_V1",
        "boundary": "Verified fixed-simulator observations and static action facts only. HP and continuous positions are UNKNOWN.",
        "control_parent": {
            "record_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002",
            "plan_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002",
            "plan_sha256": EXPECTED_PARENT["plan_sha256"],
            "action_sha256": EXPECTED_PARENT["action_sha256"],
            "events_gz_sha256": EXPECTED_PARENT["events_gz_sha256"],
            "events_restored_sha256": EXPECTED_PARENT["events_restored_sha256"],
            "result": "20 kills / 13 leaks / life -11; 4 death events / 4 unique IDs; not a global best claim.",
        },
        "observed_stop": {
            "last_artillery_damage": {"event_index": 19344, "frame": 4177, "amount": 249.1},
            "target_selection_still_artillery": {"event_index": 19340, "frame": 4177, "target_id": "enemy_1112_emppnt#0"},
            "retreat": {"dp_change_index": 19405, "retreat_index": 19406, "frame": 4200, "refund": 9},
            "not_death_transfer_or_no_candidate": True,
        },
        "in_flight_shell_risk": {
            "start": {"event_index": 19046, "frame": 4111, "target_position_runtime_x_y": [7, 5]},
            "if_steward_stays": "A projectile consistent with delay 3.0 seconds would reach frame 4211; this is mechanism evidence, not proof of survival.",
            "after_retreat_observation": "No matching ENEMY_ABILITY_HIT is recorded while Steward is absent; next recorded shell starts #19583@4261 locked [6,2] and hits Hibiscus #19876@4361.",
            "exact_hp_if_present_at_4211": "UNKNOWN",
        },
        "different_control": {
            "R98_C1": "43 hits end at 4297; Steward dies at 4330 from a 910 shell. Plan/action/events hashes are in experience_records_snapshot_v1.jsonl.",
            "R102_C1": "38 hits end at 3937; Steward dies at 3943.",
            "R102_C2": "9 hits end at 2545; Steward dies at 2593.",
        },
        "M70_reference_only": {
            "plan_sha256": "fe265c2837d962184647bded4ce0725f4fdd3f8bef013d05cf5ade5ef89ddf9d",
            "action_sha256": "c6248dd2da3eda2668c286190001600906cdc5c3b6322883ed1fb6b63d07560a",
            "artillery_damage": {"frames": [4225, 4273], "kill_frame": 4273},
            "claim_boundary": "Reference window only; does not prove delayed R101 C2 reproduces it or preserves other duties.",
        },
        "static_feasibility": {
            "steward_cost": 18,
            "steward_redeploy_time_frames": 70,
            "preferred_probe_frame": 4280,
            "cooldown_if_retreat_4280": {"available_at": 4350, "scheduled_redeploy": 6301, "feasible": True},
            "dp_path_from_4200_observation": "Before retreat DP=82; +9 refund makes 91. Fang's 4320 skill fills to cap 99; scheduled 6301 Steward deploy costs 18 and leaves 81. Delaying retreat preserves enough DP.",
            "not_survival_claim": "Static feasibility does not assert survival at 4211 or any later frame.",
        },
        "single_change_policy": {
            "fixed_parent": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002",
            "allowed_change": "Change only the frame of the Steward RETREAT scheduled at 4200.",
            "forbidden": "No other deployment, retreat, tile, direction, skill, operator, cost declaration, or tactical revision.",
            "preferred_probe": 4280,
            "fallback_rule": "If 4280 is illegal under production checks, Sol may select one evidence-based later legal frame; if none exists, stop without simulation.",
        },
    }


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("c2-retreat-window experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)
    actual = {
        "plan_sha256": digest(SOURCE / "plan_snapshot.json"),
        "action_sha256": digest(SOURCE / "action_snapshot.json"),
        "events_gz_sha256": digest(SOURCE / "diagnostic_events.json.gz"),
        "events_restored_sha256": restored_digest(SOURCE / "diagnostic_events.json.gz"),
    }
    if actual != EXPECTED_PARENT:
        raise RuntimeError(f"R101 C2 identity mismatch: {actual}")
    parent = BUNDLE / "parent_R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002"
    parent.mkdir(parents=True, exist_ok=True)
    for name in ("plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "final_status.json"):
        shutil.copyfile(SOURCE / name, parent / name)
    plan = json.loads((parent / "plan_snapshot.json").read_text())
    final = json.loads((parent / "final_status.json").read_text())
    if plan["operational_plan_id"] != "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002" or final["plan_id"] != plan["operational_plan_id"]:
        raise RuntimeError("R101 C2 plan_id mismatch")
    parent_record = {
        "schema_version": "KIMIARK_C2_RETREAT_WINDOW_PARENT_IDENTITY_MANIFEST_V1",
        "fixed_parent_policy": "Only this verified R101 C2 parent is authorized; selector retrieval is not used to select a parent.",
        "parent_candidates": [{
            "record_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002",
            "candidate_id": "candidate-002",
            "declared_plan_id": plan["operational_plan_id"],
            "final_status_plan_id": final["plan_id"],
            "plan_sha256": actual["plan_sha256"],
            "action_sha256": actual["action_sha256"],
            "events_gz_sha256": actual["events_gz_sha256"],
            "events_restored_sha256": actual["events_restored_sha256"],
            "operator_union_count": len(set(plan["selected_low_star_operator_ids"]) | {action["operator_id"] for action in plan["action_timeline"] if action["action_type"] == "DEPLOY"}),
            "archive_status": "VERIFIED",
            "parent_eligibility": "FIXED_CONTROLLED_PARENT",
        }],
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", parent_record)
    snapshot = BUNDLE / "experience_records_snapshot_v1.jsonl"
    snapshot.write_bytes((ROOT / "output/codex_experience_selector_v1/experience_records.jsonl").read_bytes())
    fact_path = BUNDLE / "retreat_window_fact_pack_v1.json"
    write_json(fact_path, retreat_window_fact_pack())
    shutil.copyfile(SOURCE_EXPERIMENT / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")
    evidence = json.loads((SOURCE_EXPERIMENT / "input_bundle/llm_evidence_context.json").read_text())
    evidence.pop("cold_start_task_root", None)
    evidence.pop("r100_experience_usage_fact_pack_v1", None)
    evidence.pop("r97_next_prompt_suggestion", None)
    evidence.pop("r98_closeout", None)
    evidence["revision_entry_mode"] = "PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {
        "path": "input_bundle/parent_identity_manifest_v1.json",
        "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"),
        "candidate_plan_ids": [item["declared_plan_id"] for item in parent_record["parent_candidates"]],
        "selection_policy": "Parent is fixed to R101 C2 for this single-variable attribution test; no selector override.",
    }
    evidence["experience_records_snapshot_v1"] = {
        "path": "input_bundle/experience_records_snapshot_v1.jsonl",
        "sha256": digest(snapshot),
        "advisory_status": "READ_ONLY_PRIOR_EVIDENCE_ONLY_NOT_A_PARENT_SELECTOR",
    }
    evidence["retreat_window_fact_pack_v1"] = {
        "path": "input_bundle/retreat_window_fact_pack_v1.json",
        "sha256": digest(fact_path),
        "boundary": "Verified historical facts and static feasibility; survival remains UNKNOWN.",
    }
    evidence["single_variable_change_policy"] = {
        "required_parent": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002",
        "required_action_diff": "Exactly one changed action: Steward RETREAT frame 4200 -> one legal later frame.",
        "preferred_probe": 4280,
        "required_validation_card_fields": ["control_parent", "unique_change", "chosen_frame_justification", "cooldown_and_dp_calculation", "expected_observable_events", "refuting_events", "known_risks"],
        "candidate_limit": 1,
        "simulation_limit": 1,
    }
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID, "stage_id": "main_08-07", "model": "gpt-6.1-sol", "reasoning_effort": "high", "features_apps": False,
        "plan_id_prefix": PLAN_PREFIX, "plan_label": "SOL_HIGH_SEVEN_C2_RETREAT_WINDOW", "execution_backend": "CONTROLLED_RUNNER", "allow_fake_execution": False, "simulation_timeout_seconds": 3600,
        "mechanics_version": "m38b-2781-animation-speed-v1", "facts_source_dir": BUNDLE.as_posix(), "session_root": (DEST / "session").as_posix(),
        "budget_path": (DEST / "simulation_budget_v1.json").as_posix(), "candidate_ledger_path": (DEST / "candidate_ledger_v1.json").as_posix(),
        "authorization_config_path": (DEST / "model_authorization_v1.json").as_posix(), "max_unique_deployed_operators": 7,
        "max_real_cli_starts": 1, "max_check_calls": 5, "max_candidates": 1, "max_stage_simulations": 1,
    }
    write_json(DEST / "session_config_v1.json", config)
    write_json(DEST / "simulation_budget_v1.json", {"schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1", "stage_id": "main_08-07", "max_stage_simulations": 1, "prior_stage_simulations": 0, "started_stage_simulations": 0})
    write_json(DEST / "candidate_ledger_v1.json", {"schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2", "session_id": SESSION_ID, "max_check_calls": 5, "used_check_calls": 0, "max_candidates": 1, "used_candidates": 0, "checks": [], "attempts": []})
    extra = [
        f"mcp_servers.kimiark.command={json.dumps(str(ROOT / '.venv/bin/python'))}",
        f"mcp_servers.kimiark.args={json.dumps([str(ROOT / 'scripts/kimiark_tactical_stdio_service_v1.py'), str(DEST / 'session_config_v1.json')])}",
        "mcp_servers.kimiark.required=true", "mcp_servers.kimiark.default_tools_approval_mode=approve",
        'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]',
    ]
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_MODEL_AUTHORIZATION_V2", "authorization_status": "USER_AUTHORIZED_THIS_BOUNDARY",
        "authorization_boundary": "One fresh gpt-6.1-sol/high CLI; 5 checks, 1 candidate, 1 complete fixed simulation; old ledgers remain closed.",
        "provider": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high", "features_apps": False,
        "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True},
        "extra_config_values": extra,
    })
    prompt = f"""You are gpt-6.1-sol (reasoning high) in one authorized KimiArk Codex CLI session. Work only in this repository and use only the local MCP server `kimiark`. First call `get_session_status` and confirm gpt-6.1-sol/high, features.apps=false, K=7, mechanics `m38b-2781-animation-speed-v1`, max_real_cli_starts 1, 5 checks, 1 candidate, and 1 complete simulation. This is an independent ledger; do not resume or transfer old budgets.

Only `get_session_status`, `check_plan`, `run_simulation`, and `query_events` are permitted. Read-only shell may inspect supplied evidence. Do not use another model/agent, web service, tactical search, or shell simulation. Do not modify code, mechanics, budgets, authorization, or result files.

This is a controlled single-variable attribution test, not general tactical redesign, selector tuning, or RL. The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_c2_retreat_window_v1/input_bundle/`. The sole authorized parent is verified `R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002` through `parent_identity_manifest_v1.json`. Verify its plan/action/events hashes before proposing anything. `experience_records_snapshot_v1.jsonl` is read-only prior evidence, not a parent selector.

The question is whether R101 C2's scheduled 4200 Steward retreat truncated a still-valuable artillery window. It is distinct from R98 C1's 4330 death and R102's earlier deaths. Read `retreat_window_fact_pack_v1.json`. The preferred probe is 4280 because M70 observed artillery hits at 4225/4273 and killed at 4273, but that is not a universal deadline or survival guarantee. Static facts say 4280 keeps the scheduled 6301 redeploy legal and DP feasible; an artillery shell consistent with hitting [7,5] around 4211 makes survival UNKNOWN. You must choose one legal later retreat frame. Prefer 4280 if legal; use another evidence-based legal frame only if needed; stop if none is legal.

Change exactly one action: the Steward RETREAT frame scheduled at 4200. Keep every other deployment, retreat, tile, direction, skill, operator, frame, and declaration identical. Only a short validation card may explain the controlled change. It must record the parent hashes, unique diff, chosen frame, cooldown/DP calculation, expected events, refuting events, in-flight-shell risk, and possible replacement cost. Do not alter healing, opening, central duties, protected routes, roster, or any later action. Normalized action diff must be exactly one RETREAT frame change.

HARD ROSTER LIMIT: the union of selected_low_star_operator_ids and every DEPLOY action operator_id must contain at most 7 distinct IDs. Same-ID redeployment counts once; robots count. After `check_plan` passes, freeze the exact candidate/hash and run exactly once. Do not add a second candidate or simulation. Query before/after 4177/4200 events, the in-flight shell, actual target selection, damage, artillery death/leak, operator deaths, DP/redeploy, first new failure, and full settlement. Compare pre-change events to the original; if they differ unexpectedly, mark control validity insufficient rather than forcing attribution.

Additional hits are not WIN. Report complete settlement, both protected targets, roadblocks, artillery, central #21/#22/#33/#34, action errors, death events versus unique dead IDs, exact kills/leaks/life, and remaining enemies. Visible usage may be UNKNOWN_CLI_INTERNAL; cached_input is an input subset. Fixed-simulator scope only; no real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global-minimum claims."""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    manifest_files = []
    for path in sorted(item for item in BUNDLE.rglob("*") if item.is_file() and item.name != "bundle_manifest_v1.json"):
        entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["restored_sha256"] = restored_digest(path)
        manifest_files.append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_C2_RETREAT_WINDOW_INPUT_BUNDLE_MANIFEST_V1",
        "files": manifest_files,
    })


if __name__ == "__main__":
    main()
