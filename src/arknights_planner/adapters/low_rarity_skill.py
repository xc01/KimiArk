"""Bounded source-backed low-rarity skill interpretation for M10.

This is intentionally not a general blackboard interpreter. It recognizes a small,
source-backed family of low-rarity time-SP patterns and explicitly reports every
other pattern as unsupported.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from arknights_planner.models.runtime import SPRecoveryMode, SkillEffect, SyntheticSkill
from arknights_planner.models.skill import SkillLevel


class RealSkillSupport(str, Enum):
    EXECUTABLE_APPROXIMATED = "EXECUTABLE_APPROXIMATED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class InterpretedLowRaritySkill:
    skill_id: str
    support: RealSkillSupport
    reason: str
    executable_effect: SyntheticSkill | None
    source_pattern: tuple[tuple[str, float | int | str | None], ...]


class LowRarityBlackboardEffectInterpreter:
    """Interpret three bounded source-backed low-rarity skill families.

    `atk: x` maps to `1 + x` in the existing synthetic attack runtime.  A source
    description that says it immediately gains deployment cost maps `cost: x` to an
    immediate DP change at activation.  Those mappings retain their source pattern;
    no other Blackboard keys acquire implicit semantics.
    """

    version = "low-rarity-blackboard-v3-generic-operator"

    def interpret(self, skill_id: str, level: SkillLevel) -> InterpretedLowRaritySkill:
        pattern = level.blackboard
        values = dict(pattern)
        if (level.skill_type.value == "AUTO" and level.sp_type.value == "INCREASE_WHEN_ATTACK"
                and float(level.duration.value or 0.0) == 0.0 and set(values) <= {"atk_scale", "times"}
                and isinstance(values.get("atk_scale"), (int, float))
                and (values.get("times") is None or isinstance(values.get("times"), (int, float)))):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.ATTACK, sp_per_second=0.0, duration=0.0,
                effect=SkillEffect(next_attack_atk_scale=float(values["atk_scale"]), next_attack_hit_count=int(float(values.get("times", 1.0)))),
                auto_activate=True,
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "attack-SP next-attack scaled-hit pattern", effect, pattern)
        time_sp = (
            level.sp_type.value == "INCREASE_WITH_TIME",
            level.initial_sp.value is not None,
            level.sp_cost.value is not None,
        )
        if not all(time_sp):
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.UNSUPPORTED, "outside bounded time-SP low-rarity skill families", None, pattern)
        numeric = lambda key: isinstance(values.get(key), (int, float))
        manual_duration = level.skill_type.value == "MANUAL" and level.duration.value is not None and float(level.duration.value) > 0
        if manual_duration and set(values) == {"atk"} and numeric("atk"):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=float(level.duration.value),
                effect=SkillEffect(atk_multiplier=1.0 + float(values["atk"])),
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "manual time-SP finite atk pattern; synthetic ATK multiplier mapping", effect, pattern)
        if manual_duration and set(values) == {"def"} and numeric("def"):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=float(level.duration.value),
                effect=SkillEffect(defense_additive_ratio=float(values["def"])),
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "manual time-SP finite defense-buff pattern", effect, pattern)
        if manual_duration and set(values) == {"attack_speed"} and numeric("attack_speed"):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=float(level.duration.value),
                effect=SkillEffect(attack_speed_additive=float(values["attack_speed"])),
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "manual time-SP finite ASPD-additive pattern", effect, pattern)
        if manual_duration and set(values) == {"atk", "attack_speed"} and numeric("atk") and numeric("attack_speed"):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=float(level.duration.value),
                effect=SkillEffect(atk_multiplier=1.0 + float(values["atk"]), attack_speed_additive=float(values["attack_speed"])),
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "manual time-SP finite ATK and ASPD-additive pattern", effect, pattern)
        if manual_duration and set(values) == {"atk", "ability_range_forward_extend"} and numeric("atk") and numeric("ability_range_forward_extend"):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=float(level.duration.value),
                effect=SkillEffect(atk_multiplier=1.0 + float(values["atk"]), range_forward_extend=int(float(values["ability_range_forward_extend"]))),
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "manual time-SP finite ATK and forward-range-extend pattern", effect, pattern)
        if manual_duration and set(values) == {"cost", "atk"} and numeric("cost") and numeric("atk"):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=float(level.duration.value),
                effect=SkillEffect(atk_multiplier=1.0 + float(values["atk"]), dp_immediate=float(values["cost"])),
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "manual time-SP finite atk + immediate DP pattern; synthetic ATK mapping", effect, pattern)
        if (level.skill_type.value == "MANUAL" and float(level.duration.value or 0.0) == 0.0
                and set(values) == {"heal_scale"} and numeric("heal_scale")):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=0.0,
                effect=SkillEffect(immediate_self_heal_ratio=float(values["heal_scale"])),
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "manual time-SP immediate max-HP self-heal pattern", effect, pattern)
        if manual_duration and set(values) == {"atk", "base_attack_time"} and numeric("atk") and numeric("base_attack_time"):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=float(level.duration.value),
                effect=SkillEffect(atk_multiplier=1.0 + float(values["atk"]), base_attack_time_override=float(values["base_attack_time"]), heal_mode=True),
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "manual time-SP heal-mode pattern with explicit base-healing interval", effect, pattern)
        if (level.skill_type.value == "AUTO" and float(level.duration.value or 0.0) == 0.0
                and set(values) == {"cost"} and numeric("cost")):
            effect = SyntheticSkill(
                skill_id=skill_id, initial_sp=float(level.initial_sp.value), sp_cost=float(level.sp_cost.value),
                recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0, duration=0.0,
                effect=SkillEffect(dp_immediate=float(values["cost"])), auto_activate=True,
            )
            return InterpretedLowRaritySkill(skill_id, RealSkillSupport.EXECUTABLE_APPROXIMATED, "automatic time-SP instant DP pattern", effect, pattern)
        return InterpretedLowRaritySkill(skill_id, RealSkillSupport.UNSUPPORTED, "outside bounded manual/automatic time-SP atk-or-DP patterns", None, pattern)
