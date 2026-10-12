from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
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

OUT = ROOT / "output/r8_1_low_star_full_tactical_closure_v1"
GAMEDATA = ROOT / "data/ArknightsGameData"
BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/responses"
MODEL = "kimi-k3"
MECHANICS = "m18.9-stage-device-runtime-v1"
TIMEOUT_SECONDS = 900
STAGE_ID = "main_08-01"
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
        "schema_version": "R8_1_LOW_STAR_FULL_TACTICAL_CLOSURE_V1_SOURCE_MANIFEST",
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


def evidence_context() -> dict[str, Any]:
    level = load(LEVEL_PATH)
    context = load(CONTEXT_PATH)
    previous_plan = load(PREVIOUS_PLAN_PATH)
    previous_actions = load(PREVIOUS_ACTIONS_PATH)
    previous_diagnostic = load(PREVIOUS_DIAGNOSTIC_PATH)
    options = level["options"]
    prior_routes = [
        {**route, "status": "PRIOR_CONDITIONAL_MODEL_NOT_CLIENT_FACT"}
        for route in context["exact_route_threats"]["routes"]
    ]
    return {
        "milestone": "R8_1_LOW_STAR_FULL_TACTICAL_CLOSURE_V1",
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
        "deployable_ground_tiles_row_col": context["stage_facts"]["deployable_ground_tiles"],
        "deployable_high_ground_tiles_row_col": context["stage_facts"]["deployable_high_ground_tiles"],
        "predefined_devices": context["stage_devices"],
        "enemy_facts": enemy_facts(level),
        "source_routes": compact_source_routes(level),
        "source_wave_schedule": compact_wave_schedule(level),
        "model_spawn_timeline": model_spawn_timeline(),
        "terrain_navigation_facts": compact_navigation_facts(),
        "prior_route_pressure_model": prior_routes,
        "previous_plan_experience": {
            "plan_id": previous_plan["revised_operational_plans"][0]["operational_plan_id"],
            "tactical_thesis": previous_plan["revised_operational_plans"][0]["tactical_thesis"],
            "action_candidate": previous_actions,
            "frame_941_diagnostic_result": previous_diagnostic["result"],
            "route_kills_and_blocks_at_941": previous_diagnostic["event_summaries"],
            "prior_budget_note": "The prior diagnostic exceeded a one-run budget; only the persisted final run is reusable as model evidence.",
            "confirmed_counterexamples": [
                "Active roadblock occupies deployment tiles; [9,2] deployment is invalid in the current model.",
                "Merchant upkeep is real: 3 DP every 3 seconds, auto-retreat on insufficient DP, no confirmed refund.",
                "Exact first merchant-upkeep debit remains UNKNOWN.",
                "4-star and 5-star units from older plans are outside the current 1-3 star domain.",
            ],
            "route_feedback_qualifications": load(PREVIOUS_FEEDBACK_PATH),
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
                },
            },
        }
    )
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
                "items": {"additionalProperties": True, "properties": plan_properties, "type": "object"},
            },
            "revised_stage_understanding": {"type": "object", "additionalProperties": True},
            "revised_strategic_hypotheses": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_tactical_requirements": {"type": "object", "additionalProperties": True},
            "retained_tactical_knowledge": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "uncertainties": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        },
        "type": "object",
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
- Cover the entire wave schedule, including late waves and every route that leaks under the previous plan.
- action_timeline must contain every executable action in order. Use DEPLOY, ACTIVATE_SKILL, RETREAT. Each DEPLOY must have tile as [row,col] and a direction. Use ACTIVATE_SKILL only for manual skills, not auto skills.
- Do not deploy on active predefined device tiles. You may design around, but not remove, roadblocks unless the evidence supports removal; that removal mechanic is currently UNKNOWN, so do not depend on it.

The full stage lasts beyond the old 0-941 opening. Plan through every spawn until all enemies are killed. The previous B2 plan survived frame 941 with 0 leaks but 4 active enemies and 13,800 remaining HP, so its formation was not complete.

Evidence status is supplied as JSON. Distinguish CONFIRMED_FROM_CODE/GAMEDATA, prior conditional model facts, and UNKNOWN. Do not turn a prior model deadline into a client rule. Do not treat active roadblock navigation as proven; ordinary WALK navigation through or around it remains UNKNOWN.

Keep the response compact enough to finish inside 32,768 output tokens. Do not repeat evidence prose. Keep action rationales short. The complete evidence JSON follows:

EVIDENCE_JSON
{evidence_json}
"""


def request_payload(prompt: str) -> dict[str, Any]:
    return {
        "model": MODEL,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "stream": True,
        "text": {
            "format": {
                "name": "r8_1_low_star_full_tactical_closure_v1",
                "schema": output_schema(),
                "strict": False,
                "type": "json_schema",
            }
        },
    }


def stream_once(payload: dict[str, Any]) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
    errors = validate_tactical_request(payload)
    if errors:
        raise RuntimeError("invalid tactical request: " + ", ".join(errors))
    if (OUT / "llm_raw_response.txt").is_file():
        raise RuntimeError("Kimi response already exists; exactly-one-call policy forbids retry")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    credential = os.environ.get("ARK_API_KEY_agent")
    if not credential:
        raise RuntimeError("ARK_API_KEY_agent is not set")
    request = urllib.request.Request(
        BASE_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json", "Accept": "text/event-stream"},
    )
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
    from kimi_responses_transport import parse_sse

    accumulator = StreamAccumulator()
    for event in parse_sse(raw.decode("utf-8", errors="replace")):
        accumulator.observe(event)
    return accumulator.response_envelope or {}, accumulator, raw


def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = evidence_context()
    prompt = prompt_text(evidence)
    payload = request_payload(prompt)
    write("llm_request.json", payload)
    write("llm_evidence_context.json", evidence)
    write("revision_output_schema.json", output_schema())
    write_text("constraint_informed_prompt.txt", prompt)
    write(
        "llm_request_fingerprint.json",
        {
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "request_sha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        },
    )
    write("source_manifest.json", source_manifest())
    write("prepare_status.json", {"phase": "PREPARED", "request_schema": payload["text"]["format"]["name"]})


def call() -> None:
    payload = load(OUT / "llm_request.json") if (OUT / "llm_request.json").is_file() else request_payload((OUT / "constraint_informed_prompt.txt").read_text(encoding="utf-8"))
    if not (OUT / "llm_request.json").is_file():
        write("llm_request.json", payload)
    envelope, accumulator, raw = stream_once(payload)
    write_text("llm_raw_response.txt", raw.decode(errors="replace") if raw else "")
    diagnostics = {
        "http_status": 200 if accumulator.terminal_event == "response.completed" else None,
        "model": accumulator.response_envelope.get("model") if accumulator.response_envelope else None,
        "request_id": None,
        "terminal_event": accumulator.terminal_event,
        "classification": accumulator.classify(),
        "response_bytes": len(raw),
    }
    write("llm_call_record.json", diagnostics)
    if accumulator.error or accumulator.terminal_event != "response.completed":
        write("final_status.json", {"kimi_call_count": 1, "status": "KIMI_CALL_FAILED_NO_RETRY", **diagnostics})
        raise SystemExit("Kimi call failed without retry")
    text = extract_response_text(accumulator.response_envelope or {})[0]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        write("response_completion_validation.json", {"kimi_call_count": 1, "json_parse": "FAIL", "error": str(exc)})
        write("final_status.json", {"kimi_call_count": 1, "status": "KIMI_RESPONSE_JSON_INVALID_NO_RETRY"})
        raise
    write("llm_structured_output.json", parsed)
    plans = parsed.get("revised_operational_plans") or []
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
