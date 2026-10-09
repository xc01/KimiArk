from __future__ import annotations

from typing import Protocol


class ProjectileModel(Protocol):
    def hit_delay(
        self,
        *,
        source_tile: tuple[int, int],
        target_position: tuple[float, float],
    ) -> float:
        """Return a synthetic delay; future models may depend on distance and type."""


class InstantProjectileModel:
    """Synthetic default. Zero delay is architectural only, not a game-mechanics claim."""

    def hit_delay(self, *, source_tile: tuple[int, int], target_position: tuple[float, float]) -> float:
        return 0.0
