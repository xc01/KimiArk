#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[5]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_small_learning_v1"
REVIEW = EXPERIMENT / "read_only_review_v1"
MANIFEST = EXPERIMENT / "artifact_manifest_v1.json"
TRANSCRIPT = EXPERIMENT / "session/codex_cli/attempt_01/codex_exec.jsonl.gz"
REPORT_JSON = REVIEW / "read_only_review_v1.json"
REPORT_MD = REVIEW / "read_only_review_v1.md"
REVIEW_MANIFEST = REVIEW / "review_manifest_v1.json"

OPERATOR_MAX_HP = {
    "char_123_fang": 1325.0,
    "char_4093_frston": 1152.0,
    "char_283_midn": 1653.0,
    "char_208_melan": 2745.0,
    "char_212_ansel": 1135.0,
    "char_120_hibisc": 1220.0,
    "char_210_stward": 1100.0,
}

KEY_ENEMY_IDS = [
    "enemy_1110_uamord#21",
    "enemy_1110_uamord#22",
    "enemy_1108_uterer#28",
    "enemy_1108_uterer#31",
    "enemy_1110_uamord#33",
    "enemy_1110_uamord#34",
]

OPERATOR_DEATH_TYPES = {"DAMAGE", "ENEMY_ABILITY_HIT", "HEAL", "OPERATOR_DEATH"}
ARTILLERY_SHELL_TYPES = {"ENEMY_ABILITY_START", "PROJECTILE_BORN", "ENEMY_ABILITY_HIT"}
DEVICE_TYPES = {"DEVICE_DAMAGE", "DEVICE_DESTROYED"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def verify_experiment_manifest() -> dict[str, Any]:
    manifest = load_json(MANIFEST)
    bad = []
    for item in manifest["files"]:
        path = ROOT / item["path"]
        if not path.is_file():
            bad.append({"path": item["path"], "reason": "missing"})
            continue
        raw = path.read_bytes()
        if path.name.endswith(".gz"):
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                bad.append({"path": item["path"], "reason": "archive hash"})
            if item.get("bytes") != path.stat().st_size:
                bad.append({"path": item["path"], "reason": "archive bytes"})
            raw = gzip.decompress(raw)
        if hashlib.sha256(raw).hexdigest() != item.get("restored_sha256", item["sha256"]):
            bad.append({"path": item["path"], "reason": "restored/file hash"})
    return {
        "entries": len(manifest["files"]),
        "verified": not bad,
        "mismatches": bad,
        "sha256": sha256(MANIFEST),
    }


def candidate_root(number: int) -> Path:
    return EXPERIMENT / "session/candidates" / f"candidate-{number:03d}"


def load_candidate(number: int) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    root = candidate_root(number)
    plan = load_gzip_json(root / "simulation/plan_snapshot.json.gz")
    events = load_gzip_json(root / "simulation/diagnostic_events.json.gz")["events"]
    summary = load_gzip_json(root / "simulation/diagnostic_summary.json.gz")
    return plan, events, summary


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event.get("event_type"),
        "frame": event.get("frame"),
        "source_id": event.get("source_id"),
        "target_id": event.get("target_id"),
        "details": event.get("details", {}),
    }


def select_events(
    events: list[dict[str, Any]],
    *,
    types: set[str],
    earliest: int | None = None,
    latest: int | None = None,
    source_id: str | None = None,
    target_id: str | None = None,
) -> list[dict[str, Any]]:
    matches = []
    for event in events:
        if event.get("event_type") not in types:
            continue
        frame = event.get("frame")
        if earliest is not None and frame < earliest:
            continue
        if latest is not None and frame > latest:
            continue
        if source_id is not None and event.get("source_id") != source_id:
            continue
        if target_id is not None and event.get("target_id") != target_id:
            continue
        matches.append(compact_event(event))
    return matches


def operator_damage(events: list[dict[str, Any]], operator_id: str, latest: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ordinary_damage_total": 0.0,
        "ordinary_damage_count": 0,
        "ability_damage_total": 0.0,
        "ability_damage_count": 0,
        "heal_total": 0.0,
        "heal_count": 0,
        "events": [],
    }
    for event in events:
        if event.get("target_id") != operator_id:
            continue
        if event["event_type"] not in {"DAMAGE", "ENEMY_ABILITY_HIT", "HEAL", "OPERATOR_DEATH"}:
            continue
        if latest is not None and event.get("frame") > latest:
            continue
        kind = event["event_type"]
        if kind == "DAMAGE":
            result["ordinary_damage_total"] += float(event.get("details", {}).get("amount", 0))
            result["ordinary_damage_count"] += 1
        elif kind == "ENEMY_ABILITY_HIT":
            result["ability_damage_total"] += float(event.get("details", {}).get("amount", 0))
            result["ability_damage_count"] += 1
        elif kind == "HEAL":
            result["heal_total"] += float(event.get("details", {}).get("amount", 0))
            result["heal_count"] += 1
        result["events"].append(compact_event(event))
    return result


def roadblock_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    damage: dict[str, dict[str, Any]] = defaultdict(lambda: {"event_count": 0, "damage_total": 0.0})
    destroyed = {}
    all_roadblock_events = []
    for event in events:
        target = event.get("target_id") or ""
        source = event.get("source_id") or ""
        if target.startswith("trap_020_roadblock") or source.startswith("trap_020_roadblock"):
            all_roadblock_events.append(compact_event(event))
        if event["event_type"] == "DEVICE_DAMAGE" and target.startswith("trap_020_roadblock"):
            item = damage[target]
            item["event_count"] += 1
            item["damage_total"] += float(event.get("details", {}).get("amount", 0))
        elif event["event_type"] == "DEVICE_DESTROYED" and target.startswith("trap_020_roadblock"):
            destroyed[target] = event.get("frame")
    return {"damage": dict(sorted(damage.items())), "destroyed_frames": dict(sorted(destroyed.items()))}


def protected_target_summary(events: list[dict[str, Any]], target_id: str) -> dict[str, Any]:
    return [
        compact_event(event)
        for event in events
        if target_id in (event.get("source_id"), event.get("target_id"))
        and event["event_type"] in {"SPAWN", "BLOCK", "TARGET_SELECTION", "ATTACK_STRIKE", "ATTACK_START", "DAMAGE", "PROJECTILE_BORN", "ENEMY_DEATH", "PROTECTED_TARGET_REACHED", "ENEMY_LEAK"}
    ]


def key_enemy_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for enemy_id in KEY_ENEMY_IDS:
        matches = [
            event for event in events
            if enemy_id in (event.get("source_id"), event.get("target_id"))
        ]
        result[enemy_id] = {
            "event_types": dict(sorted(Counter(event["event_type"] for event in matches).items())),
            "operator_ordinary_damage_taken": sum(
                float(event.get("details", {}).get("amount", 0))
                for event in matches
                if event["event_type"] == "DAMAGE" and event.get("target_id") == enemy_id
                and str(event.get("source_id", "")).startswith("char_")
            ),
            "operator_ability_damage_taken": sum(
                float(event.get("details", {}).get("amount", 0))
                for event in matches
                if event["event_type"] == "ENEMY_ABILITY_HIT" and event.get("target_id") == enemy_id
                and str(event.get("source_id", "")).startswith("char_")
            ),
            "operator_block_count": sum(
                event["event_type"] == "BLOCK" and event.get("target_id") == enemy_id
                for event in matches
            ),
        }
    return result


def candidate_summary(number: int) -> dict[str, Any]:
    plan, events, diagnostic_summary = load_candidate(number)
    return {
        "candidate_id": f"candidate-{number:03d}",
        "candidate_sha256": load_json(candidate_root(number) / "candidate_record.json")["candidate_sha256"],
        "plan_id": plan["operational_plan_id"],
        "parent_plan_id": plan.get("parent_plan_id"),
        "selected_operator_ids": plan["selected_low_star_operator_ids"],
        "action_count": len(plan["action_timeline"]),
        "validation_card": plan.get("validation_card"),
        "final_status": load_json(candidate_root(number) / "simulation/final_status.json"),
        "protected_target_deaths": diagnostic_summary.get("protected_target_deaths", []),
        "protected_target_reached_events": diagnostic_summary.get("protected_target_reached_events", []),
        "roadblocks": roadblock_summary(events),
        "protected_target_3": protected_target_summary(events, "enemy_3001_upeopl#3"),
        "key_enemies": key_enemy_summary(events),
    }


def opening_dependency() -> dict[str, Any]:
    c1_plan, c1_events, _ = load_candidate(1)
    c2_plan, c2_events, _ = load_candidate(2)
    c1_fang = operator_damage(c1_events, "char_123_fang", 1389)
    c1_friston = operator_damage(c1_events, "char_4093_frston", 1554)
    c1_ansel = operator_damage(c1_events, "char_212_ansel", 1571)
    c2_ansel = operator_damage(c2_events, "char_212_ansel", 2593)
    c2_steward = operator_damage(c2_events, "char_210_stward", 3460)
    return {
        "planned_central_window": "4380-5500",
        "c1": {
            "fang": c1_fang,
            "friston": c1_friston,
            "ansel": c1_ansel,
            "no_heal_to_fang_or_friston_before_deaths": not any(
                event["event_type"] == "HEAL"
                and event.get("target_id") in {"char_123_fang", "char_4093_frston"}
                and event.get("frame") < 1389
                for event in c1_events
            ),
            "artillery_shells": select_events(c1_events, types=ARTILLERY_SHELL_TYPES, earliest=1200, latest=1700, source_id="enemy_1112_emppnt#0"),
            "deaths": select_events(c1_events, types={"OPERATOR_DEATH"}, earliest=0, latest=1800),
        },
        "c2": {
            "opening_heals": select_events(c2_events, types={"HEAL"}, earliest=1321, latest=1681, source_id="char_120_hibisc"),
            "fang_skill_dp": select_events(c2_events, types={"DP_CHANGE"}, earliest=2060, latest=2080),
            "steward_deploy": select_events(c2_events, types={"DEPLOY"}, earliest=2070, latest=2072, source_id="char_210_stward"),
            "ansel": c2_ansel,
            "ansel_shell_window": select_events(c2_events, types=ARTILLERY_SHELL_TYPES, earliest=2343, latest=2593, source_id="enemy_1112_emppnt#0"),
            "ansel_survival_arithmetic": {
                "max_hp": OPERATOR_MAX_HP["char_212_ansel"],
                "first_hit_remaining": OPERATOR_MAX_HP["char_212_ansel"] - 891,
                "self_heal_after_first_hit": 506.8,
                "before_second_hit": OPERATOR_MAX_HP["char_212_ansel"] - 891 + 506.8,
                "second_hit_would_be_fatal": OPERATOR_MAX_HP["char_212_ansel"] - 891 + 506.8 - 891 < 0,
                "boundary": "Derived from listed max HP and complete DAMAGE/ENEMY_ABILITY_HIT/HEAL events; no direct HP-state field is logged.",
            },
            "steward": c2_steward,
            "steward_shell_window": select_events(c2_events, types=ARTILLERY_SHELL_TYPES, earliest=2910, latest=3460, source_id="enemy_1112_emppnt#0"),
            "steward_survival_arithmetic": {
                "max_hp": OPERATOR_MAX_HP["char_210_stward"],
                "first_three_hits_each": 910.0,
                "listed_heals_between_hits": [
                    558.9,
                    351.1,
                    558.9,
                    351.1,
                    558.9,
                ],
                "final_hit_frame": 3460,
                "boundary": "Survival to frame 3460 is arithmetically consistent with listed HP cap and heal caps; no direct HP-state field is logged.",
            },
            "central_contact_21_22": key_enemy_summary(c2_events),
        },
    }


def query_audit() -> dict[str, Any]:
    rows = []
    with gzip.open(TRANSCRIPT, "rt", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            item = payload.get("item", {})
            if payload.get("type") != "item.completed" or item.get("type") != "mcp_tool_call":
                continue
            arguments = item.get("arguments") or {}
            result = (item.get("result") or {}).get("structured_content") or {}
            pagination = result.get("pagination") or {}
            rows.append({
                "item_id": item.get("id"),
                "tool": item.get("tool"),
                "status": item.get("status"),
                "arguments": arguments,
                "total_matches": pagination.get("total_matches"),
                "returned_matches": pagination.get("returned_matches"),
                "next_offset": pagination.get("next_offset"),
                "truncated": pagination.get("truncated"),
                "byte_budget_truncated": pagination.get("byte_budget_truncated"),
                "response_event_bytes": result.get("response_event_bytes"),
                "observation_coverage": result.get("observation_coverage"),
                "aggregate": result.get("aggregate"),
            })
    queries = [row for row in rows if row["tool"] == "query_events"]
    signatures = defaultdict(list)
    for row in queries:
        arguments = row["arguments"]
        signature = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        signatures[signature].append(row["item_id"])
    for row in queries:
        signature = json.dumps(row["arguments"], ensure_ascii=False, sort_keys=True)
        row["exact_duplicate"] = len(signatures[signature]) > 1
        row["page_continuation_followed"] = False
        row["page_not_followed"] = row.get("next_offset") is not None
    for index, row in enumerate(queries):
        next_offset = row.get("next_offset")
        if next_offset is None:
            continue
        expected = dict(row["arguments"])
        expected["offset"] = next_offset
        expected_signature = json.dumps(expected, ensure_ascii=False, sort_keys=True)
        row["page_continuation_followed"] = any(
            json.dumps(candidate["arguments"], ensure_ascii=False, sort_keys=True) == expected_signature
            for candidate in queries[index + 1:index + 4]
        )
    by_candidate = Counter(row["arguments"].get("candidate_id") for row in queries)
    by_type = Counter(row["arguments"].get("event_type") for row in queries)
    return {
        "completed_tool_calls": len(rows),
        "completed_tool_counts": dict(Counter(row["tool"] for row in rows)),
        "query_count": len(queries),
        "query_count_by_candidate": dict(by_candidate),
        "query_count_by_event_type": dict(sorted(by_type.items())),
        "all_observation_coverage_complete": all(row["observation_coverage"] == "COMPLETE" for row in queries),
        "exact_duplicate_count": sum(row["exact_duplicate"] for row in queries),
        "truncated_page_count": sum(row["truncated"] is True for row in queries),
        "truncated_page_continuations_followed": sum(row["page_continuation_followed"] is True for row in queries),
        "truncated_page_continuations_not_followed": sum(
            row["truncated"] is True and row["page_continuation_followed"] is False
            for row in queries
        ),
        "aggregate_scope_verified_from_source": True,
        "aggregate_scope_source_lines": "scripts/kimiark_tactical_stdio_service_v1.py:1170-1190",
        "queries": queries,
    }


def build_report() -> dict[str, Any]:
    evidence = json.loads((EXPERIMENT / "input_bundle/llm_evidence_context.json").read_text(encoding="utf-8"))
    return {
        "schema_version": "KIMIARK_SMALL_LEARNING_READ_ONLY_REVIEW_V1",
        "scope": {
            "real_model_calls": 0,
            "real_simulations": 0,
            "new_experiment_starts": 0,
            "existing_budget_changed": False,
        },
        "source_state": {
            "local_head": "0e33dca1db721d14b047c145b41009fb60f8fb3a",
            "origin_master_observed": "0e33dca1db721d14b047c145b41009fb60f8fb3a",
            "work_independently_confirmed": False,
            "manifest": verify_experiment_manifest(),
        },
        "mechanics_version": evidence["mechanics_version"],
        "coordinate_conventions": evidence["stage_active_facts"]["coordinate_conventions"],
        "roadblock_plan_tiles_row_col": evidence["stage_active_facts"]["roadblock_plan_tiles_row_col"],
        "active_device_tiles_col_row": evidence["stage_active_facts"]["active_device_tiles_col_row"],
        "candidates": [candidate_summary(1), candidate_summary(2)],
        "opening_dependency": opening_dependency(),
        "query_effectiveness": query_audit(),
        "next_question": {
            "priority": 1,
            "question": "Can a seven-ID structure preserve C2's opening healer sequence and Steward deployment while changing the shell-survival condition enough that Ansel and Steward are alive through 3460, and then still put live arts output or BLOCK on #21/#22 in the 4380-5500 window?",
            "already_answered_without_new_simulation": [
                "C1's central hypothesis was not refuted; it was truncated before the planned window.",
                "C2 repaired Fang/Friston survival through Steward deployment, but Ansel and Steward were not alive through 3460.",
                "Roadblock #3 was not assigned to an operator and had zero DEVICE_DAMAGE; roadblock #3 is trap_020_roadblock#3, not protected enemy_3001_upeopl#3.",
                "In C2, #21/#22 had no operator DAMAGE, ENEMY_ABILITY_HIT, or BLOCK.",
            ],
            "new_condition_to_test": [
                "Shell-survival support for Ansel through two 891 hits at locked [7,5] and Steward through four 910 hits ending at [7,2].",
                "At least one live operator contact with #21/#22 during 4380-5500, observable as BLOCK or operator-sourced DAMAGE/ENEMY_ABILITY_HIT.",
                "Do not use roadblock #4 clearance or terminal kill/leak totals as evidence that central contact improved.",
            ],
            "no_simulation_conditions": [
                "If opening healing or Steward deployment still cannot be preserved, the central window remains untestable.",
                "If the next candidate only shifts death time or changes terminal totals while leaving 4380-5500 contact unchanged, it adds little new information.",
            ],
        },
        "scope_boundaries": {
            "fixed_simulator_only": True,
            "real_game_faithful_robust_or_probability_claim": False,
            "seven_or_fewer_feasibility": "UNKNOWN",
            "causal_counterfactual_simulation_not_run": True,
        },
    }


def write_review_manifest() -> None:
    entries = []
    for path in sorted(REVIEW.rglob("*")):
        if not path.is_file() or path == REVIEW_MANIFEST or "__pycache__" in path.parts:
            continue
        entry = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        if path.name.endswith(".gz"):
            restored = path.with_suffix("")
            if restored.is_file():
                entry["restored_sha256"] = sha256(restored)
        entries.append(entry)
    REVIEW_MANIFEST.write_text(
        json.dumps({"schema_version": "KIMIARK_SMALL_LEARNING_REVIEW_MANIFEST_V1", "files": entries}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    report = build_report()
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_review_manifest()
    print(REPORT_JSON)


if __name__ == "__main__":
    main()
