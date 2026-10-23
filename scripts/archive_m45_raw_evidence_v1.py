from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m45_joint_artillery_continuity_v1"
TARGET_ROOT = ROOT / "docs/review/fc77177/m45_joint_artillery_continuity_v1/evidence"

PLAN_FILES = [
    "budget_usage.json",
    "cli_process_attempt.json",
    "cli_process_result.json",
    "codex_command.json",
    "codex_exec.jsonl",
    "codex_final_message.txt",
    "codex_prompt.txt",
    "codex_stderr.txt",
    "codex_trajectory_summary.json",
    "evidence_completeness.json",
    "final_status.json",
    "llm_evidence_context.json",
    "llm_plan_validation.json",
    "llm_structured_output.json",
    "proxy_prestart.json",
    "revision_hypothesis_evaluation.json",
    "revision_output_schema.json",
    "run.lock",
    "simulation_gate.json",
    "static_compile_final_status.json",
    "static_compile_results.json",
]

SIMULATION_FILES = [
    "action_snapshot.json",
    "diagnostic_events.json",
    "diagnostic_summary.json",
    "final_status.json",
    "manifest.json",
    "plan_snapshot.json",
    "simulation_attempt.json",
    "simulation_parameters.json",
]

LARGE_JSON_BYTES = 64 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_gzip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as source_handle, gzip.GzipFile(
        filename="", mode="wb", fileobj=target.open("wb"), mtime=0, compresslevel=9
    ) as target_handle:
        shutil.copyfileobj(source_handle, target_handle)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def copy_evidence(source: Path, target: Path) -> dict[str, object]:
    if not source.is_file():
        return {"status": "MISSING", "source": relative(source)}
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix == ".json" and source.stat().st_size >= LARGE_JSON_BYTES:
        archive = target.with_suffix(target.suffix + ".gz")
        write_gzip(source, archive)
        return {
            "status": "ARCHIVED",
            "source": relative(source), "stored": relative(archive),
            "raw_sha256": sha256(source), "raw_bytes": source.stat().st_size,
            "compressed_sha256": sha256(archive), "compressed_bytes": archive.stat().st_size,
            "compression": "gzip",
        }
    shutil.copyfile(source, target)
    return {
        "status": "ARCHIVED_UNCOMPRESSED",
        "source": relative(source), "stored": relative(target),
        "raw_sha256": sha256(source), "raw_bytes": source.stat().st_size,
        "compressed_sha256": sha256(target), "compressed_bytes": target.stat().st_size,
        "compression": "NONE",
    }


def main() -> None:
    records: list[dict[str, object]] = []
    for attempt_number in range(1, 4):
        attempt = f"attempt_{attempt_number:02d}"
        for name in PLAN_FILES:
            records.append(copy_evidence(SOURCE_ROOT / f"{attempt}_cli/{name}", TARGET_ROOT / f"{attempt}_cli/{name}"))
        for name in SIMULATION_FILES:
            records.append(copy_evidence(SOURCE_ROOT / f"{attempt}_diagnostic/{name}", TARGET_ROOT / f"{attempt}_diagnostic/{name}"))
    for name in (
        "m45_model_authorization_v1.json",
        "m45_simulation_budget_v1.json",
        "m45_joint_failure_feedback_v1.json",
        "m45_v2_tactical_feedback_v1.json",
        "m45_v3_tactical_feedback_v1.json",
        "m45_budget_reconciliation_v1.json",
        "m45_tactical_report_v1.md",
    ):
        records.append(copy_evidence(ROOT / "docs/review/fc77177/m45_joint_artillery_continuity_v1" / name, TARGET_ROOT / name))

    index = {
        "schema_version": "M45_RAW_EVIDENCE_ARCHIVE_INDEX_V1",
        "source_root": relative(SOURCE_ROOT),
        "archive_root": relative(TARGET_ROOT),
        "policy": {
            "credentials_excluded": True,
            "gzip_large_json_bytes": LARGE_JSON_BYTES,
            "missing_materials_marked": True,
            "timeout_attempt_not_resumed": True,
        },
        "entries": records,
        "counts": {
            "total_expected": len(records),
            "archived": sum(record["status"] != "MISSING" for record in records),
            "missing": sum(record["status"] == "MISSING" for record in records),
        },
    }
    index_path = TARGET_ROOT / "archive_index_v1.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(index["counts"], sort_keys=True))
    print(relative(index_path))


if __name__ == "__main__":
    main()
