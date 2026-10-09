from __future__ import annotations

import argparse
import json
from dataclasses import asdict
import os
from pathlib import Path

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealExecutionMode, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search import ApproximateRealBeamSearch, BeamSearch, M11MinimumSquadSearch, M11SearchConfig, RealSearchConfig, M13LayeredSearch
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage
from arknights_planner.models.timeline import FrameTimeline
from arknights_planner.benchmark import HumanFailureCategory, HumanValidationRecord, HumanValidationStatus, render_human_timeline, stage_benchmark_census, low_rarity_census
from arknights_planner.agent.tactical import MockLLMRuntime, RealLLMRuntime, stage_analysis, tactical_requirements, operator_context, validate_hypothesis, provider_configuration_status
from arknights_planner.architecture import ArchitectureAudit
from arknights_planner.search.m14_ground import load_hypotheses, run_grounded, grounding_rejections, run_cardinality_audit
from arknights_planner.search.m14_repair import M14LocalRepairSearch
from arknights_planner.search.m14_opening import M14OpeningRepairSearch
from arknights_planner.search.m14_economy import M14OpeningEconomyRepair
from arknights_planner.search.m14_geometry import M14OpeningGeometrySearch
from arknights_planner.search.m14_fidelity import M14OpeningEconomyFidelityAudit
from arknights_planner.search.m15 import ConstraintGuidedFeasibilityPlanner
from arknights_planner.search.m15_repair import FailureFrontierRepair
from arknights_planner.search.mechanics_rebaseline import MechanicsRebaseline
from arknights_planner.search.m15_requirements import FrontierRequirementSolver
from arknights_planner.search.m15_multifrontier import MultiFrontierSolver
from arknights_planner.search.m15_falco import FalcoResourceAudit
from arknights_planner.search.m16_causal import CausalCombatAudit
from arknights_planner.search.m17_causal_temporal import CausalTemporalAudit
from arknights_planner.search.m18_targeting import TargetingFidelityAudit
from arknights_planner.search.m18_1_readiness import TargetingReadinessAudit
from arknights_planner.search.m19_uncertainty import UncertaintyGuardedRepair
from arknights_planner.search.m20_capability import CapabilityInterventionSynthesis
from arknights_planner.search.m21_information import InformationEfficientCausalSearch
from arknights_planner.search.m22_frontier import FrontierFeasibilityAudit
from arknights_planner.search.m23_calibration import M23CalibrationPacket
from arknights_planner.mechanics_registry import MechanicsEvidenceRegistry
from arknights_planner.search.m18_rebaseline import TargetingRebaseline
from arknights_planner.search.scope import ExperimentScope
from arknights_planner.search.top_down import TopDownPlanner
from arknights_planner.search.top_down_validation import TopDownValidation


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="arknights-plan", description="Synthetic Arknights planner experiments")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="Discover a winning strategy for the synthetic stage")
    real_demo = commands.add_parser("real-demo", help="Run the explicit APPROXIMATE_REAL 0-1 calibration fixture")
    real_demo.add_argument("stage_id")
    real_demo.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))
    real_search = commands.add_parser("real-search", help="Search deployment-only APPROXIMATE_REAL strategies for 0-1")
    real_search.add_argument("stage_id")
    real_search.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))
    real_search.add_argument("--timing", choices=("seconds", "frames"), default="frames")
    human = commands.add_parser("human-timeline", help="Render a neutral FrameTimeline as a human test sheet")
    human.add_argument("timeline", type=Path)
    human.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))
    human.add_argument("--simulator-result", default="UNTESTED")
    validate = commands.add_parser("validate", help="Persist a manual validation result; never fits simulator parameters")
    validate.add_argument("timeline", type=Path)
    validate.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))
    status = validate.add_mutually_exclusive_group(required=True)
    status.add_argument("--pass", dest="validation_status", action="store_const", const="PASS")
    status.add_argument("--fail", dest="validation_status", action="store_const", const="FAIL")
    status.add_argument("--inconclusive", dest="validation_status", action="store_const", const="INCONCLUSIVE")
    validate.add_argument("--failure-frame", type=int)
    validate.add_argument("--failure-category", choices=[item.value for item in HumanFailureCategory])
    validate.add_argument("--note")
    validate.add_argument("--output", type=Path, required=True)
    benchmark = commands.add_parser("benchmark-search", help="Run a bounded benchmark only when its compatibility is explicit")
    benchmark.add_argument("stage_id")
    benchmark.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))
    benchmark.add_argument("--output-dir", type=Path, default=Path("output/benchmarks"))
    m11 = commands.add_parser("m11-search", help="Run the bounded approximate-real M11 minimum-squad experiment")
    m11.add_argument("stage_id", choices=("6-8",))
    m11.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))
    m11.add_argument("--output-dir", type=Path, default=Path("output/benchmarks"))
    m12 = commands.add_parser("m12-search", help="Run bounded full eligible 1-3 star pool search for 6-8")
    m12.add_argument("stage_id", choices=("6-8",))
    m12.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))
    m12.add_argument("--output-dir", type=Path, default=Path("output/benchmarks"))
    m13 = commands.add_parser("m13-search", help="Run layered exhaustive K1/K2 low-rarity search for 6-8")
    m13.add_argument("stage_id", choices=("6-8",))
    m13.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData"))
    m14 = commands.add_parser("m14-llm-pilot", help="Run bounded tactical-hypothesis pilot for 6-8")
    m14.add_argument("stage_id", choices=("6-8",)); m14.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m14.add_argument("--llm-real", action="store_true"); m14.add_argument("--max-llm-calls", type=int, default=3); m14.add_argument("--llm-timeout-seconds", type=float, default=45.0); m14.add_argument("--output-dir", type=Path, default=Path("output/m14"))
    revise = commands.add_parser("m14-llm-revise", help="Use one bounded real revision call from preserved M14 evidence")
    revise.add_argument("stage_id", choices=("6-8",)); revise.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); revise.add_argument("--llm-timeout-seconds", type=float, default=300.0); revise.add_argument("--output-dir", type=Path, default=Path("output/m14"))
    cardinality = commands.add_parser("m14-cardinality-audit", help="Validate preserved M14 revision cardinality pressure without an LLM call")
    cardinality.add_argument("stage_id", choices=("6-8",)); cardinality.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); cardinality.add_argument("--output-dir", type=Path, default=Path("output/m14")); cardinality.add_argument("--simulation-budget", type=int, default=500)
    repair = commands.add_parser("m14-local-repair", help="Bounded feasibility-first repair around preserved R1/R4 structures; makes no LLM calls")
    repair.add_argument("stage_id", choices=("6-8",)); repair.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); repair.add_argument("--output-dir", type=Path, default=Path("output/m14")); repair.add_argument("--simulation-budget", type=int, default=1500); repair.add_argument("--beam-width", type=int, default=8)
    opening = commands.add_parser("m14-opening-repair", help="Audit and repair the fixed R4 K=7 opening only; makes no LLM calls")
    opening.add_argument("stage_id", choices=("6-8",)); opening.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); opening.add_argument("--output-dir", type=Path, default=Path("output/m14")); opening.add_argument("--simulation-budget", type=int, default=500); opening.add_argument("--opening-horizon-frame", type=int, default=900)
    economy = commands.add_parser("m14-opening-economy-repair", help="Constrained R4 K=7 roster repair for early-route DP economy; makes no LLM calls")
    economy.add_argument("stage_id", choices=("6-8",)); economy.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); economy.add_argument("--output-dir", type=Path, default=Path("output/m14")); economy.add_argument("--simulation-budget", type=int, default=1000); economy.add_argument("--opening-horizon-frame", type=int, default=900)
    geometry = commands.add_parser("m14-opening-geometry", help="Fixed-R4+Plume K=7 shared-route opening geometry audit; makes no LLM calls")
    geometry.add_argument("stage_id", choices=("6-8",)); geometry.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); geometry.add_argument("--output-dir", type=Path, default=Path("output/m14")); geometry.add_argument("--simulation-budget", type=int, default=800); geometry.add_argument("--opening-horizon-frame", type=int, default=900)
    fidelity = commands.add_parser("m14-opening-economy-audit", help="Audit source-backed low-rarity opening-economy mechanics; no LLM or strategy search")
    fidelity.add_argument("stage_id", choices=("6-8",)); fidelity.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); fidelity.add_argument("--output-dir", type=Path, default=Path("output/m14"))
    m15 = commands.add_parser("m15-feasibility", help="Constraint-guided bounded feasibility search for 6-8; no LLM or minimization")
    m15.add_argument("stage_id", choices=("6-8",)); m15.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m15.add_argument("--output-dir", type=Path, default=Path("output/m15")); m15.add_argument("--simulation-budget", type=int, default=2000); m15.add_argument("--beam-width", type=int, default=12); m15.add_argument("--max-cardinality", type=int, default=7)
    m15_repair = commands.add_parser("m15-frontier-repair", help="Closed-loop repair from preserved M15 parent; no LLM, mechanics expansion, or minimization")
    m15_repair.add_argument("stage_id", choices=("6-8",)); m15_repair.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m15_repair.add_argument("--output-dir", type=Path, default=Path("output/m15")); m15_repair.add_argument("--guided-budget", type=int, default=600); m15_repair.add_argument("--control-budget", type=int, default=200)
    rebaseline = commands.add_parser("mechanics-rebaseline", help="Replay preserved 6-8 strategies after a mechanics change; no search")
    rebaseline.add_argument("stage_id", choices=("6-8",)); rebaseline.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); rebaseline.add_argument("--artifact-root", type=Path, default=Path("output")); rebaseline.add_argument("--output-dir", type=Path, default=Path("output/rebaseline"))
    m15_requirements = commands.add_parser("m15-requirement-repair", help="Bounded M15.2 quantified frontier repair; no LLM, mechanics expansion, or minimization")
    m15_requirements.add_argument("stage_id", choices=("6-8",)); m15_requirements.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m15_requirements.add_argument("--output-dir", type=Path, default=Path("output/m15")); m15_requirements.add_argument("--simulation-budget", type=int, default=400)
    m15_multifrontier = commands.add_parser("m15-multifrontier", help="Bounded M15.3 multi-frontier resource conflict solver; no LLM or mechanics expansion")
    m15_multifrontier.add_argument("stage_id", choices=("6-8",)); m15_multifrontier.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m15_multifrontier.add_argument("--output-dir", type=Path, default=Path("output/m15")); m15_multifrontier.add_argument("--simulation-budget", type=int, default=600)
    falco = commands.add_parser("m15-falco-decoupling", help="Bounded M15.4 Falco critical-resource audit; no LLM, mechanics expansion, or minimization")
    falco.add_argument("stage_id", choices=("6-8",)); falco.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); falco.add_argument("--output-dir", type=Path, default=Path("output/m15")); falco.add_argument("--simulation-budget", type=int, default=150)
    m16 = commands.add_parser("m16-causal-audit", help="Paired Falco intervention causal replay; no search or LLM")
    m16.add_argument("stage_id", choices=("6-8",)); m16.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m16.add_argument("--output-dir", type=Path, default=Path("output/m16"))
    m17 = commands.add_parser("m17-causal-temporal", help="Build causal-temporal constraints from M16 evidence; diagnostic only")
    m17.add_argument("stage_id", choices=("6-8",)); m17.add_argument("--output-dir", type=Path, default=Path("output/m17"))
    m18 = commands.add_parser("m18-targeting-audit", help="Targeting fidelity audit and paired M16 replay; no search")
    m18.add_argument("stage_id", choices=("6-8",)); m18.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m18.add_argument("--output-dir", type=Path, default=Path("output/m18"))
    m181 = commands.add_parser("m18-1-readiness", help="Targeting uncertainty boundary and search readiness gate; diagnostic only")
    m181.add_argument("stage_id", choices=("6-8",)); m181.add_argument("--output-dir", type=Path, default=Path("output/m18_1"))
    m19 = commands.add_parser("m19-causal-repair", help="Uncertainty-guarded causal repair search; no LLM or mechanics expansion")
    m19.add_argument("stage_id", choices=("6-8",)); m19.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m19.add_argument("--output-dir", type=Path, default=Path("output/m19")); m19.add_argument("--simulation-budget", type=int, default=300); m19.add_argument("--beam-width", type=int, default=10)
    m20 = commands.add_parser("m20-capability-synthesis", help="Constraint-to-capability intervention synthesis; no broad search")
    m20.add_argument("stage_id", choices=("6-8",)); m20.add_argument("--output-dir", type=Path, default=Path("output/m20"))
    m21 = commands.add_parser("m21-causal-search", help="Information-efficient causal search; no LLM or mechanics expansion")
    m21.add_argument("stage_id", choices=("6-8",)); m21.add_argument("--data-root", default=os.getenv("ARKNIGHTS_GAMEDATA_ROOT", "data/ArknightsGameData")); m21.add_argument("--output-dir", type=Path, default=Path("output/m21")); m21.add_argument("--simulation-budget", type=int, default=120)
    m22 = commands.add_parser("m22-frontier-audit", help="Diagnostic frontier feasibility decomposition; no strategy search")
    m22.add_argument("stage_id", choices=("6-8",)); m22.add_argument("--output-dir", type=Path, default=Path("output/m22"))
    m23 = commands.add_parser("m23-calibration-plan", help="Generate target-allocation black-box calibration packet")
    m23.add_argument("stage_id", choices=("6-8",)); m23.add_argument("--output-dir", type=Path, default=Path("output/m23"))
    m183 = commands.add_parser("m18-targeting-rebaseline", help="Rebaseline targeting after PRTS path-distance correction")
    m183.add_argument("stage_id", choices=("6-8",)); m183.add_argument("--output-dir", type=Path, default=Path("output/m18_rebaseline"))
    architecture = commands.add_parser("architecture-audit", help="Generate architecture, evidence, scope, and versioning audit artifacts")
    architecture.add_argument("--data-root", type=Path, default=Path("data/ArknightsGameData"))
    architecture.add_argument("--output-dir", type=Path, default=Path("output/architecture_alignment"))
    architecture.add_argument("--run-smoke", action="store_true", help="Run one tiny deterministic non-LLM top-down smoke")
    architecture.add_argument("--smoke-stage", choices=("0-1",), default="0-1")
    architecture.add_argument("--validation-json", type=Path)
    top_down_validation = commands.add_parser(
        "top-down-validation",
        help="Run deterministic semantic cross-stage validation and a bounded first-WIN attempt",
    )
    top_down_validation.add_argument("--data-root", type=Path, default=Path("data/ArknightsGameData"))
    top_down_validation.add_argument("--output-dir", type=Path, default=Path("output/top_down_validation"))
    top_down_validation.add_argument("--cross-stage-budget", type=int, default=60)
    top_down_validation.add_argument("--first-win-budget", type=int, default=300)
    args = parser.parse_args(argv)
    if args.command in {"human-timeline", "validate"}:
        timeline = FrameTimeline.from_dict(json.loads(args.timeline.read_text(encoding="utf-8")))
        repository = GameDataRepository(Path(args.data_root))
        if args.command == "human-timeline":
            print(render_human_timeline(timeline=timeline, repository=repository, simulator_result=args.simulator_result, approximation_warnings=("Frame clock is configured/approximate unless its status is KNOWN",)))
            return
        used = {action.operator_id for action in timeline.actions}
        rarities = {operator_id: repository.get_operator(operator_id).star_rarity.value for operator_id in used}
        if any(value is None for value in rarities.values()):
            raise ValueError("validation requires known GameData star rarity for every used operator")
        record = HumanValidationRecord(
            timeline.stage_id, args.timeline.stem, "UNKNOWN", len(used), sum(rarities.values()),
            HumanValidationStatus(args.validation_status), args.note, args.failure_frame,
            HumanFailureCategory(args.failure_category) if args.failure_category else None,
        )
        record.save(args.output)
        print(f"Stored {record.validation_status.value} validation evidence at {args.output}; no simulator parameter was changed.")
        return
    if args.command == "benchmark-search":
        record = next((item for item in stage_benchmark_census(GameDataRepository(Path(args.data_root))) if item.code == args.stage_id or item.stage_id == args.stage_id), None)
        if record is None:
            parser.error("stage is not in the bounded M10 benchmark suite")
        output = args.output_dir / record.stage_id / "compatibility.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(asdict(record), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Stage: {record.code}")
        print(f"Benchmark compatibility: {record.compatibility}")
        for blocker in record.blockers:
            print(f"  - {blocker}")
        print(f"Compatibility artifact: {output}")
        if record.compatibility == "BLOCKED":
            print("No simulator search was run; a winning result would be fabricated under current policies.")
        return
    if args.command == "m11-search":
        adapter = ApproximateRealSimulationAdapter(GameDataRepository(Path(args.data_root)))
        outcome = M11MinimumSquadSearch(
            adapter=adapter,
            stage_id_or_code=args.stage_id,
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
            operator_pool=M11MinimumSquadSearch.default_m11_pool(),
            config=M11SearchConfig(),
        ).search()
        output = args.output_dir / outcome.stage_id
        output.mkdir(parents=True, exist_ok=True)
        summary = {
            "stage_id": outcome.stage_id,
            "mode": "APPROXIMATE_REAL",
            "stop": outcome.stop.value,
            "lower_cardinalities_exhausted": outcome.lower_cardinalities_exhausted,
            "lower_rarities_exhausted": outcome.lower_rarities_exhausted,
            "approximations": outcome.fixture.approximations_used,
            "metrics": asdict(outcome.metrics),
            "objective": asdict(outcome.objective) if outcome.objective else None,
        }
        (output / "search_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"Stage: {args.stage_id}")
        print("Mode: APPROXIMATE_REAL (not an exact Arknights simulation)")
        print(f"Search termination: {outcome.stop.value}")
        print("Approximations:")
        for approximation in outcome.fixture.approximations_used:
            print(f"  - {approximation}")
        print(f"Metrics: teams={outcome.metrics.teams_generated} strategies={outcome.metrics.strategies_generated} unique_simulations={outcome.metrics.unique_simulations} cache_hits={outcome.metrics.cache_hits}")
        if outcome.timeline is None or outcome.best is None:
            print("Result: NO_WIN_FOUND")
            print("No human timeline was exported; the bounded low-rarity model did not produce a viable candidate.")
        else:
            timeline_path = output / "best_timeline.json"
            timeline_path.write_text(json.dumps(outcome.timeline.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            print(render_human_timeline(
                timeline=outcome.timeline, repository=adapter.repository,
                simulator_result="WIN", approximation_warnings=outcome.fixture.approximations_used,
            ))
            print(f"Timeline: {timeline_path}")
        print(f"Search summary: {output / 'search_summary.json'}")
        return
    if args.command == "m12-search":
        repository = GameDataRepository(Path(args.data_root))
        adapter = ApproximateRealSimulationAdapter(repository)
        census = low_rarity_census(repository)
        configs = adapter.m12_low_rarity_configurations()
        config = M11SearchConfig(max_squad_size=3, max_teams=80, beam_width=2, placement_options_per_operator=1)
        outcome = M11MinimumSquadSearch(
            adapter=adapter, stage_id_or_code=args.stage_id,
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
            operator_pool=configs, config=config,
        ).search()
        output = args.output_dir / "m12" / outcome.stage_id
        output.mkdir(parents=True, exist_ok=True)
        summary = {"stage_id": outcome.stage_id, "mode": "APPROXIMATE_REAL", "eligible_pool": len(census),
                   "executable_pool": len(configs), "blocked": [{"operator_id": r.operator_id, "reason": r.blockers} for r in census if r.operator_id not in {c.operator_id for c in configs}],
                   "stop": outcome.stop.value, "metrics": asdict(outcome.metrics), "objective": asdict(outcome.objective) if outcome.objective else None,
                   "approximations": outcome.fixture.approximations_used}
        (output / "search_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"Stage: {args.stage_id}\nMode: APPROXIMATE_REAL (M12 full eligible low-rarity pool)")
        print(f"Eligible 1-3★ operators: {len(census)}; executable pool: {len(configs)}")
        print(f"Search termination: {outcome.stop.value}; simulations: {outcome.metrics.unique_simulations}; cache hits: {outcome.metrics.cache_hits}")
        if outcome.best:
            print(f"Result: {'WIN' if outcome.best.result.win else 'LOSS'}; actions={len(outcome.best.strategy.actions)}; score={outcome.best.result.score:.2f}")
            if outcome.timeline:
                print(outcome.timeline.to_json())
        else:
            print("Result: NO_WIN_FOUND")
        print(f"Artifact: {output / 'search_summary.json'}")
        return
    if args.command == "m13-search":
        repository = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repository)
        outcome = M13LayeredSearch(adapter=adapter, stage_id_or_code=args.stage_id, policy=RealSimulationApproximationPolicy.m11_second_quantized()).search()
        m = outcome.metrics
        print(f"Stage: {args.stage_id}\nMode: APPROXIMATE_REAL (M13 layered search)")
        print(f"Eligible executable operators: {len(outcome.executable_pool)}; blocked: {len(outcome.blocked)}")
        print(f"K=1: possible={m.k1_possible} composition_coverage={m.k1_compositions_generated}/{m.k1_possible} tactical={m.k1_tactical_evaluated}")
        print(f"K=2: possible={m.k2_possible} composition_coverage={m.k2_compositions_generated}/{m.k2_possible} tactical={m.k2_tactical_evaluated}")
        print(f"Simulations: unique={m.unique_simulations} cache_hits={m.cache_hits}; termination={outcome.termination}")
        for result in (outcome.k1_result, outcome.k2_result):
            if result and result.best:
                print(f"Best: {'WIN' if result.best.result.win else 'LOSS'} team={result.best.strategy.team} actions={len(result.best.strategy.actions)}")
        return
    if args.command == "m14-llm-pilot":
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        fixture = adapter.build_pool_fixture(stage_id_or_code=args.stage_id, configurations=adapter.m12_low_rarity_configurations(), policy=RealSimulationApproximationPolicy.m11_second_quantized())
        analysis = stage_analysis(fixture); requirements = tactical_requirements(analysis); operators = operator_context(fixture.operators)
        configuration = provider_configuration_status()
        try:
            runtime = RealLLMRuntime(max_calls=args.max_llm_calls, timeout_seconds=args.llm_timeout_seconds) if args.llm_real else MockLLMRuntime()
        except RuntimeError as exc:
            out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
            status = {"status": "REAL_LLM_BLOCKED_BY_ENVIRONMENT", "configuration": configuration, "reason": str(exc), "real_calls": 0}
            (out / "real_llm_call_summary.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
            print("REAL_LLM_BLOCKED_BY_ENVIRONMENT")
            print("Configuration: " + ", ".join(f"{k}={v}" for k,v in configuration.items()))
            print("Reason: " + str(exc))
            print(f"Artifact: {out / 'real_llm_call_summary.json'}")
            return
        context = {"stage_analysis": asdict(analysis), "requirements": [asdict(x) for x in requirements], "operators": operators, "unavailable": "12 census operators blocked by mechanics"}
        error_text = None
        try: hypotheses = runtime.generate_hypotheses(context)
        except Exception as exc:
            hypotheses = []; error_text = str(exc); print(f"LLM unavailable: {error_text}")
            diagnostic = getattr(runtime, "last_response_diagnostic", None)
            if diagnostic:
                print("Sanitized response diagnostic:")
                print(json.dumps(diagnostic, indent=2, ensure_ascii=False))
        validations = [{"hypothesis_id": h.hypothesis_id, "status": validate_hypothesis(h, fixture.operators)[0], "reason": validate_hypothesis(h, fixture.operators)[1]} for h in hypotheses]
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        (out / "stage_analysis.json").write_text(json.dumps(asdict(analysis), indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "tactical_requirements.json").write_text(json.dumps([asdict(x) for x in requirements], indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "initial_hypotheses.json").write_text(json.dumps([asdict(x) for x in hypotheses], indent=2, ensure_ascii=False), encoding="utf-8")
        if hypotheses:
            teams, results, failures = run_grounded(hypotheses, adapter, RealSimulationApproximationPolicy.m11_second_quantized())
            (out / "grounded_teams.json").write_text(json.dumps([asdict(x) for x in teams], indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "initial_llm_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "initial_failure_summary.json").write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "llm_call_summary.json").write_text(json.dumps({"runtime": type(runtime).__name__, "real_calls": getattr(runtime,"calls",0), "max_calls": args.max_llm_calls, "timeout_seconds": getattr(runtime,"timeout_seconds", None), "elapsed_seconds": getattr(runtime,"last_elapsed_seconds", None), "timeout_phase": getattr(runtime,"last_timeout_phase", None), "configuration": configuration, "error": error_text, "response_diagnostic": getattr(runtime,"last_response_diagnostic", None), "schema_diagnostics": getattr(runtime,"last_schema_diagnostics", []), "reasoning_effort": "OMITTED", "validation": validations}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Stage: {args.stage_id}\nM14 runtime: {type(runtime).__name__}; real calls={getattr(runtime,'calls',0)}")
        print(f"Routes={len(analysis.routes)} spawns={analysis.spawn_count} requirements={len(requirements)} hypotheses={len(hypotheses)}")
        if hypotheses:
            print(f"Grounded teams={len(teams)} simulator runs={sum(x['simulations'] for x in results)}")
            best = sorted(results, key=lambda x:(not x['win'], x['leaks'] if x['leaks'] is not None else 999, -x['kills'], -x['survival']))[0]
            print(f"INITIAL_LLM_BEST: win={best['win']} kills={best['kills']} leaks={best['leaks']} life={best['life']}")
        for item in validations: print(f"  {item['hypothesis_id']}: {item['status']} ({item['reason']})")
        print(f"Artifacts: {out}")
        return
    if args.command == "m14-llm-revise":
        repo=GameDataRepository(Path(args.data_root)); adapter=ApproximateRealSimulationAdapter(repo)
        out=args.output_dir / "main_06-07"
        initial=load_hypotheses(out / "real_initial_hypotheses.json")
        initial_failures=json.loads((out / "initial_failure_summary.json").read_text(encoding="utf-8"))
        fixture=adapter.build_pool_fixture(stage_id_or_code=args.stage_id, configurations=adapter.m12_low_rarity_configurations(), policy=RealSimulationApproximationPolicy.m11_second_quantized())
        context={"stage_analysis":asdict(stage_analysis(fixture)),"requirements":[asdict(x) for x in tactical_requirements(stage_analysis(fixture))],"operators":operator_context(fixture.operators),"initial_hypotheses":[asdict(x) for x in initial],"failure_summary":initial_failures,"instruction":"Distinguish simulator evidence from tactical inference. Return 3-5 revised canonical hypotheses only."}
        runtime=RealLLMRuntime(max_calls=1, timeout_seconds=args.llm_timeout_seconds)
        try:
            revised=runtime.revise_hypotheses(context, initial_failures, max_hypotheses=5)
        except Exception as exc:
            (out / "real_llm_call_summary.json").write_text(json.dumps({"status":"REVISION_CALL_FAILED","real_calls":runtime.calls,"error":str(exc),"response_diagnostic":runtime.last_response_diagnostic,"timeout_seconds":runtime.timeout_seconds},indent=2,ensure_ascii=False),encoding="utf-8")
            print(f"REVISION_CALL_FAILED: {exc}"); return
        validations=[{"hypothesis_id":h.hypothesis_id,"status":validate_hypothesis(h,fixture.operators)[0],"reason":validate_hypothesis(h,fixture.operators)[1]} for h in revised]
        scope_rejections=grounding_rejections(revised)
        accepted=tuple(h for h in revised if validate_hypothesis(h,fixture.operators)[0] == "ACCEPTED" and 1 <= h.target_cardinality <= 3)
        teams,results,revised_failures=run_grounded(accepted,adapter,RealSimulationApproximationPolicy.m11_second_quantized(),per_hypothesis=2)
        (out / "revision_prompt_summary.json").write_text(json.dumps({"initial_ids":[h.hypothesis_id for h in initial],"failure_summary":initial_failures},indent=2,ensure_ascii=False),encoding="utf-8")
        (out / "real_revised_hypotheses.json").write_text(json.dumps([asdict(x) for x in revised],indent=2,ensure_ascii=False),encoding="utf-8")
        (out / "revised_grounding_validation.json").write_text(json.dumps({"schema_validation":validations,"scope_validation":scope_rejections},indent=2,ensure_ascii=False),encoding="utf-8")
        (out / "revised_grounded_teams.json").write_text(json.dumps([asdict(x) for x in teams],indent=2,ensure_ascii=False),encoding="utf-8")
        (out / "revised_llm_results.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
        (out / "revised_failure_summary.json").write_text(json.dumps(revised_failures,indent=2,ensure_ascii=False),encoding="utf-8")
        (out / "real_llm_call_summary.json").write_text(json.dumps({"status":"REVISION_CALL_SUCCEEDED","real_calls":runtime.calls,"timeout_seconds":runtime.timeout_seconds,"elapsed_seconds":runtime.last_elapsed_seconds,"validation":validations},indent=2,ensure_ascii=False),encoding="utf-8")
        print(f"Revised hypotheses={len(revised)} accepted={len(accepted)} grounded_teams={len(teams)} simulator_runs={sum(x['simulations'] for x in results)}")
        return
    if args.command == "m14-cardinality-audit":
        if args.simulation_budget < 1 or args.simulation_budget > 500:
            parser.error("--simulation-budget must be between 1 and 500 for the bounded cardinality audit")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        revised = load_hypotheses(out / "real_revised_hypotheses.json")
        policy = RealSimulationApproximationPolicy.m11_second_quantized()
        teams, results, rejections, metrics = run_cardinality_audit(revised, adapter, policy, simulation_budget=args.simulation_budget)
        ablations = [{"hypothesis_id": item.hypothesis_id, "variant": item.variant, "requested_cardinality": item.requested_cardinality,
                      "operators": item.operators, "removed_operator_id": item.removed_operator_id,
                      "removed_capabilities": item.removed_capabilities} for item in teams]
        initial_rows = json.loads((out / "initial_llm_results.json").read_text(encoding="utf-8"))
        initial_best = min(initial_rows, key=lambda item: (not item["win"], item["leaks"], -item["kills"], -item["survival"]))
        full = [item for item in results if item["variant"] == "FULL"]
        better_full = [item for item in full if item["kills"] > initial_best["kills"] and item["leaks"] < initial_best["leaks"]]
        if len({item["hypothesis_id"] for item in better_full}) >= 2:
            classification = "SUPPORTED"
            reason = "Two independent exact-cardinality full hypotheses improved both kills and leaks over INITIAL_K<=3_BEST; this supports a current-planner K<=3 limitation, not a stage minimum-cardinality claim."
        elif results:
            classification = "NOT_SUPPORTED"
            reason = "No exact-cardinality full hypothesis improved both kills and leaks over INITIAL_K<=3_BEST within the bounded audit."
        else:
            classification = "INCONCLUSIVE"
            reason = "No complete exact-cardinality hypothesis was grounded within the bounded canonical geometry."
        comparison = {"experiment": "M14.4 bounded cardinality-pressure validation", "llm_calls": 0,
                      "initial_k_le_3_best": {"result": "WIN" if initial_best["win"] else "LOSS", "kills": initial_best["kills"],
                                                "leaks": initial_best["leaks"], "remaining_life": initial_best["life"],
                                                "attacks": initial_best["attacks"], "damage_events": initial_best["damage_events"],
                                                "survival": initial_best["survival"], "operators": initial_best["operators"]},
                      "results": results, "classification": classification, "classification_reason": reason,
                      "not_a_stage_minimum_cardinality_claim": True}
        (out / "cardinality_audit_input.json").write_text(json.dumps({"source_artifact": "real_revised_hypotheses.json", "hypotheses": [asdict(item) for item in revised], "llm_calls": 0}, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "cardinality_grounded_teams.json").write_text(json.dumps([asdict(item) for item in teams], indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "cardinality_ablation.json").write_text(json.dumps(ablations, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "cardinality_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "cardinality_comparison.json").write_text(json.dumps({**comparison, "metrics": metrics, "structural_rejections": rejections}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"LLM calls=0; grounded full/reduced teams={len(teams)}; structural rejections={len(rejections)}")
        print(f"Unique simulations={metrics['unique_simulations']} cache_hits={metrics['cache_hits']} budget={metrics['simulation_budget']}")
        for item in results:
            print(f"{item['hypothesis_id']} {item['variant']}: K={len(item['operators'])} rarity={item['rarity']} {item['result']} kills={item['kills']} leaks={item['leaks']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m14-local-repair":
        if args.simulation_budget < 1 or args.simulation_budget > 1500:
            parser.error("--simulation-budget must be between 1 and 1500 for M14.5")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        revised = tuple(item for item in load_hypotheses(out / "real_revised_hypotheses.json") if item.hypothesis_id in {"R1", "R4"})
        report = M14LocalRepairSearch(adapter=adapter, hypotheses=revised, policy=RealSimulationApproximationPolicy.m11_second_quantized(), budget=args.simulation_budget, beam_width=args.beam_width).run()
        (out / "local_repair_input.json").write_text(json.dumps({"source": "real_revised_hypotheses.json", "hypothesis_ids": [item.hypothesis_id for item in revised], "llm_calls": 0, "budget": args.simulation_budget}, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "leak_analysis.json").write_text(json.dumps(report["leak_analysis"], indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "local_repair_progress.json").write_text(json.dumps(report["progress"], indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "local_repair_results.json").write_text(json.dumps({"parents": report["parents"], "frontier": report["frontier"], "final_best": report["final_best"], "metrics": report["metrics"]}, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "local_repair_plateau.json").write_text(json.dumps(report["plateau"], indent=2, ensure_ascii=False), encoding="utf-8")
        final = report["final_best"]
        print(f"LLM calls=0; unique simulations={report['metrics']['unique_simulations']} cache_hits={report['metrics']['cache_hits']} generated={report['metrics']['candidates_generated']} structural_rejections={report['metrics']['structural_rejections']}")
        if final:
            print(f"FINAL: {final['result']} source={final['source_hypothesis']} K={final['operator_count']} stars={final['rarity']} kills={final['kills']} leaks={final['leaks']} first_leak={final['first_leak_frame']}")
        print(f"Plateau: {report['plateau']['status']} ({report['plateau']['dominant_failure']})")
        if report["winner_timeline"] is not None:
            timeline = FrameTimeline.from_dict(report["winner_timeline"])
            (out / "feasible_strategy.json").write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "human_timeline.json").write_text(json.dumps(report["winner_timeline"], indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "human_timeline.txt").write_text(render_human_timeline(timeline=timeline, repository=repo, simulator_result="WIN", robustness=str(report["winner_robustness"]), approximation_warnings=tuple(RealSimulationApproximationPolicy.m11_second_quantized().names)), encoding="utf-8")
            print("WIN preserved as FEASIBLE_NOT_MINIMAL; human validation remains UNTESTED.")
        print(f"Artifacts: {out}")
        return
    if args.command == "m14-opening-repair":
        if args.simulation_budget < 1 or args.simulation_budget > 500:
            parser.error("--simulation-budget must be between 1 and 500 for M14.6")
        if args.opening_horizon_frame < 516:
            parser.error("--opening-horizon-frame must cover the observed 10-19 second early-leak window (>=516)")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = M14OpeningRepairSearch(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), budget=args.simulation_budget, horizon_frame=args.opening_horizon_frame).run()
        for name in ("opening_failure_analysis", "opening_dp_timeline", "opening_search_results", "opening_progress", "promoted_full_battle_results"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        if report["opening_substitution_results"] is not None:
            (out / "opening_substitution_results.json").write_text(json.dumps(report["opening_substitution_results"], indent=2, ensure_ascii=False), encoding="utf-8")
        opening = report["opening_search_results"]
        best = opening["results"][0] if opening["results"] else None
        promoted = report["promoted_full_battle_results"]["promoted"]
        best_full = min(promoted, key=lambda item: (item["leaks"], -item["kills"], -(item["first_leak_frame"] or 10**9))) if promoted else None
        print(f"LLM calls=0; K=7 unchanged; opening horizon=0..{args.opening_horizon_frame}")
        print(f"Opening: generated={opening['candidates_generated']} unique_simulations={opening['unique_simulations']} structural_rejections={opening['structural_rejections']}")
        if best:
            print(f"BEST_OPENING: leaks={best['opening_leaks']} kills={best['opening_kills']} first_leak={best['first_leak_frame']} damage={best['opening_damage']:.1f}")
        if best_full:
            print(f"BEST_PROMOTED_FULL: {best_full['result']} kills={best_full['kills']} leaks={best_full['leaks']} first_leak={best_full['first_leak_frame']}")
        print(f"Opening capability pressure: {report['opening_capability_pressure']['classification']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m14-opening-economy-repair":
        if args.simulation_budget < 1 or args.simulation_budget > 1000:
            parser.error("--simulation-budget must be between 1 and 1000 for M14.7")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = M14OpeningEconomyRepair(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), budget=args.simulation_budget, horizon_frame=args.opening_horizon_frame).run()
        for name in ("opening_requirements", "operator_opening_signatures", "r4_operator_contributions", "one_slot_repair_results", "two_slot_repair_results", "opening_economy_progress", "opening_economy_full_battle_results", "dp_acceleration"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        progress = report["opening_economy_progress"]; best = report["opening_economy_full_battle_results"]["best"]
        print("LLM calls=0; K=7 unchanged; no minimization or K=8 expansion.")
        print(f"Opening: simulations={progress['opening_simulations']} full_battle={progress['full_battle_simulations']} total={progress['total_unique_simulations']} budget={args.simulation_budget}")
        print(f"BEST: {best['result']} kills={best['kills']} leaks={best['leaks']} first_leak={best['first_leak_frame']} life={best['remaining_life']}")
        print(f"Opening-economy repair: {report['opening_economy_repair']['classification']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m14-opening-geometry":
        if args.simulation_budget < 1 or args.simulation_budget > 800:
            parser.error("--simulation-budget must be between 1 and 800 for M14.8")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = M14OpeningGeometrySearch(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), budget=args.simulation_budget, horizon_frame=args.opening_horizon_frame).run()
        for name in ("opening_route_geometry", "opening_interaction_graph", "single_deployment_openings", "ranged_opening_results", "delayed_interception_results", "shared_opening_results", "promoted_geometry_full_battle_results"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "opening_geometry_metrics.json").write_text(json.dumps(report["metrics"], indent=2, ensure_ascii=False), encoding="utf-8")
        if report["opening_prefix_verified"]:
            (out / "verified_opening_prefix.json").write_text(json.dumps(report["best_opening"], indent=2, ensure_ascii=False), encoding="utf-8")
        metrics, best, full = report["metrics"], report["best_opening"], report["promoted_geometry_full_battle_results"]["best"]
        print("LLM calls=0; roster unchanged; K=7; stars=20.")
        print(f"Opening: single={report['single_deployment_openings']['candidates']} shared={report['shared_opening_results']['candidates']} unique={metrics['unique_opening_simulations']} full_battle={metrics['full_battle_simulations']} total={metrics['total_unique_simulations']} budget={metrics['budget']}")
        if best:
            print(f"BEST_OPENING: leaks={best['opening_leaks']} kills={best['opening_kills']} first_leak={best['first_leak_frame']} damage={best['opening_damage']:.1f}")
        if full:
            print(f"BEST_FULL: {full['result']} kills={full['kills']} leaks={full['leaks']} first_leak={full['first_leak_frame']} life={full['remaining_life']}")
        print(f"Shared={report['shared_opening_results']['classification']} ranged={report['ranged_opening_results']['classification']} delayed={report['delayed_interception_results']['classification']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m14-opening-economy-audit":
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = M14OpeningEconomyFidelityAudit(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized()).run()
        for name in ("low_rarity_economy_audit", "opening_economy_relevant_operators", "dp_skill_interpreter_audit", "economy_mechanics_provenance", "opening_dp_feasibility_after_audit", "economy_mechanics_validation"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        audit = report["low_rarity_economy_audit"]
        print("LLM calls=0; no broad strategy search, K=8, or minimization.")
        print(f"Low-rarity pool: eligible={audit['eligible']} executable={audit['executable']} blocked={audit['blocked']}")
        print(f"Opening-economy fidelity gap: {report['classification']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m15-feasibility":
        if args.simulation_budget < 1 or args.simulation_budget > 2000:
            parser.error("--simulation-budget must be between 1 and 2000 for M15")
        if args.beam_width < 1 or args.beam_width > 16:
            parser.error("--beam-width must be between 1 and 16 for M15")
        if args.max_cardinality < 1 or args.max_cardinality > 7:
            parser.error("--max-cardinality must be between 1 and 7 for M15")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = ConstraintGuidedFeasibilityPlanner(
            adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), beam_width=args.beam_width,
            simulation_budget=args.simulation_budget, max_cardinality=args.max_cardinality,
        ).run()
        for name in ("m15_stage_constraints", "m15_search_progress", "m15_failure_frontiers", "m15_assignment_stats", "m15_prefix_history", "m15_results", "m15_baseline_comparison"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        result, comparison = report["m15_results"], report["m15_baseline_comparison"]
        best = result["best"]
        print("LLM calls=0; constraint-guided feasibility only; no minimization.")
        print(f"Pool={len(report['m15_stage_constraints']['operator_pool'])} max_K={args.max_cardinality} beam={args.beam_width} budget={args.simulation_budget}")
        if best:
            print(f"BEST: {best['result']} K={best['operator_count']} stars={best['rarity']} kills={best['kills']} leaks={best['leaks']} first_failure={best['first_failure_frame']} life={best['remaining_life']}")
        print(f"Constraint-guided search: {comparison['classification']}; termination={result['termination']}")
        if result["timeline"]:
            (out / "feasible_strategy.json").write_text(json.dumps(result["best"], indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "human_timeline.json").write_text(json.dumps(result["timeline"], indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "human_timeline.txt").write_text(result["human_timeline"], encoding="utf-8")
            print("WIN: FEASIBLE_NOT_MINIMAL timeline exported; validation=UNTESTED")
        print(f"Artifacts: {out}")
        return
    if args.command == "mechanics-rebaseline":
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = MechanicsRebaseline(
            adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(),
            artifact_root=args.artifact_root,
        ).run()
        for name in ("mechanics_rebaseline", "mechanics_rebaseline_frontiers", "mechanics_rebaseline_comparison"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        comparison = report["mechanics_rebaseline_comparison"]
        print("Replay only: no search, LLM calls, mechanics expansion, cardinality change, or minimization.")
        print(f"Replayed={comparison['replayed_strategy_count']} unavailable={comparison['unreplayable_strategy_count']}")
        print(f"HISTORICAL_BASELINE_COMPATIBILITY={comparison['HISTORICAL_BASELINE_COMPATIBILITY']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m15-requirement-repair":
        if args.simulation_budget < 1 or args.simulation_budget > 400:
            parser.error("--simulation-budget must be between 1 and 400 for M15.2")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        parent_path = out / "m15_1_results.json"
        if not parent_path.exists():
            parser.error("M15.2 requires the preserved m15_1_results.json guided-parent artifact")
        report = FrontierRequirementSolver(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), parent_path=parent_path,
                                           simulation_budget=args.simulation_budget).run()
        for name in ("m15_2_frontier_enemy_trace", "m15_2_frontier_requirements", "m15_2_counterfactual_damage", "m15_2_contribution_opportunities", "m15_2_candidate_prechecks", "m15_2_constraint_history", "m15_2_requirement_progress", "m15_2_results", "m15_2_baseline_comparison"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        result = report["m15_2_results"]["best"]
        print("LLM calls=0; current PRTS-backed mechanics; K<=7; no minimization.")
        print(f"BEST: {result['result']} K={result['operator_count']} stars={result['rarity']} kills={result['kills']} leaks={result['leaks']} frontier={result['earliest_failure_frontier']['frame']}")
        print(f"Requirement solving: {report['m15_2_baseline_comparison']['classification']}; termination={report['m15_2_results']['termination']}")
        if report["m15_2_results"]["timeline"]:
            (out / "feasible_strategy.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "human_timeline.json").write_text(json.dumps(report["m15_2_results"]["timeline"], indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "human_timeline.txt").write_text(report["m15_2_results"]["human_timeline"], encoding="utf-8")
        print(f"Artifacts: {out}")
        return
    if args.command == "m15-multifrontier":
        if args.simulation_budget < 1 or args.simulation_budget > 600:
            parser.error("--simulation-budget must be between 1 and 600 for M15.3")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = MultiFrontierSolver(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), root=out,
                                     budget=args.simulation_budget).run()
        for name in ("m15_3_multifrontier_constraints", "m15_3_route_requirements", "m15_3_counterexample_differentials", "m15_3_resource_assignments", "m15_3_conflict_graph", "m15_3_slack_analysis", "m15_3_candidate_prechecks", "m15_3_search_progress", "m15_3_results", "m15_3_baseline_comparison"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        best = report["m15_3_results"]["best"]
        print("LLM calls=0; mechanics expansion=no; K<=7; minimization=no.")
        print(f"BEST: {best['result']} K={best['operator_count']} stars={best['rarity']} kills={best['kills']} leaks={best['leaks']} frontier_count={len(best['frontiers'])}")
        print(f"Multi-frontier solving: {report['m15_3_baseline_comparison']['classification']}; termination={report['m15_3_results']['termination']}; simulations={report['m15_3_results']['unique_simulations']} cache_hits={report['m15_3_results']['cache_hits']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m15-falco-decoupling":
        if args.simulation_budget < 1 or args.simulation_budget > 150:
            parser.error("--simulation-budget must be between 1 and 150 for M15.4")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = FalcoResourceAudit(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), root=out, budget=args.simulation_budget).run()
        for name in ("m15_4_falco_responsibility_audit", "m15_4_remove_falco_counterfactual", "m15_4_critical_resource_profile", "m15_4_responsibility_partition", "m15_4_existing_roster_reassignment", "m15_4_pool_capability_matches", "m15_4_substitution_candidates", "m15_4_candidate_prechecks", "m15_4_abc_comparison", "m15_4_results"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        best = report["m15_4_results"]["best"]
        print("LLM calls=0; mechanics expansion=no; K<=7; minimization=no.")
        print(f"A/B/C: best={best['label']} {best['result']} K={best['operator_count']} stars={best['rarity']} kills={best['kills']} leaks={best['leaks']}")
        print(f"Simulations={report['m15_4_results']['unique_full_simulations']} cache_hits={report['m15_4_results']['cache_hits']}; decoupling={report['m15_4_results']['CRITICAL_RESOURCE_DECOUPLING']}; overload={report['m15_4_results']['CRITICAL_RESOURCE_OVERLOAD']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m16-causal-audit":
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = CausalCombatAudit(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), root=Path("output/m15/main_06-07")).run()
        for name, value in report.items():
            (out / f"{name}.json").write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        r = report["m16_results"]
        print("LLM calls=0; no search, mechanics expansion, cardinality change, or minimization.")
        print(f"A: kills={r['A']['kills']} leaks={r['A']['leaks']} life={r['A']['life']}; B: kills={r['B']['kills']} leaks={r['B']['leaks']} life={r['B']['life']}")
        print(f"Isolation={report['m16_intervention_isolation']['status']}; cause={','.join(r['NON_MONOTONICITY_CAUSE'])}; local_damage_monotonicity={r['LOCAL_DAMAGE_MONOTONICITY_ASSUMPTION']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m17-causal-temporal":
        root = Path("output/m16/main_06-07")
        if not (root / "m16_enemy_outcome_comparison.json").is_file(): parser.error("M17 requires preserved M16 artifacts")
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        report = CausalTemporalAudit(root).run()
        for name, value in report.items(): (out / f"{name}.json").write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        r=report["m17_results"]
        print("LLM calls=0; strategy search=no; mechanics expansion=no; K unchanged; minimization=no.")
        print(f"Converted constraints={report['m17_m16_conversion']['converted_constraints']} interference_relations={len(report['m17_constraint_interference']['relations'])}")
        print(f"Representation={r['CAUSAL_TEMPORAL_REPRESENTATION']}; safe_intervention_checker={r['SAFE_LOCAL_INTERVENTION_CHECKER']}; local_damage_monotonicity={r['local_damage_monotonicity']}")
        print(f"Artifacts: {out}")
        return
    if args.command == "m18-targeting-audit":
        repo=GameDataRepository(Path(args.data_root)); adapter=ApproximateRealSimulationAdapter(repo); out=args.output_dir/"main_06-07"; out.mkdir(parents=True,exist_ok=True)
        report=TargetingFidelityAudit(adapter=adapter,policy=RealSimulationApproximationPolicy.m11_second_quantized(),root=Path("output/m15/main_06-07")).run()
        for name,value in report.items(): (out/f"{name}.json").write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
        r=report["m18_results"]; print("LLM calls=0; strategy search=no; no unrelated mechanics expansion."); print(f"TARGETING_FIDELITY={r['TARGETING_FIDELITY']}; M16={r['M16_CAUSAL_RESULT']}; M17={r['M17_CAUSAL_REPRESENTATION']}"); print(f"Artifacts: {out}"); return
    if args.command == "m15-frontier-repair":
        if args.guided_budget < 1 or args.guided_budget > 600:
            parser.error("--guided-budget must be between 1 and 600 for M15.1")
        if args.control_budget < 1 or args.control_budget > 200:
            parser.error("--control-budget must be between 1 and 200 for M15.1")
        repo = GameDataRepository(Path(args.data_root)); adapter = ApproximateRealSimulationAdapter(repo)
        out = args.output_dir / "main_06-07"; out.mkdir(parents=True, exist_ok=True)
        parent_path = out / "m15_results.json"
        if not parent_path.is_file():
            parser.error("M15.1 requires the preserved m15_results.json parent artifact")
        report = FailureFrontierRepair(
            adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized(), parent_path=parent_path,
            guided_budget=args.guided_budget, control_budget=args.control_budget,
        ).run()
        for name in ("m15_1_initial_parent", "m15_1_frontier_causal_trace", "m15_1_generated_constraints", "m15_1_repair_progress", "m15_1_prefix_dependencies", "m15_1_repair_level_stats", "m15_1_unguided_control", "m15_1_results", "m15_1_comparison"):
            (out / f"{name}.json").write_text(json.dumps(report[name], indent=2, ensure_ascii=False), encoding="utf-8")
        guided = report["m15_1_results"]["guided"]; control = report["m15_1_unguided_control"]["result"]
        print("LLM calls=0; mechanics expansion=no; K<=7; no minimization.")
        print(f"GUIDED: {guided['result']} K={guided['operator_count']} stars={guided['rarity']} kills={guided['kills']} leaks={guided['leaks']} frontier={guided['earliest_failure_frontier']['frame']}")
        print(f"CONTROL: {control['result']} K={control['operator_count']} stars={control['rarity']} kills={control['kills']} leaks={control['leaks']} frontier={control['earliest_failure_frontier']['frame']}")
        print(f"Failure-frontier repair: {report['m15_1_comparison']['classification']}; termination={report['m15_1_results']['termination']}")
        if report["m15_1_results"]["timeline"]:
            (out / "feasible_strategy.json").write_text(json.dumps(guided, indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "human_timeline.json").write_text(json.dumps(report["m15_1_results"]["timeline"], indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "human_timeline.txt").write_text(report["m15_1_results"]["human_timeline"], encoding="utf-8")
            print("WIN: FEASIBLE_NOT_MINIMAL timeline exported; validation=UNTESTED")
        print(f"Artifacts: {out}")
        return
    if args.command == "m18-1-readiness":
        out=args.output_dir/"main_06-07"; out.mkdir(parents=True,exist_ok=True); report=TargetingReadinessAudit(out).run()
        for name,value in report.items(): (out/f"{name}.json").write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
        print("LLM calls=0; strategy search=no; mechanics expansion=no; no K/minimization changes.")
        print(f"Causally relevant decisions={report['m18_1_targeting_decisions']['causally_relevant'].__len__()} sensitive={report['m18_1_targeting_decisions']['unresolved_sensitive_count']}; readiness={report['m18_1_search_readiness']['CAUSAL_SEARCH_READINESS']}")
        print(f"Artifacts: {out}"); return
    if args.command == "m19-causal-repair":
        if not 1 <= args.simulation_budget <= 300: parser.error("--simulation-budget must be 1..300 for M19")
        repo=GameDataRepository(Path(args.data_root)); adapter=ApproximateRealSimulationAdapter(repo); root=Path("output/m15/main_06-07"); out=args.output_dir/"main_06-07"; out.mkdir(parents=True,exist_ok=True)
        report=UncertaintyGuardedRepair(adapter=adapter,policy=RealSimulationApproximationPolicy.m11_second_quantized(),root=root,budget=args.simulation_budget,beam_width=args.beam_width).run()
        for name,value in report.items(): (out/f"{name}.json").write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
        b=report['m19_results']['best']; print("LLM calls=0; mechanics expansion=no; K<=7; minimization=no."); print(f"BEST: {b['result']} K={b['operator_count']} kills={b['kills']} leaks={b['leaks']} frontier={b['frontier']}"); print(f"interventions={len(report['m19_causal_interventions']['interventions'])} simulations={report['m19_search_progress']['simulations']} readiness-guarded={report['m19_results']['UNCERTAINTY_GUARDED_CAUSAL_SEARCH']}"); print(f"Artifacts: {out}"); return
    if args.command == "m20-capability-synthesis":
        out=args.output_dir/"main_06-07"; out.mkdir(parents=True,exist_ok=True); report=CapabilityInterventionSynthesis(Path("output/m15/main_06-07")).run()
        for name,value in report.items(): (out/f"{name}.json").write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
        r=report['m20_results']; print("LLM calls=0; mechanics expansion=no; broad strategy search=no; K<=7; minimization=no."); print(f"requirements={len(report['m20_capability_requirements']['requirements'])} providers={len(report['m20_pool_matches']['matches'])} interventions={len(report['m20_generated_interventions']['interventions'])} diversity={r['INTERVENTION_DIVERSITY']}"); print(f"Artifacts: {out}"); return
    if args.command == "m21-causal-search":
        repo=GameDataRepository(Path(args.data_root)); adapter=ApproximateRealSimulationAdapter(repo); out=args.output_dir/"main_06-07"; out.mkdir(parents=True,exist_ok=True)
        report=InformationEfficientCausalSearch(adapter=adapter,policy=RealSimulationApproximationPolicy.m11_second_quantized(),root=Path("output/m15/main_06-07"),budget=args.simulation_budget).run()
        for name,value in report.items(): (out/f"{name}.json").write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
        b=report['m21_results']['best']; print("LLM calls=0; mechanics expansion=no; K<=7; minimization=no."); print(f"BEST: {b['result']} kills={b['kills']} leaks={b['leaks']} frontier={b['frontier']}; simulations={report['m21_results']['unique_simulations']}; status={report['m21_results']['INFORMATION_EFFICIENT_CAUSAL_SEARCH']}"); print(f"Artifacts: {out}"); return
    if args.command == "m22-frontier-audit":
        out=args.output_dir/"main_06-07"; out.mkdir(parents=True,exist_ok=True); report=FrontierFeasibilityAudit(Path("output/m21/main_06-07")).run()
        for name,value in report.items(): (out/f"{name}.json").write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
        print("LLM calls=0; strategy search=no; mechanics expansion=no; K unchanged; minimization=no."); print(f"Frontier={report['m22_frontier_profile']['frontier_id']} factors={report['m22_results']['FRONTIER_FEASIBILITY']} calibration={report['m22_calibration_trigger']['REAL_GAME_CALIBRATION_RECOMMENDED']}"); print(f"Artifacts: {out}"); return
    if args.command == "m23-calibration-plan":
        out=args.output_dir/"main_06-07"; out.mkdir(parents=True,exist_ok=True); p=M23CalibrationPacket(Path(".")); report=p.run(); MechanicsEvidenceRegistry(Path(".")).save(out/'mechanics_evidence_registry.json')
        for name,value in report.items(): (out/f"{name}.json").write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
        (out/'m23_human_instructions.md').write_text(p.instructions(),encoding='utf-8')
        print("LLM calls=0; strategy search=no; mechanics changes=no; NO_HUMAN_CALIBRATION_REQUIRED"); print(f"Selected calibration questions={len(report['m23_calibration_questions']['questions'])}"); print(f"Artifacts: {out}"); return
    if args.command == "m18-targeting-rebaseline":
        out=args.output_dir/"main_06-07"; out.mkdir(parents=True,exist_ok=True); report=TargetingRebaseline(out).run()
        for name,value in report.items(): (out/f"{name}.json").write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
        print("LLM calls=0; strategy search=no; no unrelated mechanics expansion."); print(f"TARGETING_FIDELITY={report['targeting_fidelity_results']['TARGETING_FIDELITY']}; M16={report['targeting_m16_reassessment']['M16_CAUSAL_RESULT']}"); print(f"Artifacts: {out}"); return
    if args.command == "architecture-audit":
        smoke = None
        if args.run_smoke:
            repository = GameDataRepository(Path(args.data_root))
            adapter = ApproximateRealSimulationAdapter(repository)
            policy = RealSimulationApproximationPolicy.main_00_01() if args.smoke_stage == "0-1" else RealSimulationApproximationPolicy.m11_second_quantized()
            scope = ExperimentScope.main_0_1_smoke(
                operator_pool=("char_122_beagle", "char_124_kroos"),
                max_cardinality=2,
                simulation_budget=24,
            )
            smoke = TopDownPlanner(adapter=adapter, policy=policy, scope=scope).run()
            if not smoke["search"]["budget_respected"]:
                parser.error("top-down smoke exceeded its explicit simulation budget")
        validation_results = None
        if args.validation_json:
            validation_results = json.loads(args.validation_json.read_text(encoding="utf-8"))
        artifacts = ArchitectureAudit(Path(".")).run(
            output_dir=args.output_dir,
            smoke=smoke,
            validation_results=validation_results,
        )
        print("LLM calls=0; broad strategy search=no; M23 Phase B=no; human calibration=no.")
        print(f"Artifacts={len(artifacts)}; smoke={'RUN' if smoke else 'NOT_RUN'}; output={args.output_dir}")
        if smoke:
            search = smoke["search"]
            print(f"SMOKE stage={args.smoke_stage} win={search['win']} simulations={search['unique_simulations']}/{search['simulation_budget']} repair={smoke['repair_layer']}")
        return
    if args.command == "top-down-validation":
        repository = GameDataRepository(Path(args.data_root))
        adapter = ApproximateRealSimulationAdapter(repository)
        report = TopDownValidation(
            repository=repository,
            adapter=adapter,
            root=Path("."),
            cross_stage_budget=args.cross_stage_budget,
            first_win_budget=args.first_win_budget,
        ).run(args.output_dir)
        print("LLM calls=0; broad search=no; M23 Phase B=no; human calibration=no; minimization=no.")
        print(
            f"SUITE={report['CROSS_STAGE_TOP_DOWN']}; "
            f"FIRST_WIN={report['FIRST_MEANINGFUL_REAL_STAGE_WIN']}; "
            f"failure_layer={report['FIRST_WIN_FAILURE_LAYER']}; "
            f"PYTEST={report['PYTEST']}"
        )
        print(f"Artifacts={args.output_dir}")
        return
    if args.command == "demo":
        result = BeamSearch(stage=synthetic_stage(), operators=synthetic_operators(), enemies=synthetic_enemies()).search()
        best = result.best
        print("Stage: synthetic-1")
        print("Discovered strategy:")
        for action in best.strategy.actions:
            print(f"  {action.time:04.1f}  DEPLOY {action.operator_id} at {action.tile} facing {action.direction}")
        print(f"Result: {'WIN' if best.result.win else 'LOSE'}")
        print(f"Synthetic score: {best.score:.1f}")
        print(
            "Metrics: "
            f"generated={result.metrics.candidates_generated}, "
            f"simulations={result.metrics.simulations_evaluated}, "
            f"first_win={result.metrics.simulations_to_first_win}, "
            f"depth={result.metrics.search_depth}, "
            f"seconds={result.metrics.wall_clock_seconds:.3f}"
        )
        return
    if args.stage_id != "0-1":
        parser.error(f"{args.command} currently supports only 0-1")
    adapter = ApproximateRealSimulationAdapter(GameDataRepository(Path(args.data_root)))
    policy = RealSimulationApproximationPolicy.main_00_01()
    if args.command == "real-demo":
        run = adapter.run_main_00_01(mode=RealExecutionMode.APPROXIMATE_REAL, policy=policy)
        result = run.result
        print("Stage: 0-1")
        print("Mode: APPROXIMATE_REAL (not an exact Arknights simulation)")
        print("Operators:")
        for action in run.strategy.actions:
            print(f"  {action.operator_id}  {action.time:04.1f} DEPLOY at {action.tile} facing {action.direction}")
        print("Approximations:")
        for approximation in run.fixture.approximations_used:
            print(f"  - {approximation}")
        print(f"Result: {'WIN' if result.win else 'LOSS'}")
        print(f"life={result.remaining_life} kills={result.enemies_killed} leaks={result.enemies_leaked} duration={result.time_survived:.1f}s")
        return
    search = ApproximateRealBeamSearch(adapter=adapter, policy=policy, config=RealSearchConfig())
    outcome = search.search()
    best = outcome.best
    print("Stage: 0-1")
    print("Mode: APPROXIMATE_REAL (not an exact Arknights simulation)")
    print("Operator pool:")
    for operator_id, operator in sorted(outcome.fixture.operators.items()):
        stats = operator.phases[0].stats_max
        print(f"  {operator_id}  position={operator.position.value} cost={stats.cost.value} atk={stats.atk.value}")
    print("Approximations:")
    for approximation in outcome.fixture.approximations_used:
        print(f"  - {approximation}")
    print("Search:")
    if args.timing == "frames":
        clock = search.config.frame_clock
        print(f"  frame_clock kind={clock.kind.value} fps={clock.frames_per_second} status={clock.status.value} (configured/approximated)")
        print(f"  coarse_frames={search.timing_frame_candidates()}")
    else:
        print(f"  coarse_times={search.config.coarse_times}")
    print(f"  beam_width={search.config.beam_width} max_depth={search.config.max_depth}")
    print("Best strategy:")
    for action in best.strategy.actions:
        print(f"  {action.time:04.1f} DEPLOY {action.operator_id} at {action.tile} facing {action.direction}")
    if args.timing == "frames" and outcome.timeline is not None:
        print("Best action timeline:")
        for action in outcome.timeline.actions:
            print(f"  frame {action.frame:04d} {action.action_type.value} {action.operator_id} at {action.tile} facing {action.direction}" if action.tile is not None else f"  frame {action.frame:04d} {action.action_type.value} {action.operator_id}")
        print(f"  derived_seconds={float(outcome.timeline.frame_clock.seconds_for_frame(outcome.timeline.actions[0].frame)):.3f}")
        print(f"  approximate_robust_frames={outcome.robustness_frames}")
    result = best.result
    print(f"Result: {'WIN' if result.win else 'LOSS'}")
    print(f"life={result.remaining_life} kills={result.enemies_killed} leaks={result.enemies_leaked} duration={result.time_survived:.1f}s")
    metrics = outcome.metrics
    print(
        "Metrics: "
        f"generated={metrics.candidates_generated} evaluated={metrics.simulations_evaluated} "
        f"unique={metrics.unique_simulations} cache_hits={metrics.cache_hits} "
        f"first_win={metrics.simulations_to_first_win} depth={metrics.search_depth} "
        f"refinements={metrics.local_refinements}"
    )


if __name__ == "__main__":
    main()
