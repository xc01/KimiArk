from __future__ import annotations

import argparse
import hashlib
import json
import time
import zipfile
from pathlib import Path

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper


KEYWORDS = (
    "enemy_1112_emppnt",
    "emppnt",
    "1112",
    "coldattack",
    "cold_attack",
    "artillery",
    "projectile",
)


def decompress_lz4ak(data: bytes, uncompressed_size: int) -> bytes:
    mutable = bytearray(data)
    input_size = len(mutable)
    input_pos = 0
    output_pos = 0

    def extended_length(start: int) -> tuple[int, int]:
        value = 0
        while start < input_size:
            byte = mutable[start]
            value += byte
            start += 1
            if byte != 0xFF:
                break
        return value, start

    while input_pos < input_size:
        literal_count = mutable[input_pos] & 0x0F
        match_count = (mutable[input_pos] >> 4) & 0x0F
        mutable[input_pos] = (literal_count << 4) | match_count
        input_pos += 1
        if literal_count == 0x0F:
            extra, input_pos = extended_length(input_pos)
            literal_count += extra
        input_pos += literal_count
        output_pos += literal_count
        if output_pos >= uncompressed_size:
            break
        offset = (mutable[input_pos] << 8) | mutable[input_pos + 1]
        mutable[input_pos] = offset & 0xFF
        mutable[input_pos + 1] = offset >> 8
        input_pos += 2
        if match_count == 0x0F:
            extra, input_pos = extended_length(input_pos)
            match_count += extra
        output_pos += match_count + 4
    import lz4.block

    return lz4.block.decompress(bytes(mutable), uncompressed_size)


def register_decoder() -> None:
    CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak


def matches(text: str) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in KEYWORDS if keyword in lowered]


def scan_bundle(apk_path: Path, member: str) -> dict:
    with zipfile.ZipFile(apk_path) as archive:
        raw_bundle = archive.read(member)
    environment = UnityPy.load(raw_bundle)
    assets = list(environment.objects)
    bundle_object = next((obj for obj in assets if obj.type.name == "AssetBundle"), None)
    container_keys: list[str] = []
    if bundle_object is not None:
        typetree = bundle_object.read_typetree()
        container_keys = [entry[0] for entry in typetree.get("m_Container", [])]
    names: set[str] = set()
    for key in container_keys:
        names.add(key.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    names.update(obj.read().m_Name for obj in assets if obj.type.name == "GameObject")
    joined_names = "\n".join(names)
    joined_container = "\n".join(container_keys)
    name_matches = matches(joined_names)
    container_matches = matches(joined_container)
    return {
        "apk_member": member,
        "apk_member_sha256": hashlib.sha256(raw_bundle).hexdigest(),
        "compressed_size": len(raw_bundle),
        "object_count": len(assets),
        "container_count": len(container_keys),
        "container_matches": container_matches,
        "name_matches": name_matches,
        "hit": bool(container_matches or name_matches),
    }


def load_existing_records(output: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    if not output.exists():
        return records
    for line_number, line in enumerate(output.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            member = record["result"]["apk_member"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid scan record at {output}:{line_number}: {exc}") from exc
        if member in records:
            raise ValueError(f"duplicate scan record for {member} in {output}")
        records[member] = record
    return records


def scan_members(
    apk_path: Path,
    members: list[str],
    output: Path,
    *,
    force: bool = False,
    scanner=scan_bundle,
) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output.with_name(output.name + ".manifest.json")
    unique_members: list[str] = []
    seen: set[str] = set()
    for member in members:
        if member not in seen:
            unique_members.append(member)
            seen.add(member)
    requested_member_set = set(unique_members)
    existing = {} if force else load_existing_records(output)
    kept = {
        member: record
        for member, record in existing.items()
        if record.get("status") in {"ok", "skipped"} and member in requested_member_set
    }
    counts = {
        "ok": sum(record.get("status") == "ok" for record in kept.values()),
        "error": 0,
        "skipped": sum(record.get("status") == "skipped" for record in kept.values()),
    }
    pending = [member for member in unique_members if member not in kept]
    started = time.time()
    with output.open("w", encoding="utf-8") as stream:
        for member, record in sorted(kept.items()):
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        for index, member in enumerate(pending, 1):
            try:
                result = scanner(apk_path, member)
                record = {"status": "ok", "result": result}
                counts["ok"] += 1
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
            if record["result"].get("hit"):
                print(json.dumps(record["result"], ensure_ascii=False, sort_keys=True), flush=True)
    manifest = {
        "schema_version": "M32_RESOURCE_INDEX_V1",
        "records_path": str(output),
        "apk_path": str(apk_path),
        "apk_sha256": hashlib.sha256(apk_path.read_bytes()).hexdigest(),
        "requested_member_count": len(unique_members),
        "requested_members": unique_members,
        "counts": counts,
        "elapsed_seconds": time.time() - started,
        "resumed_completed_members": len(kept),
        "freshly_scanned_members": len(pending),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def default_members(apk_path: Path) -> list[str]:
    with zipfile.ZipFile(apk_path) as archive:
        return [
            name
            for name in archive.namelist()
            if name.startswith(("assets/AB/Android/battle/", "assets/AB/Android/pkgrps/"))
            and name.endswith(".ab")
        ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, default=Path("arknights-hg-2771.apk"))
    parser.add_argument("--output", type=Path, default=Path("output/m32_resource_index_v1/resource_index.jsonl"))
    parser.add_argument("--members", type=Path, help="newline-delimited bundle members; default: all battle and pkgrps bundles")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    register_decoder()
    members = default_members(args.apk)
    if args.members:
        members = [line.strip() for line in args.members.read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = scan_members(args.apk, members, args.output, force=args.force)
    print(json.dumps({key: manifest[key] for key in ("requested_member_count", "counts", "elapsed_seconds")}, sort_keys=True))


if __name__ == "__main__":
    main()
