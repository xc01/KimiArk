from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from arknights_planner.adapters.normal_low_star import (
    active_talent_candidates,
    debug_configuration,
    deployment_heal_all_value,
    deployment_sp_bonus,
    is_normal_mode_low_star,
    qualify_normal_mode_low_star,
)
from arknights_planner.gamedata.repository import GameDataRepository


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "0ef7f952dfd018392200157a5c79a6511ba69122"
SOURCE_TABLES = (
    "character_table.json",
    "skill_table.json",
    "range_table.json",
)
MECHANISM_OUTPUT_NAME = "normal_low_star_mechanism_support.json"


def file_digest(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def source_paths(operator_id: str) -> dict[str, str]:
    character = f"$.{operator_id}"
    return {
        "availability": f"{character}.itemObtainApproach,{character}.isNotObtainable",
        "identity": f"{character}.name,{character}.rarity,{character}.profession,{character}.subProfessionId,{character}.position",
        "phases_stats": f"{character}.phases[*].attributesKeyFrames[*].data",
        "range": f"{character}.phases[*].rangeId,$.{{range_id}}.grids",
        "skills": f"{character}.skills[*].skillId,$.{{skill_id}}.levels[*]",
        "talents": f"{character}.talents[*].candidates[*]",
        "potential": f"{character}.potentialRanks[*]",
        "trust": f"{character}.favorKeyFrames[*]",
    }


def skill_facts(repository: GameDataRepository, skill_id: str, level_index: int) -> dict[str, Any]:
    skill = repository.get_skill(skill_id)
    level = skill.levels[level_index]
    blackboard = {key: value for key, value in skill.levels[level_index].blackboard if value is not None}
    return {
        "skill_id": skill_id,
        "name": level.name.value,
        "level_index": level_index,
        "skill_type": level.skill_type.value,
        "duration_type": level.duration_type.value,
        "duration": level.duration.value,
        "sp_type": level.sp_type.value,
        "initial_sp": level.initial_sp.value,
        "sp_cost": level.sp_cost.value,
        "charges": level.max_charge_time.value,
        "blackboard": blackboard,
        "range_id": level.range_id.value,
        "source_path": f"$.{skill_id}.levels[{level_index}]",
    }


def skill_level_facts(repository: GameDataRepository, skill_id: str) -> list[dict[str, Any]]:
    skill = repository.get_skill(skill_id)
    return [skill_facts(repository, skill_id, index) for index in range(min(7, len(skill.levels)))]


def branch_mechanism(raw: dict[str, Any]) -> dict[str, Any]:
    description = raw.get("description") or ""
    branch = raw.get("subProfessionId")
    if branch in {"splashcaster", "aoesniper"}:
        return {
            "mechanic": "BRANCH_AREA_ATTACK",
            "runtime_supported": False,
            "status": "UNSUPPORTED_AOE_GEOMETRY",
            "reason": "GameData branch description establishes area damage, but splash radius/target geometry is not represented in the local runtime",
        }
    if "两次" in description:
        return {
            "mechanic": "BRANCH_TWO_HIT_GROUND_ATTACK",
            "runtime_supported": False,
            "status": "UNSUPPORTED_MULTI_HIT",
            "reason": "GameData description establishes two ground hits, but the generic runtime does not model the appended hit",
        }
    if "不攻击" in description and "持续恢复" in description:
        return {
            "mechanic": "BRANCH_CONTINUOUS_AURA_HEAL",
            "runtime_supported": False,
            "status": "UNSUPPORTED_AURA_HEAL",
            "reason": "GameData description establishes continuous range-wide recovery, but the runtime uses normal attacks or selected skills only",
        }
    return {
        "mechanic": "GENERIC_NORMAL_ATTACK",
        "runtime_supported": True,
        "status": "GENERIC_APPROXIMATION",
        "reason": "single-target basic attack uses the shared generic runtime",
    }


def talent_mechanism_support(repository: GameDataRepository, operator_id: str) -> dict[str, Any]:
    active = active_talent_candidates(repository, operator_id)
    if not active:
        return {
            "active_talents": [],
            "runtime_supported": True,
            "status": "NO_ACTIVE_TALENT",
        }
    recognized = []
    for candidate in active:
        description = candidate.get("description") or ""
        if "自身部署费用" in description and "部署费用" in description:
            status = "RUNTIME_SUPPORTED_SELF_COST"
            runtime_supported = True
        elif "部署后立即获得" in description and "技力" in description:
            status = "RUNTIME_SUPPORTED_DEPLOYMENT_SP"
            runtime_supported = True
        elif "部署后立即恢复全场友方单位" in description and "生命" in description:
            status = "RUNTIME_SUPPORTED_DEPLOYMENT_HEAL_ALL"
            runtime_supported = True
        elif "再部署时间" in description and "-30" in description:
            status = "RUNTIME_SUPPORTED_REDEPLOY_DELTA"
            runtime_supported = True
        else:
            status = "UNSUPPORTED_ACTIVE_TALENT"
            runtime_supported = False
        recognized.append({
            "name": candidate.get("name"),
            "description": description,
            "blackboard": candidate.get("blackboard"),
            "runtime_supported": runtime_supported,
            "status": status,
        })
    return {
        "active_talents": recognized,
        "runtime_supported": all(item["runtime_supported"] for item in recognized),
        "status": "RUNTIME_SUPPORTED" if all(item["runtime_supported"] for item in recognized) else "PARTIALLY_UNVERIFIED_OR_UNSUPPORTED",
    }


def build_mechanism_support(repository: GameDataRepository, catalog: dict[str, Any]) -> dict[str, Any]:
    low_skill_path = ROOT / "output/operator_runtime_fidelity_v1/low_rarity_skill_audit.json"
    skill_audit = {
        item["operator_id"]: item
        for item in json.loads(low_skill_path.read_text(encoding="utf-8"))["operators"]
    }
    raw_table = repository._table("character_table.json")
    operators = []
    for fact in catalog["operators"]:
        operator_id = fact["operator_id"]
        low_record = skill_audit.get(operator_id)
        skill_rows = []
        for skill_id, skill in fact["all_skill_level_facts"].items():
            selected = low_record["skills"][0] if low_record and low_record["skills"] else None
            skill_rows.append({
                "skill_id": skill_id,
                "selected_level_index": skill[-1]["level_index"],
                "runtime_supported": bool(selected and selected["planner_safe"]),
                "status": "EXECUTABLE_APPROXIMATED" if selected and selected["planner_safe"] else "UNSUPPORTED",
            })
        branch = branch_mechanism(raw_table[operator_id])
        talent = talent_mechanism_support(repository, operator_id)
        runtime_supported = all(item["runtime_supported"] for item in skill_rows) and branch["runtime_supported"] and talent["runtime_supported"]
        operators.append({
            "operator_id": operator_id,
            "debug_configuration": fact["debug_configuration"],
            "base_stats": {"runtime_supported": True, "status": "EXACT_SOURCE_KEYFRAME"},
            "normal_attack": {"runtime_supported": branch["runtime_supported"], **branch},
            "skills": skill_rows,
            "talent": talent,
            "deployment_sp_bonus": deployment_sp_bonus(repository, operator_id),
            "deployment_heal_all_value": deployment_heal_all_value(repository, operator_id),
            "overall": "PLANNER_SAFE_WITH_KNOWN_LIMITS" if runtime_supported else "NOT_PLANNER_SAFE",
        })
    return {
        "schema_version": "normal-low-star-mechanism-support-v1",
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "counts": {
            "operators": len(operators),
            "planner_safe_with_known_limits": sum(item["overall"] == "PLANNER_SAFE_WITH_KNOWN_LIMITS" for item in operators),
            "not_planner_safe": sum(item["overall"] == "NOT_PLANNER_SAFE" for item in operators),
        },
        "operators": operators,
    }


def build_catalog(repository: GameDataRepository) -> dict[str, Any]:
    raw_table = repository._table("character_table.json")
    low_star_ids = sorted(
        operator_id
        for operator_id in repository.operator_ids()
        if is_normal_mode_low_star(repository, operator_id)
    )
    operators: list[dict[str, Any]] = []
    for operator_id in low_star_ids:
        qualification = qualify_normal_mode_low_star(repository, operator_id)
        raw = raw_table[operator_id]
        operator = repository.get_operator(operator_id)
        configuration = debug_configuration(repository, operator_id)
        phase = operator.phases[configuration["phase_index"]]
        stats = phase.stats_max
        attack_range = repository.get_range(str(phase.range_id.value))
        all_talent_candidates = []
        active_talents = []
        for talent_index, talent in enumerate(raw.get("talents", [])):
            eligible_candidates = []
            for candidate_index, candidate in enumerate(talent.get("candidates", [])):
                fact = {
                    "talent_index": talent_index,
                    "candidate_index": candidate_index,
                    "name": candidate.get("name"),
                    "description": candidate.get("description"),
                    "unlock_condition": candidate.get("unlockCondition"),
                    "required_potential_rank": candidate.get("requiredPotentialRank"),
                    "range_id": candidate.get("rangeId"),
                    "blackboard": {
                        item["key"]: item["value"]
                        for item in candidate.get("blackboard", [])
                        if isinstance(item, dict)
                    },
                    "source_path": f"$.{operator_id}.talents[{talent_index}].candidates[{candidate_index}]",
                }
                all_talent_candidates.append(fact)
                unlock = candidate.get("unlockCondition") or {}
                required_rank = int(candidate.get("requiredPotentialRank", 0) or 0)
                phase_index = 1 if unlock.get("phase") == "PHASE_1" else 0
                if (
                    phase_index == configuration["phase_index"]
                    and int(unlock.get("level", 1) or 1) <= configuration["level"]
                    and required_rank <= int(configuration["required_potential_rank"])
                ):
                    eligible_candidates.append((int(unlock.get("level", 1) or 1), fact))
            if eligible_candidates:
                active_talents.append(max(eligible_candidates, key=lambda item: item[0])[1])
        operators.append({
            "operator_id": operator_id,
            "name": raw.get("name"),
            "qualification": {
                "normal_mode": is_normal_mode_low_star(repository, operator_id),
                "eligible_for_debug": qualification.eligible,
                "reasons": list(qualification.reasons),
                "item_obtain_approach": raw.get("itemObtainApproach"),
                "is_not_obtainable": raw.get("isNotObtainable"),
            },
            "identity": {
                "rarity": operator.star_rarity.value,
                "profession": raw.get("profession"),
                "branch": raw.get("subProfessionId"),
                "position": raw.get("position"),
            },
            "description": raw.get("description"),
            "trait": [
                {
                    "description": candidate.get("overrideDescripton") or candidate.get("description"),
                    "unlock_condition": candidate.get("unlockCondition"),
                    "required_potential_rank": candidate.get("requiredPotentialRank"),
                    "blackboard": {
                        item["key"]: item["value"]
                        for item in candidate.get("blackboard", [])
                        if isinstance(item, dict)
                    },
                    "source_path": f"$.{operator_id}.trait.candidates[{index}]",
                }
                for index, candidate in enumerate((raw.get("trait") or {}).get("candidates", []))
            ],
            "debug_configuration": configuration,
            "stats": {
                "max_hp": stats.max_hp.value,
                "atk": stats.atk.value,
                "def": stats.defense.value,
                "res": stats.magic_resistance.value,
                "cost": stats.cost.value,
                "block_count": stats.block_count.value,
                "attack_interval": stats.attack_interval.value,
                "redeploy_time": stats.redeploy_time.value,
            },
            "range": {
                "range_id": phase.range_id.value,
                "cells": sorted((cell.row, cell.col) for cell in attack_range.cells),
                "source_path": f"$.{str(phase.range_id.value)}.grids",
            },
            "normal_attack": {
                "damage_type": "ARTS" if raw.get("profession") == "CASTER" else "PHYSICAL",
                "combat_output": "HEAL" if raw.get("profession") == "MEDIC" else "DAMAGE",
                "base_target_count": 1,
                "single_target_note": "Splashcaster/aoesniper/ritualist branch traits need separate evidence; this is the generic runtime's target count only.",
            },
            "skills": [
                skill_facts(repository, skill_id, configuration["skill_level_index"])
                for skill_id in operator.skill_ids
            ],
            "all_skill_level_facts": {
                skill_id: skill_level_facts(repository, skill_id)
                for skill_id in operator.skill_ids
            },
            "active_talents_at_configuration": active_talents,
            "all_talent_candidates": all_talent_candidates,
            "potential_ranks": [
                {
                    "rank": index + 1,
                    "description": item.get("description"),
                    "buff": item.get("buff"),
                    "source_path": f"$.{operator_id}.potentialRanks[{index}]",
                }
                for index, item in enumerate(raw.get("potentialRanks", []))
            ],
            "trust_keyframes": raw.get("favorKeyFrames", []),
            "source_paths": source_paths(operator_id),
        })
    return {
        "schema_version": "normal-low-star-facts-v1",
        "mechanics_version": "m18.9-stage-device-runtime-v1",
        "gamedata": {
            "upstream_commit": UPSTREAM_COMMIT,
            "source_tables": [file_digest(ROOT / "data/ArknightsGameData/zh_CN/gamedata/excel" / item) for item in SOURCE_TABLES],
        },
        "policy": {
            "normal_mode": "itemObtainApproach is present and isNotObtainable is not true",
            "star_range": [1, 3],
            "debug_configuration": "3★ uses E1/max phase level and skill rank 7; 1★/2★ use phase 0/max level and no skills; all use potential 1 and trust 0",
            "potential_semantics": "requiredPotentialRank 0 corresponds to potential level 1; only rank-0 talents are active in this baseline",
        },
        "counts": {
            "normal_low_star": len(low_star_ids),
            "rarity_1": sum(operator["identity"]["rarity"] == 1 for operator in operators),
            "rarity_2": sum(operator["identity"]["rarity"] == 2 for operator in operators),
            "rarity_3": sum(operator["identity"]["rarity"] == 3 for operator in operators),
        },
        "operators": operators,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/normal_low_star_facts_v1")
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    catalog = build_catalog(repository)
    (output / "normal_low_star_facts.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    mechanism = build_mechanism_support(repository, catalog)
    (output / MECHANISM_OUTPUT_NAME).write_text(
        json.dumps(mechanism, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest = {
        "schema_version": "normal-low-star-facts-v1-manifest",
        "gamedata_commit": UPSTREAM_COMMIT,
        "source_tables": [file_digest(ROOT / "data/ArknightsGameData/zh_CN/gamedata/excel" / item) for item in SOURCE_TABLES],
        "outputs": [
            file_digest(output / "normal_low_star_facts.json"),
            file_digest(output / MECHANISM_OUTPUT_NAME),
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
