from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M59 = ROOT / "docs/review/fc77177/m59_frozen_m58_spot_fusion_v1"
OUTPUT = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m59_frozen_m58_spot_fusion_v1"
SOURCE = OUTPUT / "attempt_01_simulation"
DIAGNOSTIC = OUTPUT / "attempt_01_simulation_diagnostic"
M58 = ROOT / "docs/review/fc77177/m58_user_premise_open_roster_v1/evidence"
EVIDENCE = M59 / "evidence/attempt_01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def copy_file(path: Path, target_name: str | None = None) -> Path:
    target = EVIDENCE / (target_name or path.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return target


def gzip_file(path: Path, target_name: str) -> Path:
    target = EVIDENCE / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    with target.open("wb") as handle:
        with gzip.GzipFile(filename=path.name, mode="wb", fileobj=handle, mtime=0) as compressed:
            compressed.write(data)
    with gzip.open(target, "rb") as handle:
        restored = handle.read()
    if hashlib.sha256(restored).hexdigest() != sha256(path):
        raise RuntimeError(f"gzip restoration mismatch: {path}")
    return target


def main() -> None:
    if EVIDENCE.exists():
        raise RuntimeError(f"M59 evidence archive already exists: {EVIDENCE}")
    EVIDENCE.mkdir(parents=True)
    records: list[dict[str, object]] = []

    source_outputs = [
        SOURCE / "llm_evidence_context.json",
        SOURCE / "llm_structured_output.json",
        SOURCE / "revision_output_schema.json",
        SOURCE / "llm_plan_validation.json",
        SOURCE / "static_compile_results.json",
        SOURCE / "static_compile_final_status.json",
        SOURCE / "simulation_gate.json",
        SOURCE / "m59_contract_validation_context.json",
        SOURCE / "final_status.json",
        SOURCE / "source_llm_structured_output.normalized.json",
        SOURCE / "source_protocol_recovery_mapping.json",
        DIAGNOSTIC / "plan_snapshot.json",
        DIAGNOSTIC / "action_snapshot.json",
        DIAGNOSTIC / "manifest.json",
        DIAGNOSTIC / "simulation_attempt.json",
        DIAGNOSTIC / "simulation_parameters.json",
        (DIAGNOSTIC / "final_status.json", "diagnostic_final_status.json"),
        M59 / "m59_simulation_budget_v1.json",
        M59 / "m59_model_authorization_v1.json",
        M59 / "frozen_source_manifest_v1.json",
        M59 / "m59_event_audit_v1.json",
        M59 / "m59_closeout_v1.json",
    ]
    for path in source_outputs:
        target_name = None
        if isinstance(path, tuple):
            path, target_name = path
        target = copy_file(path, target_name)
        records.append({
            "kind": "COPY",
            "source_path": relative(path),
            "archive_path": relative(target),
            "source_sha256": sha256(path),
            "archive_sha256": sha256(target),
            "decompressed_sha256": sha256(target),
        })

    compressed_outputs = [
        (DIAGNOSTIC / "diagnostic_events.json", "diagnostic_events.json.gz"),
        (DIAGNOSTIC / "diagnostic_summary.json", "diagnostic_summary.json.gz"),
        (M58 / "attempt_01_cli/codex_prompt.txt.gz", "m58_source_codex_prompt.txt.gz"),
        (M58 / "attempt_01_cli/codex_final_message.txt.gz", "m58_source_codex_final_message.txt.gz"),
        (M58 / "attempt_01_cli/llm_evidence_context.json.gz", "m58_source_llm_evidence_context.json.gz"),
        (M58 / "attempt_01_cli/revision_output_schema.json", "m58_source_revision_output_schema.json.gz"),
        (M58 / "attempt_01_cli/invalid_final_plan.json.parsed", "m58_source_invalid_final_plan.json.parsed.gz"),
    ]
    for path, target_name in compressed_outputs:
        target = gzip_file(path, target_name)
        records.append({
            "kind": "GZIP",
            "source_path": relative(path),
            "archive_path": relative(target),
            "source_sha256": sha256(path),
            "archive_sha256": sha256(target),
            "decompressed_sha256": sha256(path),
        })

    budget_usage = {
        "schema_version": "M59_BUDGET_USAGE_V1",
        "new_tactical_cli_calls": {"max": 0, "started": 0, "remaining": 0},
        "fixed_full_stage_simulations": {"max": 1, "started": 1, "completed": 1, "remaining": 0},
        "new_model_calls": 0,
        "tactical_modifications": 0,
        "counting_basis": "STARTED count, including failures",
    }
    usage_path = M59 / "m59_budget_usage_v1.json"
    usage_path.write_text(json.dumps(budget_usage, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    copied_usage = copy_file(usage_path)
    records.append({
        "kind": "COPY",
        "source_path": relative(usage_path),
        "archive_path": relative(copied_usage),
        "source_sha256": sha256(usage_path),
        "archive_sha256": sha256(copied_usage),
        "decompressed_sha256": sha256(copied_usage),
    })

    manifest = {
        "schema_version": "M59_EVIDENCE_ARCHIVE_MANIFEST_V1",
        "archive_directory": relative(EVIDENCE),
        "record_count": len(records),
        "records": records,
    }
    manifest_path = M59 / "m59_evidence_archive_manifest_v1.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "archive": relative(EVIDENCE),
        "manifest": relative(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "records": len(records),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
