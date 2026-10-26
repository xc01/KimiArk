from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M60 = ROOT / "docs/review/fc77177/m60_m59_feedback_revision_v1"
OUTPUT = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m60_m59_feedback_revision_v1"
CLI = OUTPUT / "attempt_01_cli"
EVIDENCE = M60 / "evidence/attempt_01_cli"


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
    with target.open("wb") as raw:
        with gzip.GzipFile(filename=path.name, mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(data)
    with gzip.open(target, "rb") as handle:
        restored = handle.read()
    if hashlib.sha256(restored).hexdigest() != sha256(path):
        raise RuntimeError(f"gzip restoration mismatch: {path}")
    return target


def main() -> None:
    if EVIDENCE.exists():
        raise RuntimeError(f"M60 evidence archive already exists: {EVIDENCE}")
    EVIDENCE.mkdir(parents=True)
    records: list[dict[str, object]] = []

    copies = [
        (CLI / "cli_process_attempt.json", None),
        (CLI / "cli_process_result.json", None),
        (CLI / "codex_command.json", None),
        (CLI / "codex_stderr.txt", None),
        (CLI / "final_status.json", None),
        (CLI / "llm_plan_validation.json", None),
        (CLI / "budget_usage.json", "pre_cli_budget_usage.json"),
        (CLI / "evidence_completeness.json", None),
        (CLI / "milestone_constraints_resolution.json", None),
        (CLI / "run.lock", None),
        (M60 / "m60_model_authorization_v1.json", None),
        (M60 / "m60_simulation_budget_v1.json", None),
        (M60 / "m60_tactical_feedback_v1.json", None),
        (M60 / "m60_budget_usage_v1.json", None),
        (M60 / "m60_closeout_v1.json", None),
    ]
    for path, target_name in copies:
        target = copy_file(path, target_name)
        records.append({
            "kind": "COPY",
            "source_path": relative(path),
            "archive_path": relative(target),
            "source_sha256": sha256(path),
            "archive_sha256": sha256(target),
            "decompressed_sha256": sha256(target),
        })

    gzips = [
        (CLI / "codex_prompt.txt", "codex_prompt.txt.gz"),
        (CLI / "codex_final_message.txt", "codex_final_message.txt.gz"),
        (CLI / "revision_output_schema.json", "revision_output_schema.json.gz"),
        (CLI / "llm_evidence_context.json", "llm_evidence_context.json.gz"),
        (OUTPUT / "facts/llm_evidence_context.json", "facts_llm_evidence_context.json.gz"),
        (CLI / "invalid_final_plan.json.parsed", "invalid_final_plan.json.parsed.gz"),
        (CLI / "codex_exec.jsonl", "codex_exec.jsonl.gz"),
        (CLI / "codex_trajectory_summary.json", "codex_trajectory_summary.json.gz"),
    ]
    for path, target_name in gzips:
        target = gzip_file(path, target_name)
        records.append({
            "kind": "GZIP",
            "source_path": relative(path),
            "archive_path": relative(target),
            "source_sha256": sha256(path),
            "archive_sha256": sha256(target),
            "decompressed_sha256": sha256(path),
        })

    manifest = {
        "schema_version": "M60_EVIDENCE_ARCHIVE_MANIFEST_V1",
        "archive_directory": relative(EVIDENCE),
        "record_count": len(records),
        "records": records,
    }
    manifest_path = M60 / "m60_evidence_archive_manifest_v1.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "archive": relative(EVIDENCE),
        "manifest": relative(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "records": len(records),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
