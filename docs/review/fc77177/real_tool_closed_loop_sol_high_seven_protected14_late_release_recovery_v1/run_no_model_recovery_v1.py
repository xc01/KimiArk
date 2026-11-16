#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_recovery_v1"
CONFIG = DEST / "session_config_v1.json"
SERVICE = ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"
PYTHON = ROOT / ".venv/bin/python"
NORMALIZED = DEST / "normalized_llm_structured_output.json"
TRANSCRIPT = DEST / "no_model_service_transcript_v1.jsonl"


def rpc(method: str, request_id: int | None = None, params: dict | None = None) -> dict:
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = params
    return payload


def invoke(payloads: list[dict], timeout: int) -> tuple[int, str, str]:
    stdin = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in payloads)
    completed = subprocess.run([str(PYTHON), str(SERVICE), str(CONFIG)], input=stdin, text=True, capture_output=True, timeout=timeout, cwd=ROOT, env=os.environ, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def parse_responses(stdout: str) -> list[dict]:
    return [json.loads(line) for line in stdout.splitlines() if line.strip()]


def record_event(payload: dict) -> None:
    with TRANSCRIPT.open("a") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    if (DEST / "session/candidates").exists():
        raise RuntimeError("R107 recovery candidate already exists")
    plan = json.loads(NORMALIZED.read_text())
    candidate_sha = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (DEST / "service_call_attempt_v1.json").exists():
        raise RuntimeError("R107 recovery service calls already started")
    (DEST / "service_call_attempt_v1.json").write_text(json.dumps({
        "schema_version": "KIMIARK_NO_MODEL_RECOVERY_SERVICE_ATTEMPT_V1",
        "status": "STARTED",
        "generation_request_used": False,
        "real_cli_starts": 0,
        "argv": [str(PYTHON), str(SERVICE), str(CONFIG)],
        "normalized_candidate_sha256": candidate_sha,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    precheck_payloads = [
        rpc("initialize", 1, {"capabilities": {}, "clientInfo": {"name": "kimiark-no-model-protocol-recovery", "version": "1"}, "protocolVersion": "2025-06-18"}),
        rpc("notifications/initialized"),
        rpc("tools/list", 2),
        rpc("tools/call", 3, {"name": "get_session_status", "arguments": {}}),
        rpc("tools/call", 4, {"name": "check_plan", "arguments": {"plan": plan}}),
    ]
    code, stdout, stderr = invoke(precheck_payloads, timeout=120)
    responses = parse_responses(stdout)
    record_event({"event": "PRECHECK_COMPLETE", "exit_code": code, "responses": responses, "stderr": stderr})
    if code != 0 or len(responses) != 4:
        raise RuntimeError(f"no-model service precheck failed: exit={code}, responses={len(responses)}, stderr={stderr}")
    status = responses[2]["result"]["structuredContent"]
    check = responses[3]["result"]["structuredContent"]
    if status.get("session_id") != "real-tool-loop-sol-high-seven-protected14-recovery-v1" or check.get("status") != "PASS":
        raise RuntimeError(f"normalized check did not PASS: status={status}, check={check}")
    candidate_id = check["candidate_id"]
    if check["candidate_sha256"] != candidate_sha:
        raise RuntimeError("check response candidate hash mismatch")
    run_payloads = [rpc("tools/call", 5, {"name": "run_simulation", "arguments": {"candidate_id": candidate_id, "candidate_sha256": candidate_sha}})]
    code, stdout, stderr = invoke(run_payloads, timeout=3600)
    responses = parse_responses(stdout)
    record_event({"event": "SIMULATION_COMPLETE", "exit_code": code, "responses": responses, "stderr": stderr})
    if code != 0 or len(responses) != 1:
        raise RuntimeError(f"no-model service simulation failed: exit={code}, responses={len(responses)}, stderr={stderr}")
    result = responses[0]["result"]["structuredContent"]
    if result.get("status") not in {"COMPLETED", "IDEMPOTENT_COMPLETED"}:
        raise RuntimeError(f"simulation did not complete: {result}")
    (DEST / "service_call_result_v1.json").write_text(json.dumps({
        "schema_version": "KIMIARK_NO_MODEL_RECOVERY_SERVICE_RESULT_V1",
        "generation_request_used": False,
        "real_cli_starts": 0,
        "check_result": check,
        "simulation_result": result,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
