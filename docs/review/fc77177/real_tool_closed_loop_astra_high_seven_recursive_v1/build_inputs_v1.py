#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_coupled_contact_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_recursive_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_events(candidate: str) -> list[dict]:
    path = SOURCE / f"session/candidates/{candidate}/simulation/diagnostic_events.json.gz"
    return json.loads(gzip.open(path, "rt", encoding="utf-8").read())["events"]


def load_result(candidate: str) -> dict:
    summary_path = SOURCE / f"session/candidates/{candidate}/simulation/diagnostic_summary.json.gz"
    summary = json.loads(gzip.open(summary_path, "rt", encoding="utf-8").read())
    return {
        key: value
        for key, value in summary["result"].items()
        if key != "events"
    }


def main() -> None:
    for path in [
        SOURCE / "input_bundle/llm_evidence_context.json",
        SOURCE / "input_bundle/revision_output_schema.json",
    ]:
        shutil.copyfile(path, DEST / "input_bundle" / path.name)

    for candidate in ["candidate-001", "candidate-002"]:
        output = DEST / f"input_bundle/parent_{candidate}"
        output.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / f"session/candidates/{candidate}/simulation/plan_snapshot.json", output / "plan_snapshot.json")
        shutil.copyfile(SOURCE / f"session/candidates/{candidate}/simulation/action_snapshot.json", output / "action_snapshot.json")
        shutil.copyfile(SOURCE / f"session/candidates/{candidate}/simulation/diagnostic_events.json.gz", output / "diagnostic_events.json.gz")
        shutil.copyfile(SOURCE / f"session/candidates/{candidate}/simulation/diagnostic_summary.json.gz", output / "diagnostic_summary.json.gz")

    events = load_events("candidate-002")

    def targets(event_type: str, target_id: str | None = None, source_id: str | None = None):
        return [
            {
                "frame": event["frame"],
                "source_id": event.get("source_id"),
                "target_id": event.get("target_id"),
                "details": event.get("details"),
            }
            for event in events
            if event["event_type"] == event_type
            and (target_id is None or event.get("target_id") == target_id)
            and (source_id is None or event.get("source_id") == source_id)
        ]

    artillery = sorted({event.get("source_id") for event in events if (event.get("source_id") or "").startswith("enemy_1112_emppnt")})
    reconciliation = {
        "schema_version": "KIMIARK_SEVEN_RECURSIVE_PARENT_RECONCILIATION_V1",
        "source_experiment": SOURCE.relative_to(ROOT).as_posix(),
        "source_candidates": {
            "candidate-001": {
                "sha256": json.loads((SOURCE / "session/candidates/candidate-001/candidate_record.json").read_text())["candidate_sha256"],
                "events_gz_sha256": sha256(SOURCE / "session/candidates/candidate-001/simulation/diagnostic_events.json.gz"),
            },
            "candidate-002": {
                "sha256": json.loads((SOURCE / "session/candidates/candidate-002/candidate_record.json").read_text())["candidate_sha256"],
                "events_gz_sha256": sha256(SOURCE / "session/candidates/candidate-002/simulation/diagnostic_events.json.gz"),
            },
        },
        "event_semantics": {
            "ENEMY_DEATH": "target_id is the dead entity; source_id is the killer in observed events.",
            "ENEMY_LEAK": "source_id is the leaked entity; target_id is null in observed events.",
            "DAMAGE_ENEMY_ABILITY_HIT": "Both can be operator damage; DEVICE_DAMAGE is roadblock/device damage.",
        },
        "candidate_001": {
            "result": load_result("candidate-001"),
            "operator_deaths": targets("OPERATOR_DEATH"),
            "central_contact": {
                "enemy_1110_uamord#21": [],
                "enemy_1110_uamord#22": [],
                "enemy_1110_uamord#34": [],
            },
            "roadblocks": targets("DEVICE_DESTROYED"),
            "protected": {
                "enemy_3001_upeopl#3": targets("ENEMY_DEATH", target_id="enemy_3001_upeopl#3"),
                "enemy_3001_upeopl#14": targets("PROTECTED_TARGET_REACHED", target_id="enemy_3001_upeopl#14"),
            },
        },
        "candidate_002": {
            "result": load_result("candidate-002"),
            "operator_deaths": targets("OPERATOR_DEATH"),
            "central_contact": {
                "enemy_1110_uamord#21": [e for e in targets("DAMAGE", target_id="enemy_1110_uamord#21")],
                "enemy_1110_uamord#22": [e for e in targets("BLOCK", target_id="enemy_1110_uamord#22") + targets("DAMAGE", target_id="enemy_1110_uamord#22")],
                "enemy_1110_uamord#34": [],
            },
            "leaks": targets("ENEMY_LEAK"),
            "roadblocks": targets("DEVICE_DESTROYED"),
            "artillery_ids": artillery,
            "artillery_ability_starts": targets("ENEMY_ABILITY_START"),
            "protected": {
                "enemy_3001_upeopl#3": targets("ENEMY_DEATH", target_id="enemy_3001_upeopl#3"),
                "enemy_3001_upeopl#14": targets("PROTECTED_TARGET_REACHED", target_id="enemy_3001_upeopl#14"),
            },
        },
    }
    (DEST / "input_bundle/coupled_contact_parent_reconciliation_v1.json").write_text(
        json.dumps(reconciliation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest_path = DEST / "input_bundle/bundle_manifest_v1.json"
    bundle_dir = DEST / "input_bundle"
    bundle_paths = sorted(
        path
        for path in bundle_dir.rglob("*")
        if path.is_file() and path != manifest_path and "__pycache__" not in path.parts
    )
    manifest = {
        "schema_version": "KIMIARK_SEVEN_RECURSIVE_INPUT_BUNDLE_MANIFEST_V1",
        "files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in bundle_paths
        ],
    }
    (DEST / "input_bundle/bundle_manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(DEST)


if __name__ == "__main__":
    main()
