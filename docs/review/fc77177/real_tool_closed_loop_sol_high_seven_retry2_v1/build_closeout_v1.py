#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry2_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    candidate_dir = EXPERIMENT / "session/candidates/candidate-001/simulation"
    events_path = candidate_dir / "diagnostic_events.json"
    summary_path = candidate_dir / "diagnostic_summary.json"
    events_payload = json.loads(events_path.read_text())
    summary_payload = json.loads(summary_path.read_text())
    events = events_payload["events"]
    for plaintext in (events_path, summary_path):
        compressed_path = plaintext.with_suffix(".json.gz")
        with compressed_path.open("wb") as handle:
            with gzip.GzipFile(filename=plaintext.name, fileobj=handle, mtime=0) as gz:
                gz.write(plaintext.read_bytes())
        plaintext.unlink()

    final_status = json.loads((candidate_dir / "final_status.json").read_text())
    plan = json.loads((candidate_dir / "plan_snapshot.json").read_text())
    action = json.loads((candidate_dir / "action_snapshot.json").read_text())
    manifest = json.loads((candidate_dir / "manifest.json").read_text())
    process = json.loads((EXPERIMENT / "session/codex_cli/attempt_01/cli_process_result.json").read_text())
    authorization = json.loads((EXPERIMENT / "model_authorization_v1.json").read_text())
    ledger = json.loads((EXPERIMENT / "candidate_ledger_v1.json").read_text())
    budget = json.loads((EXPERIMENT / "simulation_budget_v1.json").read_text())
    preflight = json.loads((EXPERIMENT / "zero_model_preflight_v1.json").read_text())
    final_message = (EXPERIMENT / "session/codex_cli/attempt_01/codex_final_message.txt").read_text()

    operator_deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
    leaks = [event for event in events if event["event_type"] == "ENEMY_LEAK"]
    protected_reached = [event for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"]
    protected_3_death = [event for event in events if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") == "enemy_3001_upeopl#3"]
    devices = [event for event in events if event["event_type"] == "DEVICE_DESTROYED"]
    steward_artillery_damage = [
        event for event in events
        if event["event_type"] == "DAMAGE"
        and event.get("source_id") == "char_210_stward"
        and event.get("target_id") == "enemy_1112_emppnt#0"
    ]

    closeout = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY2_CLOSEOUT_REPORT_V1",
        "experiment_id": "real_tool_closed_loop_sol_high_seven_retry2_v1",
        "model": {
            "provider": authorization["provider"],
            "configured_model": authorization["model"],
            "reasoning_effort": authorization["reasoning_effort"],
            "features_apps": authorization["features_apps"],
            "identity_proof_boundary": "Configured identity only; no cryptographic model identity was proven.",
        },
        "process": process,
        "preflight": {
            "codex_effective_mcp": preflight["codex_effective_mcp"],
            "mcp_no_model_status": preflight["mcp_no_model_status"],
            "coverage_boundary": preflight["coverage_boundary"],
        },
        "interface": {
            "real_cli_starts": authorization["real_cli_starts"],
            "candidate_ledger": ledger,
            "simulation_budget": budget,
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "visible_usage_records": [],
        },
        "candidate": {
            "candidate_id": "candidate-001",
            "candidate_sha256": ledger["attempts"][0]["candidate_sha256"],
            "plan_id": plan["operational_plan_id"],
            "plan_sha256": digest(candidate_dir / "plan_snapshot.json"),
            "action_sha256": digest(candidate_dir / "action_snapshot.json"),
            "events_gz_sha256": digest(candidate_dir / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(candidate_dir / "diagnostic_events.json.gz"),
            "summary_gz_sha256": digest(candidate_dir / "diagnostic_summary.json.gz"),
            "summary_restored_sha256": restored_digest(candidate_dir / "diagnostic_summary.json.gz"),
            "selected_operator_ids": plan["selected_low_star_operator_ids"],
            "selected_operator_names": ["芬", "Friston-3", "月见夜", "玫兰莎", "安赛尔", "史都华德", "斑点"],
            "unique_deployed_operator_count": len(plan["selected_low_star_operator_ids"]),
            "tactical_parent": plan["validation_card"]["parent"],
            "final_status": final_status,
            "simulator_manifest": manifest,
            "observed_key_events": {
                "operator_death_events": operator_deaths,
                "unique_operator_death_ids": sorted({event["source_id"] for event in operator_deaths}),
                "enemy_leaks": leaks,
                "protected_target_reached": protected_reached,
                "protected_target_3_death": protected_3_death,
                "device_destroyed": devices,
                "steward_artillery_damage": {
                    "hit_count": len(steward_artillery_damage),
                    "total_amount": sum(event["details"]["amount"] for event in steward_artillery_damage),
                    "frames": [event["frame"] for event in steward_artillery_damage],
                },
            },
        },
        "closure": {
            "new_win": False,
            "best_verified_operator_count": 8,
            "seven_or_fewer_feasibility": "UNKNOWN",
            "second_candidate_used": False,
            "model_reason_second_unused": final_message,
        },
        "scope_boundary": [
            "Current fixed simulator only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
            "No claim of seven-ID impossibility after one complete bounded LOSS.",
            "M70 R8_7_GPT_M70_V1 remains the frozen eight-operator WIN and was not rerun.",
        ],
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)

    manifest_payload = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY2_ARTIFACT_MANIFEST_V1",
        "root": EXPERIMENT.relative_to(ROOT).as_posix(),
        "hash_algorithm": "SHA-256",
        "includes_self": False,
        "self_sha256_path": "closeout_report_v1.json.sha256",
        "files": [],
    }
    excluded_names = {
        "artifact_manifest_v1.json",
        "closeout_report_v1.json.sha256",
        "candidate_ledger_v1.json.service.lock",
        "simulation.run.lock",
        "runner.lock",
    }
    for path in sorted(path for path in EXPERIMENT.rglob("*") if path.is_file() and path.name not in excluded_names):
        entry = {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = restored_digest(path)
        manifest_payload["files"].append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", manifest_payload)
    (closeout_path.with_suffix(closeout_path.suffix + ".sha256")).write_text(
        f"{digest(closeout_path)}  {closeout_path.name}\n"
    )


if __name__ == "__main__":
    main()
