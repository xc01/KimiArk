"""Capability coverage and diverse operator assignment for top-down planning."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Any

from .stage_understanding import StageUnderstanding, TacticalRequirementModel


@dataclass(frozen=True)
class OperatorCandidate:
    operator_id: str
    score: float
    evidence: str


@dataclass(frozen=True)
class RequirementAssignment:
    requirement_id: str
    requirement_type: str
    capability: str
    candidates: tuple[OperatorCandidate, ...]
    selected_operator_id: str | None


@dataclass(frozen=True)
class OperatorCapability:
    operator_id: str
    capability: str
    status: str
    score: float
    conditions: tuple[str, ...]
    evidence: str


@dataclass(frozen=True)
class RequirementCoverage:
    requirement_id: str
    requirement_type: str
    capability: str
    hardness: str
    status: str
    providers: tuple[OperatorCapability, ...]
    independent_satisfaction_required: bool
    dedicated_operator_required: bool
    note: str


@dataclass(frozen=True)
class AssignmentCoverage:
    operator_id: str
    covered_requirement_ids: tuple[str, ...]
    primary_capability: str
    secondary_capabilities: tuple[str, ...]
    conditions: tuple[str, ...]
    evidence: str


@dataclass(frozen=True)
class OperatorResponsibilityLink:
    operator_id: str
    capability: str
    requirement_ids: tuple[str, ...]
    tactical_responsibility: str
    spatial_intent: str
    temporal_intent: str
    action_intent: str


@dataclass(frozen=True)
class CoverageAssignmentAlternative:
    assignment_id: str
    archetype: str
    operator_ids: tuple[str, ...]
    deployment_order: tuple[str, ...]
    target_requirement_ids: tuple[str, ...]
    covered_requirement_ids: tuple[str, ...]
    partial_requirement_ids: tuple[str, ...]
    uncovered_requirement_ids: tuple[str, ...]
    operator_coverage: tuple[AssignmentCoverage, ...]
    semantic_fingerprint: str
    simulation_fingerprint: str
    operator_count: int
    total_rarity: int
    score: float
    rationale: str
    responsibility_links: tuple[OperatorResponsibilityLink, ...] = ()


@dataclass(frozen=True)
class OperatorAssignmentPlan:
    assignments: tuple[RequirementAssignment, ...]
    preferred_operator_ids: tuple[str, ...]
    deployment_order: tuple[str, ...]
    capability_evidence: tuple[str, ...]
    provenance: str
    requirement_coverage: tuple[RequirementCoverage, ...] = ()
    coverage_alternatives: tuple[CoverageAssignmentAlternative, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _CoverageState:
    operators: tuple[str, ...]
    covered: tuple[str, ...]
    conditional: tuple[str, ...]
    mappings: tuple[tuple[str, str, str], ...]

    def with_operator(
        self,
        operator_id: str,
        requirement_id: str,
        capability: str,
        conditional: bool,
    ) -> "_CoverageState":
        return _CoverageState(
            tuple(dict.fromkeys((*self.operators, operator_id))),
            tuple(dict.fromkeys((*self.covered, requirement_id))),
            tuple(dict.fromkeys((*self.conditional, requirement_id))) if conditional else self.conditional,
            tuple(sorted((*self.mappings, (requirement_id, operator_id, capability)))),
        )


class OperatorAssignmentEngine:
    """Map tactical requirements to GameData-backed, composable capabilities."""

    def assign(
        self,
        understanding: StageUnderstanding,
        requirements: tuple[TacticalRequirementModel, ...],
        operators: dict,
        *,
        max_cardinality: int,
        team_size_policy: str = "LEXICOGRAPHIC_MINIMAL",
    ) -> OperatorAssignmentPlan:
        assignments = []
        selected = []
        selected_capabilities: dict[str, set[str]] = {}
        ground_slots = len(understanding.deployable_ground)
        high_ground_slots = len(understanding.deployable_high_ground)
        squad_size_bound = (
            understanding.squad_size_limit
            if understanding.squad_size_limit > 0
            else max_cardinality
        )
        effective_max_cardinality = min(
            max_cardinality,
            len(operators),
            squad_size_bound,
        )

        def can_add(operator_id: str) -> bool:
            if operator_id in selected or len(selected) >= effective_max_cardinality:
                return False
            position = operators[operator_id].position.value
            return position in {"MELEE", "RANGED"} and bool(high_ground_slots or ground_slots)

        for requirement in requirements:
            capability = requirement.capability
            candidates = tuple(self._candidates(capability, understanding, operators))
            selected_id = next((
                operator_id
                for operator_id in selected
                if capability in self.capabilities(operators[operator_id], understanding)
            ), None)
            if selected_id is None:
                selected_id = next((item.operator_id for item in candidates if can_add(item.operator_id)), None)
                if selected_id is None:
                    selected_id = next((item.operator_id for item in candidates if item.operator_id in selected), None)
            if selected_id is not None and selected_id not in selected:
                selected.append(selected_id)
            if selected_id is not None:
                selected_capabilities.setdefault(selected_id, set()).add(capability)
            assignments.append(RequirementAssignment(
                requirement.requirement_id, requirement.requirement_type, capability,
                candidates[:8], selected_id,
            ))
        if not selected:
            ranked = sorted(
                operators,
                key=lambda operator_id: self._generic_score(operators[operator_id], understanding),
                reverse=True,
            )
            selected = ranked[:min(effective_max_cardinality, len(ranked))]
        if len(selected) < min(2, max_cardinality, len(operators)):
            for operator_id in sorted(operators):
                if operator_id not in selected:
                    selected.append(operator_id)
                if len(selected) >= min(2, effective_max_cardinality):
                    break
        deployment_order = tuple(sorted(
            selected,
            key=lambda operator_id: (
                float(operators[operator_id].phases[0].stats_max.cost.value or 0),
                -float(operators[operator_id].phases[0].stats_max.atk.value or 0),
                operator_id,
            ),
        ))
        requirement_coverage = self.requirement_coverage(understanding, requirements, operators)
        alternatives = self.coverage_alternatives(
            understanding,
            requirements,
            operators,
            max_cardinality=effective_max_cardinality,
            team_size_policy=team_size_policy,
        )
        if alternatives:
            preferred = alternatives[0]
            selected = list(preferred.operator_ids)
            deployment_order = preferred.deployment_order
            preferred_mapping = {
                requirement_id: coverage.operator_id
                for coverage in preferred.operator_coverage
                for requirement_id in coverage.covered_requirement_ids
            }
            assignments = tuple(
                replace(row, selected_operator_id=preferred_mapping.get(row.requirement_id))
                for row in assignments
            )
        return OperatorAssignmentPlan(
            assignments=tuple(assignments),
            preferred_operator_ids=tuple(selected),
            deployment_order=deployment_order,
            capability_evidence=(
                "position, profession, damage type, block count, attack, defense, HP, cost, and range come from GameData operator records",
                "coverage scores use legal deployment tiles and active route cells only",
                "one operator may cover multiple requirements; SOFT and HYPOTHESIZED deficiencies rank rather than reject",
            ),
            provenance="GameData-backed composable capability coverage; no stage or operator identifiers are hard-coded",
            requirement_coverage=requirement_coverage,
            coverage_alternatives=alternatives,
        )

    def capabilities(self, operator, understanding: StageUnderstanding) -> tuple[str, ...]:
        return tuple(item.capability for item in self.capability_catalog(operator, understanding))

    def capability_catalog(self, operator, understanding: StageUnderstanding) -> tuple[OperatorCapability, ...]:
        stats = operator.phases[0].stats_max
        position = operator.position.value
        atk = float(stats.atk.value or 0)
        block = int(stats.block_count.value or 0)
        cost = float(stats.cost.value or 0)
        coverage_count = sum(item.operator_ids.count(operator.operator_id) for item in understanding.coverage_opportunities)
        shared_count = sum(
            item.operator_ids.count(operator.operator_id)
            for item in understanding.coverage_opportunities
            if item.shared
        )
        output: list[OperatorCapability] = []

        def add(capability: str, score: float | None, evidence: str, conditions: tuple[str, ...] = ()) -> None:
            if score is None:
                return
            output.append(OperatorCapability(
                operator.operator_id,
                capability,
                "CONDITIONAL" if conditions else "FULL",
                float(score),
                conditions,
                evidence,
            ))

        initial_dp = float(understanding.initial_dp)
        dp_rate = float(understanding.dp_per_second)
        early_conditions = ()
        if cost > initial_dp:
            wait_seconds = (cost - initial_dp) / dp_rate if dp_rate > 0 else None
            if wait_seconds is None:
                early_conditions = ("deploy after DP accumulation; DP rate is unavailable",)
            else:
                early_conditions = (
                    f"deploy after DP accumulation (approximately {wait_seconds:.1f}s under the current DP policy)",
                )
        add(
            "EARLY_DEPLOYMENT",
            100 - cost * 5 + atk / 100,
            f"cost={cost:.0f}, ATK={atk:.0f}, initial DP={initial_dp:.0f}",
            early_conditions,
        )
        if position == "MELEE" and block > 0:
            add("BLOCK", block * 10 + float(stats.defense.value or 0) / 100 + float(stats.max_hp.value or 0) / 1000 + coverage_count,
                f"MELEE, block={block}, DEF={float(stats.defense.value or 0):.0f}, HP={float(stats.max_hp.value or 0):.0f}",
                ("deploy on an active route or interception tile",))
            add("BLOCK_CAPACITY", block * 10 + float(stats.max_hp.value or 0) / 1000 + float(stats.defense.value or 0) / 100,
                f"MELEE spare capacity, block={block}",
                ("preserve enough block capacity for the pressure window",))
        if position == "MELEE" and atk > 0:
            add("MELEE_DPS", atk / 100 + coverage_count, f"MELEE DPS, ATK={atk:.0f}",
                ("deploy where the operator can reach blocked or passing enemies",))
        if position == "RANGED" and atk > 0:
            add("RANGED_DPS", atk / 100 + coverage_count * 2, f"RANGED, ATK={atk:.0f}, coverage opportunities={coverage_count}",
                ("deploy on a legal high-ground coverage tile",) if coverage_count else ("no ranked route-coverage opportunity was found",))
            if shared_count:
                add("MULTI_LANE_COVERAGE", shared_count * 10 + atk / 100,
                    f"RANGED, ATK={atk:.0f}, shared coverage opportunities={shared_count}",
                    ("choose a shared high-ground tile and direction",))
        if operator.damage_type == "ARTS" and atk > 0:
            add("ARTS_DAMAGE", atk / 100 + coverage_count, f"ARTS, ATK={atk:.0f}",
                ("deploy within legal Arts range of the target pressure window",))
        if operator.combat_output.value == "HEAL" and atk > 0:
            add("HEAL", atk / 100 + coverage_count, f"HEAL output, ATK={atk:.0f}",
                ("place within healing range of the frontline",))
        if operator.synthetic_skill is not None and not operator.synthetic_skill.auto_activate:
            add("SKILL", 50 + atk / 100, "interpreted executable manual skill is available",
                ("activate at the relevant skill/timing window",))
        return tuple(output)

    def requirement_coverage(
        self,
        understanding: StageUnderstanding,
        requirements: tuple[TacticalRequirementModel, ...],
        operators: dict,
    ) -> tuple[RequirementCoverage, ...]:
        output: list[RequirementCoverage] = []
        for requirement in requirements:
            providers = tuple(sorted(
                (
                    item for operator in operators.values()
                    for item in self.capability_catalog(operator, understanding)
                    if item.capability == requirement.capability
                ),
                key=lambda item: (-item.score, item.operator_id),
            ))[:8]
            if not providers:
                status = "UNCOVERED"
                note = "No operator in the explicit ExperimentScope provides this capability."
            elif all(item.status == "CONDITIONAL" for item in providers):
                status = "CONDITIONAL"
                note = "Providers exist, but coverage depends on placement, timing, skill, or pressure context."
            else:
                status = "FULL"
                note = "At least one provider has the base GameData-backed capability."
            output.append(RequirementCoverage(
                requirement.requirement_id,
                requirement.requirement_type,
                requirement.capability,
                requirement.hardness,
                status,
                providers,
                False,
                False,
                note,
            ))
        return tuple(output)

    def coverage_alternatives(
        self,
        understanding: StageUnderstanding,
        requirements: tuple[TacticalRequirementModel, ...],
        operators: dict,
        *,
        max_cardinality: int,
        max_alternatives: int = 16,
        team_size_policy: str = "LEXICOGRAPHIC_MINIMAL",
    ) -> tuple[CoverageAssignmentAlternative, ...]:
        if not requirements:
            return ()
        if team_size_policy not in {"LEXICOGRAPHIC_MINIMAL", "FEASIBILITY_FIRST"}:
            raise ValueError(f"unknown team size policy: {team_size_policy}")
        requirement_by_id = {item.requirement_id: item for item in requirements}
        providers_by_requirement = {
            item.requirement_id: tuple(sorted(
                (capability for operator in operators.values() for capability in self.capability_catalog(operator, understanding)
                 if capability.capability == item.capability),
                key=lambda row: (-row.score, row.operator_id),
            ))
            for item in requirements
        }
        target_sets = self._target_requirement_sets(requirements)
        candidates: list[CoverageAssignmentAlternative] = []
        seen_simulation_fingerprints: set[str] = set()
        ranged_requirement_id = next(
            (item.requirement_id for item in requirements if item.requirement_type == "RANGED_DPS"),
            None,
        )

        for archetype, target_ids in target_sets:
            states = self._coverage_beam(
                target_ids,
                requirement_by_id,
                providers_by_requirement,
                understanding,
                operators,
                max_cardinality,
                team_size_policy=team_size_policy,
            )
            added_for_target = 0
            for state in states:
                if not state.operators:
                    continue
                alternative = self._alternative_from_state(
                    archetype,
                    state,
                    requirements,
                    operators,
                    target_ids,
                    team_size_policy=team_size_policy,
                )
                if alternative.simulation_fingerprint in seen_simulation_fingerprints:
                    continue
                if ranged_requirement_id and ranged_requirement_id not in alternative.covered_requirement_ids:
                    continue
                seen_simulation_fingerprints.add(alternative.simulation_fingerprint)
                candidates.append(alternative)
                added_for_target += 1
                if added_for_target >= 2:
                    break

        if team_size_policy == "FEASIBILITY_FIRST":
            expansion_bases = sorted(
                candidates,
                key=lambda item: (
                    -len(item.covered_requirement_ids),
                    -item.operator_count,
                    -item.score,
                    item.assignment_id,
                ),
            )[:2]
            for base in expansion_bases:
                candidates.extend(self._feasibility_roster_alternatives(
                    base,
                    requirements,
                    understanding,
                    operators,
                    max_cardinality,
                ))

        selected: list[CoverageAssignmentAlternative] = []
        selected_archetypes: set[str] = set()
        extras: list[CoverageAssignmentAlternative] = []
        for item in candidates:
            if item.archetype not in selected_archetypes:
                selected.append(item)
                selected_archetypes.add(item.archetype)
            else:
                extras.append(item)
        def ranking_key(item: CoverageAssignmentAlternative) -> tuple[Any, ...]:
            coverage = -len(item.covered_requirement_ids)
            if team_size_policy == "FEASIBILITY_FIRST":
                return (coverage, -item.operator_count, -item.score, item.assignment_id)
            return (coverage, -item.score, item.operator_count, item.total_rarity, item.assignment_id)

        selected.sort(key=ranking_key)
        extras.sort(key=ranking_key)
        output = [*selected[:max_alternatives], *extras]
        output = output[:max_alternatives]
        if understanding.spawn_count >= 8:
            capacity_requirement = next((item for item in requirements if item.requirement_type == "SUFFICIENT_BLOCK_CAPACITY"), None)
            base = next((item for item in output if item.archetype == "BLOCKER_PLUS_RANGED_SUPPORT"), output[0] if output else None)
            if capacity_requirement is not None and base is not None:
                joint = self._joint_block_alternative(base, capacity_requirement, understanding, operators)
                if joint is not None and joint.simulation_fingerprint not in {item.simulation_fingerprint for item in output}:
                    output.append(joint)
            output.extend(self._pressure_depth_alternatives(
                next((item for item in output if item.archetype == "BLOCKER_PLUS_RANGED_SUPPORT"), output[0] if output else None),
                requirements,
                understanding,
                operators,
            ))
        if team_size_policy == "FEASIBILITY_FIRST":
            control = self.control_roster(
                understanding,
                requirements,
                operators,
                max_cardinality=max_cardinality,
            )
            if control is not None and control.simulation_fingerprint not in {
                item.simulation_fingerprint for item in output
            }:
                output.append(control)
        output = [item for index, item in enumerate(output) if index == next(
            index for index, candidate in enumerate(output) if candidate.archetype == item.archetype
        )]
        output.sort(key=ranking_key)
        return tuple(output)

    @staticmethod
    def _target_requirement_sets(
        requirements: tuple[TacticalRequirementModel, ...],
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        by_type = {item.requirement_type: item.requirement_id for item in requirements}
        hard_ids = tuple(item.requirement_id for item in requirements if item.hardness == "HARD")
        blocking = by_type.get("SINGLE_LANE_BLOCKING") or by_type.get("DUAL_LANE_BLOCKING")
        ranged = by_type.get("RANGED_DPS")
        shared = by_type.get("MULTI_LANE_RANGED_COVERAGE")
        early = by_type.get("EARLY_CHEAP_DEPLOYMENT")
        heal = by_type.get("HEALING_SUSTAIN")
        arts = by_type.get("ARTS_DAMAGE")
        capacity = by_type.get("SUFFICIENT_BLOCK_CAPACITY")
        intercept = by_type.get("STALL_INTERCEPTION")
        melee_dps = by_type.get("MELEE_DPS")

        target_sets = [(
            "BLOCKER_PLUS_RANGED_SUPPORT",
            tuple(dict.fromkeys(item for item in (*hard_ids, blocking, ranged) if item)),
        )]
        if shared:
            target_sets.append(("SHARED_HIGH_GROUND_COVERAGE", tuple(dict.fromkeys(item for item in (*hard_ids, blocking, ranged, shared) if item))))
        if early:
            target_sets.append(("EARLY_CHEAP_INTERCEPTION", tuple(dict.fromkeys(item for item in (*hard_ids, blocking, early, ranged) if item))))
        if heal:
            target_sets.append(("HEALER_SUPPORTED_FRONTLINE", tuple(dict.fromkeys(item for item in (*hard_ids, blocking, ranged, heal) if item))))
        if arts:
            target_sets.append(("ARTS_INTERCEPTION", tuple(dict.fromkeys(item for item in (*hard_ids, blocking, ranged, arts) if item))))
        if capacity or intercept:
            target_sets.append(("FRONTLINE_CAPACITY_HOLD", tuple(dict.fromkeys(item for item in (*hard_ids, blocking, ranged, capacity, intercept) if item))))
        if melee_dps:
            target_sets.append(("MELEE_DPS_HOLD", tuple(dict.fromkeys(item for item in (*hard_ids, blocking, ranged, melee_dps) if item))))
        if early and capacity:
            target_sets.append(("STAGGERED_FRONTLINE", tuple(dict.fromkeys(item for item in (*hard_ids, blocking, early, capacity, ranged) if item))))
        return tuple((archetype, ids) for archetype, ids in target_sets if ids)

    def _coverage_beam(
        self,
        target_ids: tuple[str, ...],
        requirement_by_id: dict[str, TacticalRequirementModel],
        providers_by_requirement: dict[str, tuple[OperatorCapability, ...]],
        understanding: StageUnderstanding,
        operators: dict,
        max_cardinality: int,
        team_size_policy: str = "LEXICOGRAPHIC_MINIMAL",
    ) -> tuple[_CoverageState, ...]:
        hard_ids = {item.requirement_id for item in requirement_by_id.values() if item.hardness == "HARD"}
        frontier: list[_CoverageState] = [_CoverageState((), (), (), ())]
        completed: list[_CoverageState] = []
        for _ in range(max_cardinality):
            next_states: list[_CoverageState] = []
            for state in frontier:
                uncovered = [requirement_id for requirement_id in target_ids if requirement_id not in state.covered]
                if not uncovered:
                    completed.append(state)
                    continue
                requirement_id = min(
                    uncovered,
                    key=lambda item: (
                        0 if requirement_by_id[item].hardness == "HARD" else 1,
                        -requirement_by_id[item].confidence,
                        item,
                    ),
                )
                providers = providers_by_requirement[requirement_id][:6]
                for provider in providers:
                    if provider.operator_id in state.operators or not self._fits_slots(
                        state.operators, provider.operator_id, understanding, operators
                    ):
                        continue
                    expanded = state.with_operator(
                        provider.operator_id,
                        requirement_id,
                        provider.capability,
                        provider.status == "CONDITIONAL",
                    )
                    operator_capabilities = {
                        item.capability: item
                        for item in self.capability_catalog(operators[provider.operator_id], understanding)
                    }
                    for other_requirement_id in target_ids:
                        if other_requirement_id == requirement_id or other_requirement_id in expanded.covered:
                            continue
                        other_requirement = requirement_by_id[other_requirement_id]
                        other_capability = operator_capabilities.get(other_requirement.capability)
                        if other_capability is None:
                            continue
                        expanded = expanded.with_operator(
                            provider.operator_id,
                            other_requirement_id,
                            other_capability.capability,
                            other_capability.status == "CONDITIONAL",
                        )
                    next_states.append(expanded)
            if not next_states:
                completed.extend(frontier)
                break
            next_states.sort(
                key=lambda state: self._state_score(
                    state, target_ids, hard_ids, operators, team_size_policy
                ),
                reverse=True,
            )
            deduplicated: list[_CoverageState] = []
            seen: set[tuple] = set()
            for state in next_states:
                key = (state.operators, state.covered, state.mappings)
                if key in seen:
                    continue
                seen.add(key)
                deduplicated.append(state)
                if len(deduplicated) >= 12:
                    break
            frontier = deduplicated
            completed.extend(state for state in frontier if hard_ids.issubset(state.covered))
        completed.extend(frontier)
        valid = [state for state in completed if state.operators and hard_ids.issubset(state.covered)]
        valid.sort(
            key=lambda state: self._state_score(
                state, target_ids, hard_ids, operators, team_size_policy
            ),
            reverse=True,
        )
        return tuple(valid)

    @staticmethod
    def _fits_slots(
        selected: tuple[str, ...],
        operator_id: str,
        understanding: StageUnderstanding,
        operators: dict,
    ) -> bool:
        position = operators[operator_id].position.value
        already = sum(1 for item in selected if operators[item].position.value == position)
        limit = len(understanding.deployable_high_ground) if position == "RANGED" else len(understanding.deployable_ground)
        return already < limit

    @staticmethod
    def _state_score(
        state: _CoverageState,
        target_ids: tuple[str, ...],
        hard_ids: set[str],
        operators: dict,
        team_size_policy: str = "LEXICOGRAPHIC_MINIMAL",
    ) -> float:
        covered = set(state.covered)
        hard_covered = len(covered & hard_ids)
        target_covered = len(covered & set(target_ids))
        rarity = sum(OperatorAssignmentEngine._operator_rarity(operators[item]) for item in state.operators)
        cost = sum(float(operators[item].phases[0].stats_max.cost.value or 0) for item in state.operators)
        if team_size_policy == "FEASIBILITY_FIRST":
            return 1000 * hard_covered + 100 * target_covered + 5 * len(state.operators) - cost / 100
        return 1000 * hard_covered + 100 * target_covered - 50 * len(state.operators) - 2 * rarity - cost / 10

    def _feasibility_roster_alternatives(
        self,
        base: CoverageAssignmentAlternative,
        requirements: tuple[TacticalRequirementModel, ...],
        understanding: StageUnderstanding,
        operators: dict,
        max_cardinality: int,
    ) -> tuple[CoverageAssignmentAlternative, ...]:
        if base.operator_count >= max_cardinality:
            return ()
        skill_pressure = any(window.high_risk for window in understanding.pressure_windows)
        capability_order = tuple(dict.fromkeys((
            *(item.capability for item in requirements),
            *(("SKILL",) if skill_pressure else ()),
            "RANGED_DPS",
            "BLOCK_CAPACITY",
            "HEAL",
            "MELEE_DPS",
            "EARLY_DEPLOYMENT",
            "MULTI_LANE_COVERAGE",
        )))
        requirement_by_capability = {
            item.capability: item for item in requirements
        }
        fallback = requirements[0]
        selected = list(base.operator_ids)
        additions: list[tuple[OperatorCapability, TacticalRequirementModel, str]] = []
        capability_index = 0
        while len(selected) < max_cardinality:
            provider = None
            for offset in range(len(capability_order)):
                capability = capability_order[(capability_index + offset) % len(capability_order)]
                rows = [
                    item
                    for operator in operators.values()
                    for item in self.capability_catalog(operator, understanding)
                    if item.capability == capability and item.operator_id not in selected
                ]
                if not rows:
                    continue
                provider = max(rows, key=lambda item: (item.score, item.operator_id))
                requirement = requirement_by_capability.get(capability, fallback)
                additions.append((
                    provider,
                    requirement,
                    f"redundant or reserve {capability} provider for {requirement.requirement_type}",
                ))
                selected.append(provider.operator_id)
                capability_index += offset + 1
                break
            if provider is None:
                break

        output: list[CoverageAssignmentAlternative] = []
        target_sizes = tuple(
            size for size in (5, 6, 8, 12)
            if base.operator_count < size <= max_cardinality
        )
        for target_size in target_sizes:
            rows = additions[:target_size - base.operator_count]
            alternative = self._expanded_alternative(
                base,
                f"FEASIBILITY_REDUNDANCY_K{target_size}",
                tuple((provider, requirement) for provider, requirement, _ in rows),
                operators,
                "Capability-driven feasibility roster with tactical redundancy: "
                + "; ".join(justification for _, _, justification in rows),
                team_size_policy="FEASIBILITY_FIRST",
            )
            if alternative is not None:
                output.append(alternative)
        return tuple(output)

    def control_roster(
        self,
        understanding: StageUnderstanding,
        requirements: tuple[TacticalRequirementModel, ...],
        operators: dict,
        *,
        max_cardinality: int,
    ) -> CoverageAssignmentAlternative | None:
        if not requirements or max_cardinality < 2:
            return None
        ranked = sorted(
            requirements,
            key=lambda item: (
                0 if item.hardness == "HARD" else 1,
                -item.confidence,
                item.requirement_id,
            ),
        )
        requirement_by_capability = {item.capability: item for item in requirements}
        capability_order = tuple(dict.fromkeys((
            *(item.capability for item in ranked),
            *(("SKILL",) if any(window.high_risk for window in understanding.pressure_windows) else ()),
            "RANGED_DPS",
            "BLOCK_CAPACITY",
            "HEAL",
            "MELEE_DPS",
            "MULTI_LANE_COVERAGE",
            "EARLY_DEPLOYMENT",
            "SKILL",
        )))
        selected: list[str] = []
        additions: list[tuple[OperatorCapability, TacticalRequirementModel]] = []

        def add_provider(capability: str) -> bool:
            requirement = requirement_by_capability.get(capability) or ranked[0]
            if len(selected) >= max_cardinality:
                return False
            rows = [
                item
                for operator in operators.values()
                for item in self.capability_catalog(operator, understanding)
                if item.capability == capability and item.operator_id not in selected
            ]
            if not rows:
                return False
            provider = max(rows, key=lambda item: (item.score, item.operator_id))
            selected.append(provider.operator_id)
            additions.append((provider, requirement))
            return True

        for capability in capability_order:
            add_provider(capability)
        for capability in ("RANGED_DPS", "BLOCK_CAPACITY", "HEAL", "MELEE_DPS", "SKILL"):
            add_provider(capability)
        if not additions:
            return None
        core = CoverageAssignmentAlternative(
            "control-roster-base",
            "CONTROL_CAPABILITY_RICH",
            (),
            (),
            tuple(item.requirement_id for _, item in additions),
            (),
            (),
            tuple(item.requirement_id for _, item in additions),
            (),
            "control-empty",
            "control-empty",
            0,
            0,
            0.0,
            "Empty deterministic control-roster base.",
        )
        return self._expanded_alternative(
            core,
            "CONTROL_CAPABILITY_RICH",
            tuple(additions),
            operators,
            "Automatic diagnostic control roster prioritizing capability coverage and redundancy over rarity or minimum team size.",
            team_size_policy="FEASIBILITY_FIRST",
        )

    def _alternative_from_state(
        self,
        archetype: str,
        state: _CoverageState,
        requirements: tuple[TacticalRequirementModel, ...],
        operators: dict,
        target_ids: tuple[str, ...],
        team_size_policy: str = "LEXICOGRAPHIC_MINIMAL",
    ) -> CoverageAssignmentAlternative:
        mappings = {requirement_id: (operator_id, capability) for requirement_id, operator_id, capability in state.mappings}
        operator_requirements: dict[str, list[str]] = {}
        operator_capabilities: dict[str, list[str]] = {}
        for requirement_id, (operator_id, capability) in mappings.items():
            operator_requirements.setdefault(operator_id, []).append(requirement_id)
            operator_capabilities.setdefault(operator_id, []).append(capability)
        operator_coverage = []
        responsibility_links: list[OperatorResponsibilityLink] = []
        for operator_id in state.operators:
            capabilities = tuple(dict.fromkeys(operator_capabilities.get(operator_id, ())))
            primary = capabilities[0] if capabilities else "GENERAL"
            covered_ids = tuple(sorted(operator_requirements.get(operator_id, ())))
            operator_coverage.append(AssignmentCoverage(
                operator_id,
                covered_ids,
                primary,
                capabilities[1:],
                ("placement/timing condition applies to the mapped capabilities",),
                "GameData-backed capability mapping",
            ))
            responsibility_links.append(OperatorResponsibilityLink(
                operator_id,
                primary,
                covered_ids,
                f"provide {primary} for the mapped tactical requirements",
                self._spatial_intent(primary),
                "deploy at the relevant event-relative anchor after exact DP legality",
                "DEPLOY",
            ))
        covered = tuple(sorted(state.covered))
        conditional = set(state.conditional)
        partial = tuple(sorted(conditional))
        uncovered = tuple(sorted(set(target_ids) - set(covered)))
        deployment_order = tuple(sorted(
            state.operators,
            key=lambda item: (
                float(operators[item].phases[0].stats_max.cost.value or 0),
                -float(operators[item].phases[0].stats_max.atk.value or 0),
                item,
            ),
        ))
        semantic_payload = {
            "archetype": archetype,
            "operators": list(state.operators),
            "coverage": [list(item) for item in state.mappings],
        }
        simulation_payload = {
            "operators": sorted(state.operators),
            "deployment_order": list(deployment_order),
        }
        rarity = sum(self._operator_rarity(operators[item]) for item in state.operators)
        score = self._state_score(
            state,
            target_ids,
            {item.requirement_id for item in requirements if item.hardness == "HARD"},
            operators,
            team_size_policy,
        )
        return CoverageAssignmentAlternative(
            f"{archetype.lower()}-coverage",
            archetype,
            tuple(state.operators),
            deployment_order,
            target_ids,
            covered,
            partial,
            uncovered,
            tuple(operator_coverage),
            hashlib.sha256(json.dumps(semantic_payload, sort_keys=True).encode()).hexdigest(),
            hashlib.sha256(json.dumps(simulation_payload, sort_keys=True).encode()).hexdigest(),
            len(state.operators),
            rarity,
            score,
            "Bounded capability-coverage assignment; SOFT/HYPOTHESIZED gaps are ranking evidence, not rejection.",
            tuple(responsibility_links),
        )

    @staticmethod
    def _spatial_intent(capability: str) -> str:
        return {
            "BLOCK": "place on an active route interception tile",
            "BLOCK_CAPACITY": "place on a route tile with spare block capacity",
            "MELEE_DPS": "place where the operator can attack blocked or passing enemies",
            "RANGED_DPS": "place on legal high ground with route coverage",
            "MULTI_LANE_COVERAGE": "place on a shared high-ground coverage tile and facing",
            "HEAL": "place within healing range of the frontline",
            "EARLY_DEPLOYMENT": "place on an early interception or stabilization tile",
            "SKILL": "retain deployment geometry that permits the mapped skill effect",
        }.get(capability, "place on a legal tile satisfying the mapped capability")

    def _joint_block_alternative(
        self,
        base: CoverageAssignmentAlternative,
        requirement: TacticalRequirementModel,
        understanding: StageUnderstanding,
        operators: dict,
    ) -> CoverageAssignmentAlternative | None:
        providers = [
            item for operator in operators.values()
            for item in self.capability_catalog(operator, understanding)
            if item.capability == requirement.capability and item.operator_id not in base.operator_ids
        ]
        if not providers:
            return None
        provider = max(providers, key=lambda item: (item.score, item.operator_id))
        if not self._fits_slots(base.operator_ids, provider.operator_id, understanding, operators):
            return None
        operator_ids = tuple((*base.operator_ids, provider.operator_id))
        deployment_order = tuple(sorted(
            operator_ids,
            key=lambda item: (
                float(operators[item].phases[0].stats_max.cost.value or 0),
                -float(operators[item].phases[0].stats_max.atk.value or 0),
                item,
            ),
        ))
        coverage = (*base.operator_coverage, AssignmentCoverage(
            provider.operator_id,
            (requirement.requirement_id,),
            requirement.capability,
            (),
            provider.conditions,
            provider.evidence,
        ))
        semantic_payload = {
            "archetype": "DUAL_BLOCK_FRONTLINE",
            "operators": list(operator_ids),
            "joint_requirement": requirement.requirement_id,
            "coverage": [asdict(item) for item in coverage],
        }
        simulation_payload = {"operators": sorted(operator_ids), "deployment_order": list(deployment_order)}
        rarity = base.total_rarity + self._operator_rarity(operators[provider.operator_id])
        return CoverageAssignmentAlternative(
            "dual-block-frontline-coverage",
            "DUAL_BLOCK_FRONTLINE",
            operator_ids,
            deployment_order,
            tuple(dict.fromkeys((*base.target_requirement_ids, requirement.requirement_id))),
            tuple(sorted(set(base.covered_requirement_ids) | {requirement.requirement_id})),
            tuple(sorted(set(base.partial_requirement_ids) | ({requirement.requirement_id} if provider.status == "CONDITIONAL" else set()))),
            tuple(sorted(set(base.uncovered_requirement_ids) - {requirement.requirement_id})),
            coverage,
            hashlib.sha256(json.dumps(semantic_payload, sort_keys=True).encode()).hexdigest(),
            hashlib.sha256(json.dumps(simulation_payload, sort_keys=True).encode()).hexdigest(),
            len(operator_ids),
            rarity,
            base.score + 100 - 50 - 2 * self._operator_rarity(operators[provider.operator_id]),
            "Two blockers jointly provide capacity for a high-risk pressure window; this is a hypothesis, not a hard slot requirement.",
        )

    def _pressure_depth_alternatives(
        self,
        base: CoverageAssignmentAlternative | None,
        requirements: tuple[TacticalRequirementModel, ...],
        understanding: StageUnderstanding,
        operators: dict,
    ) -> tuple[CoverageAssignmentAlternative, ...]:
        if base is None:
            return ()
        requirement_by_type = {item.requirement_type: item for item in requirements}
        capacity = requirement_by_type.get("SUFFICIENT_BLOCK_CAPACITY")
        ranged = requirement_by_type.get("RANGED_DPS")
        heal = requirement_by_type.get("HEALING_SUSTAIN")
        melee_dps = requirement_by_type.get("MELEE_DPS")
        if capacity is None or ranged is None:
            return ()

        def provider(capability: str, excluded: tuple[str, ...]) -> OperatorCapability | None:
            rows = [
                item for operator in operators.values()
                for item in self.capability_catalog(operator, understanding)
                if item.capability == capability and item.operator_id not in excluded
            ]
            return max(rows, key=lambda item: (item.score, item.operator_id)) if rows else None

        block = provider("BLOCK_CAPACITY", base.operator_ids)
        if block is None:
            return ()
        second_ranged = provider("RANGED_DPS", (*base.operator_ids, block.operator_id))
        if second_ranged is not None:
            dual_ranged = self._expanded_alternative(
                base,
                "DUAL_BLOCK_RANGED_DEPTH",
                ((block, capacity), (second_ranged, ranged)),
                operators,
                "Add a second blocker and a second ranged source for a high-pressure window.",
            )
            if melee_dps is not None:
                melee = provider("MELEE_DPS", (*base.operator_ids, block.operator_id, second_ranged.operator_id))
                if melee is not None:
                    full_pressure = self._expanded_alternative(
                        dual_ranged,
                        "FULL_PRESSURE_HOLD",
                        ((melee, melee_dps),),
                        operators,
                        "Add frontline damage while retaining two blockers and two ranged sources.",
                    )
                    if full_pressure is not None:
                        return dual_ranged, full_pressure
            return (dual_ranged,)

        if heal is not None and melee_dps is not None:
            healer = provider("HEAL", (*base.operator_ids, block.operator_id))
            melee = provider("MELEE_DPS", (*base.operator_ids, block.operator_id))
            if healer is not None and melee is not None:
                sustained = self._expanded_alternative(
                    base,
                    "SUSTAINED_FRONTLINE_HOLD",
                    ((block, capacity), (healer, heal), (melee, melee_dps)),
                    operators,
                    "Use two blockers, a healer, and frontline damage for sustained pressure.",
                )
                if sustained is not None:
                    return (sustained,)
        return ()

    def _expanded_alternative(
        self,
        base: CoverageAssignmentAlternative,
        archetype: str,
        additions: tuple[tuple[OperatorCapability, TacticalRequirementModel], ...],
        operators: dict,
        rationale: str,
        team_size_policy: str = "LEXICOGRAPHIC_MINIMAL",
    ) -> CoverageAssignmentAlternative | None:
        selected = list(base.operator_ids)
        coverage = list(base.operator_coverage)
        responsibility_links = list(base.responsibility_links)
        target_ids = list(base.target_requirement_ids)
        partial = set(base.partial_requirement_ids)
        for capability, requirement in additions:
            if capability.operator_id in selected:
                return None
            selected.append(capability.operator_id)
            coverage.append(AssignmentCoverage(
                capability.operator_id,
                (requirement.requirement_id,),
                capability.capability,
                (),
                capability.conditions,
                capability.evidence,
            ))
            target_ids.append(requirement.requirement_id)
            responsibility_links.append(OperatorResponsibilityLink(
                capability.operator_id,
                capability.capability,
                (requirement.requirement_id,),
                f"provide redundant or reserve {capability.capability} for {requirement.requirement_type}",
                self._spatial_intent(capability.capability),
                "deploy at the relevant event-relative anchor or retain as an intentional reserve",
                "DEPLOY_OR_INTENTIONAL_RESERVE",
            ))
            if capability.status == "CONDITIONAL":
                partial.add(requirement.requirement_id)
        operator_ids = tuple(selected)
        deployment_order = tuple(dict.fromkeys((
            *base.deployment_order,
            *(capability.operator_id for capability, _ in additions),
        )))
        semantic_payload = {
            "archetype": archetype,
            "operators": list(operator_ids),
            "coverage": [asdict(item) for item in coverage],
        }
        simulation_payload = {"operators": sorted(operator_ids), "deployment_order": list(deployment_order)}
        rarity = sum(self._operator_rarity(operators[item]) for item in operator_ids)
        return CoverageAssignmentAlternative(
            f"{archetype.lower()}-coverage",
            archetype,
            operator_ids,
            deployment_order,
            tuple(dict.fromkeys(target_ids)),
            tuple(sorted({requirement_id for item in coverage for requirement_id in item.covered_requirement_ids})),
            tuple(sorted(partial)),
            (),
            tuple(coverage),
            hashlib.sha256(json.dumps(semantic_payload, sort_keys=True).encode()).hexdigest(),
            hashlib.sha256(json.dumps(simulation_payload, sort_keys=True).encode()).hexdigest(),
            len(operator_ids),
            rarity,
            base.score + (100 if team_size_policy == "FEASIBILITY_FIRST" else 50) * len(additions),
            rationale,
            tuple(responsibility_links),
        )

    def _candidates(self, capability: str, understanding: StageUnderstanding, operators: dict) -> list[OperatorCandidate]:
        rows = []
        for operator_id, operator in operators.items():
            score, evidence = self._capability_score(capability, operator, understanding)
            if score is not None:
                rows.append(OperatorCandidate(operator_id, float(score), evidence))
        return sorted(rows, key=lambda item: (-item.score, item.operator_id))

    @staticmethod
    def _operator_rarity(operator) -> int:
        value = operator.star_rarity.value
        if isinstance(value, int):
            return value
        raw = operator.rarity.value
        if isinstance(raw, str) and raw.startswith("TIER_") and raw[5:].isdigit():
            return int(raw[5:])
        return 0

    @staticmethod
    def _generic_score(operator, understanding: StageUnderstanding) -> float:
        stats = operator.phases[0].stats_max
        return (
            2.0 * float(stats.atk.value or 0) / 100
            + float(stats.block_count.value or 0)
            + float(stats.max_hp.value or 0) / 1000
            - float(stats.cost.value or 0) / 10
        )

    @staticmethod
    def _capability_score(capability: str, operator, understanding: StageUnderstanding):
        stats = operator.phases[0].stats_max
        position = operator.position.value
        atk = float(stats.atk.value or 0)
        block = int(stats.block_count.value or 0)
        cost = float(stats.cost.value or 0)
        hp = float(stats.max_hp.value or 0)
        defense = float(stats.defense.value or 0)
        coverage_count = sum(item.operator_ids.count(operator.operator_id) for item in understanding.coverage_opportunities)
        shared_coverage_count = sum(item.operator_ids.count(operator.operator_id) for item in understanding.coverage_opportunities if item.shared)
        if capability == "BLOCK":
            if position != "MELEE" or block <= 0:
                return None, ""
            return block * 10 + defense / 100 + hp / 1000 + coverage_count, f"MELEE, block={block}, DEF={defense:.0f}, HP={hp:.0f}"
        if capability == "BLOCK_CAPACITY":
            if position != "MELEE" or block <= 0:
                return None, ""
            return block * 10 + hp / 1000 + defense / 100, f"MELEE spare capacity, block={block}, HP={hp:.0f}, DEF={defense:.0f}"
        if capability == "MELEE_DPS":
            if position != "MELEE" or atk <= 0:
                return None, ""
            return atk / 100 + coverage_count, f"MELEE DPS, ATK={atk:.0f}, coverage opportunities={coverage_count}"
        if capability == "RANGED_DPS":
            if position != "RANGED" or atk <= 0:
                return None, ""
            return atk / 100 + coverage_count * 2, f"RANGED, ATK={atk:.0f}, coverage opportunities={coverage_count}"
        if capability == "MULTI_LANE_COVERAGE":
            if position != "RANGED" or atk <= 0:
                return None, ""
            return shared_coverage_count * 10 + atk / 100, f"RANGED, ATK={atk:.0f}, shared coverage opportunities={shared_coverage_count}"
        if capability == "ARTS_DAMAGE":
            if operator.damage_type != "ARTS" or atk <= 0:
                return None, ""
            return atk / 100 + coverage_count, f"ARTS, ATK={atk:.0f}, coverage opportunities={coverage_count}"
        if capability == "HEAL":
            if operator.combat_output.value != "HEAL" or atk <= 0:
                return None, ""
            return atk / 100 + coverage_count, f"HEAL output, ATK={atk:.0f}"
        if capability == "EARLY_DEPLOYMENT":
            if cost <= 0:
                return None, ""
            return 100 - cost * 5 + (atk / 100 if atk else 0), f"cost={cost:.0f}, ATK={atk:.0f}"
        if capability == "SKILL":
            if operator.synthetic_skill is None:
                return None, ""
            return 50 + atk / 100, "interpreted executable skill is available"
        return None, ""
