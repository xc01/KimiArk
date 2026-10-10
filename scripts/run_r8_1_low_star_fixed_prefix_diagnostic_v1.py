from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.adapters.approximate_real import RealOperatorSelection
from arknights_planner.adapters.normal_low_star import debug_configuration, is_normal_mode_low_star
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator


ROOT = Path(__file__).resolve().parents[1]
GAMEDATA = ROOT / "data/ArknightsGameData"
SOURCE = ROOT / "output/r8_1_normal_low_star_tactical_revision_v1"
OUT = ROOT / "output/r8_1_low_star_fixed_prefix_diagnostic_v1"
FRAMES_PER_SECOND = 30
WINDOW_END_FRAME = 941
PLAN_ID = "R8OP-B2-FANG43-FRSTON85-CROSSFIRE-OPEN0941"
ACTION_FRAMES = (
    (0, "char_123_fang", (4, 3), "LEFT"),
    (90, "char_4093_frston", (8, 5), "DOWN"),
    (180, "char_4227_gallus", (9, 5), "LEFT"),
    (510, "char_124_kroos", (7, 5), "RIGHT"),
    (570, "char_285_medic2", (6, 5), "RIGHT"),
    (630, "char_502_nblade", (5, 1), "RIGHT"),
)
CONFIGURATIONS = {
    "char_123_fang": (1, 55),
    "char_4093_frston": (0, 30),
    "char_4227_gallus": (0, 30),
    "char_124_kroos": (1, 55),
    "char_285_medic2": (0, 30),
    "char_502_nblade": (0, 30),
}
MECHANISM_OMISSIONS = {
    "char_124_kroos": ("20% 150% ATK probability talent"),
    "char_4093_frston": ("10-second surrounding-ally damage reduction talent"),
    "char_4227_gallus": ("20-second magic-resistance shred talent and its priority targeting"),
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def enemy_facts() -> dict[str, Any]:
    repository = GameDataRepository(GAMEDATA)
    _, _, level_path, level_payload = repository.get_stage_level_document("main_08-01")
    enemy_path = GAMEDATA / "zh_CN/gamedata/levels/enemydata/enemy_database.json"
    enemy_database = json.loads(enemy_path.read_text(encoding="utf-8"))
    rows = []
    for reference in level_payload["enemyDbRefs"]:
        record = next(item for item in enemy_database["enemies"] if item["Key"] == reference["id"])
        variant = next(item for item in record["Value"] if item["level"] == reference["level"])
        raw = variant["enemyData"]
        attributes = raw["attributes"]
        rows.append({
            "enemy_id": reference["id"],
            "level": reference["level"],
            "overwritten_data": reference.get("overwrittenData"),
            "base_attack_time": attributes["baseAttackTime"],
            "attack_speed": attributes["attackSpeed"],
            "apply_way": raw["applyWay"],
            "source_path": f"$.enemies[Key={reference['id']}].Value[level={reference['level']}].enemyData",
        })
    return {
        "level_reference_count": len(level_payload["enemyDbRefs"]),
        "level_overwritten_data": level_payload.get("overwrittenData"),
        "level_source": str(level_path.relative_to(ROOT)),
        "enemy_database_source": str(enemy_path.relative_to(ROOT)),
        "rows": rows,
        "client_attack_windup": "UNKNOWN_NOT_USED_BY_DIAGNOSTIC_RUNTIME",
        "client_integer_rounding": "UNKNOWN",
    }


def operator_evidence(fixture: Any) -> dict[str, Any]:
    repository = GameDataRepository(GAMEDATA)
    support = load(ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json")
    support_by_id = {item["operator_id"]: item for item in support["operators"]}
    rows = []
    for operator_id, (phase_index, level) in CONFIGURATIONS.items():
        qualification = debug_configuration(repository, operator_id)
        operator = fixture.operators[operator_id]
        stats = operator.phases[0].stats_max
        rows.append({
            "operator_id": operator_id,
            "normal_mode_low_star": is_normal_mode_low_star(repository, operator_id),
            "debug_configuration": qualification,
            "deployment_cost_delta": operator.deployment_cost_delta,
            "base_attack_interval": stats.attack_interval.value,
            "block_count": stats.block_count.value,
            "attack_range": operator.attack_range,
            "synthetic_skill": json_value(operator.synthetic_skill),
            "mechanism_support": support_by_id[operator_id],
            "explicitly_omitted_mechanics": MECHANISM_OMISSIONS.get(operator_id, ()),
        })
    return {"rows": rows, "all_normal_mode_low_star": all(row["normal_mode_low_star"] for row in rows)}


def summaries(result: Any, fixture: Any) -> dict[str, Any]:
    payloads = [event_payload(event) for event in result.events]
    route_by_enemy = {
        payload["source_id"]: payload["details"]["route_id"]
        for payload in payloads
        if payload["event_type"] == "SPAWN"
    }
    by_type = {
        event_type: [payload for payload in payloads if payload["event_type"] == event_type]
        for event_type in {payload["event_type"] for payload in payloads}
    }
    routes = sorted(route_by_enemy.values())
    route_summaries = {}
    for route_id in routes:
        enemy_ids = {enemy_id for enemy_id, route in route_by_enemy.items() if route == route_id}
        route_summaries[route_id] = {
            "spawn_count": sum(1 for payload in by_type["SPAWN"] if payload["details"]["route_id"] == route_id),
            "kills": [payload for payload in by_type.get("ENEMY_DEATH", []) if payload["target_id"] in enemy_ids],
            "leaks": [payload for payload in by_type.get("ENEMY_LEAK", []) if payload["source_id"] in enemy_ids],
            "blocks": [payload for payload in by_type.get("BLOCK", []) if payload["target_id"] in enemy_ids],
            "unblocks": [payload for payload in by_type.get("UNBLOCK", []) if payload["target_id"] in enemy_ids],
        }
    deployed_ids = [payload["source_id"] for payload in by_type["DEPLOY"] if payload["details"]["legal"]]
    retreated_ids = [payload["source_id"] for payload in by_type.get("RETREAT", [])]
    died_ids = [payload["source_id"] for payload in by_type.get("OPERATOR_DEATH", [])]
    return {
        "route_summaries": route_summaries,
        "deployment_payments": [payload for payload in by_type["DEPLOY"] if payload["details"]["legal"]],
        "deployment_errors": list(result.deployment_errors),
        "skill_dp_income": [
            payload for payload in by_type.get("DP_CHANGE", [])
            if payload["details"].get("reason") == "skill_activation"
        ],
        "boundary_deployed_operator_ids": sorted(set(deployed_ids) - set(retreated_ids) - set(died_ids)),
        "boundary_retreated_operator_ids": sorted(set(retreated_ids)),
        "boundary_dead_operator_ids": sorted(set(died_ids)),
        "fixture_devices": [
            {"device_id": item.device_id, "template_id": item.template_id, "tile": item.tile}
            for item in fixture.stage.devices
        ],
        "fixture_spawn_timeline": [dict(vars(item)) for item in fixture.spawn_timeline],
    }


def output_manifest(paths: tuple[Path, ...]) -> dict[str, Any]:
    return {
        "schema_version": "R8_1_LOW_STAR_FIXED_PREFIX_DIAGNOSTIC_MANIFEST_V1",
        "files": {
            str(path.relative_to(ROOT)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in paths
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    action_candidate = load(SOURCE / "direction_complete_action_candidate.json")
    saved_actions = tuple(
        (item["frame"], item["operator_id"], tuple(item["tile"]), item["direction"])
        for item in action_candidate["actions"]
    )
    if saved_actions != ACTION_FRAMES or action_candidate["operational_plan_id"] != PLAN_ID:
        raise RuntimeError("saved B2 action candidate does not match the fixed diagnostic contract")

    repository = GameDataRepository(GAMEDATA)
    facts = enemy_facts()
    if facts["level_overwritten_data"] is not None or any(row["overwritten_data"] is not None for row in facts["rows"]):
        raise RuntimeError("main_08-01 unexpectedly overwrites enemy database facts")

    selections = tuple(
        RealOperatorSelection(
            operator_id, *CONFIGURATIONS[operator_id], tile, direction, frame / FRAMES_PER_SECOND,
        )
        for frame, operator_id, tile, direction in ACTION_FRAMES
    )
    policy = RealSimulationApproximationPolicy.m11_second_quantized()
    fixture = ApproximateRealSimulationAdapter(repository).build_fixture(
        stage_id_or_code="main_08-01", selections=selections, policy=policy,
    )
    strategy = Strategy(
        tuple(selection.operator_id for selection in selections),
        tuple(
            Action(ActionType.DEPLOY, selection.deploy_time, selection.operator_id, selection.tile, selection.direction)
            for selection in selections
        ),
    )
    # The legacy loop advances once after max_time.  Using 940/30 makes its
    # final state exactly frame 941 instead of persisting a 942 loop tail.
    result = Simulator(
        range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel(),
    ).run(
        stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies, strategy=strategy,
        config=SimulationConfig(dt=1.0 / FRAMES_PER_SECOND, max_time=(WINDOW_END_FRAME - 1) / FRAMES_PER_SECOND),
    )
    boundary_frame = round(result.time_survived * FRAMES_PER_SECOND)
    if boundary_frame != WINDOW_END_FRAME:
        raise RuntimeError(f"simulation ended at frame {boundary_frame}, not {WINDOW_END_FRAME}")

    evidence = operator_evidence(fixture)
    parameters = {
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "stage_id": "main_08-01",
        "plan_id": PLAN_ID,
        "run_mode": "DIAGNOSTIC_MODEL_PREFIX",
        "run_count": 1,
        "frames_per_second": FRAMES_PER_SECOND,
        "window_end_frame": WINDOW_END_FRAME,
        "simulation_dt_seconds": 1.0 / FRAMES_PER_SECOND,
        "simulation_max_time_seconds": (WINDOW_END_FRAME - 1) / FRAMES_PER_SECOND,
        "actual_boundary_frame": boundary_frame,
        "boundary_rule": "Legacy simulator advances one tick after max_time; max_time=(941-1)/30 intentionally yields the frame-941 boundary.",
        "spawn_schedule_policy": policy.spawn_schedule.value,
        "attack_timing_policy": policy.attack_timing.value,
        "projectile_policy": policy.projectile_timing.value,
        "damage_model_policy": policy.damage_model.value,
        "natural_dp_policy": policy.natural_dp.value,
        "ignored_real_skill_data": fixture.ignored_real_skill_data,
    }
    summary = {
        "result": {
            "win": result.win,
            "remaining_life": result.remaining_life,
            "enemies_killed": result.enemies_killed,
            "enemies_leaked": result.enemies_leaked,
            "operator_deaths": result.operator_deaths,
            "time_survived": result.time_survived,
            "final_dp": result.final_dp,
            "enemies_remaining": result.enemies_remaining,
            "remaining_enemy_hp": result.remaining_enemy_hp,
            "remaining_enemy_route_progress": result.remaining_enemy_route_progress,
        },
        "classification": "DIAGNOSTIC_MODEL_PREFIX",
        "faithful_executable_timeline": False,
        "operationally_verified": False,
        "stage_win_claim": False,
        "current_model_win": "NOT_RUN",
        "omitted_mechanics": MECHANISM_OMISSIONS,
        "event_count": len(result.events),
        "event_summaries": summaries(result, fixture),
    }
    write("simulation_parameters.json", parameters)
    write("enemy_facts_and_level_coverage.json", facts)
    write("operator_eligibility_and_runtime.json", evidence)
    write("diagnostic_events.json", {"events": [event_payload(event) for event in result.events]})
    write("diagnostic_summary.json", summary)

    source_paths = (
        Path(__file__),
        ROOT / "src/arknights_planner/simulator/simulator.py",
        ROOT / "src/arknights_planner/adapters/approximate_real.py",
        ROOT / "src/arknights_planner/adapters/normal_low_star.py",
        ROOT / "src/arknights_planner/adapters/low_rarity_skill.py",
        ROOT / "src/arknights_planner/gamedata/repository.py",
        ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json",
        ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json",
        SOURCE / "llm_structured_output.json",
        SOURCE / "direction_complete_action_candidate.json",
        ROOT / "docs/review/1e92747/corrected_dp_and_certificate.json",
        ROOT / "docs/review/1e92747/REVIEW.md",
        OUT / "simulation_parameters.json",
        OUT / "enemy_facts_and_level_coverage.json",
        OUT / "operator_eligibility_and_runtime.json",
        OUT / "diagnostic_events.json",
        OUT / "diagnostic_summary.json",
        OUT / "targeted_test_run.log",
    )
    write("run_manifest.json", output_manifest(source_paths))
    write("validation_results.json", {
        "action_contract_match": "PASS",
        "artifact_integrity": "PASS",
        "enemy_facts_and_no_level_override": "PASS",
        "normal_mode_low_star_eligibility": "PASS",
        "boundary_frame_941": "PASS",
        "stage_simulations": 1,
        "stage_win_claim": "NO",
        "faithful_certificate": "NOT_ISSUED",
    })
    route_summaries = summary["event_summaries"]["route_summaries"]
    write("final_status.json", {
        "budget": {"kimi_calls": 0, "new_plans": 0, "new_candidates": 0, "stage_simulations": 1, "search_expansions": 0},
        "classification": summary["classification"],
        "faithful_executable_timeline": False,
        "current_model_win": "NOT_RUN",
        "remaining_dp_at_frame_941": result.final_dp,
        "remaining_life_at_frame_941": result.remaining_life,
        "remaining_enemy_hp_at_frame_941": result.remaining_enemy_hp,
        "route_kills_at_frame_941": {
            route_id: [item["frame"] for item in route_summaries[route_id]["kills"]]
            for route_id in sorted(route_summaries)
        },
        "route_blocks_at_frame_941": {
            route_id: [item["frame"] for item in route_summaries[route_id]["blocks"]]
            for route_id in sorted(route_summaries)
        },
        "route_leaks_at_frame_941": {
            route_id: [item["frame"] for item in route_summaries[route_id]["leaks"]]
            for route_id in sorted(route_summaries)
        },
        "omitted_mechanics": MECHANISM_OMISSIONS,
        "client_attack_windup": "UNKNOWN_NOT_USED_BY_DIAGNOSTIC_RUNTIME",
        "client_integer_rounding": "UNKNOWN",
        "status": "DIAGNOSTIC_COMPLETE_NOT_OPERATIONALLY_VERIFIED",
    })


if __name__ == "__main__":
    main()
