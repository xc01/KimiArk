#!/usr/bin/env python3
"""Build a compact comparison summary from an M36 full-stage replay."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _frame(event: dict[str, Any]) -> int:
    return int(math.floor(float(event["time"]) * 30.0 + 1e-9))


def _group_damage(events: list[dict[str, Any]], predicate) -> dict[str, Any]:
    rows = [event for event in events if predicate(event)]
    sources = Counter(str(event["source_id"]) for event in rows)
    amounts = Counter()
    for event in rows:
        amounts[str(event["source_id"])] += float(event["details"].get("amount", 0.0))
    return {
        "count": len(rows),
        "amount": round(sum(float(event["details"].get("amount", 0.0)) for event in rows), 4),
        "sources": dict(sorted(sources.items())),
        "amount_by_source": {key: round(value, 4) for key, value in sorted(amounts.items())},
        "first_frame": _frame(rows[0]) if rows else None,
        "last_frame": _frame(rows[-1]) if rows else None,
    }


def _roadblock_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    damage_rows = [
        event
        for event in events
        if event["event_type"] == "DEVICE_DAMAGE"
        and str(event["target_id"]).startswith("trap_020_roadblock")
    ]
    damage: dict[str, Any] = {}
    for target_id in sorted({str(event["target_id"]) for event in damage_rows}):
        rows = [event for event in damage_rows if event["target_id"] == target_id]
        damage[target_id] = {
            "damage_events": len(rows),
            "damage": round(sum(float(event["details"].get("amount", 0.0)) for event in rows), 4),
            "first_frame": _frame(rows[0]),
            "last_frame": _frame(rows[-1]),
        }
    destroyed = [
        {
            "frame": _frame(event),
            "source_id": event["source_id"],
            "target_id": event["target_id"],
        }
        for event in events
        if event["event_type"] == "DEVICE_DESTROYED"
        and str(event["target_id"]).startswith("trap_020_roadblock")
    ]
    return {"damage": damage, "destroyed": destroyed}


def build(replay_dir: Path) -> dict[str, Any]:
    events_payload = json.loads((replay_dir / "diagnostic_events.json").read_text())
    events = events_payload["events"]
    summary = json.loads((replay_dir / "diagnostic_summary.json").read_text())
    final_status = json.loads((replay_dir / "final_status.json").read_text())

    artillery_source = "enemy_1112_emppnt#0"
    artillery_damage = _group_damage(
        events,
        lambda event: event["event_type"] == "DAMAGE"
        and event["target_id"] == artillery_source,
    )
    artillery_operator_damage = _group_damage(
        events,
        lambda event: event["event_type"] == "ENEMY_ABILITY_HIT"
        and event["source_id"] == artillery_source
        and str(event["target_id"]).startswith("char_"),
    )
    ability_starts = [
        {
            "frame": _frame(event),
            "target_position": event["details"]["target_position"],
            "radius": event["details"].get("radius"),
            "delay": event["details"].get("delay"),
        }
        for event in events
        if event["event_type"] == "ENEMY_ABILITY_START"
        and event["source_id"] == artillery_source
    ]
    heal_rows = [event for event in events if event["event_type"] == "HEAL"]
    heal_targets: dict[str, Counter[str]] = defaultdict(Counter)
    heal_sources: dict[str, dict[str, Any]] = {}
    for event in heal_rows:
        source = str(event["source_id"])
        target = str(event["target_id"])
        amount = float(event["details"].get("amount", 0.0))
        if source not in heal_sources:
            heal_sources[source] = {"events": 0, "amount": 0.0, "target_counts": {}}
        heal_sources[source]["events"] += 1
        heal_sources[source]["amount"] += amount
        heal_targets[source][target] += 1
    for source, source_summary in heal_sources.items():
        source_summary["amount"] = round(source_summary["amount"], 4)
        source_summary["target_counts"] = dict(sorted(heal_targets[source].items()))

    result = summary["result"]
    protected_reached = summary.get("protected_target_reached_events", [])
    protected_deaths = summary.get("protected_target_deaths", [])
    leaks = [
        {
            "frame": _frame(event),
            "source_id": event["source_id"],
        }
        for event in events
        if event["event_type"] == "ENEMY_LEAK"
    ]
    return {
        "plan_id": final_status["plan_id"],
        "classification": final_status["classification"],
        "simulator_win": final_status["simulator_win"],
        "enemies_killed": result["enemies_killed"],
        "enemies_leaked": result["enemies_leaked"],
        "remaining_life": result["remaining_life"],
        "operator_deaths": result["operator_deaths"],
        "operator_death_events": [
            {"frame": _frame(event), "operator_id": event["source_id"]}
            for event in events
            if event["event_type"] == "OPERATOR_DEATH"
        ],
        "deployment_errors": result["deployment_errors"],
        "first_objective_failure_reason": final_status["first_objective_failure_reason"],
        "first_objective_failure_time": final_status["first_objective_failure_time"],
        "first_leaks": leaks[:4],
        "leaks": leaks,
        "artillery_initial_hp": "UNKNOWN_NOT_IN_EVENT_STREAM",
        "artillery_damage": artillery_damage,
        "artillery_operator_damage": artillery_operator_damage,
        "artillery_ability_starts": ability_starts,
        "heal_sources": dict(sorted(heal_sources.items())),
        "heal_events": len(heal_rows),
        "protected_reached": protected_reached,
        "protected_deaths": protected_deaths,
        "roadblocks": _roadblock_summary(events),
        "source": {
            "replay_dir": str(replay_dir),
            "diagnostic_events": "diagnostic_events.json",
            "diagnostic_summary": "diagnostic_summary.json",
            "final_status": "final_status.json",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build(args.replay_dir), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
