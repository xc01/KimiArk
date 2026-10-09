from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from time import perf_counter

from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator.simulator import SimulationConfig, Simulator

from .evaluation import StrategyEvaluation, SyntheticStrategyEvaluator


@dataclass(frozen=True)
class SearchConfig:
    seed: int = 0  # Recorded for reproducibility; this bounded search is non-random.
    beam_width: int = 8
    max_depth: int = 2
    coarse_times: tuple[float, ...] = (0.0, 0.5, 1.0)
    refine_timing: bool = True
    refinement_deltas: tuple[float, ...] = (-0.2, -0.1, 0.1, 0.2)
    simulation_config: SimulationConfig = SimulationConfig()


@dataclass
class SearchMetrics:
    candidates_generated: int = 0
    simulations_evaluated: int = 0
    winning_candidates: int = 0
    simulations_to_first_win: int | None = None
    best_score: float = float("-inf")
    search_depth: int = 0
    iterations: int = 0
    wall_clock_seconds: float = 0.0


@dataclass(frozen=True)
class SearchResult:
    best: StrategyEvaluation
    ranked: tuple[StrategyEvaluation, ...]
    metrics: SearchMetrics


class BeamSearch:
    """Transparent, small-space synthetic deployment search with optional timing polish."""

    def __init__(self, *, stage, operators, enemies, config: SearchConfig | None = None):
        self.stage = stage
        self.operators = operators
        self.enemies = enemies
        self.config = config or SearchConfig()
        self.evaluator = SyntheticStrategyEvaluator(
            simulator=Simulator(), stage=stage, operators=operators, enemies=enemies,
            simulation_config=self.config.simulation_config,
        )
        self._cache: dict[tuple, StrategyEvaluation] = {}

    @staticmethod
    def _key(strategy: Strategy) -> tuple:
        return tuple((action.action_type.value, action.time, action.operator_id, action.tile, action.direction) for action in strategy.actions)

    @staticmethod
    def _rank_key(evaluation: StrategyEvaluation) -> tuple:
        return (-evaluation.score, evaluation.complexity, BeamSearch._key(evaluation.strategy))

    def _options(self) -> tuple[tuple[str, tuple[int, int], str], ...]:
        """Bounded, synthetic-1-only placements and facings; no real map inference."""
        return (
            *(('guard', tile, direction) for tile, direction in product(((2, 1), (3, 1), (4, 1)), ('RIGHT', 'LEFT'))),
            *(('archer', tile, direction) for tile, direction in product(((0, 2), (1, 2), (2, 2)), ('UP', 'DOWN'))),
            *(('rookie', tile, direction) for tile, direction in product(((2, 1), (3, 1)), ('RIGHT', 'LEFT'))),
        )

    def _evaluate(self, strategy: Strategy, metrics: SearchMetrics) -> StrategyEvaluation:
        key = self._key(strategy)
        if key not in self._cache:
            self._cache[key] = self.evaluator.evaluate(strategy)
            metrics.simulations_evaluated += 1
            if self._cache[key].result.win:
                metrics.winning_candidates += 1
                if metrics.simulations_to_first_win is None:
                    metrics.simulations_to_first_win = metrics.simulations_evaluated
        evaluation = self._cache[key]
        metrics.best_score = max(metrics.best_score, evaluation.score)
        return evaluation

    def generate_candidates(self, partial: Strategy) -> tuple[Strategy, ...]:
        used = set(partial.team)
        candidates: list[Strategy] = []
        for operator_id, tile, direction in self._options():
            if operator_id in used:
                continue
            for time in self.config.coarse_times:
                action = Action(ActionType.DEPLOY, time, operator_id, tile, direction)
                candidates.append(Strategy(partial.team + (operator_id,), partial.actions + (action,)))
        return tuple(candidates)

    def _refine(self, current: StrategyEvaluation, metrics: SearchMetrics) -> StrategyEvaluation:
        """Greedily try a deterministic ±0.1/0.2 s neighborhood without regression."""
        best = current
        for index, action in enumerate(current.strategy.actions):
            for delta in self.config.refinement_deltas:
                refined_time = round(max(0.0, action.time + delta), 10)
                if refined_time == action.time:
                    continue
                actions = list(best.strategy.actions)
                actions[index] = Action(action.action_type, refined_time, action.operator_id, action.tile, action.direction)
                candidate = Strategy(best.strategy.team, tuple(actions))
                evaluation = self._evaluate(candidate, metrics)
                if self._rank_key(evaluation) < self._rank_key(best):
                    best = evaluation
        return best

    def search(self) -> SearchResult:
        started = perf_counter()
        metrics = SearchMetrics()
        frontier = (Strategy((), ()),)
        all_ranked: list[StrategyEvaluation] = []
        for depth in range(1, self.config.max_depth + 1):
            generated = [candidate for partial in frontier for candidate in self.generate_candidates(partial)]
            metrics.candidates_generated += len(generated)
            evaluations = [self._evaluate(candidate, metrics) for candidate in generated]
            evaluations.sort(key=self._rank_key)
            all_ranked.extend(evaluations)
            frontier = tuple(evaluation.strategy for evaluation in evaluations[:self.config.beam_width])
            metrics.search_depth = depth
            metrics.iterations += 1
            if not frontier:
                break
        ranked_map = {self._key(item.strategy): item for item in all_ranked}
        ranked = sorted(ranked_map.values(), key=self._rank_key)
        if not ranked:
            raise RuntimeError("Synthetic search generated no candidates")
        best = ranked[0]
        if self.config.refine_timing:
            best = self._refine(best, metrics)
            ranked_map[self._key(best.strategy)] = best
            ranked = sorted(ranked_map.values(), key=self._rank_key)
        metrics.best_score = best.score
        metrics.wall_clock_seconds = perf_counter() - started
        return SearchResult(best, tuple(ranked), metrics)
