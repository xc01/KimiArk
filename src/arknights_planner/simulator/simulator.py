from __future__ import annotations

from dataclasses import dataclass
from math import floor, hypot

from arknights_planner.models.enemy import Enemy, EnemyAbility
from arknights_planner.models.operator import Operator
from arknights_planner.models.runtime import CombatOutputType, SPRecoveryMode, SyntheticSkill
from arknights_planner.models.simulation import EventType, RuntimeDevice, RuntimeEnemy, RuntimeOperator, SimulationEvent, SimulationResult, SimulationState
from arknights_planner.models.stage import Stage
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.models.timeline import FrameTimeline
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION
from arknights_planner.timing import timeline_to_strategy

from .projectile import InstantProjectileModel, ProjectileModel
from .range import CanonicalSyntheticRangeTransformer, RangeTransformer
from .combat_rules import ModifierPipeline, arts_damage, attack_interval, physical_damage


@dataclass(frozen=True)
class SimulationConfig:
    dt: float = 0.1
    max_time: float = 60.0

    def __post_init__(self) -> None:
        if self.dt <= 0:
            raise ValueError("dt must be positive")


@dataclass(frozen=True)
class _PendingHit:
    time: float
    source_id: str
    target_id: str
    raw_override: float | None = None


class Simulator:
    """A deterministic synthetic combat runtime with deliberately explicit limits."""

    _EPSILON = 1e-9
    MECHANICS_VERSION = ACTIVE_MECHANICS_VERSION

    def __init__(self, *, range_transformer: RangeTransformer | None = None, projectile_model: ProjectileModel | None = None):
        self.range_transformer = range_transformer or CanonicalSyntheticRangeTransformer()
        self.projectile_model = projectile_model or InstantProjectileModel()

    def run_timeline(self, *, stage: Stage, operators: dict[str, Operator], enemies: dict[str, Enemy], timeline: FrameTimeline, config: SimulationConfig | None = None) -> SimulationResult:
        """Evaluate an execution timeline via one explicit frame->seconds boundary.

        The inner legacy runtime remains seconds-based for now; no action is
        repeatedly converted during its tick loop. Unknown client frequency is
        rejected instead of receiving an implicit 60 FPS assumption.
        """
        return self.run(stage=stage, operators=operators, enemies=enemies, strategy=timeline_to_strategy(timeline), config=config)

    @staticmethod
    def _number(value, label: str) -> float:
        if value.value is None:
            raise ValueError(f"Simulation requires known {label}")
        return float(value.value)

    def _emit(self, state: SimulationState, event_type: EventType, *, source: str | None = None, target: str | None = None, **details: str | float | int | bool) -> None:
        state.events.append(SimulationEvent(round(state.time, 10), event_type, source, target, tuple(sorted(details.items()))))

    def _enemy_position(self, stage: Stage, enemy: RuntimeEnemy) -> tuple[float, float]:
        return next(route for route in stage.routes if route.route_id == enemy.route_id).position_at(enemy.distance)

    @staticmethod
    def _grid_position(position: tuple[float, float]) -> tuple[int, int]:
        return floor(position[0] + 0.5), floor(position[1] + 0.5)

    @staticmethod
    def _skill(operator: RuntimeOperator) -> SyntheticSkill | None:
        return operator.skill if isinstance(operator.skill, SyntheticSkill) else None

    def _effective_atk(self, operator: RuntimeOperator) -> float:
        skill = self._skill(operator)
        if operator.skill_active and skill:
            # SyntheticSkill names this as an additive + direct multiplier
            # pair.  PRTS applies direct addition before direct multiplication.
            return ModifierPipeline(
                direct_add=skill.effect.atk_additive,
                direct_multiplier_add=skill.effect.atk_multiplier - 1.0,
            ).apply(operator.base_atk)
        return operator.base_atk

    def _effective_interval(self, state: SimulationState, operator: RuntimeOperator) -> float:
        skill = self._skill(operator)
        multiplier = skill.effect.attack_interval_multiplier if operator.skill_active and skill else 1.0
        attack_speed = getattr(operator, "attack_speed", 100.0)
        if operator.attack_speed_status_until >= state.time:
            attack_speed += operator.attack_speed_status_delta
        if operator.skill_active and skill:
            attack_speed += skill.effect.attack_speed_additive
        base_interval = skill.effect.base_attack_time_override if operator.skill_active and skill and skill.effect.base_attack_time_override is not None else operator.base_attack_interval
        return attack_interval(base_interval * multiplier, attack_speed)

    def _effective_range(self, operator: RuntimeOperator) -> tuple[tuple[int, int], ...]:
        skill = self._skill(operator)
        if not operator.skill_active or not skill:
            return operator.base_attack_range
        if skill.effect.range_override is not None:
            return skill.effect.range_override
        forward_cells = tuple((0, index) for index in range(1, skill.effect.range_forward_extend + 1))
        return tuple(dict.fromkeys((*operator.base_attack_range, *skill.effect.range_add, *forward_cells)))

    def _effective_block(self, operator: RuntimeOperator) -> int:
        skill = self._skill(operator)
        delta = skill.effect.block_count_delta if operator.skill_active and skill else 0
        return max(0, operator.base_block_count + delta)

    def _spawn(self, state: SimulationState, enemies: dict[str, Enemy], *, enemy_id: str, route_id: str, spawn_index: int) -> None:
        enemy = enemies[enemy_id]
        stats = enemy.stats
        instance_id = f"{enemy_id}#{spawn_index}"
        state.active_enemies[instance_id] = RuntimeEnemy(
            instance_id=instance_id, enemy_id=enemy_id, route_id=route_id,
            hp=self._number(stats.max_hp, "enemy hp"), speed=self._number(stats.move_speed, "enemy speed"),
            life_point_reduce=int(self._number(stats.life_point_reduce, "enemy life loss")), defense=self._number(stats.defense, "enemy defense"),
            atk=self._number(stats.atk, "enemy attack"), attack_interval=self._number(stats.attack_interval, "enemy attack interval"), spawn_index=spawn_index,
            attack_range=None if getattr(stats.apply_way, "value", None) == "MELEE" else float(stats.attack_range.value) if stats.attack_range.value is not None else None,
            magic_resistance=self._number(stats.magic_resistance, "enemy magic resistance"),
            damage_type=getattr(getattr(stats, "damage_type", None), "value", None) or "PHYSICAL",
            abilities=enemy.abilities,
            ability_next_fire_time=state.time + min((ability.initial_cooldown for ability in enemy.abilities), default=0.0),
            attack_windup=enemy.attack_timing.windup_seconds if enemy.attack_timing else 0.0,
            attack_recovery=enemy.attack_timing.recovery_seconds if enemy.attack_timing else 0.0,
            attack_animation_duration=enemy.attack_timing.duration_seconds if enemy.attack_timing else 0.0,
            max_hp=self._number(stats.max_hp, "enemy hp"),
            hp_recovery_per_second=0.0 if stats.hp_recovery_per_second.value is None else float(stats.hp_recovery_per_second.value),
        )
        self._emit(state, EventType.SPAWN, source=instance_id, enemy_id=enemy_id, route_id=route_id)

    def _deployment_tile_reason(self, operator: Operator, stage: Stage, tile_coordinate: tuple[int, int] | None) -> str | None:
        tile = stage.stage_map.tile_at(tile_coordinate) if stage.stage_map and tile_coordinate is not None else None
        if tile is None or not tile.buildable or tile.tile_kind == "NON_DEPLOYABLE":
            return "tile is not buildable"
        position = operator.position.value
        if position == "MELEE" and tile.tile_kind != "GROUND":
            return "MELEE operator requires GROUND tile"
        if position == "RANGED" and tile.tile_kind != "HIGH_GROUND":
            return "RANGED operator requires HIGH_GROUND tile"
        return None

    def _deploy(self, state: SimulationState, stage: Stage, operators: dict[str, Operator], strategy: Strategy, action: Action) -> None:
        legal, reason, operator = True, "", operators.get(action.operator_id)
        if action.operator_id not in strategy.team: legal, reason = False, "operator is not in strategy team"
        elif operator is None: legal, reason = False, "unknown operator"
        elif action.operator_id in state.deployed_operators: legal, reason = False, "operator already deployed"
        elif state.redeploy_available_at.get(action.operator_id, 0.0) > state.time + self._EPSILON: legal, reason = False, "redeploy cooldown active"
        elif len(state.deployed_operators) >= int(self._number(stage.deployment_limit, "deployment limit")): legal, reason = False, "deployment limit reached"
        elif any(runtime.tile == action.tile for runtime in state.deployed_operators.values()): legal, reason = False, "tile is occupied"
        elif any(device.tile == action.tile for device in state.active_devices.values()): legal, reason = False, "tile is occupied by active stage device"
        else:
            reason = self._deployment_tile_reason(operator, stage, action.tile)
            if reason:
                legal = False
            else:
                stats = operator.phases[0].stats_max
                cost = max(0.0, self._number(stats.cost, "deployment cost") + operator.deployment_cost_delta)
                if state.dp + self._EPSILON < cost: legal, reason = False, "insufficient DP"
        tile_text = "none" if action.tile is None else f"{action.tile[0]},{action.tile[1]}"
        self._emit(state, EventType.DEPLOY, source=action.operator_id, legal=legal, tile=tile_text)
        if not legal:
            state.deployment_errors.append(f"{action.operator_id}@{action.time}: {reason}")
            return
        stats = operator.phases[0].stats_max
        skill = operator.synthetic_skill
        state.dp -= cost
        runtime = RuntimeOperator(
            operator_id=action.operator_id, tile=action.tile, direction=action.direction,
            hp=self._number(stats.max_hp, "operator hp"), max_hp=self._number(stats.max_hp, "operator hp"),
            base_atk=self._number(stats.atk, "operator attack"), base_block_count=int(self._number(stats.block_count, "operator block count")),
            base_attack_interval=self._number(stats.attack_interval, "operator attack interval"), base_attack_range=operator.attack_range,
            defense=self._number(stats.defense, "operator defense"),
            magic_resistance=self._number(stats.magic_resistance, "operator magic resistance"),
            combat_output=operator.combat_output.value,
            position=operator.position.value or "UNKNOWN",
            redeploy_time=self._number(operator.redeploy_time, "operator redeploy time"), skill=skill,
            current_sp=skill.initial_sp if skill else 0.0,
            damage_type=operator.damage_type,
            attack_speed=getattr(operator, "attack_speed", 100.0),
            maintenance_cost=operator.maintenance_cost,
            maintenance_interval=operator.maintenance_interval,
            deployment_sp_bonus=operator.deployment_sp_bonus,
            deployment_heal_all_value=operator.deployment_heal_all_value,
            redeploy_time_delta=operator.redeploy_time_delta,
        )
        if skill:
            runtime.current_sp = min(skill.sp_cost, runtime.current_sp + runtime.deployment_sp_bonus)
        runtime.skill_ready = bool(skill and runtime.current_sp >= skill.sp_cost)
        runtime.next_maintenance_time = state.time + runtime.maintenance_interval
        state.deployed_operators[action.operator_id] = runtime
        if runtime.deployment_heal_all_value:
            for ally in state.deployed_operators.values():
                healed = min(runtime.deployment_heal_all_value, ally.max_hp - ally.hp)
                ally.hp += healed
                self._emit(state, EventType.HEAL, source=runtime.operator_id, target=ally.operator_id,
                           amount=healed, reason="deployment_heal_all")
        if runtime.skill_ready:
            self._emit(state, EventType.SKILL_READY, source=runtime.operator_id)
            if skill and skill.auto_activate:
                if skill.effect.next_attack_atk_scale != 1.0:
                    runtime.skill_ready = True
                    runtime.pending_next_attack = True
                else:
                    self._activate_runtime_skill(state, runtime, skill, automatic=True)

    def _unblock(self, state: SimulationState, enemy: RuntimeEnemy) -> None:
        if enemy.blocked_by and enemy.blocked_by in state.deployed_operators:
            holder = state.deployed_operators[enemy.blocked_by]
            if enemy.instance_id in holder.blocked_enemy_ids:
                holder.blocked_enemy_ids.remove(enemy.instance_id)
            self._emit(state, EventType.UNBLOCK, source=holder.operator_id, target=enemy.instance_id)
        enemy.blocked_by = None

    def _remove_operator(self, state: SimulationState, operator_id: str, *, death: bool) -> None:
        operator = state.deployed_operators.get(operator_id)
        if operator is None:
            return
        for enemy_id in tuple(operator.blocked_enemy_ids):
            enemy = state.active_enemies.get(enemy_id)
            if enemy:
                self._unblock(state, enemy)
        del state.deployed_operators[operator_id]
        state.redeploy_available_at[operator_id] = state.time + max(0.0, operator.redeploy_time + operator.redeploy_time_delta)
        if death:
            state.operator_deaths += 1
            self._emit(state, EventType.OPERATOR_DEATH, source=operator_id)
        else:
            self._emit(state, EventType.RETREAT, source=operator_id)

    def _retreat(self, state: SimulationState, action: Action) -> None:
        if action.operator_id not in state.deployed_operators:
            state.deployment_errors.append(f"{action.operator_id}@{action.time}: operator is not deployed")
            self._emit(state, EventType.RETREAT, source=action.operator_id, legal=False)
            return
        self._remove_operator(state, action.operator_id, death=False)

    def _activate_runtime_skill(self, state: SimulationState, operator: RuntimeOperator, skill: SyntheticSkill, *, automatic: bool) -> None:
        operator.current_sp -= skill.sp_cost
        operator.skill_ready = False
        operator.skill_active = True
        operator.skill_remaining_duration = skill.duration
        self._emit(state, EventType.SKILL_ACTIVATE, source=operator.operator_id, legal=True, skill=skill.skill_id, automatic=automatic)
        if skill.effect.immediate_self_heal_ratio:
            amount = min(operator.max_hp * skill.effect.immediate_self_heal_ratio, operator.max_hp - operator.hp)
            operator.hp += amount
            self._emit(state, EventType.HEAL, source=operator.operator_id, target=operator.operator_id, amount=amount, reason="skill_immediate_self_heal")
        if skill.effect.dp_immediate:
            before = state.dp
            state.dp += skill.effect.dp_immediate
            self._emit(state, EventType.DP_CHANGE, source=operator.operator_id, amount=skill.effect.dp_immediate,
                       before=before, after=state.dp, reason="skill_activation")

    def _activate_skill(self, state: SimulationState, action: Action) -> None:
        operator = state.deployed_operators.get(action.operator_id)
        skill = self._skill(operator) if operator else None
        legal, reason = True, ""
        if operator is None: legal, reason = False, "operator is not deployed"
        elif skill is None: legal, reason = False, "operator has no synthetic skill"
        elif skill.auto_activate: legal, reason = False, "skill activates automatically"
        elif operator.skill_active: legal, reason = False, "skill already active"
        elif operator.current_sp + self._EPSILON < skill.sp_cost: legal, reason = False, "insufficient SP"
        if not legal:
            state.deployment_errors.append(f"{action.operator_id}@{action.time}: {reason}")
            self._emit(state, EventType.SKILL_ACTIVATE, source=action.operator_id, legal=False)
            return
        self._activate_runtime_skill(state, operator, skill, automatic=False)

    def _apply_damage_to_enemy(self, state: SimulationState, enemy_id: str, source_id: str, damage: float, *, kind: str = "physical") -> None:
        enemy = state.active_enemies.get(enemy_id)
        if enemy is None:
            return
        enemy.hp -= damage
        self._emit(state, EventType.DAMAGE, source=source_id, target=enemy_id, amount=damage, kind=kind)
        if enemy.hp <= 0:
            self._unblock(state, enemy)
            del state.active_enemies[enemy_id]
            state.enemies_killed += 1
            self._emit(state, EventType.ENEMY_DEATH, source=source_id, target=enemy_id)

    def _target_device_for(self, state: SimulationState, operator: RuntimeOperator) -> RuntimeDevice | None:
        if state.active_enemies:
            return None
        covered = self.range_transformer.covered_tiles(origin=operator.tile, offsets=self._effective_range(operator), direction=operator.direction)
        targets = [device for device in state.active_devices.values() if device.tile in covered]
        selected = min(targets, key=lambda device: device.device_id) if targets else None
        self._emit(state, EventType.DEVICE_TARGET_SELECTION, source=operator.operator_id,
                   target=selected.device_id if selected else None,
                   candidate_ids=tuple(device.device_id for device in targets),
                   rule="DEVICE_ONLY_WHEN_NO_ENEMY_TARGET_TAUNT_MINUS_ONE_LOWEST_DEVICE_ID")
        return selected

    def _apply_damage_to_device(self, state: SimulationState, device_id: str, source_id: str, damage: float, *, kind: str = "physical") -> None:
        device = state.active_devices.get(device_id)
        if device is None:
            return
        device.hp -= damage
        self._emit(state, EventType.DEVICE_DAMAGE, source=source_id, target=device_id, amount=damage, kind=kind)
        if device.hp <= 0:
            del state.active_devices[device_id]
            self._emit(state, EventType.DEVICE_DESTROYED, source=source_id, target=device_id)

    def _process_projectile_hit(self, state: SimulationState, source_id: str, target_id: str, *, raw_override: float | None = None) -> None:
        operator = state.deployed_operators.get(source_id)
        enemy = state.active_enemies.get(target_id)
        if operator is None:
            return
        if enemy is None:
            device = state.active_devices.get(target_id)
            if device is None:
                return
            self._emit(state, EventType.PROJECTILE_HIT, source=source_id, target=target_id)
            raw = self._effective_atk(operator) if raw_override is None else raw_override
            if operator.damage_type == "ARTS":
                damage = arts_damage(raw, device.magic_resistance,
                                     penetration_ratio=getattr(operator, "magic_resist_penetration", 0.0),
                                     penetration_flat=getattr(operator, "magic_resist_penetration_flat", 0.0))
                kind = "arts"
            else:
                damage = physical_damage(raw, device.defense,
                                         penetration_ratio=getattr(operator, "defense_penetration", 0.0),
                                         penetration_flat=getattr(operator, "defense_penetration_flat", 0.0))
                kind = "physical"
            self._apply_damage_to_device(state, target_id, source_id, damage, kind=kind)
            return
        self._emit(state, EventType.PROJECTILE_HIT, source=source_id, target=target_id)
        raw = self._effective_atk(operator) if raw_override is None else raw_override
        if operator.damage_type == "ARTS":
            damage = arts_damage(raw, getattr(enemy, "magic_resistance", 0.0),
                                 penetration_ratio=getattr(operator, "magic_resist_penetration", 0.0),
                                 penetration_flat=getattr(operator, "magic_resist_penetration_flat", 0.0))
            kind = "arts"
        else:
            damage = physical_damage(raw, enemy.defense,
                                     penetration_ratio=getattr(operator, "defense_penetration", 0.0),
                                     penetration_flat=getattr(operator, "defense_penetration_flat", 0.0))
            kind = "physical"
        self._apply_damage_to_enemy(state, target_id, source_id, damage, kind=kind)

    def _damage_operator(self, state: SimulationState, enemy: RuntimeEnemy, operator_id: str, ability: EnemyAbility | None = None) -> None:
        operator = state.deployed_operators.get(operator_id)
        if operator is None:
            return
        base_damage = enemy.atk * ability.atk_scale if ability else enemy.atk
        damage_type = ability.damage_type if ability else enemy.damage_type
        if damage_type == "ARTS":
            damage = arts_damage(base_damage, operator.magic_resistance)
            kind = "enemy_arts"
        else:
            skill = self._skill(operator)
            defense = operator.defense
            if operator.skill_active and skill:
                defense *= 1.0 + skill.effect.defense_additive_ratio
            damage = physical_damage(base_damage, defense)
            kind = "enemy_physical"
        operator.hp -= damage
        self._emit(state, EventType.DAMAGE, source=enemy.instance_id, target=operator_id, amount=damage, kind=kind)
        if operator.hp <= 0:
            self._remove_operator(state, operator_id, death=True)

    def _target_enemy_for(self, stage: Stage, state: SimulationState, operator: RuntimeOperator) -> RuntimeEnemy | None:
        covered = self.range_transformer.covered_tiles(origin=operator.tile, offsets=self._effective_range(operator), direction=operator.direction)
        blocked_targets = [
            state.active_enemies[enemy_id]
            for enemy_id in operator.blocked_enemy_ids
            if enemy_id in state.active_enemies
        ]
        if operator.position == "MELEE" and blocked_targets:
            targets = blocked_targets
            rule = "SELF_BLOCKED_FIRST_THEN_REMAINING_PATH_DISTANCE_THEN_CREATION_ORDER"
        else:
            targets = [enemy for enemy in state.active_enemies.values() if self._grid_position(self._enemy_position(stage, enemy)) in covered]
            rule = "HATRED_DES_remaining_path_distance_then_creation_order"
        def remaining_path(enemy: RuntimeEnemy) -> float:
            route = next(item for item in stage.routes if item.route_id == enemy.route_id)
            return max(0.0, route.length - enemy.distance)
        selected = min(targets, key=lambda enemy: (remaining_path(enemy), enemy.spawn_index)) if targets else None
        self._emit(state, EventType.TARGET_SELECTION, source=operator.operator_id,
                   target=selected.instance_id if selected else None,
                   candidate_ids=tuple(x.instance_id for x in targets),
                   rule=rule if selected else "NO_CANDIDATE",
                   blocked_candidate_ids=tuple(x.instance_id for x in blocked_targets),
                   candidate_path_distances=tuple((x.instance_id, remaining_path(x)) for x in targets))
        return selected

    def _target_ally_for(self, state: SimulationState, operator: RuntimeOperator) -> RuntimeOperator | None:
        covered = self.range_transformer.covered_tiles(origin=operator.tile, offsets=self._effective_range(operator), direction=operator.direction)
        targets = [ally for ally in state.deployed_operators.values() if ally.hp + self._EPSILON < ally.max_hp and ally.tile in covered]
        return min(targets, key=lambda ally: (ally.hp / ally.max_hp, ally.operator_id)) if targets else None

    def _heal(self, state: SimulationState, operator: RuntimeOperator, target: RuntimeOperator) -> None:
        raw_amount = max(1.0, self._effective_atk(operator))
        actual_amount = min(raw_amount, target.max_hp - target.hp)
        target.hp += actual_amount
        self._emit(state, EventType.HEAL, source=operator.operator_id, target=target.operator_id, amount=actual_amount)

    def _operator_outputs(self, state: SimulationState, stage: Stage, pending_hits: list[_PendingHit]) -> None:
        for operator in tuple(state.deployed_operators.values()):
            if state.time + self._EPSILON < operator.next_attack_time:
                continue
            if operator.combat_output == CombatOutputType.HEAL.value:
                target = self._target_ally_for(state, operator)
                if target is None:
                    continue
                self._emit(state, EventType.ATTACK_START, source=operator.operator_id, target=target.operator_id)
                self._emit(state, EventType.PROJECTILE_BORN, source=operator.operator_id, target=target.operator_id)
                self._emit(state, EventType.PROJECTILE_HIT, source=operator.operator_id, target=target.operator_id)
                self._heal(state, operator, target)
                operator.next_attack_time = state.time + self._effective_interval(state, operator)
                operator.attack_cooldown = self._effective_interval(state, operator)
                continue
            skill = self._skill(operator)
            if operator.skill_active and skill and skill.effect.heal_mode:
                target = self._target_ally_for(state, operator)
                if target is None:
                    continue
                self._emit(state, EventType.ATTACK_START, source=operator.operator_id, target=target.operator_id)
                self._emit(state, EventType.PROJECTILE_BORN, source=operator.operator_id, target=target.operator_id)
                self._emit(state, EventType.PROJECTILE_HIT, source=operator.operator_id, target=target.operator_id)
                self._heal(state, operator, target)
                operator.next_attack_time = state.time + self._effective_interval(state, operator)
                operator.attack_cooldown = self._effective_interval(state, operator)
            target = self._target_enemy_for(stage, state, operator)
            device = None
            if target is None:
                device = self._target_device_for(state, operator)
                if device is None:
                    continue
                target_id = device.device_id
                target_position = device.tile
            else:
                target_id = target.instance_id
                target_position = self._enemy_position(stage, target)
            next_attack_scale = 1.0
            next_attack_hits = 1
            consumed_next_attack = False
            if operator.pending_next_attack and skill:
                next_attack_scale = skill.effect.next_attack_atk_scale
                next_attack_hits = max(1, skill.effect.next_attack_hit_count)
                consumed_next_attack = True
                operator.current_sp = 0.0
                operator.skill_ready = False
                operator.pending_next_attack = False
                self._emit(state, EventType.SKILL_ACTIVATE, source=operator.operator_id, legal=True,
                           skill=skill.skill_id, automatic=True, next_attack=True)
            self._emit(state, EventType.ATTACK_START, source=operator.operator_id, target=target_id)
            delay = self.projectile_model.hit_delay(source_tile=operator.tile, target_position=target_position)
            raw_override = self._effective_atk(operator) * next_attack_scale
            for _ in range(next_attack_hits):
                self._emit(state, EventType.PROJECTILE_BORN, source=operator.operator_id, target=target_id)
                if delay <= self._EPSILON:
                    self._process_projectile_hit(state, operator.operator_id, target_id, raw_override=raw_override)
                else:
                    pending_hits.append(_PendingHit(state.time + delay, operator.operator_id, target_id, raw_override))
            if delay < 0:
                raise ValueError("Projectile model cannot return a negative delay")
            operator.next_attack_time = state.time + self._effective_interval(state, operator)
            operator.attack_cooldown = self._effective_interval(state, operator)
            if not consumed_next_attack and skill and skill.recovery_mode is SPRecoveryMode.ATTACK and not operator.skill_active and not operator.pending_next_attack:
                operator.current_sp = min(float(skill.sp_cost), operator.current_sp + 1.0)
                if operator.current_sp + self._EPSILON >= skill.sp_cost:
                    operator.skill_ready = True
                    operator.pending_next_attack = True

    def _enemy_outputs(self, state: SimulationState, stage: Stage) -> None:
        for enemy in tuple(sorted(state.active_enemies.values(), key=lambda item: item.spawn_index)):
            self._enemy_ability_outputs(state, stage, enemy)
            if enemy.attack_stand_until > self._EPSILON and state.time + self._EPSILON >= enemy.attack_stand_until:
                self._emit(state, EventType.ATTACK_RECOVERY_END, source=enemy.instance_id)
                enemy.attack_stand_until = 0.0
            if (
                enemy.attack_windup > self._EPSILON
                and not enemy.attack_windup_started
                and state.time + self._EPSILON >= enemy.next_attack_time - enemy.attack_windup
            ):
                self._emit(state, EventType.ATTACK_WINDUP, source=enemy.instance_id)
                enemy.attack_windup_started = True
            if state.time + self._EPSILON < enemy.next_attack_time:
                continue
            target_id = enemy.blocked_by if enemy.blocked_by in state.deployed_operators else None
            if target_id is None and enemy.attack_range is not None:
                position = self._enemy_position(stage, enemy)
                candidates = [operator for operator in state.deployed_operators.values() if hypot(position[0] - operator.tile[0], position[1] - operator.tile[1]) <= enemy.attack_range + self._EPSILON]
                if candidates:
                    target_id = min(candidates, key=lambda item: (hypot(position[0] - item.tile[0], position[1] - item.tile[1]), item.operator_id)).operator_id
            if target_id is None:
                enemy.attack_windup_started = state.time + self._EPSILON < enemy.next_attack_time
                continue
            special_ability = next(
                (
                    ability for ability in enemy.abilities
                    if ability.family == "EVERY_NTH_ATTACK"
                    and ability.attack_count_threshold > 0
                    and enemy.normal_attack_count + 1 >= ability.attack_count_threshold
                ),
                None,
            )
            self._emit(state, EventType.ATTACK_STRIKE, source=enemy.instance_id, target=target_id)
            self._emit(state, EventType.ATTACK_START, source=enemy.instance_id, target=target_id)
            if special_ability:
                self._emit(state, EventType.ENEMY_ABILITY_START, source=enemy.instance_id, ability=special_ability.ability_id, target_count=1)
                self._damage_operator(state, enemy, target_id, special_ability)
                self._emit(state, EventType.ENEMY_ABILITY_HIT, source=enemy.instance_id, target=target_id,
                           ability=special_ability.ability_id, amount=enemy.atk * special_ability.atk_scale,
                           kind=special_ability.damage_type)
                self._emit(state, EventType.ENEMY_STATUS_HIT, source=enemy.instance_id, target=target_id,
                           ability=special_ability.ability_id, status=special_ability.status_name,
                           duration=special_ability.status_duration, attack_speed_delta=special_ability.attack_speed_delta)
                operator = state.deployed_operators.get(target_id)
                if operator:
                    operator.attack_speed_status_until = state.time + special_ability.status_duration
                    operator.attack_speed_status_delta = special_ability.attack_speed_delta
                enemy.normal_attack_count = 0
            else:
                self._damage_operator(state, enemy, target_id)
                enemy.normal_attack_count += 1
            enemy.next_attack_time = state.time + enemy.attack_interval
            enemy.attack_stand_until = max(enemy.attack_stand_until, state.time + enemy.attack_recovery)
            enemy.attack_windup_started = False

    def _advance_enemy_passives(self, state: SimulationState, dt: float) -> None:
        for enemy in tuple(state.active_enemies.values()):
            if enemy.hp_recovery_per_second <= 0.0 or enemy.max_hp <= 0.0 or enemy.hp >= enemy.max_hp:
                continue
            amount = min(enemy.hp_recovery_per_second * dt, enemy.max_hp - enemy.hp)
            enemy.hp += amount
            self._emit(state, EventType.HEAL, source=enemy.instance_id, target=enemy.instance_id,
                       amount=amount, reason="GAME_DATA_PASSIVE_HP_REGENERATION")

    def _enemy_ability_outputs(self, state: SimulationState, stage: Stage, enemy: RuntimeEnemy) -> None:
        if not enemy.abilities:
            return
        if state.time + self._EPSILON < enemy.ability_next_fire_time:
            return
        for ability in enemy.abilities:
            if ability.family != "PERIODIC_AREA_ATTACK":
                continue
            position = self._enemy_position(stage, enemy)
            targets = [
                operator for operator in state.deployed_operators.values()
                if hypot(position[0] - operator.tile[0], position[1] - operator.tile[1]) <= ability.range_radius + self._EPSILON
            ]
            self._emit(state, EventType.ENEMY_ABILITY_START, source=enemy.instance_id, ability=ability.ability_id, target_count=len(targets))
            if not targets:
                break
            for target in sorted(targets, key=lambda item: item.operator_id):
                damage = (
                    arts_damage(enemy.atk * ability.atk_scale, target.magic_resistance)
                    if ability.damage_type == "ARTS" else physical_damage(enemy.atk * ability.atk_scale, target.defense)
                )
                target.hp -= damage
                self._emit(state, EventType.ENEMY_ABILITY_HIT, source=enemy.instance_id, target=target.operator_id,
                           ability=ability.ability_id, amount=damage, kind=ability.damage_type)
                if target.hp <= 0:
                    self._remove_operator(state, target.operator_id, death=True)
            break
        enemy.ability_next_fire_time = state.time + max(ability.cooldown for ability in enemy.abilities)

    def _advance_enemies(self, state: SimulationState, stage: Stage, dt: float) -> None:
        for enemy in list(state.active_enemies.values()):
            if enemy.blocked_by:
                continue
            if enemy.attack_stand_until > state.time + self._EPSILON:
                continue
            route = next(route for route in stage.routes if route.route_id == enemy.route_id)
            if enemy.route_wait_remaining > self._EPSILON:
                enemy.route_wait_remaining = max(0.0, enemy.route_wait_remaining - dt)
                continue
            start, proposed = enemy.distance, min(enemy.distance + enemy.speed * dt, route.length)
            if enemy.route_wait_index < len(route.waits):
                wait = route.waits[enemy.route_wait_index]
                if start - self._EPSILON <= wait.distance <= proposed + self._EPSILON:
                    enemy.distance = wait.distance
                    enemy.route_wait_index += 1
                    enemy.route_wait_remaining = wait.duration
                    continue
            candidates: list[tuple[float, RuntimeOperator]] = []
            for operator in state.deployed_operators.values():
                if len(operator.blocked_enemy_ids) >= self._effective_block(operator):
                    continue
                blocking_distance = route.distance_at(operator.tile)
                if blocking_distance is not None and start - self._EPSILON <= blocking_distance <= proposed + self._EPSILON:
                    candidates.append((blocking_distance, operator))
            if candidates:
                blocking_distance, holder = min(candidates, key=lambda item: (item[0], item[1].operator_id))
                enemy.distance = blocking_distance
                enemy.blocked_by = holder.operator_id
                holder.blocked_enemy_ids.append(enemy.instance_id)
                self._emit(state, EventType.BLOCK, source=holder.operator_id, target=enemy.instance_id)
                continue
            enemy.distance = proposed
            if enemy.distance + self._EPSILON >= route.length:
                state.remaining_life -= enemy.life_point_reduce
                state.enemies_leaked += 1
                self._emit(state, EventType.ENEMY_LEAK, source=enemy.instance_id, amount=enemy.life_point_reduce)
                del state.active_enemies[enemy.instance_id]

    def _advance_operator_runtime(self, state: SimulationState, dt: float) -> None:
        """Run at the new tick time: time-SP only, then duration expiration."""
        for operator in tuple(state.deployed_operators.values()):
            operator.attack_cooldown = max(0.0, operator.next_attack_time - state.time)
            skill = self._skill(operator)
            if not skill:
                continue
            if operator.skill_active:
                operator.skill_remaining_duration = max(0.0, operator.skill_remaining_duration - dt)
                if operator.skill_remaining_duration <= self._EPSILON:
                    operator.skill_active = False
                    operator.skill_remaining_duration = 0.0
                    self._emit(state, EventType.SKILL_END, source=operator.operator_id, skill=skill.skill_id)
            elif skill.recovery_mode is SPRecoveryMode.TIME:
                before = operator.current_sp
                operator.current_sp = min(skill.sp_cost, operator.current_sp + skill.sp_per_second * dt)
                if not operator.skill_ready and before + self._EPSILON < skill.sp_cost <= operator.current_sp + self._EPSILON:
                    operator.skill_ready = True
                    self._emit(state, EventType.SKILL_READY, source=operator.operator_id, skill=skill.skill_id)
                if skill.auto_activate and operator.skill_ready:
                    if skill.effect.next_attack_atk_scale != 1.0:
                        operator.pending_next_attack = True
                    else:
                        self._activate_runtime_skill(state, operator, skill, automatic=True)

    def _apply_maintenance(self, state: SimulationState) -> None:
        for operator_id in tuple(state.deployed_operators):
            operator = state.deployed_operators[operator_id]
            if operator.maintenance_cost <= 0 or operator.maintenance_interval <= 0:
                continue
            if state.time + self._EPSILON < operator.next_maintenance_time:
                continue
            before = state.dp
            if state.dp + self._EPSILON < operator.maintenance_cost:
                self._remove_operator(state, operator_id, death=False)
                self._emit(
                    state, EventType.RETREAT, source=operator_id, legal=True,
                    auto=True, reason="merchant_upkeep_insufficient",
                )
                continue
            state.dp -= operator.maintenance_cost
            operator.next_maintenance_time = state.time + operator.maintenance_interval
            self._emit(
                state, EventType.DP_CHANGE, source=operator_id,
                amount=-operator.maintenance_cost, before=before, after=state.dp,
                reason="merchant_upkeep",
            )

    def run(self, *, stage: Stage, operators: dict[str, Operator], enemies: dict[str, Enemy], strategy: Strategy, config: SimulationConfig | None = None) -> SimulationResult:
        if stage.stage_map is None:
            raise ValueError("Simulation requires a StageMap")
        config = config or SimulationConfig()
        state = SimulationState(0.0, self._number(stage.initial_dp, "initial DP"), stage.initial_life)
        state.active_devices = {
            device.device_id: RuntimeDevice(
                device.device_id, device.template_id, device.tile, device.hp, device.hp,
                device.defense, device.magic_resistance, device.taunt_level,
            )
            for device in stage.devices if device.ordinary_targetable
        }
        actions = sorted(enumerate(strategy.actions), key=lambda item: (item[1].time, item[0]))
        spawns = sorted((event.time + repetition * event.interval, event.enemy_id, event.route_id) for event in stage.spawn_events for repetition in range(event.count))
        action_index = spawn_index = enemy_index = 0
        pending_hits: list[_PendingHit] = []
        last_spawn_time = max((time for time, _, _ in spawns), default=0.0)
        while state.time <= config.max_time + self._EPSILON:
            for hit in sorted([item for item in pending_hits if item.time <= state.time + self._EPSILON], key=lambda item: (item.time, item.source_id, item.target_id)):
                self._process_projectile_hit(state, hit.source_id, hit.target_id, raw_override=hit.raw_override)
                pending_hits.remove(hit)
            while action_index < len(actions) and actions[action_index][1].time <= state.time + self._EPSILON:
                action = actions[action_index][1]
                if action.action_type is ActionType.DEPLOY:
                    self._deploy(state, stage, operators, strategy, action)
                elif action.action_type is ActionType.ACTIVATE_SKILL:
                    self._activate_skill(state, action)
                elif action.action_type is ActionType.RETREAT:
                    self._retreat(state, action)
                action_index += 1
            while spawn_index < len(spawns) and spawns[spawn_index][0] <= state.time + self._EPSILON:
                _, enemy_id, route_id = spawns[spawn_index]
                self._spawn(state, enemies, enemy_id=enemy_id, route_id=route_id, spawn_index=enemy_index)
                spawn_index += 1; enemy_index += 1
            self._apply_maintenance(state)
            self._enemy_outputs(state, stage)
            self._operator_outputs(state, stage, pending_hits)
            self._advance_enemy_passives(state, config.dt)
            if spawn_index == len(spawns) and not state.active_enemies and not pending_hits and state.time + self._EPSILON >= last_spawn_time:
                break
            self._advance_enemies(state, stage, config.dt)
            state.dp += stage.dp_per_second * config.dt
            state.time = round(state.time + config.dt, 10)
            self._advance_operator_runtime(state, config.dt)
        win = state.enemies_leaked == 0 and spawn_index == len(spawns) and not state.active_enemies
        score = (1000.0 if win else 0.0) + state.enemies_killed * 10.0 + state.remaining_life * 5.0 - state.enemies_leaked * 100.0
        route_lengths = {route.route_id: route.length for route in stage.routes}
        remaining_progress = sum(enemy.distance / route_lengths[enemy.route_id] for enemy in state.active_enemies.values())
        remaining_hp = sum(enemy.hp for enemy in state.active_enemies.values())
        return SimulationResult(
            win=win, remaining_life=state.remaining_life, enemies_killed=state.enemies_killed, enemies_leaked=state.enemies_leaked,
            operator_deaths=state.operator_deaths, time_survived=state.time, score=score, final_dp=state.dp,
            enemies_remaining=len(state.active_enemies), remaining_enemy_hp=remaining_hp, remaining_enemy_route_progress=remaining_progress,
            events=tuple(state.events), deployment_errors=tuple(state.deployment_errors),
        )
