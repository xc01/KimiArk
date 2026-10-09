from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationAdapter, RealSimulationApproximationPolicy, M13LoadoutPolicy
from arknights_planner.gamedata import GameDataInspector, GameDataRepository, client_frame_timing_report
from arknights_planner.benchmark import chapter_mid_late_census, low_rarity_census, runtime_coverage_report, stage_benchmark_census
from arknights_planner.models.provenance import KnowledgeStatus
from arknights_planner.simulator import basic_mechanic_audit_report


def _json_default(value: Any) -> Any:
    if isinstance(value, KnowledgeStatus):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _root(value: str | None) -> Path:
    return Path(value or os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))


def _print(value: Any) -> None:
    print(json.dumps(value, default=_json_default, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(prog="arknights-data", description="Read-only ArknightsGameData archaeology commands")
    parser.add_argument("--data-root", help="Path to the ArknightsGameData checkout")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect-repository")
    table = commands.add_parser("inspect-table"); table.add_argument("file")
    operator = commands.add_parser("inspect-operator"); operator.add_argument("name_or_id")
    operator.add_argument("--resolve-relations", action="store_true", help="Also resolve referenced skills and attack ranges")
    enemy = commands.add_parser("inspect-enemy"); enemy.add_argument("name_or_id")
    stage = commands.add_parser("inspect-stage"); stage.add_argument("stage_id")
    compatibility = commands.add_parser("simulation-compatibility", help="Explain strict real-data simulation blockers; never runs a battle")
    compatibility.add_argument("stage_id")
    compatibility.add_argument("--operator", default="char_002_amiya")
    compatibility.add_argument("--operator-phase", type=int, default=0)
    compatibility.add_argument("--operator-level", type=int, default=1)
    compatibility.add_argument("--enemy", default="enemy_1007_slime")
    compatibility.add_argument("--enemy-level", type=int, default=0)
    compatibility.add_argument("--skill-level", type=int, default=0)
    approximate_view = commands.add_parser("approximate-stage-view", help="Show explicit 0-1 tile and spawn approximations; never runs a battle")
    approximate_view.add_argument("stage_id")
    commands.add_parser("client-frame-timing", help="Show local APK frame/timing evidence; never launches a client")
    commands.add_parser("mechanics-audit", help="Show PRTS-source-separated basic combat implementation audit")
    commands.add_parser("low-rarity-mechanics", help="Census locally obtainable 1-3 star operator mechanics")
    commands.add_parser("low-rarity-loadouts", help="Show deterministic high-progression loadouts for eligible 1-3 star operators")
    commands.add_parser("low-rarity-runtime-coverage", help="Summarize executable/blocked low-rarity runtime mechanics")
    benchmark_stages = commands.add_parser("benchmark-stages", help="Show bounded Chapter 6-11 benchmark candidates and blockers")
    benchmark_stages.add_argument("--chapters", nargs="*", type=int, default=(6, 7, 8, 9, 10, 11))
    m11_stages = commands.add_parser("m11-stage-candidates", help="Census ordinary Chapter 6-11 stages by within-chapter progression")
    m11_stages.add_argument("--chapters", nargs="*", type=int, default=(6, 7, 8, 9, 10, 11))
    args = parser.parse_args(argv)
    root = _root(args.data_root)
    inspector = GameDataInspector(root)
    if args.command == "inspect-repository": _print(inspector.repository_report())
    elif args.command == "client-frame-timing": _print(client_frame_timing_report(Path("data/client")))
    elif args.command == "mechanics-audit": _print(basic_mechanic_audit_report())
    elif args.command == "low-rarity-mechanics": _print(low_rarity_census(GameDataRepository(root)))
    elif args.command == "low-rarity-loadouts":
        repo = GameDataRepository(root)
        policy = M13LoadoutPolicy.highest_legal()
        rows = []
        for record in low_rarity_census(repo):
            try:
                cfg = policy.configuration(repo, record.operator_id)
            except Exception as exc:
                rows.append({"operator_id": record.operator_id, "name": record.name, "error": str(exc)})
                continue
            op = repo.get_operator(record.operator_id)
            phase = op.phases[cfg.phase_index]
            key = next(k for k in phase.keyframes if k.level.value == cfg.level)
            rows.append({"operator_id": record.operator_id, "name": record.name, "rarity": record.rarity,
                         "phase": cfg.phase_index, "level": cfg.level, "skill_level_index": cfg.skill_level_index,
                         "cost": key.stats.cost.value, "hp": key.stats.max_hp.value, "atk": key.stats.atk.value,
                         "def": key.stats.defense.value, "res": key.stats.magic_resistance.value,
                         "block": key.stats.block_count.value, "attack_interval": key.stats.attack_interval.value,
                         "range_id": phase.range_id.value, "runtime_status": record.runtime_status.value})
        _print({"policy": "M13_HIGHEST_LEGAL_EXACT_KEYFRAME", "trust": "neutral", "potential": "neutral", "operators": rows})
    elif args.command == "low-rarity-runtime-coverage": _print(runtime_coverage_report(GameDataRepository(root)))
    elif args.command == "benchmark-stages": _print(tuple(record for record in stage_benchmark_census(GameDataRepository(root)) if record.chapter in args.chapters))
    elif args.command == "m11-stage-candidates": _print(chapter_mid_late_census(GameDataRepository(root), chapters=tuple(args.chapters)))
    elif args.command == "inspect-table": _print(inspector.inspect_table(args.file).to_dict())
    else:
        repo = GameDataRepository(root)
        if args.command == "inspect-operator":
            resolved = repo.get_operator(args.name_or_id)
            if not args.resolve_relations:
                _print(resolved)
                return
            range_ids = {phase.range_id.value for phase in resolved.phases if phase.range_id.value}
            skills = [repo.get_skill(skill_id) for skill_id in resolved.skill_ids]
            range_ids.update(
                level.range_id.value for skill in skills for level in skill.levels if level.range_id.value
            )
            _print({
                "operator": resolved,
                "skills": skills,
                "ranges": [repo.get_range(range_id) for range_id in sorted(range_ids)],
            })
        elif args.command == "inspect-enemy": _print(repo.get_enemy(args.name_or_id))
        elif args.command == "inspect-stage": _print(repo.stage_reconstruction_report(args.stage_id))
        elif args.command == "simulation-compatibility":
            bundle = RealSimulationAdapter(repo).adapt_combination(
                operator_id_or_name=args.operator, operator_phase=args.operator_phase, operator_level=args.operator_level,
                enemy_id_or_name=args.enemy, enemy_level=args.enemy_level, stage_id_or_code=args.stage_id,
                skill_level_index=args.skill_level,
            )
            _print({
                "stage_id": bundle.stage.stage.stage_id,
                "operator_id": bundle.operator.operator.operator_id,
                "enemy_id": bundle.enemy.enemy.enemy_id,
                "structurally_loadable": bundle.report.structurally_loadable,
                "simulator_executable": bundle.report.simulator_executable,
                "status_counts": {status.value: count for status, count in bundle.report.status_counts},
                "blockers": bundle.report.blockers,
            })
        else:
            if args.stage_id != "0-1":
                parser.error("approximate-stage-view currently supports only 0-1")
            policy = RealSimulationApproximationPolicy.main_00_01()
            tiles, timeline = ApproximateRealSimulationAdapter(repo).inspect_stage_approximations(
                stage_id_or_code=args.stage_id, policy=policy,
            )
            _print({
                "mode": "APPROXIMATE_REAL_INSPECTION",
                "approximations_used": policy.names,
                "tile_mappings": tiles,
                "approximated_spawn_timeline": timeline,
            })


if __name__ == "__main__":
    main()
