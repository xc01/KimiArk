"""Read-only GameData censuses; classifications are simulator support, not source fact."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from arknights_planner.gamedata.repository import GameDataRepository


class OperatorSupport(str, Enum):
    SIMPLE_SUPPORTED = "SIMPLE_SUPPORTED"
    SIMPLE_UNSUPPORTED = "SIMPLE_UNSUPPORTED"
    COMPLEX_UNSUPPORTED = "COMPLEX_UNSUPPORTED"
    NEEDS_INVESTIGATION = "NEEDS_INVESTIGATION"

class RuntimeSupportStatus(str, Enum):
    EXECUTABLE = "EXECUTABLE"
    EXECUTABLE_WITH_APPROXIMATION = "EXECUTABLE_WITH_APPROXIMATION"
    BLOCKED_BY_MECHANIC = "BLOCKED_BY_MECHANIC"
    INVALID_DATA = "INVALID_DATA"


def _talent_blockers(talents: list[dict]) -> tuple[str, ...]:
    """Return concrete, source-derived blocker labels for active phase-0 talents."""
    out: list[str] = []
    for talent in talents:
        for candidate in talent.get("candidates", []):
            cond = candidate.get("unlockCondition", {}) if isinstance(candidate, dict) else {}
            if cond.get("phase") != "PHASE_0" or cond.get("level", 1) > 1 or candidate.get("requiredPotentialRank", 0) != 0:
                continue
            text = str(candidate.get("description") or "")
            keys = {str(x.get("key")) for x in candidate.get("blackboard", []) if isinstance(x, dict)}
            if "cost" in keys or "部署费用" in text:
                out.append("PASSIVE_DP_GENERATION")
            if "damage_by_atk_scale" in keys or "attack@bomb_scale" in keys:
                out.append("DEPLOY_TRIGGERED_AREA_DAMAGE")
            if "damage_resistance" in keys or "减免" in text:
                out.append("DEPLOY_AURA_DAMAGE_REDUCTION")
            if "恢复" in text or "生命" in text or "heal" in text.lower():
                out.append("DEPLOY_TRIGGERED_HEALING")
            if ("atk" in keys or "def" in keys) and ("所有友方" in text or "单位" in text):
                out.append("DEPLOY_AURA_STAT_MODIFIER")
            if "magic_resistance" in keys or "法术抗性" in text:
                out.append("PASSIVE_RESISTANCE_MODIFIER")
            if "stun" in text or "sleep" in text or "恐惧" in text or "眩晕" in text or "沉睡" in text:
                out.append("CROWD_CONTROL_EFFECT")
            if "max_cnt" in keys or "attack@max_boom_cnt" in keys:
                out.append("LIMITED_MULTI_TARGET_EFFECT")
            if not out:
                out.append("PASSIVE_TALENT_EFFECT")
    return tuple(dict.fromkeys(out))


@dataclass(frozen=True)
class LowRarityOperatorRecord:
    operator_id: str
    name: str | None
    rarity: int
    profession: str | None
    available_phases: tuple[int, ...]
    maximum_relevant_level: int | None
    deploy_cost: int | None
    block_count: int | None
    attack_interval: float | None
    range_ids: tuple[str, ...]
    skill_ids: tuple[str, ...]
    talent_count: int
    structurally_loadable: bool
    support: OperatorSupport
    support_reason: str
    runtime_status: RuntimeSupportStatus = RuntimeSupportStatus.EXECUTABLE_WITH_APPROXIMATION
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class StageBenchmarkRecord:
    stage_id: str
    code: str | None
    chapter: int
    map_width: int | None
    map_height: int | None
    route_count: int | None
    wave_count: int | None
    fragment_count: int
    spawn_action_count: int | None
    enemy_types: tuple[str, ...]
    initial_dp: int | None
    deployment_limit: int | None
    tile_kinds: tuple[str, ...]
    compatibility: str
    blockers: tuple[str, ...]
    tier: str


@dataclass(frozen=True)
class ChapterStageCandidate:
    """Structural M11 selection input; chapter number is not a difficulty score."""

    stage_id: str
    code: str
    chapter: int
    chapter_ordinal: int
    progression_band: str
    structurally_loadable: bool
    route_count: int | None
    spawn_action_count: int | None
    enemy_types: tuple[str, ...]
    tile_kinds: tuple[str, ...]


def _support(repository: GameDataRepository, skill_ids: tuple[str, ...], talents: list[dict]) -> tuple[OperatorSupport, str]:
    phase_zero_active = any(
        candidate.get("unlockCondition", {}).get("phase") == "PHASE_0" and candidate.get("unlockCondition", {}).get("level", 1) <= 1
        for talent in talents for candidate in talent.get("candidates", []) if isinstance(candidate, dict)
    )
    manual_atk_pattern = any(
        level.skill_type.value == "MANUAL" and level.sp_type.value == "INCREASE_WITH_TIME"
        and level.duration.value is not None and float(level.duration.value) > 0
        and set(dict(level.blackboard)) == {"atk"}
        for skill_id in skill_ids for level in repository.get_skill(skill_id).levels[-1:]
    )
    if manual_atk_pattern and not phase_zero_active:
        return OperatorSupport.SIMPLE_SUPPORTED, "phase-0 baseline plus bounded manual time-SP atk-blackboard interpreter"
    if not skill_ids and not phase_zero_active:
        return OperatorSupport.SIMPLE_SUPPORTED, "exact phase-0 level-1 baseline; no active talent or skill interpreter required"
    if phase_zero_active:
        return OperatorSupport.COMPLEX_UNSUPPORTED, "phase-0 talent semantics are active and unimplemented"
    return OperatorSupport.SIMPLE_UNSUPPORTED, "skill pattern is outside M10 bounded interpreter"


def low_rarity_census(repository: GameDataRepository) -> tuple[LowRarityOperatorRecord, ...]:
    table = repository._table("character_table.json")  # read-only census over canonical source table
    records: list[LowRarityOperatorRecord] = []
    for operator_id in repository.operator_ids():
        raw = table[operator_id]
        # `character_table` also contains map entities/templates.  This source field
        # is the available local discriminator for normal operator acquisition.
        if not raw.get("itemObtainApproach") or raw.get("isNotObtainable") is True:
            continue
        operator = repository.get_operator(operator_id)
        rarity = operator.star_rarity.value
        if rarity not in {1, 2, 3}:
            continue
        phases = operator.phases
        final = phases[-1] if phases else None
        talents = raw.get("talents") or []
        phase_zero_active = any(
            candidate.get("unlockCondition", {}).get("phase") == "PHASE_0"
            and candidate.get("unlockCondition", {}).get("level", 1) <= 1
            for talent in talents for candidate in talent.get("candidates", []) if isinstance(candidate, dict)
        )
        manual_atk_pattern = any(
            level.skill_type.value == "MANUAL" and level.sp_type.value == "INCREASE_WITH_TIME"
            and level.duration.value is not None and float(level.duration.value) > 0
            and set(dict(level.blackboard)) == {"atk"}
            for skill_id in operator.skill_ids for level in repository.get_skill(skill_id).levels[-1:]
        )
        support, reason = _support(repository, operator.skill_ids, talents)
        # Runtime coverage is deliberately about the basic attack/deployment
        # model.  Unsupported optional skills are reported, but do not make a
        # basic operator unusable when no skill action is requested.  Active
        # phase-0 talents, malformed keyframes, and missing ranges do block it.
        blockers: list[str] = []
        runtime_status = RuntimeSupportStatus.EXECUTABLE_WITH_APPROXIMATION
        if not phases or not final or not final.keyframes:
            runtime_status, blockers = RuntimeSupportStatus.INVALID_DATA, ["no exact phase keyframe"]
        elif phase_zero_active:
            blockers = list(_talent_blockers(talents)) or ["PASSIVE_TALENT_EFFECT"]
            runtime_status = RuntimeSupportStatus.BLOCKED_BY_MECHANIC
        elif not final.range_id.value:
            runtime_status, blockers = RuntimeSupportStatus.BLOCKED_BY_MECHANIC, ["attack range is unavailable"]
        elif operator.skill_ids and not manual_atk_pattern:
            blockers.append("optional skill pattern is not executable: basic attacks remain available")
        records.append(LowRarityOperatorRecord(
            operator_id, operator.name.value, rarity, operator.profession.value,
            tuple(phase.phase_index for phase in phases), final.max_level.value if final else None,
            final.stats_max.cost.value if final else None, final.stats_max.block_count.value if final else None,
            final.stats_max.attack_interval.value if final else None,
            tuple(phase.range_id.value for phase in phases if phase.range_id.value), operator.skill_ids,
            len(raw.get("talents") or []), True, support, reason, runtime_status, tuple(blockers),
        ))
    return tuple(records)


def runtime_coverage_report(repository: GameDataRepository) -> dict:
    """Compact deterministic coverage report used by M13 CLI/docs."""
    records = low_rarity_census(repository)
    by_status = {status.value: sum(r.runtime_status is status for r in records) for status in RuntimeSupportStatus}
    blockers: dict[str, list[str]] = {}
    for record in records:
        if record.runtime_status is RuntimeSupportStatus.BLOCKED_BY_MECHANIC:
            for blocker in record.blockers:
                blockers.setdefault(blocker, []).append(record.operator_id)
    return {
        "eligible": len(records),
        "status_counts": by_status,
        "operators": [
            {"operator_id": r.operator_id, "name": r.name, "rarity": r.rarity,
             "profession": r.profession, "status": r.runtime_status.value,
             "blockers": list(r.blockers), "phases": list(r.available_phases),
             "max_level": r.maximum_relevant_level, "cost": r.deploy_cost,
             "block": r.block_count, "attack_interval": r.attack_interval,
             "range_ids": list(r.range_ids), "skill_ids": list(r.skill_ids)}
            for r in records
        ],
        "blocker_families": {k: sorted(v) for k, v in sorted(blockers.items())},
    }


_BENCHMARK_CODES = ("6-1", "6-2", "7-2", "7-3", "R8-1", "R8-2", "9-2", "10-2", "11-1")


def _chapter(code: str) -> int:
    if code.startswith("R8-"):
        return 8
    return int(code.split("-", 1)[0])


def stage_benchmark_census(repository: GameDataRepository) -> tuple[StageBenchmarkRecord, ...]:
    records: list[StageBenchmarkRecord] = []
    for code in _BENCHMARK_CODES:
        chapter = _chapter(code)
        # The supplied snapshot directly resolves the Chapter 6–8 selected level
        # files. Later selected stage metadata exists, but their level payload is
        # absent from the local snapshot; do not trigger an expensive repository-
        # wide filename scan or pretend their structure is known.
        if chapter >= 9:
            stage_id, raw = repository._stage_metadata(code)
            records.append(StageBenchmarkRecord(
                stage_id, raw.get("code"), chapter, None, None, None, None, 0, None, (), None, None, (), "BLOCKED",
                ("selected level payload is unavailable in this local GameData snapshot", "current APPROXIMATE_REAL adapter is bounded to main_00-01"),
                "C",
            ))
            continue
        stage = repository.get_stage(code)
        structure = stage.level_structure
        fragments = sum(len(wave.fragments) for wave in structure.waves) if structure else 0
        tile_kinds = tuple(sorted({record.tile_key.value for record in structure.tile_records if record.tile_key.value})) if structure else ()
        # Current approximate adapter is intentionally bounded to 0-1. These stages
        # are benchmark candidates, never silent execution targets.
        records.append(StageBenchmarkRecord(
            stage.stage_id, stage.code.value, chapter, stage.map_width.value, stage.map_height.value,
            stage.route_count.value, stage.wave_count.value, fragments, stage.spawn_action_count.value,
            tuple(sorted(enemy_id for enemy_id, _ in stage.enemy_references)), stage.initial_dp.value,
            stage.deployment_limit.value, tile_kinds, "BLOCKED",
            ("current APPROXIMATE_REAL adapter is bounded to main_00-01", "real spawn/range/tile/enemy-mechanic policy not established for this stage"),
            "A" if code in {"6-1", "6-2", "7-2"} else "B" if code in {"7-3", "R8-1", "R8-2"} else "C",
        ))
    return tuple(records)


def chapter_mid_late_census(repository: GameDataRepository, *, chapters: tuple[int, ...] = (6, 7, 8, 9, 10, 11)) -> tuple[ChapterStageCandidate, ...]:
    """Census ordinary stages by deterministic progression inside each chapter."""
    raw = repository._table("stage_table.json").get("stages", {})
    output: list[ChapterStageCandidate] = []
    for chapter in chapters:
        candidates = [
            (stage_id, item)
            for stage_id, item in raw.items()
            if stage_id.startswith((f"main_{chapter:02d}-", f"easy_{chapter:02d}-", f"tough_{chapter:02d}-"))
            and "#f#" not in stage_id
            and item.get("stageType") == "MAIN"
            and item.get("diffGroup") in {"NONE", "NORMAL"}
            and isinstance(item.get("code"), str)
            and item.get("levelId")
        ]
        candidates.sort(key=lambda item: (int(item[1]["code"].split("-", 1)[1]), item[0]))
        for ordinal, (stage_id, item) in enumerate(candidates, start=1):
            count = len(candidates)
            band = "EARLY" if ordinal <= max(1, count // 3) else "MID" if ordinal <= max(2, 2 * count // 3) else "LATE"
            stage = repository.get_stage(stage_id)
            structure = stage.level_structure
            tile_kinds = tuple(sorted({record.tile_key.value for record in structure.tile_records if record.tile_key.value})) if structure else ()
            output.append(ChapterStageCandidate(
                stage_id, item["code"], chapter, ordinal, band, structure is not None,
                stage.route_count.value, stage.spawn_action_count.value,
                tuple(enemy_id for enemy_id, _ in stage.enemy_references), tile_kinds,
            ))
    return tuple(output)
