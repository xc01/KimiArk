from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import hypot
from typing import Callable


Coordinate = tuple[int, int]


class WalkNavigationError(ValueError):
    pass


GRID_FOUR_WAYS: tuple[Coordinate, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))


def bresenham_clear(
    first: Coordinate,
    second: Coordinate,
    clear: Callable[[Coordinate], bool],
) -> bool:
    """Mirror the client tile-centre Bresenham raycast and its corner rule."""
    first_row, first_col = first
    second_row, second_col = second
    row_delta = abs(second_row - first_row)
    col_delta = abs(second_col - first_col)
    row_step = 1 if second_row > first_row else -1
    col_step = 1 if second_col > first_col else -1
    error = col_delta - row_delta
    if not clear(first):
        return False
    row, col = first
    while (row, col) != (second_row, second_col):
        doubled_error = 2 * error
        next_row, next_col = row, col
        if doubled_error > -row_delta:
            error -= row_delta
            next_col += col_step
        if doubled_error < col_delta:
            error += col_delta
            next_row += row_step
        if next_row != row and next_col != col and not (clear((next_row, col)) and clear((row, next_col))):
            return False
        row, col = next_row, next_col
        if not clear((row, col)):
            return False
    return True


def segment_clear(
    first: Coordinate,
    second: Coordinate,
    clear: Callable[[Coordinate], bool],
) -> bool:
    """Mirror the client row/column raycast used when diagonal moves are disabled."""
    if first[0] != second[0] and first[1] != second[1]:
        return False
    row_step = (second[0] > first[0]) - (second[0] < first[0])
    col_step = (second[1] > first[1]) - (second[1] < first[1])
    row, col = first
    if not clear((row, col)):
        return False
    while (row, col) != second:
        row += row_step
        col += col_step
        if not clear((row, col)):
            return False
    return True


@dataclass(frozen=True)
class WalkFlowField:
    """Client SPFA next-map for one WALK destination and terrain snapshot."""

    rows: int
    columns: int
    destination: Coordinate
    distances: dict[Coordinate, int]
    parents: dict[Coordinate, Coordinate]
    smoothed_parents: dict[Coordinate, Coordinate]

    def path_from(self, start: Coordinate) -> tuple[Coordinate, ...]:
        if start not in self.distances:
            raise WalkNavigationError(f"tile {start!r} cannot reach destination {self.destination!r}")
        result = [start]
        current = start
        guard = self.rows * self.columns
        while current != self.destination and guard:
            current = self.smoothed_parents[current]
            result.append(current)
            guard -= 1
        if guard == 0:
            raise WalkNavigationError("flow field produced a cycle")
        return tuple(result)


class WalkNavigator:
    """Deterministic terrain navigation from GameData tile masks."""

    def __init__(
        self,
        rows: int,
        columns: int,
        passable: Callable[[Coordinate], bool],
        *,
        obstacle_like: Callable[[Coordinate], bool] | None = None,
    ) -> None:
        self.rows = rows
        self.columns = columns
        self._passable = passable
        self._obstacle_like = obstacle_like or (lambda coordinate: False)
        self._fields: dict[tuple[Coordinate, bool], WalkFlowField] = {}

    def _in_bounds(self, coordinate: Coordinate) -> bool:
        row, col = coordinate
        return 0 <= row < self.rows and 0 <= col < self.columns

    def _clear_for_raycast(self) -> Callable[[Coordinate], bool]:
        return lambda coordinate: (
            self._in_bounds(coordinate)
            and self._passable(coordinate)
            and not self._obstacle_like(coordinate)
        )

    def field_to(self, destination: Coordinate, *, allow_diagonal: bool = True) -> WalkFlowField:
        cache_key = (destination, allow_diagonal)
        if cache_key in self._fields:
            return self._fields[cache_key]
        if not self._in_bounds(destination) or not self._passable(destination):
            raise WalkNavigationError(f"destination {destination!r} is not walkable terrain")

        distances = {destination: 0}
        parents: dict[Coordinate, Coordinate] = {}
        in_queue = {destination}
        queue = deque([destination])
        while queue:
            current = queue.popleft()
            in_queue.discard(current)
            current_distance = distances[current]
            for row_delta, col_delta in GRID_FOUR_WAYS:
                neighbour = (current[0] + row_delta, current[1] + col_delta)
                if not self._in_bounds(neighbour) or not self._passable(neighbour):
                    continue
                candidate_distance = current_distance + (1000 if self._obstacle_like(neighbour) else 1)
                if neighbour not in distances or candidate_distance < distances[neighbour]:
                    distances[neighbour] = candidate_distance
                    parents[neighbour] = current
                    if neighbour not in in_queue:
                        queue.append(neighbour)
                        in_queue.add(neighbour)

        smoothed_parents = dict(parents)
        clear = self._clear_for_raycast()
        for row in range(self.rows):
            for col in range(self.columns):
                current = (row, col)
                candidate = smoothed_parents.get(current)
                while candidate is not None:
                    ancestor = smoothed_parents.get(candidate)
                    if ancestor is None:
                        break
                    visible = (
                        bresenham_clear(current, ancestor, clear)
                        if allow_diagonal
                        else segment_clear(current, ancestor, clear)
                    )
                    if visible:
                        candidate = ancestor
                    else:
                        break
                if candidate is not None:
                    smoothed_parents[current] = candidate

        field = WalkFlowField(self.rows, self.columns, destination, distances, parents, smoothed_parents)
        self._fields[cache_key] = field
        return field

    def path(
        self,
        start: Coordinate,
        destination: Coordinate,
        *,
        allow_diagonal: bool = True,
    ) -> tuple[Coordinate, ...]:
        return self.field_to(destination, allow_diagonal=allow_diagonal).path_from(start)


def path_length(path: tuple[Coordinate, ...]) -> float:
    return sum(
        hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(path, path[1:])
    )
