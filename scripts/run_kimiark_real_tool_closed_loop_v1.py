from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_r8_1_gpt_c4_codex_cli_v1 as codex_runner
from codex_model_authorization_v1 import validate_cli_authorization


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if exclusive and path.exists():
        raise RuntimeError(f"immutable output already exists: {path}")
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def proxy_prestart(output_dir: Path) -> dict[str, Any]:
    import http.client
    import time
    from urllib.parse import urlparse

    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not proxy:
        raise RuntimeError("HTTPS_PROXY is required before real Codex start")
    parsed = urlparse(proxy)
    started = time.monotonic()
    try:
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=8)
        connection.request("CONNECT", "chatgpt.com:443")
        response = connection.getresponse()
        elapsed = round((time.monotonic() - started) * 1000, 3)
        if response.status != 200:
            raise RuntimeError(f"proxy CONNECT returned HTTP {response.status}")
    except Exception as exc:
        raise RuntimeError(f"proxy prestart failed for {proxy}: {exc}") from exc
    record = {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_PROXY_PRESTART_V1",
        "proxy": proxy,
        "connect_target": "chatgpt.com:443",
        "status": response.status,
        "elapsed_ms": elapsed,
        "counts_as_cli_start": False,
    }
    write_json(output_dir / "proxy_prestart.json", record)
    return record


def build_command(authorization_path: Path, last_message_path: Path) -> list[str]:
    authorization = load_json(authorization_path)
    command = [
        "codex", "exec", "--json", "--sandbox", "read-only", "--cd", str(ROOT),
        "-c", 'model_provider="openai"',
    ]
    for value in authorization.get("extra_config_values") or []:
        command.extend(["-c", value])
    command.extend([
        "-m", authorization["model"],
        "-c", f'model_reasoning_effort="{authorization["reasoning_effort"]}"',
        "-o", str(last_message_path), "-",
    ])
    validate_cli_authorization(authorization_path, command, prompt_sha256=None)
    return command


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the single authorized real Codex tool-loop CLI")
    parser.add_argument("--config", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    arguments = parser.parse_args()
    config_path = (ROOT / arguments.config).resolve()
    prompt_path = (ROOT / arguments.prompt).resolve()
    config = load_json(config_path)
    session_root = (ROOT / config["session_root"]).resolve()
    output_dir = session_root / "codex_cli"
    output_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = output_dir / "cli_process_attempt.json"
    if attempt_path.exists():
        raise RuntimeError("real closed-loop CLI attempt already exists; no automatic retry")
    with (output_dir / "runner.lock").open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("real closed-loop runner already holds lock") from exc
        budget_path = ROOT / config["budget_path"]
        budget = load_json(budget_path)
        if budget.get("started_stage_simulations") != 0:
            raise RuntimeError("simulation budget already has started simulations; refusing new CLI")
        ledger_path = ROOT / config["candidate_ledger_path"]
        ledger = load_json(ledger_path)
        if ledger.get("used_candidates") != 0:
            raise RuntimeError("candidate ledger already has checked candidates; refusing new CLI")
        prompt = prompt_path.read_text(encoding="utf-8")
        prompt_file = output_dir / "codex_prompt.txt"
        prompt_file.write_text(prompt + "\n", encoding="utf-8")
        last_message_path = output_dir / "codex_final_message.txt"
        command = build_command(ROOT / config["authorization_config_path"], last_message_path)
        write_json(output_dir / "codex_command.json", {
            "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_CODEX_COMMAND_V1",
            "argv": command,
            "stdin": "prompt_file_content_via_runner",
            "shell": False,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "timeout_seconds": arguments.timeout_seconds,
        }, exclusive=True)
        proxy_prestart(output_dir)
        environment = codex_runner.codex_environment()
        record = {
            "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_CLI_ATTEMPT_V1",
            "status": "STARTED",
            "started_at": utc_now(),
            "automatic_retry": False,
            "automatic_resume": False,
            "timeout_seconds": arguments.timeout_seconds,
            "command": command,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "model": config["model"],
            "reasoning_effort": config["reasoning_effort"],
            "codex_home": environment.get("CODEX_HOME"),
            "mcp_server": "kimiark",
            "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        }
        write_json(attempt_path, record, exclusive=True)
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=arguments.timeout_seconds,
                check=False,
                env=environment,
                cwd=ROOT,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="replace")
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="replace")
            (output_dir / "codex_exec.jsonl").write_text(stdout, encoding="utf-8")
            (output_dir / "codex_stderr.txt").write_text(stderr, encoding="utf-8")
            write_json(output_dir / "cli_process_result.json", {
                "status": "TIMEOUT", "exit_code": None, "timed_out": True,
            }, exclusive=True)
            raise
        (output_dir / "codex_exec.jsonl").write_text(completed.stdout, encoding="utf-8")
        (output_dir / "codex_stderr.txt").write_text(completed.stderr, encoding="utf-8")
        trajectory = codex_runner.extract_events_summary(completed.stdout)
        write_json(output_dir / "cli_process_result.json", {
            "status": "COMPLETED" if completed.returncode == 0 else "FAILED",
            "exit_code": completed.returncode,
            "timed_out": False,
            "stdout_bytes": len(completed.stdout.encode("utf-8")),
            "stderr_bytes": len(completed.stderr.encode("utf-8")),
        }, exclusive=True)
        write_json(output_dir / "codex_trajectory_summary.json", trajectory)
        if completed.returncode != 0:
            raise SystemExit(f"Codex CLI exited {completed.returncode}; no retry")
        if not last_message_path.is_file():
            raise SystemExit("Codex final message missing; no retry")
        print(json.dumps({
            "status": "COMPLETED",
            "output_dir": str(output_dir.relative_to(ROOT)),
            "usage_records": trajectory.get("usage_records", []),
            "event_count": trajectory.get("event_count"),
        }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
