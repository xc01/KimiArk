from __future__ import annotations

from dataclasses import dataclass

from arknights_planner.models.simulation import SimulationResult
from arknights_planner.models.strategy import Strategy
from arknights_planner.simulator.simulator import SimulationConfig, Simulator


@dataclass(frozen=True)
class StrategyEvaluation:
    """Synthetic-only dense ranking data, deliberately separate from game rewards."""

    strategy: Strategy
    result: SimulationResult
    score: float
    complexity: int
    invalid_action_count: int


class SyntheticStrategyEvaluator:
    """Runs the current simulator and turns only its state/result into a dense score."""

    def __init__(self, *, simulator: Simulator, stage, operators, enemies, simulation_config: SimulationConfig):
        self.simulator = simulator
        self.stage = stage
        self.operators = operators
        self.enemies = enemies
        self.simulation_config = simulation_config

    def evaluate(self, strategy: Strategy) -> StrategyEvaluation:
        result = self.simulator.run(
            stage=self.stage, operators=self.operators, enemies=self.enemies,
            strategy=strategy, config=self.simulation_config,
        )
        complexity = len(strategy.actions)
        invalid = len(result.deployment_errors)
        # These weights only order synthetic candidates; they are not Arknights rewards.
        score = (
            (10_000.0 if result.win else 0.0)
            + result.remaining_life * 100.0
            + result.enemies_killed * 500.0
            - result.enemies_leaked * 1_500.0
            - result.enemies_remaining * 300.0
            - result.remaining_enemy_hp * 2.0
            - result.remaining_enemy_route_progress * 200.0
            - invalid * 1_000.0
            - complexity * 2.0
        )
        return StrategyEvaluation(strategy, result, score, complexity, invalid)
