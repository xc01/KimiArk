#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_c2_retreat_window_v1"
ARTILLERY_ID = "enemy_1112_emppnt#0"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def first_planned_deployments(plan: dict) -> dict:
    result = {}
    for action in plan["action_timeline"]:
        if action["action_type"] == "DEPLOY" and action["operator_id"] not in result:
            result[action["operator_id"]] = {
                "frame": action["frame"],
                "direction": action["direction"],
                "plan_action_tile_row_col": action["tile"],
                "runtime_tile_col_row": list(reversed(action["tile"])),
            }
    return result


def action_errors(events: list[dict]) -> list[dict]:
    deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
    result = []
    for event in events:
        if event["event_type"] not in ("DEPLOY", "RETREAT", "SKILL_ACTIVATE") or event.get("details", {}).get("legal") is not False:
            continue
        death_frame = next(
            (death["frame"] for death in deaths if death["source_id"] == event["source_id"] and death["frame"] <= event["frame"]),
            None,
        )
        result.append({
            "frame": event["frame"],
            "event_type": event["event_type"],
            "source_id": event["source_id"],
            "executor_death_frame": death_frame,
            "classification": "dependency_failure_after_executor_death" if death_frame is not None else "independent_action_error",
        })
    return result


def tool_trajectory() -> dict:
    path = EXPERIMENT / "session/codex_cli/attempt_01/codex_exec.jsonl"
    counts = Counter()
    for line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "mcp_tool_call":
            counts[f"{item.get('tool')}:{item.get('status')}"] += 1
    return {
        "schema_version": "KIMIARK_COMPLETED_TOOL_TRAJECTORY_SUMMARY_V1",
        "counting_boundary": "Completed MCP tool-call items only; started/completed duplicates are not added.",
        "counts": dict(counts),
    }


def visible_usage() -> list[dict]:
    path = EXPERIMENT / "session/codex_cli/attempt_01/codex_exec.jsonl"
    usage = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and "usage" in event:
            usage.append(event["usage"])
    return usage


def main() -> None:
    sim_dir = EXPERIMENT / "session/candidates/candidate-001/simulation"
    events_path = sim_dir / "diagnostic_events.json"
    summary_path = sim_dir / "diagnostic_summary.json"
    if not events_path.exists():
        events_path.write_bytes(gzip.decompress((sim_dir / "diagnostic_events.json.gz").read_bytes()))
    if not summary_path.exists():
        summary_path.write_bytes(gzip.decompress((sim_dir / "diagnostic_summary.json.gz").read_bytes()))
    events = json.loads(events_path.read_text())["events"]
    summary = json.loads(summary_path.read_text())
    plan = json.loads((sim_dir / "plan_snapshot.json").read_text())
    candidate_actions = json.loads((sim_dir / "action_snapshot.json").read_text())["actions"]
    parent_dir = EXPERIMENT / "input_bundle/parent_R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002"
    parent_actions = json.loads((parent_dir / "action_snapshot.json").read_text())["actions"]
    with gzip.open(parent_dir / "diagnostic_events.json.gz", "rt") as handle:
        parent_events = json.loads(handle.read())["events"]
    for plaintext in (events_path, summary_path):
        compressed_path = candidate_dir_gz = sim_dir / f"{plaintext.name}.gz"
        with compressed_path.open("wb") as handle:
            with gzip.GzipFile(filename=plaintext.name, fileobj=handle, mode="wb", mtime=0) as gz:
                gz.write(plaintext.read_bytes())
        plaintext.unlink()

    first_mismatch = next((index for index, (left, right) in enumerate(zip(parent_events, events)) if left != right), None)
    changed_parent = parent_events[first_mismatch:first_mismatch + 4]
    changed_candidate = events[first_mismatch:first_mismatch + 4]
    deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
    leaks = [event for event in events if event["event_type"] == "ENEMY_LEAK"]
    artillery_hits = [
        event for event in events
        if event["event_type"] == "DAMAGE" and event["source_id"] == "char_210_stward" and event["target_id"] == ARTILLERY_ID
    ]
    central_blocks = [
        event for event in events
        if event["event_type"] == "BLOCK" and event.get("target_id") in {
            "enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#33", "enemy_1110_uamord#34",
        }
    ]
    central_leaks = [event for event in leaks if event.get("source_id") in central_blocks or event.get("source_id", "").startswith("enemy_1110_uamord#")]
    central_blocks = [
        event for event in events
        if event["event_type"] == "BLOCK" and event.get("target_id", "").startswith("enemy_1110_uamord#")
    ]
    central_leaks = [event for event in leaks if event.get("source_id", "").startswith("enemy_1110_uamord#")]
    action_error_rows = action_errors(events)
    errors = Counter(row["classification"] for row in action_error_rows)
    ledger = json.loads((EXPERIMENT / "candidate_ledger_v1.json").read_text())
    authorization = json.loads((EXPERIMENT / "model_authorization_v1.json").read_text())
    budget = json.loads((EXPERIMENT / "simulation_budget_v1.json").read_text())
    preflight = json.loads((EXPERIMENT / "zero_model_preflight_v1.json").read_text())
    process = json.loads((EXPERIMENT / "session/codex_cli/attempt_01/cli_process_result.json").read_text())
    relevant_heals = [
        {
            "frame": event["frame"],
            "source_id": event.get("source_id"),
            "target_id": event.get("target_id"),
            "amount": event.get("details", {}).get("amount"),
        }
        for event in events
        if event["event_type"] == "HEAL"
        and (event.get("source_id") in {"char_212_ansel", "char_120_hibisc"} or event.get("target_id") in {"char_212_ansel", "char_120_hibisc", "char_210_stward"})
    ]

    closeout = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_C2_RETREAT_WINDOW_CLOSEOUT_REPORT_V1",
        "experiment_id": "real_tool_closed_loop_sol_high_seven_c2_retreat_window_v1",
        "model": {
            "provider": authorization["provider"],
            "configured_model": authorization["model"],
            "reasoning_effort": authorization["reasoning_effort"],
            "features_apps": authorization["features_apps"],
            "identity_proof_boundary": "Configured identity only; no cryptographic model identity was proven.",
        },
        "process": process,
        "preflight": {
            "repository_head": preflight["repository_head"],
            "published_boundary": preflight["published_boundary"],
            "input_bundle_manifest_sha256": preflight["input_bundle"]["manifest_sha256"],
            "input_bundle_all_hashes_match": preflight["input_bundle"]["manifest_all_hashes_match"],
            "parent_identity": preflight["input_bundle"]["parent_candidates"][0],
            "cold_start_task_root_removed": preflight["input_bundle"]["cold_start_task_root_removed"],
            "coverage_boundary": preflight["coverage_boundary"],
        },
        "control_validity": {
            "parent_record_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002",
            "parent_plan_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002",
            "parent_plan_sha256": digest(parent_dir / "plan_snapshot.json"),
            "parent_action_sha256": digest(parent_dir / "action_snapshot.json"),
            "parent_events_gz_sha256": digest(parent_dir / "diagnostic_events.json.gz"),
            "parent_events_restored_sha256": restored_digest(parent_dir / "diagnostic_events.json.gz"),
            "candidate_sha256": ledger["attempts"][0]["candidate_sha256"],
            "candidate_plan_sha256": digest(sim_dir / "plan_snapshot.json"),
            "candidate_action_sha256": digest(sim_dir / "action_snapshot.json"),
            "events_gz_sha256": digest(sim_dir / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(sim_dir / "diagnostic_events.json.gz"),
            "summary_gz_sha256": digest(sim_dir / "diagnostic_summary.json.gz"),
            "summary_restored_sha256": restored_digest(sim_dir / "diagnostic_summary.json.gz"),
            "event_count": len(events),
            "pre_change_events_equal_count": first_mismatch,
            "first_event_difference_index": first_mismatch,
            "changed_event_window": {
                "parent": changed_parent,
                "candidate": changed_candidate,
            },
            "changed_action_diff": [
                {"index": index, "parent": parent, "candidate": candidate}
                for index, (parent, candidate) in enumerate(zip(parent_actions, candidate_actions))
                if parent != candidate
            ],
            "changed_action_count": sum(left != right for left, right in zip(parent_actions, candidate_actions)),
        },
        "fact_pack_correction": {
            "original_declared_steward_redeploy_time_frames": 70,
            "original_declared_available_at_if_retreat_4280": 4350,
            "actual_rule": "redeploy_time_frames = redeploy_time_seconds * 30; 70 * 30 = 2100",
            "actual_available_at_if_retreat_4280": 6380,
            "production_check_002_rejection": "REDEPLOY_COOLDOWN_ACTIVE at unchanged 6301 redeploy",
            "disposition": "Preserve frozen pre-run fact pack unchanged; record as a derived audit correction. 4280 was not simulated.",
        },
        "candidate": {
            "candidate_id": "candidate-001",
            "plan_id": plan["operational_plan_id"],
            "plan_sha256": digest(sim_dir / "plan_snapshot.json"),
            "action_sha256": digest(sim_dir / "action_snapshot.json"),
            "events_gz_sha256": digest(sim_dir / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(sim_dir / "diagnostic_events.json.gz"),
            "summary_gz_sha256": digest(sim_dir / "diagnostic_summary.json.gz"),
            "summary_restored_sha256": restored_digest(sim_dir / "diagnostic_summary.json.gz"),
            "validation_card": plan.get("validation_card"),
            "first_planned_deployments": first_planned_deployments(plan),
            "operator_union_count": len(plan["selected_low_star_operator_ids"]),
            "operator_union": plan["selected_low_star_operator_ids"],
            "simulator_manifest": json.loads((sim_dir / "manifest.json").read_text()),
            "summary_result": {key: value for key, value in (summary.get("result") or {}).items() if key != "events"},
            "classification": summary.get("classification"),
            "protected_target_deaths": summary.get("protected_target_deaths"),
            "protected_target_reached_events": summary.get("protected_target_reached_events"),
            "observed_key_events": {
                "operator_deaths": deaths,
                "unique_operator_death_ids": sorted({event["source_id"] for event in deaths}),
                "enemy_leaks": leaks,
                "protected_target_reached": [event for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"],
                "protected_target_reached_events": [event for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"],
                "relevant_heals": relevant_heals,
                "protected_target_death_events": [event for event in events if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") == "enemy_3001_upeopl#3"],
                "device_destroyed": [event for event in events if event["event_type"] == "DEVICE_DESTROYED"],
                "central_blocks": central_blocks,
                "central_leaks": central_leaks,
                "artillery_death": [event for event in events if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") == ARTILLERY_ID],
                "artillery_leak": [event for event in events if event["event_type"] == "ENEMY_LEAK" and event.get("source_id") == ARTILLERY_ID],
                "steward_artillery_damage": {
                    "hit_count": len(artillery_hits),
                    "total_amount": round(sum(event["details"]["amount"] for event in artillery_hits), 2),
                    "last_hit_event_index": next(index for index, event in enumerate(events) if event is artillery_hits[-1]),
                    "last_hit": artillery_hits[-1],
                    "last_artillery_target_selection": events[19340],
                    "frames": [event["frame"] for event in artillery_hits],
                },
                "steward_retreat_window": {
                    "parent_dp_change_index": 19405,
                    "parent_retreat_index": 19406,
                    "candidate_dp_change_index": 19407,
                    "candidate_retreat_index": 19408,
                    "candidate_dp_change": events[19407],
                    "candidate_retreat": events[19408],
                    "shell_start": events[19046],
                    "shell_born_frame": 4121,
                    "recorded_impact_while_absent": "NONE",
                    "next_recorded_shell_lock": {"event_index": 19583, "frame": 4261, "target_position_runtime_x_y": [6, 2]},
                    "next_recorded_shell_hit": events[19876],
                    "exact_hp_if_present_at_4211": "UNKNOWN",
                },
                "steward_redeploy_events": [event for event in events if event["event_type"] == "DEPLOY" and event.get("source_id") == "char_210_stward"],
            },
            "recorded_action_errors": action_error_rows,
            "deployment_errors": summary["result"].get("deployment_errors", []),
            "action_error_classification": {
                "dependency_failures_after_executor_death": errors.get("dependency_failure_after_executor_death", 0),
                "independent_action_errors": errors.get("independent_action_error", 0),
            },
        },
        "interface": {
            "real_cli_starts": authorization["real_cli_starts"],
            "candidate_ledger": ledger,
            "simulation_budget": budget,
            "completed_tool_trajectory": tool_trajectory(),
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "visible_usage_records": visible_usage(),
            "usage_boundary": "cached_input_tokens are an input_tokens subset and must not be added to input_tokens.",
        },
        "final_model_summary": (EXPERIMENT / "session/codex_cli/attempt_01/codex_final_message.txt").read_text(),
        "closure": {
            "new_win": False,
            "simulator_win": False,
            "best_verified_operator_count": 8,
            "seven_or_fewer_feasibility": "UNKNOWN",
            "targeted_answer": {
                "was_4200_an_immediate_one_frame_output_cutoff": "NO; the only legal fallback moved retreat to 4201 and produced no extra artillery hit. The last hit remained 4177 and the artillery leaked at 5759.",
                "was_the_material_4225_4273_window_tested": "NO; 4280 was rejected by production cooldown because redeploy at unchanged 6301 was illegal. 4201 is the latest legal retreat under the single-action constraint, so that window remains untested.",
                "conclusion_boundary": "This is a one-variable controlled comparison for R101 C2. It does not prove R101 retreat timing is globally wrong, that Steward is necessary, that another frame would WIN, or that the unavailable later window has no value.",
            },
            "complete_settlement": {
                "enemies_killed": 20,
                "enemies_leaked": 13,
                "remaining_life": -11,
                "remaining_enemy_hp": 0,
                "settlement_end_frame": 12449,
                "protected_3": "DIED_AT_3311",
                "protected_14": "REACHED_AT_12448",
                "roadblocks": "#4 destroyed 2443; #3 destroyed 11917; #2 destroyed 12116; #1 not recorded destroyed",
                "central": "#21 blocked 4646 then leaked 5101; #22/#33/#34 no recorded block and leaked 5196/6846/6996",
                "artillery": "43 hits / 12504.82 damage, no recorded artillery death, leaked 5759",
            },
            "scope_boundary": [
                "Current fixed simulator only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
                "M70 R8_7_GPT_M70_V1 remains the frozen eight-operator WIN and was not rerun.",
                "Seven-or-fewer feasibility remains UNKNOWN.",
            ],
        },
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)
    manifest_payload = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_C2_RETREAT_WINDOW_ARTIFACT_MANIFEST_V1",
        "root": EXPERIMENT.relative_to(ROOT).as_posix(),
        "hash_algorithm": "SHA-256",
        "includes_self": False,
        "self_sha256_path": "closeout_report_v1.json.sha256",
        "files": [],
    }
    excluded_names = {"artifact_manifest_v1.json", "closeout_report_v1.json.sha256", "candidate_ledger_v1.json.service.lock", "simulation.run.lock", "runner.lock"}
    for path in sorted(path for path in EXPERIMENT.rglob("*") if path.is_file() and path.name not in excluded_names):
        entry = {"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = restored_digest(path)
        manifest_payload["files"].append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", manifest_payload)
    (closeout_path.with_suffix(closeout_path.suffix + ".sha256")).write_text(f"{digest(closeout_path)}  {closeout_path.name}\n")


if __name__ == "__main__":
    main()
