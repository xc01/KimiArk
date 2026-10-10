"""Opt-in approximations for one bounded real-data execution path.

This module is intentionally separate from :mod:`real_simulation`: strict real
compatibility remains a refusal gate, while this adapter requires a visible policy
before converting source-backed 0-1 facts into existing simulator inputs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from math import ceil
from typing import Any

from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.enemy import Enemy
from arknights_planner.models.operator import Operator, OperatorAttributeKeyframe, OperatorPhase
from arknights_planner.models.runtime import CombatOutputType
from arknights_planner.models.provenance import KnowledgeStatus
from arknights_planner.models.route import Route, RouteWait, Waypoint
from arknights_planner.models.simulation import SimulationResult, SimulationRunMetadata
from arknights_planner.models.stage import BattleDevice, SpawnEvent, Stage, StageMap, StageTileRecord, Tile
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator

from .real_simulation import AdaptedRealEnemy, AdaptedRealOperator, AdaptedRealStage, RealSimulationAdapter
from .low_rarity_skill import LowRarityBlackboardEffectInterpreter, RealSkillSupport
from arknights_planner.adapters.normal_low_star import (
    deployment_heal_all_value,
    deployment_sp_bonus,
)
from arknights_planner.benchmark.census import low_rarity_census, RuntimeSupportStatus


class RealExecutionMode(str, Enum):
    STRICT_REAL = "STRICT_REAL"
    APPROXIMATE_REAL = "APPROXIMATE_REAL"


class RangeTransformPolicy(str, Enum):
    SYNTHETIC_90_DEGREE_ROW_COL = "SYNTHETIC_90_DEGREE_ROW_COL"


class SpawnSchedulePolicy(str, Enum):
    CUMULATIVE_HIERARCHICAL_PREDELAYS = "CUMULATIVE_HIERARCHICAL_PREDELAYS"
    HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED = "HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED"


class AttackTimingPolicy(str, Enum):
    ZERO_WINDUP_ZERO_EXTRA_RECOVERY = "ZERO_WINDUP_ZERO_EXTRA_RECOVERY"


class ProjectileTimingPolicy(str, Enum):
    INSTANT_PROJECTILE = "INSTANT_PROJECTILE"


class StageCoordinatePolicy(str, Enum):
    REVERSED_SERIALIZED_MAP_ROW = "REVERSED_SERIALIZED_MAP_ROW"


class DamageModelPolicy(str, Enum):
    EXISTING_SYNTHETIC_PHYSICAL_DAMAGE = "EXISTING_SYNTHETIC_PHYSICAL_DAMAGE"


class NaturalDpPolicy(str, Enum):
    ONE_DP_PER_COST_INCREASE_INTERVAL = "ONE_DP_PER_COST_INCREASE_INTERVAL"


class RouteWaitPolicy(str, Enum):
    WAIT_FOR_SECONDS_AT_PREVIOUS_MOVE_NODE = "WAIT_FOR_SECONDS_AT_PREVIOUS_MOVE_NODE"


class EnemyRangePolicy(str, Enum):
    SOURCE_RANGE_RADIUS_NEAREST_OPERATOR = "SOURCE_RANGE_RADIUS_NEAREST_OPERATOR"


@dataclass(frozen=True)
class RealSimulationApproximationPolicy:
    """Small fixed policy set required for the first 0-1 execution only."""

    range_transform: RangeTransformPolicy
    spawn_schedule: SpawnSchedulePolicy
    attack_timing: AttackTimingPolicy
    projectile_timing: ProjectileTimingPolicy
    stage_coordinates: StageCoordinatePolicy
    damage_model: DamageModelPolicy
    natural_dp: NaturalDpPolicy
    route_wait: RouteWaitPolicy = RouteWaitPolicy.WAIT_FOR_SECONDS_AT_PREVIOUS_MOVE_NODE
    enemy_range: EnemyRangePolicy = EnemyRangePolicy.SOURCE_RANGE_RADIUS_NEAREST_OPERATOR

    @classmethod
    def main_00_01(cls) -> "RealSimulationApproximationPolicy":
        return cls(
            RangeTransformPolicy.SYNTHETIC_90_DEGREE_ROW_COL,
            SpawnSchedulePolicy.CUMULATIVE_HIERARCHICAL_PREDELAYS,
            AttackTimingPolicy.ZERO_WINDUP_ZERO_EXTRA_RECOVERY,
            ProjectileTimingPolicy.INSTANT_PROJECTILE,
            StageCoordinatePolicy.REVERSED_SERIALIZED_MAP_ROW,
            DamageModelPolicy.EXISTING_SYNTHETIC_PHYSICAL_DAMAGE,
            NaturalDpPolicy.ONE_DP_PER_COST_INCREASE_INTERVAL,
        )

    @classmethod
    def m11_second_quantized(cls) -> "RealSimulationApproximationPolicy":
        """Bounded M11 policy: hierarchy-derived integer-second spawn schedule.

        This does not claim to reproduce client fragment scheduling.  It advances
        a fragment cursor by the latest represented spawn in that fragment, then
        emits each resulting time at the beginning of its integer second.
        """
        return cls(
            RangeTransformPolicy.SYNTHETIC_90_DEGREE_ROW_COL,
            SpawnSchedulePolicy.HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED,
            AttackTimingPolicy.ZERO_WINDUP_ZERO_EXTRA_RECOVERY,
            ProjectileTimingPolicy.INSTANT_PROJECTILE,
            StageCoordinatePolicy.REVERSED_SERIALIZED_MAP_ROW,
            DamageModelPolicy.EXISTING_SYNTHETIC_PHYSICAL_DAMAGE,
            NaturalDpPolicy.ONE_DP_PER_COST_INCREASE_INTERVAL,
        )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(item.value for item in (
            self.range_transform, self.spawn_schedule, self.attack_timing,
            self.projectile_timing, self.stage_coordinates, self.damage_model,
            self.natural_dp, self.route_wait, self.enemy_range,
        ))

    @property
    def cache_identity(self) -> tuple[str, ...]:
        """Version the bounded policy contract used by approximate-run caches."""
        # Economy runtime semantics changed in M14.9; previous in-memory or
        # persisted search entries must not share this identity.
        return ("real-simulation-approximation-policy-v2-economy", *self.names)


class ApproximateRealExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RealOperatorSelection:
    operator_id: str
    phase_index: int
    level: int
    tile: tuple[int, int]
    direction: str
    deploy_time: float


@dataclass(frozen=True)
class RealOperatorConfiguration:
    """Fixed, exact-keyframe operator data without a deployment decision."""

    operator_id: str
    phase_index: int
    level: int
    skill_level_index: int = -1


@dataclass(frozen=True)
class ExecutableOperatorRecord:
    operator_id: str
    name: str | None
    rarity: int
    profession: str | None
    position: str | None
    phase_index: int
    level: int
    status: str
    blockers: tuple[str, ...] = ()
    configuration: RealOperatorConfiguration | None = None


@dataclass(frozen=True)
class M12LoadoutPolicy:
    """Deterministic attainable profile: highest exact keyframe in phase 0."""
    phase_index: int = 0
    skill_level_index: int = -1

    def configuration(self, repository: GameDataRepository, operator_id: str) -> RealOperatorConfiguration:
        op = repository.get_operator(operator_id)
        phase = op.phases[self.phase_index]
        levels = [k.level.value for k in phase.keyframes if k.level.value is not None]
        if not levels:
            raise ApproximateRealExecutionError(f"no exact phase-{self.phase_index} keyframe for {operator_id}")
        return RealOperatorConfiguration(operator_id, self.phase_index, max(levels), self.skill_level_index)

    @classmethod
    def phase_zero_max(cls) -> "M12LoadoutPolicy":
        return cls(0, -1)


@dataclass(frozen=True)
class M13LoadoutPolicy:
    """Fixed high-progression profile for bounded low-rarity research.

    Selects the highest available phase and its highest *exact* source
    keyframe.  No stat interpolation, trust, or potential bonuses are added.
    Skills use the highest source level (``skill_level_index=-1``), resolved by
    the adapter.  This policy is deterministic and shared across all rarities.
    """

    skill_level_index: int = -1

    def configuration(self, repository: GameDataRepository, operator_id: str) -> RealOperatorConfiguration:
        op = repository.get_operator(operator_id)
        phases = [phase for phase in op.phases if phase.keyframes]
        if not phases:
            raise ApproximateRealExecutionError(f"no exact keyframe for {operator_id}")
        phase = max(phases, key=lambda item: item.phase_index)
        levels = [key.level.value for key in phase.keyframes if key.level.value is not None]
        if not levels:
            raise ApproximateRealExecutionError(f"no exact level keyframe for {operator_id}")
        return RealOperatorConfiguration(operator_id, phase.phase_index, max(levels), self.skill_level_index)

    @classmethod
    def highest_legal(cls) -> "M13LoadoutPolicy":
        return cls(-1)


@dataclass(frozen=True)
class MappedRealTile:
    coordinate: tuple[int, int]
    source_tile_index: int
    source_tile_key: str | None
    source_buildable_type: str | None
    simulator_category: str
    status: KnowledgeStatus


@dataclass(frozen=True)
class ApproximatedSpawn:
    wave_index: int
    fragment_index: int
    action_index: int
    enemy_id: str
    enemy_level: int
    route_id: str
    time: float
    count: int
    interval: float


@dataclass(frozen=True)
class ApproximateRealFixture:
    stage: Stage
    operators: dict[str, Operator]
    enemies: dict[str, Enemy]
    tile_mappings: tuple[MappedRealTile, ...]
    spawn_timeline: tuple[ApproximatedSpawn, ...]
    approximations_used: tuple[str, ...]
    ignored_real_skill_data: tuple[str, ...]


@dataclass(frozen=True)
class ApproximateExecutionReport:
    """Execution-mode decision distinct from the unchanged strict compatibility report."""

    mode: RealExecutionMode
    simulator_executable: bool
    approximations_used: tuple[str, ...]
    strategy_uses_real_skill: bool


@dataclass(frozen=True)
class ApproximateRealRun:
    fixture: ApproximateRealFixture
    strategy: Strategy
    result: SimulationResult
    execution_report: ApproximateExecutionReport


class ApproximateRealSimulationAdapter:
    """Build one simulator fixture only after a complete explicit policy is supplied."""

    def __init__(self, repository: GameDataRepository):
        self.repository = repository
        self.strict_adapter = RealSimulationAdapter(repository)

    @staticmethod
    def _number(value, label: str) -> float:
        if value.status is KnowledgeStatus.UNKNOWN or value.value is None:
            raise ApproximateRealExecutionError(f"{label} is {value.status.value}; no approximation was selected")
        return float(value.value)

    @staticmethod
    def _coordinate(route_coordinate, *, map_height: int) -> Waypoint:
        if route_coordinate is None or route_coordinate.row.value is None or route_coordinate.col.value is None:
            raise ApproximateRealExecutionError("real route coordinate is UNKNOWN")
        # Route positions already use field (bottom-left) coordinates. Only
        # serialized map-array row indices need inversion in _map_tiles.
        return Waypoint(float(route_coordinate.col.value), float(route_coordinate.row.value))

    def _map_tiles(self, stage: AdaptedRealStage, policy: RealSimulationApproximationPolicy) -> tuple[Tile, tuple[MappedRealTile, ...]]:
        if stage.structure is None:
            raise ApproximateRealExecutionError("stage structure is unavailable")
        if policy.stage_coordinates is not StageCoordinatePolicy.REVERSED_SERIALIZED_MAP_ROW:
            raise ApproximateRealExecutionError("no implementation for the selected stage-coordinate policy")
        records = {record.tile_index: record for record in stage.structure.tile_records}
        height = len(stage.structure.map_indices)
        runtime_tiles: list[Tile] = []
        mappings: list[MappedRealTile] = []
        for serialized_row, indices in enumerate(stage.structure.map_indices):
            for col, tile_index in enumerate(indices):
                record = records.get(tile_index)
                category, status = self._tile_category(record)
                coordinate = (col, height - 1 - serialized_row)
                runtime_tiles.append(Tile(
                    *coordinate,
                    buildable=category in {"GROUND", "HIGH_GROUND"},
                    tile_kind=category,
                ))
                mappings.append(MappedRealTile(
                    coordinate, tile_index,
                    record.tile_key.value if record else None,
                    record.buildable_type.value if record else None,
                    category, status,
                ))
        return tuple(runtime_tiles), tuple(mappings)

    @staticmethod
    def _tile_category(record: StageTileRecord | None) -> tuple[str, KnowledgeStatus]:
        if record is None or record.buildable_type.status is KnowledgeStatus.UNKNOWN:
            return "UNKNOWN", KnowledgeStatus.UNKNOWN
        mapping = {"MELEE": "GROUND", "RANGED": "HIGH_GROUND", "NONE": "NON_DEPLOYABLE"}
        category = mapping.get(record.buildable_type.value)
        return (category, KnowledgeStatus.KNOWN) if category else ("UNKNOWN", KnowledgeStatus.UNKNOWN)

    def _convert_routes(self, stage: AdaptedRealStage) -> tuple[Route, ...]:
        if stage.structure is None:
            raise ApproximateRealExecutionError("stage structure is unavailable")
        map_height = len(stage.structure.map_indices)
        routes: list[Route] = []
        for route in stage.structure.routes:
            points: list[Waypoint] = [self._coordinate(route.start_position, map_height=map_height)]
            waits: list[RouteWait] = []
            for checkpoint in route.checkpoints:
                if checkpoint.checkpoint_type.value == "MOVE":
                    if checkpoint.position is None:
                        raise ApproximateRealExecutionError("MOVE checkpoint position is UNKNOWN")
                    points.append(self._coordinate(checkpoint.position, map_height=map_height))
                elif checkpoint.checkpoint_type.value == "WAIT_FOR_SECONDS":
                    if checkpoint.time.value is None:
                        raise ApproximateRealExecutionError("WAIT_FOR_SECONDS checkpoint time is UNKNOWN")
                    # The `position` stored on this checkpoint is not interpreted
                    # as a movement node.  This opt-in policy pauses at the last
                    # reached MOVE node; the source checkpoint type/time stay
                    # preserved in StageLevelStructure for later replacement.
                    distance = Route(f"route-{route.route_index}-prefix", tuple(points)).length if len(points) > 1 else 0.0
                    waits.append(RouteWait(distance, float(checkpoint.time.value)))
                else:
                    raise ApproximateRealExecutionError(f"unsupported route checkpoint type: {checkpoint.checkpoint_type.value!r}")
            points.append(self._coordinate(route.end_position, map_height=map_height))
            routes.append(Route(f"route-{route.route_index}", tuple(points), tuple(waits)))
        return tuple(routes)

    def _devices(self, stage: AdaptedRealStage) -> tuple[BattleDevice, ...]:
        stage_id = stage.stage.stage_id
        _, _, path, payload = self.repository.get_stage_level_document(stage_id)
        characters = self.repository._table("character_table.json")
        devices: list[BattleDevice] = []
        for index, token in enumerate(payload.get("predefines", {}).get("tokenInsts") or []):
            template_id = (token.get("inst") or {}).get("characterKey")
            raw = characters.get(template_id, {})
            attributes = ((raw.get("phases") or [{}])[0].get("attributesKeyFrames") or [{}])[0].get("data") or {}
            required = ("maxHp", "def", "magicResistance", "tauntLevel")
            if not all(key in attributes for key in required):
                raise ApproximateRealExecutionError(f"device {template_id} lacks required source attributes")
            position = token.get("position") or {}
            map_height = len((payload.get("mapData") or {}).get("map") or [])
            if "row" not in position or "col" not in position or map_height == 0:
                raise ApproximateRealExecutionError(f"device {template_id} position is UNKNOWN")
            devices.append(BattleDevice(
                device_id=token.get("alias") or f"{template_id}#{index}",
                template_id=template_id,
                tile=(int(position["col"]), int(position["row"])),
                hp=float(attributes["maxHp"]),
                defense=float(attributes["def"]),
                magic_resistance=float(attributes["magicResistance"]),
                taunt_level=int(attributes["tauntLevel"]),
                ordinary_targetable=template_id == "trap_020_roadblock",
                faction="ENEMY",
            ))
        return tuple(devices)

    def _approximate_spawns(self, stage: AdaptedRealStage, enemy_levels: dict[str, int], policy: RealSimulationApproximationPolicy) -> tuple[ApproximatedSpawn, ...]:
        if stage.structure is None:
            raise ApproximateRealExecutionError("stage structure is unavailable")
        if policy.spawn_schedule not in {
            SpawnSchedulePolicy.CUMULATIVE_HIERARCHICAL_PREDELAYS,
            SpawnSchedulePolicy.HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED,
        }:
            raise ApproximateRealExecutionError("no implementation for the selected spawn-schedule policy")
        timeline: list[ApproximatedSpawn] = []
        wave_cursor = 0.0
        for wave in stage.structure.waves:
            wave_cursor += self._number(wave.pre_delay, f"wave {wave.wave_index} preDelay")
            fragment_cursor = wave_cursor
            for fragment in wave.fragments:
                fragment_cursor += self._number(fragment.pre_delay, f"fragment {fragment.fragment_index} preDelay")
                fragment_end = fragment_cursor
                for action in fragment.actions:
                    if action.action_type.value != "SPAWN":
                        continue
                    enemy_id = action.key.value
                    if not enemy_id or enemy_id not in enemy_levels:
                        raise ApproximateRealExecutionError(f"SPAWN action references unresolved enemy: {enemy_id!r}")
                    if action.route_index.value is None:
                        raise ApproximateRealExecutionError(f"SPAWN route index is {action.route_index.status.value}")
                    action_time = fragment_cursor + self._number(action.pre_delay, "action preDelay")
                    if policy.spawn_schedule is SpawnSchedulePolicy.HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED:
                        # The retained values are source-backed, but their exact
                        # sub-second/client accumulation is not.  The M11 policy
                        # uses the next integer-second boundary explicitly.
                        action_time = float(ceil(action_time))
                    timeline.append(ApproximatedSpawn(
                        wave.wave_index, fragment.fragment_index, action.action_index,
                        enemy_id, enemy_levels[enemy_id], f"route-{action.route_index.value}",
                        action_time,
                        int(self._number(action.count, "SPAWN count")),
                        self._number(action.interval, "SPAWN interval"),
                    ))
                    # Source `interval` specifies repetitions.  Its relationship
                    # to the next fragment is not recovered, so this is an opt-in
                    # bounded fragment-duration approximation.
                    fragment_end = max(fragment_end, fragment_cursor + self._number(action.pre_delay, "action preDelay") + max(0, int(self._number(action.count, "SPAWN count")) - 1) * self._number(action.interval, "SPAWN interval"))
                if policy.spawn_schedule is SpawnSchedulePolicy.HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED:
                    fragment_cursor = float(ceil(fragment_end))
            wave_cursor = fragment_cursor + self._number(wave.post_delay, f"wave {wave.wave_index} postDelay")
        return tuple(timeline)

    def _runtime_operator(self, adapted: AdaptedRealOperator, *, interpreted_skill=None, deployment_cost_delta: float = 0.0) -> Operator:
        if adapted.exact_keyframe is None or adapted.attack_range is None:
            raise ApproximateRealExecutionError("operator lacks exact keyframe or real range")
        stats = adapted.exact_keyframe.stats
        phase = OperatorPhase(
            adapted.phase_index, adapted.exact_keyframe.level, stats, stats,
            adapted.operator.phases[adapted.phase_index].range_id, (adapted.exact_keyframe,),
        )
        return replace(
            adapted.operator,
            phases=(phase,),
            attack_range=tuple((cell.row, cell.col) for cell in adapted.attack_range.cells),
            synthetic_skill=interpreted_skill,
            combat_output=(
                CombatOutputType.HEAL
                if adapted.operator.profession.value == "MEDIC"
                else CombatOutputType.DAMAGE
            ),
            redeploy_time=stats.redeploy_time,
            damage_type=("ARTS" if adapted.operator.profession.value == "CASTER" else "PHYSICAL"),
            deployment_cost_delta=deployment_cost_delta,
            deployment_sp_bonus=deployment_sp_bonus(self.repository, adapted.operator.operator_id),
            deployment_heal_all_value=deployment_heal_all_value(self.repository, adapted.operator.operator_id),
            redeploy_time_delta=self._talent_redeploy_time_delta(adapted),
        )

    def _talent_redeploy_time_delta(self, adapted: AdaptedRealOperator) -> float:
        from arknights_planner.adapters.normal_low_star import active_talent_candidates

        total = 0.0
        for candidate in active_talent_candidates(self.repository, adapted.operator.operator_id):
            blackboard = {
                item["key"]: item["value"]
                for item in candidate.get("blackboard", [])
                if isinstance(item, dict)
            }
            if "再部署时间" in (candidate.get("description") or "") and blackboard.get("respawn_time") is not None:
                total += float(
                    blackboard["respawn_time"]
                )
        return total

    def _neutral_self_deployment_cost_delta(self, adapted: AdaptedRealOperator) -> float:
        """Apply only source-explicit, neutral-potential *self* cost talents.

        This deliberately does not become a general talent interpreter.  The
        exact Chinese description protects against confusing `cost` values used
        for DP grants or other effects with an operator's deployment cost.
        """
        raw = self.repository._table("character_table.json").get(adapted.operator.operator_id, {})
        phase_names = {"PHASE_0": 0, "PHASE_1": 1, "PHASE_2": 2}
        total = 0.0
        for talent in raw.get("talents") or []:
            eligible = []
            for candidate in talent.get("candidates") or []:
                condition = candidate.get("unlockCondition") or {}
                phase = phase_names.get(condition.get("phase"))
                if phase is None or phase > adapted.phase_index or int(condition.get("level", 1)) > adapted.requested_level:
                    continue
                if int(candidate.get("requiredPotentialRank", 0)) > 0:
                    continue
                values = {str(item.get("key")): item.get("value") for item in candidate.get("blackboard") or [] if isinstance(item, dict)}
                description = str(candidate.get("description") or "")
                if set(values) == {"cost"} and isinstance(values["cost"], (int, float)) and "自身部署费用" in description:
                    eligible.append((phase, int(condition.get("level", 1)), float(values["cost"])))
            if eligible:
                total += max(eligible, key=lambda item: (item[0], item[1]))[2]
        return total

    def build_fixture(
        self,
        *,
        stage_id_or_code: str,
        selections: tuple[RealOperatorSelection, ...],
        policy: RealSimulationApproximationPolicy | None,
    ) -> ApproximateRealFixture:
        fixture = self.build_pool_fixture(
            stage_id_or_code=stage_id_or_code,
            configurations=tuple(RealOperatorConfiguration(item.operator_id, item.phase_index, item.level) for item in selections),
            policy=policy,
        )
        mapping_by_coordinate = {item.coordinate: item for item in fixture.tile_mappings}
        for selection in selections:
            mapped = mapping_by_coordinate.get(selection.tile)
            if mapped is None or mapped.status is KnowledgeStatus.UNKNOWN:
                raise ApproximateRealExecutionError(f"selected deployment tile {selection.tile} is UNKNOWN")
        return fixture

    def build_pool_fixture(
        self,
        *,
        stage_id_or_code: str,
        configurations: tuple[RealOperatorConfiguration, ...],
        policy: RealSimulationApproximationPolicy | None,
    ) -> ApproximateRealFixture:
        if policy is None:
            raise ApproximateRealExecutionError("APPROXIMATE_REAL requires an explicit RealSimulationApproximationPolicy")
        adapted_stage = self.strict_adapter.adapt_stage(stage_id_or_code)
        if not adapted_stage.structurally_loadable:
            raise ApproximateRealExecutionError("stage is not structurally loadable")
        runtime_tiles, mappings = self._map_tiles(adapted_stage, policy)
        adapted_operators = tuple(
            self.strict_adapter.adapt_operator(
                item.operator_id,
                phase_index=item.phase_index,
                level=item.level,
                skill_level_index=(len(self.repository.get_skill(self.repository.get_operator(item.operator_id).skill_ids[0]).levels) - 1 if item.skill_level_index == -1 and self.repository.get_operator(item.operator_id).skill_ids else item.skill_level_index),
            )
            for item in configurations
        )
        interpreter = LowRarityBlackboardEffectInterpreter()
        runtime_operators: dict[str, Operator] = {}
        for adapted in adapted_operators:
            interpreted = None
            if adapted.skill is not None:
                result = interpreter.interpret(adapted.skill.skill.skill_id, adapted.skill.selected_level)
                if result.support is RealSkillSupport.EXECUTABLE_APPROXIMATED:
                    interpreted = result.executable_effect
            runtime_operators[adapted.operator.operator_id] = self._runtime_operator(
                adapted, interpreted_skill=interpreted,
                deployment_cost_delta=self._neutral_self_deployment_cost_delta(adapted),
            )
        enemy_levels = dict(adapted_stage.stage.enemy_references)
        timeline = self._approximate_spawns(adapted_stage, enemy_levels, policy)
        adapted_enemies: dict[str, AdaptedRealEnemy] = {
            enemy_id: self.strict_adapter.adapt_enemy(enemy_id, level=level)
            for enemy_id, level in enemy_levels.items()
        }
        unresolved = [blocker for item in adapted_enemies.values() for blocker in item.adaptation_blockers]
        if unresolved:
            raise ApproximateRealExecutionError("; ".join(unresolved))
        routes = self._convert_routes(adapted_stage)
        cost_interval = self._number(adapted_stage.stage.cost_increase_time, "stage costIncreaseTime")
        max_life = int(self._number(adapted_stage.stage.max_life_points, "stage maxLifePoint"))
        runtime_stage = replace(
            adapted_stage.stage,
            stage_map=StageMap(
                int(self._number(adapted_stage.stage.map_width, "map width")),
                int(self._number(adapted_stage.stage.map_height, "map height")), runtime_tiles,
            ),
            routes=routes,
            spawn_events=tuple(SpawnEvent(item.time, item.enemy_id, item.route_id, item.count, item.interval) for item in timeline),
            initial_life=max_life,
            dp_per_second=1.0 / cost_interval,
            devices=self._devices(adapted_stage),
        )
        ignored_skills = tuple(
            item.operator.operator_id for item in adapted_operators
            if item.skill is not None and runtime_operators[item.operator.operator_id].synthetic_skill is None
        )
        return ApproximateRealFixture(
            runtime_stage, runtime_operators,
            {item.enemy.enemy_id: item.enemy for item in adapted_enemies.values()},
            mappings, timeline, policy.names, ignored_skills,
        )

    def m12_low_rarity_configurations(self, policy: M12LoadoutPolicy | None = None) -> tuple[RealOperatorConfiguration, ...]:
        """Build the production M12 pool from the complete census, never a handwritten list."""
        loadout = policy or M12LoadoutPolicy.phase_zero_max()
        configs = []
        for record in low_rarity_census(self.repository):
            if record.runtime_status in {RuntimeSupportStatus.EXECUTABLE, RuntimeSupportStatus.EXECUTABLE_WITH_APPROXIMATION}:
                configs.append(loadout.configuration(self.repository, record.operator_id))
        return tuple(configs)

    def m13_low_rarity_configurations(self, policy: M13LoadoutPolicy | None = None) -> tuple[RealOperatorConfiguration, ...]:
        """Return every executable low-rarity operator under high progression policy."""
        loadout = policy or M13LoadoutPolicy.highest_legal()
        configs: list[RealOperatorConfiguration] = []
        for record in low_rarity_census(self.repository):
            if record.runtime_status in {RuntimeSupportStatus.EXECUTABLE, RuntimeSupportStatus.EXECUTABLE_WITH_APPROXIMATION}:
                try:
                    configs.append(loadout.configuration(self.repository, record.operator_id))
                except ApproximateRealExecutionError:
                    continue
        return tuple(configs)

    def all_executable_phase_zero_configurations(self) -> tuple[RealOperatorConfiguration, ...]:
        """Return every obtainable operator executable by basic attacks at phase zero.

        The first-WIN feasibility pool is deliberately not rarity-restricted.  It
        uses exact phase-zero keyframes, requires a source-backed range, and
        excludes operators whose active phase-zero talents are not modeled.
        Unsupported optional skills do not block basic attacks because this
        planner path issues no skill actions.
        """
        return tuple(row.configuration for row in self._all_executable_phase_zero_rows() if row.status == "EXECUTABLE")

    def all_executable_phase_zero_pool_report(self) -> dict[str, Any]:
        rows = self._all_executable_phase_zero_rows()
        included = [row for row in rows if row.status == "EXECUTABLE"]
        excluded = [row for row in rows if row.status != "EXECUTABLE"]
        return {
            "policy": "ALL_CURRENTLY_EXECUTABLE_PHASE_ZERO_BASIC_ATTACK",
            "selection_rules": [
                "operator is normally obtainable according to character_table itemObtainApproach/isNotObtainable",
                "exact highest phase-zero source keyframe is available",
                "phase-zero attack range is source-backed",
                "no talent is active at the selected phase-zero level",
                "optional skills are not issued; unsupported skill actions do not make basic attacks unavailable",
            ],
            "included_count": len(included),
            "excluded_count": len(excluded),
            "included": [asdict(row) for row in included],
            "excluded": [asdict(row) for row in excluded],
            "provenance": "zh_CN/gamedata/excel/character_table.json and range/skill tables through GameDataRepository",
        }

    def _all_executable_phase_zero_rows(self) -> tuple[ExecutableOperatorRecord, ...]:
        cached = getattr(self, "_all_executable_phase_zero_rows_cache", None)
        if cached is not None:
            return cached
        table = self.repository._table("character_table.json")
        loadout = M12LoadoutPolicy.phase_zero_max()
        rows: list[ExecutableOperatorRecord] = []
        for operator_id in self.repository.operator_ids():
            raw = table[operator_id]
            if not raw.get("itemObtainApproach") or raw.get("isNotObtainable") is True:
                continue
            operator = self.repository.get_operator(operator_id)
            base = {
                "operator_id": operator_id,
                "name": operator.name.value,
                "rarity": int(operator.star_rarity.value or 0),
                "profession": operator.profession.value,
                "position": operator.position.value,
                "phase_index": 0,
                "level": 0,
            }
            try:
                configuration = loadout.configuration(self.repository, operator_id)
            except ApproximateRealExecutionError:
                rows.append(ExecutableOperatorRecord(**base, status="BLOCKED", blockers=("NO_EXACT_PHASE_ZERO_KEYFRAME",)))
                continue
            base["level"] = configuration.level
            blockers: list[str] = []
            if not operator.phases[0].range_id.value:
                blockers.append("PHASE_ZERO_ATTACK_RANGE_UNAVAILABLE")
            active_talent = any(
                isinstance(candidate, dict)
                and (candidate.get("unlockCondition") or {}).get("phase") == "PHASE_0"
                and int((candidate.get("unlockCondition") or {}).get("level", 1) or 0) <= configuration.level
                and int(candidate.get("requiredPotentialRank", 0) or 0) <= 0
                for talent in raw.get("talents") or []
                for candidate in talent.get("candidates") or []
            )
            if active_talent:
                blockers.append("ACTIVE_PHASE_ZERO_TALENT_NOT_MODELED")
            rows.append(ExecutableOperatorRecord(
                **base,
                status="EXECUTABLE" if not blockers else "BLOCKED",
                blockers=tuple(blockers),
                configuration=configuration,
            ))
        output = tuple(rows)
        self._all_executable_phase_zero_rows_cache = output
        return output

    def inspect_stage_approximations(
        self,
        *,
        stage_id_or_code: str,
        policy: RealSimulationApproximationPolicy | None,
    ) -> tuple[tuple[MappedRealTile, ...], tuple[ApproximatedSpawn, ...]]:
        """Read-only debug view: source tile/action hierarchy through this policy."""
        if policy is None:
            raise ApproximateRealExecutionError("APPROXIMATE_REAL inspection requires an explicit policy")
        stage = self.strict_adapter.adapt_stage(stage_id_or_code)
        _, tiles = self._map_tiles(stage, policy)
        return tiles, self._approximate_spawns(stage, dict(stage.stage.enemy_references), policy)

    @staticmethod
    def default_main_00_01_selections() -> tuple[RealOperatorSelection, ...]:
        # Both are exact source keyframes. No skill action or skill effect is used.
        return (
            RealOperatorSelection("char_129_bluep", 2, 80, (4, 2), "RIGHT", 3.0),
            RealOperatorSelection("char_010_chen", 2, 90, (1, 3), "RIGHT", 26.0),
        )

    @staticmethod
    def default_main_00_01_search_pool() -> tuple[RealOperatorConfiguration, ...]:
        return (
            RealOperatorConfiguration("char_129_bluep", 2, 80),
            RealOperatorConfiguration("char_010_chen", 2, 90),
            RealOperatorConfiguration("char_002_amiya", 2, 80),
            RealOperatorConfiguration("char_017_huang", 2, 90),
        )

    def fixed_main_00_01_strategy(self, selections: tuple[RealOperatorSelection, ...] | None = None) -> Strategy:
        selections = selections or self.default_main_00_01_selections()
        return Strategy(
            tuple(item.operator_id for item in selections),
            tuple(Action(ActionType.DEPLOY, item.deploy_time, item.operator_id, item.tile, item.direction) for item in selections),
        )

    def run_fixed_main_00_01(
        self,
        *,
        policy: RealSimulationApproximationPolicy | None,
        config: SimulationConfig | None = None,
    ) -> ApproximateRealRun:
        selections = self.default_main_00_01_selections()
        fixture = self.build_fixture(stage_id_or_code="0-1", selections=selections, policy=policy)
        strategy = self.fixed_main_00_01_strategy(selections)
        if any(action.action_type is ActionType.ACTIVATE_SKILL for action in strategy.actions):
            raise ApproximateRealExecutionError("real skill activation is not supported in APPROXIMATE_REAL")
        result = Simulator(
            range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel(),
        ).run(
            stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies, strategy=strategy,
            config=config or SimulationConfig(dt=0.1, max_time=90.0),
        )
        result = replace(result, run_metadata=SimulationRunMetadata(
            RealExecutionMode.APPROXIMATE_REAL.value,
            fixture.approximations_used,
            (fixture.stage.stage_id, *sorted(fixture.operators), *sorted(fixture.enemies)),
        ))
        return ApproximateRealRun(
            fixture, strategy, result,
            ApproximateExecutionReport(
                RealExecutionMode.APPROXIMATE_REAL, True, fixture.approximations_used,
                any(action.action_type is ActionType.ACTIVATE_SKILL for action in strategy.actions),
            ),
        )

    def run_main_00_01(
        self,
        *,
        mode: RealExecutionMode,
        policy: RealSimulationApproximationPolicy | None = None,
        config: SimulationConfig | None = None,
    ) -> ApproximateRealRun:
        """Make strict refusal and opt-in approximate execution explicit at one call site."""
        if mode is RealExecutionMode.STRICT_REAL:
            bundle = self.strict_adapter.adapt_combination(
                operator_id_or_name="char_129_bluep", operator_phase=2, operator_level=80,
                enemy_id_or_name="enemy_1007_slime", enemy_level=0, stage_id_or_code="0-1",
            )
            self.strict_adapter.require_simulator_execution(bundle)
        if mode is not RealExecutionMode.APPROXIMATE_REAL:
            raise ApproximateRealExecutionError(f"Unsupported real execution mode: {mode}")
        return self.run_fixed_main_00_01(policy=policy, config=config)
