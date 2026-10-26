from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m59_frozen_m58_spot_fusion_v1"
SOURCE = BASE / "attempt_01_simulation"
DIAGNOSTIC = BASE / "attempt_01_simulation_diagnostic"
TARGET_DIR = ROOT / "docs/review/fc77177/m59_frozen_m58_spot_fusion_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def details_map(details: Any) -> dict[str, Any]:
    if isinstance(details, dict):
        return details
    if isinstance(details, list):
        return {str(item[0]): item[1] for item in details if isinstance(item, list) and len(item) >= 2}
    return {}


def amount(event: dict[str, Any]) -> float:
    payload = details_map(event.get("details"))
    return float(payload.get("amount", 0) or 0)


def main() -> None:
    structured = json.loads((SOURCE / "llm_structured_output.json").read_text(encoding="utf-8"))
    gate = json.loads((SOURCE / "simulation_gate.json").read_text(encoding="utf-8"))
    summary = json.loads((DIAGNOSTIC / "final_status.json").read_text(encoding="utf-8"))
    diagnostic_summary = json.loads((DIAGNOSTIC / "diagnostic_summary.json").read_text(encoding="utf-8"))
    events = json.loads((DIAGNOSTIC / "diagnostic_events.json").read_text(encoding="utf-8"))["events"]
    plan = structured["revised_operational_plans"][0]
    actions = plan["action_timeline"]

    action_results: list[dict[str, Any]] = []
    events_by_action_frame: dict[tuple[int, str, str], dict[str, Any]] = {}
    for event in events:
        event_type = event.get("event_type")
        if event_type in {"DEPLOY", "RETREAT", "SKILL_ACTIVATE"}:
            action_type = "ACTIVATE_SKILL" if event_type == "SKILL_ACTIVATE" else event_type
            key = (event["frame"], event["source_id"], action_type)
            events_by_action_frame[key] = event
    for index, action in enumerate(actions, 1):
        key = (action["frame"], action["operator_id"], action["action_type"])
        observed = events_by_action_frame.get(key)
        payload = details_map(observed.get("details")) if observed else {}
        action_results.append({
            "action_index": index,
            "action": action,
            "observed": observed is not None,
            "legal": payload.get("legal", True) if observed else False,
            "runtime_details": payload,
            "failure_reason": "OPERATOR_NOT_DEPLOYED" if observed is not None and payload.get("legal") is False else None,
        })

    damage_by_source: Counter[str] = Counter()
    damage_count_by_source: Counter[str] = Counter()
    heal_by_source: Counter[str] = Counter()
    heal_count_by_source: Counter[str] = Counter()
    device_damage_by_source: Counter[str] = Counter()
    ordinary_damage_by_target: Counter[str] = Counter()
    ability_damage_by_target: Counter[str] = Counter()
    block_intervals: dict[str, list[dict[str, Any]]] = defaultdict(list)
    open_blocks: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        event_type = event["event_type"]
        source = event.get("source_id")
        target = event.get("target_id")
        if event_type == "DAMAGE":
            damage_by_source[source] += amount(event)
            damage_count_by_source[source] += 1
            ordinary_damage_by_target[target] += amount(event)
        elif event_type == "HEAL":
            heal_by_source[source] += amount(event)
            heal_count_by_source[source] += 1
        elif event_type == "DEVICE_DAMAGE":
            device_damage_by_source[source] += amount(event)
        elif event_type == "ENEMY_ABILITY_HIT":
            ability_damage_by_target[target] += amount(event)
        elif event_type == "BLOCK":
            record = {"target_id": target, "start_frame": event["frame"], "end_frame": None, "duration_seconds": None}
            block_intervals[source].append(record)
            open_blocks[(source, target)] = record
        elif event_type == "UNBLOCK" and (source, target) in open_blocks:
            record = open_blocks.pop((source, target))
            record["end_frame"] = event["frame"]
            record["duration_seconds"] = (event["frame"] - record["start_frame"]) / 30.0

    operator_ids = sorted(plan["selected_low_star_operator_ids"])
    operator_ledger: dict[str, Any] = {}
    for operator_id in operator_ids:
        operator_ledger[operator_id] = {
            "damage_dealt": damage_by_source[operator_id],
            "damage_count": damage_count_by_source[operator_id],
            "heal_dealt": heal_by_source[operator_id],
            "heal_count": heal_count_by_source[operator_id],
            "device_damage_dealt": device_damage_by_source[operator_id],
            "ordinary_damage_received": ordinary_damage_by_target[operator_id],
            "artillery_ability_damage_received": ability_damage_by_target[operator_id],
            "block_intervals": block_intervals[operator_id],
            "retreat_refund_events": [
                event for event in events
                if event["event_type"] == "DP_CHANGE"
                and event["source_id"] == operator_id
                and details_map(event["details"]).get("reason") == "retreat_refund"
            ],
            "death_events": [event for event in events if event["event_type"] == "OPERATOR_DEATH" and event["source_id"] == operator_id],
        }

    spawn_ids = [event["source_id"] for event in events if event["event_type"] == "SPAWN"]
    death_targets = {event["target_id"]: event for event in events if event["event_type"] == "ENEMY_DEATH"}
    leak_ids = [event["source_id"] for event in events if event["event_type"] == "ENEMY_LEAK"]
    reached_ids = [event["source_id"] for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"]
    entity_accounting = {
        "spawn_count": len(spawn_ids),
        "kill_counted_enemy_death_count": len([event for event in events if event["event_type"] == "ENEMY_DEATH" and details_map(event["details"]).get("kill_counted") is True]),
        "uncounted_protected_target_death_count": len([event for event in events if event["event_type"] == "ENEMY_DEATH" and details_map(event["details"]).get("kill_counted") is not True]),
        "leak_count": len(leak_ids),
        "protected_target_reached_count": len(reached_ids),
        "all_spawn_ids_settled": set(spawn_ids) == set(death_targets) | set(leak_ids) | set(reached_ids),
        "remaining_enemy_hp": (diagnostic_summary.get("result") or {}).get("remaining_enemy_hp"),
        "remaining_enemy_route_progress": (diagnostic_summary.get("result") or {}).get("remaining_enemy_route_progress"),
        "remaining_life": summary.get("remaining_life"),
    }

    spot_heals = [
        {"frame": event["frame"], "target_id": event["target_id"], "amount": amount(event)}
        for event in events if event["event_type"] == "HEAL" and event["source_id"] == "char_284_spot"
        and 2882 <= event["frame"] <= 3632
    ]
    artillery_hits = [
        {"frame": event["frame"], "target_id": event["target_id"], "amount": amount(event), "details": details_map(event["details"])}
        for event in events if event["event_type"] == "ENEMY_ABILITY_HIT" and event["source_id"] == "enemy_1112_emppnt#0"
    ]
    armored_34_events = [
        {"event_type": event["event_type"], "frame": event["frame"], "source_id": event["source_id"], "target_id": event["target_id"], "amount": amount(event) or None}
        for event in events if "enemy_1110_uamord#34" in {event.get("source_id"), event.get("target_id")}
    ]
    roadblocks: dict[str, Any] = {}
    for roadblock_id in ["trap_020_roadblock#1", "trap_020_roadblock#2", "trap_020_roadblock#3", "trap_020_roadblock#4"]:
        relevant = [
            event for event in events
            if event.get("target_id") == roadblock_id and event["event_type"] in {"DEVICE_DAMAGE", "DEVICE_DESTROYED", "BLOCK", "UNBLOCK"}
        ]
        roadblocks[roadblock_id] = {
            "first_event": relevant[0] if relevant else None,
            "last_event": relevant[-1] if relevant else None,
            "destroyed": any(event["event_type"] == "DEVICE_DESTROYED" for event in relevant),
        }

    audit = {
        "schema_version": "M59_EVENT_AUDIT_V1",
        "plan_id": plan["operational_plan_id"],
        "selected_structure_id": structured["revised_stage_understanding"]["m58_open_roster_comparison"]["selected_structure_id"],
        "action_count": len(actions),
        "simulator_result": {
            "status": summary["status"],
            "classification": summary["classification"],
            "win": summary["simulator_win"],
            "enemies_killed": summary["enemies_killed"],
            "enemies_leaked": summary["enemies_leaked"],
            "operator_deaths": summary["operator_deaths"],
            "remaining_life": summary["remaining_life"],
            "first_leak": summary["first_failure"]["first_leak"],
            "objective_failure": summary["first_failure"]["objective_failure"],
        },
        "objective_scope": gate["objective_scope"],
        "revision_hypothesis_evaluation": gate["revision_hypothesis_evaluation"],
        "runtime_action_errors": gate["runtime_action_errors"],
        "entity_accounting": entity_accounting,
        "leak_ids_frames": [
            {"source_id": event["source_id"], "frame": event["frame"], "time": event["time"]}
            for event in events if event["event_type"] == "ENEMY_LEAK"
        ],
        "operator_ledger": operator_ledger,
        "action_results": action_results,
        "fang_spot_handoff": {
            "fang_retreat_event": next(event for event in events if event["event_type"] == "RETREAT" and event["source_id"] == "char_123_fang" and event["frame"] == 2430),
            "fang_retreat_refund": next(event for event in events if event["event_type"] == "DP_CHANGE" and event["frame"] == 2430),
            "fang_active_blocks_at_retreat": [
                record for record in block_intervals.get("char_123_fang", [])
                if record["start_frame"] <= 2430 and (record["end_frame"] is None or record["end_frame"] > 2430)
            ],
            "spot_deploy_event": next(event for event in events if event["event_type"] == "DEPLOY" and event["source_id"] == "char_284_spot" and event["frame"] == 2431),
            "spot_first_block": block_intervals.get("char_284_spot", [])[0],
            "first_leak_between_retreat_and_first_spot_block": [
                event for event in events
                if event["event_type"] == "ENEMY_LEAK" and 2430 <= event["frame"] < 2588
            ],
        },
        "spot_skill_window": {
            "activation": next(event for event in events if event["event_type"] == "SKILL_ACTIVATE" and event["source_id"] == "char_284_spot" and event["frame"] == 2882),
            "end": next(event for event in events if event["event_type"] == "SKILL_END" and event["source_id"] == "char_284_spot" and event["frame"] == 3632),
            "heals": spot_heals,
            "hibiscus_artillery_hits_in_stage": [
                hit for hit in artillery_hits if hit["target_id"] == "char_120_hibisc"
            ],
        },
        "steward_rotation": {
            "planned_retreat": next(action for action in actions if action["action_type"] == "RETREAT" and action["operator_id"] == "char_210_stward" and action["frame"] == 4800),
            "actual_retreat": next(event for event in events if event["event_type"] == "RETREAT" and event["source_id"] == "char_210_stward" and event["frame"] == 4800),
            "death_before_retreat": next(event for event in events if event["event_type"] == "OPERATOR_DEATH" and event["source_id"] == "char_210_stward"),
            "redeployment": next(event for event in events if event["event_type"] == "DEPLOY" and event["source_id"] == "char_210_stward" and event["frame"] == 6901),
            "post_redeployment_damage_events": [
                event for event in events
                if event["event_type"] == "DAMAGE" and event["source_id"] == "char_210_stward" and event["frame"] >= 6901
            ],
        },
        "artillery_0": {
            "spawn": next(event for event in events if event["event_type"] == "SPAWN" and event["source_id"] == "enemy_1112_emppnt#0"),
            "leak": next(event for event in events if event["event_type"] == "ENEMY_LEAK" and event["source_id"] == "enemy_1112_emppnt#0"),
            "ability_hits": artillery_hits,
            "offensive_ability_hit_count": len(artillery_hits),
            "offensive_ability_hit_total": sum(hit["amount"] for hit in artillery_hits),
            "damage_received_from_steward": damage_by_source["char_210_stward"],
            "damage_received_hit_count_from_steward": damage_count_by_source["char_210_stward"],
            "block_events": [event for event in events if event["event_type"] == "BLOCK" and event["target_id"] == "enemy_1112_emppnt#0"],
        },
        "armored_34": {
            "spawn": next(event for event in events if event["event_type"] == "SPAWN" and event["source_id"] == "enemy_1110_uamord#34"),
            "leak": next(event for event in events if event["event_type"] == "ENEMY_LEAK" and event["source_id"] == "enemy_1110_uamord#34"),
            "all_events": armored_34_events,
        },
        "protected_targets": {
            "enemy_3001_upeopl#3": {
                "roadblock_binding": [event for event in events if event["event_type"] == "BLOCK" and event["source_id"] == "trap_020_roadblock#3" and event["target_id"] == "enemy_3001_upeopl#3"],
                "death": death_targets["enemy_3001_upeopl#3"],
                "reached": False,
                "damage_received": {
                    "ordinary": ordinary_damage_by_target["enemy_3001_upeopl#3"],
                    "artillery": ability_damage_by_target["enemy_3001_upeopl#3"],
                },
            },
            "enemy_3001_upeopl#14": {
                "roadblock_binding": [event for event in events if event["event_type"] == "BLOCK" and event["source_id"] == "trap_020_roadblock#2" and event["target_id"] == "enemy_3001_upeopl#14"],
                "death": None,
                "reached": reached_ids == ["enemy_3001_upeopl#14"],
                "damage_received": {
                    "ordinary": ordinary_damage_by_target["enemy_3001_upeopl#14"],
                    "artillery": ability_damage_by_target["enemy_3001_upeopl#14"],
                },
            },
        },
        "roadblocks": roadblocks,
        "source_evidence_sha256": {
            "llm_structured_output.json": sha256(SOURCE / "llm_structured_output.json"),
            "llm_evidence_context.json": sha256(SOURCE / "llm_evidence_context.json"),
            "revision_output_schema.json": sha256(SOURCE / "revision_output_schema.json"),
            "static_compile_results.json": sha256(SOURCE / "static_compile_results.json"),
            "simulation_gate.json": sha256(SOURCE / "simulation_gate.json"),
            "diagnostic_events.json": sha256(DIAGNOSTIC / "diagnostic_events.json"),
            "diagnostic_summary.json": sha256(DIAGNOSTIC / "diagnostic_summary.json"),
        },
    }
    target = TARGET_DIR / "m59_event_audit_v1.json"
    target.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit": str(target.relative_to(ROOT)),
        "sha256": sha256(target),
        "win": audit["simulator_result"]["win"],
        "all_spawn_ids_settled": entity_accounting["all_spawn_ids_settled"],
        "action_count": len(action_results),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
