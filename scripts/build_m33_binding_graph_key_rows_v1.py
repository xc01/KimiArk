from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "M33_ARTILLERY_BINDING_KEY_ROWS_V1"
PROJECTILE_MEMBER = "assets/AB/Android/battle/prefabs/[uc]projectiles.ab"
PROJECTILE_CAB = "CAB-34af01ecb5d2ad63aca01b6e0d71279d"
PROJECTILE_PATH_ID = -619213101382661339
EXPECTED_SCRIPTS = {
    "SimpleProjectile",
    "EffectBehaviour",
    "HitBehaviour",
    "AttachToTarget",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc


def extract_key_rows(source_graph: Path, reverse_index: Path) -> dict[str, Any]:
    projectile_root: dict[str, Any] | None = None
    for record in _jsonl(source_graph):
        result = record.get("result", {})
        if result.get("apk_member") != PROJECTILE_MEMBER:
            continue
        for obj in result.get("objects", []):
            if obj.get("path_id") == PROJECTILE_PATH_ID and obj.get("type") == "GameObject":
                projectile_root = {
                    "identity": f"{PROJECTILE_CAB}:{PROJECTILE_PATH_ID}",
                    "name": obj.get("name"),
                    "type": obj.get("type"),
                    "serialized_file": obj.get("serialized_file"),
                    "container_paths": obj.get("container_paths", []),
                    "component_references": obj.get("pptr_reference_identities", []),
                }
                break
        if projectile_root is not None:
            break
    if projectile_root is None:
        raise ValueError(f"projectile root not found in {source_graph}")

    expected_component_ids = {
        ref["target_identity"].rsplit(":", 1)[1]
        for ref in projectile_root["component_references"]
    }
    script_bindings: list[dict[str, Any]] = []
    external_references: list[dict[str, Any]] = []
    seen_scripts: set[str] = set()
    for row in _jsonl(reverse_index):
        if row.get("apk_member") != PROJECTILE_MEMBER:
            continue
        if row.get("record_type") == "SCRIPT_BINDING":
            script_name = row.get("script_name")
            source_path_id = str(row.get("source_identity", "")).rsplit(":", 1)[-1]
            if (
                script_name in EXPECTED_SCRIPTS
                and source_path_id in expected_component_ids
                and script_name not in seen_scripts
            ):
                script_bindings.append(row)
                seen_scripts.add(script_name)
        if (
            row.get("record_type") == "PPTR_REFERENCE"
            and row.get("resolution") == "RESOLVED_EXTERNAL"
            and row.get("target_cab") == PROJECTILE_CAB
        ):
            external_references.append(row)

    missing_scripts = sorted(EXPECTED_SCRIPTS - seen_scripts)
    if missing_scripts:
        raise ValueError(f"missing expected script bindings: {missing_scripts}")

    return {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "source_graph": str(source_graph),
            "source_graph_sha256": _sha256(source_graph),
            "reverse_index": str(reverse_index),
            "reverse_index_sha256": _sha256(reverse_index),
        },
        "projectile_root": projectile_root,
        "selected_script_bindings": script_bindings,
        "external_references_to_projectile_cab": external_references,
        "interpretation": {
            "external_pptr_reference_count": len(external_references),
            "meaning": "NO_DIRECT_SERIALIZED_REFERENCE_AMONG_INDEXED_BUNDLES; dynamic binding remains UNKNOWN",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-graph",
        type=Path,
        default=Path("output/m33_artillery_reverse_source_graph_v1/bundle_graph.jsonl"),
    )
    parser.add_argument(
        "--reverse-index",
        type=Path,
        default=Path("output/m33_artillery_reverse_index_v1/reverse_index.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/review/fc77177/m33_artillery_binding_v1/binding_graph_key_rows.json"),
    )
    args = parser.parse_args()
    evidence = extract_key_rows(args.source_graph, args.reverse_index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "external_references": len(evidence["external_references_to_projectile_cab"])}, sort_keys=True))


if __name__ == "__main__":
    main()
