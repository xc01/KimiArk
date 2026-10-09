"""Human test-sheet rendering from a neutral FrameTimeline only."""
from __future__ import annotations

from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.timeline import FrameTimeline, TimelineActionType
from .objective import effective_operator_ids
from .validation import HumanValidationStatus


_DIRECTION_LABELS = {"UP": "↑ 上", "DOWN": "↓ 下", "LEFT": "← 左", "RIGHT": "→ 右"}


def direction_label(direction: str) -> str:
    return _DIRECTION_LABELS[direction]


def render_human_timeline(*, timeline: FrameTimeline, repository: GameDataRepository, simulator_result: str = "UNTESTED", validation_status: HumanValidationStatus = HumanValidationStatus.UNTESTED, robustness: str = "UNMEASURED", approximation_warnings: tuple[str, ...] = ()) -> str:
    names: dict[str, str] = {}
    rarities: dict[str, int] = {}
    for operator_id in effective_operator_ids_from_timeline(timeline):
        operator = repository.get_operator(operator_id)
        names[operator_id] = operator.name.value or operator_id
        if operator.star_rarity.value is None:
            raise ValueError(f"operator has unknown GameData rarity: {operator_id}")
        rarities[operator_id] = operator.star_rarity.value
    lines = [
        f"Stage: {timeline.stage_id}",
        f"Simulator: {simulator_result}",
        f"Human validation: {validation_status.value}",
        "", "Squad:",
    ]
    for operator_id in sorted(names):
        lines.append(f"  {names[operator_id]}  {'★' * rarities[operator_id]}")
    lines += [
        f"Operators: {len(names)}", f"Total rarity: {sum(rarities.values())}★", "",
        f"Frame clock: {timeline.frame_clock.kind.value} / {timeline.frame_clock.status.value}", "Timeline:",
    ]
    for action in timeline.actions:
        seconds = f" [{float(timeline.frame_clock.seconds_for_frame(action.frame)):.3f}s]" if timeline.frame_clock.frames_per_second else ""
        name = names[action.operator_id]
        if action.action_type is TimelineActionType.DEPLOY:
            lines.append(f"  {action.frame:04d}{seconds}  DEPLOY  {name}  {action.tile}  {direction_label(action.direction or 'RIGHT')}")
        elif action.action_type is TimelineActionType.ACTIVATE_SKILL:
            lines.append(f"  {action.frame:04d}{seconds}  SKILL   {name}")
        else:
            lines.append(f"  {action.frame:04d}{seconds}  RETREAT {name}")
    lines += ["", f"Timing robustness: {robustness}", "Approximation warnings:"]
    lines.extend(f"  - {warning}" for warning in approximation_warnings or ("No simulator result attached",))
    return "\n".join(lines)


def effective_operator_ids_from_timeline(timeline: FrameTimeline) -> tuple[str, ...]:
    return tuple(sorted({action.operator_id for action in timeline.actions}))
