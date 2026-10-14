from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft7Validator

import run_r8_1_gpt_tactical_revision_v1 as prior_runner
from compile_r8_1_lowstar_c2_plan_v1 import compile_plan
from run_r8_1_low_star_full_tactical_closure_v1 import output_schema
from run_r8_1_lowstar_c2_full_diagnostic_v1 import run_full_diagnostic
from run_r8_1_lowstar_c3_failure_revision_v1 import INITIAL_BODY_LIMIT


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/r8_1_gpt_c4_codex_cli_v3"
SAVED_CLI_INPUT_DIR = ROOT / "output/r8_1_gpt_c4_codex_cli_v1"
OUT = ROOT / "output/r8_1_gpt_c4_codex_cli_v1"
DIAGNOSTIC_OUT = ROOT / "output/r8_1_gpt_c4_codex_cli_diagnostic_v1"
PLAN_ID = "R8_1_LOWSTAR_PLAN_C4"
PLAN_LABEL = "C4"
PLAN_PREFIX = "R8_1_LOWSTAR_PLAN_C4"
MODEL = "gpt-6.1-sol"
REASONING_EFFORT = os.environ.get("CODEX_REASONING_EFFORT", "medium")
CLI_TIMEOUT_SECONDS = 3600
PRIOR_CLI_STARTS = 0
CLI_ATTEMPT_NUMBER = 1
EXTRA_CONFIG_VALUES: list[str] = []
REUSE_SAVED_CLI_INPUT = False
FEEDBACK_SUMMARY_PATH = ROOT / "output/r8_1_gpt_c3_full_diagnostic_v1/diagnostic_summary.json"
FEEDBACK_EVENTS_PATH = ROOT / "output/r8_1_gpt_c3_full_diagnostic_v1/diagnostic_events.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, exclusive: bool = False) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    else:
        path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": os.path.relpath(path, ROOT), "sha256": sha256(path)}


def configure_run(
    output_dir: str,
    diagnostic_output_dir: str,
    *,
    cli_attempt: int,
    prior_cli_starts: int,
    extra_config_values: list[str] | None = None,
    reuse_saved_cli_input: bool = False,
    source_dir: str,
    plan_id: str,
    plan_label: str,
    plan_id_prefix: str,
    revision_source_plan_id: str,
    revision_source_path: str,
    feedback_summary: str,
    feedback_events: str,
) -> None:
    global OUT, DIAGNOSTIC_OUT, CLI_ATTEMPT_NUMBER, PRIOR_CLI_STARTS, REUSE_SAVED_CLI_INPUT, SOURCE
    global EXTRA_CONFIG_VALUES
    global PLAN_ID, PLAN_LABEL, PLAN_PREFIX, FEEDBACK_SUMMARY_PATH, FEEDBACK_EVENTS_PATH
    OUT = ROOT / output_dir
    DIAGNOSTIC_OUT = ROOT / diagnostic_output_dir
    CLI_ATTEMPT_NUMBER = cli_attempt
    EXTRA_CONFIG_VALUES = list(extra_config_values or [])
    PRIOR_CLI_STARTS = prior_cli_starts
    REUSE_SAVED_CLI_INPUT = reuse_saved_cli_input
    SOURCE = ROOT / source_dir
    PLAN_ID = plan_id
    PLAN_LABEL = plan_label
    PLAN_PREFIX = plan_id_prefix
    FEEDBACK_SUMMARY_PATH = ROOT / feedback_summary
    FEEDBACK_EVENTS_PATH = ROOT / feedback_events


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_run_lock() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "run.lock"
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError("another Codex CLI tactical session is running") from exc
    handle.seek(0)
    if handle.read():
        if (OUT / "cli_process_attempt.json").is_file():
            handle.close()
            raise RuntimeError("Codex CLI tactical session lock already consumed")
        handle.seek(0)
        handle.truncate()
    handle.seek(0)
    handle.write(json.dumps({
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_RUN_LOCK",
        "locked_at": utc_now(),
        "policy": "one CLI process; no script retry, resume or replacement session",
    }, sort_keys=True) + "\n")
    handle.flush()


def claim_cli_start(command: list[str]) -> dict[str, Any]:
    environment = codex_environment()
    record = {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_PROCESS_ATTEMPT",
        "attempt": CLI_ATTEMPT_NUMBER,
        "status": "STARTED",
        "started_at": utc_now(),
        "automatic_retry": False,
        "automatic_resume": False,
        "timeout_seconds": CLI_TIMEOUT_SECONDS,
        "command": command,
        "process_environment_proxy_flags": {
            "HTTP_PROXY": environment.get("HTTP_PROXY"),
            "HTTPS_PROXY": environment.get("HTTPS_PROXY"),
            "ALL_PROXY": environment.get("ALL_PROXY"),
            "NO_PROXY": environment.get("NO_PROXY"),
            "http_proxy": environment.get("http_proxy"),
            "https_proxy": environment.get("https_proxy"),
            "all_proxy": environment.get("all_proxy"),
            "no_proxy": environment.get("no_proxy"),
        },
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
    }
    write_json(OUT / "cli_process_attempt.json", record, exclusive=True)
    return record


def build_command(last_message_path: Path) -> list[str]:
    command = [
        "codex", "exec", "--json", "--sandbox", "read-only", "--cd", str(ROOT),
        "-c", 'model_provider="openai"', "-m", MODEL,
        "-c", f'model_reasoning_effort="{REASONING_EFFORT}"',
        "-o", str(last_message_path), "-",
    ]
    for value in EXTRA_CONFIG_VALUES:
        command[command.index("-m") - 2:command.index("-m") - 2] = ["-c", value]
    return command


def codex_environment() -> dict[str, str]:
    environment = dict(os.environ)
    expected = {
        "HTTP_PROXY": "http://127.0.0.1:7890",
        "HTTPS_PROXY": "http://127.0.0.1:7890",
        "ALL_PROXY": "socks5://127.0.0.1:7890",
        "NO_PROXY": "localhost,127.0.0.1,::1",
    }
    for upper, value in expected.items():
        lower = upper.lower()
        inherited = environment.get(upper)
        if inherited is not None and not inherited:
            raise RuntimeError(f"empty proxy environment variable is forbidden: {upper}")
        inherited_lower = environment.get(lower)
        if inherited_lower is not None and not inherited_lower:
            raise RuntimeError(f"empty proxy environment variable is forbidden: {lower}")
        if inherited is not None and inherited != value:
            raise RuntimeError(f"inherited {upper} conflicts with required local proxy: {inherited!r}")
        if inherited_lower is not None and inherited_lower != value:
            raise RuntimeError(f"inherited {lower} conflicts with required local proxy: {inherited_lower!r}")
        environment[upper] = value
        environment[lower] = value
    return environment


def build_prompt(evidence: dict[str, Any]) -> str:
    evidence_json = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
    result = evidence["prior_diagnostic_feedback"]["result"]
    first = evidence["prior_diagnostic_feedback"]["first_failure"]["first_leak"]
    spawn = next((row for row in evidence["prior_diagnostic_feedback"]["first_enemy_events"] if row["event_type"] == "SPAWN"), first)
    route = next((row["route"] for row in evidence["prior_diagnostic_feedback"]["route_summaries"] if first["frame"] in row["leaks"]), "UNKNOWN")
    return f"""You are {MODEL} via the local Codex CLI, the tactical decision maker for Arknights main_08-01 / R8-1.
Create exactly one compact full-stage OperationalPlan {PLAN_LABEL}. The final assistant message must be exactly one JSON object matching the supplied output schema; no markdown wrapper or commentary.
Include `provenance.revision_source` with `operational_plan_id`, `path`, and `relationship` for the prior plan.

You may use read-only shell commands to inspect the supplied evidence or `scripts/kimi_readonly_tools.py`. Do not create, modify or delete files. Do not run a stage simulation. Do not invoke other AI providers. Do not print credentials.

Only operators in `normal_low_star_catalog` are legal. Require `identity.rarity` 1-3 and `qualification.normal_mode == true`; exclude mode-specific reserve units. Every DEPLOY needs integer [row,col] and UP/DOWN/LEFT/RIGHT. WIN is zero leaks, exhausted spawns and no active enemies.

Revise the prior {prior_runner.REVISION_CONFIG['revision_source_plan_id']} conditional-runtime LOSS: {result['enemies_killed']} kills, {result['enemies_leaked']} leaks, {result['operator_deaths']} operator deaths, and remaining life {result['remaining_life']}. The first leak is {route} `{first['source_id']}` (spawn frame {spawn['frame']}, leak frame {first['frame']}). The complete per-route block, kill and leak summary is in `prior_diagnostic_feedback`. Handle every route leak, not only the first. You decide early fire timing, simultaneous blocking ownership, temporary roles, healing, skills, retreats, handovers and economic order. Python/GLM will not choose tactics for you.

Use read-only helper functions when needed to verify ranges, timing or mechanics. Do not invent roadblock navigation, target ordering, refunds, client timing or unsupported effects. Distinguish GameData facts, current-model rules and UNKNOWN. Do not repeat evidence prose. The compact evidence JSON follows:

EVIDENCE_JSON
{evidence_json}
"""


def prepare() -> dict[str, Any]:
    assert_run_lock()
    cumulative_cli_starts = PRIOR_CLI_STARTS + 1
    budget = {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_BUDGET",
        "provider": "codex-cli-openai",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "max_cli_process_starts": 1,
        "cli_process_starts_in_experiment": 0,
        "prior_cli_process_starts": PRIOR_CLI_STARTS,
        "cumulative_cli_process_starts_after_this_attempt": cumulative_cli_starts,
        "max_operational_plans": 1,
        "new_operational_plans": 0,
        "max_stage_simulations": 1,
        "stage_simulations_started": 0,
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        "automatic_retry": False,
        "automatic_resume": False,
    }
    write_json(OUT / "budget_usage.json", budget)

    if REUSE_SAVED_CLI_INPUT:
        evidence_path = SAVED_CLI_INPUT_DIR / "llm_evidence_context.json"
        prompt_path = SAVED_CLI_INPUT_DIR / "codex_prompt.txt"
        (OUT / "llm_evidence_context.json").write_bytes(evidence_path.read_bytes())
        (OUT / "codex_prompt.txt").write_bytes(prompt_path.read_bytes())
        evidence = load(evidence_path)
    else:
        old_evidence = load(SOURCE / "llm_evidence_context.json")
        evidence = copy.deepcopy(old_evidence)
        evidence["milestone"] = f"R8_1_GPT_{PLAN_LABEL}_CODEX_CLI_V1"
        evidence["tactical_provider"] = {
            "provider": "codex-cli", "model": MODEL, "reasoning_effort": REASONING_EFFORT,
            "sandbox": "read-only", "compatibility": "USER_CONFIRMED_CLI_LOGIN",
        }
        evidence["codex_cli_run_policy"] = {
            "process_starts": 1, "automatic_retry": False, "automatic_resume": False,
            "source_modification": "FORBIDDEN", "stage_simulation_by_model": "FORBIDDEN",
            "readonly_query_helpers": True,
        }
        feedback = compact_feedback(FEEDBACK_SUMMARY_PATH, FEEDBACK_EVENTS_PATH)
        evidence["prior_diagnostic_feedback"] = feedback
        evidence["provenance"] = {
            "revision_source": {
                "operational_plan_id": prior_runner.REVISION_CONFIG["revision_source_plan_id"],
                "path": prior_runner.REVISION_CONFIG["revision_source_path"],
                "relationship": "prior_plan_revision_source_not_parent_hypothesis",
            }
        }
        write_json(OUT / "llm_evidence_context.json", evidence)
        prompt_path = None
    schema = output_schema()
    write_json(OUT / "revision_output_schema.json", schema)
    if REUSE_SAVED_CLI_INPUT:
        prompt = (OUT / "codex_prompt.txt").read_text(encoding="utf-8")
    else:
        prompt = build_prompt(evidence)
        (OUT / "codex_prompt.txt").write_text(prompt, encoding="utf-8")
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > INITIAL_BODY_LIMIT:
        raise RuntimeError(f"Codex prompt exceeds {INITIAL_BODY_LIMIT} bytes: {prompt_bytes}")
    source_paths = [
        SOURCE / "llm_evidence_context.json", SOURCE / "codex_final_message.txt",
        ROOT / prior_runner.REVISION_CONFIG["revision_source_path"],
        FEEDBACK_SUMMARY_PATH, FEEDBACK_EVENTS_PATH,
        ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json",
        ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json",
        ROOT / "scripts/kimi_readonly_tools.py", ROOT / "scripts/compile_r8_1_lowstar_c2_plan_v1.py",
        ROOT / "scripts/run_r8_1_lowstar_c2_full_diagnostic_v1.py", Path(__file__),
    ]
    write_json(OUT / "source_manifest.json", {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_SOURCE_MANIFEST",
        "inputs": {path.name: file_record(path) for path in source_paths},
        "prepared_evidence": file_record(OUT / "llm_evidence_context.json"),
        "prompt": file_record(OUT / "codex_prompt.txt"),
        "saved_input_reused": REUSE_SAVED_CLI_INPUT,
        "saved_input_sources": {
            "evidence": file_record(SOURCE / "llm_evidence_context.json"),
            "cli_evidence": file_record(SAVED_CLI_INPUT_DIR / "llm_evidence_context.json"),
            "cli_prompt": file_record(SAVED_CLI_INPUT_DIR / "codex_prompt.txt"),
        } if REUSE_SAVED_CLI_INPUT else None,
    })
    return {"prompt": prompt, "schema": schema, "budget": budget}


def compact_feedback(summary_path: Path, events_path: Path) -> dict[str, Any]:
    summary = load(summary_path)
    events = load(events_path)["events"]
    route_summaries = sorted(
        (
            {
                "route": route,
                "spawn_count": row["spawn_count"],
                "blocks": row["blocks"],
                "kills": row["kills"],
                "leaks": [leak["frame"] for leak in row["leaks"]],
            }
            for route, row in summary["event_summaries"]["route_summaries"].items()
        ),
        key=lambda row: int(row["route"].split("-")[1]),
    )
    block_events = [
        {"frame": row["frame"], "event_type": row["event_type"], "operator_id": row["source_id"], "enemy_id": row["target_id"]}
        for row in events
        if row["event_type"] in {"BLOCK", "UNBLOCK"} and row["frame"] <= 2070
    ]
    return {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_PRIOR_FEEDBACK",
        "result": {key: value for key, value in summary["result"].items() if key != "events"},
        "first_failure": summary["first_failure"],
        "first_enemy_events": [
            {key: row.get(key) for key in ("frame", "event_type", "source_id", "target_id", "details")}
            for row in events
            if row.get("source_id") == summary["first_failure"]["first_leak"]["source_id"]
            and row["event_type"] != "ATTACK_WINDUP"
        ],
        "route_summaries": route_summaries,
        "deployment_events": summary["event_summaries"]["deployment_events"],
        "operator_death_events": summary["event_summaries"]["operator_death_events"],
        "automatic_skill_dp_income_frames": [row["frame"] for row in summary["event_summaries"]["automatic_skill_dp_income"]],
        "block_events": block_events,
        "block_event_selection": "BLOCK/UNBLOCK through frame 2070 only; route summaries retain every route.",
        "boundary": "Conditional current-runtime evidence; not real-game proof or strategic infeasibility.",
        "sources": {
            "summary": os.path.relpath(summary_path, ROOT),
            "events": os.path.relpath(events_path, ROOT),
        },
    }


def extract_events_summary(raw: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    malformed_lines: list[int] = []
    session_ids: list[str] = []
    thread_ids: list[str] = []
    usage_records: list[dict[str, Any]] = []

    def walk(value: Any, path: str, context: dict[str, Any]) -> None:
        if isinstance(value, dict):
            for key in ("session_id", "thread_id", "conversation_id"):
                if isinstance(value.get(key), str) and value[key] and value[key] not in (session_ids if key == "session_id" else thread_ids):
                    if key == "session_id":
                        session_ids.append(value[key])
                    else:
                        thread_ids.append(value[key])
            if isinstance(value.get("usage"), dict):
                usage_records.append({"json_pointer": path, "usage": value["usage"], **context})
            for key, child in value.items():
                walk(child, f"{path}/{key}", context)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}/{index}", context)

    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            malformed_lines.append(line_number)
            events.append({"line": line_number, "malformed": True, "error": str(exc), "text": line[:2000]})
            continue
        context = {"line": line_number, "event_type": event.get("type"), "item_type": event.get("item", {}).get("type") if isinstance(event.get("item"), dict) else None}
        events.append({"line": line_number, **context, "event": event})
        walk(event, f"/events/{line_number - 1}", context)
    return {
        "event_count": len(events),
        "event_type_counts": dict(sorted(Counter(str(row.get("event_type")) for row in events if not row.get("malformed")).items())),
        "session_ids": session_ids,
        "thread_ids": thread_ids,
        "usage_records": usage_records,
        "malformed_lines": malformed_lines,
        "events": events,
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
    }


def run_codex_once(prompt: str, command: list[str], timeout_seconds: int) -> dict[str, Any]:
    claim_cli_start(command)
    budget = load(OUT / "budget_usage.json")
    budget["cli_process_starts_in_experiment"] = 1
    write_json(OUT / "budget_usage.json", budget)
    try:
        result = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            env=codex_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="replace")
        write_json(OUT / "cli_process_result.json", {
            "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_PROCESS_RESULT", "status": "TIMEOUT",
            "exit_code": None, "timed_out": True, "stdout_bytes": len(stdout.encode()),
            "stderr_bytes": len(stderr.encode()), "error": f"CLI exceeded {timeout_seconds} seconds",
        }, exclusive=True)
        (OUT / "codex_exec.jsonl").write_text(stdout, encoding="utf-8")
        (OUT / "codex_stderr.txt").write_text(stderr, encoding="utf-8")
        raise

    (OUT / "codex_exec.jsonl").write_text(result.stdout, encoding="utf-8")
    (OUT / "codex_stderr.txt").write_text(result.stderr, encoding="utf-8")
    process_result = {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_PROCESS_RESULT", "status": "COMPLETED",
        "exit_code": result.returncode, "timed_out": False,
        "stdout_bytes": len(result.stdout.encode()), "stderr_bytes": len(result.stderr.encode()),
    }
    write_json(OUT / "cli_process_result.json", process_result, exclusive=True)
    trajectory = extract_events_summary(result.stdout)
    write_json(OUT / "codex_trajectory_summary.json", trajectory)
    return {"process": process_result, "trajectory": trajectory, "stdout": result.stdout, "stderr": result.stderr}


def run_session(runner: Callable[[str, list[str], int], dict[str, Any]] = run_codex_once) -> dict[str, Any]:
    prepared = prepare()
    evidence_path = OUT / "llm_evidence_context.json"
    schema_path = OUT / "revision_output_schema.json"
    last_message_path = OUT / "codex_final_message.txt"
    command = build_command(last_message_path)
    write_json(OUT / "codex_command.json", {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_COMMAND",
        "argv": command, "stdin": "prompt_file", "shell": False,
        "prompt_sha256": sha256(OUT / "codex_prompt.txt"),
        "timeout_seconds": CLI_TIMEOUT_SECONDS,
    })
    try:
        execution = runner(prepared["prompt"], command, CLI_TIMEOUT_SECONDS)
    except Exception as exc:
        write_json(OUT / "final_status.json", {
            "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_FINAL_STATUS", "status": "CLI_FAILED_NO_RETRY",
            "error": f"{type(exc).__name__}: {exc}", "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise

    if execution["process"]["exit_code"] != 0:
        write_json(OUT / "final_status.json", {
            "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_FINAL_STATUS", "status": "CLI_FAILED_NO_RETRY",
            "failure": execution["process"], "trajectory_summary": {
                "event_count": execution["trajectory"]["event_count"],
                "usage_records": execution["trajectory"]["usage_records"],
            }, "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": PRIOR_CLI_STARTS + 1, "new_operational_plans": 0,
            "stage_simulations_started": 0,
        })
        raise SystemExit("Codex CLI failed without retry")
    if not last_message_path.is_file():
        write_json(OUT / "final_status.json", {
            "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_FINAL_STATUS", "status": "CLI_FAILED_NO_RETRY",
            "error": "Codex CLI did not save --output-last-message", "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise SystemExit("Codex CLI final message missing")

    final_text = last_message_path.read_text(encoding="utf-8").strip()
    (OUT / "codex_final_message.txt").write_text(final_text + "\n", encoding="utf-8")
    try:
        parsed = json.loads(final_text)
    except json.JSONDecodeError as exc:
        write_json(OUT / "llm_plan_validation.json", {
            "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_PLAN_VALIDATION", "status": "FAIL",
            "error": f"final message is not JSON: {exc}",
        })
        write_json(OUT / "final_status.json", {
            "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_FINAL_STATUS", "status": "FAILED_INVALID_PLAN_NO_RETRY",
            "cli_process_starts_in_experiment": 1, "cumulative_cli_process_starts": PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise SystemExit("Codex final message is not JSON")

    prior_runner.configure_revision(
        str(OUT.relative_to(ROOT)), PLAN_LABEL, PLAN_PREFIX,
        prior_runner.REVISION_CONFIG["revision_source_plan_id"],
        prior_runner.REVISION_CONFIG["revision_source_path"],
        prior_runner.REVISION_CONFIG["feedback_summary_path"],
        prior_runner.REVISION_CONFIG["feedback_events_path"],
    )
    evidence = load(evidence_path)
    schema_errors = sorted(
        Draft7Validator(output_schema()).iter_errors(parsed), key=lambda error: list(error.path)
    )
    validation_errors = [
        f"schema: {'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in schema_errors
    ]
    validation_errors.extend(prior_runner.validate_revision_contract(parsed, evidence))
    write_json(OUT / "llm_plan_validation.json", {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_PLAN_VALIDATION",
        "status": "PASS" if not validation_errors else "FAIL", "errors": validation_errors,
    })
    if validation_errors:
        write_json(OUT / "final_status.json", {
            "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_FINAL_STATUS", "status": "FAILED_INVALID_PLAN_NO_RETRY",
            "errors": validation_errors, "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise SystemExit(f"Codex {PLAN_LABEL} failed schema/contract validation: {validation_errors}")

    write_json(OUT / "llm_structured_output.json", parsed)
    write_json(OUT / "final_status.json", {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_FINAL_STATUS",
        "status": f"GPT_{PLAN_LABEL}_RECEIVED_AND_CONTRACT_VALID", "cli_process_starts_in_experiment": 1,
        "cumulative_cli_process_starts": PRIOR_CLI_STARTS + 1,
        "new_operational_plans": 1, "stage_simulations_started": 0,
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        "session_ids": execution["trajectory"]["session_ids"],
        "thread_ids": execution["trajectory"]["thread_ids"],
        "usage_records": execution["trajectory"]["usage_records"],
    })
    return parsed


def static_check() -> dict[str, Any]:
    if load(OUT / "llm_plan_validation.json").get("status") != "PASS":
        raise RuntimeError(f"static check requires locally validated {PLAN_LABEL}")
    return compile_plan(OUT)


def simulate() -> dict[str, Any]:
    static = load(OUT / "static_compile_results.json")
    if static["conflicts"]:
        write_json(OUT / "static_compile_execution_gate.json", {
            "status": "BLOCKED_STATIC_CONFLICT", "conflicts": static["conflicts"],
        })
        raise SystemExit(f"{PLAN_LABEL} static conflicts block diagnostic simulation")
    budget = load(OUT / "budget_usage.json")
    budget["stage_simulations_started"] = 1
    write_json(OUT / "budget_usage.json", budget)
    run_full_diagnostic(source=OUT, out=DIAGNOSTIC_OUT, plan_id=PLAN_ID)
    summary = load(DIAGNOSTIC_OUT / "diagnostic_summary.json")
    write_json(OUT / "simulation_gate.json", {
        "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_SIMULATION_GATE",
            "schema_version": "R8_1_GPT_TACTICAL_CODEX_CLI_V1_SIMULATION_GATE",
            "status": "COMPLETED", "result_classification": summary["classification"],
        "faithful_certificate": summary["faithful_certificate"],
        "robust_roadblock_targeting_claim": summary["robust_roadblock_targeting_claim"],
    })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "session", "static_check", "simulate"])
    parser.add_argument("--output-dir", default="output/r8_1_gpt_c4_codex_cli_v1")
    parser.add_argument("--diagnostic-output-dir", default="output/r8_1_gpt_c4_codex_cli_diagnostic_v1")
    parser.add_argument("--cli-attempt", type=int, default=1)
    parser.add_argument("--prior-cli-starts", type=int, default=0)
    parser.add_argument(
        "--extra-config", action="append", default=[],
        help="additional Codex -c override, recorded with the attempt",
    )
    parser.add_argument("--reuse-saved-input", action="store_true")
    parser.add_argument("--source-dir", default="output/r8_1_gpt_c4_codex_cli_v3")
    parser.add_argument("--plan-id", default="R8_1_LOWSTAR_PLAN_C4")
    parser.add_argument("--plan-label", default="C4")
    parser.add_argument("--plan-id-prefix", default="R8_1_LOWSTAR_PLAN_C4")
    parser.add_argument("--revision-source-plan-id", default="R8_1_LOWSTAR_PLAN_C3")
    parser.add_argument("--revision-source-path", default="output/r8_1_gpt_tactical_revision_v1/recovered_gpt_c3.json")
    parser.add_argument("--feedback-summary", default="output/r8_1_gpt_c3_full_diagnostic_v1/diagnostic_summary.json")
    parser.add_argument("--feedback-events", default="output/r8_1_gpt_c3_full_diagnostic_v1/diagnostic_events.json")
    arguments = parser.parse_args()
    configure_run(
        arguments.output_dir, arguments.diagnostic_output_dir,
        cli_attempt=arguments.cli_attempt, prior_cli_starts=arguments.prior_cli_starts,
        extra_config_values=arguments.extra_config,
        reuse_saved_cli_input=arguments.reuse_saved_input,
        source_dir=arguments.source_dir,
        plan_id=arguments.plan_id,
        plan_label=arguments.plan_label,
        plan_id_prefix=arguments.plan_id_prefix,
        revision_source_plan_id=arguments.revision_source_plan_id,
        revision_source_path=arguments.revision_source_path,
        feedback_summary=arguments.feedback_summary,
        feedback_events=arguments.feedback_events,
    )
    prior_runner.configure_revision(
        arguments.output_dir, arguments.plan_label, arguments.plan_id_prefix,
        arguments.revision_source_plan_id, arguments.revision_source_path,
        arguments.feedback_summary, arguments.feedback_events,
    )
    if arguments.phase == "session":
        run_session()
    elif arguments.phase == "prepare":
        prepared = prepare()
        print(json.dumps({"prompt_bytes": len(prepared["prompt"].encode()), "budget": prepared["budget"]}, sort_keys=True))
    elif arguments.phase == "static_check":
        static_check()
    else:
        simulate()


if __name__ == "__main__":
    main()
