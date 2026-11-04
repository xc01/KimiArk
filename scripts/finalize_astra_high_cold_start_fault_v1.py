#!/usr/bin/env python3
import collections
import datetime
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_cold_start_v1"
CLI = DEST / "session/codex_cli"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def gzip_copy(path: Path) -> Path:
    target = path.with_name(path.name + ".gz")
    with path.open("rb") as source, gzip.open(target, "wb") as target_file:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            target_file.write(block)
    return target


def trajectory() -> dict:
    counts = collections.Counter()
    tools = collections.Counter()
    threads = []
    malformed = []
    errors = []
    for line_number, line in enumerate((CLI / "codex_exec.jsonl").read_text().splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            malformed.append({"line": line_number, "error": str(exc)})
            continue
        event_type = event.get("type")
        counts[event_type] += 1
        if event_type == "thread.started":
            threads.append(event.get("thread_id"))
        item = event.get("item") or {}
        if item.get("type") == "mcp_tool_call" and item.get("status") == "completed":
            tools[item.get("tool")] += 1
        if item.get("status") in {"failed", "error"}:
            errors.append({"line": line_number, "item_type": item.get("type"), "message": item.get("message")})
    stderr = (CLI / "codex_stderr.txt").read_text(encoding="utf-8")
    return {
        "byte_count": (CLI / "codex_exec.jsonl").stat().st_size,
        "completed_tool_call_counts": dict(sorted(tools.items())),
        "event_count": sum(counts.values()),
        "event_type_counts": dict(sorted(counts.items())),
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        "malformed_lines": malformed,
        "stderr_model_refresh_timeout_count": stderr.count("failed to refresh available models"),
        "thread_ids": threads,
        "total_completed_tool_calls": sum(tools.values()),
        "usage_records": [],
    }


def record(path: Path) -> dict:
    row = {"path": path.relative_to(DEST).as_posix(), "sha256": sha(path), "size_bytes": path.stat().st_size}
    if path.suffix == ".gz":
        digest = hashlib.sha256()
        with gzip.open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        row["gzip_original_sha256"] = digest.hexdigest()
    return row


def main() -> None:
    summary = trajectory()
    write(CLI / "codex_trajectory_summary.json", summary)
    started = json.loads((CLI / "cli_process_attempt.json").read_text(encoding="utf-8"))
    stdout_path = CLI / "codex_exec.jsonl"
    stderr_path = CLI / "codex_stderr.txt"
    final_path = CLI / "codex_final_message.txt"
    process_result = {
        "attempt": 1,
        "automatic_retry": False,
        "ended_at": datetime.datetime.fromtimestamp(stdout_path.stat().st_mtime, datetime.UTC).isoformat(),
        "exit_code": "UNKNOWN_HOST_SESSION_ABORTED",
        "final_message_exists": final_path.is_file(),
        "final_message_bytes": final_path.stat().st_size if final_path.is_file() else 0,
        "schema_version": "KIMIARK_COLD_START_CLI_PROCESS_RESULT_V1",
        "started_at": started["started_at_utc"],
        "status": "FAILED_SESSION_ABORTED",
        "stderr_bytes": stderr_path.stat().st_size,
        "stdout_bytes": stdout_path.stat().st_size,
        "timed_out": False,
        "turn_completed": False,
    }
    write(CLI / "cli_process_result.json", process_result)

    ledger = json.loads((DEST / "candidate_ledger_v1.json").read_text(encoding="utf-8"))
    budget = json.loads((DEST / "simulation_budget_v1.json").read_text(encoding="utf-8"))
    audit = json.loads((DEST / "cold_start_context_audit_v1.json").read_text(encoding="utf-8"))
    test_results = json.loads((DEST / "focused_service_test_results_v1.json").read_text(encoding="utf-8"))
    failure = {
        "budget": {
            "candidate_ledger": ledger,
            "simulation_budget": budget,
            "used_real_cli_starts": 1,
            "max_real_cli_starts": 1,
        },
        "closure": {
            "best_person_count": 8,
            "best_plan_scope": "M70 eight-operator frozen WIN; not re-run or updated",
            "candidates_simulated": 0,
            "tactical_result": "NO_TACTICAL_RESULT_AND_NOT_LOSS",
            "win": False,
        },
        "fault": {
            "automatic_resume_or_retry": False,
            "category": "HOST_SESSION_ABORTED_WITHOUT_TURN_COMPLETION",
            "final_message": False,
            "model_catalog_refresh_warnings": summary["stderr_model_refresh_timeout_count"],
            "model_inference_count": "UNKNOWN_CLI_INTERNAL",
            "started": True,
        },
        "preflight": {
            "cold_start_context_audit": audit,
            "focused_service_tests": test_results,
            "mcp_handshake": "PASS",
        },
        "schema_version": "KIMIARK_COLD_START_FAULT_REPORT_V1",
        "session_id": ledger["session_id"],
    }
    failure_path = DEST / "failure_report_v1.json"
    write(failure_path, failure)
    (DEST / "failure_report_v1.json.sha256").write_text(sha(failure_path) + "\n", encoding="ascii")

    gzip_copy(stdout_path)
    gzip_copy(DEST / "cold_start_input_bundle/llm_evidence_context.json")
    included = [path for path in sorted(DEST.rglob("*")) if path.is_file() and path.name != "artifact_manifest_v1.json"]
    manifest = {"files": [record(path) for path in included], "schema_version": "KIMIARK_COLD_START_ARTIFACT_MANIFEST_V1"}
    write(DEST / "artifact_manifest_v1.json", manifest)
    print(json.dumps({"files": len(manifest["files"]), "tools": summary["completed_tool_call_counts"]}))


if __name__ == "__main__":
    main()
