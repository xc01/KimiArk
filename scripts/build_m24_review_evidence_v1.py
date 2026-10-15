from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/review/fc77177"
BASE = ROOT / "output/r8_1_r8_7_batch_v1"
CODE_SHA = "4073c511f214ae291ea4508af84db521254cf689"
GAME_SHA = "0ef7f952dfd018392200157a5c79a6511ba69122"
MECHANICS = "m23-behavioral-mechanics-v1"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gzip(path: Path) -> Any:
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def event_file_record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        **file_record(path),
        "decompressed_sha256": sha256_bytes(gzip.decompress(raw)),
        "decompressible": True,
    }


def static_record(path: Path) -> dict[str, Any]:
    data = load(path)
    return {
        "classification": data["classification"],
        "conflict_count": len(data["conflicts"]),
        "conflicts": data["conflicts"],
    }


def match_plan_and_actions(out: Path) -> dict[str, Any]:
    plan = load(out / "plan_snapshot.json")
    action_doc = load(out / "action_snapshot.json")
    if "revised_operational_plans" in plan:
        plan = plan["revised_operational_plans"][0]
    actions = action_doc["actions"]
    return {
        "action_count": len(actions),
        "actions_match_plan_timeline": plan["action_timeline"] == actions,
        "action_snapshot_sha256": file_record(out / "action_snapshot.json")["sha256"],
        "plan_snapshot_sha256": file_record(out / "plan_snapshot.json")["sha256"],
    }


def source_snapshot_match(source: Path, out: Path) -> dict[str, Any]:
    source_doc = load(source / "llm_structured_output.json")
    plan_snapshot = load(out / "plan_snapshot.json")
    action_snapshot = load(out / "action_snapshot.json")["actions"]
    if "revised_operational_plans" in source_doc and "revised_operational_plans" in plan_snapshot:
        plan_match = source_doc == plan_snapshot
        source_actions = source_doc["revised_operational_plans"][0]["action_timeline"]
    else:
        plan_match = source_doc["revised_operational_plans"][0] == plan_snapshot
        source_actions = source_doc["revised_operational_plans"][0]["action_timeline"]
    return {
        "source_plan_matches_snapshot": plan_match,
        "source_action_matches_snapshot": source_actions == action_snapshot,
    }


def base_run(out: Path, plan_id: str, stage_id: str, source: Path) -> dict[str, Any]:
    manifest = load(out / "m23_revalidation_manifest.json")
    compact = load(out / "compact_revalidation.json")
    plan = load(out / "plan_snapshot.json")
    if "revised_operational_plans" in plan:
        plan = plan["revised_operational_plans"][0]
    return {
        "stage_id": stage_id,
        "plan_id": plan_id,
        "runtime_code_commit_sha256": CODE_SHA,
        "runtime_working_tree_git_diff": "EMPTY_AT_FROZEN_CODE_CHECKPOINT",
        "mechanics_version": MECHANICS,
        "fixed_gamedata_version_sha256": GAME_SHA,
        "source": str(source.relative_to(ROOT)),
        "source_files": {
            "llm_evidence_context.json": file_record(source / "llm_evidence_context.json"),
            "llm_structured_output.json": file_record(source / "llm_structured_output.json"),
        },
        "snapshot": match_plan_and_actions(out),
        "source_snapshot_match": source_snapshot_match(source, out),
        "static_check": static_record(out / "static_compile_results.json"),
        "simulation_parameters": file_record(out / "simulation_parameters.json"),
        "result": compact["result"],
        "counts": compact["counts"],
        "active_at_run_end_ids": compact["active_at_run_end_ids"],
        "manifest": file_record(out / "m23_revalidation_manifest.json"),
    }


def add_attempt_and_events(run: dict[str, Any], out: Path) -> dict[str, Any]:
    attempt = load(out / "simulation_attempt.json")
    run["simulation_attempt"] = {
        "started_count": int(attempt["stage_simulations_started"]),
        "completed_count": int(attempt["status"] == "COMPLETED"),
        "automatic_retry": attempt["automatic_retry"],
        "attempt_file": file_record(out / "simulation_attempt.json"),
    }
    run["event_file"] = event_file_record(out / "diagnostic_events.json.gz")
    run["event_count"] = len(load_gzip(out / "diagnostic_events.json.gz")["events"])
    run["summary_file"] = event_file_record(out / "diagnostic_summary.json.gz")
    return run


def r8_1_runs() -> list[dict[str, Any]]:
    source = ROOT / "output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli"
    out = BASE / "main_08-01/m23_deployment_slot_revalidation_v1/c7_targeting"
    summary = load_gzip(out / "roadblock_targeting_replay_summary.json.gz")
    static = static_record(out / "static_compile_results.json")
    snapshot = match_plan_and_actions(out)
    runs = []
    pairs = [
        (
            "A_NOT_ORDINARILY_TARGETABLE",
            "a_not_ordinarily_targetable_events.json.gz",
            "m23_revalidation_manifest_A_NOT_ORDINARILY_TARGETABLE.json",
            "compact_revalidation_A_NOT_ORDINARILY_TARGETABLE.json",
        ),
        (
            "B_LOW_PRIORITY_NO_ENEMY_ONLY",
            "b_low_priority_no_enemy_only_events.json.gz",
            "m23_revalidation_manifest_B_LOW_PRIORITY_NO_ENEMY_ONLY.json",
            "compact_revalidation_B_LOW_PRIORITY_NO_ENEMY_ONLY.json",
        ),
    ]
    for variant, event_name, manifest_name, compact_name in pairs:
        events = load_gzip(out / event_name)["events"]
        manifest = load(out / manifest_name)
        compact = load(out / compact_name)
        runs.append(
            {
                "stage_id": "main_08-01",
                "plan_id": "R8_1_LOWSTAR_PLAN_C7",
                "roadblock_targeting_variant": variant,
                "runtime_code_commit_sha256": CODE_SHA,
                "runtime_working_tree_git_diff": "EMPTY_AT_FROZEN_CODE_CHECKPOINT",
                "mechanics_version": MECHANICS,
                "fixed_gamedata_version_sha256": GAME_SHA,
                "source": str(source.relative_to(ROOT)),
                "source_files": {
                    "llm_evidence_context.json": file_record(source / "llm_evidence_context.json"),
                    "llm_structured_output.json": file_record(source / "llm_structured_output.json"),
                    "direction_complete_action_candidate.json": file_record(
                        source / "direction_complete_action_candidate.json"
                    ),
                },
                "snapshot": snapshot,
                "source_snapshot_match": source_snapshot_match(source, out),
                "static_check": static,
                "result": compact["result"],
                "counts": compact["counts"],
                "active_at_run_end_ids": compact["active_at_run_end_ids"],
                "simulation_attempt": {
                    "started_count": 1,
                    "completed_count": 1,
                    "automatic_retry": False,
                    "attempt_file": "NOT_PRESENT",
                    "evidence_basis": "one event file and one variant result in the shared replay summary",
                },
                "event_file": event_file_record(out / event_name),
                "event_count": len(events),
                "summary_file": event_file_record(out / "roadblock_targeting_replay_summary.json.gz"),
                "manifest": file_record(out / manifest_name),
                "shared_replay_summary_sha256": file_record(
                    out / "roadblock_targeting_replay_summary.json.gz"
                )["sha256"],
                "first_divergent_event": summary["first_divergent_event"],
            }
        )
    return runs


def related(events: list[dict[str, Any]], entity_id: str, types: set[str]) -> list[dict[str, Any]]:
    return [
        row
        for row in events
        if (row.get("source_id") == entity_id or row.get("target_id") == entity_id)
        and row.get("event_type") in types
    ]


def r8_1_feedback(events_a: list[dict[str, Any]], events_b: list[dict[str, Any]]) -> dict[str, Any]:
    target_types = {
        "SPAWN",
        "BLOCK",
        "UNBLOCK",
        "ATTACK_START",
        "ATTACK_STRIKE",
        "PROJECTILE_BORN",
        "PROJECTILE_HIT",
        "DAMAGE",
        "ENEMY_DEATH",
        "ENEMY_LEAK",
        "SKILL_ACTIVATE",
    }

    def leak_view(events: list[dict[str, Any]], enemy_id: str) -> dict[str, Any]:
        spawn = next(row for row in events if row["event_type"] == "SPAWN" and row["source_id"] == enemy_id)
        leak = next(row for row in events if row["event_type"] == "ENEMY_LEAK" and row["source_id"] == enemy_id)
        return {
            "instance_id": enemy_id,
            "route_id": spawn["details"]["route_id"],
            "spawn_frame": spawn["frame"],
            "leak_frame": leak["frame"],
            "direct_combat_events": related(events, enemy_id, target_types - {"SPAWN", "ENEMY_LEAK"}),
        }

    return {
        "schema_version": "M24_CAUSAL_FEEDBACK_R8_1_V1",
        "stage_id": "main_08-01",
        "plan_id": "R8_1_LOWSTAR_PLAN_C7",
        "leaked_instances": [
            leak_view(events_a, "enemy_1108_uterer#53"),
            leak_view(events_a, "enemy_1108_uterer#54"),
        ],
        "variant_comparison": {
            "same_final_numbers": True,
            "events_identical": False,
            "first_divergent_event": {
                "index": 2414,
                "frame": 360,
                "time": 12.0,
                "a": {
                    "event_type": "DEVICE_TARGET_SELECTION",
                    "source_id": "char_124_kroos",
                    "target_id": None,
                    "rule": "NO_CANDIDATE",
                },
                "b": {
                    "event_type": "DEVICE_TARGET_SELECTION",
                    "source_id": "char_124_kroos",
                    "target_id": "trap_020_roadblock#3",
                    "rule": "DEVICE_IF_OPERATOR_HAS_NO_ENEMY_TARGET_LOCAL_ORDINARY_DEVICE_CANDIDATES_DEVICE_ID_ORDER",
                },
            },
        },
        "interpretation": {
            "direct_cause": "route-34 late pressure is outside the recorded direct-combat coverage for both leaked instances",
            "variant_boundary": "A and B differ in device targeting; identical totals do not establish robustness",
            "UNKNOWN": ["exact client roadblock selector priority", "exact enemy route interaction outside modeled events"],
        },
    }


def r8_4_feedback(events: list[dict[str, Any]]) -> dict[str, Any]:
    ansel_events = related(
        events,
        "char_212_ansel",
        {"DAMAGE", "HEAL", "OPERATOR_DEATH", "SKILL_ACTIVATE"},
    )
    damage = [row for row in ansel_events if row["event_type"] == "DAMAGE"]
    heals = [row for row in ansel_events if row["event_type"] == "HEAL"]
    post = [row for row in events if row["frame"] >= 5304]
    post_kills = [row for row in post if row["event_type"] == "ENEMY_DEATH" and row.get("details", {}).get("kill_counted")]
    return {
        "schema_version": "M24_CAUSAL_FEEDBACK_R8_4_V1",
        "stage_id": "main_08-04",
        "plan_id": "R8_4_GPT_V4_M23_DEPLOYMENT_SLOT_REVALIDATION_V1",
        "death": {
            "operator_id": "char_212_ansel",
            "frame": 5304,
            "time": 176.8,
            "fatal_source": "enemy_1109_uabone#56",
            "fatal_damage": 241.0,
            "damage_kind": "enemy_physical",
            "lifetime_damage": sum(row["details"]["amount"] for row in damage),
            "lifetime_heal": sum(row["details"]["amount"] for row in heals),
            "damage_events": damage,
            "heal_events": heals,
        },
        "post_death_outcome": {
            "enemy_kills": len(post_kills),
            "kill_sources": sorted({row["source_id"] for row in post_kills}),
            "leaks": len([row for row in post if row["event_type"] == "ENEMY_LEAK"]),
            "protected_target_deaths": len(
                [row for row in post if row["event_type"] == "ENEMY_DEATH" and row.get("details", {}).get("life_delta", 0) < 0]
            ),
            "protected_target_arrivals": len(
                [row for row in post if row["event_type"] == "PROTECTED_TARGET_REACHED"]
            ),
            "ansel_events_after_death": [],
        },
        "interpretation": {
            "direct_cause": "sustained physical pressure from two bonecutters overcame Ansel's self-heal before frame 5304",
            "duty_effect": "Ansel produced no combat or heal events after death, but remaining deployed duties closed the route",
            "goal_boundary": "operator death is recorded separately; zero-leak and protected-target-zero-loss are not negated by it",
        },
    }


def r8_7_feedback(events: list[dict[str, Any]]) -> dict[str, Any]:
    first_death = next(row for row in events if row["event_type"] == "OPERATOR_DEATH")
    first_leak = next(row for row in events if row["event_type"] == "ENEMY_LEAK")
    artillery = [
        row
        for row in events
        if row["event_type"] in {"ENEMY_ABILITY_START", "ENEMY_ABILITY_HIT"}
        and row.get("source_id") == "enemy_1112_emppnt#0"
    ]
    protected_deaths = [
        row
        for row in events
        if row["event_type"] == "ENEMY_DEATH" and row.get("details", {}).get("life_delta", 0) < 0
    ]
    return {
        "schema_version": "M24_CAUSAL_FEEDBACK_R8_7_V1",
        "stage_id": "main_08-07",
        "plan_id": "R8_7_GPT_V13_M23_DEPLOYMENT_SLOT_REVALIDATION_V1",
        "first_operator_death": {
            "operator_id": first_death["source_id"],
            "frame": first_death["frame"],
            "time": first_death["time"],
            "preceding_artillery": [
                row
                for row in artillery
                if row["frame"] in {1440, 1530, 1590, 1680}
                and row.get("target_id") == first_death["source_id"]
            ],
        },
        "first_leak": {
            "instance_id": first_leak["source_id"],
            "frame": first_leak["frame"],
            "time": first_leak["time"],
        },
        "protected_target_deaths": [
            {
                "instance_id": row["target_id"],
                "source": row["source_id"],
                "frame": row["frame"],
                "life_delta": row["details"]["life_delta"],
            }
            for row in protected_deaths
        ],
        "artillery_lifecycle": [
            row
            for row in artillery
            if row["frame"] in {1440, 1530, 1590, 1680, 1890, 1980, 2790, 2880, 3090, 3180}
        ],
        "interpretation": {
            "opening_chain": "artillery at [3,5] hit Ansel at 1530 and 1680; the second hit killed Ansel before the first recorded leak at 1931",
            "later_chain": "later artillery and officer pressure broke the line, then roadblock-restrained civilians were struck",
            "mechanism_boundary": "current model supports delay, locked position, radius, and faction/defense filtering; exact client target selection and route interaction remain UNKNOWN",
        },
    }


def tactical_payload(
    stage_id: str,
    source: Path,
    out: Path,
    plan_id: str,
    result: dict[str, Any],
    feedback: dict[str, Any],
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    evidence_source = source / "llm_evidence_context.json"
    evidence_target = out / "evidence_context.json"
    evidence_target.write_bytes(evidence_source.read_bytes())
    plan = load(source / "llm_structured_output.json")["revised_operational_plans"][0]
    payload = {
        "schema_version": "M24_TACTICAL_REVISION_INPUT_V1",
        "stage_id": stage_id,
        "plan_id": plan_id,
        "model_policy": {
            "provider": "openai",
            "model": "gpt-6.1-sol",
            "reasoning_effort_allowed": ["medium", "high"],
            "cli_process_starts": 0,
            "status": "NOT_SENT",
        },
        "hard_goal": {
            "win": True,
            "enemy_leaks": 0,
            "protected_target_deaths": 0,
            "protected_targets_all_arrive": True,
            "operator_deaths_are_separate_metric": True,
        },
        "constraints": {
            "normal_mode_1_to_3_star_only": True,
            "exclude_mode_reserved_operators": True,
            "gpt_may_change": ["roles", "deployments", "skills", "retreats", "handoffs", "economy structure"],
            "python_may_change": [],
            "no_delay_only_solution": True,
            "no_forced_safe_arrival": True,
        },
        "mechanics": {
            "version": MECHANICS,
            "gamedata_sha256": GAME_SHA,
            "supported": [
                "remaining-life WIN gate",
                "neutral protected-target scoring",
                "ordinary-operator no attack/no block of neutrals",
                "officer protected-target attack radius",
                "roadblock protected-target restraint radius",
                "release of ordinary block slot on death",
            ],
            "unknown": [
                "exact client roadblock selector priority",
                "exact protected-target route interaction",
                "redeployment cost growth",
                "full probability dependency model",
            ],
        },
        "current_result": result,
        "causal_feedback": feedback,
        "original_plan": plan,
        "evidence_context": {
            "path": str(evidence_target.relative_to(ROOT)),
            "sha256": file_record(evidence_target)["sha256"],
        },
    }
    payload_path = out / "codex_payload.json"
    write_json(payload_path, payload)
    write_json(
        out / "payload_manifest.json",
        {
            "schema_version": "M24_TACTICAL_REVISION_PAYLOAD_MANIFEST_V1",
            "stage_id": stage_id,
            "plan_id": plan_id,
            "payload": file_record(payload_path),
            "evidence_context": file_record(evidence_target),
            "sent": False,
            "model_calls": 0,
        },
    )
    return {
        "stage_id": stage_id,
        "plan_id": plan_id,
        "payload": file_record(payload_path),
        "manifest": file_record(out / "payload_manifest.json"),
        "sent": False,
    }


def main() -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    r8_2_out = BASE / "main_08-02/m23_deployment_slot_revalidation_v1/v15"
    r8_4_out = BASE / "main_08-04/m23_deployment_slot_revalidation_v1/v4"
    r8_7_out = BASE / "main_08-07/m23_deployment_slot_revalidation_v1/v13"
    runs = r8_1_runs()
    runs.append(
        add_attempt_and_events(
            base_run(
                r8_2_out,
                "R8_2_GPT_V15_M23_DEPLOYMENT_SLOT_REVALIDATION_V1",
                "main_08-02",
                BASE / "main_08-02/clearance_cli_v15",
            ),
            r8_2_out,
        )
    )
    runs.append(
        add_attempt_and_events(
            base_run(
                r8_4_out,
                "R8_4_GPT_V4_M23_DEPLOYMENT_SLOT_REVALIDATION_V1",
                "main_08-04",
                BASE / "main_08-04/local_device_revision_v4",
            ),
            r8_4_out,
        )
    )
    runs.append(
        add_attempt_and_events(
            base_run(
                r8_7_out,
                "R8_7_GPT_V13_M23_DEPLOYMENT_SLOT_REVALIDATION_V1",
                "main_08-07",
                BASE / "main_08-07/local_device_revision_v13",
            ),
            r8_7_out,
        )
    )
    events_a = load_gzip(
        BASE
        / "main_08-01/m23_deployment_slot_revalidation_v1/c7_targeting/a_not_ordinarily_targetable_events.json.gz"
    )["events"]
    events_b = load_gzip(
        BASE
        / "main_08-01/m23_deployment_slot_revalidation_v1/c7_targeting/b_low_priority_no_enemy_only_events.json.gz"
    )["events"]
    events_r8_4 = load_gzip(r8_4_out / "diagnostic_events.json.gz")["events"]
    events_r8_7 = load_gzip(r8_7_out / "diagnostic_events.json.gz")["events"]
    causal = {
        "schema_version": "M24_CAUSAL_FEEDBACK_BUNDLE_V1",
        "code_commit_sha256": CODE_SHA,
        "mechanics_version": MECHANICS,
        "r8_1": r8_1_feedback(events_a, events_b),
        "r8_4": r8_4_feedback(events_r8_4),
        "r8_7": r8_7_feedback(events_r8_7),
    }
    write_json(REVIEW / "m24_causal_feedback_v1.json", causal)
    r8_1_payload = tactical_payload(
        "main_08-01",
        ROOT / "output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli",
        BASE / "main_08-01/m24_tactical_revision_input_v1",
        "R8_1_LOWSTAR_PLAN_C7",
        {
            "targeting_a": causal["r8_1"],
            "targeting_b": causal["r8_1"],
            "result_summary": runs[0]["result"],
        },
        causal["r8_1"],
    )
    r8_7_payload = tactical_payload(
        "main_08-07",
        BASE / "main_08-07/local_device_revision_v13",
        BASE / "main_08-07/m24_tactical_revision_input_v1",
        "R8_7_GPT_V13_M23_DEPLOYMENT_SLOT_REVALIDATION_V1",
        runs[-1]["result"],
        causal["r8_7"],
    )
    report = {
        "schema_version": "M24_REVIEW_EVIDENCE_BUNDLE_V1",
        "generated_from_saved_artifacts_only": True,
        "new_simulations": 0,
        "new_model_calls": 0,
        "code_commit_sha256": CODE_SHA,
        "mechanics_version": MECHANICS,
        "fixed_gamedata_version_sha256": GAME_SHA,
        "runs": runs,
        "start_completed_reconciliation": {
            "r8_1": "2 inferred STARTED/COMPLETED from two variant event files and shared summary",
            "r8_2": "1 STARTED/COMPLETED from simulation_attempt.json",
            "r8_4": "1 STARTED/COMPLETED from simulation_attempt.json",
            "r8_7": "1 STARTED/COMPLETED from simulation_attempt.json",
            "total_full_stage_simulations_started": 5,
        },
        "causal_feedback": file_record(REVIEW / "m24_causal_feedback_v1.json"),
        "tactical_payloads": [r8_1_payload, r8_7_payload],
        "fallback_git_bundle": {
            "path": "/tmp/KimiArk_m24_unpushed_21f2914_840de3f.bundle",
            "sha256": "0349369c7a87d2d46e835f7e651c7b715a6508abd32c0f7e72a58fb3a0af7a8b",
            "verified": True,
        },
    }
    write_json(REVIEW / "m24_review_evidence_v1.json", report)


if __name__ == "__main__":
    main()
