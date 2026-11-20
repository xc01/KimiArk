"""R125 fixes 6/7: displacement force fields + fear/lure MODEL_GAP audit."""
from arknights_planner.models.simulation import RuntimeEnemy


def test_displacement_and_fear_lure_fields_exist():
    enemy = RuntimeEnemy(instance_id="e#0", enemy_id="slug", route_id="main", hp=1.0, speed=0.0, life_point_reduce=1)
    assert enemy.displacement_velocity == (0.0, 0.0)
    assert enemy.unbalance_until == 0.0
    assert enemy.fear_until == 0.0 and enemy.fear_target_tile is None
    assert enemy.lure_until == 0.0 and enemy.lure_target_tile is None
