"""Hard-feasibility, lexicographic benchmark objective. Never scalar reward weights."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from arknights_planner.models.simulation import SimulationResult
from arknights_planner.models.strategy import Strategy


def effective_operator_ids(strategy: Strategy) -> tuple[str, ...]:
    """Distinct operators actually named by emitted external actions."""
    return tuple(sorted({action.operator_id for action in strategy.actions}))


@dataclass(frozen=True)
class StrategyObjective:
    """A winning strategy is always ordered ahead of every non-winning strategy."""

    win: bool
    unique_operator_count: int
    total_operator_rarity: int
    timing_fragility: Fraction
    external_action_count: int
    battle_duration: float

    def lexicographic_key(self) -> tuple:
        # `timing_fragility` is the inverse local robustness window width: smaller
        # means less fragile. Losses remain after all wins independent of fields.
        return (0 if self.win else 1, self.unique_operator_count, self.total_operator_rarity, self.timing_fragility, self.external_action_count, self.battle_duration)


def compare_strategies(left: StrategyObjective, right: StrategyObjective) -> int:
    """Return -1 when left is preferred, 0 for equality, +1 when right is preferred."""
    return (left.lexicographic_key() > right.lexicographic_key()) - (left.lexicographic_key() < right.lexicographic_key())


def objective_from_result(*, strategy: Strategy, result: SimulationResult, rarity_by_operator: dict[str, int], robustness_window_width: int = 0) -> StrategyObjective:
    used = effective_operator_ids(strategy)
    if any(operator_id not in rarity_by_operator for operator_id in used):
        missing = sorted(set(used) - set(rarity_by_operator))
        raise ValueError(f"missing GameData rarity for used operators: {missing}")
    # A wider local all-win interval has lower fragility. Zero means no evidence
    # was measured and is deliberately treated as maximally fragile.
    fragility = Fraction(1, max(1, robustness_window_width))
    return StrategyObjective(
        result.win, len(used), sum(rarity_by_operator[item] for item in used),
        fragility, len(strategy.actions), result.time_survived,
    )
