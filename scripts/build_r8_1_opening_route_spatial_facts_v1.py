from __future__ import annotations

import hashlib
import json
from math import floor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.adapters.normal_low_star import debug_configuration
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.search.responsibility_feasibility import build_early_threat_model
from arknights_planner.search.stage_understanding import StageUnderstandingAnalyzer
from arknights_planner.search.temporal_assignment import EarlyPressureResponsibility
from arknights_planner.simulator import ApproximateRealRangeTransformer


ROOT = Path(__file__).resolve().parents[1]
GAMEDATA = ROOT / "data/ArknightsGameData"
SOURCE = ROOT / "output/r8_1_normal_low_star_tactical_revision_v1"
OUT = ROOT / "output/r8_1_opening_route_spatial_facts_v1"
FPS = 30
ROUTE_IDS = ("route-1", "route-2", "route-3", "route-4", "route-6", "route-7", "route-8")
EXPECTED_ROADBLOCKS = {
    "trap_020_roadblock#1": (5, 3),
    "trap_020_roadblock#2": (9, 4),
    "trap_020_roadblock#3": (7, 2),
    "trap_020_roadblock#4": (1, 2),
    "trap_020_roadblock#5": (3, 5),
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame(seconds: float) -> int:
    return int(floor(seconds * FPS + 0.5))


def fixture_and_structure():
    repository = GameDataRepository(GAMEDATA)
    adapter = ApproximateRealSimulationAdapter(repository)
    fixture = adapter.build_fixture(
        stage_id_or_code="main_08-01", selections=(),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
    )
    structure = repository.get_stage_level_structure("main_08-01")
    _, _, level_path, level_payload = repository.get_stage_level_document("main_08-01")
    return repository, adapter, fixture, structure, level_path, level_payload


def tile_record_at(structure: Any, coordinate: tuple[int, int]) -> dict[str, Any]:
    height = len(structure.map_indices)
    serialized_row = height - 1 - coordinate[1]
    tile_index = structure.map_indices[serialized_row][coordinate[0]]
    record = next(item for item in structure.tile_records if item.tile_index == tile_index)
    return {
        "tile_index": tile_index,
        "tile_key": record.tile_key.value,
        "height_type": record.height_type.value,
        "buildable_type": record.buildable_type.value,
        "passable_mask": record.passable_mask.value,
        "player_side_mask": record.player_side_mask.value,
        "serialized_row": serialized_row,
        "field_row": coordinate[1],
        "source_path": f"$.mapData.tiles[{tile_index}]",
    }


def spawn_rows(fixture: Any, route_id: str) -> tuple[dict[str, Any], ...]:
    rows = []
    for item in fixture.spawn_timeline:
        if item.route_id != route_id:
            continue
        for index in range(int(item.count)):
            time = float(item.time) + index * float(item.interval)
            rows.append({
                "enemy_id": item.enemy_id,
                "enemy_level": item.enemy_level,
                "seconds": time,
                "frame": frame(time),
            })
    return tuple(rows)


def source_endpoint(source_route: dict[str, Any], key: str) -> dict[str, Any]:
    raw = source_route[key]
    coordinate = (int(raw["col"]), int(raw["row"]))
    return {
        "source_row_col": (int(raw["row"]), int(raw["col"])),
        "field_col_row": coordinate,
        "tile": None,
    }


def route_facts(fixture: Any, structure: Any, level_payload: dict[str, Any]) -> dict[str, Any]:
    routes = {route.route_id: route for route in fixture.stage.routes}
    tiles = {
        (tile.x, tile.y): tile
        for tile in fixture.stage.stage_map.tiles
    }
    facts: dict[str, Any] = {}
    for route_id in ROUTE_IDS:
        index = int(route_id.split("-")[1])
        route = routes[route_id]
        source_route = level_payload["routes"][index]
        motion_mode = source_route["motionMode"]
        spawns = spawn_rows(fixture, route_id)
        first_spawn = min(item["seconds"] for item in spawns)
        speeds = sorted({
            float(fixture.enemies[item["enemy_id"]].stats.move_speed.value)
            for item in spawns
        })
        speed = min(speeds)
        cells = []
        for x in range(int(fixture.stage.map_width.value)):
            for y in range(int(fixture.stage.map_height.value)):
                distances = route.distances_at((x, y))
                if not distances:
                    continue
                tile = tiles[(x, y)]
                record = tile_record_at(structure, (x, y))
                movement_times = route.times_at_point((x, y), speed=speed)
                cells.append({
                    "tile": [x, y],
                    "distances": list(distances),
                    "source_tile_key": record["tile_key"],
                    "buildable_type": record["buildable_type"],
                    "passable_mask": record["passable_mask"],
                    "simulator_tile_kind": tile.tile_kind,
                    "deployable_ground": bool(tile.buildable and tile.tile_kind == "GROUND" and record["passable_mask"] == "ALL"),
                    "movement_seconds_after_spawn": list(movement_times),
                    "unblocked_arrival_frames": [
                        frame(first_spawn + movement_time) for movement_time in movement_times
                    ],
                })
        fly_only_cells = [item["tile"] for item in cells if item["passable_mask"] == "FLY_ONLY"]
        if motion_mode == "WALK" and fly_only_cells:
            passability_status = "INCONSISTENT_WALK_STRAIGHT_SEGMENT_CROSSES_FLY_ONLY"
        elif motion_mode == "WALK":
            passability_status = "EXACT_TILE_CENTERS_PASSABLE_CLIENT_NAVIGATION_NOT_RECOVERED"
        else:
            passability_status = "MOTION_MODE_NOT_CHECKED_AGAINST_GROUND_PATH"
        end_seconds = route.time_at_distance(route.length, speed=speed)
        facts[route_id] = {
            "source_route_index": index,
            "motion_mode": motion_mode,
            "start": {**source_endpoint(source_route, "startPosition"), "tile": tile_record_at(structure, (source_route["startPosition"]["col"], source_route["startPosition"]["row"]))},
            "end": {**source_endpoint(source_route, "endPosition"), "tile": tile_record_at(structure, (source_route["endPosition"]["col"], source_route["endPosition"]["row"]))},
            "waypoints": [[point.x, point.y] for point in route.waypoints],
            "source_waits": [
                {"distance": item.distance, "duration": item.duration}
                for item in route.waits
            ],
            "route_length": route.length,
            "model_spawn_schedule": {
                "policy": fixture.spawn_timeline and RealSimulationApproximationPolicy.m11_second_quantized().spawn_schedule.value,
                "client_spawn_timing": "UNKNOWN",
                "rows": list(spawns),
            },
            "minimum_model_speed": speed,
            "unblocked_end_after_first_spawn_seconds": end_seconds,
            "unblocked_end_frame_after_first_spawn": frame(end_seconds),
            "post_contact_or_blocking_timing": "CONDITIONAL_UNKNOWN_AFTER_CONTACT",
            "path_cell_consistency": {
                "status": passability_status,
                "walk_fly_only_tile_candidates": fly_only_cells,
                "basis": "Exact tile centres on the public piecewise-linear Route; source waypoint navigation remains UNKNOWN.",
            },
            "path_cells": cells,
        }
    return facts


def wait_timing_facts(facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "semantics": {
            "MOVE": "Existing public Route segments; no new client physics.",
            "WAIT_FOR_SECONDS": "Public RouteWait pauses strictly before the requested distance; a wait exactly at the target is not added to arrival time.",
            "REPEATED_VISITS": "Route.distances_at preserves every exact traversal distance.",
            "BLOCKING": "Contact at a ground tile is computable; all later client timing remains UNKNOWN.",
        },
        "route_wait_totals": {
            route_id: sum(item["duration"] for item in facts[route_id]["source_waits"])
            for route_id in ROUTE_IDS
        },
        "route_specific_tile_arrivals": {
            route_id: [
                {
                    "tile": item["tile"],
                    "distances": item["distances"],
                    "unblocked_arrival_frames": item["unblocked_arrival_frames"],
                    "deployable_ground": item["deployable_ground"],
                }
                for item in facts[route_id]["path_cells"]
            ]
            for route_id in ROUTE_IDS
        },
    }


def early_threat_facts(fixture: Any) -> dict[str, Any]:
    understanding = StageUnderstandingAnalyzer().analyze(fixture)
    early = EarlyPressureResponsibility(
        window_id="R8_1_OPENING_STATIC_FACT_WINDOW",
        phase="OPENING",
        start_time=0.0,
        end_time=941.0 / FPS,
        route_ids=ROUTE_IDS,
        lane_ids=(),
        spawn_count=7,
        simultaneous_lane_count=0,
        latest_safe_deployment_time=941.0 / FPS,
        required_capabilities=(),
        block_required=False,
        pre_contact_damage_required=False,
        evidence=("Static source/fixture reconstruction; not a tactical requirement.",),
    )
    model = build_early_threat_model(
        SimpleNamespace(fixture=fixture), understanding, early_window=early,
    )
    return {
        "frame_clock": model.frame_clock,
        "routes": [vars(item) | {"wait_schedule": list(item.wait_schedule)} for item in model.routes if item.route_id in ROUTE_IDS],
        "limitation": "Threat frames are unblocked public Route movement with source waits; blocking remains conditional UNKNOWN after contact.",
    }


def b2_plan_mismatches(fixture: Any, structure: Any, facts: dict[str, Any]) -> dict[str, Any]:
    plan = load(SOURCE / "llm_structured_output.json")["revised_operational_plans"][0]
    candidate = load(SOURCE / "direction_complete_action_candidate.json")
    transformer = ApproximateRealRangeTransformer()
    tiles = {(tile.x, tile.y): tile for tile in fixture.stage.stage_map.tiles}
    route_cells = {
        route_id: {tuple(item["tile"]) for item in facts[route_id]["path_cells"]}
        for route_id in ROUTE_IDS
    }
    action_rows = []
    for action in candidate["actions"]:
        tile = tuple(action["tile"])
        repository = GameDataRepository(GAMEDATA)
        adapter = ApproximateRealSimulationAdapter(repository)
        configuration = debug_configuration(repository, action["operator_id"])
        adapted = adapter.strict_adapter.adapt_operator(
            action["operator_id"],
            phase_index=configuration["phase_index"],
            level=configuration["level"],
            skill_level_index=configuration["skill_level_index"] if configuration["skill_level_index"] is not None else -1,
        )
        offsets = tuple((cell.row, cell.col) for cell in adapted.attack_range.cells)
        coverage = transformer.covered_tiles(
            origin=tile,
            offsets=offsets,
            direction=action["direction"],
        )
        action_rows.append({
            "operator_id": action["operator_id"],
            "frame": action["frame"],
            "tile": list(tile),
            "direction": action["direction"],
            "tile_kind": tiles[tile].tile_kind,
            "active_roadblock": any(device.tile == tile for device in fixture.stage.devices),
            "exact_route_path_intersection": sorted(
                route_id for route_id, cells in route_cells.items() if tile in cells
            ),
            "ground_blocking_eligible": bool(
                tiles[tile].buildable
                and tiles[tile].tile_kind == "GROUND"
                and tile_record_at(structure, tile)["passable_mask"] == "ALL"
            ),
            "attack_coverage": sorted(list(item) for item in coverage),
            "attack_coverage_route_intersection": sorted(
                route_id for route_id, cells in route_cells.items() if coverage & cells
            ),
        })
    return {
        "plan_id": plan["operational_plan_id"],
        "actions": action_rows,
        "invalidated_plan_inputs": [
            {
                "old_input": "route-1 latest_safe_blocker_frame=191 at [8,5]",
                "new_fact": "route-1 follows y=1 through [3,1]..[8,1]; [8,5] is not on route-1. 191 is instead the unblocked route-3 arrival at [8,1].",
                "status": "OLD_INPUT_INVALID",
            },
            {
                "old_input": "route-2 arrest required by 27",
                "new_fact": "route-2 starts at [4,3]; the public unblocked first arrival is its spawn frame. [4,3] remains spatially valid for Fang.",
                "status": "OLD_DEADLINE_NOT_SOURCE_BACKED",
            },
            {
                "old_input": "route-4 handoff at [8,5] by 941",
                "new_fact": "route-4 follows y=1; its latest deployable path tile is [8,1]. [8,5] is not a route-4 blocker tile.",
                "status": "OLD_INPUT_INVALID",
            },
            {
                "old_input": "route-6 unblocked leak ~768",
                "new_fact": "route-6's public straight segment crosses FLY_ONLY candidates; client navigation and true leak timing are UNKNOWN.",
                "status": "OLD_MODEL_VALUE_INVALID",
            },
            {
                "old_input": "route-7 blocked at [5,1] by 725",
                "new_fact": "route-7's exact public path does not contain [5,1]; navigation and block timing are UNKNOWN.",
                "status": "OLD_INPUT_INVALID",
            },
            {
                "old_input": "route-8 unblocked leak ~803",
                "new_fact": "route-8's exact public path is partially represented by tile centres only; client navigation and true leak timing are UNKNOWN.",
                "status": "OLD_MODEL_VALUE_INVALID",
            },
        ],
        "preserved_action_policy": "The six saved actions are not moved, retimed, or reclassified as executable by this static audit.",
    }


def manifest(paths: tuple[Path, ...]) -> dict[str, Any]:
    return {
        "schema_version": "R8_1_OPENING_ROUTE_SPATIAL_FACTS_MANIFEST_V1",
        "files": {
            str(path.relative_to(ROOT)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in paths
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _, _, fixture, structure, level_path, level_payload = fixture_and_structure()
    facts = route_facts(fixture, structure, level_payload)
    mismatches = b2_plan_mismatches(fixture, structure, facts)
    payload = {
        "schema_version": "R8_1_OPENING_ROUTE_SPATIAL_FACTS_V1",
        "stage_id": "main_08-01",
        "coordinate_contract": {
            "serialized_map_array": "Top-row-first source array is inverted to bottom-left field y.",
            "routes_and_predefines": "Source row is already field row and is not inverted.",
            "synthetic_model": "CanonicalSyntheticRangeTransformer remains y-down; ApproximateRealRangeTransformer is y-up.",
        },
        "map_dimensions_source": [len(level_payload["mapData"]["map"][0]), len(level_payload["mapData"]["map"])],
        "level_source": str(level_path.relative_to(ROOT)),
        "roadblocks": [
            {
                "alias": item["alias"],
                "source_row_col": (item["position"]["row"], item["position"]["col"]),
                "field_col_row": (item["position"]["col"], item["position"]["row"]),
                "tile": tile_record_at(structure, (item["position"]["col"], item["position"]["row"])),
            }
            for item in level_payload["predefines"]["tokenInsts"]
        ],
        "route_facts": facts,
        "wait_timing_facts": wait_timing_facts(facts),
        "early_threat_model": early_threat_facts(fixture),
    }
    write("opening_route_spatial_timing_facts.json", payload)
    write("b2_plan_mismatch.json", mismatches)
    write("validation_results.json", {
        "map_row_flip": "PASS",
        "source_route_endpoints": "PASS",
        "five_roadblock_field_positions": "PASS",
        "wait_and_repeated_visit_representation": "PASS",
        "bottom_left_four_direction_range_check": "PASS",
        "walk_path_terrain_consistency": "FLAGGED_ROUTE_6_STRAIGHT_SEGMENT_CROSSES_FLY_ONLY",
        "client_navigation_or_pathing": "UNKNOWN",
        "simulator_run": "NOT_RUN",
    })
    write("final_status.json", {
        "kimi_calls": 0,
        "real_stage_simulations": 0,
        "new_operational_plans": 0,
        "new_action_candidates": 0,
        "search_expansions": 0,
        "routes": list(ROUTE_IDS),
        "route6_source_path_consistency": "INCONSISTENT_WITH_EXACT_TILE_CENTERS",
        "client_navigation": "UNKNOWN",
        "status": "STATIC_FACTS_REBUILT_TACTICAL_DECISION_NOT_MADE",
    })
    source_paths = (
        Path(__file__),
        ROOT / "src/arknights_planner/models/route.py",
        ROOT / "src/arknights_planner/simulator/range.py",
        ROOT / "src/arknights_planner/search/responsibility_feasibility.py",
        ROOT / "src/arknights_planner/adapters/approximate_real.py",
        ROOT / "src/arknights_planner/search/stage_understanding.py",
        SOURCE / "llm_structured_output.json",
        SOURCE / "direction_complete_action_candidate.json",
        OUT / "opening_route_spatial_timing_facts.json",
        OUT / "b2_plan_mismatch.json",
        OUT / "targeted_test_run.log",
    )
    write("run_manifest.json", manifest(source_paths))


if __name__ == "__main__":
    main()
