from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_astra_high_cold_start_attempt3_v1.py"
spec = importlib.util.spec_from_file_location("runner", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_run_once_records_success_and_turn_completion(tmp_path: Path) -> None:
    stdout = tmp_path / "stdout.jsonl"
    stderr = tmp_path / "stderr.txt"
    stdin = tmp_path / "stdin.txt"
    stdin.write_text("")
    argv = [sys.executable, "-c", "print('{\"type\":\"turn.completed\"}')"]
    result = runner.run_once(
        argv=argv, cwd=tmp_path, stdout_path=stdout, stderr_path=stderr,
        stdin_path=stdin, timeout_seconds=5,
    )
    assert result["status"] == "COMPLETED"
    assert result["turn_completed"] is True
    assert result["exit_code"] == 0
    assert result["automatic_retry"] is False


def test_run_once_records_timeout_and_does_not_retry(tmp_path: Path) -> None:
    stdout = tmp_path / "stdout.jsonl"
    stderr = tmp_path / "stderr.txt"
    stdin = tmp_path / "stdin.txt"
    stdin.write_text("")
    result = runner.run_once(
        argv=[sys.executable, "-c", "import time; time.sleep(1)"],
        cwd=tmp_path, stdout_path=stdout, stderr_path=stderr,
        stdin_path=stdin, timeout_seconds=1,
    )
    assert result["status"] == "TIMED_OUT"
    assert result["timed_out"] is True
    assert result["turn_completed"] is False
