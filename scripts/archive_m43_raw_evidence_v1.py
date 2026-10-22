from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m43_joint_responsibility_closure_v1"
TARGET_ROOT = ROOT / "docs/review/fc77177/m43_joint_responsibility_closure_v1/evidence"

CLI_FILES = [
    "codex_prompt.txt",
    "codex_final_message.txt",
    "final_status.json",
    "llm_plan_validation.json",
    "llm_structured_output.json",
    "static_compile_results.json",
    "cli_process_attempt.json",
    "cli_process_result.json",
    "codex_command.json",
    "codex_exec.jsonl",
    "codex_stderr.txt",
    "codex_trajectory_summary.json",
    "frozen_action_snapshot_v3.json",
]

SIMULATION_FILES = [
    "action_snapshot.json",
    "diagnostic_events.json",
    "diagnostic_summary.json",
    "manifest.json",
    "plan_snapshot.json",
    "simulation_attempt.json",
    "simulation_parameters.json",
    "final_status.json",
]

COMPRESSED_SUFFIXES = {".jsonl", ".txt"}
LARGE_JSON_BYTES = 64 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_gzip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_handle, gzip.GzipFile(
        filename="", mode="wb", fileobj=target.open("wb"), mtime=0, compresslevel=9
    ) as output_handle:
        shutil.copyfileobj(input_handle, output_handle)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def copy_evidence(source: Path, target: Path) -> dict[str, object]:
    if not source.is_file():
        return {"status": "MISSING", "source": relative(source)}
    target.parent.mkdir(parents=True, exist_ok=True)
    should_compress = (
        source.suffix in COMPRESSED_SUFFIXES
        or (source.suffix == ".json" and source.stat().st_size >= LARGE_JSON_BYTES)
    )
    if should_compress:
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
    cli_sources = {1: SOURCE_ROOT, 2: SOURCE_ROOT / "attempt_02_cli", 3: SOURCE_ROOT / "attempt_03_cli"}
    for attempt_number, cli_dir in cli_sources.items():
        for name in CLI_FILES:
            record = copy_evidence(cli_dir / name, TARGET_ROOT / f"attempt_{attempt_number:02d}_cli/{name}")
            if attempt_number == 2 and name in {"llm_structured_output.json", "static_compile_results.json", "frozen_action_snapshot_v3.json"}:
                record["archive_note"] = "NOT_PRODUCED_CONTRACT_BLOCKED_V2"
            if attempt_number == 1 and name == "frozen_action_snapshot_v3.json":
                record["archive_note"] = "NOT_PRODUCED_STATIC_BLOCKED_V1"
            records.append(record)
        if attempt_number != 3:
            for name in SIMULATION_FILES:
                record = copy_evidence(SOURCE_ROOT / f"attempt_{attempt_number:02d}_diagnostic/{name}", TARGET_ROOT / f"attempt_{attempt_number:02d}_diagnostic/{name}")
                record["archive_note"] = "NO_SIMULATED_CANDIDATE"
                records.append(record)
    for name in SIMULATION_FILES:
        records.append(copy_evidence(SOURCE_ROOT / "attempt_03_diagnostic" / name, TARGET_ROOT / "attempt_03_diagnostic" / name))

    index = {
        "schema_version": "M43_RAW_EVIDENCE_ARCHIVE_INDEX_V1",
        "source_root": relative(SOURCE_ROOT),
        "archive_root": relative(TARGET_ROOT),
        "policy": {
            "credentials_excluded": True,
            "gzip_jsonl": True,
            "gzip_large_json_bytes": LARGE_JSON_BYTES,
            "gzip_text_prompt_and_final_message": True,
            "missing_materials_marked": True,
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
