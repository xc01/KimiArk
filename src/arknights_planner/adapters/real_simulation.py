"""Strict, provenance-aware adapter from canonical GameData to future simulation inputs.

This module deliberately does *not* invoke the synthetic simulator. It records the
facts a real simulation would need and refuses execution until known missing
mechanics have explicit implementations or opt-in, separately documented policies.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass

from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.enemy import Enemy
from arknights_planner.models.operator import Operator, OperatorAttributeKeyframe
from arknights_planner.models.provenance import KnowledgeStatus, ValueWithSource
from arknights_planner.models.skill import AttackRange, Skill, SkillLevel
from arknights_planner.models.stage import Stage, StageActionData, StageLevelStructure


class StrictSimulationCompatibilityError(RuntimeError):
    """Raised instead of silently feeding unresolved real data into the simulator."""


@dataclass(frozen=True)
class RealSkillData:
    """A selected real skill level whose raw parameters remain non-executable."""

    skill: Skill
    selected_level: SkillLevel
    simulator_executable: bool
    execution_blockers: tuple[str, ...]


@dataclass(frozen=True)
class AdaptedRealOperator:
    operator: Operator
    phase_index: int
    requested_level: int
    exact_keyframe: OperatorAttributeKeyframe | None
    attack_range: AttackRange | None
    skill: RealSkillData | None
    structurally_loadable: bool
    adaptation_blockers: tuple[str, ...]


@dataclass(frozen=True)
class AdaptedRealEnemy:
    enemy: Enemy
    requested_level: int
    structurally_loadable: bool
    adaptation_blockers: tuple[str, ...]


@dataclass(frozen=True)
class AdaptedRealStage:
    stage: Stage
    structure: StageLevelStructure | None
    spawn_actions: tuple[StageActionData, ...]
    structurally_loadable: bool
    adaptation_blockers: tuple[str, ...]


@dataclass(frozen=True)
class CompatibilityReport:
    """Machine-readable strict-mode decision; no approximation is implicit."""

    structurally_loadable: bool
    simulator_executable: bool
    status_counts: tuple[tuple[KnowledgeStatus, int], ...]
    blockers: tuple[str, ...]
    requested_approximations: tuple[str, ...] = ()

    def count(self, status: KnowledgeStatus) -> int:
        return dict(self.status_counts).get(status, 0)


@dataclass(frozen=True)
class RealSimulationBundle:
    operator: AdaptedRealOperator
    enemy: AdaptedRealEnemy
    stage: AdaptedRealStage
    report: CompatibilityReport


class RealSimulationAdapter:
    """Adapt canonical data while keeping strict real-data execution disabled by default."""

    def __init__(self, repository: GameDataRepository, *, strict: bool = True):
        self.repository = repository
        self.strict = strict

    def adapt_skill(self, skill_id: str, *, skill_level_index: int) -> RealSkillData:
        skill = self.repository.get_skill(skill_id)
        if skill_level_index < 0 or skill_level_index >= len(skill.levels):
            raise ValueError(f"Skill level index is unavailable: {skill_id}[{skill_level_index}]")
        level = skill.levels[skill_level_index]
        # A skill can be structurally complete yet still have no generic execution.
        blocker = "real skill blackboard/effect semantics are not implemented"
        return RealSkillData(skill, level, False, (blocker,))

    def adapt_operator(
        self,
        operator_id_or_name: str,
        *,
        phase_index: int,
        level: int,
        skill_id: str | None = None,
        skill_level_index: int = 0,
    ) -> AdaptedRealOperator:
        operator = self.repository.get_operator(operator_id_or_name)
        blockers: list[str] = []
        if phase_index < 0 or phase_index >= len(operator.phases):
            raise ValueError(f"Phase index is unavailable: {operator.operator_id}[{phase_index}]")
        phase = operator.phases[phase_index]
        exact_keyframe = next((item for item in phase.keyframes if item.level.value == level), None)
        if exact_keyframe is None:
            blockers.append(
                f"operator level {level} is not an exact source keyframe for phase {phase_index}; interpolation is unsupported"
            )
        attack_range = self.repository.get_range(phase.range_id.value) if phase.range_id.value else None
        if attack_range is None:
            blockers.append("operator attack range ID is UNKNOWN")
        selected_skill_id = skill_id or (operator.skill_ids[0] if operator.skill_ids else None)
        if selected_skill_id is not None and selected_skill_id not in operator.skill_ids:
            raise ValueError(f"Skill {selected_skill_id} is not referenced by {operator.operator_id}")
        real_skill = self.adapt_skill(selected_skill_id, skill_level_index=skill_level_index) if selected_skill_id else None
        if selected_skill_id is None:
            blockers.append("operator has no selected skill")
        return AdaptedRealOperator(
            operator, phase_index, level, exact_keyframe, attack_range, real_skill,
            exact_keyframe is not None and attack_range is not None, tuple(blockers),
        )

    def adapt_enemy(self, enemy_id_or_name: str, *, level: int = 0) -> AdaptedRealEnemy:
        enemy = self.repository.get_enemy(enemy_id_or_name, level=level)
        required = {
            "HP": enemy.stats.max_hp,
            "ATK": enemy.stats.atk,
            "DEF": enemy.stats.defense,
            "RES": enemy.stats.magic_resistance,
            "move speed": enemy.stats.move_speed,
            "base attack time": enemy.stats.attack_interval,
            "mass": enemy.stats.weight,
            "life-point reduction": enemy.stats.life_point_reduce,
        }
        blockers = tuple(f"enemy level {level} {name} is {value.status.value}" for name, value in required.items() if value.status is KnowledgeStatus.UNKNOWN)
        return AdaptedRealEnemy(enemy, level, not blockers, blockers)

    def adapt_stage(self, stage_id_or_code: str) -> AdaptedRealStage:
        stage = self.repository.get_stage(stage_id_or_code)
        structure = stage.level_structure
        spawn_actions = tuple(
            action
            for wave in (structure.waves if structure else ())
            for fragment in wave.fragments
            for action in fragment.actions
            if action.action_type.value == "SPAWN"
        )
        blockers = () if structure is not None else ("stage level file is unavailable",)
        return AdaptedRealStage(stage, structure, spawn_actions, structure is not None, blockers)

    @staticmethod
    def _status_counts(*values: object) -> tuple[tuple[KnowledgeStatus, int], ...]:
        counts = {status: 0 for status in KnowledgeStatus}

        def visit(value: object) -> None:
            if isinstance(value, ValueWithSource):
                counts[value.status] += 1
            elif is_dataclass(value):
                for field in fields(value):
                    visit(getattr(value, field.name))
            elif isinstance(value, (tuple, list)):
                for item in value:
                    visit(item)
            elif isinstance(value, dict):
                for item in value.values():
                    visit(item)

        for value in values:
            visit(value)
        return tuple((status, counts[status]) for status in KnowledgeStatus)

    def compatibility_report(
        self,
        operator: AdaptedRealOperator,
        enemy: AdaptedRealEnemy,
        stage: AdaptedRealStage,
    ) -> CompatibilityReport:
        blockers = list(operator.adaptation_blockers) + list(enemy.adaptation_blockers) + list(stage.adaptation_blockers)
        if operator.attack_range is not None:
            blockers.append("real range row/col transformation by facing direction is UNKNOWN")
        if stage.spawn_actions:
            blockers.append("absolute SPAWN timing from wave/fragment/action preDelay is UNKNOWN")
        if operator.skill is not None:
            blockers.extend(operator.skill.execution_blockers)
        blockers.extend((
            "real attack windup/recovery timing is UNKNOWN",
            "real projectile behavior/timing is UNKNOWN",
        ))
        unique_blockers = tuple(dict.fromkeys(blockers))
        structurally_loadable = operator.structurally_loadable and enemy.structurally_loadable and stage.structurally_loadable
        return CompatibilityReport(
            structurally_loadable,
            False,
            self._status_counts(operator, enemy, stage),
            unique_blockers,
        )

    def adapt_combination(
        self,
        *,
        operator_id_or_name: str,
        operator_phase: int,
        operator_level: int,
        enemy_id_or_name: str,
        enemy_level: int,
        stage_id_or_code: str,
        skill_id: str | None = None,
        skill_level_index: int = 0,
    ) -> RealSimulationBundle:
        operator = self.adapt_operator(
            operator_id_or_name, phase_index=operator_phase, level=operator_level,
            skill_id=skill_id, skill_level_index=skill_level_index,
        )
        enemy = self.adapt_enemy(enemy_id_or_name, level=enemy_level)
        stage = self.adapt_stage(stage_id_or_code)
        return RealSimulationBundle(operator, enemy, stage, self.compatibility_report(operator, enemy, stage))

    def require_simulator_execution(self, bundle: RealSimulationBundle) -> None:
        """Strict gate reserved for a future real-data simulator adapter implementation."""
        if self.strict or not bundle.report.simulator_executable:
            blockers = "; ".join(bundle.report.blockers) or "no executable adapter has been implemented"
            raise StrictSimulationCompatibilityError(f"Real-data simulation is refused: {blockers}")
