import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1"
CONFIG_REL = EXPERIMENT / "session_config_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = EXPERIMENT / "input_bundle/bundle_manifest_v1.json"
    manifest = json.loads(manifest_path.read_text())
    failures = []
    for entry in manifest["files"]:
        path = ROOT / entry["path"]
        content = path.read_bytes()
        if len(content) != entry["bytes"] or sha256(path) != entry["sha256"]:
            failures.append(entry["path"])
    if failures:
        raise RuntimeError(f"input bundle hash failures: {failures}")

    doctor_path = EXPERIMENT / "session/codex_cli/attempt_01/codex_doctor_preflight.json"
    doctor = json.loads(doctor_path.read_text())
    doctor_summary = {
        "command": "codex doctor --json --network-only with openai/gpt-6-astra and four-tool MCP overrides",
        "generation_request_used": False,
        "overall_status": doctor["overallStatus"],
        "codex_version": doctor["codexVersion"],
        "checks": {
            name: {"status": value.get("status"), "summary": value.get("summary")}
            for name, value in doctor["checks"].items()
        },
        "stderr": (EXPERIMENT / "session/codex_cli/attempt_01/codex_doctor_preflight.stderr.txt").read_text(),
    }

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
    if completed.returncode != 0 or status_response.get("session_id") != "real-tool-loop-astra-high-seven-focused-v1":
        raise RuntimeError("zero-model MCP status preflight failed")
    transcript = {
        "schema_version": "KIMIARK_SEVEN_FOCUSED_ZERO_MODEL_MCP_PREFLIGHT_V1",
        "boundary": "get_session_status is a no-model MCP call and does not consume check/candidate/simulation budgets.",
        "config_path": CONFIG_REL.relative_to(ROOT).as_posix(),
        "exit_code": completed.returncode,
        "generation_request_used": False,
        "requests": requests,
        "responses": responses,
        "stderr": completed.stderr,
    }
    transcript_path = EXPERIMENT / "session/codex_cli/attempt_01/mcp_no_model_status_transcript_v1.json"
    transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n")

    comparison = EXPERIMENT / "input_bundle/zero_model_comparison_v1.json"
    m70_events = EXPERIMENT / "input_bundle/m70_diagnostic_events.json.gz"
    seven_events = EXPERIMENT / "input_bundle/seven_recursive_diagnostic_events.json.gz"
    preflight = {
        "schema_version": "KIMIARK_SEVEN_FOCUSED_ZERO_MODEL_PREFLIGHT_V1",
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
            "comparison_sha256": sha256(comparison),
            "m70_events_gz_sha256": sha256(m70_events),
            "seven_recursive_events_gz_sha256": sha256(seven_events),
        },
        "task_configuration": {
            "attempt": 1,
            "provider": "openai",
            "model": "gpt-6-astra",
            "reasoning_effort": "high",
            "features_apps": False,
            "mechanics_version": "m38b-2781-animation-speed-v1",
            "max_unique_deployed_operators": 7,
            "max_candidates": 2,
            "max_check_calls": 10,
            "max_real_cli_starts": 1,
            "used_real_cli_starts_before_start": 0,
            "prompt_sha256": sha256(EXPERIMENT / "session/codex_cli/astra_prompt_v1.txt"),
            "runner_sha256": sha256(ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"),
            "authorization_sha256_before_start": sha256(EXPERIMENT / "model_authorization_v1.json"),
            "session_config_sha256": sha256(CONFIG_REL),
        },
        "codex_doctor": doctor_summary,
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
        "coverage_boundary": "These checks do not prove a real model session, MCP tool execution, usage, or turn.completed. Attempt 1 is the authorized real-session verification.",
    }
    (EXPERIMENT / "zero_model_preflight_v1.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"preflight": "PASS", "remaining_simulations": preflight["mcp_no_model_status"]["remaining_simulations"]}))


if __name__ == "__main__":
    main()
