#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_melanha_timing_heal_competition_v1"
ATTEMPT = EXPERIMENT / "session/codex_cli"
PROMPT = ATTEMPT / "sol_prompt_v1.txt"
FINAL = ATTEMPT / "codex_final_message.txt"
AUTHORIZATION = EXPERIMENT / "model_authorization_v1.json"
CONFIG = EXPERIMENT / "session_config_v1.json"
SERVICE = ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"
PYTHON = ROOT / ".venv/bin/python"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mcp_override(name: str, value: str) -> str:
    return f"mcp_servers.kimiark.{name}={json.dumps(value, separators=(',', ':'))}"


def main() -> None:
    if (ATTEMPT / "cli_process_attempt.json").exists():
        raise RuntimeError("R108 real CLI already started")
    prompt = PROMPT.read_text(encoding="utf-8").rstrip("\n") + "\n"
    argv = [
        "codex", "exec", "--json", "--sandbox", "read-only",
        "--cd", str(ROOT),
        "-c", 'model_provider="openai"',
        "-c", mcp_override("command", str(PYTHON)),
        "-c", mcp_override("args", [str(SERVICE), str(CONFIG)]),
        "-c", "mcp_servers.kimiark.enabled=true",
        "-c", "mcp_servers.kimiark.required=true",
        "-c", 'mcp_servers.kimiark.default_tools_approval_mode="approve"',
        "-c", 'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]',
        "-m", "gpt-6.1-sol",
        "-c", 'model_reasoning_effort="high"',
        "-o", str(FINAL),
        "-",
    ]
    command_record = {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_CODEX_COMMAND_V1",
        "argv": argv,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt_bytes": len(prompt.encode()),
        "shell": False,
        "stdin": "prompt_file_content_via_runner",
        "timeout_seconds": 3600,
    }
    (ATTEMPT / "codex_command.json").write_text(json.dumps(command_record, indent=2) + "\n")
    attempt_record = {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_CLI_ATTEMPT_V1",
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "STARTED",
        "automatic_retry": False,
        "automatic_resume": False,
        "command": argv,
        "codex_home": os.environ.get("CODEX_HOME"),
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "prompt_sha256": command_record["prompt_sha256"],
        "timeout_seconds": 3600,
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        "mcp_server": "kimiark",
    }
    (ATTEMPT / "cli_process_attempt.json").write_text(json.dumps(attempt_record, indent=2) + "\n")
    try:
        completed = subprocess.run(argv, input=prompt, cwd=ROOT, text=True, capture_output=True, timeout=3600, check=False)
    except Exception as exc:
        result = {"schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_CLI_RESULT_V1", "status": "FAILED", "error": f"{type(exc).__name__}: {exc}", "automatic_retry": False, "automatic_resume": False}
        (ATTEMPT / "cli_process_result.json").write_text(json.dumps(result, indent=2) + "\n")
        raise
    (ATTEMPT / "codex_exec.jsonl").write_text(completed.stdout)
    (ATTEMPT / "codex_stderr.txt").write_text(completed.stderr)
    result = {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_CLI_RESULT_V1",
        "exit_code": completed.returncode,
        "status": "COMPLETED" if completed.returncode == 0 else "FAILED",
        "stdout_bytes": len(completed.stdout.encode()),
        "stderr_bytes": len(completed.stderr.encode()),
        "timed_out": False,
    }
    (ATTEMPT / "cli_process_result.json").write_text(json.dumps(result, indent=2) + "\n")
    if completed.returncode != 0:
        raise SystemExit(f"real CLI failed without retry: exit={completed.returncode}")
    authorization = json.loads(AUTHORIZATION.read_text())
    authorization["real_cli_starts"]["used_real_cli_starts"] = 1
    AUTHORIZATION.write_text(json.dumps(authorization, indent=2) + "\n")


if __name__ == "__main__":
    main()
