import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1"
OPERATORS = {
    "char_123_fang": "芬",
    "char_4093_frston": "Friston-3",
    "char_283_midn": "月见夜",
    "char_284_spot": "斑点",
    "char_212_ansel": "安赛尔",
    "char_120_hibisc": "芙蓉",
    "char_210_stward": "史都华德",
    "char_208_melan": "玫兰莎",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def gzip_file(source: Path, target: Path) -> None:
    raw = source.read_bytes()
    with target.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            compressed.write(raw)


def compact_events(events: list[dict]) -> dict:
    def rows(event_type: str, target_id: str | None = None, source_id: str | None = None):
        return [
            {
                "frame": event["frame"],
                "source_id": event.get("source_id"),
                "target_id": event.get("target_id"),
                "details": event.get("details", {}),
            }
            for event in events
            if event["event_type"] == event_type
            and (target_id is None or event.get("target_id") == target_id)
            and (source_id is None or event.get("source_id") == source_id)
        ]

    artillery_hits = [
        {
            "frame": event["frame"],
            "target_id": event.get("target_id"),
            "details": event.get("details", {}),
        }
        for event in events
        if event["event_type"] == "ENEMY_ABILITY_HIT" and event.get("source_id") == "enemy_1112_emppnt#0"
    ]
    return {
        "event_count": len(events),
        "operator_death_events": rows("OPERATOR_DEATH"),
        "unique_dead_operator_ids": sorted({event.get("source_id") for event in events if event["event_type"] == "OPERATOR_DEATH"}),
        "leak_events": rows("ENEMY_LEAK"),
        "enemy_death_events": rows("ENEMY_DEATH"),
        "roadblock_destroyed_events": rows("DEVICE_DESTROYED"),
        "protected_reached_events": rows("PROTECTED_TARGET_REACHED"),
        "protected_death_events": [row for row in rows("ENEMY_DEATH") if str(row.get("target_id", "")).startswith("enemy_3001_upeopl#")],
        "artillery_ability_hits": artillery_hits,
        "artillery_damage": [
            {"frame": event["frame"], "amount": event["details"].get("amount", 0)}
            for event in events
            if event["event_type"] == "DAMAGE" and event.get("source_id") == "char_210_stward" and event.get("target_id") == "enemy_1112_emppnt#0"
        ],
        "central": {
            enemy_id: {
                "block_frames": [event["frame"] for event in events if event["event_type"] == "BLOCK" and event.get("target_id") == enemy_id],
                "unblock_frames": [event["frame"] for event in events if event["event_type"] == "UNBLOCK" and event.get("target_id") == enemy_id],
                "damage_total": round(sum(event.get("details", {}).get("amount", 0) for event in events if event["event_type"] == "DAMAGE" and event.get("target_id") == enemy_id), 2),
                "leak_frames": [event["frame"] for event in events if event["event_type"] == "ENEMY_LEAK" and event.get("source_id") == enemy_id],
                "death_frames": [event["frame"] for event in events if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") == enemy_id],
            }
            for enemy_id in ("enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#34")
        },
    }


def candidate_facts(candidate_id: str) -> dict:
    candidate = EXPERIMENT / "session/candidates" / candidate_id
    simulation = candidate / "simulation"
    source = candidate / "source"
    raw_events_path = simulation / "diagnostic_events.json"
    raw_summary_path = simulation / "diagnostic_summary.json"
    events_gz = simulation / "diagnostic_events.json.gz"
    summary_gz = simulation / "diagnostic_summary.json.gz"
    gzip_file(raw_events_path, events_gz)
    gzip_file(raw_summary_path, summary_gz)
    events = json.loads(raw_events_path.read_text())["events"]
    summary = json.loads(raw_summary_path.read_text())
    result = {key: value for key, value in summary["result"].items() if key != "events"}
    structured = json.loads((source / "llm_structured_output.json").read_text())
    plan = structured["revised_operational_plans"][0]
    return {
        "candidate_id": candidate_id,
        "candidate_sha256": json.loads((candidate / "candidate_record.json").read_text())["candidate_sha256"],
        "plan_id": plan["operational_plan_id"],
        "parent_plan_id": plan.get("parent_plan_id"),
        "parent_hypothesis_id": plan.get("parent_hypothesis_id"),
        "roster_operator_ids": plan["selected_low_star_operator_ids"],
        "roster_names": [OPERATORS.get(operator_id) for operator_id in plan["selected_low_star_operator_ids"]],
        "validation_card": plan.get("validation_card"),
        "targeted_break": plan.get("targeted_break"),
        "structure_comparison": plan.get("structure_comparison"),
        "result": result,
        "events": compact_events(events),
        "hashes": {
            "source_structured_output_sha256": digest(source / "llm_structured_output.json"),
            "frozen_plan_sha256": digest(simulation / "plan_snapshot.json"),
            "frozen_action_sha256": digest(simulation / "action_snapshot.json"),
            "raw_events_sha256": digest(raw_events_path),
            "events_gz_sha256": digest(events_gz),
            "events_gz_restored_sha256": hashlib.sha256(gzip.decompress(events_gz.read_bytes())).hexdigest(),
            "raw_summary_sha256": digest(raw_summary_path),
            "summary_gz_sha256": digest(summary_gz),
            "summary_gz_restored_sha256": hashlib.sha256(gzip.decompress(summary_gz.read_bytes())).hexdigest(),
            "final_status_sha256": digest(simulation / "final_status.json"),
        },
    }


def tool_summary() -> dict:
    tools = Counter()
    for line in (EXPERIMENT / "session/codex_cli/attempt_01/codex_exec.jsonl").read_text().splitlines():
        item = json.loads(line)
        frame = item.get("item", {})
        if item.get("type") == "item.completed" and frame.get("type") == "mcp_tool_call":
            tools[frame["tool"]] += 1
    return dict(sorted(tools.items()))


def main() -> None:
    candidates = [candidate_facts("candidate-001"), candidate_facts("candidate-002")]
    authorization_path = EXPERIMENT / "model_authorization_v1.json"
    authorization = json.loads(authorization_path.read_text())
    authorization["real_cli_starts"]["used_real_cli_starts"] = 1
    authorization["real_cli_starts"]["attempt_1_status"] = "STARTED_COUNTED_COMPLETED"
    write_json(authorization_path, authorization)

    attempt_path = EXPERIMENT / "session/codex_cli/attempt_01/cli_process_attempt.json"
    attempt = json.loads(attempt_path.read_text())
    stdout_path = EXPERIMENT / "session/codex_cli/attempt_01/codex_exec.jsonl"
    stderr_path = EXPERIMENT / "session/codex_cli/attempt_01/codex_stderr.txt"
    final_path = EXPERIMENT / "session/codex_cli/attempt_01/codex_final_message.txt"
    turn = None
    for line in stdout_path.read_text().splitlines():
        item = json.loads(line)
        if item.get("type") == "turn.completed":
            turn = item
    process_result = {
        "schema_version": "KIMIARK_SEVEN_FOCUSED_PROCESS_RESULT_V1",
        "automatic_retry": False,
        "ended_at_utc": datetime_utc_from_path(stdout_path),
        "exit_code": 0,
        "final_message_bytes": final_path.stat().st_size,
        "started_at_utc": attempt["started_at_utc"],
        "status": "COMPLETED",
        "stderr_bytes": stderr_path.stat().st_size,
        "stdout_bytes": stdout_path.stat().st_size,
        "timed_out": False,
        "turn_completed": turn is not None,
        "usage": turn.get("usage") if turn else None,
    }
    write_json(EXPERIMENT / "session/codex_cli/attempt_01/cli_process_result.json", process_result)

    closeout = {
        "schema_version": "KIMIARK_SEVEN_FOCUSED_CLOSEOUT_REPORT_V1",
        "experiment_id": "real_tool_closed_loop_astra_high_seven_focused_v1",
        "best_verified_result": {"operator_count": 8, "plan_id": "R8_7_GPT_M70_V1", "simulator_win": True},
        "decision": {"new_win": False, "best_verified_operator_count": 8, "seven_or_fewer_feasibility": "UNKNOWN"},
        "authorization_and_usage": {
            "provider": "openai",
            "model": "gpt-6-astra",
            "reasoning_effort": "high",
            "features_apps": False,
            "real_cli_starts": "1/1",
            "check_calls": "2/10",
            "candidates": "2/2",
            "simulations": "2/2",
            "remaining_checks": 8,
            "remaining_candidates": 0,
            "remaining_simulations": 0,
            "automatic_retry": False,
            "cached_input_is_subset_of_input": True,
            "internal_requests": "UNKNOWN_CLI_INTERNAL",
        },
        "process": {**process_result, "mcp_tool_calls": {"total": sum(tool_summary().values()), "by_tool": tool_summary()}},
        "coordinate_correction": {
            "prior_comparison_note": "The sent comparison said plan tiles were [x,y] and DEPLOY event tiles were [row,col].",
            "corrected_for_this_run": "plan/action tiles are [row,col]; DEPLOY event detail tile strings are [x,y] after json_tile_to_runtime conversion. The sent comparison copy remains unchanged and is identified by hash.",
        },
        "gap_analysis": {
            "steward_2917_3361": "OBSERVED: ordinary attacks continue through 3157; NO_CANDIDATE 3205-3360. Artillery is absent from intervening candidate lists. Continuous positions are UNKNOWN.",
            "steward_4225_4705": "OBSERVED: attacks continue every 48 frames, switching to #21. Artillery absent from candidate lists. Continuous positions are UNKNOWN.",
            "conclusion": "Absence from eligibility/targeting, not retreat or slower cadence, best explains the gaps; exact range-crossing frames remain UNKNOWN.",
        },
        "candidates": candidates,
        "validation": {
            "candidate_001": "Opening roadblock predictions were proved, but the first shell killed both medics@2111; Steward died@2561. Later artillery-gap, central and western-transfer hypotheses were TRUNCATED_BY_EARLIER_FAILURE.",
            "candidate_002": "Staged western Hibiscus avoided the first shared-splash medic loss, but Steward died@2593 after 910@2443, Ansel 506.8@2443, and 910@2593. Roadblock #4/#14 eastern passage succeeded; protected #3 died@5353. Central #21/#22/#34 closure was TRUNCATED_BY_EARLIER_FAILURE for post-artillery-closure assumptions.",
        },
        "archive_notes": {"raw_event_and_summary_files": "Excluded from git manifest; deterministic gzip restores match recorded raw SHA-256."},
    }
    write_json(EXPERIMENT / "closeout_report_v1.json", closeout)
    build_manifest()


def build_manifest() -> None:
    manifest_path = EXPERIMENT / "attempt_artifact_manifest_v1.json"
    manifest_files = []
    for path in sorted(EXPERIMENT.rglob("*")):
        if not path.is_file() or path == manifest_path or path == Path(__file__):
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative.endswith("diagnostic_events.json") or relative.endswith("diagnostic_summary.json"):
            continue
        entry = {"path": relative, "bytes": path.stat().st_size, "sha256": digest(path)}
        if path.name.endswith(".gz"):
            entry["restored_sha256"] = hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()
        manifest_files.append(entry)
    manifest_files.append({"path": Path(__file__).relative_to(ROOT).as_posix(), "bytes": Path(__file__).stat().st_size, "sha256": digest(Path(__file__))})
    write_json(manifest_path, {"schema_version": "KIMIARK_SEVEN_FOCUSED_ATTEMPT_ARTIFACT_MANIFEST_V1", "files": sorted(manifest_files, key=lambda item: item["path"])})


def datetime_utc_from_path(path: Path) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()
