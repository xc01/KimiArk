"""R121 mechanical transport: only Astra supplies tactics; existing production gate executes."""
from __future__ import annotations
import sys,json,hashlib,copy,itertools,subprocess,shutil,fcntl,time
from pathlib import Path
from contextlib import redirect_stdout
from prepare import ROOT,BASE,read,write,sha
sys.path.insert(0,str(ROOT/'scripts'))
import kimiark_tactical_stdio_service_v1 as production
import tactical_evaluation_gate_v1 as gate
PREFIX='R121_'
FIXED={'char_124_kroos','char_283_midn','char_210_stward','char_120_hibisc','char_192_falco'}
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def action_key(payload):
 p=payload['revised_operational_plans'][0] if 'revised_operational_plans' in payload else payload
 return hashlib.sha256(canon({'selected':sorted(p['selected_low_star_operator_ids']),'actions':[{k:a[k] for k in ['action_type','operator_id','frame','tile','direction'] if k in a} for a in p['action_timeline']]}).encode()).hexdigest()
def getparent(name):
 reg=read(BASE/'parent_registry_v1.json')
 for alias,item in reg.items():
  if name in [alias,item['plan_id']]:return read(BASE/'parents'/alias/'payload.json')
 state=read(BASE/'batch_state.json')
 for row in state['variants']:
  if name in [row.get('name'),row.get('candidate_id'),row.get('plan_id')] and row.get('candidate_id'):
   return read(BASE/'session/candidates'/row['candidate_id']/'source/llm_structured_output.json')
 raise RuntimeError('Unknown actual parent: '+str(name))
def resolve_plan(name):return getparent(name)['revised_operational_plans'][0]
def evidence_events(name):
 reg=read(BASE/'parent_registry_v1.json')
 for alias,item in reg.items():
  if name in [alias,item['plan_id']]:return read(ROOT/item['artifacts']['diagnostic_events.json']['path'])['events']
 for row in read(BASE/'batch_state.json')['variants']:
  if name in [row.get('name'),row.get('candidate_id'),row.get('plan_id')] and row.get('candidate_id'):
   return read(BASE/'session/candidates'/row['candidate_id']/'simulation/diagnostic_events.json')['events']
 raise RuntimeError('No complete event source for '+str(name))
def inspect_evidence(cfg,a):
 kind=a.get('kind','events');source=a.get('source','A')
 if kind=='priority':return read(BASE/'batch_constraints.json')
 if kind=='actions':
  p=resolve_plan(source);return {'plan_id':p['operational_plan_id'],'selected':p['selected_low_star_operator_ids'],'actions':p['action_timeline'],'validation_card':p.get('validation_card')}
 if kind=='plan':return getparent(source)
 if kind=='outcome':
  ev=evidence_events(source)
  return {'leaks':[e for e in ev if e['event_type']=='ENEMY_LEAK'],'kills':[e for e in ev if e['event_type']=='ENEMY_DEATH'],'deaths':[e for e in ev if e['event_type']=='OPERATOR_DEATH'],'arrivals':[e for e in ev if e['event_type']=='PROTECTED_TARGET_REACHED'],'devices':[e for e in ev if e['event_type']=='DEVICE_DESTROYED']}
 if kind=='facts':
  facts=read(BASE/'input_bundle/template_context.json');keys=a.get('keys') or ['stage_active_facts','stage_options','source_routes','model_spawn_timeline']
  return {k:facts.get(k) for k in keys}
 if kind=='catalog':
  cat=read(BASE/'input_bundle/template_context.json')['normal_low_star_catalog'];ids=a.get('ids',[])
  return [o for o in cat if not ids or o['operator_id'] in ids]
 if kind=='diff':
  x=resolve_plan(source)['action_timeline'];y=resolve_plan(a.get('other','C'))['action_timeline'];cx={canon(z):z for z in x};cy={canon(z):z for z in y}
  return {'source':source,'other':a.get('other','C'),'only_source':[cx[k] for k in cx.keys()-cy.keys()],'only_other':[cy[k] for k in cy.keys()-cx.keys()]}
 if kind=='code':
  p=(ROOT/a['path']).resolve();p.relative_to(ROOT)
  if not p.is_file() or p.suffix not in ['.py','.json','.md']:raise RuntimeError('Read-only code path invalid')
  lines=p.read_text().splitlines();start=max(0,a.get('line',1)-1);n=min(a.get('limit',100),200)
  return {'path':str(p.relative_to(ROOT)),'first_line':start+1,'lines':lines[start:start+n],'sha256':sha(p)}
 ev=evidence_events(source);types=a.get('event_types',[]);ids=a.get('ids',[]);start=a.get('earliest_frame',0);end=a.get('latest_frame',10**9)
 matches=[(i,e) for i,e in enumerate(ev) if start<=e['frame']<=end and (not types or e['event_type'] in types) and (not ids or any(v in [e.get('source_id'),e.get('target_id')] for v in ids))]
 off=a.get('offset',0);limit=min(a.get('limit',100),200);page=matches[off:off+limit]
 if a.get('aggregate'):
  totals={};times={}
  for i,e in matches:
   k=e.get('source_id','')+' -> '+str(e.get('target_id'))+' '+e['event_type'];totals[k]=totals.get(k,0)+e.get('details',{}).get('amount',0);times.setdefault(k,[]).append(e['frame'])
  return {'source':source,'matched':len(matches),'groups':{k:{'sum':v,'count':len(times[k]),'first':min(times[k]),'last':max(times[k])} for k,v in totals.items()},'full_log_complete':True}
 return {'source':source,'total_matches':len(matches),'offset':off,'returned':len(page),'next_offset':off+len(page) if off+len(page)<len(matches) else None,'events':[{'raw_index':i,**e} for i,e in page],'full_log_complete':True}
def record_round(cfg,a):
 n=a['round']
 if not isinstance(n,int) or not 1<=n<=5:raise RuntimeError('At most five rounds')
 state=read(BASE/'batch_state.json')
 if state.get('stopped'):raise RuntimeError('Batch stopped')
 row={'round':n,'expected':a.get('expected'),'observed':a.get('observed'),'next_reason':a.get('next_reason'),'decision':a.get('decision'),'source':'Actual Astra tool request, retained verbatim'}
 state['rounds'].append(row);write(BASE/'batch_state.json',state)
 return {'status':'RECORDED','round':n,'unique_rounds':sorted({r['round'] for r in state['rounds']}),'remaining_rounds':5-len({r['round'] for r in state['rounds']})}
def build(parent,name,changes,hypothesis,n,actions=None):
 payload=copy.deepcopy(getparent(parent));p=payload['revised_operational_plans'][0];parentid=p['operational_plan_id'];new=PREFIX+name
 p.update(operational_plan_id=new,parent_plan_id=parentid,parent_hypothesis_id=new)
 payload['revision_hypothesis'].update(hypothesis_id=new,operational_plan_id=new,parent_plan_id=parentid,tactical_hypothesis=hypothesis,changed_responsibilities=[hypothesis])
 payload['revised_strategic_hypotheses'][0]['hypothesis_id']=new
 p['validation_card']={'generator':'ASTRA_AUTHORED_SEARCH_RANGE_MECHANICALLY_ENUMERATED','round':n,'parent_id':parentid,'hypothesis':hypothesis,'model_supplied_changes':changes,'original_model':'gpt-6.2-astra','reasoning_effort':'low','regression_observe':['all leaked IDs','artillery actual kill','both protected arrivals','#19','all operator deaths/action errors/active enemies']}
 if actions is not None:p['action_timeline']=copy.deepcopy(actions)
 for c in changes:
  acts=p['action_timeline'];kind=c['type']
  if kind in ['set','remove']:
   matches=[a for a in acts if a['operator_id']==c['operator'] and a['action_type']==c['action'] and a['frame']==c['frame']]
   if len(matches)!=1:raise RuntimeError('Ambiguous exact action match: '+canon(c))
   if kind=='set':matches[0].update(c['fields'])
   else:acts.remove(matches[0])
  elif kind=='add':acts.append(copy.deepcopy(c['value']))
  elif kind=='replace':
   for a in acts:
    if a['operator_id']==c['operator']:a['operator_id']=c['replacement']
  else:raise RuntimeError('Unknown change type')
 p['action_timeline'].sort(key=lambda a:a['frame'])
 p['deployment_positions_and_directions']=[copy.deepcopy(a) for a in p['action_timeline'] if a['action_type']=='DEPLOY']
 p['selected_low_star_operator_ids']=sorted(FIXED)
 if not {a['operator_id'] for a in p['action_timeline']}<=FIXED:raise RuntimeError('Fixed roster violation: only Kroos/Midnight/Steward/Hibiscus/Plume')
 return payload

def observe(candidate):
 directory=BASE/'session/candidates'/candidate/'simulation';summary=read(directory/'diagnostic_summary.json');ev=read(directory/'diagnostic_events.json')['events'];result={k:v for k,v in summary['result'].items() if k!='events'}
 kills={e['target_id']:e['frame'] for e in ev if e['event_type']=='ENEMY_DEATH' and e['details'].get('kill_counted')};leaks=[e for e in ev if e['event_type']=='ENEMY_LEAK'];arr=[e for e in ev if e['event_type']=='PROTECTED_TARGET_REACHED'];deaths=[e for e in ev if e['event_type']=='OPERATOR_DEATH']
 return {'result':result,'leaks':leaks,'kills':kills,'protected_arrivals':arr,'operator_deaths':deaths,'device_destroyed':[e for e in ev if e['event_type']=='DEVICE_DESTROYED'],'artillery_kill':kills.get('enemy_1112_emppnt#0'),'enemy19_kill':kills.get('enemy_1107_uoffcr#19'),'complete_win':bool(result['win'] and not leaks and len(arr)==2 and result['enemies_remaining']==0 and not result['deployment_errors']),'event_log':str((directory/'diagnostic_events.json').relative_to(ROOT))}
def expand(x,params):
 if isinstance(x,str) and x.startswith('$') and x[1:] in params:return params[x[1:]]
 if isinstance(x,list):return [expand(v,params) for v in x]
 if isinstance(x,dict):return {k:expand(v,params) for k,v in x.items()}
 return x

def search_variants(cfg,a):
 state=read(BASE/'batch_state.json');n=a['round']
 if state.get('stopped') or (BASE/'WIN_PENDING_VERIFICATION.json').exists():raise RuntimeError('Exploration stopped; independently verify existing WIN')
 if n not in {r['round'] for r in state['rounds']}:raise RuntimeError('Record Astra hypothesis for this round first')
 if not 1<=n<=5:raise RuntimeError('Five-round limit')
 params=a.get('parameters',{});names=list(params);choices=list(itertools.product(*(params[k] for k in names))) if names else [()]
 if len(choices)>30:raise RuntimeError('Batch max30 parameter combinations per call; narrower feedback batches recommended')
 out=[]
 for j,values in enumerate(choices):
  state=read(BASE/'batch_state.json');ledger=read(cfg.candidate_ledger_path);budget=read(cfg.budget_path)
  if ledger['used_check_calls']>=498 or ledger['used_candidates']>=98 or budget['started_stage_simulations']>=98:return {'status':'RESERVED_FINAL_BUDGET','results':out,'status_detail':status(cfg,{})}
  name=a['name']+'_'+str(j);mapping=dict(zip(names,values));changes=expand(a.get('changes',[]),mapping)
  row={'name':name,'round':n,'parent':a['parent'],'hypothesis':a['hypothesis'],'parameters':mapping,'changes':changes,'actions':expand(a.get('actions'),mapping),'source':'Astra tool arguments expanded mechanically'}
  payload=build(a['parent'],name,changes,a['hypothesis'],n,actions=row['actions']);ak=action_key(payload)
  old=next((r for r in state['variants'] if r.get('action_key')==ak),None)
  old_archive=read(BASE/'old_action_index.json').get(ak)
  if old or old_archive:out.append({'name':name,'status':'DEDUP','original':old or old_archive});continue
  row['action_key']=ak
  parent=getparent(a['parent']);ctx=read(BASE/'input_bundle/template_context.json');ctx['previous_plan_id']=parent['revised_operational_plans'][0]['operational_plan_id'];ctx['previous_plan_to_revise']=parent['revised_operational_plans'][0]
  write(cfg.facts_source_dir/'llm_evidence_context.json',ctx)
  check=checked_plan(cfg,{'plan':payload});row['check']=check;row['status']=check['status']
  if check['status']=='PASS':row.update(candidate_id=check['candidate_id'],candidate_sha256=check['candidate_sha256'],plan_id=payload['revised_operational_plans'][0]['operational_plan_id'])
  state['variants'].append(row);write(BASE/'batch_state.json',state)
  if check['status']=='PASS':
   run=production.run_simulation(cfg,{'candidate_id':row['candidate_id'],'candidate_sha256':row['candidate_sha256']});row['run']=run
   if run['status']!='COMPLETED':
    state['stopped']=True;state['blocker']=run;write(BASE/'batch_state.json',state);raise RuntimeError('Simulation not complete; no automatic retry '+canon(run))
   row['observed']=observe(row['candidate_id']);state['variants'][-1]=row;write(BASE/'batch_state.json',state)
  elif check['status']!='FAIL':return {'status':'BUDGET_OR_SERVICE_STOP','results':out,'last':check}
  compact={k:row[k] for k in ['name','parameters','status','candidate_id','candidate_sha256','observed'] if k in row}
  if row['status']=='FAIL':compact['errors']=check.get('errors')
  out.append(compact)
  if row.get('observed',{}).get('complete_win'):
   write(BASE/'WIN_PENDING_VERIFICATION.json',{'candidate_id':row['candidate_id'],'name':name});return {'status':'WIN_MUST_VERIFY','results':out}
 return {'status':'COMPLETED_PARAMETER_GROUP','results':out,'budget':status(cfg,{})['budget'],'check_call_ledger':status(cfg,{})['check_call_ledger']}

def independent_verify(cfg,a):
 candidate=a['candidate_id'];state=read(BASE/'batch_state.json')
 row=next(r for r in state['variants'] if r.get('candidate_id')==candidate)
 record=read(BASE/'session/candidates'/candidate/'candidate_record.json');assert record['check_status']=='PASS'
 for code,expected in record['controlled_code_sha256'].items():assert sha(ROOT/code)==expected
 runid='independent-'+str(len(state['independent_runs'])+1);rr=BASE/'reverification'/runid
 if rr.exists():raise RuntimeError('Independent run path already exists; no retry')
 source=rr/'source';source.mkdir(parents=True)
 for name,expected in record['frozen_inputs_sha256'].items():
  p=BASE/'session/candidates'/candidate/'source'/name
  if sha(p)==expected:shutil.copyfile(p,source/name)
  elif name=='execution_input_gate.json':
   write(source/name,row['check']['execution_input_gate']);assert sha(source/name)==expected
  else:raise RuntimeError('Frozen input mismatch')
 output=rr/'simulation';before=read(cfg.budget_path)['started_stage_simulations'];g=gate.prepare_evaluation(source_dir=source,diagnostic_output_dir=output,budget_path=cfg.budget_path,stage_id=cfg.stage_id,expected_plan_id=record['plan_id']);assert g['status']=='AUTHORIZED'
 cmd=[sys.executable,str(ROOT/'scripts/run_gpt_tactical_stage_session_v1.py'),'simulate','--stage-id',cfg.stage_id,'--facts-dir',str(source),'--output-dir',str(source),'--diagnostic-output-dir',str(output),'--plan-id',record['plan_id'],'--plan-label','R121','--plan-id-prefix','R121_','--max-unique-deployed-operators','5','--authorization-config',str(cfg.authorization_config_path),'--simulation-budget-path',str(cfg.budget_path)]
 write(rr/'provenance.json',{'candidate_id':candidate,'command':cmd,'gate':g,'frozen_inputs_sha256':record['frozen_inputs_sha256'],'budget_before':before,'source':'Astra explicitly requested independent rerun'})
 p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);(rr/'stdout.txt').write_text(p.stdout);(rr/'stderr.txt').write_text(p.stderr)
 if p.returncode:state['stopped']=True;state['blocker']={'runid':runid,'returncode':p.returncode};write(BASE/'batch_state.json',state);raise RuntimeError('Independent production run failed; no retry')
 after=read(cfg.budget_path)['started_stage_simulations'];assert after==before+1
 original=BASE/'session/candidates'/candidate/'simulation';equal={name:sha(output/name)==sha(original/name) for name in ['plan_snapshot.json','action_snapshot.json','diagnostic_events.json']}
 summary=read(output/'diagnostic_summary.json');result={k:v for k,v in summary['result'].items() if k!='events'}
 item={'run_id':runid,'candidate_id':candidate,'hash_equal':equal,'result':result,'budget_before':before,'budget_after':after,'path':str(output.relative_to(ROOT))};state['independent_runs'].append(item)
 if all(equal.values()) and row['observed']['complete_win']:state['stopped']=True;state['verified_win']=candidate
 write(BASE/'batch_state.json',state);write(rr/'verification.json',item);return item

def checked_plan(cfg,a):
 p=a['plan']['revised_operational_plans'][0]
 ids=set(p['selected_low_star_operator_ids'])|{x['operator_id'] for x in p['action_timeline'] if x['action_type']=='DEPLOY'}
 if ids!=FIXED:raise RuntimeError('Fixed five-person roster gate rejected')
 return production.check_plan(cfg,a)

def status(cfg,a):
 s=production.session_status(cfg);state=read(BASE/'batch_state.json');s['rounds_recorded']=state['rounds'];s['parent_choices']=read(BASE/'parent_registry_v1.json');s['new_plan_prefix']='R121_';s['fixed_roster']=sorted(FIXED);s['reserved_for_independent_verification']=2;s['batch_stopped']=state.get('stopped');s['independent_runs']=state['independent_runs'];return s

EXTRA=[
 {'name':'inspect_evidence','description':'Read archived raw events, complete parent plan/outcome, legal catalog, facts, action diff or code. No simulation, no inference. ids exact source/target match; raw_index preserved; paginate next_offset.','inputSchema':{'type':'object','properties':{'kind':{'type':'string','enum':['events','plan','actions','outcome','facts','catalog','diff','code','priority']},'source':{'type':'string'},'other':{'type':'string'},'ids':{'type':'array','items':{'type':'string'}},'event_types':{'type':'array','items':{'type':'string'}},'earliest_frame':{'type':'integer'},'latest_frame':{'type':'integer'},'offset':{'type':'integer'},'limit':{'type':'integer'},'aggregate':{'type':'boolean'},'keys':{'type':'array','items':{'type':'string'}},'path':{'type':'string'},'line':{'type':'integer'}},'additionalProperties':False}},
 {'name':'record_round','description':'Save actual Astra decision/visible hypothesis and audit; max5 distinct rounds. expected/observed/next_reason/decision are free text or structured evidence. Update same round after feedback.','inputSchema':{'type':'object','required':['round'],'properties':{'round':{'type':'integer','minimum':1,'maximum':5},'expected':{},'observed':{},'next_reason':{},'decision':{}},'additionalProperties':False}},
 {'name':'search_variants','description':'Mechanically execute Astra-specified change combinations through existing production check/freeze/run. No tactical design here. parent=T(empty protocol template, no battle evidence), A/B/C reference or current candidate. Optional actions is a complete Astra-authored timeline, then changes patches it. Fixed roster exactly Kroos/Midnight/Steward/Hibiscus/Plume. Set change exact type/operator/action/frame/fields; remove exact type/operator/action/frame; add value full action; replace operator/replacement. A value string $PARAM is substituted from parameter grid lists, Cartesian product. All fields/frames are model-chosen. Stable time-sort only, no silent SP fixes. Up to30 combinations per tool call, recommend small feedback groups. Static rejection counts check only. Two simulations reserved for independent reruns. Returns full role/leak feedback.','inputSchema':{'type':'object','required':['round','name','parent','hypothesis'],'properties':{'round':{'type':'integer','minimum':1,'maximum':5},'name':{'type':'string','pattern':'^[A-Za-z0-9_]+$'},'parent':{'type':'string'},'hypothesis':{'type':'string'},'changes':{'type':'array','items':{'type':'object'}},'actions':{'type':'array','items':{'type':'object'}},'parameters':{'type':'object','additionalProperties':{'type':'array'}}},'additionalProperties':False}},
 {'name':'independent_verify','description':'Re-execute one PASS completed frozen candidate with independent output/run ID, same input hashes, existing production gate and current simulation budget. Not idempotent run/cache; no new candidate.','inputSchema':{'type':'object','required':['candidate_id'],'properties':{'candidate_id':{'type':'string'}},'additionalProperties':False}}
]
HANDLERS={'inspect_evidence':inspect_evidence,'record_round':record_round,'search_variants':search_variants,'independent_verify':independent_verify,'get_session_status':status,'check_plan':checked_plan}
def main():
 cfg=production.load_session_config(Path(sys.argv[1]));log=BASE/'tool_transport.jsonl'
 for line in sys.stdin:
  if not line.strip():continue
  msg=json.loads(line);requestid=msg.get('id');method=msg.get('method')
  if method=='tools/list':response={'jsonrpc':'2.0','id':requestid,'result':{'tools':production.TOOLS+EXTRA}}
  elif method=='tools/call' and msg['params']['name'] in HANDLERS:
   name=msg['params']['name'];args=msg['params'].get('arguments',{});start=time.time()
   with log.open('a') as f:f.write(canon({'phase':'STARTED','time':start,'id':requestid,'tool':name,'arguments':args})+'\n')
   try:
    with redirect_stdout(sys.stderr):value=HANDLERS[name](cfg,args)
    response={'jsonrpc':'2.0','id':requestid,'result':production.tool_result(value)}
   except Exception as exc:response={'jsonrpc':'2.0','id':requestid,'result':production.tool_result({'error':type(exc).__name__,'message':str(exc),'automatic_retry':False})};response['result']['isError']=True
   with log.open('a') as f:f.write(canon({'phase':'COMPLETED','time':time.time(),'id':requestid,'tool':name,'response':response})+'\n')
  else:response=production.handle_message(cfg,msg)
  if response is not None:print(json.dumps(response,ensure_ascii=False,separators=(',',':')),flush=True)
if __name__=='__main__':main()
