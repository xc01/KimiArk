#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import os
import subprocess
from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry_v1"
CONFIG_REL = EXPERIMENT / "session_config_v1.json"
ATTEMPT_DIR = EXPERIMENT / "session/codex_cli"
PROMPT_PATH = ATTEMPT_DIR / "sol_prompt_v1.txt"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proxy_prestart() -> dict:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not proxy:
        raise RuntimeError("HTTPS_PROXY is required before real Codex start")
    parsed = urlparse(proxy)
    started = monotonic()
    connection = HTTPConnection(parsed.hostname, parsed.port, timeout=8)
    connection.request("CONNECT", "chatgpt.com:443")
    response = connection.getresponse()
    response.close()
    connection.close()
    elapsed = round((monotonic() - started) * 1000, 3)
    if response.status != 200:
        raise RuntimeError(f"proxy CONNECT returned HTTP {response.status}")
    return {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY_PROXY_PRESTART_V1",
        "generation_request_used": False,
        "proxy": proxy,
        "connect_target": "chatgpt.com:443",
        "status": response.status,
        "elapsed_ms": elapsed,
        "counts_as_cli_start": False,
    }


def main() -> None:
    ATTEMPT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = EXPERIMENT / "input_bundle/bundle_manifest_v1.json"
    manifest = json.loads(manifest_path.read_text())
    failures = []
    for entry in manifest["files"]:
        path = ROOT / entry["path"]
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            failures.append(entry["path"])
    if failures:
        raise RuntimeError(f"input bundle hash failures: {failures}")

    authorization = json.loads((EXPERIMENT / "model_authorization_v1.json").read_text())
    if authorization["model"] != "gpt-6.1-sol" or authorization["reasoning_effort"] != "high":
        raise RuntimeError("Sol authorization mismatch before preflight")
    doctor_argv = ["codex", "doctor", "--json", "--network-only", "-c", 'model_provider="openai"']
    for value in authorization["extra_config_values"]:
        doctor_argv.extend(["-c", value])
    doctor_completed = subprocess.run(
        doctor_argv,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=90,
    )
    doctor_path = ATTEMPT_DIR / "codex_doctor_preflight.json"
    doctor_stderr_path = ATTEMPT_DIR / "codex_doctor_preflight.stderr.txt"
    doctor_path.write_text(doctor_completed.stdout)
    doctor_stderr_path.write_text(doctor_completed.stderr)
    doctor = json.loads(doctor_path.read_text())

    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}, "clientInfo": {"name": "kimiark-zero-model-preflight", "version": "1"}, "protocolVersion": "2024-11-05"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_session_status", "arguments": {}}},
    ]
    stdin = "".join(json.dumps(message, separators=(",", ":")) + "\n" for message in requests)
    completed = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"), str(CONFIG_REL.relative_to(ROOT))],
        input=stdin,
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    status_response = responses[-1]["result"]["structuredContent"]
    if completed.returncode != 0 or status_response.get("session_id") != "real-tool-loop-sol-high-seven-retry-v1":
        raise RuntimeError("zero-model MCP status preflight failed")
    transcript = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY_ZERO_MODEL_MCP_PREFLIGHT_V1",
        "boundary": "get_session_status is a no-model MCP call and does not consume check/candidate/simulation budgets.",
        "config_path": CONFIG_REL.relative_to(ROOT).as_posix(),
        "exit_code": completed.returncode,
        "generation_request_used": False,
        "requests": requests,
        "responses": responses,
        "stderr": completed.stderr,
    }
    transcript_path = ATTEMPT_DIR / "mcp_no_model_status_transcript_v1.json"
    transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n")
    proxy = proxy_prestart()
    (ATTEMPT_DIR / "proxy_prestart.json").write_text(json.dumps(proxy, ensure_ascii=False, indent=2) + "\n")

    preflight = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY_ZERO_MODEL_PREFLIGHT_V1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generation_request_used": False,
        "repository": {
            "local_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "unrelated_dirty_files_preserved": True,
        },
        "input_bundle": {
            "manifest_entries": len(manifest["files"]),
            "manifest_all_hashes_match": not failures,
            "manifest_sha256": sha256(manifest_path),
            "retry2_parent_plan_sha256": sha256(EXPERIMENT / "input_bundle/retry2_parent_candidate-002/plan_snapshot.json"),
            "retry2_parent_action_sha256": sha256(EXPERIMENT / "input_bundle/retry2_parent_candidate-002/action_snapshot.json"),
            "retry2_parent_events_gz_sha256": sha256(EXPERIMENT / "input_bundle/retry2_parent_candidate-002/diagnostic_events.json.gz"),
        },
        "task_configuration": {
            "provider": "openai",
            "model": authorization["model"],
            "reasoning_effort": authorization["reasoning_effort"],
            "features_apps": authorization["features_apps"],
            "mechanics_version": "m38b-2781-animation-speed-v1",
            "max_unique_deployed_operators": 7,
            "max_candidates": 2,
            "max_check_calls": 10,
            "max_real_cli_starts": 1,
            "used_real_cli_starts_before_start": authorization["real_cli_starts"]["used_real_cli_starts"],
            "prompt_sha256": sha256(PROMPT_PATH),
            "runner_sha256": sha256(ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"),
            "authorization_sha256_before_start": sha256(EXPERIMENT / "model_authorization_v1.json"),
            "session_config_sha256": sha256(CONFIG_REL),
        },
        "codex_doctor": {
            "generation_request_used": False,
            "overall_status": doctor["overallStatus"],
            "codex_version": doctor["codexVersion"],
            "checks": {
                name: {"status": value.get("status"), "summary": value.get("summary")}
                for name, value in doctor["checks"].items()
            },
            "stderr": doctor_completed.stderr,
        },
        "mcp_no_model_status": {
            "exit_code": completed.returncode,
            "generation_request_used": False,
            "session_model": status_response["model"],
            "session_reasoning_effort": status_response["reasoning_effort"],
            "remaining_checks": status_response["check_call_ledger"]["remaining_check_calls"],
            "remaining_candidates": status_response["candidate_ledger"]["remaining_candidates"],
            "remaining_simulations": status_response["budget"]["remaining_stage_simulations"],
            "transcript_sha256": sha256(transcript_path),
        },
        "proxy_prestart": proxy,
        "coverage_boundary": "These checks do not prove a real model session, workspace routing, MCP tool execution, usage, or turn.completed. The authorized CLI is the real-session verification.",
    }
    (EXPERIMENT / "zero_model_preflight_v1.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"preflight": "PASS", "remaining_simulations": preflight["mcp_no_model_status"]["remaining_simulations"], "doctor": preflight["codex_doctor"]["overall_status"]}))


if __name__ == "__main__":
    main()
