from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/extract_m33_resource_binding_graph_v1.py"
    spec = importlib.util.spec_from_file_location("extract_m33_resource_binding_graph_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pptr_edges_extracts_nested_external_references_only():
    module = _load_module()
    value = {
        "m_Name": "root",
        "component": {"m_FileID": 0, "m_PathID": 1},
        "script": {"m_FileID": 1, "m_PathID": -2},
        "children": [{"m_FileID": 2, "m_PathID": 3}, {"other": 4}],
    }
    edges = module.pptr_edges(value)
    assert edges == [
        {"field": "component", "file_id": 0, "path_id": 1},
        {"field": "script", "file_id": 1, "path_id": -2},
        {"field": "children[0]", "file_id": 2, "path_id": 3},
    ]
    assert module.deduplicate_edges(edges + edges) == edges


def test_string_clues_are_deduplicated_and_preserve_paths():
    module = _load_module()
    value = {
        "container": "dyn/battle/prefabs/[uc]projectiles/projectile_enemy_emppnt.prefab",
        "items": ["projectile_enemy_emppnt", {"field": "enemy_1112_emppnt"}],
        "other": 1,
    }
    clues = module.collect_string_clues(value, ("enemy_1112_emppnt", "projectile_enemy_emppnt"))
    clues += module.collect_string_clues(value, ("enemy_1112_emppnt", "projectile_enemy_emppnt"))
    assert module.deduplicate_string_clues(clues) == [
        {
            "field": "container",
            "value": "dyn/battle/prefabs/[uc]projectiles/projectile_enemy_emppnt.prefab",
        },
        {"field": "items[0]", "value": "projectile_enemy_emppnt"},
        {"field": "items[1].field", "value": "enemy_1112_emppnt"},
    ]


def test_scan_graph_members_resumes_and_records_errors(tmp_path):
    module = _load_module()
    apk = tmp_path / "apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("good.ab", "good")
        archive.writestr("bad.ab", "bad")

    calls: list[str] = []

    failing = {"bad.ab"}

    def scanner(apk_path: Path, member: str):
        calls.append(member)
        if member in failing:
            raise ValueError("decode failed")
        return {
            "apk_member": member,
            "apk_member_sha256": "0" * 64,
            "object_count": 1,
            "container_count": 0,
            "external_count": 1,
            "pptr_edge_count": 1,
            "ownership_edge_count": 0,
            "resource_string_clue_count": 0,
            "typetree_read_error_count": 0,
        }

    output_dir = tmp_path / "graph"
    first = module.scan_graph_members(apk, ["good.ab", "bad.ab"], output_dir, scanner=scanner)
    assert first["counts"] == {"ok": 1, "error": 1}
    assert first["requested_members"] == ["good.ab", "bad.ab"]
    records = [json.loads(line) for line in (output_dir / "bundle_graph.jsonl").read_text().splitlines()]
    assert [record["result"]["apk_member"] for record in records] == ["good.ab", "bad.ab"]

    calls.clear()
    resumed = module.scan_graph_members(apk, ["bad.ab", "good.ab"], output_dir, scanner=scanner)
    assert calls == ["bad.ab"]
    assert resumed["counts"] == {"ok": 1, "error": 1}
    assert resumed["resumed_completed_members"] == 1
    assert resumed["freshly_scanned_members"] == 1
    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["requested_members"] == ["bad.ab", "good.ab"]
    assert manifest["apk_sha256"]

    failing.clear()
    calls.clear()
    recovered = module.scan_graph_members(apk, ["bad.ab", "good.ab"], output_dir, scanner=scanner)
    assert calls == ["bad.ab"]
    assert recovered["counts"] == {"ok": 2}

