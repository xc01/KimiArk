from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BUNDLES = {
    "projectiles": "assets/AB/Android/battle/prefabs/[uc]projectiles.ab",
    "enemy_fx": "assets/AB/Android/pkgrps/btl_pfb_fx_enemy_5.ab",
    "shared_fx": "assets/AB/Android/refs/fx/sharedbattle.ab",
    "ansel": "assets/AB/Android/charpack/char_212_ansel.ab",
    "hibiscus": "assets/AB/Android/charpack/char_120_hibisc.ab",
}

CONTAINER_KEYS = {
    "projectiles": "dyn/battle/prefabs/[uc]projectiles/projectile_enemy_emppnt.prefab",
    "enemy_fx": "dyn/battle/prefabs/effects/enemy_emppnt_attack_01_trail.prefab",
    "shared_fx": "Assets/Torappu/Fx/Battle/enemy/enemy_1112_emppnt/material/enemy_emppnt_07.mat",
    "ansel": "dyn/battle/prefabs/characters/char_212_ansel.prefab",
    "hibiscus": "dyn/battle/prefabs/characters/char_120_hibisc.prefab",
}

NATIVE_RANGES = {
    "EnemyTraceTargetByPriorityAbility.get_cooldown": (0x2E2A6CC, 0x2E2A76C),
    "EnemyTraceTargetByPriorityAbility.CastToTarget": (0x2E2B3E0, 0x2E2B54C),
    "EnemyTraceTargetByPriorityAbility.OnTick": (0x2E2B54C, 0x2E2C454),
    "EnemyTraceTargetByPriorityAbility._DoFindTargetByPriority": (0x2E2BFC4, 0x2E2C290),
    "EnemyTraceTargetByPriorityAbility.CheckTraceTargetInAttackRange": (0x2E2C454, 0x2E2C584),
    "EnemyTraceTargetByPriorityAbility._RegisterTraceTarget": (0x2E2C584, 0x2E2C6B4),
    "EnemyTraceTargetByPriorityAbility._UpdateTraceTargetRoute": (0x2E2C970, 0x2E2CC14),
    "EnemyTraceTargetByPriorityAbility._CanUseAttack": (0x2E2CC14, 0x2E2CE70),
    "AdvancedSelector.OnPostFilter.Entities": (0x288A898, 0x288AE08),
    "AdvancedSelector.OnPostFilter.Compare": (0x288B21C, 0x288B294),
    "FilterUtil.Filter": (0x2898C04, 0x28990F8),
    "FilterUtil._Filter_HpRatioAsc": (0x28A4EDC, 0x28A4F8C),
    "BattleFormula.CalculateHeal": (0x253F684, 0x253F770),
    "Action.Nodes.ApplyHeal.Execute": (0x2F66508, 0x2F66830),
}


def decompress_lz4ak(data: bytes, uncompressed_size: int) -> bytes:
    import lz4.block

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
    return lz4.block.decompress(bytes(mutable), uncompressed_size)


def register_decoder() -> None:
    CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_bundle(apk_path: Path, bundle_name: str) -> tuple[bytes, list, dict]:
    member = BUNDLES[bundle_name]
    with zipfile.ZipFile(apk_path) as archive:
        raw = archive.read(member)
    environment = UnityPy.load(raw)
    objects = list(environment.objects)
    bundle = next(obj for obj in objects if obj.type.name == "AssetBundle")
    containers = {entry[0]: entry[1] for entry in bundle.read_typetree()["m_Container"]}
    return raw, objects, containers


def object_by_path_id(objects: list, path_id: int):
    return next((obj for obj in objects if obj.path_id == path_id), None)


def extract_container(apk_path: Path, bundle_name: str) -> dict:
    raw, objects, containers = load_bundle(apk_path, bundle_name)
    key = CONTAINER_KEYS[bundle_name]
    entry = containers[key]
    target = object_by_path_id(objects, entry["asset"]["m_PathID"])
    data = target.read()
    cache: dict[int, object] = {}

    def deref(pointer):
        if pointer is None:
            return None
        path_id = pointer.get("m_PathID") if isinstance(pointer, dict) else pointer.m_PathID
        if not path_id:
            return None
        if path_id not in cache:
            cache[path_id] = object_by_path_id(objects, path_id)
        return cache[path_id]

    components = []
    component_pointers = getattr(data, "m_Components", [])
    if not component_pointers:
        components.append({
            "path_id": target.path_id,
            "type": target.type.name,
            "fields": target.read_typetree(),
        })
    for component_pointer in component_pointers:
        component = component_pointer.deref()
        record = {
            "path_id": component.path_id,
            "type": component.type.name,
        }
        if component.type.name == "MonoBehaviour":
            typetree = component.read_typetree()
            script = deref(typetree.get("m_Script"))
            script_name = None
            if script is not None:
                try:
                    script_data = script.read()
                    script_name = {
                        "class_name": script_data.m_ClassName,
                        "namespace": script_data.m_Namespace,
                        "assembly": script_data.m_AssemblyName,
                    }
                except Exception as exc:
                    script_name = {"error": type(exc).__name__, "message": str(exc)}
            record["script"] = script_name
            record["fields"] = typetree
        components.append(record)
    return {
        "bundle": BUNDLES[bundle_name],
        "bundle_sha256": sha256_bytes(raw),
        "container_key": key,
        "game_object": {
            "path_id": target.path_id,
            "name": data.m_Name,
        },
        "components": components,
    }


def extract_medic_components(apk_path: Path) -> dict:
    raw, objects, containers = load_bundle(apk_path, "ansel")
    key = CONTAINER_KEYS["ansel"]
    game_object = object_by_path_id(objects, containers[key]["asset"]["m_PathID"]).read()
    root = next(
        pointer.deref()
        for pointer in game_object.m_Components
        if pointer.deref().type.name == "MonoBehaviour"
    )
    root_fields = root.read_typetree()
    mode = object_by_path_id(objects, root_fields["_modes"][0]["m_PathID"]).read_typetree()
    attack = object_by_path_id(objects, mode["_attack"]["m_PathID"])
    attack_fields = attack.read_typetree()
    selector = object_by_path_id(objects, attack_fields["_selector"]["m_PathID"])
    selector_fields = selector.read_typetree()
    return {
        "operator_id": "char_212_ansel",
        "bundle": BUNDLES["ansel"],
        "bundle_sha256": sha256_bytes(raw),
        "container_key": key,
        "attack_path_id": attack.path_id,
        "attack_fields": attack_fields,
        "selector_path_id": selector.path_id,
        "selector_fields": selector_fields,
    }


def extract_native_evidence(apk_path: Path, output_dir: Path) -> dict:
    import capstone

    lib_member = "lib/arm64-v8a/libil2cpp.so"
    metadata_member = "assets/bin/Data/Managed/Metadata/global-metadata.dat"
    with zipfile.ZipFile(apk_path) as archive:
        raw_library = archive.read(lib_member)
        raw_metadata = archive.read(metadata_member)
    methods = json.load(open("/tmp/akdump5/script.json", encoding="utf-8"))["ScriptMethod"]
    symbol_by_address = {method["Address"]: method["Name"] for method in methods}
    disassembler = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    disassembler.skipdata = True
    lines = []
    for name, (start, end) in NATIVE_RANGES.items():
        lines.append(f"=== {name} 0x{start:x}-0x{end:x} ({end - start} bytes) ===")
        for instruction in disassembler.disasm(raw_library[start:end], start):
            line = f"{instruction.address:x}: {instruction.mnemonic:8} {instruction.op_str}"
            if instruction.mnemonic in {"b", "bl"}:
                try:
                    branch_target = int(instruction.op_str.replace("#", ""), 16)
                    if branch_target in symbol_by_address:
                        line += f" ; {symbol_by_address[branch_target]}"
                except ValueError:
                    pass
            lines.append(line.rstrip())
        lines.append("")
    text_path = output_dir / "m32_native_key_disasm.txt"
    text_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "library_member": lib_member,
        "library_sha256": sha256_bytes(raw_library),
        "metadata_member": metadata_member,
        "metadata_sha256": sha256_bytes(raw_metadata),
        "disassembly_sha256": sha256_bytes(text_path.read_bytes()),
        "disassembly_line_count": len(lines),
    }


def fixed_input_provenance() -> dict:
    zip_path = PROJECT_ROOT / "ArknightsGameData-master.zip"
    with zipfile.ZipFile(zip_path) as archive:
        commit = archive.comment.decode("ascii")
    files = {
        "level": "zh_CN/gamedata/levels/obt/main/level_main_08-07.json",
        "enemy_database": "zh_CN/gamedata/levels/enemydata/enemy_database.json",
        "character_table": "zh_CN/gamedata/excel/character_table.json",
    }
    results = {}
    for name, relative_path in files.items():
        zip_member = f"ArknightsGameData-master/{relative_path}"
        local_path = PROJECT_ROOT / "data/ArknightsGameData" / relative_path
        with zipfile.ZipFile(zip_path) as archive:
            zip_bytes = archive.read(zip_member)
        local_bytes = local_path.read_bytes()
        results[name] = {
            "relative_path": relative_path,
            "zip_member_sha256": sha256_bytes(zip_bytes),
            "local_sha256": sha256_bytes(local_bytes),
            "match": zip_bytes == local_bytes,
        }
    return {
        "zip_path": str(zip_path),
        "zip_comment_commit": commit,
        "files": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, default=PROJECT_ROOT / "arknights-hg-2771.apk")
    parser.add_argument("--output", type=Path, default=Path("output/m32_client_evidence_v1"))
    args = parser.parse_args()
    register_decoder()
    args.output.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for bundle_name in ("projectiles", "enemy_fx", "shared_fx"):
        outputs[bundle_name] = extract_container(args.apk, bundle_name)
    outputs["ansel"] = extract_medic_components(args.apk)
    (args.output / "m32_client_resource_evidence_v1.json").write_text(
        json.dumps(outputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    native = extract_native_evidence(args.apk, args.output)
    provenance = fixed_input_provenance()
    (args.output / "m32_fixed_input_provenance_v1.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "m32_native_evidence_manifest_v1.json").write_text(
        json.dumps(native, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "native": native}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
