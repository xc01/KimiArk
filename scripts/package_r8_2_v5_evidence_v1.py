from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path("output/r8_1_r8_7_batch_v1/main_08-02/clearance_diagnostic_v5_attempt3")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files = {}
    for compressed_name, raw_name in (
        ("diagnostic_events.json.gz", "diagnostic_events.json"),
        ("diagnostic_summary.json.gz", "diagnostic_summary.json"),
    ):
        compressed, raw = ROOT / compressed_name, ROOT / raw_name
        files[compressed_name] = {
            "bytes": compressed.stat().st_size,
            "sha256": sha256(compressed),
            "source": {"bytes": raw.stat().st_size, "sha256": sha256(raw)},
        }
    payload = {
        "schema_version": "R8_2_V5_EVIDENCE_HASHES_V1",
        "runtime_code_sha256": sha256(Path("src/arknights_planner/simulator/simulator.py")),
        "session_runner_sha256": sha256(Path("scripts/run_gpt_tactical_stage_session_v1.py")),
        "files": files,
    }
    (ROOT / "evidence_hashes.json").write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
