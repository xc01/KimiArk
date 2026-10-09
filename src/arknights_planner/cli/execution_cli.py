"""Guarded command line for the single Milestone 8 calibration plan."""
from __future__ import annotations

import argparse
from pathlib import Path
import time

from arknights_planner.execution import (
    ADBDeviceController, ExecutionTrace, MockDeviceController, PredictionTrace,
    StageGameExecutor, compare_prediction_to_execution, load_execution_configuration,
    m7_main_00_01_execution_plan, predict_m7_main_00_01,
)


def _plan_or_error(stage_id: str):
    if stage_id != "0-1":
        raise ValueError("Milestone 8 supports only main_00-01 / 0-1")
    return m7_main_00_01_execution_plan()


def _print_plan(plan, *, calibration_id: str) -> None:
    print("Stage: 0-1")
    print(f"Strategy source: {plan.strategy_source}")
    print("Mode: REAL_GAME_EXECUTION")
    print(f"Execution calibration: {calibration_id}")
    print("Actions:")
    for action in plan.strategy.actions:
        print(f"{action.time:06.3f} {action.action_type.value} {action.operator_id} at {action.tile} facing {action.direction}")
    print("Simulator source approximations:")
    for item in plan.simulator_approximation_policy:
        print(f"  - {item}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="arknights-exec", description="Guarded bounded real-game execution calibration scaffold")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("dry-run", "Resolve M7 execution gestures without device input"), ("run", "Send one explicitly guarded M7 deployment gesture")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("stage_id")
        command.add_argument("--config", type=Path, default=Path("configs/execution/main_00-01.example.json"))
        command.add_argument("--data-root", type=Path, default=Path("data/ArknightsGameData"))
        command.add_argument("--output-dir", type=Path)
        command.add_argument("--execute", action="store_true", help="Required before the run command may send device input")
        command.add_argument("--screenshots", action="store_true", help="Capture configured checkpoints during an actual run")
        if name == "run":
            # Real runs collect the bounded calibration evidence by default. Dry-run
            # remains device-free unless a later tool explicitly requests imagery.
            command.set_defaults(screenshots=True)
    compare = commands.add_parser("compare", help="Compare saved prediction and execution trace files")
    compare.add_argument("execution_trace", type=Path)
    compare.add_argument("prediction_trace", type=Path)
    args = parser.parse_args(argv)

    if args.command == "compare":
        report = compare_prediction_to_execution(PredictionTrace.load(args.prediction_trace), ExecutionTrace.load(args.execution_trace))
        for entry in report.entries:
            print(f"{entry.status.value}: {entry.subject}: {entry.interpretation}")
        return

    plan = _plan_or_error(args.stage_id)
    configuration = load_execution_configuration(args.config)
    output_dir = args.output_dir or Path("output/execution") / time.strftime("%Y%m%d-%H%M%S")
    _print_plan(plan, calibration_id=configuration.calibration_id)
    if args.command == "dry-run":
        controller = MockDeviceController(resolution=configuration.reference_resolution)
        trace = StageGameExecutor(controller, configuration).execute(plan, send_input=False, output_dir=output_dir)
        trace_path = output_dir / "execution-trace.json"
        trace.save(trace_path)
        prediction = predict_m7_main_00_01(args.data_root)
        prediction_path = output_dir / "prediction-trace.json"
        prediction.save(prediction_path)
        print("Dry run: no device input was sent.")
        print(f"Execution trace: {trace_path}")
        print(f"Prediction trace: {prediction_path}")
        return

    if not args.execute:
        parser.error("real device input is blocked; rerun with --execute after checking dry-run output")
    controller = ADBDeviceController(serial=configuration.adb_serial)
    # Resolve and print device facts before a tap/swipe can occur.
    print(f"Selected ADB device: {controller.device_id}")
    print(f"Calibrated device resolution: {controller.screen_size()}")
    trace = StageGameExecutor(controller, configuration).execute(
        plan, send_input=True, output_dir=output_dir, capture_screenshots=args.screenshots,
    )
    trace_path = output_dir / "execution-trace.json"
    trace.save(trace_path)
    prediction = predict_m7_main_00_01(args.data_root)
    prediction_path = output_dir / "prediction-trace.json"
    prediction.save(prediction_path)
    report = compare_prediction_to_execution(prediction, trace)
    report_path = output_dir / "calibration-report.json"
    report.save(report_path)
    print(f"Execution trace: {trace_path}")
    print(f"Prediction trace: {prediction_path}")
    print(f"Calibration report: {report_path}")


if __name__ == "__main__":
    main()
