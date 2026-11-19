from __future__ import annotations
import copy,sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=Path(__file__).resolve().parent
OLD=BASE.parent/'seven_group_search_v1'
sys.path.insert(0,str(OLD))
import search_batch as shared
shared.BASE=BASE;shared.PREFIX='R116_'
read,write,digest,key,summarize=shared.read,shared.write,shared.digest,shared.action_key,shared.summarize
FANG='char_123_fang';MEL='char_208_melan';MID='char_283_midn';SPOT='char_284_spot';ANSEL='char_212_ansel';HIBI='char_120_hibisc';STEW='char_210_stward';FRIS='char_4093_frston'
def set_(op,kind,old_frame,**fields):return dict(type='set',operator=op,action=kind,frame=old_frame,fields=fields)
def add(op,kind,frame,**fields):return dict(type='add',value=dict(action_type=kind,operator_id=op,frame=frame,**fields))
def rm(op,kind,frame):return dict(type='remove',operator=op,action=kind,frame=frame)
def replace(op,new):return dict(type='replace',operator=op,replacement=new)
def selected(p):return p['revised_operational_plans'][0]
def getparent(name):
 if name in ['baseline','complementary']:return read(BASE/'parents'/f'{name}_payload.json')
 r=next(x for x in read(BASE/'search_state.json')['variants'] if x['name']==name)
 return read(BASE/'session/candidates'/r['check']['candidate_id']/'source/llm_structured_output.json')
def build(name,parent,changes,hypothesis,round_):
 payload=getparent(parent);p=selected(payload);parentid=p['operational_plan_id'];pid='R116_'+name
 p.update(operational_plan_id=pid,parent_plan_id=parentid,parent_hypothesis_id=pid)
 payload['revision_hypothesis'].update(hypothesis_id=pid,operational_plan_id=pid,parent_plan_id=parentid,tactical_hypothesis=hypothesis,changed_responsibilities=[hypothesis])
 payload['revised_strategic_hypotheses'][0]['hypothesis_id']=pid
 p['validation_card']={'generator':'deterministic_parameter_search','round':round_,'parent_id':parentid,'parent_payload_sha256':hashlib.sha256(shared.canonical(getparent(parent))).hexdigest(),'hypothesis':hypothesis,'changes':changes,'observe':['all leaks and actual kills','both protected arrivals','roadblock4 clearance','artillery actual death','all deaths and action errors'],'unknown':['continuous positions','exact HP if not recorded']}
 for c in changes:
  a=p['action_timeline'];kind=c['type']
  if kind in ['set','remove']:
   matches=[x for x in a if x['operator_id']==c['operator'] and x['action_type']==c['action'] and x['frame']==c['frame']]
   if len(matches)!=1:raise RuntimeError('Ambiguous action '+str(c))
   if kind=='set':matches[0].update(c['fields'])
   else:a.remove(matches[0])
  elif kind=='add':a.append(copy.deepcopy(c['value']))
  elif kind=='replace':
   for x in a:
    if x['operator_id']==c['operator']:x['operator_id']=c['replacement']
  else:raise RuntimeError(kind)
 p['action_timeline'].sort(key=lambda a:a['frame'])
 p['deployment_positions_and_directions']=[copy.deepcopy(a) for a in p['action_timeline'] if a['action_type']=='DEPLOY']
 p['selected_low_star_operator_ids']=sorted({a['operator_id'] for a in p['deployment_positions_and_directions']})
 if len(p['selected_low_star_operator_ids'])>7:raise RuntimeError('K>7')
 return payload

def variant(name,parent,changes,hypothesis,round_):
 if not isinstance(round_,int) or not 1 <= round_ <= 5:raise RuntimeError('R116 permits at most five tactical hypothesis rounds')
 state=read(BASE/'search_state.json')
 if state.get('closed'):raise RuntimeError('Batch closed')
 if any(r['name']==name for r in state['variants']):return next(r for r in state['variants'] if r['name']==name)
 payload=build(name,parent,changes,hypothesis,round_);ak=key(selected(payload))
 old=read(BASE/'old_action_index.json');dup=next((r for r in state['variants'] if r['action_key']==ak),None)
 row=dict(name=name,parent=parent,parent_plan_id=selected(getparent(parent))['operational_plan_id'],round=round_,changes=changes,hypothesis=hypothesis,action_key=ak)
 if dup or ak in old:
  row.update(status='DEDUP_SKIPPED',previous=dup['name'] if dup else old[ak]);state['variants'].append(row);write(BASE/'search_state.json',state);print(json.dumps({'name':name,'status':'DEDUP_SKIPPED'}),flush=True);return row
 ledger=read(BASE/'candidate_ledger_v1.json');budget=read(BASE/'simulation_budget_v1.json')
 if ledger['used_candidates']>=98 or budget['started_stage_simulations']>=98 or ledger['used_check_calls']>=498:raise RuntimeError('Exploration limit, two final runs reserved')
 parentpayload=getparent(parent);context=read(BASE/'input_bundle/baseline_context.json');context['previous_plan_id']=selected(parentpayload)['operational_plan_id'];context['previous_plan_to_revise']=selected(parentpayload)
 write(BASE/'input_bundle/llm_evidence_context.json',context)
 check=shared.tool('check_plan',{'plan':payload},name+'_check');row.update(status=check['status'],check=check)
 state['round']=max(state['round'],round_);state['variants'].append(row);write(BASE/'search_state.json',state)
 if check['status']=='PASS':
  run=shared.tool('run_simulation',{'candidate_id':check['candidate_id'],'candidate_sha256':check['candidate_sha256']},name+'_run');row['simulation_status']=run['status']
  if run['status']!='COMPLETED':raise RuntimeError('Simulation incomplete; no retry: '+str(run))
  output=BASE/'session/candidates'/check['candidate_id']/'simulation';o=summarize(output)
  ev=read(output/'diagnostic_events.json')['events'];o['deaths']=[e for e in ev if e['event_type']=='OPERATOR_DEATH'];o['devices_destroyed']=[e for e in ev if e['event_type']=='DEVICE_DESTROYED']
  o['artillery_hits']=sum(e['event_type']=='DAMAGE' and e['target_id']=='enemy_1112_emppnt#0' for e in ev)
  row['observed']=o;state['variants'][-1]=row;write(BASE/'search_state.json',state)
 if check['status'] not in ['PASS','FAIL']:raise RuntimeError('Service refusal '+str(check))
 o=row.get('observed',{})
 print(json.dumps({'name':name,'status':row['status'],'errors':check.get('errors',[])[:2],'leaks':[int(e['id'].split('#')[-1]) for e in o.get('leaks',[])],'kills':o.get('result',{}).get('enemies_killed'),'arrivals':list(o.get('protected_reached',{})),'artillery':o.get('artillery_dead'),'simulations':read(BASE/'simulation_budget_v1.json')['started_stage_simulations']},ensure_ascii=False),flush=True)
 if o.get('complete_win'):write(BASE/'WIN_PENDING_VERIFICATION.json',{'name':name,'candidate_id':check['candidate_id']});raise SystemExit('WIN: stop exploration and independently verify')
 return row

def round_record(number,expected,actual,why):write(BASE/f'round_{number}_record.json',{'expected_event_change':expected,'observed_change':actual,'why_next_round':why})
