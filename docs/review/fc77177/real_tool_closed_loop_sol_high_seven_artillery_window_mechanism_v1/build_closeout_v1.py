#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_window_mechanism_v1"
PARENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_window_mechanism_v1/input_bundle/default_parent_R110_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_002"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def compress_json(path: Path) -> dict:
    compressed_path = path.with_suffix(path.suffix + ".gz")
    source_digest = digest(path)
    with compressed_path.open("wb") as handle:
        with gzip.GzipFile(filename=path.name, fileobj=handle, mode="wb", mtime=0) as archive:
            archive.write(path.read_bytes())
    restored = restored_digest(compressed_path)
    if restored != source_digest:
        raise RuntimeError(f"restored hash mismatch: {compressed_path}")
    path.unlink()
    return {
        "bytes": compressed_path.stat().st_size,
        "path": compressed_path.relative_to(EXPERIMENT).as_posix(),
        "restored_sha256": restored,
        "sha256": digest(compressed_path),
    }


def deep_diff(parent: dict, candidate: dict) -> list[dict]:
    parent_actions = parent["actions"]
    candidate_actions = candidate["actions"]
    if len(parent_actions) > len(candidate_actions):
        raise RuntimeError("candidate has fewer actions than parent")
    unchanged_prefix = 0
    for left, right in zip(parent_actions, candidate_actions):
        if left == right:
            unchanged_prefix += 1
        else:
            break
    return [{
        "index": unchanged_prefix,
        "parent": parent_actions[unchanged_prefix],
        "candidate": candidate_actions[unchanged_prefix],
        "added_tail": candidate_actions[len(parent_actions):],
        "changed_count": sum(left != right for left, right in zip(parent_actions, candidate_actions)),
    }]


def observed_key_events(events: list[dict]) -> dict:
    artillery = [
        event for event in events
        if event.get("event_type") == "DAMAGE"
        and event.get("target_id") == "enemy_1112_emppnt#0"
        and event.get("source_id") == "char_210_stward"
    ]
    central_ids = ["enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#33", "enemy_1110_uamord#34"]
    return {
        "route_11_block_death": [event for event in events if event.get("event_type") in {"BLOCK", "ENEMY_DEATH"} and event.get("target_id") == "enemy_1107_uoffcr#11"],
        "route_13_block_death": [event for event in events if event.get("event_type") in {"BLOCK", "ENEMY_DEATH"} and event.get("target_id") == "enemy_1107_uoffcr#13"],
        "roadblock4_destroyed": [event for event in events if event.get("event_type") == "DEVICE_DESTROYED" and event.get("target_id") == "trap_020_roadblock#4"],
        "steward_artillery_damage": {"first": artillery[0], "last": artillery[-1], "count": len(artillery), "damage_total": sum(event["details"]["amount"] for event in artillery)} if artillery else {"count": 0, "damage_total": 0},
        "artillery_death": [event for event in events if event.get("event_type") == "ENEMY_DEATH" and event.get("target_id") == "enemy_1112_emppnt#0"],
        "artillery_leak": [event for event in events if event.get("event_type") == "ENEMY_LEAK" and event.get("source_id") == "enemy_1112_emppnt#0"],
        "enemy_19_death_leak": [event for event in events if event.get("target_id") == "enemy_1107_uoffcr#19" or (event.get("source_id") == "enemy_1107_uoffcr#19" and event.get("event_type") == "ENEMY_LEAK")],
        "central_enemy_deaths_leaks": {enemy_id: [event for event in events if event.get("target_id") == enemy_id or (event.get("source_id") == enemy_id and event.get("event_type") == "ENEMY_LEAK")] for enemy_id in central_ids},
        "operator_deaths": [event for event in events if event.get("event_type") == "OPERATOR_DEATH"],
        "protected_target_reached_events": [event for event in events if event.get("event_type") == "PROTECTED_TARGET_REACHED"],
        "protected_target_deaths": [event for event in events if event.get("event_type") == "ENEMY_DEATH" and event.get("target_id") in {"enemy_3001_upeopl#3", "enemy_3001_upeopl#14"}],
        "late_steward_heals": [event for event in events if event.get("event_type") == "HEAL" and event.get("target_id") == "char_210_stward" and 3300 <= event.get("frame", 0) <= 4300],
        "hibiscus_diversion_window_heals": [event for event in events if event.get("event_type") == "HEAL" and event.get("source_id") == "char_120_hibisc" and 3350 <= event.get("frame", 0) <= 3500],
    }


def main() -> None:
    ledger = json.loads((EXPERIMENT / "candidate_ledger_v1.json").read_text())
    authorization = json.loads((EXPERIMENT / "model_authorization_v1.json").read_text())
    budget = json.loads((EXPERIMENT / "simulation_budget_v1.json").read_text())
    attempt = json.loads((EXPERIMENT / "session/codex_cli/cli_process_attempt.json").read_text())
    process = json.loads((EXPERIMENT / "session/codex_cli/cli_process_result.json").read_text())
    pre_cli_status = json.loads((EXPERIMENT / "session/mcp/pre_cli_status.json").read_text())["result"]["structuredContent"]
    parent_identity = json.loads((EXPERIMENT / "input_bundle/parent_identity_manifest_v1.json").read_text())
    parent_actions = json.loads((PARENT / "action_snapshot.json").read_text())

    exec_path = EXPERIMENT / "session/codex_cli/codex_exec.jsonl"
    tool_counts = Counter()
    usage_records = []
    visible_messages = []
    stream_errors = []
    for line in exec_path.read_text().splitlines():
        if not line:
            continue
        parsed = json.loads(line)
        if parsed.get("type") == "item.completed":
            item = parsed.get("item", {})
            if item.get("type") == "mcp_tool_call":
                tool_counts[item["tool"]] += 1
            if item.get("type") == "agent_message":
                visible_messages.append(item.get("text"))
        if parsed.get("type") == "error":
            stream_errors.append(parsed.get("message"))
        if parsed.get("type") == "turn.failed":
            stream_errors.append((parsed.get("error") or {}).get("message"))
        if parsed.get("type") == "turn.completed":
            usage_records.append(parsed.get("usage"))

    archives = {}
    candidate_records = []
    for candidate_id in ("candidate-001", "candidate-002"):
        candidate_dir = EXPERIMENT / "session/candidates" / candidate_id
        simulation = candidate_dir / "simulation"
        source = candidate_dir / "source"
        events_path = simulation / "diagnostic_events.json"
        summary_path = simulation / "diagnostic_summary.json"
        events = json.loads(events_path.read_text())["events"]
        summary = json.loads(summary_path.read_text())
        final_status = json.loads((simulation / "final_status.json").read_text())
        plan = json.loads((simulation / "plan_snapshot.json").read_text())
        action = json.loads((simulation / "action_snapshot.json").read_text())
        structured = json.loads((source / "llm_structured_output.json").read_text())
        validation_card = structured["revised_operational_plans"][0]["validation_card"]
        record = {
            "schema_version": "KIMIARK_R112_ARTILLERY_WINDOW_CANDIDATE_RECORD_V1",
            "candidate_id": candidate_id,
            "candidate_sha256": next(item["candidate_sha256"] for item in ledger["attempts"] if item["candidate_id"] == candidate_id),
            "plan_id": plan["operational_plan_id"],
            "plan_sha256": digest(simulation / "plan_snapshot.json"),
            "action_sha256": digest(simulation / "action_snapshot.json"),
            "events_gz_sha256": None,
            "events_restored_sha256": None,
            "selected_operator_ids": plan["selected_low_star_operator_ids"],
            "parent_plan_id": validation_card["main_parent"]["plan_id"],
            "parent_plan_sha256": validation_card["main_parent"]["plan_sha256"],
            "parent_action_sha256": validation_card["main_parent"]["action_sha256"],
            "validation_card": validation_card,
            "summary_result": final_status,
            "observed_key_events": observed_key_events(events),
            "protected_target_reached_events": summary["protected_target_reached_events"],
            "protected_target_deaths": summary["protected_target_deaths"],
            "recorded_action_errors": summary["result"]["deployment_errors"],
            "action_error_classification": "PRODUCTION_RECORDED_DEPLOYMENT_ERRORS" if summary["result"]["deployment_errors"] else "NONE",
            "action_diff": deep_diff(parent_actions, action),
            "all_leaks": {event["source_id"]: event["frame"] for event in events if event.get("event_type") == "ENEMY_LEAK"},
        }
        for name in (events_path.name, summary_path.name):
            archive = compress_json(simulation / name)
            record["events_gz_sha256" if "events" in name else "summary_gz_sha256"] = archive["sha256"]
            record["events_restored_sha256" if "events" in name else "summary_restored_sha256"] = archive["restored_sha256"]
            archives[f"{candidate_id}/{name}"] = archive
        candidate_records.append(record)

    closeout = {
        "schema_version": "KIMIARK_R112_ARTILLERY_WINDOW_MECHANISM_CLOSEOUT_V1",
        "experiment_id": EXPERIMENT.name,
        "model": {
            "provider": authorization["provider"],
            "configured_model": authorization["model"],
            "reasoning_effort": authorization["reasoning_effort"],
            "features_apps": authorization["features_apps"],
            "identity_proof_boundary": "Configured identity only; no cryptographic remote-model identity was proven.",
        },
        "process_and_budget": {
            "attempt": attempt,
            "process_result": process,
            "automatic_retry_or_resume": False,
            "automatic_model_or_region_change": False,
            "stream_errors": stream_errors,
            "stderr_catalog_refresh_timeouts": "OBSERVED_NONFATAL_MODEL_DIRECTORY_REFRESH_TIMEOUTS; session completed normally and no quota error was returned",
            "visible_agent_messages": visible_messages,
            "usage_records": usage_records,
            "usage_boundary": "Visible CLI turn usage only; internal request count remains UNKNOWN_CLI_INTERNAL.",
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "real_cli_starts": authorization["real_cli_starts"],
            "candidate_ledger": ledger,
            "simulation_budget": budget,
            "production_tool_calls": dict(sorted(tool_counts.items())),
            "cached_is_input_subset": True,
        },
        "pre_cli_status": {
            "session_id": pre_cli_status["session_id"],
            "mechanics_version": pre_cli_status["mechanics_version"],
            "execution_backend": pre_cli_status["execution_backend"],
            "allow_fake_execution": pre_cli_status["allow_fake_execution"],
            "max_unique_deployed_operators": pre_cli_status["max_unique_deployed_operators"],
        },
        "parent_identity": parent_identity,
        "event_alignment": {
            "parent_r110_c2": {
                "plan_id": "R110_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_002",
                "steward_hits": 37,
                "steward_damage_total": 10786.03,
                "steward_death": 3911,
                "artillery_leak": 5759,
            },
            "candidate_001_first_divergence": {"event_frame": 1740, "change": "Hibiscus tile 2,6 UP -> 2,7 UP"},
            "candidate_002_first_divergence": {"event_frame": 3400, "change": "Added Fang RETREAT; parent had enemy #15 ATTACK_WINDUP at same frame"},
            "visible_alignment_notes": [
                "R106 first relevant allocation difference at 1654 and 2021 shell lock change; cadence matched C2 through C2's last hit@3889.",
                "R110 C1 first differs from C2 at Hibiscus heal@3116; C1 heal@3288 went to Fang and Hibiscus died@3311.",
                "R111 C001 boosted Steward@2944 but Hibiscus heal@3116 went to Fang and Hibiscus died@3161; artillery leaked@5759.",
            ],
        },
        "candidates": candidate_records,
        "large_json_archives": archives,
        "conclusions": {
            "complete_simulator_win": False,
            "candidate_001_hypothesis": "REFUTED_BY_EVENTS: early Hibiscus isolation removed essential support; Ansel died@2111, Melantha@2261, Steward@2711; route #13 and both protected targets failed; 12 kills/21 leaks.",
            "candidate_002_hypothesis": "SUPPORTED_FOR_SPECIFIC_MECHANISM: late Fang removal changed Hibiscus heal@3460 from Fang in parent to Hibiscus self-heal; Hibiscus survived and delivered Steward heals; Steward 45 hits/13227.21 and artillery killed@4273. It does not prove exact HP sufficiency or treatment competition as a universal cause.",
            "candidate_002_intermediate_named_duties": {"route_11_death": 2881, "route_13_death": 3311, "roadblock4_destroy": 2026, "protected_14_reach": 12448, "artillery_death": 4273, "artillery_leak": None},
            "candidate_002_additional_observed_success": {"protected_3_reach": 15549},
            "candidate_002_independent_failures": {"first_leak": {"enemy_id": "enemy_1107_uoffcr#19", "frame": 4475}, "central_leaks": {"enemy_1110_uamord#21": 5046, "enemy_1110_uamord#22": 6886, "enemy_1110_uamord#33": 6901, "enemy_1110_uamord#34": 6996}},
            "candidate_002_full_result": {"kills": 22, "leaks": 11, "remaining_life": -8, "remaining_enemies": 0, "simulator_win": False},
            "new_artillery_output_vs_parent": {"hit_delta": 8, "damage_delta": 2441.18},
            "boundary": "Fixed-simulator evidence only; no real-game, faithful, robust, probability, seven-ID-impossibility, or global-minimum claim.",
        },
        "unauthorized_next_question": "With artillery and the named early/protected duties now co-observed, test a mechanism for the first independent central/route leak (#19@4475, then #21@5046) while preserving late Fang removal, physician geometry, and artillery closure. Full WIN still requires zero leaks and dual protected arrival.",
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)
    (EXPERIMENT / "closeout_report_v1.json.sha256").write_text(digest(closeout_path) + "\n")

    manifest_paths = [
        EXPERIMENT / "candidate_ledger_v1.json",
        EXPERIMENT / "model_authorization_v1.json",
        EXPERIMENT / "simulation_budget_v1.json",
        EXPERIMENT / "session_config_v1.json",
        EXPERIMENT / "closeout_report_v1.json",
        EXPERIMENT / "closeout_report_v1.json.sha256",
    ]
    for path in sorted(EXPERIMENT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(EXPERIMENT).as_posix()
        if path == (EXPERIMENT / "artifact_manifest_v1.json"):
            continue
        if relative.startswith("session/candidates/") and (path.name in {"diagnostic_events.json", "diagnostic_summary.json"}):
            continue
        if relative.startswith("session/candidates/simulation.run.lock"):
            continue
        if relative.endswith(".lock") or "__pycache__/" in relative:
            continue
        manifest_paths.append(path)
    artifact_entries = []
    for path in sorted(set(manifest_paths)):
        entry = {"bytes": path.stat().st_size, "path": path.relative_to(EXPERIMENT).as_posix(), "sha256": digest(path)}
        if path.name.endswith(".json.gz"):
            entry["restored_sha256"] = restored_digest(path)
        artifact_entries.append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", {
        "schema_version": "KIMIARK_R112_ARTILLERY_WINDOW_ARTIFACT_MANIFEST_V1",
        "gzip_policy": "Single-layer gzip; every compressed diagnostic JSON was restored and sha256-verified.",
        "artifacts": artifact_entries,
    })

    markdown = """# R112 artillery-window mechanism closeout

- Complete fixed-simulator WIN failed; final usage was CLI 1/1, checks 3/10, candidates 2/2, simulations 2/2. No retry/resume/model change occurred.
- C001's early Hibiscus isolation was refuted: Ansel died@2111, Melantha@2261, Steward@2711; result 12 kills/21 leaks, artillery leaked@5759, #13 and both protected targets failed.
- C002 restored early geometry and added Fang retreat@3400/redeploy@5501. Hibiscus heal@3460 changed from Fang to self-heal, and Steward received late heal@3632/3804. Steward delivered 45 hits/13,227.21 damage (+8/+2,441.18 vs R110 C2) and killed artillery@4273 with no artillery leak.
- C002 also retained #11@2881, #13@3311, roadblock4@2026, #14 reach@12448, and #3 reach@15549. But #19 leaked@4475, central #21@5046/#22@6886/#33@6901/#34@6996 leaked, final was 22 kills/11 leaks/life -8.
- Stream-visible model usage: input 1,458,801 / cached input 1,344,640 / output 11,645; internal request count UNKNOWN_CLI_INTERNAL. Model-directory refresh timeouts in stderr were nonfatal; no quota error was returned.
- Large diagnostic JSONs are single-layer gzip archives with restored-hash verification in `artifact_manifest_v1.json`. M70 remains the eight-ID fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN.
"""
    (EXPERIMENT / "experiment_closeout_v1.md").write_text(markdown)


if __name__ == "__main__":
    main()
