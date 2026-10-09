"""Temporal responsibilities and bounded operator-assignment expansion."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from .operator_assignment import CoverageAssignmentAlternative, OperatorAssignmentPlan
from .stage_understanding import StageUnderstanding, TacticalRequirementModel


@dataclass(frozen=True)
class EarlyPressureResponsibility:
    window_id: str
    phase: str
    start_time: float
    end_time: float
    route_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    spawn_count: int
    simultaneous_lane_count: int
    latest_safe_deployment_time: float
    required_capabilities: tuple[str, ...]
    block_required: bool
    pre_contact_damage_required: bool
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class TemporalResponsibility:
    responsibility_id: str
    role: str
    requirement_id: str
    pressure_window: str
    lane_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    start_time: float
    end_time: float
    required_capability: str
    required_capability_strength: str
    simultaneity_group: str | None
    replaceable: bool
    reserve_relation: str


@dataclass(frozen=True)
class SimultaneityConstraint:
    group_id: str
    window_id: str
    route_ids: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    minimum_distinct_operators: int
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class RoleOverload:
    operator_id: str
    responsibility_ids: tuple[str, ...]
    reason: str
    severity: str


@dataclass(frozen=True)
class OpeningDPFeasibility:
    assignment_id: str
    initial_dp: float
    dp_per_second: float
    deployment_costs: tuple[float, ...]
    feasible: bool
    infeasible_deployment_index: int | None
    infeasible_deployment_time: float | None
    evidence: str


@dataclass(frozen=True)
class TemporalAssignmentFrontier:
    assignment_id: str
    archetype: str
    operator_ids: tuple[str, ...]
    deployment_order: tuple[str, ...]
    temporal_responsibilities: tuple[TemporalResponsibility, ...]
    simultaneity_constraints: tuple[SimultaneityConstraint, ...]
    role_overloads: tuple[RoleOverload, ...]
    requirement_coverage: dict[str, str]
    opening_dp_feasibility: OpeningDPFeasibility
    reserve_utilization: dict[str, Any]
    semantic_fingerprint: str
    feasible: bool
    rejection_reasons: tuple[str, ...]
    precheck_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _lane_ids_for_routes(understanding: StageUnderstanding, routes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        lane.lane_id
        for lane in understanding.lanes
        if set(routes).intersection(lane.route_ids)
    ))


def _window(understanding: StageUnderstanding, window_id: str):
    return next((item for item in understanding.pressure_windows if item.window_id == window_id), None)


def derive_early_pressure_responsibilities(
    understanding: StageUnderstanding,
    requirements: tuple[TacticalRequirementModel, ...],
) -> tuple[EarlyPressureResponsibility, ...]:
    requirements_by_window: dict[str, list[TacticalRequirementModel]] = {}
    for requirement in requirements:
        requirements_by_window.setdefault(requirement.pressure_window, []).append(requirement)
    output = []
    for window in understanding.pressure_windows:
        rows = requirements_by_window.get(window.window_id, [])
        capabilities = tuple(dict.fromkeys(item.capability for item in rows))
        lane_ids = _lane_ids_for_routes(understanding, window.route_ids)
        speeds = [
            item.speed
            for item in understanding.enemy_archetypes
            if item.enemy_id in set(window.enemy_ids) and item.speed > 0
        ]
        route_lengths = [route.length for route in understanding.routes if route.route_id in set(window.route_ids)]
        first_contact = window.start_time
        if speeds and route_lengths:
            first_contact += min(route_lengths) / max(speeds)
        blocking = any("BLOCK" in capability for capability in capabilities)
        ranged = any("DPS" in capability or "COVERAGE" in capability for capability in capabilities)
        output.append(EarlyPressureResponsibility(
            window_id=window.window_id,
            phase=window.phase,
            start_time=window.start_time,
            end_time=window.end_time,
            route_ids=tuple(sorted(window.route_ids)),
            lane_ids=lane_ids,
            spawn_count=window.spawn_count,
            simultaneous_lane_count=window.simultaneous_lane_count,
            latest_safe_deployment_time=max(0.0, first_contact),
            required_capabilities=capabilities or ("RANGED_DPS",),
            block_required=blocking,
            pre_contact_damage_required=ranged or not blocking,
            evidence=(
                f"stage pressure window {window.window_id}",
                window.evidence,
                *(item.evidence for item in rows),
            ),
        ))
    return tuple(output)


def derive_temporal_responsibilities(
    understanding: StageUnderstanding,
    requirements: tuple[TacticalRequirementModel, ...],
) -> tuple[TemporalResponsibility, ...]:
    output = []
    for index, requirement in enumerate(requirements):
        window = _window(understanding, requirement.pressure_window)
        start = window.start_time if window else 0.0
        end = window.end_time if window else 0.0
        strength = "LOW" if requirement.confidence < 0.55 else "MEDIUM" if requirement.confidence < 0.75 else "HIGH"
        group = (
            f"SIM-{requirement.pressure_window}"
            if window and window.simultaneous_lane_count > 1
            else None
        )
        output.append(TemporalResponsibility(
            responsibility_id=f"TR-{index:02d}",
            role=requirement.requirement_type,
            requirement_id=requirement.requirement_id,
            pressure_window=requirement.pressure_window,
            lane_ids=_lane_ids_for_routes(understanding, requirement.affected_routes),
            route_ids=tuple(sorted(requirement.affected_routes)),
            start_time=start,
            end_time=end,
            required_capability=requirement.capability,
            required_capability_strength=strength,
            simultaneity_group=group,
            replaceable=requirement.hardness != "HARD",
            reserve_relation=(
                "EARLY_ACTIVE" if window and window.start_time <= 30.0
                else "MID_ACTIVE" if window and window.start_time <= 90.0
                else "LATE_ACTIVE" if window
                else "INTENTIONAL_RESERVE"
            ),
        ))
    return tuple(output)


def derive_simultaneity_constraints(
    responsibilities: tuple[TemporalResponsibility, ...],
) -> tuple[SimultaneityConstraint, ...]:
    groups: dict[str, list[TemporalResponsibility]] = {}
    for row in responsibilities:
        if row.simultaneity_group:
            groups.setdefault(row.simultaneity_group, []).append(row)
    return tuple(
        SimultaneityConstraint(
            group_id=group_id,
            window_id=rows[0].pressure_window,
            route_ids=tuple(sorted({route for row in rows for route in row.route_ids})),
            requirement_ids=tuple(sorted({row.requirement_id for row in rows})),
            minimum_distinct_operators=len(rows),
            evidence=tuple(f"{row.responsibility_id} overlaps {row.pressure_window}" for row in rows),
        )
        for group_id, rows in sorted(groups.items())
    )


def detect_role_overloads(
    responsibilities: tuple[TemporalResponsibility, ...],
) -> tuple[RoleOverload, ...]:
    by_group: dict[str, list[TemporalResponsibility]] = {}
    for row in responsibilities:
        if row.simultaneity_group:
            by_group.setdefault(row.simultaneity_group, []).append(row)
    output = []
    for group_id, rows in sorted(by_group.items()):
        distinct_routes = {tuple(sorted(row.route_ids)) for row in rows if row.route_ids}
        if len(rows) > 1 and len(distinct_routes) > 1:
            output.append(RoleOverload(
                operator_id="ANY_REUSED_OPERATOR",
                responsibility_ids=tuple(row.responsibility_id for row in rows),
                reason="Distinct simultaneous route responsibilities cannot share one operator without shared spatial coverage evidence.",
                severity="HIGH",
            ))
    return tuple(output)


def _temporal_deployment_order(
    assignment: CoverageAssignmentAlternative,
    operators: dict[str, Any],
    deployment_limit: int,
) -> tuple[str, ...]:
    active = tuple(sorted(
        assignment.operator_ids[:deployment_limit],
        key=lambda operator_id: (
            float(operators[operator_id].phases[0].stats_max.cost.value or 0),
            operator_id,
        ),
    ))
    reserves = tuple(item for item in assignment.operator_ids if item not in active)
    return active + reserves


def _opening_dp_feasibility(
    assignment: CoverageAssignmentAlternative,
    operators: dict[str, Any],
    understanding: StageUnderstanding,
    deployment_limit: int,
    latest_safe_deployment_time: float | None,
) -> OpeningDPFeasibility:
    initial_dp = float(understanding.initial_dp)
    dp_rate = float(understanding.dp_per_second)
    costs: list[float] = []
    feasible = True
    failure_index = None
    failure_time = None
    order = _temporal_deployment_order(assignment, operators, deployment_limit)[:deployment_limit]
    available = initial_dp
    elapsed = 0.0
    for index, operator_id in enumerate(order):
        cost = float(operators[operator_id].phases[0].stats_max.cost.value or 0)
        costs.append(cost)
        if available < cost:
            wait = (cost - available) / max(dp_rate, 0.001)
            elapsed += wait
            available = cost
        available -= cost
        if latest_safe_deployment_time is not None and elapsed > latest_safe_deployment_time + 0.001:
            feasible = False
            failure_index = index
            failure_time = elapsed
            break
    return OpeningDPFeasibility(
        assignment_id=assignment.assignment_id,
        initial_dp=initial_dp,
        dp_per_second=dp_rate,
        deployment_costs=tuple(costs),
        feasible=feasible,
        infeasible_deployment_index=failure_index,
        infeasible_deployment_time=failure_time,
        evidence=(
            "Sequential DP lower-bound precheck; downstream event-relative timing remains the legality authority."
            if feasible else
            "The cost-aware opening sequence is too late for the conservative first-contact deadline."
        ),
    )


def _coverage_status(
    assignment: CoverageAssignmentAlternative,
    requirements: tuple[TacticalRequirementModel, ...],
    understanding: StageUnderstanding,
    operators: dict[str, Any],
    engine: Any,
) -> dict[str, str]:
    output = {}
    for requirement in requirements:
        providers = [
            item for item in assignment.operator_coverage
            if requirement.capability == item.primary_capability
            or requirement.capability in item.secondary_capabilities
            or requirement.requirement_id in item.covered_requirement_ids
        ]
        if providers:
            statuses = {
                item.status
                for operator_id in providers
                for item in engine.capability_catalog(operators[operator_id.operator_id], understanding)
                if item.capability == requirement.capability
            }
            output[requirement.requirement_id] = (
                "FULL" if "FULL" in statuses
                else "CONDITIONAL" if "CONDITIONAL" in statuses
                else "PARTIAL"
            )
        else:
            output[requirement.requirement_id] = "UNSATISFIED"
    return output


def _reserve_utilization(
    assignment: CoverageAssignmentAlternative,
    deployment_limit: int,
) -> dict[str, Any]:
    active = assignment.deployment_order[:deployment_limit]
    reserves = tuple(item for item in assignment.operator_ids if item not in active)
    return {
        "active_first_wave": tuple(active),
        "intentional_reserves": reserves,
        "accidental_unused": (),
        "reserve_policy": "Assignment semantics preserve roster operators beyond the stage deployment limit as temporal reserves.",
    }


def _temporal_semantic_fingerprint(
    assignment: CoverageAssignmentAlternative,
    responsibilities: tuple[TemporalResponsibility, ...],
) -> str:
    payload = {
        "archetype": assignment.archetype,
        "mappings": [
            {
                "operator_id": item.operator_id,
                "requirement_ids": item.covered_requirement_ids,
                "capability": item.primary_capability,
            }
            for item in assignment.operator_coverage
        ],
        "deployment_order": assignment.deployment_order,
        "temporal": [asdict(item) for item in responsibilities],
    }
    material = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode()).hexdigest()


def expand_hypotheses_with_assignments(
    hypotheses,
    assignment: OperatorAssignmentPlan,
    *,
    max_hypotheses: int,
    frontier: tuple[TemporalAssignmentFrontier, ...] = (),
):
    """Bind each hypothesis to a distinct assignment alternative without mutating tactics."""
    alternatives = assignment.coverage_alternatives
    temporal_orders = {
        item.assignment_id: item.deployment_order
        for item in frontier
        if not item.rejection_reasons
    }
    if not alternatives:
        return hypotheses
    expanded = []
    seen = set()
    for index, hypothesis in enumerate(hypotheses):
        alternative = alternatives[index % len(alternatives)]
        semantic_key = (hypothesis.tactical_archetype, alternative.semantic_fingerprint, hypothesis.hypothesis_id)
        if semantic_key in seen:
            continue
        seen.add(semantic_key)
        expanded.append(type(hypothesis)(
            hypothesis_id=f"{hypothesis.hypothesis_id}--{alternative.assignment_id}",
            summary=hypothesis.summary,
            reasoning=hypothesis.reasoning,
            target_cardinality=alternative.operator_count,
            tactical_archetype=hypothesis.tactical_archetype,
            required_capabilities=hypothesis.required_capabilities,
            preferred_operator_ids=alternative.operator_ids,
            alternative_operator_ids=(*hypothesis.alternative_operator_ids, *alternative.operator_ids),
            placement_intents=hypothesis.placement_intents,
            deployment_order=temporal_orders.get(alternative.assignment_id, alternative.deployment_order),
            skill_use_intents=hypothesis.skill_use_intents,
            retreat_redeploy_intents=hypothesis.retreat_redeploy_intents,
            operator_responsibilities=tuple(
                asdict(item) for item in alternative.responsibility_links
            ) or hypothesis.operator_responsibilities,
            confidence=hypothesis.confidence,
        ))
    return tuple(expanded[:max_hypotheses])


def build_temporal_assignment_frontier(
    understanding: StageUnderstanding,
    requirements: tuple[TacticalRequirementModel, ...],
    assignment: OperatorAssignmentPlan,
    operators: dict[str, Any],
    engine: Any,
    *,
    deployment_limit: int,
    max_assignments: int = 16,
) -> tuple[TemporalAssignmentFrontier, ...]:
    responsibilities = derive_temporal_responsibilities(understanding, requirements)
    simultaneity = derive_simultaneity_constraints(responsibilities)
    overloads = detect_role_overloads(responsibilities)
    early = derive_early_pressure_responsibilities(understanding, requirements)
    earliest_deadline = min((item.latest_safe_deployment_time for item in early), default=None)
    output = []
    for alternative in assignment.coverage_alternatives[:max_assignments]:
        deployment_order = _temporal_deployment_order(alternative, operators, deployment_limit)
        dp = _opening_dp_feasibility(
            alternative,
            operators,
            understanding,
            deployment_limit,
            earliest_deadline,
        )
        coverage = _coverage_status(alternative, requirements, understanding, operators, engine)
        rejects = []
        if any(status == "UNSATISFIED" for status in coverage.values()):
            rejects.append("ASSIGNMENT_REQUIREMENT_UNSATISFIED")
        warnings = () if dp.feasible else ("OPENING_DP_RISK",)
        frontier = TemporalAssignmentFrontier(
            assignment_id=alternative.assignment_id,
            archetype=alternative.archetype,
            operator_ids=alternative.operator_ids,
            deployment_order=deployment_order,
            temporal_responsibilities=responsibilities,
            simultaneity_constraints=simultaneity,
            role_overloads=overloads,
            requirement_coverage=coverage,
            opening_dp_feasibility=dp,
            reserve_utilization=_reserve_utilization(alternative, deployment_limit),
            semantic_fingerprint=_temporal_semantic_fingerprint(alternative, responsibilities),
            feasible=not rejects,
            rejection_reasons=tuple(rejects),
            precheck_warnings=warnings,
        )
        output.append(frontier)
    return tuple(output)
