#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_v1"
ATTEMPT = EXPERIMENT / "session/codex_cli/attempt_01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    raw_path = ATTEMPT / "codex_exec.jsonl"
    compressed_path = ATTEMPT / "codex_exec.jsonl.gz"
    compressed_path.write_bytes(gzip.compress(raw_path.read_bytes(), mtime=0))
    raw_path.unlink()

    events = [json.loads(line) for line in gzip.decompress(compressed_path.read_bytes()).decode().splitlines() if line.strip()]
    error = next((event["message"] for event in events if event.get("type") == "error"), None)
    turn_failed = next((event for event in events if event.get("type") == "turn.failed"), None)
    result = json.loads((ATTEMPT / "cli_process_result.json").read_text())
    attempt = json.loads((ATTEMPT / "cli_process_attempt.json").read_text())
    preflight = json.loads((EXPERIMENT / "zero_model_preflight_v1.json").read_text())
    failure = {
        "schema_version": "KIMIARK_SEVEN_BREAKPOINT_FAILURE_REPORT_V1",
        "experiment_id": "real_tool_closed_loop_astra_high_seven_breakpoint_v1",
        "best_verified_result": {"operator_count": 8, "plan_id": "R8_7_GPT_M70_V1", "simulator_win": True},
        "decision": {"new_tactical_result": False, "best_verified_operator_count": 8, "seven_or_fewer_feasibility": "UNKNOWN"},
        "authorization_and_usage": {
            "provider": "openai",
            "model": "gpt-6-astra",
            "reasoning_effort": "high",
            "features_apps": False,
            "real_cli_starts": "1/1",
            "completed_model_turns": 0,
            "check_calls": "0/10",
            "candidates": "0/2",
            "simulations": "0/2",
            "visible_usage": None,
            "internal_requests": "UNKNOWN_CLI_INTERNAL",
            "cached_input_is_subset_of_input": True,
            "automatic_retry": False,
            "automatic_resume": False,
            "attempt_3_authorized": False,
        },
        "process": {**result, "mcp_tool_calls": {"total": 0, "by_tool": {}}},
        "jsonl_event_counts": dict(sorted(Counter(event.get("type") for event in events).items())),
        "failure": {
            "client_visible_layer": "usage_limit",
            "error_message": error,
            "turn_failed": turn_failed,
            "turn_completed": result["turn_completed"],
            "exit_code": result["exit_code"],
            "classification": "QUOTA_LIMIT_BEFORE_ANY_MCP_TOOL_CALL",
        },
        "preflight": {
            "input_bundle_manifest_all_hashes_match": preflight["input_bundle"]["manifest_all_hashes_match"],
            "codex_doctor_overall_status": preflight["codex_doctor"]["overall_status"],
            "mcp_no_model_status_passed": True,
            "proxy_prestart_path": "session/codex_cli/attempt_01/proxy_prestart.json",
            "coverage_boundary": "Preflight did not and cannot prove a real model turn. The authorized CLI was that verification and hit usage limit before any MCP tool call.",
        },
        "tactical_boundary": {
            "model_changed": False,
            "simulator_or_mechanics_changed": False,
            "tactical_assumption_changed": False,
            "loss_claimed": False,
            "quota_used_as_tactical_evidence": False,
        },
        "archive": {
            "prompt_sha256": attempt["prompt_sha256"],
            "jsonl_gz_sha256": digest(compressed_path),
            "jsonl_gz_restored_sha256": restored_digest(compressed_path),
            "old_evidence_preserved": True,
        },
    }
    write_json(EXPERIMENT / "failure_report_v1.json", failure)

    files = []
    for path in sorted(EXPERIMENT.rglob("*")):
        if path.is_file() and path.name != "attempt_artifact_manifest_v1.json":
            entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
            if path.suffix == ".gz":
                entry["restored_sha256"] = restored_digest(path)
            files.append(entry)
    write_json(EXPERIMENT / "attempt_artifact_manifest_v1.json", {
        "schema_version": "KIMIARK_SEVEN_BREAKPOINT_ATTEMPT_ARTIFACT_MANIFEST_V1",
        "files": files,
    })
    print(json.dumps({"archive": "PASS", "files": len(files)}))


if __name__ == "__main__":
    main()
