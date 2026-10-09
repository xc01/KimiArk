from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    DEPLOY = "DEPLOY"
    ACTIVATE_SKILL = "ACTIVATE_SKILL"
    RETREAT = "RETREAT"


@dataclass(frozen=True)
class Action:
    action_type: ActionType
    time: float
    operator_id: str
    tile: tuple[int, int] | None = None
    direction: str = "RIGHT"


@dataclass(frozen=True)
class Strategy:
    team: tuple[str, ...]
    actions: tuple[Action, ...]
