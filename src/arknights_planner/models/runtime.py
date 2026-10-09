from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DeploymentPositionType(str, Enum):
    MELEE = "MELEE"
    RANGED = "RANGED"


class SPRecoveryMode(str, Enum):
    TIME = "TIME"
    ATTACK = "ATTACK"  # Generic one-SP-per-normal-attack recovery for next-attack skills.
    DEFENSE = "DEFENSE"  # Reserved only; not implemented in this synthetic milestone.


class CombatOutputType(str, Enum):
    DAMAGE = "DAMAGE"
    HEAL = "HEAL"


@dataclass(frozen=True)
class SkillEffect:
    """Small synthetic effect set; values are runtime modifiers, not GameData parsing."""

    atk_multiplier: float = 1.0
    atk_additive: float = 0.0
    attack_interval_multiplier: float = 1.0
    range_override: tuple[tuple[int, int], ...] | None = None
    range_add: tuple[tuple[int, int], ...] = ()
    block_count_delta: int = 0
    dp_immediate: float = 0.0
    defense_additive_ratio: float = 0.0
    attack_speed_additive: float = 0.0
    next_attack_atk_scale: float = 1.0
    next_attack_hit_count: int = 1
    range_forward_extend: int = 0
    base_attack_time_override: float | None = None
    immediate_self_heal_ratio: float = 0.0
    heal_mode: bool = False


@dataclass(frozen=True)
class SyntheticSkill:
    skill_id: str
    initial_sp: float
    sp_cost: float
    recovery_mode: SPRecoveryMode
    sp_per_second: float
    duration: float
    effect: SkillEffect
    auto_activate: bool = False
