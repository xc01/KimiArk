"""Compact simulator-side prediction traces for calibration comparisons."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealOperatorConfiguration, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.simulation import EventType, SimulationResult
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator

from .executor import ExecutionPlan, m7_main_00_01_execution_plan
from .traces import action_from_dict, action_to_dict
from arknights_planner.models.strategy import Strategy
from arknights_planner.models.frame import FrameClock


@dataclass(frozen=True)
class PredictedEvent:
    battle_time: float
    kind: str
    source_id: str | None = None
    target_id: str | None = None
    frame: int | None = None


@dataclass(frozen=True)
class PredictionTrace:
    stage_id: str
    strategy_source: str
    strategy: Strategy
    simulator_mode: str
    approximation_policy: tuple[str, ...]
    predicted_terminal_state: str
    predicted_battle_duration: float
    events: tuple[PredictedEvent, ...]

    def to_dict(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "strategy_source": self.strategy_source,
            "strategy": {"team": list(self.strategy.team), "actions": [action_to_dict(item) for item in self.strategy.actions]},
            "simulator_mode": self.simulator_mode,
            "approximation_policy": list(self.approximation_policy),
            "predicted_terminal_state": self.predicted_terminal_state,
            "predicted_battle_duration": self.predicted_battle_duration,
            "events": [asdict(item) for item in self.events],
        }

    @classmethod
    def from_dict(cls, value: dict) -> "PredictionTrace":
        return cls(
            stage_id=value["stage_id"], strategy_source=value["strategy_source"],
            strategy=Strategy(tuple(value["strategy"]["team"]), tuple(action_from_dict(item) for item in value["strategy"]["actions"])),
            simulator_mode=value["simulator_mode"], approximation_policy=tuple(value["approximation_policy"]),
            predicted_terminal_state=value["predicted_terminal_state"],
            predicted_battle_duration=float(value["predicted_battle_duration"]),
            events=tuple(PredictedEvent(**item) for item in value["events"]),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PredictionTrace":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


_PREDICTED_EVENTS = {
    EventType.SPAWN: "SPAWN",
    EventType.DEPLOY: "DEPLOY",
    EventType.ATTACK_START: "ATTACK_START",
    EventType.DAMAGE: "DAMAGE",
    EventType.ENEMY_DEATH: "ENEMY_DEATH",
    EventType.ENEMY_LEAK: "ENEMY_LEAK",
}


def prediction_trace_from_result(plan: ExecutionPlan, result: SimulationResult, frame_clock: FrameClock | None = None) -> PredictionTrace:
    """Keep calibration output compact while exposing first-target acquisition.

    The simulator does not currently emit a standalone target-acquisition event, so
    the first attack-start per operator is presented as a *derived* acquisition
    marker. It is not a claim about a hidden client event.
    """
    events: list[PredictedEvent] = []
    seen_attackers: set[str] = set()
    for event in result.events:
        kind = _PREDICTED_EVENTS.get(event.event_type)
        if kind:
            frame = frame_clock.frame_for_seconds(event.time) if frame_clock and frame_clock.frames_per_second else None
            events.append(PredictedEvent(event.time, kind, event.source_id, event.target_id, frame))
        if event.event_type is EventType.ATTACK_START and event.source_id and event.source_id not in seen_attackers:
            seen_attackers.add(event.source_id)
            frame = frame_clock.frame_for_seconds(event.time) if frame_clock and frame_clock.frames_per_second else None
            events.append(PredictedEvent(event.time, "FIRST_TARGET_ACQUISITION", event.source_id, event.target_id, frame))
    end_frame = frame_clock.frame_for_seconds(result.time_survived) if frame_clock and frame_clock.frames_per_second else None
    events.append(PredictedEvent(result.time_survived, "BATTLE_END", frame=end_frame))
    events.sort(key=lambda item: (item.battle_time, item.kind, item.source_id or "", item.target_id or ""))
    metadata = result.run_metadata
    return PredictionTrace(
        plan.stage_id, plan.strategy_source, plan.strategy,
        metadata.mode if metadata else "SIMULATOR", metadata.approximations_used if metadata else plan.simulator_approximation_policy,
        "WIN" if result.win else "LOSS", result.time_survived, tuple(events),
    )


def predict_m7_main_00_01(data_root: Path) -> PredictionTrace:
    """Execute the source-backed/explicit-approximation simulator for the M7 plan."""
    plan = m7_main_00_01_execution_plan()
    policy = RealSimulationApproximationPolicy.main_00_01()
    adapter = ApproximateRealSimulationAdapter(GameDataRepository(data_root))
    fixture = adapter.build_pool_fixture(
        stage_id_or_code="0-1",
        configurations=(RealOperatorConfiguration("char_129_bluep", 2, 80),),
        policy=policy,
    )
    result = Simulator(
        range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel(),
    ).run(
        stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies, strategy=plan.strategy,
        config=SimulationConfig(dt=0.1, max_time=90.0),
    )
    from dataclasses import replace
    from arknights_planner.models.simulation import SimulationRunMetadata
    result = replace(result, run_metadata=SimulationRunMetadata("APPROXIMATE_REAL", fixture.approximations_used, ("main_00-01",)))
    return prediction_trace_from_result(plan, result, FrameClock.configured(30, provenance="M9 explicit approximate planner clock; client relation unresolved"))
