from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/build_m33_binding_graph_key_rows_v1.py"
    spec = importlib.util.spec_from_file_location("build_m33_binding_graph_key_rows_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_extract_key_rows_selects_expected_scripts_and_external_refs(tmp_path):
    module = _load_module()
    source_graph = tmp_path / "graph.jsonl"
    root_identity = f"{module.PROJECTILE_CAB}:{module.PROJECTILE_PATH_ID}"
    component_refs = [
        {
            "field": f"m_Component[{index}].component",
            "resolution": "RESOLVED_INTERNAL",
            "source_identity": root_identity,
            "target_identity": f"{module.PROJECTILE_CAB}:{path_id}",
        }
        for index, path_id in enumerate((100, 101, 102, 103))
    ]
    _write_jsonl(
        source_graph,
        [
            {
                "status": "ok",
                "result": {
                    "apk_member": "other.ab",
                    "objects": [],
                },
            },
            {
                "status": "ok",
                "result": {
                    "apk_member": module.PROJECTILE_MEMBER,
                    "objects": [
                        {
                            "path_id": module.PROJECTILE_PATH_ID,
                            "type": "GameObject",
                            "name": "projectile_enemy_emppnt",
                            "serialized_file": module.PROJECTILE_CAB,
                            "container_paths": ["projectile_enemy_emppnt.prefab"],
                            "pptr_reference_identities": component_refs,
                        }
                    ],
                },
            },
        ],
    )
    reverse_index = tmp_path / "reverse.jsonl"
    script_rows = [
        {
            "apk_member": module.PROJECTILE_MEMBER,
            "record_type": "SCRIPT_BINDING",
            "script_name": script_name,
            "source_identity": f"{module.PROJECTILE_CAB}:{100 + index}",
        }
        for index, script_name in enumerate(
            ("SimpleProjectile", "EffectBehaviour", "HitBehaviour", "AttachToTarget")
        )
    ]
    _write_jsonl(
        reverse_index,
        script_rows + [
            {
                "apk_member": "other.ab",
                "record_type": "PPTR_REFERENCE",
                "resolution": "RESOLVED_EXTERNAL",
                "target_cab": module.PROJECTILE_CAB,
            },
            {
                "apk_member": module.PROJECTILE_MEMBER,
                "record_type": "PPTR_REFERENCE",
                "resolution": "RESOLVED_EXTERNAL",
                "target_cab": module.PROJECTILE_CAB,
            },
        ],
    )
    evidence = module.extract_key_rows(source_graph, reverse_index)
    assert evidence["schema_version"] == module.SCHEMA_VERSION
    assert evidence["projectile_root"]["name"] == "projectile_enemy_emppnt"
    assert [row["script_name"] for row in evidence["selected_script_bindings"]] == [
        "SimpleProjectile",
        "EffectBehaviour",
        "HitBehaviour",
        "AttachToTarget",
    ]
    assert len(evidence["external_references_to_projectile_cab"]) == 1
    assert evidence["inputs"]["source_graph_sha256"]
    assert evidence["inputs"]["reverse_index_sha256"]
