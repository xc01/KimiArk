from __future__ import annotations

from dataclasses import dataclass, field

from .provenance import ValueWithSource, unknown


@dataclass(frozen=True)
class EnemyStats:
    max_hp: ValueWithSource[float | int | None] = field(default_factory=unknown)
    atk: ValueWithSource[float | int | None] = field(default_factory=unknown)
    defense: ValueWithSource[float | int | None] = field(default_factory=unknown)
    magic_resistance: ValueWithSource[float | int | None] = field(default_factory=unknown)
    move_speed: ValueWithSource[float | int | None] = field(default_factory=unknown)
    attack_interval: ValueWithSource[float | int | None] = field(default_factory=unknown)
    weight: ValueWithSource[int | None] = field(default_factory=unknown)
    life_point_reduce: ValueWithSource[int | None] = field(default_factory=unknown)
    attack_range: ValueWithSource[float | int | None] = field(default_factory=unknown)
    block_requirement: ValueWithSource[int | None] = field(default_factory=unknown)
    apply_way: ValueWithSource[str | None] = field(default_factory=unknown)
    damage_type: ValueWithSource[str | None] = field(default_factory=unknown)
    hp_recovery_per_second: ValueWithSource[float | int | None] = field(default_factory=unknown)


@dataclass(frozen=True)
class EnemyAbility:
    """A bounded enemy ability primitive; unsupported families stay outside the model."""

    ability_id: str
    family: str
    cooldown: float
    initial_cooldown: float
    range_radius: float
    atk_scale: float
    damage_type: str = "ARTS"
    attack_count_threshold: int = 0
    status_name: str | None = None
    status_duration: float = 0.0
    attack_speed_delta: float = 0.0


@dataclass(frozen=True)
class EnemyAttackTiming:
    """Offline client-derived normal-attack animation timing."""

    animation: str
    duration_seconds: float
    windup_seconds: float
    recovery_seconds: float
    evidence_class: str
    source_url: str | None = None
    extraction_version: str = "enemy_attack_timing_v1"


@dataclass(frozen=True)
class Enemy:
    enemy_id: str
    name: ValueWithSource[str | None]
    stats: EnemyStats
    raw_source_file: str
    abilities: tuple[EnemyAbility, ...] = ()
    attack_timing: EnemyAttackTiming | None = None
