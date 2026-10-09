"""Explicit experiment scope for bounded planner runs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION


@dataclass(frozen=True)
class ExperimentScope:
    stage_id: str
    operator_pool: tuple[str, ...]
    max_cardinality: int
    mechanics_version: str = ACTIVE_MECHANICS_VERSION
    simulation_budget: int = 0
    search_policy: str = "BOUNDED_TOP_DOWN"
    pool_policy: str = "EXPLICIT_OPERATOR_IDS"
    squad_size_limit: int | None = None
    deployment_limit: int | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.stage_id:
            raise ValueError("ExperimentScope requires a stage_id")
        if not self.operator_pool:
            raise ValueError("ExperimentScope requires an explicit operator pool")
        if self.max_cardinality < 1:
            raise ValueError("max_cardinality must be positive")
        if self.simulation_budget < 0:
            raise ValueError("simulation_budget cannot be negative")
        if len(set(self.operator_pool)) != len(self.operator_pool):
            raise ValueError("operator_pool cannot contain duplicate operator IDs")
        if self.max_cardinality > len(self.operator_pool):
            raise ValueError("max_cardinality cannot exceed the explicit operator pool")
        if self.squad_size_limit is not None and self.max_cardinality > self.squad_size_limit:
            raise ValueError("max_cardinality cannot exceed the explicit squad-size limit")

    @classmethod
    def main_6_8_low_rarity(
        cls,
        *,
        operator_pool: tuple[str, ...],
        max_cardinality: int = 7,
        simulation_budget: int = 2000,
        search_policy: str = "M15_CONSTRAINT_GUIDED_FEASIBILITY",
    ) -> "ExperimentScope":
        return cls(
            stage_id="6-8",
            operator_pool=operator_pool,
            max_cardinality=max_cardinality,
            simulation_budget=simulation_budget,
            search_policy=search_policy,
            pool_policy="BENCHMARK_LOW_RARITY_1_3_STAR",
            notes=("K<=7 is a benchmark bound, not a global planner property.",),
        )

    @classmethod
    def main_0_1_smoke(
        cls,
        *,
        operator_pool: tuple[str, ...],
        max_cardinality: int = 3,
        simulation_budget: int = 24,
    ) -> "ExperimentScope":
        return cls(
            stage_id="0-1",
            operator_pool=operator_pool,
            max_cardinality=max_cardinality,
            simulation_budget=simulation_budget,
            search_policy="TINY_DETERMINISTIC_SMOKE",
            pool_policy="EXPLICIT_SMOKE_POOL",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def conclusion_scope(self) -> dict[str, Any]:
        return {
            "scope_type": "EXPERIMENT_SCOPE",
            "stage_id": self.stage_id,
            "operator_pool_policy": self.pool_policy,
            "max_cardinality": self.max_cardinality,
            "mechanics_version": self.mechanics_version,
            "simulation_budget": self.simulation_budget,
            "search_policy": self.search_policy,
            "squad_size_limit": self.squad_size_limit,
            "deployment_limit": self.deployment_limit,
            "global_claim_valid": False,
        }
