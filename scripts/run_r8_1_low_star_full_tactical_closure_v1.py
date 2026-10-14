from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from jsonschema import Draft7Validator
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from kimi_responses_transport import (  # noqa: E402
    StreamAccumulator,
    extract_response_text,
    validate_tactical_request,
)

OUT = ROOT / "output/r8_1_low_star_full_tactical_closure_v2"
GAMEDATA = ROOT / "data/ArknightsGameData"
BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/responses"
MODEL = "kimi-k3"
MECHANICS = "m18.9-stage-device-runtime-v1"
TIMEOUT_SECONDS = 900
STAGE_ID = "main_08-01"
ROADBLOCK_TILES_COL_ROW = [[5, 3], [9, 4], [7, 2], [1, 2], [3, 5]]
OUTPUT_TOKEN_LIMIT = 32768
LEVEL_PATH = GAMEDATA / "zh_CN/gamedata/levels/obt/main/level_main_08-01.json"
CONTEXT_PATH = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
LOW_STAR_PATH = ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json"
SUPPORT_PATH = ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json"
NAVIGATION_PATH = ROOT / "output/r8_1_walk_navigation_facts_v1/walk_navigation_facts.json"
PREVIOUS_PLAN_PATH = ROOT / "output/r8_1_normal_low_star_tactical_revision_v1/llm_structured_output.json"
PREVIOUS_ACTIONS_PATH = ROOT / "output/r8_1_normal_low_star_tactical_revision_v1/direction_complete_action_candidate.json"
PREVIOUS_DIAGNOSTIC_PATH = ROOT / "output/r8_1_low_star_fixed_prefix_diagnostic_v1/diagnostic_summary.json"
PREVIOUS_FEEDBACK_PATH = ROOT / "docs/review/48fa985/feedback_qualifications.json"
ROADBLOCK_EVIDENCE_PATH = ROOT / "output/r8_1_roadblock_prefab_evidence_v2/roadblock_prefab_extraction.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def source_manifest() -> dict[str, Any]:
    paths = [
        LEVEL_PATH,
        CONTEXT_PATH,
        LOW_STAR_PATH,
        SUPPORT_PATH,
        NAVIGATION_PATH,
        PREVIOUS_PLAN_PATH,
        PREVIOUS_ACTIONS_PATH,
        PREVIOUS_DIAGNOSTIC_PATH,
        PREVIOUS_FEEDBACK_PATH,
        ROADBLOCK_EVIDENCE_PATH,
        ROOT / "scripts/kimi_responses_transport.py",
        Path(__file__),
    ]
    return {
        "generation_code": {"sha256": sha256(Path(__file__)), "source": "scripts/run_r8_1_low_star_full_tactical_closure_v1.py"},
        "inputs": {str(path.relative_to(ROOT)): file_record(path) for path in paths},
        "mechanics_version": MECHANICS,
        "schema_version": "R8_1_LOW_STAR_FULL_TACTICAL_CLOSURE_V2_SOURCE_MANIFEST",
    }


def enemy_facts(level: dict[str, Any]) -> list[dict[str, Any]]:
    enemy_path = GAMEDATA / "zh_CN/gamedata/levels/enemydata/enemy_database.json"
    database = load(enemy_path)
    def value(item: Any) -> Any:
        return item.get("m_value") if isinstance(item, dict) and "m_value" in item else item

    rows = []
    for reference in level["enemyDbRefs"]:
        record = next(item for item in database["enemies"] if item["Key"] == reference["id"])
        variant = next(item for item in record["Value"] if item["level"] == reference["level"])
        raw = variant["enemyData"]
        attributes = raw["attributes"]
        rows.append(
            {
                "enemy_id": reference["id"],
                "level": reference["level"],
                "overwritten_data": reference.get("overwrittenData"),
                "max_hp": value(attributes["maxHp"]),
                "atk": value(attributes["atk"]),
                "defense": value(attributes["def"]),
                "magic_resistance": value(attributes["magicResistance"]),
                "move_speed": value(attributes["moveSpeed"]),
                "attack_interval": value(attributes["baseAttackTime"]),
                "attack_speed": value(attributes["attackSpeed"]),
                "life_point_reduce": value(raw.get("lifePointReduce")),
                "apply_way": value(raw["applyWay"]),
                "source_path": f"$.enemies[Key={reference['id']}].Value[level={reference['level']}].enemyData",
            }
        )
    return rows


def compact_source_routes(level: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for route_index, route in enumerate(level.get("routes") or []):
        rows.append(
            {
                "route_id": f"route-{route_index}",
                "source_route_index": route_index,
                "motion_mode": route.get("motionMode"),
                "start_row_col": [route["startPosition"]["row"], route["startPosition"]["col"]],
                "end_row_col": [route["endPosition"]["row"], route["endPosition"]["col"]],
                "allow_diagonal_move": route.get("allowDiagonalMove", False),
                "checkpoints": [
                    {
                        "type": checkpoint.get("type"),
                        "position_row_col": [checkpoint["position"]["row"], checkpoint["position"]["col"]],
                        "time_seconds": checkpoint.get("time"),
                    }
                    for checkpoint in (route.get("checkpoints") or [])
                ],
            }
        )
    return rows


def compact_wave_schedule(level: dict[str, Any]) -> dict[str, Any]:
    waves = level.get("waves") or []
    fragments = []
    for fragment_index, fragment in enumerate(waves[0].get("fragments") or []):
        actions = []
        for action in fragment.get("actions") or []:
            if action.get("actionType") == "SPAWN":
                actions.append(
                    {
                        "action_type": action["actionType"],
                        "enemy_id": action["key"],
                        "count": action["count"],
                        "route_id": f"route-{action['routeIndex']}",
                        "source_route_index": action["routeIndex"],
                        "pre_delay_seconds": action.get("preDelay"),
                        "interval_seconds": action.get("interval"),
                    }
                )
        fragments.append({"fragment_index": fragment_index, "pre_delay_seconds": fragment.get("preDelay"), "spawn_actions": actions})
    return {
        "source_path": "$.waves[0].fragments[*]",
        "source_semantics": "preDelay and interval are exact source offsets; the simulator applies its fixed hierarchical second-quantized policy.",
        "wave_count": len(waves),
        "fragments": fragments,
    }


def compact_operator_catalog() -> list[dict[str, Any]]:
    facts = load(LOW_STAR_PATH)
    support = load(SUPPORT_PATH)
    support_by_id = {item["operator_id"]: item for item in support["operators"]}
    rows = []
    for operator in facts["operators"]:
        support_row = support_by_id[operator["operator_id"]]
        rows.append(
            {
                "operator_id": operator["operator_id"],
                "name": operator["name"],
                "qualification": operator["qualification"],
                "identity": operator["identity"],
                "debug_configuration": operator["debug_configuration"],
                "stats": operator["stats"],
                "range": operator["range"],
                "normal_attack": operator["normal_attack"],
                "selected_skills": operator.get("skills") or [],
                "talents": operator.get("talents") or [],
                "runtime_support": {
                    "overall": support_row.get("overall"),
                    "base_stats": support_row.get("base_stats"),
                    "normal_attack": support_row.get("normal_attack"),
                    "skills": support_row.get("skills"),
                    "talent": support_row.get("talent"),
                    "deployment_sp_bonus": support_row.get("deployment_sp_bonus"),
                    "deployment_heal_all_value": support_row.get("deployment_heal_all_value"),
                },
            }
        )
    return rows


def compact_navigation_facts() -> dict[str, Any]:
    source = load(NAVIGATION_PATH)
    routes = {}
    for route_id, route in source["routes"].items():
        routes[route_id] = {
            "source_route_index": route["source_route_index"],
            "source_start_row_col": route["source_start_row_col"],
            "source_end_row_col": route["source_end_row_col"],
            "source_motion_mode": route["source_motion_mode"],
            "source_checkpoints": route["source_checkpoints"],
            "source_waits": route["source_waits"],
            "terrain_spfa_waypoints_col_row": route["terrain_spfa_waypoints_col_row"],
            "terrain_spfa_path_cells": route.get("terrain_spfa_path_cells", []),
            "terrain_spfa_cell_traversals": route.get("terrain_spfa_cell_traversals", []),
            "terrain_spfa_length": route["terrain_spfa_length"],
            "roadblock_interior_intersections": route["roadblock_interior_intersections"],
            "fly_only_interior_consistent": route["fly_only_interior_consistent"],
        }
    return {
        "status_classification": source["status_classification"],
        "coordinate_convention": source["coordinate_convention"],
        "roadblock_positions_row_col": source["roadblock_positions_row_col"],
        "routes": routes,
        "limitations": source["limitations"],
    }


def model_spawn_timeline() -> dict[str, Any]:
    from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
    from arknights_planner.gamedata.repository import GameDataRepository

    repository = GameDataRepository(GAMEDATA)
    fixture = ApproximateRealSimulationAdapter(repository).build_pool_fixture(
        stage_id_or_code=STAGE_ID,
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
        "last_spawn_seconds": max((event["time_seconds"] for event in events), default=0.0),
        "events": events,
    }


def runtime_stage_active_facts() -> dict[str, Any]:
    from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
    from arknights_planner.gamedata.repository import GameDataRepository

    repository = GameDataRepository(GAMEDATA)
    fixture = ApproximateRealSimulationAdapter(repository).build_pool_fixture(
        stage_id_or_code=STAGE_ID,
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
    ground_tiles = [[item.x, item.y] for item in stage.stage_map.tiles if item.tile_kind == "GROUND"]
    high_ground_tiles = [[item.x, item.y] for item in stage.stage_map.tiles if item.tile_kind == "HIGH_GROUND"]
    roadblocks = [item for item in devices if item["template_id"] == "trap_020_roadblock"]
    if sorted(item["tile_col_row"] for item in roadblocks) != sorted(ROADBLOCK_TILES_COL_ROW):
        raise RuntimeError("active roadblock facts do not match the fixed source contract")
    return {
        "source": "GameData level plus ApproximateRealSimulationAdapter with RealSimulationApproximationPolicy.m11_second_quantized",
        "status": "CURRENT_PUBLIC_RUNTIME_ACTIVE_FACTS",
        "map_size_col_row": [stage.stage_map.width, stage.stage_map.height],
        "coordinate_conventions": {
            "game_data_predefines": "Named row and col fields in field bottom-left coordinates; do not invert route/device positions.",
            "serialized_map_array": "Serialized row is reversed for runtime tile conversion.",
            "active_fact_arrays": "Arrays named col_row are [x=col, y=row].",
            "kimi_action_tile": "Plan/action JSON tile arrays are [row, col].",
            "compiler_runtime_action_tile": "Runtime Action.tile is (x=col, y=row), converted from [row,col] as (col,row).",
        },
        "roadblock_tiles_col_row": ROADBLOCK_TILES_COL_ROW,
        "active_device_tiles_col_row": [item["tile_col_row"] for item in devices],
        "devices": devices,
        "deployable_ground_tiles_col_row": ground_tiles,
        "deployable_high_ground_tiles_col_row": high_ground_tiles,
        "runtime_adapter_routes": routes,
    }


def evidence_context() -> dict[str, Any]:
    level = load(LEVEL_PATH)
    options = level["options"]
    active_facts = runtime_stage_active_facts()
    return {
        "milestone": "R8_1_LOW_STAR_FULL_TACTICAL_CLOSURE_V2",
        "stage_id": STAGE_ID,
        "mechanics_version": MECHANICS,
        "gamedata_commit": "0ef7f952dfd018392200157a5c79a6511ba69122",
        "stage_options": {
            "deployment_limit": options["characterLimit"],
            "max_life_point": options["maxLifePoint"],
            "initial_cost": options["initialCost"],
            "max_cost": options["maxCost"],
            "cost_increase_time_seconds": options["costIncreaseTime"],
        },
        "enemy_facts": enemy_facts(level),
        "source_routes": compact_source_routes(level),
        "source_wave_schedule": compact_wave_schedule(level),
        "model_spawn_timeline": model_spawn_timeline(),
        "stage_active_facts": active_facts,
        "historical_context_not_active": {
            "status": "HISTORICAL_ONLY_DO_NOT_USE_AS_ACTIVE_FACTS",
            "records": {
                "old_deterministic_context": file_record(CONTEXT_PATH),
                "old_b2_plan": file_record(PREVIOUS_PLAN_PATH),
                "old_b2_action_candidate": file_record(PREVIOUS_ACTIONS_PATH),
                "old_b2_diagnostic": file_record(PREVIOUS_DIAGNOSTIC_PATH),
                "old_route_feedback_qualifications": file_record(PREVIOUS_FEEDBACK_PATH),
                "historical_walk_navigation_facts": file_record(NAVIGATION_PATH),
            },
            "invalidated_conclusions": [
                "Old deterministic opening-pressure conclusions, including the [8,5] / frame 191 anchor and related deadlines, are not active facts.",
                "The old B2 frame-941 zero-leak diagnostic is not an active tactical baseline; it was affected by coordinate, WAIT, high-ground blocking and clock defects.",
                "Old labels naming [col,row] arrays as row_col are invalid; use the explicit active coordinate conventions.",
            ],
            "reusable_non_tactical_lessons": [
                "Merchant upkeep is real: 3 DP every 3 seconds, auto-retreat on insufficient DP, no confirmed refund.",
                "Exact first merchant-upkeep debit remains UNKNOWN.",
                "Active roadblocks block deployment; their ordinary-WALK navigation effect remains UNKNOWN.",
                "4-star and 5-star units from older plans are outside the current 1-3 star domain.",
            ],
        },
        "normal_low_star_catalog": compact_operator_catalog(),
        "normal_low_star_support_counts": load(SUPPORT_PATH)["counts"],
        "roadblock_evidence": {
            "passable_mask": 0,
            "keep_current_passable_mask": True,
            "override_obstacle_like_move_cost": True,
            "ordinary_walk_navigation_effect": "UNKNOWN",
            "deployment_occupancy_effect": "CONFIRMED_ACTIVE_DEVICE_BLOCKS_TILE_IN_CURRENT_MODEL",
            "source": file_record(ROADBLOCK_EVIDENCE_PATH),
        },
        "simulation_domain": {
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
                "active roadblock effect on ordinary WALK navigation",
                "precise client wait/block priority",
            ],
            "output_budget": {
                "provider_created_envelope_limit_tokens": OUTPUT_TOKEN_LIMIT,
                "termination_usage_or_incomplete_details": "UNKNOWN",
                "confirmed_server_truncation_cause": "UNKNOWN",
            },
        },
        "hard_policy": {
            "ordinary_mode_only": True,
            "rarity_range": [1, 3],
            "exclude_mode_specific_reserve_operators": True,
            "one_operational_plan": True,
            "full_stage_scope": True,
            "do_not_require_complete_client_navigation_proof": True,
        },
    }


def output_schema() -> dict[str, Any]:
    array_properties = (
        "allowed_substitutions", "battle_phases", "changed_conflicting_assumptions",
        "conditional_responsibilities", "corridor_responsibilities", "deployment_positions_and_directions",
        "explicit_deadline_basis", "forbidden_substitutions", "formation_transitions",
        "mandatory_tactical_invariants", "opening_responsibilities", "optional_responsibilities",
        "pressure_window_responsibilities", "reserve_strategy", "skill_intents", "temporary_roles",
        "unknown_dependencies", "verification_questions",
    )
    plan_properties = {key: {"type": "array", "items": {"type": "object", "additionalProperties": True}} for key in array_properties}
    plan_properties.update(
        {
            "formation_structure": {"type": "object", "additionalProperties": True},
            "operational_plan_id": {"type": "string"},
            "parent_hypothesis_id": {"type": "string"},
            "selected_low_star_operator_ids": {"type": "array", "items": {"type": "string"}},
            "tactical_thesis": {"type": "string"},
            "action_timeline": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "action_type": {"type": "string"},
                        "frame": {"type": "integer"},
                        "operator_id": {"type": "string"},
                        "tile": {"type": "array", "items": {"type": "integer"}},
                        "direction": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["action_type", "frame", "operator_id"],
                    "allOf": [
                        {
                            "if": {"properties": {"action_type": {"const": "DEPLOY"}}, "required": ["action_type"]},
                            "then": {"required": ["tile", "direction"]},
                        }
                    ],
                },
            },
        }
    )
    plan_required = [
        "operational_plan_id", "parent_hypothesis_id", "tactical_thesis",
        "selected_low_star_operator_ids", "deployment_positions_and_directions",
        "formation_structure", "formation_transitions", "corridor_responsibilities",
        "pressure_window_responsibilities", "skill_intents", "mandatory_tactical_invariants",
        "action_timeline",
    ]
    return {
        "additionalProperties": True,
        "properties": {
            "counterexample_avoidance_explanations": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "deterministic_verifier_questions": {"type": "array", "items": {"type": "string"}},
            "explicit_assumptions": {"type": "array", "items": {"type": "string"}},
            "lessons_from_infeasibility": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "rejected_tactical_assumptions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_operational_plans": {
                "type": "array",
                "maxItems": 1,
                "minItems": 1,
                "items": {"additionalProperties": True, "properties": plan_properties, "required": plan_required, "type": "object"},
            },
            "revised_stage_understanding": {"type": "object", "additionalProperties": True},
            "revised_strategic_hypotheses": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_tactical_requirements": {"type": "object", "additionalProperties": True},
            "retained_tactical_knowledge": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "uncertainties": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        },
        "type": "object",
        "required": ["revised_operational_plans", "revised_stage_understanding", "revised_tactical_requirements", "revised_strategic_hypotheses"],
    }


def prompt_text(evidence: dict[str, Any]) -> str:
    evidence_json = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
    return f"""You are Kimi-K3, the tactical decision maker for Arknights stage {STAGE_ID} / R8-1.
Create exactly one complete OperationalPlan for the whole stage using ordinary-mode 1-3 star operators only.

The goal is simulator WIN, not economy minimization. Before WIN, do not reduce operator count, actions, rarity or cost. Use the full supplied roster and the full wave schedule. You own all tactical decisions: opening, phase transitions, route responsibilities, pressure windows, skills, blocking, fire sharing, healing, retreats, handoffs and conditional lane concessions. Python will verify, not invent, tactics.

Hard domain rules:
- Only operators in normal_low_star_catalog may be used. Their rarity must be 1-3 and normal_mode must be true. Exclude mode-specific reserve operators and 4-star+ units.
- Do not invent statistics, costs, frames, ranges, skill effects, tiles or mechanics. Tactical design frames are allowed, but must be labeled as choices under the supplied 30 FPS model.
- Preserve every invariant you declare. Put unsupported mechanics in unknown_dependencies, never as load-bearing mandatory proof.
- Explain what you retain and reject from the previous B2 plan and the earlier merchant/roadblock failures.
- Cover the entire wave schedule, including late waves and every route that the current runtime model shows as exposed. Treat old B2 pressure conclusions and its frame-941 diagnostic as invalid historical context, not as an active tactical baseline.
- action_timeline must contain every executable action in order. Use DEPLOY, ACTIVATE_SKILL, RETREAT. Each DEPLOY must have tile as [row,col] and a direction. Use ACTIVATE_SKILL only for manual skills, not auto skills.
- Do not deploy on active predefined device tiles. You may design around, but not remove, roadblocks unless the evidence supports removal; that removal mechanic is currently UNKNOWN, so do not depend on it.

The full stage lasts beyond the old 0-941 opening. Plan through every spawn until all enemies are killed.

Evidence status is supplied as JSON. Distinguish CONFIRMED_FROM_CODE/GAMEDATA, prior conditional model facts, and UNKNOWN. Do not turn a prior model deadline into a client rule. Do not treat active roadblock navigation as proven; ordinary WALK navigation through or around it remains UNKNOWN.

Keep the response compact enough to finish inside {OUTPUT_TOKEN_LIMIT} output tokens. Do not repeat evidence prose. Keep action rationales short. The complete evidence JSON follows:

EVIDENCE_JSON
{evidence_json}
"""


def parse_embedded_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("model") != MODEL:
        raise ValueError("payload model does not match")
    if payload.get("stream") is not True:
        raise ValueError("payload stream is not true")
    input_items = payload.get("input") or []
    if len(input_items) != 1 or input_items[0].get("role") != "user":
        raise ValueError("payload must contain exactly one user message")
    content = input_items[0].get("content") or []
    if len(content) != 1 or content[0].get("type") != "input_text":
        raise ValueError("payload must contain one input_text block")
    text = content[0].get("text") or ""
    marker = "EVIDENCE_JSON\n"
    if marker not in text:
        raise ValueError("EVIDENCE_JSON marker is missing")
    evidence_text = text.split(marker, 1)[1]
    try:
        return json.loads(evidence_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"embedded evidence is not valid JSON: {exc}") from exc


def validate_final_payload(payload: dict[str, Any], evidence_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        embedded = parse_embedded_evidence(payload)
    except ValueError as exc:
        embedded = None
        errors.append(str(exc))
    current = load(evidence_path)
    if embedded != current:
        errors.append("embedded evidence does not match current prepared evidence")
    if payload.get("text", {}).get("format", {}).get("schema") != output_schema():
        errors.append("payload schema does not match current output schema")
    active = current.get("stage_active_facts") or {}
    if active.get("roadblock_tiles_col_row") != ROADBLOCK_TILES_COL_ROW:
        errors.append("active roadblock facts do not match fixed GameData positions")
    if "prior_route_pressure_model" in current:
        errors.append("stale prior route pressure model is present in active evidence")
    historical = current.get("historical_context_not_active") or {}
    if historical.get("status") != "HISTORICAL_ONLY_DO_NOT_USE_AS_ACTIVE_FACTS":
        errors.append("old B2 context is not marked historical-only")
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body_path = OUT / "llm_request_body.txt"
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    if not body_path.is_file():
        errors.append("final pending request body has not been saved")
    else:
        saved_body = body_path.read_text(encoding="utf-8")
        if saved_body != body:
            errors.append("final serialized body does not match saved pending body")
    if len(errors):
        raise ValueError("; ".join(errors))
    return {
        "schema_version": "R8_1_LOW_STAR_FULL_TACTICAL_CLOSURE_V2_FINAL_PAYLOAD_VALIDATION",
        "status": "PASS",
        "evidence_embedded": True,
        "evidence_matches_prepared_file": True,
        "schema_matches_prepared_schema": True,
        "roadblock_tiles_col_row": ROADBLOCK_TILES_COL_ROW,
        "request_sha256": request_sha256(payload),
        "body_sha256": body_hash,
        "body_bytes": len(body.encode()),
        "historical_context_is_not_active": True,
    }


def validate_operational_plan_output(parsed: Any, evidence: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(parsed, dict):
        return ["response is not a JSON object"]
    plans = parsed.get("revised_operational_plans")
    if not isinstance(plans, list) or len(plans) != 1:
        return [f"exactly one revised_operational_plans item is required, got {len(plans) if isinstance(plans, list) else 'non-list'}"]
    plan = plans[0]
    if not isinstance(plan, dict):
        return ["operational plan is not an object"]
    for key in (
        "operational_plan_id", "parent_hypothesis_id", "tactical_thesis", "selected_low_star_operator_ids",
        "deployment_positions_and_directions", "formation_structure", "formation_transitions",
        "corridor_responsibilities", "pressure_window_responsibilities", "skill_intents",
        "mandatory_tactical_invariants", "action_timeline",
    ):
        if key not in plan:
            errors.append(f"plan missing {key}")
    catalog = {item["operator_id"]: item for item in evidence.get("normal_low_star_catalog", [])}
    active = evidence.get("stage_active_facts")
    if not isinstance(active, dict):
        return ["stage_active_facts is required and must be an object"]
    roadblock_rows = active.get("roadblock_tiles_col_row")
    if not isinstance(roadblock_rows, list):
        return ["stage_active_facts.roadblock_tiles_col_row is required"]
    device_rows = active.get("active_device_tiles_col_row")
    if not isinstance(device_rows, list):
        return ["stage_active_facts.active_device_tiles_col_row is required"]
    try:
        occupied_runtime_tiles = {tuple(int(value) for value in row) for row in device_rows}
    except (TypeError, ValueError):
        return ["stage_active_facts.active_device_tiles_col_row must contain integer [col,row] rows"]
    selected = plan.get("selected_low_star_operator_ids") or []
    if not isinstance(selected, list) or not selected:
        errors.append("selected_low_star_operator_ids is empty")
    for operator_id in selected:
        operator = catalog.get(operator_id)
        if operator is None:
            errors.append(f"unknown selected operator {operator_id}")
        else:
            qualification = operator.get("qualification") or {}
            identity = operator.get("identity") or {}
            if qualification.get("normal_mode") is not True or not 1 <= identity.get("rarity", 0) <= 3:
                errors.append(f"operator is outside ordinary 1-3 star domain: {operator_id}")
    actions = plan.get("action_timeline")
    if not isinstance(actions, list) or not actions:
        errors.append("action_timeline is empty")
    previous_frame = -1
    for index, action in enumerate(actions or []):
        label = f"action[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{label} is not an object")
            continue
        action_type = action.get("action_type")
        if action_type not in {"DEPLOY", "ACTIVATE_SKILL", "RETREAT"}:
            errors.append(f"{label} has unsupported action_type {action_type}")
        frame = action.get("frame")
        if not isinstance(frame, int) or frame < 0:
            errors.append(f"{label} frame is not a nonnegative integer")
        elif frame < previous_frame:
            errors.append(f"{label} frame is out of order")
        else:
            previous_frame = frame
        operator_id = action.get("operator_id")
        if operator_id not in catalog:
            errors.append(f"{label} references unknown operator {operator_id}")
        if action_type == "DEPLOY":
            tile = action.get("tile")
            if not isinstance(tile, list) or len(tile) != 2 or not all(isinstance(value, int) for value in tile):
                errors.append(f"{label} DEPLOY lacks integer [row,col]")
                continue
            row, col = tile
            if [col, row] in roadblock_rows:
                errors.append(f"{label} deploys on active roadblock [row,col]={tile}")
            elif (col, row) in occupied_runtime_tiles:
                errors.append(f"{label} deploys on an active stage device [row,col]={tile}")
            runtime_tile = (col, row)
            active = evidence.get("stage_active_facts") or {}
            ground = active.get("deployable_ground_tiles_col_row") or []
            high = active.get("deployable_high_ground_tiles_col_row") or []
            position = (catalog.get(operator_id) or {}).get("identity", {}).get("position")
            if position == "MELEE" and runtime_tile not in [tuple(item) for item in ground]:
                errors.append(f"{label} MELEE tile is not active deployable ground [row,col]={tile}")
            if position == "RANGED" and runtime_tile not in [tuple(item) for item in high]:
                errors.append(f"{label} RANGED tile is not active deployable high ground [row,col]={tile}")
        if action_type in {"DEPLOY"} and action.get("direction") not in {"UP", "DOWN", "LEFT", "RIGHT"}:
            errors.append(f"{label} DEPLOY lacks a legal direction")
    return errors


def build_strategy_handoff(plan: dict[str, Any]) -> dict[str, Any]:
    from arknights_planner.models.strategy import Action, ActionType, Strategy

    actions = []
    for item in plan.get("action_timeline") or []:
        action_type = ActionType(item["action_type"])
        runtime_tile = tuple(item["tile"][::-1]) if action_type is ActionType.DEPLOY and isinstance(item.get("tile"), list) else None
        action = Action(
            action_type=action_type,
            time=item["frame"] / 30.0,
            operator_id=item["operator_id"],
            tile=runtime_tile,
            direction=item.get("direction", "RIGHT"),
        )
        actions.append(action)
    strategy = Strategy(tuple(plan.get("selected_low_star_operator_ids") or []), tuple(actions))
    return {
        "schema_version": "R8_1_LOW_STAR_FULL_TACTICAL_CLOSURE_V2_PUBLIC_STRATEGY_HANDOFF",
        "status": "HANDOFF_READY_NOT_COMPILED",
        "operational_plan_id": plan.get("operational_plan_id"),
        "coordinate_conversion": "JSON [row,col] -> Action.tile (x=col,y=row)",
        "public_model": "arknights_planner.models.strategy.Strategy and Action",
        "strategy_actions": [
            {
                "action_type": action.action_type.value,
                "time_seconds": action.time,
                "operator_id": action.operator_id,
                "tile_col_row": list(action.tile) if action.tile is not None else None,
                "direction": action.direction,
            }
            for action in strategy.actions
        ],
        "certificate": "NONE",
        "tactical_validation_claim": "NONE",
    }


def request_payload(prompt: str) -> dict[str, Any]:
    return {
        "model": MODEL,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "stream": True,
        "text": {
            "format": {
                "name": "r8_1_low_star_full_tactical_closure_v2",
                "schema": output_schema(),
                "strict": False,
                "type": "json_schema",
            }
        },
    }


def request_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def append_attempt_record(record: dict[str, Any]) -> None:
    with (OUT / "llm_call_attempts.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def start_attempt(payload: dict[str, Any]) -> dict[str, Any]:
    record = {
        "attempt_id": datetime.now(timezone.utc).isoformat(),
        "request_sha256": request_sha256(payload),
        "status": "ATTEMPT_STARTED",
        "model": payload.get("model"),
        "budget_counted_before_network": True,
    }
    append_attempt_record(record)
    return record


def finish_attempt(record: dict[str, Any], accumulator: StreamAccumulator, raw: bytes) -> None:
    record.update(
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": accumulator.terminal_event or "ATTEMPT_FAILED",
            "error": accumulator.error,
            "http_status": accumulator.http_status,
            "request_id": accumulator.request_id,
            "response_bytes": len(raw),
        }
    )
    append_attempt_record(record)


def stream_once(payload: dict[str, Any]) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
    errors = validate_tactical_request(payload)
    if errors:
        raise RuntimeError("invalid tactical request: " + ", ".join(errors))
    if (OUT / "llm_call_attempts.jsonl").is_file():
        raise RuntimeError("Kimi attempt already exists; exactly-one-attempt policy forbids retry")
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    credential = os.environ.get("ARK_API_KEY_agent")
    if not credential:
        raise RuntimeError("ARK_API_KEY_agent is not set")
    request = urllib.request.Request(
        BASE_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    attempt = start_attempt(payload)
    accumulator = StreamAccumulator()
    request_id = None
    http_status = None
    raw_chunks: list[bytes] = []
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            http_status = response.status
            request_id = response.headers.get("x-request-id")
            for raw_bytes in response:
                raw_chunks.append(raw_bytes)
            raw = b"".join(raw_chunks)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        request_id = exc.headers.get("x-request-id") if exc.headers else request_id
        http_status = exc.code
        accumulator.error = f"HTTP {exc.code}: {raw.decode(errors='replace')}"
        accumulator.http_status = http_status
        accumulator.request_id = request_id
    except (TimeoutError, socket.timeout) as exc:
        raw = b"".join(raw_chunks)
        accumulator.error = f"TIMEOUT: {exc}"
    except urllib.error.URLError as exc:
        raw = b"".join(raw_chunks)
        accumulator.error = f"URL_ERROR: {exc.reason}"
    except OSError as exc:
        raw = b"".join(raw_chunks)
        accumulator.error = f"NETWORK_OR_STREAM_INTERRUPTED: {exc}"
    except KeyboardInterrupt:
        raw = b"".join(raw_chunks)
        accumulator.error = "INTERRUPTED"
        finish_attempt(attempt, accumulator, raw)
        raise
    from kimi_responses_transport import parse_sse

    for event in parse_sse(raw.decode("utf-8", errors="replace")):
        accumulator.observe(event)
    if accumulator.error is None and accumulator.terminal_event is None:
        accumulator.error = "NO_TERMINAL_EVENT"
    accumulator.http_status = http_status
    accumulator.request_id = request_id
    finish_attempt(attempt, accumulator, raw)
    return accumulator.response_envelope or {}, accumulator, raw


def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = evidence_context()
    prompt = prompt_text(evidence)
    payload = request_payload(prompt)
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body_path = OUT / "llm_request_body.txt"
    if body_path.is_file() and body_path.read_text(encoding="utf-8") != body:
        raise RuntimeError("prepared final request body differs from existing pending body; use a new output directory")
    body_path.write_text(body, encoding="utf-8")
    write("llm_request.json", payload)
    write("llm_evidence_context.json", evidence)
    write("revision_output_schema.json", output_schema())
    write_text("constraint_informed_prompt.txt", prompt)
    write(
        "llm_request_fingerprint.json",
        {
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "request_sha256": request_sha256(payload),
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "body_bytes": len(body.encode()),
        },
    )
    write("source_manifest.json", source_manifest())
    write("prepare_status.json", {"phase": "PREPARED", "request_schema": payload["text"]["format"]["name"]})


def call() -> None:
    request_path = OUT / "llm_request.json"
    evidence_path = OUT / "llm_evidence_context.json"
    if not request_path.is_file() or not evidence_path.is_file():
        write("final_status.json", {"kimi_call_count": 0, "status": "FINAL_PAYLOAD_NOT_PREPARED"})
        raise SystemExit("final payload is not prepared")
    payload = load(request_path)
    try:
        final_payload_validation = validate_final_payload(payload, evidence_path)
        write("llm_final_payload_validation.json", final_payload_validation)
    except Exception as exc:
        write("llm_final_payload_validation.json", {"status": "FAIL", "error": str(exc)})
        write("final_status.json", {"kimi_call_count": 0, "status": "FINAL_PAYLOAD_REJECTED_NO_CALL"})
        raise SystemExit("final payload validation failed; no call was made") from exc
    envelope, accumulator, raw = stream_once(payload)
    write_text("llm_raw_response.txt", raw.decode(errors="replace") if raw else "")
    diagnostics = {
        "http_status": accumulator.http_status,
        "model": accumulator.response_envelope.get("model") if accumulator.response_envelope else None,
        "request_id": accumulator.request_id,
        "terminal_event": accumulator.terminal_event,
        "classification": accumulator.classify(),
        "response_bytes": len(raw),
    }
    write("llm_call_record.json", diagnostics)
    if accumulator.error or accumulator.terminal_event != "response.completed":
        write("final_status.json", {"kimi_call_count": 1, "status": "KIMI_CALL_FAILED_NO_RETRY", **diagnostics})
        raise SystemExit("Kimi call failed without retry")
    if accumulator.http_status != 200:
        write("final_status.json", {"kimi_call_count": 1, "status": "KIMI_CALL_FAILED_NO_RETRY", **diagnostics})
        raise SystemExit("Kimi call failed without retry")
    text = extract_response_text(accumulator.response_envelope or {})[0]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        write("response_completion_validation.json", {"kimi_call_count": 1, "json_parse": "FAIL", "error": str(exc)})
        write("final_status.json", {"kimi_call_count": 1, "status": "KIMI_RESPONSE_JSON_INVALID_NO_RETRY"})
        raise
    evidence = load(evidence_path)
    contract_errors = validate_operational_plan_output(parsed, evidence)
    try:
        schema_errors = sorted(
            Draft7Validator(output_schema()).iter_errors(parsed),
            key=lambda error: list(error.path),
        )
        contract_errors.extend(
            f"schema: {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in schema_errors
        )
    except Exception as exc:
        contract_errors.append(f"schema validation unavailable: {exc}")
    if contract_errors:
        write("llm_invalid_structured_output.json", parsed)
        write(
            "response_completion_validation.json",
            {
                "kimi_call_count": 1,
                "model": accumulator.response_envelope.get("model") if accumulator.response_envelope else MODEL,
                "raw_response_sha256": hashlib.sha256((OUT / "llm_raw_response.txt").read_bytes()).hexdigest(),
                "json_parse": "PASS",
                "contract_and_schema_validation": "FAIL",
                "errors": contract_errors,
            },
        )
        write("final_status.json", {"kimi_call_count": 1, "status": "KIMI_RESPONSE_CONTRACT_INVALID_NO_RETRY"})
        raise SystemExit("Kimi response failed contract validation without retry")
    write("llm_structured_output.json", parsed)
    plans = parsed.get("revised_operational_plans") or []
    write("strategy_handoff.json", build_strategy_handoff(plans[0]))
    write(
        "response_completion_validation.json",
        {
            "kimi_call_count": 1,
            "model": accumulator.response_envelope.get("model") if accumulator.response_envelope else MODEL,
            "raw_response_sha256": hashlib.sha256((OUT / "llm_raw_response.txt").read_bytes()).hexdigest(),
            "single_call_policy": "PASS",
            "json_parse": "PASS",
            "one_operational_plan": len(plans) == 1,
        },
    )
    write("grounding_validation.json", {"kimi_call_count": 1, "revised_operational_plan_count": len(plans), "status": "STRUCTURAL_PARSE_PASS"})
    write("final_status.json", {"kimi_call_count": 1, "status": "KIMI_CALL_AND_CONTRACT_COMPLETE", "operational_plan_count": len(plans)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "call"])
    arguments = parser.parse_args()
    if arguments.phase == "prepare":
        prepare()
        return
    call()


if __name__ == "__main__":
    main()
