from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from dataclasses import is_dataclass

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.adapters.approximate_real import RealOperatorSelection
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator

from run_r8_1_lowstar_c2_full_diagnostic_v1 import (
    FRAMES_PER_SECOND, GAMEDATA, first_failure_context, json_value, load,
    event_payload, summaries, write_json,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli"
OUT = ROOT / "output/r8_1_gpt_tactical_batch_v1/r8_1_c7_roadblock_targeting_replay"
STAGE_ID = "main_08-01"
PLAN_ID = "R8_1_LOWSTAR_PLAN_C7"


def file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def event_difference(left: tuple[Any, ...], right: tuple[Any, ...]) -> dict[str, Any] | None:
    for index, (first, second) in enumerate(zip(left, right)):
        if first != second:
            return {"index": index, "a": json_value(first), "b": json_value(second)}
    if len(left) != len(right):
        return {"index": min(len(left), len(right)), "a_length": len(left), "b_length": len(right)}
    return None


def run_replay() -> dict[str, Any]:
    out = OUT
    out.mkdir(parents=True, exist_ok=True)
    static = load(SOURCE / "static_compile_results.json")
    candidate = load(SOURCE / "direction_complete_action_candidate.json")
    evidence = load(SOURCE / "llm_evidence_context.json")
    plan = load(SOURCE / "llm_structured_output.json")["revised_operational_plans"][0]
    if candidate["operational_plan_id"] != PLAN_ID or static["conflicts"]:
        raise SystemExit("roadblock replay premise not met")
    actions = candidate["actions"]
    catalog = {row["operator_id"]: row for row in evidence["normal_low_star_catalog"]}
    deployments = [action for action in actions if action["action_type"] == "DEPLOY"]
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
    strategy_actions = [
        Action(
            ActionType[action["action_type"]],
            int(action["frame"]) / FRAMES_PER_SECOND,
            action["operator_id"],
            (int(action["tile"][1]), int(action["tile"][0])) if "tile" in action else None,
            action.get("direction"),
        )
        for action in actions
    ]
    policy = RealSimulationApproximationPolicy.m11_second_quantized()
    fixture = ApproximateRealSimulationAdapter(GameDataRepository(GAMEDATA)).build_fixture(
        stage_id_or_code=STAGE_ID, selections=selections, policy=policy,
    )
    strategy = Strategy(tuple(action["operator_id"] for action in deployments), tuple(strategy_actions))
    variants: dict[str, Any] = {}
    events_by_variant: dict[str, tuple[Any, ...]] = {}
    for variant, ordinary_targetable in (
        ("A_NOT_ORDINARILY_TARGETABLE", False),
        ("B_LOW_PRIORITY_NO_ENEMY_ONLY", True),
    ):
        stage = replace(
            fixture.stage,
            devices=tuple(
                replace(device, ordinary_targetable=ordinary_targetable)
                for device in fixture.stage.devices
            ),
        )
        result = Simulator(
            range_transformer=ApproximateRealRangeTransformer(),
            projectile_model=InstantProjectileModel(),
        ).run(
            stage=stage, operators=fixture.operators, enemies=fixture.enemies,
            strategy=strategy, config=SimulationConfig(dt=1 / FRAMES_PER_SECOND, max_time=600.0),
        )
        events = [event_payload(event) for event in result.events]
        device_damage = [row for row in events if row["event_type"] == "DEVICE_DAMAGE"]
        variants[variant] = {
            "ordinary_targetable": ordinary_targetable,
            "result": json_value(result),
            "event_count": len(events),
            "event_summaries": summaries(events),
            "first_failure": first_failure_context(events),
            "roadblock_attack_count": len(device_damage),
            "roadblock_damage_sources": sorted({row["source_id"] for row in device_damage}),
        }
        write_json(out / f"{variant.lower()}_events.json", {"events": events})
        events_by_variant[variant] = result.events
    all_win = all(row["result"]["win"] for row in variants.values())
    audit = {
        "schema_version": "R8_1_C7_ROADBLOCK_TARGETING_REPLAY_V1",
        "classification": "CONDITIONAL_MODEL_ROADBLOCK_TARGETING_REPLAY",
        "plan_id": PLAN_ID,
        "policy": policy.names,
        "frames_per_second": FRAMES_PER_SECOND,
        "simulation_dt_seconds": 1 / FRAMES_PER_SECOND,
        "simulation_max_time_seconds": 600.0,
        "action_count": len(actions),
        "action_contract": actions,
        "same_action_timeline": True,
        "variants": variants,
        "first_divergent_event": event_difference(
            events_by_variant["A_NOT_ORDINARILY_TARGETABLE"],
            events_by_variant["B_LOW_PRIORITY_NO_ENEMY_ONLY"],
        ),
        "all_variants_win": all_win,
        "robust_roadblock_targeting_claim": "SUPPORTED_WITHIN_TWO_VARIANTS" if all_win else "NOT_SUPPORTED",
        "real_game_win_claim": False,
        "omitted_or_unknown_mechanics": evidence["simulation_domain"]["omitted_or_unknown_mechanics"],
    }
    write_json(out / "roadblock_targeting_replay_summary.json", audit)
    write_json(out / "run_manifest.json", {
        "schema_version": "R8_1_C7_ROADBLOCK_TARGETING_REPLAY_MANIFEST_V1",
        "files": {
            str(SOURCE / "llm_structured_output.json"): file_record(SOURCE / "llm_structured_output.json"),
            str(SOURCE / "direction_complete_action_candidate.json"): file_record(SOURCE / "direction_complete_action_candidate.json"),
            str(SOURCE / "static_compile_results.json"): file_record(SOURCE / "static_compile_results.json"),
            str(Path(__file__).resolve()): file_record(Path(__file__).resolve()),
        },
    })
    final = {
        "conditional_model_win": bool(variants["B_LOW_PRIORITY_NO_ENEMY_ONLY"]["result"]["win"]),
        "all_roadblock_targeting_variants_win": all_win,
        "robust_roadblock_targeting_claim": audit["robust_roadblock_targeting_claim"],
        "real_game_win_claim": False,
        "status": "REPLAY_COMPLETE",
    }
    write_json(out / "final_status.json", final)
    return audit


if __name__ == "__main__":
    summary = run_replay()
    print(json.dumps({
        "all_variants_win": summary["all_variants_win"],
        "results": {name: row["result"] for name, row in summary["variants"].items()},
    }, sort_keys=True))
