from __future__ import annotations

from dataclasses import replace

from arknights_planner.models.enemy import Enemy, EnemyStats
from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.projectile import ProjectileModel
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage


class OneSecondProjectile:
    def hit_delay(self, *, source_tile, target_position) -> float:
        return 1.0


def test_delayed_projectile_does_not_hit_after_shooter_death():
    stage = replace(
        synthetic_stage(),
        spawn_events=(SpawnEvent(0.0, "slug", "main"),),
        routes=(Route("main", (Waypoint(1, 1), Waypoint(6, 1))),),
    )
    enemies = dict(synthetic_enemies())
    enemies["slug"] = Enemy(
        "slug",
        known("Delay Probe", "stronghold-differential/micro", "$.slug.name"),
        replace(
            enemies["slug"].stats,
            move_speed=known(0.0, "stronghold-differential/micro", "$.slug.speed"),
            attack_interval=known(0.9, "stronghold-differential/micro", "$.slug.interval"),
            atk=known(600, "stronghold-differential/micro", "$.slug.atk"),
            attack_range=known(2.0, "stronghold-differential/micro", "$.slug.range"),
        ),
        "stronghold-differential/micro",
    )
    strategy = Strategy(("archer",), (Action(ActionType.DEPLOY, 1.1, "archer", (1, 2), "UP"),))
    result = Simulator(projectile_model=OneSecondProjectile()).run(
        stage=stage,
        operators=synthetic_operators(),
        enemies=enemies,
        strategy=strategy,
        config=SimulationConfig(dt=0.1, max_time=4.0),
    )
    born = [event for event in result.events if event.event_type.name == "PROJECTILE_BORN" and event.source_id == "archer"]
    impacts = [event for event in result.events if event.event_type.name == "PROJECTILE_HIT" and event.source_id == "archer"]
    assert [event.time for event in born] == [1.1]
    assert impacts == []
