from types import SimpleNamespace
from dataclasses import replace

from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, RouteWait, Waypoint
from arknights_planner.models.simulation import SimulationState
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.responsibility_feasibility import build_early_threat_model
from arknights_planner.simulator import Simulator
from arknights_planner.simulator.synthetic import synthetic_stage, synthetic_enemies, synthetic_operators


def test_latest_model_interception_considers_the_last_revisit():
    route = Route(
        "loop", (Waypoint(4, 3), Waypoint(3, 3), Waypoint(4, 3), Waypoint(3, 3), Waypoint(4, 3), Waypoint(9, 1)),
        tuple(RouteWait(float(d), 4.0) for d in range(5)),
    )
    fixture = SimpleNamespace(
        stage=SimpleNamespace(routes=(route,)),
        spawn_timeline=(SimpleNamespace(route_id="loop", time=0.0, count=1, interval=0.0, enemy_id="enemy"),),
        enemies={"enemy": SimpleNamespace(stats=SimpleNamespace(move_speed=known(1.1, "synthetic/review", "$.speed")))},
        operators={},
    )
    understanding = SimpleNamespace(
        routes=(SimpleNamespace(route_id="loop", exact_cells=((3, 3), (4, 3)), lane_id="lane"),),
        deployable_ground=((3, 3), (4, 3)), deployable_high_ground=(),
    )
    result = build_early_threat_model(SimpleNamespace(fixture=fixture), understanding, early_window=SimpleNamespace(route_ids=("loop",)))
    row = result.routes[0]
    assert row.earliest_operator_contact_frame == 0
    assert row.latest_interception_tile == (4, 3)
    assert row.latest_interception_distance == 4.0
    assert row.latest_safe_blocker_frame == 589


def test_late_deployment_can_block_a_revisited_tile_in_the_public_runtime():
    stage = replace(synthetic_stage(), routes=(Route("main", (Waypoint(0, 1), Waypoint(4, 1), Waypoint(0, 1), Waypoint(6, 1))),))
    state = SimulationState(5.0, 10.0, 3)
    simulator = Simulator()
    strategy = Strategy(("guard",), (Action(ActionType.DEPLOY, 5.0, "guard", (3, 1)),))
    simulator._deploy(state, stage, synthetic_operators(), strategy, strategy.actions[0])
    simulator._spawn(state, synthetic_stage(), synthetic_enemies(), enemy_id="slug", route_id="main", spawn_index=0)
    enemy = state.active_enemies["slug#0"]
    enemy.distance = 5.0
    simulator._advance_enemies(state, stage, 0.1)
    assert enemy.blocked_by == "guard"
    assert enemy.distance == 5.0
