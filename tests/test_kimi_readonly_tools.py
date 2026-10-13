from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from kimi_readonly_tools import (  # noqa: E402
    BASE_RULE_CARD,
    MECHANIC_TOPICS,
    TOOLS_SCHEMA,
    ReadOnlyQueryEngine,
    source_mapping,
)
from kimi_tool_loop import (  # noqa: E402
    ToolLoopBudget,
    build_tool_continuation_payload,
    build_tool_enabled_request,
    execute_tool_calls,
    run_mock_tool_session,
    validate_tool_request,
)
from kimi_responses_transport import StreamAccumulator  # noqa: E402


def engine() -> ReadOnlyQueryEngine:
    return ReadOnlyQueryEngine()


def config(operator_id: str) -> dict:
    return engine().operators[operator_id]["debug_configuration"]


def coverage_call(operator_id: str, tile: list[int], direction: str, targets: list[tuple[str, list[int]]]) -> dict:
    return {
        "operator_id": operator_id,
        "configuration": config(operator_id),
        "tile": tile,
        "direction": direction,
        "targets": [{"label": label, "tile": tile} for label, tile in targets],
    }


def sse(events: list[tuple[str, dict]]) -> bytes:
    return "".join(
        f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
        for name, data in events
    ).encode()


class ReadonlyToolTests(unittest.TestCase):
    def test_c1_declared_range_counterexamples(self):
        eng = engine()
        hibiscus = eng.query_range_coverage(coverage_call(
            "char_120_hibisc", [5, 7], "UP", [("char_122_beagle", [4, 6]), ("char_281_popka", [4, 7])]
        ))
        stward = eng.query_range_coverage(coverage_call(
            "char_210_stward", [5, 6], "UP", [("char_122_beagle", [4, 6]), ("char_281_popka", [4, 7])]
        ))
        lancet = eng.query_range_coverage(coverage_call(
            "char_285_medic2", [2, 9], "LEFT", [("char_208_melan", [1, 7]), ("char_500_noirc", [1, 6])]
        ))
        self.assertFalse(all(target["covered"] for target in hibiscus["targets"]))
        self.assertEqual([row["range_id"] for row in (hibiscus, stward, lancet)], ["3-3", "3-1", "3-1"])
        self.assertFalse(all(target["covered"] for target in stward["targets"]))
        self.assertEqual([target["covered"] for target in lancet["targets"]], [True, False])

    def test_c1_hibiscus_second_activation_not_ready(self):
        result = engine().check_timing_constraints({
            "skill_activations": [
                {"operator_id": "char_120_hibisc", "frame": 3000, "assume_ready": True},
                {"operator_id": "char_120_hibisc", "frame": 4200, "assume_ready": True},
            ],
            "dp_ledger": {"initial_dp": 0, "entries": []},
            "deployment_conditions": [],
        })
        self.assertEqual(result["conflicts"][0]["earliest_ready_frame"], 4500)
        self.assertEqual(result["conflicts"][0]["frame"], 4200)
        self.assertEqual(result["proof_status"], "NOT_A_BATTLE_FEASIBILITY_PROOF")

    def test_unknown_mechanic_returns_unknown(self):
        result = engine().query_mechanic({"topic": "not_whitelisted"})
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["result"])
        self.assertIn("topic is not in the whitelist", result["unknowns"][0])

    def test_stage_and_affordance_summaries_stay_readonly(self):
        eng = engine()
        stage = eng.query_mechanic({"topic": "r8_1_stage_facts"})
        affordance = eng.query_mechanic({"topic": "affordance_catalog"})
        self.assertEqual(stage["result"]["roadblock_tiles_col_row"], [[5, 3], [9, 4], [7, 2], [1, 2], [3, 5]])
        self.assertEqual(stage["result"]["stage_id"], "main_08-01")
        self.assertIn("supported_mechanics", affordance["result"])
        self.assertIn("omitted_or_unknown_mechanics", affordance["result"])

    def test_invalid_configuration_is_rejected_without_reorientation(self):
        arguments = coverage_call("char_120_hibisc", [5, 7], "UP", [("x", [4, 6])])
        arguments["configuration"]["level"] += 1
        with self.assertRaisesRegex(ValueError, "declared configuration"):
            engine().query_range_coverage(arguments)

    def test_source_mapping_hashes_existing_sources(self):
        mapping = source_mapping(BASE_RULE_CARD["sources"])
        self.assertTrue(all(row["exists"] for row in mapping["sources"].values()))
        self.assertTrue(all(len(row["sha256"]) == 64 for row in mapping["sources"].values()))


class ToolLoopTests(unittest.TestCase):
    def setUp(self):
        self.engine = engine()
        base = json.loads((ROOT / "output/r8_1_low_star_full_tactical_closure_v2/llm_request.json").read_text())
        self.payload = build_tool_enabled_request(base)
        self.plan = json.loads((ROOT / "output/r8_1_low_star_full_tactical_closure_v2/llm_structured_output.json").read_text())

    def test_tool_enabled_request_preserves_user_start_and_forbids_previous_response(self):
        self.assertEqual(self.payload["input"][0]["role"], "user")
        self.assertNotIn("previous_response_id", self.payload)
        self.assertEqual({tool["name"] for tool in self.payload["tools"]}, {"query_mechanic", "query_range_coverage", "check_timing_constraints"})
        self.assertIn("TOOLS_AND_BASE_RULES_JSON", self.payload["input"][0]["content"][0]["text"])

    def test_end_to_end_mock_queries_and_returns_valid_plan(self):
        arguments = coverage_call("char_120_hibisc", [5, 7], "UP", [("char_122_beagle", [4, 6])])
        call = {"call_id": "call-1", "name": "query_range_coverage", "arguments": json.dumps(arguments, separators=(",", ":"))}
        terminal_call = {"type": "function_call", "call_id": "call-1", "name": "query_range_coverage", "arguments": call["arguments"]}
        terminal_plan = {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(self.plan)}]}

        def fake_stream(payload):
            if "function_call_output" not in payload["input"][-1].get("type", ""):
                envelope = {"id": "resp-tool", "status": "completed", "output": [terminal_call]}
                events = [
                    ("response.created", {"response": {"id": "resp-tool", "status": "in_progress", "output": []}}),
                    ("response.output_item.added", {"item": terminal_call}),
                    ("response.function_call_arguments.delta", {"call_id": "call-1", "delta": call["arguments"]}),
                    ("response.function_call_arguments.done", {"call_id": "call-1", "arguments": call["arguments"]}),
                    ("response.completed", {"response": envelope}),
                ]
            else:
                envelope = {"id": "resp-plan", "status": "completed", "output": [terminal_plan]}
                events = [
                    ("response.created", {"response": {"id": "resp-plan", "status": "in_progress", "output": []}}),
                    ("response.completed", {"response": envelope}),
                ]
            accumulator = StreamAccumulator()
            from kimi_responses_transport import parse_sse
            for event in parse_sse(sse(events)):
                accumulator.observe(event)
            return envelope, accumulator, sse(events)

        result = run_mock_tool_session(self.payload, self.engine, fake_stream, lambda parsed: [] if parsed == self.plan else ["plan mismatch"])
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["budget"]["model_requests_started"], 2)
        self.assertEqual(result["budget"]["tool_calls_executed"], 1)
        self.assertEqual(result["trajectories"][0]["tool_results"][0]["result"]["covered_tiles_json_row_col"][0], [5, 6])
        continuation = result["trajectories"][1]["request"]
        self.assertEqual(continuation["input_roles_types"][0], {"role": "user", "type": None})
        self.assertEqual(continuation["input_roles_types"][1], {"role": None, "type": "function_call_output"})
        self.assertIsNone(continuation["previous_response_id"])

    def test_incomplete_tool_response_is_not_executed(self):
        def fake_stream(payload):
            envelope = {"id": "resp-incomplete", "status": "in_progress", "output": []}
            accumulator = StreamAccumulator()
            from kimi_responses_transport import parse_sse
            payload_text = "event: response.created\ndata: {}\n\nevent: response.incomplete\ndata: {}\n\n"
            for event in parse_sse(payload_text):
                accumulator.observe(event)
            return envelope, accumulator, payload_text.encode()
        executed = mock.Mock()
        with mock.patch("kimi_tool_loop.execute_tool_calls", executed):
            result = run_mock_tool_session(self.payload, self.engine, fake_stream)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error"], "NO_TERMINAL_EVENT")
        executed.assert_not_called()

    def test_invalid_call_and_wrong_result_ids_are_rejected(self):
        call = {"call_id": "call-bad", "name": "shell", "arguments": "{}"}
        budget = ToolLoopBudget()
        results = execute_tool_calls([call], self.engine, budget)
        self.assertEqual(results[0]["status"], "INVALID_NOT_EXECUTED")
        self.assertEqual(budget.tool_calls_seen, 1)
        self.assertEqual(budget.tool_calls_executed, 0)
        with self.assertRaisesRegex(Exception, "call_ids"):
            build_tool_continuation_payload(self.payload, [{"call_id": "a", "name": "query_mechanic", "arguments": "{}"}], [{"call_id": "wrong", "result": {}}])

    def test_request_budget_exhausts_before_fourth_model_request(self):
        call = {"call_id": "call-loop", "name": "query_mechanic", "arguments": json.dumps({"topic": "coordinates_and_direction"})}
        terminal_call = {"type": "function_call", **{key: value for key, value in call.items() if key != "name"}, "name": "query_mechanic"}
        def fake_stream(payload):
            envelope = {"id": "resp-loop", "status": "completed", "output": [terminal_call]}
            accumulator = StreamAccumulator()
            from kimi_responses_transport import parse_sse
            events = [
                ("response.created", {"response": {"id": "resp-loop", "status": "in_progress", "output": []}}),
                ("response.completed", {"response": envelope}),
            ]
            for event in parse_sse(sse(events)):
                accumulator.observe(event)
            return envelope, accumulator, sse(events)
        result = run_mock_tool_session(self.payload, self.engine, fake_stream)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error"], "request budget exhausted before final plan")
        self.assertEqual(result["budget"]["model_requests_started"], 3)

    def test_invalid_final_plan_fails_without_simulation(self):
        terminal_plan = {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(self.plan)}]}
        def fake_stream(payload):
            envelope = {"id": "resp-bad", "status": "completed", "output": [terminal_plan]}
            accumulator = StreamAccumulator()
            from kimi_responses_transport import parse_sse
            events = [
                ("response.created", {"response": {"id": "resp-bad", "status": "in_progress", "output": []}}),
                ("response.completed", {"response": envelope}),
            ]
            for event in parse_sse(sse(events)):
                accumulator.observe(event)
            return envelope, accumulator, sse(events)
        result = run_mock_tool_session(self.payload, self.engine, fake_stream, lambda parsed: ["invalid synthetic plan"])
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["errors"], ["invalid synthetic plan"])


if __name__ == "__main__":
    unittest.main()
