#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_duty_conflict_v1"
ATTEMPT = EXPERIMENT / "session/codex_cli/attempt_01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def compress(source: Path, target: Path) -> dict[str, str | int]:
    target.write_bytes(gzip.compress(source.read_bytes(), mtime=0))
    return {"bytes": target.stat().st_size, "sha256": digest(target), "restored_sha256": restored_digest(target)}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    compressed = []
    for candidate_id in ("candidate-001", "candidate-002"):
        simulation = EXPERIMENT / f"session/candidates/{candidate_id}/simulation"
        for name in ("diagnostic_events.json", "diagnostic_summary.json"):
            archive = simulation / f"{name}.gz"
            if not archive.exists():
                compressed.append({"candidate_id": candidate_id, "path": archive.relative_to(ROOT).as_posix(), **compress(simulation / name, archive)})
                (simulation / name).unlink()

    jsonl_path = ATTEMPT / "codex_exec.jsonl"
    jsonl_archive = ATTEMPT / "codex_exec.jsonl.gz"
    events = [json.loads(line) for line in gzip.decompress(jsonl_archive.read_bytes()).decode().splitlines() if line.strip()]
    turn = next((event for event in events if event.get("type") == "turn.completed"), None)
    failure = next(event for event in events if event.get("type") == "turn.failed")
    raw_tools = Counter()
    completed_tools = Counter()
    for event in events:
        item = event.get("item") or {}
        if item.get("type") == "mcp_tool_call":
            raw_tools[item.get("tool")] += 1
            if event.get("type") == "item.completed":
                completed_tools[item.get("tool")] += 1
    if not jsonl_archive.exists():
        compressed.append({"path": jsonl_archive.relative_to(ROOT).as_posix(), **compress(jsonl_path, jsonl_archive)})
        jsonl_path.unlink()

    result = load(ATTEMPT / "cli_process_result.json")
    candidates = []
    for candidate_id in ("candidate-001", "candidate-002"):
        simulation = EXPERIMENT / f"session/candidates/{candidate_id}/simulation"
        final = load(simulation / "final_status.json")
        plan = load(simulation / "plan_snapshot.json")
        candidates.append({
            "candidate_id": candidate_id,
            "candidate_sha256": next(item["candidate_sha256"] for item in load(EXPERIMENT / "candidate_ledger_v1.json")["attempts"] if item["candidate_id"] == candidate_id),
            "plan_id": final["plan_id"],
            "roster_operator_ids": plan["selected_low_star_operator_ids"],
            "final_status": final,
            "hashes": {
                "plan_snapshot_sha256": digest(simulation / "plan_snapshot.json"),
                "action_snapshot_sha256": digest(simulation / "action_snapshot.json"),
                "final_status_sha256": digest(simulation / "final_status.json"),
                "diagnostic_events_gz_sha256": digest(simulation / "diagnostic_events.json.gz"),
                "diagnostic_events_restored_sha256": restored_digest(simulation / "diagnostic_events.json.gz"),
                "diagnostic_summary_gz_sha256": digest(simulation / "diagnostic_summary.json.gz"),
                "diagnostic_summary_restored_sha256": restored_digest(simulation / "diagnostic_summary.json.gz"),
            },
        })

    closeout = {
        "schema_version": "KIMIARK_SEVEN_DUTY_CONFLICT_CLOSEOUT_REPORT_V1",
        "experiment_id": "real_tool_closed_loop_astra_high_seven_duty_conflict_v1",
        "best_verified_result": {"operator_count": 8, "plan_id": "R8_7_GPT_M70_V1", "simulator_win": True},
        "decision": {"new_win": False, "best_verified_operator_count": 8, "seven_or_fewer_feasibility": "UNKNOWN"},
        "authorization_and_usage": {
            "provider": "openai",
            "model": "gpt-6-astra",
            "reasoning_effort": "high",
            "features_apps": False,
            "real_cli_starts": "1/1",
            "check_calls": "4/10",
            "candidates": "2/2",
            "simulations": "2/2",
            "automatic_retry": False,
            "automatic_resume": False,
            "internal_requests": "UNKNOWN_CLI_INTERNAL",
            "cached_input_is_subset_of_input": True,
            "visible_usage": turn.get("usage") if turn else None,
        },
        "process": {
            **result,
            "jsonl_event_counts": dict(sorted(Counter(event.get("type") for event in events).items())),
            "terminal_turn_failed": failure,
            "mcp_tool_calls": {
                "raw_started_plus_completed": {"total": sum(raw_tools.values()), "by_tool": dict(sorted(raw_tools.items()))},
                "completed_unique_by_tool": {"total": sum(completed_tools.values()), "by_tool": dict(sorted(completed_tools.items()))},
            },
        },
        "candidates": candidates,
        "validation_summary": {
            "candidate_001": "LOSS 13/20 with 8 deaths and life -19; first leak was officer#13@3425. The duty-conflict restructuring failed opening/route pressure and cannot validate the targeted support-conflict chain.",
            "candidate_002": "LOSS 12/21 with 8 deaths and life -20; first leak was officer#11@3065. Earlier healer support did not recover opening/route closure and worsened the full result.",
            "terminal_model_status": "After both complete simulations and event queries, the CLI hit usage limit before turn.completed/final message. The two tactical LOSS results remain complete; no post-simulation final synthesis was produced.",
        },
        "archive_compression": compressed,
    }
    write_json(EXPERIMENT / "closeout_report_v1.json", closeout)

    files = []
    for path in sorted(EXPERIMENT.rglob("*")):
        if path.is_file() and path.name != "attempt_artifact_manifest_v1.json":
            entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
            if path.suffix == ".gz":
                entry["restored_sha256"] = restored_digest(path)
            files.append(entry)
    write_json(EXPERIMENT / "attempt_artifact_manifest_v1.json", {
        "schema_version": "KIMIARK_SEVEN_DUTY_CONFLICT_ATTEMPT_ARTIFACT_MANIFEST_V1",
        "files": files,
    })
    print(json.dumps({"closeout": "PASS", "files": len(files)}))


if __name__ == "__main__":
    main()
