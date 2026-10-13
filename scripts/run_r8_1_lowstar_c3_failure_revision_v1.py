from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from kimi_readonly_tools import BASE_RULE_CARD, ReadOnlyQueryEngine
from kimi_tool_loop import (
    ToolLoopBudget,
    build_tool_enabled_request,
    run_mock_tool_session,
    validate_final_operational_plan,
    validate_tool_request,
)
from kimi_responses_transport import StreamAccumulator, parse_sse
from run_r8_1_low_star_full_tactical_closure_v1 import compact_operator_catalog, output_schema


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_lowstar_c3_failure_revision_v1"
C2_OUT = ROOT / "output/r8_1_lowstar_c2_compact_tool_revision_v2"
DIAGNOSTIC = ROOT / "output/r8_1_lowstar_c2_full_diagnostic_v1"
FACTS = ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json"
SUPPORT = ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json"
BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/responses"
MODEL = "kimi-k3"
MECHANICS = "m18.9-stage-device-runtime-v1"
TIMEOUT_SECONDS = 900
TOKEN_LIMIT = 32768
INITIAL_BODY_LIMIT = 140_000
CONTINUATION_BODY_LIMIT = 200_000
MAX_MODEL_REQUESTS = 3
MAX_TOOL_CALLS = 6
PLAN_ID_PREFIX = "R8_1_LOWSTAR_PLAN_C3"
PARENT_PLAN_ID = "R8_1_LOWSTAR_PLAN_C2"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def action_outcomes() -> list[dict[str, Any]]:
    plan = load(C2_OUT / "llm_structured_output.json")["revised_operational_plans"][0]
    summary = load(DIAGNOSTIC / "diagnostic_summary.json")
    events = load(DIAGNOSTIC / "diagnostic_events.json")["events"]
    sim_end_frame = round(float(summary["result"]["time_survived"]) * 30)
    outcomes: dict[tuple[str, int], dict[str, Any]] = {}
    for row in summary["event_summaries"]["deployment_events"]:
        outcomes[("DEPLOY", int(row["frame"]))] = {
            "operator_id": row["source_id"], "status": "EXECUTED" if row["details"].get("legal") else "REJECTED",
            "reason": row["details"].get("reason"), "cost": row["details"].get("cost"),
        }
    for row in summary["event_summaries"]["skill_activations"]:
        key = ("ACTIVATE_SKILL", int(row["frame"]))
        current = outcomes.get(key)
        if current is None or row["details"].get("legal") is False:
            outcomes[key] = {
                "operator_id": row["source_id"], "status": "EXECUTED" if row["details"].get("legal") else "REJECTED",
                "reason": None if row["details"].get("legal") else "manual skill activation rejected (operator unavailable)",
            }
    for row in summary["event_summaries"]["retreat_events"]:
        outcomes[("RETREAT", int(row["frame"]))] = {
            "operator_id": row["source_id"], "status": "EXECUTED" if row["details"].get("legal") else "REJECTED",
            "reason": None if row["details"].get("legal") else "retreat rejected (operator unavailable)",
        }
    rows = []
    for action in plan["action_timeline"]:
        key = (action["action_type"], int(action["frame"]))
        outcome = outcomes.get(key, {})
        if not outcome:
            status = "NOT_REACHED" if int(action["frame"]) > sim_end_frame else "NO_OBSERVABLE_EVENT"
            outcome = {"status": status, "reason": f"simulation ended at frame {sim_end_frame}" if status == "NOT_REACHED" else "no matching event"}
        rows.append({
            "action_type": action["action_type"], "frame": int(action["frame"]),
            "operator_id": action["operator_id"], "status": outcome["status"], "reason": outcome.get("reason"),
        })
    return rows


def c2_failure_evidence() -> dict[str, Any]:
    events = load(DIAGNOSTIC / "diagnostic_events.json")["events"]
    summary = load(DIAGNOSTIC / "diagnostic_summary.json")
    deaths = [
        {"frame": row["frame"], "operator_id": row["source_id"]}
        for row in events if row["event_type"] == "OPERATOR_DEATH"
    ]
    vanilla_blocks = [
        {"frame": row["frame"], "route_enemy_id": row["target_id"]}
        for row in events if row["event_type"] == "BLOCK" and row["source_id"] == "char_240_wyvern"
    ]
    vanilla_unblocks = [
        {"frame": row["frame"], "route_enemy_id": row["target_id"]}
        for row in events if row["event_type"] == "UNBLOCK" and row["source_id"] == "char_240_wyvern"
    ]
    first_leaks = [
        {"frame": row["frame"], "enemy_id": row["source_id"]}
        for row in events if row["event_type"] == "ENEMY_LEAK"
    ][:2]
    fang_auto = next(row for row in summary["event_summaries"]["automatic_skill_dp_income"] if row["source_id"] == "char_123_fang")
    return {
        "schema_version": "R8_1_LOWSTAR_C2_DIAGNOSTIC_KEY_EVIDENCE_V1",
        "result": {
            "simulator_win": bool(summary["result"]["win"]), "enemies_killed": int(summary["result"]["enemies_killed"]),
            "enemies_leaked": int(summary["result"]["enemies_leaked"]), "remaining_life": float(summary["result"]["remaining_life"]),
            "operator_deaths": int(summary["result"]["operator_deaths"]), "simulation_end_frame": round(float(summary["result"]["time_survived"]) * 30),
        },
        "fang_auto_income": {"frame": round(float(fang_auto["time"]) * 30), "dp_before": float(fang_auto["details"]["before"]), "dp_after": float(fang_auto["details"]["after"]), "amount": float(fang_auto["details"]["amount"])},
        "deaths": deaths,
        "vanilla_block_ownership": vanilla_blocks,
        "vanilla_death_unblocks": vanilla_unblocks,
        "first_leaks": first_leaks,
        "key_economic_rejections": [
            {"frame": 1650, "operator_id": "char_240_wyvern", "event": "manual DP skill rejected because operator died at frame 1243"},
            {"frame": 1680, "operator_id": "char_120_hibisc", "event": "DEPLOY rejected: insufficient DP"},
            {"frame": 3000, "operator_id": "char_120_hibisc", "event": "ACTIVATE_SKILL rejected because deployment at 1680 never occurred"},
            {"frame": 4200, "operator_id": "char_122_beagle", "event": "ACTIVATE_SKILL rejected because operator died at frame 3516"},
            {"frame": 4650, "operator_id": "char_281_popka", "event": "ACTIVATE_SKILL rejected because operator died at frame 4077"},
        ],
        "action_outcomes": action_outcomes(),
        "boundary": "Conditional current-runtime diagnostic facts; not real-game proof and not a claim of strategic infeasibility.",
        "source": str((DIAGNOSTIC / "diagnostic_summary.json").relative_to(ROOT)),
    }


def previous_c2_plan_summary() -> dict[str, Any]:
    plan = load(C2_OUT / "llm_structured_output.json")["revised_operational_plans"][0]
    return {key: plan.get(key) for key in (
        "operational_plan_id", "tactical_thesis", "selected_low_star_operator_ids",
        "deployment_positions_and_directions", "action_timeline", "corridor_responsibilities",
        "pressure_window_responsibilities", "skill_intents", "mandatory_tactical_invariants",
        "unknown_dependencies",
    )}


def evidence_context() -> dict[str, Any]:
    base = load(C2_OUT / "llm_evidence_context.json")
    base.pop("previous_c1_plan_to_revise", None)
    base.update({
        "milestone": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1",
        "normal_low_star_catalog": compact_operator_catalog(),
        "c2_failure_evidence": c2_failure_evidence(),
        "previous_c2_plan_to_revise": previous_c2_plan_summary(),
        "decision_task": {
            "full_stage_scope": True,
            "win_scope": "full_stage_until_simulator_WIN_or_LOSS_after_all_spawn_events",
            "one_operational_plan": True,
            "readonly_tool_call_limit": MAX_TOOL_CALLS,
            "model_request_limit_including_continuations": MAX_MODEL_REQUESTS,
            "learning_task": "Absorb the C2 death -> lost income -> lost blocking ownership -> leak chain without losing zero-leak scope.",
            "required_uncertainty_discipline": "Do not turn conditional runtime results or UNKNOWN mechanics into real-game impossibility claims.",
        },
        "provenance": {
            "facts": file_record(FACTS),
            "mechanism_support": file_record(SUPPORT),
            "previous_c2_plan": file_record(C2_OUT / "llm_structured_output.json"),
            "c2_static_check": file_record(C2_OUT / "static_compile_results.json"),
            "c2_diagnostic_summary": file_record(DIAGNOSTIC / "diagnostic_summary.json"),
            "c2_diagnostic_events": file_record(DIAGNOSTIC / "diagnostic_events.json"),
            "generation_code": file_record(Path(__file__)),
        },
    })
    return base


def compactness_check(evidence: dict[str, Any], payload: dict[str, Any], body: str) -> dict[str, Any]:
    catalog = evidence.get("normal_low_star_catalog") or []
    three_stars = [row for row in catalog if row.get("identity", {}).get("rarity") == 3]
    checks = {
        "body_bytes_at_or_below_limit": len(body.encode()) <= INITIAL_BODY_LIMIT,
        "continuation_limit_configured": CONTINUATION_BODY_LIMIT == 200_000,
        "all_34_low_stars_present": len(catalog) == 34,
        "all_17_three_stars_present": len(three_stars) == 17,
        "c2_failure_evidence_present": bool(evidence.get("c2_failure_evidence")),
        "c2_action_outcomes_covered": len(evidence.get("c2_failure_evidence", {}).get("action_outcomes") or []) == len(evidence.get("previous_c2_plan_to_revise", {}).get("action_timeline") or []),
        "no_bulk_diagnostic_events_embedded": "events" not in evidence.get("c2_failure_evidence", {}),
        "query_protocol_unbound_from_final_schema": payload.get("text") is None and payload.get("max_output_tokens") == TOKEN_LIMIT,
        "tools_whitelisted": {row.get("name") for row in payload.get("tools") or []} == {"query_mechanic", "query_range_coverage", "check_timing_constraints"},
    }
    if not all(checks.values()):
        raise RuntimeError("C3 evidence or payload completeness check failed: " + json.dumps(checks, ensure_ascii=False, sort_keys=True))
    return checks


def prompt_text(evidence: dict[str, Any]) -> str:
    return f"""You are Kimi-K3, the tactical decision maker for Arknights main_08-01 / R8-1.
This is the QUERY PHASE for one compact full-stage OperationalPlan C3 using only ordinary-mode 1-3 star operators.

You are revising C2 after its diagnostic LOSS. The decisive model sequence was not merely late damage:
Fang produced 6 DP at frame 570 and enabled Noirc at 600, but died at 890; Vanilla blocked route-2 at 822 and route-6 at 1076, then died at 1243 and released both; Beagle deployed at 1290, so the route-6 enemy leaked at 1295 and route-2 leaked at 1394; Vanilla's frame-1650 DP skill and Hibiscus' frame-1680 deployment then failed. Later Beagle and Popka deaths extended the failure chain. This is conditional current-runtime evidence, not a real-game result or a strategic impossibility proof.

Use the read-only tools to verify assumptions before committing:
- query range coverage for explicit deployment responsibilities.
- query timing constraints for skill readiness, DP payments and deployments.
- query mechanics/stage facts when unsure about coordinates, SP, WIN, roadblocks or support.
Return only native tool calls in this response (up to six). Do not return the final JSON yet.

You decide the new opening structure and support pattern. Python will not choose replacements or move your actions. You may preserve useful C2 ideas, but the plan must explicitly explain:
1. how the opener and early support survive or transfer blocking ownership before death;
2. how DP income and payments remain valid if an opener dies;
3. how route-2 and route-6 handover avoids the 1243->1295/1394 leak chain;
4. how later healing and blocking survive Beagle/Popka deaths;
5. which C2 assumptions changed and which UNKNOWNs remain.

Hard rules:
- Only normal_low_star_catalog operators are legal; rarity 1-3; ordinary_mode true; no mode-specific reserve units.
- Every DEPLOY has integer [row,col] and UP/DOWN/LEFT/RIGHT.
- WIN remains zero leaks, exhausted spawns and no active enemies.
- Do not invent refunds, upkeep, roadblock navigation, target ordering or client timing.
- Keep route responsibilities, phases, pressure windows, skills, healing, blocking, retreats and handovers specific.

The compact evidence JSON follows:

EVIDENCE_JSON
{json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))}
"""


def finalize_plan_payload(payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    finalized = copy.deepcopy(payload)
    finalized["max_output_tokens"] = TOKEN_LIMIT
    finalized["text"] = {
        "format": {
            "name": "r8_1_lowstar_c3_failure_revision_v1",
            "schema": schema,
            "strict": False,
            "type": "json_schema",
        }
    }
    finalized["input"] = list(finalized.get("input") or []) + [{
        "role": "user",
        "content": [{"type": "input_text", "text": (
            "All readonly tool calls have now been executed and returned above. "
            "Return exactly one compact full-stage OperationalPlan C3 as final JSON. "
            "Use only ordinary-mode 1-3 star operators; every DEPLOY must have tile and direction. "
            "Include declared_range_checks for explicit deployment responsibilities; use unknown_reason instead of guessing. "
            "Explain how C2's opener-death, income, blocking-ownership and handover failures are handled. "
            "Do not emit another tool call or non-JSON wrapper."
        )}],
    }]
    errors = validate_tool_request(finalized)
    if errors:
        raise RuntimeError("invalid final continuation: " + ", ".join(errors))
    return finalized


def source_manifest(evidence_path: Path) -> dict[str, Any]:
    paths = [FACTS, SUPPORT, C2_OUT / "llm_structured_output.json", C2_OUT / "static_compile_results.json",
             DIAGNOSTIC / "diagnostic_summary.json", DIAGNOSTIC / "diagnostic_events.json",
             ROOT / "scripts/kimi_readonly_tools.py", ROOT / "scripts/kimi_responses_transport.py",
             ROOT / "scripts/kimi_tool_loop.py", Path(__file__)]
    return {
        "schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_SOURCE_MANIFEST",
        "inputs": {path.name: file_record(path) for path in paths},
        "prepared_evidence": file_record(evidence_path),
        "mechanics_version": MECHANICS,
    }


def validate_c3_contract(parsed: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    errors = validate_final_operational_plan(parsed, evidence, output_schema())
    plans = parsed.get("revised_operational_plans") if isinstance(parsed, dict) else None
    plan = plans[0] if isinstance(plans, list) and len(plans) == 1 else {}
    if not str(plan.get("operational_plan_id", "")).startswith(PLAN_ID_PREFIX):
        errors.append("operational_plan_id must identify C3")
    hypothesis_ids = {
        row.get("hypothesis_id")
        for row in parsed.get("revised_strategic_hypotheses") or []
        if isinstance(row, dict) and row.get("hypothesis_id")
    }
    if plan.get("parent_hypothesis_id") not in hypothesis_ids:
        errors.append("parent_hypothesis_id must reference a revised_strategic_hypotheses hypothesis_id")
    if len(plan.get("revised_operational_plans") or plan.get("action_timeline") or []) == 0:
        errors.append("C3 action timeline is empty")
    if parsed.get("provenance", {}).get("revision_source", {}).get("operational_plan_id") != PARENT_PLAN_ID:
        errors.append("provenance.revision_source must identify C2")
    return errors


def prepare() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    attempt_path = OUT / "llm_call_attempts.jsonl"
    if attempt_path.exists() and any(line.strip() for line in attempt_path.read_text(encoding="utf-8").splitlines()):
        raise RuntimeError("C3 attempt log already contains calls; refusing to reset or rerun")
    attempt_path.write_text("", encoding="utf-8")
    write_json("budget_usage.json", {
        "schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_BUDGET",
        "max_model_requests": MAX_MODEL_REQUESTS, "max_readonly_tool_calls": MAX_TOOL_CALLS,
        "model_requests_started": 0, "readonly_tool_calls_executed": 0,
        "automatic_retry": False, "continuation_counts_as_model_request": True,
    })
    evidence = evidence_context()
    evidence_path = OUT / "llm_evidence_context.json"
    write_json("llm_evidence_context.json", evidence)
    schema = output_schema()
    write_json("revision_output_schema.json", schema)
    prompt = prompt_text(evidence)
    write_text("constraint_informed_prompt.txt", prompt)
    base_payload = {
        "model": MODEL, "stream": True,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "max_output_tokens": TOKEN_LIMIT,
    }
    payload = build_tool_enabled_request(base_payload)
    errors = validate_tool_request(payload)
    if errors:
        raise RuntimeError("invalid prepared C3 tool request: " + ", ".join(errors))
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    write_json("compactness_check.json", compactness_check(evidence, payload, body))
    write_text("llm_request_body.txt", body)
    write_json("llm_request.json", payload)
    write_json("llm_request_fingerprint.json", {
        "request_sha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(), "body_bytes": len(body.encode()),
    })
    write_json("source_manifest.json", source_manifest(evidence_path))
    write_json("prepare_status.json", {"phase": "PREPARED", "schema": "r8_1_lowstar_c3_failure_revision_v1"})
    return payload


def append_attempt(record: dict[str, Any]) -> None:
    with (OUT / "llm_call_attempts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def update_budget(model_requests: int | None = None, tool_calls: int | None = None) -> None:
    path = OUT / "budget_usage.json"
    state = load(path)
    if model_requests is not None:
        state["model_requests_started"] = max(state["model_requests_started"], model_requests)
    if tool_calls is not None:
        state["readonly_tool_calls_executed"] = max(state["readonly_tool_calls_executed"], tool_calls)
    write_json("budget_usage.json", state)


def make_stream_once(start_attempt: int = 0) -> Any:
    attempts = start_attempt

    def stream_once(payload: dict[str, Any]) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
        nonlocal attempts
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        continuation = any(item.get("type") == "function_call_output" for item in payload.get("input", []))
        body_limit = CONTINUATION_BODY_LIMIT if continuation else INITIAL_BODY_LIMIT
        if len(body) > body_limit:
            raise RuntimeError(f"request body exceeds {body_limit} bytes before network: {len(body)}")
        attempts += 1
        update_budget(model_requests=attempts)
        (OUT / f"attempt_{attempts}_request.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (OUT / f"attempt_{attempts}_request_body.txt").write_bytes(body)
        credential = os.environ.get("ARK_API_KEY_agent")
        if not credential:
            raise RuntimeError("ARK_API_KEY_agent is not set")
        request = urllib.request.Request(BASE_URL, data=body, method="POST", headers={
            "Accept": "text/event-stream", "Authorization": f"Bearer {credential}", "Content-Type": "application/json",
        })
        append_attempt({
            "attempt": attempts, "phase": "STARTED", "started_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": BASE_URL, "model": MODEL, "max_output_tokens": payload.get("max_output_tokens"),
            "request_body_sha256": hashlib.sha256(body).hexdigest(), "continuation": continuation,
            "body_bytes": len(body), "body_limit": body_limit,
        })
        accumulator = StreamAccumulator()
        http_status = None
        request_id = None
        chunks: list[bytes] = []
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                http_status = response.status
                request_id = response.headers.get("x-request-id")
                for raw_bytes in response:
                    chunks.append(raw_bytes)
        except urllib.error.HTTPError as exc:
            chunks.append(exc.read())
            http_status = exc.code
            request_id = exc.headers.get("x-request-id") if exc.headers else request_id
            accumulator.error = f"HTTP {exc.code}: {chunks[-1].decode(errors='replace')}"
        except (TimeoutError, socket.timeout) as exc:
            accumulator.error = f"TIMEOUT: {exc}"
        except urllib.error.URLError as exc:
            accumulator.error = f"URL_ERROR: {exc.reason}"
        except OSError as exc:
            accumulator.error = f"NETWORK_OR_STREAM_INTERRUPTED: {exc}"
        raw = b"".join(chunks)
        (OUT / f"attempt_{attempts}_raw_response.txt").write_bytes(raw)
        for event in parse_sse(raw.decode("utf-8", errors="replace")):
            accumulator.observe(event)
        accumulator.http_status = http_status
        accumulator.request_id = request_id
        append_attempt({
            "attempt": attempts, "phase": "FINISHED", "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": accumulator.terminal_event or "ATTEMPT_FAILED", "error": accumulator.error,
            "http_status": http_status, "request_id": request_id,
            "response_sha256": hashlib.sha256(raw).hexdigest(), "response_bytes": len(raw),
        })
        write_json(f"attempt_{attempts}_classification.json", accumulator.classify())
        return accumulator.response_envelope or {}, accumulator, raw

    return stream_once


def call() -> dict[str, Any]:
    evidence_path = OUT / "llm_evidence_context.json"
    schema_path = OUT / "revision_output_schema.json"
    request_path = OUT / "llm_request.json"
    for path in (evidence_path, schema_path, request_path):
        if not path.is_file():
            raise RuntimeError(f"missing prepared input: {path}")
    if load(OUT / "budget_usage.json").get("model_requests_started", 0) > 0:
        raise RuntimeError("C3 budget already consumed; restart cannot reset or retry")
    payload = load(request_path)
    evidence = load(evidence_path)
    schema = load(schema_path)
    budget = ToolLoopBudget(max_model_requests=MAX_MODEL_REQUESTS, max_tool_calls=MAX_TOOL_CALLS)
    engine = ReadOnlyQueryEngine(evidence_path=evidence_path)
    session = run_mock_tool_session(
        payload, engine, make_stream_once(), evidence=evidence, plan_schema=schema, budget=budget,
        finalize_payload=lambda item: finalize_plan_payload(item, schema),
        validate_plan=lambda parsed: validate_c3_contract(parsed, evidence),
    )
    update_budget(model_requests=budget.model_requests_started, tool_calls=budget.tool_calls_executed)
    write_json("tool_loop_session.json", session)
    write_json("tool_loop_budget.json", session.get("budget", budget.__dict__))
    if session.get("status") != "COMPLETE":
        write_json("final_status.json", {
            "schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_FINAL_STATUS",
            "status": "FAILED_NO_RETRY", "failure": session, "budget_usage": load(OUT / "budget_usage.json"),
        })
        raise SystemExit("C3 tool session failed without retry")
    parsed = session["operational_plan"]
    plan_errors = validate_c3_contract(parsed, evidence)
    if plan_errors:
        write_json("llm_plan_validation.json", {"schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_PLAN_VALIDATION", "status": "FAIL", "errors": plan_errors})
        raise RuntimeError("C3 failed local contract validation")
    write_json("llm_structured_output.json", parsed)
    write_json("llm_plan_validation.json", {
        "schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_PLAN_VALIDATION",
        "status": "PASS", "evidence_path": str(evidence_path.relative_to(ROOT)),
    })
    plans = parsed.get("revised_operational_plans", [])
    write_json("grounding_validation.json", {
        "one_operational_plan": len(plans) == 1,
        "selected_operator_ids": plans[0].get("selected_low_star_operator_ids", []) if plans else [],
        "direction_complete_deploys": all(action.get("action_type") != "DEPLOY" or (action.get("tile") and action.get("direction")) for action in (plans[0].get("action_timeline", []) if plans else [])),
        "status": "PASS" if len(plans) == 1 else "FAIL",
    })
    write_json("final_status.json", {
        "schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_FINAL_STATUS",
        "status": "C3_RECEIVED_AND_CONTRACT_VALID",
        "actual_model_requests": budget.model_requests_started,
        "actual_readonly_tool_calls": budget.tool_calls_executed,
        "new_operational_plans": len(plans), "stage_simulations": 0, "tactical_search_expansions": 0,
        "static_compile_check": "PENDING",
    })
    return parsed


def tool_forced_session() -> dict[str, Any]:
    for name in ("final_status.json", "budget_usage.json"):
        source = OUT / name
        backup = OUT / f"{name.removesuffix('.json')}_after_attempt1.json"
        if source.is_file() and not backup.exists():
            backup.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    evidence_path = OUT / "llm_evidence_context.json"
    schema_path = OUT / "revision_output_schema.json"
    for path in (evidence_path, schema_path):
        if not path.is_file():
            raise RuntimeError(f"missing tool-forced input: {path}")
    state = load(OUT / "budget_usage.json")
    if state.get("model_requests_started") != 1:
        raise RuntimeError("tool-forced session requires exactly one counted prior request")
    payload = load(OUT / "attempt_1_request.json")
    evidence = load(evidence_path)
    schema = load(schema_path)
    payload["tool_choice"] = "required"
    payload["input"][0]["content"][0]["text"] += (
        "\n\nSECOND_ATTEMPT_PROTOCOL_GUARD: The prior response used its entire output budget on hidden reasoning and ended "
        "response.incomplete with no assistant message and no native tool call. This is a deliberate, separately recorded "
        "attempt, not an automatic retry. Do not perform exhaustive tactical search before tools. Return only native "
        "function calls for at most six high-value readonly checks. If a final JSON is requested later, emit it directly."
    )
    errors = validate_tool_request(payload)
    if errors:
        raise RuntimeError("invalid tool-forced request: " + ", ".join(errors))
    budget = ToolLoopBudget(max_model_requests=MAX_MODEL_REQUESTS, max_tool_calls=MAX_TOOL_CALLS)
    engine = ReadOnlyQueryEngine(evidence_path=evidence_path)
    session = run_mock_tool_session(
        payload, engine, make_stream_once(start_attempt=1), evidence=evidence, plan_schema=schema, budget=budget,
        finalize_payload=lambda item: finalize_plan_payload(item, schema),
        validate_plan=lambda parsed: validate_c3_contract(parsed, evidence),
    )
    update_budget(model_requests=1 + budget.model_requests_started, tool_calls=budget.tool_calls_executed)
    write_json("tool_loop_tool_forced_session.json", session)
    write_json("tool_loop_budget.json", load(OUT / "budget_usage.json"))
    if session.get("status") != "COMPLETE":
        write_json("final_status.json", {
            "schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_FINAL_STATUS",
            "status": "FAILED_NO_RETRY", "failure": session, "prior_attempt_status": "RESPONSE_INCOMPLETE",
            "tool_choice_attempt": {"field": "tool_choice", "value": "required", "provider_support": "UNVERIFIED_BEFORE_REQUEST"},
            "budget_usage": load(OUT / "budget_usage.json"),
        })
        raise SystemExit("C3 tool-forced session failed without retry")
    parsed = session["operational_plan"]
    plan_errors = validate_c3_contract(parsed, evidence)
    if plan_errors:
        write_json("llm_plan_validation.json", {"schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_PLAN_VALIDATION", "status": "FAIL", "errors": plan_errors})
        raise RuntimeError("C3 failed local contract validation")
    write_json("llm_structured_output.json", parsed)
    write_json("llm_plan_validation.json", {
        "schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_PLAN_VALIDATION",
        "status": "PASS", "evidence_path": str(evidence_path.relative_to(ROOT)),
    })
    plans = parsed.get("revised_operational_plans", [])
    write_json("grounding_validation.json", {
        "one_operational_plan": len(plans) == 1,
        "selected_operator_ids": plans[0].get("selected_low_star_operator_ids", []) if plans else [],
        "direction_complete_deploys": all(action.get("action_type") != "DEPLOY" or (action.get("tile") and action.get("direction")) for action in (plans[0].get("action_timeline", []) if plans else [])),
        "status": "PASS" if len(plans) == 1 else "FAIL",
    })
    write_json("final_status.json", {
        "schema_version": "R8_1_LOWSTAR_C3_FAILURE_REVISION_V1_FINAL_STATUS",
        "status": "C3_RECEIVED_AND_CONTRACT_VALID",
        "actual_model_requests": 1 + budget.model_requests_started,
        "actual_readonly_tool_calls": budget.tool_calls_executed,
        "new_operational_plans": len(plans), "stage_simulations": 0, "tactical_search_expansions": 0,
        "static_compile_check": "PENDING",
    })
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "call", "tool_forced"])
    arguments = parser.parse_args()
    if arguments.phase == "prepare":
        prepare()
        return
    if arguments.phase == "tool_forced":
        tool_forced_session()
        return
    call()


if __name__ == "__main__":
    main()
