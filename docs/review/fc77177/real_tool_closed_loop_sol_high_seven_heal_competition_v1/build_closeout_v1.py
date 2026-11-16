#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1"
PARENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_early_protected_v1/session/candidates/candidate-001/simulation"


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
            with gzip.GzipFile(filename=plaintext.name, fileobj=handle, mode="wb", mtime=0) as archive:
                archive.write(plaintext.read_bytes())
    if plaintext.exists():
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
            "unblocks": [{"frame": row["frame"], "source_id": row.get("source_id")} for row in rows if row["event_type"] == "UNBLOCK"],
            "deaths": [{"frame": row["frame"], "source_id": row.get("source_id"), "details": row.get("details")} for row in rows if row["event_type"] == "ENEMY_DEATH"],
            "leaks": [{"frame": row["frame"]} for row in rows if row["event_type"] == "ENEMY_LEAK"],
        }
    return result


def heal_delivery(events: list[dict], latest_frame: int) -> dict:
    recipients = ("char_210_stward", "char_120_hibisc", "char_212_ansel", "char_4093_frston")
    result = {}
    for recipient in recipients:
        rows = [event for event in events if event["event_type"] == "HEAL" and event.get("target_id") == recipient and event["frame"] <= latest_frame]
        result[recipient] = {
            "event_count": len(rows),
            "total_amount": round(sum(float(row["details"]["amount"]) for row in rows), 2),
            "events": [{"frame": row["frame"], "source_id": row.get("source_id"), "amount": row["details"].get("amount")} for row in rows],
        }
    return result


def mcp_completed_summary() -> dict:
    trajectory_path = EXPERIMENT / "session/codex_cli/codex_exec.jsonl"
    events = [json.loads(line) for line in trajectory_path.read_text().splitlines() if line.strip()]
    completed = []
    for event in events:
        item = event.get("item", event.get("event", {}).get("item", {}))
        if event.get("type") == "item.completed" and item.get("type") == "mcp_tool_call" and item.get("status") == "completed":
            completed.append(item)
    counts = Counter(item["tool"] for item in completed)
    usage = next((event.get("usage") for event in events if event.get("type") == "turn.completed"), "UNKNOWN")
    return {
        "schema_version": "KIMIARK_R106_MCP_COMPLETED_CALL_SUMMARY_V1",
        "counting_boundary": "Completed MCP tool calls only; started/in_progress notifications are not summed.",
        "get_session_status": counts.get("get_session_status", 0),
        "check_plan": counts.get("check_plan", 0),
        "run_simulation": counts.get("run_simulation", 0),
        "query_events": counts.get("query_events", 0),
        "total_completed": len(completed),
        "real_cli_starts": 1,
        "model_generation": True,
        "usage": usage,
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
    }


def candidate_summary(candidate_id: str) -> dict:
    candidate_root = EXPERIMENT / "session/candidates" / candidate_id
    simulation = candidate_root / "simulation"
    record = load_json(candidate_root / "candidate_record.json")
    final_status = load_json(simulation / "final_status.json")
    summary = load_json_archive(simulation / "diagnostic_summary.json")["result"]
    events = load_json_archive(simulation / "diagnostic_events.json")["events"]
    plan = load_json(simulation / "plan_snapshot.json")
    model_output = load_json(candidate_root / "source/llm_structured_output.json")
    model_plan = next((item for item in model_output.get("revised_operational_plans", []) if item.get("operational_plan_id") == record["plan_id"]), {})
    validation_card = model_plan.get("validation_card")
    decision = validation_card.get("experience_selector_decision_record", {}) if isinstance(validation_card, dict) else {}
    deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
    protected_death_events = [event for event in events if event["event_type"] == "ENEMY_DEATH" and str(event.get("target_id", "")).startswith("enemy_3001_upeopl#")]
    reached = [event for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"]
    artillery = steward_artillery(events)
    relevant_heals = [event for event in events if event["event_type"] == "HEAL" and event.get("source_id") in {"char_212_ansel", "char_120_hibisc"}]
    return {
        "candidate_id": candidate_id,
        "candidate_sha256": record["candidate_sha256"],
        "plan_id": record["plan_id"],
        "plan_sha256": digest(simulation / "plan_snapshot.json"),
        "action_sha256": digest(simulation / "action_snapshot.json"),
        "events_gz_sha256": digest(simulation / "diagnostic_events.json.gz") if (simulation / "diagnostic_events.json.gz").exists() else None,
        "events_restored_sha256": restored_digest(simulation / "diagnostic_events.json.gz") if (simulation / "diagnostic_events.json.gz").exists() else digest(simulation / "diagnostic_events.json"),
        "summary_gz_sha256": digest(simulation / "diagnostic_summary.json.gz") if (simulation / "diagnostic_summary.json.gz").exists() else None,
        "summary_restored_sha256": restored_digest(simulation / "diagnostic_summary.json.gz") if (simulation / "diagnostic_summary.json.gz").exists() else digest(simulation / "diagnostic_summary.json"),
        "configured_model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "model_generation": True,
        "parent_plan_id": decision.get("selected_parent", {}).get("plan_id", "UNKNOWN"),
        "referenced_experience_ids": model_output.get("revision_hypothesis", {}).get("referenced_experience_ids", []),
        "decision_record_present": isinstance(decision, dict) and bool(decision),
        "validation_card_present": isinstance(validation_card, dict),
        "validation_card": validation_card,
        "controlled_code_sha256": record.get("controlled_code_sha256", {}),
        "facts_source_sha256": record.get("facts_source_sha256", {}),
        "selected_low_star_operator_ids": plan["selected_low_star_operator_ids"],
        "operator_union_count": record["unique_deployed_operator_count"],
        "result": {
            "win": summary.get("win") or final_status.get("simulator_win"),
            "enemies_killed": final_status["enemies_killed"],
            "enemies_leaked": final_status["enemies_leaked"],
            "remaining_life": final_status["remaining_life"],
            "remaining_enemy_hp": final_status.get("remaining_enemy_hp"),
            "operator_deaths": len(deaths),
            "unique_operator_death_ids": sorted({event.get("source_id") for event in deaths}),
            "operator_death_events": [{"frame": event["frame"], "source_id": event.get("source_id")} for event in deaths],
            "first_objective_failure_reason": final_status["first_objective_failure_reason"],
            "first_objective_failure_time": final_status["first_objective_failure_time"],
            "protected_death_events": [{"frame": event["frame"], "target_id": event.get("target_id"), "source_id": event.get("source_id")} for event in protected_death_events],
            "protected_reached_events": [{"frame": event["frame"], "source_id": event.get("source_id")} for event in reached],
            "action_errors": action_errors(events),
        },
        "summary_result": {
            "win": summary.get("win") or final_status.get("simulator_win"),
            "enemies_killed": final_status["enemies_killed"],
            "enemies_leaked": final_status["enemies_leaked"],
            "remaining_life": final_status["remaining_life"],
            "simulator_win": final_status.get("simulator_win"),
        },
        "observed_key_events": {
            "early_routes": early_routes(events),
            "protected_targets": protected_targets(events),
            "central": central(events),
            "steward_artillery": artillery,
            "heal_delivery_through_3911": heal_delivery(events, 3911),
            "relevant_heals": [{"frame": event["frame"], "source_id": event.get("source_id"), "target_id": event.get("target_id"), "amount": event["details"].get("amount")} for event in relevant_heals],
            "artillery_death": artillery["death_events"],
            "artillery_leak": artillery["leak_events"],
            "protected_target_reached_events": [{"frame": event["frame"], "source_id": event.get("source_id")} for event in reached],
            "device_destroyed": [{"frame": event["frame"], "source_id": event.get("source_id"), "target_id": event.get("target_id")} for event in events if event["event_type"] == "DEVICE_DESTROYED"],
            "leaks": [{"frame": event["frame"], "source_id": event.get("source_id")} for event in events if event["event_type"] == "ENEMY_LEAK"],
        },
    }


def action_diff(parent_actions: list[dict], candidate_actions: list[dict]) -> dict:
    changes = []
    for index in range(max(len(parent_actions), len(candidate_actions))):
        old = parent_actions[index] if index < len(parent_actions) else None
        new = candidate_actions[index] if index < len(candidate_actions) else None
        if old != new:
            changes.append({"action_index": index, "parent": old, "candidate": new})
    return {"changed_action_count": len(changes), "changed_actions": changes}


def main() -> None:
    parent_plan = load_json(PARENT / "plan_snapshot.json")
    parent_actions = load_json(PARENT / "action_snapshot.json")["actions"]
    parent_events = load_json_archive(PARENT / "diagnostic_events.json")["events"]
    candidate = candidate_summary("candidate-001")
    candidate["action_diff_from_r105_c1"] = action_diff(parent_actions, load_json(EXPERIMENT / "session/candidates/candidate-001/simulation/action_snapshot.json")["actions"])
    archive_large_json(EXPERIMENT / "session/candidates/candidate-001/simulation/diagnostic_events.json")
    archive_large_json(EXPERIMENT / "session/candidates/candidate-001/simulation/diagnostic_summary.json")
    candidate["events_gz_sha256"] = digest(EXPERIMENT / "session/candidates/candidate-001/simulation/diagnostic_events.json.gz")
    candidate["events_restored_sha256"] = restored_digest(EXPERIMENT / "session/candidates/candidate-001/simulation/diagnostic_events.json.gz")
    candidate["summary_gz_sha256"] = digest(EXPERIMENT / "session/candidates/candidate-001/simulation/diagnostic_summary.json.gz")
    candidate["summary_restored_sha256"] = restored_digest(EXPERIMENT / "session/candidates/candidate-001/simulation/diagnostic_summary.json.gz")
    candidate_events = load_json_archive(EXPERIMENT / "session/candidates/candidate-001/simulation/diagnostic_events.json")["events"]
    common_prefix = 0
    for old, new in zip(parent_events, candidate_events):
        if old != new:
            break
        common_prefix += 1
    closeout = {
        "schema_version": "KIMIARK_R106_HEAL_COMPETITION_CLOSEOUT_V1",
        "experiment_id": "real_tool_closed_loop_sol_high_seven_heal_competition_v1",
        "interface": {
            "production_tools": ["get_session_status", "check_plan", "run_simulation", "query_events"],
            "execution_backend": "CONTROLLED_RUNNER",
            "direct_simulator_bypass": False,
            "mcp_calls": mcp_completed_summary(),
            "budget": {
                "authorized_real_cli_starts": 1,
                "used_real_cli_starts": 1,
                "authorized_check_calls": 5,
                "used_check_calls": 1,
                "authorized_candidates": 1,
                "used_candidates": 1,
                "authorized_complete_simulations": 1,
                "used_complete_simulations": 1,
            },
            "usage_boundary": "cached_input_tokens are an input subset; internal requests are UNKNOWN_CLI_INTERNAL.",
        },
        "parent": {
            "record_id": "R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001:candidate-001",
            "plan_id": "R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001",
            "plan_sha256": "3b8c452a9f0aaf9667f3420ecdf912290ce5c69b984895b46447410563ee5e52",
            "action_sha256": "d48eac7ffe3006947abbc6bbc89e9b517cb441643a8672e40ec78b18d20bdafb",
            "events_gz_sha256": "8d41df1f984342181719b842c9b5469682733080c4006e5f413ec499ba55e6f5",
            "events_restored_sha256": "0dbf92c86e530a9b6183394b1fa3ad2ae568aeaaa3a9e707bfecb9814c5d10cb",
        },
        "model": {
            "configured_model": "gpt-6.1-sol",
            "reasoning_effort": "high",
            "model_generation": True,
            "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 1, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True},
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "usage": mcp_completed_summary()["usage"],
        },
        "integration_assessment": {
            "input_bundle_frozen": True,
            "selected_parent_correct": candidate["parent_plan_id"] == "R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001",
            "visible_experience_references_present": bool(candidate["referenced_experience_ids"]),
            "requested_experience_selector_decision_record_present": candidate["decision_record_present"],
            "requested_validation_card_present": candidate["validation_card_present"],
            "boundary": "Presence and citation do not alone prove correct tactical use; event-level assessment is in closure.",
        },
        "candidates": [candidate],
        "control_validity": {
            "parent_event_count": len(parent_events),
            "candidate_event_count": len(candidate_events),
            "exact_equal_prefix_event_count": common_prefix,
            "prefix_boundary": "Equal through parent frame 1380 target-selection; parent's 1381 Ansel deploy diverges because candidate delays that deploy to 1396.",
            "roster_unchanged": True,
            "geometry_unchanged": True,
        },
        "closure": {
            "simulator_win": False,
            "new_win": False,
            "seven_or_fewer_feasibility": "UNKNOWN",
            "best_verified_operator_count": 8,
            "complete_settlement": {
                "candidate_001": "22 kills / 11 leaks / life -9; zero active enemies; #11/#13 blocked and killed; Steward survived@3911 and retreated@4280; artillery killed@4273 with 45 hits/13,227.21 damage.",
                "independent_failures": "Protected #14 died@3911; protected #3 reached@15549; central #21/#22/#33/#34 leaked@6697/6661/6846/6996; first hostile leak was #23@5766; Midnight/Friston/Fang died@5379/6262/6298; action errors were Midnight skill@5400 and retreat@9001.",
            },
            "hypothesis_classification": {
                "early_route_closure": "OBSERVED",
                "physician_allocation_change": "OBSERVED_ALLOCATIONS_NOT_PROVEN_CAUSAL_MECHANISM",
                "hibiscus_3461_shell_survival": "OBSERVED",
                "steward_3911_hit_survival": "OBSERVED",
                "artillery_closure": "OBSERVED",
                "protected_route_closure": "REFUTED",
                "central_closure": "REFUTED",
            },
            "targeted_answer": "The timing change preserved routes, moved actual heals toward Hibiscus and Steward, allowed Hibiscus and Steward to survive their prior death shells, and closed artillery. It did not close protected #14 or central armor; global LOSS does not uniformly refute these local observations.",
            "next_question": "Can protected #14's shell/officer exposure be separated from the route-holder/support tile chain without changing the proven #11/#13 closure or artillery closure, and can late central #33/#34 receive a live blocker/output holder before their leak windows? Continuous positions and exact HP remain UNKNOWN.",
            "scope_boundary": [
                "Current fixed simulator only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
                "M70 R8_7_GPT_M70_V1 remains the frozen eight-operator WIN; seven-or-fewer feasibility remains UNKNOWN.",
                "R104 remains the reusable seven-ID artillery-closed branch; R106 preserves that closure in a different seven-ID branch without claiming a complete WIN.",
            ],
        },
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)
    manifest = {
        "schema_version": "KIMIARK_R106_ARTIFACT_MANIFEST_V1",
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
