"""Structural feasibility checks between tactical intent and stage geometry."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from arknights_planner.agent.tactical import PlanHypothesis
from arknights_planner.search.stage_understanding import (
    StageUnderstanding,
    TacticalRequirementModel,
)


@dataclass(frozen=True)
class RealizabilityCheck:
    subject_type: str
    subject_id: str
    check: str
    status: str
    evidence: str
    actionability: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TacticalRealizabilityResult:
    status: str
    checks: tuple[RealizabilityCheck, ...]
    accepted_hypotheses: tuple[PlanHypothesis, ...]
    revised_hypotheses: tuple[PlanHypothesis, ...]
    rejected_hypotheses: tuple[PlanHypothesis, ...]
    revision_ancestry: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [item.to_dict() for item in self.checks],
            "accepted_hypotheses": [item.hypothesis_id for item in self.accepted_hypotheses],
            "revised_hypotheses": [item.hypothesis_id for item in self.revised_hypotheses],
            "rejected_hypotheses": [item.hypothesis_id for item in self.rejected_hypotheses],
            "revision_ancestry": list(self.revision_ancestry),
        }


class TacticalRealizabilityAnalyzer:
    """Reject or revise hypotheses that contradict exact stage geometry."""

    VERSION = "tactical-realizability-v1"

    def validate(
        self,
        understanding: StageUnderstanding,
        requirements: tuple[TacticalRequirementModel, ...],
        hypotheses: tuple[PlanHypothesis, ...],
    ) -> TacticalRealizabilityResult:
        checks = list(self._requirement_checks(understanding, requirements))
        requirement_status = {
            item.subject_id: item.status
            for item in checks
            if item.subject_type == "TACTICAL_REQUIREMENT"
        }
        accepted: list[PlanHypothesis] = []
        revised: list[PlanHypothesis] = []
        rejected: list[PlanHypothesis] = []
        ancestry: list[dict[str, str]] = []

        for hypothesis in hypotheses:
            revised_hypothesis, reason = self._revise_hypothesis(
                hypothesis,
                understanding,
                requirements,
                requirement_status,
            )
            if revised_hypothesis is None:
                rejected.append(hypothesis)
                checks.append(RealizabilityCheck(
                    "PLAN_HYPOTHESIS",
                    hypothesis.hypothesis_id,
                    "STRUCTURAL_REALIZABILITY",
                    "REJECTED",
                    reason,
                    tuple(
                        lane.actionability
                        for lane in understanding.lanes
                    ),
                ))
                continue
            if revised_hypothesis is hypothesis:
                accepted.append(hypothesis)
                checks.append(RealizabilityCheck(
                    "PLAN_HYPOTHESIS",
                    hypothesis.hypothesis_id,
                    "STRUCTURAL_REALIZABILITY",
                    "ACCEPTED",
                    "Required tactical actions have exact legal geometry.",
                    tuple(
                        lane.actionability
                        for lane in understanding.lanes
                    ),
                ))
                continue
            accepted.append(revised_hypothesis)
            revised.append(revised_hypothesis)
            ancestry.append({
                "parent_hypothesis_id": hypothesis.hypothesis_id,
                "revised_hypothesis_id": revised_hypothesis.hypothesis_id,
                "reason": reason,
            })
            checks.append(RealizabilityCheck(
                "PLAN_HYPOTHESIS",
                hypothesis.hypothesis_id,
                "STRUCTURAL_REALIZABILITY",
                "REVISED",
                reason,
                tuple(
                    lane.actionability
                    for lane in understanding.lanes
                ),
            ))

        status = "SUPPORTED"
        if rejected and not accepted:
            status = "NO_REALIZABLE_HYPOTHESIS"
        elif revised or rejected:
            status = "SUPPORTED_WITH_REVISIONS_OR_REJECTIONS"
        return TacticalRealizabilityResult(
            status=status,
            checks=tuple(checks),
            accepted_hypotheses=tuple(accepted),
            revised_hypotheses=tuple(revised),
            rejected_hypotheses=tuple(rejected),
            revision_ancestry=tuple(ancestry),
        )

    def _requirement_checks(
        self,
        understanding: StageUnderstanding,
        requirements: tuple[TacticalRequirementModel, ...],
    ) -> tuple[RealizabilityCheck, ...]:
        output: list[RealizabilityCheck] = []
        route_by_id = {route.route_id: route for route in understanding.routes}
        lane_by_id = {lane.lane_id: lane for lane in understanding.lanes}

        for requirement in requirements:
            if requirement.capability in {"BLOCK", "BLOCK_CAPACITY"}:
                affected_routes = tuple(
                    route_by_id[route_id]
                    for route_id in requirement.affected_routes
                    if route_id in route_by_id
                )
                non_blockable = tuple(
                    route.route_id for route in affected_routes if not route.blockable
                )
                block_tiles = tuple(sorted({
                    tile
                    for route in affected_routes
                    for tile in route.block_tiles
                }))
                output.append(RealizabilityCheck(
                    "TACTICAL_REQUIREMENT",
                    requirement.requirement_id,
                    "EXACT_BLOCKABLE_ROUTE_GEOMETRY",
                    "INFEASIBLE" if non_blockable else "FEASIBLE",
                    (
                        f"non-blockable routes: {', '.join(non_blockable)}"
                        if non_blockable
                        else f"exact legal ground tiles: {len(block_tiles)}"
                    ),
                    tuple(route.actionability if hasattr(route, "actionability") else () for route in affected_routes),
                ))
            elif requirement.requirement_type == "PRE_CONTACT_DAMAGE":
                covered_routes = {
                    route_id
                    for opportunity in understanding.coverage_opportunities
                    for route_id in opportunity.route_ids
                }
                feasible = any(
                    route_id in covered_routes
                    for route_id in requirement.affected_routes
                )
                output.append(RealizabilityCheck(
                    "TACTICAL_REQUIREMENT",
                    requirement.requirement_id,
                    "RANGED_PRE_CONTACT_COVERAGE",
                    "FEASIBLE" if feasible else "INFEASIBLE",
                    (
                        "at least one exact legal ranged coverage opportunity exists"
                        if feasible else "no exact legal ranged coverage opportunity covers the affected routes"
                    ),
                    ("PRE_CONTACT_DAMAGE_REQUIRED",),
                ))
            elif requirement.capability == "MULTI_LANE_COVERAGE":
                feasible = any(
                    opportunity.shared
                    and set(opportunity.route_ids).intersection(requirement.affected_routes)
                    for opportunity in understanding.coverage_opportunities
                )
                output.append(RealizabilityCheck(
                    "TACTICAL_REQUIREMENT",
                    requirement.requirement_id,
                    "SHARED_RANGED_COVERAGE",
                    "FEASIBLE" if feasible else "INFEASIBLE",
                    "shared exact route coverage exists" if feasible else "no shared exact route coverage exists",
                    ("SHARED_COVERAGE_OPPORTUNITY",),
                ))
            elif requirement.capability == "HEAL":
                block_tiles = {
                    tile
                    for lane in understanding.lanes
                    for tile in lane.block_tiles
                }
                plausible_support = any(
                    opportunity.tile_kind == "HIGH_GROUND"
                    and any(
                        abs(opportunity.tile[0] - tile[0]) + abs(opportunity.tile[1] - tile[1]) <= 3
                        for tile in block_tiles
                    )
                    for opportunity in understanding.coverage_opportunities
                ) if block_tiles else False
                output.append(RealizabilityCheck(
                    "TACTICAL_REQUIREMENT",
                    requirement.requirement_id,
                    "SUSTAIN_POSITION_OPPORTUNITY",
                    "FEASIBLE" if plausible_support else "INFEASIBLE",
                    "high-ground support geometry is structurally plausible near an exact block tile"
                    if plausible_support else "no plausible high-ground support geometry near an exact block tile",
                    ("SUSTAIN_POSITION_OPPORTUNITY",),
                ))

        for lane_id, lane in lane_by_id.items():
            output.append(RealizabilityCheck(
                "LANE",
                lane_id,
                "EXACT_LANE_ACTIONABILITY",
                "FEASIBLE" if lane.actionability != "NO_EXACT_TILE_INTERSECTION" else "INFEASIBLE",
                f"{len(lane.block_tiles)} exact ground block tiles; {len(lane.route_ids)} active routes",
                (lane.actionability,),
            ))
        return tuple(output)

    def _revise_hypothesis(
        self,
        hypothesis: PlanHypothesis,
        understanding: StageUnderstanding,
        requirements: tuple[TacticalRequirementModel, ...],
        requirement_status: dict[str, str],
    ) -> tuple[PlanHypothesis | None, str]:
        capabilities = set(hypothesis.required_capabilities)
        blockable_lanes = tuple(lane for lane in understanding.lanes if lane.blockable)
        non_blockable_lanes = tuple(lane for lane in understanding.lanes if not lane.blockable)
        blocking_requirement_ids = {
            item.requirement_id
            for item in requirements
            if item.capability in {"BLOCK", "BLOCK_CAPACITY"}
        }
        infeasible_nonblocking = tuple(
            item for item in requirements
            if requirement_status.get(item.requirement_id) == "INFEASIBLE"
            and item.capability in capabilities
            and item.capability not in {"BLOCK", "BLOCK_CAPACITY"}
        )
        if infeasible_nonblocking:
            return None, (
                "required tactical capability has no exact legal structural opportunity: "
                + ", ".join(sorted(item.requirement_id for item in infeasible_nonblocking))
            )
        invalid_blocking = any(
            requirement_status.get(item) == "INFEASIBLE"
            for item in blocking_requirement_ids
        )
        needs_revision = False
        reason_parts: list[str] = []

        if invalid_blocking and "BLOCK" in capabilities:
            needs_revision = True
            if not blockable_lanes:
                reason_parts.append("no active lane has an exact legal ground interception tile")
            else:
                reason_parts.append(
                    "at least one active lane is non-blockable under exact route geometry"
                )

        if non_blockable_lanes and "RANGED_DPS" not in capabilities:
            needs_revision = True
            reason_parts.append("non-blockable lane requires pre-contact ranged damage")

        pre_contact_requirements = tuple(
            item for item in requirements
            if item.requirement_type == "PRE_CONTACT_DAMAGE"
        )
        if any(
            requirement_status.get(item.requirement_id) == "INFEASIBLE"
            for item in pre_contact_requirements
        ) and "RANGED_DPS" in capabilities:
            return None, "non-blockable lane has no exact legal ranged coverage opportunity"

        if not needs_revision:
            return hypothesis, ""

        if not blockable_lanes:
            archetype = "RANGED_INTERCEPTION_ONLY"
            capabilities.discard("BLOCK")
            capabilities.discard("BLOCK_CAPACITY")
            capabilities.add("RANGED_DPS")
        else:
            archetype = "BLOCK_REALIZABLE_LANE_RANGED_INTERCEPT_OTHER"
            capabilities.update({"BLOCK", "RANGED_DPS"})

        revised = replace(
            hypothesis,
            hypothesis_id=f"{hypothesis.hypothesis_id}:realizable",
            tactical_archetype=archetype,
            required_capabilities=tuple(dict.fromkeys(capabilities)),
            summary=(
                f"Realizability revision: {archetype}; preserve legal blocking and "
                "use ranged pre-contact damage where blocking is impossible."
            ),
            reasoning=(
                f"Parent {hypothesis.hypothesis_id} was revised because "
                + "; ".join(reason_parts)
                + ". Revision uses exact StageUnderstanding route geometry."
            ),
            skill_use_intents=tuple(dict.fromkeys((
                *hypothesis.skill_use_intents,
                "activate a supported damage or sustain skill in the mapped pressure window",
            ))),
        )
        return revised, "; ".join(reason_parts)
