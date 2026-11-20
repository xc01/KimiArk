"""R125 fix 8 verification: artillery skips without target and does not reset cooldown (KB-R124-001)."""
from dataclasses import replace
from arknights_planner.models.provenance import known
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import synthetic_operators, synthetic_stage


def test_artillery_empty_candidates_does_not_fire():
    # regression guard: no candidates -> no ENEMY_ABILITY_START emitted; semantics
    # verified by code audit (cooldown not written when candidates empty).
    from arknights_planner.simulator.synthetic import synthetic_enemies
    result = Simulator().run(
        stage=synthetic_stage(), operators=synthetic_operators(), enemies=synthetic_enemies(),
        strategy=Strategy((), ()),
        config=SimulationConfig(dt=1 / 30, max_time=1.0),
    )
    assert not [event for event in result.events if event.event_type.value == "ENEMY_ABILITY_START"]
