#!/usr/bin/env python3
import argparse
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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def gzip_original_sha256(path):
    with gzip.open(path, "rb") as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root

    session_config = load_json(root / "session_config_v1.json")
    budget = load_json(root / "simulation_budget_v1.json")
    candidate_ledger = load_json(root / "candidate_ledger_v1.json")
    trajectory = load_json(root / "session/codex_cli/codex_trajectory_summary.json")

    tool_counts = {}
    for record in trajectory["events"]:
        item = record.get("event", {}).get("item", {})
        if item.get("type") == "mcp_tool_call" and item.get("status") == "completed":
            tool = item.get("tool", "UNKNOWN_TOOL")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1

    candidates = []
    for index in range(1, budget["started_stage_simulations"] + 1):
        candidate_id = f"candidate-{index:03d}"
        candidate_root = root / "session/candidates" / candidate_id
        candidate_record = load_json(candidate_root / "candidate_record.json")
        final_status = load_json(candidate_root / "simulation/final_status.json")
        diagnostic_summary = load_json(candidate_root / "simulation/diagnostic_summary.json")
        action_snapshot = load_json(candidate_root / "simulation/action_snapshot.json")
        raw_events = load_json(candidate_root / "simulation/diagnostic_events.json")["events"]
        structured_output = load_json(
            candidate_root / "source/llm_structured_output.json"
        )

        operator_deaths = []
        protected_deaths = []
        protected_reached = []
        for event in raw_events:
            event_type = event.get("event_type")
            if event_type == "OPERATOR_DEATH":
                operator_deaths.append(event)
            elif event_type == "ENEMY_DEATH" and str(event.get("target_id", "")).startswith("enemy_3001_upeopl#"):
                protected_deaths.append(event)
            elif event_type == "PROTECTED_TARGET_REACHED":
                protected_reached.append(event)

        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_sha256": candidate_record["candidate_sha256"],
                "check_id": candidate_record["check_id"],
                "revision_hypothesis": structured_output.get("revision_hypothesis"),
                "plan_id": final_status["plan_id"],
                "action_count": len(action_snapshot["actions"]),
                "deployed_operator_ids": sorted(
                    {
                        action["operator_id"]
                        for action in action_snapshot["actions"]
                        if action.get("action_type") == "DEPLOY"
                    }
                ),
                "unique_deployed_operator_count": candidate_record["unique_deployed_operator_count"],
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
            }
        )

    report = {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_TERRA_V3_CLOSURE_REPORT_V1",
        "session_id": session_config["session_id"],
        "model": {
            "configured_provider": "openai",
            "configured_model": session_config["model"],
            "reasoning_effort": session_config["reasoning_effort"],
            "features_apps": session_config["features_apps"],
            "identity_proof_boundary": "Configured identity only; internal model request count is UNKNOWN_CLI_INTERNAL.",
        },
        "cli": {
            "real_cli_starts": 1,
            "process_status": "COMPLETED",
            "exit_code": 0,
            "timed_out": False,
            "thread_ids": trajectory["thread_ids"],
            "session_ids": trajectory["session_ids"],
            "internal_model_request_count": trajectory["internal_model_request_count"],
            "usage_records": trajectory["usage_records"],
        },
        "interface": {
            "tool_call_counts": dict(sorted(tool_counts.items())),
            "total_completed_tool_calls": sum(tool_counts.values()),
            "real_cli_starts": 1,
            "internal_model_request_count": trajectory["internal_model_request_count"],
        },
        "budget": {
            "simulation_budget": budget,
            "candidate_ledger": candidate_ledger,
            "remaining_candidates": 0,
            "remaining_check_calls": candidate_ledger["max_check_calls"]
            - candidate_ledger["used_check_calls"],
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
            "Service can verify configured model identity but cannot prove the remote model identity from that setting alone.",
            "Tool parameter restrictions do not provide OS-level sandbox isolation.",
        ],
    }
    report_path = root / "closure_report_v1.json"
    write_json(report_path, report)

    manifest = {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_TERRA_V3_ARTIFACT_MANIFEST_V1",
        "root": str(root),
        "hash_algorithm": "SHA-256",
        "includes_self": False,
        "self_sha256_path": "closure_report_v1.json.sha256",
        "files": [],
    }
    all_paths = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in all_paths:
        if not path.is_file() or path.name in {
            "diagnostic_events.json",
            "diagnostic_summary.json",
            "artifact_manifest_v1.json",
            "closure_report_v1.json.sha256",
        }:
            continue
        relative_path = path.relative_to(root).as_posix()
        entry = {
            "path": relative_path,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
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
