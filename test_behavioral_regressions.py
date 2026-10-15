from dataclasses import replace
from pathlib import Path
import json
import os
import subprocess
import pytest
from arknights_planner.adapters.approximate_real import ApproximateRealSimulationAdapter
from arknights_planner.adapters.low_rarity_skill import LowRarityBlackboardEffectInterpreter
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route,Waypoint
from arknights_planner.models.enemy import EnemyAbility
from arknights_planner.models.simulation import SimulationState,EventType
from arknights_planner.models.strategy import Action,ActionType,Strategy
from arknights_planner.simulator.simulator import Simulator,_PendingAreaHit
from arknights_planner.simulator.synthetic import runtime_stage,runtime_operators,runtime_enemies
from compile_r8_1_lowstar_c2_plan_v1 import build_dp_ledger
ROOT=Path(__file__).resolve().parents[0]
repo=GameDataRepository(Path(os.environ.get('ARKNIGHTS_GAMEDATA_ROOT',str(ROOT/'data/ArknightsGameData'))))
adapter=ApproximateRealSimulationAdapter(repo)
sim=Simulator()

def source_op(oid):
 raw=repo.get_operator(oid);phase=1 if raw.star_rarity.value==3 else 0
 adapted=adapter.strict_adapter.adapt_operator(oid,phase_index=phase,level=int(raw.phases[phase].max_level.value),skill_level_index=6 if raw.skill_ids else 0)
 skill=LowRarityBlackboardEffectInterpreter().interpret(adapted.skill.skill.skill_id,adapted.skill.selected_level).executable_effect if adapted.skill else None
 return adapter._runtime_operator(adapted,interpreted_skill=skill,deployment_cost_delta=adapter._neutral_self_deployment_cost_delta(adapted))

def deploy(o,tile=(3,1)):
 state=SimulationState(0,1000,5);sim._deploy(state,runtime_stage(),{o.operator_id:o},Strategy((o.operator_id,),()),Action(ActionType.DEPLOY,0,o.operator_id,tile,'RIGHT'))
 return state,state.deployed_operators[o.operator_id]

def enemy(state,oid='brute',*,neutral=False,defense=0,hp=10000,atk=0,idx=0):
 base=runtime_enemies()['brute'];e=replace(base,enemy_id=oid,stats=replace(base.stats,atk=known(atk,'probe','atk'),max_hp=known(hp,'probe','hp'),defense=known(defense,'probe','def'),is_neutral=known(neutral,'probe','neutral'),attack_range=known(10,'probe','range')))
 sim._spawn(state,runtime_stage(),{oid:e},enemy_id=oid,route_id='main',spawn_index=idx)
 return state.active_enemies[f'{oid}#{idx}']

def test_ansel_skill_changes_actual_range():
 state,o=deploy(source_op('char_212_ansel'),(3,2));before=sim._effective_range(o);o.skill_active=True
 assert set(sim._effective_range(o))-set(before)

def test_midnight_active_skill_deals_arts_damage():
 state,o=deploy(source_op('char_283_midn'));o.skill_active=True;e=enemy(state,defense=200);e.distance=3
 sim._process_projectile_hit(state,o.operator_id,e.instance_id)
 hit=next(e for e in state.events if e.event_type is EventType.DAMAGE)
 assert dict(hit.details)['kind']=='arts'

def test_spot_skill_uses_source_heal_range():
 state,o=deploy(source_op('char_284_spot'));o.skill_active=True
 assert len(sim._effective_range(o))>1

def test_beagle_unlocked_defense_talent_applied():
 state,o=deploy(source_op('char_122_beagle'))
 assert o.defense==pytest.approx(490*1.1)

def test_circle_wholly_beyond_endpoint_has_no_contact():
 route=Route('r',(Waypoint(0,0),Waypoint(1,0)))
 assert route.blocking_windows((3,0),radius=.6)==()

def test_artillery_never_damages_hostile_enemies():
 state=SimulationState(0,0,5);hostile=enemy(state)
 before=hostile.hp;sim._process_area_hit(state,runtime_stage(),_PendingAreaHit(0,'artillery',(0,1),1.2,50,'PHYSICAL'))
 assert hostile.hp==before

def test_artillery_neutral_damage_respects_defense():
 state=SimulationState(0,0,5);civil=enemy(state,'civil',neutral=True,defense=20)
 before=civil.hp;sim._process_area_hit(state,runtime_stage(),_PendingAreaHit(0,'artillery',(0,1),1.2,50,'PHYSICAL'))
 assert before-civil.hp==pytest.approx(30)

def test_artillery_can_fire_again_after_first_impact():
 state=SimulationState(0,0,5);a=enemy(state,'artillery');c=enemy(state,'civil',neutral=True,idx=1)
 a.abilities=(EnemyAbility('shot','DELAYED_LOCKED_AREA_ATTACK',5,0,1.2,1,damage_type='PHYSICAL',delay_seconds=3,protected_target_priority=True),)
 pending=[];sim._enemy_ability_outputs(state,runtime_stage(),a,pending)
 state.time=3;sim._process_area_hit(state,runtime_stage(),pending.pop())
 state.time=5;sim._enemy_ability_outputs(state,runtime_stage(),a,pending)
 assert sum(e.event_type is EventType.ENEMY_ABILITY_START for e in state.events)==2

def test_artillery_has_no_extra_instant_single_target_attack():
 state,o=deploy(runtime_operators()['blocker']);a=enemy(state,'artillery',atk=10)
 a.abilities=(EnemyAbility('shot','DELAYED_LOCKED_AREA_ATTACK',5,0,1.2,1,damage_type='PHYSICAL',delay_seconds=3,protected_target_priority=True),)
 pending=[];sim._enemy_outputs(state,runtime_stage(),pending)
 assert pending
 assert not any(e.event_type is EventType.DAMAGE and e.source_id==a.instance_id for e in state.events)

def test_artillery_acquisition_range_not_explosion_radius():
 state,o=deploy(runtime_operators()['blocker'],(2,1));a=enemy(state,'artillery');c=enemy(state,'civil',neutral=True,idx=1);c.distance=1.5
 a.attack_range=2
 a.abilities=(EnemyAbility('shot','DELAYED_LOCKED_AREA_ATTACK',5,0,1.2,1,damage_type='PHYSICAL',delay_seconds=3,protected_target_priority=True),)
 pending=[];sim._enemy_ability_outputs(state,runtime_stage(),a,pending)
 assert pending[0].position==(1.5,1)

def test_static_refund_cannot_exceed_stage_max_dp(tmp_path):
 (tmp_path/'llm_evidence_context.json').write_text(json.dumps({'stage_options':{'initial_cost':99,'max_cost':99,'deployment_limit':8}}))
 cat={'guard':{'identity':{'rarity':3},'stats':{'cost':18},'selected_skills':[]}}
 plan={'action_timeline':[{'action_type':'DEPLOY','operator_id':'guard','frame':0},{'action_type':'RETREAT','operator_id':'guard','frame':3000}]}
 ledger=build_dp_ledger(plan,cat,{'guard':{}},tmp_path)
 assert ledger['final_balance']==99


def test_cold_changes_enemy_actual_attack_interval():
 state,o=deploy(runtime_operators()['blocker']);a=enemy(state,'cold_enemy',atk=10)
 state.time=15;a.attack_interval=1;a.attack_speed_status_until=25;a.attack_speed_status_delta=-30
 sim._enemy_outputs(state,runtime_stage(),[])
 assert a.next_attack_time==pytest.approx(15+1/.7)

def test_friendly_device_uses_source_x1_not_circle_one():
 from arknights_planner.models.stage import BattleDevice,SpawnEvent
 from arknights_planner.simulator import SimulationConfig
 grids={(x.row,x.col) for x in repo.get_range('x-1').cells};assert (2,0) in grids
 stage=replace(runtime_stage(),routes=(Route('main',(Waypoint(2,1),Waypoint(6,1))),),spawn_events=(SpawnEvent(0,'brute','main'),),devices=(BattleDevice('ice','trap_022_frosts_friend',(0,1),1000,0,0,0,False,'FRIENDLY'),))
 base=runtime_enemies()['brute'];e=replace(base,stats=replace(base.stats,move_speed=known(0,'probe','speed')))
 result=sim.run(stage=stage,operators={},enemies={'brute':e},strategy=Strategy((),()),config=SimulationConfig(dt=.1,max_time=15.1))
 assert any(e.event_type is EventType.ENEMY_STATUS_HIT for e in result.events)
