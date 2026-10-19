from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EXPERIENCE_SCHEMA_VERSION = "KIMIARK_TACTICAL_EXPERIENCE_RECORD_V1"
REVISION_HYPOTHESIS_SCHEMA_VERSION = "KIMIARK_REVISION_HYPOTHESIS_V1"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_experience_record(record: dict[str, Any]) -> list[str]:
    required = {
        "experience_id", "stage_id", "mechanics_version", "code_commit_sha256",
        "game_data_sha256", "source_plan_id", "source_artifact_sha256",
        "failure_category", "status", "applicable_conditions", "verified_events",
        "evidence_paths", "supported_hypotheses", "refuted_hypotheses", "unproven",
    }
    errors = [f"missing {field}" for field in sorted(required - set(record))]
    if record.get("failure_category") not in {
        "CONTRACT_INVALID", "PROGRAM_OR_MECHANISM_UNKNOWN", "LEGAL_BATTLE_LOSS", "CURRENT_MODEL_WIN"
    }:
        errors.append("invalid failure_category")
    if record.get("status") not in {
        "CANDIDATE_REFLECTION", "EVIDENCE_SUPPORTED", "STALE_MECHANICS", "INVALIDATED"
    }:
        errors.append("invalid status")
    for field in ("applicable_conditions", "verified_events", "evidence_paths",
                  "supported_hypotheses", "refuted_hypotheses", "unproven"):
        if not isinstance(record.get(field), list):
            errors.append(f"{field} must be an array")
    return errors


def load_experience_records(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("experience store must contain records")
    invalid = [record.get("experience_id", "<missing>") for record in records if validate_experience_record(record)]
    if invalid:
        raise ValueError(f"invalid experience records: {invalid}")
    return records


def applicability_status(record: dict[str, Any], mechanics_version: str) -> str:
    if record.get("mechanics_version") == mechanics_version:
        return "CURRENT_MECHANICS"
    return "REQUIRES_REVALIDATION"


def retrieve_experiences(
    records: list[dict[str, Any]], *, stage_id: str, mechanics_version: str,
    failure_category: str | None = None, responsibility_tags: set[str] | None = None,
    operator_ids: set[str] | None = None, limit: int = 3,
) -> list[dict[str, Any]]:
    tags = responsibility_tags or set()
    operators = operator_ids or set()
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for record in records:
        if record.get("stage_id") != stage_id:
            continue
        if failure_category and record.get("failure_category") != failure_category:
            continue
        score = 0
        if failure_category and record.get("failure_category") == failure_category:
            score += 5
        score += len(tags & set(record.get("responsibility_tags") or []))
        score += 2 * len(operators & set(record.get("relevant_operator_ids") or []))
        if score <= 0:
            if failure_category is not None or tags or operators:
                continue
            score = 1
        candidate = dict(record)
        candidate["retrieval_score"] = score
        candidate["applicability_status"] = applicability_status(record, mechanics_version)
        scored.append((score, record["experience_id"], candidate))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in scored[:max(0, limit)]]


def add_revision_hypothesis_schema(schema: dict[str, Any]) -> dict[str, Any]:
    updated = dict(schema)
    properties = dict(updated.get("properties") or {})
    required = list(updated.get("required") or [])
    properties["revision_hypothesis"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "hypothesis_id", "parent_plan_id", "operational_plan_id",
            "referenced_experience_ids", "tactical_hypothesis",
            "changed_responsibilities", "expected_first_observable_event",
            "if_expected_event_absent",
        ],
        "properties": {
            "hypothesis_id": {"type": "string", "minLength": 1},
            "parent_plan_id": {"type": "string", "minLength": 1},
            "operational_plan_id": {"type": "string", "minLength": 1},
            "referenced_experience_ids": {
                "type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}
            },
            "tactical_hypothesis": {"type": "string", "minLength": 20},
            "changed_responsibilities": {
                "type": "array", "minItems": 1,
                "items": {"type": "string", "minLength": 10},
            },
            "expected_first_observable_event": {
                "type": "object", "additionalProperties": False,
                "required": ["event_type", "source_id", "target_id", "earliest_frame", "latest_frame"],
                "properties": {
                    "event_type": {"type": "string", "minLength": 1},
                    "source_id": {"type": ["string", "null"]},
                    "target_id": {"type": ["string", "null"]},
                    "earliest_frame": {"type": "integer", "minimum": 0},
                    "latest_frame": {"type": "integer", "minimum": 0},
                },
            },
            "if_expected_event_absent": {"type": "string", "minLength": 20},
        },
    }
    updated["properties"] = properties
    if "revision_hypothesis" not in required:
        required.append("revision_hypothesis")
    updated["required"] = required
    return updated


def _event_matches(event: dict[str, Any], expected: dict[str, Any]) -> bool:
    if event.get("event_type") != expected.get("event_type"):
        return False
    for key in ("source_id", "target_id"):
        if expected.get(key) is not None and event.get(key) != expected[key]:
            return False
    frame = event.get("frame")
    return isinstance(frame, int) and expected["earliest_frame"] <= frame <= expected["latest_frame"]


def evaluate_revision_hypothesis(
    parsed: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, Any]:
    hypothesis = parsed.get("revision_hypothesis") or {}
    expected = hypothesis.get("expected_first_observable_event") or {}
    if not expected:
        return {"status": "UNKNOWN", "reason": "NO_EXPECTED_EVENT_DECLARED"}
    matches = [event for event in events if _event_matches(event, expected)]
    return {
        "status": "VERIFIED" if matches else "NOT_VERIFIED",
        "matches": matches[:3],
        "expected": expected,
    }


def classify_candidate(
    *, validation: dict[str, Any] | None, static_conflicts: list[Any] | None,
    simulation_gate: dict[str, Any] | None,
) -> str:
    if validation is None or validation.get("status") != "PASS":
        return "A_CONTRACT_INVALID"
    if static_conflicts:
        return "B_STATIC_CONFLICT"
    if simulation_gate is None:
        return "B_PIPELINE_INCOMPLETE"
    if simulation_gate.get("status") != "COMPLETED":
        return "B_PROGRAM_OR_MECHANISM_UNKNOWN"
    return "D_CURRENT_MODEL_WIN" if simulation_gate.get("simulator_win") else "C_LEGAL_BATTLE_LOSS"


def update_branch_state(
    state: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    required = {"candidate_id", "parent_plan_id", "operational_plan_id", "classification", "revision_hypothesis"}
    missing = required - set(candidate)
    if missing:
        raise ValueError(f"candidate missing fields: {sorted(missing)}")
    updated = json.loads(json.dumps(state, ensure_ascii=False))
    updated.setdefault("schema_version", "KIMIARK_TACTICAL_BRANCH_STATE_V1")
    updated.setdefault("frozen_baselines", {})
    updated.setdefault("current_best", None)
    updated.setdefault("exploration", None)
    updated.setdefault("candidates", [])
    updated["candidates"].append(candidate)
    if candidate["classification"] in {"D_CURRENT_MODEL_WIN", "C_LEGAL_BATTLE_LOSS"}:
        slot = "current_best" if candidate["classification"] == "D_CURRENT_MODEL_WIN" else "exploration"
        if candidate["classification"] == "C_LEGAL_BATTLE_LOSS" and updated.get("current_best") is None:
            updated["current_best"] = candidate
        else:
            updated[slot] = candidate
    updated["last_updated_candidate_id"] = candidate["candidate_id"]
    return updated
