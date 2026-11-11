#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_closure_v1"
CONFIG_PATH = EXPERIMENT / "session_config_v1.json"
AUTHORIZATION_PATH = EXPERIMENT / "model_authorization_v1.json"
SERVICE_PATH = ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"
PYTHON_PATH = ROOT / ".venv/bin/python"
ATTEMPT_DIR = EXPERIMENT / "session/codex_cli"
PROMPT_PATH = ATTEMPT_DIR / "sol_prompt_v1.txt"
SESSION_ID = "real-tool-loop-sol-high-seven-artillery-closure-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request(method: str, request_id: int | None = None, params: dict | None = None) -> dict:
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = params
    return payload


def proxy_prestart() -> dict:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not proxy:
        raise RuntimeError("HTTPS_PROXY is required before real Codex start")
    parsed = urlparse(proxy)
    connection = HTTPConnection(parsed.hostname, parsed.port, timeout=8)
    started = monotonic()
    connection.request("CONNECT", "chatgpt.com:443")
    response = connection.getresponse()
    response.close()
    connection.close()
    elapsed = round((monotonic() - started) * 1000, 3)
    if response.status != 200:
        raise RuntimeError(f"proxy CONNECT returned HTTP {response.status}")
    return {"schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_CLOSURE_PROXY_PRESTART_V1", "generation_request_used": False, "proxy": proxy, "connect_target": "chatgpt.com:443", "status": response.status, "elapsed_ms": elapsed, "counts_as_cli_start": False}


def parse_codex_mcp_config(authorization: dict) -> tuple[str, list[str]]:
    command_value = None
    args_value = None
    for raw in authorization["extra_config_values"]:
        key, value = raw.split("=", 1)
        if key == "mcp_servers.kimiark.command":
            command_value = value
        elif key == "mcp_servers.kimiark.args":
            args_value = value
    if command_value is None or args_value is None:
        raise RuntimeError("Codex MCP command/args overrides missing")
    command = json.loads(command_value)
    args = json.loads(args_value)
    if not isinstance(command, str) or not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        raise RuntimeError("Codex MCP command/args malformed")
    return command, args


def main() -> None:
    ATTEMPT_DIR.mkdir(parents=True, exist_ok=True)
    authorization = json.loads(AUTHORIZATION_PATH.read_text())
    if authorization["model"] != "gpt-6.1-sol" or authorization["reasoning_effort"] != "high":
        raise RuntimeError("Sol authorization mismatch before preflight")
    if authorization["real_cli_starts"]["used_real_cli_starts"] != 0:
        raise RuntimeError("artillery-closure CLI already started")
    codex_command, codex_args = parse_codex_mcp_config(authorization)
    expected_args = [str(SERVICE_PATH), str(CONFIG_PATH)]
    if codex_args != expected_args or codex_command != str(PYTHON_PATH):
        raise RuntimeError("Codex MCP command/args mismatch")
    manifest_path = EXPERIMENT / "input_bundle/bundle_manifest_v1.json"
    manifest = json.loads(manifest_path.read_text())
    failures = [entry["path"] for entry in manifest["files"] if (ROOT / entry["path"]).stat().st_size != entry["bytes"] or sha256(ROOT / entry["path"]) != entry["sha256"]]
    if failures:
        raise RuntimeError(f"input bundle hash failures: {failures}")
    evidence = json.loads((EXPERIMENT / "input_bundle/llm_evidence_context.json").read_text())
    identity = json.loads((EXPERIMENT / "input_bundle/parent_identity_manifest_v1.json").read_text())
    if evidence.get("cold_start_task_root") is not None:
        raise RuntimeError("artillery-closure evidence must not use cold_start_task_root")
    if evidence.get("revision_entry_mode") != "PARENT_CANDIDATE_REVISION_V1" or len(identity["parent_candidates"]) != 10:
        raise RuntimeError("artillery-closure parent-candidate revision entry mismatch")
    doctor_argv = ["codex", "doctor", "--json", "--network-only", "-c", 'model_provider="openai"']
    for value in authorization["extra_config_values"]:
        doctor_argv.extend(["-c", value])
    doctor_completed = subprocess.run(doctor_argv, cwd=ROOT, text=True, capture_output=True, check=True, timeout=90)
    doctor_path = ATTEMPT_DIR / "codex_doctor_preflight.json"
    doctor_stderr_path = ATTEMPT_DIR / "codex_doctor_preflight.stderr.txt"
    doctor_path.write_text(doctor_completed.stdout)
    doctor_stderr_path.write_text(doctor_completed.stderr)
    doctor = json.loads(doctor_path.read_text())
    requests = [
        request("initialize", 1, {"capabilities": {}, "clientInfo": {"name": "kimiark-zero-model-artillery-closure-preflight", "version": "1"}, "protocolVersion": "2024-11-05"}),
        request("notifications/initialized"),
        request("tools/list", 2),
        request("tools/call", 3, {"name": "get_session_status", "arguments": {}}),
    ]
    stdin = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in requests)
    argv = [codex_command, *codex_args]
    started = monotonic()
    completed = subprocess.run(argv, input=stdin, text=True, capture_output=True, timeout=30, cwd=ROOT, env=os.environ)
    elapsed_ms = round((monotonic() - started) * 1000, 3)
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode != 0 or len(responses) != 3:
        raise RuntimeError(f"MCP preflight failed: exit={completed.returncode}, responses={len(responses)}, stderr={completed.stderr}")
    status_response = responses[-1]["result"]["structuredContent"]
    if status_response.get("session_id") != SESSION_ID:
        raise RuntimeError("MCP status session mismatch")
    if status_response["model"] != "gpt-6.1-sol" or status_response["reasoning_effort"] != "high":
        raise RuntimeError("MCP status model/effort mismatch")
    transcript = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_CLOSURE_ZERO_MODEL_MCP_PREFLIGHT_V1",
        "boundary": "Exact command/args parsed from Codex overrides; no check/candidate/simulation budget is consumed.",
        "codex_effective_mcp_command": codex_command, "codex_effective_mcp_args": codex_args, "working_directory": str(ROOT),
        "environment_variable_names_not_values": sorted(name for name in os.environ if name.lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}),
        "exit_code": completed.returncode, "elapsed_ms": elapsed_ms, "generation_request_used": False, "requests": requests, "responses": responses, "stderr": completed.stderr,
    }
    transcript_path = ATTEMPT_DIR / "mcp_no_model_status_transcript_v1.json"
    transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n")
    proxy = proxy_prestart()
    (ATTEMPT_DIR / "proxy_prestart.json").write_text(json.dumps(proxy, ensure_ascii=False, indent=2) + "\n")
    preflight = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_CLOSURE_ZERO_MODEL_PREFLIGHT_V1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generation_request_used": False,
        "repository_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "input_bundle": {"manifest_entries": len(manifest["files"]), "manifest_all_hashes_match": not failures, "manifest_sha256": sha256(manifest_path), "cold_start_task_root_removed": True, "parent_candidates": identity["parent_candidates"]},
        "task_configuration": {
            "provider": authorization["provider"], "model": authorization["model"], "reasoning_effort": authorization["reasoning_effort"], "features_apps": authorization["features_apps"],
            "mechanics_version": "m38b-2781-animation-speed-v1", "max_unique_deployed_operators": 7, "max_candidates": 2, "max_check_calls": 10, "max_real_cli_starts": 1,
            "used_real_cli_starts_before_start": authorization["real_cli_starts"]["used_real_cli_starts"], "prompt_sha256": sha256(PROMPT_PATH), "runner_sha256": sha256(SERVICE_PATH),
            "authorization_sha256_before_start": sha256(AUTHORIZATION_PATH), "session_config_sha256": sha256(CONFIG_PATH),
        },
        "codex_effective_mcp": {"command": codex_command, "args": codex_args, "service_script_path_present": SERVICE_PATH.as_posix() in codex_args, "session_config_path_present": CONFIG_PATH.as_posix() in codex_args},
        "codex_doctor": {"generation_request_used": False, "overall_status": doctor.get("overallStatus"), "codex_version": doctor.get("codexVersion"), "checks": {name: {"status": value.get("status"), "summary": value.get("summary")} for name, value in doctor.get("checks", {}).items()}, "stderr": doctor_completed.stderr},
        "mcp_no_model_status": {"argv": argv, "cwd": str(ROOT), "environment_variable_names_not_values": transcript["environment_variable_names_not_values"], "exit_code": completed.returncode, "elapsed_ms": elapsed_ms, "generation_request_used": False, "session_id": status_response["session_id"], "session_model": status_response["model"], "session_reasoning_effort": status_response["reasoning_effort"], "remaining_checks": status_response["check_call_ledger"]["remaining_check_calls"], "remaining_candidates": status_response["candidate_ledger"]["remaining_candidates"], "remaining_simulations": status_response["budget"]["remaining_stage_simulations"], "transcript_sha256": sha256(transcript_path)},
        "proxy_prestart": proxy,
        "coverage_boundary": "These checks do not prove a real model session, workspace routing, MCP tool execution, usage, or turn.completed. The authorized CLI is the real-session verification.",
    }
    (EXPERIMENT / "zero_model_preflight_v1.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"preflight": "PASS", "session_id": status_response["session_id"], "session_model": status_response["model"], "remaining_simulations": status_response["budget"]["remaining_stage_simulations"], "doctor_status": preflight["codex_doctor"]["overall_status"]}))


if __name__ == "__main__":
    main()
