"""Task-aware stage eligibility derived from GameData stage semantics."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


SUPPORTED_TILE_KEYS = frozenset({
    "tile_start",
    "tile_floor",
    "tile_road",
    "tile_end",
    "tile_wall",
    "tile_forbidden",
    "tile_fence",
    "tile_fence_bound",
})


class PlannerTaskType(str, Enum):
    AUTONOMOUS_TEAM_SELECTION = "AUTONOMOUS_TEAM_SELECTION"
    TIMING_ONLY_PLANNING = "TIMING_ONLY_PLANNING"
    SIMULATOR_FIDELITY_TEST = "SIMULATOR_FIDELITY_TEST"


@dataclass(frozen=True)
class ForcedOperatorRecord:
    operator_id: str
    source: str
    phase: str | None = None
    level: int | None = None
    skill_index: int | None = None
    main_skill_level: int | None = None


@dataclass(frozen=True)
class StageEligibility:
    stage_id: str
    display_stage_code: str | None
    free_team_selection: bool
    fixed_squad: bool
    preset_deployed_units: bool
    forced_operators: tuple[ForcedOperatorRecord, ...]
    forced_operator_levels_or_skills: tuple[ForcedOperatorRecord, ...]
    tutorial_or_story_special: bool
    normal_deployment_available: bool
    squad_size_limit: int | None
    deployment_limit: int | None
    simulator_supported: bool
    unsupported_mechanics: tuple[str, ...]
    source: str
    provenance: dict[str, str]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def eligible_for(
        self,
        task_type: PlannerTaskType | str,
        *,
        require_simulator_support: bool = True,
    ) -> "StageTaskEligibility":
        task = PlannerTaskType(task_type)
        semantic_reasons: list[str] = []
        runtime_reasons: list[str] = []
        if task is PlannerTaskType.AUTONOMOUS_TEAM_SELECTION:
            if self.fixed_squad:
                semantic_reasons.append("FIXED_SQUAD")
            if self.preset_deployed_units:
                semantic_reasons.append("PRESET_DEPLOYED_UNITS")
            if self.forced_operators:
                semantic_reasons.append("FORCED_OPERATORS")
            if self.tutorial_or_story_special:
                semantic_reasons.append("TUTORIAL_OR_STORY_SPECIAL")
            if not self.normal_deployment_available:
                semantic_reasons.append("NORMAL_DEPLOYMENT_UNAVAILABLE")
        elif task is PlannerTaskType.TIMING_ONLY_PLANNING:
            if self.tutorial_or_story_special and not (self.fixed_squad or self.preset_deployed_units):
                semantic_reasons.append("TUTORIAL_OR_STORY_SPECIAL")
            if not self.normal_deployment_available and not (self.fixed_squad or self.preset_deployed_units):
                semantic_reasons.append("NORMAL_DEPLOYMENT_UNAVAILABLE")

        if require_simulator_support:
            if not self.simulator_supported:
                runtime_reasons.append("SIMULATOR_UNSUPPORTED")
            runtime_reasons.extend(self.unsupported_mechanics)

        reasons = tuple(dict.fromkeys((*semantic_reasons, *runtime_reasons)))
        return StageTaskEligibility(
            stage_id=self.stage_id,
            display_stage_code=self.display_stage_code,
            task_type=task.value,
            eligible=not reasons,
            semantic_eligible=not semantic_reasons,
            simulator_ready=not runtime_reasons,
            rejection_reasons=reasons,
            source=self.source,
        )


@dataclass(frozen=True)
class StageTaskEligibility:
    stage_id: str
    display_stage_code: str | None
    task_type: str
    eligible: bool
    semantic_eligible: bool
    simulator_ready: bool
    rejection_reasons: tuple[str, ...]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StageEligibilityAnalyzer:
    """Read stage and level JSON semantics without stage-specific special cases."""

    VERSION = "stage-eligibility-v1"

    def analyze(self, repository, stage_id_or_code: str) -> StageEligibility:
        stage_id, metadata, path, payload = repository.get_stage_level_document(stage_id_or_code)
        options = payload.get("options") or {}
        predefines = payload.get("predefines") or {}
        hard_predefines = payload.get("hardPredefines") or {}
        character_cards = self._rows(predefines, "characterCards") + self._rows(hard_predefines, "characterCards")
        character_insts = self._rows(predefines, "characterInsts") + self._rows(hard_predefines, "characterInsts")
        forced = tuple(dict.fromkeys((
            *self._forced_records(character_cards, "characterCards"),
            *self._forced_records(character_insts, "characterInsts"),
        )))
        forced_ids = {item.operator_id for item in forced}
        forced_details = forced

        function_mask = options.get("functionDisableMask")
        normal_deployment = (
            options.get("characterLimit", 0) > 0
            and function_mask in {None, "NONE"}
            and not bool(metadata.get("isStoryOnly"))
        )
        predefined_metadata = bool(metadata.get("isPredefined") or metadata.get("isHardPredefined"))
        fixed_squad = predefined_metadata or bool(character_cards)
        preset_deployed_units = bool(character_insts)
        free_team_selection = (
            not fixed_squad
            and not preset_deployed_units
            and not forced_ids
            and normal_deployment
            and not bool(options.get("isTrainingLevel"))
        )
        tutorial_or_story_special = (
            bool(options.get("isTrainingLevel"))
            or bool(options.get("isHardTrainingLevel"))
            or bool(metadata.get("isStoryOnly"))
            or function_mask not in {None, "NONE"}
        )

        tile_keys = {
            record.tile_key.value
            for record in repository.get_stage(stage_id).level_structure.tile_records
            if record.tile_key.value
        }
        unsupported: list[str] = []
        unsupported.extend(f"UNSUPPORTED_TILE:{key}" for key in sorted(tile_keys - SUPPORTED_TILE_KEYS))
        if "tile_flystart" in tile_keys:
            unsupported.append("AERIAL_ROUTE_NOT_REPRESENTED")
        if forced_ids or preset_deployed_units:
            unsupported.append("PREDEFINED_UNITS_NOT_MODELED")
        if bool(metadata.get("bossMark")):
            unsupported.append("BOSS_STAGE_EXCLUDED_FROM_FIRST_WIN_FEASIBILITY")
        if bool(metadata.get("isStoryOnly")):
            unsupported.append("STORY_ONLY_STAGE")

        stage = repository.get_stage(stage_id)
        squad_size_limit = (
            int(stage.squad_size_limit.value)
            if stage.squad_size_limit.value is not None
            else None
        )
        character_limit = options.get("characterLimit")
        deployment_limit = int(character_limit) if isinstance(character_limit, int) else None
        simulator_supported = not unsupported
        return StageEligibility(
            stage_id=stage_id,
            display_stage_code=metadata.get("code"),
            free_team_selection=free_team_selection,
            fixed_squad=fixed_squad,
            preset_deployed_units=preset_deployed_units,
            forced_operators=forced,
            forced_operator_levels_or_skills=forced_details,
            tutorial_or_story_special=tutorial_or_story_special,
            normal_deployment_available=normal_deployment,
            squad_size_limit=squad_size_limit,
            deployment_limit=deployment_limit,
            simulator_supported=simulator_supported,
            unsupported_mechanics=tuple(unsupported),
            source=str(path),
            provenance={
                "stage_metadata": "GameData stage_table.json",
                "level_options": "GameData level JSON options",
                "squad_size_limit": (
                    "explicit stage_table.json maxSlot when positive; maxSlot=-1 uses the "
                    "current simulator-supported normal bound of 12, not an unverified client-default claim"
                ),
                "predefines": "GameData level JSON predefines/hardPredefines",
                "simulator_support": "supported tile keys, predefined-unit modeling, story/boss flags, and deployment controls",
            },
            confidence=0.95 if payload is not None else 0.5,
        )

    @staticmethod
    def _rows(section: dict[str, Any], key: str) -> list[dict[str, Any]]:
        value = section.get(key)
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _forced_records(rows: list[dict[str, Any]], source: str) -> tuple[ForcedOperatorRecord, ...]:
        output: list[ForcedOperatorRecord] = []
        for row in rows:
            instance = row.get("inst") or {}
            operator_id = instance.get("characterKey")
            if not operator_id:
                continue
            output.append(ForcedOperatorRecord(
                operator_id=operator_id,
                source=source,
                phase=instance.get("phase"),
                level=instance.get("level") if isinstance(instance.get("level"), int) else None,
                skill_index=row.get("skillIndex") if isinstance(row.get("skillIndex"), int) else None,
                main_skill_level=row.get("mainSkillLvl") if isinstance(row.get("mainSkillLvl"), int) else None,
            ))
        return tuple(output)


class StageIneligibleError(RuntimeError):
    """Raised when a planner task is semantically incompatible with a stage."""
