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
    movement_mode: str = "WALK"
    hidden_spans: tuple[tuple[float, float], ...] = ()

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

    def distances_at(self, point: tuple[int, int], *, tolerance: float = 1e-9) -> tuple[float, ...]:
        """Return every exact traversal distance, preserving repeated visits."""
        target_x, target_y = point
        distances: list[float] = []
        accumulated = 0.0
        for first, second in zip(self.waypoints, self.waypoints[1:]):
            dx, dy = second.x - first.x, second.y - first.y
            segment = hypot(dx, dy)
            if segment == 0:
                continue
            factor = ((target_x - first.x) * dx + (target_y - first.y) * dy) / (segment * segment)
            projected_x, projected_y = first.x + factor * dx, first.y + factor * dy
            if -tolerance <= factor <= 1 + tolerance and hypot(target_x - projected_x, target_y - projected_y) <= tolerance:
                distance = accumulated + min(max(factor, 0.0), 1.0) * segment
                if not distances or abs(distance - distances[-1]) > tolerance:
                    distances.append(distance)
            accumulated += segment
        return tuple(distances)

    def hidden_at(self, distance: float, *, tolerance: float = 1e-9) -> bool:
        return any(start - tolerance <= distance <= end + tolerance for start, end in self.hidden_spans)

    def blocking_windows(
        self,
        point: tuple[float, float],
        *,
        radius: float,
        tolerance: float = 1e-9,
    ) -> tuple[tuple[float, float], ...]:
        """Return route-distance intervals whose centres enter a circular blocker."""
        if radius < 0:
            raise ValueError("blocker radius must be non-negative")
        windows: list[tuple[float, float]] = []
        accumulated = 0.0
        for first, second in zip(self.waypoints, self.waypoints[1:]):
            dx, dy = second.x - first.x, second.y - first.y
            segment_length = hypot(dx, dy)
            if segment_length == 0:
                continue
            # Project onto the infinite line before clipping.  Clamping the
            # projection before computing half_chord makes a nearby endpoint
            # look closer than the true line segment intersection.
            factor = ((point[0] - first.x) * dx + (point[1] - first.y) * dy) / (segment_length * segment_length)
            closest_x = first.x + factor * dx
            closest_y = first.y + factor * dy
            perpendicular_distance = hypot(point[0] - closest_x, point[1] - closest_y)
            if perpendicular_distance <= radius + tolerance:
                half_chord = max(0.0, radius * radius - perpendicular_distance * perpendicular_distance) ** 0.5
                line_start = factor * segment_length - half_chord
                line_end = factor * segment_length + half_chord
                start = accumulated + min(max(line_start, 0.0), segment_length)
                end = accumulated + min(max(line_end, 0.0), segment_length)
                if end - start > -tolerance:
                    windows.append((start, end))
            accumulated += segment_length
        merged: list[tuple[float, float]] = []
        for start, end in sorted(windows):
            if merged and start <= merged[-1][1] + tolerance:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return tuple(merged)

    def time_at_distance(self, distance: float, *, speed: float) -> float:
        """Movement time including source waits strictly before this distance."""
        if speed <= 0:
            raise ValueError("route time requires a positive move speed")
        elapsed = distance / speed
        return elapsed + sum(wait.duration for wait in self.waits if wait.distance < distance)

    def times_at_point(self, point: tuple[int, int], *, speed: float) -> tuple[float, ...]:
        """Arrival times for every repeated visit to an exact tile centre."""
        return tuple(self.time_at_distance(distance, speed=speed) for distance in self.distances_at(point))
