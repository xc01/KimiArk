from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class Waypoint:
    """A continuous route point in synthetic map coordinates (x=column, y=row)."""

    x: float
    y: float


@dataclass(frozen=True)
class RouteWait:
    """An explicit pause at an already-reached route distance."""

    distance: float
    duration: float


@dataclass(frozen=True)
class Route:
    route_id: str
    waypoints: tuple[Waypoint, ...]
    waits: tuple[RouteWait, ...] = ()

    def __post_init__(self) -> None:
        if len(self.waypoints) < 2:
            raise ValueError("A route requires at least two waypoints")
        if any(wait.distance < 0 or wait.duration < 0 for wait in self.waits):
            raise ValueError("Route wait distances and durations must be non-negative")
        if tuple(sorted(self.waits, key=lambda item: item.distance)) != self.waits:
            raise ValueError("Route waits must be ordered by distance")

    @property
    def length(self) -> float:
        return sum(
            hypot(second.x - first.x, second.y - first.y)
            for first, second in zip(self.waypoints, self.waypoints[1:])
        )

    def position_at(self, distance: float) -> tuple[float, float]:
        """Return a continuous piecewise-linear position clamped to this route."""
        remaining = min(max(distance, 0.0), self.length)
        for first, second in zip(self.waypoints, self.waypoints[1:]):
            segment = hypot(second.x - first.x, second.y - first.y)
            if segment == 0:
                continue
            if remaining <= segment:
                factor = remaining / segment
                return first.x + (second.x - first.x) * factor, first.y + (second.y - first.y) * factor
            remaining -= segment
        last = self.waypoints[-1]
        return last.x, last.y

    def distance_at(self, point: tuple[int, int], *, tolerance: float = 1e-9) -> float | None:
        """Locate an exact tile centre on the route, if it lies on a segment."""
        target_x, target_y = point
        accumulated = 0.0
        for first, second in zip(self.waypoints, self.waypoints[1:]):
            dx, dy = second.x - first.x, second.y - first.y
            segment = hypot(dx, dy)
            if segment == 0:
                continue
            factor = ((target_x - first.x) * dx + (target_y - first.y) * dy) / (segment * segment)
            projected_x, projected_y = first.x + factor * dx, first.y + factor * dy
            if -tolerance <= factor <= 1 + tolerance and hypot(target_x - projected_x, target_y - projected_y) <= tolerance:
                return accumulated + min(max(factor, 0.0), 1.0) * segment
            accumulated += segment
        return None
