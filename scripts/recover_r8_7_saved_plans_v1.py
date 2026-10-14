from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from compile_r8_1_lowstar_c2_plan_v1 import compile_plan
from run_r8_1_low_star_full_tactical_closure_v1 import (
    output_schema,
    validate_operational_plan_output,
)


ROOT = Path(__file__).resolve().parents[1]
PLANS = [
    ("main_08-02", "cli", "R8_2_GPT_V1"),
    ("main_08-02", "cli_v2", "R8_2_GPT_V2"),
    ("main_08-02", "cli_v3", "R8_2_GPT_V3"),
    ("main_08-04", "cli", "R8_4_GPT_V1"),
    ("main_08-04", "cli_v2", "R8_4_GPT_V2"),
    ("main_08-07", "cli", "R8_7_GPT_V1"),
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
    }


def nested_changes(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    if before == after:
        return []
    if not isinstance(before, dict) or not isinstance(after, dict):
        return [{"path": path, "before": before, "after": after}]
    changes = []
    for key in sorted(set(before) | set(after)):
        child = f"{path}.{key}"
        if key not in before:
            changes.append({"path": child, "before": None, "after": after[key]})
        elif key not in after:
            changes.append({"path": child, "before": before[key], "after": None})
        else:
            changes.extend(nested_changes(before[key], after[key], child))
    return changes


def recover_one(stage_dir: str, source_name: str, normalized_plan_id: str, out_root: Path) -> dict[str, Any]:
    source = ROOT / "output/r8_1_r8_7_batch_v1" / stage_dir / source_name
    out = out_root / stage_dir / source_name
    if out.exists():
        raise RuntimeError(f"recovery output already exists: {out}")
    out.mkdir(parents=True)
    shutil.copy2(source / "invalid_final_plan.json.parsed", out / "invalid_final_plan.json.parsed")
    shutil.copy2(ROOT / "output/r8_1_r8_7_batch_v1" / stage_dir / "facts_v2/llm_evidence_context.json", out / "llm_evidence_context.json")
    (out / "revision_output_schema.json").write_text(
        json.dumps(output_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    original = load(out / "invalid_final_plan.json.parsed")
    normalized = copy.deepcopy(original)
    before_plan_id = normalized["revised_operational_plans"][0].get("operational_plan_id")
    normalized["revised_operational_plans"][0]["operational_plan_id"] = normalized_plan_id
    changes = nested_changes(original, normalized)
    (out / "llm_structured_output.json").write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    evidence = load(out / "llm_evidence_context.json")
    schema = output_schema()
    schema_errors = [
        f"schema: {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in sorted(Draft7Validator(schema).iter_errors(normalized), key=lambda item: list(item.path))
    ]
    contract_errors = validate_operational_plan_output(normalized, evidence)
    plan_contract = [
        (item.get("action_type"), item.get("frame"), item.get("operator_id"), item.get("tile"), item.get("direction"))
        for item in normalized["revised_operational_plans"][0]["action_timeline"]
    ]
    record = {
        "schema_version": "R8_1_R8_7_SAVED_PLAN_RECOVERY_V1",
        "stage_id": f"main_08-{stage_dir.removeprefix('main_08-')}",
        "source_dir": source.relative_to(ROOT).as_posix(),
        "source_plan_file": file_record(source / "invalid_final_plan.json.parsed"),
        "source_operational_plan_id": before_plan_id,
        "normalized_operational_plan_id": normalized_plan_id,
        "normalization_allowed": ["operational_plan_id"],
        "tactical_action_normalization": "NONE",
        "plan_action_contract": plan_contract,
        "changes": changes,
        "source_sha256": sha256(source / "invalid_final_plan.json.parsed"),
        "normalized_sha256": sha256(out / "llm_structured_output.json"),
        "evidence": file_record(out / "llm_evidence_context.json"),
        "schema_validation_errors": schema_errors,
        "contract_validation_errors": contract_errors,
    }
    (out / "normalization_record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if schema_errors or contract_errors:
        (out / "recovery_final_status.json").write_text(
            json.dumps({"status": "RECOVERY_VALIDATION_FAILED", **record}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {**record, "status": "RECOVERY_VALIDATION_FAILED"}
    static = compile_plan(out)
    final = {
        "schema_version": "R8_1_R8_7_SAVED_PLAN_RECOVERY_V1",
        "status": "RECOVERED_AND_STATIC_CHECKED",
        **record,
        "static_classification": static["classification"],
        "static_conflict_count": len(static["conflicts"]),
        "static_unknown_count": len(static["unknowns"]),
        "static_conflicts": static["conflicts"],
        "static_unknowns": static["unknowns"],
    }
    (out / "recovery_final_status.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="output/r8_1_r8_7_batch_v1/recovery_v1")
    arguments = parser.parse_args()
    results = [
        recover_one(stage, source, plan_id, ROOT / arguments.out)
        for stage, source, plan_id in PLANS
    ]
    summary = {
        "schema_version": "R8_1_R8_7_SAVED_PLAN_RECOVERY_V1_SUMMARY",
        "recovered_count": sum(item["status"] == "RECOVERED_AND_STATIC_CHECKED" for item in results),
        "failed_count": sum(item["status"] != "RECOVERED_AND_STATIC_CHECKED" for item in results),
        "results": results,
    }
    out = ROOT / arguments.out
    (out / "recovery_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: summary[key] for key in ("schema_version", "recovered_count", "failed_count")}, sort_keys=True))


if __name__ == "__main__":
    main()
