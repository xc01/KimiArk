"""M13 layered composition coverage and bounded tactical search.

The composition layer is exhaustive for K=1/K=2; detailed timeline evaluation is
explicitly bounded and reported separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from time import perf_counter

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy,
    M13LoadoutPolicy,
)
from arknights_planner.benchmark.census import low_rarity_census
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig, M11SearchResult


@dataclass(frozen=True)
class TeamFeatures:
    operator_ids: tuple[str, ...]
    rarity_sum: int
    damage_types: tuple[str, ...]
    blocking_capacity: int
    healing_count: int
    total_cost: int


@dataclass(frozen=True)
class M13SearchConfig:
    max_squad_size: int = 2
    max_tactical_teams_k1: int = 34
    max_tactical_teams_k2: int = 80
    m11: M11SearchConfig = M11SearchConfig(max_squad_size=2, max_teams=80, beam_width=2, placement_options_per_operator=1)


@dataclass
class M13SearchMetrics:
    k1_possible: int = 0
    k1_compositions_generated: int = 0
    k1_tactical_evaluated: int = 0
    k2_possible: int = 0
    k2_compositions_generated: int = 0
    k2_tactical_evaluated: int = 0
    unique_simulations: int = 0
    cache_hits: int = 0
    wall_clock_seconds: float = 0.0


@dataclass(frozen=True)
class M13SearchOutcome:
    stage_id: str
    executable_pool: tuple[str, ...]
    blocked: tuple[tuple[str, tuple[str, ...]], ...]
    features: tuple[TeamFeatures, ...]
    k1_result: M11SearchResult | None
    k2_result: M11SearchResult | None
    metrics: M13SearchMetrics
    termination: str


def team_features(adapter: ApproximateRealSimulationAdapter, ids: tuple[str, ...]) -> TeamFeatures:
    ops = [adapter.repository.get_operator(item) for item in ids]
    rarities = tuple(int(op.star_rarity.value or 0) for op in ops)
    damage_types = tuple(sorted({"ARTS" if op.profession.value == "CASTER" else "PHYSICAL" for op in ops}))
    blocking = sum(int(op.phases[-1].stats_max.block_count.value or 0) for op in ops)
    healing = sum(1 for op in ops if op.profession.value == "MEDIC")
    cost = sum(int(op.phases[-1].stats_max.cost.value or 0) for op in ops)
    return TeamFeatures(ids, sum(rarities), damage_types, blocking, healing, cost)


class M13LayeredSearch:
    """Exhaust composition layer, then run bounded M11 tactical search."""

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter, stage_id_or_code: str,
                 policy: RealSimulationApproximationPolicy, config: M13SearchConfig | None = None):
        self.adapter, self.stage_id_or_code, self.policy = adapter, stage_id_or_code, policy
        self.config = config or M13SearchConfig()
        census = low_rarity_census(adapter.repository)
        self.blocked = tuple((r.operator_id, r.blockers) for r in census if r.runtime_status.value == "BLOCKED_BY_MECHANIC")
        self.pool = tuple(item.operator_id for item in adapter.m12_low_rarity_configurations(M13LoadoutPolicy.highest_legal()))
        ids = tuple(sorted(self.pool))
        # Composition features are deterministic, read-only planner input.
        # Keeping them available before ``search()`` preserves the M13
        # inspection contract used by the regression suite.
        self.features = tuple(team_features(self.adapter, team) for team in (*combinations(ids, 1), *combinations(ids, 2)))

    def search(self) -> M13SearchOutcome:
        started = perf_counter(); metrics = M13SearchMetrics()
        ids = tuple(sorted(self.pool))
        k1 = tuple(combinations(ids, 1)); k2 = tuple(combinations(ids, 2))
        metrics.k1_possible = len(k1); metrics.k2_possible = len(k2)
        metrics.k1_compositions_generated = len(k1); metrics.k2_compositions_generated = len(k2)
        # Tactical evaluator is intentionally bounded; composition coverage remains 100%.
        k1_result = k2_result = None
        if k1:
            cfg = M11SearchConfig(
                frame_clock=self.config.m11.frame_clock,
                coarse_deployment_frames=self.config.m11.coarse_deployment_frames,
                placement_options_per_operator=self.config.m11.placement_options_per_operator,
                beam_width=self.config.m11.beam_width,
                max_squad_size=1,
                max_teams=self.config.m11.max_teams,
                refinement_frames=self.config.m11.refinement_frames,
                simulation_config=self.config.m11.simulation_config,
            )
            pool1 = tuple(self.adapter.m12_low_rarity_configurations(M13LoadoutPolicy.highest_legal())[: self.config.max_tactical_teams_k1])
            k1_result = M11MinimumSquadSearch(adapter=self.adapter, stage_id_or_code=self.stage_id_or_code, policy=self.policy, operator_pool=pool1, config=cfg).search()
            metrics.k1_tactical_evaluated = len(pool1)
            metrics.unique_simulations += k1_result.metrics.unique_simulations; metrics.cache_hits += k1_result.metrics.cache_hits
        if k2:
            # Pair composition coverage is complete above; detailed search uses a bounded pool
            # to avoid an unbounded Cartesian timeline expansion.
            pool2 = tuple(self.adapter.m12_low_rarity_configurations(M13LoadoutPolicy.highest_legal())[: self.config.max_tactical_teams_k2])
            k2_result = M11MinimumSquadSearch(adapter=self.adapter, stage_id_or_code=self.stage_id_or_code, policy=self.policy, operator_pool=pool2, config=self.config.m11).search()
            metrics.k2_tactical_evaluated = min(len(k2), self.config.max_tactical_teams_k2)
            metrics.unique_simulations += k2_result.metrics.unique_simulations; metrics.cache_hits += k2_result.metrics.cache_hits
        metrics.wall_clock_seconds = perf_counter() - started
        winning = any(
            result is not None and result.best is not None and result.best.result.win
            for result in (k1_result, k2_result)
        )
        return M13SearchOutcome(self.stage_id_or_code, ids, self.blocked, self.features, k1_result, k2_result, metrics, "WIN_FOUND" if winning else "BEST_FOUND_UNDER_BUDGET")
