#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_gap_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def ensure_plaintext(path: Path) -> None:
    archive_path = path.with_suffix(path.suffix + ".gz")
    if not path.exists() and archive_path.exists():
        path.write_bytes(gzip.decompress(archive_path.read_bytes()))


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


def main() -> None:
    ledger = json.loads((EXPERIMENT / "candidate_ledger_v1.json").read_text())
    authorization = json.loads((EXPERIMENT / "model_authorization_v1.json").read_text())
    budget = json.loads((EXPERIMENT / "simulation_budget_v1.json").read_text())
    attempt = json.loads((EXPERIMENT / "session/codex_cli/cli_process_attempt.json").read_text())
    process = json.loads((EXPERIMENT / "session/codex_cli/cli_process_result.json").read_text())
    pre_cli_status = json.loads((EXPERIMENT / "session/mcp/pre_cli_status.json").read_text())["result"]["structuredContent"]
    parent_identity = json.loads((EXPERIMENT / "input_bundle/parent_identity_manifest_v1.json").read_text())
    exec_path = EXPERIMENT / "session/codex_cli/codex_exec.jsonl"

    tool_counts = Counter(
        json.loads(line)["item"]["tool"]
        for line in exec_path.read_text().splitlines()
        if line and json.loads(line).get("type") == "item.completed"
        and json.loads(line).get("item", {}).get("type") == "mcp_tool_call"
    )
    errors = []
    visible_messages = []
    usage_record = None
    for line in exec_path.read_text().splitlines():
        parsed = json.loads(line)
        if parsed.get("type") == "error":
            errors.append(parsed.get("message"))
        if parsed.get("type") == "turn.failed":
            errors.append((parsed.get("error") or {}).get("message"))
        if parsed.get("type") == "item.completed" and parsed.get("item", {}).get("type") == "agent_message":
            visible_messages.append(parsed["item"].get("text"))
        if parsed.get("type") == "turn.completed":
            usage_record = parsed.get("usage")
    if not errors:
        raise RuntimeError("expected quota/usage failure was not found")
    if not any("usage limit" in str(error) for error in errors):
        raise RuntimeError(f"unexpected terminal error: {errors}")

    candidate_dir = EXPERIMENT / "session/candidates/candidate-001"
    plan = json.loads((candidate_dir / "simulation/plan_snapshot.json").read_text())
    structured = json.loads((candidate_dir / "source/llm_structured_output.json").read_text())
    ensure_plaintext(candidate_dir / "simulation/diagnostic_summary.json")
    ensure_plaintext(candidate_dir / "simulation/diagnostic_events.json")
    validation_plan = structured["revised_operational_plans"][0]
    summary = json.loads((candidate_dir / "simulation/diagnostic_summary.json").read_text())
    events = json.loads((candidate_dir / "simulation/diagnostic_events.json").read_text())["events"]
    result = summary["result"]
    artillery_damage = [
        event for event in events
        if event.get("event_type") == "DAMAGE"
        and event.get("target_id") == "enemy_1112_emppnt#0"
        and event.get("source_id") == "char_210_stward"
    ]
    def deaths(enemy_id: str) -> list[int]:
        return [event["frame"] for event in events if event.get("event_type") == "ENEMY_DEATH" and event.get("target_id") == enemy_id]
    def leaks(enemy_id: str) -> list[int]:
        return [event["frame"] for event in events if event.get("event_type") == "ENEMY_LEAK" and event.get("source_id") == enemy_id]

    archives = {}
    for plaintext in (candidate_dir / "simulation/diagnostic_events.json", candidate_dir / "simulation/diagnostic_summary.json"):
        archives[plaintext.name] = compress_json(plaintext)

    closeout = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_GAP_PARTIAL_CLOSEOUT_V1",
        "experiment_id": EXPERIMENT.name,
        "model": {
            "provider": authorization["provider"],
            "configured_model": authorization["model"],
            "reasoning_effort": authorization["reasoning_effort"],
            "features_apps": authorization["features_apps"],
            "identity_proof_boundary": "Configured identity only; no cryptographic remote-model identity was proven.",
        },
        "process_and_failure": {
            "attempt": attempt,
            "process_result": process,
            "terminal_errors": errors,
            "classification": "EXTERNAL_QUOTA_USAGE_LIMIT",
            "automatic_retry_or_resume": False,
            "automatic_model_or_region_change": False,
            "final_message_file_exists": (EXPERIMENT / "session/codex_cli/codex_final_message.txt").exists(),
            "visible_agent_messages_before_failure": visible_messages,
            "usage_record": usage_record,
            "usage_boundary": "No turn.completed usage record; model usage is not available from this failed turn.",
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        },
        "budget_and_counters": {
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
        "candidate_001": {
            "candidate_id": "candidate-001",
            "candidate_sha256": ledger["attempts"][0]["candidate_sha256"],
            "plan_id": plan["operational_plan_id"],
            "plan_sha256": digest(candidate_dir / "simulation/plan_snapshot.json"),
            "action_sha256": digest(candidate_dir / "simulation/action_snapshot.json"),
            "selected_operator_ids": plan["selected_low_star_operator_ids"],
            "validation_card": validation_plan.get("validation_card"),
            "observed_result": {
                "classification": summary["classification"],
                "deployment_errors": result["deployment_errors"],
                "enemies_killed": result["enemies_killed"],
                "enemies_leaked": result["enemies_leaked"],
                "enemies_remaining": result["enemies_remaining"],
                "first_leak": summary["first_failure"]["first_leak"],
                "first_objective_failure": summary["first_failure"]["objective_failure"],
                "operator_deaths": [event for event in events if event.get("event_type") == "OPERATOR_DEATH"],
                "protected_target_deaths": summary["protected_target_deaths"],
                "protected_target_reached_events": summary["protected_target_reached_events"],
                "real_game_win_claim": summary["real_game_win_claim"],
                "operationally_verified": summary["operationally_verified"],
            },
            "key_duty_observations": {
                "route_11_deaths": deaths("enemy_1107_uoffcr#11"),
                "route_13_deaths": deaths("enemy_1107_uoffcr#13"),
                "roadblock4_destroyed": [event["frame"] for event in events if event.get("event_type") == "DEVICE_DESTROYED" and event.get("target_id") == "trap_020_roadblock#4"],
                "steward_artillery": {
                    "first_hit": artillery_damage[0]["frame"],
                    "last_hit": artillery_damage[-1]["frame"],
                    "hit_count": len(artillery_damage),
                    "damage_total": sum(event["details"]["amount"] for event in artillery_damage),
                    "death_frames": [event["frame"] for event in events if event.get("event_type") == "OPERATOR_DEATH" and event.get("source_id") == "char_210_stward"],
                    "death_shell": [event for event in events if event.get("event_type") == "ENEMY_ABILITY_HIT" and event.get("target_id") == "char_210_stward" and event.get("source_id") == "enemy_1112_emppnt#0" and event.get("frame") == 3970],
                    "artillery_death_frames": deaths("enemy_1112_emppnt#0"),
                    "artillery_leak_frames": leaks("enemy_1112_emppnt#0"),
                },
                "hibiscus_skill_test": {
                    "activated_frames": [event["frame"] for event in events if event.get("event_type") == "SKILL_ACTIVATE" and event.get("source_id") == "char_120_hibisc"],
                    "early_heals": [event for event in events if event.get("event_type") == "HEAL" and event.get("source_id") == "char_120_hibisc" and 2900 <= event.get("frame", 0) <= 3500],
                    "death_frames": [event["frame"] for event in events if event.get("event_type") == "OPERATOR_DEATH" and event.get("source_id") == "char_120_hibisc"],
                },
                "protected_3_death_frames": deaths("enemy_3001_upeopl#3"),
                "protected_14_death_frames": deaths("enemy_3001_upeopl#14"),
                "central_leaks": {enemy_id: leaks(enemy_id) for enemy_id in ("enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#33", "enemy_1110_uamord#34")},
            },
            "large_json_archives": archives,
        },
        "conclusions": {
            "complete_simulator_win": False,
            "proven_named_triple": False,
            "hypothesis_classification": {
                "early_hibiscus_boost_repair": "REFUTED_BY_EVENTS: Hibiscus delivered boosted heals to Steward@2944 and self@3030 but died@3161; Steward still died@3970 and artillery leaked@5759.",
                "treatment_competition_as_general_cause": "PARTIAL_HYPOTHESIS_ONLY: timing changes altered heal targets and deaths, but exact HP/full candidate ordering remains UNKNOWN.",
            },
            "preserved_duties": {"routes_11_13": True, "roadblock4": True, "protected_14_reach": True},
            "regressed_or_failed_duties": {"artillery_closure": True, "protected_3": True, "central_21_22_33_34": True},
            "candidate_002": "NOT_RUN_DUE_TO_EXTERNAL_QUOTA_USAGE_LIMIT; remaining check/candidate/simulation budget was not consumed.",
            "boundary": "Fixed-simulator evidence only; no real-game, faithful, robust, probability, seven-ID-impossibility, or global-minimum claim.",
        },
        "unauthorized_next_question": "After quota is restored under a new authorization, test a mechanism that keeps Steward alive through its recorded 3911/3970 shell windows without relying on early Hibiscus support; preserve C2's #11/#13/#14 chain and specify who delivers the needed late heal or accepts/reduces shell exposure.",
    }
    closeout_path = EXPERIMENT / "closeout_report_v1.json"
    write_json(closeout_path, closeout)
    (EXPERIMENT / "closeout_report_v1.json.sha256").write_text(digest(closeout_path) + "\n")

    manifest_paths = [
        EXPERIMENT / "candidate_ledger_v1.json",
        EXPERIMENT / "model_authorization_v1.json",
        EXPERIMENT / "simulation_budget_v1.json",
        EXPERIMENT / "session_config_v1.json",
        EXPERIMENT / "session/codex_cli/sol_prompt_v1.txt",
        EXPERIMENT / "session/codex_cli/codex_command.json",
        EXPERIMENT / "session/codex_cli/codex_exec.jsonl",
        EXPERIMENT / "session/codex_cli/codex_stderr.txt",
        EXPERIMENT / "session/codex_cli/cli_process_attempt.json",
        EXPERIMENT / "session/codex_cli/cli_process_result.json",
        EXPERIMENT / "session/mcp/pre_cli_status.json",
    ]
    for candidate_directory in sorted((EXPERIMENT / "session/candidates").glob("candidate-*")):
        for path in sorted(candidate_directory.rglob("*")):
            if path.is_file() and path.name not in {"diagnostic_events.json", "diagnostic_summary.json"}:
                manifest_paths.append(path)
    for archive in archives.values():
        manifest_paths.append(EXPERIMENT / archive["path"])
    artifact_entries = []
    for path in sorted(set(manifest_paths)):
        entry = {"bytes": path.stat().st_size, "path": path.relative_to(EXPERIMENT).as_posix(), "sha256": digest(path)}
        if path.name.endswith(".json.gz"):
            entry["restored_sha256"] = restored_digest(path)
        artifact_entries.append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_GAP_ARTIFACT_MANIFEST_V1",
        "gzip_policy": "Single-layer gzip; every compressed diagnostic JSON was restored and sha256-verified.",
        "artifacts": artifact_entries,
    })

    markdown = f"""# R111 artillery-gap partial closeout\n\n- The CLI was terminated by an explicit external quota/usage limit; no automatic retry/resume/model/region change was made.\n- Budget used: CLI 1/1, checks 2/10, candidates 1/2, simulations 1/2. Candidate 002 and one simulation were deliberately not run.\n- C001 tested only Hibiscus skill 3140→2773. It preserved #11/#13, roadblock4, and #14 reach, but Hibiscus died earlier@3161; Steward still died@3970 and artillery leaked@5759.\n- Steward output was 2161→3937 with 38 hits/11,035.13 damage. #3 died@5384 and central #21/#22/#33/#34 leaked. No complete seven-ID WIN and no proven named triple.\n- The early-Hibiscus-boost repair hypothesis is refuted by events; treatment competition remains only a partial hypothesis. M70 remains the eight-ID fixed-simulator WIN and seven-or-fewer feasibility remains UNKNOWN.\n- Large diagnostic JSONs are single-layer gzip archives with restored-hash verification in `artifact_manifest_v1.json`.\n"""
    (EXPERIMENT / "experiment_closeout_v1.md").write_text(markdown)


if __name__ == "__main__":
    main()
