from __future__ import annotations

from typing import Protocol


class RangeTransformer(Protocol):
    def covered_tiles(
        self,
        *,
        origin: tuple[int, int],
        offsets: tuple[tuple[int, int], ...],
        direction: str,
    ) -> set[tuple[int, int]]:
        """Convert canonical range offsets into map tiles for one facing direction."""


class CanonicalSyntheticRangeTransformer:
    """Synthetic-only orientation rule; it makes no claim about Arknights' rule.

    Offsets are defined for RIGHT. RIGHT=(dx,dy), DOWN=(-dy,dx), LEFT=(-dx,-dy),
    and UP=(dy,-dx), with x increasing right and y increasing down.
    """

    _directions = {"RIGHT", "DOWN", "LEFT", "UP"}

    def covered_tiles(
        self,
        *,
        origin: tuple[int, int],
        offsets: tuple[tuple[int, int], ...],
        direction: str,
    ) -> set[tuple[int, int]]:
        if direction not in self._directions:
            raise ValueError(f"Unsupported synthetic direction: {direction}")
        def rotate(dx: int, dy: int) -> tuple[int, int]:
            if direction == "RIGHT": return dx, dy
            if direction == "DOWN": return -dy, dx
            if direction == "LEFT": return -dx, -dy
            return dy, -dx
        return {(origin[0] + rotate(dx, dy)[0], origin[1] + rotate(dx, dy)[1]) for dx, dy in offsets}


class ApproximateRealRangeTransformer:
    """Opt-in approximation for real `range_table` row/col cells.

    It treats a real raw cell `(row, col)` as the synthetic RIGHT-facing offset
    `(col, -row)` and then applies the synthetic 90-degree rotation rule. This is
    deliberately not a recovered Arknights client transform.
    """

    def __init__(self) -> None:
        self._synthetic = CanonicalSyntheticRangeTransformer()

    def covered_tiles(
        self,
        *,
        origin: tuple[int, int],
        offsets: tuple[tuple[int, int], ...],
        direction: str,
    ) -> set[tuple[int, int]]:
        converted = tuple((col, -row) for row, col in offsets)
        return self._synthetic.covered_tiles(origin=origin, offsets=converted, direction=direction)
