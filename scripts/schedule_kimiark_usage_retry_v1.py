#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "output/kimiark_usage_retry_scheduler"
STATE_PATH = STATE_DIR / "state.json"
LOCK_PATH = STATE_DIR / "scheduler.lock"
PID_PATH = STATE_DIR / "scheduler.pid"
LOG_PATH = STATE_DIR / "scheduler.log"
FROZEN_PROMPT_SHA256 = "57b4a4c465355657188546ba15eab787e4ac6c094536eca69609814c144d40f5"
PRIOR_CLI_STARTS = 52
MAX_NEW_CLI_STARTS = 10
NEXT_ATTEMPT = 4
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
USAGE_LIMIT_MARKERS = (
    "You’ve hit your usage limit",
    "You've hit your usage limit",
)


def utc_now() -> str:
    return dt.datetime.now(ZoneInfo("UTC")).isoformat()


def local_now() -> dt.datetime:
    return dt.datetime.now(LOCAL_TZ)


def iso_local(value: dt.datetime) -> str:
    return value.astimezone(LOCAL_TZ).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_state(state: dict[str, Any]) -> None:
    temporary = STATE_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, STATE_PATH)


def log_event(message: str) -> None:
    stamp = iso_local(local_now())
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {message}\n")


def load_state() -> dict[str, Any]:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def parse_explicit_reset_time(text: str) -> dt.datetime | None:
    match = re.search(
        r"try again at\s+(?:(\d{1,2})(?:st|nd|rd|th)\s+)?([A-Z][a-z]+)(?:\s+(\d{1,2})(?:st|nd|rd|th))?,\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    day = int(match.group(1) or match.group(3))
    month_name = match.group(2)
    year = int(match.group(4))
    hour = int(match.group(5))
    minute = int(match.group(6))
    meridiem = match.group(7).upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    if meridiem == "AM" and hour == 12:
        hour = 0
    month_number = dt.datetime.strptime(month_name, "%B").month
    return dt.datetime(year, month_number, day, hour, minute, tzinfo=LOCAL_TZ)


def find_usage_limit_message(attempt_dir: Path) -> tuple[bool, str | None]:
    stdout_path = attempt_dir / "codex_exec.jsonl"
    if not stdout_path.is_file():
        return False, None
    matches: list[str] = []
    for line in stdout_path.read_text(encoding="utf-8", errors="replace").splitlines():
        for marker in USAGE_LIMIT_MARKERS:
            if marker in line:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    event = {"raw": line}
                matches.append(json.dumps(event, ensure_ascii=False))
                break
    if not matches:
        return False, None
    return True, matches[-1]


def run_attempt(state: dict[str, Any], attempt: int, prior_cli_starts: int) -> dict[str, Any]:
    attempt_id = f"attempt_{attempt:02d}"
    output_dir = ROOT / f"output/r8_1_r8_7_batch_v1/main_08-07/m25_tactical_revision_v1/{attempt_id}_cli"
    diagnostic_dir = ROOT / f"output/r8_1_r8_7_batch_v1/main_08-07/m25_tactical_revision_v1/{attempt_id}_diagnostic"
    command = [
        "/home/bigdata/Desktop/cybergym-main/.venv/bin/python",
        "scripts/run_gpt_tactical_stage_session_v1.py", "session",
        "--stage-id", "main_08-07",
        "--facts-dir", "output/r8_1_r8_7_batch_v1/main_08-07/m25_runner_input_v1/attempt_01_source",
        "--output-dir", str(output_dir.relative_to(ROOT)),
        "--diagnostic-output-dir", str(diagnostic_dir.relative_to(ROOT)),
        "--plan-id", "R8_7_GPT_M25_V2",
        "--plan-label", "R8-7-M25-V2",
        "--plan-id-prefix", "R8_7_GPT",
        "--cli-attempt", str(attempt),
        "--prior-cli-starts", str(prior_cli_starts),
        "--extra-config", "features.apps=false",
        "--revision-source", "output/r8_1_r8_7_batch_v1/main_08-07/m25_tactical_revision_v1/attempt_02_compact_revision_source",
        "--diagnostic-summary", "output/r8_1_r8_7_batch_v1/main_08-07/m25_tactical_revision_v1/attempt_01_diagnostic/diagnostic_summary.json",
        "--tactical-feedback", "docs/review/fc77177/m25_r8_7_v14_tactical_feedback.json",
    ]
    environment = dict(os.environ)
    environment.update({
        "HTTP_PROXY": "http://127.0.0.1:7890",
        "HTTPS_PROXY": "http://127.0.0.1:7890",
        "ALL_PROXY": "socks5://127.0.0.1:7890",
        "NO_PROXY": "localhost,127.0.0.1,::1",
        "http_proxy": "http://127.0.0.1:7890",
        "https_proxy": "http://127.0.0.1:7890",
        "all_proxy": "socks5://127.0.0.1:7890",
        "no_proxy": "localhost,127.0.0.1,::1",
        "CODEX_HOME": str(ROOT / ".runtime/codex-home"),
        "CODEX_REASONING_EFFORT": "high",
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT / 'scripts'}",
    })
    record: dict[str, Any] = {
        "attempt": attempt,
        "started_at_local": iso_local(local_now()),
        "started_at_utc": utc_now(),
        "output_dir": str(output_dir.relative_to(ROOT)),
        "diagnostic_dir": str(diagnostic_dir.relative_to(ROOT)),
        "command": command,
        "automatic_retry": False,
    }
    state["current_attempt"] = record
    write_state(state)
    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    record["finished_at_local"] = iso_local(local_now())
    record["finished_at_utc"] = utc_now()
    record["exit_code"] = completed.returncode
    prompt_path = output_dir / "codex_prompt.txt"
    record["prompt_sha256"] = sha256(prompt_path) if prompt_path.is_file() else None
    record["prompt_sha256_matches_frozen"] = record["prompt_sha256"] == FROZEN_PROMPT_SHA256
    final_path = output_dir / "final_status.json"
    record["final_status"] = json.loads(final_path.read_text(encoding="utf-8")) if final_path.is_file() else None
    usage_limited, usage_event = find_usage_limit_message(output_dir)
    record["usage_limited"] = usage_limited
    record["usage_limit_event"] = usage_event
    return record


def classify_result(attempt: int, record: dict[str, Any]) -> tuple[str, dt.datetime | None, dict[str, Any]]:
    output_dir = ROOT / record["output_dir"]
    next_attempt = attempt + 1
    diagnostic_dir = ROOT / record["diagnostic_dir"]
    result: dict[str, Any] = {"classification": record.get("final_status", {}).get("status", "UNKNOWN")}
    if record.get("usage_limited"):
        failure_time = local_now()
        wait_until = failure_time + dt.timedelta(hours=5)
        explicit = parse_explicit_reset_time(record.get("usage_limit_event") or "")
        if explicit is not None and explicit > wait_until:
            wait_until = explicit
        result["reason"] = "USAGE_LIMIT_FIVE_HOUR_WAIT"
        return "WAITING", wait_until, result
    if record.get("exit_code") != 0:
        result["reason"] = "NON_USAGE_CLI_OR_PIPELINE_FAILURE_STOPPED"
        return "STOPPED", None, result
    final_status = record.get("final_status") or {}
    if final_status.get("new_operational_plans") != 1:
        result["reason"] = "NO_OPERATIONAL_PLAN_STOPPED"
        return "STOPPED", None, result
    simulation_gate_path = output_dir / "simulation_gate.json"
    static_path = output_dir / "static_compile_results.json"
    if not simulation_gate_path.is_file():
        if static_path.is_file():
            static = json.loads(static_path.read_text(encoding="utf-8"))
            if static.get("conflicts"):
                result["reason"] = "STATIC_CONFLICT_REVISE_IMMEDIATELY"
                result["static_conflict_summary"] = str(static_path.relative_to(ROOT))
                return "WAITING", local_now() + dt.timedelta(minutes=1), result
        result["reason"] = "PLAN_OBTAINED_BUT_PIPELINE_INCOMPLETE_STOPPED"
        return "STOPPED", None, result
    gate = json.loads(simulation_gate_path.read_text(encoding="utf-8"))
    summary_path = diagnostic_dir / "diagnostic_summary.json"
    if not summary_path.is_file():
        result["reason"] = "SIMULATION_GATE_WITHOUT_SUMMARY_STOPPED"
        return "STOPPED", None, result
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    result_summary = summary.get("result", {})
    result["win"] = result_summary.get("win")
    result["enemies_leaked"] = result_summary.get("enemies_leaked")
    result["protected_target_deaths"] = len(summary.get("protected_target_deaths") or [])
    result["protected_targets_reached"] = len(summary.get("protected_target_reached_events") or [])
    if gate.get("simulator_win") and result_summary.get("enemies_leaked") == 0 and not summary.get("protected_target_deaths") and len(summary.get("protected_target_reached_events") or []) == 2:
        result["reason"] = "PERFECT_CURRENT_MODEL_SIMULATOR_WIN"
        return "COMPLETE", None, result
    result["reason"] = "SIMULATED_LOSS_REVISE_IMMEDIATELY"
    result["diagnostic_summary"] = str(summary_path.relative_to(ROOT))
    return "WAITING", local_now() + dt.timedelta(minutes=1), result


def scheduler_loop() -> None:
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_handle.seek(0)
        lock_handle.truncate()
        lock_handle.write(f"{os.getpid()} {utc_now()}\n")
        lock_handle.flush()
        PID_PATH.write_text(f"{os.getpid()}\n", encoding="utf-8")
        state = load_state()
        state["status"] = "WAITING"
        state["scheduler_pid"] = os.getpid()
        state["last_wakeup_at_local"] = iso_local(local_now())
        write_state(state)
        log_event(f"scheduler started pid={os.getpid()} next_run={state['next_run_local']}")
        stopping = False

        def request_stop(signum: int, frame: Any) -> None:
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)

        while not stopping:
            state = load_state()
            if state.get("status") == "COMPLETE":
                break
            if state.get("status") == "STOPPED":
                break
            if state.get("starts_used", 0) >= MAX_NEW_CLI_STARTS:
                state["status"] = "STOPPED"
                state["stop_reason"] = "BUDGET_EXHAUSTED"
                write_state(state)
                break
            next_run = dt.datetime.fromisoformat(state["next_run_local"])
            wait_seconds = (next_run - local_now()).total_seconds()
            if wait_seconds > 0:
                state["status"] = "WAITING"
                state["seconds_until_next_run"] = round(wait_seconds, 3)
                write_state(state)
                time.sleep(min(wait_seconds, 30))
                continue
            attempt = int(state["next_attempt"])
            prior_cli_starts = int(state["prior_cli_starts"])
            if attempt > NEXT_ATTEMPT + MAX_NEW_CLI_STARTS - 1:
                state["status"] = "STOPPED"
                state["stop_reason"] = "BUDGET_EXHAUSTED"
                write_state(state)
                break
            state["status"] = "RUNNING"
            state["starts_used"] = int(state.get("starts_used", 0)) + 1
            state["remaining_budget_after_started_attempt"] = MAX_NEW_CLI_STARTS - int(state["starts_used"])
            write_state(state)
            log_event(f"attempt={attempt} start prior_cli={prior_cli_starts}")
            try:
                record = run_attempt(state, attempt, prior_cli_starts)
            except Exception as exc:
                record = {
                    "attempt": attempt,
                    "exception": f"{type(exc).__name__}: {exc}",
                    "finished_at_local": iso_local(local_now()),
                    "automatic_retry": False,
                }
            state = load_state()
            attempts = list(state.get("attempts", []))
            attempts.append(record)
            state["attempts"] = attempts
            state["current_attempt"] = None
            state["prior_cli_starts"] = prior_cli_starts + 1
            state["cumulative_cli_process_starts"] = prior_cli_starts + 1
            state["next_attempt"] = attempt + 1
            classification, wait_until, details = classify_result(attempt, record)
            state["status"] = classification
            state["last_result"] = {"attempt": attempt, **details}
            state["seconds_until_next_run"] = None
            if wait_until is not None:
                state["next_run_local"] = iso_local(wait_until)
            state["last_updated_local"] = iso_local(local_now())
            state["last_updated_utc"] = utc_now()
            write_state(state)
            log_event(f"attempt={attempt} finished status={classification} details={json.dumps(details,ensure_ascii=False,sort_keys=True)} next_run={state.get('next_run_local')}")

        state = load_state()
        state["scheduler_stopped_at_local"] = iso_local(local_now())
        state["scheduler_stopped_at_utc"] = utc_now()
        write_state(state)


def initialize_state(next_run: dt.datetime) -> None:
    state = {
        "schema_version": "KIMIARK_USAGE_RETRY_SCHEDULER_STATE_V1",
        "created_at_local": iso_local(local_now()),
        "created_at_utc": utc_now(),
        "status": "WAITING",
        "next_attempt": NEXT_ATTEMPT,
        "next_run_local": iso_local(next_run),
        "prior_cli_starts": PRIOR_CLI_STARTS,
        "cumulative_cli_process_starts": PRIOR_CLI_STARTS,
        "max_new_cli_starts": MAX_NEW_CLI_STARTS,
        "starts_used": 0,
        "remaining_budget_before_next_attempt": MAX_NEW_CLI_STARTS,
        "frozen_prompt_sha256": FROZEN_PROMPT_SHA256,
        "retry_policy": {
            "usage_limit_wait_hours": 5,
            "honor_later_explicit_reset_time": True,
            "network_auth_protocol_failure": "STOP_NO_WAIT",
            "tactical_or_static_failure": "REVISE_IMMEDIATELY",
            "new_attempt_directory_required": True,
            "automatic_retry": False,
        },
        "attempts": [],
    }
    write_state(state)


def lock_is_held() -> bool:
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        return False


def reconcile(stop_reason: str | None) -> dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.is_file():
        return {"status": "NOT_INITIALIZED"}
    state = load_state()
    executor_alive = lock_is_held()
    if executor_alive:
        state["executor_alive"] = True
        state["last_checked_local"] = iso_local(local_now())
        state["last_checked_utc"] = utc_now()
        write_state(state)
        return {"status": state.get("status"), "executor_alive": True}
    if state.get("status") not in {"COMPLETE", "STOPPED"}:
        state["status"] = "INTERRUPTED" if not stop_reason else "STOPPED"
        state["stop_reason"] = stop_reason or "EXECUTOR_NOT_RUNNING"
        state["interrupted_at_local"] = iso_local(local_now())
        state["interrupted_at_utc"] = utc_now()
    state["executor_alive"] = False
    state["last_checked_local"] = iso_local(local_now())
    state["last_checked_utc"] = utc_now()
    write_state(state)
    return {
        "status": state.get("status"),
        "stop_reason": state.get("stop_reason"),
        "executor_alive": False,
        "state_file": str(STATE_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "status", "stop", "reconcile"])
    parser.add_argument("--stop-reason")
    parser.add_argument("--wait-hours", type=float, default=5.0)
    arguments = parser.parse_args()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if arguments.command == "status":
        if not STATE_PATH.is_file():
            print(json.dumps({"status": "NOT_INITIALIZED"}, sort_keys=True))
            return
        print(json.dumps(load_state(), ensure_ascii=False, indent=2, sort_keys=True))
        return
    if arguments.command == "reconcile":
        print(json.dumps(reconcile(arguments.stop_reason), ensure_ascii=False, indent=2, sort_keys=True))
        return
    if arguments.command == "stop":
        if not PID_PATH.is_file():
            print("scheduler is not running")
            return
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"stop signal sent to scheduler pid {pid}")
        return

    if PID_PATH.exists() and PID_PATH.read_text().strip().isdigit():
        pid = int(PID_PATH.read_text().strip())
        try:
            os.kill(pid, 0)
            raise RuntimeError(f"scheduler already running with pid {pid}")
        except ProcessLookupError:
            PID_PATH.unlink()
    next_run = local_now() + dt.timedelta(hours=arguments.wait_hours)
    initialize_state(next_run)
    log_handle = LOG_PATH.open("ab", buffering=0)
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "daemon"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(json.dumps({
        "status": "SCHEDULED",
        "pid_file": str(PID_PATH),
        "state_file": str(STATE_PATH),
        "log_file": str(LOG_PATH),
        "next_attempt": NEXT_ATTEMPT,
        "next_run_local": iso_local(next_run),
        "frozen_prompt_sha256": FROZEN_PROMPT_SHA256,
        "prior_cli_starts": PRIOR_CLI_STARTS,
        "new_cli_budget": MAX_NEW_CLI_STARTS,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "daemon":
        scheduler_loop()
    else:
        main()
