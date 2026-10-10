from __future__ import annotations

from dataclasses import dataclass, field

from .provenance import ValueWithSource, unknown
from .runtime import CombatOutputType, SyntheticSkill


@dataclass(frozen=True)
class OperatorStats:
    max_hp: ValueWithSource[float | int | None] = field(default_factory=unknown)
    atk: ValueWithSource[float | int | None] = field(default_factory=unknown)
    defense: ValueWithSource[float | int | None] = field(default_factory=unknown)
    magic_resistance: ValueWithSource[float | int | None] = field(default_factory=unknown)
    cost: ValueWithSource[int | None] = field(default_factory=unknown)
    block_count: ValueWithSource[int | None] = field(default_factory=unknown)
    attack_interval: ValueWithSource[float | None] = field(default_factory=unknown)
    redeploy_time: ValueWithSource[float | int | None] = field(default_factory=unknown)


@dataclass(frozen=True)
class OperatorAttributeKeyframe:
    """An exact source keyframe; no level interpolation is implied."""

    level: ValueWithSource[int | None]
    stats: OperatorStats


@dataclass(frozen=True)
class OperatorPhase:
    phase_index: int
    max_level: ValueWithSource[int | None]
    stats_min: OperatorStats
    stats_max: OperatorStats
    range_id: ValueWithSource[str | None] = field(default_factory=unknown)
    keyframes: tuple[OperatorAttributeKeyframe, ...] = ()


@dataclass(frozen=True)
class Operator:
    operator_id: str
    name: ValueWithSource[str | None]
    profession: ValueWithSource[str | None]
    branch: ValueWithSource[str | None]
    rarity: ValueWithSource[str | int | None]
    position: ValueWithSource[str | None]
    phases: tuple[OperatorPhase, ...]
    raw_source_file: str
    skill_ids: tuple[str, ...] = ()
    attack_range: tuple[tuple[int, int], ...] = ()
    synthetic_skill: SyntheticSkill | None = None
    combat_output: CombatOutputType = CombatOutputType.DAMAGE
    redeploy_time: ValueWithSource[float | None] = field(default_factory=unknown)
    star_rarity: ValueWithSource[int | None] = field(default_factory=unknown)
    damage_type: str = "PHYSICAL"
    deployment_cost_delta: float = 0.0
    attack_speed: float = 100.0
    maintenance_cost: float = 0.0
    maintenance_interval: float = 0.0
    deployment_sp_bonus: float = 0.0
    deployment_heal_all_value: float = 0.0
    redeploy_time_delta: float = 0.0
