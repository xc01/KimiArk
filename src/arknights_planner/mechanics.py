"""Mechanics versioning and stale artifact dependency checks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ACTIVE_MECHANICS_VERSION = "m18.9-stage-device-runtime-v1"

MECHANICS_VERSION_HISTORY = {
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
    ACTIVE_MECHANICS_VERSION: {
        "status": "ACTIVE",
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
