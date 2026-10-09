from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from arknights_planner.models.simulation import EventType

from .evaluation import StrategyEvaluation


class FailureCategory(str, Enum):
    INSUFFICIENT_DP = "INSUFFICIENT_DP"
    ILLEGAL_DEPLOYMENT = "ILLEGAL_DEPLOYMENT"
    DEPLOYMENT_LIMIT_REACHED = "DEPLOYMENT_LIMIT_REACHED"
    LEAK_BEFORE_DEFENSE = "LEAK_BEFORE_DEFENSE"
    INSUFFICIENT_DAMAGE = "INSUFFICIENT_DAMAGE"
    POOR_DEPLOYMENT_TIMING = "POOR_DEPLOYMENT_TIMING"


@dataclass(frozen=True)
class FailureAnalysis:
    categories: tuple[FailureCategory, ...]
    reasons: tuple[str, ...]


def analyze_failure(evaluation: StrategyEvaluation) -> FailureAnalysis:
    """Classify only directly observable synthetic failure conditions."""
    result = evaluation.result
    reasons: list[tuple[FailureCategory, str]] = []
    errors = "\n".join(result.deployment_errors)
    if "insufficient DP" in errors:
        reasons.append((FailureCategory.INSUFFICIENT_DP, "a deployment was rejected for insufficient DP"))
    if "deployment limit reached" in errors:
        reasons.append((FailureCategory.DEPLOYMENT_LIMIT_REACHED, "a deployment exceeded the synthetic limit"))
    if any(text in errors for text in ("tile is not buildable", "tile is occupied", "unknown operator", "not in strategy team", "already deployed")):
        reasons.append((FailureCategory.ILLEGAL_DEPLOYMENT, "a deployment action was illegal"))
    leaks = [event for event in result.events if event.event_type is EventType.ENEMY_LEAK]
    legal_deployments = [event for event in result.events if event.event_type is EventType.DEPLOY and ("legal", True) in event.details]
    attacks = [event for event in result.events if event.event_type is EventType.ATTACK_START]
    spawns = [event for event in result.events if event.event_type is EventType.SPAWN]
    if leaks and (not legal_deployments or leaks[0].time < legal_deployments[0].time):
        reasons.append((FailureCategory.LEAK_BEFORE_DEFENSE, "an enemy leaked before a legal deployment was active"))
    if leaks and attacks:
        reasons.append((FailureCategory.INSUFFICIENT_DAMAGE, "attacks occurred but enemies still leaked"))
    if leaks and legal_deployments and spawns and legal_deployments[0].time > spawns[0].time:
        reasons.append((FailureCategory.POOR_DEPLOYMENT_TIMING, "first legal deployment occurred after the first spawn"))
    return FailureAnalysis(tuple(category for category, _ in reasons), tuple(reason for _, reason in reasons))
