from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealOperatorSelection,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator
from run_r8_1_lowstar_c2_full_diagnostic_v1 import (
    event_payload,
    fail_started,
    file_record,
    first_failure_context,
    json_value,
    summaries,
)


ROOT = Path(__file__).resolve().parents[1]
GAMEDATA = ROOT / "data/ArknightsGameData"
FRAMES_PER_SECOND = 30.0


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_full_diagnostic(*, source: Path, out: Path, stage_id: str, plan_id: str) -> dict[str, Any]:
    evidence = load(source / "llm_evidence_context.json")
    plan = load(source / "llm_structured_output.json")["revised_operational_plans"][0]
    actions = plan["action_timeline"]
    deployments = [item for item in actions if item.get("action_type") == "DEPLOY"]
    if len({item["operator_id"] for item in deployments}) != len(deployments):
        raise RuntimeError("a deployment operator is reused without a source-backed RETREAT")
    catalog = {item["operator_id"]: item for item in evidence["normal_low_star_catalog"]}
    selections = tuple(
        RealOperatorSelection(
            item["operator_id"],
            int(catalog[item["operator_id"]]["debug_configuration"]["phase_index"]),
            int(catalog[item["operator_id"]]["debug_configuration"]["level"]),
            (int(item["tile"][1]), int(item["tile"][0])),
            item.get("direction"),
            int(item["frame"]) / FRAMES_PER_SECOND,
        )
        for item in deployments
    )
    strategy_actions = []
    for item in actions:
        action_type = {
            "DEPLOY": ActionType.DEPLOY,
            "ACTIVATE_SKILL": ActionType.ACTIVATE_SKILL,
            "RETREAT": ActionType.RETREAT,
        }[item["action_type"]]
        tile = (int(item["tile"][1]), int(item["tile"][0])) if "tile" in item else None
        strategy_actions.append(Action(action_type, int(item["frame"]) / FRAMES_PER_SECOND, item["operator_id"], tile, item.get("direction")))
    started = {
        "schema_version": "GPT_TACTICAL_STAGE_DIAGNOSTIC_ATTEMPT_V1",
        "stage_id": stage_id, "plan_id": plan_id, "action_count": len(actions),
        "stage_simulations_started": 1, "status": "STARTED", "automatic_retry": False,
        "policy": RealSimulationApproximationPolicy.m11_second_quantized().names,
    }
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "simulation_attempt.json", started)
    try:
        policy = RealSimulationApproximationPolicy.m11_second_quantized()
        fixture = ApproximateRealSimulationAdapter(GameDataRepository(GAMEDATA)).build_fixture(
            stage_id_or_code=stage_id, selections=selections, policy=policy,
        )
        strategy = Strategy(tuple(item["operator_id"] for item in deployments), tuple(strategy_actions))
        result = Simulator(
            range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel(),
        ).run(
            stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies,
            strategy=strategy,
            config=SimulationConfig(dt=1 / FRAMES_PER_SECOND, max_time=600.0),
        )
    except Exception as exc:
        fail_started(f"{type(exc).__name__}: {exc}", started, out)
        raise
    events = [event_payload(event) for event in result.events]
    event_summaries = summaries(events)
    parameters = {
        "mechanics_version": evidence["mechanics_version"],
        "stage_id": stage_id, "plan_id": plan_id,
        "run_mode": "DIAGNOSTIC_MODEL_FULL_STAGE", "run_count": 1,
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
    partial_support = evidence["stage_mechanism_support"]["full_stage_result_support"] == "PARTIAL_SIMULATION_ONLY"
    classification = (
        ("PARTIAL_MECHANICS_DIAGNOSTIC_WIN" if result.win else "PARTIAL_MECHANICS_DIAGNOSTIC_LOSS")
        if partial_support else "DIAGNOSTIC_MODEL_FULL_STAGE"
    )
    summary = {
        "result": json_value(result),
        "classification": classification,
        "full_stage_mechanism_support": evidence["stage_mechanism_support"]["full_stage_result_support"],
        "civilian_operator_targetability": evidence["stage_mechanism_support"]["operator_targetability_of_friendly_units"],
        "civilian_blocking": evidence["stage_mechanism_support"]["friendly_unit_blocking"],
        "faithful_certificate": "NOT_ISSUED", "operationally_verified": False,
        "real_game_win_claim": False, "robust_claim": "NOT_EVALUATED",
        "omitted_or_unknown_mechanics": evidence["simulation_domain"]["omitted_or_unknown_mechanics"],
        "event_count": len(events), "event_summaries": event_summaries,
        "first_failure": first_failure_context(events),
    }
    write_json(out / "simulation_attempt.json", {**started, "status": "COMPLETED", "result_saved": True})
    write_json(out / "simulation_parameters.json", parameters)
    write_json(out / "diagnostic_events.json", {"events": events})
    write_json(out / "diagnostic_summary.json", summary)
    write_json(out / "final_status.json", {
        "schema_version": "GPT_TACTICAL_STAGE_DIAGNOSTIC_FINAL_STATUS_V1",
        "stage_id": stage_id, "plan_id": plan_id,
        "classification": classification, "faithful_certificate": "NOT_ISSUED",
        "simulator_win": bool(result.win), "real_game_win_claim": False,
        "robust_claim": "NOT_EVALUATED",
        "remaining_life": result.remaining_life, "enemies_killed": result.enemies_killed,
        "enemies_leaked": result.enemies_leaked, "operator_deaths": result.operator_deaths,
        "final_dp": result.final_dp, "first_failure": summary["first_failure"],
        "status": "DIAGNOSTIC_COMPLETE_NOT_OPERATIONALLY_VERIFIED",
    })
    return summary
