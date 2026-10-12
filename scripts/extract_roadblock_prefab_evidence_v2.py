from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper


APK_MEMBER = "assets/AB/Android/pkgrps/btl_pfb_tokens_0.ab"
CONTAINER_KEY = "dyn/battle/prefabs/[uc]tokens/trap_020_roadblock.prefab"
OUTPUT_DIR = Path("output/r8_1_roadblock_prefab_evidence_v2")

DISASSEMBLY_METHODS = {
    "Tile.get_moveCost": (0x277BE88, 0x277BF00),
    "Tile.get_isObstacleLike": (0x277BF00, 0x277BF98),
    "Tile.OverwriteObstacleLikeMoveCost": (0x27825CC, 0x278264C),
    "SPFA.CheckReachable": (0x276C044, 0x276C224),
    "SPFA._CheckCachedMapReachable": (0x276C224, 0x276C3A8),
    "Tile.RefreshTileOptionsViaToken": (0x2783DE4, 0x2783FBC),
    "Tile.TryUpdateOptions": (0x2785658, 0x2785804),
    "Tile.RewriteOptions": (0x2785804, 0x2785A44),
    "Tile.RestoreOptionsOnlyViaToken": (0x2786F58, 0x2787128),
    "Trap.CheckHasFilterTag": (0x2987600, 0x29876AC),
    "Enemy.SpecialBlockCondition.CheckBlockable": (0x293BBD8, 0x293BF50),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decompress_lz4ak(data: bytes, uncompressed_size: int) -> bytes:
    # Algorithm from isHarryh/Ark-Unpacker, BSD-3-Clause.
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


def parse_unityfs_header(data: bytes) -> dict:
    signature_end = data.index(b"\0") + 1
    version_end = signature_end + 4
    player_version_end = data.index(b"\0", version_end) + 1
    engine_version_end = data.index(b"\0", player_version_end) + 1
    size_offset = engine_version_end
    return {
        "signature": data[: signature_end - 1].decode("ascii"),
        "format_version": struct.unpack(">I", data[signature_end:version_end])[0],
        "unity_player_version": data[version_end : player_version_end - 1].decode("ascii"),
        "unity_engine_version": data[player_version_end : engine_version_end - 1].decode("ascii"),
        "bundle_size": struct.unpack(">q", data[size_offset : size_offset + 8])[0],
        "compressed_blocks_info_size": struct.unpack(">I", data[size_offset + 8 : size_offset + 12])[0],
        "uncompressed_blocks_info_size": struct.unpack(">I", data[size_offset + 12 : size_offset + 16])[0],
        "flags": struct.unpack(">I", data[size_offset + 16 : size_offset + 20])[0],
    }


def resolve_path_id(objects: list, path_id: int):
    return next((obj for obj in objects if obj.path_id == path_id), None)


def compact_component(obj, selected_fields: list[str] | None = None) -> dict:
    typetree = obj.read_typetree()
    if selected_fields is None:
        selected_fields = list(typetree)
    return {
        "path_id": obj.path_id,
        "type": obj.type.name,
        "fields": {field: typetree[field] for field in selected_fields if field in typetree},
    }


def extract(apk_path: Path, output_dir: Path) -> dict:
    import zipfile

    with zipfile.ZipFile(apk_path) as archive:
        raw_bundle = archive.read(APK_MEMBER)
    header = parse_unityfs_header(raw_bundle)

    errors: list[dict] = []
    try:
        UnityPy.load(raw_bundle)
    except Exception as exc:
        errors.append(
            {
                "method": "UNITYPY_DEFAULT",
                "exception_type": type(exc).__name__,
                "message": str(exc),
            }
        )

    CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak
    environment = UnityPy.load(raw_bundle)
    objects = list(environment.objects)
    asset_bundle = next(obj for obj in objects if obj.type.name == "AssetBundle")
    bundle_typetree = asset_bundle.read_typetree()
    container_entry = next(item for item in bundle_typetree["m_Container"] if item[0] == CONTAINER_KEY)
    asset_info = container_entry[1]
    target_path_id = asset_info["asset"]["m_PathID"]
    target = resolve_path_id(objects, target_path_id)
    target_data = target.read()
    if target_data.m_Name != "trap_020_roadblock":
        raise RuntimeError(f"unexpected target name: {target_data.m_Name}")

    root_component = None
    for pair in target_data.m_Components:
        component = pair.deref()
        if component.type.name != "MonoBehaviour":
            continue
        fields = component.read_typetree()
        if "_rewriteTileOptions" in fields and "_modes" in fields:
            root_component = component
            break
    if root_component is None:
        raise RuntimeError("Token-like root component was not found")

    root_fields = root_component.read_typetree()
    mode_path_id = root_fields["_modes"][0]["m_PathID"]
    mode_component = resolve_path_id(objects, mode_path_id)
    common_ability_path_id = root_fields["_commonAbilities"][0]["m_PathID"]
    common_ability_component = resolve_path_id(objects, common_ability_path_id)

    extraction = {
        "schema_version": "R8_1_ROADBLOCK_PREFAB_EVIDENCE_V2",
        "source": {
            "apk_member": APK_MEMBER,
            "container_key": CONTAINER_KEY,
            "asset_bundle_object_path_id": asset_bundle.path_id,
            "asset_preload_index": asset_info["preloadIndex"],
            "asset_preload_size": asset_info["preloadSize"],
            "unityfs_header": header,
            "bundle_sha256": sha256_bytes(raw_bundle),
        },
        "decode_attempts": errors
        + [
            {
                "method": "ARKNIGHTS_LZ4AK_FLAG_4",
                "status": "SUCCESS",
                "decoded_object_count": len(objects),
            }
        ],
        "prefab": {
            "game_object_path_id": target.path_id,
            "game_object_name": target_data.m_Name,
            "root_component": compact_component(
                root_component,
                [
                    "_modes",
                    "_commonAbilities",
                    "_traitAbility",
                    "_motionMode",
                    "_blockMode",
                    "_sideType",
                    "_category",
                    "_rewriteTileOptions",
                    "_rewriteTileHeightTypeOnMode",
                    "_rewriteTileHeightTypeOnModeBySelf",
                    "_ignoreBlockAnyRoutes",
                    "_hideTileOptions",
                    "_rewriteTileAdvancedBuildMask",
                    "_withdrawable",
                    "_blockRadiusSquare",
                    "_filterTag",
                ],
            ),
            "mode_component": compact_component(
                mode_component,
                [
                    "_tileOptions",
                    "_keepCurrentPassableMask",
                    "_keepCurrentBuildableType",
                    "_rewriteTileHeightType",
                    "_rewriteTileHeight",
                    "_rewriteHeight",
                    "_rewriteTileAdvancedBuildMask",
                ],
            ),
            "common_ability_component": compact_component(common_ability_component, ["_buffs", "_metadata"]),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "roadblock_prefab_extraction.json").write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return extraction


def disassemble(native_library: Path, output_dir: Path) -> None:
    import capstone

    raw = native_library.read_bytes()
    disassembler = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    lines: list[str] = []
    for name, (start, end) in DISASSEMBLY_METHODS.items():
        lines.append(f"=== {name} 0x{start:x}-0x{end:x} ===")
        lines.extend(f"{ins.address:x}:\t{ins.mnemonic}\t{ins.op_str}" for ins in disassembler.disasm(raw[start:end], start))
        lines.append("")
    (output_dir / "roadblock_navigation_disasm.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    parser.add_argument("native_library", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    extraction = extract(args.apk, args.output_dir)
    disassemble(args.native_library, args.output_dir)

    raw_files = []
    for name in ("roadblock_prefab_extraction.json", "roadblock_navigation_disasm.txt"):
        path = args.output_dir / name
        raw_files.append({"path": name, "sha256": sha256_bytes(path.read_bytes())})
    evidence = {
        "schema_version": "R8_1_ROADBLOCK_PREFAB_EVIDENCE_V2",
        "budget": {
            "kimi_calls": 0,
            "real_stage_simulations": 0,
            "new_operational_plans": 0,
            "new_action_candidates": 0,
            "expanded_tactical_search": 0,
        },
        "apk_sha256": sha256_bytes(args.apk.read_bytes()),
        "native_library_sha256": sha256_bytes(args.native_library.read_bytes()),
        "gamedata_commit": "0ef7f952dfd018392200157a5c79a6511ba69122",
        "confirmed_from_code": {
            "prefab_rewrite_tile_options": extraction["prefab"]["root_component"]["fields"]["_rewriteTileOptions"],
            "keep_current_passable_mask": extraction["prefab"]["mode_component"]["fields"]["_keepCurrentPassableMask"],
            "tile_options_passable_mask": extraction["prefab"]["mode_component"]["fields"]["_tileOptions"]["passableMask"],
            "override_obstacle_like_move_cost": extraction["prefab"]["mode_component"]["fields"]["_tileOptions"][
                "overrideObstacleLikeMoveCost"
            ],
            "filter_tags": extraction["prefab"]["root_component"]["fields"]["_filterTag"],
        },
        "ordinary_walk_navigation": {
            "passable_mask": "UNCHANGED_BY_KEEP_CURRENT_PASSABLE_MASK",
            "route_refresh_change_signal": "MOVE_COST_OR_PASSABLE_MASK_CHANGE_PARTICIPATES",
            "route_refresh_scheduling": "NON_BATCHING_CALLS_MAP_UPDATE_ROUTES; BATCHING_ACCUMULATES_DIRTY_ROUTES",
            "avoid_obstacle_like_reachable": "CACHED_NODE_DISTANCE_MINUS_TILE_MOVE_COST_LESS_THAN_1000",
            "r8_1_avoid_obstacle_like_scenario": "UNKNOWN",
            "default_route_generation_effect": "UNKNOWN",
            "historical_labels_superseded": [
                "NOT_TRIGGERED_FOR_UNCHANGED_WALK_FLY_MASK",
                "FALSE_IF_AVOID_OBSTACLE_LIKE_IS_TRUE",
            ],
        },
        "civilian_talulah_blocking": "UNKNOWN",
        "cross_version_applicability": "UNKNOWN",
        "raw_evidence_files": raw_files,
    }
    (args.output_dir / "roadblock_prefab_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "ARTIFACT_MANIFEST_V1",
        "files": [
            {"path": path.name, "sha256": sha256_bytes(path.read_bytes())}
            for path in sorted(args.output_dir.iterdir(), key=lambda item: item.name)
            if path.name != "manifest.json"
        ],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
