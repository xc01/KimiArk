from dataclasses import replace
import pytest
from arknights_planner.models.simulation import SimulationState
from arknights_planner.models.provenance import known
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import Simulator
from arknights_planner.simulator.synthetic import synthetic_stage, synthetic_enemies, synthetic_operators
from arknights_planner.adapters.normal_low_star import charger_economy
from arknights_planner.adapters.approximate_real import ApproximateRealSimulationAdapter, M13LoadoutPolicy, RealSimulationApproximationPolicy
from arknights_planner.gamedata.repository import GameDataRepository

def setup_state(cap=99):
    op=replace(synthetic_operators()['guard'],kill_dp_reward=1,retreat_refunds_initial_cost=True)
    state=SimulationState(time=0,dp=20,remaining_life=3,max_dp=cap)
    sim=Simulator();stage=synthetic_stage()
    sim._deploy(state,stage,{'guard':op},Strategy(('guard',),()),Action(ActionType.DEPLOY,0,'guard',(3,1),'RIGHT'))
    return sim,state,stage,op

def test_source_trait_and_actual_adapter_mapping():
    repo=GameDataRepository('data/ArknightsGameData')
    assert charger_economy(repo,'char_192_falco')['kill_dp_reward']==1
    assert not charger_economy(repo,'char_123_fang')['retreat_refunds_initial_cost']
    adapter=ApproximateRealSimulationAdapter(repo)
    config=M13LoadoutPolicy.highest_legal().configuration(repo,'char_192_falco')
    fixture=adapter.build_pool_fixture(stage_id_or_code='main_08-07',configurations=(config,),policy=RealSimulationApproximationPolicy.m11_second_quantized())
    assert fixture.operators['char_192_falco'].kill_dp_reward==1
    assert fixture.operators['char_192_falco'].retreat_refunds_initial_cost

@pytest.mark.parametrize('kill_owner,expected',[('guard',1),('other',0)])
def test_final_blow_only_once(kill_owner,expected):
    sim,state,stage,op=setup_state();before=state.dp
    sim._spawn(state,stage,synthetic_enemies(),enemy_id='slug',route_id='main',spawn_index=0)
    enemy=state.active_enemies['slug#0']
    sim._damage_enemy(state,enemy,kill_owner,40,kind='physical')
    assert state.dp==before
    sim._damage_enemy(state,enemy,kill_owner,60,kind='physical')
    assert state.dp==before+expected
    events=[e for e in state.events if dict(e.details).get('reason')=='charger_kill_reward']
    assert len(events)==expected

def test_cap_and_nonkill_neutral_no_income():
    sim,state,stage,op=setup_state();state.dp=99
    sim._spawn(state,stage,synthetic_enemies(),enemy_id='slug',route_id='main',spawn_index=0)
    sim._damage_enemy(state,state.active_enemies['slug#0'],'guard',100,kind='physical')
    event=state.events[-2] if state.events[-1].event_type.name=='ENEMY_DEATH' else state.events[-1]
    assert state.dp==99 and dict(event.details)['amount']==0
    sim._spawn(state,stage,synthetic_enemies(),enemy_id='slug',route_id='main',spawn_index=1)
    neutral=state.active_enemies['slug#1'];neutral.is_neutral=True;neutral.counts_as_kill=False
    state.dp=50;sim._damage_enemy(state,neutral,'guard',100,kind='physical')
    assert state.dp==50

def test_living_retreat_initial_cost_across_redeploy_and_no_death_refund():
    sim,state,stage,op=setup_state();state.dp=0
    sim._remove_operator(state,'guard',death=False)
    assert state.dp==5
    state.time=10;state.dp=20
    stats=replace(op.phases[0].stats_max,cost=known(9,'test','cost'))
    newop=replace(op,phases=(replace(op.phases[0],stats_max=stats),))
    sim._deploy(state,stage,{'guard':newop},Strategy(('guard',),()),Action(ActionType.DEPLOY,10,'guard',(3,1),'RIGHT'))
    assert state.deployed_operators['guard'].deployment_cost==9
    sim._remove_operator(state,'guard',death=False)
    assert state.dp==16 #20-9+initial5, not current9
    state.time=20;sim._deploy(state,stage,{'guard':op},Strategy(('guard',),()),Action(ActionType.DEPLOY,20,'guard',(3,1),'RIGHT'))
    before=state.dp;sim._remove_operator(state,'guard',death=True)
    assert state.dp==before

def test_static_full_refund_without_assuming_any_kills(tmp_path):
    import json
    from compile_r8_1_lowstar_c2_plan_v1 import build_dp_ledger
    (tmp_path/'llm_evidence_context.json').write_text(json.dumps({'stage_options':{'initial_cost':10,'max_cost':99,'deployment_limit':8}}))
    plan={'action_timeline':[{'action_type':'DEPLOY','operator_id':'x','frame':0},{'action_type':'RETREAT','operator_id':'x','frame':30}]}
    cat={'x':{'identity':{'rarity':3},'stats':{'cost':10},'selected_skills':[]}}
    support={'x':{'economy_trait':{'retreat_refunds_initial_cost':True}}}
    ledger=build_dp_ledger(plan,cat,support,tmp_path)
    refunds=[e for e in ledger['entries'] if e['event']=='RETREAT_REFUND']
    assert refunds[0]['delta']==10 and ledger['final_balance']==11
    assert not any('KILL' in e['event'] for e in ledger['entries'])
