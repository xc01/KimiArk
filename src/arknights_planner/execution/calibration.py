"""Evidence-aware first comparison of a simulator prediction and execution trace."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path

from .prediction import PredictionTrace
from .traces import ExecutionTrace


class ComparisonStatus(str, Enum):
    OBSERVED = "OBSERVED"
    UNOBSERVED = "UNOBSERVED"
    CANNOT_COMPARE = "CANNOT_COMPARE"


@dataclass(frozen=True)
class ComparisonEntry:
    subject: str
    status: ComparisonStatus
    predicted: str | None
    observed: str | None
    interpretation: str


@dataclass(frozen=True)
class CalibrationReport:
    stage_id: str
    entries: tuple[ComparisonEntry, ...]

    def to_dict(self) -> dict:
        return {"stage_id": self.stage_id, "entries": [{**asdict(item), "status": item.status.value} for item in self.entries]}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def compare_prediction_to_execution(prediction: PredictionTrace, execution: ExecutionTrace) -> CalibrationReport:
    if prediction.stage_id != execution.stage_id:
        raise ValueError("prediction and execution traces refer to different stages")
    entries: list[ComparisonEntry] = []
    for index, intended in enumerate(prediction.strategy.actions):
        record = execution.actions[index] if index < len(execution.actions) else None
        subject = f"deployment:{intended.operator_id}:{index}"
        if record is None or record.command_start_monotonic is None:
            entries.append(ComparisonEntry(
                subject, ComparisonStatus.UNOBSERVED, f"intended battle time {intended.time:.3f}", None,
                "no real input command was issued (dry-run or incomplete trace)",
            ))
        elif record.error:
            entries.append(ComparisonEntry(
                subject, ComparisonStatus.OBSERVED, f"intended battle time {intended.time:.3f}", f"command error: {record.error}",
                "device-command failure is observed; game acceptance remains unobserved",
            ))
        else:
            entries.append(ComparisonEntry(
                subject, ComparisonStatus.OBSERVED, f"intended battle time {intended.time:.3f}",
                f"command lateness {record.command_lateness_seconds:.3f}s",
                "input issuance is observed; screenshots are retained but no visual deployment detector is implemented",
            ))
    if execution.terminal_state is None:
        entries.append(ComparisonEntry(
            "terminal_state", ComparisonStatus.UNOBSERVED, prediction.predicted_terminal_state, None,
            "no victory/failure recognizer or manual terminal annotation is present",
        ))
        entries.append(ComparisonEntry(
            "battle_duration", ComparisonStatus.UNOBSERVED, f"{prediction.predicted_battle_duration:.3f}s", None,
            "terminal battle time was not observed",
        ))
    else:
        entries.append(ComparisonEntry(
            "terminal_state", ComparisonStatus.OBSERVED, prediction.predicted_terminal_state, execution.terminal_state,
            "terminal comparison is observational only; simulator mechanics remain approximate",
        ))
        entries.append(ComparisonEntry(
            "battle_duration", ComparisonStatus.OBSERVED, f"{prediction.predicted_battle_duration:.3f}s",
            f"{execution.terminal_battle_time:.3f}s" if execution.terminal_battle_time is not None else None,
            "only comparable when the trace includes a terminal battle time",
        ))
    entries.append(ComparisonEntry(
        "spawn_and_combat_events", ComparisonStatus.CANNOT_COMPARE,
        "simulator SPAWN/ATTACK/DAMAGE/DEATH events", None,
        "Milestone 8 stores screenshots only; it does not detect enemies, HP, or combat events",
    ))
    entries.append(ComparisonEntry(
        "scheduler_jitter", ComparisonStatus.OBSERVED if any(item.command_lateness_seconds is not None for item in execution.actions) else ComparisonStatus.UNOBSERVED,
        "0.000s ideal lateness",
        ", ".join(f"{item.command_lateness_seconds:.3f}s" for item in execution.actions if item.command_lateness_seconds is not None) or None,
        "measures host command scheduling, not in-game acceptance timing",
    ))
    return CalibrationReport(prediction.stage_id, tuple(entries))
