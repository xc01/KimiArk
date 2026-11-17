#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_gap_v1/session_config_v1.json"
SERVICE = ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"


def call(name: str, arguments: dict, *, timeout: int = 3600) -> dict:
    request_id = 1
    messages = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": "kimiark-zero-model-mcp-client", "version": "1.0.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    ]
    stdin_text = "".join(json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n" for message in messages)
    completed = subprocess.run(
        [sys.executable, str(SERVICE), str(CONFIG)],
        input=stdin_text.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ROOT,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.decode(errors="replace") or f"service exited {completed.returncode}")
    response = None
    for line in completed.stdout.decode(errors="replace").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("id") == request_id:
            response = payload
            break
    if response is None:
        raise SystemExit("service did not return a response for tools/call")
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description="Zero-model production MCP four-tool client")
    parser.add_argument("tool", choices=["get_session_status", "check_plan", "run_simulation", "query_events"])
    parser.add_argument("--arguments-json", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    response = call(args.tool, json.loads(args.arguments_json))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    result = response.get("result") or {}
    print(json.dumps({"isError": result.get("isError", False), "structuredContent": result.get("structuredContent")}, ensure_ascii=False, sort_keys=True))
    return 2 if result.get("isError") else 0


if __name__ == "__main__":
    raise SystemExit(main())
