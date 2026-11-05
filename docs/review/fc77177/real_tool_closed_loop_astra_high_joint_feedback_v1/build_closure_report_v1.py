#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_joint_feedback_v1"
SESSION = EXPERIMENT / "session"
CANDIDATE_ROOT = SESSION / "candidates"
TRANSCRIPT = SESSION / "codex_cli/attempt_01/codex_exec.jsonl"
OUTPUT = EXPERIMENT / "closure_report_v1.json"

OPERATOR_NAMES = {
    "char_123_fang": "芬",
    "char_4093_frston": "Friston-3",
    "char_283_midn": "月见夜",
    "char_208_melan": "玫兰莎",
    "char_212_ansel": "安赛尔",
    "char_120_hibisc": "芙蓉",
    "char_284_spot": "斑点",
    "char_210_stward": "史都华德",
}

KEY_ENEMY_IDS = {
    "enemy_1110_uamord#21",
    "enemy_1110_uamord#22",
    "enemy_1108_uterer#28",
    "enemy_1108_uterer#31",
    "enemy_1110_uamord#33",
    "enemy_1110_uamord#34",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_events(candidate_dir: Path) -> list[dict[str, Any]]:
    path = candidate_dir / "simulation/diagnostic_events.json.gz"
    if not path.exists():
        path = candidate_dir / "simulation/diagnostic_events.json"
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["events"]


def amount(event: dict[str, Any]) -> float:
    return float(event.get("details", {}).get("amount", 0))


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event.get("event_type"),
        "frame": event.get("frame"),
        "time": event.get("time"),
        "source_id": event.get("source_id"),
        "target_id": event.get("target_id"),
        "details": event.get("details", {}),
    }


def candidate_summary(candidate_dir: Path) -> dict[str, Any]:
    structured = json.loads((candidate_dir / "source/llm_structured_output.json").read_text())
    plan = structured["revised_operational_plans"][0]
    record = json.loads((candidate_dir / "candidate_record.json").read_text())
    final_status = json.loads((candidate_dir / "simulation/final_status.json").read_text())
    events = load_events(candidate_dir)
    selected = plan.get("selected_low_star_operator_ids", [])
    roadblocks: dict[str, dict[str, Any]] = defaultdict(lambda: {"damage_events": 0, "damage_total": 0.0, "destroyed": False, "destroy_frame": None})
    artillery_damage: dict[str, dict[str, Any]] = defaultdict(lambda: {"events": 0, "total": 0.0, "first_frame": None, "last_frame": None})
    artillery_final = None
    operator_deaths = [compact_event(event) for event in events if event["event_type"] == "OPERATOR_DEATH"]
    leaks = [compact_event(event) for event in events if event["event_type"] == "ENEMY_LEAK"]
    protected_reached = [compact_event(event) for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"]
    key_enemies: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["event_type"] == "DEVICE_DAMAGE":
            target = event.get("target_id")
            if target and target.startswith("trap_020_roadblock"):
                roadblocks[target]["damage_events"] += 1
                roadblocks[target]["damage_total"] += amount(event)
        elif event["event_type"] == "DEVICE_DESTROYED":
            target = event.get("target_id")
            if target and target.startswith("trap_020_roadblock"):
                roadblocks[target]["destroyed"] = True
                roadblocks[target]["destroy_frame"] = event.get("frame")
        elif event["event_type"] == "DAMAGE" and event.get("target_id") == "enemy_1112_emppnt#0":
            source = event.get("source_id")
            item = artillery_damage[source]
            item["events"] += 1
            item["total"] += amount(event)
            item["first_frame"] = item["first_frame"] if item["first_frame"] is not None else event["frame"]
            item["last_frame"] = event["frame"]
        elif event["event_type"] in {"ENEMY_DEATH", "ENEMY_LEAK"} and event.get("source_id") == "enemy_1112_emppnt#0":
            artillery_final = compact_event(event)
        elif (event.get("source_id") in KEY_ENEMY_IDS or event.get("target_id") in KEY_ENEMY_IDS):
            enemy_id = event.get("source_id") if event.get("source_id") in KEY_ENEMY_IDS else event.get("target_id")
            item = key_enemies.setdefault(enemy_id, {"damage_taken_total": 0.0, "damage_dealt_total": 0.0, "damage_event_count": 0, "final_event": None})
            if event["event_type"] == "DAMAGE":
                item["damage_event_count"] += 1
                if event.get("target_id") == enemy_id:
                    item["damage_taken_total"] += amount(event)
                if event.get("source_id") == enemy_id:
                    item["damage_dealt_total"] += amount(event)
            elif event["event_type"] == "ENEMY_ABILITY_HIT":
                item["damage_event_count"] += 1
                if event.get("target_id") == enemy_id:
                    item["damage_taken_total"] += amount(event)
                if event.get("source_id") == enemy_id:
                    item["damage_dealt_total"] += amount(event)
            elif event["event_type"] in {"ENEMY_DEATH", "ENEMY_LEAK"} and event.get("source_id") == enemy_id:
                item["final_event"] = compact_event(event)
    return {
        "candidate_id": record["candidate_id"],
        "candidate_sha256": record["candidate_sha256"],
        "plan_id": plan.get("operational_plan_id"),
        "declared_parent_plan_id": plan.get("parent_plan_id"),
        "declared_parent_hypothesis_id": plan.get("parent_hypothesis_id"),
        "root_lineage_gap": plan.get("parent_plan_id") is None,
        "selected_operator_ids": selected,
        "selected_operator_names": [OPERATOR_NAMES.get(item, item) for item in selected],
        "action_count": len(plan.get("action_timeline", [])),
        "strategic_hypotheses": structured.get("revised_strategic_hypotheses", []),
        "revision_hypothesis_evaluation": json.loads((candidate_dir / "source/revision_hypothesis_evaluation.json").read_text()),
        "final_status": final_status,
        "roadblocks": dict(sorted(roadblocks.items())),
        "artillery_damage": dict(sorted(artillery_damage.items())),
        "artillery_final_event": artillery_final,
        "key_enemies": dict(sorted(key_enemies.items())),
        "operator_deaths": operator_deaths,
        "unique_operator_death_count": len({event.get("target_id") for event in operator_deaths}),
        "leaks": leaks,
        "protected_targets_reached": protected_reached,
    }


def tool_calls() -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for line in TRANSCRIPT.read_text().splitlines():
        payload = json.loads(line)
        item = payload.get("item", {})
        if item.get("type") != "mcp_tool_call" or item.get("status") != "completed":
            continue
        tool = item.get("tool")
        arguments = item.get("arguments") or {}
        counts[tool] += 1
        compact_arguments: dict[str, Any] = arguments
        if tool == "check_plan":
            plan = arguments.get("plan", {}).get("revised_operational_plans", [{}])[0]
            compact_arguments = {"operational_plan_id": plan.get("operational_plan_id")}
        calls.append({
            "item_id": item.get("id"),
            "tool": tool,
            "arguments": compact_arguments,
        })
    return {"counts": dict(counts), "calls": calls}


def usage() -> dict[str, Any]:
    for line in reversed(TRANSCRIPT.read_text().splitlines()):
        payload = json.loads(line)
        if payload.get("type") == "turn.completed" and isinstance(payload.get("usage"), dict):
            return {
                **payload["usage"],
                "cached_input_is_input_subset": True,
                "internal_model_requests": "UNKNOWN_CLI_INTERNAL",
            }
    raise RuntimeError("turn.completed usage not found")


def build() -> dict[str, Any]:
    candidates = [candidate_summary(path) for path in sorted(CANDIDATE_ROOT.glob("candidate-*"))]
    calls = tool_calls()
    process_result = json.loads((SESSION / "codex_cli/attempt_01/cli_process_result.json").read_text())
    authorization = json.loads((EXPERIMENT / "model_authorization_v1.json").read_text())
    budget = json.loads((EXPERIMENT / "simulation_budget_v1.json").read_text())
    ledger = json.loads((EXPERIMENT / "candidate_ledger_v1.json").read_text())
    return {
        "schema_version": "KIMIARK_JOINT_FEEDBACK_CLOSURE_REPORT_V1",
        "experiment_id": "real_tool_closed_loop_astra_high_joint_feedback_v1",
        "session_id": "real-tool-loop-astra-high-joint-feedback-v1",
        "model": authorization["model"],
        "reasoning_effort": authorization["reasoning_effort"],
        "features_apps": authorization["features_apps"],
        "cli_process_result": process_result,
        "authorization": authorization,
        "budget": budget,
        "candidate_ledger": ledger,
        "tool_calls": calls,
        "usage": usage(),
        "best_result": {
            "simulator_win": any(candidate["final_status"].get("simulator_win") for candidate in candidates),
            "best_operator_count": None,
            "frozen_best_baseline": "M70 eight-ID WIN remains unchanged",
        },
        "candidates": candidates,
        "scope_boundaries": {
            "current_fixed_simulator_only": True,
            "real_game_faithful_robust_or_probability_claim": False,
            "seven_or_fewer_feasibility_proof": "UNKNOWN",
            "unused_budget_does_not_transfer": True,
        },
        "post_run_service_guard": {
            "observed_gap": "All candidates left cold_start parent_plan_id undeclared; the previous root gate did not reject this.",
            "minimal_fix": "Require declared root parent for every cold_start candidate and completed-candidate parents after the first run.",
            "focused_test_command": "uv run --no-sync pytest -q tests/test_kimiark_tactical_stdio_service_v1.py",
            "focused_test_result": "PASS",
            "archived_run_code_hash_change_disclosed": True,
        },
    }


def main() -> None:
    report = build()
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
