#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from collections import Counter


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "docs/review/fc77177/real_tool_closed_loop_deterministic_seven_melanha_timing_v1"
SOURCE = BASE / "input_bundle/candidate_plan.json"
OUTPUT_DIR = BASE / "derived_stable_sort"
OUTPUT = OUTPUT_DIR / "normalized_stable_sort_candidate_plan_v1.json"
REPORT = OUTPUT_DIR / "stable_sort_normalization_record_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def canonical_multiset(actions: list[dict]) -> Counter:
    return Counter(json.dumps(action, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for action in actions)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    plan = source["revised_operational_plans"][0]
    original_actions = plan["action_timeline"]
    indexed_actions = list(enumerate(original_actions))
    stable_actions = sorted(indexed_actions, key=lambda item: int(item[1]["frame"]))
    mapping = [
        {
            "old_index": old_index,
            "new_index": new_index,
            "action_type": action["action_type"],
            "operator_id": action["operator_id"],
            "frame": int(action["frame"]),
            "moved": old_index != new_index,
        }
        for new_index, (old_index, action) in enumerate(stable_actions)
    ]
    normalized_actions = [copy.deepcopy(action) for _, action in stable_actions]

    if len(normalized_actions) != len(original_actions):
        raise SystemExit("stable sort changed action count")
    if [action["frame"] for action in normalized_actions] != sorted(int(action["frame"]) for action in original_actions):
        raise SystemExit("stable sort did not produce nondecreasing frames")
    if canonical_multiset(original_actions) != canonical_multiset(normalized_actions):
        raise SystemExit("action multiset changed")
    same_frame_preserved = True
    by_frame: dict[int, list[int]] = {}
    for row in mapping:
        by_frame.setdefault(row["frame"], []).append(row["old_index"])
    for old_indexes in by_frame.values():
        if old_indexes != sorted(old_indexes):
            same_frame_preserved = False

    normalized = copy.deepcopy(source)
    normalized["revised_operational_plans"][0]["action_timeline"] = normalized_actions
    write_json(OUTPUT, normalized)

    record = {
        "schema_version": "KIMIARK_R108_MELANHA_STABLE_SORT_NORMALIZATION_RECORD_V1",
        "purpose": "Serialization normalization only; no action field, roster, identity, tile, direction, or frame is changed.",
        "tactical_change_count": 0,
        "sort_key": ["frame"],
        "stable_same_frame_policy": "Python sorted stability preserves original relative order for equal frames.",
        "source": {
            "path": "input_bundle/candidate_plan.json",
            "sha256": digest(SOURCE),
            "action_count": len(original_actions),
        },
        "normalized": {
            "path": "derived_stable_sort/normalized_stable_sort_candidate_plan_v1.json",
            "sha256": digest(OUTPUT),
            "action_count": len(normalized_actions),
            "action_multiset_canonical_sha256": canonical_digest(normalized_actions),
        },
        "equivalence": {
            "action_count_equal": True,
            "action_object_sequence_after_order_removed_equal": original_actions == normalized_actions,
            "action_multiset_equal": True,
            "same_frame_relative_order_preserved": same_frame_preserved,
            "nondecreasing_after_sort": True,
        },
        "old_to_new_index_mapping": mapping,
        "moved_actions": [row for row in mapping if row["moved"]],
        "boundary": "This does not resolve SP_NOT_READY at 3903 and is not a production candidate, check, simulation, or tactical validation.",
    }
    write_json(REPORT, record)
    print(json.dumps({
        "moved_actions": record["moved_actions"],
        "normalized_sha256": record["normalized"]["sha256"],
        "same_frame_relative_order_preserved": same_frame_preserved,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
