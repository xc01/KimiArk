from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m58_user_premise_open_roster_v1/attempt_01_cli"
TARGET_DIR = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m58_user_premise_open_roster_v1/attempt_01_protocol_recovery_v1"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recursive_diff(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    pointer = path or "/"
    if isinstance(left, dict) and isinstance(right, dict):
        operations: list[dict[str, Any]] = []
        for key in sorted(set(left) - set(right)):
            operations.append({"op": "remove", "path": f"{pointer}/{key}", "value": left[key]})
        for key in sorted(set(right) - set(left)):
            operations.append({"op": "add", "path": f"{pointer}/{key}", "value": right[key]})
        for key in sorted(set(left) & set(right)):
            operations.extend(recursive_diff(left[key], right[key], f"{pointer}/{key}"))
        return operations
    if left != right:
        return [{"op": "replace", "path": pointer, "old": left, "new": right}]
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--target-dir", type=Path, default=TARGET_DIR)
    arguments = parser.parse_args()
    source = arguments.source_dir.resolve()
    target = arguments.target_dir.resolve()
    if target.exists() and any(target.iterdir()):
        raise RuntimeError(f"protocol recovery target is not empty: {target}")

    response_path = source / "codex_final_message.txt"
    original = json.loads(response_path.read_text(encoding="utf-8"))
    comparison = ((original.get("revised_stage_understanding") or {}).get("m58_open_roster_comparison") or {})
    contenders = comparison.get("contenders")
    if not isinstance(contenders, list) or len(contenders) < 3:
        raise RuntimeError("lossless recovery requires a contenders list with at least three entries")
    if "candidates" in comparison or "selected_structure_id" in comparison:
        raise RuntimeError("lossless recovery requires absent normalized fields in the original")
    contender_ids = [row.get("contender_id") for row in contenders]
    if any(not isinstance(contender_id, str) or not contender_id for contender_id in contender_ids):
        raise RuntimeError("every contender must have a non-empty contender_id")
    if len(set(contender_ids)) != len(contender_ids):
        raise RuntimeError("contender_id values must be unique")
    selected_rows = [row for row in contenders if row.get("selected") is True]
    if len(selected_rows) != 1:
        raise RuntimeError("lossless recovery requires exactly one selected contender")
    for row in contenders:
        if not isinstance(row.get("selected"), bool):
            raise RuntimeError("every contender selected field must be boolean")
    structure_id_values = [row.get("structure_id") for row in contenders]
    if all(value is not None for value in structure_id_values):
        candidate_id_source = "structure_id"
    elif all(value is None for value in structure_id_values):
        candidate_id_source = "contender_id"
    else:
        raise RuntimeError("candidate ID source must be uniformly structure_id or contender_id")
    if candidate_id_source == "contender_id":
        for row in contenders:
            if row.get("structure_id") is not None:
                raise RuntimeError("mixed candidate ID sources prevent lossless recovery")
            row["structure_id"] = row["contender_id"]
    candidate_ids = [row["structure_id"] for row in contenders]
    if any(not isinstance(candidate_id, str) or not candidate_id for candidate_id in candidate_ids):
        raise RuntimeError("every mapped candidate must have a non-empty structure_id")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise RuntimeError("mapped candidate structure_id values must be unique")
    selected_id = selected_rows[0]["structure_id"]

    normalized = copy.deepcopy(original)
    normalized_comparison = normalized["revised_stage_understanding"]["m58_open_roster_comparison"]
    normalized_comparison.pop("contenders")
    normalized_comparison["candidates"] = copy.deepcopy(contenders)
    normalized_comparison["selected_structure_id"] = selected_id

    target.mkdir(parents=True, exist_ok=True)
    for name in ("codex_prompt.txt", "revision_output_schema.json", "llm_evidence_context.json"):
        shutil.copy2(source / name, target / name)
    normalized_path = target / "llm_structured_output.normalized.json"
    normalized_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    original_plan = original["revised_operational_plans"][0]
    normalized_plan = normalized["revised_operational_plans"][0]
    original_actions = original_plan["action_timeline"]
    normalized_actions = normalized_plan["action_timeline"]
    mapping = {
        "schema_version": "M58_PROTOCOL_RECOVERY_MAPPING_V1",
        "recovery_type": "OUTER_FIELD_PROTOCOL_ONLY",
        "model_call_started": True,
        "new_model_call_for_recovery": False,
        "source_response": {
            "path": str(response_path.relative_to(ROOT)),
            "sha256": file_sha256(response_path),
        },
        "source_hashes": {
            name: file_sha256(source / name)
            for name in ("codex_prompt.txt", "revision_output_schema.json", "llm_evidence_context.json")
        },
        "source_support": {
            "contenders_path": "/revised_stage_understanding/m58_open_roster_comparison/contenders",
            "contender_count": len(contenders),
            "contender_ids": contender_ids,
            "selected_contender_path": (
                "/revised_stage_understanding/m58_open_roster_comparison/contenders/"
                + str(contender_ids.index(selected_id))
            ),
            "selected_contender_id": selected_id,
            "selected_flag_count": len(selected_rows),
            "candidate_id_source": candidate_id_source,
            "candidate_id_mapping": (
                [] if candidate_id_source == "structure_id" else [
                    {
                        "source_path": (
                            "/revised_stage_understanding/m58_open_roster_comparison/contenders/"
                            + str(index) + "/contender_id"
                        ),
                        "target_path": (
                            "/revised_stage_understanding/m58_open_roster_comparison/candidates/"
                            + str(index) + "/structure_id"
                        ),
                        "value": row["structure_id"],
                    }
                    for index, row in enumerate(contenders)
                ]
            ),
        },
        "normalized_target": {
            "path": str(normalized_path.relative_to(ROOT)),
            "sha256": file_sha256(normalized_path),
        },
        "mapping_operations": [
            {
                "op": "RENAME_EXISTING_ARRAY",
                "source_path": "/revised_stage_understanding/m58_open_roster_comparison/contenders",
                "target_path": "/revised_stage_understanding/m58_open_roster_comparison/candidates",
                "item_count": len(contenders),
            },
            {
                "op": "ADD_SCALAR_FROM_EXISTING_UNIQUE_SELECTED_CONTENDER_ID",
                "target_path": "/revised_stage_understanding/m58_open_roster_comparison/selected_structure_id",
                "source_path": (
                    "/revised_stage_understanding/m58_open_roster_comparison/contenders/"
                    + str(contender_ids.index(selected_id)) + "/contender_id"
                ),
                "value": selected_id,
            },
            *(
                []
                if candidate_id_source == "structure_id"
                else [
                    {
                        "op": "ADD_ALIAS_FROM_EXISTING_CONTENDER_ID",
                        "source_path": (
                            "/revised_stage_understanding/m58_open_roster_comparison/contenders/"
                            + str(index) + "/contender_id"
                        ),
                        "target_path": (
                            "/revised_stage_understanding/m58_open_roster_comparison/candidates/"
                            + str(index) + "/structure_id"
                        ),
                        "value": row["structure_id"],
                    }
                    for index, row in enumerate(contenders)
                ]
            ),
        ],
        "plan_invariance": {
            "plan_path": "/revised_operational_plans/0",
            "plan_canonical_sha256_original": canonical_sha256(original_plan),
            "plan_canonical_sha256_normalized": canonical_sha256(normalized_plan),
            "plan_deep_equal": original_plan == normalized_plan,
            "action_timeline_path": "/revised_operational_plans/0/action_timeline",
            "action_timeline_canonical_sha256_original": canonical_sha256(original_actions),
            "action_timeline_canonical_sha256_normalized": canonical_sha256(normalized_actions),
            "action_timeline_deep_equal": original_actions == normalized_actions,
            "action_count": len(original_actions),
        },
        "json_diff": recursive_diff(original, normalized),
        "lossless_recovery_allowed": (
            original_plan == normalized_plan
            and original_actions == normalized_actions
            and len(contender_ids) == len(set(contender_ids))
            and len(selected_rows) == 1
        ),
    }
    mapping_path = target / "protocol_recovery_mapping.json"
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not mapping["lossless_recovery_allowed"]:
        raise RuntimeError("normalized protocol recovery failed invariance checks")
    print(json.dumps({
        "normalized": str(normalized_path),
        "mapping": str(mapping_path),
        "selected_structure_id": selected_id,
        "plan_deep_equal": True,
        "action_timeline_deep_equal": True,
        "json_diff_operations": len(mapping["json_diff"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
