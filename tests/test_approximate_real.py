from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from arknights_planner.adapters import (
    ApproximateRealExecutionError, ApproximateRealSimulationAdapter, RealExecutionMode,
    RealSimulationApproximationPolicy, StrictSimulationCompatibilityError,
)
from arknights_planner.cli.plan_cli import main
from arknights_planner.cli.data_cli import main as data_main
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.simulation import EventType
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Strategy
from arknights_planner.simulator import ApproximateRealRangeTransformer, SimulationConfig, Simulator


@pytest.fixture(scope="module")
def local_gamedata_root() -> Path:
    root = Path(__file__).resolve().parents[1] / "data/ArknightsGameData"
    if not (root / "zh_CN/gamedata/excel/character_table.json").is_file():
        pytest.skip("locally supplied ArknightsGameData is not available")
    return root


@pytest.fixture()
def adapter(local_gamedata_root: Path) -> ApproximateRealSimulationAdapter:
    return ApproximateRealSimulationAdapter(GameDataRepository(local_gamedata_root))


def test_strict_mode_still_refuses_real_0_1(adapter):
    with pytest.raises(StrictSimulationCompatibilityError):
        adapter.run_main_00_01(mode=RealExecutionMode.STRICT_REAL)


def test_approximate_mode_requires_explicit_policy(adapter):
    with pytest.raises(ApproximateRealExecutionError, match="requires an explicit"):
        adapter.run_main_00_01(mode=RealExecutionMode.APPROXIMATE_REAL)


@pytest.mark.parametrize(
    ("direction", "expected"),
    (("RIGHT", {(6, 5)}), ("DOWN", {(5, 6)}), ("LEFT", {(4, 5)}), ("UP", {(5, 4)})),
)
def test_approximate_real_range_transform_has_explicit_four_facing_rule(direction, expected):
    # Raw real cell (row=0, col=1) is treated as one forward cell only by this approximation.
    assert ApproximateRealRangeTransformer().covered_tiles(origin=(5, 5), offsets=((0, 1),), direction=direction) == expected


def test_real_tile_mapping_and_route_conversion_are_source_derived(adapter):
    fixture = adapter.build_fixture(
        stage_id_or_code="0-1", selections=adapter.default_main_00_01_selections(),
        policy=RealSimulationApproximationPolicy.main_00_01(),
    )
    tiles = {item.coordinate: item for item in fixture.tile_mappings}
    assert (tiles[(4, 2)].source_tile_key, tiles[(4, 2)].simulator_category) == ("tile_wall", "HIGH_GROUND")
    assert (tiles[(1, 3)].source_tile_key, tiles[(1, 3)].simulator_category) == ("tile_road", "GROUND")

    route = next(item for item in fixture.stage.routes if item.route_id == "route-2")
    assert [(point.x, point.y) for point in route.waypoints] == [(8.0, 3.0), (3.0, 2.0), (3.0, 3.0), (1.0, 3.0), (1.0, 2.0), (0.0, 2.0)]
    one_step = route.position_at(1.0)
    assert one_step[0] < 8.0 and one_step[1] < 3.0


def test_real_enemy_uses_converted_0_1_route_until_leak(adapter):
    fixture = adapter.build_fixture(
        stage_id_or_code="0-1", selections=adapter.default_main_00_01_selections(),
        policy=RealSimulationApproximationPolicy.main_00_01(),
    )
    single_spawn_stage = replace(
        fixture.stage,
        spawn_events=(SpawnEvent(0.0, "enemy_1007_slime", "route-2"),),
    )
    result = Simulator(range_transformer=ApproximateRealRangeTransformer()).run(
        stage=single_spawn_stage, operators=fixture.operators, enemies=fixture.enemies,
        strategy=Strategy((), ()), config=SimulationConfig(dt=0.1, max_time=12.0),
    )
    leak = [event for event in result.events if event.event_type is EventType.ENEMY_LEAK]
    assert result.enemies_leaked == 1
    assert leak[0].time >= 10.0  # It traverses the converted source route before leaking.


def test_approximated_spawn_timeline_is_deterministic_and_preserves_hierarchy(adapter):
    policy = RealSimulationApproximationPolicy.main_00_01()
    first = adapter.build_fixture(stage_id_or_code="0-1", selections=adapter.default_main_00_01_selections(), policy=policy)
    second = adapter.build_fixture(stage_id_or_code="0-1", selections=adapter.default_main_00_01_selections(), policy=policy)
    assert first.spawn_timeline == second.spawn_timeline
    assert [item.time for item in first.spawn_timeline] == [5.0, 13.0, 21.0, 26.0, 29.0, 36.0, 37.0]
    assert len(first.stage.level_structure.waves[0].fragments) == 6
    assert first.spawn_timeline[0].fragment_index == 1
    assert set(first.enemies) == {"enemy_1007_slime", "enemy_1002_nsabr"}


def test_fixed_0_1_run_has_manifest_uses_base_attack_time_and_does_not_execute_skills(adapter):
    run = adapter.run_main_00_01(
        mode=RealExecutionMode.APPROXIMATE_REAL,
        policy=RealSimulationApproximationPolicy.main_00_01(),
    )
    result = run.result
    bluep = run.fixture.operators["char_129_bluep"]
    attack_times = [event.time for event in result.events if event.event_type is EventType.ATTACK_START and event.source_id == "char_129_bluep"]

    assert bluep.phases[0].stats_max.attack_interval.value == 1.0
    assert attack_times[1] - attack_times[0] == 1.0
    assert result.run_metadata is not None
    assert result.run_metadata.mode == "APPROXIMATE_REAL"
    assert run.execution_report.simulator_executable is True
    assert run.execution_report.strategy_uses_real_skill is False
    assert "ZERO_WINDUP_ZERO_EXTRA_RECOVERY" in result.run_metadata.approximations_used
    assert "INSTANT_PROJECTILE" in result.run_metadata.approximations_used
    assert run.fixture.ignored_real_skill_data == ("char_129_bluep", "char_010_chen")
    assert not any(event.event_type is EventType.SKILL_ACTIVATE for event in result.events)
    assert result.win is True
    assert result.enemies_killed == 11
    assert result.enemies_leaked == 0
    assert {event.event_type for event in result.events} >= {EventType.SPAWN, EventType.DEPLOY, EventType.BLOCK, EventType.ATTACK_START, EventType.DAMAGE, EventType.ENEMY_DEATH}


def test_real_demo_cli_identifies_approximate_mode(local_gamedata_root, capsys):
    main(["real-demo", "0-1", "--data-root", str(local_gamedata_root)])
    output = capsys.readouterr().out
    assert "Mode: APPROXIMATE_REAL" in output
    assert "not an exact Arknights simulation" in output
    assert "INSTANT_PROJECTILE" in output
    assert "Result: WIN" in output


def test_approximate_stage_view_exposes_tile_mapping_and_spawn_timeline(local_gamedata_root, capsys):
    data_main(["--data-root", str(local_gamedata_root), "approximate-stage-view", "0-1"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "APPROXIMATE_REAL_INSPECTION"
    assert payload["tile_mappings"][0]["source_tile_key"] == "tile_forbidden"
    assert payload["approximated_spawn_timeline"][0]["time"] == 5.0
