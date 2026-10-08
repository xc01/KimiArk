from __future__ import annotations

import unittest

from kimi_responses_transport import consume_stream, parse_sse, validate_tactical_request


NORMAL_STREAM = """event: response.created
data: {"response":{"id":"resp_1","status":"in_progress","output":[]}}

event: response.in_progress
data: {"response":{"id":"resp_1","status":"in_progress","output":[]}}

event: response.reasoning_summary_text.delta
data: {"delta":"thinking"}

event: response.output_item.added
data: {"item":{"type":"reasoning"}}

event: response.output_item.added
data: {"item":{"type":"message"}}

event: response.output_text.delta
data: {"delta":"OK"}

event: response.output_text.done
data: {"text":"OK"}

event: response.output_item.done
data: {"item":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"OK"}]}}

event: response.completed
data: {"response":{"id":"resp_1","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"OK"}]}]}}

"""

NO_TERMINAL_STREAM = NORMAL_STREAM.replace(
    'event: response.completed\ndata: {"response":{"id":"resp_1","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"OK"}]}]}}\n\n',
    "",
)

REASONING_ONLY_STREAM = """event: response.created
data: {"response":{"id":"resp_2","status":"in_progress","output":[]}}

event: response.output_item.added
data: {"item":{"type":"reasoning"}}

event: response.reasoning_summary_text.delta
data: {"delta":"long reasoning"}

event: response.completed
data: {"response":{"id":"resp_2","status":"completed","output":[{"type":"reasoning","summary":[{"type":"summary_text","text":"long reasoning"}]}]}}

"""

FAILED_STREAM = """event: response.created
data: {"response":{"id":"resp_3","status":"in_progress","output":[]}}

event: response.failed
data: {"response":{"id":"resp_3","status":"failed","error":{"code":"X"}}}

"""

MALFORMED_STREAM = """event: response.created
data: {not-json}

event: response.output_item.added
data: {"item":{"type":"message"}}

event: response.output_text.delta
data: {"delta":"OK"}

event: response.completed
data: {"response":{"id":"resp_4","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"OK"}]}]}}

"""

DUPLICATED_DONE_STREAM = """event: response.created
data: {"response":{"id":"resp_5","status":"in_progress","output":[]}}

event: response.output_item.added
data: {"item":{"type":"message"}}

event: response.output_text.delta
data: {"delta":"OK"}

event: response.output_text.done
data: {"text":"OK"}

event: response.output_text.done
data: {"text":"OK"}

event: response.completed
data: {"response":{"id":"resp_5","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"OK"}]}]}}

"""


class ResponsesTransportTests(unittest.TestCase):
    def test_normal_stream_separates_reasoning_and_final_text(self):
        result = consume_stream(NORMAL_STREAM).classify()
        self.assertTrue(result["complete"])
        self.assertTrue(result["assistant_message_present"])
        self.assertEqual(result["final_output_text"], "OK")
        self.assertEqual(result["reasoning_text"], "thinking")
        self.assertEqual(result["terminal_event"], "response.completed")

    def test_connection_close_without_terminal_is_incomplete(self):
        result = consume_stream(NO_TERMINAL_STREAM).classify()
        self.assertFalse(result["complete"])
        self.assertIsNone(result["terminal_event"])
        self.assertEqual(result["final_output_text"], "OK")

    def test_reasoning_is_not_final_output(self):
        result = consume_stream(REASONING_ONLY_STREAM).classify()
        self.assertFalse(result["complete"])
        self.assertFalse(result["assistant_message_present"])
        self.assertEqual(result["final_output_text"], "")
        self.assertEqual(result["reasoning_text"], "long reasoning")

    def test_failed_terminal_is_preserved(self):
        result = consume_stream(FAILED_STREAM).classify()
        self.assertFalse(result["complete"])
        self.assertEqual(result["terminal_event"], "response.failed")

    def test_event_order_is_preserved(self):
        events = parse_sse(NORMAL_STREAM)
        self.assertEqual([event.sequence for event in events], list(range(1, len(events) + 1)))
        self.assertEqual(events[-1].event, "response.completed")

    def test_completed_response_without_message_is_rejected(self):
        result = consume_stream(REASONING_ONLY_STREAM).classify()
        self.assertFalse(result["assistant_message_present"])
        self.assertFalse(result["complete"])

    def test_stream_interruption_has_no_synthetic_completion(self):
        result = consume_stream(NO_TERMINAL_STREAM).classify()
        self.assertIsNone(result["terminal_event"])
        self.assertFalse(result["complete"])

    def test_malformed_data_does_not_crash_accumulator(self):
        result = consume_stream(MALFORMED_STREAM).classify()
        self.assertEqual(result["terminal_event"], "response.completed")
        self.assertTrue(result["assistant_message_present"])
        self.assertEqual(result["final_output_text"], "OK")

    def test_duplicated_output_done_does_not_duplicate_text(self):
        result = consume_stream(DUPLICATED_DONE_STREAM).classify()
        self.assertTrue(result["complete"])
        self.assertEqual(result["final_output_text"], "OK")

    def test_assistant_prefill_and_previous_response_are_forbidden(self):
        errors = validate_tactical_request({
            "stream": True,
            "previous_response_id": "resp_old",
            "input": [{"role": "assistant", "content": []}],
        })
        self.assertIn("PREVIOUS_RESPONSE_ID_FORBIDDEN", errors)
        self.assertIn("INPUT_0_ROLE_NOT_USER", errors)


if __name__ == "__main__":
    unittest.main()
