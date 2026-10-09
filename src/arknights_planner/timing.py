"""Explicit conversion boundary between legacy seconds and canonical frame actions."""
from __future__ import annotations

from fractions import Fraction

from .models.frame import FrameClock
from .models.timeline import FrameAction, FrameTimeline, TimelineActionType
from .models.strategy import Action, ActionType, Strategy


def strategy_to_timeline(strategy: Strategy, *, stage_id: str, frame_clock: FrameClock, simulator_mode: str | None = None, approximation_policy_version: str | None = None) -> FrameTimeline:
    """Convert legacy second-based fixtures once at a boundary."""
    actions: list[FrameAction] = []
    for ordinal, action in enumerate(strategy.actions):
        frame = frame_clock.frame_for_seconds(Fraction(str(action.time)))
        action_type = TimelineActionType(action.action_type.value)
        actions.append(FrameAction(frame, action_type, action.operator_id, action.tile, action.direction if action_type is TimelineActionType.DEPLOY else None, ordinal))
    return FrameTimeline(stage_id, frame_clock, tuple(actions), simulator_mode=simulator_mode, approximation_policy_version=approximation_policy_version)


def timeline_to_strategy(timeline: FrameTimeline) -> Strategy:
    """Convert to the existing simulator's seconds only at the simulator boundary."""
    if timeline.frame_clock.frames_per_second is None:
        raise ValueError("cannot adapt an unknown-frequency timeline to seconds")
    actions = []
    for action in timeline.actions:
        legacy_type = ActionType(action.action_type.value)
        seconds = float(timeline.frame_clock.seconds_for_frame(action.frame))
        actions.append(Action(legacy_type, seconds, action.operator_id, action.tile, action.direction or "RIGHT"))
    return Strategy(tuple(dict.fromkeys(action.operator_id for action in actions)), tuple(actions))
