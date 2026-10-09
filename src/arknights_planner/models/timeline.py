"""Neutral external action timeline. Internal simulator events never enter it."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .frame import FrameClock, validate_frame


class TimelineActionType(str, Enum):
    DEPLOY = "DEPLOY"
    ACTIVATE_SKILL = "ACTIVATE_SKILL"
    RETREAT = "RETREAT"


@dataclass(frozen=True)
class FrameAction:
    frame: int
    action_type: TimelineActionType
    operator_id: str
    tile: tuple[int, int] | None = None
    direction: str | None = None
    ordinal: int = 0

    def __post_init__(self) -> None:
        validate_frame(self.frame)
        if not isinstance(self.action_type, TimelineActionType):
            try:
                object.__setattr__(self, "action_type", TimelineActionType(self.action_type))
            except (TypeError, ValueError) as error:
                raise ValueError(f"unsupported external action: {self.action_type!r}") from error
        if self.action_type is TimelineActionType.DEPLOY:
            if self.tile is None or self.direction is None:
                raise ValueError("DEPLOY requires tile and direction")
        elif self.tile is not None or self.direction is not None:
            raise ValueError(f"{self.action_type.value} cannot contain deployment coordinates")

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"frame": self.frame, "type": self.action_type.value, "operator_id": self.operator_id}
        if self.tile is not None:
            value["tile"] = list(self.tile)
        if self.direction is not None:
            value["direction"] = self.direction
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any], ordinal: int = 0) -> "FrameAction":
        return cls(int(value["frame"]), TimelineActionType(value["type"]), value["operator_id"], tuple(value["tile"]) if value.get("tile") is not None else None, value.get("direction"), ordinal)


@dataclass(frozen=True)
class FrameTimeline:
    stage_id: str
    frame_clock: FrameClock
    actions: tuple[FrameAction, ...]
    strategy_id: str | None = None
    source_search_id: str | None = None
    simulator_mode: str | None = None
    approximation_policy_version: str | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported FrameTimeline schema version")
        if any(action.action_type not in TimelineActionType for action in self.actions):
            raise ValueError("timeline contains an unsupported external action")
        # Stable authored ordinal is the only tie-breaker; no hash/dict iteration.
        ordered = tuple(sorted(enumerate(self.actions), key=lambda item: (item[1].frame, item[0])))
        normalized = tuple(FrameAction(action.frame, action.action_type, action.operator_id, action.tile, action.direction, index) for index, (_, action) in enumerate(ordered))
        if normalized != self.actions:
            object.__setattr__(self, "actions", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "stage_id": self.stage_id,
            "frame_clock": self.frame_clock.to_dict(),
            "strategy_id": self.strategy_id,
            "source_search_id": self.source_search_id,
            "simulator_mode": self.simulator_mode,
            "approximation_policy_version": self.approximation_policy_version,
            "actions": [action.to_dict() for action in self.actions],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FrameTimeline":
        return cls(
            stage_id=value["stage_id"], frame_clock=FrameClock.from_dict(value["frame_clock"]),
            actions=tuple(FrameAction.from_dict(item, ordinal) for ordinal, item in enumerate(value.get("actions", ()))),
            strategy_id=value.get("strategy_id"), source_search_id=value.get("source_search_id"),
            simulator_mode=value.get("simulator_mode"), approximation_policy_version=value.get("approximation_policy_version"),
            schema_version=int(value.get("schema_version", 1)),
        )
