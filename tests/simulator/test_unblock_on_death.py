from __future__ import annotations

from dataclasses import replace

from arknights_planner.models.operator import OperatorPhase, OperatorStats
from arknights_planner.models.provenance import known
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import (
    synthetic_enemies,
    synthetic_operators,
    synthetic_stage,
)


_SOURCE = "tests/simulator/test_unblock_on_death.py"


def _strong_guard(*, block: int = 1) -> dict[str, object]:
    operators = synthetic_operators()
    guard = operators["guard"]
    stats = replace(guard.phases[0].stats_max, atk=known(30, _SOURCE, "$.atk"), max_hp=known(10_000, _SOURCE, "$.hp"))
    phase = replace(guard.phases[0], stats_min=stats, stats_max=stats)
    operators["guard"] = replace(guard, phases=(phase,), attack_range=((0, 0),))
    if block != 1:
        stats = replace(stats, block_count=known(block, _SOURCE, "$.block"))
        phase = replace(phase, stats_min=stats, stats_max=stats)
        operators["guard"] = replace(guard, phases=(phase,))
    return operators


def _stage(*spawn_frames: int):
    stage = synthetic_stage()
    return replace(
        stage,
        spawn_events=tuple(SpawnEvent(frame / 30, "slug", "main") for frame in spawn_frames),
        initial_life=known(max(1, len(spawn_frames)), _SOURCE, "$.life"),
    )


def test_direct_death_releases_slot_and_next_enemy_is_blocked() -> None:
    stage = _stage(0, 360)
    result = Simulator().run(
        stage=stage, operators=_strong_guard(), enemies=synthetic_enemies(),
        strategy=Strategy(("guard",), (Action(ActionType.DEPLOY, 0, "guard", (3, 1), "RIGHT"),)),
        config=SimulationConfig(dt=1 / 30, max_time=15.0),
    )
    assert [event.target_id for event in result.events if event.event_type.value == "BLOCK"] == ["slug#0", "slug#1"]
    assert [event.target_id for event in result.events if event.event_type.value == "UNBLOCK"] == ["slug#0"]
    assert result.enemies_killed == 1
    assert result.enemies_leaked == 0


def test_projectile_death_releases_slot_and_next_enemy_is_blocked() -> None:
    operators = _strong_guard()
    guard = operators["guard"]
    stats = replace(guard.phases[0].stats_max, atk=known(0, _SOURCE, "$.atk"), max_hp=known(10_000, _SOURCE, "$.hp"))
    operators["guard"] = replace(guard, phases=(replace(guard.phases[0], stats_min=stats, stats_max=stats),))
    archer = operators["archer"]
    stats = replace(archer.phases[0].stats_max, atk=known(30, _SOURCE, "$.atk"), max_hp=known(10_000, _SOURCE, "$.hp"))
    operators["archer"] = replace(archer, phases=(replace(archer.phases[0], stats_min=stats, stats_max=stats),))
    stage = _stage(0, 360)
    result = Simulator().run(
        stage=stage, operators=operators, enemies=synthetic_enemies(),
        strategy=Strategy(("guard", "archer"), (
            Action(ActionType.DEPLOY, 0, "guard", (3, 1), "RIGHT"),
            Action(ActionType.DEPLOY, 0, "archer", (3, 2), "UP"),
        )),
        config=SimulationConfig(dt=1 / 30, max_time=20.0),
    )
    projectile_kills = [event for event in result.events if event.event_type.value == "ENEMY_DEATH" and event.source_id == "archer"]
    assert len(projectile_kills) == 2
    assert [event.target_id for event in result.events if event.event_type.value == "BLOCK"] == ["slug#0", "slug#1"]
    assert [event.target_id for event in result.events if event.event_type.value == "UNBLOCK"] == ["slug#0", "slug#1"]
    assert result.enemies_killed == 2
    assert result.enemies_leaked == 0


def test_multi_block_releases_only_the_dead_enemy() -> None:
    operators = _strong_guard(block=2)
    enemies = synthetic_enemies()
    weakened = replace(enemies["slug"], enemy_id="weakened")
    enemies["weakened"] = weakened
    slug_stats = replace(enemies["slug"].stats, max_hp=known(80, _SOURCE, "$.hp"))
    enemies["slug"] = replace(enemies["slug"], stats=slug_stats)
    stage = replace(_stage(0, 90, 720), spawn_events=(
        SpawnEvent(0, "slug", "main"), SpawnEvent(3, "weakened", "main"), SpawnEvent(24, "slug", "main"),
    ))
    result = Simulator().run(
        stage=stage, operators=operators, enemies=enemies,
        strategy=Strategy(("guard",), (Action(ActionType.DEPLOY, 0, "guard", (3, 1), "RIGHT"),)),
        config=SimulationConfig(dt=1 / 30, max_time=6.0),
    )
    unblocks = [event.target_id for event in result.events if event.event_type.value == "UNBLOCK"]
    blocks = [event.target_id for event in result.events if event.event_type.value == "BLOCK"]
    assert unblocks == ["slug#0"]
    assert blocks[:2] == ["slug#0", "weakened#1"]
    assert result.enemies_killed == 1
    assert result.enemies_leaked == 0
