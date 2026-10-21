from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/build_m33_bundle_dependency_index_v1.py"
    spec = importlib.util.spec_from_file_location("build_m33_bundle_dependency_index_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dependency_scan_resumes_and_reports_matches(tmp_path):
    module = _load_module()
    apk_path = tmp_path / "apk"
    apk_path.write_bytes(b"apk")
    failures = {"bad.bin"}

    def scanner(apk_path: Path, member: str):
        if member in failures:
            raise ValueError("decode failed")
        return {
            "apk_member": member,
            "apk_member_sha256": "0" * 64,
            "serialized_files": [f"CAB-{member}"],
            "external_dependencies": [],
            "matched_container_paths": (
                ["dyn/battle/prefabs/[uc]projectiles/projectile_enemy_emppnt.prefab"]
                if member == "good.bin"
                else []
            ),
        }

    output = tmp_path / "dependencies.jsonl"
    first = module.scan_members(apk_path, ["good.bin", "bad.bin"], output, scanner=scanner)
    assert first["counts"] == {"error": 1, "ok": 1}
    assert first["matched_container_bundles"] == ["good.bin"]
    records = [json.loads(line) for line in output.open()]
    assert [record["result"]["apk_member"] for record in records] == ["good.bin", "bad.bin"]

    second = module.scan_members(apk_path, ["bad.bin", "good.bin"], output, scanner=scanner)
    failures.clear()
    third = module.scan_members(apk_path, ["bad.bin", "good.bin"], output, scanner=scanner)
    assert third["counts"] == {"ok": 2}
    assert second["counts"] == {"error": 1, "ok": 1}
    assert second["freshly_scanned_members"] == 1
