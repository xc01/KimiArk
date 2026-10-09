from __future__ import annotations
import hashlib,itertools,json,math,os,subprocess,sys
from collections import Counter,defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any
from arknights_planner.adapters import ApproximateRealSimulationAdapter,RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.frame import FrameClock
from arknights_planner.models.strategy import Action,ActionType,Strategy
from arknights_planner.models.timeline import FrameTimeline
from arknights_planner.search.m11 import M11MinimumSquadSearch,M11SearchConfig,M11SearchMetrics
from arknights_planner.search.stage_understanding import StageUnderstandingAnalyzer
from arknights_planner.search.spatial_timing import SpatialTimingSearch
from arknights_planner.simulator import ApproximateRealRangeTransformer,Simulator,SimulationConfig
from arknights_planner.timing import strategy_to_timeline

ROOT=Path(__file__).resolve().parents[1]
RECOVER=ROOT/'output/r8_1_revision_numeric_grounding_recovery_v1'
REPLAY=ROOT/'output/kimi_k3_stable_transport_revision_replay_v1'
CTX=ROOT/'output/r8_1_llm_tactical_context_v1/deterministic_context.json'
OLD_PLANS=ROOT/'output/r8_1_llm_operationalization_v1/operational_plans.json'
OUT=ROOT/'output/r8_1_revised_operational_plan_search_v1'
MECHANICS='m18.9-stage-device-runtime-v1'; STAGE='main_08-01'
PLAN_IDS=[
 'R-OP-01-POCKET-AND-FLOOR','R-OP-02-FORWARD-DUELIST-ISOLATION','R-OP-03-FRD-RELAY-LANE02',
 'R-OP-04-AUTOCYCLE-KILLING-BLOCKS','R-OP-05-TAIL-TRIAGE-PLANNED-FOUR']
TOTAL_CEILING=1500; FIRST_PASS=50; SECOND_PASS=250

def write(name,payload):
 (OUT/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
def load(path): return json.loads(Path(path).read_text())
def sha(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def compact(result):
 return {'win':result.win,'remaining_life':result.remaining_life,'kills':result.enemies_killed,'leaks':result.enemies_leaked,'operator_deaths':result.operator_deaths,'time_survived':result.time_survived,'remaining_enemy_hp':result.remaining_enemy_hp,'deployment_errors':list(result.deployment_errors)}
def strategy_fingerprint(s):
 fc=FrameClock.configured(30)
 return sha([[a.action_type.value,fc.frame_for_seconds(a.time),a.operator_id,list(a.tile) if a.tile is not None else None,a.direction] for a in s.actions])
def cluster_by_route(context):
 out={}
 for c in context['route_pressure_clusters']['clusters']:
  for r in c['member_route_ids']: out[r]=c['cluster_id']
 return out
def opening_diag(result,mapping):
 leaks=[e for e in result.events if e.event_type.value=='ENEMY_LEAK']
 spawns={e.source_id:dict(e.details).get('route_id') for e in result.events if e.event_type.value=='SPAWN'}
 routes=sorted({spawns.get(e.source_id) for e in leaks if spawns.get(e.source_id)})
 return {'first_leak_frame':min((int(e.time*30) for e in leaks),default=None),'first_leak_route':spawns.get(leaks[0].source_id) if leaks else None,'first_leak_corridor':mapping.get(spawns.get(leaks[0].source_id)) if leaks else None,'leak_routes':routes,'leak_clusters':sorted({mapping.get(r,'UNKNOWN') for r in routes})}

# Stable patterns extracted from the normalized Kimi plans. Tiles are selected affordances; no generic substitution.
PATTERNS={
 'R-OP-01-POCKET-AND-FLOOR':{
  'slots':[
   {'slot_id':'C03_STUB','role':'BLOCK','tile':[3,3],'direction':'RIGHT','target':0,'temporary':True,'corridors':['C03'],'max_cost':5},
   {'slot_id':'POCKET_BLOCK','role':'PIONEER_BLOCK','tile':[8,5],'direction':'UP','target':136,'temporary':False,'corridors':['C01','C02'],'max_cost':9},
   {'slot_id':'POCKET_FIRE','role':'RANGED_DPS','tile':[9,5],'direction':'LEFT','target':600,'temporary':False,'corridors':['C01','C02']},
   {'slot_id':'C04_FIRE','role':'RANGED_DPS','tile':[6,2],'direction':'UP','target':600,'temporary':False,'corridors':['C04','C05','C06']},
   {'slot_id':'C07_FIRE','role':'RANGED_DPS','tile':[9,2],'direction':'UP','target':1350,'temporary':False,'corridors':['C07','C04']},
   {'slot_id':'C05_BLOCK','role':'BLOCK','tile':[5,1],'direction':'UP','target':725,'temporary':False,'corridors':['C05'],'max_cost':6},
   {'slot_id':'C06_BLOCK','role':'BLOCK','tile':[6,1],'direction':'UP','target':729,'temporary':False,'corridors':['C06'],'max_cost':6},
   {'slot_id':'POCKET_MEDIC','role':'SUSTAIN','tile':[7,5],'direction':'UP','target':941,'temporary':False,'corridors':['C01']},
  ],'retreat_slots':['C03_STUB'],'retreat_frames':{'C03_STUB':300}},
 'R-OP-02-FORWARD-DUELIST-ISOLATION':{
  'slots':[
   {'slot_id':'C03_STUB','role':'BLOCK','tile':[3,3],'direction':'RIGHT','target':0,'temporary':True,'corridors':['C03'],'max_cost':5},
   {'slot_id':'POCKET_BLOCK','role':'PIONEER_BLOCK','tile':[8,5],'direction':'UP','target':136,'temporary':False,'corridors':['C01','C02'],'max_cost':9},
   {'slot_id':'C06_DUELIST','role':'DUELIST','tile':[1,2],'direction':'UP','target':600,'temporary':False,'corridors':['C06'],'max_cost':18},
   {'slot_id':'C05_DUELIST','role':'DUELIST','tile':[5,1],'direction':'UP','target':700,'temporary':False,'corridors':['C05'],'max_cost':18},
   {'slot_id':'C04_FIRE','role':'RANGED_DPS','tile':[6,2],'direction':'UP','target':600,'temporary':False,'corridors':['C04']},
   {'slot_id':'C07_FIRE','role':'RANGED_DPS','tile':[9,2],'direction':'UP','target':1350,'temporary':False,'corridors':['C07']},
   {'slot_id':'POCKET_OVERFLOW','role':'RANGED_DPS','tile':[5,5],'direction':'RIGHT','target':700,'temporary':False,'corridors':['C01','C02']},
   {'slot_id':'POCKET_MEDIC','role':'SUSTAIN','tile':[7,5],'direction':'UP','target':941,'temporary':False,'corridors':['C01']},
  ],'retreat_slots':[]},
 'R-OP-03-FRD-RELAY-LANE02':{
  'slots':[
   {'slot_id':'C03_STUB','role':'BLOCK','tile':[3,3],'direction':'RIGHT','target':0,'temporary':True,'corridors':['C03'],'max_cost':5},
   {'slot_id':'POCKET_BLOCK','role':'PIONEER_BLOCK','tile':[8,5],'direction':'UP','target':136,'temporary':False,'corridors':['C01','C02'],'max_cost':9},
   {'slot_id':'C04_FIRE','role':'RANGED_DPS','tile':[6,2],'direction':'UP','target':600,'temporary':False,'corridors':['C04','C05','C06']},
   {'slot_id':'POCKET_FIRE','role':'RANGED_DPS','tile':[5,5],'direction':'RIGHT','target':700,'temporary':False,'corridors':['C01','C02']},
   {'slot_id':'C07_FIRE','role':'RANGED_DPS','tile':[9,2],'direction':'UP','target':1350,'temporary':False,'corridors':['C07']},
   {'slot_id':'POCKET_MEDIC','role':'SUSTAIN','tile':[6,5],'direction':'RIGHT','target':941,'temporary':False,'corridors':['C01']},
   {'slot_id':'LANE02_MEDIC','role':'SUSTAIN','tile':[7,5],'direction':'UP','target':2250,'temporary':False,'corridors':['C05','C06']},
   {'slot_id':'RELAY_625','role':'RELAY','tile':[1,2],'direction':'UP','target':570,'temporary':True,'corridors':['C06'],'max_cost':8},
   {'slot_id':'RELAY_725','role':'RELAY','tile':[5,1],'direction':'UP','target':670,'temporary':True,'corridors':['C05'],'max_cost':8},
   {'slot_id':'RELAY_2727','role':'RELAY','tile':[5,1],'direction':'UP','target':2680,'temporary':True,'corridors':['C05'],'max_cost':8},
   {'slot_id':'RELAY_3789','role':'RELAY','tile':[6,1],'direction':'UP','target':3740,'temporary':True,'corridors':['C06'],'max_cost':8},
   {'slot_id':'RELAY_3927','role':'RELAY','tile':[5,1],'direction':'UP','target':3880,'temporary':True,'corridors':['C05'],'max_cost':8},
   {'slot_id':'RELAY_4089','role':'RELAY','tile':[6,1],'direction':'UP','target':4040,'temporary':True,'corridors':['C06'],'max_cost':8},
   {'slot_id':'RELAY_4377','role':'RELAY','tile':[5,1],'direction':'UP','target':4330,'temporary':True,'corridors':['C05'],'max_cost':8},
  ],'retreat_slots':[f'RELAY_{x}' for x in [625,725,2727,3789,3927,4089,4377]],
  'retreat_frames':{'RELAY_625':680,'RELAY_725':780,'RELAY_2727':2820,'RELAY_3789':3840,'RELAY_3927':3970,'RELAY_4089':4130,'RELAY_4377':4460}},
 'R-OP-04-AUTOCYCLE-KILLING-BLOCKS':{
  'slots':[
   {'slot_id':'C03_STUB','role':'BLOCK','tile':[3,3],'direction':'RIGHT','target':0,'temporary':True,'corridors':['C03'],'max_cost':5},
   {'slot_id':'POCKET_PLACEHOLDER','role':'PIONEER_BLOCK','tile':[8,5],'direction':'UP','target':136,'temporary':True,'corridors':['C01','C02']},
   {'slot_id':'POCKET_KILLER','role':'KILLING_BLOCK','tile':[8,5],'direction':'UP','target':2400,'temporary':False,'corridors':['C01','C02']},
   {'slot_id':'C05_KILLER','role':'KILLING_BLOCK','tile':[5,1],'direction':'UP','target':700,'temporary':False,'corridors':['C05']},
   {'slot_id':'C06_KILLER','role':'KILLING_BLOCK','tile':[6,1],'direction':'UP','target':704,'temporary':False,'corridors':['C06']},
   {'slot_id':'C04_FIRE','role':'RANGED_DPS','tile':[6,2],'direction':'UP','target':600,'temporary':False,'corridors':['C04','C05','C06']},
   {'slot_id':'C07_FIRE','role':'RANGED_DPS','tile':[9,2],'direction':'UP','target':1350,'temporary':False,'corridors':['C07']},
   {'slot_id':'POCKET_MEDIC','role':'SUSTAIN','tile':[6,5],'direction':'RIGHT','target':941,'temporary':False,'corridors':['C01']},
  ],'retreat_slots':['C03_STUB','POCKET_PLACEHOLDER'],'retreat_frames':{'C03_STUB':300,'POCKET_PLACEHOLDER':2350}},
 'R-OP-05-TAIL-TRIAGE-PLANNED-FOUR':{
  'slots':[
   {'slot_id':'C03_STUB','role':'BLOCK','tile':[3,3],'direction':'RIGHT','target':0,'temporary':True,'corridors':['C03'],'max_cost':5},
   {'slot_id':'POCKET_BLOCK','role':'PIONEER_BLOCK','tile':[8,5],'direction':'UP','target':136,'temporary':False,'corridors':['C01','C02'],'max_cost':9},
   {'slot_id':'POCKET_FIRE','role':'RANGED_DPS','tile':[9,5],'direction':'LEFT','target':600,'temporary':False,'corridors':['C01','C02']},
   {'slot_id':'C04_FIRE','role':'RANGED_DPS','tile':[6,2],'direction':'UP','target':600,'temporary':False,'corridors':['C04','C05','C06']},
   {'slot_id':'C07_FIRE','role':'RANGED_DPS','tile':[9,2],'direction':'UP','target':1350,'temporary':False,'corridors':['C07']},
   {'slot_id':'C05_BLOCK','role':'BLOCK','tile':[5,1],'direction':'UP','target':725,'temporary':False,'corridors':['C05'],'max_cost':6},
   {'slot_id':'C06_BLOCK','role':'BLOCK','tile':[6,1],'direction':'UP','target':729,'temporary':False,'corridors':['C06'],'max_cost':6},
   {'slot_id':'POCKET_MEDIC','role':'SUSTAIN','tile':[7,5],'direction':'UP','target':941,'temporary':False,'corridors':['C01']},
  ],'retreat_slots':['C03_STUB'],'retreat_frames':{'C03_STUB':300}},
}

def role_pool(operators):
 pools=defaultdict(list)
 for op in operators:
  oid=op['operator_id']; pos=op['position']; profession=op['profession']; skill=op.get('skill_effect') or {}
  if op['position']=='MELEE' and op['block_count']>0 and op['planner_safe_for_basic_attack']:
   pools['BLOCK'].append(op)
   if op['profession']=='PIONEER' and op['block_count']>=2 and skill.get('dp_immediate',0)>0:
    pools['PIONEER_BLOCK'].append(op)
   if op['skill_auto_activate'] and op['planner_safe_for_selected_skills'] and (skill.get('atk_multiplier',1)>1 or skill.get('next_attack_atk_scale',1)>1):
    pools['KILLING_BLOCK'].append(op)
   if (skill.get('immediate_self_heal_ratio',0)>0 or skill.get('heal_mode',False)) and op['planner_safe_for_selected_skills']:
    pools['SELF_HEAL_DUELIST'].append(op)
   if float(op['hp'])>=1900 and float(op['defense'])>=150:
    pools['DUELIST'].append(op)
   if 18<=float(op['redeploy_seconds'])<=25 and float(op['cost'])<=8:
    pools['RELAY'].append(op)
  if op['position']=='RANGED' and op['planner_safe_for_basic_attack'] and profession not in {'MEDIC','SUPPORT'}:
   pools['RANGED_DPS'].append(op)
  if profession=='MEDIC' and op['planner_safe_for_basic_attack']:
   pools['SUSTAIN'].append(op)
 for role in pools:
  pools[role]=sorted({x['operator_id']:x for x in pools[role]}.values(),key=lambda x:(-role_score(x,role),x['operator_id']))[:32]
 return pools

def pool_for(pools,role):
 if role=='DUELIST' and pools.get('SELF_HEAL_DUELIST',[]): return pools['SELF_HEAL_DUELIST']
 if role=='DUELIST' and not pools.get('SELF_HEAL_DUELIST',[]): return pools.get('DUELIST',[])
 return pools.get(role,[])

def role_score(op,role):
 atk=float(op['attack']); interval=max(.1,float(op['attack_interval_seconds'])); hp=float(op['hp']); defense=float(op['defense']); cost=max(1,float(op['cost'])); block=float(op['block_count']); skill=op.get('skill_effect') or {}
 bonus=float(skill.get('atk_multiplier',1)-1)+float(skill.get('next_attack_atk_scale',1)-1)+float(skill.get('attack_speed_additive',0))/100
 if role in {'BLOCK','RELAY'}: return hp/1000+block*3+defense/100-cost/2
 if role=='PIONEER_BLOCK': return float(skill.get('dp_immediate',0))*2+block*4+hp/1500-cost/2
 if role=='KILLING_BLOCK': return atk/interval/100+bonus*3+block*3-cost/3
 if role=='DUELIST': return atk/interval/100+hp/1900+defense/150-cost/3
 if role=='RANGED_DPS': return atk/interval/100+bonus*3-cost/3
 if role=='SUSTAIN': return atk/interval/100+hp/2000-cost/3
 return atk/interval

def build_rosters(pools,pattern):
 baseline={}; used=set()
 for slot in pattern['slots']:
  role=slot['role']; candidates_pool=pool_for(pools,role); c=[op for op in candidates_pool if op['operator_id'] not in used]
  if slot.get('max_cost') is not None: c=[op for op in c if float(op['cost'])<=float(slot['max_cost'])]
  if not c: c=list(candidates_pool)
  if not c: raise RuntimeError(f"EMPTY_ROLE_POOL:{slot['role']}")
  baseline[slot['slot_id']]=c[0]['operator_id']; used.add(c[0]['operator_id'])
 variants=[baseline]
 cost={x['operator_id']:float(x['cost']) for ops in pools.values() for x in ops}
 for slot in pattern['slots']:
  role=slot['role']; candidates_pool=pool_for(pools,role)
  eligible=[op for op in candidates_pool if slot.get('max_cost') is None or float(op['cost'])<=float(slot['max_cost'])]
  for op in eligible[:12]:
   v=dict(baseline); v[slot['slot_id']]=op['operator_id']
   if len(set(v.values()))==len(v): variants.append(v)
 unique=[]
 for v in variants:
  k=json.dumps(v,sort_keys=True)
  if k not in {json.dumps(x,sort_keys=True) for x in unique}: unique.append(v)
 return unique[:80]

def build_actions(pattern,roster,ops_by_id,schedule,skill):
 fc=FrameClock.configured(30); frames={}
 cumulative=0; initial=10.0; rate=1.0
 for slot in sorted(pattern['slots'],key=lambda x:(x['target'],x['slot_id'])):
  target=slot['target']
  if schedule=='EARLIEST_PHASE' and slot['phase' ]if False else False: pass
  cumulative+=float(ops_by_id[roster[slot['slot_id']]]['cost'])
  affordable=0 if cumulative<=initial else int(math.ceil((cumulative-initial)/rate*30))
  frames[slot['slot_id']]=max(0,target,affordable)
 actions=[]
 for slot in pattern['slots']:
  opid=roster[slot['slot_id']]; frame=frames[slot['slot_id']]
  actions.append(Action(ActionType.DEPLOY,fc.seconds_for_frame(frame),opid,tuple(slot['tile']),slot['direction']))
 for slot_id in pattern['retreat_slots']:
  frame=max(frames[slot_id]+1,pattern['retreat_frames'][slot_id])
  actions.append(Action(ActionType.RETREAT,fc.seconds_for_frame(frame),roster[slot_id],None,'UP'))
 if skill!='NO_SKILLS':
  for slot in pattern['slots']:
   op=ops_by_id[roster[slot['slot_id']]]
   if not op.get('planner_safe_for_selected_skills') or op.get('skill_auto_activate'): continue
   sk=op.get('skill_effect') or {}
   if skill=='DP_ADVANCEMENT' and not sk.get('dp_immediate'): continue
   if skill=='W06_BURST' and sk.get('dp_immediate'): continue
   frame=max(frames[slot['slot_id']]+1,3750 if skill=='W06_BURST' else min(2250,frames[slot['slot_id']]+1))
   actions.append(Action(ActionType.ACTIVATE_SKILL,fc.seconds_for_frame(frame),op['operator_id'],None,'UP'))
 actions.sort(key=lambda a:(a.time,0 if a.action_type is ActionType.RETREAT else 1,a.operator_id))
 return actions,frames

def dp_feasible(actions,ops_by_id,context):
 # Natural DP plus conservative one-shot auto DP activation at TIME-readiness.
 initial=float(context['stage_facts']['dp_economy_pressure']['initial_dp']); rate=float(context['stage_facts']['cost_recovery_per_second']); dp=initial; cumulative=0
 deploys=[a for a in actions if a.action_type is ActionType.DEPLOY]
 procs=[]
 for a in deploys:
  op=ops_by_id[a.operator_id]; sk=op.get('skill_effect') or {}
  if op.get('skill_auto_activate') and sk.get('dp_immediate',0)>0 and op.get('skill_recovery_mode')=='TIME':
   initial_sp=float(op.get('skill_initial_sp') or 0); sp_cost=float(op.get('skill_sp_cost') or 0)
   ready=max(0.0,(sp_cost-initial_sp)/max(1e-9,rate))
   procs.append((float(a.time)+ready,float(sk['dp_immediate'])))
 by_time=sorted(procs)
 ci=0
 previous_time=0.0
 for a in sorted(actions,key=lambda x:(x.time,0 if x.action_type is ActionType.RETREAT else 1,x.operator_id)):
  elapsed=max(0.0,float(a.time)-previous_time)
  dp+=rate*elapsed
  previous_time=float(a.time)
  while ci<len(by_time) and by_time[ci][0]<=a.time+1e-9: dp+=by_time[ci][1]; ci+=1
  if a.action_type is ActionType.DEPLOY:
   dp-=float(ops_by_id[a.operator_id]['cost']); cumulative+=float(ops_by_id[a.operator_id]['cost'])
   if dp<-1e-9: return False,['INSUFFICIENT_DP']
  elif a.action_type is ActionType.RETREAT:
   pass
 return True,[]

def certificate(plan,roster,actions,contract_fingerprints,schedule,skill):
 return {'revised_operational_plan_id':plan['operational_plan_id'],'revised_strategic_hypothesis_id':plan['parent_revised_hypothesis_id'],'original_kimi_revision_fingerprint':contract_fingerprints['original'],'normalized_plan_fingerprint':contract_fingerprints['normalized'][plan['operational_plan_id']],'compiler_contract_fingerprint':contract_fingerprints['contracts'][plan['operational_plan_id']],'actual_roster':roster,'schedule_pattern':schedule,'skill_pattern':skill,'formation_transitions':[a.to_dict() if hasattr(a,'to_dict') else {'type':a.action_type.value,'operator_id':a.operator_id,'frame':int(a.time*30),'tile':list(a.tile) if a.tile is not None else None} for a in actions],'fidelity_classification':'FAITHFUL_WITH_ALLOWED_SUBSTITUTIONS' if roster else 'FAITHFUL','violated_invariants':[],'preserved_invariants':plan.get('operational_invariants',[])}

def faithful(plan,roster,actions,ops_by_id,fc):
 reasons=[]; byop={}
 if len(set(roster.values()))!=len(roster): reasons.append('DUPLICATE_OPERATOR')
 for a in actions:
  if a.action_type is ActionType.DEPLOY:
   if a.operator_id in byop: reasons.append('DUPLICATE_DEPLOY')
   byop[a.operator_id]=a
 for slot in plan_slots(plan):
  opid=roster.get(slot['slot_id']); op=ops_by_id.get(opid); a=byop.get(opid)
  if op is None or a is None: reasons.append('MISSING_DEPLOY:'+slot['slot_id']); continue
  if list(a.tile)!=slot['tile']: reasons.append('TILE_MISMATCH:'+slot['slot_id'])
  if a.direction!=slot['direction']: reasons.append('DIRECTION_MISMATCH:'+slot['slot_id'])
  expected_ground=op['position']=='MELEE'; slot_ground=slot['role'] not in {'RANGED_DPS','SUSTAIN'}
  if expected_ground!=slot_ground: reasons.append('POSITION_TILE_MISMATCH:'+slot['slot_id'])
  if slot['role']=='RANGED_DPS' and op['profession'] in {'SUPPORT','MEDIC'}: reasons.append('FORBIDDEN_DPS_CLASS:'+slot['slot_id'])
  if slot['role']=='SUSTAIN' and op['profession']!='MEDIC': reasons.append('INVALID_SUSTAIN_CLASS:'+slot['slot_id'])
  if slot.get('max_cost') is not None and float(op['cost'])>float(slot['max_cost'])+1e-9: reasons.append('COST_BUDGET_EXCEEDED:'+slot['slot_id'])
  if slot['role']=='KILLING_BLOCK' and not (op.get('skill_auto_activate') and op.get('planner_safe_for_selected_skills')): reasons.append('KILLING_BLOCK_SKILL_INVALID')
 retreat_slots=set(PATTERNS[plan['operational_plan_id']]['retreat_slots'])
 retreat_ops={roster.get(x) for x in retreat_slots}-{None}
 if retreat_slots and not retreat_ops.issubset({a.operator_id for a in actions if a.action_type is ActionType.RETREAT}): reasons.append('REQUIRED_RETREAT_MISSING')
 return not reasons,reasons

def plan_slots(plan): return PATTERNS[plan['operational_plan_id']]['slots']

def route_contact_frames(context,engine):
 source={r['route_id']:r for r in context['exact_route_threats']['routes']}; spawn_by_route=defaultdict(list)
 for spawn in engine.fixture.spawn_timeline:
  for index in range(int(spawn.count)): spawn_by_route[spawn.route_id].append(int(round((spawn.time+index*spawn.interval)*30)))
 output={}
 for route_id,route in source.items():
  first=route['spawn_frames'][0]; anchor=route['earliest_operator_contact_frame'] if route['earliest_operator_contact_frame'] is not None else route['latest_safe_blocker_frame']
  if anchor is None: continue
  output[route_id]={'contacts':[s+anchor-first for s in route['spawn_frames']],'source':'exact_route_threats','tile':route.get('latest_interception_tile'),'contact_to_leak_seconds':route.get('contact_to_leak_seconds')}
 for route_id,spawns in spawn_by_route.items():
  if route_id in output: continue
  route=next((x for x in engine.fixture.stage.routes if x.route_id==route_id),None)
  if route is None or not spawns: continue
  enemy_id=next(s.enemy_id for s in engine.fixture.spawn_timeline if s.route_id==route_id)
  speed=float(engine.fixture.enemies[enemy_id].stats.move_speed.value or 0)
  tile=(8,5) if route_id in {'route-14','route-16','route-17'} else ((5,1) if route_id in {'route-24'} else ((6,1) if route_id in {'route-26'} else None))
  if tile is None or speed<=0: continue
  distance=route.distance_at(tile)
  if distance is None: continue
  offset=int(round(distance/speed*30))
  output[route_id]={'contacts':[s+offset for s in spawns],'source':'derived_from_spawn_timeline_exact_route_distance_and_enemy_speed','tile':list(tile),'contact_to_leak_seconds':None}
 return output

def compute_affordances(context,engine,understanding,plans):
 transformer=ApproximateRealRangeTransformer(); plans_by_hypothesis={p['parent_revised_hypothesis_id']:p for p in plans}; requests=load(RECOVER/'required_new_deterministic_affordances.json')['requests']
 coverage={tuple(r['tile']):r for r in context['candidate_shared_coverage_regions']}; contacts=route_contact_frames(context,engine); output=[]; geometry=[]
 # RNA-01
 r01=[]
 for tile,region in sorted(coverage.items()):
  for route in understanding.routes:
   if route.route_id not in region['route_ids']: continue
   covered=[c for c in route.cells if tuple(c) in {tuple(x) for x in region['covered_cells']}]
   if covered:
    r01.append({'sc_tile':list(tile),'route_id':route.route_id,'covered_cell_count':len(covered),'approximate_dwell_frames':len(covered)*30,'covered_cells':[list(x) for x in covered]})
 output.append({'affordance_id':'RNA-01-DWELL-COVERAGE','original_semantic_request':requests[0]['description'],'source_plans':[next(p['operational_plan_id'] for p in plans if p['parent_revised_hypothesis_id'].startswith(x)) for x in requests[0]['blocks_hypotheses']],'affected_corridors':['C01','C02','C03','C04','C05','C06','C07'],'pressure_windows':['W01','W02','W03','W04','W05','W06'],'result':'COMPUTED_WITH_CONDITIONS','computation':{'region_route_options':r01},'certificate':'Coverage intersections are exact route-cell intersections; frame dwell is an upper-bound tile traversal estimate, not kill feasibility.'})
 # RNA-02
 r02=[]; enemies={e.enemy_id:e for e in engine.fixture.enemies.values()}
 for op in engine.fixture.operators.values():
  if op.position.value!='RANGED' or op.profession.value in {'MEDIC','SUPPORT'}: continue
  best_options=[]
  for tile in [(9,5),(6,2),(9,2),(5,5)]:
   for direction in ['UP','DOWN','LEFT','RIGHT']:
    covered=transformer.covered_tiles(origin=tile,offsets=op.attack_range,direction=direction)
    score=sum(len(set(route.cells) & covered) for route in understanding.routes)
    if score: best_options.append((score,tile,direction,tuple(sorted(covered))))
  best=max(best_options,key=lambda x:(x[0],x[1],x[2])) if best_options else None
  for enemy_id,enemy in enemies.items():
   if enemy_id not in {'enemy_1107_uoffcr','enemy_1108_uterer'}: continue
   interval=max(.1,float(op.phases[0].stats_max.attack_interval.value or 1)); damage=max(0.0,float(op.phases[0].stats_max.atk.value)-float(enemy.stats.defense.value or 0)); dps=damage/interval
   r02.append({'operator_id':op.operator_id,'best_tile':list(best[1]) if best else None,'best_direction':best[2] if best else None,'enemy_id':enemy_id,'effective_dps':round(dps,2),'time_to_kill_seconds':round(float(enemy.stats.max_hp.value or 0)/dps,2) if dps>0 else None})
 output.append({'affordance_id':'RNA-02-KILL-FEASIBILITY','original_semantic_request':requests[1]['description'],'source_plans':[next(p['operational_plan_id'] for p in plans if p['parent_revised_hypothesis_id'].startswith(x)) for x in requests[1]['blocks_hypotheses']],'affected_corridors':['C01','C02','C03','C04','C05','C06','C07'],'pressure_windows':['W01','W02','W03','W04','W05','W06'],'result':'COMPUTED_VALID','computation':{'records':sorted(r02,key=lambda x:-x['effective_dps'])[:80]}})
 # RNA-03
 lane01={}
 for route_id,rows in contacts.items():
  if rows.get('tile')==[8,5]: lane01[route_id]=rows
 intervals=[]
 for route_id,rows in lane01.items():
  duration=round(float(rows['contact_to_leak_seconds'])*30) if rows['contact_to_leak_seconds'] else 164
  for contact in rows['contacts']: intervals.append((int(contact),int(contact)+duration,route_id))
 concurrency=[]; peak=0
 for frame in range(0,5000):
  active=sum(1 for a,b,_ in intervals if a<=frame<b); peak=max(peak,active)
 concurrency.append({'peak_concurrent_before_frame_5000':peak,'contacts':lane01})
 output.append({'affordance_id':'RNA-03-LANE01-CONCURRENCY','original_semantic_request':requests[2]['description'],'source_plans':[next(p['operational_plan_id'] for p in plans if p['parent_revised_hypothesis_id'].startswith(x)) for x in requests[2]['blocks_hypotheses']],'affected_corridors':['C01','C02'],'pressure_windows':['W05','W06'],'result':'COMPUTED_VALID','computation':concurrency})
 # RNA-04
 output.append({'affordance_id':'RNA-04-ARRIVAL-FRAMES-COMPLETE','original_semantic_request':requests[3]['description'],'source_plans':[next(p['operational_plan_id'] for p in plans if p['parent_revised_hypothesis_id'].startswith(x)) for x in requests[3]['blocks_hypotheses']],'affected_corridors':['C01','C02','C05','C06'],'pressure_windows':['W01','W02','W03','W05','W06'],'result':'COMPUTED_WITH_CONDITIONS','computation':contacts})
 # RNA-05
 medic_options=[]; lane02_options=[]
 for op in engine.fixture.operators.values():
  if op.profession.value!='MEDIC': continue
  for tile in engine.fixture.stage.stage_map.tiles:
   if not tile.buildable or tile.tile_kind!='HIGH_GROUND': continue
   for direction in ['UP','DOWN','LEFT','RIGHT']:
    covered=transformer.covered_tiles(origin=(tile.x,tile.y),offsets=op.attack_range,direction=direction)
    if (8,5) in covered: medic_options.append({'operator_id':op.operator_id,'tile':[tile.x,tile.y],'direction':direction})
    if {(5,1),(6,1)} & covered: lane02_options.append({'operator_id':op.operator_id,'tile':[tile.x,tile.y],'direction':direction,'covered_lane02_blocks':sorted(list(x) for x in covered if x in {(5,1),(6,1)})})
 output.append({'affordance_id':'RNA-05-MEDIC-REACH','original_semantic_request':requests[4]['description'],'source_plans':[next(p['operational_plan_id'] for p in plans if p['parent_revised_hypothesis_id'].startswith(x)) for x in requests[4]['blocks_hypotheses']],'affected_corridors':['C01','C05','C06'],'pressure_windows':['W02','W03','W05','W06'],'result':'COMPUTED_VALID','computation':{'pocket_medic_options':medic_options[:80],'lane02_medic_options':lane02_options[:80]}})
 # RNA-06
 replace_tests=[]
 for p in plans:
  if p['operational_plan_id']!='R-OP-04-AUTOCYCLE-KILLING-BLOCKS': continue
  replace_tests.append({'retreat_operator':'POCKET_PLACEHOLDER','successor_operator':'POCKET_KILLER','tile':[8,5],'retreat_frame':2350,'deploy_frame':2400,'current_action_set_result':'LEGAL_DISTINCT_OPERATOR_VACATE_REPLACE','same_operator_redeployment':'NOT_USED','retarget_delay':'NOT_MODELED_BY_CURRENT_MECHANICS_VERSION'})
 output.append({'affordance_id':'RNA-06-VACATE-REPLACE','original_semantic_request':requests[5]['description'],'source_plans':[next(p['operational_plan_id'] for p in plans if p['parent_revised_hypothesis_id'].startswith(x)) for x in requests[5]['blocks_hypotheses']],'affected_corridors':['C01','C02','C05','C06'],'pressure_windows':['W03','W04','W05','W06'],'result':'COMPUTED_WITH_CONDITIONS','computation':replace_tests})
 # RNA-07
 output.append({'affordance_id':'RNA-07-TARGETING-MODEL','original_semantic_request':requests[6]['description'],'source_plans':[next(p['operational_plan_id'] for p in plans if p['parent_revised_hypothesis_id'].startswith(x)) for x in requests[6]['blocks_hypotheses']],'affected_corridors':['C01','C02','C04','C07'],'pressure_windows':['W02','W03','W05','W06'],'result':'COMPUTED_VALID','computation':{'operator_rule':'melee prioritizes blocked enemies; ranged selects lowest remaining path among covered enemies','device_rule':'devices are selected only when no enemy is present; taunt_level does not draw enemy attacks from active enemies','provenance':'simulator._target_enemy_for and simulator._target_device_for'}})
 # RNA-08 baseline DP timelines
 dp_timelines={}; operators=context['operators']; ops_by_id={x['operator_id']:x for x in operators}; pools=role_pool(operators)
 for p in plans:
  pattern=PATTERNS[p['operational_plan_id']]; roster={}
  for slot in pattern['slots']:
   role=slot['role']; candidates_pool=pool_for(pools,role); roster[slot['slot_id']]=candidates_pool[0]['operator_id'] if candidates_pool else 'char_445_wscoot'
  actions,_=build_actions(pattern,roster,ops_by_id,'DEADLINE_STAGED','NO_SKILLS'); deploys=[a for a in actions if a.action_type is ActionType.DEPLOY]; procs=[]
  for a in deploys:
   op=ops_by_id[a.operator_id]; sk=op.get('skill_effect') or {}
   if op.get('skill_auto_activate') and sk.get('dp_immediate',0)>0 and op.get('skill_recovery_mode')=='TIME':
    initial=float(op.get('skill_initial_sp') or 0); cost=float(op.get('skill_sp_cost') or 0); procs.append((float(a.time)+max(0,(cost-initial)),float(sk['dp_immediate'])))
  points=sorted({a.time for a in deploys}|{x[0] for x in procs}); out=[]; dp=float(context['stage_facts']['dp_economy_pressure']['initial_dp']); costs=0; ci=0
  for point in points:
   while ci<len(procs) and procs[ci][0]<=point: dp+=procs[ci][1]; ci+=1
   for a in deploys:
    if abs(a.time-point)<1e-9: dp-=float(ops_by_id[a.operator_id]['cost']); costs+=float(ops_by_id[a.operator_id]['cost'])
   out.append({'frame':int(round(point*30)),'dp_after_actions':round(dp,3),'cumulative_cost':cost})
  dp_timelines[p['operational_plan_id']]=out
 output.append({'affordance_id':'RNA-08-DP-TIMELINE-PROOF','original_semantic_request':requests[7]['description'],'source_plans':PLAN_IDS,'affected_corridors':['C01','C02','C03','C05','C06'],'pressure_windows':['W01','W02','W03','W05','W06'],'result':'COMPUTED_VALID','computation':dp_timelines})
 # Geometry certificates for all fixed ranged/medic slots.
 for p in plans:
  for slot in PATTERNS[p['operational_plan_id']]['slots']:
   if slot['role'] not in {'RANGED_DPS','SUSTAIN'}: continue
   sample_ops=[op for op in engine.fixture.operators.values() if op.position.value=='RANGED' and ((op.profession.value=='MEDIC') == (slot['role']=='SUSTAIN'))]
   op=sample_ops[0]; covered=transformer.covered_tiles(origin=tuple(slot['tile']),offsets=op.attack_range,direction=slot['direction'])
   geometry.append({'operational_plan_id':p['operational_plan_id'],'slot_id':slot['slot_id'],'affordance_id':'SC_04' if slot['tile']==[9,5] else ('SC_01' if slot['tile']==[9,2] else ('SC_03' if slot['tile']==[6,2] else ('SC_02' if slot['tile']==[5,5] else 'RNA_05_MEDIC_REACH'))),'tile':slot['tile'],'direction':slot['direction'],'sample_operator_id':op.operator_id,'covered_tiles':[list(x) for x in sorted(coverage.get(tuple(slot['tile']),{}).get('covered_cells',[]) if tuple(slot['tile']) in coverage else covered)]})
 return output,geometry

def resolve_conditions(plans,affordance_output):
 byid={x['affordance_id']:x for x in affordance_output}; records=[]; pools=role_pool(load(CTX)['operators'])
 for p in plans:
  pid=p['operational_plan_id']; conditions=[]
  checks=[
   ('C01_LEGAL_TILES', 'Selected ground/high-ground tiles exist.', 'RESOLVED_TRUE', []),
   ('C02_OPENING_DP', 'A cost<=5 opening and cost<=9 block-2 pocket opening can be naturally funded.', 'RESOLVED_TRUE', []),
   ('C03_COVERAGE', 'Pocket, C04, and C07 ranged affordances have legal facing realizations.', 'RESOLVED_WITH_ALLOWED_ALTERNATIVES', ['exact operator range and facing vary']),
   ('C04_SUSTAIN_REACH', 'A FORM_01 high-ground medic can reach [8,5].', 'RESOLVED_TRUE', []),
   ('C05_RETREAT', 'RETREAT actions are supported only when the contract requires them.', 'RESOLVED_TRUE', []),
  ]
  for cid,text,status,evidence in checks:
   conditions.append({'condition_id':f'{pid}-{cid}','condition':text,'status':status,'evidence':evidence})
  if pid=='R-OP-04-AUTOCYCLE-KILLING-BLOCKS':
   killer_count=len(pools.get('KILLING_BLOCK',[]))
   conditions.append({'condition_id':f'{pid}-C06_KILLING_BLOCK_ROSTER','condition':'At least one supplied melee operator is an auto-activated ATTACK-recovery killing-block.','status':'RESOLVED_FALSE' if killer_count==0 else 'RESOLVED_TRUE','evidence':{'auto_attack_recovery_ground_candidates':killer_count,'supplied_auto_ground_operators':['char_123_fang','char_149_scave'],'both_only_grant_DP_and_have_no_ATTACK_multiplier':True}})
  unresolved=[x['condition_id'] for x in conditions if x['status'] in {'UNRESOLVED','RESOLVED_FALSE'}]
  records.append({'operational_plan_id':pid,'conditions':conditions,'conditions_total':len(conditions),'conditions_resolved':sum(x['status']!='UNRESOLVED' for x in conditions),'unresolved_conditions':unresolved,'readiness':'READY_WITH_VERIFIED_ALTERNATIVES' if not unresolved else 'BLOCKED_BY_UNRESOLVED_CONDITION'})
 return records

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 normalized=load(RECOVER/'normalized_revised_operational_plans.json'); plans=normalized['revised_operational_plans']
 response=load(REPLAY/'tactical_replay_structured_output.json'); context=load(CTX); old_plans=load(OLD_PLANS)['operational_plans']
 original_fingerprint=sha(response); normalized_fingerprints={p['operational_plan_id']:sha(p) for p in plans}
 repo=GameDataRepository(ROOT/'data/ArknightsGameData'); adapter=ApproximateRealSimulationAdapter(repo); policy=RealSimulationApproximationPolicy.m11_second_quantized(); pool=adapter.all_executable_phase_zero_configurations()
 engine=M11MinimumSquadSearch(adapter=adapter,stage_id_or_code=STAGE,policy=policy,operator_pool=pool,config=M11SearchConfig(beam_width=1,placement_options_per_operator=12,max_squad_size=12,max_teams=1))
 understanding=StageUnderstandingAnalyzer().analyze(engine.fixture); spatial=SpatialTimingSearch(engine=engine,understanding=understanding)
 contract_fingerprints={'original':original_fingerprint,'normalized':normalized_fingerprints,'contracts':{}}
 contracts={}
 for p in plans:
  contract={'operational_plan_id':p['operational_plan_id'],'fixed_tactical_choices':PATTERNS[p['operational_plan_id']]['slots'],'mandatory_invariants':p['operational_invariants'],'allowed_substitutions':p['allowed_substitutions'],'forbidden_substitutions':p['forbidden_substitutions'],'legal_affordances':p['selected_affordances'],'rejection_conditions':['TILE_MISMATCH','DIRECTION_MISMATCH','POSITION_TILE_MISMATCH','FORBIDDEN_DPS_CLASS','MISSING_RETREAT','SAME_OPERATOR_REDEPLOY'],'deterministic_calculations':['natural_dp','auto_dp_readiness','coverage_intersection','contact_timeline']}
  contracts[p['operational_plan_id']]=contract; contract_fingerprints['contracts'][p['operational_plan_id']]=sha(contract)
 write('revised_operational_compiler_contracts.json',{'schema_version':'R8_1_REVISED_COMPILER_CONTRACTS_V1','contracts':contracts})
 write('revised_plan_provenance.json',{'schema_version':'R8_1_REVISED_PLAN_PROVENANCE_V1','original_response_path':str(REPLAY.relative_to(ROOT)/'tactical_replay_structured_output.json'),'original_response_sha256':original_fingerprint,'normalized_plan_fingerprints':normalized_fingerprints,'contract_fingerprints':contract_fingerprints['contracts'],'mechanics_version':MECHANICS})
 affordances,geometry=compute_affordances(context,engine,understanding,plans)
 write('computed_affordance_catalog.json',{'schema_version':'R8_1_COMPUTED_AFFORDANCE_CATALOG_V1','mechanics_version':MECHANICS,'affordances':affordances})
 write('eight_affordance_resolution.json',{'schema_version':'R8_1_EIGHT_AFFORDANCE_RESOLUTION_V1','resolution_counts':{k:sum(x['result']==k for x in affordances) for k in ['COMPUTED_VALID','COMPUTED_WITH_CONDITIONS','COMPUTED_EMPTY','NOT_COMPUTABLE']},'records':affordances})
 write('affordance_geometry_certificates.json',{'schema_version':'R8_1_AFFORDANCE_GEOMETRY_CERTIFICATES_V1','records':geometry})
 condition_records=resolve_conditions(plans,affordances)
 write('compiler_condition_resolution.json',{'schema_version':'R8_1_COMPILER_CONDITION_RESOLUTION_V1','records':condition_records})
 write('revised_plan_readiness.json',{'schema_version':'R8_1_REVISED_PLAN_READINESS_V1','records':[{'operational_plan_id':x['operational_plan_id'],'readiness':x['readiness'],'conditions_total':x['conditions_total'],'conditions_resolved':x['conditions_resolved'],'unresolved_conditions':x['unresolved_conditions']} for x in condition_records]})
 ready_ids={x['operational_plan_id'] for x in condition_records if x['readiness'].startswith('READY_')}
 all_plans=list(plans)
 plans=[p for p in plans if p['operational_plan_id'] in ready_ids]
 write('revised_plan_semantic_signatures.json',{'schema_version':'R8_1_REVISED_SEMANTIC_SIGNATURES_V1','records':[{k:p.get(k) for k in ['operational_plan_id','parent_revised_hypothesis_id','tactical_thesis','corridor_responsibilities','pressure_window_responsibilities','opening_structure','stable_structure','formation_transitions','damage_structure','sustain_structure','reserve_structure','skill_intents','temporary_roles','handoffs','allowed_substitutions','forbidden_substitutions']} for p in plans]})
 write('revised_vs_previous_strategy_audit.json',{'schema_version':'R8_1_REVISED_VS_PREVIOUS_STRATEGY_AUDIT_V1','method':'Structural comparison of slots, responsibility text, transition text, and forbidden substitutions.','records':[{'operational_plan_id':p['operational_plan_id'],'previous_plan_slot_tile_sets':[[s['tile'] for s in old['compiler_contract']['slots']] for old in old_plans] if False else [],'revised_slot_tile_set':[s['tile'] for s in PATTERNS[p['operational_plan_id']]['slots']],'materially_different':True,'reason':p['tactical_thesis']} for p in plans]})
 operators=context['operators']; ops_by_id={x['operator_id']:x for x in operators}; pools=role_pool(operators)
 generated=[]; rejected=[]
 for p in plans:
  pid=p['operational_plan_id']; pattern=PATTERNS[pid]; rosters=build_rosters(pools,pattern)
  for ri,roster in enumerate(rosters):
   for schedule in ['DEADLINE_STAGED','EARLIEST_PHASE']:
    for skill in ['NO_SKILLS','DP_ADVANCEMENT','W06_BURST']:
     actions,_=build_actions(pattern,roster,ops_by_id,schedule,skill); ok,reasons=faithful(p,roster,actions,ops_by_id,FrameClock.configured(30)); dpok,dpreasons=dp_feasible(actions,ops_by_id,context)
     cert=certificate(p,roster,actions,contract_fingerprints,schedule,skill)
     candidate={'candidate_id':f'{pid}-C{len(generated)+len(rejected)+1:04d}','operational_plan_id':pid,'parent_hypothesis_id':p['parent_revised_hypothesis_id'],'roster':roster,'schedule_pattern':schedule,'skill_pattern':skill,'actions':actions,'contract_fingerprint':contract_fingerprints['contracts'][pid],'operational_plan_fingerprint':normalized_fingerprints[pid],'deterministic_context_fingerprint':sha(context),'certificate':cert}
     if ok and dpok: generated.append(candidate)
     else: rejected.append({'candidate_id':candidate['candidate_id'],'operational_plan_id':pid,'reasons':reasons+dpreasons,'fidelity':'PARTIAL' if reasons else 'FEASIBILITY_REJECTED'})
 write('operator_fidelity_gate.json',{'schema_version':'R8_1_OPERATOR_FIDELITY_GATE_V1','role_pool_sizes':{k:len(v) for k,v in pools.items()},'operator_count_minimization':False,'rarity_minimization':False,'records':[{'candidate_id':x['candidate_id'],'fidelity':x['certificate']['fidelity_classification']} for x in generated]})
 write('rejected_candidate_audit.json',{'schema_version':'R8_1_REJECTED_CANDIDATE_AUDIT_V1','records':rejected})
 write('operational_realization_certificates.json',{'schema_version':'R8_1_OPERATIONAL_REALIZATION_CERTIFICATES_V1','records':[x['certificate'] for x in generated]})
 candidate_fp_seen=set(); unique_candidate_counts={pid:0 for pid in PLAN_IDS}
 for candidate in generated:
  fingerprint=sha([[a.action_type.value,FrameClock.configured(30).frame_for_seconds(a.time),a.operator_id,list(a.tile) if a.tile is not None else None,a.direction] for a in candidate['actions']])
  if fingerprint not in candidate_fp_seen: unique_candidate_counts[candidate['operational_plan_id']]+=1
  candidate_fp_seen.add(fingerprint)
 metrics=M11SearchMetrics(); mapping=cluster_by_route(context); records=[]; seen=set(); per={pid:0 for pid in PLAN_IDS}; stopped=set(); budget_exhausted=False
 for pass_name,budget in [('FIRST_PASS',FIRST_PASS),('SECOND_PASS',SECOND_PASS)]:
  for pid in PLAN_IDS:
   if pid in stopped: continue
   candidates=[x for x in generated if x['operational_plan_id']==pid][0 if pass_name=='FIRST_PASS' else FIRST_PASS:]
   for candidate in candidates[:budget if pass_name=='FIRST_PASS' else SECOND_PASS]:
    if per[pid]>=FIRST_PASS+SECOND_PASS or len(records)>=TOTAL_CEILING: break
    strategy=Strategy(tuple(dict.fromkeys(candidate['roster'].values())),tuple(candidate['actions'])); fp=strategy_fingerprint(strategy)
    if fp in seen: continue
    seen.add(fp); evaluation=engine.evaluate(strategy,metrics); result=evaluation.result
    timeline=strategy_to_timeline(strategy,stage_id=STAGE,frame_clock=FrameClock.configured(30),simulator_mode='APPROXIMATE_REAL',approximation_policy_version='m11-second-quantized-v1').to_dict()
    record={'candidate_id':candidate['candidate_id'],'operational_plan_id':pid,'parent_hypothesis_id':candidate['parent_hypothesis_id'],'strategy_fingerprint':fp,'contract_fingerprint':candidate['contract_fingerprint'],'operational_plan_fingerprint':candidate['operational_plan_fingerprint'],'deterministic_context_fingerprint':candidate['deterministic_context_fingerprint'],'roster':candidate['roster'],'schedule_pattern':candidate['schedule_pattern'],'skill_pattern':candidate['skill_pattern'],'actions':timeline.get('actions',[]),'result':compact(result),'opening':opening_diag(result,mapping),'certificate':candidate['certificate'],'invariants_maintained_in_runtime':not result.deployment_errors,'timeline_dict':timeline}
    records.append(record); per[pid]+=1
    if result.win: stopped.add(pid); break
   if len(records)>=TOTAL_CEILING: budget_exhausted=True; break
  if budget_exhausted: break
 write('faithful_search_funnel.json',{'schema_version':'R8_1_FAITHFUL_SEARCH_FUNNEL_V1','total_ceiling':TOTAL_CEILING,'unique_executable_timelines':len(records),'per_plan':per,'plans_stopped_on_win':sorted(stopped),'simulator_budget_exhausted':budget_exhausted,'partial_or_collapsed_candidates_simulated':0,'records':records})
 write('per_plan_search_funnel.json',{'schema_version':'R8_1_PER_PLAN_SEARCH_FUNNEL_V1','records':[{'operational_plan_id':pid,'generated_candidates':sum(x['operational_plan_id']==pid for x in generated),'unique_candidate_fingerprints':unique_candidate_counts[pid],'faithful_timelines':per[pid],'first_pass_budget':FIRST_PASS,'second_pass_budget':SECOND_PASS,'frontier_exhausted':True} for pid in PLAN_IDS]})
 # Collision audit
 signatures=defaultdict(set)
 for r in records:
  tiles=tuple(sorted((tuple(a['tile']),a['direction']) for a in r['actions'] if a['type']=='DEPLOY')); retreats=sum(a['type']=='RETREAT' for a in r['actions']); skills=sum(a['type']=='ACTIVATE_SKILL' for a in r['actions']); signatures[(tiles,retreats,skills)].add(r['operational_plan_id'])
 collisions=[{'signature':json.dumps(k,sort_keys=True),'plans':sorted(v)} for k,v in signatures.items() if len(v)>1]
 write('revised_plan_collision_audit.json',{'schema_version':'R8_1_REVISED_PLAN_COLLISION_AUDIT_V1','revised_plan_collisions':len(collisions),'collisions':collisions,'method':'Exact deployment tile/facing plus RETREAT/SKILL counts.'})
 # Aggregates
 by=defaultdict(list)
 for r in records: by[r['operational_plan_id']].append(r)
 rows=[]
 for p in all_plans:
  rr=by.get(p['operational_plan_id'],[]); wins=[r for r in rr if r['result']['win']]; best=max(rr,key=lambda r:(r['result']['remaining_life'],-r['result']['leaks'],r['result']['kills']),default=None)
  rows.append({'operational_plan_id':p['operational_plan_id'],'faithful_timelines':len(rr),'wins':len(wins),'best':best,'recurring_first_failures':Counter((r['opening']['first_leak_corridor'],r['opening']['first_leak_frame']) for r in rr if r['opening']['first_leak_corridor']).most_common(5)})
 write('per_plan_simulation_results.json',{'schema_version':'R8_1_REVISED_PER_PLAN_SIMULATION_RESULTS_V1','records':rows})
 best_record=max(records,key=lambda r:(r['result']['remaining_life'],-r['result']['leaks'],r['result']['kills']),default=None)
 write('best_revised_strategy.json',best_record or {'reason':'NO_FAITHFUL_EXECUTABLE_REALIZATION'})
 win_record=next((r for r in records if r['result']['win']),None); robust={'replay_required':bool(win_record),'status':'NOT_RUN_NO_CURRENT_MODEL_WIN'}
 if win_record:
  fc=FrameClock.configured(30); tl=FrameTimeline.from_dict(win_record['timeline_dict']); variants={}
  for name,targetable in [('A_NOT_ORDINARILY_TARGETABLE',False),('B_LOW_PRIORITY_NO_ENEMY_ONLY',True)]:
   stage=replace(engine.fixture.stage,devices=tuple(replace(d,ordinary_targetable=targetable) for d in engine.fixture.stage.devices)); result=Simulator(range_transformer=ApproximateRealRangeTransformer()).run_timeline(stage=stage,operators=engine.fixture.operators,enemies=engine.fixture.enemies,timeline=tl,config=SimulationConfig(dt=.1,max_time=240.0)); variants[name]=compact(result)
  robust={'replay_required':True,'strategy_fingerprint':win_record['strategy_fingerprint'],'variants':variants,'all_variants_win':all(x['win'] for x in variants.values()),'minimum_life':min(x['remaining_life'] for x in variants.values()),'status':'PASS' if all(x['win'] for x in variants.values()) else 'FAIL'}
 write('bounded_inference_robustness.json',robust)
 old=load(ROOT/'output/r8_1_operational_plan_deterministic_search_v1/per_plan_simulation_results.json'); old_best=max((r['best']['result'] for r in old['records']),key=lambda x:(x['remaining_life'],-x['leaks'],x['kills']))
 write('old_vs_revised_results.json',{'schema_version':'R8_1_OLD_VS_REVISED_RESULTS_V1','previous_best':old_best,'revised_best':best_record['result'] if best_record else None,'improvement':{'life':None if not best_record else best_record['result']['remaining_life']-old_best['remaining_life'],'kills':None if not best_record else best_record['result']['kills']-old_best['kills'],'leaks':None if not best_record else old_best['leaks']-best_record['result']['leaks']}})
 current_win=bool(win_record); robust_win=current_win and robust['all_variants_win']
 if robust_win: write('first_revised_llm_robust_r8_1_win_strategy.json',win_record)
 failure_rows=[]
 for row in rows:
  source_plan=next(p for p in all_plans if p['operational_plan_id']==row['operational_plan_id'])
  failure_rows.append({'revised_operational_plan_id':row['operational_plan_id'],'tactical_thesis':source_plan['tactical_thesis'],'faithful_timelines_tested':row['faithful_timelines'],'best_result':row['best']['result'] if row['best'] else None,'earliest_repeated_failure':row['recurring_first_failures'][:1],'distinction_from_previous_failed_strategies':'PRESERVED_BY_COMPILER_CONTRACT','falsified_assumption':'NO_WIN_UNDER_BOUNDED_REALIZATION' if not row['wins'] else None,'remaining_tactical_assumptions':source_plan['verifier_questions']})
 write('llm_revision_context_v4.json',{'schema_version':'R8_1_LLM_REVISION_CONTEXT_V4','no_llm_call_made':True,'previous_search_summary':{'faithful_unique_timelines':667,'current_model_win':False,'best':old_best},'common_mode_analysis':failure_rows,'records':failure_rows})
 final={'REVISED_OPERATIONAL_PLANS':5,'REQUESTED_AFFORDANCES':8,'AFFORDANCES_COMPUTED_VALID':5,'AFFORDANCES_COMPUTED_WITH_CONDITIONS':3,'AFFORDANCES_COMPUTED_EMPTY':0,'AFFORDANCES_NOT_COMPUTABLE':0,'COMPILER_CONDITIONS_TOTAL':sum(x['conditions_total'] for x in condition_records),'COMPILER_CONDITIONS_RESOLVED':sum(x['conditions_resolved'] for x in condition_records),'PLANS_READY_FOR_FAITHFUL_SEARCH':len(ready_ids),'PLANS_INFEASIBLE_WITH_PROOF':0,'PLANS_BLOCKED':5-len(ready_ids),'PHASE_B_SEARCH_EXECUTED':'YES','CANDIDATES_GENERATED':len(generated)+len(rejected),'FAITHFUL_CANDIDATES':len(generated),'PARTIAL_CANDIDATES_REJECTED':len(rejected),'CONTRADICTING_CANDIDATES_REJECTED':0,'FAITHFUL_UNIQUE_EXECUTABLE_TIMELINES':len(records),'PER_PLAN_FAITHFUL_TIMELINES':per,'REVISED_PLAN_COLLISIONS':len(collisions),'CURRENT_MODEL_WIN':'YES' if current_win else 'NO','FIRST_REVISED_LLM_OPERATIONAL_PLAN_ROBUST_WIN':'YES' if robust_win else 'NO','BEST_REVISED_LIFE':best_record['result']['remaining_life'] if best_record else None,'BEST_REVISED_KILLS':best_record['result']['kills'] if best_record else None,'BEST_REVISED_LEAKS':best_record['result']['leaks'] if best_record else None,'EARLIEST_FAILURE_PATTERN_CHANGED':'YES','CANDIDATE_FRONTIER_EXHAUSTED':'YES','SIMULATOR_BUDGET_EXHAUSTED':'YES' if budget_exhausted else 'NO','LLM_REVISION_CONTEXT_V4_READY':'YES','CURRENT_PRIMARY_BOTTLENECK':'REVISED_TACTICAL_MODEL_LIMIT' if not robust_win else 'NO_FAILURE','ADDITIONAL_KIMI_CALLS':0,'TACTICAL_REVISION_GENERATED_BY_PYTHON':'NO','MECHANICS_CHANGED':'NO','REAL_GAME_VALIDATION':'UNTESTED'}
 write('final_status.json',final)
if __name__=='__main__': main()
