from __future__ import annotations

from dataclasses import dataclass, field

from .enemy import EnemyAbility
from enum import Enum


class EventType(str, Enum):
    TARGET_SELECTION = "TARGET_SELECTION"
    SPAWN = "SPAWN"
    DEPLOY = "DEPLOY"
    ATTACK_START = "ATTACK_START"
    ATTACK_WINDUP = "ATTACK_WINDUP"
    ATTACK_STRIKE = "ATTACK_STRIKE"
    ATTACK_RECOVERY_END = "ATTACK_RECOVERY_END"
    PROJECTILE_BORN = "PROJECTILE_BORN"
    PROJECTILE_HIT = "PROJECTILE_HIT"
    DAMAGE = "DAMAGE"
    ENEMY_DEATH = "ENEMY_DEATH"
    ENEMY_LEAK = "ENEMY_LEAK"
    ENEMY_ABILITY_START = "ENEMY_ABILITY_START"
    ENEMY_ABILITY_HIT = "ENEMY_ABILITY_HIT"
    ENEMY_STATUS_HIT = "ENEMY_STATUS_HIT"
    BLOCK = "BLOCK"
    UNBLOCK = "UNBLOCK"
    SKILL_READY = "SKILL_READY"
    SKILL_ACTIVATE = "SKILL_ACTIVATE"
    SKILL_END = "SKILL_END"
    DP_CHANGE = "DP_CHANGE"
    HEAL = "HEAL"
    OPERATOR_DEATH = "OPERATOR_DEATH"
    RETREAT = "RETREAT"
    DEVICE_TARGET_SELECTION = "DEVICE_TARGET_SELECTION"
    DEVICE_DAMAGE = "DEVICE_DAMAGE"
    DEVICE_DESTROYED = "DEVICE_DESTROYED"


@dataclass(frozen=True)
class SimulationEvent:
    time: float
    event_type: EventType
    source_id: str | None = None
    target_id: str | None = None
    details: tuple[tuple[str, str | float | int | bool], ...] = ()


@dataclass
class RuntimeEnemy:
    instance_id: str
    enemy_id: str
    route_id: str
    hp: float
    speed: float
    life_point_reduce: int
    defense: float = 0.0
    atk: float = 0.0
    attack_interval: float = 1.0
    attack_range: float | None = None
    magic_resistance: float = 0.0
    damage_type: str = "PHYSICAL"
    next_attack_time: float = 0.0
    distance: float = 0.0
    blocked_by: str | None = None
    spawn_index: int = 0
    route_wait_index: int = 0
    route_wait_remaining: float = 0.0
    abilities: tuple[EnemyAbility, ...] = ()
    ability_next_fire_time: float = 0.0
    attack_windup: float = 0.0
    attack_recovery: float = 0.0
    attack_animation_duration: float = 0.0
    attack_stand_until: float = 0.0
    attack_windup_started: bool = False
    max_hp: float = 0.0
    hp_recovery_per_second: float = 0.0
    normal_attack_count: int = 0


@dataclass
class RuntimeOperator:
    operator_id: str
    tile: tuple[int, int]
    direction: str
    hp: float
    max_hp: float
    base_atk: float
    base_block_count: int
    base_attack_interval: float
    base_attack_range: tuple[tuple[int, int], ...]
    defense: float
    magic_resistance: float
    combat_output: str
    redeploy_time: float
    position: str = "UNKNOWN"
    skill: object | None = None
    current_sp: float = 0.0
    skill_ready: bool = False
    skill_active: bool = False
    skill_remaining_duration: float = 0.0
    attack_cooldown: float = 0.0
    next_attack_time: float = 0.0
    pending_next_attack: bool = False
    blocked_enemy_ids: list[str] = field(default_factory=list)
    damage_type: str = "PHYSICAL"
    attack_speed: float = 100.0
    defense_penetration: float = 0.0
    defense_penetration_flat: float = 0.0
    magic_resist_penetration: float = 0.0
    magic_resist_penetration_flat: float = 0.0
    attack_speed_status_until: float = 0.0
    attack_speed_status_delta: float = 0.0


@dataclass
class RuntimeDevice:
    device_id: str
    template_id: str
    tile: tuple[int, int]
    hp: float
    max_hp: float
    defense: float
    magic_resistance: float
    taunt_level: int


@dataclass
class SimulationState:
    time: float
    dp: float
    remaining_life: int
    active_enemies: dict[str, RuntimeEnemy] = field(default_factory=dict)
    active_devices: dict[str, RuntimeDevice] = field(default_factory=dict)
    deployed_operators: dict[str, RuntimeOperator] = field(default_factory=dict)
    redeploy_available_at: dict[str, float] = field(default_factory=dict)
    events: list[SimulationEvent] = field(default_factory=list)
    enemies_killed: int = 0
    enemies_leaked: int = 0
    operator_deaths: int = 0
    deployment_errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SimulationRunMetadata:
    """Run-level provenance; avoids attaching source data to inner-loop arithmetic."""

    mode: str
    approximations_used: tuple[str, ...] = ()
    source_entities: tuple[str, ...] = ()


@dataclass(frozen=True)
class SimulationResult:
    win: bool
    remaining_life: int
    enemies_killed: int
    enemies_leaked: int
    operator_deaths: int
    time_survived: float
    score: float
    final_dp: float
    enemies_remaining: int
    remaining_enemy_hp: float
    remaining_enemy_route_progress: float
    events: tuple[SimulationEvent, ...]
    deployment_errors: tuple[str, ...]
    run_metadata: SimulationRunMetadata | None = None
