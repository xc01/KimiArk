from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def event_id(event: dict[str, Any]) -> str:
    return event.get("source_id") or event.get("target_id") or ""


def damage_rows(events: list[dict[str, Any]], *, target_prefix: str) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    kinds: dict[tuple[str, str], set[str]] = defaultdict(set)
    for event in events:
        if event.get("event_type") != "DAMAGE":
            continue
        source = event.get("source_id") or ""
        target = event.get("target_id") or ""
        if not target.startswith(target_prefix) or target == source:
            continue
        key = (source, target)
        totals[key] += float(event.get("details", {}).get("amount") or 0)
        counts[key] += 1
        kinds[key].add(str(event.get("details", {}).get("kind") or "unknown"))
    return sorted(
        (
            {
                "source_id": source,
                "target_id": target,
                "amount": round(total, 4),
                "hits": counts[(source, target)],
                "damage_kinds": sorted(kinds[(source, target)]),
            }
            for (source, target), total in totals.items()
        ),
        key=lambda row: (-row["amount"], row["source_id"], row["target_id"]),
    )


def aggregate_by_id(events: list[dict[str, Any]], event_type: str, key: str) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for event in events:
        if event.get("event_type") != event_type:
            continue
        identity = event.get(key) or ""
        totals[identity] += float(event.get("details", {}).get("amount") or 0)
        counts[identity] += 1
    return sorted(
        ({"id": identity, "amount": round(total, 4), "events": counts[identity]} for identity, total in totals.items()),
        key=lambda row: (-row["amount"], row["id"]),
    )


def lifecycle(events: list[dict[str, Any]], identity: str) -> list[dict[str, Any]]:
    noisy = {"TARGET_SELECTION", "ATTACK_WINDUP", "DEVICE_TARGET_SELECTION", "ATTACK_RECOVERY_END"}
    return [
        {
            "event_type": event.get("event_type"),
            "frame": event.get("frame"),
            "time": event.get("time"),
            "source_id": event.get("source_id"),
            "target_id": event.get("target_id"),
            "details": event.get("details"),
        }
        for event in events
        if identity in {event.get("source_id"), event.get("target_id")} and event.get("event_type") not in noisy
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-attempt", type=int, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--diagnostic-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    diagnostic = load(args.diagnostic_dir / "diagnostic_summary.json")
    final_status = load(args.diagnostic_dir / "final_status.json")
    events = load(args.diagnostic_dir / "diagnostic_events.json")["events"]
    plan = load(args.diagnostic_dir / "plan_snapshot.json")
    deployments = [event for event in events if event.get("event_type") == "DEPLOY"]
    retreats = [event for event in events if event.get("event_type") == "RETREAT"]
    deaths = [event for event in events if event.get("event_type") == "OPERATOR_DEATH"]
    blocks = [event for event in events if event.get("event_type") == "BLOCK"]
    heals = [event for event in events if event.get("event_type") == "HEAL"]
    skills = [event for event in events if event.get("event_type") == "SKILL_ACTIVATE"]
    leaks = [event for event in events if event.get("event_type") == "ENEMY_LEAK"]
    enemy_deaths = [event for event in events if event.get("event_type") == "ENEMY_DEATH" and event.get("details", {}).get("kill_counted") is True]
    protected_reached = [event for event in events if event.get("event_type") == "PROTECTED_TARGET_REACHED"]
    artillery = [
        event
        for event in events
        if str(event.get("source_id") or "").startswith("enemy_1112_emppnt")
        and event.get("event_type") in {"PROJECTILE_BORN", "DAMAGE", "ENEMY_DEATH", "ENEMY_LEAK"}
    ]
    roadblocks = [
        {
            "event_type": event.get("event_type"),
            "frame": event.get("frame"),
            "time": event.get("time"),
            "source_id": event.get("source_id"),
            "target_id": event.get("target_id"),
            "details": event.get("details"),
        }
        for event in events
        if event.get("event_type") in {"BLOCK", "UNBLOCK", "DEVICE_DAMAGE", "DEVICE_DESTROYED"}
        and str(event.get("source_id", "")).startswith("trap_020_roadblock")
    ]

    first_leak = next((event for event in leaks if event.get("frame") == final_status.get("first_failure", {}).get("first_leak", {}).get("frame")), leaks[0] if leaks else None)
    first_death = deaths[0] if deaths else None
    special_ids = ["enemy_1107_uoffcr#13", "enemy_1110_uamord#21", "enemy_1110_uamord#34", "enemy_1108_uterer#28", "enemy_1108_uterer#31"]
    first_leak_lifecycle = lifecycle(events, first_leak["source_id"]) if first_leak else []
    feedback = {
        "schema_version": f"KIMIARK_M73_CANDIDATE_{args.candidate_attempt}_FEEDBACK_V1",
        "scope": "Current fixed simulator, old action timeline only; no frame is a portable deadline.",
        "plan": {
            "plan_id": plan.get("operational_plan_id"),
            "parent_hypothesis_id": plan.get("parent_hypothesis_id"),
            "roster_ids": plan.get("selected_low_star_operator_ids"),
            "action_count": len(plan.get("action_timeline") or []),
            "tactical_thesis": plan.get("tactical_thesis"),
        },
        "result": {
            "classification": final_status.get("result_classification"),
            "enemies_killed": final_status.get("enemies_killed"),
            "enemies_leaked": final_status.get("enemies_leaked"),
            "operator_death_events": final_status.get("operator_deaths"),
            "remaining_life": final_status.get("remaining_life"),
            "first_leak": first_leak,
            "first_life_zero": next(
                (
                    event
                    for event in events
                    if event.get("event_type") == "OBJECTIVE_FAILURE"
                ),
                None,
            ),
        },
        "upstream_failure": {
            "first_operator_death": first_death,
            "first_leak_contact": [row for row in first_leak_lifecycle if row.get("event_type") in {"SPAWN", "BLOCK", "UNBLOCK", "ATTACK_START", "ATTACK_STRIKE", "DAMAGE", "ENEMY_LEAK"}],
            "note": "First leak is reported as an event fact; upstream survival, blocking and economic dependencies must be traced in the selected plan.",
        },
        "all_leaks": [
            {"enemy_id": event.get("source_id"), "frame": event.get("frame"), "time": event.get("time")}
            for event in leaks
        ],
        "enemy_deaths": [
            {"enemy_id": event.get("target_id"), "killed_by": event.get("source_id"), "frame": event.get("frame")}
            for event in enemy_deaths
        ],
        "protected_targets": {
            "reached": protected_reached,
            "deaths": diagnostic.get("protected_target_deaths", []),
            "damage_rows": damage_rows(events, target_prefix="enemy_3001_upeopl"),
        },
        "operator_deaths": deaths,
        "operator_damage_taken": damage_rows(events, target_prefix="char_"),
        "operator_damage_dealt_to_enemies": damage_rows(events, target_prefix="enemy_"),
        "operator_healing": aggregate_by_id(heals, "HEAL", "source_id"),
        "operator_blocks": aggregate_by_id(blocks, "BLOCK", "source_id"),
        "skill_activations": skills,
        "deployments": deployments,
        "retreats": retreats,
        "artillery": {
            "projectiles_and_damage": artillery,
            "note": "PROJECTILE_BORN records cast/locked position; it does not prove the whole artillery chain or subsequent survival.",
        },
        "roadblock_events": roadblocks,
        "special_enemy_lifecycles": {identity: lifecycle(events, identity) for identity in special_ids},
        "deployment_errors": diagnostic.get("event_summaries", {}).get("deployment_errors", []),
        "budget_after_candidate": {
            "candidate_attempts": args.candidate_attempt,
            "real_cli_starts": args.candidate_attempt,
            "full_simulations": args.candidate_attempt,
        },
        "revision_requirements": [
            "Repair upstream survival and live blocking before treating later insufficient-DP or not-deployed actions as independent causes.",
            "Account for every skill income, retreat refund, deployment cost and whether the required provider was alive at that frame.",
            "Provide actual blocking plus sufficient contact for all leak classes; do not infer coverage from range alone.",
            "Close both artillery survival and every roadblock passage for both protected targets.",
            "Do not reuse first-candidate timing as a portable deadline; recalculate targeting, healing and paths after roster or position changes.",
        ],
        "source": {
            "plan_snapshot": str(args.diagnostic_dir / "plan_snapshot.json"),
            "diagnostic_events": str(args.diagnostic_dir / "diagnostic_events.json"),
            "diagnostic_summary": str(args.diagnostic_dir / "diagnostic_summary.json"),
            "final_status": str(args.diagnostic_dir / "final_status.json"),
        },
    }
    write(args.output, feedback)
    write(Path("docs/review/fc77177/m73_open_dependency_reduction_v1/evidence") / args.output.name, feedback)


if __name__ == "__main__":
    main()
