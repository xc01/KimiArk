#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_early_protected_v1"
PARENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_deterministic_seven_c2_coupled_retreat_v1/session/candidates/candidate-001/simulation"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def load_json_archive(path: Path) -> dict:
    compressed = path.with_suffix(path.suffix + ".gz")
    if compressed.exists():
        return json.loads(gzip.decompress(compressed.read_bytes()))
    return json.loads(path.read_text())


def archive_large_json(plaintext: Path) -> None:
    compressed = plaintext.with_suffix(plaintext.suffix + ".gz")
    if not compressed.exists():
        with compressed.open("wb") as handle:
            with gzip.GzipFile(filename=plaintext.name, fileobj=handle, mode="wb", mtime=0) as gz:
                gz.write(plaintext.read_bytes())
    if not plaintext.exists():
        return
    plaintext.unlink()


def action_errors(events: list[dict]) -> list[dict]:
    return [
        {"frame": event["frame"], "event_type": event["event_type"], "source_id": event.get("source_id")}
        for event in events
        if event["event_type"] in ("DEPLOY", "RETREAT", "SKILL_ACTIVATE") and event.get("details", {}).get("legal") is False
    ]


def steward_artillery(events: list[dict]) -> dict:
    rows = [event for event in events if event["event_type"] == "DAMAGE" and event.get("source_id") == "char_210_stward" and event.get("target_id") == "enemy_1112_emppnt#0"]
    return {
        "hit_count": len(rows),
        "total_amount": round(sum(float(row["details"]["amount"]) for row in rows), 2),
        "first_frame": min((row["frame"] for row in rows), default=None),
        "last_frame": max((row["frame"] for row in rows), default=None),
        "death_events": [event for event in events if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") == "enemy_1112_emppnt#0"],
        "leak_events": [event for event in events if event["event_type"] == "ENEMY_LEAK" and event.get("source_id") == "enemy_1112_emppnt#0"],
    }


def early_routes(events: list[dict]) -> dict:
    result = {}
    for enemy_id in ("enemy_1107_uoffcr#11", "enemy_1107_uoffcr#13"):
        rows = [event for event in events if event.get("target_id") == enemy_id or event.get("source_id") == enemy_id]
        result[enemy_id] = {
            "blocks": [{"frame": row["frame"], "source_id": row.get("source_id")} for row in rows if row["event_type"] == "BLOCK"],
            "damage_received": [{"frame": row["frame"], "source_id": row.get("source_id"), "amount": row["details"].get("amount")} for row in rows if row["event_type"] == "DAMAGE" and row.get("target_id") == enemy_id],
            "deaths": [{"frame": row["frame"], "source_id": row.get("source_id"), "details": row.get("details")} for row in rows if row["event_type"] == "ENEMY_DEATH"],
            "leaks": [{"frame": row["frame"]} for row in rows if row["event_type"] == "ENEMY_LEAK"],
        }
    return result


def protected_targets(events: list[dict]) -> dict:
    result = {}
    for enemy_id in ("enemy_3001_upeopl#3", "enemy_3001_upeopl#14"):
        rows = [event for event in events if event.get("target_id") == enemy_id or event.get("source_id") == enemy_id]
        result[enemy_id] = {
            "damage_received": [{"frame": row["frame"], "source_id": row.get("source_id"), "amount": row["details"].get("amount"), "kind": row["details"].get("kind")} for row in rows if row["event_type"] in ("DAMAGE", "ENEMY_ABILITY_HIT") and row.get("target_id") == enemy_id],
            "deaths": [{"frame": row["frame"], "source_id": row.get("source_id"), "details": row.get("details")} for row in rows if row["event_type"] == "ENEMY_DEATH"],
            "reached": [{"frame": row["frame"], "details": row.get("details")} for row in rows if row["event_type"] == "PROTECTED_TARGET_REACHED"],
        }
    return result


def central(events: list[dict]) -> dict:
    central_ids = {"enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#33", "enemy_1110_uamord#34"}
    result = {}
    for enemy_id in sorted(central_ids):
        rows = [event for event in events if event.get("target_id") == enemy_id or event.get("source_id") == enemy_id]
        result[enemy_id] = {
            "blocks": [{"frame": row["frame"], "source_id": row.get("source_id")} for row in rows if row["event_type"] == "BLOCK"],
            "deaths": [{"frame": row["frame"], "source_id": row.get("source_id"), "details": row.get("details")} for row in rows if row["event_type"] == "ENEMY_DEATH"],
            "leaks": [{"frame": row["frame"]} for row in rows if row["event_type"] == "ENEMY_LEAK"],
        }
    return result


def mcp_completed_summary() -> dict:
    trajectory = load_json(EXPERIMENT / "session/codex_cli/codex_trajectory_summary.json")
    completed = [event["event"]["item"] for event in trajectory["events"] if event.get("event", {}).get("item", {}).get("type") == "mcp_tool_call" and event["event"]["item"].get("status") == "completed"]
    counts = Counter(item["tool"] for item in completed)
    return {
        "schema_version": "KIMIARK_R105_MCP_COMPLETED_CALL_SUMMARY_V1",
        "counting_boundary": "Completed MCP tool calls only; in_progress/completed notifications are not summed.",
        "get_session_status": counts.get("get_session_status", 0),
        "check_plan": counts.get("check_plan", 0),
        "run_simulation": counts.get("run_simulation", 0),
        "query_events": counts.get("query_events", 0),
        "total_completed": len(completed),
        "real_cli_starts": 1,
        "model_generation": True,
        "usage": trajectory["usage_records"],
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
    }


def candidate_summary(candidate_id: str) -> dict:
    candidate_root = EXPERIMENT / "session/candidates" / candidate_id
    sim = candidate_root / "simulation"
    record = load_json(candidate_root / "candidate_record.json")
    final = load_json(sim / "final_status.json")
    events = load_json_archive(sim / "diagnostic_events.json")["events"]
    summary = load_json_archive(sim / "diagnostic_summary.json")["result"]
    plan = load_json(sim / "plan_snapshot.json")
    output = load_json(candidate_root / "source/llm_structured_output.json")
    deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
    protected_death_events = [event for event in events if event["event_type"] == "ENEMY_DEATH" and str(event.get("target_id", "")).startswith("enemy_3001_upeopl#")]
    reached = [event for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"]
    relevant_heals = [event for event in events if event["event_type"] == "HEAL" and event.get("source_id") in {"char_120_hibisc", "char_212_ansel"} and event.get("target_id") in {"char_120_hibisc", "char_123_fang", "char_210_stward", "char_212_ansel", "char_283_midn", "char_284_spot", "char_4093_frston"}]
    central_ids = {"enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#33", "enemy_1110_uamord#34"}
    central_deaths = [event for event in events if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") in central_ids]
    artillery = steward_artillery(events)
    return {
        "candidate_id": candidate_id,
        "candidate_sha256": record["candidate_sha256"],
        "plan_id": record["plan_id"],
        "plan_sha256": digest(sim / "plan_snapshot.json"),
        "action_sha256": digest(sim / "action_snapshot.json"),
        "events_gz_sha256": digest(sim / "diagnostic_events.json.gz") if (sim / "diagnostic_events.json.gz").exists() else None,
        "events_restored_sha256": restored_digest(sim / "diagnostic_events.json.gz") if (sim / "diagnostic_events.json.gz").exists() else digest(sim / "diagnostic_events.json"),
        "summary_gz_sha256": digest(sim / "diagnostic_summary.json.gz") if (sim / "diagnostic_summary.json.gz").exists() else None,
        "summary_restored_sha256": restored_digest(sim / "diagnostic_summary.json.gz") if (sim / "diagnostic_summary.json.gz").exists() else digest(sim / "diagnostic_summary.json"),
        "configured_model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "model_generation": True,
        "parent_plan_id": output["revision_hypothesis"]["parent_plan_id"],
        "referenced_experience_ids": output["revision_hypothesis"]["referenced_experience_ids"],
        "decision_record_present": isinstance(output["revision_hypothesis"].get("experience_selector_decision_record"), dict),
        "validation_card_present": isinstance(output["revision_hypothesis"].get("validation_card"), dict),
        "selected_low_star_operator_ids": plan["selected_low_star_operator_ids"],
        "operator_union_count": record["unique_deployed_operator_count"],
        "result": {
            "win": summary.get("win") or final.get("simulator_win"),
            "enemies_killed": final["enemies_killed"],
            "enemies_leaked": final["enemies_leaked"],
            "remaining_life": final["remaining_life"],
            "remaining_enemy_hp": final.get("remaining_enemy_hp"),
            "operator_deaths": len(deaths),
            "unique_operator_death_ids": sorted({event.get("source_id") for event in deaths}),
            "operator_death_events": [{"frame": event["frame"], "source_id": event.get("source_id")} for event in deaths],
            "first_objective_failure_reason": final["first_objective_failure_reason"],
            "first_objective_failure_time": final["first_objective_failure_time"],
            "protected_death_events": [{"frame": event["frame"], "target_id": event.get("target_id"), "source_id": event.get("source_id")} for event in protected_death_events],
            "protected_reached_events": [{"frame": event["frame"], "source_id": event.get("source_id")} for event in reached],
            "action_errors": action_errors(events),
        },
        "summary_result": {
            "win": summary.get("win") or final.get("simulator_win"),
            "enemies_killed": final["enemies_killed"],
            "enemies_leaked": final["enemies_leaked"],
            "remaining_life": final["remaining_life"],
            "simulator_win": final.get("simulator_win"),
        },
        "observed_key_events": {
            "early_routes": early_routes(events),
            "protected_targets": protected_targets(events),
            "central": central(events),
            "steward_artillery": steward_artillery(events),
            "relevant_heals": [{"frame": event["frame"], "source_id": event.get("source_id"), "target_id": event.get("target_id"), "amount": event["details"].get("amount")} for event in relevant_heals],
            "artillery_death": artillery["death_events"],
            "artillery_leak": artillery["leak_events"],
            "protected_target_reached_events": [{"frame": event["frame"], "source_id": event.get("source_id")} for event in reached],
            "enemy_deaths": [{"frame": event["frame"], "source_id": event.get("source_id"), "target_id": event.get("target_id"), "details": event.get("details")} for event in central_deaths],
            "device_destroyed": [{"frame": event["frame"], "source_id": event.get("source_id"), "target_id": event.get("target_id")} for event in events if event["event_type"] == "DEVICE_DESTROYED"],
        },
    }


def action_diff(parent: list[dict], candidate: list[dict]) -> dict:
    changes = []
    max_length = max(len(parent), len(candidate))
    for index in range(max_length):
        old = parent[index] if index < len(parent) else None
        new = candidate[index] if index < len(candidate) else None
        if old != new:
            changes.append({"action_index": index, "parent": old, "candidate": new})
    return {"changed_action_count": len(changes), "changed_actions": changes}


def main() -> None:
    parent_plan = load_json(PARENT / "plan_snapshot.json")
    parent_actions = json.loads((PARENT / "action_snapshot.json").read_text())["actions"]
    candidates = [candidate_summary(candidate_id) for candidate_id in ("candidate-001", "candidate-002")]
    for candidate in candidates:
        candidate["action_diff_from_r104"] = action_diff(parent_actions, json.loads((EXPERIMENT / f"session/candidates/{candidate['candidate_id']}/simulation/action_snapshot.json").read_text())["actions"])
        archive_large_json(EXPERIMENT / f"session/candidates/{candidate['candidate_id']}/simulation/diagnostic_events.json")
        archive_large_json(EXPERIMENT / f"session/candidates/{candidate['candidate_id']}/simulation/diagnostic_summary.json")
    closeout = {
        "schema_version": "KIMIARK_R105_EARLY_PROTECTED_CLOSEOUT_V1",
        "experiment_id": "real_tool_closed_loop_sol_high_seven_early_protected_v1",
        "interface": {
            "production_tools": ["get_session_status", "check_plan", "run_simulation", "query_events"],
            "execution_backend": "CONTROLLED_RUNNER",
            "direct_simulator_bypass": False,
            "mcp_calls": mcp_completed_summary(),
            "budget": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 1, "authorized_check_calls": 10, "used_check_calls": 4, "authorized_candidates": 2, "used_candidates": 2, "authorized_complete_simulations": 2, "used_complete_simulations": 2},
            "usage_boundary": "cached_input_tokens are an input subset; internal requests are UNKNOWN_CLI_INTERNAL.",
        },
        "parent": {
            "record_id": "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001:candidate-001",
            "plan_id": "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001",
            "plan_sha256": "d91955b06f7bf4145b355152ce2bcd203b3973b469ff4889c6d6d83a1d87048b",
            "action_sha256": "816ec7a9ce93591c5c21c7fea6f811374f0df25238082b483a8a1919c9e7e847",
            "events_gz_sha256": "5b3e33285108938e844cb82cc4d7274494ac16887fd3071087d309c09c424052",
            "events_restored_sha256": "46a72b6dd5f86feef0538897fc773a2e4726154f535fd2b6adb75b007beee1a4",
        },
        "model": {
            "configured_model": "gpt-6.1-sol",
            "reasoning_effort": "high",
            "model_generation": True,
            "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 1, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True},
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "usage": "VISIBLE_TURN_COMPLETED_USAGE_IN_MCP_CALL_SUMMARY",
        },
        "integration_assessment": {
            "input_bundle_frozen": True,
            "selected_parent_correct": all(candidate["parent_plan_id"] == "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001" for candidate in candidates),
            "visible_experience_references_present": all(candidate["referenced_experience_ids"] for candidate in candidates),
            "requested_experience_selector_decision_record_present": all(candidate["decision_record_present"] for candidate in candidates),
            "requested_validation_card_present": all(candidate["validation_card_present"] for candidate in candidates),
            "gap": "Both plans declared the verified R104 parent and referenced experience IDs, but neither supplied the requested experience_selector_decision_record or validation_card object. Their tactical_hypothesis/changed_responsibilities are visible, yet expected/refuting event coverage was incomplete.",
        },
        "candidates": candidates,
        "closure": {
            "simulator_win": False,
            "new_win": False,
            "seven_or_fewer_feasibility": "UNKNOWN",
            "best_verified_operator_count": 8,
            "complete_settlement": {
                "candidate_001": "20 kills / 13 leaks / life -12; #11/#13 blocked and killed, protected #3/#14 died, artillery leaked, no central armor death.",
                "candidate_002": "12 kills / 21 leaks / life -20; #11/#13 damaged but leaked, Friston/Hibiscus/Ansel died together at 2111, artillery leaked, protected #3/#14 died.",
            },
            "targeted_answer": "C1 repaired the targeted early routes but lost the R104 artillery closure earlier because Steward died at 3911; protected targets still died. C2 regressed earlier with a triple shell death and did not close early routes, artillery, protected routes, or central armor.",
            "scope_boundary": [
                "Current fixed simulator only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
                "M70 R8_7_GPT_M70_V1 remains the frozen eight-operator WIN; seven-or-fewer feasibility remains UNKNOWN.",
                "R104 remains the reusable seven-ID artillery-closed branch, not a complete WIN; this loss does not erase that branch.",
            ],
        },
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)
    manifest = {
        "schema_version": "KIMIARK_R105_ARTIFACT_MANIFEST_V1",
        "root": EXPERIMENT.relative_to(ROOT).as_posix(),
        "hash_algorithm": "SHA-256",
        "includes_self": False,
        "self_sha256_path": "closeout_report_v1.json.sha256",
        "files": [],
    }
    excluded = {
        "artifact_manifest_v1.json", "closeout_report_v1.json.sha256",
        "candidate_ledger_v1.json.service.lock", "simulation.run.lock", "runner.lock", "simulation_budget_v1.evaluation.lock",
    }
    for path in sorted(path for path in EXPERIMENT.rglob("*") if path.is_file() and path.name not in excluded):
        entry = {"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = restored_digest(path)
        manifest["files"].append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", manifest)
    (closeout_path.with_suffix(closeout_path.suffix + ".sha256")).write_text(f"{digest(closeout_path)}  {closeout_path.name}\n")


if __name__ == "__main__":
    main()
