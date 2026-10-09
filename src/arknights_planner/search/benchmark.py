"""Cardinality-first bounded team search, separate from timeline search.

It is intentionally simulator-agnostic: a stage becomes eligible only after a
compatibility policy provides a deterministic team->timeline evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Callable

from arknights_planner.benchmark.objective import StrategyObjective


class BenchmarkSearchStop(str, Enum):
    MINIMUM_SQUAD_WITHIN_BOUNDED_DOMAIN = "MINIMUM_SQUAD_WITHIN_BOUNDED_DOMAIN"
    LOWER_CARDINALITY_EXHAUSTED = "LOWER_CARDINALITY_EXHAUSTED"
    SEARCH_BUDGET_REACHED = "SEARCH_BUDGET_REACHED"
    NO_WIN_FOUND = "NO_WIN_FOUND"


@dataclass(frozen=True)
class TeamCandidate:
    operator_ids: tuple[str, ...]
    rarity_sum: int


@dataclass(frozen=True)
class BenchmarkSearchConfig:
    max_squad_size: int = 4
    max_teams: int = 100


@dataclass
class BenchmarkSearchMetrics:
    teams_generated: int = 0
    teams_pruned: int = 0
    teams_simulated: int = 0
    winning_teams: int = 0
    first_win_evaluation: int | None = None
    best_squad_size: int | None = None
    best_rarity_sum: int | None = None


@dataclass(frozen=True)
class BenchmarkSearchResult:
    best_team: TeamCandidate | None
    best_objective: StrategyObjective | None
    stop: BenchmarkSearchStop
    metrics: BenchmarkSearchMetrics


class SquadCardinalitySearch:
    """Enumerate small teams by count, then rarity; timeline search stays external."""

    def __init__(self, *, rarity_by_operator: dict[str, int], config: BenchmarkSearchConfig | None = None):
        self.rarity_by_operator = dict(rarity_by_operator)
        self.config = config or BenchmarkSearchConfig()

    def teams(self, size: int) -> tuple[TeamCandidate, ...]:
        candidates = [TeamCandidate(ids, sum(self.rarity_by_operator[item] for item in ids)) for ids in combinations(sorted(self.rarity_by_operator), size)]
        return tuple(sorted(candidates, key=lambda item: (item.rarity_sum, item.operator_ids)))

    def search(self, *, evaluate_team: Callable[[TeamCandidate], StrategyObjective | None], prune_team: Callable[[TeamCandidate], str | None] | None = None) -> BenchmarkSearchResult:
        metrics = BenchmarkSearchMetrics()
        evaluated = 0
        for size in range(1, min(self.config.max_squad_size, len(self.rarity_by_operator)) + 1):
            winning: list[tuple[TeamCandidate, StrategyObjective]] = []
            for team in self.teams(size):
                metrics.teams_generated += 1
                reason = prune_team(team) if prune_team else None
                if reason:
                    metrics.teams_pruned += 1
                    continue
                if evaluated >= self.config.max_teams:
                    return BenchmarkSearchResult(None, None, BenchmarkSearchStop.SEARCH_BUDGET_REACHED, metrics)
                objective = evaluate_team(team)
                evaluated += 1
                metrics.teams_simulated += 1
                if objective is not None and objective.win:
                    winning.append((team, objective))
                    metrics.winning_teams += 1
                    if metrics.first_win_evaluation is None:
                        metrics.first_win_evaluation = evaluated
            if winning:
                best_team, best_objective = min(winning, key=lambda item: item[1].lexicographic_key())
                metrics.best_squad_size = size
                metrics.best_rarity_sum = best_team.rarity_sum
                return BenchmarkSearchResult(best_team, best_objective, BenchmarkSearchStop.MINIMUM_SQUAD_WITHIN_BOUNDED_DOMAIN, metrics)
        return BenchmarkSearchResult(None, None, BenchmarkSearchStop.NO_WIN_FOUND, metrics)
