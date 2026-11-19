"""R119 lossless archive only. Never executes models, checks, or battles."""
import gzip
import hashlib
from prepare import BASE, read, write

EXCLUDED = {"artifact_manifest_v1.json", "archive_verification_v1.json"}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def eligible(path):
    return path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".lock")

def main():
    journal = BASE / "gzip_archive_v1.json"
    records = read(journal) if journal.exists() else []
    known = {r["original_path"] for r in records}
    # Only new R119 large originals; old parent archives are read-only.
    for path in sorted(BASE.rglob("*")):
        if not eligible(path) or path.suffix not in {".json", ".jsonl"}:
            continue
        if path.stat().st_size < 512 * 1024:
            continue
        if path.name not in {"diagnostic_events.json", "diagnostic_summary.json", "codex_exec.jsonl", "codex_trajectory_summary.json", "tool_transport.jsonl"}:
            continue
        relative = str(path.relative_to(BASE))
        raw = path.read_bytes()
        assert not raw.startswith(b"\x1f\x8b"), "Original already gzip"
        compressed = gzip.compress(raw, compresslevel=6, mtime=0)
        assert gzip.decompress(compressed) == raw
        target = path.with_name(path.name + ".gz")
        if target.exists():
            assert gzip.decompress(target.read_bytes()) == raw, "Conflicting archive"
        target.write_bytes(compressed)
        assert digest(gzip.decompress(target.read_bytes())) == digest(raw)
        if relative not in known:
            records.append({"original_path": relative, "gzip_path": str(target.relative_to(BASE)), "uncompressed_sha256": digest(raw), "gzip_sha256": digest(compressed), "uncompressed_bytes": len(raw), "gzip_bytes": len(compressed), "restoration_verified": True})
            known.add(relative)
        write(journal, records)
        path.unlink()
    files = {}
    for path in sorted(BASE.rglob("*")):
        if not eligible(path) or path.name in EXCLUDED:
            continue
        raw = path.read_bytes()
        item = {"sha256": digest(raw), "bytes": len(raw)}
        if path.suffix == ".gz":
            restored = gzip.decompress(raw)
            assert not restored.startswith(b"\x1f\x8b"), "Double gzip"
            item.update(uncompressed_sha256=digest(restored), uncompressed_bytes=len(restored), restoration_verified=True)
        files[str(path.relative_to(BASE))] = item
    write(BASE / "artifact_manifest_v1.json", {"schema_version": "R119_ARCHIVE_MANIFEST_V1", "scope": "R119 only, no old originals rewritten", "files": files, "gzip_files": len(records), "excluded_generated_files": sorted(EXCLUDED), "locks_and_python_caches_preserved_but_not_committed": True})
    print({"files": len(files), "gzip_originals": len(records), "restoration_verified": True})

if __name__ == "__main__":
    main()
