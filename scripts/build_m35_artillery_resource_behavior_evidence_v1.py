from __future__ import annotations

import argparse
import bisect
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper


RESOURCE_VERSION = "26-10-14-13-45-10-99469376"
CLIENT_VERSION = "2.7.81"
VERSION_URL = "https://ak-conf.hypergryph.com/config/prod/official/Android/version"
HOT_LIST_URL = (
    f"https://ak.hycdn.cn/assetbundle/official/Android/assets/{RESOURCE_VERSION}/hot_update_list.json"
)
VERSION_RETRIEVED_AT = "2026-10-22T00:16:21+08:00"
HOT_LIST_RETRIEVED_AT = "2026-10-22T00:17:08+08:00"
CDN_TEMPLATE = (
    "https://ak.hycdn.cn/assetbundle/official/Android/assets/"
    f"{RESOURCE_VERSION}/{{name}}"
)
ENEMY_BUNDLE_PATH = "battle/enm_pfb_6.ab"
PROJECTILE_BUNDLE_PATH = "battle/prefabs/[uc]projectiles.ab"
FX_BUNDLE_PATH = "pkgrps/btl_pfb_fx_enemy_5.ab"
ENEMY_CONTAINER = "dyn/battle/prefabs/enemies/enemy_1112_emppnt.prefab"
PROJECTILE_CONTAINER = "dyn/battle/prefabs/[uc]projectiles/projectile_enemy_emppnt.prefab"
ENEMY_PATH_ID = -2534595712224000645
PROJECTILE_PATH_ID = -619213101382661339

RESOURCE_MANIFEST_ROWS = {
    ENEMY_BUNDLE_PATH: {
        "hash": "bed8a426e9ea6fb8f7fd6674a618785c",
        "md5": "9f928e64bae47fa7539837b236adba60",
        "totalSize": 230047,
        "abSize": 287728,
    },
    "refs/arts/enm_art_5.ab": {
        "hash": "061ef1662cdda3cb85526252caf404af",
        "md5": "0c96b1b3fe5a3eea7286b9dbaf5b6c25",
        "totalSize": 2832003,
        "abSize": 3502604,
    },
    "refs/arts/enm_art_6.ab": {
        "hash": "4bc47b1f426a644f473a29dc99ae1107",
        "md5": "fbb347a09f0dd39c1c7faea08291a98c",
        "totalSize": 3590249,
        "abSize": 4528075,
    },
    PROJECTILE_BUNDLE_PATH: {
        "hash": "e320cabfc89a0555338d4bc1090ddcc4",
        "md5": "8ed77a0fb3c6e3cc1aad725dc8524ac6",
        "totalSize": 1546440,
        "abSize": 1857625,
    },
    FX_BUNDLE_PATH: {
        "hash": "1e7bd5d400068e30fd808c12ed43f130",
        "md5": "e137d4ef0d6f364abed29806d2d002d6",
        "totalSize": 2827028,
        "abSize": 3745304,
    },
}

DISASSEMBLY_METHODS = [
    "Torappu.Battle.Abilities.RangedAttack$$DoCastOnTargets",
    "Torappu.Battle.Abilities.RangedAttack$$OnCastOnTarget",
    "Torappu.Battle.Abilities.RangedAttack$$CreateProjectile",
    "Torappu.Battle.Abilities.RangedAttack$$GetTargetLocatable",
    "Torappu.Battle.Abilities.RangedAttack$$OnWaitForPostDelay",
    "Torappu.Battle.Abilities.RangedAttack$$OnCastEnd",
    "Torappu.Battle.Projectile$$Init",
    "Torappu.Battle.Projectile$$OnTick",
    "Torappu.Battle.Projectile$$OnProjectileReached",
    "Torappu.Battle.Projectile$$DealProjectileReached",
    "Torappu.Battle.Projectile$$DealHitTarget",
    "Torappu.Battle.SimpleProjectile$$GetLifeTime",
    "Torappu.Battle.SimpleProjectile$$GetMaxHitNum",
    "Torappu.Battle.Projectiles.AttachToTarget$$OnInit",
    "Torappu.Battle.Projectiles.AttachToTarget$$OnTick",
    "Torappu.Battle.Projectiles.HitBehaviour$$Init",
    "Torappu.Battle.Projectiles.HitBehaviour$$OnProjectileReached",
    "Torappu.Battle.Projectiles.HitBehaviour$$DealHitTarget",
    "Torappu.Battle.Projectiles.HitBehaviour$$OnTriggerEnter2D",
    "Torappu.Battle.AdvancedSelector$$OnPostFilter",
    "Torappu.Battle.Abilities.AbstractBasicAttack$$OnCastStart",
    "Torappu.Battle.Abilities.AbstractBasicAttack$$OnCastEnd",
    "Torappu.Battle.Enemy$$OnTick",
    "Torappu.Battle.Entity$$OnTick",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def register_lz4ak_decoder() -> None:
    sys_path = Path(__file__).resolve().parents[1] / "scripts"
    import sys

    if str(sys_path) not in sys.path:
        sys.path.insert(0, str(sys_path))
    from extract_m32_client_evidence_v1 import decompress_lz4ak

    CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak


def wrapper_name(logical_name: str) -> str:
    suffix_index = logical_name.rfind(".")
    stem = logical_name[:suffix_index] if suffix_index >= 0 else logical_name
    return stem.replace("/", "_") + ".dat"


def load_bundle(bundle_path: Path) -> tuple[UnityPy.Environment, dict[int, Any], dict[str, Any], str]:
    register_lz4ak_decoder()
    raw = bundle_path.read_bytes()
    environment = UnityPy.load(raw)
    objects = {obj.path_id: obj for obj in environment.objects}
    bundle = next(obj for obj in environment.objects if obj.type.name == "AssetBundle")
    container = dict(bundle.read_typetree()["m_Container"])
    serialized_file = next(
        value
        for value in environment.file.files.values()
        if type(value).__name__ == "SerializedFile"
    )
    return environment, objects, container, serialized_file.name


def serialized_identity(serialized_file_name: str, path_id: int) -> str:
    return f"{serialized_file_name}:{path_id}"


def object_summary(objects: dict[int, Any], path_id: int) -> dict[str, Any]:
    obj = objects[path_id]
    typetree = obj.read_typetree()
    return {
        "path_id": path_id,
        "type": obj.type.name,
        "name": typetree.get("m_Name", ""),
        "fields": typetree,
    }


def validate_resource(resource_dir: Path, logical_name: str) -> dict[str, Any]:
    wrapper = resource_dir / wrapper_name(logical_name)
    extracted_path = resource_dir / "downloads/v2_7_81" / logical_name
    record: dict[str, Any] = {
        "logical_path": logical_name,
        "wrapper_name": wrapper_name(logical_name),
        "wrapper_url": CDN_TEMPLATE.format(name=wrapper_name(logical_name)),
        "wrapper_exists": wrapper.exists(),
        "downloaded": extracted_path.exists(),
    }
    if wrapper.exists():
        wrapper_bytes = wrapper.read_bytes()
        record["wrapper_sha256"] = sha256_bytes(wrapper_bytes)
        with zipfile.ZipFile(io.BytesIO(wrapper_bytes)) as archive:
            members = archive.infolist()
            record["wrapper_members"] = [member.filename for member in members]
            if len(members) == 1 and members[0].filename == logical_name:
                member_bytes = archive.read(logical_name)
                record["member_md5"] = hashlib.md5(member_bytes).hexdigest()
                record["member_sha256"] = sha256_bytes(member_bytes)
                record["member_size"] = len(member_bytes)
                expected = RESOURCE_MANIFEST_ROWS.get(logical_name)
                if expected:
                    record["manifest_md5"] = expected["md5"]
                    record["manifest_ab_size"] = expected["abSize"]
                    record["manifest_md5_match"] = record["member_md5"] == expected["md5"]
                    record["manifest_size_match"] = record["member_size"] == expected["abSize"]
    if extracted_path.exists():
        member_bytes = extracted_path.read_bytes()
        record["member_sha256"] = sha256_bytes(member_bytes)
    return record


def collect_bundle_evidence(resource_dir: Path) -> dict[str, Any]:
    enemy_bundle = (
        resource_dir
        / "downloads/v2_7_81/battle_enm_pfb_6.dat.extract/battle/enm_pfb_6.ab"
    )
    projectile_bundle = (
        resource_dir
        / "downloads/v2_7_81/projectiles.extract/battle/prefabs/[uc]projectiles.ab"
    )
    fx_bundle = (
        resource_dir
        / "downloads/v2_7_81/pkgrps_btl_pfb_fx_enemy_5.dat.extract/pkgrps/btl_pfb_fx_enemy_5.ab"
    )
    _, enemy_objects, _, enemy_serialized = load_bundle(enemy_bundle)
    enemy_root = object_summary(enemy_objects, ENEMY_PATH_ID)
    components = [component["component"]["m_PathID"] for component in enemy_root["fields"]["m_Component"]]
    enemy_root["component_types"] = [
        enemy_objects[path_id].type.name for path_id in components
    ]
    mode = object_summary(enemy_objects, 5500900743873693051)
    combat = object_summary(enemy_objects, -3150289406525635205)
    selector = object_summary(enemy_objects, -1308437885939022469)
    scan_ability = object_summary(enemy_objects, -2578624576459176581)
    _, projectile_objects, _, projectile_serialized = load_bundle(projectile_bundle)
    projectile = object_summary(projectile_objects, PROJECTILE_PATH_ID)
    projectile_components = [
        component["component"]["m_PathID"] for component in projectile["fields"]["m_Component"]
    ]
    projectile["component_types"] = [
        projectile_objects[path_id].type.name for path_id in projectile_components
    ]
    projectile_children = {
        path_id: object_summary(projectile_objects, path_id)
        for path_id in projectile_components
        if projectile_objects[path_id].type.name == "MonoBehaviour"
    }
    _, fx_objects, fx_container, fx_serialized = load_bundle(fx_bundle)
    return {
        "enemy_bundle": {
            "path": str(enemy_bundle),
            "sha256": sha256_bytes(enemy_bundle.read_bytes()),
            "serialized_file": enemy_serialized,
            "prefab": serialized_identity(enemy_serialized, ENEMY_PATH_ID),
            "container": ENEMY_CONTAINER,
            "root": enemy_root,
            "mode": mode,
            "combat_ability": combat,
            "target_selector": selector,
            "scan_ability": scan_ability,
        },
        "projectile_bundle": {
            "path": str(projectile_bundle),
            "sha256": sha256_bytes(projectile_bundle.read_bytes()),
            "serialized_file": projectile_serialized,
            "prefab": serialized_identity(projectile_serialized, PROJECTILE_PATH_ID),
            "container": PROJECTILE_CONTAINER,
            "root": projectile,
            "components": projectile_children,
        },
        "fx_bundle": {
            "path": str(fx_bundle),
            "sha256": sha256_bytes(fx_bundle.read_bytes()),
            "serialized_file": fx_serialized,
            "emppnt_containers": {
                path: entry["asset"]
                for path, entry in fx_container.items()
                if "emppnt" in path.lower()
            },
        },
    }


def disassemble_method(
    library: bytes,
    method: dict[str, Any],
    method_addresses: list[int],
    symbol_by_address: dict[int, str],
) -> dict[str, Any]:
    import capstone

    start = int(method["Address"])
    end_index = bisect.bisect_right(method_addresses, start)
    end = method_addresses[end_index] if end_index < len(method_addresses) else len(library)
    disassembler = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    disassembler.skipdata = True
    lines: list[str] = []
    calls: list[str] = []
    for instruction in disassembler.disasm(library[start:end], start):
        line = f"{instruction.address:x}: {instruction.mnemonic:8} {instruction.op_str}"
        if instruction.mnemonic in {"b", "bl"}:
            try:
                target = int(instruction.op_str.lstrip("#"), 16)
            except ValueError:
                target = None
            if target in symbol_by_address:
                symbol = symbol_by_address[target]
                line += f" ; {symbol}"
                if instruction.mnemonic == "bl":
                    calls.append(symbol)
        lines.append(line)
    return {
        "name": method["Name"],
        "start": start,
        "end": end,
        "size": end - start,
        "direct_calls": list(dict.fromkeys(calls)),
        "disassembly": lines,
    }


def collect_behavior_evidence(dump_dir: Path, apk_dir: Path) -> dict[str, Any]:
    script_data = json.loads((dump_dir / "script.json").read_text(encoding="utf-8"))["ScriptMethod"]
    method_by_name = {method["Name"]: method for method in script_data}
    methods = [method_by_name[name] for name in DISASSEMBLY_METHODS if name in method_by_name]
    method_addresses = sorted({int(method["Address"]) for method in script_data})
    symbol_by_address = {int(method["Address"]): method["Name"] for method in script_data}
    library_path = apk_dir / "lib/arm64-v8a/libil2cpp.so"
    library = library_path.read_bytes()
    disassembly = [
        disassemble_method(library, method, method_addresses, symbol_by_address)
        for method in methods
    ]
    for method in disassembly:
        method.pop("disassembly")
    return {
        "library": {
            "path": str(library_path),
            "sha256": sha256_bytes(library),
        },
        "dump_cs_sha256": sha256_bytes((dump_dir / "dump.cs").read_bytes()),
        "script_json_sha256": sha256_bytes((dump_dir / "script.json").read_bytes()),
        "methods": disassembly,
    }


def collect_source_provenance(project_root: Path, apk_path: Path) -> dict[str, Any]:
    game_data_zip = project_root / "ArknightsGameData-master.zip"
    with zipfile.ZipFile(game_data_zip) as archive:
        game_data_commit = archive.comment.decode("ascii")
        files = {}
        for name in (
            "zh_CN/gamedata/levels/obt/main/level_main_08-07.json",
            "zh_CN/gamedata/levels/enemydata/enemy_database.json",
        ):
            data = archive.read(f"ArknightsGameData-master/{name}")
            files[name] = {"sha256": sha256_bytes(data), "size": len(data)}
    return {
        "build2771_apk": {
            "path": str(apk_path),
            "sha256": sha256_bytes(apk_path.read_bytes()),
            "size": apk_path.stat().st_size,
        },
        "build2771_resource_manifest": {
            "resource_version": "26-08-16-13-31-15_02805c",
            "idx_sha256": "11898eef33eecef9f4ac015863944df305531f8fcd6f0fa1d2274d5b0b23fad9",
            "signature_verification": "NOT_PERFORMED",
        },
        "game_data_zip": {
            "sha256": sha256_bytes(game_data_zip.read_bytes()),
            "commit": game_data_commit,
            "files": files,
        },
        "resource_version_comparison": {
            "production": "26-08-16-13-31-15_02805c",
            "migration_evidence": RESOURCE_VERSION,
            "same_version_facts_claimed": False,
        },
    }


def build_evidence(project_root: Path, apk_path: Path, resource_dir: Path, dump_dir: Path, apk_dir: Path) -> dict[str, Any]:
    hot_list_path = resource_dir / "hot_update_list_current.json"
    hot_list = json.loads(hot_list_path.read_text(encoding="utf-8"))
    present_rows = {
        row["name"]: row for row in hot_list["abInfos"] if row["name"] in RESOURCE_MANIFEST_ROWS
    }
    absent_rows = sorted(set(RESOURCE_MANIFEST_ROWS) - set(present_rows))
    resources = [
        validate_resource(resource_dir, name)
        for name in (
            ENEMY_BUNDLE_PATH,
            "refs/arts/enm_art_5.ab",
            "refs/arts/enm_art_6.ab",
            PROJECTILE_BUNDLE_PATH,
            FX_BUNDLE_PATH,
        )
    ]
    return {
        "schema_version": "M35_ARTILLERY_RESOURCE_BEHAVIOR_EVIDENCE_V1",
        "resource_version": RESOURCE_VERSION,
        "client_version": CLIENT_VERSION,
        "hot_list": {
            "path": str(hot_list_path),
            "sha256": sha256_bytes(hot_list_path.read_bytes()),
            "url": HOT_LIST_URL,
            "retrieved_at": HOT_LIST_RETRIEVED_AT,
            "version_id": hot_list.get("versionId"),
            "manifest_version": hot_list.get("manifestVersion"),
            "rows_requested": len(RESOURCE_MANIFEST_ROWS),
            "rows_present": len(present_rows),
            "rows_absent": absent_rows,
        },
        "resources": resources,
        "binding_evidence": collect_bundle_evidence(resource_dir),
        "behavior_evidence": collect_behavior_evidence(dump_dir, apk_dir),
        "source_provenance": collect_source_provenance(project_root, apk_path),
        "resource_version_source": {
            "url": VERSION_URL,
            "path": str(resource_dir / "version_current.json"),
            "sha256": sha256_bytes((resource_dir / "version_current.json").read_bytes()),
            "retrieved_at": VERSION_RETRIEVED_AT,
            "response": json.loads(
                (resource_dir / "version_current.json").read_text(encoding="utf-8")
            ),
        },
        "conclusion": {
            "migration_candidate_resource_chain": "CONFIRMED_FROM_RESOURCES",
            "build2771_enemy_body_bundle": "CURRENTLY_UNAVAILABLE",
            "build2771_behavior_chain": "NOT_CLAIMED",
            "signature_verification": "NOT_PERFORMED",
            "attack_interval_start_event": "PARTIALLY_UNKNOWN",
            "radius_1_2_semantics": "PROJECTILE_COLLIDER_AND_REACHED_TARGET_QUERY_INPUT",
            "runtime_change_required": "NO_CONFIRMED_CLIENT_BEHAVIOR_DIFFERENCE",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apk", type=Path, default=Path("arknights-hg-2771.apk"))
    parser.add_argument("--resource-dir", type=Path, default=Path("/tmp/m35_resource"))
    parser.add_argument("--dump-dir", type=Path, default=Path("/tmp/akdump5"))
    parser.add_argument("--apk-dir", type=Path, default=Path("/tmp/m33apk"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (
        args.project_root
        / "docs/review/fc77177/m35_artillery_resource_v1/artillery_resource_behavior_evidence.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence = build_evidence(
        args.project_root.resolve(),
        args.apk.resolve(),
        args.resource_dir.resolve(),
        args.dump_dir.resolve(),
        args.apk_dir.resolve(),
    )
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "bytes": output.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
