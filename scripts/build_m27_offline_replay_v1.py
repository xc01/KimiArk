from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def compact(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event.get("event_type"),
        "frame": event.get("frame"),
        "source_id": event.get("source_id"),
        "target_id": event.get("target_id"),
        "details": event.get("details"),
    }


def target_chain(events: list[dict[str, Any]], target_id: str) -> dict[str, Any]:
    damage_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("event_type") == "DAMAGE" and event.get("target_id") == target_id:
            key = (event.get("source_id"), event.get("details", {}).get("kind"))
            damage_groups[key].append(event)
    deaths = [event for event in events if event.get("event_type") == "ENEMY_DEATH" and event.get("target_id") == target_id]
    ability_hits = [
        event for event in events
        if event.get("event_type") == "ENEMY_ABILITY_HIT" and event.get("target_id") == target_id
    ]
    return {
        "spawn": next((compact(event) for event in events if event.get("event_type") == "SPAWN" and event.get("source_id") == target_id), None),
        "roadblock_restraints": [
            compact(event) for event in events
            if event.get("event_type") == "BLOCK" and event.get("target_id") == target_id and str(event.get("source_id", "")).startswith("trap_")
        ],
        "damage_groups": [
            {
                "source_id": source_id,
                "kind": kind,
                "hits": len(rows),
                "amount": sum(row["details"]["amount"] for row in rows),
                "frames": [row["frame"] for row in rows],
            }
            for (source_id, kind), rows in damage_groups.items()
        ],
        "ability_hits": [compact(event) for event in ability_hits],
        "death": next((compact(event) for event in deaths), None),
        "last_hit_source_id": deaths[0].get("source_id") if deaths else None,
    }


def build_replay(events_path: Path, summary_path: Path, output_path: Path) -> dict[str, Any]:
    event_data = load_gzip_json(events_path)
    summary = load_gzip_json(summary_path)
    events = event_data.get("events") or []
    artillery_id = "enemy_1112_emppnt#0"
    damage_to_artillery: dict[str, dict[str, Any]] = defaultdict(lambda: {"frames": [], "amount": 0.0, "kinds": Counter()})
    for event in events:
        if event.get("event_type") == "DAMAGE" and event.get("target_id") == artillery_id:
            row = damage_to_artillery[event["source_id"]]
            row["frames"].append(event["frame"])
            row["amount"] += event["details"].get("amount", 0)
            row["kinds"][event["details"].get("kind")] += 1
    protected_ids = {
        event["target_id"] for event in summary.get("protected_target_deaths", [])
        if event.get("target_id")
    }
    death_ids = {event["source_id"] for event in events if event.get("event_type") == "OPERATOR_DEATH"}
    later_source_errors = []
    for error in summary.get("result", {}).get("deployment_errors", []):
        if "operator is not deployed" in error:
            later_source_errors.append(error)
    result = summary.get("result", {})
    payload = {
        "schema_version": "M27_OFFLINE_EVENT_REPLAY_V1",
        "source_stage_id": "main_08-07",
        "source_plan_id": "R8_7_GPT_M26_V3",
        "failure_category": "LEGAL_BATTLE_LOSS",
        "simulation_status": "COMPLETED_LOSS",
        "evidence": {
            "events_path": str(events_path.relative_to(ROOT)),
            "events_sha256": sha256(events_path),
            "summary_path": str(summary_path.relative_to(ROOT)),
            "summary_sha256": sha256(summary_path),
            "event_count": len(events),
        },
        "objective_scope": {
            "simulator_win": result.get("win"),
            "project_perfect_target": False,
            "enemies_killed": result.get("enemies_killed"),
            "enemies_leaked": result.get("enemies_leaked"),
            "operator_deaths": len(summary.get("event_summaries", {}).get("operator_death_events", [])),
            "protected_target_deaths": len(summary.get("protected_target_deaths", [])),
            "protected_targets_reached": len(summary.get("protected_target_reached_events", [])),
            "remaining_life": result.get("remaining_life"),
            "targeting_variant_results": "NOT_EVALUATED_IN_SOURCE_RUN",
            "faithful_certificate_status": summary.get("faithful_certificate"),
            "real_game_status": "NOT_PLAYED",
        },
        "observed_causal_chain": {
            "midnight": target_chain(events, "char_283_midn"),
            "artillery_unit": {
                "ability_starts": [
                    compact(event) for event in events
                    if event.get("event_type") == "ENEMY_ABILITY_START" and event.get("source_id") == artillery_id
                ],
                "ability_hits": [
                    compact(event) for event in events
                    if event.get("event_type") == "ENEMY_ABILITY_HIT" and event.get("source_id") == artillery_id
                ],
                "incoming_damage": [
                    {"source_id": source_id, "amount": row["amount"], "hit_count": len(row["frames"]), "frames": row["frames"], "kinds": dict(row["kinds"])}
                    for source_id, row in damage_to_artillery.items()
                ],
                "death": next((compact(event) for event in events if event.get("event_type") == "ENEMY_DEATH" and event.get("target_id") == artillery_id), None),
                "leak": next((compact(event) for event in events if event.get("event_type") == "ENEMY_LEAK" and event.get("source_id") == artillery_id), None),
            },
            "protected_targets": {target_id: target_chain(events, target_id) for target_id in sorted(protected_ids)},
            "operator_deaths": [
                compact(event) for event in events if event.get("event_type") == "OPERATOR_DEATH"
            ],
            "first_leak": summary.get("first_failure", {}).get("first_leak"),
            "later_command_failures": later_source_errors,
        },
        "interpretation": {
            "observed": [
                "Midnight was deployed at 1305 and died at 1680; no HEAL event targeted Midnight before death.",
                "Artillery enemy_1112_emppnt#0 survived through frame 5759 and then leaked.",
                "Protected target #3 died at 3180 with artillery as last hit.",
                "Protected target #14 died at 3966 with enemy_1107_uoffcr#18 as last hit after earlier officer and artillery pressure.",
                "Twelve later ACTIVATE_SKILL or RETREAT commands failed because their source operators were absent."
            ],
            "causal_explanations": [
                "Midnight death broke later conditional commands that assumed its survival.",
                "The failure to remove artillery persisted enemy area pressure and prolonged opening/upper position exposure.",
                "Roadblock restraint concentrated protected-target exposure; officer and artillery pressure together preceded both deaths.",
                "First leak and protected-target loss can interact through objective life, but they are distinct failure chains."
            ],
            "unproven_or_unknown": [
                "Exact client artillery locking, visibility and target selection outside the current model.",
                "Whether another GPT structure can satisfy zero leaks, zero protected-target deaths and safe arrival.",
                "A general low-star strategy conclusion cannot be inferred from this single fixed-action loss."
            ],
        },
        "revision_boundary": "This evidence is feedback only; Python/GLM may not choose or edit tactical actions.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, default=ROOT / "docs/review/fc77177/m26_r8_7_attempt04_diagnostic_events.json.gz")
    parser.add_argument("--summary", type=Path, default=ROOT / "docs/review/fc77177/m26_r8_7_attempt04_diagnostic_summary.json.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/review/fc77177/m27_r8_7_attempt04_offline_replay_v1.json")
    arguments = parser.parse_args()
    payload = build_replay(arguments.events, arguments.summary, arguments.output)
    print(json.dumps({"output": str(arguments.output), "sha256": sha256(arguments.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
