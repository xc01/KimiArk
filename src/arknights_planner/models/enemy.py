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
    is_friendly: ValueWithSource[bool | None] = field(default_factory=unknown)
    counts_as_kill: ValueWithSource[bool | None] = field(default_factory=unknown)
    counts_as_leak: ValueWithSource[bool | None] = field(default_factory=unknown)
    death_life_point_reduce: ValueWithSource[int | None] = field(default_factory=unknown)
    is_neutral: ValueWithSource[bool | None] = field(default_factory=unknown)
    protected_target_attack_radius: ValueWithSource[float | int | None] = field(default_factory=unknown)
    movement_mode: ValueWithSource[str | None] = field(default_factory=unknown)


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
    delay_seconds: float = 0.0
    windup_seconds: float = 0.0
    animation_event_time_seconds: float | None = None
    animation_duration_seconds: float | None = None
    animation_speed: float | None = None
    attack_time_seconds: float | None = None
    max_anim_scale: float | None = None
    affected_by_slow_down: bool | None = None
    anim_slow_down: float = 1.0
    protected_target_priority: bool = False


def animation_event_real_seconds(
    *,
    animation_event_time_seconds: float,
    animation_duration_seconds: float,
    animation_speed: float,
    attack_time_seconds: float,
    max_anim_scale: float | None,
    affected_by_slow_down: bool = False,
    slow_down: float = 0.0,
    anim_slow_down: float = 1.0,
) -> float:
    """Scale a raw Spine event to real time using the candidate client formula.

    ``animation_speed`` is animation seconds advanced per real second.  The
    returned value is seconds from cast start to the named raw event.  A slow
    status multiplies the animation-data speed and divides both raw duration and
    the configured max scale, matching the ``_affectedBySlowDown`` branch.
    """
    if animation_speed <= 0:
        raise ValueError("animation_speed must be positive")
    if attack_time_seconds <= 0:
        raise ValueError("attack_time_seconds must be positive")
    if animation_duration_seconds < 0 or animation_event_time_seconds < 0:
        raise ValueError("raw animation times cannot be negative")
    slowdown_active = affected_by_slow_down and slow_down != 0
    if not slowdown_active:
        anim_slow_down = 1.0
    if anim_slow_down <= 0:
        raise ValueError("anim_slow_down must be positive")

    scaled_duration = animation_duration_seconds / anim_slow_down
    animation_scale = max(attack_time_seconds / scaled_duration, 0.1)
    if max_anim_scale is not None and max_anim_scale >= 0:
        scale_cap = min(max_anim_scale / anim_slow_down, 2.5) if slowdown_active else max_anim_scale
        animation_scale = min(animation_scale, scale_cap)
    return animation_event_time_seconds * animation_scale / (animation_speed * anim_slow_down)


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
