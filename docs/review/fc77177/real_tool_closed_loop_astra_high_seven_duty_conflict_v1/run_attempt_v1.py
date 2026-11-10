#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import http.client
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_duty_conflict_v1"
ATTEMPT_DIR = EXPERIMENT / "session/codex_cli/attempt_01"
PROMPT_PATH = EXPERIMENT / "session/codex_cli/astra_prompt_v1.txt"
CONFIG_PATH = EXPERIMENT / "session_config_v1.json"
AUTHORIZATION_PATH = EXPERIMENT / "model_authorization_v1.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_bytes(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def proxy_prestart() -> dict[str, Any]:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not proxy:
        raise RuntimeError("HTTPS_PROXY is required before real Codex start")
    parsed = urlparse(proxy)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=8)
    started = time.monotonic()
    connection.request("CONNECT", "chatgpt.com:443")
    response = connection.getresponse()
    elapsed = round((time.monotonic() - started) * 1000, 3)
    if response.status != 200:
        raise RuntimeError(f"proxy CONNECT returned HTTP {response.status}")
    record = {
        "connect_target": "chatgpt.com:443",
        "counts_as_cli_start": False,
        "elapsed_ms": elapsed,
        "generation_request_used": False,
        "proxy": proxy,
        "schema_version": "KIMIARK_SEVEN_DUTY_CONFLICT_PROXY_PRESTART_V1",
        "status": response.status,
    }
    write_json(ATTEMPT_DIR / "proxy_prestart.json", record)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_once(argv: list[str], stdout_path: Path, stderr_path: Path, stdin_path: Path, timeout_seconds: int) -> dict[str, Any]:
    started_text = utc_now()
    turn_completed = False
    with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file, stdin_path.open("rb") as stdin_file:
        process = subprocess.Popen(argv, cwd=ROOT, stdin=stdin_file, stdout=stdout_file, stderr=stderr_file)
        timed_out = False
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            exit_code = process.wait()
        stdout_file.flush()
        stderr_file.flush()
    for line in stdout_path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            turn_completed = True
            break
    status = "TIMED_OUT" if timed_out else "FAILED" if exit_code != 0 else "COMPLETED" if turn_completed else "COMPLETED_WITHOUT_TURN_COMPLETION"
    return {
        "automatic_retry": False,
        "ended_at_utc": utc_now(),
        "exit_code": exit_code,
        "final_message_bytes": file_bytes(stdout_path.parent / "codex_final_message.txt"),
        "schema_version": "KIMIARK_SEVEN_DUTY_CONFLICT_PROCESS_RESULT_V1",
        "started_at_utc": started_text,
        "status": status,
        "stderr_bytes": file_bytes(stderr_path),
        "stdout_bytes": file_bytes(stdout_path),
        "timed_out": timed_out,
        "turn_completed": turn_completed,
    }


def main() -> None:
    ATTEMPT_DIR.mkdir(parents=True, exist_ok=True)
    result_path = ATTEMPT_DIR / "cli_process_result.json"
    with (ATTEMPT_DIR / "runner.lock").open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(2)
        if result_path.exists():
            raise SystemExit(3)
        authorization = load_json(AUTHORIZATION_PATH)
        starts = authorization["real_cli_starts"]
        if starts.get("used_real_cli_starts") != 0 or starts.get("authorized_real_cli_starts") != 1:
            raise SystemExit(4)
        proxy_prestart()
        stdout_path = ATTEMPT_DIR / "codex_exec.jsonl"
        stderr_path = ATTEMPT_DIR / "codex_stderr.txt"
        final_path = ATTEMPT_DIR / "codex_final_message.txt"
        argv = [
            "timeout", "3600s", "codex", "exec", "--json", "--sandbox", "read-only",
            "--cd", str(ROOT),
            "-c", 'model_provider="openai"',
            "-c", "features.apps=false",
            "-c", f'mcp_servers.kimiark.command="{ROOT / ".venv/bin/python"}"',
            "-c", f'mcp_servers.kimiark.args=["{ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"}","{CONFIG_PATH}"]',
            "-c", "mcp_servers.kimiark.required=true",
            "-c", 'mcp_servers.kimiark.default_tools_approval_mode="approve"',
            "-c", 'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]',
            "-m", "gpt-6-astra",
            "-c", 'model_reasoning_effort="high"',
            "-o", str(final_path),
            "-",
        ]
        write_json(ATTEMPT_DIR / "codex_command.json", {
            "argv": argv,
            "prompt_path": PROMPT_PATH.relative_to(ROOT).as_posix(),
            "prompt_sha256": sha256_path(PROMPT_PATH),
            "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_CODEX_COMMAND_V2",
            "shell": False,
            "stdin": "prompt_file_content",
            "timeout_seconds": 3600,
        })
        write_json(ATTEMPT_DIR / "cli_process_attempt.json", {
            "authorized_real_cli_starts": 1,
            "automatic_retry": False,
            "prompt_sha256": sha256_path(PROMPT_PATH),
            "started_at_utc": utc_now(),
        })
        (ATTEMPT_DIR / "runner.pid").write_text(f"{os.getpid()}\n")
        starts.update({"attempt_1_status": "STARTED_COUNTED", "used_real_cli_starts": 1})
        write_json(AUTHORIZATION_PATH, authorization)
        result = run_once(argv, stdout_path, stderr_path, PROMPT_PATH, 3600)
        authorization = load_json(AUTHORIZATION_PATH)
        authorization["real_cli_starts"]["attempt_1_status"] = f"STARTED_COUNTED_{result['status']}"
        write_json(AUTHORIZATION_PATH, authorization)
        write_json(result_path, result)
        write_json(ATTEMPT_DIR / "runner_state.json", {
            "process_result": result,
            "schema_version": "KIMIARK_SEVEN_DUTY_CONFLICT_RUNNER_STATE_V1",
            "status": "FINISHED",
        })


if __name__ == "__main__":
    main()
