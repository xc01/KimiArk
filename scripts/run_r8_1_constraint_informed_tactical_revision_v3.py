from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kimi_responses_transport import (  # noqa: E402
    StreamAccumulator,
    SSEEvent,
    extract_response_text,
    validate_tactical_request,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_constraint_informed_revision_v3"
AUDIT = ROOT / "output/r8_1_operational_feasibility_unsat_core_audit_v1"
RECOVER = ROOT / "output/r8_1_revision_numeric_grounding_recovery_v1"
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
AFFORDANCES = ROOT / "output/r8_1_llm_operationalization_v1/deterministic_affordance_catalog.json"
CAUSAL = ROOT / "output/r8_1_revised_search_coverage_causal_audit_v1/first_failure_causal_analysis.json"
BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/responses"
MODEL = "kimi-k3"
MAX_OUTPUT_TOKENS = 128000
TIMEOUT_SECONDS = 900
MECHANICS = "m18.9-stage-device-runtime-v1"
STAGE = "main_08-01"


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def write(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_text(name: str, value: str) -> None:
    (OUT / name).write_text(value, encoding="utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_path(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_sse_line(raw: str, event: str | None, data_lines: list[str]) -> tuple[SSEEvent | None, str | None]:
    if raw.startswith("event:"):
        return None, raw[6:].strip()
    if raw.startswith("data:"):
        data_lines.append(raw[5:].strip())
        return None, event
    if raw.strip():
        return None, event
    if not data_lines and not event:
        return None, None
    raw_data = "\n".join(data_lines)
    try:
        data = json.loads(raw_data) if raw_data else {}
    except json.JSONDecodeError:
        data = {"malformed_data": raw_data}
    return SSEEvent(event=event or "message", data=data, sequence=0), None


def stream_once(payload: dict[str, Any]) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
    validation_errors = validate_tactical_request(payload)
    if validation_errors:
        raise RuntimeError("TRANSPORT_REQUEST_VALIDATION_FAILED:" + ",".join(validation_errors))
    if (OUT / "llm_raw_response.txt").is_file():
        raise RuntimeError("LLM_RAW_RESPONSE_ALREADY_EXISTS_SINGLE_CALL_POLICY")
    api_key = os.environ.get("ARK_API_KEY_agent")
    if not api_key:
        raise RuntimeError("MISSING_CREDENTIAL_ENVIRONMENT")
    body = json.dumps(payload, ensure_ascii=False).encode()
    write("llm_request.json", payload)
    request = urllib.request.Request(
        BASE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    started = time.time()
    raw_chunks: list[bytes] = []
    accumulator = StreamAccumulator()
    current_event: str | None = None
    data_lines: list[str] = []
    sequence = 0
    http_status = None
    request_id = None
    transport_error = None
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            http_status = response.status
            request_id = response.headers.get("x-request-id")
            for raw_line in response:
                raw_bytes = raw_line if isinstance(raw_line, bytes) else str(raw_line).encode()
                raw_chunks.append(raw_bytes)
                text_line = raw_bytes.decode(errors="replace").rstrip("\r\n")
                parsed, current_event = parse_sse_line(text_line, current_event, data_lines)
                if parsed is None:
                    continue
                sequence += 1
                parsed.sequence = sequence
                accumulator.observe(parsed)
                data_lines = []
    except urllib.error.HTTPError as exc:
        http_status = exc.code
        request_id = exc.headers.get("x-request-id")
        raw_chunks.append(exc.read())
        transport_error = f"HTTPError:{exc.code}"
    except Exception as exc:
        transport_error = f"{type(exc).__name__}:{exc}"
    raw_http = b"".join(raw_chunks)
    write_text("llm_raw_response.txt", raw_http.decode(errors="replace"))
    envelope = accumulator.response_envelope or {}
    result = {
        "safe_http_status": http_status,
        "request_id": request_id,
        "response_id": envelope.get("id"),
        "response_status": envelope.get("status"),
        "terminal_event": accumulator.terminal_event,
        "transport_error": transport_error,
        "parser_errors": accumulator.classify()["errors"],
        "event_count": len(accumulator.events),
        "raw_http_bytes": len(raw_http),
        "raw_http_sha256": sha_bytes(raw_http),
        "elapsed_seconds": time.time() - started,
        "idle_timeout_seconds": TIMEOUT_SECONDS,
        "automatic_continuation_attempted": False,
    }
    write("llm_http_result.json", result)
    if envelope:
        write("llm_response_envelope.json", envelope)
    return result, accumulator, raw_http


def completion_diagnostics(result: dict[str, Any], accumulator: StreamAccumulator) -> dict[str, Any]:
    envelope = accumulator.response_envelope or {}
    output_text, item_types = extract_response_text(envelope)
    assistant_present = any(
        item.get("type") == "message" and item.get("role") == "assistant"
        for item in envelope.get("output", [])
    )
    json_valid = False
    json_error = None
    parsed = None
    if output_text:
        try:
            parsed = json.loads(output_text)
            json_valid = True
        except Exception as exc:
            json_error = str(exc)
    completed = (
        result.get("transport_error") is None
        and accumulator.terminal_event == "response.completed"
        and not accumulator.classify()["errors"]
        and envelope.get("status") == "completed"
        and assistant_present
        and bool(output_text.strip())
        and json_valid
    )
    return {
        "successful_completion": completed,
        "terminal_status": envelope.get("status") or result.get("response_status"),
        "terminal_event": accumulator.terminal_event,
        "assistant_message_present": assistant_present,
        "output_item_types": item_types,
        "output_text_bytes": len(output_text.encode()),
        "output_json_valid": json_valid,
        "output_json_error": json_error,
        "incomplete_details": envelope.get("incomplete_details"),
        "provider_error": envelope.get("error"),
        "usage": envelope.get("usage"),
        "max_output_tokens": envelope.get("max_output_tokens"),
        "accumulated_delta_matches_envelope": accumulator.output_text == output_text,
        "reasoning_delta_bytes": len(accumulator.reasoning_text.encode()),
    }


def plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "operational_plan_id": plan.get("operational_plan_id"),
        "parent_revised_hypothesis_id": plan.get("parent_revised_hypothesis_id"),
        "tactical_thesis": plan.get("tactical_thesis"),
        "opening_structure": plan.get("opening_structure"),
        "corridor_responsibilities": plan.get("corridor_responsibilities"),
        "pressure_window_responsibilities": plan.get("pressure_window_responsibilities"),
        "formation_transitions": plan.get("formation_transitions"),
        "operational_invariants": plan.get("operational_invariants"),
        "allowed_substitutions": plan.get("allowed_substitutions"),
        "forbidden_substitutions": plan.get("forbidden_substitutions"),
    }


def experience_memory() -> dict[str, Any]:
    feedback = load(AUDIT / "future_llm_feasibility_feedback.json")
    plans = load(RECOVER / "normalized_revised_operational_plans.json")["revised_operational_plans"]
    plan_by_id = {plan["operational_plan_id"]: plan for plan in plans}
    records = []
    for index, row in enumerate(feedback["records"], start=1):
        plan_id = row["operational_plan_id"]
        plan = plan_by_id[plan_id]
        records.append(
            {
                "experience_id": f"EXP-{index:03d}-{plan_id.split('-')[1]}",
                "experience_scope": "STAGE_SPECIFIC_EXPERIENCE",
                "stage_id": STAGE,
                "mechanics_version": MECHANICS,
                "source_plan_id": plan_id,
                "failed_tactical_assumption": row["failed_tactical_invariant"],
                "conflicting_constraints": row["conflicting_requirements"],
                "deadline": row["deadline_frame"],
                "minimum_required_cost": row["minimum_cost"],
                "available_dp_bound": row["available_dp"],
                "deficit": row["deficit"],
                "evidence_sources": [
                    "output/r8_1_operational_feasibility_unsat_core_audit_v1/optimistic_dp_feasibility_bounds.json",
                    "output/r8_1_operational_feasibility_unsat_core_audit_v1/unsat_core_certificates.json",
                    "output/r8_1_operational_feasibility_unsat_core_audit_v1/exact_dp_ledgers.json",
                ],
                "applicability_conditions": [
                    "The same mandatory responsibility set and capability distinctions apply.",
                    "Distinct simultaneous operators are required.",
                    "The deadline and DP rules remain unchanged.",
                    "No additional source-backed DP-generation mechanism is assumed.",
                ],
                "generalizable_lesson": (
                    f"Under these plan-specific requirements, the mandatory prefix costs at least {row['minimum_cost']} DP "
                    f"while only {row['available_dp']} DP is safely available by frame {row['deadline_frame']}; "
                    "the conflict is conditional, not a universal prohibition on similar formations."
                ),
                "possible_tactical_revision_dimensions": [
                    "Mandatory versus conditional responsibilities",
                    "Temporal sequencing",
                    "Resource sharing or role consolidation if the plan explicitly authorizes it",
                    "Formation transition ordering",
                    "Different economy-generation intent",
                    "Route-specific triage",
                ],
                "confidence": "HIGH_FOR_SPECIFIC_CONSTRAINT_SET",
                "limitations": [
                    "This is a conflicting constraint set, not a proven minimal UNSAT core.",
                    "It does not prove that the strategic objective is globally impossible.",
                    "A materially different responsibility structure may be feasible.",
                ],
                "original_tactical_thesis": plan.get("tactical_thesis"),
            }
        )
    causal = load(CAUSAL)
    records.append(
        {
            "experience_id": "EXP-006-EARLY-SURVIVAL",
            "experience_scope": "STAGE_SPECIFIC_EXPERIENCE",
            "stage_id": STAGE,
            "mechanics_version": MECHANICS,
            "source_plan_id": "R8_1_HISTORICAL_SEARCH_BEST_CLUSTER",
            "failed_tactical_assumption": "Opening frontline survival alone was treated as sufficient before ranged pocket-fire responsibility was established.",
            "conflicting_constraints": [
                "char_123_fang died at frame 654",
                "enemy_1107_uoffcr leaked on route-3 at frame 678",
                "POCKET_FIRE responsibility was not established",
            ],
            "deadline": 678,
            "minimum_required_cost": None,
            "available_dp_bound": None,
            "deficit": None,
            "evidence_sources": [
                "output/r8_1_revised_search_coverage_causal_audit_v1/first_failure_causal_analysis.json",
                "output/r8_1_revised_search_coverage_causal_audit_v1/c01_frame678_event_trace.json",
            ],
            "applicability_conditions": [
                "A durable melee unit is the only established C01/route-3 control.",
                "Ranged damage or an equivalent kill mechanism is not established before the enemy can kill that unit.",
            ],
            "generalizable_lesson": (
                "Early survival must verify the handoff from blocking control to damage or an equivalent route-neutralizing mechanism; "
                "deployment of the blocker alone does not establish pocket-fire responsibility."
            ),
            "possible_tactical_revision_dimensions": [
                "Earlier damage establishment",
                "Temporary damage role",
                "Different blocking durability",
                "Route-specific control",
                "Different pocket-fire concept",
            ],
            "confidence": "HIGH_FOR_OBSERVED_TRACE",
            "limitations": [
                "This does not require every plan to reproduce the same pocket-fire tactic.",
                "It is one observed failure trace, not a global tactical rule.",
            ],
        }
    )
    return {
        "schema_version": "R8_1_FEASIBILITY_EXPERIENCE_MEMORY_V1",
        "stage_id": STAGE,
        "mechanics_version": MECHANICS,
        "knowledge_policy": {
            "stage_specific_experience": "Conditional on the exact plan, deadline, capability, and economy evidence.",
            "general_mechanics_knowledge": "Only source-backed GameData and verified mechanics facts are factual.",
            "tactical_hypothesis": "Proposed revisions are unverified until deterministic validation and simulation.",
        },
        "previous_infeasible_plans": 5,
        "records": records,
    }


def reasoning_context() -> dict[str, Any]:
    memory = load(OUT / "feasibility_experience_memory.json")
    parsed = load(OUT / "llm_structured_output.json")
    prior_items: list[dict[str, Any]] = []
    for row in memory["records"]:
        policy = (
            "DO_NOT_REPEAT_UNCHANGED"
            if row["experience_id"] != "EXP-006-EARLY-SURVIVAL"
            else "DO_NOT_REPEAT_UNCHANGED_WITHOUT_EARLY_DAMAGE_OR_HANDOFF"
        )
        prior_items.append(
            {
                "experience_id": row["experience_id"],
                "source_plan_id": row["source_plan_id"],
                "policy": policy,
                "failed_assumption": row["failed_tactical_assumption"],
                "conditional_evidence": {
                    "deadline": row.get("deadline"),
                    "minimum_required_cost": row.get("minimum_required_cost"),
                    "available_dp_bound": row.get("available_dp_bound"),
                    "deficit": row.get("deficit"),
                },
                "applicability_conditions": row["applicability_conditions"],
                "generalizable_lesson": row["generalizable_lesson"],
                "may_reconsider_with_changed_conditions": row["possible_tactical_revision_dimensions"],
            }
        )
    revised = []
    for plan in parsed["revised_operational_plans"]:
        revised.append(
            {
                "operational_plan_id": plan["operational_plan_id"],
                "tactical_thesis": plan["tactical_thesis"],
                "changed_conflicting_assumptions": plan["changed_conflicting_assumptions"],
                "selected_affordance_ids": plan["selected_affordance_ids"],
                "verification_questions": plan["verifier_questions"],
                "status": "HYPOTHESIS_AWAITING_DETERMINISTIC_VERIFICATION",
            }
        )
    return {
        "schema_version": "R8_1_CONSTRAINT_INFORMED_REASONING_CONTEXT_V1",
        "stage_id": STAGE,
        "mechanics_version": MECHANICS,
        "knowledge_policy": {
            "STAGE_SPECIFIC_EXPERIENCE": "Conditional on the exact responsibilities, capability distinctions, timing and economy in its certificate.",
            "GENERAL_MECHANICS_KNOWLEDGE": "Only source-backed GameData and current-runtime mechanics may be treated as factual game rules.",
            "TACTICAL_HYPOTHESIS": "LLM formations and resource-sharing decisions require deterministic feasibility and simulation evidence.",
        },
        "prior_tactical_ideas": prior_items,
        "revised_tactical_hypotheses": revised,
        "remaining_tactical_choices": [
            "Mandatory versus conditional responsibility selection",
            "Sequential versus simultaneous establishment",
            "Explicitly authorized role sharing",
            "Formation-transition ordering",
            "Legal handoff or RETREAT structure",
            "Skill scheduling objective",
            "Route-specific resource concentration",
        ],
        "deterministic_boundary": "The deterministic verifier proves or rejects supplied constraints; it does not invent a replacement tactic.",
    }


def output_schema() -> dict[str, Any]:
    operational_plan = {
        "type": "object",
        "additionalProperties": True,
        "required": [
            "operational_plan_id",
            "parent_hypothesis_id",
            "tactical_thesis",
            "changed_conflicting_assumptions",
            "opening_responsibilities",
            "battle_phases",
            "corridor_responsibilities",
            "pressure_window_responsibilities",
            "formation_structure",
            "formation_transitions",
            "temporary_roles",
            "stable_roles",
            "damage_responsibilities",
            "sustain_responsibilities",
            "reserve_strategy",
            "skill_intents",
            "selected_affordance_ids",
            "compiler_slots",
            "allowed_substitutions",
            "forbidden_substitutions",
            "mandatory_tactical_invariants",
            "conditional_responsibilities",
            "optional_responsibilities",
            "verifier_questions",
        ],
        "properties": {
            "operational_plan_id": {"type": "string"},
            "parent_hypothesis_id": {"type": "string"},
            "tactical_thesis": {"type": "string"},
            "changed_conflicting_assumptions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "opening_responsibilities": {"type": "array", "items": {"type": "string"}},
            "battle_phases": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "corridor_responsibilities": {"type": "array", "items": {"type": "string"}},
            "pressure_window_responsibilities": {"type": "array", "items": {"type": "string"}},
            "formation_structure": {"type": "object", "additionalProperties": True},
            "formation_transitions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "temporary_roles": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "stable_roles": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "damage_responsibilities": {"type": "array", "items": {"type": "string"}},
            "sustain_responsibilities": {"type": "array", "items": {"type": "string"}},
            "reserve_strategy": {"type": "object", "additionalProperties": True},
            "skill_intents": {"type": "array", "items": {"type": "string"}},
            "selected_affordance_ids": {"type": "array", "items": {"type": "string"}},
            "compiler_slots": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "allowed_substitutions": {"type": "array", "items": {"type": "string"}},
            "forbidden_substitutions": {"type": "array", "items": {"type": "string"}},
            "mandatory_tactical_invariants": {"type": "array", "items": {"type": "string"}},
            "conditional_responsibilities": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "optional_responsibilities": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "verifier_questions": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "type": "object",
        "additionalProperties": True,
        "required": [
            "lessons_from_infeasibility",
            "retained_tactical_knowledge",
            "rejected_tactical_assumptions",
            "revised_stage_understanding",
            "revised_tactical_requirements",
            "revised_strategic_hypotheses",
            "revised_operational_plans",
            "counterexample_avoidance_explanations",
            "explicit_assumptions",
            "uncertainties",
            "deterministic_verifier_questions",
        ],
        "properties": {
            "lessons_from_infeasibility": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "retained_tactical_knowledge": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "rejected_tactical_assumptions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_stage_understanding": {"type": "object", "additionalProperties": True},
            "revised_tactical_requirements": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_strategic_hypotheses": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_operational_plans": {"type": "array", "minItems": 2, "maxItems": 3, "items": operational_plan},
            "counterexample_avoidance_explanations": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "explicit_assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainties": {"type": "array", "items": {"type": "string"}},
            "deterministic_verifier_questions": {"type": "array", "items": {"type": "string"}},
        },
    }


def compact_operators(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    keys = [
        "operator_id",
        "name",
        "profession",
        "position",
        "rarity",
        "cost",
        "block_count",
        "redeploy_seconds",
        "hp",
        "attack",
        "defense",
        "magic_resistance",
        "attack_interval_seconds",
        "attack_range",
        "skill_name",
        "skill_sp_cost",
        "skill_initial_sp",
        "skill_recovery_mode",
        "skill_auto_activate",
        "skill_effect",
        "planner_safe_for_basic_attack",
        "skill_supported",
        "planner_safe_for_selected_skills",
    ]
    for operator in context["operators"]:
        row = {key: operator.get(key) for key in keys if key in operator}
        rows.append(row)
    return rows


def compact_plan_threats(context: dict[str, Any]) -> list[dict[str, Any]]:
    keys = [
        "route_id",
        "enemy_id",
        "enemy_speed",
        "lane_id",
        "spawn_frames",
        "latest_safe_blocker_frame",
        "latest_interception_tile",
        "legal_interception_tiles",
        "contact_to_leak_seconds",
        "earliest_operator_contact_frame",
    ]
    return [{key: row.get(key) for key in keys if key in row} for row in context["exact_route_threats"]["routes"]]


def build_prompt(memory: dict[str, Any]) -> str:
    context = load(CONTEXT)
    affordances = load(AFFORDANCES)
    old_plans = load(RECOVER / "normalized_revised_operational_plans.json")["revised_operational_plans"]
    causal = load(CAUSAL)
    old_summaries = [plan_summary(plan) for plan in old_plans]
    payload = {
        "task": "R8_1_CONSTRAINT_INFORMED_TACTICAL_REVISION_V3",
        "mechanics_version": MECHANICS,
        "stage_id": STAGE,
        "feasibility_experience_memory": memory,
        "historical_early_failure": {
            "classification": causal.get("classification"),
            "mechanism": causal.get("mechanism"),
            "event_sequence": causal.get("event_sequence"),
            "counterfactual_attribution": causal.get("counterfactual_attribution"),
        },
        "previous_operational_plans_condensed": old_summaries,
        "deterministic_stage_context": {
            "stage_facts": context["stage_facts"],
            "exact_route_threats": {"routes": compact_plan_threats(context)},
            "route_pressure_clusters": context["route_pressure_clusters"],
            "pressure_windows": context["pressure_windows"],
            "candidate_interception_regions": context["candidate_interception_regions"],
            "candidate_shared_coverage_regions": context["candidate_shared_coverage_regions"],
            "stage_devices": context["stage_devices"],
            "prior_simulator_failures": context["prior_simulator_failures"],
            "operators": compact_operators(context),
        },
        "deterministic_affordance_catalog": affordances,
    }
    instructions = """You previously proposed tactical plans for R8-1. Deterministic verification has established that five of those plans cannot satisfy their own deployment-economy and responsibility-deadline constraints.

These failures are valuable tactical evidence.

Your task is to understand why those plans failed and intentionally revise the tactical decisions that produced the conflicts.

Do not merely propose a different roster or move a deployment slightly earlier.

Reconsider which responsibilities are mandatory, which must coexist, which can be sequential, which can share resources, and how the formation can evolve while respecting the actual economy.

Preserve useful tactical ideas where justified.

Generate 2-3 materially different, operationally explicit plans.

Do not invent exact game statistics or deployment frames.

Use the supplied deterministic constraints and affordances.

A revised plan should explain exactly which previously conflicting tactical assumption it changes.

For every previous infeasible plan, explain: what tactical decision created the conflict; whether it was caused by simultaneity; whether a responsibility was required too early; whether independent deployment was unnecessarily assumed; whether an expensive capability combination was required; whether a formation transition was incompatible with available economy; which tactical concept remains worth preserving; and which tactical assumption must change. Reference actual supplied evidence. Do not answer only with generic statements such as "need more DP."

You may consider sequential responsibility establishment, shared damage or blocking responsibilities, temporary early control, delayed stable formation, different economy generation, alternative capability allocation, route-specific triage, forward damage, different topology, legal RETREAT and handoffs, and different skill scheduling objectives. These are examples, not mandates.

Reason separately about early C01/route-3 survival and later economy deadlines. You may replace the previous pocket-fire concept entirely if justified.

Return one machine-readable JSON object only. Do not use Markdown. Use simple JSON fields compatible with the provided schema.

For each OperationalPlan, compiler_slots is required for deterministic verification. Each slot must use only supplied affordance IDs and include: slot_id; role (BLOCK, PIONEER_BLOCK, KILLING_BLOCK, DUELIST, RANGED_DPS, SUSTAIN, or RELAY); affordance_id; corridor; pressure_window; phase; establishment_semantic (MUST_BE_ACTIVE, MUST_BE_ACTIVE_AND_DP_CAPABLE, MUST_BE_ACTIVE_WITH_AUTO_SKILL_SUPPORTED, MUST_HAVE_COVERAGE, MUST_BE_SKILL_READY, or MUST_COMPLETE_TRANSITION); deadline_basis using a supplied route ID and threat event (BLOCK, FIRE, or MEDIC); capability_requirements; whether it may share a live operator with another slot; and optional replacement_group, must_vacate_slot, retreat_basis, or max_cost_design_choice. Do not invent tile coordinates or exact frames. The deterministic verifier will resolve legal tiles, facing, timing, and economy.

Do not claim a revised plan is definitely feasible. That belongs to deterministic verification.

CONSTRAINT_INFORMED_REASONING_PAYLOAD_JSON:
"""
    return instructions + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def prepare() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    memory = experience_memory()
    write("feasibility_experience_memory.json", memory)
    write(
        "lessons_from_infeasibility.json",
        {
            "schema_version": "R8_1_LESSONS_FROM_INFEASIBILITY_INPUT_V1",
            "source": "output/r8_1_operational_feasibility_unsat_core_audit_v1",
            "records": memory["records"],
        },
    )
    prompt = build_prompt(memory)
    write_text("constraint_informed_reasoning_prompt.txt", prompt)
    schema = output_schema()
    write("revision_output_schema.json", schema)
    payload = {
        "model": MODEL,
        "stream": True,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "r8_1_constraint_informed_tactical_revision_v3",
                "schema": schema,
                "strict": False,
            }
        },
    }
    write("llm_request_fingerprint.json", {
        "schema_version": "R8_1_CONSTRAINT_INFORMED_LLM_REQUEST_FINGERPRINT_V1",
        "provider": "volcengine-agent-plan",
        "model": MODEL,
        "endpoint": BASE_URL,
        "wire_protocol": "responses",
        "stream": True,
        "assistant_message_prefill_allowed": False,
        "previous_response_id_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_continuation_allowed": False,
        "prompt_bytes": len(prompt.encode()),
        "prompt_sha256": sha_bytes(prompt.encode()),
        "request_json_bytes": len(json.dumps(payload, ensure_ascii=False).encode()),
        "request_json_sha256": sha_bytes(json.dumps(payload, ensure_ascii=False).encode()),
        "created_at_utc": utc_now(),
        "planned_kimi_call_count": 1,
    })
    return {"prompt_bytes": len(prompt.encode()), "experience_entries": len(memory["records"])}


def call_llm() -> dict[str, Any]:
    if not (OUT / "llm_request_fingerprint.json").is_file() or not (OUT / "constraint_informed_reasoning_prompt.txt").is_file():
        raise RuntimeError("PREPARE_ARTIFACTS_MISSING")
    payload = {
        "model": MODEL,
        "stream": True,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": (OUT / "constraint_informed_reasoning_prompt.txt").read_text()}
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "r8_1_constraint_informed_tactical_revision_v3",
                "schema": load(OUT / "revision_output_schema.json"),
                "strict": False,
            }
        },
    }
    result, accumulator, _ = stream_once(payload)
    diagnostics = completion_diagnostics(result, accumulator)
    diagnostics.update({"kimi_call_count": 1, "no_automatic_continuation": result.get("automatic_continuation_attempted") is False})
    write("response_completion_validation.json", diagnostics)
    if not diagnostics["successful_completion"]:
        raise RuntimeError("KIMI_SINGLE_CALL_DID_NOT_COMPLETE_SUCCESSFULLY")
    output_text = extract_response_text(accumulator.response_envelope or {})[0]
    parsed = json.loads(output_text)
    write("llm_structured_output.json", parsed)
    return diagnostics


def grounding_validation() -> dict[str, Any]:
    parsed = load(OUT / "llm_structured_output.json")
    affordance_catalog = load(AFFORDANCES)["affordances"]
    affordance_ids = {row["affordance_id"] for row in affordance_catalog}
    context = load(CONTEXT)
    route_ids = {row["route_id"] for row in context["exact_route_threats"]["routes"]}
    affordance_route_ids = {
        route_id
        for affordance in affordance_catalog
        for route_id in affordance.get("served_routes", [])
    }
    corridor_ids = {f"C{index:02d}" for index in range(1, 8)} | {"NONE_BACKFIELD"}
    known_roles = {
        "BLOCK",
        "PIONEER_BLOCK",
        "KILLING_BLOCK",
        "DUELIST",
        "RANGED_DPS",
        "SUSTAIN",
        "RELAY",
    }
    known_states = {
        "MUST_BE_ACTIVE",
        "MUST_BE_ACTIVE_AND_DP_CAPABLE",
        "MUST_BE_ACTIVE_WITH_AUTO_SKILL_SUPPORTED",
        "MUST_HAVE_COVERAGE",
        "MUST_BE_SKILL_READY",
        "MUST_COMPLETE_TRANSITION",
    }
    errors = []
    warnings = []
    specificity = []
    required_top = [
        "lessons_from_infeasibility",
        "retained_tactical_knowledge",
        "rejected_tactical_assumptions",
        "revised_stage_understanding",
        "revised_tactical_requirements",
        "revised_strategic_hypotheses",
        "revised_operational_plans",
        "counterexample_avoidance_explanations",
        "explicit_assumptions",
        "uncertainties",
        "deterministic_verifier_questions",
    ]
    missing_top = [key for key in required_top if key not in parsed]
    if missing_top:
        errors.append("MISSING_TOP_LEVEL:" + ",".join(missing_top))
    if not 2 <= len(parsed.get("revised_operational_plans", [])) <= 3:
        errors.append("REVISED_PLAN_COUNT_NOT_2_3")
    for plan in parsed.get("revised_operational_plans", []):
        plan_id = plan.get("operational_plan_id", "UNKNOWN")
        unknown_affordances = sorted(set(plan.get("selected_affordance_ids", [])) - affordance_ids)
        if unknown_affordances:
            errors.append(f"{plan_id}:UNKNOWN_AFFORDANCES:" + ",".join(unknown_affordances))
        for slot in plan.get("compiler_slots", []):
            if slot.get("affordance_id") not in affordance_ids:
                errors.append(f"{plan_id}:{slot.get('slot_id')}:UNKNOWN_SLOT_AFFORDANCE")
            route_id = str(slot.get("deadline_basis", "")).split(":", 1)[0]
            if route_id not in route_ids and route_id not in affordance_route_ids:
                errors.append(f"{plan_id}:{slot.get('slot_id')}:UNKNOWN_ROUTE")
            elif route_id not in route_ids:
                warnings.append(f"{plan_id}:{slot.get('slot_id')}:ROUTE_ONLY_IN_AFFORDANCE_NO_EXACT_THREAT_TIMING")
            if slot.get("corridor") not in corridor_ids:
                warnings.append(f"{plan_id}:{slot.get('slot_id')}:NONSTANDARD_CORRIDOR_LABEL")
            if slot.get("role") not in known_roles:
                errors.append(f"{plan_id}:{slot.get('slot_id')}:UNKNOWN_ROLE")
            if slot.get("establishment_semantic") not in known_states:
                errors.append(f"{plan_id}:{slot.get('slot_id')}:UNKNOWN_ESTABLISHMENT_STATE")
        required_plan_fields = [
            "tactical_thesis",
            "opening_responsibilities",
            "battle_phases",
            "corridor_responsibilities",
            "pressure_window_responsibilities",
            "formation_structure",
            "formation_transitions",
            "temporary_roles",
            "stable_roles",
            "damage_responsibilities",
            "sustain_responsibilities",
            "reserve_strategy",
            "skill_intents",
            "selected_affordance_ids",
            "compiler_slots",
            "allowed_substitutions",
            "forbidden_substitutions",
            "mandatory_tactical_invariants",
            "conditional_responsibilities",
            "optional_responsibilities",
            "verifier_questions",
        ]
        missing = [
            key
            for key in required_plan_fields
            if key not in plan or plan.get(key) is None or plan.get(key) == "" or plan.get(key) == []
        ]
        specificity.append(
            {
                "operational_plan_id": plan_id,
                "missing_or_empty_required_fields": missing,
                "operational_specificity": "PASS" if not missing else "FAIL",
                "compiler_slot_count": len(plan.get("compiler_slots", [])),
            }
        )
    numeric_policy = {
        "exact_frames_in_narrative": "TACTICAL_DESIGN_TARGET_NOT_GAME_FACT",
        "cost_and_dp_arithmetic": "COMPUTABLE_DESIGN_CALCULATION_REQUIRING_VERIFICATION",
        "operator_stat_thresholds": "DESIGN_REQUIREMENT_OR_SOURCE_BACKED_STAT",
        "tile_coordinates": "GROUNDED_ONLY_WHEN_PRESENT_IN_SELECTED_AFFORDANCE",
    }
    return {
        "schema_version": "R8_1_CONSTRAINT_INFORMED_GROUNDING_VALIDATION_V1",
        "raw_response_immutable": True,
        "json_valid": True,
        "kimi_call_count": 1,
        "revised_plan_count": len(parsed.get("revised_operational_plans", [])),
        "errors": errors,
        "warnings": warnings,
        "specificity": specificity,
        "numeric_classification_policy": numeric_policy,
        "status": "PASS_WITH_WARNINGS" if not errors and warnings else ("PASS" if not errors else "FAIL"),
    }


def plan_capability_pool(
    context: dict[str, Any],
    repair_module: Any,
    slot: dict[str, Any],
    plan_slots: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    role = slot["role"]
    requirements = str(slot.get("capability_requirements", ""))
    reference_match = re.search(r"\b[A-Z]\d{2}\b", requirements)
    if plan_slots and reference_match:
        reference = reference_match.group(0)
        referenced = next(
            (item for item in plan_slots if str(item.get("slot_id", "")).startswith(reference)),
            None,
        )
        if referenced:
            requirements = str(referenced.get("capability_requirements", requirements))
    if role in {"KILLING_BLOCK", "RANGED_DPS", "RELAY"}:
        pool = repair_module.selected_usage_pool(
            context,
            role,
            fidelity_by_id=repair_module.engine_fidelity,
            census_by_id=repair_module.engine_census,
        )
    elif role == "PIONEER_BLOCK":
        pool = repair_module.selected_usage_pool(
            context,
            role,
            fidelity_by_id=repair_module.engine_fidelity,
            census_by_id=repair_module.engine_census,
        )
    else:
        pool = []
        requirements = requirements.lower()
        minimum_block = 0
        minimum_hp = 0.0
        minimum_defense = 0.0
        for marker, target in (("block>=", "minimum_block"), ("hp>=", "minimum_hp"), ("def>=", "minimum_defense")):
            marker_index = requirements.find(marker)
            if marker_index < 0:
                continue
            suffix = requirements[marker_index + len(marker):]
            digits = ""
            for char in suffix:
                if char.isdigit():
                    digits += char
                elif digits:
                    break
            if digits:
                if target == "minimum_block":
                    minimum_block = int(digits)
                elif target == "minimum_hp":
                    minimum_hp = float(digits)
                else:
                    minimum_defense = float(digits)
        for operator in context["operators"]:
            if operator.get("position") != "MELEE" or not operator.get("planner_safe_for_basic_attack"):
                continue
            if float(operator.get("block_count", 0)) < minimum_block:
                continue
            if float(operator.get("hp", 0)) < minimum_hp:
                continue
            if float(operator.get("defense", 0)) < minimum_defense:
                continue
            pool.append(operator)
    maximum_cost = slot.get("max_cost_design_choice")
    if maximum_cost is not None:
        pool = [row for row in pool if float(row["cost"]) <= float(maximum_cost)]
    return sorted(pool, key=lambda row: (float(row["cost"]), row["operator_id"]))


def feasibility_analysis() -> dict[str, Any]:
    repair = import_repair()
    repair.load_fidelity_tables()
    context = load(CONTEXT)
    routes = repair.route_map(context)
    parsed = load(OUT / "llm_structured_output.json")
    records = []
    all_plan_slots = [
        slot for plan in parsed["revised_operational_plans"] for slot in plan["compiler_slots"]
    ]
    pools: list[list[dict[str, Any]]] = []

    def minimum_cost_for_prefix(prefix: list[dict[str, Any]]) -> tuple[float | None, dict[str, str]]:
        best: tuple[float, list[tuple[str, str]]] | None = None

        def walk(index: int, used: set[str], cost: float, assignment: list[tuple[str, str]]) -> None:
            nonlocal best
            if best is not None and cost >= best[0]:
                return
            if index == len(pools):
                best = (cost, list(assignment))
                return
            candidates = sorted(
                pools[index],
                key=lambda operator: (float(operator["cost"]), operator["operator_id"]),
            )
            for operator in candidates:
                operator_id = operator["operator_id"]
                if operator_id in used:
                    continue
                assignment.append((prefix[index]["slot_id"], operator_id))
                walk(index + 1, used | {operator_id}, cost + float(operator["cost"]), assignment)
                assignment.pop()

        walk(0, set(), 0.0, [])
        return (best[0], dict(best[1])) if best is not None else (None, {})

    for plan in parsed["revised_operational_plans"]:
        plan_slots = plan["compiler_slots"]
        opening_rows = []
        for slot in plan_slots:
            route_id, kind = str(slot["deadline_basis"]).split(":", 1)
            route = routes.get(route_id)
            deadline = repair.establishment_deadline(route, kind)
            # A spawn time is not an establishment deadline. Unknown timing
            # must remain unknown until the plan-specific contract resolves it.
            if deadline is None or deadline > 729:
                continue
            opening_rows.append({**slot, "deadline_frame": deadline})
        opening_rows.sort(key=lambda row: (row["deadline_frame"], row["slot_id"]))
        prefix_results = []
        first_conflict = None
        for index, row in enumerate(opening_rows):
            prefix = opening_rows[: index + 1]
            pools.clear()
            pools[:] = [plan_capability_pool(context, repair, slot, all_plan_slots) for slot in prefix]
            minimum_cost, assignment = minimum_cost_for_prefix(prefix)
            available_dp = 10.0 + float(row["deadline_frame"]) / 30.0
            deficit = max(0.0, (minimum_cost or 0.0) - available_dp)
            status = (
                "NO_DP_CONFLICT_UNDER_SIMPLIFIED_ASSUMPTIONS"
                if minimum_cost is not None and deficit <= 1e-9
                else ("CANDIDATE_POOL_EMPTY" if minimum_cost is None
                      else "DP_CONFLICT_UNDER_SIMPLIFIED_ASSUMPTIONS")
            )
            row_result = {
                "deadline_frame": row["deadline_frame"],
                "slot_id": row["slot_id"],
                "prefix_slots": [item["slot_id"] for item in prefix],
                "minimum_cost": minimum_cost,
                "available_dp_no_retreat_refund": available_dp,
                "deficit": deficit,
                "minimum_assignment": assignment,
                "status": status,
            }
            prefix_results.append(row_result)
            if status != "NO_DP_CONFLICT_UNDER_SIMPLIFIED_ASSUMPTIONS" and first_conflict is None:
                first_conflict = row_result
        empty_roles = sorted(
            {
                row["role"]
                for row in opening_rows
                if not plan_capability_pool(context, repair, row, all_plan_slots)
            }
        )
        # This analyzer does not establish that its deadline, distinct-unit
        # assignment, or natural-only economy bounds preserve the supplied plan.
        # Its arithmetic is diagnostic, never a proof of plan infeasibility.
        current_mechanics_status = "FEASIBILITY_UNKNOWN"
        records.append(
            {
                "operational_plan_id": plan["operational_plan_id"],
                "classification": current_mechanics_status,
                "proof_limitations": [
                    "PLAN_SPECIFIC_DEADLINE_NOT_VERIFIED",
                    "SHARING_CONDITIONAL_PHASE_AND_TRANSITION_SEMANTICS_NOT_VERIFIED",
                    "NATURAL_ONLY_DP_IS_NOT_A_VERIFIED_TOTAL_DP_UPPER_BOUND",
                    "CAPABILITY_POOL_AND_GEOMETRY_NOT_FULLY_VERIFIED",
                    "ONLY_DEADLINES_AT_OR_BEFORE_FRAME_729_ANALYZED",
                ],
                "first_conflict": first_conflict,
                "prefix_results": prefix_results,
                "empty_roles_in_opening_prefix": empty_roles,
                "economy_model": {
                    "initial_dp": 10.0,
                    "natural_dp_rate_per_second": 1.0,
                    "retreat_refund": 0.0,
                    "reason": "Diagnostic assumptions only; skill DP and retreat refunds are omitted, not proven unavailable.",
                },
                "required_unverified_conditions": [
                    condition
                    for condition in [
                        "RETREAT_REFUND_AMOUNT_AND_TIMING",
                        "SAFE_ARRIVAL_GAP_FOR_SAME_TILE_UPGRADE",
                    ]
                    if any(row.get("retreat_basis") or row.get("must_vacate_slot")
                           for row in plan["compiler_slots"])
                ],
            }
        )
    return {
        "schema_version": "R8_1_CONSTRAINT_INFORMED_FEASIBILITY_CERTIFICATES_V1",
        "mechanics_version": MECHANICS,
        "no_simulation_reason": "No constructive witness: plan-specific deadlines, semantics and complete economy remain unverified; simplified prefix conflicts are not proven tactical failures.",
        "records": records,
    }


def import_repair() -> Any:
    spec = importlib.util.spec_from_file_location(
        "semantic_repair",
        ROOT / "scripts/run_r8_1_operational_semantic_preservation_repair_v1.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def postprocess() -> dict[str, Any]:
    parsed = load(OUT / "llm_structured_output.json")
    # Validate required dependencies before replacing any historical artifacts.
    grounding = grounding_validation()
    feasibility = feasibility_analysis()
    write("revised_stage_understanding.json", {
        "schema_version": "R8_1_REVISED_STAGE_UNDERSTANDING_V3",
        "source": "output/r8_1_constraint_informed_revision_v3/llm_structured_output.json",
        "payload": parsed.get("revised_stage_understanding", {}),
    })
    write("revised_tactical_requirements.json", {
        "schema_version": "R8_1_REVISED_TACTICAL_REQUIREMENTS_V3",
        "payload": parsed.get("revised_tactical_requirements", []),
    })
    write("revised_operational_plans.json", {
        "schema_version": "R8_1_REVISED_OPERATIONAL_PLANS_V3",
        "kimi_call_count": 1,
        "plans": parsed["revised_operational_plans"],
    })
    write("constraint_informed_reasoning_context.json", reasoning_context())
    write("grounding_validation.json", grounding)
    write("feasibility_certificates.json", feasibility)
    write("constructive_feasibility_witnesses.json", {
        "schema_version": "R8_1_CONSTRUCTIVE_FEASIBILITY_WITNESSES_V1",
        "witnesses": [],
        "status": "NOT_RUN",
        "reason": feasibility["no_simulation_reason"],
    })
    learning_rows = []
    eliminated = repeated = replaced = 0
    for record in feasibility["records"]:
        if record["classification"] == "INFEASIBLE_WITH_PROVEN_CONFLICT":
            classification = "OLD_CONFLICT_REPLACED_BY_NEW_CONFLICT"
            replaced += 1
        else:
            classification = "NOT_DETERMINED"
        learning_rows.append(
            {
                "operational_plan_id": record["operational_plan_id"],
                "learning_progress": classification,
                "evidence": record["first_conflict"],
            }
        )
    write("counterexample_avoidance_validation.json", {
        "schema_version": "R8_1_COUNTEREXAMPLE_AVOIDANCE_VALIDATION_V1",
        "records": learning_rows,
        "old_conflicts_eliminated": eliminated,
        "old_conflicts_repeated": repeated,
        "new_conflicts_discovered": replaced,
    })
    write("per_plan_feasibility_results.json", {
        "schema_version": "R8_1_PER_PLAN_FEASIBILITY_RESULTS_V1",
        "records": [
            {
                "operational_plan_id": row["operational_plan_id"],
                "classification": row["classification"],
                "first_conflict": row["first_conflict"],
                "unverified_conditions": row["required_unverified_conditions"],
            }
            for row in feasibility["records"]
        ],
    })
    write("bounded_search_results.json", {
        "schema_version": "R8_1_BOUNDED_FAITHFUL_SEARCH_RESULTS_V3",
        "status": "NOT_RUN",
        "maximum_budget": 200,
        "timelines_generated": 0,
        "unique_executable_timelines": 0,
        "reason": feasibility["no_simulation_reason"],
    })
    write("battle_failure_feedback.json", {
        "schema_version": "R8_1_CONSTRAINT_INFORMED_BATTLE_FAILURE_FEEDBACK_V1",
        "simulation_run": False,
        "primary_feedback": feasibility["no_simulation_reason"],
        "future_deterministic_prerequisite": "Verify plan-specific deadlines, responsibility semantics and complete source-backed economy before promoting any diagnostic conflict to tactical feedback.",
        "new_conflicts": [
            {
                "operational_plan_id": row["operational_plan_id"],
                "deadline_frame": row["first_conflict"]["deadline_frame"],
                "minimum_cost": row["first_conflict"]["minimum_cost"],
                "available_dp": row["first_conflict"]["available_dp_no_retreat_refund"],
                "deficit": row["first_conflict"]["deficit"],
            }
            for row in feasibility["records"]
            if row["classification"] == "INFEASIBLE_WITH_PROVEN_CONFLICT"
        ],
    })
    write("learning_progress_assessment.json", {
        "schema_version": "R8_1_LEARNING_PROGRESS_ASSESSMENT_V1",
        "classification": "NOT_DETERMINED",
        "evidence_used": "The plans explicitly cite EXP-001 through EXP-006 and materially change pioneer/medic, merged-anchor, upstream/downstream blocking, and delayed-upgrade structures.",
        "remaining_failure": feasibility["no_simulation_reason"],
        "old_conflicts_eliminated": eliminated,
        "old_conflicts_repeated": repeated,
        "new_conflicts_discovered": replaced,
        "records": learning_rows,
    })
    write("final_status.json", final_status(grounding, feasibility))
    validation = validation_results()
    write("validation_results.json", validation)
    return {
        "grounding_status": grounding["status"],
        "feasible_plans": sum(row["classification"] == "FEASIBLE_WITH_CONSTRUCTIVE_WITNESS" for row in feasibility["records"]),
        "infeasible_plans": sum(row["classification"] == "INFEASIBLE_WITH_PROVEN_CONFLICT" for row in feasibility["records"]),
    }


def final_status(grounding: dict[str, Any], feasibility: dict[str, Any]) -> dict[str, Any]:
    learning = load(OUT / "learning_progress_assessment.json")
    return {
        "KIMI_CALL_COUNT": 1,
        "MODEL": MODEL,
        "PREVIOUS_INFEASIBLE_PLANS": 5,
        "COUNTEREXAMPLE_MEMORY_ENTRIES": len(load(OUT / "feasibility_experience_memory.json")["records"]),
        "NEW_OPERATIONAL_PLANS": len(load(OUT / "revised_operational_plans.json")["plans"]),
        "OLD_CONFLICTS_ELIMINATED": learning["old_conflicts_eliminated"],
        "OLD_CONFLICTS_REPEATED": learning["old_conflicts_repeated"],
        "NEW_CONFLICTS_DISCOVERED": learning["new_conflicts_discovered"],
        "CONSTRUCTIVELY_FEASIBLE_PLANS": sum(row["classification"] == "FEASIBLE_WITH_CONSTRUCTIVE_WITNESS" for row in feasibility["records"]),
        "CONDITIONALLY_FEASIBLE_PLANS": sum(row["classification"] == "FEASIBLE_WITH_CONDITIONS" for row in feasibility["records"]),
        "PROVEN_INFEASIBLE_PLANS": sum(row["classification"] == "INFEASIBLE_WITH_PROVEN_CONFLICT" for row in feasibility["records"]),
        "GROUNDING_BLOCKED_PLANS": 0,
        "FAITHFUL_UNIQUE_TIMELINES": 0,
        "CURRENT_MODEL_WIN": "NOT_RUN",
        "ROBUST_WIN": "NOT_RUN",
        "LEARNING_PROGRESS": learning["classification"],
        "PRIMARY_REMAINING_BOTTLENECK": "PLAN_SPECIFIC_DETERMINISTIC_CONTRACT_UNVERIFIED",
        "MECHANICS_CHANGED": "NO",
        "REAL_GAME_VALIDATION": "UNTESTED",
        "GIT_COMMIT_CREATED": "PENDING",
        "GIT_COMMIT_SHA": "NONE",
        "GIT_BRANCH": subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip() or "NONE",
        "GITHUB_PUSH": "PENDING",
        "GITHUB_REPOSITORY": "https://github.com/BasicallyKawaii/arknights-auto-planner.git",
        "GITHUB_COMMIT_OR_BRANCH_URL": "NONE",
        "GITHUB_BLOCKER": "PENDING_DELIVERY",
    }


def validation_results() -> dict[str, Any]:
    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "scripts", "src", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    unittest_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_r8_1_constraint_informed_tactical_revision_v3",
            "scripts.test_kimi_responses_transport",
            "-v",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT / 'scripts'}"},
        capture_output=True,
        text=True,
    )
    required = [
        "feasibility_experience_memory.json",
        "constraint_informed_reasoning_context.json",
        "llm_request_fingerprint.json",
        "llm_raw_response.txt",
        "llm_structured_output.json",
        "lessons_from_infeasibility.json",
        "revised_stage_understanding.json",
        "revised_tactical_requirements.json",
        "revised_operational_plans.json",
        "counterexample_avoidance_validation.json",
        "grounding_validation.json",
        "feasibility_certificates.json",
        "constructive_feasibility_witnesses.json",
        "per_plan_feasibility_results.json",
        "bounded_search_results.json",
        "battle_failure_feedback.json",
        "learning_progress_assessment.json",
        "validation_results.json",
        "final_status.json",
    ]
    missing = [name for name in required if not (OUT / name).is_file()]
    secrets = []
    for artifact in OUT.glob("*.json"):
        text = artifact.read_text(errors="ignore")
        if "ARK_API_KEY_agent=" in text or "Authorization: Bearer " in text:
            secrets.append(artifact.name)
    checks = [
        {"check": "compileall", "status": "PASS" if compile_result.returncode == 0 else "FAIL"},
        {"check": "unittest", "status": "PASS" if unittest_result.returncode == 0 else "FAIL"},
        {"check": "artifact_integrity", "status": "PASS" if not missing else "FAIL"},
        {"check": "secret_scan", "status": "PASS" if not secrets else "FAIL"},
    ]
    return {
        "schema_version": "R8_1_CONSTRAINT_INFORMED_REVISION_V3_VALIDATION",
        "overall_status": "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL",
        "pytest": "UNAVAILABLE",
        "unittest_returncode": unittest_result.returncode,
        "unittest_output_tail": unittest_result.stderr.strip().splitlines()[-30:],
        "missing_artifacts": missing,
        "secret_scan_hits": secrets,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["prepare", "llm", "postprocess"], required=True)
    args = parser.parse_args()
    if args.stage == "prepare":
        print(json.dumps(prepare(), sort_keys=True))
    elif args.stage == "llm":
        print(json.dumps(call_llm(), sort_keys=True))
    else:
        print(json.dumps(postprocess(), sort_keys=True))


if __name__ == "__main__":
    main()
