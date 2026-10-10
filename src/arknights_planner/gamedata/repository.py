from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arknights_planner.models.enemy import Enemy, EnemyAbility, EnemyAttackTiming, EnemyStats
from arknights_planner.models.operator import Operator, OperatorAttributeKeyframe, OperatorPhase, OperatorStats
from arknights_planner.models.provenance import known, unknown
from arknights_planner.models.provenance import KnowledgeStatus, ValueWithSource
from arknights_planner.models.skill import AttackRange, BlackboardParameter, RangeCell, Skill, SkillLevel
from arknights_planner.models.stage import (
    ReconstructionField, Stage, StageActionData, StageCoordinate, StageFragmentData,
    StageLevelStructure, StageReconstructionReport, StageRouteData, StageTileRecord,
    StageWaveData, StageRouteCheckpointData,
)


class GameDataNotFoundError(LookupError):
    pass


class GameDataRepository:
    """Central, read-only raw-table resolver with source paths retained on every fact."""

    def __init__(self, data_root: str | Path):
        self.root = Path(data_root)
        self.excel_root = self.root / "zh_CN/gamedata/excel"
        self.levels_root = self.root / "zh_CN/gamedata/levels"
        self._tables: dict[str, Any] = {}

    def _table(self, filename: str) -> Any:
        if filename not in self._tables:
            path = self.excel_root / filename
            if not path.is_file():
                raise GameDataNotFoundError(f"Required table is absent: {path}")
            self._tables[filename] = json.loads(path.read_text(encoding="utf-8"))
        return self._tables[filename]

    def operator_ids(self) -> tuple[str, ...]:
        """Stable IDs from source table, for read-only censuses."""
        return tuple(sorted(self._table("character_table.json")))

    def stage_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._table("stage_table.json").get("stages", {})))

    @staticmethod
    def _star_rarity(raw: object, source: str, path: str) -> ValueWithSource[int | None]:
        if isinstance(raw, str) and raw.startswith("TIER_") and raw[5:].isdigit():
            return ValueWithSource(int(raw[5:]), KnowledgeStatus.DERIVABLE, 1.0, source, path)
        return unknown()

    def get_range(self, range_id: str) -> AttackRange:
        """Resolve the `range_table.json` `id`/`direction`/`grids` schema."""
        raw = self._table("range_table.json").get(range_id)
        if raw is None:
            raise GameDataNotFoundError(f"Attack range not found: {range_id}")
        source = "zh_CN/gamedata/excel/range_table.json"
        cells = tuple(
            RangeCell(
                grid["row"], grid["col"],
                known(grid["row"], source, f"$.{range_id}.grids[{index}].row"),
                known(grid["col"], source, f"$.{range_id}.grids[{index}].col"),
            )
            for index, grid in enumerate(raw.get("grids", []))
            if isinstance(grid, dict) and isinstance(grid.get("row"), int) and isinstance(grid.get("col"), int)
        )
        return AttackRange(range_id, self._field(raw, "direction", source, f"$.{range_id}.direction"), cells, source)

    def get_skill(self, skill_id: str) -> Skill:
        """Resolve level data; skill names belong to individual `levels`, not the root."""
        raw = self._table("skill_table.json").get(skill_id)
        if raw is None:
            raise GameDataNotFoundError(f"Skill not found: {skill_id}")
        source = "zh_CN/gamedata/excel/skill_table.json"
        levels: list[SkillLevel] = []
        for index, level in enumerate(raw.get("levels", [])):
            sp_data = level.get("spData") or {}
            blackboard = tuple(
                (entry.get("key", ""), entry.get("value"))
                for entry in level.get("blackboard") or []
                if isinstance(entry, dict)
            )
            prefix = f"$.{skill_id}.levels[{index}]"
            blackboard_parameters = tuple(
                BlackboardParameter(
                    self._field(entry, "key", source, f"{prefix}.blackboard[{blackboard_index}].key"),
                    self._field(entry, "value", source, f"{prefix}.blackboard[{blackboard_index}].value"),
                )
                for blackboard_index, entry in enumerate(level.get("blackboard") or [])
                if isinstance(entry, dict)
            )
            levels.append(SkillLevel(
                index,
                self._field(level, "name", source, f"{prefix}.name"),
                self._field(level, "rangeId", source, f"{prefix}.rangeId"),
                self._field(level, "skillType", source, f"{prefix}.skillType"),
                self._field(level, "durationType", source, f"{prefix}.durationType"),
                self._field(sp_data, "spType", source, f"{prefix}.spData.spType"),
                self._field(sp_data, "spCost", source, f"{prefix}.spData.spCost"),
                self._field(sp_data, "initSp", source, f"{prefix}.spData.initSp"),
                self._field(sp_data, "maxChargeTime", source, f"{prefix}.spData.maxChargeTime"),
                self._field(level, "duration", source, f"{prefix}.duration"), blackboard, blackboard_parameters,
            ))
        return Skill(skill_id, self._field(raw, "hidden", source, f"$.{skill_id}.hidden"), tuple(levels), source)

    @staticmethod
    def _field(obj: dict[str, Any], field: str, source_file: str, source_path: str):
        return known(obj[field], source_file, source_path) if field in obj else unknown()

    def get_operator(self, operator_id_or_name: str) -> Operator:
        table = self._table("character_table.json")
        match_id = next((key for key, value in table.items() if key == operator_id_or_name or value.get("name") == operator_id_or_name), None)
        if match_id is None:
            raise GameDataNotFoundError(f"Operator not found: {operator_id_or_name}")
        raw = table[match_id]
        source = "zh_CN/gamedata/excel/character_table.json"
        phases: list[OperatorPhase] = []
        for index, phase in enumerate(raw.get("phases", [])):
            raw_keyframes = [item for item in phase.get("attributesKeyFrames", []) if isinstance(item, dict)]
            minimum = raw_keyframes[0].get("data", {}) if raw_keyframes else {}
            maximum = raw_keyframes[-1].get("data", {}) if raw_keyframes else {}
            def stats(values: dict[str, Any], prefix: str) -> OperatorStats:
                return OperatorStats(
                    self._field(values, "maxHp", source, f"$.{match_id}.phases[{index}].{prefix}.maxHp"),
                    self._field(values, "atk", source, f"$.{match_id}.phases[{index}].{prefix}.atk"),
                    self._field(values, "def", source, f"$.{match_id}.phases[{index}].{prefix}.def"),
                    self._field(values, "magicResistance", source, f"$.{match_id}.phases[{index}].{prefix}.magicResistance"),
                    self._field(values, "cost", source, f"$.{match_id}.phases[{index}].{prefix}.cost"),
                    self._field(values, "blockCnt", source, f"$.{match_id}.phases[{index}].{prefix}.blockCnt"),
                    self._field(values, "baseAttackTime", source, f"$.{match_id}.phases[{index}].{prefix}.baseAttackTime"),
                    self._field(values, "respawnTime", source, f"$.{match_id}.phases[{index}].{prefix}.respawnTime"),
                )
            keyframes = tuple(
                OperatorAttributeKeyframe(
                    self._field(keyframe, "level", source, f"$.{match_id}.phases[{index}].attributesKeyFrames[{keyframe_index}].level"),
                    stats(keyframe.get("data", {}) if isinstance(keyframe.get("data"), dict) else {}, f"attributesKeyFrames[{keyframe_index}].data"),
                )
                for keyframe_index, keyframe in enumerate(raw_keyframes)
            )
            phases.append(OperatorPhase(
                index, self._field(phase, "maxLevel", source, f"$.{match_id}.phases[{index}].maxLevel"),
                stats(minimum, "min"), stats(maximum, "max"),
                self._field(phase, "rangeId", source, f"$.{match_id}.phases[{index}].rangeId"), keyframes,
            ))
        redeploy_time = phases[-1].stats_max.redeploy_time if phases else unknown()
        maintenance_cost = 0.0
        maintenance_interval = 0.0
        trait_description = str(raw.get("description") or "")
        for candidate in (raw.get("trait") or {}).get("candidates") or []:
            values = {
                str(item.get("key")): item.get("value")
                for item in candidate.get("blackboard") or []
                if isinstance(item, dict)
            }
            interval = values.get("interval")
            cost = values.get("cost")
            if (
                set(values) == {"interval", "cost"}
                and isinstance(interval, (int, float))
                and isinstance(cost, (int, float))
                and interval > 0
                and cost < 0
                and "部署费用" in trait_description
                and "消耗" in trait_description
                and "自动撤退" in trait_description
            ):
                maintenance_interval = float(interval)
                maintenance_cost = abs(float(cost))
                break
        return Operator(
            match_id, self._field(raw, "name", source, f"$.{match_id}.name"),
            self._field(raw, "profession", source, f"$.{match_id}.profession"),
            self._field(raw, "subProfessionId", source, f"$.{match_id}.subProfessionId"),
            self._field(raw, "rarity", source, f"$.{match_id}.rarity"),
            self._field(raw, "position", source, f"$.{match_id}.position"), tuple(phases), source,
            tuple(entry["skillId"] for entry in raw.get("skills", []) if isinstance(entry, dict) and "skillId" in entry),
            redeploy_time=redeploy_time,
            star_rarity=self._star_rarity(raw.get("rarity"), source, f"$.{match_id}.rarity"),
            maintenance_cost=maintenance_cost,
            maintenance_interval=maintenance_interval,
        )

    def _enemy_database(self) -> dict[str, Any]:
        cache_key = "__enemy_database__"
        if cache_key not in self._tables:
            path = self.levels_root / "enemydata/enemy_database.json"
            if not path.is_file():
                raise GameDataNotFoundError(f"Required enemy database is absent: {path}")
            self._tables[cache_key] = json.loads(path.read_text(encoding="utf-8"))
        return self._tables[cache_key]

    @staticmethod
    def _defined_value(wrapper: Any, source_file: str, source_path: str) -> ValueWithSource[Any]:
        if isinstance(wrapper, dict) and wrapper.get("m_defined") is True:
            return known(wrapper.get("m_value"), source_file, source_path)
        return unknown()

    def _enemy_key_for_name(self, enemy_id_or_name: str) -> str | None:
        handbook = self._table("enemy_handbook_table.json").get("enemyData", {})
        if enemy_id_or_name in handbook:
            return enemy_id_or_name
        if isinstance(handbook, dict):
            return next((key for key, item in handbook.items() if item.get("name") == enemy_id_or_name), None)
        return None

    def get_enemy(self, enemy_id_or_name: str, *, level: int = 0) -> Enemy:
        """Resolve actual combat stats from `levels/enemydata/enemy_database.json`.

        The handbook supplies semantic metadata; it does not hold the combat stat
        records used by a level. A non-zero `level` is accepted only when that
        database entry explicitly defines a value; inheritance/merge semantics are
        not inferred in this archaeology milestone.
        """
        enemy_id = self._enemy_key_for_name(enemy_id_or_name) or enemy_id_or_name
        entries = self._enemy_database().get("enemies", [])
        record = next((item for item in entries if item.get("Key") == enemy_id), None)
        if record is None:
            raise GameDataNotFoundError(f"Enemy not found in enemy database: {enemy_id_or_name}")
        variant = next((item for item in record.get("Value", []) if item.get("level") == level), None)
        if variant is None:
            raise GameDataNotFoundError(f"Enemy level not found: {enemy_id} level {level}")
        raw = variant.get("enemyData", {})
        attributes = raw.get("attributes", {})
        handbook = self._table("enemy_handbook_table.json").get("enemyData", {}).get(enemy_id, {})
        handbook_damage_type = next((item for item in handbook.get("damageType") or [] if isinstance(item, str)), None)
        attack_timing = self._enemy_attack_timings().get(enemy_id)
        source = "zh_CN/gamedata/levels/enemydata/enemy_database.json"
        base = f"$.enemies[Key={enemy_id}].Value[level={level}].enemyData"
        abilities: tuple[EnemyAbility, ...] = ()
        for raw_skill in raw.get("skills") or []:
            if not isinstance(raw_skill, dict) or raw_skill.get("prefabKey") != "coldattack":
                continue
            blackboard = {
                item.get("key"): item.get("value")
                for item in raw_skill.get("blackboard") or []
                if isinstance(item, dict)
            }
            abilities = (EnemyAbility(
                ability_id="coldattack", family="EVERY_NTH_ATTACK", cooldown=10.0,
                initial_cooldown=0.0, range_radius=0.0, atk_scale=1.0,
                damage_type="ARTS", attack_count_threshold=2, status_name="COLD",
                status_duration=float(blackboard.get("freeze", 0.0)),
                attack_speed_delta=-30.0,
            ),)
            break
        return Enemy(
            enemy_id, self._defined_value(raw.get("name"), source, f"{base}.name.m_value"),
            EnemyStats(
                self._defined_value(attributes.get("maxHp"), source, f"{base}.attributes.maxHp.m_value"), self._defined_value(attributes.get("atk"), source, f"{base}.attributes.atk.m_value"),
                self._defined_value(attributes.get("def"), source, f"{base}.attributes.def.m_value"), self._defined_value(attributes.get("magicResistance"), source, f"{base}.attributes.magicResistance.m_value"),
                self._defined_value(attributes.get("moveSpeed"), source, f"{base}.attributes.moveSpeed.m_value"), self._defined_value(attributes.get("baseAttackTime"), source, f"{base}.attributes.baseAttackTime.m_value"),
                self._defined_value(attributes.get("massLevel"), source, f"{base}.attributes.massLevel.m_value"), self._defined_value(raw.get("lifePointReduce"), source, f"{base}.lifePointReduce.m_value"),
                self._defined_value(raw.get("rangeRadius"), source, f"{base}.rangeRadius.m_value"),
                unknown(),
                self._field(raw, "applyWay", source, f"{base}.applyWay.m_value"),
                known("ARTS", "zh_CN/gamedata/excel/enemy_handbook_table.json", f"$.enemyData.{enemy_id}.damageType") if handbook_damage_type == "MAGIC" else known("PHYSICAL", "zh_CN/gamedata/excel/enemy_handbook_table.json", f"$.enemyData.{enemy_id}.damageType") if handbook_damage_type else unknown(),
                self._defined_value(attributes.get("hpRecoveryPerSec"), source, f"{base}.attributes.hpRecoveryPerSec.m_value"),
            ), source,
            abilities=abilities,
            attack_timing=attack_timing,
        )

    def _enemy_attack_timings(self) -> dict[str, EnemyAttackTiming]:
        cache_key = "__enemy_attack_timings__"
        if cache_key not in self._tables:
            path = Path(__file__).resolve().parents[3] / "output/enemy_attack_timing_fidelity_v1/normalized_enemy_attack_timing.json"
            self._tables[cache_key] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"records": []}
        records = self._tables[cache_key].get("records", [])
        timings: dict[str, EnemyAttackTiming] = {}
        for record in records:
            animation = record.get("attack_animation") or {}
            if animation.get("windup_seconds") is None or animation.get("recovery_seconds") is None:
                continue
            timings[record["enemy_id"]] = EnemyAttackTiming(
                animation=animation["selected_animation"],
                duration_seconds=float(animation["animation_duration_seconds"]),
                windup_seconds=float(animation["windup_seconds"]),
                recovery_seconds=float(animation["recovery_seconds"]),
                evidence_class=record.get("evidence_class", "EXACT_CLIENT_DERIVED"),
                source_url=record.get("source_url"),
                extraction_version=record.get("extraction_version", "enemy_attack_timing_v1"),
            )
        return timings

    def _stage_metadata(self, lookup: str) -> tuple[str, dict[str, Any]]:
        stages = self._table("stage_table.json").get("stages", {})
        if lookup in stages:
            return lookup, stages[lookup]
        # Several later-story codes have EASY/NORMAL/TOUGH records.  A code-only
        # lookup is deliberately deterministic and selects the ordinary NORMAL
        # main-stage data rather than whichever JSON object happened to occur first.
        candidates = [(stage_id, item) for stage_id, item in stages.items() if item.get("code") == lookup]
        preference = {"NORMAL": 0, "NONE": 1, "EASY": 2, "TOUGH": 3, "ALL": 4}
        result = min(candidates, key=lambda item: (preference.get(item[1].get("diffGroup"), 99), item[0])) if candidates else None
        if result is None:
            raise GameDataNotFoundError(f"Stage not found in stage_table.json: {lookup}")
        return result

    def _find_level_payload(self, level_id: str) -> tuple[Path | None, dict[str, Any] | None]:
        if not self.levels_root.is_dir():
            return None, None
        safe_parts = [part.lower() for part in level_id.split("/") if part and part not in {".", ".."}]
        candidate = self.levels_root.joinpath(*safe_parts).with_suffix(".json")
        if candidate.is_file():
            return candidate, json.loads(candidate.read_text(encoding="utf-8"))
        for path in self.levels_root.rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("levelId") == level_id:
                return path, payload
        return None, None

    def _coordinate(self, raw: Any, source: str, path: str) -> StageCoordinate | None:
        if not isinstance(raw, dict):
            return None
        return StageCoordinate(
            self._field(raw, "row", source, f"{path}.row"),
            self._field(raw, "col", source, f"{path}.col"),
        )

    def _stage_level_structure(self, stage_id: str, path: Path | None, payload: dict[str, Any] | None) -> StageLevelStructure | None:
        """Preserve level-file facts without mapping them to synthetic simulation rules."""
        if path is None or payload is None:
            return None
        source = str(path)
        map_data = payload.get("mapData", {}) if isinstance(payload.get("mapData"), dict) else {}
        raw_map = map_data.get("map", [])
        map_indices = tuple(
            tuple(value for value in row if isinstance(value, int))
            for row in raw_map if isinstance(row, list)
        )
        tile_records = tuple(
            StageTileRecord(
                tile_index,
                self._field(tile, "tileKey", source, f"$.mapData.tiles[{tile_index}].tileKey"),
                self._field(tile, "heightType", source, f"$.mapData.tiles[{tile_index}].heightType"),
                self._field(tile, "buildableType", source, f"$.mapData.tiles[{tile_index}].buildableType"),
                self._field(tile, "passableMask", source, f"$.mapData.tiles[{tile_index}].passableMask"),
                self._field(tile, "playerSideMask", source, f"$.mapData.tiles[{tile_index}].playerSideMask"),
            )
            for tile_index, tile in enumerate(map_data.get("tiles", [])) if isinstance(tile, dict)
        )
        routes = tuple(
            StageRouteData(
                route_index,
                self._coordinate(route.get("startPosition"), source, f"$.routes[{route_index}].startPosition"),
                self._coordinate(route.get("endPosition"), source, f"$.routes[{route_index}].endPosition"),
                tuple(
                    StageRouteCheckpointData(
                        self._field(checkpoint, "type", source, f"$.routes[{route_index}].checkpoints[{checkpoint_index}].type"),
                        self._field(checkpoint, "time", source, f"$.routes[{route_index}].checkpoints[{checkpoint_index}].time"),
                        self._coordinate(
                            checkpoint.get("position", checkpoint), source,
                            f"$.routes[{route_index}].checkpoints[{checkpoint_index}].position",
                        ),
                    )
                    for checkpoint_index, checkpoint in enumerate(route.get("checkpoints") or [])
                    if isinstance(checkpoint, dict)
                ),
                source,
            )
            for route_index, route in enumerate(payload.get("routes", [])) if isinstance(route, dict)
        )
        waves = tuple(
            StageWaveData(
                wave_index,
                self._field(wave, "preDelay", source, f"$.waves[{wave_index}].preDelay"),
                self._field(wave, "postDelay", source, f"$.waves[{wave_index}].postDelay"),
                tuple(
                    StageFragmentData(
                        fragment_index,
                        self._field(fragment, "preDelay", source, f"$.waves[{wave_index}].fragments[{fragment_index}].preDelay"),
                        tuple(
                            StageActionData(
                                action_index,
                                self._field(action, "actionType", source, f"$.waves[{wave_index}].fragments[{fragment_index}].actions[{action_index}].actionType"),
                                self._field(action, "key", source, f"$.waves[{wave_index}].fragments[{fragment_index}].actions[{action_index}].key"),
                                self._field(action, "count", source, f"$.waves[{wave_index}].fragments[{fragment_index}].actions[{action_index}].count"),
                                self._field(action, "preDelay", source, f"$.waves[{wave_index}].fragments[{fragment_index}].actions[{action_index}].preDelay"),
                                self._field(action, "interval", source, f"$.waves[{wave_index}].fragments[{fragment_index}].actions[{action_index}].interval"),
                                self._field(action, "routeIndex", source, f"$.waves[{wave_index}].fragments[{fragment_index}].actions[{action_index}].routeIndex"),
                            )
                            for action_index, action in enumerate(fragment.get("actions", [])) if isinstance(action, dict)
                        ),
                    )
                    for fragment_index, fragment in enumerate(wave.get("fragments", [])) if isinstance(fragment, dict)
                ),
            )
            for wave_index, wave in enumerate(payload.get("waves", [])) if isinstance(wave, dict)
        )
        return StageLevelStructure(map_indices, tile_records, routes, waves, source)

    def get_stage_level_structure(self, stage_id_or_code: str) -> StageLevelStructure:
        """Return the source-backed level hierarchy without flattening spawn timing."""
        _, meta = self._stage_metadata(stage_id_or_code)
        level_id = meta.get("levelId")
        path, payload = self._find_level_payload(level_id) if isinstance(level_id, str) else (None, None)
        structure = self._stage_level_structure(stage_id_or_code, path, payload)
        if structure is None:
            raise GameDataNotFoundError(f"Level data not found for stage: {stage_id_or_code}")
        return structure

    def get_stage_level_document(self, stage_id_or_code: str) -> tuple[str, dict[str, Any], Path, dict[str, Any]]:
        """Return raw stage metadata and the corresponding level JSON document."""
        stage_id, metadata = self._stage_metadata(stage_id_or_code)
        level_id = metadata.get("levelId")
        path, payload = self._find_level_payload(level_id) if isinstance(level_id, str) else (None, None)
        if path is None or payload is None:
            raise GameDataNotFoundError(f"Level data not found for stage: {stage_id_or_code}")
        return stage_id, metadata, path, payload

    def get_stage(self, stage_id_or_code: str) -> Stage:
        stage_id, meta = self._stage_metadata(stage_id_or_code)
        level_id = meta.get("levelId")
        path, payload = self._find_level_payload(level_id) if isinstance(level_id, str) else (None, None)
        source = "zh_CN/gamedata/excel/stage_table.json"
        map_data = (payload or {}).get("mapData", {})
        map_rows = map_data.get("map", [])
        routes = (payload or {}).get("routes", [])
        waves = (payload or {}).get("waves", [])
        refs = (payload or {}).get("enemyDbRefs", [])
        structure = self._stage_level_structure(stage_id, path, payload)
        spawn_actions = [
            action for wave in waves for fragment in wave.get("fragments", []) for action in fragment.get("actions", [])
            if action.get("actionType") == "SPAWN"
        ]
        level_source = str(path) if path else source
        width = max((len(row) for row in map_rows if isinstance(row, list)), default=None)
        height = len(map_rows) if isinstance(map_rows, list) else None
        max_slot = meta.get("maxSlot")
        if isinstance(max_slot, int) and max_slot > 0:
            squad_size_limit: ValueWithSource[int | None] = known(
                max_slot, source, f"$.stages.{stage_id}.maxSlot"
            )
        elif max_slot == -1:
            squad_size_limit = ValueWithSource(
                12,
                KnowledgeStatus.APPROXIMATED,
                0.80,
                source,
                f"$.stages.{stage_id}.maxSlot == -1; current simulator-supported normal squad bound",
            )
        else:
            squad_size_limit = unknown()
        return Stage(
            stage_id, self._field(meta, "code", source, f"$.stages.{stage_id}.code"), self._field(meta, "name", source, f"$.stages.{stage_id}.name"),
            ValueWithSource(width, KnowledgeStatus.DERIVABLE, 1.0, level_source, "$.mapData.map") if path and width is not None else unknown(),
            ValueWithSource(height, KnowledgeStatus.DERIVABLE, 1.0, level_source, "$.mapData.map") if path and height is not None else unknown(),
            known(len(routes), level_source, "$.routes") if path else unknown(), known(len(waves), level_source, "$.waves") if path else unknown(), str(path) if path else None,
            self._field(meta, "levelId", source, f"$.stages.{stage_id}.levelId"),
            tuple((item["id"], item.get("level", 0)) for item in refs if isinstance(item, dict) and "id" in item),
            known(len(spawn_actions), level_source, "$.waves[*].fragments[*].actions[actionType=SPAWN]") if path else unknown(),
            self._field((payload or {}).get("options", {}), "initialCost", level_source, "$.options.initialCost"),
            self._field((payload or {}).get("options", {}), "characterLimit", level_source, "$.options.characterLimit"),
            squad_size_limit=squad_size_limit,
            level_structure=structure,
            max_life_points=self._field((payload or {}).get("options", {}), "maxLifePoint", level_source, "$.options.maxLifePoint"),
            cost_increase_time=self._field((payload or {}).get("options", {}), "costIncreaseTime", level_source, "$.options.costIncreaseTime"),
        )

    def stage_reconstruction_report(self, stage_id_or_code: str) -> StageReconstructionReport:
        stage = self.get_stage(stage_id_or_code)
        def field(name: str, value) -> ReconstructionField:
            return ReconstructionField(name, value.status, value.source_file)
        return StageReconstructionReport(stage.stage_id, (
            field("Map", stage.map_width),
            ReconstructionField("Enemy roster", KnowledgeStatus.KNOWN if stage.enemy_references else KnowledgeStatus.UNKNOWN, stage.raw_source_file),
            field("Enemy routes", stage.route_count), field("Waves", stage.wave_count), field("Spawn events", stage.spawn_action_count),
            ReconstructionField("Spawn timeline semantics", KnowledgeStatus.UNKNOWN, stage.raw_source_file),
            ReconstructionField("Operator stats", KnowledgeStatus.KNOWN, "character_table.json"),
            ReconstructionField("Enemy stats", KnowledgeStatus.KNOWN, "levels/enemydata/enemy_database.json"),
            ReconstructionField("Projectile speed", KnowledgeStatus.UNKNOWN), ReconstructionField("Attack windup", KnowledgeStatus.UNKNOWN),
            ReconstructionField("Damage frame", KnowledgeStatus.UNKNOWN), ReconstructionField("Event ordering", KnowledgeStatus.UNKNOWN),
        ))
