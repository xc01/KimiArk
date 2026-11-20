"""R125 fix 4: enemy hatred orders by last-deployed first (KB-PRTS-001)."""
from dataclasses import replace
from arknights_planner.models.provenance import known
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage

SOURCE = "tests/simulator/test_enemy_last_deploy_priority.py"


def test_later_deployed_operator_attracted_first():
    # Enemy with a ranged attack range and two attackable operators: the later
    # deployed one must be selected by last-deploy-first hatred (KB-PRTS-001).
    from arknights_planner.models.stage import SpawnEvent
    enemies = {
        key: replace(enemy, stats=replace(enemy.stats, attack_range=known(2.5, SOURCE, "$.range")))
        for key, enemy in synthetic_enemies().items()
    }
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(0.0, "slug", "main"),))
    result = Simulator().run(
        stage=stage, operators=synthetic_operators(), enemies=enemies,
        strategy=Strategy(("guard", "archer"), (
            Action(ActionType.DEPLOY, 0.0, "guard", (2, 1), "RIGHT"),
            Action(ActionType.DEPLOY, 0.2, "archer", (3, 2), "UP"),
        )),
        config=SimulationConfig(dt=0.1, max_time=2.0),
    )
    selections = [event for event in result.events
                  if event.event_type.value == "TARGET_SELECTION"
                  and event.source_id.startswith("slug") and event.target_id]
    assert selections, "expected enemy to select a ranged target"
    later = [event for event in selections if event.time > 0.2]
    assert later, "expected enemy to reselect after archer deploys"
    first_after_archer = later[0]
    assert dict(first_after_archer.details).get("rule") == "ENEMY_HATRED_LAST_DEPLOYED_FIRST_MODEL_GAP_TAUNT_ARMOR"
    assert first_after_archer.target_id == "archer"
