from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import sys
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from kimi_readonly_tools import TOOLS_SCHEMA, ReadOnlyQueryEngine
from kimi_responses_transport import StreamAccumulator, extract_response_text, parse_sse
from kimi_tool_loop import (
    ToolLoopBudget,
    build_tool_continuation_payload,
    execute_tool_calls,
    validate_tool_request,
)


OUT = ROOT / "output/r8_1_kimi_tool_protocol_probe_v1"
BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/responses"
MODEL = "kimi-k3"
TIMEOUT_SECONDS = 300
OUTPUT_TOKEN_LIMIT = 1024


def write_json(name: str, payload: Any) -> None:
    (OUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_attempt(record: dict[str, Any]) -> None:
    with (OUT / "call_attempts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def protocol_request(prompt: str) -> dict[str, Any]:
    return {
        "model": MODEL,
        "stream": True,
        "max_output_tokens": OUTPUT_TOKEN_LIMIT,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "tools": copy.deepcopy(TOOLS_SCHEMA),
    }


def stream_once(payload: dict[str, Any], attempt_number: int) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
    errors = validate_tool_request(payload)
    if errors:
        raise RuntimeError("invalid protocol tool request: " + ", ".join(errors))
    request_path = OUT / f"attempt_{attempt_number}_request.json"
    request_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    (OUT / f"attempt_{attempt_number}_request_body.txt").write_bytes(body)
    credential = os.environ.get("ARK_API_KEY_agent")
    if not credential:
        raise RuntimeError("ARK_API_KEY_agent is not set")
    request = urllib.request.Request(
        BASE_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    started = {
        "attempt": attempt_number,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": BASE_URL,
        "model": payload.get("model"),
        "max_output_tokens": payload.get("max_output_tokens"),
        "request_body_sha256": hashlib.sha256(body).hexdigest(),
    }
    append_attempt(started)
    accumulator = StreamAccumulator()
    http_status = None
    request_id = None
    raw_chunks: list[bytes] = []
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            http_status = response.status
            request_id = response.headers.get("x-request-id")
            for raw_bytes in response:
                raw_chunks.append(raw_bytes)
    except urllib.error.HTTPError as exc:
        raw_chunks = [exc.read()]
        http_status = exc.code
        request_id = exc.headers.get("x-request-id") if exc.headers else request_id
        accumulator.error = f"HTTP {exc.code}: {raw_chunks[0].decode(errors='replace')}"
    except (TimeoutError, socket.timeout) as exc:
        accumulator.error = f"TIMEOUT: {exc}"
    except urllib.error.URLError as exc:
        accumulator.error = f"URL_ERROR: {exc.reason}"
    except OSError as exc:
        accumulator.error = f"NETWORK_OR_STREAM_INTERRUPTED: {exc}"
    raw = b"".join(raw_chunks)
    (OUT / f"attempt_{attempt_number}_raw_response.txt").write_bytes(raw)
    for event in parse_sse(raw.decode("utf-8", errors="replace")):
        accumulator.observe(event)
    accumulator.http_status = http_status
    accumulator.request_id = request_id
    append_attempt({
        "attempt": attempt_number,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": accumulator.terminal_event or "ATTEMPT_FAILED",
        "error": accumulator.error,
        "http_status": http_status,
        "request_id": request_id,
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "response_bytes": len(raw),
    })
    return accumulator.response_envelope or {}, accumulator, raw


def failure_result(budget: ToolLoopBudget, reason: str, details: Any) -> dict[str, Any]:
    return {
        "schema_version": "R8_1_KIMI_TOOL_PROTOCOL_PROBE_V1",
        "status": "FAILED",
        "compatibility_status": "UNVERIFIED",
        "failure_reason": reason,
        "details": details,
        "budget": budget.__dict__,
        "new_tactical_plans": 0,
        "action_candidates": 0,
        "stage_simulations": 0,
        "tactical_search_expansions": 0,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "call_attempts.jsonl").write_text("", encoding="utf-8")
    budget = ToolLoopBudget(max_model_requests=2, max_tool_calls=1)
    prompt = (
        "Protocol compatibility probe only. Call query_mechanic once with "
        '{"topic":"coordinates_and_direction"}. After receiving the tool result, '
        "reply with one short sentence confirming the coordinate convention. "
        "Do not generate an OperationalPlan."
    )
    initial_request = protocol_request(prompt)
    engine = ReadOnlyQueryEngine()
    try:
        budget.start_model_request()
        envelope, accumulator, raw = stream_once(initial_request, 1)
    except Exception as exc:
        result = failure_result(budget, "FIRST_REQUEST_FAILED", {
            "error": str(exc), "traceback": traceback.format_exc(),
        })
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("first protocol request failed without retry") from exc

    classification = accumulator.classify()
    write_json("attempt_1_classification.json", classification)
    if accumulator.error or accumulator.terminal_event != "response.completed" or envelope.get("status") != "completed":
        result = failure_result(budget, "FIRST_RESPONSE_NOT_COMPLETED", {
            "error": accumulator.error,
            "terminal_event": accumulator.terminal_event,
            "response_status": envelope.get("status"),
            "http_status": accumulator.http_status,
            "request_id": accumulator.request_id,
        })
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("first protocol response was not completed")
    if "function_call" not in classification.get("output_item_types", []) or not classification.get("function_calls"):
        result = failure_result(budget, "NO_NATIVE_FUNCTION_CALL", {
            "classification": classification,
            "final_output_text": extract_response_text(envelope)[0],
        })
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("provider did not emit a native function_call")
    if classification.get("malformed_events"):
        result = failure_result(budget, "MALFORMED_FUNCTION_CALL_EVENTS", classification.get("malformed_events"))
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("first response contained malformed function call events")

    calls = classification.get("function_calls", [])
    try:
        tool_results = execute_tool_calls(calls, engine, budget)
    except Exception as exc:
        result = failure_result(budget, "TOOL_PREFLIGHT_FAILED", {"error": str(exc)})
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("tool preflight failed without retry") from exc
    if len(tool_results) != 1 or tool_results[0].get("status") != "EXECUTED":
        result = failure_result(budget, "TOOL_NOT_EXECUTED", {"tool_results": tool_results})
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("single read-only tool was not executed")

    try:
        continuation = build_tool_continuation_payload(initial_request, calls, tool_results)
    except Exception as exc:
        result = failure_result(budget, "CONTINUATION_BUILD_FAILED", {"error": str(exc)})
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("continuation build failed without retry") from exc
    write_json("attempt_1_tool_results.json", tool_results)
    write_json("attempt_2_request.json", continuation)

    try:
        budget.start_model_request()
        final_envelope, final_accumulator, final_raw = stream_once(continuation, 2)
    except Exception as exc:
        result = failure_result(budget, "CONTINUATION_REQUEST_FAILED", {
            "error": str(exc), "traceback": traceback.format_exc(),
        })
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("continuation request failed without retry") from exc

    final_classification = final_accumulator.classify()
    write_json("attempt_2_classification.json", final_classification)
    confirmation_text, final_item_types = extract_response_text(final_envelope)
    if final_accumulator.error or final_accumulator.terminal_event != "response.completed" or final_envelope.get("status") != "completed":
        result = failure_result(budget, "CONTINUATION_RESPONSE_NOT_COMPLETED", {
            "error": final_accumulator.error,
            "terminal_event": final_accumulator.terminal_event,
            "response_status": final_envelope.get("status"),
            "http_status": final_accumulator.http_status,
            "request_id": final_accumulator.request_id,
        })
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("continuation response was not completed")
    if final_classification.get("malformed_events") or not confirmation_text.strip():
        result = failure_result(budget, "CONTINUATION_CONFIRMATION_INVALID", {
            "malformed_events": final_classification.get("malformed_events"),
            "final_output_text": confirmation_text,
            "final_item_types": final_item_types,
        })
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("continuation did not produce a valid confirmation")
    if "revised_operational_plans" in confirmation_text:
        result = failure_result(budget, "TACTICAL_PLAN_GENERATED_FORBIDDEN", {"final_output_text": confirmation_text})
        write_json("protocol_result.json", result)
        write_json("final_status.json", {"status": "PROTOCOL_PROBE_FAILED", "actual_model_requests": budget.model_requests_started})
        raise SystemExit("protocol probe unexpectedly produced a tactical plan key")

    result = {
        "schema_version": "R8_1_KIMI_TOOL_PROTOCOL_PROBE_V1",
        "status": "COMPLETE",
        "compatibility_status": "CONFIRMED_NON_TACTICAL_TOOL_ROUND",
        "scope": "PROTOCOL_PROBE_ONLY_NO_TACTICAL_CONTEXT_NO_C2",
        "endpoint": BASE_URL,
        "model": MODEL,
        "requested_output_budget_tokens": OUTPUT_TOKEN_LIMIT,
        "actual_model_requests": budget.model_requests_started,
        "actual_readonly_tool_executions": budget.tool_calls_executed,
        "attempt_1": {
            "http_status": accumulator.http_status,
            "request_id": accumulator.request_id,
            "terminal_event": accumulator.terminal_event,
            "usage": envelope.get("usage"),
            "function_call": calls[0],
            "call_id": calls[0].get("call_id"),
        },
        "attempt_2": {
            "http_status": final_accumulator.http_status,
            "request_id": final_accumulator.request_id,
            "terminal_event": final_accumulator.terminal_event,
            "usage": final_envelope.get("usage"),
            "final_output_text": confirmation_text,
        },
        "native_function_call_observed": "function_call" in classification.get("output_item_types", []),
        "local_tool_result_call_id": tool_results[0].get("call_id"),
        "continuation_input_types": [item.get("type") for item in continuation.get("input", [])],
        "new_tactical_plans": 0,
        "action_candidates": 0,
        "stage_simulations": 0,
        "tactical_search_expansions": 0,
    }
    write_json("protocol_result.json", result)
    write_json("final_status.json", {"status": "PROTOCOL_PROBE_COMPLETE", **result})


if __name__ == "__main__":
    main()
