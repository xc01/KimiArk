from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EXPERIENCE_SCHEMA_VERSION = "KIMIARK_TACTICAL_EXPERIENCE_RECORD_V2"
REVISION_HYPOTHESIS_SCHEMA_VERSION = "KIMIARK_REVISION_HYPOTHESIS_V2"
EVENT_QUERY_SCHEMA_VERSION = "KIMIARK_EVENT_QUERY_V2"
BRANCH_SCHEMA_VERSION = "KIMIARK_TACTICAL_BRANCH_STATE_V2"

FAILURE_CATEGORIES = {
    "A_CONTRACT_INVALID": "CONTRACT_INVALID",
    "B_STATIC_CONFLICT": "STATIC_CONFLICT",
    "B_PROGRAM_OR_MECHANISM_UNKNOWN": "PROGRAM_OR_MECHANISM_UNKNOWN",
    "C_LEGAL_BATTLE_LOSS": "LEGAL_BATTLE_LOSS",
    "D_CURRENT_MODEL_WIN": "CURRENT_MODEL_WIN",
}


def classify_candidate(
    *, validation: dict[str, Any], static_conflicts: list[Any], simulation_gate: dict[str, Any]
) -> str:
    if validation.get("status") != "PASS":
        return "A_CONTRACT_INVALID"
    if static_conflicts:
        return "B_STATIC_CONFLICT"
    if simulation_gate.get("simulator_win") is True:
        return "D_CURRENT_MODEL_WIN"
    return "C_LEGAL_BATTLE_LOSS"


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
    if record.get("failure_category") not in set(FAILURE_CATEGORIES.values()):
        errors.append("invalid failure_category")
    if record.get("status") not in {
        "CANDIDATE_REFLECTION", "EVIDENCE_SUPPORTED", "STALE_MECHANICS", "INVALIDATED"
    }:
        errors.append("invalid status")
    if record.get("status") == "INVALIDATED" and not record.get("invalidation"):
        errors.append("INVALIDATED requires invalidation provenance")
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


def applicability_status(
    record: dict[str, Any], mechanics_version: str, game_data_sha256: str | None = None
) -> str:
    if record["status"] == "INVALIDATED":
        return "INVALIDATED"
    mechanics_current = record["mechanics_version"] == mechanics_version
    game_data_current = (
        game_data_sha256 is None or record.get("game_data_sha256") == game_data_sha256
    )
    if mechanics_current and game_data_current:
        return "CURRENT_MECHANICS"
    return "REQUIRES_REVALIDATION"


def retrieve_experiences(
    records: list[dict[str, Any]], *, stage_id: str, mechanics_version: str,
    failure_category: str | None = None, responsibility_tags: set[str] | None = None,
    operator_ids: set[str] | None = None, source_plan_id: str | None = None,
    game_data_sha256: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    tags = responsibility_tags or set()
    operators = operator_ids or set()
    scored: list[tuple[int, str, str, dict[str, Any]]] = []
    for record in records:
        if record["stage_id"] != stage_id or record["status"] == "INVALIDATED":
            continue
        if failure_category and record["failure_category"] != failure_category:
            continue
        score = 20 if source_plan_id and record["source_plan_id"] == source_plan_id else 0
        if failure_category and record["failure_category"] == failure_category:
            score += 5
        score += len(tags & set(record.get("responsibility_tags") or []))
        score += 2 * len(operators & set(record.get("relevant_operator_ids") or []))
        if score <= 0:
            if failure_category is not None or tags or operators or source_plan_id:
                continue
            score = 1
        candidate = dict(record)
        candidate["retrieval_score"] = score
        candidate["applicability_status"] = applicability_status(
            record, mechanics_version, game_data_sha256
        )
        scored.append((score, record["experience_id"], record["status"], candidate))
    scored.sort(key=lambda row: (-row[0], row[2] != "EVIDENCE_SUPPORTED", row[1], row[2]))
    unique: dict[str, dict[str, Any]] = {}
    for _, _, _, candidate in scored:
        unique[candidate["experience_id"]] = candidate
    return list(unique.values())[:max(0, limit)]


def add_revision_hypothesis_schema(schema: dict[str, Any]) -> dict[str, Any]:
    updated = dict(schema)
    properties = dict(updated.get("properties") or {})
    required = list(updated.get("required") or [])
    plans = properties.get("revised_operational_plans")
    if isinstance(plans, dict) and isinstance(plans.get("items"), dict):
        plan = dict(plans["items"])
        plan_required = list(plan.get("required") or [])
        if "battle_phases" not in plan_required:
            plan_required.append("battle_phases")
        plan["required"] = plan_required
        plan["properties"] = {
            **(plan.get("properties") or {}),
            "battle_phases": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": [
                        "phase_id", "goal", "start_condition", "completion_condition",
                        "responsibilities", "survival_dependencies", "handoff_requirements",
                        "failure_effect_on_later_phases",
                    ],
                    "properties": {
                        "phase_id": {"type": "string", "minLength": 1},
                        "goal": {"type": "string", "minLength": 5},
                        "start_condition": {"type": "string", "minLength": 5},
                        "completion_condition": {"type": "string", "minLength": 5},
                        "responsibilities": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 5}},
                        "survival_dependencies": {"type": "array", "items": {"type": "string", "minLength": 5}},
                        "handoff_requirements": {"type": "array", "items": {"type": "string", "minLength": 5}},
                        "failure_effect_on_later_phases": {"type": "string", "minLength": 5},
                    },
                },
            },
        }
        plans["items"] = plan
        properties["revised_operational_plans"] = plans
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
                "type": "array", "minItems": 1, "items": {"type": "string", "minLength": 10}
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
    updated = dict(updated)
    if "revision_hypothesis" not in required:
        required.append("revision_hypothesis")
    updated["required"] = required
    return updated


EVENT_ALIASES = {"ENEMY_BLOCKED": "BLOCK"}
OBSERVED_EVENT_TYPES = {
    "BLOCK", "UNBLOCK", "DAMAGE", "HEAL", "DEPLOY", "RETREAT", "SPAWN",
    "ENEMY_DEATH", "OPERATOR_DEATH", "ENEMY_LEAK", "OBJECTIVE_FAILURE",
    "ENEMY_ABILITY_START", "ENEMY_ABILITY_HIT", "PROTECTED_TARGET_REACHED",
    "SKILL_ACTIVATE", "SKILL_END", "DEVICE_DAMAGE", "DEVICE_DESTROYED",
    "PROJECTILE_BORN",
}


def normalize_event_query(expected: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(expected, dict):
        return {"status": "INVALID_QUERY", "reason": "QUERY_NOT_OBJECT"}
    required = {"event_type", "source_id", "target_id", "earliest_frame", "latest_frame"}
    if required - set(expected):
        return {"status": "INVALID_QUERY", "reason": "QUERY_MISSING_FIELDS", "missing": sorted(required - set(expected))}
    event_type = expected["event_type"]
    if not isinstance(event_type, str) or not event_type:
        return {"status": "INVALID_QUERY", "reason": "INVALID_EVENT_TYPE"}
    earliest, latest = expected["earliest_frame"], expected["latest_frame"]
    if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in (earliest, latest)):
        return {"status": "INVALID_QUERY", "reason": "INVALID_FRAME_WINDOW"}
    if earliest > latest:
        return {"status": "INVALID_QUERY", "reason": "REVERSED_FRAME_WINDOW"}
    for key in ("source_id", "target_id"):
        if expected[key] is not None and not isinstance(expected[key], str):
            return {"status": "INVALID_QUERY", "reason": f"INVALID_{key.upper()}"}
    result = {**expected, "event_type": EVENT_ALIASES.get(event_type, event_type), "event_type_declared": event_type}
    if result["event_type"] not in OBSERVED_EVENT_TYPES:
        return {**result, "status": "INVALID_QUERY", "reason": "EVENT_TYPE_NOT_DECLARED_SUPPORTED"}
    if result["event_type"] == "OPERATOR_DEATH" and not isinstance(result.get("source_id"), str):
        return {**result, "status": "INVALID_QUERY", "reason": "OPERATOR_DEATH_REQUIRES_SOURCE_OPERATOR"}
    if result["event_type"] == "OPERATOR_DEATH" and result.get("target_id") is not None:
        return {**result, "status": "INVALID_QUERY", "reason": "OPERATOR_DEATH_TARGET_MUST_BE_NULL"}
    return {**result, "status": "VALID_QUERY"}


def _event_matches(event: dict[str, Any], expected: dict[str, Any]) -> bool:
    if event.get("event_type") != expected.get("event_type"):
        return False
    if expected.get("event_type") in {"DEPLOY", "RETREAT", "SKILL_ACTIVATE"}:
        details = event.get("details")
        if isinstance(details, dict) and details.get("legal") is False:
            return False
    for key in ("source_id", "target_id"):
        if expected.get(key) is not None and event.get(key) != expected[key]:
            return False
    frame = event.get("frame")
    return isinstance(frame, int) and not isinstance(frame, bool) and expected["earliest_frame"] <= frame <= expected["latest_frame"]


def evaluate_revision_hypothesis(
    parsed: dict[str, Any], events: list[dict[str, Any]] | dict[str, Any],
    *, observation_complete: bool = True,
) -> dict[str, Any]:
    hypothesis = parsed.get("revision_hypothesis") or {}
    query = normalize_event_query(hypothesis.get("expected_first_observable_event"))
    if query["status"] != "VALID_QUERY":
        return {"status": query["status"], "reason": query.get("reason"), "query": query}
    if not isinstance(events, list):
        return {"status": "UNKNOWN", "reason": "EVENTS_NOT_ARRAY", "query": query}
    matches = [event for event in events if _event_matches(event, query)]
    observed_status = "VERIFIED" if matches else "EVENT_NOT_OBSERVED" if observation_complete else "UNKNOWN"
    result = {
        "status": observed_status,
        "matches": matches[:3],
        "query": query,
        "observation_complete": observation_complete,
        "interpretation": {
            "VERIFIED": "The declared observable occurred; the full tactical hypothesis is not thereby proven.",
            "EVENT_NOT_OBSERVED": "No matching event was observed over the complete declared window.",
            "UNKNOWN": "The event log does not establish coverage of the complete declared window.",
            "INVALID_QUERY": "The event prediction cannot be evaluated under the declared protocol.",
            }[observed_status],
    }
    if not observation_complete and not matches:
        result["status"] = "UNKNOWN"
    return result


def extract_operational_plan_id(plan_object: dict[str, Any] | None) -> str | None:
    if not isinstance(plan_object, dict):
        return None
    candidate = plan_object
    plans = plan_object.get("revised_operational_plans")
    if isinstance(plans, list) and len(plans) == 1 and isinstance(plans[0], dict):
        candidate = plans[0]
    value = candidate.get("operational_plan_id")
    return value if isinstance(value, str) and value else None


def extract_parent_plan_id(plan_object: dict[str, Any] | None) -> str | None:
    if not isinstance(plan_object, dict):
        return None
    candidate = plan_object
    root_revision = (
        plan_object.get("revision_hypothesis")
        if isinstance(plan_object.get("revision_hypothesis"), dict)
        else {}
    )
    plans = plan_object.get("revised_operational_plans")
    if isinstance(plans, list) and len(plans) == 1 and isinstance(plans[0], dict):
        candidate = plans[0]
    revision = candidate.get("revision_hypothesis") if isinstance(candidate.get("revision_hypothesis"), dict) else {}
    value = candidate.get("parent_plan_id") or revision.get("parent_plan_id") or root_revision.get("parent_plan_id")
    return value if isinstance(value, str) and value else None


def extract_declared_parent_plan_id(parsed: dict[str, Any] | None) -> str | None:
    if not isinstance(parsed, dict):
        return None
    root_revision = parsed.get("revision_hypothesis") if isinstance(parsed.get("revision_hypothesis"), dict) else {}
    root_parent = root_revision.get("parent_plan_id")
    if isinstance(root_parent, str) and root_parent:
        return root_parent
    plans = parsed.get("revised_operational_plans")
    if isinstance(plans, list) and len(plans) == 1:
        return extract_parent_plan_id(plans[0])
    return extract_parent_plan_id(parsed)


def objective_scope(
    result: dict[str, Any], *, expected_protected_target_count: int | None = None
) -> dict[str, Any]:
    expected_protected_target_count = (
        result.get("expected_protected_target_count")
        if expected_protected_target_count is None else expected_protected_target_count
    )
    leaks = result.get("enemies_leaked")
    deaths = result.get("protected_target_deaths")
    reached = result.get("protected_targets_reached")
    if expected_protected_target_count is None:
        protected_targets_all_reached = None
        perfect = None
    else:
        protected_targets_all_reached = reached == expected_protected_target_count
        perfect = bool(result.get("win")) and leaks == 0 and deaths == 0 and protected_targets_all_reached
    return {
        "win": bool(result.get("win")),
        "zero_leaks": leaks == 0,
        "protected_targets_zero_deaths": deaths == 0,
        "expected_protected_target_count": expected_protected_target_count,
        "protected_targets_all_reached": protected_targets_all_reached,
        "perfect": perfect,
    }


def _candidate_context(candidate: dict[str, Any]) -> tuple[Any, ...]:
    objective_scope = candidate.get("objective_scope") if isinstance(candidate.get("objective_scope"), dict) else {}
    return candidate.get("stage_id"), candidate.get("mechanics_version"), objective_scope.get("objective_key", "PROJECT_HARD_WIN")


def _battle_loss_rank(candidate: dict[str, Any]) -> tuple[Any, ...]:
    result = candidate.get("result") or {}
    return (
        result.get("enemies_leaked") if isinstance(result.get("enemies_leaked"), int) else 2**31,
        result.get("protected_target_deaths") if isinstance(result.get("protected_target_deaths"), int) else 2**31,
        result.get("operator_deaths") if isinstance(result.get("operator_deaths"), int) else 2**31,
        candidate.get("action_count") if isinstance(candidate.get("action_count"), int) else None,
        candidate.get("candidate_id", ""),
    )


def update_branch_state(state: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    required = {
        "candidate_id", "parent_plan_id", "operational_plan_id", "classification",
        "stage_id", "mechanics_version", "objective_scope", "revision_hypothesis",
    }
    missing = required - set(candidate)
    if missing:
        raise ValueError(f"candidate missing fields: {sorted(missing)}")
    if candidate["classification"] not in FAILURE_CATEGORIES:
        raise ValueError("invalid candidate classification")
    updated = json.loads(json.dumps(state, ensure_ascii=False))
    updated["schema_version"] = BRANCH_SCHEMA_VERSION
    updated.setdefault("frozen_baselines", {})
    updated.setdefault("current_best", None)
    updated.setdefault("exploration", None)
    updated.setdefault("candidates", [])
    updated["candidates"].append(candidate)
    updated["last_updated_candidate_id"] = candidate["candidate_id"]
    if candidate["classification"] == "D_CURRENT_MODEL_WIN":
        current = updated.get("current_best")
        if current is not None and _candidate_context(current) != _candidate_context(candidate):
            updated.setdefault("comparison_conflicts", []).append({
                "reason": "INCOMPATIBLE_CONTEXT_FOR_CURRENT_BEST",
                "kept_candidate_id": current["candidate_id"],
                "rejected_candidate_id": candidate["candidate_id"],
            })
        elif current is None:
            updated["current_best"] = candidate
        else:
            old_scope, new_scope = objective_scope(current.get("result") or {}), objective_scope(candidate.get("result") or {})
            old_action_count = current.get("action_count")
            new_action_count = candidate.get("action_count")
            if (
                old_scope["perfect"] is True and new_scope["perfect"] is not True
            ) or (old_scope["perfect"] is not True and new_scope["perfect"] is True):
                updated["current_best"] = candidate if new_scope["perfect"] is True else current
            elif not isinstance(old_action_count, int) or not isinstance(new_action_count, int):
                updated.setdefault("comparison_conflicts", []).append({
                    "reason": "MISSING_ACTION_COUNT_FOR_WIN_RANKING",
                    "kept_candidate_id": current["candidate_id"],
                    "rejected_candidate_id": candidate["candidate_id"],
                })
            else:
                old_key = (
                    old_scope["perfect"] is True, old_scope["win"], old_action_count,
                    current["candidate_id"],
                )
                new_key = (
                    new_scope["perfect"] is True, new_scope["win"], new_action_count,
                    candidate["candidate_id"],
                )
                updated["current_best"] = candidate if new_key < old_key else current
    elif candidate["classification"] == "C_LEGAL_BATTLE_LOSS":
        current = updated.get("exploration")
        if current is None or _candidate_context(current) != _candidate_context(candidate):
            updated["exploration"] = candidate
        elif _battle_loss_rank(candidate) < _battle_loss_rank(current):
            updated["exploration"] = candidate
    else:
        updated.setdefault("comparison_conflicts", []).append({
            "reason": "CANDIDATE_NOT_ELIGIBLE_FOR_BRANCH_PROMOTION",
            "classification": candidate["classification"],
            "candidate_id": candidate["candidate_id"],
        })
    return updated
