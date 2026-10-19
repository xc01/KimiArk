from __future__ import annotations

import fcntl
import json
from pathlib import Path

import schedule_kimiark_usage_retry_v1 as scheduler


def test_reconcile_does_not_keep_a_dead_executor_waiting(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "scheduler"
    state_dir.mkdir()
    monkeypatch.setattr(scheduler, "STATE_DIR", state_dir)
    monkeypatch.setattr(scheduler, "STATE_PATH", state_dir / "state.json")
    monkeypatch.setattr(scheduler, "LOCK_PATH", state_dir / "scheduler.lock")
    monkeypatch.setattr(scheduler, "PID_PATH", state_dir / "scheduler.pid")
    monkeypatch.setattr(scheduler, "LOG_PATH", state_dir / "scheduler.log")
    (state_dir / "state.json").write_text(json.dumps({
        "status": "WAITING",
        "next_run_local": "2026-01-01T00:00:00+08:00",
    }), encoding="utf-8")

    result = scheduler.reconcile("EXECUTOR_NOT_RUNNING")

    assert result == {
        "status": "STOPPED",
        "stop_reason": "EXECUTOR_NOT_RUNNING",
        "executor_alive": False,
        "state_file": str(state_dir / "state.json"),
    }
    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "STOPPED"
    assert state["stop_reason"] == "EXECUTOR_NOT_RUNNING"
    assert state["executor_alive"] is False


def test_lock_is_held_detects_an_active_executor(tmp_path: Path, monkeypatch) -> None:
    lock_path = tmp_path / "scheduler.lock"
    monkeypatch.setattr(scheduler, "LOCK_PATH", lock_path)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert scheduler.lock_is_held() is True
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    assert scheduler.lock_is_held() is False
