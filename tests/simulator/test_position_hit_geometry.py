"""R125 fix 2: cursor/feet offset + hit-radius collision (KB-BILI-004, KB-PRTS-004, KB-BILI-002)."""
from dataclasses import replace
from math import hypot
from arknights_planner.models.provenance import known
from arknights_planner.models.simulation import SimulationState, RuntimeEnemy
from arknights_planner.simulator import Simulator
from arknights_planner.simulator.synthetic import synthetic_stage, synthetic_enemies

SOURCE = "synthetic/r125-position"


def _state_with_enemy(distance: float):
    state = SimulationState(time=0, dp=20, remaining_life=3, max_dp=20)
    sim = Simulator()
    stage = synthetic_stage()
    sim._spawn(state, stage, synthetic_enemies(), enemy_id='slug', route_id='main', spawn_index=0)
    enemy = state.active_enemies['slug#0']
    enemy.distance = distance
    return sim, state, stage, enemy


def test_feet_offset_is_0_2_below_entity():
    sim, state, stage, enemy = _state_with_enemy(0.0)
    entity = sim._enemy_position(stage, enemy)
    feet = sim._enemy_feet_position(stage, enemy)
    assert abs(feet[0] - entity[0]) < 1e-9
    assert abs((entity[1] - 0.2) - feet[1]) < 1e-9


def test_hit_radius_distance_from_entity_center():
    sim, state, stage, enemy = _state_with_enemy(0.0)
    pos = sim._enemy_position(stage, enemy)
    assert sim._enemy_hit_radius() == 0.1
    # outside the hit radius by 0.11 -> no hit; 0.09 -> hit
    assert not sim._position_hits_enemy(stage, (pos[0] + 0.2, pos[1]), enemy, sim._enemy_hit_radius())
    assert sim._position_hits_enemy(stage, (pos[0] + 0.09, pos[1]), enemy, sim._enemy_hit_radius())


def test_entity_feet_and_cursor_track_route():
    sim, state, stage, enemy = _state_with_enemy(2.0)
    entity = sim._enemy_position(stage, enemy)
    cursor = sim._enemy_cursor_position(stage, enemy)
    feet = sim._enemy_feet_position(stage, enemy)
    assert hypot(cursor[0] - entity[0], cursor[1] - entity[1]) < 1e-9  # route offset currently zero
    assert abs(hypot(feet[0] - entity[0], feet[1] - entity[1]) - 0.2) < 1e-9
