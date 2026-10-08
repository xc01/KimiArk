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
        elif event.event == "response.output_text.delta":
            self.output_text += data.get("delta", "")
        elif event.event == "response.output_text.done":
            self.output_text = data.get("text", self.output_text)
        elif event.event in {
            "response.reasoning_summary_text.delta",
            "response.reasoning_summary_text.done",
            "response.reasoning_text.delta",
            "response.reasoning_text.done",
        }:
            self.reasoning_text += data.get("delta", data.get("text", ""))
        elif event.event in {"response.completed", "response.incomplete", "response.failed"}:
            if self.terminal_event is not None:
                self.error = f"Multiple terminal SSE events: {self.terminal_event}, {event.event}"
                return
            self.terminal_event = event.event
            self.response_envelope = response
            if event.event == "response.failed":
                self.error = json.dumps(data.get("response", {}).get("error", data.get("error", "")))

    def classify(self) -> dict[str, Any]:
        envelope = self.response_envelope or {}
        assistant_items = [
            item
            for item in envelope.get("output", [])
            if item.get("type") == "message" and item.get("role") == "assistant"
        ]
        return {
            "terminal_event": self.terminal_event,
            "complete": self.terminal_event == "response.completed"
            and bool(assistant_items)
            and bool(self.output_text.strip()),
            "assistant_message_present": bool(assistant_items),
            "final_output_text": self.output_text,
            "reasoning_text": self.reasoning_text,
            "output_item_types": self.output_item_types,
            "response_status": envelope.get("status"),
            "errors": [self.error] if self.error else [],
            "malformed_events": self.malformed_events,
        }


def parse_sse(payload: str) -> list[SSEEvent]:
    events: list[SSEEvent] = []
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
    for index, item in enumerate(payload.get("input", [])):
        if not isinstance(item, dict):
            errors.append(f"INPUT_{index}_NOT_OBJECT")
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
