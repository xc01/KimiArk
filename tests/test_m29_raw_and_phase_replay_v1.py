from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "docs/review/fc77177/m29_phase_replay_v2_v3.json"
MANIFEST = ROOT / "docs/review/fc77177/m29_iteration_raw_manifest_v1.json"
BUDGET = ROOT / "docs/review/fc77177/m29_simulation_budget_v1.json"
V4_FEEDBACK = ROOT / "docs/review/fc77177/m29_v4_causal_feedback_v1.json"
V4_EVENTS = ROOT / (
    "output/r8_1_r8_7_batch_v1/main_08-07/m29_iteration_v1/"
    "m29_v4_evaluation_v1/diagnostic/diagnostic_events.json.gz"
)
V5_FEEDBACK = ROOT / "docs/review/fc77177/m29_v5_causal_feedback_v1.json"
V5_EVENTS = ROOT / (
    "output/r8_1_r8_7_batch_v1/main_08-07/m29_iteration_v1/"
    "attempt_09_diagnostic/diagnostic_events.json.gz"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_phase_replay_binds_saved_plans_and_key_events() -> None:
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    assert replay["schema_version"] == "KIMIARK_M29_SAVED_EVENT_PHASE_REPLAY_V1"
    plans = {row["plan_id"]: row for row in replay["plans"]}
    assert set(plans) == {"R8_7_GPT_M29_V2", "R8_7_GPT_M29_V3"}

    for row in replay["plans"]:
        plan_path = ROOT / row["source_plan"]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["operational_plan_id"] == row["plan_id"]
        replay_ids = [phase["phase_id"] for phase in row["phase_replay"]]
        assert replay_ids == [phase["phase_id"] for phase in plan["battle_phases"]]

    v2 = plans["R8_7_GPT_M29_V2"]
    assert v2["earliest_failure_chain"]["first_operator_death"]["frame"] == 1380
    assert v2["earliest_failure_chain"]["first_leak"]["frame"] == 4731
    v3 = plans["R8_7_GPT_M29_V3"]
    assert v3["earliest_failure_chain"]["first_operator_death"]["frame"] == 1269
    assert v3["earliest_failure_chain"]["first_leak"]["frame"] == 1611


def _has_event(events: list[dict], expected: dict) -> bool:
    return any(
        event.get("event_type") == expected["event_type"]
        and event.get("frame") == expected["frame"]
        and event.get("source_id") == expected["source_id"]
        and event.get("target_id") == expected["target_id"]
        for event in events
    )


def test_replay_key_events_exist_in_compressed_saved_records() -> None:
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    expected = {
        "R8_7_GPT_M29_V2": [
            {"event_type": "OPERATOR_DEATH", "frame": 1380, "source_id": "char_285_medic2", "target_id": None},
            {"event_type": "ENEMY_DEATH", "frame": 3330, "source_id": "enemy_1112_emppnt#0", "target_id": "enemy_3001_upeopl#3"},
            {"event_type": "ENEMY_LEAK", "frame": 4731, "source_id": "enemy_1107_uoffcr#19", "target_id": None},
            {"event_type": "PROTECTED_TARGET_REACHED", "frame": 11624, "source_id": "enemy_3001_upeopl#14", "target_id": None},
        ],
        "R8_7_GPT_M29_V3": [
            {"event_type": "OPERATOR_DEATH", "frame": 1269, "source_id": "char_123_fang", "target_id": None},
            {"event_type": "ENEMY_LEAK", "frame": 1611, "source_id": "enemy_1107_uoffcr#6", "target_id": None},
            {"event_type": "PROTECTED_TARGET_REACHED", "frame": 2867, "source_id": "enemy_3001_upeopl#3", "target_id": None},
            {"event_type": "ENEMY_DEATH", "frame": 3930, "source_id": "enemy_1112_emppnt#0", "target_id": "enemy_3001_upeopl#14"},
        ],
    }
    for row in replay["plans"]:
        events_path = ROOT / row["source_events"]
        with gzip.open(events_path.with_suffix(".json.gz"), "rt", encoding="utf-8") as handle:
            events = json.load(handle)["events"]
        assert all(_has_event(events, item) for item in expected[row["plan_id"]])


def test_raw_manifest_hashes_match_compressed_and_available_files() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "KIMIARK_M29_RAW_MATERIAL_MANIFEST_V2"
    checked = 0
    for row in manifest["files"]:
        compressed = ROOT / (row.get("compressed_path") or "")
        if compressed.is_file():
            assert _sha256(compressed) == row["compressed_sha256"]
            digest = hashlib.sha256()
            with gzip.open(compressed, "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            assert digest.hexdigest() == row["sha256"]
            checked += 1
        else:
            original = ROOT / row["path"]
            if original.is_file():
                assert _sha256(original) == row["sha256"]
                checked += 1
    assert checked >= 100


def test_phase_replay_evidence_corrections_are_bound_to_saved_events() -> None:
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    names = {row["operator_id"]: row["name"] for row in replay["operator_name_corrections"]}
    assert names == {"char_240_wyvern": "香草", "char_192_falco": "翎羽"}

    v2 = next(row for row in replay["plans"] if row["plan_id"] == "R8_7_GPT_M29_V2")
    eastern = next(phase for phase in v2["phase_replay"] if phase["phase_id"] == "EASTERN_RELEASE")
    assert eastern["observation"] == "ROADBLOCK_3_NOT_DESTROYED_MEDIC_FAIL"
    assert any(
        evidence["event_type"] == "DEVICE_DAMAGE"
        and evidence["frame"] == 1860
        and evidence["target_id"] == "trap_020_roadblock#3"
        for evidence in eastern["direct_evidence"]
    )
    assert all(
        not (evidence["event_type"] == "DEVICE_DESTROYED" and evidence["frame"] == 1860)
        for evidence in eastern["direct_evidence"]
    )

    artillery = next(phase for phase in v2["phase_replay"] if phase["phase_id"] == "ARTILLERY")
    civilian_hit = next(
        evidence
        for evidence in artillery["direct_evidence"]
        if evidence.get("frame") == 3030 and evidence.get("target_id") == "enemy_3001_upeopl#3"
    )
    assert civilian_hit["event_type"] == "DAMAGE"

    events_path = ROOT / v2["source_events"]
    with gzip.open(events_path.with_suffix(".json.gz"), "rt", encoding="utf-8") as handle:
        events = json.load(handle)["events"]
    assert not any(
        event["event_type"] == "DEVICE_DESTROYED"
        and event["frame"] == 1860
        and event.get("target_id") == "trap_020_roadblock#3"
        for event in events
    )
    assert any(
        event["event_type"] == "DAMAGE"
        and event["frame"] == 3030
        and event.get("source_id") == "enemy_1112_emppnt#0"
        and event.get("target_id") == "enemy_3001_upeopl#3"
        for event in events
    )


def test_v4_feedback_tracks_completed_loss_and_key_saved_events() -> None:
    assert json.loads(BUDGET.read_text(encoding="utf-8"))["started_stage_simulations"] >= 3
    feedback = json.loads(V4_FEEDBACK.read_text(encoding="utf-8"))
    medical = feedback["medical_support_replay"]
    assert [row["operator_id"] for row in medical["deployment_established"]] == ["char_212_ansel", "char_120_hibisc"]
    assert medical["deployment_established"][1]["direction"] == "DOWN"
    assert medical["deployment_established"][1]["direction_source"] == "FROZEN_ACTION"
    assert all(row["direction_observation"] == "NOT_RECORDED" for row in medical["deployment_direct_observation"])
    assert medical["status_at_1680"] == "BOTH_ANSEL_AND_HIBISCUS_ALIVE_AND_HEALING"
    assert feedback["validation"]["static_conflicts"] == 0
    assert feedback["validation"]["battle_classification"] == "LEGAL_BATTLE_LOSS"
    assert feedback["result"]["simulator_win"] is False
    assert feedback["result"]["enemies_leaked"] == 12
    assert feedback["result"]["operator_deaths"] == 10
    assert feedback["predicted_enemy_death"]["status"] == "EVENT_OBSERVED"

    with gzip.open(V4_EVENTS, "rt", encoding="utf-8") as handle:
        events = json.load(handle)["events"]
    expected = [
        {"event_type": "ENEMY_DEATH", "frame": 1080, "source_id": "char_124_kroos", "target_id": "enemy_1108_uterer#4"},
        {"event_type": "ENEMY_DEATH", "frame": 3180, "source_id": "enemy_1112_emppnt#0", "target_id": "enemy_3001_upeopl#3"},
        {"event_type": "ENEMY_LEAK", "frame": 5759, "source_id": "enemy_1112_emppnt#0", "target_id": None},
        {"event_type": "BLOCK", "frame": 3620, "source_id": "trap_020_roadblock#2", "target_id": "enemy_3001_upeopl#14"},
        {"event_type": "PROTECTED_TARGET_REACHED", "frame": 8774, "source_id": "enemy_3001_upeopl#14", "target_id": None},
    ]
    assert all(_has_event(events, item) for item in expected)


def test_v5_feedback_tracks_revised_hypothesis_and_saved_loss() -> None:
    assert json.loads(BUDGET.read_text(encoding="utf-8"))["started_stage_simulations"] == 4
    feedback = json.loads(V5_FEEDBACK.read_text(encoding="utf-8"))
    assert feedback["validation"]["battle_classification"] == "LEGAL_BATTLE_LOSS"
    assert feedback["predicted_enemy_death"]["status"] == "EVENT_OBSERVED"
    assert feedback["hypothesis_comparison"]["v4_failure_addressed"]["roadblock_3_cleared"] is True
    assert feedback["result"] == {
        "simulator_win": False,
        "perfect_project_win": False,
        "enemies_killed": 24,
        "enemies_leaked": 9,
        "operator_deaths": 9,
        "remaining_life": -8,
        "final_dp": 99,
        "score": -700,
        "protected_target_deaths": 2,
        "protected_target_arrivals": 0,
        "remaining_hostiles_at_run_end": 0,
        "first_leak_frame": 5319,
        "first_leak_enemy": "enemy_1110_uamord#21",
        "first_objective_failure_frame": 5385,
        "run_end_time": 301.0,
    }

    with gzip.open(V5_EVENTS, "rt", encoding="utf-8") as handle:
        events = json.load(handle)["events"]
    expected = [
        {"event_type": "ENEMY_DEATH", "frame": 1095, "source_id": "char_208_melan", "target_id": "enemy_1108_uterer#4"},
        {"event_type": "DEVICE_DESTROYED", "frame": 1815, "source_id": "char_208_melan", "target_id": "trap_020_roadblock#3"},
        {"event_type": "ENEMY_DEATH", "frame": 3930, "source_id": "enemy_1112_emppnt#0", "target_id": "enemy_3001_upeopl#14"},
        {"event_type": "ENEMY_LEAK", "frame": 5759, "source_id": "enemy_1112_emppnt#0", "target_id": None},
        {"event_type": "ENEMY_DEATH", "frame": 5430, "source_id": "enemy_1112_emppnt#0", "target_id": "enemy_3001_upeopl#3"},
    ]
    assert all(_has_event(events, item) for item in expected)
    assert not any(
        event["event_type"] == "DEVICE_DESTROYED"
        and event.get("target_id") == "trap_020_roadblock#4"
        for event in events
    )
