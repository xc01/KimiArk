"""Small, deterministic deployment-only search over the explicit 0-1 approximation."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from math import ceil
from time import perf_counter

from arknights_planner.adapters import (
    ApproximateRealFixture, ApproximateRealSimulationAdapter, RealExecutionMode,
    RealOperatorConfiguration, RealSimulationApproximationPolicy,
)
from arknights_planner.models.simulation import EventType, SimulationResult, SimulationRunMetadata
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.models.frame import FrameClock
from arknights_planner.models.timeline import FrameTimeline
from arknights_planner.timing import strategy_to_timeline
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator


@dataclass(frozen=True)
class RealSearchConfig:
    beam_width: int = 8
    max_depth: int = 2
    coarse_times: tuple[float, ...] = (0.0, 4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0)
    placements_per_operator: int = 4
    refine_timing: bool = True
    refinement_deltas: tuple[float, ...] = (-1.0, 1.0)
    simulation_config: SimulationConfig = SimulationConfig(dt=0.1, max_time=90.0)
    frame_clock: FrameClock = FrameClock.configured(30, provenance="M9 explicit approximate planner clock; client relation unresolved")
    coarse_frames: tuple[int, ...] = (0, 120, 240, 360, 480, 600, 720, 840)
    refinement_frame_deltas: tuple[int, ...] = (-30, 30)
    refinement_levels: tuple[int, ...] = (30, 10, 3, 1)


@dataclass(frozen=True)
class RealDeploymentOption:
    operator_id: str
    tile: tuple[int, int]
    direction: str
    route_coverage: int


@dataclass(frozen=True)
class RealStrategyEvaluation:
    strategy: Strategy
    result: SimulationResult
    score: float
    invalid_action_count: int
    complexity: int


class RealFailureCategory(str, Enum):
    INSUFFICIENT_DP = "INSUFFICIENT_DP"
    ILLEGAL_DEPLOYMENT = "ILLEGAL_DEPLOYMENT"
    DEPLOYMENT_LIMIT_REACHED = "DEPLOYMENT_LIMIT_REACHED"
    DEFENSE_ESTABLISHED_TOO_LATE = "DEFENSE_ESTABLISHED_TOO_LATE"
    INSUFFICIENT_DAMAGE = "INSUFFICIENT_DAMAGE"
    POOR_TILE_COVERAGE = "POOR_TILE_COVERAGE"
    OPERATOR_DEATH = "OPERATOR_DEATH"
    LEAK_BEFORE_DEPLOYMENT = "LEAK_BEFORE_DEPLOYMENT"
    EXCESS_UNUSED_DEPLOYMENT_CAPACITY = "EXCESS_UNUSED_DEPLOYMENT_CAPACITY"


@dataclass(frozen=True)
class RealFailureAnalysis:
    categories: tuple[RealFailureCategory, ...]
    reasons: tuple[str, ...]


def analyze_real_failure(evaluation: RealStrategyEvaluation) -> RealFailureAnalysis:
    """Diagnose only result/event facts; no hidden real-game interpretation."""
    result = evaluation.result
    errors = "\n".join(result.deployment_errors)
    findings: list[tuple[RealFailureCategory, str]] = []
    if "insufficient DP" in errors:
        findings.append((RealFailureCategory.INSUFFICIENT_DP, "a deployment was rejected for insufficient DP"))
    if "deployment limit reached" in errors:
        findings.append((RealFailureCategory.DEPLOYMENT_LIMIT_REACHED, "a deployment exceeded the stage limit"))
    if any(text in errors for text in ("tile is not buildable", "tile is occupied", "unknown operator", "not in strategy team", "already deployed")):
        findings.append((RealFailureCategory.ILLEGAL_DEPLOYMENT, "a deployment action was illegal"))
    leaks = [event for event in result.events if event.event_type is EventType.ENEMY_LEAK]
    spawns = [event for event in result.events if event.event_type is EventType.SPAWN]
    deploys = [event for event in result.events if event.event_type is EventType.DEPLOY and ("legal", True) in event.details]
    attacks = [event for event in result.events if event.event_type is EventType.ATTACK_START]
    if leaks and not deploys:
        findings.append((RealFailureCategory.LEAK_BEFORE_DEPLOYMENT, "an enemy leaked without a legal deployment"))
    if leaks and deploys and spawns and deploys[0].time > spawns[0].time:
        findings.append((RealFailureCategory.DEFENSE_ESTABLISHED_TOO_LATE, "first legal deployment followed the first spawn"))
    if leaks and attacks:
        findings.append((RealFailureCategory.INSUFFICIENT_DAMAGE, "attacks occurred but at least one enemy leaked"))
    if leaks and not attacks:
        findings.append((RealFailureCategory.POOR_TILE_COVERAGE, "no attacks were emitted before a leak"))
    if result.operator_deaths:
        findings.append((RealFailureCategory.OPERATOR_DEATH, "one or more deployed operators died"))
    if not result.win and not deploys and result.remaining_life > 0:
        findings.append((RealFailureCategory.EXCESS_UNUSED_DEPLOYMENT_CAPACITY, "life remained while deployment capacity was unused"))
    return RealFailureAnalysis(tuple(category for category, _ in findings), tuple(reason for _, reason in findings))


@dataclass
class RealSearchMetrics:
    candidates_generated: int = 0
    simulations_evaluated: int = 0
    unique_simulations: int = 0
    cache_hits: int = 0
    winning_candidates: int = 0
    simulations_to_first_win: int | None = None
    search_depth: int = 0
    local_refinements: int = 0
    best_score: float = float("-inf")
    wall_clock_seconds: float = 0.0


@dataclass(frozen=True)
class RealSearchResult:
    best: RealStrategyEvaluation
    ranked: tuple[RealStrategyEvaluation, ...]
    metrics: RealSearchMetrics
    fixture: ApproximateRealFixture
    timeline: FrameTimeline | None = None
    robustness_frames: tuple[int, ...] = ()


class ApproximateRealBeamSearch:
    """Staged beam search for fixed exact-keyframe operators on approximate 0-1."""

    def __init__(
        self,
        *,
        adapter: ApproximateRealSimulationAdapter,
        policy: RealSimulationApproximationPolicy,
        operator_pool: tuple[RealOperatorConfiguration, ...] | None = None,
        config: RealSearchConfig | None = None,
    ):
        self.adapter = adapter
        self.policy = policy
        self.operator_pool = operator_pool or adapter.default_main_00_01_search_pool()
        self.config = config or RealSearchConfig()
        self.fixture = adapter.build_pool_fixture(stage_id_or_code="0-1", configurations=self.operator_pool, policy=policy)
        self.simulator = Simulator(range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel())
        self._cache: dict[tuple, RealStrategyEvaluation] = {}
        self._options = self._build_options()

    @staticmethod
    def _strategy_key(strategy: Strategy) -> tuple:
        # Runtime executes actions in timestamp order while preserving authored order
        # for ties. Canonicalize non-tied sequences so equivalent candidates share a
        # simulation cache entry without changing same-timestamp semantics.
        ordered_actions = sorted(enumerate(strategy.actions), key=lambda item: (round(item[1].time, 10), item[0]))
        return (
            tuple(sorted(strategy.team)),
            tuple(
                (action.action_type.value, round(action.time, 10), action.operator_id, action.tile, action.direction)
                for _, action in ordered_actions
            ),
        )

    def _cache_key(self, strategy: Strategy) -> tuple:
        return (
            "approximate-real-search-v1", self.fixture.stage.stage_id, self.policy.cache_identity,
            self.config.frame_clock.version, self.config.frame_clock.kind.value,
            str(self.config.frame_clock.frames_per_second) if self.config.frame_clock.frames_per_second else None,
            tuple((item.operator_id, item.phase_index, item.level) for item in self.operator_pool),
            self.config.simulation_config.dt, self.config.simulation_config.max_time,
            self._strategy_key(strategy),
        )

    @staticmethod
    def _rank_key(evaluation: RealStrategyEvaluation) -> tuple:
        return (-evaluation.score, evaluation.complexity, ApproximateRealBeamSearch._strategy_key(evaluation.strategy))

    def _route_tiles(self) -> set[tuple[int, int]]:
        active_route_ids = {item.route_id for item in self.fixture.spawn_timeline}
        cells: set[tuple[int, int]] = set()
        for route in self.fixture.stage.routes:
            if route.route_id not in active_route_ids:
                continue
            for first, second in zip(route.waypoints, route.waypoints[1:]):
                steps = max(1, ceil(max(abs(second.x - first.x), abs(second.y - first.y))))
                for step in range(steps + 1):
                    ratio = step / steps
                    cells.add((round(first.x + (second.x - first.x) * ratio), round(first.y + (second.y - first.y) * ratio)))
        return cells

    def _build_options(self) -> tuple[RealDeploymentOption, ...]:
        route_tiles = self._route_tiles()
        transformer = ApproximateRealRangeTransformer()
        options: list[RealDeploymentOption] = []
        by_operator: dict[str, list[RealDeploymentOption]] = {}
        for operator_id, operator in self.fixture.operators.items():
            needed_kind = "GROUND" if operator.position.value == "MELEE" else "HIGH_GROUND"
            for tile in self.fixture.stage.stage_map.tiles:
                if not tile.buildable or tile.tile_kind != needed_kind:
                    continue
                for direction in ("RIGHT", "DOWN", "LEFT", "UP"):
                    coverage = transformer.covered_tiles(origin=(tile.x, tile.y), offsets=operator.attack_range, direction=direction)
                    route_coverage = len(coverage & route_tiles)
                    if operator.position.value == "MELEE":
                        on_route = any(route.distance_at((tile.x, tile.y)) is not None for route in self.fixture.stage.routes if route.route_id in {item.route_id for item in self.fixture.spawn_timeline})
                        if not on_route:
                            continue
                    if route_coverage:
                        by_operator.setdefault(operator_id, []).append(RealDeploymentOption(operator_id, (tile.x, tile.y), direction, route_coverage))
        for operator_id in sorted(by_operator):
            ranked = sorted(by_operator[operator_id], key=lambda item: (-item.route_coverage, item.tile, item.direction))
            options.extend(ranked[:self.config.placements_per_operator])
        return tuple(options)

    def deployment_options(self) -> tuple[RealDeploymentOption, ...]:
        return self._options

    def timing_candidates(self) -> tuple[float, ...]:
        if self.config.coarse_frames:
            return tuple(float(self.config.frame_clock.seconds_for_frame(frame)) for frame in self.config.coarse_frames)
        return self.config.coarse_times

    def timing_frame_candidates(self) -> tuple[int, ...]:
        if self.config.coarse_frames:
            return self.config.coarse_frames
        return tuple(self.config.frame_clock.frame_for_seconds(time) for time in self.config.coarse_times)

    def _evaluate(self, strategy: Strategy, metrics: RealSearchMetrics) -> RealStrategyEvaluation:
        key = self._cache_key(strategy)
        if key in self._cache:
            metrics.cache_hits += 1
            evaluation = self._cache[key]
        else:
            result = self.simulator.run(
                stage=self.fixture.stage, operators=self.fixture.operators, enemies=self.fixture.enemies,
                strategy=strategy, config=self.config.simulation_config,
            )
            result = replace(result, run_metadata=SimulationRunMetadata(
                RealExecutionMode.APPROXIMATE_REAL.value,
                self.fixture.approximations_used,
                (self.fixture.stage.stage_id, *sorted(self.fixture.operators), *sorted(self.fixture.enemies)),
            ))
            invalid = len(result.deployment_errors)
            complexity = len(strategy.actions)
            # These are search-order weights only, not Arknights utility semantics.
            score = (
                (100_000.0 if result.win else 0.0)
                + result.remaining_life * 1_000.0
                + result.enemies_killed * 1_000.0
                - result.enemies_leaked * 8_000.0
                - result.enemies_remaining * 2_000.0
                - result.remaining_enemy_hp * 5.0
                - result.remaining_enemy_route_progress * 1_000.0
                - invalid * 15_000.0
                - result.operator_deaths * 3_000.0
                - complexity * 10.0
                - result.time_survived * 0.1
            )
            evaluation = RealStrategyEvaluation(strategy, result, score, invalid, complexity)
            self._cache[key] = evaluation
            metrics.simulations_evaluated += 1
            metrics.unique_simulations += 1
            if result.win:
                metrics.winning_candidates += 1
                if metrics.simulations_to_first_win is None:
                    metrics.simulations_to_first_win = metrics.simulations_evaluated
        metrics.best_score = max(metrics.best_score, evaluation.score)
        return evaluation

    def generate_candidates(self, partial: Strategy) -> tuple[Strategy, ...]:
        used = set(partial.team)
        used_tiles = {action.tile for action in partial.actions if action.action_type is ActionType.DEPLOY}
        candidates: list[Strategy] = []
        for option in self._options:
            if option.operator_id in used or option.tile in used_tiles:
                continue
            operator = self.fixture.operators[option.operator_id]
            cost = operator.phases[0].stats_max.cost.value
            for time in self.config.coarse_times:
                # A conservative individual-cost check prunes obvious no-DP starts;
                # multi-deploy DP validity remains simulator-evaluated.
                if cost is not None and self.fixture.stage.initial_dp.value is not None:
                    if self.fixture.stage.initial_dp.value + self.fixture.stage.dp_per_second * time < cost:
                        continue
                action = Action(ActionType.DEPLOY, time, option.operator_id, option.tile, option.direction)
                candidates.append(Strategy(partial.team + (option.operator_id,), partial.actions + (action,)))
        return tuple(candidates)

    def _refine(self, best: RealStrategyEvaluation, metrics: RealSearchMetrics) -> RealStrategyEvaluation:
        current = best
        for index, action in enumerate(best.strategy.actions):
            fps = self.config.frame_clock.frames_per_second
            if self.config.coarse_frames and fps:
                levels = self.config.refinement_levels
                for level in levels:
                    for delta in (-level, level):
                        frame = max(0, round(action.time * float(fps)) + delta)
                        time = round(float(frame / fps), 10)
                        if time == current.strategy.actions[index].time:
                            continue
                        actions = list(current.strategy.actions)
                        actions[index] = Action(ActionType.DEPLOY, time, action.operator_id, action.tile, action.direction)
                        candidate = Strategy(current.strategy.team, tuple(actions))
                        metrics.local_refinements += 1
                        evaluation = self._evaluate(candidate, metrics)
                        if self._rank_key(evaluation) < self._rank_key(current):
                            current = evaluation
            else:
                for delta in self.config.refinement_deltas:
                    time = round(max(0.0, action.time + delta), 10)
                    if time == action.time:
                        continue
                    actions = list(best.strategy.actions)
                    actions[index] = Action(ActionType.DEPLOY, time, action.operator_id, action.tile, action.direction)
                    candidate = Strategy(best.strategy.team, tuple(actions))
                    metrics.local_refinements += 1
                    evaluation = self._evaluate(candidate, metrics)
                    if self._rank_key(evaluation) < self._rank_key(current):
                        current = evaluation
        return current

    def search(self) -> RealSearchResult:
        started = perf_counter()
        metrics = RealSearchMetrics()
        frontier = (Strategy((), ()),)
        ranked_map: dict[tuple, RealStrategyEvaluation] = {}
        for depth in range(1, self.config.max_depth + 1):
            generated = [candidate for partial in frontier for candidate in self.generate_candidates(partial)]
            metrics.candidates_generated += len(generated)
            evaluations = [self._evaluate(candidate, metrics) for candidate in generated]
            evaluations.sort(key=self._rank_key)
            for evaluation in evaluations:
                ranked_map[self._strategy_key(evaluation.strategy)] = evaluation
            frontier = tuple(item.strategy for item in evaluations[:self.config.beam_width])
            metrics.search_depth = depth
            if not frontier:
                break
        if not ranked_map:
            raise RuntimeError("Real search generated no candidates")
        ranked = sorted(ranked_map.values(), key=self._rank_key)
        best = ranked[0]
        if self.config.refine_timing:
            best = self._refine(best, metrics)
            ranked_map[self._strategy_key(best.strategy)] = best
            ranked = sorted(ranked_map.values(), key=self._rank_key)
        metrics.best_score = best.score
        metrics.wall_clock_seconds = perf_counter() - started
        timeline = strategy_to_timeline(
            best.strategy, stage_id=self.fixture.stage.stage_id, frame_clock=self.config.frame_clock,
            simulator_mode=RealExecutionMode.APPROXIMATE_REAL.value,
            approximation_policy_version="real-simulation-approximation-policy-v2-economy",
        )
        # Small local robustness check in the canonical frame domain. It is
        # diagnostic only and does not alter the winning strategy.
        robustness: list[int] = []
        if timeline.actions:
            action = timeline.actions[0]
            for delta in (-3, -2, -1, 0, 1, 2, 3):
                frame = max(0, action.frame + delta)
                adjusted = Action(ActionType.DEPLOY, float(self.config.frame_clock.seconds_for_frame(frame)), action.operator_id, action.tile, action.direction or "RIGHT")
                candidate = Strategy(best.strategy.team, (adjusted, *best.strategy.actions[1:]))
                if self._evaluate(candidate, metrics).result.win:
                    robustness.append(frame)
        return RealSearchResult(best, tuple(ranked), metrics, self.fixture, timeline, tuple(robustness))
