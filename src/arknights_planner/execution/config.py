"""Local, manually calibrated execution configuration."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .coordinates import FacingGestureMapper, NormalizedPoint, NormalizedVector, StageGridCoordinateMapper, Viewport


def _point(value: list[float] | tuple[float, float]) -> NormalizedPoint:
    return NormalizedPoint(float(value[0]), float(value[1]))


def _vector(value: list[float] | tuple[float, float]) -> NormalizedVector:
    return NormalizedVector(float(value[0]), float(value[1]))


@dataclass(frozen=True)
class ExecutionConfiguration:
    calibration_id: str
    adb_serial: str | None
    reference_resolution: tuple[int, int]
    viewport: Viewport
    stage_grid: StageGridCoordinateMapper
    operator_cards: dict[str, NormalizedPoint]
    facing: FacingGestureMapper
    drag_duration_seconds: float
    direction_duration_seconds: float
    battle_start_offset_seconds: float
    checkpoint_times: tuple[float, ...]

    @classmethod
    def from_dict(cls, value: dict) -> "ExecutionConfiguration":
        viewport = Viewport(**value.get("viewport", {}))
        grid = value["stage_grid"]
        return cls(
            calibration_id=value["calibration_id"],
            adb_serial=value.get("adb_serial"),
            reference_resolution=tuple(value["reference_resolution"]),
            viewport=viewport,
            stage_grid=StageGridCoordinateMapper(
                origin_tile=tuple(grid["origin_tile"]), origin_screen=_point(grid["origin_screen"]),
                x_axis=_vector(grid["x_axis"]), y_axis=_vector(grid["y_axis"]),
                calibration_id=value["calibration_id"],
            ),
            operator_cards={operator_id: _point(point) for operator_id, point in value["operator_cards"].items()},
            facing=FacingGestureMapper(_point(value["facing_gesture"]["distance"])),
            drag_duration_seconds=float(value.get("drag_duration_seconds", 0.35)),
            direction_duration_seconds=float(value.get("direction_duration_seconds", 0.20)),
            battle_start_offset_seconds=float(value.get("battle_start_offset_seconds", 0.0)),
            checkpoint_times=tuple(float(item) for item in value.get("checkpoint_times", ())),
        )


def load_execution_configuration(path: Path) -> ExecutionConfiguration:
    """Load JSON only, avoiding a runtime YAML dependency for this narrow scaffold."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"execution configuration not found: {path}")
    except json.JSONDecodeError as error:
        raise ValueError(f"execution configuration must be JSON: {error}") from error
    return ExecutionConfiguration.from_dict(value)
