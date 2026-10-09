"""Serializable real-execution trace records; screenshots stay as files."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from arknights_planner.models.strategy import Action, ActionType, Strategy


def action_to_dict(action: Action) -> dict:
    return {
        "type": action.action_type.value,
        "time": action.time,
        "operator_id": action.operator_id,
        "tile": list(action.tile) if action.tile is not None else None,
        "direction": action.direction,
    }


def action_from_dict(value: dict) -> Action:
    return Action(
        ActionType(value["type"]), float(value["time"]), value["operator_id"],
        tuple(value["tile"]) if value.get("tile") is not None else None, value.get("direction", "RIGHT"),
    )


@dataclass(frozen=True)
class Observation:
    label: str
    battle_time: float
    monotonic_time: float | None
    reference: str | None
    kind: str = "SCREENSHOT"


@dataclass(frozen=True)
class ActionExecutionRecord:
    action: Action
    intended_battle_time: float
    command_start_monotonic: float | None
    tile_placement_monotonic: float | None
    direction_selection_monotonic: float | None
    command_end_monotonic: float | None
    command_lateness_seconds: float | None
    card_pixel: tuple[int, int] | None
    tile_pixel: tuple[int, int] | None
    facing_pixel: tuple[int, int] | None
    error: str | None = None


@dataclass(frozen=True)
class ExecutionTrace:
    stage_id: str
    strategy_source: str
    strategy: Strategy
    device_identifier: str
    screen_resolution: tuple[int, int]
    coordinate_calibration_id: str
    execution_start_monotonic: float
    battle_origin_monotonic: float
    battle_origin_assumption: str
    dry_run: bool
    simulator_approximation_policy: tuple[str, ...]
    actions: tuple[ActionExecutionRecord, ...]
    observations: tuple[Observation, ...]
    execution_errors: tuple[str, ...]
    terminal_state: str | None = None
    terminal_battle_time: float | None = None

    def to_dict(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "strategy_source": self.strategy_source,
            "strategy": {"team": list(self.strategy.team), "actions": [action_to_dict(item) for item in self.strategy.actions]},
            "device_identifier": self.device_identifier,
            "screen_resolution": list(self.screen_resolution),
            "coordinate_calibration_id": self.coordinate_calibration_id,
            "execution_start_monotonic": self.execution_start_monotonic,
            "battle_origin_monotonic": self.battle_origin_monotonic,
            "battle_origin_assumption": self.battle_origin_assumption,
            "dry_run": self.dry_run,
            "simulator_approximation_policy": list(self.simulator_approximation_policy),
            "actions": [
                {
                    **asdict(item),
                    "action": action_to_dict(item.action),
                    "card_pixel": list(item.card_pixel) if item.card_pixel else None,
                    "tile_pixel": list(item.tile_pixel) if item.tile_pixel else None,
                    "facing_pixel": list(item.facing_pixel) if item.facing_pixel else None,
                }
                for item in self.actions
            ],
            "observations": [asdict(item) for item in self.observations],
            "execution_errors": list(self.execution_errors),
            "terminal_state": self.terminal_state,
            "terminal_battle_time": self.terminal_battle_time,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "ExecutionTrace":
        strategy = Strategy(tuple(value["strategy"]["team"]), tuple(action_from_dict(item) for item in value["strategy"]["actions"]))
        actions = tuple(ActionExecutionRecord(
            action=action_from_dict(item["action"]),
            intended_battle_time=float(item["intended_battle_time"]),
            command_start_monotonic=item.get("command_start_monotonic"),
            tile_placement_monotonic=item.get("tile_placement_monotonic"),
            direction_selection_monotonic=item.get("direction_selection_monotonic"),
            command_end_monotonic=item.get("command_end_monotonic"),
            command_lateness_seconds=item.get("command_lateness_seconds"),
            card_pixel=tuple(item["card_pixel"]) if item.get("card_pixel") else None,
            tile_pixel=tuple(item["tile_pixel"]) if item.get("tile_pixel") else None,
            facing_pixel=tuple(item["facing_pixel"]) if item.get("facing_pixel") else None,
            error=item.get("error"),
        ) for item in value["actions"])
        return cls(
            stage_id=value["stage_id"], strategy_source=value["strategy_source"], strategy=strategy,
            device_identifier=value["device_identifier"], screen_resolution=tuple(value["screen_resolution"]),
            coordinate_calibration_id=value["coordinate_calibration_id"],
            execution_start_monotonic=float(value["execution_start_monotonic"]),
            battle_origin_monotonic=float(value["battle_origin_monotonic"]),
            battle_origin_assumption=value["battle_origin_assumption"], dry_run=bool(value["dry_run"]),
            simulator_approximation_policy=tuple(value.get("simulator_approximation_policy", ())),
            actions=actions,
            observations=tuple(Observation(**item) for item in value.get("observations", ())),
            execution_errors=tuple(value.get("execution_errors", ())),
            terminal_state=value.get("terminal_state"), terminal_battle_time=value.get("terminal_battle_time"),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ExecutionTrace":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
