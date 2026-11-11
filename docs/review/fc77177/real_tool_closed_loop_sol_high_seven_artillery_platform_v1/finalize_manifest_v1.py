#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    files = []
    excluded_names = {
        "artifact_manifest_v1.json",
        "closeout_report_v1.json.sha256",
        "candidate_ledger_v1.json.service.lock",
        "simulation.run.lock",
        "runner.lock",
    }
    for path in sorted(item for item in EXPERIMENT.rglob("*") if item.is_file() and item.name not in excluded_names and "__pycache__" not in item.parts):
        entry = {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = restored_digest(path)
        files.append(entry)
    write_json(EXPERIMENT / "artifact_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_PLATFORM_ARTIFACT_MANIFEST_V1",
        "root": EXPERIMENT.relative_to(ROOT).as_posix(),
        "hash_algorithm": "SHA-256",
        "includes_self": False,
        "self_sha256_path": "closeout_report_v1.json.sha256",
        "files": files,
    })


if __name__ == "__main__":
    main()
