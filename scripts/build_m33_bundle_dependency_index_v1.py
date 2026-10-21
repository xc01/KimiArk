from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import UnityPy

SCHEMA_VERSION = "M33_BUNDLE_DEPENDENCY_INDEX_V1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEARCH_TERMS = ("enemy_1112_emppnt", "projectile_enemy_emppnt", "emppnt")


def _load_decoder_module() -> Any:
    path = PROJECT_ROOT / "scripts/extract_m32_resource_index_v1.py"
    spec = importlib.util.spec_from_file_location("extract_m32_resource_index_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scan_dependencies(apk_path: Path, member: str) -> dict[str, Any]:
    with zipfile.ZipFile(apk_path) as archive:
        raw = archive.read(member)
    environment = UnityPy.load(raw)
    serialized_files = sorted(
        name
        for name, value in getattr(environment.file, "files", {}).items()
        if type(value).__name__ == "SerializedFile"
    )
    if not serialized_files:
        raise ValueError(f"no SerializedFile in {member}")
    externals: list[dict[str, Any]] = []
    for serialized_name in serialized_files:
        serialized_file = environment.file.files[serialized_name]
        for index, external in enumerate(serialized_file.externals, 1):
            path = external.path
            cab = Path(path).name if path.startswith("archive:/") else None
            externals.append(
                {
                    "serialized_file": serialized_name,
                    "external_index": index,
                    "path": path,
                    "cab": cab,
                }
            )
    bundle_object = next((obj for obj in environment.objects if obj.type.name == "AssetBundle"), None)
    container_matches: list[str] = []
    if bundle_object is not None:
        typetree = bundle_object.read_typetree()
        for container_path, _entry in typetree.get("m_Container", []):
            if any(term in container_path for term in SEARCH_TERMS):
                container_matches.append(container_path)
    return {
        "apk_member": member,
        "apk_member_sha256": hashlib.sha256(raw).hexdigest(),
        "serialized_files": serialized_files,
        "external_dependencies": externals,
        "matched_container_paths": container_matches,
    }


def load_existing_records(output: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not output.exists():
        return records
    for line_number, line in enumerate(output.open(encoding="utf-8"), 1):
        try:
            record = json.loads(line)
            member = record["result"]["apk_member"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid dependency record at {output}:{line_number}: {exc}") from exc
        if member in records:
            raise ValueError(f"duplicate dependency record for {member}")
        records[member] = record
    return records


def scan_members(
    apk_path: Path,
    members: list[str],
    output: Path,
    *,
    force: bool = False,
    scanner=scan_dependencies,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    unique: list[str] = []
    seen: set[str] = set()
    for member in members:
        if member not in seen:
            unique.append(member)
            seen.add(member)
    requested = set(unique)
    existing = {} if force else load_existing_records(output)
    kept = {
        member: record
        for member, record in existing.items()
        if record.get("status") in {"ok", "skipped"} and member in requested
    }
    pending = [member for member in unique if member not in kept]
    counts: Counter[str] = Counter(record.get("status", "") for record in kept.values())
    started = time.time()
    with output.open("w", encoding="utf-8") as stream:
        for member in sorted(kept):
            stream.write(json.dumps(kept[member], ensure_ascii=False, sort_keys=True) + "\n")
        for member in pending:
            try:
                record = {"status": "ok", "result": scanner(apk_path, member)}
            except Exception as exc:
                record = {
                    "status": "error",
                    "result": {
                        "apk_member": member,
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            if record["status"] in {"ok", "skipped"}:
                kept[member] = record
            counts[record["status"]] += 1
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
    matched_bundles = []
    external_cab_hits: dict[str, list[str]] = {}
    for member in sorted(kept):
        if kept[member]["status"] != "ok":
            continue
        result = kept[member]["result"]
        if result["matched_container_paths"]:
            matched_bundles.append(member)
        for dependency in result["external_dependencies"]:
            cab = dependency["cab"]
            if cab:
                external_cab_hits.setdefault(cab, []).append(member)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "records_path": str(output),
        "apk_path": str(apk_path),
        "apk_sha256": hashlib.sha256(apk_path.read_bytes()).hexdigest(),
        "search_terms": list(SEARCH_TERMS),
        "requested_member_count": len(unique),
        "requested_members": unique,
        "counts": dict(sorted(counts.items())),
        "matched_container_bundle_count": len(matched_bundles),
        "matched_container_bundles": matched_bundles,
        "projectile_cab_external_referencing_bundle_count": len(
            external_cab_hits.get("CAB-34af01ecb5d2ad63aca01b6e0d71279d", [])
        ),
        "elapsed_seconds": time.time() - started,
        "resumed_completed_members": len(kept),
        "freshly_scanned_members": len(pending),
    }
    output.with_suffix(output.suffix + ".manifest.json").write_text(
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
    parser.add_argument("--output", type=Path, default=Path("output/m33_bundle_dependency_index_v1/bundle_dependencies.jsonl"))
    parser.add_argument("--members", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    decoder = _load_decoder_module()
    decoder.register_decoder()
    members = (
        [line.strip() for line in args.members.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.members
        else default_members(args.apk)
    )
    manifest = scan_members(args.apk, members, args.output, force=args.force)
    print(
        json.dumps(
            {
                "requested_member_count": manifest["requested_member_count"],
                "counts": manifest["counts"],
                "matched_container_bundle_count": manifest["matched_container_bundle_count"],
                "projectile_cab_external_referencing_bundle_count": manifest[
                    "projectile_cab_external_referencing_bundle_count"
                ],
                "elapsed_seconds": manifest["elapsed_seconds"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
