#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
OUTPUT = ROOT / "docs/review/fc77177/m70_vs_astra_c3_comparison_v1/m70_vs_astra_c3_comparison_v1.json"
M70_DIR = ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic"
C3_DIR = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_cold_start_v1/session/candidates/candidate-003"
M70_EVENTS = M70_DIR / "diagnostic_events.json.gz"
M70_SUMMARY = M70_DIR / "diagnostic_summary.json.gz"
C3_EVENTS = C3_DIR / "simulation/diagnostic_events.json.gz"
C3_SUMMARY = C3_DIR / "simulation/diagnostic_summary.json.gz"

CRITICAL_EVENT_TYPES = {
    "DEPLOY",
    "RETREAT",
    "OPERATOR_DEATH",
    "SKILL_ACTIVATE",
    "BLOCK",
    "UNBLOCK",
    "ENEMY_ABILITY_START",
    "ENEMY_ABILITY_HIT",
    "PROJECTILE_BORN",
    "DAMAGE",
    "HEAL",
    "ENEMY_DEATH",
    "ENEMY_LEAK",
    "OBJECTIVE_FAILURE",
    "PROTECTED_TARGET_REACHED",
    "DEVICE_DESTROYED",
    "SPAWN",
}

KEY_ENEMY_IDS = {
    "enemy_1110_uamord#21",
    "enemy_1110_uamord#22",
    "enemy_1108_uterer#28",
    "enemy_1108_uterer#31",
    "enemy_1110_uamord#33",
    "enemy_1110_uamord#34",
}

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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def restored_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_events(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)["events"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "frame": event.get("frame"),
        "time": event.get("time"),
        "event_type": event.get("event_type"),
        "source_id": event.get("source_id"),
        "target_id": event.get("target_id"),
        "details": event.get("details", {}),
    }


def rounded(value: float) -> float:
    return round(value, 4)


def first_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    for event in events:
        if event["event_type"] == event_type:
            return compact_event(event)
    return None


def critical_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [compact_event(event) for event in events if event["event_type"] in CRITICAL_EVENT_TYPES]


def action_signature(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_type": action.get("action_type"),
        "operator_id": action.get("operator_id"),
        "frame": action.get("frame"),
        "tile": action.get("tile"),
        "direction": action.get("direction"),
    }


def static_plan(plan: dict[str, Any]) -> dict[str, Any]:
    selected = plan["selected_low_star_operator_ids"]
    actions = [action_signature(action) for action in plan["action_timeline"]]
    return {
        "plan_id": plan["operational_plan_id"],
        "parent_hypothesis_id": plan.get("parent_hypothesis_id"),
        "selected_operator_ids": selected,
        "selected_operator_names": [OPERATOR_NAMES.get(operator_id, operator_id) for operator_id in selected],
        "action_count": len(actions),
        "actions": actions,
    }


def validate_manifest(source_dir: Path, simulation_dir: Path, event_path: Path, summary_path: Path) -> dict[str, Any]:
    manifest = load_json(simulation_dir / "manifest.json")
    source_dir_from_manifest = Path(manifest["source"])
    manifest_path = "simulation/manifest.json" if simulation_dir != source_dir else "manifest.json"
    action_ok = sha256(simulation_dir / "action_snapshot.json") == manifest["action_snapshot_sha256"]
    plan_ok = sha256(simulation_dir / "plan_snapshot.json") == manifest["plan_snapshot_sha256"]
    evidence_ok = sha256(source_dir_from_manifest / "llm_evidence_context.json") == manifest["source_files_sha256"]["llm_evidence_context.json"]
    structured_ok = sha256(source_dir_from_manifest / "llm_structured_output.json") == manifest["source_files_sha256"]["llm_structured_output.json"]
    return {
        "manifest_path": manifest_path,
        "manifest_sha256": sha256(simulation_dir / "manifest.json"),
        "plan_id": manifest["plan_id"],
        "mechanics_version": manifest["mechanics_version"],
        "manifest_plan_snapshot_sha256_matches_file": plan_ok,
        "manifest_action_snapshot_sha256_matches_file": action_ok,
        "manifest_evidence_context_sha256_matches_source": evidence_ok,
        "manifest_structured_output_sha256_matches_source": structured_ok,
        "diagnostic_events_gzip_sha256": sha256(event_path),
        "diagnostic_events_restored_sha256": restored_sha256(event_path),
        "diagnostic_summary_gzip_sha256": sha256(summary_path),
        "diagnostic_summary_restored_sha256": restored_sha256(summary_path),
    }


def operator_stats(events: list[dict[str, Any]], operator_ids: list[str]) -> list[dict[str, Any]]:
    result = []
    for operator_id in operator_ids:
        damage_dealt = 0.0
        damage_taken = 0.0
        heal_amount = 0.0
        block_targets = []
        kills = 0
        for event in events:
            if event["event_type"] == "DAMAGE":
                if event.get("source_id") == operator_id:
                    damage_dealt += float(event["details"].get("amount", 0))
                if event.get("target_id") == operator_id:
                    damage_taken += float(event["details"].get("amount", 0))
            elif event["event_type"] == "HEAL" and event.get("source_id") == operator_id:
                heal_amount += float(event["details"].get("amount", 0))
            elif event["event_type"] == "BLOCK" and event.get("source_id") == operator_id:
                block_targets.append(event.get("target_id"))
            elif event["event_type"] == "ENEMY_DEATH" and event.get("source_id") == operator_id:
                kills += 1
        result.append(
            {
                "operator_id": operator_id,
                "chinese_name": OPERATOR_NAMES.get(operator_id, operator_id),
                "damage_dealt": rounded(damage_dealt),
                "damage_taken": rounded(damage_taken),
                "heal_amount": rounded(heal_amount),
                "block_event_count": len(block_targets),
                "distinct_block_target_count": len(set(block_targets)),
                "enemy_kill_events": kills,
            }
        )
    return result


def key_enemy_stats(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for enemy_id in sorted(KEY_ENEMY_IDS):
        relevant = [event for event in events if event.get("source_id") == enemy_id or event.get("target_id") == enemy_id]
        critical = [compact_event(event) for event in relevant if event["event_type"] in CRITICAL_EVENT_TYPES]
        damage_to_enemy = [event for event in relevant if event["event_type"] == "DAMAGE" and event.get("target_id") == enemy_id]
        damage_by_enemy = [event for event in relevant if event["event_type"] == "DAMAGE" and event.get("source_id") == enemy_id]
        block_segments = [
            event
            for event in relevant
            if event["event_type"] in {"BLOCK", "UNBLOCK"} and event.get("target_id") == enemy_id
        ]
        damage_sources = defaultdict(float)
        for event in damage_to_enemy:
            damage_sources[event.get("source_id")] += float(event["details"].get("amount", 0))
        final_event = critical[-1] if critical else None
        result.append(
            {
                "enemy_id": enemy_id,
                "critical_event_count": len(critical),
                "damage_taken": rounded(sum(float(event["details"].get("amount", 0)) for event in damage_to_enemy)),
                "damage_event_count": len(damage_to_enemy),
                "damage_sources": {key: rounded(value) for key, value in sorted(damage_sources.items())},
                "damage_dealt_by_enemy": rounded(sum(float(event["details"].get("amount", 0)) for event in damage_by_enemy)),
                "block_unblock_events": block_segments,
                "final_event": final_event,
                "compact_critical_events": critical,
            }
        )
    return result


def artillery_shells(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shells = []
    starts = [event for event in events if event["event_type"] == "ENEMY_ABILITY_START" and (event.get("source_id") or "").startswith("enemy_1112_emppnt")]
    for start in starts:
        start_frame = int(start["frame"])
        born_candidates = [
            event
            for event in events
            if event["event_type"] == "PROJECTILE_BORN"
            and start_frame <= int(event["frame"]) < start_frame + 120
            and (event.get("source_id") or "").startswith("enemy_1112_emppnt")
        ]
        hits = [
            event
            for event in events
            if event["event_type"] == "ENEMY_ABILITY_HIT"
            and start_frame <= int(event["frame"]) < start_frame + 150
            and (event.get("source_id") or "").startswith("enemy_1112_emppnt")
        ]
        heals_near_hits = [
            compact_event(event)
            for event in events
            if event["event_type"] == "HEAL"
            and hits
            and start_frame - 90 <= int(event["frame"]) <= int(hits[-1]["frame"]) + 90
        ]
        shells.append(
            {
                "ability_start_frame": start_frame,
                "ability_start_time": start.get("time"),
                "ability_start_details": start.get("details", {}),
                "projectile_born": [compact_event(event) for event in born_candidates],
                "ability_hits": [compact_event(event) for event in hits],
                "affected_target_ids": sorted({event.get("target_id") for event in hits if event.get("target_id")}),
                "total_hit_damage": rounded(sum(float(event["details"].get("amount", 0)) for event in hits)),
                "heals_within_3s_window_around_hits": heals_near_hits,
            }
        )
    return shells


def deployment_state_at(events: list[dict[str, Any]], frame: int) -> list[dict[str, str]]:
    states = {}
    for event in events:
        event_frame = int(event["frame"])
        if event_frame > frame:
            break
        source_id = event.get("source_id")
        if event["event_type"] == "DEPLOY":
            states[source_id] = {"operator_id": source_id, "runtime_tile": event["details"].get("tile"), "state": "DEPLOYED"}
        elif event["event_type"] in {"RETREAT", "OPERATOR_DEATH"}:
            states[source_id] = {"operator_id": source_id, "runtime_tile": event["details"].get("tile"), "state": event["event_type"]}
    return list(states.values())


def comparison() -> dict[str, Any]:
    m70_events = load_events(M70_EVENTS)
    c3_events = load_events(C3_EVENTS)
    m70_manifest = validate_manifest(M70_DIR, M70_DIR, M70_EVENTS, M70_SUMMARY)
    c3_manifest = validate_manifest(C3_DIR / "source", C3_DIR / "simulation", C3_EVENTS, C3_SUMMARY)
    m70_plan = load_json(M70_DIR / "plan_snapshot.json")
    c3_plan = load_json(C3_DIR / "simulation/plan_snapshot.json")
    m70_structured = load_json(M70_DIR.parent / "candidate_v1/llm_structured_output.json")
    c3_structured = load_json(C3_DIR / "source/llm_structured_output.json")
    m70_static = static_plan(m70_plan)
    c3_plan_object = c3_plan if "selected_low_star_operator_ids" in c3_plan else c3_plan["revised_operational_plans"][0]
    c3_static = static_plan(c3_plan_object)
    earliest_action_difference = None
    for index, (left, right) in enumerate(zip(m70_static["actions"], c3_static["actions"])):
        if left != right:
            earliest_action_difference = {"index": index, "m70": left, "c3": right}
            break
    first_event_difference = None
    for index, (left, right) in enumerate(zip(m70_events, c3_events)):
        if left != right:
            first_event_difference = {
                "index": index,
                "m70": compact_event(left),
                "c3": compact_event(right),
            }
            break
    m70_operator_union = m70_static["selected_operator_ids"]
    c3_operator_union = c3_static["selected_operator_ids"]
    first_leak_m70 = first_event(m70_events, "ENEMY_LEAK")
    first_leak_c3 = first_event(c3_events, "ENEMY_LEAK")
    first_failure_c3 = first_event(c3_events, "OPERATOR_DEATH")
    objective_failure_c3 = first_event(c3_events, "OBJECTIVE_FAILURE")
    return {
        "schema_version": "KIMIARK_M70_VS_ASTRA_C3_COMPARISON_V1",
        "analysis_scope": {
            "uses_original_archived_events_only": True,
            "starts_model": 0,
            "runs_new_simulation": 0,
            "starts_new_experiment": 0,
            "changes_tactical_actions": False,
            "counterfactuals_are_arithmetic_conditions_only": True,
        },
        "sources": {
            "m70": {
                "label": "M70 V1 attempt_01_diagnostic",
                "diagnostic_dir": str(M70_DIR.relative_to(ROOT)),
                "plan_path": str((M70_DIR / "plan_snapshot.json").relative_to(ROOT)),
                "events_path": str(M70_EVENTS.relative_to(ROOT)),
                "evidence_validation": m70_manifest,
                "final_status": load_json(M70_DIR / "final_status.json"),
            },
            "c3": {
                "label": "real_tool_closed_loop_astra_high_cold_start_v1 attempt3 candidate-003",
                "candidate_dir": str(C3_DIR.relative_to(ROOT)),
                "structured_output_path": str((C3_DIR / "source/llm_structured_output.json").relative_to(ROOT)),
                "events_path": str(C3_EVENTS.relative_to(ROOT)),
                "evidence_validation": c3_manifest,
                "final_status": load_json(C3_DIR / "simulation/final_status.json"),
            },
        },
        "static_plan_comparison": {
            "m70": m70_static,
            "c3": c3_static,
            "m70_minus_c3_operator_ids": sorted(set(m70_operator_union) - set(c3_operator_union)),
            "c3_minus_m70_operator_ids": sorted(set(c3_operator_union) - set(m70_operator_union)),
            "shared_operator_ids": sorted(set(m70_operator_union) & set(c3_operator_union)),
            "earliest_aligned_action_difference": earliest_action_difference,
            "earliest_raw_event_difference": first_event_difference,
            "coordinate_note": "Plan tile is [row,col]; diagnostic DEPLOY details and replay show runtime [col,row].",
        },
        "terminal_comparison": {
            "m70": {
                "simulator_win": True,
                "enemies_killed": 33,
                "enemies_leaked": 0,
                "remaining_life": 3,
                "operator_deaths": 0,
                "first_leak": first_leak_m70,
                "objective_failure": None,
            },
            "c3": {
                "simulator_win": False,
                "enemies_killed": 24,
                "enemies_leaked": 9,
                "remaining_life": -8,
                "operator_deaths": 4,
                "first_observed_operator_death": first_failure_c3,
                "first_leak": first_leak_c3,
                "objective_failure": objective_failure_c3,
                "protected_targets_reached": sum(1 for event in c3_events if event["event_type"] == "PROTECTED_TARGET_REACHED"),
            },
        },
        "operator_contribution_comparison": {
            "m70": operator_stats(m70_events, m70_operator_union),
            "c3": operator_stats(c3_events, c3_operator_union),
        },
        "key_enemy_comparison": {
            "m70": key_enemy_stats(m70_events),
            "c3": key_enemy_stats(c3_events),
        },
        "artillery_window_comparison": {
            "m70": artillery_shells(m70_events),
            "c3": artillery_shells(c3_events),
        },
        "protected_target_and_roadblock_comparison": {
            "m70": critical_events(
                [
                    event
                    for event in m70_events
                    if "upeopl" in str(event.get("source_id", ""))
                    or "trap_020_roadblock" in str(event.get("target_id", ""))
                    or event["event_type"] in {"DEVICE_DESTROYED", "PROTECTED_TARGET_REACHED"}
                ]
            ),
            "c3": critical_events(
                [
                    event
                    for event in c3_events
                    if "upeopl" in str(event.get("source_id", ""))
                    or "trap_020_roadblock" in str(event.get("target_id", ""))
                    or event["event_type"] in {"DEVICE_DESTROYED", "PROTECTED_TARGET_REACHED"}
                ]
            ),
        },
        "deployment_state_at_key_frames": {
            "m70_first_artillery_hit": deployment_state_at(m70_events, 1993),
            "c3_first_artillery_hit": deployment_state_at(c3_events, 1993),
            "m70_melantha_retreat": deployment_state_at(m70_events, 2054),
            "c3_artillery_continues_after_first_hit": deployment_state_at(c3_events, 2093),
        },
        "interpretation_boundaries": {
            "same_mechanics_version_does_not_prove_every_input_identical": True,
            "no_target_position_reconstruction_where_no_event": True,
            "no_new_simulation_or_ablation_was_used_for_causality": True,
            "event_not_observed_meaning": "Only full-window zero match supports absence; partial coverage remains UNKNOWN.",
        },
        "key_findings": [
            {
                "finding": "Earliest action/input divergence is at index 3: M70 deploys Melantha at row 6, col 5 on frame 841, while C3 deploys Spot at the same runtime tile on frame 901.",
                "evidence": "static_plan_comparison.earliest_aligned_action_difference",
                "status": "OBSERVED",
            },
            {
                "finding": "M70's Melantha destroys roadblock #4 at frame 1966; C3 has no DEVICE_DAMAGE or DEVICE_DESTROYED for roadblock #4. C3 therefore leaves both upper/lower protected routes blocked and eventually neither protected target reaches.",
                "evidence": "protected_target_and_roadblock_comparison; C3 events: #14 BLOCK by roadblock#4 at 3251, #14 artillery death at 3943, #3 still blocked by roadblock#1 from 2773 and artillery death at 5353.",
                "status": "OBSERVED",
            },
            {
                "finding": "C3's first directly observed acceptance-critical failure is protected-passage failure: roadblock #4 blocks #14 at frame 3251. It precedes the first operator death and first enemy leak.",
                "evidence": "C3 DEVICE_DESTROYED/PROTECTED_TARGET_REACHED comparison and terminal_comparison.",
                "status": "OBSERVED",
            },
            {
                "finding": "M70 kills artillery at frame 4273 with Steward after 45 hits / 13227.21 damage. C3 fails to kill it in the observed window; it survives through frame 8762, deals damage in 23 shell windows and kills both protected targets.",
                "evidence": "artillery_window_comparison and ENEMY_DEATH records.",
                "status": "OBSERVED",
            },
            {
                "finding": "The first two artillery shells diverge materially: M70 shell 1 hits Melantha for 845 and shell 2 hits nobody; C3 shell 1 hits Spot for 558 and shell 2 locks [6,5], hitting Ansel+Steward for 1801. This is not proof that one replacement causes all later failures.",
                "evidence": "artillery_window_comparison shell starts 1893 and 2043.",
                "status": "OBSERVED",
            },
            {
                "finding": "C3's terminal deaths form a chain but not a proof of unique root cause: #14 is blocked by surviving #4 and dies to artillery; Steward and later other operators die; #22/#21 leak; #3 dies to artillery. Removing Melantha is an observed roster difference, not proof that simply restoring her would WIN.",
                "evidence": "terminal_comparison, protected events, key_enemy_comparison.",
                "status": "CAUSAL_CHAIN_WITH_COUNTERFACTUAL_LIMIT",
            },
        ],
        "counterfactual_arithmetic_only": [
            {
                "condition": "If C3 could destroy roadblock#4 before protected target #14 reaches it, the observed BLOCK at 3251 would not exist in that counterfactual.",
                "basis": "M70 shows 15 Melanha hits totaling 8358.56 destroy #4 at 1966; C3 shows zero #4 events.",
                "boundary": "This does not assert which action or operator can safely perform the damage without changing the rest of C3.",
            },
            {
                "condition": "If C3 kills artillery before its 3943 shell, the observed 950 damage to #14 and the 3943 death of #14 would not exist under that isolated arithmetic assumption.",
                "basis": "C3 #14 receives artillery damage at 3643, 3793 and 3943; M70 kills artillery at 4273 after 13227.21 Steward damage.",
                "boundary": "Earlier killing requires output contact and HP arithmetic not solved here.",
            },
            {
                "condition": "If artillery is removed from C3 after 3943, the observed #3 artillery deaths at 5053/5203/5353 are removed in that isolated counterfactual.",
                "basis": "C3 records three 950 hits to #3 and a death at 5353.",
                "boundary": "This does not remove enemy leaks or establish a WIN without full replacement simulation.",
            },
        ],
        "replay_usage": {
            "existing_replay_script": "scripts/tactical_battle_replay_v1.py",
            "m70_dump_frames": [1893, 2053, 2093],
            "c3_dump_frames": [1893, 2053, 2093, 3793, 3943],
            "mode": "event-accurate discrete states and locked artillery points only",
        },
        "unknowns": [
            {
                "question": "Whether a seven-ID structure can both clear #4/#2/#1 and retain enough artillery/central output.",
                "status": "UNKNOWN",
                "reason": "No authorized replacement simulation or ablation was run.",
            },
            {
                "question": "Exact client-like enemy continuous positions outside BLOCK/UNBLOCK evidence.",
                "status": "UNKNOWN",
                "reason": "Archived events do not reconstruct continuous enemy trajectory; replay intentionally leaves positions unknown.",
            },
            {
                "question": "Whether replacing Melantha with another directory-legal operator is feasible.",
                "status": "UNKNOWN",
                "reason": "This is a read-only comparison, not a roster search.",
            },
        ],
        "next_validation_questions": [
            {
                "question": "Which window(s) can supply 8358.56 physical damage to roadblock#4 without starving the artillery kill chain?",
                "constraint": "M70 destroyed #4 at frame 1966 before #14 spawns at 3030; C3 did no #4 damage.",
            },
            {
                "question": "How much Steward contact is required before frame 4273-equivalent to kill artillery, and who supplies it if Melanha is absent?",
                "constraint": "M70 records 45 Steward hits / 13227.21 damage and kills at 4273; C3 records 38 hits / 11035.13 and survives.",
            },
            {
                "question": "Can a replacement keep lower-central blocking while also opening #4/#1/#2 passage and avoiding the C3 artillery cluster at [6,5]/[7,5]/[6.6,6]?",
                "constraint": "C3 shell windows show repeated Ansel+Steward 1801 hits before Steward dies at 3943.",
            },
        ],
    }


def main() -> None:
    report = comparison()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
