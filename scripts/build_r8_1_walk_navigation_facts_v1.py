from __future__ import annotations

import hashlib
import json
from math import floor, hypot
from pathlib import Path
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.route import Route, RouteWait, Waypoint
from arknights_planner.navigation import WalkNavigator


ROOT = Path(__file__).resolve().parents[1]
FALLBACK_LEVEL = ROOT / "output/r8_1_deadline_295_reclassification_v1/gamedata/level_main_08-01.json"
OUT = ROOT / "output/r8_1_walk_navigation_facts_v1"
ROUTE_INDEXES = (2, 3, 6, 7, 8)
ROADBLOCKS = {
    "trap_020_roadblock#1": (5, 3),
    "trap_020_roadblock#2": (9, 4),
    "trap_020_roadblock#3": (7, 2),
    "trap_020_roadblock#4": (1, 2),
    "trap_020_roadblock#5": (3, 5),
}


def write(name: str, payload: dict[str, Any]) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crossed_tiles(first: tuple[int, int], second: tuple[int, int]) -> set[tuple[int, int]]:
    """Tiles whose interior is crossed by the straight centre-to-centre segment."""
    first_row, first_col = first
    second_row, second_col = second
    result = {first, second}
    row_delta = second_row - first_row
    col_delta = second_col - first_col
    boundaries: list[tuple[float, list[tuple[int, int]]]] = []
    for index in range(1, abs(row_delta) + 1):
        boundary_row = first_row + index if row_delta > 0 else first_row - index
        boundary = (1, boundary_row - (1 if row_delta > 0 else 0))
        if boundaries and boundaries[-1][0] == index / abs(row_delta):
            boundaries[-1][1].append(boundary)
        else:
            boundaries.append((index / abs(row_delta), [boundary]))
    for index in range(1, abs(col_delta) + 1):
        boundary_col = first_col + index if col_delta > 0 else first_col - index
        boundary = (2, boundary_col - (1 if col_delta > 0 else 0))
        value = index / abs(col_delta)
        if boundaries and boundaries[-1][0] == value:
            boundaries[-1][1].append(boundary)
        else:
            boundaries.append((value, [boundary]))
    row = first_row
    col = first_col
    for _, updates in sorted(boundaries, key=lambda item: item[0]):
        for axis, boundary in updates:
            if axis == 1:
                row = boundary
            else:
                col = boundary
        result.add((row, col))
    return result


def terrain(level: dict[str, Any]) -> tuple[int, int, dict[tuple[int, int], str]]:
    serialized_rows = level["mapData"]["map"]
    tiles = level["mapData"]["tiles"]
    masks: dict[tuple[int, int], str] = {}
    for serialized_row, indices in enumerate(serialized_rows):
        for col, tile_index in enumerate(indices):
            masks[(len(serialized_rows) - 1 - serialized_row, col)] = tiles[tile_index]["passableMask"]
    return len(serialized_rows), len(serialized_rows[0]), masks


def route_targets(source_route: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    result = [(source_route["startPosition"]["row"], source_route["startPosition"]["col"])]
    result.extend(
        (checkpoint["position"]["row"], checkpoint["position"]["col"])
        for checkpoint in source_route.get("checkpoints") or []
        if checkpoint["type"] == "MOVE"
    )
    result.append((source_route["endPosition"]["row"], source_route["endPosition"]["col"]))
    return tuple(result)


def route_facts(
    level: dict[str, Any],
    route_index: int,
    obstacle_positions: set[tuple[int, int]] | None = None,
) -> dict[str, Any]:
    source_route = level["routes"][route_index]
    rows, columns, masks = terrain(level)
    passable = {coordinate for coordinate, mask in masks.items() if mask == "ALL"}
    obstacle_positions = obstacle_positions or set()
    navigator = WalkNavigator(
        rows,
        columns,
        passable.__contains__,
        obstacle_like=obstacle_positions.__contains__,
    )
    targets = route_targets(source_route)
    legs = [navigator.path(first, second) for first, second in zip(targets, targets[1:])]
    leg_lengths = [sum(hypot(second[0] - first[0], second[1] - first[1]) for first, second in zip(leg, leg[1:])) for leg in legs]

    waypoints: list[Waypoint] = []
    waits: list[RouteWait] = []
    target_index = 0
    for checkpoint in source_route.get("checkpoints") or []:
        if checkpoint["type"] == "MOVE":
            target_index += 1
        elif checkpoint["type"] == "WAIT_FOR_SECONDS":
            waits.append(RouteWait(sum(leg_lengths[:target_index]), float(checkpoint["time"])))
    for index, leg in enumerate(legs):
        leg_points = [Waypoint(float(col), float(row)) for row, col in leg]
        if index == 0:
            waypoints.extend(leg_points)
        else:
            waypoints.extend(leg_points[1:])
    route = Route(f"route-{route_index}", tuple(waypoints), tuple(waits))
    path_cells: set[tuple[int, int]] = set()
    fly_interior_crossings: list[tuple[float, float]] = []
    for leg in legs:
        for first, second in zip(leg, leg[1:]):
            cells = crossed_tiles(first, second)
            path_cells.update(cells)
            fly_interior_crossings.extend(
                (float(first[1] + (second[1] - first[1]) * fraction), float(first[0] + (second[0] - first[0]) * fraction))
                for cell in cells - {first, second}
                if masks[cell] == "FLY_ONLY"
                for fraction in (0.5,)
            )

    walk_cell_crossings: list[dict[str, Any]] = []
    for coordinate in sorted(path_cells):
        x, y = coordinate[1], coordinate[0]
        distances = route.distances_at((x, y))
        walk_cell_crossings.append(
            {
                "tile": [int(x), int(y)],
                "passable_mask": masks[coordinate],
                "route_distances": list(distances),
                "conditional_seconds_at_speed_1": [route.time_at_distance(item, speed=1.0) for item in distances],
                "wait_intersects": any(item in {wait.distance for wait in waits} for item in distances),
            }
        )

    return {
        "route_id": f"route-{route_index}",
        "source_route_index": route_index,
        "source_motion_mode": source_route["motionMode"],
        "source_allow_diagonal_move": source_route["allowDiagonalMove"],
        "source_start_row_col": list(targets[0]),
        "source_end_row_col": list(targets[-1]),
        "source_targets_row_col": [list(item) for item in targets],
        "source_navigation_flags": {
            "spawn_random_range": source_route["spawnRandomRange"],
            "spawn_offset": source_route["spawnOffset"],
            "visit_every_tile_center": source_route["visitEveryTileCenter"],
            "visit_every_node_center": source_route["visitEveryNodeCenter"],
            "visit_every_check_point": source_route["visitEveryCheckPoint"],
        },
        "source_checkpoints": [
            {
                "type": item["type"],
                "time": item["time"],
                "position_row_col": [item["position"]["row"], item["position"]["col"]],
                "reach_offset": item["reachOffset"],
                "randomize_reach_offset": item["randomizeReachOffset"],
                "reach_distance": item["reachDistance"],
            }
            for item in source_route.get("checkpoints") or []
        ],
        "source_waits": [
            {"distance": item.distance, "duration": item.duration}
            for item in waits
        ],
        "terrain_spfa_waypoints_col_row": [[int(item.x), int(item.y)] for item in route.waypoints],
        "terrain_spfa_length": route.length,
        "terrain_spfa_bresenham_path_cells": [item["tile"] for item in walk_cell_crossings],
        "terrain_spfa_cell_traversals": walk_cell_crossings,
        "fly_only_interior_crossings": fly_interior_crossings,
        "fly_only_interior_consistent": not fly_interior_crossings,
        "roadblock_interior_intersections": [
            item["tile"] for item in walk_cell_crossings if tuple(reversed(item["tile"])) in ROADBLOCKS.values()
        ],
    }


def adapter_check() -> dict[str, Any]:
    repository_path = ROOT / "data/ArknightsGameData"
    if not repository_path.is_dir():
        return {"status": "NOT_RUN", "reason": "data/ArknightsGameData is absent from checkout"}
    fixture = ApproximateRealSimulationAdapter(GameDataRepository(repository_path)).build_fixture(
        stage_id_or_code="main_08-01",
        selections=(),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
    )
    result = {}
    for route in fixture.stage.routes:
        if route.route_id not in {f"route-{index}" for index in ROUTE_INDEXES}:
            continue
        result[route.route_id] = {
            "waypoints_col_row": [[int(item.x), int(item.y)] for item in route.waypoints],
            "length": route.length,
            "waits": [{"distance": item.distance, "duration": item.duration} for item in route.waits],
        }
    return {"status": "PASS", "converted_routes": result}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    level = json.loads(FALLBACK_LEVEL.read_text(encoding="utf-8"))
    base_routes = {f"route-{index}": route_facts(level, index) for index in ROUTE_INDEXES}
    roadblock_positions = set(ROADBLOCKS.values())
    conditional_routes = {
        f"route-{index}": route_facts(level, index, roadblock_positions)
        for index in ROUTE_INDEXES
    }
    facts = {
        "schema_version": "R8_1_WALK_NAVIGATION_FACTS_V1",
        "stage_id": "main_08-01",
        "coordinate_convention": "Route and device source row/col are field bottom-left coordinates; mapData.map is top-row-first and inverted for tile lookup.",
        "routes": base_routes,
        "conditional_roadblock_as_full_obstacle_routes": conditional_routes,
        "roadblock_positions_row_col": [list(item) for item in sorted(ROADBLOCKS.values())],
        "status_classification": {
            "terrain_spfa_bresenham_model": "CONFIRMED_FROM_CODE",
            "fly_only_interior_consistency": "CONFIRMED_FROM_CODE",
            "route3_control": "CONFIRMED_FROM_CODE",
            "exact_client_path": "UNKNOWN",
            "roadblock_navigation_effect": "UNKNOWN",
            "wait_blocking_radius_and_priority": "UNKNOWN",
            "conditional_roadblock_variant": "HYPOTHESIS_NOT_CLIENT_FACT",
        },
        "limitations": [
            "Times are conditional unblocked model arrivals at 1 tile/second plus source waits; enemy speeds, client pre-roll and precise tick timing are not applied.",
            "No cell or conditional model time is a deployment hard deadline; blocking radius, wait priority and dynamic roadblock navigation remain unverified.",
            "The roadblock-as-full-obstacle variant is diagnostic only. GameData says roadblocks can block Ursa civilians and Talulah, but not that every WALK enemy treats them identically.",
            "Do not infer no real interception from absence of a route cell centre; use continuous crossing evidence only as a static terrain consistency check.",
        ],
    }
    write("walk_navigation_facts.json", facts)
    source_evidence = {
        "schema_version": "R8_1_WALK_NAVIGATION_SOURCE_EVIDENCE_V1",
        "fixed_gamedata_level": {
            "path": str(FALLBACK_LEVEL.relative_to(ROOT)),
            "sha256": sha256(FALLBACK_LEVEL),
            "field_paths": [
                "$.mapData.map",
                "$.mapData.tiles[*].passableMask",
                "$.routes[*].motionMode",
                "$.routes[*].allowDiagonalMove",
                "$.routes[*].checkpoints",
                "$.predefines.tokenInsts[*]",
            ],
        },
        "client_code_addresses": {
            "architecture": "arm64-v8a libil2cpp.so in ark build 2771; local sha256=3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259",
            "Tile.get_passableMask": "0x277f988",
            "Tile.IsPassable": "0x2782140",
            "Tile.IsPassableGoTo": "0x27821d0",
            "SPFA._GenerateNextMapImpl": "0x276b460",
            "SPFA._PostprocessAndMakeNextMapSmoothly": "0x276ba64",
            "SPFA._RaycastBresenhamLine": "0x276c500",
            "SPFA._RaycastSegmentLine": "0x276cc54",
            "Route.ReconstructRoute": "0x276d548",
        },
        "confirmed_semantics": [
            "MotionMask WALK=0, FLY=1; WALK uses passableMask ALL tiles (MotionMask enum at dump.cs lines 1437952-1437964).",
            "SPFA seeds the destination, relaxes four orthogonal neighbours with strict improvement and stores the first parent.",
            "Smoothing advances to the next parent only after a row/column or Bresenham raycast succeeds; a failed raycast does not overwrite the current candidate.",
            "Bresenham diagonal steps require both orthogonal side tiles clear.",
        ],
        "external_reference": "external/Stronghold-Protocol/docs/research/08-waves-official.md section 3.1 and server/sim/grid.js bresenhamClear/smoothChains",
        "prts_stage_reference": "https://prts.wiki/w/R8-1 describes roadblocks as blockable by Ursa civilians and Talulah and destroyable by player units.",
        "open_questions": [
            "Whether active trap_020_roadblock affects every WALK enemy's SPFA, only listed enemy types, or neither.",
            "Client exact corner/rounding handling at runtime and enemy collision radius.",
            "Blocking geometry and target precedence while waiting at a repeated cell.",
        ],
    }
    write("source_evidence.json", source_evidence)
    adapter = adapter_check()
    write("adapter_conversion_check.json", adapter)
    write(
        "final_status.json",
        {
            "status": "TERRAIN_NAVIGATION_RESTORED_ROADBLOCK_NAVIGATION_UNKNOWN",
            "kimi_calls": 0,
            "real_stage_simulations": 0,
            "new_operational_plans": 0,
            "new_action_candidates": 0,
            "tactical_search_expansions": 0,
            "routes_rebuilt": [f"route-{index}" for index in ROUTE_INDEXES],
            "fly_only_interior_consistent": all(item["fly_only_interior_consistent"] for item in base_routes.values()),
            "roadblock_navigation_effect": "UNKNOWN",
            "next_owner": "WORK_REVIEW",
        },
    )
    tracked_sources = [
        Path("scripts/build_r8_1_walk_navigation_facts_v1.py"),
        Path("src/arknights_planner/navigation.py"),
        Path("src/arknights_planner/adapters/approximate_real.py"),
        Path("src/arknights_planner/models/stage.py"),
        Path("src/arknights_planner/gamedata/repository.py"),
        Path("tests/test_walk_navigation_v1.py"),
        Path("tests/test_r8_1_walk_navigation_facts_v1.py"),
    ]
    artifacts = [
        "walk_navigation_facts.json",
        "source_evidence.json",
        "adapter_conversion_check.json",
        "final_status.json",
    ]
    manifest = {
        "schema_version": "R8_1_WALK_NAVIGATION_FACTS_MANIFEST_V1",
        "files": {},
    }
    for path in tracked_sources:
        absolute = ROOT / path
        manifest["files"][str(path)] = {
            "bytes": absolute.stat().st_size,
            "sha256": sha256(absolute),
        }
    for name in artifacts:
        absolute = OUT / name
        relative = absolute.relative_to(ROOT)
        manifest["files"][str(relative)] = {
            "bytes": absolute.stat().st_size,
            "sha256": sha256(absolute),
        }
    write("artifact_manifest.json", manifest)


if __name__ == "__main__":
    main()
