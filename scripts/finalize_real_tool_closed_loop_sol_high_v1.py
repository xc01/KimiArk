#!/usr/bin/env python3
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path


def load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gzip_original_sha256(path):
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_jsonl(path):
    events = []
    malformed_lines = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            malformed_lines.append({"line": line_number, "error": str(exc)})
    return events, malformed_lines


def summarize_cli_attempt(attempt_root):
    events, malformed = parse_jsonl(attempt_root / "codex_exec.jsonl")
    completed_tools = []
    usage_records = []
    thread_ids = []
    event_type_counts = collections.Counter(event.get("type") for event in events)
    for line_number, event in enumerate(events, 1):
        if event.get("type") == "thread.started" and event.get("thread_id"):
            thread_ids.append(event["thread_id"])
        item = event.get("item")
        if event.get("type") == "item.completed" and isinstance(item, dict) and item.get("type") == "mcp_tool_call":
            completed_tools.append(item.get("tool", "UNKNOWN_TOOL"))
        if event.get("type") == "turn.completed" and event.get("usage"):
            usage_records.append({"line": line_number, "usage": event["usage"]})
    tool_counts = dict(sorted(collections.Counter(completed_tools).items()))
    return {
        "attempt_root": str(attempt_root.relative_to(attempt_root.parents[3])),
        "events": events,
        "summary": {
            "event_count": len(events),
            "event_type_counts": dict(sorted(event_type_counts.items())),
            "completed_tool_call_counts": tool_counts,
            "total_completed_tool_calls": len(completed_tools),
            "thread_ids": thread_ids,
            "usage_records": usage_records,
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "malformed_lines": malformed,
        },
    }


def compact_attempt_events(ledger):
    return [
        {
            "candidate_id": item.get("candidate_id"),
            "candidate_sha256": item.get("candidate_sha256"),
            "kind": item.get("kind"),
            "status": item.get("status"),
            "errors": item.get("errors", []),
        }
        for item in ledger.get("checks", [])
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root
    session_config = load_json(root / "session_config_v1.json")
    budget = load_json(root / "simulation_budget_v1.json")
    ledger = load_json(root / "candidate_ledger_v1.json")
    retry_authorization = load_json(
        root / "session/codex_cli/attempt_02/retry_authorization_v1.json"
    )
    attempt_1 = summarize_cli_attempt(root / "session/codex_cli")
    attempt_2 = summarize_cli_attempt(root / "session/codex_cli/attempt_02")
    attempt_1_process = load_json(root / "session/codex_cli/cli_process_result.json")
    attempt_2_process = load_json(root / "session/codex_cli/attempt_02/cli_process_result.json")

    candidates = []
    for index in range(1, budget["started_stage_simulations"] + 1):
        candidate_id = f"candidate-{index:03d}"
        candidate_root = root / "session/candidates" / candidate_id
        record = load_json(candidate_root / "candidate_record.json")
        final_status = load_json(candidate_root / "simulation/final_status.json")
        diagnostic_summary = load_json(candidate_root / "simulation/diagnostic_summary.json")
        action_snapshot = load_json(candidate_root / "simulation/action_snapshot.json")
        structured_output = load_json(candidate_root / "source/llm_structured_output.json")
        raw_events = load_json(candidate_root / "simulation/diagnostic_events.json")["events"]
        operator_deaths = [event for event in raw_events if event.get("event_type") == "OPERATOR_DEATH"]
        protected_deaths = [
            event for event in raw_events
            if event.get("event_type") == "ENEMY_DEATH"
            and str(event.get("target_id", "")).startswith("enemy_3001_upeopl#")
        ]
        protected_reached = [
            event for event in raw_events if event.get("event_type") == "PROTECTED_TARGET_REACHED"
        ]
        candidates.append({
            "candidate_id": candidate_id,
            "candidate_sha256": record["candidate_sha256"],
            "check_id": record["check_id"],
            "revision_hypothesis": structured_output.get("revision_hypothesis"),
            "plan_id": final_status["plan_id"],
            "action_count": len(action_snapshot["actions"]),
            "deployed_operator_ids": sorted({
                action["operator_id"] for action in action_snapshot["actions"]
                if action.get("action_type") == "DEPLOY"
            }),
            "unique_deployed_operator_count": record["unique_deployed_operator_count"],
            "result": {
                "simulator_win": final_status["simulator_win"],
                "enemies_killed": final_status["enemies_killed"],
                "enemies_leaked": final_status["enemies_leaked"],
                "remaining_life": final_status["remaining_life"],
                "score": diagnostic_summary["result"]["score"],
                "time_survived": diagnostic_summary["result"]["time_survived"],
            },
            "first_leak": final_status["first_failure"]["first_leak"],
            "first_objective_failure": final_status["first_failure"]["objective_failure"],
            "deployment_errors": diagnostic_summary["result"]["deployment_errors"],
            "operator_death_count": len(operator_deaths),
            "unique_operator_death_ids": sorted({event["source_id"] for event in operator_deaths}),
            "operator_death_events": operator_deaths,
            "protected_target_death_count": len(protected_deaths),
            "protected_target_death_events": protected_deaths,
            "protected_target_reached_count": len(protected_reached),
            "protected_target_reached_events": protected_reached,
            "diagnostic_event_count": len(raw_events),
        })

    combined_tool_counts = collections.Counter()
    for attempt in (attempt_1, attempt_2):
        combined_tool_counts.update(attempt["summary"]["completed_tool_call_counts"])
    usage_records = []
    for attempt_index, attempt in enumerate((attempt_1, attempt_2), 1):
        for record in attempt["summary"]["usage_records"]:
            usage_records.append({"attempt": attempt_index, **record})

    report = {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_SOL_HIGH_CLOSURE_REPORT_V1",
        "session_id": session_config["session_id"],
        "model": {
            "configured_provider": "openai",
            "configured_model": session_config["model"],
            "reasoning_effort": session_config["reasoning_effort"],
            "features_apps": session_config["features_apps"],
            "identity_proof_boundary": "Configured identity only; internal model request count is UNKNOWN_CLI_INTERNAL.",
        },
        "cli_attempts": [
            {
                "attempt": 1,
                "process_result": attempt_1_process,
                "trajectory_summary": attempt_1["summary"],
                "service_fault_report": load_json(root / "failure_report_v1.json"),
            },
            {
                "attempt": 2,
                "process_result": attempt_2_process,
                "trajectory_summary": attempt_2["summary"],
                "retry_authorization": retry_authorization,
                "stderr_error_note": "Completed normally despite trailing model catalog refresh timeout warnings; tactical tools, candidates, and simulations completed.",
            },
        ],
        "interface": {
            "combined_completed_tool_call_counts": dict(sorted(combined_tool_counts.items())),
            "combined_completed_tool_calls": sum(combined_tool_counts.values()),
            "real_cli_starts": 2,
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "visible_usage_records": usage_records,
        },
        "budget": {
            "simulation_budget": budget,
            "candidate_ledger": ledger,
            "compact_checks": compact_attempt_events(ledger),
            "remaining_candidates": 0,
            "remaining_check_calls": ledger["max_check_calls"] - ledger["used_check_calls"],
            "remaining_simulations": 0,
            "budget_exhausted": True,
        },
        "closure": {
            "win": False,
            "best_person_count": 8,
            "best_plan_scope": "M70 eight-operator frozen WIN; not re-run or updated",
            "candidate_count": len(candidates),
            "simulation_count": len(candidates),
            "all_candidates_loss": all(not item["result"]["simulator_win"] for item in candidates),
        },
        "candidates": candidates,
        "unverified_boundaries": [
            "Fixed simulator scope only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
            "No seven-or-fewer feasibility proof is claimed after five bounded LOSS candidates.",
            "Service can verify configured model identity but cannot prove remote model identity from that setting alone.",
            "Tool parameter restrictions do not provide OS-level sandbox isolation.",
        ],
    }
    report_path = root / "closure_report_v1.json"
    write_json(report_path, report)
    (root / "session/codex_cli/codex_trajectory_summary.json").write_text(
        json.dumps(attempt_1["summary"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "session/codex_cli/attempt_02/codex_trajectory_summary.json").write_text(
        json.dumps(attempt_2["summary"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_SOL_HIGH_ARTIFACT_MANIFEST_V1",
        "root": str(root),
        "hash_algorithm": "SHA-256",
        "includes_self": False,
        "self_sha256_path": "closure_report_v1.json.sha256",
        "files": [],
    }
    excluded_names = {
        "diagnostic_events.json",
        "diagnostic_summary.json",
        "artifact_manifest_v1.json",
        "closure_report_v1.json.sha256",
    }
    all_paths = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in all_paths:
        if path.name in excluded_names:
            continue
        relative_path = path.relative_to(root).as_posix()
        entry = {"path": relative_path, "size_bytes": path.stat().st_size, "sha256": sha256(path)}
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = gzip_original_sha256(path)
        manifest["files"].append(entry)
    manifest_path = root / "artifact_manifest_v1.json"
    write_json(manifest_path, manifest)
    report_path.with_suffix(report_path.suffix + ".sha256").write_text(
        f"{sha256(report_path)}  {report_path.name}\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
