"""Mechanics versioning and stale artifact dependency checks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ACTIVE_MECHANICS_VERSION = "m38b-2781-animation-speed-v1"

MECHANICS_VERSION_HISTORY = {
    "m36-2781-artillery-clock-v1": {
        "status": "SUPERSEDED",
        "summary": "Uses 2.7.81 candidate-model evidence to keep the delayed locked-area artillery clock tied to attack-time changes rather than resetting while no target exists. Build-2771 identity is not claimed.",
    },
    "m38-2781-artillery-projectile-windup-v1": {
        "status": "SUPERSEDED",
        "status_history": "SUPERSEDED_BY_m38b",
        "summary": "Separates artillery cast wind-up, projectile creation, fixed-point lock, and the projectile's 3-second delay using 2.7.81 candidate-model evidence. Its 0.077778-second wind-up used duration divided by attack time and is superseded by the animation-speed formula.",
    },
    "m38b-2781-animation-speed-v1": {
        "status": "ACTIVE",
        "summary": "Separates artillery cast wind-up, projectile creation, fixed-point lock, and the projectile's 3-second delay using 2.7.81 candidate-model evidence. Build-2771 identity is not claimed.",
    },
    "m23-behavioral-mechanics-v1": {
        "status": "SUPERSEDED",
        "summary": "Connects skill range/damage/heal behavior to runtime, fixes route blocker intersection, artillery launch-impact cycles, COLD attack interval, friendly device x-1 geometry, and static refund/deployment semantics. Full mechanism closure is not claimed.",
    },
    "m18-targeting-v1": {
        "status": "HISTORICAL",
        "summary": "Target-selection diagnostics with route-progress ordering.",
    },
    "m18.1-target-distance-v2": {
        "status": "SUPERSEDED",
        "summary": "Ordinary target ordering changed to remaining legal route distance then stable creation order.",
    },
    "m18.2-blocked-target-v1": {
        "status": "SUPERSEDED",
        "summary": "Adds PRTS-backed ordinary self-blocked target priority for melee operators.",
    },
    "m18.3-enemy-attack-v1": {
        "status": "ACTIVE",
        "status_history": "SUPERSEDED_BY_m18.4",
        "summary": "GameData-backed enemy applyWay gates melee attack range; MAGIC enemy attacks use the PRTS Arts formula.",
    },
    "m18.4-enemy-metadata-v1": {
        "status": "ACTIVE",
        "status_history": "SUPERSEDED_BY_m18.5",
        "summary": "Unwraps GameData ValueWithSource metadata for enemy applyWay and damageType, making the m18.3 range/formula gates deterministic.",
    },
    "m18.5-operator-generic-v1": {
        "status": "ACTIVE",
        "status_history": "SUPERSEDED_BY_m18.6",
        "summary": "Adds generic low-rarity operator skill primitives: DEF buff, ASPD additive, forward range extension, and attack-SP next-attack replacement.",
    },
    "m18.6-low-rarity-closure-v1": {
        "status": "ACTIVE",
        "status_history": "SUPERSEDED_BY_m18.7",
        "summary": "Adds BAT override, immediate max-HP self-heal, and heal-mode generic primitives for low-rarity closure.",
    },
    "m18.7-enemy-attack-timing-v1": {
        "status": "SUPERSEDED",
        "status_history": "SUPERSEDED_BY_m18.8",
        "summary": "Adds offline client-derived enemy Spine OnAttack timing as generic wind-up/strike/recovery behavior.",
    },
    "m18.8-enemy-ability-passives-v1": {
        "status": "SUPERSEDED",
        "status_history": "SUPERSEDED_BY_m18.9",
        "summary": "Adds enemy passive HP regeneration and exact every-second-attack cold override while retaining client-derived enemy attack timing.",
    },
    "m20-stage-clock-v1": {
        "status": "SUPERSEDED",
        "summary": "Adds stage moveMultiplier, maxCost, required block capacity, air eligibility, retreat refund, fragment/wave waits, and disappear/appear hidden spans.",
    },
    "m22-deep-mechanics-partial-v1": {
        "status": "SUPERSEDED",
        "summary": "Adds stage moveMultiplier, maxCost, required block capacity, air eligibility, retreat refund, fragment/wave waits, and disappear/appear hidden spans.",
    },
    "m19.0-neutral-protected-target-v1": {
        "status": "SUPERSEDED",
        "summary": "Adds neutral protected-target faction, life scoring, and roadblock civilian blocking.",
    },
    "m18.9-stage-device-runtime-v1": {
        "status": "SUPERSEDED",
        "summary": "Adds enemy passive HP regeneration and exact every-second-attack cold override while retaining client-derived enemy attack timing.",
    },
}


@dataclass(frozen=True)
class MechanicsArtifactDependency:
    artifact_path: str
    mechanics_version: str
    affected_topics: tuple[str, ...]


def artifact_mechanics_status(
    recorded_version: str,
    active_version: str = ACTIVE_MECHANICS_VERSION,
) -> str:
    if recorded_version == active_version:
        return "CURRENT"
    if recorded_version in MECHANICS_VERSION_HISTORY:
        return "STALE_REQUIRES_DETERMINISTIC_REPLAY"
    return "UNKNOWN_VERSION_TREAT_AS_STALE"


def audit_mechanics_dependencies(
    dependencies: tuple[MechanicsArtifactDependency, ...],
    active_version: str = ACTIVE_MECHANICS_VERSION,
) -> dict[str, Any]:
    rows = []
    for dependency in dependencies:
        status = artifact_mechanics_status(dependency.mechanics_version, active_version)
        rows.append({
            **dependency.__dict__,
            "status": status,
            "reuse_policy": "CURRENT_EVIDENCE" if status == "CURRENT" else "HISTORICAL_ONLY_UNTIL_REPLAYED",
        })
    return {
        "active_mechanics_version": active_version,
        "version_history": MECHANICS_VERSION_HISTORY,
        "dependencies": rows,
        "current_count": sum(row["status"] == "CURRENT" for row in rows),
        "stale_count": sum(row["status"] != "CURRENT" for row in rows),
    }
