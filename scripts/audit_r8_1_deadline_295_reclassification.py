from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_deadline_295_reclassification_v1"
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
FRAME_RATE = 30
MECHANICS_VERSION = "m18.9-stage-device-runtime-v1"
STAGE_ID = "main_08-01"
ROUTE_ID = "route-3"
ENEMY_ID = "enemy_1107_uoffcr"


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def first_defined(record: dict[str, Any], key: str) -> Any:
    value = record.get(key, {})
    return value.get("m_value") if value.get("m_defined") else None


def spawn_frame(level: dict[str, Any]) -> int:
    fragment = next(
        fragment
        for wave in level["waves"]
        for fragment in wave.get("fragments", [])
        if any(
            action.get("actionType") == "SPAWN"
            and action.get("routeIndex") == 3
            and action.get("key") == ENEMY_ID
            for action in fragment.get("actions", [])
        )
    )
    action = next(
        action
        for action in fragment["actions"]
        if action.get("actionType") == "SPAWN"
        and action.get("routeIndex") == 3
        and action.get("key") == ENEMY_ID
    )
    spawn_seconds = float(level["waves"][0].get("preDelay", 0)) + float(
        fragment.get("preDelay", 0)
    ) + float(action.get("preDelay", 0))
    return math.ceil(spawn_seconds * FRAME_RATE)


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    level_path = OUT / "gamedata/level_main_08-01.json"
    enemy_path = OUT / "gamedata/enemy_1107_uoffcr.json"
    level = load(level_path)
    enemy = load(enemy_path)
    context = load(CONTEXT)
    route = next(
        item for item in context["exact_route_threats"]["routes"] if item["route_id"] == ROUTE_ID
    )
    enemy_row = next(
        item for item in enemy["enemies"] if item.get("Key") == ENEMY_ID
    )
    enemy_data = enemy_row["Value"][0]["enemyData"]
    speed = float(first_defined(enemy_data["attributes"], "moveSpeed"))
    spawn = spawn_frame(level)
    contact_distance = float(route["earliest_operator_contact_distance"])
    latest_distance = float(route["latest_interception_distance"])
    contact_frame = math.ceil(spawn + contact_distance / speed * FRAME_RATE)
    latest_frame = math.ceil(spawn + latest_distance / speed * FRAME_RATE)

    route_evidence = {
        "schema_version": "R8_1_ROUTE3_CONTACT_EVIDENCE_V1",
        "stage_id": STAGE_ID,
        "mechanics_version": MECHANICS_VERSION,
        "frame_rate": FRAME_RATE,
        "route_id": ROUTE_ID,
        "enemy_id": ENEMY_ID,
        "spawn_frame": spawn,
        "earliest_operator_contact_distance": contact_distance,
        "earliest_operator_contact_frame": contact_frame,
        "latest_interception_distance": latest_distance,
        "latest_safe_blocker_frame": latest_frame,
        "legal_interception_tiles": route["legal_interception_tiles"],
        "latest_interception_tile": route["latest_interception_tile"],
        "formulas": {
            "earliest_operator_contact_frame": "ceil(spawn_frame + earliest_contact_distance / move_speed * frame_rate)",
            "latest_safe_blocker_frame": "ceil(spawn_frame + latest_interception_distance / move_speed * frame_rate)",
        },
        "source_files": {
            "level": file_record(level_path),
            "enemy": file_record(enemy_path),
            "deterministic_context": file_record(CONTEXT),
        },
    }
    (OUT / "route3_contact_evidence.json").write_text(
        json.dumps(route_evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )

    audit = {
        "schema_version": "R8_1_DEADLINE_295_RECLASSIFICATION_V1",
        "stage_id": STAGE_ID,
        "mechanics_version": MECHANICS_VERSION,
        "claim_id": "ROUTE3_FIRE_ESTABLISHMENT_DEADLINE_295",
        "previous_classification": "HARD_ESTABLISHMENT_DEADLINE",
        "corrected_classification": "DERIVED_EARLIEST_OPERATOR_CONTACT_EVENT_NOT_PROVEN_ESTABLISHMENT_DEADLINE",
        "derived_contact_frame": contact_frame,
        "latest_safe_blocker_frame": latest_frame,
        "is_confirmed_hard_deadline": False,
        "reason": (
            "Frame 295 is the earliest frame at which the route-3 enemy can contact a legal interception tile. "
            "The supplied OperationalPlans do not explicitly require FIRE establishment at that instant; "
            "therefore using it as a hard establishment deadline is a compiler assumption."
        ),
        "replacement_deadline_invented": False,
        "affected_previous_conflicts": [
            "R8OP-A-MERGED-ANCHOR-REFUND-LATTICE:A03_MERGED_ANCHOR:295",
            "R8OP-B-UPSTREAM-DAM-AND-RELAY:B04_POCKET_FIRE:295",
            "R8OP-C-DELAYED-KILLING-BLOCK-EVOLUTION:C03_MERGED_ANCHOR:295",
        ],
        "evidence": route_evidence,
        "original_artifacts_preserved": True,
    }
    (OUT / "deadline_295_reclassification.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return audit


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True))
