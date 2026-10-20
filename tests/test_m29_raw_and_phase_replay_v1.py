from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "docs/review/fc77177/m29_phase_replay_v2_v3.json"
MANIFEST = ROOT / "docs/review/fc77177/m29_iteration_raw_manifest_v1.json"


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
        compressed = ROOT / row.get("compressed_path", "")
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
