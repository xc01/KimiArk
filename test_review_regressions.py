from dataclasses import replace
from pathlib import Path
import json
import pytest
from arknights_planner.models.route import Route,Waypoint
from arknights_planner.models.runtime import SyntheticSkill,SkillEffect,SPRecoveryMode
from arknights_planner.models.strategy import Strategy,Action,ActionType
from arknights_planner.models.provenance import known
from arknights_planner.models.simulation import SimulationState,RuntimeDevice,EventType
from arknights_planner.simulator import Simulator,SimulationConfig
from arknights_planner.simulator.synthetic import runtime_stage,runtime_operators,runtime_enemies
from arknights_planner.gamedata.repository import GameDataRepository
from compile_r8_1_lowstar_c2_plan_v1 import build_dp_ledger

ROOT=Path(__file__).resolve().parents[0]

def test_static_sp_uses_first_deploy_until_retreat():
 p=ROOT/'output/r8_1_r8_7_batch_v1/main_08-07/local_device_revision_v12'
 plan=json.loads((p/'llm_structured_output.json').read_text())['revised_operational_plans'][0]
 evidence=json.loads((p/'llm_evidence_context.json').read_text())
 catalog={x['operator_id']:x for x in evidence['normal_low_star_catalog']}
 supports={x['operator_id']:x for x in json.loads((ROOT/'output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json').read_text())['operators']}
 full=build_dp_ledger(plan,catalog,supports,p)
 prefix=build_dp_ledger(dict(plan,action_timeline=[a for a in plan['action_timeline'] if a['frame']<3375]),catalog,supports,p)
 assert full['skill_readiness']['char_121_lava@2721']==prefix['skill_readiness']['char_121_lava@2721']

def test_zero_duration_auto_does_not_lose_recovery_tick():
 guard=replace(runtime_operators()['blocker'],synthetic_skill=SyntheticSkill('auto',1,2,SPRecoveryMode.TIME,1,0,SkillEffect(dp_immediate=1),True))
 stage=replace(runtime_stage(),spawn_events=(__import__('arknights_planner.models.stage',fromlist=['SpawnEvent']).SpawnEvent(100,'brute','main'),))
 result=Simulator().run(stage=stage,operators={'blocker':guard},enemies=runtime_enemies(),strategy=Strategy(('blocker',),(Action(ActionType.DEPLOY,0,'blocker',(3,1),'RIGHT'),)),config=SimulationConfig(dt=.1,max_time=6))
 assert [e.time for e in result.events if e.event_type is EventType.SKILL_ACTIVATE]==pytest.approx([1,3,5])

def test_civilian_bind_applies_at_point_five_tiles():
 sim=Simulator();stage=runtime_stage();state=SimulationState(0,0,3)
 enemy=GameDataRepository(ROOT/'data/ArknightsGameData').get_enemy('enemy_3001_upeopl')
 sim._spawn(state,stage,{enemy.enemy_id:enemy},enemy_id=enemy.enemy_id,route_id='main',spawn_index=0)
 runtime=next(iter(state.active_enemies.values()));runtime.distance=2.5;runtime.speed=1
 state.active_devices['rb']=RuntimeDevice('rb','trap_020_roadblock',(3,1),8000,8000,200,20,-1)
 sim._advance_enemies(state,stage,.01)
 assert runtime.distance==pytest.approx(2.5)

def test_circle_intersection_segment_endpoint():
 route=Route('test',(Waypoint(0,0),Waypoint(1,0)))
 windows=route.blocking_windows((1.3,0),radius=.4472)
 assert windows[0][0]==pytest.approx(1.3-.4472)
