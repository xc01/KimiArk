from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_experience_selector_v1 as selector


def _fake_candidate(tmp_path: Path, *, corrupted: bool = False) -> tuple[Path, Path]:
    source = tmp_path / "candidate-001"
    sim = source / "simulation"
    sim.mkdir(parents=True)
    plan = {"operational_plan_id": "TEST_PLAN_001", "action_timeline": [{"action_type": "DEPLOY", "operator_id": "char_212_ansel"}], "selected_low_star_operator_ids": ["char_212_ansel"]}
    action = {"action_timeline": plan["action_timeline"]}
    events = {"events": [{"event_type": "HEAL", "source_id": "char_120_hibisc", "target_id": "char_210_stward"}]}
    (sim / "plan_snapshot.json").write_text(json.dumps(plan), encoding="utf-8")
    (sim / "action_snapshot.json").write_text(json.dumps(action), encoding="utf-8")
    raw = json.dumps(events).encode("utf-8")
    if corrupted:
        (sim / "diagnostic_events.json.gz").write_bytes(b"\x1f\x8bcorrupt")
    else:
        (sim / "diagnostic_events.json.gz").write_bytes(gzip.compress(raw))
    closeout = {"model": {"configured_model": "fake-model", "reasoning_effort": "high"}, "candidate": {
        "candidate_id": "candidate-001", "plan_id": "TEST_PLAN_001",
        "plan_sha256": selector.sha256_file(sim / "plan_snapshot.json"),
        "action_sha256": selector.sha256_file(sim / "action_snapshot.json"),
        "events_gz_sha256": selector.sha256_file(sim / "diagnostic_events.json.gz"),
        "events_restored_sha256": selector.sha256_bytes(raw),
        "observed_key_events": {"relevant_heals": events["events"]},
        "summary_result": {"win": False, "enemies_killed": 1, "enemies_leaked": 2},
        "validation_card": {"causal_change": "route healer coverage"},
    }}
    closeout_path = source / "closeout.json"
    closeout_path.write_text(json.dumps(closeout), encoding="utf-8")
    return closeout_path, sim


def _record(record_id: str, *, tags: list[str], win: bool, mechanics: str = selector.MECHANICS_VERSION) -> dict:
    return {
        "record_id": record_id, "plan_id": record_id, "candidate_id": "candidate-001",
        "mechanics_version": mechanics, "configured_model": "fake", "operator_union": ["a"],
        "operator_union_count": 1, "responsibility_tags": tags,
        "evidence_hashes": {"actual": {"plan_sha256": "p", "action_sha256": "a"}},
        "responsible_paths": {}, "archive_status": "VERIFIED", "coverage_status": "FIXED_SIMULATOR_ONLY",
        "normalized_action_sha256": record_id, "retention_status": "ELIGIBLE",
        "event_observation_summary": {"summary_result": {"win": win, "enemies_killed": 20, "enemies_leaked": 3}, "observed_key_events": {}},
    }


def test_record_requires_consistent_union_and_current_mechanics() -> None:
    record = _record("A", tags=["ARTILLERY_OUTPUT"], win=False)
    assert selector.validate_record(record) == []
    record["operator_union_count"] = 2
    assert "operator_union_count mismatch" in selector.validate_record(record)


def test_import_is_idempotent_and_duplicate_is_reported() -> None:
    records = [_record("A", tags=["WIN_REFERENCE"], win=True)]
    merged, updated = selector.import_idempotent(records, records)
    assert merged == records
    assert updated == []
    changed = records[0] | {"event_observation_summary": {"summary_result": {"win": True, "enemies_killed": 21, "enemies_leaked": 3}}}
    merged, updated = selector.import_idempotent(records, [changed])
    assert updated == ["A"]


def test_branch_retention_keeps_distinct_strengths_and_duplicates() -> None:
    records = [
        _record("WIN", tags=["WIN_REFERENCE"], win=True),
        _record("OUTPUT", tags=["ARTILLERY_OUTPUT"], win=False),
        _record("SUPPORT", tags=["SUPPORT_DELIVERY"], win=False),
        _record("DUPLICATE", tags=["PROTECTED_ROUTE"], win=False),
    ]
    records[3]["normalized_action_sha256"] = "OUTPUT"
    _, retained, changes = selector.retain_branches(records)
    assert {"WIN", "OUTPUT", "SUPPORT"} <= set(retained)
    assert "DUPLICATE_ACTION:OUTPUT==DUPLICATE" in changes


def test_bad_hash_and_gzip_are_not_silently_imported(tmp_path: Path) -> None:
    closeout_path, sim = _fake_candidate(tmp_path)
    closeout = json.loads(closeout_path.read_text(encoding="utf-8"))
    closeout["candidate"]["plan_sha256"] = "0" * 64
    record, issues = selector.build_record(
        experiment_id="TEST", candidate_id="candidate-001", closeout_path=closeout_path,
        closeout=closeout, candidate=closeout["candidate"],
        plan_path=sim / "plan_snapshot.json", action_path=sim / "action_snapshot.json",
        events_path=sim / "diagnostic_events.json.gz",
    )
    assert record["archive_status"] == "IDENTITY_PROBLEM"
    assert record["retention_status"] == "REFERENCE_ONLY_IDENTITY_PROBLEM"
    assert issues["hash_mismatches"][0]["status"] == "MISMATCH"
    bad_closeout, bad_sim = _fake_candidate(tmp_path / "bad", corrupted=True)
    with pytest.raises(ValueError, match="corrupt gzip"):
        selector.load_events(bad_sim / "diagnostic_events.json.gz")


def test_m70_is_eight_id_reference_and_context_marks_reduction(tmp_path: Path) -> None:
    records, issues = selector.import_default_sources()
    m70 = next(record for record in records if record["plan_id"] == "R8_7_GPT_M70_V1")
    assert m70["operator_union_count"] == 8
    assert "WIN_REFERENCE" in m70["responsibility_tags"]
    assert not issues
    package, omitted = selector.build_context(
        records, goal="seven-ID artillery closure", k=7,
        target_tags={"ARTILLERY_KILL", "SUPPORT_DELIVERY"}, byte_limit=28_000,
        catalog_path=tmp_path / "catalog.json",
    )
    m70_context = next(item for item in package["parent_candidates"] if item["plan_id"] == "R8_7_GPT_M70_V1")
    assert m70_context["parent_eligibility"] == "REFERENCE_TO_EDIT"
    assert m70_context["k_constraint"]["must_reduce"] is True
    assert not [item for item in package["failed_evidence"] if item["record_id"] == m70["record_id"]]
    assert selector.DEFAULT_CATALOG.exists()


def test_selector_isolates_mechanics_and_observes_byte_limit(tmp_path: Path) -> None:
    records = [
        _record("CURRENT", tags=["SUPPORT_DELIVERY"], win=False),
        _record("STALE", tags=["SUPPORT_DELIVERY"], win=False, mechanics="other-mechanics"),
    ]
    selected = selector.select_complementary(records, k=7, target_tags={"SUPPORT_DELIVERY"})
    assert [item["record_id"] for item in selected] == ["CURRENT"]
    package, omitted = selector.build_context(records, goal="test", k=7, target_tags={"SUPPORT_DELIVERY"}, byte_limit=2_000, catalog_path=tmp_path / "missing.json")
    assert package and omitted
    assert package["byte_limit"] == 2_000


def test_prediction_is_not_marked_as_observation() -> None:
    record = _record("A", tags=["SUPPORT_DELIVERY"], win=False)
    record["model_predictions"] = [{"field": "causal_change", "prediction": "will heal Steward", "status": "MODEL_PREDICTION"}]
    assert record["model_predictions"][0]["status"] == "MODEL_PREDICTION"
    assert record["event_observation_summary"]["observed_key_events"] == {}
