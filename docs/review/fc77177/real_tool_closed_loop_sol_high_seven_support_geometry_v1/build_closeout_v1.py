#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_support_geometry_v1"


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
                "plan_action_tile": action["tile"],
                "runtime_tile": list(reversed(action["tile"])),
            }
    return result


def action_errors(events: list[dict]) -> list[dict]:
    deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
    result = []
    for event in events:
        if event["event_type"] not in ("DEPLOY", "RETREAT", "SKILL_ACTIVATE") or event.get("details", {}).get("legal") is not False:
            continue
        death_frame = next((death["frame"] for death in deaths if death["source_id"] == event["source_id"] and death["frame"] <= event["frame"]), None)
        result.append({
            "frame": event["frame"],
            "event_type": event["event_type"],
            "source_id": event["source_id"],
            "executor_death_frame": death_frame,
            "classification": "dependency_failure_after_executor_death" if death_frame is not None else "independent_action_error",
        })
    return result


def main() -> None:
    process = json.loads((EXPERIMENT / "session/codex_cli/attempt_01/cli_process_result.json").read_text())
    authorization = json.loads((EXPERIMENT / "model_authorization_v1.json").read_text())
    ledger = json.loads((EXPERIMENT / "candidate_ledger_v1.json").read_text())
    budget = json.loads((EXPERIMENT / "simulation_budget_v1.json").read_text())
    preflight = json.loads((EXPERIMENT / "zero_model_preflight_v1.json").read_text())
    final_message = (EXPERIMENT / "session/codex_cli/attempt_01/codex_final_message.txt").read_text()
    candidate_summaries = []
    for candidate_index in (1, 2):
        candidate_dir = EXPERIMENT / f"session/candidates/candidate-{candidate_index:03d}/simulation"
        events_path = candidate_dir / "diagnostic_events.json"
        summary_path = candidate_dir / "diagnostic_summary.json"
        if events_path.is_file():
            with events_path.open("rt") as handle:
                events = json.loads(handle.read())["events"]
            summary = json.loads(summary_path.read_text())
        else:
            events_path = candidate_dir / "diagnostic_events.json.gz"
            summary_path = candidate_dir / "diagnostic_summary.json.gz"
            with gzip.open(events_path, "rt") as handle:
                events = json.loads(handle.read())["events"]
            with gzip.open(summary_path, "rt") as handle:
                summary = json.loads(handle.read())
        plan = json.loads((candidate_dir / "plan_snapshot.json").read_text())
        manifest = json.loads((candidate_dir / "manifest.json").read_text())
        for plaintext in (events_path, summary_path):
            compressed_path = candidate_dir / f"{plaintext.name}.gz" if plaintext.suffix != ".gz" else plaintext
            if compressed_path != plaintext:
                with compressed_path.open("wb") as handle:
                    with gzip.GzipFile(filename=plaintext.name, fileobj=handle, mode="wb", mtime=0) as gz:
                        gz.write(plaintext.read_bytes())
                plaintext.unlink()
        operator_deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
        leaks = [event for event in events if event["event_type"] == "ENEMY_LEAK"]
        protected_reached = [event for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"]
        protected_deaths = [event for event in events if event["event_type"] == "OBJECTIVE_FAILURE" and event.get("details", {}).get("reason") == "PROTECTED_TARGET_DEATH"]
        devices = [event for event in events if event["event_type"] == "DEVICE_DESTROYED"]
        steward_artillery = [
            event for event in events
            if event["event_type"] == "DAMAGE"
            and event.get("source_id") == "char_210_stward"
            and event.get("target_id") == "enemy_1112_emppnt#0"
        ]
        shells = [
            {"frame": event["frame"], "target_id": event.get("target_id"), "details": event.get("details", {})}
            for event in events
            if event["event_type"] == "ENEMY_ABILITY_HIT" and str(event.get("source_id", "")).startswith("enemy_1112_emppnt#")
        ]
        steward_heals = [
            {"frame": event["frame"], "source_id": event.get("source_id"), "amount": event.get("details", {}).get("amount")}
            for event in events
            if event["event_type"] == "HEAL" and event.get("target_id") == "char_210_stward"
        ]
        summary_result = {key: value for key, value in (summary.get("result") or {}).items() if key != "events"}
        errors = action_errors(events)
        candidate_summaries.append({
            "candidate_id": f"candidate-{candidate_index:03d}",
            "candidate_sha256": ledger["attempts"][candidate_index - 1]["candidate_sha256"],
            "plan_id": plan["operational_plan_id"],
            "validation_card": plan.get("validation_card"),
            "first_planned_deployments": first_planned_deployments(plan),
            "plan_sha256": digest(candidate_dir / "plan_snapshot.json"),
            "action_sha256": digest(candidate_dir / "action_snapshot.json"),
            "events_gz_sha256": digest(candidate_dir / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(candidate_dir / "diagnostic_events.json.gz"),
            "summary_gz_sha256": digest(candidate_dir / "diagnostic_summary.json.gz"),
            "summary_restored_sha256": restored_digest(candidate_dir / "diagnostic_summary.json.gz"),
            "simulator_manifest": manifest,
            "summary_result": summary_result,
            "classification": summary.get("classification"),
            "protected_target_deaths": summary.get("protected_target_deaths"),
            "protected_target_reached_events": summary.get("protected_target_reached_events"),
            "observed_key_events": {
                "operator_deaths": operator_deaths,
                "unique_operator_death_ids": sorted({event["source_id"] for event in operator_deaths}),
                "enemy_leaks": leaks,
                "protected_target_reached": protected_reached,
                "protected_target_death_events": protected_deaths,
                "protected_target_deaths_from_summary": summary.get("protected_target_deaths"),
                "device_destroyed": devices,
                "artillery_shells_on_operators": shells,
                "steward_artillery_damage": {
                    "hit_count": len(steward_artillery),
                    "total_amount": round(sum(event["details"]["amount"] for event in steward_artillery), 2),
                    "frames": [event["frame"] for event in steward_artillery],
                },
                "heals_to_steward": steward_heals,
                "artillery_death": [
                    {"frame": event["frame"], "source_id": event.get("source_id"), "target_id": event.get("target_id")}
                    for event in events if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") == "enemy_1112_emppnt#0"
                ],
            },
            "recorded_action_errors": errors,
            "action_error_classification": {
                "dependency_failures_after_executor_death": sum(1 for item in errors if item["executor_death_frame"] is not None),
                "independent_action_errors": sum(1 for item in errors if item["executor_death_frame"] is None),
            },
        })

    closeout = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_CLOSEOUT_REPORT_V1",
        "experiment_id": "real_tool_closed_loop_sol_high_seven_support_geometry_v1",
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
            "codex_doctor": preflight["codex_doctor"],
            "proxy_prestart": preflight["proxy_prestart"],
            "parent_candidates": preflight["input_bundle"]["parent_candidates"],
            "cold_start_task_root_removed": preflight["input_bundle"]["cold_start_task_root_removed"],
            "coverage_boundary": preflight["coverage_boundary"],
        },
        "interface": {
            "real_cli_starts": authorization["real_cli_starts"],
            "candidate_ledger": ledger,
            "simulation_budget": budget,
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "visible_usage_records": [],
        },
        "candidates": candidate_summaries,
        "final_model_summary": final_message,
        "closure": {
            "new_win": False,
            "best_verified_operator_count": 8,
            "seven_or_fewer_feasibility": "UNKNOWN",
            "candidate_results": {
                "R97_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_001": "COMPLETE_LOSS 13/20, life -19, 7 death events/7 unique IDs, 9 action errors",
                "R97_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_002": "COMPLETE_LOSS 24/9, life -8, 3 death events/3 unique IDs, 1 action error",
            },
            "causal_learning": {
                "proved": "C2 separated observed outer splash geometry and kept both medics alive.",
                "refuted": "That separation did not establish Hibiscus-to-Steward healing, artillery closure, central closure, protected safety, or WIN.",
                "remaining": "Exact arbitrary-frame HP, target-choice causality, and whether either geometry could succeed under different actions remain UNKNOWN.",
            },
        },
        "scope_boundary": [
            "Current fixed simulator only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
            "No claim of seven-ID impossibility after two complete bounded LOSS candidates.",
            "M70 R8_7_GPT_M70_V1 remains the frozen eight-operator WIN and was not rerun.",
        ],
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)
    manifest_payload = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_ARTIFACT_MANIFEST_V1",
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
    (closeout_path.with_suffix(closeout_path.suffix + ".sha256")).write_text(f"{digest(closeout_path)}  {closeout_path.name}\n")


if __name__ == "__main__":
    main()
