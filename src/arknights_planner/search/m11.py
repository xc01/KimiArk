"""Bounded, cardinality-first approximate-real search for the M11 target.

This is intentionally a small bridge between the real-data fixture adapter and the
existing simulator.  It does not claim a global roster optimum: the bounded pool,
placement options, time grid and beam limits are all explicit in the result.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from fractions import Fraction
from itertools import combinations
from math import ceil
from time import perf_counter

from arknights_planner.adapters import (
    ApproximateRealFixture, ApproximateRealSimulationAdapter,
    RealExecutionMode, RealOperatorConfiguration, RealSimulationApproximationPolicy,
)
from arknights_planner.benchmark.objective import StrategyObjective, effective_operator_ids, objective_from_result
from arknights_planner.models.frame import FrameClock
from arknights_planner.models.simulation import SimulationResult, SimulationRunMetadata
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.models.timeline import FrameTimeline
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator
from arknights_planner.timing import strategy_to_timeline


class M11SearchStop(str, Enum):
    MINIMUM_SQUAD_WITHIN_BOUNDED_DOMAIN = "MINIMUM_SQUAD_WITHIN_BOUNDED_DOMAIN"
    BEST_FOUND_UNDER_BUDGET = "BEST_FOUND_UNDER_BUDGET"
    NO_WIN_FOUND = "NO_WIN_FOUND"


@dataclass(frozen=True)
class M11SearchConfig:
    frame_clock: FrameClock = FrameClock.configured(30, provenance="M11 configured approximate planner clock; client relation unresolved")
    coarse_deployment_frames: tuple[int, ...] = (0, 180, 360, 540)
    placement_options_per_operator: int = 2
    beam_width: int = 2
    max_squad_size: int = 3
    max_teams: int = 24
    refinement_frames: tuple[int, ...] = (-30, -10, -3, -1, 1, 3, 10, 30)
    simulation_config: SimulationConfig = SimulationConfig(dt=0.2, max_time=300.0)


@dataclass(frozen=True)
class M11DeploymentOption:
    operator_id: str
    tile: tuple[int, int]
    direction: str
    route_coverage: int


@dataclass(frozen=True)
class M11Evaluation:
    strategy: Strategy
    result: SimulationResult
    dense_rank: tuple


@dataclass
class M11SearchMetrics:
    teams_generated: int = 0
    teams_pruned: int = 0
    teams_simulated: int = 0
    strategies_generated: int = 0
    unique_simulations: int = 0
    cache_hits: int = 0
    winning_teams: int = 0
    first_win_evaluation: int | None = None
    refinement_simulations: int = 0
    wall_clock_seconds: float = 0.0


@dataclass(frozen=True)
class M11SearchResult:
    stage_id: str
    fixture: ApproximateRealFixture
    best: M11Evaluation | None
    objective: StrategyObjective | None
    timeline: FrameTimeline | None
    robustness_by_action: tuple[tuple[int, int, int, int], ...]
    lower_cardinalities_exhausted: bool
    lower_rarities_exhausted: bool
    stop: M11SearchStop
    metrics: M11SearchMetrics


class M11MinimumSquadSearch:
    """Search a preselected low-rarity pool one used-operator cardinality at a time."""

    VERSION = "m11-minimum-squad-search-v1"

    def __init__(
        self,
        *,
        adapter: ApproximateRealSimulationAdapter,
        stage_id_or_code: str,
        policy: RealSimulationApproximationPolicy,
        operator_pool: tuple[RealOperatorConfiguration, ...],
        config: M11SearchConfig | None = None,
    ):
        self.adapter = adapter
        self.policy = policy
        self.config = config or M11SearchConfig()
        self.operator_pool = tuple(sorted(operator_pool, key=lambda item: item.operator_id))
        self.fixture = adapter.build_pool_fixture(stage_id_or_code=stage_id_or_code, configurations=self.operator_pool, policy=policy)
        self.simulator = Simulator(range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel())
        self.rarity_by_operator = {
            item.operator_id: int(adapter.repository.get_operator(item.operator_id).star_rarity.value)
            for item in self.operator_pool
        }
        self._cache: dict[tuple, M11Evaluation] = {}
        self._options = self._build_options()

    @staticmethod
    def default_m11_pool() -> tuple[RealOperatorConfiguration, ...]:
        """Exact phase-0 level-40 keyframes selected for 7-4's bounded domain."""
        return (
            RealOperatorConfiguration("char_120_hibisc", 0, 40),  # healer, manual ATK skill
            RealOperatorConfiguration("char_122_beagle", 0, 40),  # blocker
            RealOperatorConfiguration("char_124_kroos", 0, 40),   # physical ranged DPS
            RealOperatorConfiguration("char_208_melan", 0, 40),   # melee DPS, manual ATK skill
        )

    def _route_cells(self) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        spawned_route_ids = {item.route_id for item in self.fixture.spawn_timeline}
        for route in self.fixture.stage.routes:
            if route.route_id not in spawned_route_ids:
                continue
            for first, second in zip(route.waypoints, route.waypoints[1:]):
                steps = max(1, ceil(max(abs(second.x - first.x), abs(second.y - first.y))))
                for step in range(steps + 1):
                    ratio = step / steps
                    cells.add((round(first.x + (second.x - first.x) * ratio), round(first.y + (second.y - first.y) * ratio)))
        return cells

    def _build_options(self) -> tuple[M11DeploymentOption, ...]:
        route_cells = self._route_cells()
        transformer = ApproximateRealRangeTransformer()
        grouped: dict[str, list[M11DeploymentOption]] = {}
        for operator_id, operator in self.fixture.operators.items():
            kind = "GROUND" if operator.position.value == "MELEE" else "HIGH_GROUND"
            for tile in self.fixture.stage.stage_map.tiles:
                if not tile.buildable or tile.tile_kind != kind:
                    continue
                for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                    coverage = transformer.covered_tiles(origin=(tile.x, tile.y), offsets=operator.attack_range, direction=direction)
                    score = len(coverage & route_cells)
                    if operator.position.value == "MELEE":
                        score += 100 * sum(
                            route.distance_at((tile.x, tile.y)) is not None
                            for route in self.fixture.stage.routes
                            if route.route_id in {entry.route_id for entry in self.fixture.spawn_timeline}
                        )
                    if score:
                        grouped.setdefault(operator_id, []).append(M11DeploymentOption(operator_id, (tile.x, tile.y), direction, score))
        options: list[M11DeploymentOption] = []
        for operator_id in sorted(grouped):
            options.extend(sorted(grouped[operator_id], key=lambda item: (-item.route_coverage, item.tile, item.direction))[:self.config.placement_options_per_operator])
        return tuple(options)

    def deployment_options(self) -> tuple[M11DeploymentOption, ...]:
        return self._options

    def evaluate(self, strategy: Strategy, metrics: M11SearchMetrics) -> M11Evaluation:
        """Evaluate one complete strategy for a caller-owned bounded search."""
        return self._evaluate(strategy, metrics)

    def _strategy_key(self, strategy: Strategy) -> tuple:
        return tuple((action.action_type.value, self.config.frame_clock.frame_for_seconds(action.time), action.operator_id, action.tile, action.direction) for action in strategy.actions)

    def _cache_key(self, strategy: Strategy) -> tuple:
        return (
            self.VERSION, self.fixture.stage.stage_id, self.policy.cache_identity,
            self.config.frame_clock.version, str(self.config.frame_clock.frames_per_second),
            self.config.simulation_config.dt, self.config.simulation_config.max_time,
            tuple((item.operator_id, item.phase_index, item.level, item.skill_level_index) for item in self.operator_pool),
            self._strategy_key(strategy),
        )

    @staticmethod
    def _dense_rank(result: SimulationResult, strategy: Strategy) -> tuple:
        """Only an internal beam ordering signal; final choice is lexicographic."""
        return (
            0 if result.win else 1,
            -result.remaining_life,
            result.enemies_leaked,
            result.enemies_remaining,
            result.remaining_enemy_hp,
            result.operator_deaths,
            len(strategy.actions),
            tuple((action.time, action.operator_id, action.tile, action.direction) for action in strategy.actions),
        )

    def _evaluate(self, strategy: Strategy, metrics: M11SearchMetrics) -> M11Evaluation:
        key = self._cache_key(strategy)
        if key in self._cache:
            metrics.cache_hits += 1
            return self._cache[key]
        result = self.simulator.run(
            stage=self.fixture.stage, operators=self.fixture.operators, enemies=self.fixture.enemies,
            strategy=strategy, config=self.config.simulation_config,
        )
        result = replace(result, run_metadata=SimulationRunMetadata(
            RealExecutionMode.APPROXIMATE_REAL.value, self.fixture.approximations_used,
            (self.fixture.stage.stage_id, *sorted(self.fixture.operators), *sorted(self.fixture.enemies)),
        ))
        evaluation = M11Evaluation(strategy, result, self._dense_rank(result, strategy))
        self._cache[key] = evaluation
        metrics.unique_simulations += 1
        if result.win and metrics.first_win_evaluation is None:
            metrics.first_win_evaluation = metrics.unique_simulations
        return evaluation

    def _deploy_extensions(self, partial: Strategy, team: tuple[str, ...]) -> tuple[Strategy, ...]:
        used_tiles = {action.tile for action in partial.actions if action.action_type is ActionType.DEPLOY}
        deployed = {action.operator_id for action in partial.actions if action.action_type is ActionType.DEPLOY}
        candidates: list[Strategy] = []
        for option in self._options:
            if option.operator_id not in team or option.operator_id in deployed or option.tile in used_tiles:
                continue
            cost = self.fixture.operators[option.operator_id].phases[0].stats_max.cost.value
            for frame in self.config.coarse_deployment_frames:
                time = float(self.config.frame_clock.seconds_for_frame(frame))
                if cost is not None and self.fixture.stage.initial_dp.value is not None and self.fixture.stage.initial_dp.value + self.fixture.stage.dp_per_second * time < float(cost):
                    continue
                action = Action(ActionType.DEPLOY, time, option.operator_id, option.tile, option.direction)
                actions = tuple(sorted((*partial.actions, action), key=lambda item: (item.time, item.operator_id)))
                candidates.append(Strategy(team, actions))
        return tuple(candidates)

    def _search_team(self, team: tuple[str, ...], metrics: M11SearchMetrics) -> tuple[M11Evaluation, ...]:
        frontier = (Strategy(team, ()),)
        all_evaluations: list[M11Evaluation] = []
        for _ in range(len(team)):
            generated = [candidate for partial in frontier for candidate in self._deploy_extensions(partial, team)]
            metrics.strategies_generated += len(generated)
            evaluations = [self._evaluate(candidate, metrics) for candidate in generated]
            all_evaluations.extend(evaluations)
            frontier = tuple(item.strategy for item in sorted(evaluations, key=lambda item: item.dense_rank)[:self.config.beam_width])
            if not frontier:
                break
        metrics.teams_simulated += 1
        return tuple(all_evaluations)

    def search_ordered_fixed_team(
        self,
        team: tuple[str, ...],
        deployment_order: tuple[str, ...],
        *,
        timing_offsets: tuple[int, ...] = (0, 90),
        robustness: bool = True,
    ) -> M11SearchResult:
        """Evaluate one hypothesis-conditioned team without cardinality search.

        This is intentionally diagnostic: it tests the exact team and declared
        order, but neither makes a minimum-squad claim nor enumerates other
        compositions.  Tiles and directions remain deterministic route-coverage
        choices from this searcher's canonical map geometry.
        """
        if set(team) != set(deployment_order) or len(team) != len(deployment_order):
            raise ValueError("deployment_order must contain every fixed-team operator exactly once")
        if any(operator_id not in self.fixture.operators for operator_id in team):
            raise ValueError("fixed team contains an operator outside this fixture")
        if not timing_offsets or any(offset < 0 for offset in timing_offsets):
            raise ValueError("timing_offsets must be non-empty non-negative frames")

        started = perf_counter()
        metrics = M11SearchMetrics(teams_generated=1)
        frontier = (Strategy(team, ()),)
        final: tuple[M11Evaluation, ...] = ()
        for operator_id in deployment_order:
            generated: list[Strategy] = []
            for partial in frontier:
                used_tiles = {action.tile for action in partial.actions if action.action_type is ActionType.DEPLOY}
                # Prefer distinct tiles.  Direction-only variants on one tile do
                # not repair a collision after the beam chooses that tile.
                options: list[M11DeploymentOption] = []
                seen_tiles: set[tuple[int, int]] = set()
                option_limit = max(1, min(3, self.config.placement_options_per_operator))
                for item in self._options:
                    if item.operator_id != operator_id or item.tile in used_tiles or item.tile in seen_tiles:
                        continue
                    options.append(item)
                    seen_tiles.add(item.tile)
                    if len(options) == option_limit:
                        break
                if not options:
                    continue
                spent = sum(float(self.fixture.operators[action.operator_id].phases[0].stats_max.cost.value or 0)
                            for action in partial.actions if action.action_type is ActionType.DEPLOY)
                cost = float(self.fixture.operators[operator_id].phases[0].stats_max.cost.value or 0)
                initial_dp = float(self.fixture.stage.initial_dp.value or 0)
                rate = float(self.fixture.stage.dp_per_second)
                needed_seconds = max(0.0, (spent + cost - initial_dp) / rate) if rate > 0 else 0.0
                earliest = ceil(needed_seconds * float(self.config.frame_clock.frames_per_second))
                if partial.actions:
                    earliest = max(earliest, self.config.frame_clock.frame_for_seconds(partial.actions[-1].time) + 1)
                for option in options:
                    for offset in timing_offsets:
                        frame = earliest + offset
                        action = Action(ActionType.DEPLOY, float(self.config.frame_clock.seconds_for_frame(frame)), operator_id, option.tile, option.direction)
                        generated.append(Strategy(team, (*partial.actions, action)))
            metrics.strategies_generated += len(generated)
            evaluated = tuple(self._evaluate(candidate, metrics) for candidate in generated)
            if not evaluated:
                frontier = ()
                break
            final = evaluated
            frontier = tuple(item.strategy for item in sorted(evaluated, key=lambda item: item.dense_rank)[:self.config.beam_width])
        metrics.teams_simulated = 1
        metrics.wall_clock_seconds = perf_counter() - started
        completed = tuple(item for item in final if len(item.strategy.actions) == len(team))
        best = min(completed, key=lambda item: item.dense_rank) if completed else None
        if best is None:
            return M11SearchResult(self.fixture.stage.stage_id, self.fixture, None, None, None, (), False, False, M11SearchStop.NO_WIN_FOUND, metrics)
        if not best.result.win:
            return M11SearchResult(self.fixture.stage.stage_id, self.fixture, best, None, None, (), False, False, M11SearchStop.NO_WIN_FOUND, metrics)
        if not robustness:
            objective = objective_from_result(strategy=best.strategy, result=best.result, rarity_by_operator=self.rarity_by_operator)
            timeline = strategy_to_timeline(best.strategy, stage_id=self.fixture.stage.stage_id, frame_clock=self.config.frame_clock, simulator_mode=RealExecutionMode.APPROXIMATE_REAL.value, approximation_policy_version="m11-second-quantized-v1")
            return M11SearchResult(self.fixture.stage.stage_id, self.fixture, best, objective, timeline, (), False, False, M11SearchStop.BEST_FOUND_UNDER_BUDGET, metrics)
        robustness = self._robustness(best, metrics)
        width = min((entry[3] for entry in robustness), default=0)
        objective = objective_from_result(strategy=best.strategy, result=best.result, rarity_by_operator=self.rarity_by_operator, robustness_window_width=width)
        timeline = strategy_to_timeline(best.strategy, stage_id=self.fixture.stage.stage_id, frame_clock=self.config.frame_clock, simulator_mode=RealExecutionMode.APPROXIMATE_REAL.value, approximation_policy_version="m11-second-quantized-v1")
        return M11SearchResult(self.fixture.stage.stage_id, self.fixture, best, objective, timeline, robustness, False, False, M11SearchStop.BEST_FOUND_UNDER_BUDGET, metrics)

    def _robustness(self, evaluation: M11Evaluation, metrics: M11SearchMetrics) -> tuple[tuple[int, int, int, int], ...]:
        windows: list[tuple[int, int, int, int]] = []
        for index, action in enumerate(evaluation.strategy.actions):
            center = self.config.frame_clock.frame_for_seconds(action.time)
            wins: list[int] = []
            for delta in self.config.refinement_frames:
                frame = max(0, center + delta)
                actions = list(evaluation.strategy.actions)
                actions[index] = replace(action, time=self.config.frame_clock.seconds_for_frame(frame))
                candidate = self._evaluate(Strategy(evaluation.strategy.team, tuple(actions)), metrics)
                metrics.refinement_simulations += 1
                if candidate.result.win:
                    wins.append(frame)
            if evaluation.result.win:
                wins.append(center)
            windows.append((center, min(wins) if wins else center, max(wins) if wins else center, len(set(wins))))
        return tuple(windows)

    def search(self) -> M11SearchResult:
        started = perf_counter()
        metrics = M11SearchMetrics()
        best: M11Evaluation | None = None
        best_objective: StrategyObjective | None = None
        lower_exhausted = True
        lower_rarity_exhausted = False
        pool_ids = tuple(item.operator_id for item in self.operator_pool)
        for cardinality in range(1, min(self.config.max_squad_size, len(pool_ids)) + 1):
            teams = tuple(combinations(pool_ids, cardinality))
            if len(teams) > self.config.max_teams:
                teams = teams[:self.config.max_teams]
                lower_exhausted = False
            metrics.teams_generated += len(teams)
            wins: list[M11Evaluation] = []
            for team in teams:
                evaluations = self._search_team(team, metrics)
                if evaluations:
                    candidate = min(evaluations, key=lambda item: item.dense_rank)
                    if best is None or candidate.dense_rank < best.dense_rank:
                        best = candidate
                team_wins = [item for item in evaluations if item.result.win and len(effective_operator_ids(item.strategy)) == cardinality]
                if team_wins:
                    metrics.winning_teams += 1
                    wins.extend(team_wins)
            if wins:
                # Team order is already rarity-agnostic.  Evaluate all generated
                # winning candidates at this cardinality by the hard objective.
                enriched: list[tuple[StrategyObjective, M11Evaluation]] = []
                for item in wins:
                    enriched.append((objective_from_result(strategy=item.strategy, result=item.result, rarity_by_operator=self.rarity_by_operator), item))
                enriched.sort(key=lambda item: (item[0].lexicographic_key(), item[1].dense_rank))
                best_objective, best = enriched[0]
                # A beam limits spatial/timing candidates, so no global rarity
                # claim is made unless future exhaustive bounds are substituted.
                lower_rarity_exhausted = False
                break
            # At cardinality two and above a beam intentionally prunes timeline
            # prefixes.  It remains useful search, but cannot certify exhaustive
            # lower-cardinality feasibility in the bounded spatial/time domain.
            if cardinality >= 2:
                lower_exhausted = False
        metrics.wall_clock_seconds = perf_counter() - started
        if best is None:
            return M11SearchResult(self.fixture.stage.stage_id, self.fixture, None, None, None, (), lower_exhausted, False, M11SearchStop.NO_WIN_FOUND, metrics)
        if not best.result.win:
            return M11SearchResult(self.fixture.stage.stage_id, self.fixture, best, None, None, (), lower_exhausted, False, M11SearchStop.NO_WIN_FOUND, metrics)
        robustness = self._robustness(best, metrics)
        width = min((entry[3] for entry in robustness), default=0)
        best_objective = objective_from_result(strategy=best.strategy, result=best.result, rarity_by_operator=self.rarity_by_operator, robustness_window_width=width)
        timeline = strategy_to_timeline(best.strategy, stage_id=self.fixture.stage.stage_id, frame_clock=self.config.frame_clock, simulator_mode=RealExecutionMode.APPROXIMATE_REAL.value, approximation_policy_version="m11-second-quantized-v1")
        stop = M11SearchStop.MINIMUM_SQUAD_WITHIN_BOUNDED_DOMAIN if lower_exhausted else M11SearchStop.BEST_FOUND_UNDER_BUDGET
        return M11SearchResult(self.fixture.stage.stage_id, self.fixture, best, best_objective, timeline, robustness, lower_exhausted, lower_rarity_exhausted, stop, metrics)
