from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import socket
import urllib.error
import urllib.request
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kimi_readonly_tools import ReadOnlyQueryEngine
from kimi_responses_transport import StreamAccumulator, parse_sse
from kimi_tool_loop import (
    ToolLoopError,
    ToolLoopBudget,
    build_tool_continuation_payload,
    execute_tool_calls,
    build_tool_enabled_request,
    run_mock_tool_session,
    validate_tool_request,
)
from compile_r8_1_lowstar_c2_plan_v1 import compile_plan
from run_r8_1_low_star_full_tactical_closure_v1 import output_schema
from run_r8_1_lowstar_c3_failure_revision_v1 import (
    CONTINUATION_BODY_LIMIT,
    INITIAL_BODY_LIMIT,
    MAX_MODEL_REQUESTS,
    MAX_TOOL_CALLS,
    PARENT_PLAN_ID,
    PLAN_ID_PREFIX,
    TOKEN_LIMIT,
    evidence_context,
    load,
    validate_c3_contract,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_gpt_tactical_revision_v1"
MECHANICS = "m18.9-stage-device-runtime-v1"
TIMEOUT_SECONDS = 900

PROVIDERS = {
    "sub2api": {
        "base_url": "https://sub2api.amox.cc:18443/v1/responses",
        "credential_env": "SUB2API_API_KEY",
        "default_model": "gpt-6.1-sol",
        "reasoning_field": "reasoning",
    },
    "kimi": {
        "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3/responses",
        "credential_env": "ARK_API_KEY_agent",
        "default_model": "kimi-k3",
        "reasoning_field": None,
    },
}


def write_json(name: str | Path, payload: Any) -> None:
    path = name if isinstance(name, Path) else OUT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def provider_config(provider: str) -> dict[str, Any]:
    if provider not in PROVIDERS:
        raise ValueError(f"unsupported tactical provider {provider!r}")
    return PROVIDERS[provider]


def prompt_text(evidence: dict[str, Any], model: str) -> str:
    return f"""You are {model}, the tactical decision maker for Arknights main_08-01 / R8-1.
This is the QUERY PHASE for one compact full-stage OperationalPlan C3 using only ordinary-mode 1-3 star operators.

You are revising C2 after its conditional current-runtime LOSS. The decisive model sequence was not merely late damage:
Fang produced 6 DP at frame 570 and enabled Noirc at 600, but died at 890; Vanilla blocked route-2 at 822 and route-6 at 1076, then died at 1243 and released both; Beagle deployed at 1290, so route-6 leaked at 1295 and route-2 leaked at 1394; Vanilla's frame-1650 DP skill and Hibiscus' frame-1680 deployment then failed. Later Beagle and Popka deaths extended the failure chain. This is conditional model evidence, not a real-game result or proof of strategic infeasibility.

Use the read-only tools to verify assumptions before committing:
- range coverage for explicit deployment responsibilities;
- timing constraints for skill readiness, DP payments and deployments;
- mechanics/stage facts for coordinates, SP, WIN, roadblocks or support boundaries.
Return only native tool calls in this response (up to six). Do not return final JSON yet.

You decide the opening structure and support pattern. Python will not choose replacements or move actions. You may preserve useful C2 ideas, but must explain:
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
            "name": "r8_1_gpt_tactical_revision_v1",
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
        raise RuntimeError("GPT evidence or payload completeness check failed: " + json.dumps(checks, ensure_ascii=False, sort_keys=True))
    return checks


def source_manifest(evidence_path: Path) -> dict[str, Any]:
    paths = [
        ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json",
        ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json",
        ROOT / "output/r8_1_lowstar_c2_compact_tool_revision_v2/llm_structured_output.json",
        ROOT / "output/r8_1_lowstar_c2_compact_tool_revision_v2/static_compile_results.json",
        ROOT / "output/r8_1_lowstar_c2_full_diagnostic_v1/diagnostic_summary.json",
        ROOT / "output/r8_1_lowstar_c2_full_diagnostic_v1/diagnostic_events.json",
        ROOT / "scripts/kimi_readonly_tools.py",
        ROOT / "scripts/kimi_responses_transport.py",
        ROOT / "scripts/kimi_tool_loop.py",
        ROOT / "scripts/compile_r8_1_lowstar_c2_plan_v1.py",
        Path(__file__),
    ]
    return {
        "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_SOURCE_MANIFEST",
        "inputs": {path.name: file_record(path) for path in paths},
        "prepared_evidence": file_record(evidence_path),
        "mechanics_version": MECHANICS,
    }


def assert_run_lock() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "run.lock"
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError("another GPT tactical session is running; concurrent entry is forbidden") from exc
    handle.seek(0)
    if handle.read(1):
        handle.close()
        raise RuntimeError("GPT budget lock already consumed; restart cannot reset the session")
    handle.seek(0)
    handle.write(json.dumps({
        "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_RUN_LOCK",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "policy": "one exclusive session; persistent STARTED records are the consumed-budget authority",
    }, sort_keys=True) + "\n")
    handle.flush()


def save_exclusive(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


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
    write_json(path, state)


def reconcile_budget_from_request_log() -> dict[str, Any]:
    records = [json.loads(line) for line in (OUT / "llm_call_attempts.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    started = sum(row.get("phase") == "STARTED" for row in records)
    finished = sum(row.get("phase") == "FINISHED" for row in records)
    state = load(OUT / "budget_usage.json")
    current = int(state.get("model_requests_started", 0))
    if started != current:
        state["model_requests_started"] = max(current, started)
        state["budget_reconciliation"] = "STARTED records are authoritative, including requests without FINISHED records."
        write_json("budget_usage.json", state)
    if state["model_requests_started"] > 0 or state["model_requests_started"] >= state["max_model_requests"]:
        raise RuntimeError(
            f"GPT model request budget exhausted: "
            f"{state['model_requests_started']}/{state['max_model_requests']} STARTED records"
        )
    return {"started": started, "finished": finished, **state}


def make_stream_once(provider: str, model: str, reasoning_effort: str | None) -> Any:
    config = provider_config(provider)
    base_url = config["base_url"]
    attempts = load(OUT / "budget_usage.json").get("model_requests_started", 0)

    def stream_once(payload: dict[str, Any]) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
        nonlocal attempts
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        continuation = any(item.get("type") == "function_call_output" for item in payload.get("input", []))
        body_limit = CONTINUATION_BODY_LIMIT if continuation else INITIAL_BODY_LIMIT
        if len(body) > body_limit:
            raise RuntimeError(f"request body exceeds {body_limit} bytes before network: {len(body)}")
        credential = os.environ.get(config["credential_env"])
        if not credential:
            raise RuntimeError(f"{config['credential_env']} is not set")
        attempts += 1
        update_budget(model_requests=attempts)
        save_exclusive(OUT / f"attempt_{attempts}_request.json", json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        save_exclusive(OUT / f"attempt_{attempts}_request_body.txt", body.decode("utf-8"))
        request = urllib.request.Request(base_url, data=body, method="POST", headers={
            "Accept": "text/event-stream", "Authorization": f"Bearer {credential}", "Content-Type": "application/json",
        })
        append_attempt({
            "attempt": attempts, "phase": "STARTED", "started_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider, "endpoint": base_url, "model": model,
            "reasoning_effort": reasoning_effort, "max_output_tokens": payload.get("max_output_tokens"),
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
        save_exclusive(OUT / f"attempt_{attempts}_raw_response.txt", raw.decode("utf-8"))
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
        write_json(OUT / f"attempt_{attempts}_classification.json", accumulator.classify())
        return accumulator.response_envelope or {}, accumulator, raw

    return stream_once


def prepare(provider: str, model: str, reasoning_effort: str | None) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    attempt_path = OUT / "llm_call_attempts.jsonl"
    if attempt_path.exists() and any(line.strip() for line in attempt_path.read_text(encoding="utf-8").splitlines()):
        raise RuntimeError("GPT attempt log already contains calls; refusing to reset or rerun")
    attempt_path.write_text("", encoding="utf-8")
    write_json("budget_usage.json", {
        "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_BUDGET",
        "provider": provider, "model": model, "reasoning_effort": reasoning_effort,
        "max_model_requests": MAX_MODEL_REQUESTS, "max_readonly_tool_calls": MAX_TOOL_CALLS,
        "model_requests_started": 0, "readonly_tool_calls_executed": 0,
        "automatic_retry": False, "continuation_counts_as_model_request": True,
    })
    evidence = evidence_context()
    evidence["tactical_provider"] = {
        "provider": provider, "model": model, "reasoning_effort": reasoning_effort,
        "compatibility": "UNVERIFIED_BEFORE_PROJECT_REQUEST",
    }
    evidence_path = OUT / "llm_evidence_context.json"
    write_json("llm_evidence_context.json", evidence)
    schema = output_schema()
    write_json("revision_output_schema.json", schema)
    prompt = prompt_text(evidence, model)
    write_text("constraint_informed_prompt.txt", prompt)
    payload: dict[str, Any] = {
        "model": model, "stream": True,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "max_output_tokens": TOKEN_LIMIT,
    }
    reasoning_field = provider_config(provider)["reasoning_field"]
    if reasoning_field and reasoning_effort:
        payload[reasoning_field] = {"effort": reasoning_effort}
    request = build_tool_enabled_request(payload)
    errors = validate_tool_request(request)
    if errors:
        raise RuntimeError("invalid prepared GPT tool request: " + ", ".join(errors))
    body = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    write_json("compactness_check.json", compactness_check(evidence, request, body))
    write_text("llm_request_body.txt", body)
    write_json("llm_request.json", request)
    write_json("llm_request_fingerprint.json", {
        "request_sha256": hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(), "body_bytes": len(body.encode()),
    })
    write_json("source_manifest.json", source_manifest(evidence_path))
    write_json("prepare_status.json", {"phase": "PREPARED", "schema": "r8_1_gpt_tactical_revision_v1"})
    return request


def call(provider: str, model: str, reasoning_effort: str | None) -> dict[str, Any]:
    evidence_path = OUT / "llm_evidence_context.json"
    schema_path = OUT / "revision_output_schema.json"
    request_path = OUT / "llm_request.json"
    for path in (evidence_path, schema_path, request_path):
        if not path.is_file():
            raise RuntimeError(f"missing prepared input: {path}")
    assert_run_lock()
    reconcile_budget_from_request_log()
    config = provider_config(provider)
    if not os.environ.get(config["credential_env"]):
        error = {
            "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_PREFLIGHT",
            "status": "STOPPED_MISSING_CREDENTIAL",
            "credential_env": config["credential_env"],
            "actual_http_requests": 0,
            "message": f"Set {config['credential_env']} before the bounded tactical call; credential fallback is forbidden.",
        }
        write_json("preflight_error.json", error)
        write_json("final_status.json", {
            "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_FINAL_STATUS",
            "status": "STOPPED_MISSING_CREDENTIAL", "failure": error,
            "actual_model_requests": 0, "actual_readonly_tool_calls": 0,
            "new_operational_plans": 0, "stage_simulations": 0,
        })
        raise SystemExit(f"missing credential: {config['credential_env']}")
    payload = load(request_path)
    evidence = load(evidence_path)
    schema = load(schema_path)
    budget = ToolLoopBudget(max_model_requests=MAX_MODEL_REQUESTS, max_tool_calls=MAX_TOOL_CALLS)
    engine = ReadOnlyQueryEngine(evidence_path=evidence_path)
    session = run_mock_tool_session(
        payload, engine, make_stream_once(provider, model, reasoning_effort),
        evidence=evidence, plan_schema=schema, budget=budget,
        finalize_payload=lambda item: finalize_plan_payload(item, schema),
        validate_plan=lambda parsed: validate_c3_contract(parsed, evidence),
    )
    update_budget(model_requests=budget.model_requests_started, tool_calls=budget.tool_calls_executed)
    write_json("tool_loop_session.json", session)
    write_json("tool_loop_budget.json", session.get("budget", budget.__dict__))
    if session.get("status") != "COMPLETE":
        write_json("final_status.json", {
            "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_FINAL_STATUS",
            "status": "FAILED_NO_RETRY", "failure": session,
            "budget_usage": load(OUT / "budget_usage.json"),
        })
        raise SystemExit("GPT tool session failed without retry")
    parsed = session["operational_plan"]
    plan_errors = validate_c3_contract(parsed, evidence)
    if plan_errors:
        write_json("llm_plan_validation.json", {
            "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_PLAN_VALIDATION",
            "status": "FAIL", "errors": plan_errors,
        })
        raise RuntimeError("GPT-C3 failed local contract validation")
    write_json("llm_structured_output.json", parsed)
    write_json("llm_plan_validation.json", {
        "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_PLAN_VALIDATION",
        "status": "PASS", "evidence_path": str(evidence_path.relative_to(ROOT)),
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
        "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_FINAL_STATUS",
        "status": "GPT_C3_RECEIVED_AND_CONTRACT_VALID",
        "actual_model_requests": budget.model_requests_started,
        "actual_readonly_tool_calls": budget.tool_calls_executed,
        "new_operational_plans": len(plans), "stage_simulations": 0,
        "tactical_search_expansions": 0, "static_compile_check": "PENDING",
    })
    return parsed


def static_check() -> dict[str, Any]:
    if load(OUT / "llm_plan_validation.json").get("status") != "PASS":
        raise RuntimeError("static check requires a locally validated GPT-C3 plan")
    return compile_plan(OUT)


def resume_after_transport_fix(provider: str, model: str, reasoning_effort: str | None) -> dict[str, Any]:
    evidence_path = OUT / "llm_evidence_context.json"
    schema_path = OUT / "revision_output_schema.json"
    request_path = OUT / "attempt_1_request.json"
    raw_path = OUT / "attempt_1_raw_response.txt"
    for path in (evidence_path, schema_path, request_path, raw_path):
        if not path.is_file():
            raise RuntimeError(f"missing saved transport-fix input: {path}")
    state = load(OUT / "budget_usage.json")
    if state.get("model_requests_started") != 1 or state.get("readonly_tool_calls_executed") != 0:
        raise RuntimeError("transport-fix resume requires exactly one counted request and zero executed tools")
    schema = load(schema_path)
    evidence = load(evidence_path)
    saved_request = load(request_path)
    accumulator = StreamAccumulator()
    for event in parse_sse(raw_path.read_text(encoding="utf-8")):
        accumulator.observe(event)
    classification = accumulator.classify()
    write_json("saved_tool_round_classification.json", classification)
    calls = classification.get("function_calls") or []
    if accumulator.error or accumulator.terminal_event != "response.completed":
        raise RuntimeError("saved response is not a completed tool round")
    if classification.get("malformed_events"):
        raise ToolLoopError("saved tool round is malformed: " + ", ".join(classification["malformed_events"]))
    if not calls or not classification.get("requires_tool_execution"):
        raise ToolLoopError("saved response does not contain a completed native tool call")
    replay_budget = ToolLoopBudget(max_model_requests=0, max_tool_calls=MAX_TOOL_CALLS)
    engine = ReadOnlyQueryEngine(evidence_path=evidence_path)
    tool_results = execute_tool_calls(calls, engine, replay_budget)
    write_json("saved_tool_round_results.json", {
        "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_SAVED_TOOL_REPLAY",
        "budget": replay_budget.__dict__,
        "results": tool_results,
    })
    if any(row.get("status") != "EXECUTED" for row in tool_results):
        raise RuntimeError("saved native tool call could not be executed")
    continuation = build_tool_continuation_payload(saved_request, calls, tool_results)
    continuation = finalize_plan_payload(continuation, schema)
    errors = validate_tool_request(continuation)
    if errors:
        raise RuntimeError("invalid resumed final continuation: " + ", ".join(errors))
    body = json.dumps(continuation, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(body) > CONTINUATION_BODY_LIMIT:
        raise RuntimeError(f"resumed request body exceeds {CONTINUATION_BODY_LIMIT} bytes before network: {len(body)}")
    write_json("resume_continuation_request.json", continuation)
    write_text("resume_continuation_request_body.txt", body.decode())
    write_json("resume_request_fingerprint.json", {
        "request_sha256": hashlib.sha256(json.dumps(continuation, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "body_sha256": hashlib.sha256(body).hexdigest(), "body_bytes": len(body), "body_limit": CONTINUATION_BODY_LIMIT,
    })
    budget = ToolLoopBudget(max_model_requests=MAX_MODEL_REQUESTS - 1, max_tool_calls=0)
    session = run_mock_tool_session(
        continuation, engine, make_stream_once(provider, model, reasoning_effort),
        evidence=evidence, plan_schema=schema, budget=budget,
        finalize_payload=lambda item: finalize_plan_payload(item, schema),
        validate_plan=lambda parsed: validate_c3_contract(parsed, evidence),
    )
    update_budget(
        model_requests=1 + budget.model_requests_started,
        tool_calls=replay_budget.tool_calls_executed + budget.tool_calls_executed,
    )
    write_json("resume_session.json", session)
    write_json("tool_loop_budget.json", load(OUT / "budget_usage.json"))
    if session.get("status") != "COMPLETE":
        write_json("final_status.json", {
            "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_FINAL_STATUS",
            "status": "FAILED_NO_RETRY_AFTER_TRANSPORT_FIX",
            "prior_transport_failure": "COMPLETED_RESPONSE_MIXED_COMMENTARY_AND_NATIVE_TOOL_CALL",
            "failure": session, "budget_usage": load(OUT / "budget_usage.json"),
        })
        raise SystemExit("GPT resumed tool session failed without retry")
    parsed = session["operational_plan"]
    plan_errors = validate_c3_contract(parsed, evidence)
    if plan_errors:
        write_json("llm_plan_validation.json", {
            "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_PLAN_VALIDATION",
            "status": "FAIL", "errors": plan_errors,
        })
        raise RuntimeError("GPT-C3 failed local contract validation")
    write_json("llm_structured_output.json", parsed)
    write_json("llm_plan_validation.json", {
        "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_PLAN_VALIDATION",
        "status": "PASS", "evidence_path": str(evidence_path.relative_to(ROOT)),
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
        "schema_version": "R8_1_GPT_TACTICAL_REVISION_V1_FINAL_STATUS",
        "status": "GPT_C3_RECEIVED_AND_CONTRACT_VALID",
        "actual_model_requests": 1 + budget.model_requests_started,
        "actual_readonly_tool_calls": replay_budget.tool_calls_executed + budget.tool_calls_executed,
        "new_operational_plans": len(plans), "stage_simulations": 0,
        "tactical_search_expansions": 0, "static_compile_check": "PENDING",
    })
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "call", "resume_after_transport_fix", "static_check"])
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="sub2api")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    arguments = parser.parse_args()
    config = provider_config(arguments.provider)
    model = arguments.model or config["default_model"]
    reasoning_effort = arguments.reasoning_effort
    if reasoning_effort is None and arguments.provider == "sub2api":
        reasoning_effort = "medium"
    if reasoning_effort is not None and arguments.provider == "sub2api" and reasoning_effort != "medium":
        raise SystemExit("this bounded session only permits sub2api reasoning effort medium")
    if arguments.phase == "prepare":
        prepare(arguments.provider, model, reasoning_effort)
        return
    if arguments.phase == "static_check":
        static_check()
        return
    if arguments.phase == "resume_after_transport_fix":
        resume_after_transport_fix(arguments.provider, model, reasoning_effort)
        return
    call(arguments.provider, model, reasoning_effort)


if __name__ == "__main__":
    main()
