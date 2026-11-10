#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry_v1"
CONFIG_PATH = EXPERIMENT / "session_config_v1.json"
AUTHORIZATION_PATH = EXPERIMENT / "model_authorization_v1.json"
SERVICE_PATH = ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"
PYTHON_PATH = ROOT / ".venv/bin/python"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request(method: str, request_id: int | None = None, params: dict | None = None) -> dict:
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = params
    return payload


def run_client(argv: list[str], requests: list[dict], timeout_seconds: float = 30) -> dict:
    stdin = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in requests)
    started = monotonic()
    try:
        completed = subprocess.run(
            argv,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            cwd=ROOT,
        )
        elapsed_ms = round((monotonic() - started) * 1000, 3)
        responses = []
        for line in completed.stdout.splitlines():
            if line.strip():
                responses.append(json.loads(line))
        return {
            "argv": argv,
            "generation_request_used": False,
            "exit_code": completed.returncode,
            "timed_out": False,
            "elapsed_ms": elapsed_ms,
            "response_count": len(responses),
            "responses": responses,
            "stdout_bytes": len(completed.stdout.encode("utf-8")),
            "stderr_bytes": len(completed.stderr.encode("utf-8")),
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "generation_request_used": False,
            "exit_code": None,
            "timed_out": True,
            "elapsed_ms": round((monotonic() - started) * 1000, 3),
            "response_count": 0,
            "stdout_bytes": len((exc.stdout or "").encode("utf-8")),
            "stderr_bytes": len((exc.stderr or "").encode("utf-8")),
            "stderr": (exc.stderr or b"").decode(errors="replace"),
        }


def main() -> None:
    config = json.loads(AUTHORIZATION_PATH.read_text())
    configured_args_value = next(value for value in config["extra_config_values"] if value.startswith("mcp_servers.kimiark.args="))
    configured_args_text = configured_args_value.split("=", 1)[1]
    configured_args = json.loads(configured_args_text)
    codex_effective_argv = [str(PYTHON_PATH), *configured_args]
    direct_argv = [str(PYTHON_PATH), str(SERVICE_PATH), str(CONFIG_PATH)]

    requests = [
        request("initialize", 1, {"capabilities": {}, "clientInfo": {"name": "kimiark-zero-model-recovery-test", "version": "1"}, "protocolVersion": "2024-11-05"}),
        request("notifications/initialized"),
        request("tools/list", 2),
        request("tools/call", 3, {"name": "get_session_status", "arguments": {}}),
    ]
    direct = run_client(direct_argv, requests)
    configured_emulation = run_client(codex_effective_argv, requests[:2])

    status_response = direct["responses"][-1]["result"]["structuredContent"] if direct["response_count"] == 3 and not direct.get("timed_out") else None
    direct_ok = bool(
        not direct.get("timed_out")
        and direct["exit_code"] == 0
        and direct["response_count"] == 3
        and status_response
        and status_response.get("session_id") == "real-tool-loop-sol-high-seven-retry-v1"
        and status_response.get("model") == "gpt-6.1-sol"
    )
    configured_failed = bool(configured_emulation.get("timed_out") or configured_emulation.get("exit_code") != 0 or configured_emulation["response_count"] == 0)
    report = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY_ZERO_MODEL_HANDSHAKE_ROOT_CAUSE_V1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generation_request_used": False,
        "budget_change": {
            "authorized_real_cli_starts": 1,
            "used_real_cli_starts": 1,
            "used_check_calls": 0,
            "used_candidates": 0,
            "started_stage_simulations": 0,
        },
        "comparison": {
            "zero_model_preflight_service_argv": direct_argv,
            "codex_effective_service_argv": codex_effective_argv,
            "configured_mcp_args": configured_args,
            "missing_service_script_path": configured_args != [str(SERVICE_PATH), str(CONFIG_PATH)],
            "environment_variable_names_not_values": sorted(
                name for name in os.environ
                if name.lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
            ),
            "working_directory_root": str(ROOT),
            "python_executable": str(PYTHON_PATH),
            "session_config_path": str(CONFIG_PATH),
            "service_script_path": str(SERVICE_PATH),
        },
        "preflight_blind_spot": {
            "observed": "run_zero_model_preflight_v1.py invoked the service directly with the correct script path, but did not parse the mcp_servers.kimiark.args override that Codex would use.",
            "effect": "Preflight validated the service but not the exact Codex-managed launch argv.",
        },
        "catalog_refresh_timeouts": {
            "classification": "SAME_TIME_OBSERVATIONS_ONLY",
            "established_as_mcp_root_cause": False,
            "reason": "The configured-args emulation reproduced immediate exit without any network request, while direct service initialization succeeded.",
        },
        "repair": {
            "changed_files": [
                "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry_v1/build_experiment_v1.py",
                "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry_v1/run_attempt_v1.py",
            ],
            "required_codex_effective_args": [str(SERVICE_PATH), str(CONFIG_PATH)],
            "changed_old_authorization_or_budget": False,
            "automatic_real_cli_retry_authorized": False,
        },
        "direct_production_service_test": direct,
        "codex_configured_args_emulation": configured_emulation,
        "classification": {
            "direct_production_service_ok": direct_ok,
            "codex_configured_args_failed": configured_failed,
            "root_cause": "CONFIGURATION_DEFECT_CONFIRMED" if direct_ok and configured_failed else "UNKNOWN",
        },
        "sensitive_values_archived": False,
    }
    output_path = EXPERIMENT / "zero_model_handshake_root_cause_v1.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "classification": report["classification"]["root_cause"],
        "direct_ok": direct_ok,
        "configured_failed": configured_failed,
        "direct_elapsed_ms": direct["elapsed_ms"],
        "configured_exit_code": configured_emulation["exit_code"],
    }))


if __name__ == "__main__":
    main()
