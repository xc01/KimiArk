from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from kimi_responses_transport import StreamAccumulator  # noqa: E402


class LowStarFullClosureV1Tests(unittest.TestCase):
    def test_prompt_embeds_evidence_json(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "run_r8_1_low_star_full_tactical_closure_v1",
            ROOT / "scripts/run_r8_1_low_star_full_tactical_closure_v1.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        prompt = module.prompt_text({"test_marker": {"operator_id": "char_123_fang", "cost": 11}})
        self.assertIn("EVIDENCE_JSON", prompt)
        self.assertIn("char_123_fang", prompt)

    def test_empty_incomplete_event_preserves_created_envelope(self) -> None:
        accumulator = StreamAccumulator()
        accumulator.observe(
            type(
                "SSEEvent",
                (),
                {
                    "event": "response.created",
                    "data": {"response": {"model": "kimi-k3", "status": "in_progress"}},
                    "sequence": 1,
                },
            )()
        )
        accumulator.observe(
            type(
                "SSEEvent",
                (),
                {"event": "response.incomplete", "data": {}, "sequence": 2},
            )()
        )
        classification = accumulator.classify()
        self.assertEqual(accumulator.response_envelope["model"], "kimi-k3")
        self.assertEqual(classification["terminal_event"], "response.incomplete")
        self.assertFalse(classification["complete"])


if __name__ == "__main__":
    unittest.main()
