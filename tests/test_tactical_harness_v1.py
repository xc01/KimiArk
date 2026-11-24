"""Fake-backend regression for the reusable tactical-experiment harness.

No model call and no real simulation: everything runs on TEST_ONLY_FAKE.
The production service forbids repository-external paths, so fixtures live under output/.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "scripts/tactical_harness/run_demo_fake_backend.py"


@pytest.fixture()
def demo_root() -> Path:
    relative = Path("output/tactical_harness_test") / uuid.uuid4().hex[:12]
    root = REPO_ROOT / relative
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _run_demo(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEMO), str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )


def test_harness_fake_backend_acceptance(demo_root: Path) -> None:
    completed = _run_demo(demo_root)
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-4000:]
    summary = [line for line in completed.stdout.splitlines() if line.startswith("checks:")]
    assert summary and "failed: 0" in summary[0], completed.stdout[-4000:]
    batch = demo_root / "acceptance_v1"
    state = json.loads((batch / "batch_state.json").read_text(encoding="utf-8"))
    assert sorted({row["round"] for row in state["rounds"]}) == [1, 2]
    assert state["teaching_records"], "expected at least one split teaching record"
    assert json.loads((batch / "candidate_ledger_v1.json").read_text(encoding="utf-8"))["used_candidates"] >= 2
    assert json.loads((batch / "simulation_budget_v1.json").read_text(encoding="utf-8"))["started_stage_simulations"] >= 2


def test_harness_transport_counts_started_and_completed_separately(demo_root: Path) -> None:
    completed = _run_demo(demo_root)
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-4000:]
    lines = [
        json.loads(line)
        for line in (demo_root / "acceptance_v1/tool_transport.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    phases = [row["phase"] for row in lines]
    assert phases.count("STARTED") == phases.count("COMPLETED")
    started = [row["id"] for row in lines if row["phase"] == "STARTED"]
    done = [row["id"] for row in lines if row["phase"] == "COMPLETED"]
    assert started == done


def test_harness_prepare_refuses_overwrite(demo_root: Path) -> None:
    out = demo_root / "batch"
    out.mkdir()
    (out / "session_config_v1.json").write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/tactical_harness/prepare_harness.py"),
            "--out", str(out.relative_to(REPO_ROOT)),
            "--template-evidence", "docs/review/fc77177/five_astra_r129_dual_track_v1/input_bundle/llm_evidence_context.json",
            "--template-schema", "docs/review/fc77177/five_astra_r129_dual_track_v1/input_bundle/revision_output_schema.json",
            "--session-id", "TEST_ONLY-x", "--stage-id", "FAKE_TEST-x",
            "--plan-prefix", "X_", "--plan-label", "X", "--backend", "TEST_ONLY_FAKE",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "refusing to overwrite" in (result.stderr + result.stdout)
