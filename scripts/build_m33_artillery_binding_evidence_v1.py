from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path
from typing import Any


PROJECTILE_MEMBER = "assets/AB/Android/battle/prefabs/[uc]projectiles.ab"
SCRIPT_MEMBERS = {
    "assets/AB/Android/anon/25ca9f1e45dc03e951bc38ef8f0a3670.bin",
    "assets/AB/Android/anon/9331724438927fc1266f8a4db7766543.bin",
}
PROJECTILE_CAB = "CAB-34af01ecb5d2ad63aca01b6e0d71279d"
SCRIPT_CAB = "CAB-658d74aab777086fc32b93f385be999a"
PROJECTILE_PATH_ID = -619213101382661339


def _load_graph_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts/extract_m33_resource_binding_graph_v1.py"
    spec = importlib.util.spec_from_file_location("extract_m33_resource_binding_graph_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_decoder_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts/extract_m32_resource_index_v1.py"
    spec = importlib.util.spec_from_file_location("extract_m32_resource_index_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_environment(graph_module: Any, apk: Path, member: str) -> Any:
    with zipfile.ZipFile(apk) as archive:
        raw = archive.read(member)
    import UnityPy

    return UnityPy.load(raw)


def build_evidence(apk: Path, output: Path) -> dict[str, Any]:
    graph_module = _load_graph_module()
    decoder_module = _load_decoder_module()
    decoder_module.register_decoder()

    script_names: dict[int, str] = {}
    for member in sorted(SCRIPT_MEMBERS):
        environment = _load_environment(graph_module, apk, member)
        for obj in environment.objects:
            if obj.type.name != "MonoScript":
                continue
            typetree = obj.read_typetree()
            script_names[obj.path_id] = typetree.get("m_Name")

    environment = _load_environment(graph_module, apk, PROJECTILE_MEMBER)
    objects = {obj.path_id: obj for obj in environment.objects}
    root = objects[PROJECTILE_PATH_ID]
    root_tree = root.read_typetree()
    components: list[dict[str, Any]] = []
    for index, entry in enumerate(root_tree.get("m_Component", [])):
        path_id = entry["component"]["m_PathID"]
        obj = objects[path_id]
        typetree = obj.read_typetree()
        script = typetree.get("m_Script")
        script_identity = f"{SCRIPT_CAB}:{script['m_PathID']}" if script else None
        components.append(
            {
                "index": index,
                "source_identity": f"{PROJECTILE_CAB}:{path_id}",
                "type": obj.type.name,
                "script_identity": script_identity,
                "script_name": script_names.get(script["m_PathID"]) if script else None,
                "reference": {
                    "field_path": f"m_Component[{index}].component",
                    "source_path_id": PROJECTILE_PATH_ID,
                    "target_path_id": path_id,
                    "target_identity": f"{PROJECTILE_CAB}:{path_id}",
                    "resolution": "RESOLVED_INTERNAL",
                },
                "fields": typetree,
            }
        )

    apk_sha = hashlib.sha256(apk.read_bytes()).hexdigest()
    evidence = {
        "schema_version": "M33_ARTILLERY_BINDING_EVIDENCE_V1",
        "apk_path": str(apk),
        "apk_sha256": apk_sha,
        "projectile": {
            "resource_path": "dyn/battle/prefabs/[uc]projectiles/projectile_enemy_emppnt.prefab",
            "apk_member": PROJECTILE_MEMBER,
            "apk_member_sha256": hashlib.sha256(zipfile.ZipFile(apk).read(PROJECTILE_MEMBER)).hexdigest(),
            "serialized_file": PROJECTILE_CAB,
            "path_id": PROJECTILE_PATH_ID,
            "identity": f"{PROJECTILE_CAB}:{PROJECTILE_PATH_ID}",
            "components": components,
        },
        "selected_client_type_methods": {
            "Torappu.Battle.SimpleProjectile": {"dump_cs_type": "TypeDefIndex:10667"},
            "Torappu.Battle.HitBehaviour": {
                "dump_cs_type": "TypeDefIndex:12437",
                "Init_RVA": "0x2BFB724",
                "OnProjectileReached_RVA": "0x2C0B5C4",
                "DealHitTarget_RVA": "0x2BFBDB8",
                "OnTriggerEnter2D_RVA": "0x2C0C37C",
            },
            "Torappu.Battle.AdvancedMovement": {
                "dump_cs_type": "TypeDefIndex:12496",
                "Init_RVA": "0x2C2BF5C",
                "OnTick_RVA": "0x2C2C360",
                "CheckStartTick_RVA": "0x2C2CDA8",
            },
            "Torappu.Battle.Enemy": {
                "CheckTargetInAttackRange_RVA": "0x2928618",
                "SearchAttackTarget_RVA": "0x29247F8",
            },
        },
        "game_data_facts": {
            "enemy_id": "enemy_1112_emppnt",
            "max_hp": 13000,
            "attack": 1000,
            "defense": 800,
            "magic_resistance_percent": 50.0,
            "base_attack_time_seconds": 5.0,
            "range_radius": 2.0,
            "apply_way": "RANGED",
            "motion": "FLY",
            "source": "data/ArknightsGameData/zh_CN/gamedata/levels/enemydata/enemy_database.json",
        },
        "chain_status": {
            "config_to_generic_enemy": "CONFIRMED_FROM_GAMEDATA_AND_CLIENT_METHODS",
            "projectile_to_scripts": "CONFIRMED_FROM_MONOSCRIPT_PPTR",
            "explosion_radius_field": "CONFIRMED_AS_CIRCLE_COLLIDER_2D_RADIUS",
            "enemy_to_projectile_creation": "NO_DIRECT_SERIALIZED_PPTR_FOUND",
            "attack_interval_start_clock": "UNKNOWN",
            "targeting_order": "UNKNOWN",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, default=Path("arknights-hg-2771.apk"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/review/fc77177/m33_artillery_binding_v1/artillery_binding_evidence.json"),
    )
    args = parser.parse_args()
    evidence = build_evidence(args.apk, args.output)
    print(json.dumps({"output": str(args.output), "apk_sha256": evidence["apk_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
