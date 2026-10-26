from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "docs/review/fc77177/m58_user_premise_open_roster_v1/evidence"
OUTPUT_DIR = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m59_frozen_m58_spot_fusion_v1/attempt_01_simulation"
M59_DIR = ROOT / "docs/review/fc77177/m59_frozen_m58_spot_fusion_v1"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_gzip(path: Path) -> bytes:
    with gzip.open(path, "rb") as handle:
        return handle.read()


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
    cli_dir = SOURCE_DIR / "attempt_01_cli"
    recovery_dir = SOURCE_DIR / "protocol_recovery_v3"
    output_dir = OUTPUT_DIR
    original_text = load_gzip(cli_dir / "codex_final_message.txt.gz")
    prompt_text = load_gzip(cli_dir / "codex_prompt.txt.gz")
    evidence_text = load_gzip(cli_dir / "llm_evidence_context.json.gz")
    original = json.loads(original_text)
    normalized = json.loads((recovery_dir / "llm_structured_output.normalized.json").read_text(encoding="utf-8"))
    mapping = json.loads((recovery_dir / "protocol_recovery_mapping.json").read_text(encoding="utf-8"))
    active = json.loads((output_dir / "llm_structured_output.json").read_text(encoding="utf-8"))
    invalid_parsed = json.loads((output_dir / "source_invalid_final_plan.json.parsed").read_text(encoding="utf-8"))
    active_evidence = json.loads((output_dir / "llm_evidence_context.json").read_text(encoding="utf-8"))
    active_schema = json.loads((output_dir / "revision_output_schema.json").read_text(encoding="utf-8"))
    source_schema = json.loads((recovery_dir.parent / "attempt_01_cli/revision_output_schema.json").read_text(encoding="utf-8"))

    comparison_original = original["revised_stage_understanding"]["m58_open_roster_comparison"]
    comparison_normalized = normalized["revised_stage_understanding"]["m58_open_roster_comparison"]
    contenders = comparison_original["contenders"]
    candidates = comparison_normalized["candidates"]
    aliases = [
        {
            "source_path": f"/revised_stage_understanding/m58_open_roster_comparison/contenders/{index}/contender_id",
            "target_path": f"/revised_stage_understanding/m58_open_roster_comparison/candidates/{index}/structure_id",
            "source_value": row.get("contender_id"),
            "target_value": candidates[index].get("structure_id"),
        }
        for index, row in enumerate(contenders)
    ]
    candidates_without_alias = [{key: value for key, value in row.items() if key != "structure_id"} for row in candidates]
    alias_equality = [
        item["source_value"] == item["target_value"] and isinstance(item["target_value"], str) and bool(item["target_value"])
        for item in aliases
    ]
    stripped_equality = [left == right for left, right in zip(contenders, candidates_without_alias)]
    selected_rows = [row for row in contenders if row.get("selected") is True]
    selected_structure_id = comparison_normalized.get("selected_structure_id")
    actual_json_diff = recursive_diff(original, normalized)
    expected_json_diff_operations = [
        "//revised_stage_understanding/m58_open_roster_comparison/contenders",
        "//revised_stage_understanding/m58_open_roster_comparison/candidates",
        "//revised_stage_understanding/m58_open_roster_comparison/selected_structure_id",
    ]

    original_plan = original["revised_operational_plans"][0]
    normalized_plan = normalized["revised_operational_plans"][0]
    original_actions = original_plan["action_timeline"]
    normalized_actions = normalized_plan["action_timeline"]
    plan_ids = [row.get("contender_id") for row in contenders]
    selected_union = set(original_plan.get("selected_low_star_operator_ids") or [])
    selected_union.update(
        action.get("operator_id")
        for action in original_actions
        if action.get("action_type") == "DEPLOY"
    )
    plan_invariance = {
        "plan_path": "/revised_operational_plans/0",
        "plan_deep_equal": original_plan == normalized_plan,
        "plan_canonical_sha256_original": canonical_sha256(original_plan),
        "plan_canonical_sha256_normalized": canonical_sha256(normalized_plan),
        "action_timeline_path": "/revised_operational_plans/0/action_timeline",
        "action_timeline_deep_equal": original_actions == normalized_actions,
        "action_timeline_canonical_sha256_original": canonical_sha256(original_actions),
        "action_timeline_canonical_sha256_normalized": canonical_sha256(normalized_actions),
        "action_count": len(original_actions),
    }
    source_file_hashes = {
        "codex_prompt.txt": file_sha256(cli_dir / "codex_prompt.txt.gz") and hashlib.sha256(prompt_text).hexdigest(),
        "codex_final_message.txt": file_sha256(cli_dir / "codex_final_message.txt.gz") and hashlib.sha256(original_text).hexdigest(),
        "llm_evidence_context.json": file_sha256(cli_dir / "llm_evidence_context.json.gz") and hashlib.sha256(evidence_text).hexdigest(),
        "revision_output_schema.json": file_sha256(cli_dir / "revision_output_schema.json"),
        "invalid_final_plan.json.parsed": file_sha256(output_dir / "source_invalid_final_plan.json.parsed"),
        "llm_structured_output.normalized.json": file_sha256(output_dir / "source_llm_structured_output.normalized.json"),
        "protocol_recovery_mapping.json": file_sha256(recovery_dir / "protocol_recovery_mapping.json"),
        "llm_plan_validation.normalized.json": file_sha256(recovery_dir / "llm_plan_validation.normalized.json"),
        "static_compile_results.normalized.json": file_sha256(recovery_dir / "static_compile_results.normalized.json"),
    }
    active_file_hashes = {
        "llm_evidence_context.json": file_sha256(output_dir / "llm_evidence_context.json"),
        "llm_structured_output.json": file_sha256(output_dir / "llm_structured_output.json"),
        "revision_output_schema.json": file_sha256(output_dir / "revision_output_schema.json"),
    }
    checks = {
        "original_response_deep_equal_invalid_parsed": original == invalid_parsed,
        "normalized_deep_equal_active_structured_output": normalized == active,
        "normalized_evidence_deep_equal_active_evidence": json.loads(evidence_text) == active_evidence,
        "source_schema_deep_equal_active_schema": source_schema == active_schema,
        "contender_count_is_three": len(contenders) == 3,
        "contender_ids_unique": len(plan_ids) == len(set(plan_ids)) and all(plan_ids),
        "exactly_one_selected_contender": len(selected_rows) == 1,
        "candidate_alias_count_matches": len(aliases) == len(contenders) == len(candidates),
        "every_alias_from_existing_contender_id": all(alias_equality),
        "every_candidate_deep_equal_after_stripping_alias": all(stripped_equality),
        "selected_structure_id_maps_unique_selected_contender": (
            selected_structure_id == selected_rows[0].get("contender_id") if len(selected_rows) == 1 else False
        ),
        "actual_json_diff_matches_outer_protocol_shape": [
            item["path"] for item in actual_json_diff
        ] == expected_json_diff_operations,
        "mapping_lossless_recovery_allowed": mapping.get("lossless_recovery_allowed") is True,
        "mapping_recovery_type_outer_protocol_only": mapping.get("recovery_type") == "OUTER_FIELD_PROTOCOL_ONLY",
        "mapping_no_new_model_call": mapping.get("new_model_call_for_recovery") is False,
        "plan_action_invariance": plan_invariance,
        "selected_deploy_union_count_is_eight": len(selected_union) == 8,
        "selected_plan_id": original_plan.get("operational_plan_id"),
        "selected_parent_hypothesis_id": original_plan.get("parent_hypothesis_id"),
        "contender_ids": plan_ids,
        "selected_structure_id": selected_structure_id,
        "selected_operator_union": sorted(selected_union),
        "source_file_sha256": source_file_hashes,
        "active_file_sha256": active_file_hashes,
        "candidate_id_alias_mapping": aliases,
        "actual_json_diff_operation_count": len(actual_json_diff),
    }
    required_true = {
        key: value
        for key, value in checks.items()
        if isinstance(value, bool)
    }
    required_true["plan_action_invariance"] = (
        plan_invariance["plan_deep_equal"]
        and plan_invariance["action_timeline_deep_equal"]
        and plan_invariance["plan_canonical_sha256_original"] == plan_invariance["plan_canonical_sha256_normalized"]
        and plan_invariance["action_timeline_canonical_sha256_original"] == plan_invariance["action_timeline_canonical_sha256_normalized"]
    )
    checks["passed"] = all(required_true.values())
    manifest = {
        "schema_version": "M59_FROZEN_SOURCE_AUDIT_V1",
        "source_directory": str(SOURCE_DIR.relative_to(ROOT)),
        "output_directory": str(OUTPUT_DIR.relative_to(ROOT)),
        "checks": checks,
    }
    target = M59_DIR / "frozen_source_manifest_v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not checks["passed"]:
        failed = {key: value for key, value in required_true.items() if value is not True}
        raise RuntimeError(f"M59 frozen source audit failed: {failed}")
    print(json.dumps({
        "manifest": str(target.relative_to(ROOT)),
        "plan_sha256": plan_invariance["plan_canonical_sha256_normalized"],
        "action_timeline_sha256": plan_invariance["action_timeline_canonical_sha256_normalized"],
        "action_count": plan_invariance["action_count"],
        "selected_structure_id": selected_structure_id,
        "selected_operator_union_count": len(selected_union),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
