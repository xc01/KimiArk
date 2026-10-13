from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from unittest import mock

from kimi_readonly_tools import (
    BASE_RULE_CARD,
    TOOLS_SCHEMA,
    ReadOnlyQueryEngine,
    source_mapping,
)
from kimi_responses_transport import StreamAccumulator, parse_sse
from kimi_tool_loop import (
    ToolLoopBudget,
    build_tool_continuation_payload,
    build_tool_enabled_request,
    execute_tool_calls,
    run_mock_tool_session,
    validate_final_operational_plan,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_readonly_tool_loop_fix_v2"
C1 = ROOT / "output/r8_1_low_star_full_tactical_closure_v2"


def write_json(name: str, payload: Any) -> None:
    (OUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sse(events: list[tuple[str, dict]]) -> bytes:
    return "".join(
        f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
        for name, data in events
    ).encode("utf-8")


def observe(events: list[tuple[str, dict]]) -> StreamAccumulator:
    accumulator = StreamAccumulator()
    raw = sse(events)
    for event in parse_sse(raw.decode("utf-8")):
        accumulator.observe(event)
    return accumulator


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    engine = ReadOnlyQueryEngine()
    base_request = json.loads((C1 / "llm_request.json").read_text(encoding="utf-8"))
    c1_plan = json.loads((C1 / "llm_structured_output.json").read_text(encoding="utf-8"))
    initial_request = build_tool_enabled_request(base_request)

    queries = [
        ("query_range_coverage", {
            "operator_id": "char_120_hibisc",
            "configuration": engine.operators["char_120_hibisc"]["debug_configuration"],
            "tile": [5, 7], "direction": "UP",
            "targets": [
                {"label": "char_122_beagle", "tile": [4, 6]},
                {"label": "char_281_popka", "tile": [4, 7]},
            ],
        }),
        ("query_range_coverage", {
            "operator_id": "char_210_stward",
            "configuration": engine.operators["char_210_stward"]["debug_configuration"],
            "tile": [5, 6], "direction": "UP",
            "targets": [
                {"label": "char_122_beagle", "tile": [4, 6]},
                {"label": "char_281_popka", "tile": [4, 7]},
            ],
        }),
        ("query_range_coverage", {
            "operator_id": "char_285_medic2",
            "configuration": engine.operators["char_285_medic2"]["debug_configuration"],
            "tile": [2, 9], "direction": "LEFT",
            "targets": [
                {"label": "char_208_melan", "tile": [1, 7]},
                {"label": "char_500_noirc", "tile": [1, 6]},
            ],
        }),
        ("check_timing_constraints", {
            "skill_activations": [
                {"operator_id": "char_120_hibisc", "frame": 3000, "assume_ready": True},
                {"operator_id": "char_120_hibisc", "frame": 4200, "assume_ready": True},
            ],
            "dp_ledger": {"initial_dp": 0, "entries": []},
            "deployment_conditions": [],
        }),
    ]
    c1_replay = []
    for index, (name, arguments) in enumerate(queries):
        c1_replay.append({
            "query_index": index,
            "name": name,
            "arguments": arguments,
            "result": engine.execute(name, arguments),
        })

    calls = [
        {
            "call_id": f"call-c1-{index}",
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        }
        for index, (name, arguments) in enumerate(queries)
    ]
    output_items = [
        {"type": "function_call", **call, "item_id": f"item-{index}"}
        for index, call in enumerate(calls)
    ]
    tool_events = [("response.created", {"response": {"id": "resp-v2-tool", "status": "in_progress", "output": []}})]
    for item in output_items:
        tool_events.append(("response.output_item.added", {"item": item}))
        tool_events.append(("response.function_call_arguments.delta", {"item_id": item["item_id"], "delta": item["arguments"]}))
        tool_events.append(("response.function_call_arguments.done", {"item_id": item["item_id"], "arguments": item["arguments"]}))
    terminal_tool_response = {"response": {"id": "resp-v2-tool", "status": "completed", "output": output_items}}
    tool_events.append(("response.completed", terminal_tool_response))
    accumulator = observe(tool_events)
    classification = accumulator.classify()

    tool_results = execute_tool_calls(classification["function_calls"], engine, ToolLoopBudget())
    continuation = build_tool_continuation_payload(initial_request, classification["function_calls"], tool_results)
    final_plan_item = {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(c1_plan, ensure_ascii=False, separators=(",", ":"))}]}
    final_response = {"response": {"id": "resp-v2-plan", "status": "completed", "output": [final_plan_item]}}
    final_events = [
        ("response.created", {"response": {"id": "resp-v2-plan", "status": "in_progress", "output": []}}),
        ("response.completed", final_response),
    ]

    def stream(payload: dict[str, Any]) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
        events = final_events if any(item.get("type") == "function_call_output" for item in payload.get("input", [])) else tool_events
        raw = sse(events)
        local_accumulator = StreamAccumulator()
        for event in parse_sse(raw.decode("utf-8")):
            local_accumulator.observe(event)
        return local_accumulator.response_envelope or {}, local_accumulator, raw

    session = run_mock_tool_session(initial_request, engine, stream)
    if session.get("status") != "COMPLETE":
        raise RuntimeError(f"mock session failed: {session}")
    if session.get("operational_plan") != c1_plan:
        raise RuntimeError("mock final plan does not match C1 protocol replay")

    invalid_result = execute_tool_calls(
        [{"call_id": "invalid", "name": "query_mechanic", "arguments": '{"topic":3}'}],
        engine,
        ToolLoopBudget(),
    )
    duplicate_rejected = False
    duplicate_budget = ToolLoopBudget()
    duplicate_call = {"call_id": "same", "name": "query_mechanic", "arguments": '{"topic":"coordinates_and_direction"}'}
    try:
        execute_tool_calls([duplicate_call, duplicate_call], engine, duplicate_budget)
    except Exception as exc:
        duplicate_rejected = "duplicate function call_id" in str(exc)
    budget_rejected = False
    budget_calls = [
        {"call_id": f"call-{index}", "name": "query_mechanic", "arguments": '{"topic":"coordinates_and_direction"}'}
        for index in range(7)
    ]
    budget_budget = ToolLoopBudget()
    try:
        execute_tool_calls(budget_calls, engine, budget_budget)
    except Exception as exc:
        budget_rejected = "tool call budget exhausted" in str(exc)

    dp_result = engine.check_timing_constraints({
        "skill_activations": [],
        "dp_ledger": {
            "initial_dp": 17,
            "same_frame_order": "DECLARED_LEDGER_ORDER",
            "entries": [{
                "entry_id": "hibisc-deploy", "frame": 1800, "delta": -17,
                "label": "deploy char_120_hibisc", "evidence_status": "DECLARED",
            }],
        },
        "deployment_conditions": [{
            "operator_id": "char_120_hibisc", "frame": 1800, "tile": [5, 7],
            "declared_cost": 17, "payment_entry_ids": ["hibisc-deploy"],
        }],
    })
    dp_ambiguous = engine.check_timing_constraints({
        "skill_activations": [],
        "dp_ledger": {
            "initial_dp": 17, "same_frame_order": "UNKNOWN",
            "entries": [{"frame": 1800, "delta": -17, "label": "payment", "evidence_status": "DECLARED"}],
        },
        "deployment_conditions": [{
            "operator_id": "char_120_hibisc", "frame": 1800, "tile": [5, 7], "declared_cost": 17,
        }],
    })

    write_json("base_rule_card.json", BASE_RULE_CARD)
    write_json("tools_schema.json", TOOLS_SCHEMA)
    write_json("c1_counterexample_queries.json", {
        "schema_version": "R8_1_READONLY_TOOL_C1_REPLAY_V2",
        "claim_scope": "CONDITIONAL_MODEL_COUNTEREXAMPLES_NOT_REAL_GAME_OBSERVATIONS",
        "queries": c1_replay,
    })
    write_json("mock_initial_request.json", initial_request)
    write_json("mock_continuation_request.json", continuation)
    write_json("mock_responses.json", {
        "schema_version": "R8_1_READONLY_TOOL_MOCK_RESPONSES_V2",
        "streams": [
            {"phase": "TOOL_QUERY", "raw": sse(tool_events).decode("utf-8")},
            {"phase": "FINAL_PLAN", "raw": sse(final_events).decode("utf-8")},
        ],
    })
    write_json("mock_session_result.json", session)
    write_json("fix_regressions.json", {
        "schema_version": "R8_1_READONLY_TOOL_LOOP_FIX_V2_REGRESSIONS",
        "transport_function_call_registered": bool(classification["function_calls"]),
        "transport_function_call_item_ids": [item["item_id"] for item in output_items],
        "continuation_input_types": [item.get("type") for item in continuation["input"]],
        "continuation_call_contexts": [
            {"call_id": item.get("call_id"), "name": item.get("name"), "arguments": item.get("arguments")}
            for item in continuation["input"] if item.get("type") == "function_call"
        ],
        "invalid_arguments": invalid_result,
        "duplicate_call_id_rejected": duplicate_rejected,
        "duplicate_budget_consumed_before_preflight": duplicate_budget.tool_calls_seen,
        "seventh_call_rejected": budget_rejected,
        "seventh_budget_consumed_before_preflight": budget_budget.tool_calls_seen,
        "linked_same_frame_dp": dp_result,
        "ambiguous_same_frame_dp": dp_ambiguous,
        "mandatory_final_plan_validation_passed_for_c1_replay": validate_final_operational_plan(c1_plan) == [],
    })
    write_json("provider_compatibility.json", {
        "schema_version": "R8_1_READONLY_TOOL_LOOP_FIX_V2_PROVIDER_COMPATIBILITY",
        "endpoint": "https://ark.cn-beijing.volces.com/api/plan/v3/responses",
        "model": "kimi-k3",
        "continuation_policy": "full initial user context, matching function_call items, then function_call_output items",
        "previous_response_id": "ABSENT_FORBIDDEN_BY_PROJECT_POLICY",
        "assistant_prefill": "ABSENT_FORBIDDEN_BY_PROJECT_POLICY",
        "compatibility_status": "UNVERIFIED",
        "scope": "Offline mock only; no real Kimi request was made.",
    })
    write_json("source_mapping.json", source_mapping(BASE_RULE_CARD["sources"]))
    write_json("validation_results.json", {
        "schema_version": "R8_1_READONLY_TOOL_LOOP_FIX_V2_VALIDATION",
        "status": "PASS",
        "mock_session_status": session.get("status"),
        "mock_model_requests": session.get("budget", {}).get("model_requests_started"),
        "mock_tool_calls_executed": session.get("budget", {}).get("tool_calls_executed"),
        "c1_replay_counts_as_protocol_test_only": True,
        "tactical_learning_claim": "NONE",
        "real_kimi_requests": 0,
        "real_stage_simulations": 0,
        "new_real_plans_or_candidates": 0,
        "tactical_search_expansions": 0,
        "provider_tool_compatibility": "UNVERIFIED",
    })
    write_json("final_status.json", {
        "schema_version": "R8_1_READONLY_TOOL_LOOP_FIX_V2_FINAL_STATUS",
        "status": "OFFLINE_FIX_COMPLETE",
        "kimi_call_count": 0,
        "real_stage_simulation_count": 0,
        "new_real_operational_plan_count": 0,
        "provider_tool_compatibility": "UNVERIFIED",
    })
    files = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            data = path.read_bytes()
            files[path.name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    write_json("manifest.json", {
        "schema_version": "R8_1_READONLY_TOOL_LOOP_FIX_V2_MANIFEST",
        "artifacts": files,
    })


if __name__ == "__main__":
    main()
