from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arknights_planner.gamedata.repository import GameDataRepository


@dataclass(frozen=True)
class NormalLowStarQualification:
    operator_id: str
    eligible: bool
    reasons: tuple[str, ...]


def _raw_character(repository: GameDataRepository, operator_id: str) -> dict[str, Any]:
    raw = repository._table("character_table.json").get(operator_id)
    if not isinstance(raw, dict):
        raise KeyError(operator_id)
    return raw


def is_normal_mode_operator(repository: GameDataRepository, operator_id: str) -> bool:
    raw = _raw_character(repository, operator_id)
    return bool(raw.get("itemObtainApproach")) and raw.get("isNotObtainable") is not True


def is_normal_mode_low_star(repository: GameDataRepository, operator_id: str) -> bool:
    if not is_normal_mode_operator(repository, operator_id):
        return False
    operator = repository.get_operator(operator_id)
    return operator.star_rarity.value is not None and 1 <= int(operator.star_rarity.value) <= 3


def qualify_normal_mode_low_star(
    repository: GameDataRepository, operator_id: str
) -> NormalLowStarQualification:
    reasons: list[str] = []
    if not is_normal_mode_operator(repository, operator_id):
        reasons.append("NOT_NORMAL_MODE_OBTAINABLE")
    operator = repository.get_operator(operator_id)
    rarity = operator.star_rarity.value
    if rarity is None or not 1 <= int(rarity) <= 3:
        reasons.append("RARITY_OUTSIDE_1_TO_3")
    return NormalLowStarQualification(operator_id, not reasons, tuple(reasons))


def debug_configuration(repository: GameDataRepository, operator_id: str) -> dict[str, Any]:
    """Return the explicitly chosen, source-grounded low-star test configuration."""
    qualification = qualify_normal_mode_low_star(repository, operator_id)
    if not qualification.eligible:
        raise ValueError(f"{operator_id}: {', '.join(qualification.reasons)}")
    operator = repository.get_operator(operator_id)
    rarity = int(operator.star_rarity.value)
    phase_index = 1 if rarity == 3 else 0
    phase = operator.phases[phase_index]
    return {
        "rarity": rarity,
        "phase_index": phase_index,
        "level": int(phase.max_level.value),
        "skill_rank": 7 if operator.skill_ids else None,
        "skill_level_index": 6 if operator.skill_ids else None,
        "potential_level": 1,
        "required_potential_rank": 0,
        "trust": 0,
        "legal_for_debug": True,
    }


def active_talent_candidates(
    repository: GameDataRepository, operator_id: str
) -> list[dict[str, Any]]:
    try:
        configuration = debug_configuration(repository, operator_id)
    except ValueError:
        return []
    raw = _raw_character(repository, operator_id)
    active: list[dict[str, Any]] = []
    for talent_index, talent in enumerate(raw.get("talents", [])):
        eligible: list[tuple[int, dict[str, Any]]] = []
        for candidate_index, candidate in enumerate(talent.get("candidates", [])):
            unlock = candidate.get("unlockCondition") or {}
            phase_index = 1 if unlock.get("phase") == "PHASE_1" else 0
            if (
                phase_index == configuration["phase_index"]
                and int(unlock.get("level", 1) or 1) <= configuration["level"]
                and int(candidate.get("requiredPotentialRank", 0) or 0)
                <= int(configuration["required_potential_rank"])
            ):
                eligible.append((int(unlock.get("level", 1) or 1), candidate))
        if eligible:
            active.append(max(eligible, key=lambda item: item[0])[1])
    return active


def _blackboard(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        item["key"]: item["value"]
        for item in candidate.get("blackboard", [])
        if isinstance(item, dict)
    }


def deployment_sp_bonus(repository: GameDataRepository, operator_id: str) -> float:
    total = 0.0
    for candidate in active_talent_candidates(repository, operator_id):
        description = candidate.get("description") or ""
        if "部署后立即获得" in description and "技力" in description:
            total += float(_blackboard(candidate).get("sp", 0.0) or 0.0)
    return total


def deployment_heal_all_value(repository: GameDataRepository, operator_id: str) -> float:
    total = 0.0
    for candidate in active_talent_candidates(repository, operator_id):
        description = candidate.get("description") or ""
        if "部署后立即恢复全场友方单位" in description and "生命" in description:
            total += float(_blackboard(candidate).get("value", 0.0) or 0.0)
    return total
