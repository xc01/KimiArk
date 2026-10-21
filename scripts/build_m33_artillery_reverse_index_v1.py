from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "M33_ARTILLERY_REVERSE_INDEX_V1"
DEFAULT_TERMS = (
    "enemy_1112_emppnt",
    "projectile_enemy_emppnt",
    "CAB-658d74aab777086fc32b93f385be999a",
)
TARGET_SCRIPT_CAB = "CAB-658d74aab777086fc32b93f385be999a"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_graph_records(
    graph_paths: list[Path],
    output: Path,
    *,
    terms: tuple[str, ...] = DEFAULT_TERMS,
) -> dict[str, Any]:
    script_names: dict[str, str] = {}
    for graph_path in graph_paths:
        with graph_path.open(encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                if record.get("status") != "ok":
                    continue
                for obj in record["result"].get("objects", []):
                    if obj.get("type") == "MonoScript" and obj.get("serialized_file") and obj.get("name"):
                        script_names[f"{obj['serialized_file']}:{obj['path_id']}"] = obj["name"]

    stats = {
        "pptr_reference": 0,
        "gameobject_component": 0,
        "resource_string_clue": 0,
        "script_binding": 0,
        "container_hit": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for graph_path in graph_paths:
            with graph_path.open(encoding="utf-8") as graph_stream:
                for line in graph_stream:
                    record = json.loads(line)
                    if record.get("status") != "ok":
                        continue
                    result = record["result"]
                    common = {
                        "apk_member": result["apk_member"],
                        "apk_member_sha256": result["apk_member_sha256"],
                    }
                    for edge in result.get("pptr_edges", []):
                        row = {
                            "record_type": "PPTR_REFERENCE",
                            "source_identity": edge.get("source_identity"),
                            "field": edge.get("field"),
                            "target_identity": edge.get("target_identity"),
                            "target_cab": edge.get("target_cab"),
                            "target_path_id": edge.get("target_path_id"),
                            "resolution": edge.get("resolution"),
                            **common,
                        }
                        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                        stats["pptr_reference"] += 1
                        if edge.get("field") == "m_Script" and edge.get("source_type") == "MonoBehaviour":
                            script_name = script_names.get(edge.get("target_identity", ""))
                            binding = {
                                "record_type": "SCRIPT_BINDING",
                                "source_identity": edge.get("source_identity"),
                                "source_type": edge.get("source_type"),
                                "field": edge.get("field"),
                                "target_identity": edge.get("target_identity"),
                                "target_cab": edge.get("target_cab"),
                                "script_name": script_name,
                                "resolution": (
                                    "RESOLVED_MONOSCRIPT" if script_name else "SCRIPT_NAME_UNKNOWN"
                                ),
                                **common,
                            }
                            stream.write(json.dumps(binding, ensure_ascii=False, sort_keys=True) + "\n")
                            stats["script_binding"] += 1
                    for edge in result.get("ownership_edges", []):
                        stream.write(
                            json.dumps(
                                {
                                    "record_type": "GAMEOBJECT_COMPONENT",
                                    **edge,
                                    **common,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                            + "\n"
                        )
                        stats["gameobject_component"] += 1
                    for clue in result.get("resource_string_clues", []):
                        stream.write(
                            json.dumps(
                                {
                                    "record_type": "RESOURCE_STRING_CLUE",
                                    **clue,
                                    **common,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                            + "\n"
                        )
                        stats["resource_string_clue"] += 1
                    for entry in result.get("container_entries", []):
                        path = entry.get("container_path", "")
                        if any(term in path for term in terms):
                            asset = entry.get("asset", {})
                            file_id = asset.get("m_FileID")
                            target_identity = (
                                f"{result['serialized_files'][0]}:{asset.get('m_PathID')}"
                                if file_id == 0 and result.get("serialized_files")
                                else f"UNRESOLVED_EXTERNAL[{file_id}]:{asset.get('m_PathID')}"
                            )
                            stream.write(
                                json.dumps(
                                    {
                                        "record_type": "CONTAINER_HIT",
                                        "container_path": path,
                                        "target_identity": target_identity,
                                        **common,
                                    },
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                                + "\n"
                            )
                            stats["container_hit"] += 1
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "records_path": str(output),
        "input_graph_paths": [str(path) for path in graph_paths],
        "input_graph_sha256": {str(path): sha256(path) for path in graph_paths},
        "output_sha256": sha256(output),
        "search_terms": list(terms),
        "target_script_cab": TARGET_SCRIPT_CAB,
        "stats": stats,
    }
    output.with_suffix(output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("graphs", nargs="+", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/m33_artillery_reverse_index_v1/reverse_index.jsonl"),
    )
    args = parser.parse_args()
    manifest = normalize_graph_records(args.graphs, args.output)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
