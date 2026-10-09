from __future__ import annotations

from fractions import Fraction

import pytest

from arknights_planner.models.frame import FrameClock, FrameClockKind, validate_frame
from arknights_planner.models.provenance import KnowledgeStatus
from arknights_planner.models.timeline import FrameAction, FrameTimeline, TimelineActionType
from arknights_planner.timing import strategy_to_timeline, timeline_to_strategy
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator


def test_frame_validation_and_clock_rational_conversion():
    assert validate_frame(0) == 0
    with pytest.raises(ValueError): validate_frame(-1)
    with pytest.raises(TypeError): validate_frame(1.0)
    clock = FrameClock.configured(Fraction(30, 1))
    assert clock.seconds_for_frame(90) == Fraction(3, 1)
    assert clock.frame_for_seconds(Fraction(3, 1)) == 90
    assert clock.to_dict()["frames_per_second"] == "30"


def test_unknown_client_frame_frequency_is_explicit():
    clock = FrameClock.unknown_client()
    assert clock.kind is FrameClockKind.CLIENT_LOGIC_FRAME
    assert clock.status is KnowledgeStatus.UNKNOWN
    with pytest.raises(ValueError): clock.seconds_for_frame(1)


def test_timeline_supports_all_three_actions_and_stable_same_frame_order():
    timeline = FrameTimeline(
        "0-1", FrameClock.configured(30),
        (
            FrameAction(100, TimelineActionType.RETREAT, "a"),
            FrameAction(100, TimelineActionType.DEPLOY, "b", (1, 2), "LEFT"),
            FrameAction(100, TimelineActionType.ACTIVATE_SKILL, "b"),
        ),
    )
    assert [action.action_type for action in timeline.actions] == [TimelineActionType.RETREAT, TimelineActionType.DEPLOY, TimelineActionType.ACTIVATE_SKILL]
    restored = FrameTimeline.from_dict(timeline.to_dict())
    assert restored == timeline


def test_timeline_rejects_wait_and_invalid_action_payloads():
    with pytest.raises(ValueError): FrameAction(1, "WAIT", "x")
    with pytest.raises(ValueError): FrameAction(1, TimelineActionType.DEPLOY, "x")
    with pytest.raises(ValueError): FrameAction(1, TimelineActionType.RETREAT, "x", (1, 1), "RIGHT")


def test_legacy_seconds_are_converted_once_at_boundary():
    strategy = Strategy(("x",), (Action(ActionType.DEPLOY, 3.0, "x", (1, 2), "LEFT"), Action(ActionType.RETREAT, 4.0, "x")))
    timeline = strategy_to_timeline(strategy, stage_id="0-1", frame_clock=FrameClock.configured(30))
    assert [action.frame for action in timeline.actions] == [90, 120]
    assert timeline_to_strategy(timeline).actions[0].time == 3.0


def test_simulator_frame_boundary_rejects_unknown_frequency_and_accepts_configured():
    from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage
    stage, operators, enemies = synthetic_stage(), synthetic_operators(), synthetic_enemies()
    timeline = FrameTimeline(
        "synthetic-1", FrameClock.configured(10),
        (FrameAction(0, TimelineActionType.DEPLOY, "guard", (3, 1), "RIGHT"),),
    )
    result = Simulator().run_timeline(stage=stage, operators=operators, enemies=enemies, timeline=timeline, config=SimulationConfig(max_time=1.0))
    assert result.events[0].event_type.value == "DEPLOY"
    with pytest.raises(ValueError):
        Simulator().run_timeline(stage=stage, operators=operators, enemies=enemies, timeline=FrameTimeline("synthetic-1", FrameClock.unknown_client(), ()), config=SimulationConfig(max_time=1.0))
