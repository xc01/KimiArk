"""Source-backed foundational combat formulas from the local PRTS snapshot.

The source copy is ``data/prts/game-data-basics.html`` and
``data/prts/battle-mechanics.html``.  These helpers intentionally implement
only the deterministic formula layer; modifier/伤判 effects remain separate
runtime work and are not silently approximated here.
"""
from __future__ import annotations

from dataclasses import dataclass


PRTS_GAME_DATA_SOURCE = "data/prts/game-data-basics.html#伤害公式"
PRTS_BATTLE_SOURCE = "data/prts/battle-mechanics.html#伤害及其处理"


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def physical_damage(base_damage: float, defense: float, *, penetration_ratio: float = 0.0,
                    penetration_flat: float = 0.0) -> float:
    """PRTS physical formula: max(0.05A, A-(1-Ip)max(0,D-Iv))."""
    return max(0.05 * base_damage, base_damage - (1.0 - penetration_ratio) * max(0.0, defense - penetration_flat))


def arts_damage(base_damage: float, resistance: float, *, penetration_ratio: float = 0.0,
                penetration_flat: float = 0.0) -> float:
    """PRTS Arts formula, including its 5% minimum."""
    return max(0.05 * base_damage, 0.01 * base_damage * max(0.0, 100.0 - (1.0 - penetration_ratio) * max(0.0, resistance - penetration_flat)))


def elemental_damage(base_damage: float, resistance: float) -> float:
    return max(0.05 * base_damage, 0.01 * base_damage * max(0.0, 100.0 - resistance))


def true_damage(base_damage: float) -> float:
    return base_damage


def healing_amount(base_damage: float) -> float:
    return base_damage


def attack_interval(theoretical_interval: float, attack_speed: float = 100.0) -> float:
    """PRTS T=T0/(clamp(S,10,600)/100); S's attribute lower bound is 20."""
    return theoretical_interval / (clamp(attack_speed, 10.0, 600.0) / 100.0)


@dataclass(frozen=True)
class ModifierPipeline:
    """Four-stage PRTS attribute modifier aggregation."""
    direct_add: float = 0.0
    direct_multiplier_add: float = 0.0
    final_add: float = 0.0
    final_multiplier: float = 1.0

    def apply(self, base: float) -> float:
        final_multiplier = self.final_multiplier
        if final_multiplier < 0:
            final_multiplier += 1.0
        direct_multiplier = max(0.0, 1.0 + self.direct_multiplier_add)
        return (base + self.direct_add) * direct_multiplier * final_multiplier + self.final_add * final_multiplier
