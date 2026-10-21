from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/extract_m32_resource_index_v1.py"
    spec = importlib.util.spec_from_file_location("extract_m32_resource_index_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_scanner(failed_member: str):
    def scan(apk_path: Path, member: str) -> dict:
        if member == failed_member:
            raise ValueError("decode failed")
        return {"apk_member": member, "hit": member == "good.ab"}

    return scan


def _apk(tmp_path: Path) -> Path:
    apk = tmp_path / "apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("good.ab", "good")
        archive.writestr("bad.ab", "bad")
    return apk


def test_scan_members_continues_after_decode_error_and_can_resume(tmp_path):
    module = _load_module()
    apk = _apk(tmp_path)
    output = tmp_path / "resource_index.jsonl"
    first = module.scan_members(apk, ["good.ab", "bad.ab"], output, scanner=_fake_scanner("bad.ab"))
    assert first["counts"] == {"ok": 1, "error": 1, "skipped": 0}
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert [record["result"]["apk_member"] for record in records] == ["good.ab", "bad.ab"]

    resumed = module.scan_members(apk, ["bad.ab", "good.ab"], output, scanner=_fake_scanner("other.ab"))
    assert resumed["counts"] == {"ok": 2, "error": 0, "skipped": 0}
    assert resumed["resumed_completed_members"] == 1
    assert resumed["freshly_scanned_members"] == 1
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert [record["result"]["apk_member"] for record in records] == ["good.ab", "bad.ab"]
    assert all(record["status"] == "ok" for record in records)
    manifest = json.loads(output.with_name(output.name + ".manifest.json").read_text())
    assert manifest["requested_members"] == ["bad.ab", "good.ab"]
    assert manifest["apk_sha256"]


def test_scan_members_counts_requested_duplicate_once(tmp_path):
    module = _load_module()
    apk = _apk(tmp_path)
    output = tmp_path / "resource_index.jsonl"
    manifest = module.scan_members(apk, ["good.ab", "good.ab"], output, scanner=_fake_scanner("bad.ab"))
    assert manifest["requested_member_count"] == 1
    assert manifest["counts"]["ok"] == 1
