import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_r8_1_gpt_c4_codex_cli_v1 as runner


ROOT = Path(__file__).parents[1]


class GptC4CodexCliTests(unittest.TestCase):
    def test_codex_command_is_argument_array_without_shell_bypass(self):
        command = runner.build_command(Path("schema.json"), Path("final.txt"))
        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertIn("--json", command)
        self.assertIn("--sandbox", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertIn('model_provider="openai"', command)
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_codex_process_receives_local_proxy_defaults(self):
        with mock.patch.dict(runner.os.environ, {}, clear=True):
            environment = runner.codex_environment()
        self.assertEqual(environment["HTTP_PROXY"], "http://127.0.0.1:7890")
        self.assertEqual(environment["HTTPS_PROXY"], "http://127.0.0.1:7890")
        self.assertEqual(environment["ALL_PROXY"], "socks5://127.0.0.1:7890")

    def test_jsonl_trajectory_extracts_ids_and_usage(self):
        raw = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
            json.dumps({"type": "session", "session_id": "session-1", "usage": {"input_tokens": 11, "output_tokens": 7}}),
            "not-json",
        ])
        summary = runner.extract_events_summary(raw)
        self.assertEqual(summary["session_ids"], ["session-1"])
        self.assertEqual(summary["thread_ids"], ["thread-1"])
        self.assertEqual(summary["usage_records"][0]["usage"], {"input_tokens": 11, "output_tokens": 7})
        self.assertEqual(summary["malformed_lines"], [3])
        self.assertEqual(summary["internal_model_request_count"], "UNKNOWN_CLI_INTERNAL")

    def test_failed_cli_process_is_counted_and_not_restarted(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_dir = Path(temporary)
            original_out = runner.OUT
            runner.OUT = temporary_dir
            try:
                runner.write_json(temporary_dir / "budget_usage.json", {"cli_process_starts": 0})
                completed = mock.Mock(returncode=3, stdout="", stderr="provider unavailable")
                with mock.patch.object(runner.subprocess, "run", return_value=completed) as run:
                    execution = runner.run_codex_once("prompt", ["codex", "exec"], 1)
                    self.assertEqual(execution["process"]["exit_code"], 3)
                    self.assertEqual(run.call_count, 1)
                    self.assertEqual(run.call_args.kwargs.get("shell", False), False)
                    with self.assertRaises(FileExistsError):
                        runner.run_codex_once("prompt", ["codex", "exec"], 1)
                    self.assertEqual(run.call_count, 1)
                state = json.loads((temporary_dir / "budget_usage.json").read_text())
                self.assertEqual(state["cli_process_starts"], 1)
                self.assertEqual(
                    json.loads((temporary_dir / "cli_process_result.json").read_text())["exit_code"], 3,
                )
            finally:
                runner.OUT = original_out

    def test_invalid_final_message_is_rejected_without_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_dir = Path(temporary)
            original_out = runner.OUT
            original_source = runner.SOURCE
            runner.OUT = temporary_dir
            runner.SOURCE = ROOT / "output/r8_1_gpt_c4_tactical_revision_v1"
            try:
                (temporary_dir / "codex_final_message.txt").write_text("not-json", encoding="utf-8")
                completed = mock.Mock(returncode=0, stdout="", stderr="")

                def fake_run(*args, **kwargs):
                    runner.run_codex_once("prompt", args[0], kwargs["timeout"])
                    return completed

                with mock.patch.object(runner.subprocess, "run", return_value=completed):
                    with self.assertRaises(SystemExit):
                        runner.run_session()
                self.assertFalse((temporary_dir / "llm_structured_output.json").exists())
                self.assertEqual(
                    json.loads((temporary_dir / "llm_plan_validation.json").read_text())["status"], "FAIL",
                )
            finally:
                runner.OUT = original_out
                runner.SOURCE = original_source


if __name__ == "__main__":
    unittest.main()
