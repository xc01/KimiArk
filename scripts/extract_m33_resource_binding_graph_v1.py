from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import UnityPy


SCHEMA_VERSION = "M33_RESOURCE_BINDING_GRAPH_V1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_scanner_module() -> Any:
    scanner_path = PROJECT_ROOT / "scripts/extract_m32_resource_index_v1.py"
    spec = importlib.util.spec_from_file_location("extract_m32_resource_index_v1", scanner_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pptr_edges(value: Any, field: str = "", *, include_internal: bool = True) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"m_FileID", "m_PathID"}.issubset(value):
            file_id = value["m_FileID"]
            path_id = value["m_PathID"]
            if include_internal or file_id != 0:
                edges.append(
                    {
                        "field": field,
                        "file_id": file_id,
                        "path_id": path_id,
                    }
                )
            return edges
        for key, child in value.items():
            edges.extend(pptr_edges(child, f"{field}.{key}" if field else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            edges.extend(pptr_edges(child, f"{field}[{index}]"))
    return edges


def deduplicate_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for edge in edges:
        key = (edge["field"], edge["file_id"], edge["path_id"])
        unique.setdefault(key, edge)
    return list(unique.values())


def external_cab(path: str) -> str | None:
    if path.startswith("archive:/"):
        return Path(path).name
    return None


def collect_string_clues(
    value: Any,
    terms: tuple[str, ...],
    field: str = "",
    *,
    max_depth: int = 32,
) -> list[dict[str, str]]:
    clues: list[dict[str, str]] = []
    if max_depth < 0:
        return clues
    if isinstance(value, str):
        if any(term in value for term in terms):
            clues.append({"field": field, "value": value})
    elif isinstance(value, dict):
        for key, child in value.items():
            child_field = f"{field}.{key}" if field else str(key)
            clues.extend(collect_string_clues(child, terms, child_field, max_depth=max_depth - 1))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_field = f"{field}[{index}]"
            clues.extend(collect_string_clues(child, terms, child_field, max_depth=max_depth - 1))
    return clues


def deduplicate_string_clues(clues: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for clue in clues:
        unique.setdefault((clue["field"], clue["value"]), clue)
    return list(unique.values())


def scan_bundle_graph(apk_path: Path, member: str) -> dict[str, Any]:
    with zipfile.ZipFile(apk_path) as archive:
        raw_bundle = archive.read(member)
    environment = UnityPy.load(raw_bundle)
    serialized_files = {
        name: value
        for name, value in getattr(environment.file, "files", {}).items()
        if type(value).__name__ == "SerializedFile"
    }
    if not serialized_files:
        raise ValueError(f"no SerializedFile in {member}")
    primary_serialized_file = next(iter(sorted(serialized_files)))

    bundle_object = next(
        (obj for obj in environment.objects if obj.type.name == "AssetBundle"), None
    )
    container_entries: list[dict[str, Any]] = []
    if bundle_object is not None:
        typetree = bundle_object.read_typetree()
        for container_path, entry in typetree.get("m_Container", []):
            container_entries.append({"container_path": container_path, "asset": entry["asset"]})

    external_paths: dict[str, dict[str, Any]] = {}
    for serialized_name, serialized_file in serialized_files.items():
        for index, external in enumerate(serialized_file.externals, 1):
            cab = external_cab(external.path)
            external_paths[str(index)] = {
                "serialized_file": serialized_name,
                "external_index": index,
                "path": external.path,
                "cab": cab,
            }

    objects: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    ownership_edges: list[dict[str, Any]] = []
    string_clues: list[dict[str, str]] = []
    type_counts: Counter[str] = Counter()
    read_errors: list[dict[str, Any]] = []
    objects_by_path_id: dict[int, Any] = {}
    for obj in environment.objects:
        objects_by_path_id[obj.path_id] = obj
    for obj in environment.objects:
        type_name = obj.type.name
        type_counts[type_name] += 1
        name = None
        typetree = None
        try:
            typetree = obj.read_typetree()
            name = typetree.get("m_Name")
        except Exception as exc:
            read_errors.append(
                {
                    "path_id": obj.path_id,
                    "type": type_name,
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
        container_paths = [
            entry["container_path"]
            for entry in container_entries
            if entry["asset"].get("m_PathID") == obj.path_id
        ]
        serialized_refs: list[dict[str, Any]] = []
        if isinstance(typetree, dict):
            for raw_edge in pptr_edges(typetree):
                target_file = (
                    primary_serialized_file
                    if raw_edge["file_id"] == 0
                    else external_paths.get(str(raw_edge["file_id"]), {}).get("cab")
                )
                serialized_refs.append(
                    {
                        "field": raw_edge["field"],
                        "source_identity": f"{primary_serialized_file}:{obj.path_id}",
                        "target_identity": (
                            f"{target_file}:{raw_edge['path_id']}"
                            if target_file
                            else f"UNRESOLVED_EXTERNAL[{raw_edge['file_id']}]:{raw_edge['path_id']}"
                        ),
                        "resolution": (
                            "RESOLVED_INTERNAL"
                            if raw_edge["file_id"] == 0
                            else ("RESOLVED_EXTERNAL" if target_file else "UNRESOLVED_EXTERNAL")
                        ),
                    }
                )
        objects.append(
            {
                "path_id": obj.path_id,
                "type": type_name,
                "name": name,
                "serialized_file": primary_serialized_file,
                "container_paths": container_paths,
                "pptr_reference_identities": serialized_refs,
                "read_error": bool(name is None and typetree is None),
            }
        )
        if type_name == "GameObject" and typetree:
            for index, component_entry in enumerate(typetree.get("m_Component", [])):
                component = component_entry.get("component", {})
                ownership_edges.append(
                    {
                        "relation": "GAMEOBJECT_HAS_COMPONENT",
                        "source_identity": f"{primary_serialized_file}:{obj.path_id}",
                        "target_identity": f"{primary_serialized_file}:{component.get('m_PathID')}",
                        "field": f"m_Component[{index}].component",
                        "resolution": "RESOLVED_INTERNAL",
                    }
                )
        elif type_name == "Component" and typetree and typetree.get("m_GameObject"):
            pass
        if typetree and isinstance(typetree, dict) and "m_GameObject" in typetree:
            game_object = typetree["m_GameObject"]
            ownership_edges.append(
                {
                    "relation": "COMPONENT_BELONGS_TO_GAMEOBJECT",
                    "source_identity": f"{primary_serialized_file}:{obj.path_id}",
                    "target_identity": f"{primary_serialized_file}:{game_object.get('m_PathID')}",
                    "field": "m_GameObject",
                    "resolution": "RESOLVED_INTERNAL",
                }
            )
        string_clues.extend(
            collect_string_clues(
                typetree,
                (
                    "enemy_1112_emppnt",
                    "projectile_enemy_emppnt",
                    "CAB-658d74aab777086fc32b93f385be999a",
                    "emppnt",
                ),
            )
        )
        if typetree is None:
            continue
        obj_edges = deduplicate_edges(pptr_edges(typetree))
        for edge in obj_edges:
            external = external_paths.get(str(edge["file_id"]))
            target_serialized_file = (
                primary_serialized_file
                if edge["file_id"] == 0
                else external.get("cab") if external else None
            )
            edge.update(
                {
                    "source_path_id": obj.path_id,
                    "source_type": type_name,
                    "source_identity": f"{primary_serialized_file}:{obj.path_id}",
                    "external_index": edge["file_id"],
                    "target_serialized_file": target_serialized_file,
                    "target_external_path": external["path"] if external else None,
                    "target_cab": external["cab"] if external else None,
                    "target_path_id": edge["path_id"],
                    "target_identity": (
                        f"{target_serialized_file}:{edge['path_id']}"
                        if target_serialized_file
                        else f"UNRESOLVED_EXTERNAL[{edge['file_id']}]:{edge['path_id']}"
                    ),
                    "resolution": (
                        "RESOLVED_INTERNAL"
                        if edge["file_id"] == 0
                        else ("RESOLVED_EXTERNAL" if external and external.get("cab") else "UNRESOLVED_EXTERNAL")
                    ),
                }
            )
            edges.append(edge)

    return {
        "apk_member": member,
        "apk_member_sha256": hashlib.sha256(raw_bundle).hexdigest(),
        "compressed_size": len(raw_bundle),
        "serialized_files": sorted(serialized_files),
        "container_count": len(container_entries),
        "container_entries": container_entries,
        "external_count": len(external_paths),
        "external_paths": external_paths,
        "object_count": len(objects),
        "object_type_counts": dict(sorted(type_counts.items())),
        "objects": objects,
        "pptr_edge_count": len(edges),
        "ownership_edge_count": len(ownership_edges),
        "ownership_edges": ownership_edges,
        "resource_string_clue_count": len(string_clues),
        "resource_string_clues": deduplicate_string_clues(string_clues),
        "pptr_edges": edges,
        "typetree_read_error_count": len(read_errors),
        "typetree_read_errors": read_errors,
    }


def load_existing_records(output: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not output.exists():
        return records
    for line_number, line in enumerate(output.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            member = record["result"]["apk_member"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid graph record at {output}:{line_number}: {exc}") from exc
        if member in records:
            raise ValueError(f"duplicate graph record for {member} in {output}")
        records[member] = record
    return records


def scan_graph_members(
    apk_path: Path,
    members: list[str],
    output_dir: Path,
    *,
    force: bool = False,
    scanner: Callable[[Path, str], dict[str, Any]] = scan_bundle_graph,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "bundle_graph.jsonl"
    unique_members: list[str] = []
    seen: set[str] = set()
    for member in members:
        if member not in seen:
            unique_members.append(member)
            seen.add(member)

    existing = {} if force else load_existing_records(output)
    requested = set(unique_members)
    completed = {
        member: record
        for member, record in existing.items()
        if record.get("status") in {"ok", "skipped"} and member in requested
    }
    pending = [member for member in unique_members if member not in completed]
    counts: Counter[str] = Counter(
        record["status"] for record in completed.values() if record["status"] in {"ok", "skipped"}
    )
    started = time.time()
    results: dict[str, dict[str, Any]] = {}
    with output.open("w", encoding="utf-8") as stream:
        for member in sorted(completed):
            stream.write(json.dumps(completed[member], ensure_ascii=False, sort_keys=True) + "\n")
        for member in pending:
            try:
                result = scanner(apk_path, member)
                record = {"status": "ok", "result": result}
                counts["ok"] += 1
                results[member] = record
            except Exception as exc:
                record = {
                    "status": "error",
                    "result": {
                        "apk_member": member,
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
                counts["error"] += 1
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()

    ok_results = [results[member]["result"] for member in sorted(results) if results[member]["status"] == "ok"]
    summary = {
        "bundle_count": counts["ok"],
        "object_count": sum(result["object_count"] for result in ok_results),
        "container_count": sum(result["container_count"] for result in ok_results),
        "external_dependency_count": sum(result["external_count"] for result in ok_results),
        "pptr_edge_count": sum(result["pptr_edge_count"] for result in ok_results),
        "ownership_edge_count": sum(result["ownership_edge_count"] for result in ok_results),
        "resource_string_clue_count": sum(result["resource_string_clue_count"] for result in ok_results),
        "typetree_read_error_count": sum(result["typetree_read_error_count"] for result in ok_results),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "output_dir": str(output_dir),
        "records_path": str(output),
        "apk_path": str(apk_path),
        "apk_sha256": hashlib.sha256(apk_path.read_bytes()).hexdigest(),
        "requested_member_count": len(unique_members),
        "requested_members": unique_members,
        "counts": dict(sorted(counts.items())),
        "summary": summary,
        "elapsed_seconds": time.time() - started,
        "resumed_completed_members": len(completed),
        "freshly_scanned_members": len(pending),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def default_members(apk_path: Path) -> list[str]:
    with zipfile.ZipFile(apk_path) as archive:
        return [
            name
            for name in archive.namelist()
            if name.startswith("assets/AB/Android/") and name.endswith((".ab", ".bin"))
        ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, default=Path("arknights-hg-2771.apk"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/m33_resource_binding_graph_v1"))
    parser.add_argument("--members", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    scanner_module = _load_scanner_module()
    scanner_module.register_decoder()
    if args.members:
        members = [line.strip() for line in args.members.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        members = default_members(args.apk)
    manifest = scan_graph_members(args.apk, members, args.output_dir, force=args.force)
    print(
        json.dumps(
            {
                "requested_member_count": manifest["requested_member_count"],
                "counts": manifest["counts"],
                "summary": manifest["summary"],
                "elapsed_seconds": manifest["elapsed_seconds"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
