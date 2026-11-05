#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_coupled_contact_v1"
OUTPUT = EXPERIMENT / "artifact_manifest_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files = []
    for path in sorted(EXPERIMENT.rglob("*")):
        if not path.is_file() or path == OUTPUT or "__pycache__" in path.parts:
            continue
        entry = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        if path.name.endswith(".gz"):
            entry["restored_sha256"] = hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()
        files.append(entry)
    payload = {
        "schema_version": "KIMIARK_COUPLED_CONTACT_FAILURE_ARTIFACT_MANIFEST_V1",
        "files": files,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
