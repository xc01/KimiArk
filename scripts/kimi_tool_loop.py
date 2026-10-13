from __future__ import annotations

import copy
import json
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from jsonschema import Draft7Validator
from run_r8_1_low_star_full_tactical_closure_v1 import (
    OUT,
    load,
    output_schema,
    validate_operational_plan_output,
)
EVIDENCE_CONTEXT = OUT / "llm_evidence_context.json"
from kimi_responses_transport import StreamAccumulator, validate_tactical_request
from kimi_readonly_tools import BASE_RULE_CARD, TOOLS_SCHEMA, TOOL_NAMES, ReadOnlyQueryEngine


class ToolLoopError(RuntimeError):
    pass


class BudgetExceededError(ToolLoopError):
    pass


@dataclass
class ToolLoopBudget:
    max_model_requests: int = 3
    max_tool_calls: int = 6
    model_requests_started: int = 0
    tool_calls_seen: int = 0
    tool_calls_executed: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def start_model_request(self) -> None:
        if self.model_requests_started >= self.max_model_requests:
            raise BudgetExceededError("model request budget exhausted; continuations count as requests")
        self.model_requests_started += 1

    def start_tool_call(self) -> None:
        if self.tool_calls_seen >= self.max_tool_calls:
            raise BudgetExceededError("tool call budget exhausted")
        self.tool_calls_seen += 1

    def check_tool_batch(self, count: int) -> None:
        if self.tool_calls_seen + count > self.max_tool_calls:
            raise BudgetExceededError(
                f"tool call budget exhausted; batch would use {count} but only "
                f"{self.max_tool_calls - self.tool_calls_seen} remain"
            )


def validate_tool_request(payload: dict[str, Any]) -> list[str]:
    errors = validate_tactical_request(payload)
    if payload.get("previous_response_id") is not None:
        errors.append("TOOL_LOOP_PREVIOUS_RESPONSE_ID_FORBIDDEN")
    tools = payload.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append("TOOL_LOOP_REQUIRES_TOOLS")
    else:
        names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
        if len(names) != len(tools) or set(names) != TOOL_NAMES:
            errors.append("TOOL_LOOP_TOOL_WHITELIST_MISMATCH")
        if any(tool.get("type") != "function" for tool in tools if isinstance(tool, dict)):
            errors.append("TOOL_LOOP_ONLY_FUNCTION_TOOLS_ALLOWED")
    return errors


def build_tool_enabled_request(base_payload: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(base_payload)
    payload["tools"] = copy.deepcopy(TOOLS_SCHEMA)
    prompt = payload["input"][0]["content"][0]["text"]
    payload["input"][0]["content"][0]["text"] = (
        prompt
        + "\nTOOLS_AND_BASE_RULES_JSON\n"
        + json.dumps({"base_rule_card": BASE_RULE_CARD, "tools": TOOLS_SCHEMA}, ensure_ascii=False, separators=(",", ":"))
    )
    errors = validate_tool_request(payload)
    if errors:
        raise ToolLoopError("invalid tool request: " + ", ".join(errors))
    return payload


def parse_tool_arguments(call: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(call.get("call_id"), str) or not call.get("call_id"):
        raise ToolLoopError("function call lacks call_id")
    if call.get("name") not in TOOL_NAMES:
        raise ToolLoopError(f"function call has non-whitelisted name {call.get('name')!r}")
    arguments = call.get("arguments")
    if not isinstance(arguments, str):
        raise ToolLoopError("function call arguments must be a JSON string")
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ToolLoopError(f"function call arguments are incomplete JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ToolLoopError("function call arguments must be a JSON object")
    return parsed


def execute_tool_calls(calls: list[dict[str, Any]], engine: ReadOnlyQueryEngine, budget: ToolLoopBudget) -> list[dict[str, Any]]:
    call_ids = [call.get("call_id") for call in calls]
    if len(call_ids) != len(set(call_ids)):
        raise ToolLoopError("duplicate function call_id")
    budget.check_tool_batch(len(calls))
    results = []
    for call in calls:
        budget.start_tool_call()
        record = {"call_id": call.get("call_id"), "name": call.get("name"), "arguments": call.get("arguments")}
        try:
            arguments = parse_tool_arguments(call)
            schema = next(
                tool.get("parameters") for tool in TOOLS_SCHEMA if tool.get("name") == call["name"]
            )
            schema_errors = sorted(
                Draft7Validator(schema).iter_errors(arguments),
                key=lambda error: list(error.path),
            )
            if schema_errors:
                raise ToolLoopError(
                    "invalid function arguments: "
                    + "; ".join(
                        f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
                        for error in schema_errors
                    )
                )
            result = engine.execute(call["name"], arguments)
            record.update({"status": "EXECUTED", "result": result})
            budget.tool_calls_executed += 1
        except Exception as exc:
            record.update({
                "status": "INVALID_NOT_EXECUTED",
                "result": {"status": "ERROR", "error": str(exc)},
            })
        results.append(record)
    return results


def build_tool_continuation_payload(
    base_payload: dict[str, Any],
    calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = copy.deepcopy(base_payload)
    if len({call.get("call_id") for call in calls}) != len(calls):
        raise ToolLoopError("duplicate function call_id")
    result_by_call = {row.get("call_id"): row for row in tool_results}
    if {call.get("call_id") for call in calls} != set(result_by_call):
        raise ToolLoopError("tool result call_ids do not exactly match function calls")
    input_items = []
    for call in calls:
        result = result_by_call[call["call_id"]]
        input_items.extend((
            {
                "type": "function_call",
                "call_id": call["call_id"],
                "name": call["name"],
                "arguments": call["arguments"],
            },
            {
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": json.dumps(result.get("result"), ensure_ascii=False, separators=(",", ":")),
            },
        ))
    payload["input"] = payload.get("input", []) + input_items
    errors = validate_tool_request(payload)
    if errors:
        raise ToolLoopError("invalid tool continuation: " + ", ".join(errors))
    return payload


def request_summary(payload: dict[str, Any], phase: str) -> dict[str, Any]:
    return {
        "phase": phase,
        "input_item_count": len(payload.get("input") or []),
        "input_roles_types": [
            {"role": item.get("role"), "type": item.get("type")}
            for item in payload.get("input") or []
        ],
        "tool_count": len(payload.get("tools") or []),
        "tool_names": [tool.get("name") for tool in payload.get("tools") or []],
        "previous_response_id": payload.get("previous_response_id"),
        "model": payload.get("model"),
        "endpoint_field": "unchanged",
    }


def validate_final_operational_plan(parsed: Any) -> list[str]:
    schema_errors = sorted(
        Draft7Validator(output_schema()).iter_errors(parsed),
        key=lambda error: list(error.path),
    )
    errors = [
        f"schema: {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in schema_errors
    ]
    errors.extend(validate_operational_plan_output(parsed, load(EVIDENCE_CONTEXT)))
    return errors


def run_mock_tool_session(
    payload: dict[str, Any],
    engine: ReadOnlyQueryEngine,
    stream_once: Callable[[dict[str, Any]], tuple[dict[str, Any], StreamAccumulator, bytes]],
    validate_plan: Callable[[Any], list[str]] | None = None,
) -> dict[str, Any]:
    budget = ToolLoopBudget()
    current_payload = copy.deepcopy(payload)
    model_results = []
    trajectories = []
    for _ in range(budget.max_model_requests):
        errors = validate_tool_request(current_payload)
        if errors:
            return {"status": "FAILED", "error": "invalid tool request", "errors": errors, "budget": budget.__dict__, "trajectories": trajectories}
        budget.start_model_request()
        try:
            envelope, accumulator, raw = stream_once(current_payload)
        except Exception as exc:
            model_results.append({"phase": "NETWORK_OR_TRANSPORT", "error": str(exc), "traceback": traceback.format_exc()})
            return {"status": "FAILED", "error": "model request failed", "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories}
        classification = accumulator.classify()
        calls = classification.get("function_calls") or []
        model_results.append({
            "phase": "TOOL_CALL" if classification.get("requires_tool_execution") else "FINAL_RESPONSE",
            "terminal_event": accumulator.terminal_event,
            "http_status": accumulator.http_status,
            "request_id": accumulator.request_id,
            "usage": (envelope or {}).get("usage"),
            "function_calls": classification.get("function_calls"),
            "response_bytes": len(raw),
        })
        if accumulator.error or accumulator.terminal_event != "response.completed":
            return {"status": "FAILED", "error": accumulator.error or "NO_TERMINAL_EVENT", "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories}
        if classification.get("malformed_events"):
            return {
                "status": "FAILED", "error": "malformed function call events",
                "errors": classification.get("malformed_events"), "model_requests": model_results,
                "budget": budget.__dict__, "trajectories": trajectories,
            }
        if envelope.get("status") != "completed":
            return {"status": "FAILED", "error": "RESPONSE_STATUS_NOT_COMPLETED", "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories}
        if calls and not classification.get("function_calls_complete"):
            return {
                "status": "FAILED", "error": "function calls are not complete",
                "errors": classification.get("function_call_completion_statuses"),
                "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories,
            }
        if calls and classification.get("requires_tool_execution"):
            try:
                tool_results = execute_tool_calls(calls, engine, budget)
                continuation = build_tool_continuation_payload(current_payload, calls, tool_results)
            except Exception as exc:
                return {"status": "FAILED", "error": str(exc), "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories}
            trajectories.append({"request": request_summary(current_payload, "TOOL_QUERY"), "calls": calls, "tool_results": tool_results})
            current_payload = continuation
            continue
        if not calls:
            text_parts = []
            for item in envelope.get("output", []):
                if item.get("type") == "message" and item.get("role") == "assistant":
                    text_parts.extend(content.get("text", "") for content in item.get("content", []) if content.get("type") == "output_text")
            text = "".join(text_parts)
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                return {"status": "FAILED", "error": f"invalid final JSON: {exc}", "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories}
            plan_errors = validate_final_operational_plan(parsed)
            plan_errors.extend(validate_plan(parsed) if validate_plan else [])
            if plan_errors:
                return {"status": "FAILED", "error": "invalid final plan", "errors": plan_errors, "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories}
            trajectories.append({"request": request_summary(current_payload, "FINAL_PLAN"), "request_payload": current_payload, "function_calls": calls})
            return {
                "status": "COMPLETE",
                "operational_plan": parsed,
                "model_requests": model_results,
                "budget": budget.__dict__,
                "trajectories": trajectories,
                "provider_compatibility": "OFFLINE_MOCK_ONLY_PROVIDER_TOOL_COMPATIBILITY_UNVERIFIED",
            }
        return {"status": "FAILED", "error": "completed response mixed final message and tool calls", "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories}
    return {"status": "FAILED", "error": "request budget exhausted before final plan", "model_requests": model_results, "budget": budget.__dict__, "trajectories": trajectories}
