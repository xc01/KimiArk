from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSEEvent:
    event: str
    data: Any
    sequence: int


@dataclass
class StreamAccumulator:
    events: list[SSEEvent] = field(default_factory=list)
    output_text: str = ""
    reasoning_text: str = ""
    output_item_types: list[str] = field(default_factory=list)
    terminal_event: str | None = None
    response_envelope: dict[str, Any] | None = None
    error: str | None = None
    malformed_events: list[str] = field(default_factory=list)
    function_calls: list[dict[str, Any]] = field(default_factory=list)
    function_calls_with_done_item: set[str] = field(default_factory=set)
    function_calls_with_done_arguments: set[str] = field(default_factory=set)
    http_status: int | None = None
    request_id: str | None = None

    def observe(self, event: SSEEvent) -> None:
        self.events.append(event)
        data = event.data if isinstance(event.data, dict) else {}
        response = data.get("response", data)
        if event.event == "response.created":
            self.response_envelope = response
        elif event.event == "response.output_item.added":
            item = data.get("item", {})
            item_type = item.get("type")
            if item_type and item_type not in self.output_item_types:
                self.output_item_types.append(item_type)
            if item_type == "function_call":
                call = {
                    "call_id": item.get("call_id"),
                    "name": item.get("name"),
                    "arguments": item.get("arguments", ""),
                    "status": item.get("status"),
                }
                item_id = item.get("item_id", item.get("id"))
                if item_id is not None:
                    call["item_id"] = item_id
                call["status"] = item.get("status")
                self.function_calls.append(call)
        elif event.event == "response.output_item.done":
            item = data.get("item") or {}
            if item.get("type") == "function_call":
                item_id = item.get("item_id", item.get("id"))
                call_id = item.get("call_id")
                calls = [
                    call for call in self.function_calls
                    if (item_id is not None and call.get("item_id") == item_id)
                    or call.get("call_id") == call_id
                ]
                if not calls:
                    self.malformed_events.append(f"function item done without added call {item_id or call_id}")
                else:
                    calls[0].update({
                        "call_id": item.get("call_id", calls[0].get("call_id")),
                        "name": item.get("name", calls[0].get("name")),
                        "arguments": item.get("arguments", calls[0].get("arguments", "")),
                        "status": item.get("status", "completed"),
                    })
                    if item_id is not None:
                        calls[0]["item_id"] = item_id
                    self.function_calls_with_done_item.add(item_id or call_id)
        elif event.event == "response.output_text.delta":
            self.output_text += data.get("delta", "")
        elif event.event == "response.output_text.done":
            if "text" in data:
                self.output_text = data["text"]
        elif event.event in {
            "response.reasoning_summary_text.delta",
            "response.reasoning_summary_text.done",
            "response.reasoning_text.delta",
            "response.reasoning_text.done",
        }:
            if "delta" in data:
                self.reasoning_text += data["delta"]
            elif "text" in data:
                self.reasoning_text = data["text"]
        elif event.event in {"response.completed", "response.incomplete", "response.failed"}:
            if self.terminal_event is not None:
                self.error = f"Multiple terminal SSE events: {self.terminal_event}, {event.event}"
                return
            self.terminal_event = event.event
            if response:
                self.response_envelope = response
            if event.event == "response.failed":
                self.error = json.dumps(data.get("response", {}).get("error", data.get("error", "")))
        elif event.event == "response.function_call_arguments.delta":
            call_id = data.get("call_id") or data.get("item_id")
            calls = [call for call in self.function_calls if call.get("call_id") == call_id or call.get("item_id") == call_id]
            if not calls:
                self.malformed_events.append(f"function argument delta without call {call_id}")
            else:
                calls[-1]["arguments"] += data.get("delta", "")
        elif event.event == "response.function_call_arguments.done":
            call_id = data.get("call_id") or data.get("item_id")
            calls = [call for call in self.function_calls if call.get("call_id") == call_id or call.get("item_id") == call_id]
            if not calls:
                self.malformed_events.append(f"function argument done without call {call_id}")
            elif "arguments" in data:
                final_arguments = data["arguments"]
                accumulated = calls[-1]["arguments"]
                if isinstance(accumulated, str) and accumulated and accumulated != final_arguments:
                    self.malformed_events.append(
                        f"function arguments done does not match accumulated arguments for {call_id}"
                    )
                calls[-1]["arguments"] = final_arguments
                self.function_calls_with_done_arguments.add(call_id)

    def classify(self) -> dict[str, Any]:
        envelope = self.response_envelope or {}
        assistant_items = [
            item
            for item in envelope.get("output", [])
            if item.get("type") == "message" and item.get("role") == "assistant"
        ]
        calls = list(self.function_calls)
        if not calls:
            calls = [
                {
                    **({"item_id": item["item_id"]} if item.get("item_id") is not None else {}),
                    "call_id": item.get("call_id"),
                    "name": item.get("name"),
                    "arguments": item.get("arguments", ""),
                    "status": item.get("status"),
                }
                for item in envelope.get("output", [])
                if item.get("type") == "function_call"
            ]
            self.function_calls = calls
        elif self.function_calls:
            final_items = [item for item in envelope.get("output", []) if item.get("type") == "function_call"]
            if not final_items:
                self.malformed_events.append("terminal response envelope lacks streamed function calls")
            else:
                matched_final_indexes: set[int] = set()
                for call in calls:
                    item_id = call.get("item_id")
                    final_index = next(
                        (index for index, item in enumerate(final_items) if index not in matched_final_indexes and (
                            (item_id is not None and item.get("item_id", item.get("id")) == item_id)
                            or call.get("call_id") == item.get("call_id")
                        )),
                        None,
                    )
                    if final_index is None:
                        self.malformed_events.append(f"final response lacks streamed function call {call.get('call_id')}")
                        continue
                    matched_final_indexes.add(final_index)
                    final_item = final_items[final_index]
                    for field_name in ("call_id", "name", "arguments"):
                        if call.get(field_name) != final_item.get(field_name):
                            self.malformed_events.append(
                                f"final function call {call.get('call_id')} {field_name} differs from stream"
                            )
                    if call.get("status") is None:
                        call["status"] = final_item.get("status")
                    elif final_item.get("status") != call.get("status"):
                        self.malformed_events.append(
                            f"final function call {call.get('call_id')} status differs from stream"
                        )
                if len(matched_final_indexes) != len(final_items):
                    self.malformed_events.append("final response contains function calls not present in stream")
        completed_calls = bool(calls) and all(call.get("status") == "completed" for call in calls)
        call_ids = [call.get("call_id") for call in calls]
        if len(call_ids) != len(set(call_ids)):
            self.malformed_events.append("duplicate function call_id")
        for call in calls:
            if not isinstance(call.get("call_id"), str) or not call["call_id"]:
                self.malformed_events.append("function call lacks call_id")
            if call.get("name") not in {"query_mechanic", "query_range_coverage", "check_timing_constraints"}:
                self.malformed_events.append(f"function call has non-whitelisted name {call.get('name')!r}")
            if not isinstance(call.get("arguments"), str) or not call["arguments"]:
                self.malformed_events.append("function call lacks arguments string")
        return {
            "terminal_event": self.terminal_event,
            "complete": (
                self.terminal_event == "response.completed"
                and bool(assistant_items)
                and bool(self.output_text.strip())
                and not completed_calls
            ),
            "assistant_message_present": bool(assistant_items),
            "final_output_text": self.output_text,
            "reasoning_text": self.reasoning_text,
            "output_item_types": self.output_item_types,
            "response_status": envelope.get("status"),
            "function_call_completion_statuses": [call.get("status") for call in calls],
            "function_calls_complete": bool(calls) and all(call.get("status") == "completed" for call in calls),
            "errors": [self.error] if self.error else [],
            "malformed_events": self.malformed_events,
            "function_calls": calls,
            "tool_round_complete": (
                self.terminal_event == "response.completed"
                and envelope.get("status") == "completed"
                and completed_calls
                and not self.error
            ),
            "requires_tool_execution": (
                self.terminal_event == "response.completed"
                and envelope.get("status") == "completed"
                and completed_calls
                and not self.error
            ),
        }


def parse_sse(payload: str) -> list[SSEEvent]:
    events: list[SSEEvent] = []
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")
    event_name = ""
    data_lines: list[str] = []
    sequence = 0
    for line in payload.splitlines():
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line == "":
            if data_lines or event_name:
                raw_data = "\n".join(data_lines)
                try:
                    data = json.loads(raw_data) if raw_data else {}
                except json.JSONDecodeError:
                    data = raw_data
                sequence += 1
                events.append(SSEEvent(event=event_name or "message", data=data, sequence=sequence))
            event_name = ""
            data_lines = []
    if data_lines or event_name:
        raw_data = "\n".join(data_lines)
        try:
            data = json.loads(raw_data) if raw_data else {}
        except json.JSONDecodeError:
            data = raw_data
        sequence += 1
        events.append(SSEEvent(event=event_name or "message", data=data, sequence=sequence))
    return events


def validate_tactical_request(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("previous_response_id") is not None:
        errors.append("PREVIOUS_RESPONSE_ID_FORBIDDEN")
    if payload.get("stream") is not True:
        errors.append("STREAM_TRUE_REQUIRED")
    tools = payload.get("tools") or []
    for index, item in enumerate(payload.get("input", [])):
        if not isinstance(item, dict):
            errors.append(f"INPUT_{index}_NOT_OBJECT")
            continue
        if tools and item.get("type") == "function_call":
            if not item.get("call_id"):
                errors.append(f"INPUT_{index}_FUNCTION_CALL_ID_REQUIRED")
            if not item.get("name"):
                errors.append(f"INPUT_{index}_FUNCTION_CALL_NAME_REQUIRED")
            if not isinstance(item.get("arguments"), str):
                errors.append(f"INPUT_{index}_FUNCTION_CALL_ARGUMENTS_REQUIRED")
            continue
        if tools and item.get("type") == "function_call_output":
            if not item.get("call_id"):
                errors.append(f"INPUT_{index}_FUNCTION_OUTPUT_CALL_ID_REQUIRED")
            if "output" not in item:
                errors.append(f"INPUT_{index}_FUNCTION_OUTPUT_REQUIRED")
            continue
        if item.get("role") != "user":
            errors.append(f"INPUT_{index}_ROLE_NOT_USER")
    return errors


def consume_stream(payload: str) -> StreamAccumulator:
    accumulator = StreamAccumulator()
    for event in parse_sse(payload):
        accumulator.observe(event)
    return accumulator


def extract_response_text(response: dict[str, Any]) -> tuple[str, list[str]]:
    if isinstance(response.get("output_text"), str):
        return response["output_text"], ["flat_output_text"]
    if isinstance(response.get("output_text"), list):
        return "".join(
            item if isinstance(item, str) else item.get("text", "")
            for item in response["output_text"]
        ), ["flat_output_text_list"]
    text_parts: list[str] = []
    item_types: list[str] = []
    for item in response.get("output", []):
        item_types.append(item.get("type", "UNKNOWN"))
        if item.get("type") == "message" and item.get("role") == "assistant":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text_parts.append(content.get("text", ""))
    return "".join(text_parts), item_types
