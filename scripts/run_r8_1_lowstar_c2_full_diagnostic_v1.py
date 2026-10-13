from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.adapters.approximate_real import RealOperatorSelection
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator


ROOT = Path(__file__).resolve().parents[1]
GAMEDATA = ROOT / "data/ArknightsGameData"
DEFAULT_SOURCE = ROOT / "output/r8_1_lowstar_c2_compact_tool_revision_v2"
DEFAULT_OUT = ROOT / "output/r8_1_lowstar_c2_full_diagnostic_v1"
FRAMES_PER_SECOND = 30
DEFAULT_PLAN_ID = "R8_1_LOWSTAR_PLAN_C2"
STAGE_ID = "main_08-01"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def event_payload(event: Any) -> dict[str, Any]:
    return {
        "time": event.time,
        "frame": round(event.time * FRAMES_PER_SECOND),
        "event_type": event.event_type.value,
        "source_id": event.source_id,
        "target_id": event.target_id,
        "details": dict(event.details),
    }


def json_value(value: Any) -> Any:
    return asdict(value) if is_dataclass(value) else value


def fail_started(error: str, started: dict[str, Any], out: Path) -> None:
    record = {**started, "status": "FAILED_BEFORE_RESULT", "error": error}
    write_json(out / "simulation_attempt.json", record)
    write_json(out / "final_status.json", {
        "budget": {"kimi_requests": 0, "new_plans": 0, "new_candidates": 0,
                   "stage_simulations_started": 1, "search_expansions": 0},
        "faithful_certificate": "NOT_ISSUED",
        "result_claim": "NONE",
        "status": "SIMULATION_START_FAILED",
    })


def first_failure_context(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    leaks = [row for row in events if row["event_type"] == "ENEMY_LEAK"]
    if not leaks:
        return None
    first = leaks[0]
    window_start = max(0.0, float(first["time"]) - 10.0)
    related = [row for row in events if row["target_id"] == first["source_id"] and row["time"] >= window_start]
    economic = [row for row in events if row["event_type"] == "DP_CHANGE" and row["time"] >= window_start]
    return {"first_leak": first, "related_enemy_events": related, "economic_events": economic}


def summaries(events: list[dict[str, Any]]) -> dict[str, Any]:
    route_by_enemy = {
        row["source_id"]: row["details"]["route_id"]
        for row in events if row["event_type"] == "SPAWN"
    }
    by_type: dict[str, list[dict[str, Any]]] = {}
    for row in events:
        by_type.setdefault(row["event_type"], []).append(row)
    routes = sorted(set(route_by_enemy.values()))
    route_summaries: dict[str, Any] = {}
    for route_id in routes:
        enemy_ids = {enemy_id for enemy_id, route in route_by_enemy.items() if route == route_id}
        route_summaries[route_id] = {
            "spawn_count": sum(row["source_id"] in enemy_ids for row in by_type.get("SPAWN", [])),
            "kills": [row["frame"] for row in by_type.get("ENEMY_DEATH", []) if row["target_id"] in enemy_ids],
            "leaks": [row for row in by_type.get("ENEMY_LEAK", []) if row["source_id"] in enemy_ids],
            "blocks": [row["frame"] for row in by_type.get("BLOCK", []) if row["target_id"] in enemy_ids],
        }
    activations = by_type.get("SKILL_ACTIVATE", [])
    dp_changes = by_type.get("DP_CHANGE", [])
    skill_dp_income = []
    for row in dp_changes:
        if row["details"].get("reason") != "skill_activation":
            continue
        activation = next((item for item in activations if item["source_id"] == row["source_id"] and item["time"] == row["time"]), None)
        skill_dp_income.append({**row, "automatic": bool(activation and activation["details"].get("automatic"))})
    return {
        "route_summaries": route_summaries,
        "deployment_events": by_type.get("DEPLOY", []),
        "retreat_events": by_type.get("RETREAT", []),
        "operator_death_events": by_type.get("OPERATOR_DEATH", []),
        "skill_activations": activations,
        "skill_dp_income": skill_dp_income,
        "automatic_skill_dp_income": [row for row in skill_dp_income if row["automatic"]],
        "deployment_errors": [row for row in by_type.get("DEPLOY", []) if row["details"].get("legal") is False],
    }


def run_full_diagnostic(source: Path = DEFAULT_SOURCE, out: Path = DEFAULT_OUT, plan_id: str = DEFAULT_PLAN_ID) -> None:
    source = source if source.is_absolute() else ROOT / source
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    static = load(source / "static_compile_results.json")
    candidate = load(source / "direction_complete_action_candidate.json")
    evidence = load(source / "llm_evidence_context.json")
    plan = load(source / "llm_structured_output.json")["revised_operational_plans"][0]
    if candidate["operational_plan_id"] != plan_id or static["classification"] not in {
        "STATIC_CONTRACT_CHECKED_CONDITIONAL", "STATIC_CONTRACT_CHECKED_NO_RANGE_TARGET_UNKNOWN"
    } or static["conflicts"]:
        raise SystemExit("full diagnostic execution premise not met")
    actions = candidate["actions"]
    catalog = {row["operator_id"]: row for row in evidence["normal_low_star_catalog"]}
    deployments = [action for action in actions if action["action_type"] == "DEPLOY"]
    selected_ids = set(plan["selected_low_star_operator_ids"])
    deployment_ids = {action["operator_id"] for action in deployments}
    if deployment_ids != selected_ids or len(deployment_ids) != len(deployments):
        raise SystemExit("saved deployment set does not match selected catalog")
    candidate_contract = [
        (action["action_type"], int(action["frame"]), action["operator_id"], action.get("tile"), action.get("direction"))
        for action in actions
    ]
    plan_contract = [
        (action["action_type"], int(action["frame"]), action["operator_id"], action.get("tile"), action.get("direction"))
        for action in plan["action_timeline"]
    ]
    if candidate_contract != plan_contract:
        raise SystemExit("direction-complete candidate does not match the saved action timeline")
    selections = tuple(
        RealOperatorSelection(
            action["operator_id"],
            int(catalog[action["operator_id"]]["debug_configuration"]["phase_index"]),
            int(catalog[action["operator_id"]]["debug_configuration"]["level"]),
            (int(action["tile"][1]), int(action["tile"][0])),
            action["direction"],
            int(action["frame"]) / FRAMES_PER_SECOND,
        )
        for action in deployments
    )
    strategy_actions = []
    for action in actions:
        action_type = {
            "DEPLOY": ActionType.DEPLOY,
            "ACTIVATE_SKILL": ActionType.ACTIVATE_SKILL,
            "RETREAT": ActionType.RETREAT,
        }[action["action_type"]]
        tile = (int(action["tile"][1]), int(action["tile"][0])) if "tile" in action else None
        strategy_actions.append(Action(action_type, int(action["frame"]) / FRAMES_PER_SECOND, action["operator_id"], tile, action.get("direction")))
    started = {
        "schema_version": "R8_1_LOWSTAR_C2_FULL_DIAGNOSTIC_ATTEMPT_V1",
        "plan_id": plan_id,
        "action_count": len(actions),
        "stage_simulations_started": 1,
        "status": "STARTED",
        "policy": RealSimulationApproximationPolicy.m11_second_quantized().names,
        "automatic_retry": False,
    }
    write_json(out / "simulation_attempt.json", started)
    try:
        policy = RealSimulationApproximationPolicy.m11_second_quantized()
        fixture = ApproximateRealSimulationAdapter(GameDataRepository(GAMEDATA)).build_fixture(
            stage_id_or_code=STAGE_ID, selections=selections, policy=policy,
        )
        strategy = Strategy(tuple(action["operator_id"] for action in deployments), tuple(strategy_actions))
        result = Simulator(
            range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel(),
        ).run(
            stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies,
            strategy=strategy, config=SimulationConfig(dt=1 / FRAMES_PER_SECOND, max_time=600.0),
        )
    except Exception as exc:
        fail_started(f"{type(exc).__name__}: {exc}", started, out)
        return
    events = [event_payload(event) for event in result.events]
    event_summaries = summaries(events)
    parameters = {
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "stage_id": STAGE_ID,
        "plan_id": plan_id,
        "run_mode": "DIAGNOSTIC_MODEL_FULL_STAGE",
        "run_count": 1,
        "frames_per_second": FRAMES_PER_SECOND,
        "simulation_dt_seconds": 1 / FRAMES_PER_SECOND,
        "simulation_max_time_seconds": 600.0,
        "spawn_schedule_policy": policy.spawn_schedule.value,
        "attack_timing_policy": policy.attack_timing.value,
        "projectile_policy": policy.projectile_timing.value,
        "damage_model_policy": policy.damage_model.value,
        "natural_dp_policy": policy.natural_dp.value,
        "ignored_real_skill_data": fixture.ignored_real_skill_data,
    }
    summary = {
        "result": json_value(result),
        "classification": "DIAGNOSTIC_MODEL_FULL_STAGE",
        "faithful_certificate": "NOT_ISSUED",
        "operationally_verified": False,
        "real_game_win_claim": False,
        "robust_roadblock_targeting_claim": "NOT_EVALUATED",
        "omitted_or_unknown_mechanics": evidence["simulation_domain"]["omitted_or_unknown_mechanics"],
        "event_count": len(events),
        "event_summaries": event_summaries,
        "first_failure": first_failure_context(events),
    }
    completed = {**started, "status": "COMPLETED", "result_saved": True}
    write_json(out / "simulation_attempt.json", completed)
    write_json(out / "simulation_parameters.json", parameters)
    write_json(out / "diagnostic_events.json", {"events": events})
    write_json(out / "diagnostic_summary.json", summary)
    source_paths = (
        Path(__file__).resolve(), source / "llm_structured_output.json", source / "direction_complete_action_candidate.json",
        source / "static_compile_results.json", source / "llm_evidence_context.json",
        (ROOT / "src/arknights_planner/simulator/simulator.py"), (ROOT / "src/arknights_planner/adapters/approximate_real.py"),
        (ROOT / "src/arknights_planner/adapters/low_rarity_skill.py"), (ROOT / "scripts/compile_r8_1_lowstar_c2_plan_v1.py"),
        out / "simulation_parameters.json", out / "diagnostic_events.json", out / "diagnostic_summary.json",
    )
    write_json(out / "run_manifest.json", {
        "schema_version": "R8_1_LOWSTAR_C2_FULL_DIAGNOSTIC_MANIFEST_V1",
        "files": {str(path.relative_to(ROOT)): file_record(path) for path in source_paths},
    })
    final_result = summary["result"]
    write_json(out / "final_status.json", {
        "budget": {"kimi_requests": 0, "new_plans": 0, "new_candidates": 0,
                   "stage_simulations_started": 1, "search_expansions": 0},
        "classification": "DIAGNOSTIC_MODEL_FULL_STAGE",
        "faithful_certificate": "NOT_ISSUED",
        "simulator_win": bool(final_result["win"]),
        "real_game_win_claim": False,
        "robust_roadblock_targeting_claim": "NOT_EVALUATED",
        "remaining_life": final_result["remaining_life"],
        "enemies_killed": final_result["enemies_killed"],
        "enemies_leaked": final_result["enemies_leaked"],
        "operator_deaths": final_result["operator_deaths"],
        "final_dp": final_result["final_dp"],
        "automatic_skill_dp_income_count": len(event_summaries["automatic_skill_dp_income"]),
        "deployment_errors": event_summaries["deployment_errors"],
        "first_failure": summary["first_failure"],
        "status": "DIAGNOSTIC_COMPLETE_NOT_OPERATIONALLY_VERIFIED",
    })


if __name__ == "__main__":
    run_full_diagnostic()
