"""Boundaries that turn canonical data into explicitly constrained runtime inputs."""

from .real_simulation import (
    AdaptedRealEnemy,
    AdaptedRealOperator,
    AdaptedRealStage,
    CompatibilityReport,
    RealSimulationAdapter,
    RealSimulationBundle,
    RealSkillData,
    StrictSimulationCompatibilityError,
)
from .approximate_real import (
    ApproximateExecutionReport, ApproximateRealExecutionError, ApproximateRealFixture, ApproximateRealRun,
    ApproximateRealSimulationAdapter, ApproximatedSpawn, MappedRealTile,
    RealExecutionMode, RealOperatorConfiguration, RealOperatorSelection, RealSimulationApproximationPolicy,
    M13LoadoutPolicy,
)
from .low_rarity_skill import InterpretedLowRaritySkill, LowRarityBlackboardEffectInterpreter, RealSkillSupport

__all__ = [
    "AdaptedRealEnemy", "AdaptedRealOperator", "AdaptedRealStage",
    "CompatibilityReport", "RealSimulationAdapter", "RealSimulationBundle",
    "RealSkillData", "StrictSimulationCompatibilityError",
    "ApproximateExecutionReport", "ApproximateRealExecutionError", "ApproximateRealFixture", "ApproximateRealRun",
    "ApproximateRealSimulationAdapter", "ApproximatedSpawn", "MappedRealTile",
    "RealExecutionMode", "RealOperatorConfiguration", "RealOperatorSelection", "RealSimulationApproximationPolicy", "M13LoadoutPolicy",
    "InterpretedLowRaritySkill", "LowRarityBlackboardEffectInterpreter", "RealSkillSupport",
]
