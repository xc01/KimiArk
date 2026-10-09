"""Bounded execution of one known deployment strategy through a DeviceController."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from arknights_planner.models.strategy import Action, ActionType, Strategy

from .config import ExecutionConfiguration
from .controller import DeviceController, ScreenshotCapture
from .coordinates import ScreenCoordinateMapper
from .traces import ActionExecutionRecord, ExecutionTrace, Observation


@dataclass(frozen=True)
class ExecutionPlan:
    stage_id: str
    strategy_source: str
    strategy: Strategy
    simulator_approximation_policy: tuple[str, ...]


class ObservationProvider(Protocol):
    def observe(self, *, label: str, battle_time: float) -> Observation: ...


class ScreenshotObservationProvider:
    def __init__(self, controller: DeviceController, output_dir: Path):
        self.controller = controller
        self.output_dir = output_dir
        self._counter = 0

    def observe(self, *, label: str, battle_time: float) -> Observation:
        self._counter += 1
        path = self.output_dir / "screenshots" / f"{self._counter:03d}_{label}.png"
        capture: ScreenshotCapture = self.controller.screenshot(path)
        return Observation(label, battle_time, capture.monotonic_time, capture.path)


def m7_main_00_01_execution_plan() -> ExecutionPlan:
    """The single M7 discovery selected as a real-client calibration fixture."""
    return ExecutionPlan(
        stage_id="0-1",
        strategy_source="M7 real-search result",
        strategy=Strategy(
            ("char_129_bluep",),
            (Action(ActionType.DEPLOY, 3.0, "char_129_bluep", (4, 2), "LEFT"),),
        ),
        simulator_approximation_policy=(
            "SYNTHETIC_90_DEGREE_ROW_COL",
            "CUMULATIVE_HIERARCHICAL_PREDELAYS",
            "ZERO_WINDUP_ZERO_EXTRA_RECOVERY",
            "INSTANT_PROJECTILE",
            "REVERSED_SERIALIZED_MAP_ROW",
            "EXISTING_SYNTHETIC_PHYSICAL_DAMAGE",
            "ONE_DP_PER_COST_INCREASE_INTERVAL",
        ),
    )


class StageGameExecutor:
    """Schedules known strategy actions against a shared monotonic battle origin."""

    def __init__(self, controller: DeviceController, configuration: ExecutionConfiguration):
        self.controller = controller
        self.configuration = configuration

    def _coordinates(self, action: Action, mapper: ScreenCoordinateMapper) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        if action.action_type is not ActionType.DEPLOY or action.tile is None:
            raise ValueError("Milestone 8 only supports deploy actions with tiles")
        card = self.configuration.operator_cards.get(action.operator_id)
        if card is None:
            raise ValueError(f"no configured operator-card coordinate for {action.operator_id}")
        card_pixel = mapper.to_pixels(card)
        tile_pixel = self.configuration.stage_grid.tile_to_pixels(action.tile, mapper)
        facing_pixel = self.configuration.facing.endpoint(tile_pixel, action.direction, mapper)
        return card_pixel, tile_pixel, facing_pixel

    def _record_scheduled(self, action: Action, mapper: ScreenCoordinateMapper) -> ActionExecutionRecord:
        card, tile, facing = self._coordinates(action, mapper)
        return ActionExecutionRecord(action, action.time, None, None, None, None, None, card, tile, facing)

    def execute(
        self,
        plan: ExecutionPlan,
        *,
        send_input: bool,
        output_dir: Path,
        capture_screenshots: bool = False,
    ) -> ExecutionTrace:
        """Run or dry-run the bounded plan; `send_input` is the explicit safety guard."""
        resolution = self.controller.screen_size()
        mapper = ScreenCoordinateMapper(*resolution, viewport=self.configuration.viewport)
        started = self.controller.current_monotonic_time()
        origin = started + self.configuration.battle_start_offset_seconds
        provider = ScreenshotObservationProvider(self.controller, output_dir) if capture_screenshots else None
        observations: list[Observation] = []
        records: list[ActionExecutionRecord] = []
        errors: list[str] = []
        checkpoint_times = iter(sorted(set(self.configuration.checkpoint_times)))
        next_checkpoint = next(checkpoint_times, None)

        if not send_input:
            for action in sorted(plan.strategy.actions, key=lambda item: item.time):
                records.append(self._record_scheduled(action, mapper))
            return ExecutionTrace(
                plan.stage_id, plan.strategy_source, plan.strategy, self.controller.device_id,
                resolution, self.configuration.calibration_id, started, origin,
                "manual battle-ready confirmation + configured battle_start_offset_seconds", True,
                plan.simulator_approximation_policy, tuple(records), tuple(), tuple(errors),
            )

        for action in sorted(plan.strategy.actions, key=lambda item: item.time):
            while next_checkpoint is not None and next_checkpoint < action.time:
                self.controller.sleep_until(origin + next_checkpoint)
                if provider:
                    observations.append(provider.observe(label=f"checkpoint_{next_checkpoint:05.2f}", battle_time=next_checkpoint))
                next_checkpoint = next(checkpoint_times, None)
            deadline = origin + action.time
            self.controller.sleep_until(deadline)
            if provider:
                observations.append(provider.observe(label=f"before_{action.operator_id}", battle_time=action.time))
            try:
                card, tile, facing = self._coordinates(action, mapper)
                command_start = self.controller.current_monotonic_time()
                # The configured three-command gesture is intentionally transparent.
                # It records command issuance, not proof that the game accepted it.
                self.controller.tap(card)
                self.controller.swipe(card, tile, self.configuration.drag_duration_seconds)
                tile_placement_time = self.controller.current_monotonic_time()
                self.controller.swipe(tile, facing, self.configuration.direction_duration_seconds)
                direction_selection_time = self.controller.current_monotonic_time()
                command_end = direction_selection_time
                records.append(ActionExecutionRecord(
                    action, action.time, command_start, tile_placement_time, direction_selection_time, command_end,
                    command_start - deadline,
                    card, tile, facing,
                ))
                if provider:
                    observations.append(provider.observe(label=f"after_{action.operator_id}", battle_time=command_end - origin))
            except Exception as error:  # preserve a partial trace for calibration.
                errors.append(f"{action.operator_id}@{action.time}: {error}")
                records.append(ActionExecutionRecord(action, action.time, None, None, None, None, None, None, None, None, str(error)))

        while next_checkpoint is not None:
            self.controller.sleep_until(origin + next_checkpoint)
            if provider:
                observations.append(provider.observe(label=f"checkpoint_{next_checkpoint:05.2f}", battle_time=next_checkpoint))
            next_checkpoint = next(checkpoint_times, None)
        return ExecutionTrace(
            plan.stage_id, plan.strategy_source, plan.strategy, self.controller.device_id,
            resolution, self.configuration.calibration_id, started, origin,
            "manual battle-ready confirmation + configured battle_start_offset_seconds", False,
            plan.simulator_approximation_policy, tuple(records), tuple(observations), tuple(errors),
        )
