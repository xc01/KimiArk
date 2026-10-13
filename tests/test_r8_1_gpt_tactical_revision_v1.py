import json
import unittest.mock
import tempfile
import unittest
from pathlib import Path

import run_r8_1_gpt_tactical_revision_v1 as runner
from kimi_responses_transport import StreamAccumulator, parse_sse
from kimi_tool_loop import build_tool_continuation_payload


ROOT = Path(__file__).parents[1]
OUT = ROOT / "output/r8_1_gpt_tactical_revision_v1"


class GptTacticalRevisionTests(unittest.TestCase):
    def test_provider_selection_and_bounded_request_fields(self):
        self.assertEqual(
            set(runner.PROVIDERS),
            {"sub2api", "kimi"},
        )
        self.assertEqual(runner.provider_config("sub2api")["credential_env"], "SUB2API_API_KEY")
        payload = json.loads((OUT / "llm_request.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["model"], "gpt-6.1-sol")
        self.assertEqual(payload["reasoning"], {"effort": "medium"})
        self.assertEqual(payload["max_output_tokens"], 32_768)
        self.assertNotIn("previous_response_id", payload)
        self.assertNotIn("text", payload)
        self.assertEqual({row["name"] for row in payload["tools"]}, {
            "query_mechanic", "query_range_coverage", "check_timing_constraints",
        })

    def test_prepared_payload_has_complete_low_star_catalog_and_no_credentials(self):
        evidence = json.loads((OUT / "llm_evidence_context.json").read_text(encoding="utf-8"))
        body = (OUT / "llm_request_body.txt").read_bytes()
        self.assertEqual(len(evidence["normal_low_star_catalog"]), 34)
        self.assertEqual(sum(row["identity"]["rarity"] == 3 for row in evidence["normal_low_star_catalog"]), 17)
        self.assertEqual(evidence["tactical_provider"], {
            "provider": "sub2api",
            "model": "gpt-6.1-sol",
            "reasoning_effort": "medium",
            "compatibility": "UNVERIFIED_BEFORE_PROJECT_REQUEST",
        })
        self.assertLessEqual(len(body), runner.INITIAL_BODY_LIMIT)
        self.assertNotIn(b"Bearer", body)
        self.assertNotIn(b"Authorization", body)

    def test_parent_hypothesis_may_reference_strategic_hypothesis_not_plan_id(self):
        parsed = json.loads((OUT / "invalid_final_plan.json").read_text(encoding="utf-8"))["parsed"]
        evidence = json.loads((OUT / "llm_evidence_context.json").read_text(encoding="utf-8"))
        errors = runner.validate_c3_contract(parsed, evidence)
        self.assertNotIn("parent_hypothesis_id must reference a revised_strategic_hypotheses hypothesis_id", errors)
        self.assertIn("action[17] frame is out of order", errors)
        self.assertIn("provenance.revision_source must identify C2", errors)

    def test_tool_continuation_keeps_call_context_before_result(self):
        base_payload = json.loads((OUT / "llm_request.json").read_text(encoding="utf-8"))
        call = {
            "call_id": "test_call_id", "name": "query_mechanic",
            "arguments": '{"topic":"WIN"}',
        }
        result = [{"call_id": "test_call_id", "result": {"status": "OK"}}]
        continuation = build_tool_continuation_payload(base_payload, [call], result)
        self.assertEqual([row.get("type") for row in continuation["input"]], [
            None, "function_call", "function_call_output",
        ])
        self.assertEqual(continuation["input"][-2]["call_id"], "test_call_id")
        self.assertEqual(continuation["input"][-1]["call_id"], "test_call_id")

    def test_missing_credential_stops_without_http_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_dir = Path(temporary)
            temporary_dir.mkdir(exist_ok=True)
            (temporary_dir / "llm_call_attempts.jsonl").write_text("", encoding="utf-8")
            (temporary_dir / "budget_usage.json").write_text(json.dumps({
                "model_requests_started": 0, "max_model_requests": 3,
                "readonly_tool_calls_executed": 0,
            }), encoding="utf-8")
            for name in ("llm_evidence_context.json", "revision_output_schema.json", "llm_request.json"):
                (temporary_dir / name).write_bytes((OUT / name).read_bytes())
            original_out = runner.OUT
            runner.OUT = temporary_dir
            try:
                with unittest.mock.patch.dict("os.environ", {"SUB2API_API_KEY": ""}, clear=False):
                    with self.assertRaises(SystemExit):
                        runner.call("sub2api", "gpt-6.1-sol", "medium")
            finally:
                runner.OUT = original_out
            self.assertEqual(json.loads((temporary_dir / "budget_usage.json").read_text())["model_requests_started"], 0)
            self.assertFalse(any(temporary_dir.glob("attempt_*.json")))
            self.assertEqual(
                json.loads((temporary_dir / "final_status.json").read_text())["actual_model_requests"], 0,
            )

    def test_gpt_completed_commentary_with_native_call_executes_tool(self):
        message = {
            "type": "message", "id": "msg-1", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": "I’ll verify economy before planning."}],
        }
        call = {
            "type": "function_call", "id": "fc-1", "item_id": "fc-1",
            "call_id": "call-1", "name": "query_mechanic",
            "arguments": '{"topic":"economy"}', "status": "completed",
        }
        raw = "\n".join([
            "event: response.created",
            "data: " + json.dumps({"response": {"id": "resp-1", "status": "in_progress", "output": []}}),
            "",
            "event: response.completed",
            "data: " + json.dumps({"response": {"id": "resp-1", "status": "completed", "output": [message, call]}}),
            "",
        ])
        accumulator = StreamAccumulator()
        for event in parse_sse(raw):
            accumulator.observe(event)
        classification = accumulator.classify()
        self.assertTrue(classification["requires_tool_execution"])
        self.assertTrue(classification["assistant_message_present"])
        self.assertEqual(classification["function_call_completion_statuses"], ["completed"])
        self.assertEqual(classification["function_calls"][0]["name"], "query_mechanic")
        self.assertEqual(classification["function_calls"][0]["arguments"], '{"topic":"economy"}')

    def test_stream_attempt_files_continue_persisted_budget_sequence(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_dir = Path(temporary)
            (temporary_dir / "llm_call_attempts.jsonl").write_text("", encoding="utf-8")
            (temporary_dir / "budget_usage.json").write_text(json.dumps({
                "model_requests_started": 1, "max_model_requests": 3,
                "readonly_tool_calls_executed": 0,
            }), encoding="utf-8")
            original_out = runner.OUT
            runner.OUT = temporary_dir
            try:
                stream_once = runner.make_stream_once("sub2api", "gpt-6.1-sol", "medium")
                with unittest.mock.patch.dict("os.environ", {"SUB2API_API_KEY": "offline-test"}, clear=False):
                    with unittest.mock.patch.object(runner.urllib.request, "urlopen", side_effect=RuntimeError("offline")):
                        with self.assertRaises(RuntimeError):
                            stream_once({"stream": True, "input": []})
            finally:
                runner.OUT = original_out
            self.assertTrue((temporary_dir / "attempt_2_request.json").is_file())
            self.assertTrue((temporary_dir / "attempt_2_request_body.txt").is_file())

    def test_started_records_block_restart_even_without_finish_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_dir = Path(temporary)
            (temporary_dir / "llm_call_attempts.jsonl").write_text(
                json.dumps({"phase": "STARTED", "request_body_sha256": "abc"}) + "\n",
                encoding="utf-8",
            )
            (temporary_dir / "budget_usage.json").write_text(json.dumps({
                "model_requests_started": 0, "max_model_requests": 3,
                "readonly_tool_calls_executed": 0,
            }), encoding="utf-8")
            original_out = runner.OUT
            runner.OUT = temporary_dir
            try:
                with self.assertRaisesRegex(RuntimeError, "1/3 STARTED records"):
                    runner.reconcile_budget_from_request_log()
            finally:
                runner.OUT = original_out
            self.assertEqual(
                json.loads((temporary_dir / "budget_usage.json").read_text())["model_requests_started"], 1,
            )

    def test_concurrent_entries_are_locked(self):
        original_out = runner.OUT
        with tempfile.TemporaryDirectory() as temporary:
            temporary_dir = Path(temporary)
            (temporary_dir / "llm_call_attempts.jsonl").write_text("", encoding="utf-8")
            (temporary_dir / "budget_usage.json").write_text(json.dumps({
                "model_requests_started": 0, "max_model_requests": 3,
                "readonly_tool_calls_executed": 0,
            }), encoding="utf-8")
            runner.OUT = temporary_dir
            original_handle = runner.RUN_LOCK_HANDLE
            runner.RUN_LOCK_HANDLE = None
            try:
                runner.assert_run_lock()
                (temporary_dir / "budget_usage.json").write_text(json.dumps({
                    "model_requests_started": 1, "max_model_requests": 3,
                    "readonly_tool_calls_executed": 0,
                }), encoding="utf-8")
                runner.RUN_LOCK_HANDLE = None
                with self.assertRaisesRegex(RuntimeError, "budget lock already consumed"):
                    runner.assert_run_lock()
            finally:
                runner.RUN_LOCK_HANDLE = original_handle
                runner.OUT = original_out

    def test_lock_recovers_only_before_any_model_request(self):
        original_out = runner.OUT
        with tempfile.TemporaryDirectory() as temporary:
            temporary_dir = Path(temporary)
            (temporary_dir / "llm_call_attempts.jsonl").write_text("", encoding="utf-8")
            (temporary_dir / "run.lock").write_text("{}\n", encoding="utf-8")
            (temporary_dir / "budget_usage.json").write_text(json.dumps({
                "model_requests_started": 0, "max_model_requests": 3,
                "readonly_tool_calls_executed": 0,
            }), encoding="utf-8")
            original_handle = runner.RUN_LOCK_HANDLE
            runner.OUT = temporary_dir
            runner.RUN_LOCK_HANDLE = None
            try:
                runner.assert_run_lock()
            finally:
                runner.RUN_LOCK_HANDLE = original_handle
                runner.OUT = original_out


if __name__ == "__main__":
    unittest.main()
