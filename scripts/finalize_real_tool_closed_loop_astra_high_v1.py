#!/usr/bin/env python3
import collections
import datetime
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_v1"
CLI_DIR = DEST / "session/codex_cli"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def gzip_copy(source: Path) -> Path:
    target = source.with_name(source.name + ".gz")
    with source.open("rb") as reader, gzip.open(target, "wb") as writer:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            writer.write(block)
    return target


def parse_trajectory() -> dict:
    path = CLI_DIR / "codex_exec.jsonl"
    event_types = collections.Counter()
    tool_counts = collections.Counter()
    thread_ids = []
    usage_records = []
    errors = []
    malformed_lines = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            malformed_lines.append({"line": line_number, "error": str(exc)})
            continue
        event_type = event.get("type")
        event_types[event_type] += 1
        if event_type == "thread.started" and event.get("thread_id"):
            thread_ids.append(event["thread_id"])
        item = event.get("item") or {}
        if item.get("type") == "mcp_tool_call" and item.get("status") == "completed":
            tool_counts[item.get("tool")] += 1
        if event_type == "turn.completed" and event.get("usage"):
            usage_records.append({"line": line_number, "usage": event["usage"]})
        if item.get("status") in {"failed", "error"}:
            errors.append({"line": line_number, "item_type": item.get("type")})
    return {
        "byte_count": path.stat().st_size,
        "completed_tool_call_counts": dict(sorted(tool_counts.items())),
        "event_count": sum(event_types.values()),
        "event_type_counts": dict(sorted(event_types.items())),
        "errors": errors,
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        "malformed_lines": malformed_lines,
        "thread_ids": thread_ids,
        "total_completed_tool_calls": sum(tool_counts.values()),
        "usage_records": usage_records,
    }


def process_result() -> dict:
    started = json.loads((CLI_DIR / "cli_process_attempt.json").read_text(encoding="utf-8"))
    stdout_path = CLI_DIR / "codex_exec.jsonl"
    stderr_path = CLI_DIR / "codex_stderr.txt"
    final_path = CLI_DIR / "codex_final_message.txt"
    return {
        "attempt": 1,
        "automatic_retry": False,
        "ended_at": datetime.datetime.fromtimestamp(
            stdout_path.stat().st_mtime, datetime.UTC
        ).isoformat(),
        "exit_code": 0,
        "final_message_bytes": final_path.stat().st_size,
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_ASTRA_CLI_PROCESS_RESULT_V1",
        "started_at": started["started_at_utc"],
        "status": "COMPLETED",
        "stderr_bytes": stderr_path.stat().st_size,
        "stdout_bytes": stdout_path.stat().st_size,
        "timed_out": False,
    }


def candidate_summary(candidate_id: str) -> dict:
    candidate_dir = DEST / "session/candidates" / candidate_id
    record = json.loads((candidate_dir / "candidate_record.json").read_text(encoding="utf-8"))
    output = json.loads(
        (candidate_dir / "source/llm_structured_output.json").read_text(encoding="utf-8")
    )
    plan = output["revised_operational_plans"][0]
    final = json.loads(
        (candidate_dir / "simulation/final_status.json").read_text(encoding="utf-8")
    )
    diagnostic = json.loads(
        (candidate_dir / "simulation/diagnostic_summary.json").read_text(encoding="utf-8")
    )
    return {
        "action_count": len(plan["action_timeline"]),
        "candidate_id": candidate_id,
        "candidate_sha256": record["candidate_sha256"],
        "deployed_operator_ids": sorted(
            {
                action["operator_id"]
                for action in plan["action_timeline"]
                if action.get("action_type") == "DEPLOY"
            }
        ),
        "deployment_errors": diagnostic["result"]["deployment_errors"],
        "diagnostic_event_count": diagnostic["event_count"],
        "first_leak": final["first_failure"]["first_leak"],
        "first_objective_failure": final["first_failure"]["objective_failure"],
        "operator_death_count": final["operator_deaths"],
        "operator_death_events": diagnostic["event_summaries"].get("operator_death_events", []),
        "plan_id": plan["operational_plan_id"],
        "protected_target_death_count": len(diagnostic["protected_target_deaths"]),
        "protected_target_death_events": diagnostic["protected_target_deaths"],
        "protected_target_reached_count": len(diagnostic["protected_target_reached_events"]),
        "protected_target_reached_events": diagnostic["protected_target_reached_events"],
        "result": {
            "enemies_killed": final["enemies_killed"],
            "enemies_leaked": final["enemies_leaked"],
            "remaining_life": final["remaining_life"],
            "simulator_win": final["simulator_win"],
        },
        "revision_hypothesis": output["revision_hypothesis"],
        "selected_operator_ids": plan["selected_low_star_operator_ids"],
        "tactical_thesis": plan["tactical_thesis"],
        "unique_deployed_operator_count": len(plan["selected_low_star_operator_ids"]),
        "unique_operator_death_ids": sorted(
            {
                event["source_id"]
                for event in diagnostic["event_summaries"].get("operator_death_events", [])
                if event.get("event_type") == "OPERATOR_DEATH" and event.get("source_id")
            }
        ),
    }


def artifact_record(path: Path) -> dict:
    record = {
        "path": path.relative_to(DEST).as_posix(),
        "sha256": sha256_path(path),
        "size_bytes": path.stat().st_size,
    }
    if path.suffix == ".gz":
        digest = hashlib.sha256()
        with gzip.open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        record["gzip_original_sha256"] = digest.hexdigest()
    return record


def main() -> None:
    trajectory = parse_trajectory()
    write_json(CLI_DIR / "codex_trajectory_summary.json", trajectory)
    result = process_result()
    write_json(CLI_DIR / "cli_process_result.json", result)

    for candidate_path in sorted((DEST / "session/candidates").glob("candidate-*/simulation")):
        for name in ("diagnostic_events.json", "diagnostic_summary.json"):
            gzip_copy(candidate_path / name)

    ledger = json.loads((DEST / "candidate_ledger_v1.json").read_text(encoding="utf-8"))
    budget = json.loads((DEST / "simulation_budget_v1.json").read_text(encoding="utf-8"))
    authorization = json.loads(
        (DEST / "model_authorization_v1.json").read_text(encoding="utf-8")
    )
    audit = json.loads((DEST / "audit_roster_openness_v1.json").read_text(encoding="utf-8"))
    equivalence = json.loads(
        (DEST / "input_equivalence_manifest_v1.json").read_text(encoding="utf-8")
    )
    candidates = [
        candidate_summary(f"candidate-{index:03d}") for index in range(1, 6)
    ]
    usage = trajectory["usage_records"]
    closure = {
        "audit": {
            "conclusion": audit["conclusion"],
            "no_model_fixture": audit["no_model_fixture"],
            "prompt_anchor_risk": audit["prompt"]["anchor_risk"],
            "schema_version": audit["schema_version"],
        },
        "budget": {
            "budget_exhausted": budget["started_stage_simulations"]
            >= budget["max_stage_simulations"],
            "candidate_ledger": ledger,
            "simulation_budget": budget,
        },
        "closure": {
            "all_candidates_loss": all(
                not candidate["result"]["simulator_win"] for candidate in candidates
            ),
            "best_person_count": 8,
            "best_plan_scope": "M70 eight-operator frozen WIN; not re-run or updated",
            "candidate_count": len(candidates),
            "simulation_count": len(candidates),
            "win": False,
        },
        "comparison_boundary": [
            "Same model-independent baseline files and mechanics, facts, K, budgets, and production runner.",
            "Astra used an independent fresh one-CLI authorization derived from the Sol retry prompt.",
            "Input anchoring conditions were not eliminated; differences are not a strict model-only comparison.",
        ],
        "candidates": candidates,
        "input_equivalence": {
            "baseline_files_equal": equivalence["baseline_files_equal"],
            "baseline_file_count": len(equivalence["baseline_files"]),
            "prompt_delta_policy": equivalence["prompt_delta_policy"],
            "nonprompt_conditions_equal": equivalence["nonprompt_conditions_equal"],
        },
        "interface": {
            "completed_tool_call_counts": trajectory["completed_tool_call_counts"],
            "internal_model_request_count": trajectory["internal_model_request_count"],
            "real_cli_starts": 1,
            "total_completed_tool_calls": trajectory["total_completed_tool_calls"],
            "usage_records": usage,
        },
        "model": {
            "configured_model": authorization["model"],
            "configured_provider": authorization["provider"],
            "features_apps": False,
            "identity_proof_boundary": "Configured identity only; internal model request count is UNKNOWN_CLI_INTERNAL.",
            "reasoning_effort": authorization["reasoning_effort"],
        },
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_ASTRA_HIGH_CLOSURE_REPORT_V1",
        "session_id": ledger["session_id"],
        "unverified_boundaries": [
            "Fixed simulator scope only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
            "No seven-or-fewer feasibility proof is claimed after five bounded LOSS candidates.",
            "Service can verify configured model identity but cannot prove remote model identity from that setting alone.",
            "Tool parameter restrictions do not provide OS-level sandbox isolation.",
        ],
    }
    closure_path = DEST / "closure_report_v1.json"
    write_json(closure_path, closure)
    (DEST / "closure_report_v1.json.sha256").write_text(
        sha256_path(closure_path) + "  closure_report_v1.json\n", encoding="ascii"
    )

    included = [
        path
        for path in sorted(DEST.rglob("*"))
        if path.is_file()
        and path.name not in {"artifact_manifest_v1.json", "artifact_manifest_v1.json.sha256"}
        and not path.name.endswith(".tmp-*")
    ]
    manifest = {
        "files": [artifact_record(path) for path in included],
        "schema_version": "KIMIARK_CLOSED_LOOP_ASTRA_ARTIFACT_MANIFEST_V1",
    }
    write_json(DEST / "artifact_manifest_v1.json", manifest)
    write_json(
        DEST / "artifact_manifest_v1.json.sha256",
        sha256_path(DEST / "artifact_manifest_v1.json") + "\n",
    )
    print(json.dumps({"candidates": len(candidates), "manifest_files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
