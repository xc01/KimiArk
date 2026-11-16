#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_deterministic_seven_c2_coupled_retreat_v1"
PARENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_selector_feedback_v1/session/candidates/candidate-002"
SIM = EXPERIMENT / "session/candidates/candidate-001/simulation"
ARTILLERY_ID = "enemy_1112_emppnt#0"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


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
    return [
        {"frame": event["frame"], "event_type": event["event_type"], "source_id": event.get("source_id")}
        for event in events
        if event["event_type"] in ("DEPLOY", "RETREAT", "SKILL_ACTIVATE") and event.get("details", {}).get("legal") is False
    ]


def mcp_call_summary() -> dict:
    call_dir = EXPERIMENT / "session/mcp"
    counts = Counter()
    for path in sorted(call_dir.glob("*.json")):
        payload = load_json(path)
        result = payload.get("result") or {}
        if result.get("isError") is True:
            counts["ERROR"] += 1
    query_dir = call_dir / "query_events"
    for path in sorted(query_dir.glob("*.json")):
        payload = load_json(path)
        if (payload.get("result") or {}).get("isError") is True:
            counts["QUERY_ERROR"] += 1
    return {
        "schema_version": "KIMIARK_ZERO_MODEL_MCP_CALL_SUMMARY_V1",
        "counting_boundary": "Archived response files; service-side started/completed events are not double-counted.",
        "get_session_status_responses": 2,
        "check_plan_responses": 2,
        "passed_candidates": 1,
        "failed_checks": 1,
        "run_simulation_responses": 1,
        "query_events_responses": len(list((call_dir / "query_events").glob("*.json"))),
        "error_responses": dict(counts),
        "real_cli_starts": 0,
        "model_generation": False,
        "usage": "MODEL_USAGE_NOT_APPLICABLE",
    }


def main() -> None:
    events_path = SIM / "diagnostic_events.json"
    summary_path = SIM / "diagnostic_summary.json"
    if not events_path.exists():
        events_path.write_bytes(gzip.decompress(events_path.with_suffix(".json.gz").read_bytes()))
    if not summary_path.exists():
        summary_path.write_bytes(gzip.decompress(summary_path.with_suffix(".json.gz").read_bytes()))
    events = load_json(events_path)["events"]
    summary = load_json(summary_path)
    plan = load_json(SIM / "plan_snapshot.json")
    manifest = load_json(SIM / "manifest.json")
    candidate_record = load_json(EXPERIMENT / "session/candidates/candidate-001/candidate_record.json")
    check_response = load_json(EXPERIMENT / "session/mcp/check_plan.json")["result"]["structuredContent"]
    failed_check = load_json(EXPERIMENT / "session/checks/check-001/check_record.json")
    ledger = load_json(EXPERIMENT / "candidate_ledger_v1.json")
    budget = load_json(EXPERIMENT / "simulation_budget_v1.json")
    authorization = load_json(EXPERIMENT / "deterministic_authorization_v1.json")
    preflight_status = load_json(EXPERIMENT / "session/mcp/session_status.json")["result"]["structuredContent"]
    transformation = load_json(EXPERIMENT / "input_bundle/transformation_record_v1.json")
    parent_plan = load_json(PARENT / "simulation/plan_snapshot.json")
    parent_actions = json.loads((PARENT / "simulation/action_snapshot.json").read_text())["actions"]
    candidate_actions = json.loads((SIM / "action_snapshot.json").read_text())["actions"]
    with gzip.open(PARENT / "simulation/diagnostic_events.json.gz", "rt") as handle:
        parent_events = json.loads(handle.read())["events"]
    for plaintext in (events_path, summary_path):
        compressed_path = plaintext.with_suffix(".json.gz")
        with compressed_path.open("wb") as handle:
            with gzip.GzipFile(filename=plaintext.name, fileobj=handle, mode="wb", mtime=0) as gz:
                gz.write(plaintext.read_bytes())
        plaintext.unlink()

    first_mismatch = next((index for index, (left, right) in enumerate(zip(parent_events, events)) if left != right), None)
    artillery_hits = [
        event for event in events
        if event["event_type"] == "DAMAGE" and event["source_id"] == "char_210_stward" and event["target_id"] == ARTILLERY_ID
    ]
    extra_hits = [event for event in artillery_hits if event["frame"] > 4177]
    artillery_death = [event for event in events if event["event_type"] == "ENEMY_DEATH" and event["target_id"] == ARTILLERY_ID]
    deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
    leaks = [event for event in events if event["event_type"] == "ENEMY_LEAK"]
    errors = action_errors(events)
    central_blocks = [event for event in events if event["event_type"] == "BLOCK" and str(event.get("target_id", "")).startswith("enemy_1110_uamord#")]
    central_leaks = [event for event in leaks if str(event.get("source_id", "")).startswith("enemy_1110_uamord#")]
    device_events = [event for event in events if event["event_type"] == "DEVICE_DESTROYED"]
    protected_reached = [event for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"]
    protected_deaths = [event for event in events if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") == "enemy_3001_upeopl#3"]
    result_without_events = {key: value for key, value in (summary.get("result") or {}).items() if key != "events"}
    relevant_heals = [
        event for event in events
        if event["event_type"] == "HEAL"
        and (event.get("source_id") in {"char_212_ansel", "char_120_hibisc"} or event.get("target_id") in {"char_212_ansel", "char_120_hibisc", "char_210_stward"})
    ]
    observed_key_events = {
        "artillery_window": {
            "steward_to_artillery_hits": {"count": len(artillery_hits), "total_amount": round(sum(item["details"]["amount"] for item in artillery_hits), 2), "frames": [item["frame"] for item in artillery_hits]},
            "extra_hits_after_4177": extra_hits,
            "last_artillery_target_selections_4200_4280": [
                event for event in events
                if event["event_type"] == "TARGET_SELECTION" and event.get("source_id") == "char_210_stward"
                and 4200 <= event.get("frame", 0) <= 4280
            ],
            "artillery_death": artillery_death,
            "artillery_leak": [event for event in leaks if event.get("source_id") == ARTILLERY_ID],
        },
        "in_flight_shell_and_support": [
            event for event in events
            if 4200 <= event.get("frame", 0) <= 4280
            and event["event_type"] in ("ENEMY_ABILITY_HIT", "HEAL", "SKILL_ACTIVATE", "DP_CHANGE", "RETREAT", "OPERATOR_DEATH")
        ],
        "steward_retreat_and_redeploy": [
            event for event in events
            if event.get("source_id") == "char_210_stward"
            and event["event_type"] in ("RETREAT", "DEPLOY")
            and 4200 <= event.get("frame", 0) <= 6500
        ],
        "operator_deaths": deaths,
        "unique_operator_death_ids": sorted({event["source_id"] for event in deaths}),
        "enemy_leaks": leaks,
        "protected_target_reached": protected_reached,
        "protected_target_reached_events": protected_reached,
        "protected_target_deaths": protected_deaths,
        "device_destroyed": device_events,
        "artillery_death": artillery_death,
        "central_blocks": central_blocks,
        "central_leaks": central_leaks,
        "recorded_action_errors": errors,
        "relevant_heals": relevant_heals,
    }

    closeout = {
        "schema_version": "KIMIARK_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_CLOSEOUT_V1",
        "experiment_id": "real_tool_closed_loop_deterministic_seven_c2_coupled_retreat_v1",
        "model": {
            "configured_model": authorization["model"],
            "reasoning_effort": authorization["reasoning_effort"],
            "model_generation": False,
            "real_cli_starts": authorization["real_cli_starts"],
            "usage": "MODEL_USAGE_NOT_APPLICABLE",
            "internal_model_request_count": 0,
        },
        "parent": {
            "record_id": "R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002",
            "plan_id": parent_plan["operational_plan_id"],
            "plan_sha256": digest(PARENT / "simulation/plan_snapshot.json"),
            "action_sha256": digest(PARENT / "simulation/action_snapshot.json"),
            "events_gz_sha256": digest(PARENT / "simulation/diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(PARENT / "simulation/diagnostic_events.json.gz"),
        },
        "candidate": {
            "candidate_id": "candidate-001",
            "plan_id": plan["operational_plan_id"],
            "candidate_sha256": candidate_record["candidate_sha256"],
            "plan_sha256": digest(SIM / "plan_snapshot.json"),
            "action_sha256": digest(SIM / "action_snapshot.json"),
            "events_gz_sha256": digest(SIM / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(SIM / "diagnostic_events.json.gz"),
            "summary_gz_sha256": digest(SIM / "diagnostic_summary.json.gz"),
            "summary_restored_sha256": restored_digest(SIM / "diagnostic_summary.json.gz"),
            "simulator_manifest": manifest,
            "first_planned_deployments": first_planned_deployments(plan),
            "operator_union_count": len(plan["selected_low_star_operator_ids"]),
            "operator_union": plan["selected_low_star_operator_ids"],
            "configured_model": authorization["model"],
            "reasoning_effort": authorization["reasoning_effort"],
            "model_generation": False,
            "observed_key_events": observed_key_events,
        },
        "controlled_transformation": {
            "generation": "DETERMINISTIC_SCRIPT",
            "model_generation": False,
            "authorization": "USER_PROMPT_AUTHORIZED_EXACT_TWO_FRAME_COUPLED_RETIMING",
            "record": transformation,
            "changed_action_count": sum(left != right for left, right in zip(parent_actions, candidate_actions)),
            "changed_actions": [
                {"action_index": index, "parent_action": left, "candidate_action": right}
                for index, (left, right) in enumerate(zip(parent_actions, candidate_actions))
                if left != right
            ],
        },
        "check_and_gate": {
            "session_status": preflight_status,
            "failed_check_001": failed_check,
            "failed_check_reason": "Contract metadata revision_hypothesis contained non-schema fields; tactical action diff was unchanged and repaired before candidate creation.",
            "passed_check_002_response": check_response,
            "passed_check_002_record_file": "Service did not create check_record.json for a PASS check; candidate_record.json and archived MCP response are used.",
            "candidate_ledger": ledger,
            "simulation_budget": budget,
            "static_conflicts": load_json(EXPERIMENT / "session/candidates/candidate-001/source/static_compile_results.json")["conflicts"],
            "production_backend": "CONTROLLED_RUNNER",
            "direct_simulator_bypass": False,
        },
        "control_validity": {
            "event_count_parent": len(parent_events),
            "event_count_candidate": len(events),
            "pre_change_events_equal_count": first_mismatch,
            "first_event_difference_index": first_mismatch,
            "parent_first_difference": parent_events[first_mismatch],
            "candidate_first_difference": events[first_mismatch],
            "boundary": "The first difference is the authorized 4200 retreat being absent; this supports comparability up to 4200 but does not prove causal sufficiency after the divergence.",
        },
        "observed_key_events": observed_key_events,
        "summary_result": result_without_events,
        "classification": summary.get("classification"),
        "interface": {
            "mcp_calls": mcp_call_summary(),
            "candidate_ledger": ledger,
            "simulation_budget": budget,
            "service_failures": "NONE_OBSERVED",
        },
        "closure": {
            "new_win": False,
            "simulator_win": False,
            "best_verified_operator_count": 8,
            "seven_or_fewer_feasibility": "UNKNOWN",
            "targeted_answer": {
                "did_staying_through_4280_produce_extra_output": "YES: 4225 DAMAGE 249.10 and 4273 DAMAGE 473.29.",
                "did_it_close_artillery": "YES for this frozen R101 C2-derived structure: artillery ENEMY_DEATH at 4273 with kill_counted=true; no artillery leak.",
                "was_complete_WIN_obtained": "NO: 21 kills / 12 leaks / life -10; protected #3 died, central armor #21/#22/#33/#34 leaked, and Fang died at 4954.",
                "return_cost": "6381 redeploy was legal and cost 18. Central #21 was blocked at 4646 but leaked later at 5353; no central armor enemy death was recorded. The later return did not close central duties, and terminal differences must not be attributed solely to the retreat.",
                "control_boundary": "Events before 4200 matched for 19,405 entries. After divergence, the candidate is a coupled-retiming control of R101 C2, not proof that every retreat timing or role is general.",
            },
            "complete_settlement": {
                "enemies_killed": 21,
                "enemies_leaked": 12,
                "remaining_life": -10,
                "remaining_enemy_hp": 0,
                "settlement_end_frame": 12449,
                "protected_3": "DIED_AT_3311",
                "protected_14": "REACHED_AT_12448",
                "roadblocks": "#4 destroyed 2443; #3 destroyed 11917; #2 destroyed 12116; #1 not recorded destroyed",
                "central": "#21 blocked 4646 then leaked 5353; #22/#33/#34 no recorded block and leaked 5196/6846/6996",
                "artillery": "45 hits / 13227.21 damage; killed at 4273; no leak",
                "deaths": "2 events / 2 unique IDs: Friston 2111, Fang 4954",
                "action_errors": 0,
            },
            "next_supported_question": "Whether a complete seven-ID plan can retain this 4200-4280 platform closure while replacing or earlier placing the 6301-family central blocker, because #21 still leaked and Fang died before the delayed return.",
            "scope_boundary": [
                "Current fixed simulator only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
                "M70 R8_7_GPT_M70_V1 remains the frozen eight-operator WIN; seven-or-fewer feasibility remains UNKNOWN.",
                "The result is limited to this deterministic two-frame transformation of R101 C2 and does not prove role necessity or seven-ID impossibility.",
            ],
        },
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)
    artifact_manifest = {
        "schema_version": "KIMIARK_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_ARTIFACT_MANIFEST_V1",
        "root": EXPERIMENT.relative_to(ROOT).as_posix(),
        "hash_algorithm": "SHA-256",
        "includes_self": False,
        "self_sha256_path": "closeout_report_v1.json.sha256",
        "files": [],
    }
    excluded_names = {
        "artifact_manifest_v1.json", "closeout_report_v1.json.sha256",
        "candidate_ledger_v1.json.service.lock", "simulation.run.lock", "runner.lock",
    }
    for path in sorted(path for path in EXPERIMENT.rglob("*") if path.is_file() and path.name not in excluded_names):
        entry = {"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = restored_digest(path)
        artifact_manifest["files"].append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", artifact_manifest)
    (closeout_path.with_suffix(closeout_path.suffix + ".sha256")).write_text(f"{digest(closeout_path)}  {closeout_path.name}\n")


if __name__ == "__main__":
    main()
