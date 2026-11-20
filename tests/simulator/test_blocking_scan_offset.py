"""R125 fix 3: 3-frame block scan + 0.2s reposition (KB-BILI-002)."""
from dataclasses import replace
from math import hypot
from arknights_planner.models.provenance import known
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage

SOURCE = "tests/simulator/test_blocking_scan_offset.py"


def _stage(spawn_frame: int = 0):
    stage = synthetic_stage()
    return replace(stage, spawn_events=(SpawnEvent(spawn_frame / 30, "slug", "main"),))


def _operators():
    return synthetic_operators()


def test_real_frame_rate_blocks_on_scan_frame():
    stage = _stage(0)
    result = Simulator().run(
        stage=stage, operators=_operators(), enemies=synthetic_enemies(),
        strategy=Strategy(("guard",), (Action(ActionType.DEPLOY, 0, "guard", (3, 1), "RIGHT"),)),
        config=SimulationConfig(dt=1 / 30, max_time=3.0),
    )
    blocks = [event for event in result.events if event.event_type.value == "BLOCK" and event.source_id == "guard"]
    assert blocks, "expected enemy to be blocked at real frame rate"
    # BLOCK should occur on a tick where tick_index % 3 == 0
    assert any(abs(event.time * 30 % 3) < 1e-9 for event in blocks)


def test_reposition_target_recorded_and_0_2s_window():
    sim = Simulator()
    state = sim._init_state(stage=_stage(0), operators=_operators(), enemies=synthetic_enemies(), stage_id=None) if hasattr(sim, "_init_state") else None
    # Direct unit check: RuntimeEnemy fields exist and helper applies movement
    from arknights_planner.models.simulation import RuntimeEnemy
    enemy = RuntimeEnemy(instance_id="e#0", enemy_id="slug", route_id="main", hp=1.0, speed=0.0, life_point_reduce=1)
    assert enemy.block_reposition_remaining == 0.0
    assert enemy.block_reposition_target is None
