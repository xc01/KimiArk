#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from difflib import SequenceMatcher


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_recovery_v1"
ORIGINAL = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_v1"
PARENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1/session/candidates/candidate-001/simulation"
CANDIDATE = EXPERIMENT / "session/candidates/candidate-001"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def load_parent_events() -> list[dict]:
    with gzip.open(PARENT / "diagnostic_events.json.gz", "rt", encoding="utf-8") as handle:
        return json.load(handle)["events"]


def archive_large_json(path: Path) -> None:
    compressed = path.with_suffix(path.suffix + ".gz")
    with compressed.open("wb") as handle:
        with gzip.GzipFile(filename=path.name, fileobj=handle, mode="wb", mtime=0) as archive:
            archive.write(path.read_bytes())
    if path.exists():
        path.unlink()


def event_rows(events: list[dict], event_type: str, predicate=None) -> list[dict]:
    rows = [event for event in events if event.get("event_type") == event_type]
    if predicate is not None:
        rows = [event for event in rows if predicate(event)]
    return rows


def compact(events: list[dict], keys: tuple[str, ...] = ("frame", "source_id", "target_id", "details")) -> list[dict]:
    return [{key: event.get(key) for key in keys} for event in events]


def enemy_chain(events: list[dict], enemy_id: str) -> dict:
    related = [event for event in events if event.get("target_id") == enemy_id or event.get("source_id") == enemy_id]
    damage = event_rows(related, "DAMAGE", lambda event: event.get("target_id") == enemy_id)
    ability_hits = event_rows(related, "ENEMY_ABILITY_HIT", lambda event: event.get("target_id") == enemy_id)
    return {
        "blocks": compact(event_rows(related, "BLOCK", lambda event: event.get("target_id") == enemy_id)),
        "unblocks": compact(event_rows(related, "UNBLOCK", lambda event: event.get("target_id") == enemy_id)),
        "damage": {
            "count": len(damage),
            "total": round(sum(float(event["details"]["amount"]) for event in damage if "amount" in event.get("details", {})), 2),
            "first": compact(damage[:1]),
            "last": compact(damage[-1:]),
        },
        "enemy_ability_hits": {
            "count": len(ability_hits),
            "total": round(sum(float(event["details"]["amount"]) for event in ability_hits if "amount" in event.get("details", {})), 2),
            "rows": compact(ability_hits),
        },
        "deaths": compact(event_rows(related, "ENEMY_DEATH", lambda event: event.get("target_id") == enemy_id)),
        "leaks": compact(event_rows(related, "ENEMY_LEAK", lambda event: event.get("source_id") == enemy_id)),
        "reached": compact(event_rows(related, "PROTECTED_TARGET_REACHED", lambda event: event.get("source_id") == enemy_id)),
    }


def artillery(events: list[dict]) -> dict:
    hits = event_rows(events, "DAMAGE", lambda event: event.get("source_id") == "char_210_stward" and event.get("target_id") == "enemy_1112_emppnt#0")
    return {
        "hit_count": len(hits),
        "total_damage": round(sum(float(event["details"]["amount"]) for event in hits), 2),
        "first_hit_frame": hits[0]["frame"] if hits else None,
        "last_hit_frame": hits[-1]["frame"] if hits else None,
        "enemy_death": compact(event_rows(events, "ENEMY_DEATH", lambda event: event.get("target_id") == "enemy_1112_emppnt#0")),
        "enemy_leak": compact(event_rows(events, "ENEMY_LEAK", lambda event: event.get("source_id") == "enemy_1112_emppnt#0")),
        "steward_death": compact(event_rows(events, "OPERATOR_DEATH", lambda event: event.get("source_id") == "char_210_stward")),
        "steward_retreats": compact(event_rows(events, "RETREAT", lambda event: event.get("source_id") == "char_210_stward")),
    }


def action_diff(parent_actions: list[dict], candidate_actions: list[dict]) -> list[dict]:
    result = []
    parent_keys = [json.dumps(action, ensure_ascii=False, sort_keys=True) for action in parent_actions]
    candidate_keys = [json.dumps(action, ensure_ascii=False, sort_keys=True) for action in candidate_actions]
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, parent_keys, candidate_keys, autojunk=False).get_opcodes():
        if tag != "equal":
            result.append({
                "change": tag,
                "parent_indices": list(range(i1, i2)),
                "candidate_indices": list(range(j1, j2)),
                "parent_actions": parent_actions[i1:i2],
                "candidate_actions": candidate_actions[j1:j2],
            })
    return result


def main() -> None:
    plan = load_json(CANDIDATE / "simulation/plan_snapshot.json")
    action = load_json(CANDIDATE / "simulation/action_snapshot.json")
    manifest = load_json(CANDIDATE / "simulation/manifest.json")
    final_status = load_json(CANDIDATE / "simulation/final_status.json")
    parent_plan = load_json(PARENT / "plan_snapshot.json")
    parent_action = load_json(PARENT / "action_snapshot.json")
    parent_events = load_parent_events()
    events = load_json(CANDIDATE / "simulation/diagnostic_events.json")["events"]
    summary = load_json(CANDIDATE / "simulation/diagnostic_summary.json")
    service_result = load_json(EXPERIMENT / "service_call_result_v1.json")
    mapping = load_json(EXPERIMENT / "protocol_recovery_mapping_v1.json")

    common_prefix = 0
    while common_prefix < min(len(parent_events), len(events)) and parent_events[common_prefix] == events[common_prefix]:
        common_prefix += 1

    by_type: dict[str, list[dict]] = {}
    for index, event in enumerate(events):
        by_type.setdefault(event["event_type"], []).append(event)
    protected_deaths = event_rows(events, "ENEMY_DEATH", lambda event: event.get("target_id") in {"enemy_3001_upeopl#3", "enemy_3001_upeopl#14"})
    protected_reached = event_rows(events, "PROTECTED_TARGET_REACHED", lambda event: event.get("source_id") in {"enemy_3001_upeopl#3", "enemy_3001_upeopl#14"})
    action_errors = [
        {"frame": event["frame"], "event_type": event["event_type"], "source_id": event.get("source_id")}
        for event_type in ("DEPLOY", "RETREAT", "SKILL_ACTIVATE")
        for event in by_type.get(event_type, [])
        if event.get("details", {}).get("legal") is False
    ]
    operator_deaths = event_rows(events, "OPERATOR_DEATH")
    leaks = event_rows(events, "ENEMY_LEAK")
    central_ids = ["enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#33", "enemy_1110_uamord#34"]

    candidate_validation = plan["validation_card"]
    candidate = {
        "candidate_id": "candidate-001",
        "plan_id": plan["operational_plan_id"],
        "parent_plan_id": candidate_validation["experience_selector_decision_record"]["selected_parent"]["record_id"].rsplit(":", 1)[0],
        "recovery_class": "MODEL_ORIGINAL_OUTPUT_LOSSLESS_PROTOCOL_RECOVERY",
        "recovery_source": {
            "original_model_output_sha256": mapping["original_sha256"],
            "original_plan_id": mapping["original_operational_plan_id"],
            "normalized_sha256": mapping["normalized_sha256"],
            "canonical_candidate_sha256": service_result["check_result"]["candidate_sha256"],
            "changed_json_paths": mapping["changed_json_paths"],
            "tactical_fields_unchanged": True,
        },
        "model": {
            "configured_model": "gpt-6.1-sol",
            "reasoning_effort": "high",
            "generation_protocol_recovery": False,
            "generation_identity_boundary": "Original tactical output was generated by the R107 real model; this independent recovery run made no model generation.",
        },
        "plan_sha256": digest(CANDIDATE / "simulation/plan_snapshot.json"),
        "action_sha256": digest(CANDIDATE / "simulation/action_snapshot.json"),
        "events_gz_sha256": None,
        "events_restored_sha256": None,
        "operator_union_count": len(plan["selected_low_star_operator_ids"]),
        "summary_result": final_status,
        "protected_target_deaths": compact(protected_deaths),
        "protected_target_reached_events": compact(protected_reached),
        "recorded_action_errors": action_errors,
        "action_error_classification": "OBSERVED_LEGAL_FALSE_AT_RUN",
        "observed_key_events": {
            "equal_parent_event_prefix": {"count": common_prefix, "parent_frame_at_divergence": parent_events[common_prefix]["frame"] if common_prefix < len(parent_events) else None},
            "early_routes": {
                "enemy_1107_uoffcr#11": enemy_chain(events, "enemy_1107_uoffcr#11"),
                "enemy_1107_uoffcr#13": enemy_chain(events, "enemy_1107_uoffcr#13"),
            },
            "protected_targets": {
                "enemy_3001_upeopl#3": enemy_chain(events, "enemy_3001_upeopl#3"),
                "enemy_3001_upeopl#14": enemy_chain(events, "enemy_3001_upeopl#14"),
            },
            "artillery": artillery(events),
            "roadblock_destructions": compact(event_rows(events, "DEVICE_DESTROYED")),
            "operator_deaths": compact(operator_deaths),
            "leaks_by_id_and_frame": compact(leaks),
            "central_chains": {enemy_id: enemy_chain(events, enemy_id) for enemy_id in central_ids},
        },
        "simulator_manifest": manifest,
        "validation_card": candidate_validation,
    }
    closeout = {
        "schema_version": "KIMIARK_R107_RECOVERY_CLOSEOUT_V1",
        "experiment_id": "real_tool_closed_loop_sol_high_seven_protected14_late_release_recovery_v1",
        "model": candidate["model"],
        "budget": {
            "authorized_real_cli_starts": 0,
            "used_real_cli_starts": 0,
            "authorized_model_generation_calls": 0,
            "used_model_generation_calls": 0,
            "authorized_check_calls": 5,
            "used_check_calls": int(service_result["check_result"]["check_call_counted"]),
            "authorized_candidates": 1,
            "used_candidates": int(service_result["check_result"]["candidate_counted"]),
            "authorized_complete_simulations": 1,
            "used_complete_simulations": int(service_result["simulation_result"]["simulation_started_counted"]),
            "automatic_retry_or_resume": False,
            "counting_boundary": "Completed tool calls counted once; model usage is not applicable because generation was 0.",
        },
        "protocol_recovery": {
            "original_experiment_budget": {"real_cli_starts": 1, "check_calls": 1, "candidates": 0, "complete_simulations": 0},
            "original_failure": "check-001 rejected wrong operational_plan_id before candidate creation",
            "required_id_authority": mapping["correct_id_authority"],
            "normalized_only_identity_fields": mapping["changed_json_paths"],
            "tactical_deep_equality": mapping["deep_equality_check"],
            "production_check": service_result["check_result"],
            "future_session_boundary": "While one CLI remains active, using remaining checks to correct a contract/static failure is normal in-budget tool use; a CLI exit requires new authorization and is not resume/retry.",
        },
        "control_validity": {
            "parent_record_id": candidate_validation["experience_selector_decision_record"]["selected_parent"]["record_id"],
            "parent_plan_sha256": candidate_validation["experience_selector_decision_record"]["selected_parent"]["plan_sha256"],
            "parent_action_sha256": candidate_validation["experience_selector_decision_record"]["selected_parent"]["action_sha256"],
            "parent_event_count": len(parent_events),
            "candidate_event_count": len(events),
            "equal_prefix_event_count": common_prefix,
            "first_divergence": "frame 901 DEPLOY: parent Spot replaced by candidate Melantha; this is the model's declared tactical intervention.",
            "parent_roster": parent_plan["selected_low_star_operator_ids"],
            "candidate_roster": plan["selected_low_star_operator_ids"],
        },
        "action_diff_machine": {
            "schema": "SEQUENCE_MATCHER_ACTION_DIFF",
            "parent_action_count": len(parent_action["actions"]),
            "candidate_action_count": len(action["actions"]),
            "diff": action_diff(parent_action["actions"], action["actions"]),
        },
        "candidates": [candidate],
        "closure": {
            "simulator_win": bool(final_status["simulator_win"]),
            "new_win": bool(final_status["simulator_win"]),
            "seven_or_fewer_feasibility": "UNKNOWN",
            "best_verified_operator_count": 8,
            "complete_settlement": {
                "result": "20 kills / 13 leaks / life -11; zero active enemies; five operator deaths.",
                "first_failure": "enemy_1107_uoffcr#19 leaked at frame 4507; first objective-failure record is enemy_1110_uamord#22 at frame 5359.",
                "protected": "#3 died at 5384 from enemy_1107_uoffcr#23; #14 reached at 12448 without recorded DAMAGE, ENEMY_ABILITY_HIT, or ENEMY_DEATH.",
                "early_routes": "#11 BLOCK 2738 / death 2881 and #13 BLOCK 3098 / death 3311 remained closed.",
                "artillery": "Steward survived to 3970 then died; 38 hits/11,035.13 damage, artillery survived and leaked at 5759. The planned 4280 retreat was illegal because Steward was already dead.",
                "central": "#21/#22/#33/#34 leaked at 5046/5359/6846/6996; #22 was briefly blocked, #33/#34 had no recorded BLOCK.",
            },
            "hypothesis_classification": {
                "early_route_closure": "OBSERVED",
                "protected_14_early_release": "REFUTED_IN_THIS_RUN",
                "protected_3_safety": "REFUTED_IN_THIS_RUN",
                "artillery_closure": "REFUTED_IN_THIS_RUN",
                "central_closure": "REFUTED_IN_THIS_RUN",
            },
            "targeted_answer": "The protocol-recovered run produced a complete LOSS. Melantha did not preserve the R106 artillery closure, and the protected-14 release assumption did not turn #14 into a safe route: #14 was never blocked by roadblock 4 and reached safely, while #3 instead died. This is event-specific refutation for this candidate, not evidence that #14's route task is impossible.",
            "next_question": "Can a revised candidate preserve #11/#13 closure while retaining Steward's support long enough to close artillery, and simultaneously give protected #3 a live stop/kill before officer#23's 5264/5324/5384 chain? Continuous positions and exact HP remain UNKNOWN.",
            "scope_boundary": [
                "Current fixed simulator only; not real-game, faithful, robust, probabilistic WIN, or global minimum.",
                "M70 R8_7_GPT_M70_V1 remains the frozen eight-ID complete fixed-simulator WIN.",
                "R106 remains a seven-ID route+artillery local-success branch; R107 recovery is a separate LOSS and does not supersede it.",
            ],
        },
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)

    for name in ("diagnostic_events.json", "diagnostic_summary.json"):
        archive_large_json(CANDIDATE / "simulation" / name)
    candidate["events_gz_sha256"] = digest(CANDIDATE / "simulation/diagnostic_events.json.gz")
    candidate["events_restored_sha256"] = restored_digest(CANDIDATE / "simulation/diagnostic_events.json.gz")
    write_json(closeout_path, closeout)

    manifest_payload = {
        "schema_version": "KIMIARK_R107_RECOVERY_ARTIFACT_MANIFEST_V1",
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
        manifest_payload["files"].append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", manifest_payload)
    (closeout_path.with_suffix(closeout_path.suffix + ".sha256")).write_text(f"{digest(closeout_path)}  {closeout_path.name}\n")


if __name__ == "__main__":
    main()
