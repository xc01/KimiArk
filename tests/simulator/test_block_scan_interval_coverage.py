"""R127: the 3-frame block scan must cover the whole travelled interval.

R125 fix 3 gated operator block scans to every third logical frame but kept the
candidate window at the single tick [start, proposed].  Any enemy that crossed a
blocker's tile during the two skipped frames was never tested and walked free --
on main_08-07 this silently dropped the archived M70 eight-operator WIN from
33 kills / 0 leaks to 9 kills / 24 leaks.  The scan must instead test the
distance travelled since the previous scan.
"""
from dataclasses import replace

from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import (
    synthetic_enemies,
    synthetic_operators,
    synthetic_stage,
)


def _run(spawn_frame: int):
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(spawn_frame / 30, "slug", "main"),))
    return Simulator().run(
        stage=stage,
        operators=synthetic_operators(),
        enemies=synthetic_enemies(),
        strategy=Strategy(("guard",), (Action(ActionType.DEPLOY, 0, "guard", (3, 1), "RIGHT"),)),
        config=SimulationConfig(dt=1 / 30, max_time=6.0),
    )


def test_every_spawn_phase_is_blocked_despite_3_frame_scan() -> None:
    # A single blocker must catch the enemy no matter which tick of the 3-frame
    # scan cycle the enemy happens to cross its tile on.
    failures = []
    for spawn_frame in range(30):
        result = _run(spawn_frame)
        blocks = [event for event in result.events if event.event_type.value == "BLOCK"]
        if not blocks or result.enemies_leaked:
            failures.append((spawn_frame, len(blocks), result.enemies_leaked))
    assert failures == []


def test_block_scan_start_tracks_last_scanned_distance() -> None:
    result = _run(0)
    events = [event for event in result.events if event.event_type.value == "BLOCK"]
    assert events, "enemy should be blocked"
    # BLOCK is emitted on a scan frame (tick_index % 3 == 0 at real frame rate).
    assert any(abs(event.time * 30 % 3) < 1e-9 for event in events)
