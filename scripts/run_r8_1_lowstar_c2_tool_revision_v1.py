from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import socket
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from run_r8_1_low_star_full_tactical_closure_v1 import (
    compact_operator_catalog,
    evidence_context as closure_evidence_context,
    output_schema,
)
from kimi_readonly_tools import BASE_RULE_CARD, ReadOnlyQueryEngine
from kimi_responses_transport import StreamAccumulator, parse_sse
from kimi_tool_loop import (
    ToolLoopBudget,
    execute_tool_calls,
    build_tool_continuation_payload,
    build_tool_enabled_request,
    run_mock_tool_session,
    validate_final_operational_plan,
    validate_tool_request,
)


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output/r8_1_lowstar_c2_compact_tool_revision_v2"
C1_PLAN = ROOT / "output/r8_1_low_star_full_tactical_closure_v2/llm_structured_output.json"
FACTS = ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json"
SUPPORT = ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json"
BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/responses"
MODEL = "kimi-k3"
MECHANICS = "m18.9-stage-device-runtime-v1"
TIMEOUT_SECONDS = 900
QUERY_TOKEN_LIMIT = 32768
FINAL_TOKEN_LIMIT = 32768
MAX_REQUEST_BODY_BYTES = 140_000
CONTINUATION_BODY_LIMIT = 200_000
MAX_MODEL_REQUESTS = 3
MAX_TOOL_CALLS = 6


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


def previous_plan_summary() -> dict[str, Any]:
    parsed = load(C1_PLAN)
    plan = parsed["revised_operational_plans"][0]
    return {
        "operational_plan_id": plan.get("operational_plan_id"),
        "tactical_thesis": plan.get("tactical_thesis"),
        "selected_low_star_operator_ids": plan.get("selected_low_star_operator_ids"),
        "deployment_positions_and_directions": plan.get("deployment_positions_and_directions"),
        "action_timeline": plan.get("action_timeline"),
        "corridor_responsibilities": plan.get("corridor_responsibilities"),
        "pressure_window_responsibilities": plan.get("pressure_window_responsibilities"),
        "skill_intents": plan.get("skill_intents"),
        "conditional_responsibilities": plan.get("conditional_responsibilities"),
    }


def c1_counterexamples() -> list[dict[str, Any]]:
    return [
        {
            "counterexample_id": "C1_RANGE_HIBISCUS_UP",
            "operator_id": "char_120_hibisc",
            "configuration": "ordinary 3-star debug configuration",
            "tile_json_row_col": [5, 7], "direction": "UP",
            "not_covered_targets_json_row_col": [[4, 6], [4, 7]],
            "status": "CONDITIONAL_MODEL_COUNTEREXAMPLE_VERIFY_WITH_QUERY_RANGE_COVERAGE",
        },
        {
            "counterexample_id": "C1_RANGE_STWARD_UP",
            "operator_id": "char_210_stward",
            "configuration": "ordinary 3-star debug configuration",
            "tile_json_row_col": [5, 6], "direction": "UP",
            "not_covered_targets_json_row_col": [[4, 6], [4, 7]],
            "status": "CONDITIONAL_MODEL_COUNTEREXAMPLE_VERIFY_WITH_QUERY_RANGE_COVERAGE",
        },
        {
            "counterexample_id": "C1_RANGE_LANCET_LEFT",
            "operator_id": "char_285_medic2",
            "configuration": "ordinary 1-star debug configuration",
            "tile_json_row_col": [2, 9], "direction": "LEFT",
            "covered_target_json_row_col": [1, 7],
            "not_covered_target_json_row_col": [1, 6],
            "status": "CONDITIONAL_MODEL_COUNTEREXAMPLE_VERIFY_WITH_QUERY_RANGE_COVERAGE",
        },
        {
            "counterexample_id": "C1_HIBISCUS_SECOND_SKILL",
            "operator_id": "char_120_hibisc",
            "first_activation_frame": 3000,
            "first_activation_assumption": "successful",
            "declared_second_activation_frame": 4200,
            "model_earliest_ready_frame": 4500,
            "sp_model": "time recovery 1/s while inactive; paused during effect",
            "status": "CONDITIONAL_MODEL_COUNTEREXAMPLE_VERIFY_WITH_CHECK_TIMING_CONSTRAINTS",
        },
        {
            "counterexample_id": "C1_WIN_RULE",
            "c1_target": "at most 4 leaks",
            "current_simulator_win_rule": "zero leaks, all spawn events consumed, no active enemies",
            "status": "CONFIRMED_FROM_CURRENT_PUBLIC_RUNTIME_CODE",
        },
    ]


def evidence_context() -> dict[str, Any]:
    base = closure_evidence_context()
    return {
        "milestone": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2",
        "stage_id": base["stage_id"],
        "mechanics_version": MECHANICS,
        "gamedata_commit": base["gamedata_commit"],
        "authoritative_policy": {
            "ordinary_mode_only": True,
            "rarity_range": [1, 3],
            "exclude_mode_specific_reserve_operators": True,
            "three_star_ordinary_catalog_count_must_be_17": True,
            "debug_configuration": "3★ E1/max level, skill rank 7, potential 1, trust 0; 1★/2★ phase 0/max level; all trust 0",
        },
        "stage_options": base["stage_options"],
        "enemy_facts": base["enemy_facts"],
        "source_routes": base["source_routes"],
        "source_wave_schedule": base["source_wave_schedule"],
        "model_spawn_timeline": base["model_spawn_timeline"],
        "stage_active_facts": base["stage_active_facts"],
        "roadblock_evidence": base["roadblock_evidence"],
        "simulation_domain": base["simulation_domain"],
        "normal_low_star_catalog": compact_operator_catalog(),
        "normal_low_star_support_counts": load(SUPPORT)["counts"],
        "base_rule_card": BASE_RULE_CARD,
        "c1_conditioned_counterexamples": c1_counterexamples(),
        "previous_c1_plan_to_revise": previous_plan_summary(),
        "decision_task": {
            "full_stage_scope": True,
            "win_scope": "full_stage_until_simulator_WIN_or_LOSS_after_all_spawn_events",
            "one_operational_plan": True,
            "readonly_tool_call_limit": MAX_TOOL_CALLS,
            "model_request_limit_including_continuations": MAX_MODEL_REQUESTS,
            "required_uncertainty_discipline": "Do not turn model-derived counterexamples or UNKNOWN mechanics into confirmed game impossibility.",
        },
        "provenance": {
            "facts": file_record(FACTS),
            "mechanism_support": file_record(SUPPORT),
            "previous_c1_plan": file_record(C1_PLAN),
            "generation_code": file_record(Path(__file__)),
        },
    }


def compactness_check(evidence: dict[str, Any], payload: dict[str, Any], body: str) -> dict[str, Any]:
    catalog = evidence.get("normal_low_star_catalog") or []
    three_stars = [row for row in catalog if row.get("identity", {}).get("rarity") == 3]
    checks = {
        "body_bytes_at_or_below_limit": len(body.encode()) <= MAX_REQUEST_BODY_BYTES,
        "all_34_low_stars_present": len(catalog) == 34,
        "all_17_three_stars_present": len(three_stars) == 17,
        "compact_rows_have_runtime_support": all("runtime_support" in row for row in catalog),
        "duplicate_full_support_table_absent": "normal_low_star_mechanism_support" not in evidence,
        "action_window_frames_absent": "action_window_frames" not in evidence.get("decision_task", {}),
        "c1_counterexamples_present": len(evidence.get("c1_conditioned_counterexamples") or []) == 5,
        "stage_routes_present": len(evidence.get("source_routes") or []) >= 30,
        "stage_wave_schedule_present": bool(evidence.get("source_wave_schedule")),
        "roadblocks_present": len((evidence.get("stage_active_facts") or {}).get("roadblock_tiles_col_row") or []) == 5,
        "query_protocol_unbound_from_final_schema": payload.get("text") is None and payload.get("max_output_tokens") == QUERY_TOKEN_LIMIT,
        "tools_whitelisted": {row.get("name") for row in payload.get("tools") or []} == {"query_mechanic", "query_range_coverage", "check_timing_constraints"},
    }
    if not all(checks.values()):
        raise RuntimeError("compact evidence or query payload completeness check failed: " + json.dumps(checks, ensure_ascii=False, sort_keys=True))
    return checks


def prompt_text(evidence: dict[str, Any]) -> str:
    return f"""You are Kimi-K3, the tactical decision maker for Arknights main_08-01 / R8-1.
This is the QUERY PHASE for one compact full-stage OperationalPlan C2 using only ordinary-mode 1-3 star operators.

Use the supplied C1 conditioned counterexamples as tactical feedback, then actively verify candidate assumptions with the read-only tools:
- query range coverage for any deployment responsibility you intend to rely on.
- query timing constraints for skill readiness, DP payments and same-frame deployment economy.
- query mechanics/stage facts when unsure about coordinates, SP, damage, WIN rule, roadblocks or affordance support.
Do not merely describe a tool call. The deterministic loop must execute a native tool call and return its result.
In this response, return only native tool calls (up to six). Do not return the final OperationalPlan JSON.

You must revise C1 yourself. Do not copy it unchanged. Explicitly absorb these points:
1. Hibiscus at [5,7] UP does not cover [4,6]/[4,7] in the current range model.
2. Stward at [5,6] UP does not cover [4,6]/[4,7].
3. Lancet-2 at [2,9] LEFT covers Melantha [1,7] but not Noirc [1,6].
4. With Hibiscus first skill successfully active at frame 3000, the current time-SP model makes frame 4200 too early; the conditional earliest is about frame 4500.
5. WIN requires zero leaks, exhausted spawns and no active enemies. “At most 4 leaks” is not a WIN.

Hard rules:
- Only operators in normal_low_star_catalog are legal. Rarity must be 1-3, ordinary_mode must be true, and mode-specific reserve operators are forbidden.
- Every DEPLOY must have a tile and one of UP/DOWN/LEFT/RIGHT.
- Do not invent mechanics, statistics, refunds, upkeep behavior, roadblock navigation or target ordering.
- Treat unsupported mechanics as conditional/optional, never as mandatory proof.
- Preserve route responsibilities, phases, pressure windows, skills, healing, blocking, retreats and handovers in the plan.
- Be compact, but do not omit tactical semantics required by the schema.
- State which C1 assumptions changed, which counterexamples were absorbed, and what remains UNKNOWN.

The compact evidence JSON follows:

EVIDENCE_JSON
{json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))}
"""


def finalize_plan_payload(payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    finalized = copy.deepcopy(payload)
    finalized["max_output_tokens"] = FINAL_TOKEN_LIMIT
    finalized["text"] = {
        "format": {
            "name": "r8_1_lowstar_c2_compact_tool_revision_v2",
            "schema": schema,
            "strict": False,
            "type": "json_schema",
        }
    }
    finalized["input"] = list(finalized.get("input") or []) + [{
        "role": "user",
        "content": [{"type": "input_text", "text": (
            "All readonly tool calls have now been executed and returned above. "
            "Return exactly one compact OperationalPlan C2 as final JSON. "
            "Use only ordinary-mode 1-3 star operators; every DEPLOY must have tile and direction. "
            "Include declared_range_checks for each explicit deployment responsibility. Each row needs operator_id, tile, direction, responsibility_kind and exact targets; use unknown_reason instead of guessing when no concrete target is known. "
            "Explain absorbed C1 counterexamples, changed assumptions, conditional semantics and UNKNOWNs. "
            "Do not emit another tool call, reasoning-only response, or non-JSON wrapper."
        )}],
    }]
    errors = validate_tool_request(finalized)
    if errors:
        raise RuntimeError("invalid final continuation: " + ", ".join(errors))
    return finalized


def source_manifest(evidence_path: Path) -> dict[str, Any]:
    paths = [FACTS, SUPPORT, C1_PLAN, ROOT / "scripts/kimi_readonly_tools.py", ROOT / "scripts/kimi_responses_transport.py", ROOT / "scripts/kimi_tool_loop.py", Path(__file__)]
    return {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_SOURCE_MANIFEST",
        "inputs": {path.name: file_record(path) for path in paths},
        "prepared_evidence": file_record(evidence_path),
        "mechanics_version": MECHANICS,
    }


def prepare() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    attempt_path = OUT / "llm_call_attempts.jsonl"
    if attempt_path.exists() and any(line.strip() for line in attempt_path.read_text(encoding="utf-8").splitlines()):
        raise RuntimeError("budgeted attempt log already contains calls; refusing to reset or rerun")
    attempt_path.write_text("", encoding="utf-8")
    write_json("budget_usage.json", {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_BUDGET",
        "max_model_requests": MAX_MODEL_REQUESTS,
        "max_readonly_tool_calls": MAX_TOOL_CALLS,
        "model_requests_started": 0,
        "readonly_tool_calls_executed": 0,
        "automatic_retry": False,
        "continuation_counts_as_model_request": True,
    })
    evidence = evidence_context()
    evidence_path = OUT / "llm_evidence_context.json"
    write_json("llm_evidence_context.json", evidence)
    schema = output_schema()
    write_json("revision_output_schema.json", schema)
    prompt = prompt_text(evidence)
    write_text("constraint_informed_prompt.txt", prompt)
    base_payload = {
        "model": MODEL,
        "stream": True,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "max_output_tokens": QUERY_TOKEN_LIMIT,
    }
    payload = build_tool_enabled_request(base_payload)
    errors = validate_tool_request(payload)
    if errors:
        raise RuntimeError("invalid prepared tool request: " + ", ".join(errors))
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    write_json("compactness_check.json", compactness_check(evidence, payload, body))
    write_text("llm_request_body.txt", body)
    write_json("llm_request.json", payload)
    write_json("llm_request_fingerprint.json", {
        "request_sha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "body_bytes": len(body.encode()),
    })
    write_json("source_manifest.json", source_manifest(evidence_path))
    write_json("prepare_status.json", {"phase": "PREPARED", "schema": "r8_1_lowstar_c2_compact_tool_revision_v2"})
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


def make_stream_once(body_limit: int = MAX_REQUEST_BODY_BYTES, start_attempt: int = 0) -> Any:
    attempts = start_attempt

    def stream_once(payload: dict[str, Any]) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
        nonlocal attempts
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        if len(body) > body_limit:
            raise RuntimeError(f"request body exceeds {body_limit} bytes before network: {len(body)}")
        attempts += 1
        update_budget(model_requests=attempts)
        request_path = OUT / f"attempt_{attempts}_request.json"
        request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (OUT / f"attempt_{attempts}_request_body.txt").write_bytes(body)
        credential = os.environ.get("ARK_API_KEY_agent")
        if not credential:
            raise RuntimeError("ARK_API_KEY_agent is not set")
        request = urllib.request.Request(
            BASE_URL,
            data=body,
            method="POST",
            headers={"Accept": "text/event-stream", "Authorization": f"Bearer {credential}", "Content-Type": "application/json"},
        )
        append_attempt({
            "attempt": attempts,
            "phase": "STARTED",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": BASE_URL,
            "model": MODEL,
            "max_output_tokens": payload.get("max_output_tokens"),
            "request_body_sha256": hashlib.sha256(body).hexdigest(),
            "continuation": any(item.get("type") == "function_call_output" for item in payload.get("input", [])),
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
            "attempt": attempts,
            "phase": "FINISHED",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": accumulator.terminal_event or "ATTEMPT_FAILED",
            "error": accumulator.error,
            "http_status": http_status,
            "request_id": request_id,
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "response_bytes": len(raw),
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
    budget_state = load(OUT / "budget_usage.json")
    if budget_state.get("model_requests_started", 0) > 0:
        raise RuntimeError("budget already consumed; restart cannot reset or retry")
    payload = load(request_path)
    evidence = load(evidence_path)
    schema = load(schema_path)
    budget = ToolLoopBudget(max_model_requests=MAX_MODEL_REQUESTS, max_tool_calls=MAX_TOOL_CALLS)
    engine = ReadOnlyQueryEngine(evidence_path=evidence_path)
    session = run_mock_tool_session(
        payload,
        engine,
        make_stream_once(),
        evidence=evidence,
        plan_schema=schema,
        budget=budget,
        finalize_payload=lambda payload: finalize_plan_payload(payload, schema),
    )
    update_budget(model_requests=budget.model_requests_started, tool_calls=budget.tool_calls_executed)
    write_json("tool_loop_session.json", session)
    write_json("tool_loop_budget.json", session.get("budget", budget.__dict__))
    if session.get("status") != "COMPLETE":
        write_json("final_status.json", {
            "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_FINAL_STATUS",
            "status": "FAILED_NO_RETRY",
            "failure": session,
            "budget_usage": load(OUT / "budget_usage.json"),
        })
        raise SystemExit("C2 tool session failed without retry")
    parsed = session["operational_plan"]
    write_json("llm_structured_output.json", parsed)
    validation = {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_PLAN_VALIDATION",
        "schema": "r8_1_lowstar_c2_compact_tool_revision_v2",
        "evidence_path": str(evidence_path.relative_to(ROOT)),
        "schema_errors": sorted(Draft7Validator(schema).iter_errors(parsed), key=lambda error: list(error.path)),
        "status": "PASS",
    }
    validation["schema_errors"] = [
        f"schema: {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in validation["schema_errors"]
    ]
    if validation["schema_errors"]:
        validation["status"] = "FAIL"
        write_json("llm_plan_validation.json", validation)
        raise RuntimeError("final C2 plan failed schema validation")
    plans = parsed.get("revised_operational_plans", [])
    write_json("llm_plan_validation.json", validation)
    write_json("grounding_validation.json", {
        "one_operational_plan": len(plans) == 1,
        "selected_operator_ids": plans[0].get("selected_low_star_operator_ids", []) if plans else [],
        "direction_complete_deploys": all(
            action.get("action_type") != "DEPLOY" or (action.get("tile") and action.get("direction"))
            for action in (plans[0].get("action_timeline", []) if plans else [])
        ),
        "status": "PASS" if len(plans) == 1 else "FAIL",
    })
    write_json("final_status.json", {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_FINAL_STATUS",
        "status": "C2_RECEIVED_AND_CONTRACT_VALID",
        "interface_status": session.get("status"),
        "actual_model_requests": budget.model_requests_started,
        "actual_readonly_tool_calls": budget.tool_calls_executed,
        "new_operational_plans": len(plans),
        "stage_simulations": 0,
        "tactical_search_expansions": 0,
        "static_compile_check": "PENDING",
    })
    return parsed


def resume() -> dict[str, Any]:
    budget_state = load(OUT / "budget_usage.json")
    if budget_state.get("model_requests_started") != 2:
        raise RuntimeError("resume requires the saved V2 state: 2 counted requests")
    if (OUT / "attempt_3_request_body.txt").exists():
        raise RuntimeError("resume already ran; refusing to reset, retry, or re-execute saved calls")
    saved_session_path = OUT / "tool_loop_session.json"
    saved_session = load(saved_session_path)
    if saved_session.get("status") != "FAILED" or saved_session.get("error") != "model request failed":
        raise RuntimeError("saved V2 session does not match the blocked final-continuation state")
    trajectories = saved_session.get("trajectories") or []
    if len(trajectories) != 1:
        raise RuntimeError("expected exactly one saved native tool trajectory")
    calls = trajectories[0].get("calls") or []
    original_results = trajectories[0].get("tool_results") or []
    if len(calls) != 6 or len(original_results) != 6:
        raise RuntimeError("expected exactly six saved native function calls and results")

    evidence_path = OUT / "llm_evidence_context.json"
    schema_path = OUT / "revision_output_schema.json"
    request_path = OUT / "attempt_1_request.json"
    for name in ("llm_evidence_context.json", "revision_output_schema.json", "attempt_1_request.json"):
        if not (OUT / name).is_file():
            raise RuntimeError(f"missing resume input: {OUT / name}")
    evidence = load(evidence_path)
    schema = load(schema_path)
    request = load(request_path)
    range_calls = [row for row in calls if row.get("name") == "query_range_coverage"]
    timing_calls = [row for row in calls if row.get("name") == "check_timing_constraints"]
    if len(range_calls) != 5 or len(timing_calls) != 1:
        raise RuntimeError("expected five saved range calls and one timing call")
    if any(row.get("name") != "check_timing_constraints" or row.get("status") != "EXECUTED" for row in original_results if row.get("call_id") == timing_calls[0].get("call_id")):
        raise RuntimeError("saved timing call result was not executed")

    for source, target in (
        ("final_status.json", "final_status_pre_resume.json"),
        ("budget_usage.json", "budget_usage_pre_resume.json"),
        ("source_manifest.json", "source_manifest_pre_resume.json"),
    ):
        if (OUT / source).is_file() and not (OUT / target).exists():
            shutil.copy2(OUT / source, OUT / target)

    engine = ReadOnlyQueryEngine(evidence_path=evidence_path)
    if (OUT / "revalidated_range_tool_calls.json").is_file():
        saved_revalidation = load(OUT / "revalidated_range_tool_calls.json")
        if saved_revalidation.get("status") != "PASS" or len(saved_revalidation.get("rows") or []) != 5:
            raise RuntimeError("saved range revalidation is not a complete five-call PASS record")
        if budget_state.get("readonly_tool_calls_executed") != 6:
            raise RuntimeError("saved revalidation requires 6 total executed tools")
        revalidated_rows = saved_revalidation["rows"]
        expected_ids = {call.get("call_id") for call in range_calls}
        if {row.get("call_id") for row in revalidated_rows} != expected_ids:
            raise RuntimeError("saved range revalidation call_ids do not match saved calls")
    else:
        if budget_state.get("readonly_tool_calls_executed") != 1:
            raise RuntimeError("fresh revalidation requires the saved state: 1 executed tool")
        revalidation_budget = ToolLoopBudget(max_model_requests=0, max_tool_calls=MAX_TOOL_CALLS)
        revalidated_rows = []
        for call in range_calls:
            row = execute_tool_calls([call], engine, revalidation_budget)[0]
            revalidated_rows.append({
                "call_id": call.get("call_id"),
                "original_result": next(item for item in original_results if item.get("call_id") == call.get("call_id")),
                "revalidated_result": row,
            })
        if revalidation_budget.tool_calls_executed != 5 or any(row["revalidated_result"].get("status") != "EXECUTED" for row in revalidated_rows):
            update_budget(tool_calls=revalidation_budget.tool_calls_executed)
            write_json("revalidated_range_tool_calls.json", {
                "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_RANGE_REVALIDATION",
                "status": "FAILED_NO_RETRY",
                "rows": revalidated_rows,
            })
            raise SystemExit("saved range-call revalidation failed without retry")
        update_budget(tool_calls=6)
        write_json("revalidated_range_tool_calls.json", {
            "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_RANGE_REVALIDATION",
            "status": "PASS",
            "scope": "Saved completed function_calls only; the existing timing result was preserved and not re-executed.",
            "rows": revalidated_rows,
        })

    revalidated_by_call = {row["revalidated_result"].get("call_id"): row["revalidated_result"] for row in revalidated_rows}
    combined_results = []
    for call, original in zip(calls, original_results):
        combined_results.append(revalidated_by_call.get(call.get("call_id"), original))
    continuation = build_tool_continuation_payload(request, calls, combined_results)
    final_payload = finalize_plan_payload(continuation, schema)
    final_body = json.dumps(final_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    resume_manifest = {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_RESUME_MANIFEST",
        "original_request_body": file_record(OUT / "attempt_1_request_body.txt"),
        "revalidated_results": file_record(OUT / "revalidated_range_tool_calls.json"),
        "final_request_body": {
            "bytes": len(final_body),
            "body_limit": CONTINUATION_BODY_LIMIT,
            "sha256": hashlib.sha256(final_body).hexdigest(),
        },
        "code": {
            "kimi_readonly_tools": file_record(ROOT / "scripts/kimi_readonly_tools.py"),
            "runner": file_record(Path(__file__)),
        },
    }
    write_json("resume_continuation_manifest.json", resume_manifest)
    if len(final_body) > CONTINUATION_BODY_LIMIT:
        (OUT / "attempt_3_blocked_request_body.txt").write_bytes(final_body)
        write_json("final_status.json", {
            "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_FINAL_STATUS",
            "status": "FAILED_NO_RETRY",
            "failure": {"error": "CONTINUATION_BODY_SIZE_LIMIT", "body_bytes": len(final_body), "body_limit": CONTINUATION_BODY_LIMIT},
            "budget_usage": load(OUT / "budget_usage.json"),
        })
        raise SystemExit("resumed continuation exceeds 200000 bytes before network")

    envelope, accumulator, raw = make_stream_once(
        body_limit=CONTINUATION_BODY_LIMIT,
        start_attempt=2,
    )(final_payload)
    classification = accumulator.classify()
    model_result = {
        "phase": "FINAL_RESPONSE",
        "terminal_event": accumulator.terminal_event,
        "http_status": accumulator.http_status,
        "request_id": accumulator.request_id,
        "usage": (envelope or {}).get("usage"),
        "function_calls": classification.get("function_calls"),
        "response_bytes": len(raw),
    }
    error = accumulator.error
    if error is None and accumulator.terminal_event == "response.incomplete":
        error = "RESPONSE_INCOMPLETE"
    elif error is None and accumulator.terminal_event != "response.completed":
        error = "NO_TERMINAL_EVENT"
    if error is None and classification.get("malformed_events"):
        error = "malformed function call events"
    if error is None and (envelope or {}).get("status") != "completed":
        error = "RESPONSE_STATUS_NOT_COMPLETED"
    if error is None and classification.get("function_calls"):
        error = "FINAL_RESPONSE_CONTAINS_TOOL_CALL"
    if error is None:
        text_parts = []
        for item in (envelope or {}).get("output", []):
            if item.get("type") == "message" and item.get("role") == "assistant":
                text_parts.extend(content.get("text", "") for content in item.get("content", []) if content.get("type") == "output_text")
        text = "".join(text_parts)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            error = f"invalid final JSON: {exc}"
        else:
            plan_errors = validate_final_operational_plan(parsed, evidence, schema)
            if plan_errors:
                write_json("llm_plan_validation.json", {
                    "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_PLAN_VALIDATION",
                    "schema": "r8_1_lowstar_c2_compact_tool_revision_v2",
                    "status": "FAIL",
                    "errors": plan_errors,
                })
                error = "invalid final plan"
                failure_payload = {"plan_errors": plan_errors}
            else:
                failure_payload = None
    else:
        failure_payload = None

    write_json("tool_loop_resume_session.json", {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_RESUME_SESSION",
        "status": "COMPLETE" if error is None else "FAILED",
        "error": error,
        "model_requests": [model_result],
        "revalidated_tool_count": 5,
        "preserved_timing_tool_count": 1,
    })
    update_budget(model_requests=3, tool_calls=6)
    write_json("tool_loop_budget.json", load(OUT / "budget_usage.json"))
    if error is not None:
        write_json("final_status.json", {
            "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_FINAL_STATUS",
            "status": "FAILED_NO_RETRY",
            "failure": {"error": error, **(failure_payload or {})},
            "classification": classification,
            "budget_usage": load(OUT / "budget_usage.json"),
        })
        raise SystemExit("C2 resumed final continuation failed without retry")

    write_json("llm_structured_output.json", parsed)
    write_json("llm_plan_validation.json", {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_PLAN_VALIDATION",
        "schema": "r8_1_lowstar_c2_compact_tool_revision_v2",
        "evidence_path": str(evidence_path.relative_to(ROOT)),
        "status": "PASS",
    })
    plans = parsed.get("revised_operational_plans", [])
    write_json("grounding_validation.json", {
        "one_operational_plan": len(plans) == 1,
        "selected_operator_ids": plans[0].get("selected_low_star_operator_ids", []) if plans else [],
        "direction_complete_deploys": all(
            action.get("action_type") != "DEPLOY" or (action.get("tile") and action.get("direction"))
            for action in (plans[0].get("action_timeline", []) if plans else [])
        ),
        "status": "PASS" if len(plans) == 1 else "FAIL",
    })
    write_json("final_status.json", {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_FINAL_STATUS",
        "status": "C2_RECEIVED_AND_CONTRACT_VALID",
        "interface_status": "RESUMED_FINAL_RESPONSE_COMPLETE",
        "actual_model_requests": 3,
        "actual_readonly_tool_calls": 6,
        "new_operational_plans": len(plans),
        "stage_simulations": 0,
        "tactical_search_expansions": 0,
        "static_compile_check": "PENDING",
    })
    return parsed


def deep_diff(left: Any, right: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(left) is not type(right):
        return [{"path": path, "before": left, "after": right}]
    if isinstance(left, dict):
        differences: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                differences.append({"path": f"{path}.{key}", "before": left.get(key), "after": right.get(key)})
            else:
                differences.extend(deep_diff(left[key], right[key], f"{path}.{key}"))
        return differences
    if isinstance(left, list):
        differences = []
        for index in range(max(len(left), len(right))):
            before = left[index] if index < len(left) else None
            after = right[index] if index < len(right) else None
            if index >= len(left) or index >= len(right):
                differences.append({"path": f"{path}[{index}]", "before": before, "after": after})
            else:
                differences.extend(deep_diff(before, after, f"{path}[{index}]"))
        return differences
    return [] if left == right else [{"path": path, "before": left, "after": right}]


def normalize_c2() -> dict[str, Any]:
    classification_path = OUT / "attempt_3_classification.json"
    classification = load(classification_path)
    if classification.get("terminal_event") != "response.completed" or classification.get("assistant_message_present") is not True:
        raise RuntimeError("saved C2 final response is not a completed assistant response")
    original = json.loads(classification.get("final_output_text") or "")
    normalized = copy.deepcopy(original)
    changes: list[dict[str, Any]] = []
    for plan_index, plan in enumerate(original.get("revised_operational_plans") or []):
        for question_index, question in enumerate(plan.get("verification_questions") or []):
            if isinstance(question, str):
                normalized["revised_operational_plans"][plan_index]["verification_questions"][question_index] = {"question": question}
                changes.append({
                    "json_path": f"$.revised_operational_plans[{plan_index}].verification_questions[{question_index}]",
                    "before": question,
                    "after": {"question": question},
                })
    if len(changes) != 3:
        raise RuntimeError(f"expected exactly three string verification questions, got {len(changes)}")
    differences = deep_diff(original, normalized)
    if len(differences) != len(changes):
        raise RuntimeError("normalization produced changes beyond the three verification_questions wrappers")
    evidence = load(OUT / "llm_evidence_context.json")
    schema = load(OUT / "revision_output_schema.json")
    original_errors = validate_final_operational_plan(original, evidence, schema)
    normalized_errors = validate_final_operational_plan(normalized, evidence, schema)
    write_json("llm_raw_final_output.json", original)
    write_json("llm_structured_output.json", normalized)
    write_json("c2_normalization.json", {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_NORMALIZATION",
        "source_response": file_record(OUT / "attempt_3_raw_response.txt"),
        "source_classification": file_record(classification_path),
        "raw_final_output": file_record(OUT / "llm_raw_final_output.json"),
        "normalized_output": file_record(OUT / "llm_structured_output.json"),
        "transformation": "Wrap only string verification_questions as {question:<original string>}; preserve the original string unchanged.",
        "changes": changes,
        "deep_diff_count": len(differences),
        "deep_diff": differences,
        "original_validation_errors": original_errors,
        "normalized_validation_errors": normalized_errors,
        "status": "PASS" if not normalized_errors and len(differences) == 3 else "FAIL",
    })
    write_json("llm_plan_validation.json", {
        "schema_version": "R8_1_LOWSTAR_C2_COMPACT_TOOL_REVISION_V2_PLAN_VALIDATION",
        "schema": "r8_1_lowstar_c2_compact_tool_revision_v2",
        "status": "PASS" if not normalized_errors else "FAIL",
        "errors": normalized_errors,
        "normalization_evidence": "c2_normalization.json",
    })
    if normalized_errors:
        raise SystemExit("normalized C2 failed schema/contract validation")
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "call", "resume", "normalize"])
    arguments = parser.parse_args()
    if arguments.phase == "prepare":
        prepare()
        return
    if arguments.phase == "resume":
        resume()
        return
    if arguments.phase == "normalize":
        normalize_c2()
        return
    call()


if __name__ == "__main__":
    main()
