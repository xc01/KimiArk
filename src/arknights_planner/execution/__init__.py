"""Isolated, opt-in real-client execution and calibration scaffolding.

Nothing in this package is imported by GameData loading, simulation, or search.
"""

from .calibration import CalibrationReport, ComparisonEntry, ComparisonStatus, compare_prediction_to_execution
from .config import ExecutionConfiguration, load_execution_configuration
from .controller import ADBDeviceController, DeviceController, MockDeviceController
from .coordinates import FacingGestureMapper, NormalizedPoint, NormalizedVector, ScreenCoordinateMapper, StageGridCoordinateMapper, Viewport
from .executor import ExecutionPlan, StageGameExecutor, m7_main_00_01_execution_plan
from .prediction import PredictionTrace, predict_m7_main_00_01
from .traces import ExecutionTrace

__all__ = [
    "ADBDeviceController", "CalibrationReport", "ComparisonEntry", "ComparisonStatus",
    "DeviceController", "ExecutionConfiguration", "ExecutionPlan", "ExecutionTrace",
    "FacingGestureMapper", "MockDeviceController", "NormalizedPoint", "NormalizedVector", "PredictionTrace",
    "ScreenCoordinateMapper", "StageGameExecutor", "StageGridCoordinateMapper", "Viewport",
    "compare_prediction_to_execution", "load_execution_configuration", "m7_main_00_01_execution_plan",
    "predict_m7_main_00_01",
]
