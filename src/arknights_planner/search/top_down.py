"""Top-down, hypothesis-first planner orchestration.

The planner starts from GameData-derived stage understanding and tactical
requirements.  Historical failure/frontier tools remain downstream repair
tools and are not imported by this module.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    M13LoadoutPolicy,
    RealOperatorConfiguration,
    RealSimulationApproximationPolicy,
)
from arknights_planner.agent.tactical import PlanHypothesis, operator_context
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION
from arknights_planner.mechanics_registry import MechanicsEvidenceRegistry
from arknights_planner.models.simulation import EventType
from .m11 import M11MinimumSquadSearch, M11SearchConfig
from .operator_assignment import OperatorAssignmentEngine, OperatorAssignmentPlan
from .scope import ExperimentScope
from .spatial_timing import SpatialTimingConfig, SpatialTimingSearch
from .stage_eligibility import (
    PlannerTaskType,
    StageEligibilityAnalyzer,
    StageIneligibleError,
)
from .stage_understanding import (
    StageUnderstanding,
    StageUnderstandingAnalyzer,
    TacticalRequirementModel,
    derive_tactical_requirements,
)
from .temporal_assignment import (
    build_temporal_assignment_frontier,
    derive_early_pressure_responsibilities,
    expand_hypotheses_with_assignments,
)
from .tactical_realizability import TacticalRealizabilityAnalyzer


class DeterministicHypothesisGenerator:
    """No-LLM tactical prior derived from stage structure and capabilities."""

    def generate_hypotheses(
        self,
        context: dict[str, Any],
        *,
        max_hypotheses: int = 1,
    ) -> tuple[PlanHypothesis, ...]:
        understanding = context.get("stage_understanding", {})
        assignment = context.get("operator_assignment", {})
        if isinstance(understanding, StageUnderstanding):
            understanding = understanding.to_dict()
        if isinstance(assignment, OperatorAssignmentPlan):
            assignment = assignment.to_dict()

        selected = tuple(assignment.get("preferred_operator_ids", ()))
        deployment_order = tuple(assignment.get("deployment_order", selected)) or selected
        assignment_rows = tuple(assignment.get("assignments", ()))
        lane_count = int(understanding.get("blocking_pressure", {}).get("lane_count", 1))
        shared_coverage = any(item.get("shared") for item in understanding.get("coverage_opportunities", ()))
        capabilities = tuple(
            row.get("capability")
            for row in assignment.get("assignments", ())
            if row.get("capability")
        )
        placement_intents = tuple(
            f"{item.get('tile_kind', 'DEPLOYABLE')} at {item.get('tile')} covers routes {', '.join(item.get('route_ids', ()))}"
            for item in understanding.get("coverage_opportunities", ())[:3]
        ) or ("legal route-crossing or route-covering deployment",)

        coverage_alternatives = tuple(assignment.get("coverage_alternatives", ()))
        if coverage_alternatives:
            hypotheses: list[PlanHypothesis] = []
            for alternative in coverage_alternatives:
                capabilities = tuple(dict.fromkeys(
                    capability
                    for coverage in alternative.get("operator_coverage", ())
                    for capability in (coverage.get("primary_capability"), *coverage.get("secondary_capabilities", ()))
                    if capability
                ))
                covered = len(alternative.get("covered_requirement_ids", ()))
                partial = len(alternative.get("partial_requirement_ids", ()))
                uncovered = len(alternative.get("uncovered_requirement_ids", ()))
                confidence = min(0.85, 0.5 + 0.05 * covered - 0.02 * partial - 0.03 * uncovered)
                hypotheses.append(PlanHypothesis(
                    hypothesis_id=alternative.get("assignment_id", f"coverage-{len(hypotheses) + 1}"),
                    summary=f"Use a {alternative.get('archetype', 'coverage')} assignment with explicit requirement coverage.",
                    reasoning=(
                        f"The assignment covers {covered} target requirements, marks {partial} as conditional, and leaves "
                        f"{uncovered} optional target requirements uncovered. One operator may cover multiple requirements; "
                        "SOFT and HYPOTHESIZED gaps rank the hypothesis rather than rejecting it before simulation."
                    ),
                    target_cardinality=int(alternative.get("operator_count", len(alternative.get("operator_ids", ())))),
                    tactical_archetype=alternative.get("archetype", "COVERAGE_ASSIGNMENT"),
                    required_capabilities=capabilities,
                    preferred_operator_ids=tuple(alternative.get("operator_ids", ())),
                    alternative_operator_ids=(),
                    placement_intents=placement_intents,
                    deployment_order=tuple(alternative.get("deployment_order", alternative.get("operator_ids", ()))),
                    skill_use_intents=("activate an interpreted skill only in its mapped pressure window",),
                    retreat_redeploy_intents=(),
                    operator_responsibilities=tuple(alternative.get("responsibility_links", ())),
                    confidence=max(0.35, confidence),
                ))
            return tuple(hypotheses[:max_hypotheses])

        hypotheses: list[PlanHypothesis] = []
        if lane_count <= 1:
            hypotheses.append(PlanHypothesis(
                hypothesis_id="single-choke-hold",
                summary="Hold the single lane cluster with a blocker and ranged support.",
                reasoning=(
                    f"StageUnderstanding groups active routes into {lane_count} lane cluster. "
                    "Capability assignment selects a blocker first and ranged damage from legal coverage opportunities. "
                    "Expected failure modes are insufficient block capacity, insufficient DPS, or late deployment."
                ),
                target_cardinality=len(selected),
                tactical_archetype="SINGLE_CHOKE_HOLD",
                required_capabilities=tuple(dict.fromkeys(("BLOCK", "RANGED_DPS", *capabilities))),
                preferred_operator_ids=selected,
                alternative_operator_ids=(),
                placement_intents=placement_intents,
                deployment_order=deployment_order,
                skill_use_intents=("activate an interpreted skill only in a high-risk pressure window",),
                retreat_redeploy_intents=(),
                confidence=0.72,
            ))
        else:
            hypotheses.append(PlanHypothesis(
                hypothesis_id="dual-lane-hold",
                summary="Assign blocking and ranged coverage to simultaneous pressure lanes.",
                reasoning=(
                    f"StageUnderstanding finds {lane_count} lane clusters and simultaneous pressure. "
                    "The hypothesis prioritizes lane-specific blocking before shared high-ground damage. "
                    "Expected failure modes are one uncovered lane, insufficient block capacity, or split DPS."
                ),
                target_cardinality=len(selected),
                tactical_archetype="DUAL_LANE_HOLD",
                required_capabilities=tuple(dict.fromkeys(("BLOCK", "RANGED_DPS", *capabilities))),
                preferred_operator_ids=selected,
                alternative_operator_ids=(),
                placement_intents=placement_intents,
                deployment_order=deployment_order,
                skill_use_intents=("activate an interpreted skill only when a lane pressure window peaks",),
                retreat_redeploy_intents=(),
                confidence=0.7,
            ))

        if shared_coverage:
            hypotheses.append(PlanHypothesis(
                hypothesis_id="shared-high-ground-coverage",
                summary="Use shared high-ground coverage to support multiple lanes.",
                reasoning=(
                    "At least one legal coverage opportunity crosses multiple active route records. "
                    "The hypothesis trades lane-specific placement for shared ranged coverage. "
                    "Expected failure modes are weak single-lane blocking and target allocation changes."
                ),
                target_cardinality=len(selected),
                tactical_archetype="SHARED_HIGH_GROUND_COVERAGE",
                required_capabilities=tuple(dict.fromkeys(("RANGED_DPS", "MULTI_LANE_COVERAGE", *capabilities))),
                preferred_operator_ids=tuple(sorted(selected, key=lambda item: (item not in deployment_order, deployment_order.index(item) if item in deployment_order else 0, item))),
                alternative_operator_ids=(),
                placement_intents=placement_intents,
                deployment_order=deployment_order,
                skill_use_intents=("delay skill use until enemies from multiple routes are in shared coverage",),
                retreat_redeploy_intents=(),
                confidence=0.65,
            ))

        def substitute_team(capability: str) -> tuple[str, ...] | None:
            row = next((item for item in assignment_rows if item.get("capability") == capability), None)
            if not row or not row.get("selected_operator_id"):
                return None
            replacement = next((
                candidate.get("operator_id")
                for candidate in row.get("candidates", ())
                if candidate.get("operator_id") and candidate.get("operator_id") not in selected
            ), None)
            if replacement is None:
                return None
            return tuple(
                replacement if operator_id == row["selected_operator_id"] else operator_id
                for operator_id in selected
            )

        blocker_team = substitute_team("BLOCK")
        if blocker_team and blocker_team != selected:
            hypotheses.append(PlanHypothesis(
                hypothesis_id="alternative-blocker-assignment",
                summary="Substitute the capability-ranked blocker while retaining the same tactical structure.",
                reasoning="OperatorAssignment provides a next-ranked GameData-backed blocker for the same blocking requirement.",
                target_cardinality=len(blocker_team),
                tactical_archetype="SINGLE_CHOKE_HOLD",
                required_capabilities=("BLOCK", "RANGED_DPS"),
                preferred_operator_ids=blocker_team,
                alternative_operator_ids=selected,
                placement_intents=placement_intents,
                deployment_order=tuple(blocker_team),
                skill_use_intents=(),
                retreat_redeploy_intents=(),
                confidence=0.62,
            ))

        ranged_team = substitute_team("RANGED_DPS")
        if ranged_team and ranged_team != selected:
            hypotheses.append(PlanHypothesis(
                hypothesis_id="alternative-ranged-assignment",
                summary="Substitute the capability-ranked ranged damage dealer.",
                reasoning="OperatorAssignment provides a next-ranked GameData-backed ranged DPS candidate for the same coverage requirement.",
                target_cardinality=len(ranged_team),
                tactical_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
                required_capabilities=("BLOCK", "RANGED_DPS"),
                preferred_operator_ids=ranged_team,
                alternative_operator_ids=selected,
                placement_intents=placement_intents,
                deployment_order=tuple(ranged_team),
                skill_use_intents=(),
                retreat_redeploy_intents=(),
                confidence=0.62,
            ))

        heal_row = next((item for item in assignment_rows if item.get("capability") == "HEAL"), None)
        heal_candidates = tuple(item.get("operator_id") for item in heal_row.get("candidates", ()) if item.get("operator_id")) if heal_row else ()
        healer = heal_candidates[0] if heal_candidates else None
        operator_rows = {item.get("operator_id"): item for item in context.get("operators", ())}
        if healer and healer not in selected and len(selected) >= 2:
            replaceable = next((
                operator_id for operator_id in reversed(selected)
                if operator_rows.get(operator_id, {}).get("position") == "RANGED"
            ), None)
            if replaceable:
                healer_team = tuple(healer if operator_id == replaceable else operator_id for operator_id in selected)
                hypotheses.append(PlanHypothesis(
                    hypothesis_id="healer-supported-frontline",
                    summary="Trade one ranged DPS slot for healer-supported sustain.",
                    reasoning="StageUnderstanding marks sustain risk and OperatorAssignment provides a GameData-backed healing candidate.",
                    target_cardinality=len(healer_team),
                    tactical_archetype="HEALER_SUPPORTED_FRONTLINE",
                    required_capabilities=("BLOCK", "RANGED_DPS", "HEAL"),
                    preferred_operator_ids=healer_team,
                    alternative_operator_ids=selected,
                    placement_intents=placement_intents,
                    deployment_order=tuple(healer_team),
                    skill_use_intents=("activate healing skill only after frontline damage begins",),
                    retreat_redeploy_intents=(),
                    confidence=0.6,
                ))

        hypotheses.append(PlanHypothesis(
            hypothesis_id="staggered-blocker-ranged-support",
            summary="Deploy cheap interception first, then add ranged support.",
            reasoning=(
                "The stage pressure and DP profile support a staggered opening. "
                "Capability assignment orders operators by source-backed cost and output. "
                "Expected failure modes are an early leak before the first blocker or late DPS."
            ),
            target_cardinality=len(selected),
            tactical_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
            required_capabilities=tuple(dict.fromkeys(("EARLY_DEPLOYMENT", "BLOCK", "RANGED_DPS", *capabilities))),
            preferred_operator_ids=selected,
            alternative_operator_ids=(),
            placement_intents=placement_intents,
            deployment_order=deployment_order,
            skill_use_intents=("use skills only after the frontline is established",),
            retreat_redeploy_intents=(),
            confidence=0.68,
        ))
        return tuple(hypotheses[:max_hypotheses])


class TopDownPlanner:
    """Orchestrate understanding-first planning with an explicit search scope."""

    def __init__(
        self,
        *,
        adapter: ApproximateRealSimulationAdapter,
        policy: RealSimulationApproximationPolicy,
        scope: ExperimentScope,
        hypothesis_generator: DeterministicHypothesisGenerator | None = None,
        spatial_config: SpatialTimingConfig | None = None,
        placement_options_per_operator: int = 8,
        root: Path | None = None,
    ):
        self.adapter = adapter
        self.policy = policy
        self.scope = scope
        self.hypothesis_generator = hypothesis_generator or DeterministicHypothesisGenerator()
        self.spatial_config = spatial_config or SpatialTimingConfig()
        self.placement_options_per_operator = placement_options_per_operator
        self.root = root or Path(__file__).resolve().parents[3]
        self.mechanics_registry = MechanicsEvidenceRegistry(self.root)

    def _configurations(self) -> tuple[RealOperatorConfiguration, ...]:
        if self.scope.pool_policy == "ALL_CURRENTLY_EXECUTABLE_PHASE_ZERO":
            allowed = set(self.scope.operator_pool)
            return tuple(
                item for item in self.adapter.all_executable_phase_zero_configurations()
                if item.operator_id in allowed
            )
        loadout = M13LoadoutPolicy.highest_legal()
        return tuple(loadout.configuration(self.adapter.repository, operator_id) for operator_id in self.scope.operator_pool)

    @staticmethod
    def _event_details(event) -> dict[str, Any]:
        return dict(event.details)

    @staticmethod
    def _strategy_fingerprint(strategy) -> str:
        payload = {
            "team": list(strategy.team),
            "actions": [
                {
                    "type": action.action_type.value,
                    "time": str(action.time),
                    "operator_id": action.operator_id,
                    "tile": action.tile,
                    "direction": action.direction,
                }
                for action in strategy.actions
            ],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _result_summary(result) -> dict[str, Any]:
        return {
            "win": bool(result.win),
            "remaining_life": result.remaining_life,
            "kills": result.enemies_killed,
            "leaks": result.enemies_leaked,
            "operator_deaths": result.operator_deaths,
            "time_survived": result.time_survived,
            "enemies_remaining": result.enemies_remaining,
            "remaining_enemy_hp": result.remaining_enemy_hp,
            "deployment_errors": list(result.deployment_errors),
        }

    def _failure_diagnosis(
        self,
        result,
        understanding: StageUnderstanding,
        assignment: OperatorAssignmentPlan,
        strategy,
        operators: dict,
    ) -> dict[str, Any]:
        spawn_routes = {
            event.source_id: self._event_details(event).get("route_id")
            for event in result.events
            if event.event_type is EventType.SPAWN
        }
        leaks = [event for event in result.events if event.event_type is EventType.ENEMY_LEAK]
        leak_routes = tuple(dict.fromkeys(filter(None, (spawn_routes.get(event.source_id) for event in leaks))))
        first_leak_time = leaks[0].time if leaks else None
        deploy_times = [action.time for action in strategy.actions if action.action_type.value == "DEPLOY"]
        assigned_ids = set(assignment.preferred_operator_ids)
        covered_routes = {
            route_id
            for opportunity in understanding.coverage_opportunities
            if assigned_ids.intersection(opportunity.operator_ids)
            for route_id in opportunity.route_ids
        }
        blocker_capacity = sum(
            int(operators[operator_id].phases[0].stats_max.block_count.value or 0)
            for operator_id in assignment.preferred_operator_ids
        )

        categories: list[str] = []
        if result.deployment_errors:
            if any("insufficient DP" in error for error in result.deployment_errors):
                categories.append("TIMING_ISSUE")
            if any("tile" in error or "MELEE operator" in error or "RANGED operator" in error for error in result.deployment_errors):
                categories.append("LOCAL_PLACEMENT_ISSUE")
            if any("deployment limit" in error for error in result.deployment_errors):
                categories.append("TACTICAL_HYPOTHESIS_ISSUE")
        if leaks and first_leak_time is not None and deploy_times and first_leak_time < max(deploy_times):
            categories.append("TIMING_ISSUE")
        if len(understanding.lanes) >= 2 and blocker_capacity < len(understanding.lanes):
            categories.append("TACTICAL_HYPOTHESIS_ISSUE")
        if result.operator_deaths:
            categories.append("OPERATOR_ASSIGNMENT_ISSUE")
        if result.enemies_killed < understanding.spawn_count / 2:
            categories.append("OPERATOR_ASSIGNMENT_ISSUE")
        if any(route_id not in covered_routes for route_id in leak_routes):
            categories.append("SPATIAL_SKELETON_ISSUE")
        if result.enemies_remaining and not leaks:
            categories.append("OPERATOR_ASSIGNMENT_ISSUE")
        if not categories:
            categories.append("OPERATOR_ASSIGNMENT_ISSUE" if leaks else "UNKNOWN")

        layer_priority = (
            "TACTICAL_HYPOTHESIS_ISSUE",
            "OPERATOR_ASSIGNMENT_ISSUE",
            "SPATIAL_SKELETON_ISSUE",
            "TIMING_ISSUE",
            "LOCAL_PLACEMENT_ISSUE",
            "UNKNOWN",
        )
        primary_layer = next((category for category in layer_priority if category in categories), categories[0])
        high_level_first = primary_layer in {"TACTICAL_HYPOTHESIS_ISSUE", "OPERATOR_ASSIGNMENT_ISSUE", "SPATIAL_SKELETON_ISSUE"}
        return {
            "categories": tuple(dict.fromkeys(categories)),
            "primary_layer": primary_layer,
            "first_leak_time": first_leak_time,
            "leak_routes": leak_routes,
            "assigned_coverage_routes": tuple(sorted(covered_routes)),
            "high_level_revision_before_local_repair": high_level_first,
            "revision_policy": (
                "revise hypothesis, assignment, or skeleton first; bounded local repair only for a concrete timing/placement candidate"
            ),
            "local_repair_eligible": not high_level_first and any(category in {"TIMING_ISSUE", "LOCAL_PLACEMENT_ISSUE"} for category in categories),
            "local_repair_policy": "supporting layer only; consume no more than 40% of the experiment budget",
        }

    def _runtime_mechanics_gates(self, result) -> dict[str, Any]:
        context = {
            "lifecycle": "RETARGET_AFTER_TARGET_DISAPPEARANCE",
            "planner_controls_targeting": False,
            "alternative_retarget_policy_implemented": False,
        }
        unknown = self.mechanics_registry.unknown_gate(
            "Q3",
            context,
            topic="targeting",
            terms=("retarget", "attack", "lock"),
        )
        planner_relevance = not result.win
        counterfactual_sensitivity = False
        mechanics_work = self.mechanics_registry.mechanics_work_gate(
            "Q3",
            context,
            planner_relevance=planner_relevance,
            counterfactual_sensitivity=counterfactual_sensitivity,
        )
        human_calibration = self.mechanics_registry.human_calibration_gate(
            "Q3",
            context,
            planner_relevance=planner_relevance,
            counterfactual_sensitivity=counterfactual_sensitivity,
        )
        return {
            "registry_used_in_runtime_path": True,
            "unknown_gate_used": True,
            "mechanics_work_gate_used": True,
            "human_calibration_gate_used": True,
            "Q3": {
                "unknown_gate": unknown,
                "mechanics_work_gate": mechanics_work,
                "human_calibration_gate": human_calibration,
            },
            "deterministic_sensitivity_check": {
                "planner_relevance": planner_relevance,
                "planner_controls_targeting": False,
                "alternative_retarget_policy_implemented": False,
                "counterfactual_sensitivity": counterfactual_sensitivity,
                "reason": "External planner actions do not control retarget timing, and no alternative policy is implemented; continue with the scoped approximation.",
            },
            "result": "NO_MECHANICS_WORK_REQUIRED",
            "human_calibration_result": "NO_HUMAN_CALIBRATION_REQUIRED",
        }

    def run(self) -> dict[str, Any]:
        if self.scope.simulation_budget <= 0:
            raise ValueError("TopDownPlanner requires a positive explicit simulation budget")

        eligibility = StageEligibilityAnalyzer().analyze(
            self.adapter.repository, self.scope.stage_id
        )
        first_win_attempt = self.scope.search_policy in {
            "FIRST_MEANINGFUL_WIN_ATTEMPT",
            "FIRST_HIGH_FIDELITY_MEANINGFUL_WIN",
            "FEASIBILITY_FIRST",
        }
        eligibility_task = eligibility.eligible_for(
            PlannerTaskType.AUTONOMOUS_TEAM_SELECTION
        )
        if first_win_attempt and not eligibility_task.eligible:
            raise StageIneligibleError(
                "stage is ineligible for autonomous team selection: "
                + ", ".join(eligibility_task.rejection_reasons)
            )

        configurations = self._configurations()
        config = M11SearchConfig(
            beam_width=1,
            placement_options_per_operator=self.placement_options_per_operator,
            max_squad_size=self.scope.max_cardinality,
            max_teams=1,
        )
        engine = M11MinimumSquadSearch(
            adapter=self.adapter,
            stage_id_or_code=self.scope.stage_id,
            policy=self.policy,
            operator_pool=configurations,
            config=config,
        )
        fixture = engine.fixture
        understanding = StageUnderstandingAnalyzer().analyze(fixture)
        requirements = derive_tactical_requirements(understanding)
        assignment = OperatorAssignmentEngine().assign(
            understanding,
            requirements,
            fixture.operators,
            max_cardinality=self.scope.max_cardinality,
            team_size_policy="FEASIBILITY_FIRST" if first_win_attempt else "LEXICOGRAPHIC_MINIMAL",
        )
        temporal_assignment = build_temporal_assignment_frontier(
            understanding,
            requirements,
            assignment,
            fixture.operators,
            OperatorAssignmentEngine(),
            deployment_limit=understanding.deployment_limit,
        )
        operators = operator_context(fixture.operators)
        context = {
            "stage_understanding": understanding.to_dict(),
            "tactical_requirements": [requirement.to_dict() for requirement in requirements],
            "operator_assignment": assignment.to_dict(),
            "temporal_assignment": [item.to_dict() for item in temporal_assignment],
            "early_pressure_responsibilities": [
                asdict(item)
                for item in derive_early_pressure_responsibilities(understanding, requirements)
            ],
            "temporal_assignment": [item.to_dict() for item in temporal_assignment],
            "early_pressure_responsibilities": [
                asdict(item)
                for item in derive_early_pressure_responsibilities(understanding, requirements)
            ],
            "operators": operators,
            "operator_ids": self.scope.operator_pool,
            "max_cardinality": self.scope.max_cardinality,
        }
        max_hypotheses = min(16, max(6, len(assignment.coverage_alternatives))) if first_win_attempt else max(1, len(assignment.preferred_operator_ids))
        hypotheses = self.hypothesis_generator.generate_hypotheses(
            context,
            max_hypotheses=max_hypotheses,
        )
        if first_win_attempt:
            hypotheses = expand_hypotheses_with_assignments(
                hypotheses,
                assignment,
                max_hypotheses=max_hypotheses,
                frontier=temporal_assignment,
            )
        generated_hypothesis_count = len(hypotheses)
        realizability = TacticalRealizabilityAnalyzer().validate(
            understanding,
            requirements,
            hypotheses,
        )
        hypotheses = realizability.accepted_hypotheses
        if not hypotheses:
            raise RuntimeError(
                "top-down planner requires at least one structurally realizable hypothesis; "
                f"rejected={len(realizability.rejected_hypotheses)}"
            )

        if first_win_attempt:
            spatial_search = SpatialTimingSearch(
                engine=engine,
                understanding=understanding,
                config=self.spatial_config,
            )
            spatial_outcome = spatial_search.search(
                hypotheses,
                simulation_budget=self.scope.simulation_budget,
            )
            simulations_used = spatial_outcome.metrics.unique_simulations
            cache_hits = spatial_outcome.metrics.cache_hits
            selected_hypotheses = list(hypotheses)
            attempts = []
            for row in spatial_outcome.attempts:
                attempts.append({
                    **row,
                    "team": list(row.get("team", ())),
                    "strategy_fingerprint": (
                        self._strategy_fingerprint(spatial_outcome.best.strategy)
                        if spatial_outcome.best and row.get("hypothesis_id") == spatial_outcome.best_hypothesis_id
                        else None
                    ),
                    "full_skeleton_reached": row.get("skeletons_generated", 0) > 0,
                    "spatial_timing_candidates_generated": row.get("timing_candidates_generated", 0),
                    "unique_simulations": row.get("unique_simulations", 0),
                    "candidate_simulations": row.get("unique_simulations", 0),
                    "robustness_simulations": 0,
                    "cache_hits": 0,
                })
            best_hypothesis = next(
                (item for item in hypotheses if item.hypothesis_id == spatial_outcome.best_hypothesis_id),
                None,
            )
            best = spatial_outcome.best
            best_outcome = SimpleNamespace(
                best=best,
                stop=spatial_outcome.stop,
                timeline=spatial_outcome.timeline,
                robustness_by_action=spatial_outcome.robustness_by_action,
            )

            failure = None
            if best is None:
                failure = {
                    "categories": ["SPATIAL_SKELETON_ISSUE"],
                    "primary_layer": "SPATIAL_SKELETON_ISSUE",
                    "revision_policy": "revise the spatial skeleton or operator assignment before local repair",
                    "local_repair_eligible": False,
                }
            elif not best.result.win:
                failure = self._failure_diagnosis(
                    best.result, understanding, assignment, best.strategy, fixture.operators
                )
            timeline = (
                spatial_outcome.timeline.to_dict()
                if spatial_outcome.timeline is not None else None
            )
            mechanics_gates = self._runtime_mechanics_gates(
                best.result if best is not None else type("NoResult", (), {"win": False})()
            )
            top_down_simulations = spatial_outcome.spatial_metrics.coarse_simulations
            local_repair_simulations = spatial_outcome.spatial_metrics.refinement_simulations
            return {
                "pipeline": [
                    "GameData", "GameUnderstanding", "TacticalRequirements",
                    "PlanHypotheses", "TacticalRealizability", "OperatorAssignment",
                    "SpatialSkeleton", "EventRelativeDeploymentTiming",
                    "EventRelativeSkillTiming", "Simulator", "CoarseToFineTiming",
                    "TopDownFailureRevision",
                ],
                "scope": self.scope.to_dict(),
                "conclusion_scope": self.scope.conclusion_scope(),
                "stage_eligibility": {
                    **eligibility.to_dict(),
                    "task_eligibility": eligibility_task.to_dict(),
                },
                "stage_understanding": understanding.to_dict(),
                "tactical_requirements": [item.to_dict() for item in requirements],
                "operator_assignment": assignment.to_dict(),
                "tactical_realizability": realizability.to_dict(),
                "hypotheses": [asdict(item) for item in hypotheses],
                "hypothesis": asdict(best_hypothesis) if best_hypothesis is not None else None,
                "llm_calls": 0,
                "real_llm_used": False,
                "search": {
                    "policy": self.scope.search_policy,
                    "stop": spatial_outcome.stop.value,
                    "win": bool(best and best.result.win),
                    "operator_ids": list(best.strategy.team) if best else [],
                    "action_count": len(best.strategy.actions) if best else 0,
                    "strategy_fingerprint": self._strategy_fingerprint(best.strategy) if best else None,
                    "unique_simulations": simulations_used,
                    "cache_hits": cache_hits,
                    "simulation_budget": self.scope.simulation_budget,
                    "budget_respected": simulations_used <= self.scope.simulation_budget,
                    "top_down_exploration_simulations": top_down_simulations,
                    "local_repair_simulations": local_repair_simulations,
                    "budget_split_respected": (
                        simulations_used == 0
                        or (
                            top_down_simulations >= 0.7 * simulations_used
                            and local_repair_simulations <= 0.3 * simulations_used
                        )
                    ),
                    "attempts": attempts,
                    "robustness_by_action": [list(row) for row in spatial_outcome.robustness_by_action],
                    "real_game_validation": "UNTESTED",
                },
                "candidate_funnel": {
                    "plan_hypotheses_generated": len(hypotheses),
                    "plan_hypotheses_generated_before_realizability": generated_hypothesis_count,
                    "plan_hypotheses_rejected_by_realizability": len(realizability.rejected_hypotheses),
                    "plan_hypotheses_revised_by_realizability": len(realizability.revised_hypotheses),
                    "plan_hypotheses_selected_for_budget": len(selected_hypotheses),
                    "plan_hypotheses_rejected_for_budget": 0,
                    "plan_hypotheses_simulated": len(attempts),
                    "hypotheses_without_complete_skeleton": sum(not row["full_skeleton_reached"] for row in attempts),
                    "tactical_requirement_sets_generated": 1,
                    "operator_assignments_generated": len(assignment.coverage_alternatives),
                    "operator_assignment_archetypes": list(dict.fromkeys(item.archetype for item in assignment.coverage_alternatives)),
                    "operator_assignments_rejected_before_simulation": 0,
                    "soft_or_hypothesized_deficiencies_allowed": True,
                    "tactical_regions_generated": spatial_outcome.spatial_metrics.regions_generated,
                    "tile_candidates_generated": spatial_outcome.spatial_metrics.tile_candidates_generated,
                    "tile_candidates_after_pruning": spatial_outcome.spatial_metrics.tile_candidates_after_pruning,
                    "facing_candidates_generated": spatial_outcome.spatial_metrics.facing_candidates_generated,
                    "facing_candidates_after_deduplication": spatial_outcome.spatial_metrics.facing_candidates_after_deduplication,
                    "skeletons_generated": spatial_outcome.spatial_metrics.skeletons_generated,
                    "skeletons_deduplicated": spatial_outcome.spatial_metrics.skeletons_deduplicated,
                    "skeletons_reaching_timing": spatial_outcome.spatial_metrics.skeletons_reaching_timing,
                    "timing_candidates_generated": spatial_outcome.spatial_metrics.timing_candidates_generated,
                    "timing_candidates_deduplicated": spatial_outcome.spatial_metrics.timing_candidates_deduplicated,
                    "timing_candidates_dp_rejected": spatial_outcome.spatial_metrics.timing_candidates_dp_rejected,
                    "spatial_timing_candidates_generated": spatial_outcome.spatial_metrics.timing_candidates_deduplicated,
                    "unique_full_simulations": simulations_used,
                    "cache_hits": cache_hits,
                    "budget_utilization": simulations_used / self.scope.simulation_budget,
                    "local_repair_simulations": local_repair_simulations,
                },
                "spatial_timing": {
                    "implementation_version": SpatialTimingSearch.VERSION,
                    "metrics": asdict(spatial_outcome.spatial_metrics),
                    "regions": [item.to_dict() for item in spatial_search.regions()],
                    "best_skeleton": spatial_outcome.best_skeleton.to_dict() if spatial_outcome.best_skeleton else None,
                    "audit": spatial_outcome.audit,
                    "timing_refinement_history": spatial_outcome.timing_refinement_history,
                },
                "result": self._result_summary(best.result) if best is not None else {"win": False, "reason": "NO_COMPLETE_SKELETON"},
                "failure_diagnosis": failure,
                "repair_layer": "BOUNDED_LOCAL_TIMING_ONLY",
                "causal_repair_role": "SUPPORTING_LAYER",
                "mechanics_gates": mechanics_gates,
                "external_timeline": timeline,
                "mechanics_version": ACTIVE_MECHANICS_VERSION,
                "first_win_principle": "A first complete simulator WIN has priority over narrow minimization or additional mechanics archaeology.",
            }

        attempts: list[dict[str, Any]] = []
        best_hypothesis = None
        best_outcome = None
        simulations_used = 0
        cache_hits = 0
        timing_offsets = (0, 90) if first_win_attempt else (0,)
        option_count = max(1, min(3, config.placement_options_per_operator))
        projected_simulations = 0
        robustness_reserve = 0
        selected_hypotheses: list[PlanHypothesis] = []
        for hypothesis in hypotheses:
            team_size = len(hypothesis.preferred_operator_ids)
            candidate_worst = option_count * len(timing_offsets) * team_size
            robustness_worst = len(config.refinement_frames) * team_size
            if projected_simulations + candidate_worst + max(robustness_reserve, robustness_worst) > self.scope.simulation_budget:
                break
            selected_hypotheses.append(hypothesis)
            projected_simulations += candidate_worst
            robustness_reserve = max(robustness_reserve, robustness_worst)

        for hypothesis in selected_hypotheses:
            outcome = engine.search_ordered_fixed_team(
                hypothesis.preferred_operator_ids,
                hypothesis.deployment_order,
                timing_offsets=timing_offsets,
                robustness=False,
            )
            candidate_simulations = outcome.metrics.unique_simulations
            robustness_simulations = 0
            cache_hits += outcome.metrics.cache_hits
            if outcome.best is not None and outcome.best.result.win:
                robust_outcome = engine.search_ordered_fixed_team(
                    hypothesis.preferred_operator_ids,
                    hypothesis.deployment_order,
                    timing_offsets=timing_offsets,
                    robustness=True,
                )
                robustness_simulations = robust_outcome.metrics.unique_simulations
                cache_hits += robust_outcome.metrics.cache_hits
                outcome = robust_outcome
            simulations_used += candidate_simulations + robustness_simulations
            if simulations_used > self.scope.simulation_budget:
                raise RuntimeError("top-down planner exceeded its explicit simulation budget")
            attempts.append({
                "hypothesis_id": hypothesis.hypothesis_id,
                "tactical_archetype": hypothesis.tactical_archetype,
                "team": list(outcome.best.strategy.team) if outcome.best else [],
                "strategy_fingerprint": self._strategy_fingerprint(outcome.best.strategy) if outcome.best else None,
                "result": self._result_summary(outcome.best.result) if outcome.best else {"win": False, "reason": "NO_COMPLETE_SKELETON"},
                "unique_simulations": candidate_simulations + robustness_simulations,
                "candidate_simulations": candidate_simulations,
                "robustness_simulations": robustness_simulations,
                "spatial_timing_candidates_generated": outcome.metrics.strategies_generated,
                "full_skeleton_reached": outcome.best is not None,
                "cache_hits": outcome.metrics.cache_hits,
            })
            if outcome.best is None:
                continue
            if best_outcome is None or (
                (outcome.best.result.win and not best_outcome.best.result.win)
                or (outcome.best.result.win == best_outcome.best.result.win and outcome.best.dense_rank < best_outcome.best.dense_rank)
            ):
                best_hypothesis = hypothesis
                best_outcome = outcome
            if outcome.best.result.win:
                break

        best = best_outcome.best if best_outcome is not None else None
        failure = None
        if best is None:
            failure = {
                "categories": ["SPATIAL_SKELETON_ISSUE"],
                "primary_layer": "SPATIAL_SKELETON_ISSUE",
                "revision_policy": "revise the spatial skeleton or operator assignment before local repair",
                "local_repair_eligible": False,
            }
        elif not best.result.win:
            failure = self._failure_diagnosis(best.result, understanding, assignment, best.strategy, fixture.operators)

        timeline = best_outcome.timeline.to_dict() if best_outcome is not None and best_outcome.timeline is not None else None
        mechanics_gates = self._runtime_mechanics_gates(best.result if best is not None else type("NoResult", (), {"win": False})())
        top_down_simulations = simulations_used
        local_repair_simulations = 0
        return {
            "pipeline": [
                "GameData",
                "GameUnderstanding",
                "TacticalRequirements",
                "PlanHypotheses",
                "OperatorAssignment",
                "SpatialSkeleton",
                "TimingSearch",
                "Simulator",
                "TopDownFailureRevision",
                "BoundedLocalRepairIfEligible",
            ],
            "scope": self.scope.to_dict(),
            "conclusion_scope": self.scope.conclusion_scope(),
            "stage_eligibility": {
                **eligibility.to_dict(),
                "task_eligibility": eligibility_task.to_dict(),
            },
            "stage_understanding": understanding.to_dict(),
            "tactical_requirements": [requirement.to_dict() for requirement in requirements],
            "operator_assignment": assignment.to_dict(),
            "temporal_assignment": [item.to_dict() for item in temporal_assignment],
            "early_pressure_responsibilities": [
                asdict(item)
                for item in derive_early_pressure_responsibilities(understanding, requirements)
            ],
            "hypotheses": [asdict(hypothesis) for hypothesis in hypotheses],
            "hypothesis": asdict(best_hypothesis) if best_hypothesis is not None else None,
            "llm_calls": 0,
            "real_llm_used": False,
            "search": {
                "policy": self.scope.search_policy,
                "stop": best_outcome.stop.value if best_outcome is not None else "NO_HYPOTHESIS_WITHIN_BUDGET",
                "win": bool(best and best.result.win),
                "operator_ids": list(best.strategy.team) if best else [],
                "action_count": len(best.strategy.actions) if best else 0,
                "strategy_fingerprint": self._strategy_fingerprint(best.strategy) if best else None,
                "unique_simulations": simulations_used,
                "cache_hits": cache_hits,
                "simulation_budget": self.scope.simulation_budget,
                "budget_respected": simulations_used <= self.scope.simulation_budget,
                "top_down_exploration_simulations": top_down_simulations,
                "local_repair_simulations": local_repair_simulations,
                "budget_split_respected": top_down_simulations >= 0.6 * simulations_used and local_repair_simulations <= 0.4 * simulations_used,
                "attempts": attempts,
                "robustness_by_action": [list(row) for row in best_outcome.robustness_by_action] if best_outcome is not None else [],
                "real_game_validation": "UNTESTED",
            },
            "candidate_funnel": {
                "plan_hypotheses_generated": len(hypotheses),
                "plan_hypotheses_selected_for_budget": len(selected_hypotheses),
                "plan_hypotheses_rejected_for_budget": len(hypotheses) - len(selected_hypotheses),
                "plan_hypotheses_simulated": len(attempts),
                "hypotheses_without_complete_skeleton": sum(not row["full_skeleton_reached"] for row in attempts),
                "tactical_requirement_sets_generated": 1,
                "operator_assignments_generated": len(assignment.coverage_alternatives),
                "operator_assignment_archetypes": list(dict.fromkeys(item.archetype for item in assignment.coverage_alternatives)),
                "operator_assignments_rejected_before_simulation": 0,
                "soft_or_hypothesized_deficiencies_allowed": True,
                "spatial_timing_candidates_generated": sum(row["spatial_timing_candidates_generated"] for row in attempts),
                "unique_full_simulations": simulations_used,
                "cache_hits": cache_hits,
                "budget_utilization": simulations_used / self.scope.simulation_budget if self.scope.simulation_budget else 0.0,
                "local_repair_simulations": 0,
            },
            "result": self._result_summary(best.result) if best is not None else {"win": False, "reason": "NO_COMPLETE_SKELETON"},
            "failure_diagnosis": failure,
            "repair_layer": "NOT_INVOKED",
            "causal_repair_role": "SUPPORTING_LAYER",
            "mechanics_gates": mechanics_gates,
            "external_timeline": timeline,
            "mechanics_version": ACTIVE_MECHANICS_VERSION,
            "first_win_principle": "A first complete simulator WIN has priority over narrow minimization or additional mechanics archaeology.",
        }
