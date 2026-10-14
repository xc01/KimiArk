from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from arknights_planner.models.enemy import Enemy, EnemyStats
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.provenance import known
from arknights_planner.models.simulation import EventType
from arknights_planner.models.stage import BattleDevice, SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import runtime_enemies, runtime_operators, runtime_stage
from tests.simulator.test_combat_runtime import events

_SOURCE = "tests/simulator/test_neutral_protected_target.py"


def _neutral() -> Enemy:
    stats = EnemyStats(
        max_hp=known(1_000, _SOURCE, "$.neutral.hp"), atk=known(0, _SOURCE, "$.neutral.atk"),
        defense=known(0, _SOURCE, "$.neutral.def"), magic_resistance=known(0, _SOURCE, "$.neutral.res"),
        move_speed=known(1.0, _SOURCE, "$.neutral.speed"), attack_interval=known(0, _SOURCE, "$.neutral.interval"),
        weight=known(0, _SOURCE, "$.neutral.mass"), life_point_reduce=known(0, _SOURCE, "$.neutral.life"),
        apply_way=known("NONE", _SOURCE, "$.neutral.applyWay"), damage_type=known("NO_DAMAGE", _SOURCE, "$.neutral.damage"),
        counts_as_kill=known(False, _SOURCE, "$.neutral.invalidKilled"),
        counts_as_leak=known(False, _SOURCE, "$.neutral.arrival"),
        death_life_point_reduce=known(1, _SOURCE, "$.neutral.dead"),
        is_neutral=known(True, _SOURCE, "$.neutral.faction"),
    )
    return Enemy("civilian", known("Civilian", _SOURCE, "$.neutral.name"), stats, _SOURCE)


def _selector(*, radius: float = 1.2, speed: float = 0.0) -> Enemy:
    stats = EnemyStats(
        max_hp=known(1_000, _SOURCE, "$.selector.hp"), atk=known(1_200, _SOURCE, "$.selector.atk"),
        defense=known(0, _SOURCE, "$.selector.def"), magic_resistance=known(0, _SOURCE, "$.selector.res"),
        move_speed=known(speed, _SOURCE, "$.selector.speed"), attack_interval=known(1, _SOURCE, "$.selector.interval"),
        weight=known(0, _SOURCE, "$.selector.mass"), life_point_reduce=known(1, _SOURCE, "$.selector.life"),
        apply_way=known("MELEE", _SOURCE, "$.selector.applyWay"), damage_type=known("PHYSICAL", _SOURCE, "$.selector.damage"),
        protected_target_attack_radius=known(radius, _SOURCE, "$.selector.radius"),
    )
    return Enemy("selector", known("Selector", _SOURCE, "$.selector.name"), stats, _SOURCE)


def test_fixed_game_data_marks_civilian_and_officer_correctly() -> None:
    repository = GameDataRepository(Path(__file__).resolve().parents[2] / "data/ArknightsGameData")
    civilian = repository.get_enemy("enemy_3001_upeopl").stats
    officer = repository.get_enemy("enemy_1107_uoffcr").stats
    assert civilian.is_neutral.value is True
    assert officer.protected_target_attack_radius.value == 1.2


def _run(*, stage=None, operators=None, enemies=None, actions=(), max_time: float = 1.2):
    if stage is None:
        stage = replace(
            runtime_stage(),
            spawn_events=(SpawnEvent(0.0, "civilian", "main"), SpawnEvent(0.0, "selector", "main")),
        )
    return Simulator().run(
        stage=stage or runtime_stage(), operators=operators or runtime_operators(),
        enemies=enemies or {}, strategy=Strategy(tuple({"civilian", "selector", "blocker", "healer"}), tuple(actions)),
        config=SimulationConfig(dt=0.1, max_time=max_time),
    )


def targeted(result, event_type: EventType, *, source: str | None = None, target: str | None = None):
    rows = events(result, event_type, source=source)
    return [row for row in rows if target is None or row.target_id == target]


def test_life_zero_or_negative_is_never_a_win() -> None:
    zero = _run(enemies={"civilian": _neutral(), "selector": _selector()})
    assert zero.remaining_life == 0
    assert zero.win is False
    assert zero.first_objective_failure_time is not None
    assert zero.first_objective_failure_reason == "PROTECTED_TARGET_DEATH"

    stage = replace(
        runtime_stage(), initial_life=known(1, _SOURCE, "$.life"),
        spawn_events=(
            SpawnEvent(0.0, "civilian", "main"), SpawnEvent(0.0, "civilian", "main"),
            SpawnEvent(0.0, "selector", "main"),
        ),
    )
    negative = _run(stage=stage, enemies={"civilian": _neutral(), "selector": _selector()})
    negative = Simulator().run(
        stage=stage, operators=runtime_operators(), enemies={"civilian": _neutral(), "selector": _selector()},
        strategy=Strategy(tuple(), tuple()), config=SimulationConfig(dt=0.1, max_time=2.2),
    )
    assert negative.remaining_life < 0
    assert negative.win is False


def test_neutral_safe_arrival_is_not_leak_kill_or_life_loss() -> None:
    stage = replace(runtime_stage(), spawn_events=(SpawnEvent(0.0, "civilian", "main"),))
    result = _run(stage=stage, enemies={"civilian": _neutral()}, max_time=7.2)
    assert events(result, EventType.PROTECTED_TARGET_REACHED, source="civilian#0")
    assert not events(result, EventType.ENEMY_LEAK)
    assert not events(result, EventType.ENEMY_DEATH)
    assert result.enemies_killed == 0
    assert result.enemies_leaked == 0
    assert result.remaining_life == 1


def test_operator_does_not_attack_or_block_neutral_but_enemy_can_attack_it() -> None:
    blocker = Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT")
    result = _run(operators=runtime_operators(), enemies={"civilian": _neutral(), "selector": _selector()}, actions=(blocker,))
    assert not events(result, EventType.ATTACK_START, source="blocker")
    assert not targeted(result, EventType.BLOCK, source="blocker", target="civilian#0")
    assert targeted(result, EventType.TARGET_SELECTION, source="selector#1", target="civilian#0")
    assert targeted(result, EventType.DAMAGE, source="selector#1", target="civilian#0")
    assert not targeted(result, EventType.DAMAGE, source="selector#1", target="blocker")


def test_protected_target_attack_respects_radius() -> None:
    stage = replace(
        runtime_stage(),
        spawn_events=(SpawnEvent(0.0, "civilian", "main"), SpawnEvent(2.0, "selector", "main")),
    )
    result = _run(stage=stage, enemies={"civilian": _neutral(), "selector": _selector(radius=0.1)}, max_time=3.2)
    assert not targeted(result, EventType.TARGET_SELECTION, source="selector#1", target="civilian#0")
    assert not targeted(result, EventType.DAMAGE, source="selector#1", target="civilian#0")


def test_ordinary_medic_selects_deployed_operators_not_neutrals() -> None:
    healer = Action(ActionType.DEPLOY, 0.0, "healer", (3, 2), "UP")
    blocker = Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT")
    brute = replace(runtime_enemies()["brute"], stats=replace(runtime_enemies()["brute"].stats, attack_range=known(3.5, _SOURCE, "$.brute.range"), apply_way=known("RANGED", _SOURCE, "$.brute.applyWay")))
    operators = runtime_operators()
    healer_model = operators["healer"]
    healer_stats = replace(healer_model.phases[0].stats_max, max_hp=known(10_000, _SOURCE, "$.healer.hp"))
    operators["healer"] = replace(healer_model, phases=(replace(healer_model.phases[0], stats_min=healer_stats, stats_max=healer_stats),))
    stage = replace(runtime_stage(), spawn_events=(SpawnEvent(0.0, "civilian", "main"), SpawnEvent(0.0, "brute", "main")))
    result = _run(stage=stage, operators=operators, enemies={"civilian": _neutral(), "brute": brute}, actions=(healer, blocker), max_time=3.2)
    heals = events(result, EventType.HEAL, source="healer")
    assert heals
    assert all(event.target_id == "blocker" for event in heals)
    assert not targeted(result, EventType.HEAL, target="civilian#0")


def test_roadblock_blocks_neutral_but_not_ordinary_enemy() -> None:
    device = BattleDevice("roadblock#0", "trap_020_roadblock", (2, 1), 1, 1, 0, 0, ordinary_targetable=True)
    stage = replace(runtime_stage(), devices=(device,), spawn_events=(SpawnEvent(0.0, "civilian", "main"),))
    neutral = _run(stage=stage, enemies={"civilian": _neutral()}, max_time=3.2)
    assert targeted(neutral, EventType.BLOCK, source="roadblock#0", target="civilian#0")
    assert not targeted(neutral, EventType.BLOCK, source="blocker", target="civilian#0")

    ordinary_stage = replace(stage, spawn_events=(SpawnEvent(0.0, "brute", "main"),))
    ordinary_blocker = Action(ActionType.DEPLOY, 0.0, "blocker", (3, 1), "RIGHT")
    ordinary = _run(stage=ordinary_stage, enemies={"brute": runtime_enemies()["brute"]}, actions=(ordinary_blocker,), max_time=4.2)
    assert targeted(ordinary, EventType.BLOCK, source="blocker", target="brute#0")
    assert not targeted(ordinary, EventType.BLOCK, source="roadblock#0", target="brute#0")
