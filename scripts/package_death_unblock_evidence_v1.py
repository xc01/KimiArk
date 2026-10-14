from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


SIMULATION_ROOT = Path("output/r8_1_r8_7_batch_v1/death_unblock_fixed_revalidation_v1")
ROADBLOCK_ROOT = Path(
    "output/r8_1_gpt_tactical_batch_v1/r8_1_c7_roadblock_targeting_replay_death_unblock_fixed_v1"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package(root: Path, package_names: tuple[str, ...], manifest_name: str) -> None:
    files: dict[str, object] = {}
    for source in sorted(root.rglob("*.json")):
        if source.name not in package_names or source.name.endswith(".gz"):
            continue
        destination = source.with_suffix(source.suffix + ".gz")
        payload = source.read_bytes()
        with destination.open("wb") as handle:
            with gzip.GzipFile(fileobj=handle, mode="wb", compresslevel=1, mtime=0) as compressed:
                compressed.write(payload)
        record = {
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
            "source_bytes": source.stat().st_size,
            "source_sha256": sha256(source),
        }
        files[str(destination)] = record
    manifest = {
        "manifest_sha256_inputs": sorted(files),
        "runtime_code_sha256": sha256(Path("src/arknights_planner/simulator/simulator.py")),
        "schema_version": "DEATH_UNBLOCK_EVIDENCE_PACKAGE_V1",
    }
    (root / manifest_name).write_text(
        json.dumps({**manifest, "files": files}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation", action="store_true")
    parser.add_argument("--roadblock", action="store_true")
    arguments = parser.parse_args()
    if arguments.simulation:
        package(SIMULATION_ROOT, ("diagnostic_events.json", "diagnostic_summary.json"), "evidence_package.json")
    if arguments.roadblock:
        package(
            ROADBLOCK_ROOT,
            (
                "a_not_ordinarily_targetable_events.json",
                "b_low_priority_no_enemy_only_events.json",
                "roadblock_targeting_replay_summary.json",
            ),
            "evidence_package.json",
        )


if __name__ == "__main__":
    main()
