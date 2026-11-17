#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_triple_duty_batch_v1"


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


def deaths(events: list[dict], enemy_id: str) -> list[int]:
    return [event["frame"] for event in events if event.get("event_type") == "ENEMY_DEATH" and event.get("target_id") == enemy_id]


def leaks(events: list[dict], enemy_id: str) -> list[int]:
    return [event["frame"] for event in events if event.get("event_type") == "ENEMY_LEAK" and event.get("source_id") == enemy_id]


def candidate_report(candidate_id: str, candidate_sha256: str) -> dict:
    candidate_dir = EXPERIMENT / "session/candidates" / candidate_id
    plan_path = candidate_dir / "simulation/plan_snapshot.json"
    action_path = candidate_dir / "simulation/action_snapshot.json"
    summary_path = candidate_dir / "simulation/diagnostic_summary.json"
    events_path = candidate_dir / "simulation/diagnostic_events.json"
    structured_path = candidate_dir / "source/llm_structured_output.json"

    plan = json.loads(plan_path.read_text())
    structured = json.loads(structured_path.read_text())
    validation_plan = structured["revised_operational_plans"][0]
    summary = json.loads(summary_path.read_text())
    events = json.loads(events_path.read_text())["events"]
    artillery_damage = [
        event for event in events
        if event.get("event_type") == "DAMAGE"
        and event.get("target_id") == "enemy_1112_emppnt#0"
        and event.get("source_id") == "char_210_stward"
    ]
    result = summary["result"]
    archive = {}
    for plaintext in (events_path, summary_path):
        archive[plaintext.name] = compress_json(plaintext)

    return {
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "plan_id": plan["operational_plan_id"],
        "plan_sha256": digest(plan_path),
        "action_sha256": digest(action_path),
        "selected_operator_ids": plan["selected_low_star_operator_ids"],
        "validation_card": validation_plan.get("validation_card"),
        "parent_hypothesis_id": validation_plan.get("parent_hypothesis_id"),
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
            "route_11_deaths": deaths(events, "enemy_1107_uoffcr#11"),
            "route_13_deaths": deaths(events, "enemy_1107_uoffcr#13"),
            "roadblock4_destroyed": [event for event in events if event.get("event_type") == "DEVICE_DESTROYED" and event.get("target_id") == "trap_020_roadblock#4"],
            "artillery": {
                "enemy_id": "enemy_1112_emppnt#0",
                "death_frames": deaths(events, "enemy_1112_emppnt#0"),
                "steward_hit_count": len(artillery_damage),
                "steward_damage_total": sum(event["details"]["amount"] for event in artillery_damage),
                "leak_frames": leaks(events, "enemy_1112_emppnt#0"),
            },
            "protected_3_death_frames": deaths(events, "enemy_3001_upeopl#3"),
            "protected_14_death_frames": deaths(events, "enemy_3001_upeopl#14"),
            "central_leaks": {
                enemy_id: leaks(events, enemy_id)
                for enemy_id in ("enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#33", "enemy_1110_uamord#34")
            },
        },
        "large_json_archives": archive,
    }


def main() -> None:
    ledger = json.loads((EXPERIMENT / "candidate_ledger_v1.json").read_text())
    authorization = json.loads((EXPERIMENT / "model_authorization_v1.json").read_text())
    budget = json.loads((EXPERIMENT / "simulation_budget_v1.json").read_text())
    process = json.loads((EXPERIMENT / "session/codex_cli/cli_process_result.json").read_text())
    pre_cli_status = json.loads((EXPERIMENT / "session/mcp/pre_cli_status.json").read_text())["result"]["structuredContent"]
    parent_identity = json.loads((EXPERIMENT / "input_bundle/parent_identity_manifest_v1.json").read_text())
    codex_exec_path = EXPERIMENT / "session/codex_cli/codex_exec.jsonl"
    tool_counts = Counter(
        json.loads(line)["item"]["tool"]
        for line in codex_exec_path.read_text().splitlines()
        if line and json.loads(line).get("type") == "item.completed"
        and json.loads(line).get("item", {}).get("type") == "mcp_tool_call"
    )
    usage_record = None
    for line in codex_exec_path.read_text().splitlines():
        parsed = json.loads(line)
        if parsed.get("type") == "turn.completed":
            usage_record = parsed.get("usage")

    candidates = [candidate_report(f"candidate-{index:03d}", attempt["candidate_sha256"]) for index, attempt in enumerate(ledger["attempts"], start=1)]
    closeout = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_CLOSEOUT_V1",
        "experiment_id": EXPERIMENT.name,
        "model": {
            "provider": authorization["provider"],
            "configured_model": authorization["model"],
            "reasoning_effort": authorization["reasoning_effort"],
            "features_apps": authorization["features_apps"],
            "identity_proof_boundary": "Configured identity only; no cryptographic remote-model identity was proven.",
        },
        "process": process,
        "budget_and_counters": {
            "real_cli_starts": authorization["real_cli_starts"],
            "candidate_ledger": ledger,
            "simulation_budget": budget,
            "production_tool_calls": dict(sorted(tool_counts.items())),
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
            "visible_usage_records": usage_record if usage_record is not None else [],
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
        "comparison": {
            "earliest_duty_divergence_r106_vs_c5": {
                "observed": "R106 Melantha damaged #5@1036; C5's lower support substitution produced a different early chain. The model's event query reported Melantha@1036 versus Spot@1054, followed by C5 Friston@1479 and Steward@2923.",
                "boundary": "This is observed timing divergence, not proof that one early event alone caused all later losses.",
            },
            "parent_choice": "R106 was used as default primary because it observed #11/#13 plus artillery@4273; C5 and R107 recovery remained references.",
        },
        "candidates": candidates,
        "conclusions": {
            "complete_simulator_win": False,
            "proven_named_triple": False,
            "best_candidate_id": "candidate-002",
            "best_observed_kills_leaks": [21, 12],
            "routes_11_13_closed_in_every_run": all(candidate["key_duty_observations"]["route_11_deaths"] and candidate["key_duty_observations"]["route_13_deaths"] for candidate in candidates),
            "roadblock4_destroyed_in_every_run": all(candidate["key_duty_observations"]["roadblock4_destroyed"] for candidate in candidates),
            "protected_14_reached_in_runs": ["candidate-001", "candidate-002"],
            "artillery_closed_in_any_run": any(candidate["key_duty_observations"]["artillery"]["death_frames"] for candidate in candidates),
            "artillery_leaked_in_every_run": all(candidate["key_duty_observations"]["artillery"]["leak_frames"] == [5759] for candidate in candidates),
            "candidate_3_regression": "Changing Ansel to [5,6] DOWN caused external healing but Melantha@2143 and Steward@2593 deaths, artillery support fell to 9 hits/2466.09, #14 died@6314, and 19/14 followed.",
            "boundary": "Fixed-simulator evidence only; no real-game, faithful, robust, probability, seven-ID-impossibility, or global-minimum claim.",
        },
        "unauthorized_next_question": "Can C2's retained #11/#13/#14 chain and surviving Hibiscus window be kept while separating Steward's artillery support from the observed physician/heal competition enough to close artillery before its 5759 leak, without adding an eighth ID?",
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
        EXPERIMENT / "session/codex_cli/codex_final_message.txt",
        EXPERIMENT / "session/codex_cli/codex_stderr.txt",
        EXPERIMENT / "session/codex_cli/cli_process_attempt.json",
        EXPERIMENT / "session/codex_cli/cli_process_result.json",
        EXPERIMENT / "session/mcp/pre_cli_status.json",
    ]
    for candidate_dir in sorted((EXPERIMENT / "session/candidates").glob("candidate-*")):
        for path in sorted(candidate_dir.rglob("*")):
            if path.is_file() and path.name not in {"diagnostic_events.json", "diagnostic_summary.json"}:
                manifest_paths.append(path)
    for candidate in candidates:
        for archive in candidate["large_json_archives"].values():
            manifest_paths.append(EXPERIMENT / archive["path"])

    artifact_entries = []
    for path in sorted(set(manifest_paths)):
        entry = {"bytes": path.stat().st_size, "path": path.relative_to(EXPERIMENT).as_posix(), "sha256": digest(path)}
        if path.name.endswith(".json.gz"):
            entry["restored_sha256"] = restored_digest(path)
        artifact_entries.append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_TRIPLE_DUTY_BATCH_ARTIFACT_MANIFEST_V1",
        "gzip_policy": "Single-layer gzip; every compressed diagnostic JSON was restored and sha256-verified.",
        "artifacts": artifact_entries,
    })

    markdown = f"""# R110 triple-duty batch closeout\n\n- Model session completed normally. Configured identity: {authorization['model']}/{authorization['reasoning_effort']}; features.apps={authorization['features_apps']}.\n- Budget used: CLI {authorization['real_cli_starts']['used_real_cli_starts']}/{authorization['real_cli_starts']['authorized_real_cli_starts']}, checks {ledger['used_check_calls']}/{ledger['max_check_calls']}, candidates {ledger['used_candidates']}/{ledger['max_candidates']}, simulations {budget['started_stage_simulations']}/{budget['max_stage_simulations']}.\n- No complete seven-ID WIN and no proven named triple. Best candidate was candidate-002 at 21 kills/12 leaks.\n- #11/#13 closed in every run. #14 reached in C001/C002; artillery and all four named central enemies leaked in every run. C003 regressed to 19/14 with both protected targets dead.\n- Final boundaries: M70 remains the eight-ID fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN. No real-game, faithful, robust, probability, impossibility, or global-minimum claim is made.\n- Large diagnostic JSONs are single-layer gzip archives with restored-hash verification in `artifact_manifest_v1.json`.\n"""
    (EXPERIMENT / "experiment_closeout_v1.md").write_text(markdown)


if __name__ == "__main__":
    main()
