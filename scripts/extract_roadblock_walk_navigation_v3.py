from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from pathlib import Path
from typing import Any


OUTPUT_DIR = Path("output/r8_1_roadblock_walk_navigation_v3")
LEVEL_PATH = Path("data/ArknightsGameData/zh_CN/gamedata/levels/obt/main/level_main_08-01.json")
GAMEDATA_COMMIT = "0ef7f952dfd018392200157a5c79a6511ba69122"
NATIVE_LIBRARY_SHA256 = "3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259"

METHODS: dict[str, tuple[int, int]] = {
    "Map.InitRouteAndPassableMap": (0x2755250, 0x27552E8),
    "Map._InitRoutesAndPassableMaps": (0x2753D58, 0x27541D0),
    "Map.ReplaceAllRoutes": (0x2755434, 0x2755774),
    "Map.UpdateAllRoutes": (0x2755774, 0x2755AFC),
    "Map.get_isBatchingTileUpdate": (0x2755AFC, 0x2755B74),
    "Map.AccumulateDirtyRoutes": (0x275615C, 0x27561F0),
    "Map.UpdateRoutes": (0x2755CE0, 0x275615C),
    "Map.EndBatchTileUpdate": (0x2755C24, 0x2755CE0),
    "SPFA.GenerateNextMap": (0x276AFD8, 0x276B460),
    "SPFA._GenerateNextMapImpl": (0x276B460, 0x276BA64),
    "SPFA.GenerateNextMapWithoutCaching": (0x276BC30, 0x276BD30),
    "SPFA.CheckPassableGoto": (0x276BD30, 0x276BDF4),
    "SPFA.CheckReachable": (0x276C044, 0x276C224),
    "SPFA._CheckCachedMapReachable": (0x276C224, 0x276C3A8),
    "SPFA.ClearCache": (0x276C3A8, 0x276C470),
    "SPFA.ClearAllCaches": (0x276C470, 0x276C500),
    "Route..ctor": (0x276D2E4, 0x276D4B8),
    "Route._CreateNextMap": (0x276D4B8, 0x276D548),
    "Route.ReconstructRoute": (0x276D548, 0x276D6EC),
    "Route.ReconstructNextMap": (0x276D6EC, 0x276D898),
    "Tile.Options": (0x27820D8, 0x2782140),
    "Tile.IsPassable": (0x2782140, 0x27821D0),
    "Tile.IsPassableGoto": (0x27821D0, 0x27822C0),
    "Tile.get_moveCost": (0x277BE88, 0x277BF00),
    "Tile.get_isObstacleLike": (0x277BF00, 0x277BF98),
    "Tile.OverwriteObstacleLikeMoveCost": (0x27825CC, 0x278264C),
    "Tile.RefreshTileOptionsViaToken": (0x2783DE4, 0x2783FBC),
    "Tile.TryUpdateOptions": (0x2785658, 0x2785804),
    "Tile.RewriteOptions": (0x2785804, 0x2785A44),
    "Tile.RestoreOptionsOnlyViaToken": (0x2786F58, 0x2787128),
}

INSTRUCTION_EDGES = {
    "Map._InitRoutesAndPassableMaps": [
        {"instruction": "0x2753ed0", "target": "0x2782140", "target_method": "Tile.IsPassable", "argument_flow": "tile, motion-bit 0 (WALK_ONLY)"},
        {"instruction": "0x2753f88", "target": "0x276ae38", "target_method": "SPFA..ctor", "argument_flow": "new SPFA(map)"},
        {"instruction": "0x275402c", "target": "0x276d2e4", "target_method": "Route..ctor", "argument_flow": "duplicated RouteData, Map, SPFA"},
        {"instruction": "0x2754138", "target": "0x276d2e4", "target_method": "Route..ctor", "argument_flow": "duplicated extra RouteData, Map, SPFA"},
        {"instruction": "0x275419c", "target": "0x2755774", "target_method": "Map.UpdateAllRoutes", "argument_flow": "this"},
    ],
    "Map.UpdateAllRoutes": [
        {"instruction": "0x275592c", "target": "0x276d6ec", "target_method": "Route.ReconstructNextMap", "argument_flow": "main route"},
        {"instruction": "0x2755980", "target": "0x276d6ec", "target_method": "Route.ReconstructNextMap", "argument_flow": "extra route"},
        {"instruction": "0x2755a58", "target": "0x276d6ec", "target_method": "Route.ReconstructNextMap", "argument_flow": "runtime route"},
        {"instruction": "0x2755ac4", "target": "0x276d6ec", "target_method": "Route.ReconstructNextMap", "argument_flow": "runtime extra route"},
    ],
    "Tile.RewriteOptions": [
        {"instruction": "0x27858a8", "target": "virtual Tile.get_moveCost", "target_method": "Tile.get_moveCost", "argument_flow": "tile before option rewrite"},
        {"instruction": "0x2785908", "target": "virtual Tile.get_moveCost", "target_method": "Tile.get_moveCost", "argument_flow": "tile after option rewrite"},
        {"instruction": "0x2785910", "target": "local compare", "target_method": "compare_old_vs_new_move_cost", "argument_flow": "old != new -> change bit"},
        {"instruction": "0x278593c", "target": "local compare", "target_method": "xor_passable_masks", "argument_flow": "((old ^ new) & 3)"},
        {"instruction": "0x278594c", "target": "0x2755afc", "target_method": "Map.get_isBatchingTileUpdate", "argument_flow": "this"},
        {"instruction": "0x2785968", "target": "0x275615c", "target_method": "Map.AccumulateDirtyRoutes", "argument_flow": "mask, when batching flag is true"},
        {"instruction": "0x2785998", "target": "0x2755ce0", "target_method": "Map.UpdateRoutes", "argument_flow": "WALK then FLY when batching flag is false"},
    ],
    "SPFA.GenerateNextMap": [
        {"instruction": "0x276b0b4", "target": "Dictionary.TryGetValue", "target_method": "cache_lookup", "argument_flow": "PathRequest key and motion-mode cache index"},
        {"instruction": "0x276b0c8", "target": "0x276b150", "target_method": "SPFA._LoadedCacheMap", "argument_flow": "cached map -> destination on cache hit"},
        {"instruction": "0x276b11c", "target": "0x276b460", "target_method": "SPFA._GenerateNextMapImpl", "argument_flow": "cache miss"},
        {"instruction": "0x276b130", "target": "0x276ba64", "target_method": "SPFA._PostprocessAndMakeNextMapSmoothly", "argument_flow": "after cache-miss generation"},
    ],
    "SPFA._GenerateNextMapImpl": [
        {"instruction": "0x276b714", "target": "0x2752f5c", "target_method": "Map.get_Item", "argument_flow": "request.targetPos"},
        {"instruction": "0x276b72c", "target": "0x2782140", "target_method": "Tile.IsPassable", "argument_flow": "start tile, request.motionMode"},
        {"instruction": "0x276b840", "target": "0x3f36ba4", "target_method": "GridPosition.op_Addition", "argument_flow": "node.pos + static neighbor direction"},
        {"instruction": "0x276b874", "target": "0x2752f5c", "target_method": "Map.get_Item", "argument_flow": "neighbor GridPosition"},
        {"instruction": "0x276b8e0", "target": "virtual SPFA.CheckPassableGoto", "target_method": "SPFA.CheckPassableGoto", "argument_flow": "neighbor tile, request, direction"},
        {"instruction": "0x276b940", "target": "virtual Tile.get_moveCost", "target_method": "Tile.get_moveCost", "argument_flow": "neighbor tile"},
        {"instruction": "0x276b988", "target": "local compare", "target_method": "relax_candidate_distance", "argument_flow": "candidate.distance = current.distance + tile.moveCost"},
    ],
    "SPFA.CheckReachable": [
        {"instruction": "0x276c170", "target": "Dictionary.TryGetValue", "target_method": "cache_lookup", "argument_flow": "request and motion-mode cache index"},
        {"instruction": "0x276c1e8", "target": "0x276afd8", "target_method": "SPFA.GenerateNextMap", "argument_flow": "cache miss"},
        {"instruction": "0x276c1fc", "target": "0x276c224", "target_method": "SPFA._CheckCachedMapReachable", "argument_flow": "cached or newly generated map, targetPos, avoidObstacleLike"},
    ],
    "SPFA._CheckCachedMapReachable": [
        {"instruction": "0x276c340", "target": "0x2752f5c", "target_method": "Map.get_Item", "argument_flow": "target GridPosition"},
        {"instruction": "0x276c374", "target": "virtual Tile.get_moveCost", "target_method": "Tile.get_moveCost", "argument_flow": "queried tile"},
        {"instruction": "0x276c378", "target": "local compare", "target_method": "cached_distance_minus_tile_moveCost_lt_1000", "argument_flow": "return cached_node.distance - tile.moveCost < 1000"},
    ],
    "Tile.TryUpdateOptions": [
        {"instruction": "0x2785714", "target": "local write", "target_method": "keep_current_passable_mask", "argument_flow": "old tile.passableMask -> Tile.Options.passableMask when requested"},
        {"instruction": "0x2785748", "target": "0x2785804", "target_method": "Tile.RewriteOptions", "argument_flow": "tile and Tile.Options"},
    ],
    "Tile.RestoreOptionsOnlyViaToken": [
        {"instruction": "0x2786ffc", "target": "0x2785804", "target_method": "Tile.RewriteOptions", "argument_flow": "saved original Tile.Options"},
        {"instruction": "0x2787024", "target": "local write", "target_method": "restore_passable_mask", "argument_flow": "original Tile.Options.passableMask"},
        {"instruction": "0x2787038", "target": "local write", "target_method": "restore_move_cost_state", "argument_flow": "original move-cost override and cost fields"},
        {"instruction": "0x2787054", "target": "local write", "target_method": "restore_height", "argument_flow": "original height"},
    ],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_decodability(instruction_count: int, consumed_bytes: int, total_bytes: int) -> dict[str, Any]:
    if total_bytes <= 0:
        raise ValueError("total_bytes must be positive")
    if instruction_count == 0:
        classification = "ENTRY_DECODE_FAILED"
        reason = "The default Capstone stream stopped at the first instruction without decoding any instruction."
    elif consumed_bytes < total_bytes:
        classification = "PARTIAL_DECODE"
        reason = "The default Capstone stream decoded a prefix and stopped before the requested end address."
    else:
        classification = "COMPLETE_DECODE"
        reason = "The default Capstone stream consumed the requested range."
    return {
        "classification": classification,
        "instruction_count": instruction_count,
        "consumed_bytes": consumed_bytes,
        "unconsumed_bytes": total_bytes - consumed_bytes,
        "reason": reason,
    }


def disassemble(native_library: Path, output_dir: Path) -> dict[str, dict[str, Any]]:
    try:
        import capstone
    except ImportError as exc:
        raise RuntimeError("capstone is required; install project optional dependency client-evidence") from exc

    raw = native_library.read_bytes()
    decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    lines: list[str] = []
    decodability: dict[str, dict[str, Any]] = {}
    for name, (start, end) in METHODS.items():
        data = raw[start:end]
        instructions = list(decoder.disasm(data, start))
        lines.append(f"=== {name} 0x{start:x}-0x{end:x} ===")
        lines.extend(
            f"{item.address:x}:\t{item.mnemonic}\t{item.op_str}".rstrip()
            for item in instructions
        )
        lines.append("")
        consumed_bytes = 0 if not instructions else instructions[-1].address + instructions[-1].size - start
        decodability[name] = classify_decodability(len(instructions), consumed_bytes, len(data))
    (output_dir / "ordinary_walk_navigation_disasm.txt").write_text("\n".join(lines), encoding="utf-8")
    return decodability


def summarize_routes() -> dict[str, Any]:
    level = json.loads(LEVEL_PATH.read_text(encoding="utf-8"))
    routes = level.get("routes") or []
    walk_routes = []
    for index, route in enumerate(routes):
        if not route or route.get("motionMode") != "WALK":
            continue
        walk_routes.append(
            {
                "source_route_index": index,
                "start_row_col": [route["startPosition"]["row"], route["startPosition"]["col"]],
                "end_row_col": [route["endPosition"]["row"], route["endPosition"]["col"]],
                "checkpoints": [
                    {
                        "type": checkpoint.get("type"),
                        "position_row_col": [checkpoint["position"]["row"], checkpoint["position"]["col"]],
                        "time": checkpoint.get("time"),
                    }
                    for checkpoint in (route.get("checkpoints") or [])
                ],
            }
        )
    return {
        "level_path": str(LEVEL_PATH),
        "gamedata_commit": GAMEDATA_COMMIT,
        "source_route_count": len(routes),
        "source_motion_mode_counts": {
            mode: sum(bool(route and route.get("motionMode") == mode) for route in routes)
            for mode in ("WALK", "E_NUM")
        },
        "walk_routes": walk_routes,
    }


def build_evidence(native_library: Path, output_dir: Path, decodability: dict[str, str]) -> dict[str, Any]:
    r8_routes = summarize_routes()
    chain = [
        {
            "edge": "LevelData.routes -> Map.InitRouteAndPassableMap -> Map._InitRoutesAndPassableMaps",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x27552cc..0x27552e0", "0x2753d58"],
        },
        {
            "edge": "Map._InitRoutesAndPassableMaps -> Tile.IsPassable(tile, WALK_ONLY)",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x2753ed0", "0x2782140"],
            "argument_flow": "the loop stores bit 0 of Tile.IsPassable(tile, 0), and MotionMask.WALK_ONLY == 1",
        },
        {
            "edge": "Map._InitRoutesAndPassableMaps -> SPFA..ctor(map)",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x2753f88", "0x276ae38"],
        },
        {
            "edge": "Map._InitRoutesAndPassableMaps -> Route..ctor(RouteData, Map, SPFA) for main and extra routes",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x275402c", "0x2754138", "0x276d2e4"],
        },
        {
            "edge": "Map._InitRoutesAndPassableMaps -> Map.UpdateAllRoutes",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x275419c", "0x2755774"],
        },
        {
            "edge": "Map.UpdateAllRoutes -> Route.ReconstructNextMap",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x275592c", "0x2755980", "0x2755a58", "0x2755ac4"],
        },
        {
            "edge": "Route.ReconstructNextMap -> SPFA path generation",
            "status": "UNKNOWN_MISSING_STATIC_EDGE",
            "reason": "Default Capstone entry decoding fails at the start of Route..ctor, ReconstructRoute and ReconstructNextMap; method signatures and stored SPFA reference are not enough to prove the call. This does not prove that every aligned word in the ranges is invalid.",
            "evidence": ["0x276d2e4", "0x276d548", "0x276d6ec"],
        },
        {
            "edge": "SPFA.GenerateNextMap -> cached-map load or SPFA._GenerateNextMapImpl + postprocess",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x276b0b4", "0x276b0c8", "0x276b11c", "0x276b130"],
        },
        {
            "edge": "SPFA._GenerateNextMapImpl -> Tile.IsPassable / SPFA.CheckPassableGoto / Tile.get_moveCost",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x276b72c", "0x276b8e0", "0x276b940"],
            "argument_flow": "request.motionMode selects the passable bit; each neighbor's Tile.get_moveCost is added to candidate distance.",
        },
        {
            "edge": "Tile.RewriteOptions -> change bits and Map.UpdateRoutes/AccumulateDirtyRoutes",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x2785910", "0x278593c", "0x278594c", "0x2785968", "0x2785998"],
        },
        {
            "edge": "Tile.RestoreOptionsOnlyViaToken -> Tile.RewriteOptions with saved options",
            "status": "CONFIRMED_FROM_CODE",
            "evidence": ["0x2786ffc", "0x2787024", "0x2787038", "0x2787054"],
        },
    ]
    return {
        "schema_version": "R8_1_ROADBLOCK_WALK_NAVIGATION_V3",
        "budget": {
            "kimi_calls": 0,
            "real_stage_simulations": 0,
            "new_operational_plans": 0,
            "new_action_candidates": 0,
            "expanded_tactical_search": 0,
        },
        "inputs": {
            "native_library_sha256": sha256(native_library),
            "expected_native_library_sha256": NATIVE_LIBRARY_SHA256,
            "gamedata_commit": GAMEDATA_COMMIT,
            "level_sha256": sha256(LEVEL_PATH),
            "prior_prefab_evidence": {
                "path": "output/r8_1_roadblock_prefab_evidence_v2/roadblock_prefab_extraction.json",
                "sha256": sha256(Path("output/r8_1_roadblock_prefab_evidence_v2/roadblock_prefab_extraction.json")),
            },
        },
        "corrections": [
            {
                "old_label": "NOT_TRIGGERED_FOR_UNCHANGED_WALK_FLY_MASK",
                "validity": "FALSE",
                "corrected": "A moveCost-only change produces a change bit; Tile.RewriteOptions compares virtual get_moveCost before and after and ORs that bit with the passable-mask XOR.",
                "scope": "Static call in build 2771. Does not imply immediate refresh in every runtime state.",
                "evidence": ["0x2785908..0x2785914", "0x278593c..0x2785948"],
            },
            {
                "old_label": "FALSE_IF_AVOID_OBSTACLE_LIKE_IS_TRUE",
                "validity": "OVERGENERALIZED",
                "corrected": "SPFA._CheckCachedMapReachable returns cached_node.distance - queried_tile.get_moveCost() < 1000. Example cached=1000,tile=1000 returns true; cached=1001,tile=1 returns false.",
                "scope": "This is CheckReachable arithmetic, not ordinary path generation, and no R8-1 reachable scenario is proven here.",
                "evidence": ["0x276c374..0x276c380"],
            },
        ],
        "ordinary_walk_navigation": {
            "passability": "Tile.IsPassableGoto checks Tile.IsPassable(tile, motionMode) and the tile's per-mode block-edge bits.",
            "path_generation_cost": "SPFA._GenerateNextMapImpl adds each accepted neighbor's virtual Tile.get_moveCost to the candidate node distance.",
            "route_refresh_signal": "moveCost change and passableMask XOR are combined into dirty bits.",
            "route_refresh_scheduling": {
                "map_is_batching_tile_update_false": "Tile.RewriteOptions loops WALK and FLY and calls Map.UpdateRoutes(mode).",
                "map_is_batching_tile_update_true": "Tile.RewriteOptions calls Map.AccumulateDirtyRoutes(mask); Map.EndBatchTileUpdate later calls Map.UpdateRoutes for accumulated bits.",
            },
            "avoid_obstacle_like": "CheckReachable/_CheckCachedMapReachable evaluates cached_node.distance - queried_tile.get_moveCost() < 1000; its R8-1 ordinary-route applicability is UNKNOWN.",
            "destruction_restore": "Tile.RestoreOptionsOnlyViaToken calls Tile.RewriteOptions with saved original Tile.Options and conditionally restores individual fields.",
            "chain": chain,
            "route_decodability": decodability,
        },
        "r8_1_route_scope": r8_routes,
        "limitations": [
            "The supplied client binary cannot be independently aligned to the pinned GameData commit beyond fixed source hashes and method address evidence.",
            "Default Capstone entry decoding fails for the Route methods; the missing Route-to-SPFA edge remains UNKNOWN and the cause is not established.",
            "No active roadblock state transition or tap_roadblock binding is proven in this artifact.",
        ],
        "conclusion_scope": "PARTIAL_STATIC_EVIDENCE; no faithful R8-1 navigation or tactical feasibility claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("native_library", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if sha256(args.native_library) != NATIVE_LIBRARY_SHA256:
        raise RuntimeError("native library hash does not match the pinned build")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    decodability = disassemble(args.native_library, args.output_dir)
    evidence = build_evidence(args.native_library, args.output_dir, decodability)
    (args.output_dir / "ordinary_walk_navigation_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    provenance = [
        "Source: data/client/lib/arm64-v8a/libil2cpp.so from arknights-hg-2771.apk.",
        "Command: PYTHONPATH=<capstone> python3 scripts/extract_roadblock_walk_navigation_v3.py data/client/lib/arm64-v8a/libil2cpp.so",
        "GameData: fixed commit 0ef7f952dfd018392200157a5c79a6511ba69122.",
        "Tool: Capstone AArch64 disassembler. Cross-version applicability remains UNKNOWN.",
        "No APK bundle, client binary, metadata file, credential, or full tactical simulation is uploaded by this generator.",
    ]
    (args.output_dir / "provenance.txt").write_text("\n".join(provenance) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "ARTIFACT_MANIFEST_V1",
        "files": [
            {"path": path.name, "sha256": sha256(path)}
            for path in sorted(args.output_dir.iterdir(), key=lambda item: item.name)
            if path.name != "manifest.json"
        ],
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
