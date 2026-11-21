"""R126: rerun archived frozen five-op plan under m40f mechanics (offline diagnostic)."""
from __future__ import annotations
import json, sys, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from arknights_planner.adapters.approximate_real import ApproximateRealSimulationAdapter, RealOperatorSelection, RealSimulationApproximationPolicy
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import Simulator, SimulationConfig
from arknights_planner.simulator.range import ApproximateRealRangeTransformer
from arknights_planner.simulator.projectile import InstantProjectileModel
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION

FRAMES = 30.0
STAGE_ID = "main_08-07"
GAMEDATA = ROOT / "data/ArknightsGameData"


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def run(source: Path, out: Path, plan_id: str) -> None:
    source = source if source.is_absolute() else ROOT / source
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    candidate = json.loads((source / "direction_complete_action_candidate.json").read_text())
    evidence = json.loads((source / "llm_evidence_context.json").read_text())
    plan = json.loads((source / "llm_structured_output.json").read_text())["revised_operational_plans"][0]
    if candidate["operational_plan_id"] != plan_id:
        raise SystemExit("plan id mismatch")
    actions = candidate["actions"]
    catalog = {row["operator_id"]: row for row in evidence["normal_low_star_catalog"]}
    deployments = [action for action in actions if action["action_type"] == "DEPLOY"]
    if {a["operator_id"] for a in deployments} != set(plan["selected_low_star_operator_ids"]):
        raise SystemExit("deploy set != selected")
    selections = tuple(
        RealOperatorSelection(
            action["operator_id"],
            int(catalog[action["operator_id"]]["debug_configuration"]["phase_index"]),
            int(catalog[action["operator_id"]]["debug_configuration"]["level"]),
            (int(action["tile"][1]), int(action["tile"][0])),
            action["direction"],
            int(action["frame"]) / FRAMES,
        )
        for action in deployments
    )
    strategy_actions = []
    for action in actions:
        at = {"DEPLOY": ActionType.DEPLOY, "ACTIVATE_SKILL": ActionType.ACTIVATE_SKILL, "RETREAT": ActionType.RETREAT}[action["action_type"]]
        tile = (int(action["tile"][1]), int(action["tile"][0])) if "tile" in action else None
        strategy_actions.append(Action(at, int(action["frame"]) / FRAMES, action["operator_id"], tile, action.get("direction")))
    policy = RealSimulationApproximationPolicy.m11_second_quantized()
    fixture = ApproximateRealSimulationAdapter(GameDataRepository(GAMEDATA)).build_fixture(
        stage_id_or_code=STAGE_ID, selections=selections, policy=policy)
    strategy = Strategy(tuple(a["operator_id"] for a in deployments), tuple(strategy_actions))
    result = Simulator(range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel()).run(
        stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies,
        strategy=strategy, config=SimulationConfig(dt=1 / FRAMES, max_time=600.0))
    events = [{"time": e.time, "frame": round(e.time * FRAMES), "event_type": e.event_type.value,
               "source_id": e.source_id, "target_id": e.target_id, "details": dict(e.details)} for e in result.events]
    leaks = [e for e in events if e["event_type"] == "ENEMY_LEAK"]
    deaths = [e for e in events if e["event_type"] == "OPERATOR_DEATH"]
    summary = {
        "classification": "R126_MECH40_RERUN_DIAGNOSTIC_LOSS_OR_WIN",
        "mechanics_version": ACTIVE_MECHANICS_VERSION,
        "parent_plan_id": plan_id,
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.iterdir())},
        "simulator_win": bool(result.win),
        "enemies_killed": result.enemies_killed,
        "enemies_leaked": result.enemies_leaked,
        "remaining_life": result.remaining_life,
        "operator_deaths": result.operator_deaths,
        "leak_ids": [e["source_id"] for e in leaks],
        "event_count": len(events),
    }
    write_json(out / "simulation_parameters.json", {"mechanics_version": ACTIVE_MECHANICS_VERSION, "stage_id": STAGE_ID,
                                                    "plan_id": plan_id, "dt": 1 / FRAMES, "max_time": 600.0,
                                                    "run_mode": "R126_MECH40_RERUN_DIAGNOSTIC"})
    write_json(out / "diagnostic_events.json", {"events": events})
    write_json(out / "diagnostic_summary.json", summary)
    write_json(out / "final_status.json", summary)
    print(json.dumps(summary, ensure_ascii=False)[:600])


if __name__ == "__main__":
    run(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
