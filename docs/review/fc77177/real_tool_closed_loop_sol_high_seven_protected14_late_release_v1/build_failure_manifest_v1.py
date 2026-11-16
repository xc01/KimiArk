#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    import gzip
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def main() -> None:
    manifest = {
        "schema_version": "KIMIARK_R107_FAILURE_ARTIFACT_MANIFEST_V1",
        "root": EXPERIMENT.relative_to(ROOT).as_posix(),
        "hash_algorithm": "SHA-256",
        "files": [],
    }
    excluded = {"artifact_manifest_v1.json", "candidate_ledger_v1.json.service.lock", "simulation.run.lock", "runner.lock", "simulation_budget_v1.evaluation.lock", "build_failure_manifest_v1.py"}
    for path in sorted(path for path in EXPERIMENT.rglob("*") if path.is_file() and path.name not in excluded):
        entry = {"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = restored_digest(path)
        manifest["files"].append(entry)
    (EXPERIMENT / "artifact_manifest_v1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"files": len(manifest["files"])}, sort_keys=True))


if __name__ == "__main__":
    main()
