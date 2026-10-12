from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from kimi_responses_transport import StreamAccumulator  # noqa: E402


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_r8_1_low_star_full_tactical_closure_v1",
        ROOT / "scripts/run_r8_1_low_star_full_tactical_closure_v1.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeHeaders:
    def get(self, name: str):
        return "test-request-id" if name.lower() == "x-request-id" else None


class FakeResponse:
    status = 200

    def __init__(self, chunks):
        self._chunks = tuple(chunks)
        self.headers = FakeHeaders()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __iter__(self):
        yield from self._chunks


def synthetic_evidence(module):
    return {
        "stage_active_facts": {
            "roadblock_tiles_col_row": module.ROADBLOCK_TILES_COL_ROW,
            "deployable_ground_tiles_col_row": [[4, 3]],
            "deployable_high_ground_tiles_col_row": [[2, 2]],
        },
        "historical_context_not_active": {
            "status": "HISTORICAL_ONLY_DO_NOT_USE_AS_ACTIVE_FACTS"
        },
        "normal_low_star_catalog": [
            {
                "operator_id": "char_123_fang",
                "identity": {"rarity": 3, "position": "MELEE"},
                "qualification": {"normal_mode": True},
            }
        ],
    }


def synthetic_plan(operator_id="char_123_fang", missing_direction=False):
    deploy = {
        "action_type": "DEPLOY",
        "frame": 27,
        "operator_id": operator_id,
        "tile": [3, 4],
    }
    if not missing_direction:
        deploy["direction"] = "RIGHT"
    return {
        "revised_operational_plans": [
            {
                "operational_plan_id": "test-plan",
                "parent_hypothesis_id": "test-hypothesis",
                "tactical_thesis": "synthetic offline contract sample",
                "selected_low_star_operator_ids": [operator_id],
                "deployment_positions_and_directions": [{"operator_id": operator_id, "tile": [3, 4], "direction": "RIGHT"}],
                "formation_structure": {"opening": "one melee blocker"},
                "formation_transitions": [],
                "corridor_responsibilities": [{"route": "route-1", "responsibility": "block"}],
                "pressure_window_responsibilities": [],
                "skill_intents": [],
                "mandatory_tactical_invariants": [],
                "action_timeline": [deploy],
            }
        ],
        "revised_stage_understanding": {"synthetic": True},
        "revised_tactical_requirements": {"synthetic": True},
        "revised_strategic_hypotheses": [],
    }


class LowStarFullClosureV1Tests(unittest.TestCase):
    def test_prompt_embeds_evidence_json(self) -> None:
        module = load_runner()
        prompt = module.prompt_text({"test_marker": {"operator_id": "char_123_fang", "cost": 11}})
        self.assertIn("EVIDENCE_JSON", prompt)
        self.assertIn("char_123_fang", prompt)
        self.assertNotIn("survived frame 941 with 0 leaks", prompt)

    def test_empty_incomplete_event_preserves_created_envelope(self) -> None:
        accumulator = StreamAccumulator()
        accumulator.observe(
            type("SSEEvent", (), {"event": "response.created", "data": {"response": {"model": "kimi-k3", "status": "in_progress"}}, "sequence": 1})()
        )
        accumulator.observe(type("SSEEvent", (), {"event": "response.incomplete", "data": {}, "sequence": 2})())
        classification = accumulator.classify()
        self.assertEqual(accumulator.response_envelope["model"], "kimi-k3")
        self.assertEqual(classification["terminal_event"], "response.incomplete")
        self.assertFalse(classification["complete"])

    def test_valid_final_payload_and_contract_handoff(self) -> None:
        module = load_runner()
        evidence = synthetic_evidence(module)
        payload = module.request_payload(module.prompt_text(evidence))
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            module.OUT.joinpath("llm_request_body.txt").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            evidence_path = module.OUT / "llm_evidence_context.json"
            evidence_path.write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
            validation = module.validate_final_payload(payload, evidence_path)
            self.assertEqual(validation["status"], "PASS")
            parsed = synthetic_plan()
            self.assertEqual(module.validate_operational_plan_output(parsed, evidence), [])
            module.OUT.joinpath("response.json").write_text(json.dumps(parsed), encoding="utf-8")
            handoff = module.build_strategy_handoff(parsed["revised_operational_plans"][0])
            self.assertEqual(handoff["status"], "HANDOFF_READY_NOT_COMPILED")
            self.assertEqual(handoff["strategy_actions"][0]["tile_col_row"], [4, 3])

    def test_stale_cache_or_mismatched_body_is_rejected(self) -> None:
        module = load_runner()
        evidence = synthetic_evidence(module)
        current_payload = module.request_payload(module.prompt_text(evidence))
        stale_payload = module.request_payload("stale prompt without evidence")
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            module.OUT.joinpath("llm_request_body.txt").write_text(json.dumps(stale_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            evidence_path = module.OUT / "llm_evidence_context.json"
            evidence_path.write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError) as context:
                module.validate_final_payload(current_payload, evidence_path)
            self.assertIn("does not match saved pending body", str(context.exception))

    def test_empty_embedded_evidence_is_rejected_against_nonempty_prepared(self) -> None:
        module = load_runner()
        evidence = synthetic_evidence(module)
        payload = module.request_payload("EVIDENCE_JSON\n{}")
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            module.OUT.joinpath("llm_request_body.txt").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            evidence_path = module.OUT / "llm_evidence_context.json"
            evidence_path.write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError) as context:
                module.validate_final_payload(payload, evidence_path)
            self.assertIn("does not match current prepared evidence", str(context.exception))

    def test_second_attempt_is_rejected_before_network(self) -> None:
        module = load_runner()
        payload = {"model": module.MODEL, "input": [{"role": "user", "content": []}], "stream": True}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            module.OUT.joinpath("llm_call_attempts.jsonl").write_text("{}\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"ARK_API_KEY_agent": "offline-test"}), mock.patch("urllib.request.urlopen", side_effect=AssertionError("network must not be called")):
                with self.assertRaisesRegex(RuntimeError, "exactly-one-attempt"):
                    module.stream_once(payload)

    def test_schema_rejects_empty_multiple_and_missing_direction(self) -> None:
        module = load_runner()
        from jsonschema import Draft7Validator

        validator = Draft7Validator(module.output_schema())
        evidence = synthetic_evidence(module)
        empty = module.validate_operational_plan_output({"revised_operational_plans": []}, evidence)
        multiple = module.validate_operational_plan_output({"revised_operational_plans": [synthetic_plan(), synthetic_plan()]}, evidence)
        missing_direction = module.validate_operational_plan_output(synthetic_plan(missing_direction=True), evidence)
        self.assertTrue(any("exactly one" in error for error in empty))
        self.assertTrue(any("exactly one" in error for error in multiple))
        self.assertTrue(any("lacks a legal direction" in error for error in missing_direction))
        for parsed in ({}, {"revised_operational_plans": []}, {"revised_operational_plans": [synthetic_plan(), synthetic_plan()]}):
            self.assertTrue(list(validator.iter_errors(parsed)))
        missing_direction_parsed = synthetic_plan(missing_direction=True)
        self.assertTrue(list(validator.iter_errors(missing_direction_parsed)))

    def test_http_error_is_counted_and_preserves_status(self) -> None:
        module = load_runner()
        payload = {"model": module.MODEL, "input": [{"role": "user", "content": []}], "stream": True}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            error = urllib.error.HTTPError(module.BASE_URL, 401, "Unauthorized", {}, io.BytesIO(b"http failure"))
            with mock.patch.dict(os.environ, {"ARK_API_KEY_agent": "offline-test"}), mock.patch("urllib.request.urlopen", side_effect=error):
                envelope, accumulator, raw = module.stream_once(payload)
            self.assertEqual(accumulator.http_status, 401)
            records = [json.loads(line) for line in module.OUT.joinpath("llm_call_attempts.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["status"], "ATTEMPT_STARTED")
            self.assertEqual(records[1]["status"], "ATTEMPT_FAILED")
            self.assertEqual(records[1]["http_status"], 401)

    def test_timeout_is_counted_without_retry(self) -> None:
        module = load_runner()
        payload = {"model": module.MODEL, "input": [{"role": "user", "content": []}], "stream": True}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            with mock.patch.dict(os.environ, {"ARK_API_KEY_agent": "offline-test"}), mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
                module.stream_once(payload)
            records = [json.loads(line) for line in module.OUT.joinpath("llm_call_attempts.jsonl").read_text().splitlines()]
            self.assertEqual(records[-1]["status"], "ATTEMPT_FAILED")
            self.assertIn("TIMEOUT", records[-1]["error"])

    def test_stream_interrupt_is_counted(self) -> None:
        module = load_runner()
        payload = {"model": module.MODEL, "input": [{"role": "user", "content": []}], "stream": True}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            def fail_after_chunk():
                yield b"event: response.output_text.delta\ndata: {}\n\n"
                raise OSError("stream interrupted")

            class InterruptedResponse:
                status = 200
                headers = FakeHeaders()

                def __iter__(self):
                    return fail_after_chunk()

            class InterruptedContext:
                def __enter__(self):
                    return InterruptedResponse()

                def __exit__(self, *args):
                    return False

            with mock.patch.dict(os.environ, {"ARK_API_KEY_agent": "offline-test"}), mock.patch("urllib.request.urlopen", return_value=InterruptedContext()):
                module.stream_once(payload)
            records = [json.loads(line) for line in module.OUT.joinpath("llm_call_attempts.jsonl").read_text().splitlines()]
            self.assertEqual(records[-1]["status"], "ATTEMPT_FAILED")
            self.assertIn("INTERRUPTED", records[-1]["error"])

    def test_call_sends_validated_body_and_rejects_incomplete(self) -> None:
        module = load_runner()
        evidence = synthetic_evidence(module)
        prompt = module.prompt_text(evidence)
        payload = module.request_payload(prompt)
        parsed = synthetic_plan()
        completed = {
            "model": module.MODEL,
            "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(parsed)}]}],
        }
        incomplete = {"model": module.MODEL, "status": "in_progress"}
        sse = (
            f"event: response.created\ndata: {json.dumps({'response': incomplete})}\n\n"
            f"event: response.output_text.delta\ndata: {json.dumps({'delta': json.dumps(parsed)})}\n\n"
            f"event: response.output_text.done\ndata: {json.dumps({'text': json.dumps(parsed)})}\n\n"
            f"event: response.incomplete\ndata: {json.dumps({'response': {}})}\n\n"
        )
        captured = {}
        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse([sse.encode()])
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            module.OUT.joinpath("llm_request.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            module.OUT.joinpath("llm_evidence_context.json").write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
            module.OUT.joinpath("llm_request_body.txt").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            with mock.patch.dict(os.environ, {"ARK_API_KEY_agent": "offline-test"}), mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                with self.assertRaises(SystemExit):
                    module.call()
            expected = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            self.assertEqual(captured["request"].data, expected)
            self.assertFalse(module.OUT.joinpath("llm_structured_output.json").exists())
            status = json.loads(module.OUT.joinpath("final_status.json").read_text())
            self.assertEqual(status["status"], "KIMI_CALL_FAILED_NO_RETRY")
            self.assertEqual(status["http_status"], 200)
            self.assertEqual(status["terminal_event"], "response.incomplete")

    def test_call_saves_completed_response_handoff(self) -> None:
        module = load_runner()
        evidence = synthetic_evidence(module)
        prompt = module.prompt_text(evidence)
        payload = module.request_payload(prompt)
        parsed = synthetic_plan()
        envelope = {
            "model": module.MODEL,
            "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(parsed)}]}],
        }
        sse = (
            f"event: response.created\ndata: {json.dumps({'response': envelope})}\n\n"
            f"event: response.output_text.delta\ndata: {json.dumps({'delta': json.dumps(parsed)})}\n\n"
            f"event: response.output_text.done\ndata: {json.dumps({'text': json.dumps(parsed)})}\n\n"
            f"event: response.completed\ndata: {json.dumps({'response': envelope})}\n\n"
        )
        captured = {}
        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse([sse.encode()])
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(module, "OUT", Path(directory)):
            module.OUT.mkdir(exist_ok=True)
            module.OUT.joinpath("llm_request.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            module.OUT.joinpath("llm_evidence_context.json").write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
            module.OUT.joinpath("llm_request_body.txt").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            with mock.patch.dict(os.environ, {"ARK_API_KEY_agent": "offline-test"}), mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                module.call()
            expected = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            self.assertEqual(captured["request"].data, expected)
            saved = json.loads(module.OUT.joinpath("llm_structured_output.json").read_text())
            self.assertEqual(saved, parsed)
            handoff = json.loads(module.OUT.joinpath("strategy_handoff.json").read_text())
            self.assertEqual(handoff["status"], "HANDOFF_READY_NOT_COMPILED")
            self.assertEqual(handoff["certificate"], "NONE")
            self.assertEqual(handoff["strategy_actions"][0]["tile_col_row"], [4, 3])
            status = json.loads(module.OUT.joinpath("final_status.json").read_text())
            self.assertEqual(status["status"], "KIMI_CALL_AND_CONTRACT_COMPLETE")


if __name__ == "__main__":
    unittest.main()
