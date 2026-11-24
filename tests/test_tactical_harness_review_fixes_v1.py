"""Offline unit tests for the five tactical-harness review items.

No model call, no simulation, no experiment ledger: these import the harness module directly
and exercise pure functions / a fake production executor under output/.
"""
from __future__ import annotations

import gzip
import json
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
import importlib.util  # noqa: E402
import sys  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src"))

_SPEC = importlib.util.spec_from_file_location(
    "tactical_harness_service_v1", REPO_ROOT / "scripts/tactical_harness/tactical_harness_service_v1.py"
)
harness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(harness)


@pytest.fixture()
def scratch() -> Path:
    """The production service forbids repository-external paths, so unit fixtures live under output/."""
    import shutil
    import uuid

    root = REPO_ROOT / "output/tactical_harness_unit" / uuid.uuid4().hex[:12]
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "batch_state.json", {"schema_version": harness.STATE_SCHEMA, "rounds": [], "variants": [], "stopped": False})
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _observe(scratch: Path, result: dict, events: list, stage_id: str = "main_08-07") -> dict:
    sim = scratch / "session/candidates/candidate-001/simulation"
    _write(sim / "diagnostic_summary.json", {"result": result})
    _write(sim / "diagnostic_events.json", {"events": events})
    harness.BASE = scratch
    harness.CONFIG = types.SimpleNamespace(stage_id=stage_id)
    return harness.observe("candidate-001")


R8_7_WIN_RESULT = {
    "win": True, "enemies_killed": 33, "enemies_leaked": 0,
    "operator_deaths": [], "remaining_life": 3, "final_dp": 10,
    "deployment_errors": [], "enemies_remaining": 0,
}
BOTH_ARRIVALS = [
    {"frame": 11119, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#14", "target_id": None, "details": {}},
    {"frame": 11349, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#3", "target_id": None, "details": {}},
]


# --------------------------------------------------------------------------- item 1
def test_recoverable_and_fatal_statuses_are_disjoint_and_explicit():
    assert "FAIL" in harness.RECOVERABLE_CHECK_STATUSES
    assert "INPUT_REJECTED_BEFORE_PRODUCTION_CHECK" in harness.RECOVERABLE_CHECK_STATUSES
    assert not (harness.RECOVERABLE_CHECK_STATUSES & harness.FATAL_CHECK_STATUSES)
    assert "CHECK_BUDGET_EXHAUSTED" in harness.FATAL_CHECK_STATUSES


def test_check_fault_classification_separates_ledger_from_service():
    ledger = harness.classify_check_fault(RuntimeError("candidate ledger belongs to a different session"))
    assert ledger["kind"] == "ledger_inconsistency"
    service = harness.classify_check_fault(RuntimeError("connection refused"))
    assert service["kind"] == "check_service_fault"
    assert harness.fatal_stop_kind("CHECK_BUDGET_EXHAUSTED") == "check_budget_exhausted"
    assert harness.fatal_stop_kind("BUDGET_EXHAUSTED") == "check_budget_exhausted"


# --------------------------------------------------------------------------- item 3
def test_plan_grid_reports_huge_grid_without_allocating():
    names, total, shape = harness.plan_grid({f"d{i}": list(range(10)) for i in range(8)})
    assert total == 10 ** 8
    assert shape["dimensions"] == 8 and names == [f"d{i}" for i in range(8)]


def test_iter_grid_is_lazy_and_ordered():
    grid = {"a": [1, 2, 3], "b": ["x", "y"]}
    iterator = harness.iter_grid(grid)
    assert next(iterator) == (1, "x")
    assert next(iterator) == (1, "y")
    assert next(iterator) == (2, "x")
    assert harness._preview_rows(grid, "p", 2) == [
        {"index": 0, "name": "p_0", "parameters": {"a": 1, "b": "x"}},
        {"index": 1, "name": "p_1", "parameters": {"a": 1, "b": "y"}},
    ]
    with pytest.raises(RuntimeError):
        harness.plan_grid({"a": 5})


# --------------------------------------------------------------------------- item 4
def test_complete_win_requires_every_declared_condition(scratch: Path):
    observed = _observe(scratch, R8_7_WIN_RESULT, BOTH_ARRIVALS)
    assert observed["stage_acceptance"]["status"] == "COMPLETE_WIN"
    assert observed["complete_win"] is True


def test_missing_enemies_remaining_is_insufficient_evidence(scratch: Path):
    result = {k: v for k, v in R8_7_WIN_RESULT.items() if k != "enemies_remaining"}
    observed = _observe(scratch, result, BOTH_ARRIVALS)
    assert observed["stage_acceptance"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert observed["complete_win"] is False


def test_definite_failure_is_not_win_even_with_other_fields_missing(scratch: Path):
    result = {"win": True, "enemies_killed": 20, "enemies_leaked": 3, "deployment_errors": []}
    observed = _observe(scratch, result, BOTH_ARRIVALS)
    assert observed["stage_acceptance"]["status"] == "NOT_WIN"
    assert any("enemies_leaked" in failure for failure in observed["stage_acceptance"]["failures"])


def test_duplicate_arrival_id_never_satisfies_two_targets(scratch: Path):
    result = dict(R8_7_WIN_RESULT)
    events = [BOTH_ARRIVALS[0], {**BOTH_ARRIVALS[0], "frame": 11120}]
    observed = _observe(scratch, result, events)
    acceptance = observed["stage_acceptance"]
    assert acceptance["status"] == "NOT_WIN"
    assert any("duplicate arrival" in failure for failure in acceptance["failures"])


def test_artillery_and_key_enemies_come_from_stage_profile(scratch: Path):
    result = dict(R8_7_WIN_RESULT)
    events = BOTH_ARRIVALS + [
        {"frame": 4273, "event_type": "ENEMY_DEATH", "source_id": "char_210_stward", "target_id": "enemy_1112_emppnt#0", "details": {"kill_counted": True}},
        {"frame": 4281, "event_type": "ENEMY_DEATH", "source_id": "char_210_stward", "target_id": "enemy_1107_uoffcr#19", "details": {"kill_counted": True}},
    ]
    observed = _observe(scratch, result, events)
    assert observed["artillery_kill"]["frame"] == 4273
    assert observed["key_enemy_kills"]["enemy_1107_uoffcr#19"]["frame"] == 4281


def test_fake_projection_cannot_certify_a_real_win(scratch: Path):
    result = {**R8_7_WIN_RESULT, "FAKE_TEST": True}
    observed = _observe(scratch, result, BOTH_ARRIVALS)
    assert observed["stage_acceptance"]["status"] == "ARTIFACT_PROJECTION_NOT_REAL_WIN"
    assert observed["complete_win"] is False


def test_unconfigured_stage_is_insufficient_not_win(scratch: Path):
    observed = _observe(scratch, R8_7_WIN_RESULT, BOTH_ARRIVALS, stage_id="main_99-99")
    assert observed["stage_acceptance"]["status"] == "INSUFFICIENT_EVIDENCE"


def test_real_m70_archive_is_a_certified_complete_win(scratch: Path):
    """The frozen eight-op WIN must still satisfy the stricter acceptance rule."""
    archive = REPO_ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic"
    if not (archive / "diagnostic_events.json.gz").is_file():
        pytest.skip("M70 archive not present in this checkout")
    sim = scratch / "session/candidates/candidate-001/simulation"
    for name in ("diagnostic_events.json", "diagnostic_summary.json"):
        (sim).mkdir(parents=True, exist_ok=True)
        (sim / name).write_bytes(gzip.decompress((archive / f"{name}.gz").read_bytes()))
    harness.BASE = scratch
    harness.CONFIG = types.SimpleNamespace(stage_id="main_08-07")
    observed = harness.observe("candidate-001")
    assert observed["stage_acceptance"]["status"] == "COMPLETE_WIN"
    assert observed["protected_arrival_distinct_count"] == 2
    assert observed["artillery_kill"] is not None


# --------------------------------------------------------------------------- item 2 + 5 (helpers)
def test_payload_hash_matches_production_check_hash():
    """The ledger reconciliation key must equal what production.check_plan hashes."""
    import kimiark_tactical_stdio_service_v1 as production

    payload = {"revised_operational_plans": [{"operational_plan_id": "X_1", "action_timeline": []}]}
    expected = production.sha256_bytes(production.canonical_json(payload).encode("utf-8"))
    assert harness.payload_candidate_sha256(payload) == expected


def test_teacher_message_id_is_stable_and_content_addressed(scratch: Path):
    harness.BASE = scratch
    harness.CONFIG = types.SimpleNamespace()
    first = harness.record_teacher_prompt(None, {"text": "原样转给 Astra：先查 1382 的 SP。"})
    second = harness.record_teacher_prompt(None, {"text": "原样转给 Astra：先查 1382 的 SP。"})
    assert first["status"] == "RECORDED"
    assert second["status"] == "ALREADY_RECORDED"
    assert first["message_id"] == second["message_id"]
    assert len(harness.teacher_messages()) == 1


def test_astra_paraphrase_is_flagged_not_labelled_verbatim(scratch: Path):
    harness.BASE = scratch
    harness.CONFIG = types.SimpleNamespace()
    msg = harness.record_teacher_prompt(None, {"text": "先看 SP 是否转好，再谈夹炮兵。"})
    record = harness.record_teaching(None, {
        "teacher_message_id": msg["message_id"],
        "user_quote": "A paraphrased rewrite",
        "astra_interpretation": "Astra believes the cast is refused for charge reasons",
    })
    assert record["quote_provenance"] == "ASTRA_QUOTE_DIVERGES_FROM_STORED_TEACHER_MESSAGE"
    assert record["quote_mismatch"] is not None
    quotes = (scratch / "teaching/user_quotes_v1.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(quotes[0])["quote"] == "A paraphrased rewrite"


def test_resolved_teacher_quote_uses_stored_text(scratch: Path):
    harness.BASE = scratch
    harness.CONFIG = types.SimpleNamespace()
    msg = harness.record_teacher_prompt(None, {"text": "先看 SP 是否转好。"})
    record = harness.record_teaching(None, {"teacher_message_id": msg["message_id"], "astra_interpretation": "x"})
    assert record["quote_provenance"] == "TEACHER_VERBATIM_RESOLVED_FROM_STORED_MESSAGE"
    quotes = (scratch / "teaching/user_quotes_v1.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(quotes[0])["quote"] == "先看 SP 是否转好。"
