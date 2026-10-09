"""Configuration-driven coordinate mappings for the bounded 0-1 executor."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedPoint:
    """A point expressed relative to a configured viewport, in [0, 1] coordinates."""

    x: float
    y: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.x <= 1.0 or not 0.0 <= self.y <= 1.0:
            raise ValueError("normalized coordinates must be in [0, 1]")


@dataclass(frozen=True)
class NormalizedVector:
    """A signed viewport-relative vector used by stage-grid calibration axes."""

    x: float
    y: float


@dataclass(frozen=True)
class Viewport:
    """Normalized device rectangle containing the game viewport."""

    left: float = 0.0
    top: float = 0.0
    width: float = 1.0
    height: float = 1.0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("viewport dimensions must be positive")
        if self.left < 0 or self.top < 0 or self.left + self.width > 1 or self.top + self.height > 1:
            raise ValueError("viewport must be contained in normalized device bounds")


@dataclass(frozen=True)
class ScreenCoordinateMapper:
    """Maps configured normalized points into current screenshot/device pixels."""

    width: int
    height: int
    viewport: Viewport = Viewport()

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("screen resolution must be positive")

    def to_pixels(self, point: NormalizedPoint) -> tuple[int, int]:
        x = (self.viewport.left + point.x * self.viewport.width) * self.width
        y = (self.viewport.top + point.y * self.viewport.height) * self.height
        return round(x), round(y)

    def delta_to_pixels(self, point: NormalizedPoint) -> tuple[int, int]:
        return round(point.x * self.viewport.width * self.width), round(point.y * self.viewport.height * self.height)

    def to_normalized(self, pixel: tuple[int, int]) -> NormalizedPoint:
        x = (pixel[0] / self.width - self.viewport.left) / self.viewport.width
        y = (pixel[1] / self.height - self.viewport.top) / self.viewport.height
        return NormalizedPoint(x, y)


@dataclass(frozen=True)
class StageGridCoordinateMapper:
    """Affine, manually calibrated map from simulator tile `(x, y)` to screen space.

    Simulator coordinates use x rightward and y upward.  `origin_tile` and the two
    normalized axis vectors must be calibrated for the fixed stage/camera layout;
    they are independent from real attack-range rotation semantics.
    """

    origin_tile: tuple[int, int]
    origin_screen: NormalizedPoint
    x_axis: NormalizedVector
    y_axis: NormalizedVector
    calibration_id: str

    def tile_to_normalized(self, tile: tuple[int, int]) -> NormalizedPoint:
        dx = tile[0] - self.origin_tile[0]
        dy = tile[1] - self.origin_tile[1]
        point = NormalizedPoint(
            self.origin_screen.x + dx * self.x_axis.x + dy * self.y_axis.x,
            self.origin_screen.y + dx * self.x_axis.y + dy * self.y_axis.y,
        )
        return point

    def tile_to_pixels(self, tile: tuple[int, int], mapper: ScreenCoordinateMapper) -> tuple[int, int]:
        return mapper.to_pixels(self.tile_to_normalized(tile))


@dataclass(frozen=True)
class FacingGestureMapper:
    """Maps four simulator direction labels to a configured normalized swipe delta."""

    distance: NormalizedPoint

    def endpoint(self, origin: tuple[int, int], direction: str, mapper: ScreenCoordinateMapper) -> tuple[int, int]:
        vector = {
            "RIGHT": (self.distance.x, 0.0),
            "DOWN": (0.0, self.distance.y),
            "LEFT": (-self.distance.x, 0.0),
            "UP": (0.0, -self.distance.y),
        }.get(direction)
        if vector is None:
            raise ValueError(f"unsupported facing direction: {direction}")
        dx, dy = mapper.delta_to_pixels(NormalizedPoint(abs(vector[0]), abs(vector[1])))
        return origin[0] + (dx if vector[0] >= 0 else -dx), origin[1] + (dy if vector[1] >= 0 else -dy)
