from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from arknights_planner.cli.execution_cli import main
from arknights_planner.execution.calibration import ComparisonStatus, compare_prediction_to_execution
from arknights_planner.execution.config import ExecutionConfiguration
from arknights_planner.execution.controller import ADBDeviceController, MockDeviceController
from arknights_planner.execution.coordinates import (
    FacingGestureMapper, NormalizedPoint, NormalizedVector, ScreenCoordinateMapper,
    StageGridCoordinateMapper, Viewport,
)
from arknights_planner.execution.executor import ExecutionPlan, StageGameExecutor, m7_main_00_01_execution_plan
from arknights_planner.execution.prediction import PredictionTrace, prediction_trace_from_result
from arknights_planner.execution.traces import ExecutionTrace
from arknights_planner.models.simulation import SimulationResult, SimulationRunMetadata
from arknights_planner.models.strategy import Action, ActionType, Strategy


def execution_config() -> ExecutionConfiguration:
    return ExecutionConfiguration(
        calibration_id="test-calibration-v1",
        adb_serial=None,
        reference_resolution=(1000, 800),
        viewport=Viewport(0.1, 0.1, 0.8, 0.8),
        stage_grid=StageGridCoordinateMapper(
            origin_tile=(4, 2), origin_screen=NormalizedPoint(0.5, 0.5),
            x_axis=NormalizedVector(0.1, 0.02), y_axis=NormalizedVector(-0.03, -0.1),
            calibration_id="test-calibration-v1",
        ),
        operator_cards={"char_129_bluep": NormalizedPoint(0.2, 0.9), "other": NormalizedPoint(0.3, 0.9)},
        facing=FacingGestureMapper(NormalizedPoint(0.1, 0.1)),
        drag_duration_seconds=0.2,
        direction_duration_seconds=0.1,
        battle_start_offset_seconds=0.0,
        checkpoint_times=(0.5, 3.5),
    )


def simple_plan(*actions: Action) -> ExecutionPlan:
    return ExecutionPlan("0-1", "test", Strategy(tuple(action.operator_id for action in actions), tuple(actions)), ("POLICY",))


def simulation_result() -> SimulationResult:
    return SimulationResult(
        win=True, remaining_life=20, enemies_killed=1, enemies_leaked=0, operator_deaths=0,
        time_survived=6.0, score=1.0, final_dp=0.0, enemies_remaining=0,
        remaining_enemy_hp=0.0, remaining_enemy_route_progress=0.0, events=(), deployment_errors=(),
        run_metadata=SimulationRunMetadata("APPROXIMATE_REAL", ("POLICY",)),
    )


def test_normalized_coordinate_mapping_with_viewport():
    mapper = ScreenCoordinateMapper(1000, 800, Viewport(0.1, 0.2, 0.8, 0.6))
    assert mapper.to_pixels(NormalizedPoint(0.5, 0.5)) == (500, 400)
    assert mapper.to_normalized((500, 400)) == NormalizedPoint(0.5, 0.5)


def test_stage_grid_mapping_preserves_documented_simulator_axes():
    grid = execution_config().stage_grid
    assert grid.tile_to_normalized((4, 2)) == NormalizedPoint(0.5, 0.5)
    point = grid.tile_to_normalized((5, 3))
    assert point.x == pytest.approx(0.57)
    assert point.y == pytest.approx(0.42)


@pytest.mark.parametrize("direction,expected", [("RIGHT", (580, 400)), ("DOWN", (500, 480)), ("LEFT", (420, 400)), ("UP", (500, 320))])
def test_facing_gesture_mapping(direction, expected):
    mapper = ScreenCoordinateMapper(1000, 800)
    assert FacingGestureMapper(NormalizedPoint(0.08, 0.10)).endpoint((500, 400), direction, mapper) == expected


def test_shared_deadline_schedule_avoids_cumulative_sleep_drift(tmp_path):
    configuration = replace(execution_config(), checkpoint_times=())
    controller = MockDeviceController(resolution=configuration.reference_resolution, now=100.0)
    plan = simple_plan(
        Action(ActionType.DEPLOY, 1.0, "char_129_bluep", (4, 2), "LEFT"),
        Action(ActionType.DEPLOY, 2.0, "other", (5, 2), "RIGHT"),
    )
    trace = StageGameExecutor(controller, configuration).execute(plan, send_input=True, output_dir=tmp_path)
    sleeps = [item[1] for item in controller.commands if item[0] == "sleep_until"]
    assert sleeps[:2] == [101.0, 102.0]
    assert [item.command_start_monotonic for item in trace.actions] == [101.0, 102.0]
    assert all(item.command_lateness_seconds == 0.0 for item in trace.actions)


def test_mock_deploy_gesture_records_card_tile_direction_and_timestamps(tmp_path):
    configuration = replace(execution_config(), checkpoint_times=())
    controller = MockDeviceController(resolution=configuration.reference_resolution)
    plan = simple_plan(Action(ActionType.DEPLOY, 1.0, "char_129_bluep", (4, 2), "LEFT"))
    trace = StageGameExecutor(controller, configuration).execute(plan, send_input=True, output_dir=tmp_path, capture_screenshots=True)
    record = trace.actions[0]
    assert [item[0] for item in controller.commands] == ["sleep_until", "screenshot", "tap", "swipe", "swipe", "screenshot"]
    assert record.card_pixel is not None and record.tile_pixel is not None and record.facing_pixel is not None
    assert record.command_start_monotonic is not None
    assert record.tile_placement_monotonic is not None
    assert record.direction_selection_monotonic is not None
    assert record.command_end_monotonic == record.direction_selection_monotonic
    assert len(trace.observations) == 2


def test_execution_trace_serialization_round_trip(tmp_path):
    controller = MockDeviceController(resolution=(1000, 800))
    trace = StageGameExecutor(controller, execution_config()).execute(
        m7_main_00_01_execution_plan(), send_input=False, output_dir=tmp_path,
    )
    path = tmp_path / "trace.json"
    trace.save(path)
    assert ExecutionTrace.load(path) == trace


def test_prediction_trace_generation_is_compact_and_includes_battle_end():
    trace = prediction_trace_from_result(m7_main_00_01_execution_plan(), simulation_result())
    assert trace.simulator_mode == "APPROXIMATE_REAL"
    assert trace.predicted_terminal_state == "WIN"
    assert trace.events[-1].kind == "BATTLE_END"


def test_calibration_report_distinguishes_observed_unobserved_and_cannot_compare(tmp_path):
    controller = MockDeviceController(resolution=(1000, 800))
    execution = StageGameExecutor(controller, execution_config()).execute(
        m7_main_00_01_execution_plan(), send_input=True, output_dir=tmp_path,
    )
    prediction = prediction_trace_from_result(m7_main_00_01_execution_plan(), simulation_result())
    report = compare_prediction_to_execution(prediction, execution)
    assert ComparisonStatus.OBSERVED in {entry.status for entry in report.entries}
    assert ComparisonStatus.UNOBSERVED in {entry.status for entry in report.entries}
    assert ComparisonStatus.CANNOT_COMPARE in {entry.status for entry in report.entries}


def test_dry_run_resolves_gestures_but_sends_no_input(tmp_path):
    controller = MockDeviceController(resolution=(1000, 800))
    trace = StageGameExecutor(controller, execution_config()).execute(
        m7_main_00_01_execution_plan(), send_input=False, output_dir=tmp_path,
    )
    assert trace.dry_run is True
    assert controller.commands == []
    assert trace.actions[0].card_pixel is not None
    assert trace.actions[0].command_start_monotonic is None


def test_cli_requires_explicit_execute_guard(tmp_path):
    config_path = Path(__file__).resolve().parents[1] / "configs/execution/main_00-01.example.json"
    with pytest.raises(SystemExit):
        main(["run", "0-1", "--config", str(config_path), "--output-dir", str(tmp_path)])


def test_adb_command_construction_never_contacts_a_live_device():
    assert ADBDeviceController.command_for(
        adb_path="adb", serial="emulator-5554", arguments=("shell", "input", "tap", "10", "20"),
    ) == ("adb", "-s", "emulator-5554", "shell", "input", "tap", "10", "20")


@pytest.mark.device_integration
@pytest.mark.skipif(not os.getenv("ARKNIGHTS_RUN_DEVICE_TESTS"), reason="requires explicit local device-test opt-in")
def test_optional_live_device_environment_is_explicitly_opted_in():
    """Reserved marker only; real experiments are manually bounded by the CLI."""
    assert os.getenv("ARKNIGHTS_RUN_DEVICE_TESTS") == "1"
