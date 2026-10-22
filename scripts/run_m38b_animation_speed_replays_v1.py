from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION
from build_m36_key_chain_summary_v1 import build
from run_gpt_tactical_stage_diagnostic_v1 import run_full_diagnostic


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07"
OUT = BASE / "m38b_animation_speed_correction_v1"
REPLAY_SOURCES = {
    "m30_v2": (
        "R8_7_GPT_M30_V2",
        BASE / "m36_client_behavior_reverification_v1/m30_v2_static_check",
    ),
    "m31_v3": (
        "R8_7_GPT_M31_V3",
        BASE / "m36_client_behavior_reverification_v1/m31_v3_static_check",
    ),
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def source_plan(source: Path) -> dict[str, Any]:
    return load(source / "llm_structured_output.json")["revised_operational_plans"][0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.dry_run and args.resume:
        raise RuntimeError("Use either --dry-run or --resume, not both")
    if args.resume:
        if not OUT.is_dir():
            raise RuntimeError(f"M38b replay output directory is absent: {OUT}")
    elif OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"M38b replay output directory is not empty: {OUT}")
    frozen_inputs = {
        "mechanics_version": ACTIVE_MECHANICS_VERSION,
        "implementation": {
            "simulator": file_record(ROOT / "src/arknights_planner/simulator/simulator.py"),
            "enemy_model": file_record(ROOT / "src/arknights_planner/models/enemy.py"),
            "gamedata_repository": file_record(ROOT / "src/arknights_planner/gamedata/repository.py"),
            "mechanics_registry": file_record(ROOT / "src/arknights_planner/mechanics.py"),
        },
        "simulation_inputs": {
            name: {path.name: file_record(path) for path in sorted(source.glob("llm_*.json"))}
            for name, (_, source) in REPLAY_SOURCES.items()
        },
    }
    ledger: dict[str, Any] = {
        "schema_version": "M38B_ANIMATION_SPEED_REPLAY_BUDGET_V1",
        "stage_simulations_max": 2,
        "stage_simulations_started": 0,
        "stage_simulations_completed": 0,
        "stage_simulations_failed": 0,
        "tactical_cli_starts": 0,
        "budget_inheritance": "M38 correction round; independent 2-run authorization",
        "runs": {},
    }
    if args.resume:
        frozen_inputs = load(OUT / "frozen_inputs.json")
        ledger = load(OUT / "m38b_simulation_budget_v1.json")
        ledger["budget_integrity"] = "RESUMING_EXISTING_LEDGER"
    if args.dry_run:
        print(json.dumps({"frozen_inputs": frozen_inputs, "budget": ledger}, indent=2, sort_keys=True))
        return
    if not args.resume:
        OUT.mkdir(parents=True)
        write_json(OUT / "frozen_inputs.json", frozen_inputs)
        write_json(OUT / "m38b_simulation_budget_v1.json", ledger)
    try:
        for index, (name, (plan_id, source)) in enumerate(REPLAY_SOURCES.items(), 1):
            existing = ledger["runs"].get(name)
            if existing and existing.get("status") == "COMPLETED":
                continue
            reservation = {
                "schema_version": "M38B_ANIMATION_SPEED_REPLAY_RESERVATION_V1",
                "run": name,
                "reservation_index": index,
                "plan_id": plan_id,
                "stage_id": "main_08-07",
                "status": "RESERVED",
                "automatic_retry": False,
            }
            write_json(OUT / f"{name}.simulation_reservation.json", reservation)
            ledger["runs"][name] = reservation
            if not existing:
                ledger["stage_simulations_started"] = index
            write_json(OUT / "m38b_simulation_budget_v1.json", ledger)
            replay = OUT / f"{name}_replay"
            if not args.resume or not replay.is_dir() or not any(replay.iterdir()):
                run_full_diagnostic(source=source, out=replay, stage_id="main_08-07", plan_id=plan_id)
            plan = source_plan(source)
            plan_match = plan == load(replay / "plan_snapshot.json")
            if not plan_match:
                raise RuntimeError(f"M38b replay plan mismatch: {name}")
            write_json(replay / "m38b_key_chain_summary.json", build(replay))
            completed = {
                **reservation,
                "status": "COMPLETED",
                "resume_note": "Simulation completed before ledger finalization; no replay was repeated." if existing else None,
                "plan_match": plan_match,
                "mechanics_version": ACTIVE_MECHANICS_VERSION,
                "action_snapshot": file_record(replay / "action_snapshot.json"),
                "plan_snapshot": file_record(replay / "plan_snapshot.json"),
                "diagnostic_events": file_record(replay / "diagnostic_events.json"),
                "diagnostic_summary": file_record(replay / "diagnostic_summary.json"),
                "manifest": file_record(replay / "manifest.json"),
            }
            write_json(OUT / f"{name}.simulation_reservation.json", completed)
            ledger["runs"][name] = completed
            ledger["stage_simulations_completed"] = index
            write_json(OUT / "m38b_simulation_budget_v1.json", ledger)
    except Exception:
        ledger["budget_integrity"] = "STOPPED_CHECK_LEDGER_AND_RESERVATIONS"
        write_json(OUT / "m38b_simulation_budget_v1.json", ledger)
        raise
    ledger["budget_integrity"] = "OK"
    write_json(OUT / "m38b_simulation_budget_v1.json", ledger)

    package = ROOT / "docs/review/fc77177/m38b_animation_speed_correction_v1/replays"
    for name in REPLAY_SOURCES:
        source_dir = OUT / f"{name}_replay"
        destination = package / name
        destination.mkdir(parents=True, exist_ok=True)
        for filename in (
            "action_snapshot.json",
            "plan_snapshot.json",
            "final_status.json",
            "m38b_key_chain_summary.json",
            "manifest.json",
            "simulation_parameters.json",
            "simulation_attempt.json",
        ):
            shutil.copy2(source_dir / filename, destination / filename)
        for filename in ("diagnostic_events.json", "diagnostic_summary.json"):
            raw = (source_dir / filename).read_bytes()
            compressed_path = destination / f"{filename}.gz"
            compressed_path.write_bytes(gzip.compress(raw, mtime=0))
            write_json(destination / f"{filename}.hashes.json", {
                "sha256_before_gzip": hashlib.sha256(raw).hexdigest(),
                "sha256_after_gzip": hashlib.sha256(compressed_path.read_bytes()).hexdigest(),
                "bytes_before_gzip": len(raw),
                "bytes_after_gzip": compressed_path.stat().st_size,
            })


if __name__ == "__main__":
    main()
