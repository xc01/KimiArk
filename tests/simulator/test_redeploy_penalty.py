from dataclasses import replace
import pytest
from arknights_planner.models.simulation import SimulationState
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import Simulator
from arknights_planner.simulator.synthetic import synthetic_stage, synthetic_operators

def _mk():
    op = synthetic_operators()['guard']
    state = SimulationState(time=0, dp=40, remaining_life=3, max_dp=40)
    sim = Simulator(); stage = synthetic_stage()
    return sim, state, stage, op

def _deploy(sim, state, stage, op):
    sim._deploy(state, stage, {'guard': op}, Strategy(('guard',), ()),
                Action(ActionType.DEPLOY, state.time, 'guard', (3, 1), 'RIGHT'))

def test_penalty_sequence_5_7_10_10_and_refund_cap():
    sim, state, stage, op = _mk()
    costs = []
    for i in range(4):
        state.time = i * 10.0
        _deploy(sim, state, stage, op)
        costs.append(state.deployed_operators['guard'].deployment_cost)
        sim._remove_operator(state, 'guard', death=False)
    assert costs == [5, 7, 10, 10]  # 5, floor(5*1.5)=7, floor(5*2)=10, stack capped
    # guard is not charger: refunds floor(min(paid, base 5)*0.5)=2 each retreat
    assert state.dp == 40 - 5 - 7 - 10 - 10 + 2 * 4

def test_penalty_cap_and_death_increments_stack():
    sim, state, stage, op = _mk()
    _deploy(sim, state, stage, op)
    sim._remove_operator(state, 'guard', death=True)  # death stacks too
    state.time = 10; _deploy(sim, state, stage, op)
    assert state.deployed_operators['guard'].deployment_cost == 7
    sim._remove_operator(state, 'guard', death=False)
    assert state.redeploy_penalty_stacks['guard'] == 2
    state.time = 20; _deploy(sim, state, stage, op)
    assert state.deployed_operators['guard'].deployment_cost == 10
    sim._remove_operator(state, 'guard', death=False)
    state.time = 30; _deploy(sim, state, stage, op)
    assert state.deployed_operators['guard'].deployment_cost == 10  # capped at 2 stacks
    # death no refund; 4th stays deployed; retreats refund floor(min(paid,base 5)*0.5)=2 each
    assert state.dp == 40 - 5 - 7 - 10 - 10 + 2 * 2 == 12

def test_failed_deploy_does_not_stack_and_independent_ids():
    sim, state, stage, op = _mk()
    _deploy(sim, state, stage, op)
    state.dp = 0.0
    sim._remove_operator(state, 'guard', death=False)
    state.time += 30.0  # clear redeploy cooldown
    state.dp = 0.0      # force insufficient DP
    _deploy(sim, state, stage, op)
    assert state.redeploy_penalty_stacks.get('guard', 0) == 1  # only from retreat
    assert any('insufficient DP' in e for e in state.deployment_errors)
