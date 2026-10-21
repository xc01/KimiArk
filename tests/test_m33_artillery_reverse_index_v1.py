from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/build_m33_artillery_reverse_index_v1.py"
    spec = importlib.util.spec_from_file_location("build_m33_artillery_reverse_index_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reverse_index_preserves_identity_and_resolves_scripts(tmp_path):
    module = _load_module()
    graph = tmp_path / "graph.jsonl"
    graph.write_text(
        json.dumps(
            {
                "status": "ok",
                "result": {
                    "apk_member": "bundle.ab",
                    "apk_member_sha256": "0" * 64,
                    "serialized_files": ["CAB-source"],
                    "objects": [
                        {
                            "type": "MonoScript",
                            "serialized_file": "CAB-scripts",
                            "path_id": 101,
                            "name": "SimpleProjectile",
                        }
                    ],
                    "pptr_edges": [
                        {
                            "source_identity": "CAB-source:1",
                            "source_type": "MonoBehaviour",
                            "field": "m_Script",
                            "target_identity": "CAB-scripts:101",
                            "target_cab": "CAB-scripts",
                            "target_path_id": 101,
                            "resolution": "RESOLVED_EXTERNAL",
                        }
                    ],
                    "ownership_edges": [
                        {
                            "relation": "GAMEOBJECT_HAS_COMPONENT",
                            "source_identity": "CAB-source:1",
                            "target_identity": "CAB-source:2",
                            "field": "m_Component[0].component",
                            "resolution": "RESOLVED_INTERNAL",
                        }
                    ],
                    "resource_string_clues": [{"field": "m_Name", "value": "enemy_1112_emppnt"}],
                    "container_entries": [
                        {
                            "container_path": "enemy_1112_emppnt.prefab",
                            "asset": {"m_FileID": 0, "m_PathID": 1},
                        }
                    ],
                },
            }
        )
        + "\n"
    )
    output = tmp_path / "index.jsonl"
    manifest = module.normalize_graph_records([graph], output, terms=("enemy_1112_emppnt",))
    rows = [json.loads(line) for line in output.open()]
    assert manifest["stats"] == {
        "pptr_reference": 1,
        "gameobject_component": 1,
        "resource_string_clue": 1,
        "script_binding": 1,
        "container_hit": 1,
    }
    script_binding = next(row for row in rows if row["record_type"] == "SCRIPT_BINDING")
    assert script_binding["source_identity"] == "CAB-source:1"
    assert script_binding["script_name"] == "SimpleProjectile"
    assert script_binding["apk_member_sha256"] == "0" * 64
