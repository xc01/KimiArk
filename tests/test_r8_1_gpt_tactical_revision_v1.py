import json
import unittest.mock
import tempfile
import unittest
from pathlib import Path

import run_r8_1_gpt_tactical_revision_v1 as runner
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
                "model_requests_started": 0, "readonly_tool_calls_executed": 0,
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


if __name__ == "__main__":
    unittest.main()
