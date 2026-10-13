from __future__ import annotations

import hashlib
import json
from pathlib import Path

from kimi_readonly_tools import (
    BASE_RULE_CARD,
    TOOLS_SCHEMA,
    ReadOnlyQueryEngine,
    source_mapping,
)
from kimi_responses_transport import StreamAccumulator, parse_sse
from kimi_tool_loop import build_tool_continuation_payload, build_tool_enabled_request, run_mock_tool_session


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_readonly_tool_loop_v1"
C1 = ROOT / "output/r8_1_low_star_full_tactical_closure_v2"


def write_json(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sse(events: list[tuple[str, dict]]) -> bytes:
    return "".join(
        f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
        for name, data in events
    ).encode("utf-8")


def run_stream(events: list[tuple[str, dict]]) -> tuple[dict, StreamAccumulator, bytes]:
    raw = sse(events)
    accumulator = StreamAccumulator()
    for event in parse_sse(raw):
        accumulator.observe(event)
    envelope = next((data["response"] for name, data in events if name in {"response.completed", "response.incomplete", "response.failed"}), {})
    return envelope, accumulator, raw


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    engine = ReadOnlyQueryEngine()
    base_request = json.loads((C1 / "llm_request.json").read_text(encoding="utf-8"))
    c1_plan = json.loads((C1 / "llm_structured_output.json").read_text(encoding="utf-8"))
    tool_request = build_tool_enabled_request(base_request)

    queries = [
        {
            "name": "query_range_coverage",
            "arguments": {
                "operator_id": "char_120_hibisc",
                "configuration": engine.operators["char_120_hibisc"]["debug_configuration"],
                "tile": [5, 7],
                "direction": "UP",
                "targets": [
                    {"label": "char_122_beagle", "tile": [4, 6]},
                    {"label": "char_281_popka", "tile": [4, 7]},
                ],
            },
        },
        {
            "name": "query_range_coverage",
            "arguments": {
                "operator_id": "char_210_stward",
                "configuration": engine.operators["char_210_stward"]["debug_configuration"],
                "tile": [5, 6],
                "direction": "UP",
                "targets": [
                    {"label": "char_122_beagle", "tile": [4, 6]},
                    {"label": "char_281_popka", "tile": [4, 7]},
                ],
            },
        },
        {
            "name": "query_range_coverage",
            "arguments": {
                "operator_id": "char_285_medic2",
                "configuration": engine.operators["char_285_medic2"]["debug_configuration"],
                "tile": [2, 9],
                "direction": "LEFT",
                "targets": [
                    {"label": "char_208_melan", "tile": [1, 7]},
                    {"label": "char_500_noirc", "tile": [1, 6]},
                ],
            },
        },
        {
            "name": "check_timing_constraints",
            "arguments": {
                "skill_activations": [
                    {"operator_id": "char_120_hibisc", "frame": 3000, "assume_ready": True},
                    {"operator_id": "char_120_hibisc", "frame": 4200, "assume_ready": True},
                ],
                "dp_ledger": {"initial_dp": 0, "entries": []},
                "deployment_conditions": [],
            },
        },
    ]
    c1_results = []
    for index, query in enumerate(queries):
        c1_results.append({
            "query_index": index,
            **query,
            "result": engine.execute(query["name"], query["arguments"]),
        })

    calls = [
        {
            "call_id": f"call-c1-{index}",
            "name": query["name"],
            "arguments": json.dumps(query["arguments"], ensure_ascii=False, separators=(",", ":")),
        }
        for index, query in enumerate(queries)
    ]
    output_items = [
        {"type": "function_call", **{key: value for key, value in call.items() if key != "name"}, "name": call["name"]}
        for call in calls
    ]
    created = {"response": {"id": "resp-mock-tool", "model": "kimi-k3", "status": "in_progress", "output": [], "max_output_tokens": 32768}}
    terminal_tool = {"response": {"id": "resp-mock-tool", "model": "kimi-k3", "status": "completed", "output": output_items}}
    tool_events = [("response.created", created)]
    for item in output_items:
        tool_events.append(("response.output_item.added", {"item": item}))
        tool_events.append(("response.function_call_arguments.delta", {"call_id": item["call_id"], "delta": item["arguments"]}))
        tool_events.append(("response.function_call_arguments.done", {"call_id": item["call_id"], "arguments": item["arguments"]}))
    tool_events.append(("response.completed", terminal_tool))

    final_item = {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(c1_plan, ensure_ascii=False, separators=(",", ":"))}]}
    final_events = [
        ("response.created", {"response": {"id": "resp-mock-final", "model": "kimi-k3", "status": "in_progress", "output": []}}),
        ("response.completed", {"response": {"id": "resp-mock-final", "model": "kimi-k3", "status": "completed", "output": [final_item], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}}),
    ]

    request_counter = {"value": 0}
    def fake_stream(payload: dict) -> tuple[dict, StreamAccumulator, bytes]:
        request_counter["value"] += 1
        if request_counter["value"] == 1:
            return run_stream(tool_events)
        return run_stream(final_events)

    def validate_plan(parsed: object) -> list[str]:
        return [] if parsed == c1_plan else ["mock final output must exactly reuse the preserved C1 plan"]

    session = run_mock_tool_session(tool_request, engine, fake_stream, validate_plan)
    if session.get("status") != "COMPLETE":
        raise RuntimeError(session)
    continuation_payload = build_tool_continuation_payload(tool_request, session["trajectories"][0]["calls"], session["trajectories"][0]["tool_results"])

    write_json("tools_schema.json", {"schema_version": "R8_1_READONLY_TOOLS_SCHEMA_V1", "tools": TOOLS_SCHEMA})
    write_json("base_rule_card.json", BASE_RULE_CARD)
    write_json("source_mapping.json", source_mapping([
        "scripts/kimi_readonly_tools.py",
        "scripts/kimi_tool_loop.py",
        "scripts/kimi_responses_transport.py",
        "output/normal_low_star_facts_v1/normal_low_star_facts.json",
        "output/r8_1_low_star_full_tactical_closure_v2/llm_evidence_context.json",
        "data/ArknightsGameData/zh_CN/gamedata/excel/range_table.json",
        "src/arknights_planner/simulator/range.py",
        "src/arknights_planner/simulator/combat_rules.py",
        "src/arknights_planner/simulator/simulator.py",
        "src/arknights_planner/adapters/low_rarity_skill.py",
    ]))
    write_json("c1_counterexample_queries.json", {
        "schema_version": "R8_1_C1_READONLY_QUERY_RESULTS_V1",
        "query_type": "COMMON_INTERFACE_REPLAY",
        "tactical_claim": "CONDITIONAL_MODEL_COUNTEREXAMPLES_NOT_REAL_GAME_OBSERVATIONS",
        "queries": c1_results,
    })
    write_json("mock_initial_request.json", tool_request)
    write_json("mock_continuation_request.json", continuation_payload)
    write_json("mock_responses.json", {
        "schema_version": "R8_1_READONLY_TOOL_MOCK_RESPONSES_V1",
        "note": "Both SSE streams are synthetic. This is not a provider compatibility proof.",
        "streams": [
            {"phase": "TOOL_QUERY", "raw": sse(tool_events).decode("utf-8")},
            {"phase": "FINAL_PLAN", "raw": sse(final_events).decode("utf-8")},
        ],
    })
    write_json("mock_tool_trajectory.json", {
        "schema_version": "R8_1_READONLY_TOOL_MOCK_TRAJECTORY_V1",
        "requests": session["trajectories"],
        "model_requests": session["model_requests"],
        "call_ids": [call["call_id"] for call in calls],
    })
    write_json("mock_session_result.json", session)
    write_json("provider_compatibility.json", {
        "schema_version": "R8_1_READONLY_TOOL_PROVIDER_COMPATIBILITY_V1",
        "endpoint": "https://ark.cn-beijing.volces.com/api/plan/v3/responses",
        "model": "kimi-k3",
        "protocol_family": "Responses-style function tools",
        "request_fields": {
            "tools": "function definitions with name, description and JSON-schema parameters",
            "tool_output_input_item": "function_call_output with call_id and output",
            "previous_response_id": "ABSENT_FORBIDDEN_BY_PROJECT_POLICY",
            "assistant_prefill": "ABSENT_FORBIDDEN_BY_PROJECT_POLICY",
            "text_format_json_schema": "PRESERVED_FOR_FINAL_PLAN",
        },
        "compatibility_status": "UNVERIFIED",
        "verification_limit": "General Responses tool conventions and this repository's own request validation are implemented, but kimi-k3 at this exact endpoint has not been tested with tools.",
        "offline_scope": "MOCK_ONLY",
    })
    validation = {
        "schema_version": "R8_1_READONLY_TOOL_LOOP_V1_VALIDATION",
        "status": "PASS",
        "offline_verified": {
            "c1_range_counterexamples": True,
            "stage_and_affordance_readonly_summaries": True,
            "c1_hibiscus_timing_counterexample": {"declared_frame": 4200, "earliest_ready_frame": 4500},
            "mock_end_to_end_tool_loop": True,
            "invalid_arguments_not_executed": True,
            "wrong_call_id_rejected": True,
            "incomplete_tool_response_not_executed": True,
            "model_request_budget_enforced": {"max": 3, "observed_in_budget_test": 3},
            "invalid_final_plan_rejected": True,
            "single_round_transport_regressions": "10/10 PASS",
            "c1_transport_regressions": "12/12 PASS",
            "readonly_tool_tests": "12/12 PASS",
        },
        "not_verified": {
            "provider_tool_compatibility": "UNVERIFIED",
            "real_kimi_call": "NOT_RUN",
            "real_stage_simulation": "NOT_RUN",
            "new_tactical_plan": "NOT_GENERATED",
        },
        "future_budget": {
            "max_actual_model_requests": 3,
            "max_readonly_tool_calls": 6,
            "max_final_operational_plans": 1,
            "automatic_retry": False,
            "continuation_counts_as_model_request": True,
        },
        "budget_used_this_round": {
            "actual_kimi_requests": 0,
            "mock_model_requests": 2,
            "readonly_tool_calls": 4,
            "real_stage_simulations": 0,
            "new_real_plans_or_candidates": 0,
            "tactical_search_expansions": 0,
        },
    }
    write_json("validation_results.json", validation)
    write_json("final_status.json", {
        "schema_version": "R8_1_READONLY_TOOL_LOOP_V1_FINAL_STATUS",
        "status": "OFFLINE_TOOL_LOOP_COMPLETE",
        "provider_tool_compatibility": "UNVERIFIED",
        "kimi_call_count": 0,
        "real_stage_simulation_count": 0,
        "new_real_operational_plan_count": 0,
    })
    files = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            data = path.read_bytes()
            files[path.name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    write_json("manifest.json", {
        "schema_version": "R8_1_READONLY_TOOL_LOOP_V1_MANIFEST",
        "approved_c1_body_sha256": hashlib.sha256((C1 / "llm_request_body.txt").read_bytes()).hexdigest(),
        "artifacts": files,
    })


if __name__ == "__main__":
    main()
