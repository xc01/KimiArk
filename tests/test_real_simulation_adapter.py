from __future__ import annotations

import json
from pathlib import Path

import pytest

from arknights_planner.adapters import RealSimulationAdapter, StrictSimulationCompatibilityError
from arknights_planner.cli.data_cli import main
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.provenance import KnowledgeStatus


def test_real_shaped_fixture_adapts_exact_keyframe_without_interpolation(gamedata_root):
    adapter = RealSimulationAdapter(GameDataRepository(gamedata_root))
    operator = adapter.adapt_operator("char_test", phase_index=0, level=50, skill_level_index=0)

    assert operator.structurally_loadable is True
    assert operator.exact_keyframe is not None
    assert operator.exact_keyframe.stats.atk.value == 500
    assert operator.exact_keyframe.stats.redeploy_time.value == 70
    assert operator.attack_range is not None
    assert operator.attack_range.cells == ()
    assert operator.skill is not None
    assert operator.skill.selected_level.blackboard_parameters[0].value.source_path.endswith("blackboard[0].value")
    assert operator.skill.simulator_executable is False

    unsupported = adapter.adapt_operator("char_test", phase_index=0, level=2)
    assert unsupported.exact_keyframe is None
    assert "interpolation is unsupported" in unsupported.adaptation_blockers[0]


def test_real_shaped_stage_preserves_hierarchy_and_strict_mode_refuses_execution(gamedata_root):
    adapter = RealSimulationAdapter(GameDataRepository(gamedata_root))
    bundle = adapter.adapt_combination(
        operator_id_or_name="char_test", operator_phase=0, operator_level=50,
        enemy_id_or_name="enemy_test", enemy_level=0, stage_id_or_code="1-7",
    )

    assert bundle.stage.structure is not None
    assert bundle.stage.structure.map_indices == ((0, 1, 2), (3, 4, 5))
    assert len(bundle.stage.structure.routes) == 1
    assert len(bundle.stage.structure.waves) == 1
    assert bundle.stage.structure.waves[0].fragments[0].actions[0].pre_delay.status is KnowledgeStatus.UNKNOWN
    assert len(bundle.stage.spawn_actions) == 1
    assert bundle.report.structurally_loadable is True
    assert bundle.report.simulator_executable is False
    assert any("absolute SPAWN timing" in blocker for blocker in bundle.report.blockers)
    with pytest.raises(StrictSimulationCompatibilityError):
        adapter.require_simulator_execution(bundle)


@pytest.fixture(scope="module")
def local_gamedata_root() -> Path:
    root = Path(__file__).resolve().parents[1] / "data/ArknightsGameData"
    if not (root / "zh_CN/gamedata/excel/character_table.json").is_file():
        pytest.skip("locally supplied ArknightsGameData is not available")
    return root


def _real_bundle(local_gamedata_root: Path):
    return RealSimulationAdapter(GameDataRepository(local_gamedata_root)).adapt_combination(
        operator_id_or_name="char_002_amiya", operator_phase=0, operator_level=1,
        enemy_id_or_name="enemy_1007_slime", enemy_level=0, stage_id_or_code="0-1",
    )


def test_real_amiya_skill_and_range_are_loaded_without_synthetic_execution(local_gamedata_root):
    bundle = _real_bundle(local_gamedata_root)
    operator = bundle.operator

    assert operator.operator.operator_id == "char_002_amiya"
    assert operator.exact_keyframe is not None
    assert operator.exact_keyframe.stats.atk.value == 276
    assert operator.attack_range is not None
    assert [(cell.row, cell.col) for cell in operator.attack_range.cells[:3]] == [(1, 0), (1, 1), (1, 2)]
    assert operator.operator.attack_range == ()  # No synthetic rotation is applied to real data.
    assert operator.skill is not None
    assert operator.skill.skill.skill_id == "skcom_magic_rage[3]"
    assert operator.skill.selected_level.initial_sp.value == 0
    assert operator.skill.selected_level.sp_cost.value == 40
    assert operator.skill.selected_level.duration.value == 30.0
    assert operator.skill.selected_level.blackboard_parameters[0].key.value == "attack_speed"
    assert operator.skill.simulator_executable is False


def test_real_slime_and_stage_structure_retain_source_backed_facts(local_gamedata_root):
    bundle = _real_bundle(local_gamedata_root)
    enemy = bundle.enemy.enemy
    stage = bundle.stage

    assert enemy.stats.max_hp.value == 550
    assert enemy.stats.atk.value == 130
    assert enemy.stats.attack_interval.value == 1.7
    assert enemy.stats.life_point_reduce.value == 1
    assert stage.stage.stage_id == "main_00-01"
    assert (stage.stage.map_width.value, stage.stage.map_height.value) == (9, 6)
    assert (stage.stage.initial_dp.value, stage.stage.deployment_limit.value) == (10, 8)
    assert stage.stage.enemy_references == (("enemy_1007_slime", 0), ("enemy_1002_nsabr", 0))
    assert stage.structure is not None
    assert len(stage.structure.routes) == 10
    assert stage.structure.routes[0].start_position is not None
    assert stage.structure.routes[0].start_position.row.value == 0
    assert stage.structure.routes[0].start_position.col.value == 0
    assert stage.structure.tile_records[0].tile_key.value == "tile_forbidden"
    assert len(stage.structure.waves) == 1
    assert len(stage.structure.waves[0].fragments) == 6
    assert len(stage.spawn_actions) == 7
    first_spawn = stage.spawn_actions[0]
    assert first_spawn.key.value == "enemy_1007_slime"
    assert first_spawn.pre_delay.value == 3.0


def test_real_higher_enemy_level_unknowns_are_not_merged(local_gamedata_root):
    enemy = RealSimulationAdapter(GameDataRepository(local_gamedata_root)).adapt_enemy("enemy_1007_slime", level=1)
    assert enemy.enemy.stats.max_hp.value == 2050
    assert enemy.enemy.stats.defense.status is KnowledgeStatus.UNKNOWN
    assert any("DEF is UNKNOWN" in blocker for blocker in enemy.adaptation_blockers)


def test_real_compatibility_cli_reports_strict_blockers(local_gamedata_root, capsys):
    main(["--data-root", str(local_gamedata_root), "simulation-compatibility", "0-1"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["structurally_loadable"] is True
    assert payload["simulator_executable"] is False
    assert payload["status_counts"]["KNOWN"] > 0
    assert any("range row/col transformation" in blocker for blocker in payload["blockers"])
