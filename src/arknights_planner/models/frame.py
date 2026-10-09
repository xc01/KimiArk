"""Integer-frame timing contracts for planner output.

Frame frequency is deliberately provenance-aware: a frame index is canonical even
when its wall-clock duration is not known.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Any

from .provenance import KnowledgeStatus


class FrameClockKind(str, Enum):
    CLIENT_LOGIC_FRAME = "CLIENT_LOGIC_FRAME"
    CONFIGURED_FRAME = "CONFIGURED_FRAME"
    SIMULATOR_FRAME = "SIMULATOR_FRAME"


@dataclass(frozen=True)
class FrameClock:
    kind: FrameClockKind
    frames_per_second: Fraction | None
    status: KnowledgeStatus
    provenance: str
    confidence: float = 0.0
    version: str = "frame-clock-v1"

    def __post_init__(self) -> None:
        if self.frames_per_second is not None and self.frames_per_second <= 0:
            raise ValueError("frames_per_second must be positive")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    @classmethod
    def unknown_client(cls) -> "FrameClock":
        return cls(FrameClockKind.CLIENT_LOGIC_FRAME, None, KnowledgeStatus.UNKNOWN, "APK archaeology: exact relation unresolved", 0.15)

    @classmethod
    def configured(cls, frames_per_second: int | Fraction, *, provenance: str = "explicit planner configuration") -> "FrameClock":
        return cls(FrameClockKind.CONFIGURED_FRAME, Fraction(frames_per_second), KnowledgeStatus.APPROXIMATED, provenance, 0.5)

    @classmethod
    def simulator(cls, frames_per_second: int | Fraction = 10) -> "FrameClock":
        return cls(FrameClockKind.SIMULATOR_FRAME, Fraction(frames_per_second), KnowledgeStatus.APPROXIMATED, "synthetic simulator timing configuration", 0.5)

    def seconds_for_frame(self, frame: int) -> Fraction:
        validate_frame(frame)
        if self.frames_per_second is None:
            raise ValueError("this FrameClock has unknown frame frequency")
        return Fraction(frame, 1) / self.frames_per_second

    def frame_for_seconds(self, seconds: Fraction | int | float) -> int:
        if self.frames_per_second is None:
            raise ValueError("this FrameClock has unknown frame frequency")
        # Decimal float inputs are compatibility presentation values; parse their
        # spelling so 3.0 does not acquire binary floating-point residue.
        value = Fraction(str(seconds)) * self.frames_per_second if isinstance(seconds, float) else Fraction(seconds) * self.frames_per_second
        if value.denominator != 1:
            raise ValueError("seconds do not map to an exact integer frame")
        validate_frame(value.numerator)
        return value.numerator

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "frames_per_second": str(self.frames_per_second) if self.frames_per_second is not None else None,
            "status": self.status.value,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FrameClock":
        fps = value.get("frames_per_second")
        return cls(FrameClockKind(value["kind"]), Fraction(fps) if fps is not None else None, KnowledgeStatus(value["status"]), value["provenance"], float(value.get("confidence", 0.0)), value.get("version", "frame-clock-v1"))


def validate_frame(frame: int) -> int:
    if isinstance(frame, bool) or not isinstance(frame, int):
        raise TypeError("frame must be a non-negative integer")
    if frame < 0:
        raise ValueError("frame must be non-negative")
    return frame
