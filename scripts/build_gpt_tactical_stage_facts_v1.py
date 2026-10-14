from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata.repository import GameDataRepository
from run_r8_1_low_star_full_tactical_closure_v1 import (
    compact_operator_catalog,
    compact_source_routes,
    compact_wave_schedule,
    enemy_facts,
    output_schema,
)


ROOT = Path(__file__).resolve().parents[1]
GAMEDATA = ROOT / "data/ArknightsGameData"
LOW_STAR_PATH = ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json"
SUPPORT_PATH = ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json"
REFERENCE_CONTEXT = ROOT / "output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli/llm_evidence_context.json"
MECHANICS_VERSION = "m18.9-stage-device-runtime-v1"
GAMEDATA_COMMIT = "0ef7f952dfd018392200157a5c79a6511ba69122"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
    }


def active_stage_facts(stage_id: str) -> dict[str, Any]:
    fixture = ApproximateRealSimulationAdapter(GameDataRepository(GAMEDATA)).build_pool_fixture(
        stage_id_or_code=stage_id,
        configurations=(),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
    )
    stage = fixture.stage
    devices = [
        {
            "device_id": item.device_id,
            "template_id": item.template_id,
            "tile_col_row": [item.tile[0], item.tile[1]],
            "ordinary_targetable": item.ordinary_targetable,
        }
        for item in stage.devices
    ]
    routes = [
        {
            "route_id": item.route_id,
            "model_length": item.length,
            "waypoints_col_row": [[int(point.x), int(point.y)] for point in item.waypoints],
            "waits": [{"distance": wait.distance, "duration": wait.duration} for wait in item.waits],
        }
        for item in stage.routes
    ]
    occupied_tiles = {tuple(item.tile) for item in stage.devices}
    enemy_runtime = []
    for enemy_id, enemy in sorted(fixture.enemies.items()):
        stats = enemy.stats
        enemy_runtime.append(
            {
                "enemy_id": enemy_id,
                "ability_count": len(enemy.abilities),
                "attack_timing_evidence_class": enemy.attack_timing.evidence_class
                if enemy.attack_timing
                else "NONE",
                "supported_abilities": [item.ability_type for item in enemy.abilities],
                "is_friendly": stats.is_friendly.to_dict() if stats.is_friendly else None,
                "counts_as_kill": stats.counts_as_kill.to_dict() if stats.counts_as_kill else None,
                "counts_as_leak": stats.counts_as_leak.to_dict() if stats.counts_as_leak else None,
                "death_life_point_reduce": stats.death_life_point_reduce.to_dict() if stats.death_life_point_reduce else None,
                "operator_targetability": "UNKNOWN",
                "blockability": "UNKNOWN",
            }
        )
    return {
        "source": "GameData level plus ApproximateRealSimulationAdapter with RealSimulationApproximationPolicy.m11_second_quantized",
        "status": "CURRENT_PUBLIC_RUNTIME_ACTIVE_FACTS",
        "map_size_col_row": [stage.stage_map.width, stage.stage_map.height],
        "coordinate_conventions": {
            "game_data_predefines": "Named row and col fields in field bottom-left coordinates; do not invert route/device positions.",
            "serialized_map_array": "Serialized row is reversed for runtime tile conversion.",
            "active_fact_arrays": "Arrays named col_row are [x=col, y=row].",
            "plan_action_tile": "Plan/action JSON tile arrays are [row, col].",
            "compiler_runtime_action_tile": "Runtime Action.tile is (x=col,y=row), converted from [row,col] as (col,row).",
        },
        "active_device_tiles_col_row": [item["tile_col_row"] for item in devices],
        "roadblock_tiles_col_row": [
            item["tile_col_row"] for item in devices if item["template_id"] == "trap_020_roadblock"
        ],
        "roadblock_plan_tiles_row_col": [
            [item["tile_col_row"][1], item["tile_col_row"][0]]
            for item in devices if item["template_id"] == "trap_020_roadblock"
        ],
        "devices": devices,
        "terrain_ground_tiles_col_row": [
            [item.x, item.y] for item in stage.stage_map.tiles if item.tile_kind == "GROUND"
        ],
        "terrain_high_ground_tiles_col_row": [
            [item.x, item.y] for item in stage.stage_map.tiles if item.tile_kind == "HIGH_GROUND"
        ],
        "deployable_ground_tiles_col_row": sorted(
            [[item.x, item.y] for item in stage.stage_map.tiles
             if item.tile_kind == "GROUND" and (item.x, item.y) not in occupied_tiles]
        ),
        "deployable_high_ground_tiles_col_row": sorted(
            [[item.x, item.y] for item in stage.stage_map.tiles
             if item.tile_kind == "HIGH_GROUND" and (item.x, item.y) not in occupied_tiles]
        ),
        "runtime_adapter_routes": routes,
        "enemy_runtime": enemy_runtime,
    }


def spawn_timeline(stage_id: str) -> dict[str, Any]:
    fixture = ApproximateRealSimulationAdapter(GameDataRepository(GAMEDATA)).build_pool_fixture(
        stage_id_or_code=stage_id,
        configurations=(),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
    )
    events = [
        {
            "time_seconds": event.time,
            "frame_at_30fps": round(event.time * 30),
            "enemy_id": event.enemy_id,
            "route_id": event.route_id,
            "count": event.count,
            "interval_seconds": event.interval,
        }
        for event in fixture.spawn_timeline
    ]
    return {
        "status": "DIAGNOSTIC_MODEL_SCHEDULE_NOT_CLIENT_FACT",
        "policy": "HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED",
        "last_spawn_seconds": max((item["time_seconds"] for item in events), default=0.0),
        "events": events,
    }


def simulation_domain() -> dict[str, Any]:
    return {
        "action_clock": "30 FPS, frame/30 seconds",
        "natural_dp_model": "+1 DP per source costIncreaseTime second",
        "supported_action_types": ["DEPLOY", "ACTIVATE_SKILL", "RETREAT"],
        "supported_mechanics": [
            "source stats, deployment costs, ranges, blocking and ordinary attacks",
            "bounded source-backed manual ATK/DEF/attack-speed/heal skills",
            "attack-SP next-attack scaled-hit pattern",
            "deployment SP, deployment global heal, neutral self-cost talent, selected redeploy-time delta",
            "merchant upkeep",
            "active predefined device deployment occupancy",
            "ordinary low-star basic healing",
        ],
        "omitted_or_unknown_mechanics": [
            "exact client attack windup and integer rounding",
            "complete AoE splash geometry",
            "probability talents and target-order deviations",
            "unsupported talents and summons",
            "complex status effects",
            "active device effect on ordinary WALK navigation",
            "precise client wait/block priority",
            "stage-specific non-lifePointReduce loss mechanisms unless listed as supported",
        ],
    }


def build_context(stage_id: str) -> dict[str, Any]:
    repository = GameDataRepository(GAMEDATA)
    _, _, level_path, level = repository.get_stage_level_document(stage_id)
    reference = load(REFERENCE_CONTEXT)
    source_route_types = sorted({
        checkpoint["type"]
        for row in compact_source_routes(level)
        for checkpoint in row["checkpoints"]
    })
    runtime_supported_route_types = {"MOVE", "WAIT_FOR_SECONDS"}
    unsupported_route_types = sorted(set(source_route_types) - runtime_supported_route_types)
    adapter_blocked = bool(unsupported_route_types)
    semantics = []
    for item in enemy_facts(level):
        enemy = repository.get_enemy(item["enemy_id"], level=item["level"])
        stats = enemy.stats
        semantics.append({
            "enemy_id": item["enemy_id"],
            "is_friendly": stats.is_friendly.to_dict(),
            "counts_as_kill": stats.counts_as_kill.to_dict(),
            "counts_as_leak": stats.counts_as_leak.to_dict(),
            "death_life_point_reduce": stats.death_life_point_reduce.to_dict(),
            "operator_targetability": "UNKNOWN",
            "blockability": "UNKNOWN",
        })
    return {
        "schema_version": "GPT_TACTICAL_STAGE_FACTS_V1",
        "stage_id": stage_id,
        "mechanics_version": MECHANICS_VERSION,
        "gamedata_commit": GAMEDATA_COMMIT,
        "authoritative_policy": {
            "ordinary_mode_only": True,
            "rarity_range": [1, 3],
            "exclude_mode_specific_reserve_operators": True,
            "three_star_ordinary_catalog_count_must_be_17": True,
            "one_operational_plan": True,
            "full_stage_scope": True,
        },
        "base_rule_card": reference["base_rule_card"],
        "stage_options": {
            "deployment_limit": level["options"]["characterLimit"],
            "max_life_point": level["options"]["maxLifePoint"],
            "initial_cost": level["options"]["initialCost"],
            "max_cost": level["options"]["maxCost"],
            "cost_increase_time_seconds": level["options"]["costIncreaseTime"],
        },
        "enemy_facts": enemy_facts(level),
        "source_routes": compact_source_routes(level),
        "source_wave_schedule": compact_wave_schedule(level),
        "model_spawn_timeline": spawn_timeline(stage_id) if not adapter_blocked else {
            "status": "BLOCKED_UNSUPPORTED_ROUTE_CHECKPOINT",
            "unsupported_types": unsupported_route_types,
        },
        "stage_active_facts": active_stage_facts(stage_id) if not adapter_blocked else {
            "status": "SOURCE_ONLY_RUNTIME_ADAPTER_BLOCKED",
            "runtime_adapter_blockers": unsupported_route_types,
        },
        "normal_low_star_catalog": compact_operator_catalog(),
        "normal_low_star_support_counts": load(SUPPORT_PATH)["counts"],
        "simulation_domain": simulation_domain(),
        "stage_mechanism_support": {
            "raw_route_checkpoint_types": source_route_types,
            "runtime_adapter_supported_checkpoint_types": sorted(runtime_supported_route_types),
            "runtime_adapter_unsupported_checkpoint_types": unsupported_route_types,
            "runtime_adapter_status": "BLOCKED" if adapter_blocked else "OK",
            "enemy_semantics": semantics,
            "protected_target_arrival_semantics": "SOURCE_BACKED_NO_LIFE_DELTA",
            "protected_target_death_life_delta": "SOURCE_BACKED_BY_dead.value",
            "protected_target_kill_counting": "SOURCE_BACKED_NOT_COUNTED",
            "operator_targetability_of_friendly_units": "UNKNOWN",
            "friendly_unit_blocking": "UNKNOWN",
            "full_stage_result_support": "PARTIAL_SIMULATION_ONLY",
        },
        "hard_policy": {
            "ordinary_mode_only": True,
            "rarity_range": [1, 3],
            "exclude_mode_specific_reserve_operators": True,
            "one_operational_plan": True,
            "full_stage_scope": True,
            "do_not_require_complete_client_navigation_proof": True,
        },
        "provenance": {
            "raw_level": file_record(level_path),
            "operator_facts": file_record(LOW_STAR_PATH),
            "operator_support": file_record(SUPPORT_PATH),
            "generator": "scripts/build_gpt_tactical_stage_facts_v1.py",
        },
        "decision_task": {
            "deliverable": "one compact OperationalPlan JSON only",
            "must_cover": "all routes from first spawn to final WIN condition",
            "must_include": "route responsibilities, pressure windows, attack, healing, blocking, skills, retreats and handoffs",
        },
        "output_schema": output_schema(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-id", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    context = build_context(arguments.stage_id)
    out = ROOT / arguments.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "llm_evidence_context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "stage_id": arguments.stage_id,
        "bytes": len((out / "llm_evidence_context.json").read_bytes()),
        "routes": len(context["source_routes"]),
        "spawn_actions": sum(
            len(fragment["spawn_actions"])
            for fragment in context["source_wave_schedule"]["fragments"]
        ),
        "runtime_adapter_status": context["stage_mechanism_support"]["runtime_adapter_status"],
        "full_stage_result_support": context["stage_mechanism_support"]["full_stage_result_support"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
