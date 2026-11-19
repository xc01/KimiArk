"""Archive-only verification of completed Astra decisions and production results."""
from pathlib import Path
from collections import Counter
import json,hashlib,sys,subprocess,gzip
from prepare import ROOT,BASE,read,write,sha
import batch_service as service

def archived_bytes(path):
 path=Path(path)
 if path.exists():return path.read_bytes()
 return gzip.decompress(path.with_name(path.name+".gz").read_bytes())

def subset_delta(parent_ev,observed):
 a={e['source_id'] for e in parent_ev if e['event_type']=='ENEMY_LEAK'};b={e['source_id'] for e in observed['leaks']}
 return {'eliminated':sorted(a-b),'added':sorted(b-a),'strict_subset':b<a}

def main():
 state=read(BASE/'batch_state.json');ledger=read(BASE/'candidate_ledger_v1.json');budget=read(BASE/'simulation_budget_v1.json');cli=BASE/'session/codex_cli'
 assert (ledger['used_check_calls'],ledger['used_candidates'],budget['started_stage_simulations'])==(24,18,19)
 assert Counter(r['status'] for r in ledger['checks'])=={'PASS':18,'FAIL':6}
 result=read(cli/'cli_process_result.json');assert result['status']=='COMPLETED' and result['exit_code']==0 and result['cli_starts']==1
 trace=[json.loads(line) for line in archived_bytes(cli/'codex_exec.jsonl').decode().splitlines() if line.strip()]
 assert all(sum(r['type']==t for r in trace)==1 for t in ['thread.started','turn.started','turn.completed'])
 calls=[r['item'] for r in trace if r['type']=='item.completed' and r.get('item',{}).get('type')=='mcp_tool_call']
 searches=[r['arguments'] for r in calls if r['tool']=='search_variants'];rounds=[r['arguments'] for r in calls if r['tool']=='record_round']
 assert len(searches)==8 and len(rounds)==10 and {r['round'] for r in rounds}==set(range(1,6))
 write(BASE/'actual_model_search_requests.json',searches);write(BASE/'actual_model_round_records.json',rounds)
 for path,expected in read(BASE/'sealed_ledger_hashes.json').items():assert sha(ROOT/path)==expected,path
 for path,expected in read(cli/'frozen_start_manifest.json')['inputs'].items():assert sha(ROOT/path)==expected,path
 reg=read(BASE/'parent_registry_v1.json')
 for alias,parent in reg.items():
  assert sha(BASE/'parents'/alias/'payload.json')==parent['payload_copy_sha256']
  for item in parent['artifacts'].values():assert sha(ROOT/item['path'])==item['sha256']
 rows=[r for r in state['variants'] if r['status']=='PASS'];assert len(rows)==18
 checked=[];summaries=[];hashes={};parent_events={name:service.evidence_events(name) for name in reg}
 for r in state['variants']:
  request=next(x for x in searches if r['name'].rsplit('_',1)[0]==x['name'])
  assert service.expand(request['changes'],r['parameters'])==r['changes']
  assert (request['parent'],request['hypothesis'],request['round'])==(r['parent'],r['hypothesis'],r['round'])
  if r['status']!='PASS':continue
  cid=r['candidate_id'];cr=BASE/'session/candidates'/cid
  reconstructed=service.build(r['parent'],r['name'],r['changes'],r['hypothesis'],r['round'])
  assert reconstructed==read(cr/'source/llm_structured_output.json')
  assert reconstructed['revised_operational_plans'][0]==read(cr/'simulation/plan_snapshot.json')
  record=read(cr/'candidate_record.json');assert record['check_status']=='PASS' and record['unique_deployed_operator_count']<=7
  for path,value in record['controlled_code_sha256'].items():assert sha(ROOT/path)==value,path
  hashes=record['controlled_code_sha256'];assert r['run']['status']=='COMPLETED'
  summary=read(cr/'simulation/diagnostic_summary.json')['result']
  assert r['observed']['result']=={k:v for k,v in summary.items() if k!='events'}
  checked.append({'candidate_id':cid,'request_name':request['name'],'model_supplied_parameters_deep_equal':True,'payload_reconstructed_deep_equal':True,'plan_frozen_equal':True})
  delta={name:subset_delta(ev,r['observed']) for name,ev in parent_events.items()}
  summaries.append({k:r[k] for k in ['name','round','parent','hypothesis','parameters','changes','candidate_id','candidate_sha256','plan_id']}|{'observed':r['observed'],'leak_delta_to_parents':delta,'action_hash':sha(cr/'simulation/action_snapshot.json'),'events_hash':hashlib.sha256(archived_bytes(cr/'simulation/diagnostic_events.json')).hexdigest()})
 write(BASE/'model_provenance_verification.json',{'status':'PASS','source':'One real Astra/low thread, actual completed tool calls, no host tactics','candidates':checked})
 write(BASE/'candidate_results_v1.json',{'completed':summaries,'rejected':[{'name':r['name'],'round':r['round'],'changes':r['changes'],'errors':r['check'].get('errors',[])} for r in state['variants'] if r['status']=='FAIL']})
 reservations=[read(p) for parent in [BASE/'session/candidates',BASE/'reverification'] for p in parent.glob('*/simulation.simulation_reservation.json')]
 assert len(reservations)==19 and sorted(r['reservation_index'] for r in reservations)==list(range(1,20)) and all(r['status']=='COMPLETED' and r['result_saved'] for r in reservations)
 independent=state['independent_runs'];assert len(independent)==1 and independent[0]['candidate_id']=='candidate-016' and independent[0]['budget_before']==18 and independent[0]['budget_after']==19 and all(independent[0]['hash_equal'].values())
 chosen=next(r for r in rows if r['candidate_id']=='candidate-016');bestplan=service.resolve_plan('candidate-016');baseplan=service.resolve_plan('B')
 diffs=[{'index':i,'before':a,'after':b} for i,(a,b) in enumerate(zip(baseplan['action_timeline'],bestplan['action_timeline'])) if a!=b]
 assert len(baseplan['action_timeline'])==len(bestplan['action_timeline']) and len(diffs)==1
 assert diffs[0]['before']['direction']=='RIGHT' and diffs[0]['after']['direction']=='DOWN' and all(diffs[0]['before'].get(k)==diffs[0]['after'].get(k) for k in diffs[0]['before'] if k!='direction')
 write(BASE/'best_canonical_action_diff.json',{'reference_parent':'B','candidate_id':'candidate-016','changes':diffs,'tactical_field_changes':1})
 evidence={}
 for source in ['B','D','candidate-016']:
  ev=service.evidence_events(source);focus={'enemy_1108_uterer#1','enemy_1108_uterer#5','enemy_1107_uoffcr#6','enemy_1107_uoffcr#9','enemy_1107_uoffcr#10','enemy_1107_uoffcr#12','enemy_3001_upeopl#14','enemy_1107_uoffcr#19','trap_020_roadblock#4'}
  events=[{'raw_index':i,**e} for i,e in enumerate(ev) if (e['event_type'] in ['DAMAGE','BLOCK','UNBLOCK','ENEMY_DEATH','ENEMY_LEAK','PROTECTED_TARGET_REACHED','DEVICE_DESTROYED'] and (e.get('source_id') in focus or e.get('target_id') in focus)) or e['event_type']=='OPERATOR_DEATH']
  ref=reg[source]['artifacts']['diagnostic_events.json']['path'] if source in reg else str((BASE/'session/candidates'/source/'simulation/diagnostic_events.json').relative_to(ROOT))
  evidence[source]={'event_log':ref,'raw_event_indexed':True,'selected_events':events}
 write(BASE/'key_event_index_v1.json',evidence)
 damage={}
 for source in ['B','candidate-016']:
  ev=service.evidence_events(source);damage[source]={}
  for target in ['enemy_1108_uterer#1','enemy_1107_uoffcr#6','enemy_1107_uoffcr#10','enemy_1107_uoffcr#12']:
   hits=[e for e in ev if e['event_type']=='DAMAGE' and e['source_id']=='char_123_fang' and e['target_id']==target]
   damage[source][target]={'hit_count':len(hits),'amount':sum(e['details']['amount'] for e in hits),'frames':[e['frame'] for e in hits]}
 write(BASE/'extra_damage_comparison.json',{'observations':damage,'actual_extra_kills':0,'leak_id_set_changed':False,'meaning':'A no-regression directional coverage observation, not actual closure or strict leak-set progress'})
 usage=result['usage_records'];assert all(0<=x['usage'].get('cached_input_tokens',0)<=x['usage']['input_tokens'] for x in usage)
 counts={'production_check':24,'static_reject':6,'frozen_PASS_candidates':18,'actual_full_simulations':19,'candidate_first_runs':18,'independent_reruns':1,'rounds':5,'real_tactical_CLI_processes':1,'real_tactical_model_sessions':1,'model':'gpt-6.2-astra','reasoning_effort':'low','features_apps':False,'CLI_usage':usage,'internal_model_requests':'UNKNOWN_CLI_INTERNAL'}
 write(BASE/'execution_identity_v1.json',{'head_at_start':'a155ad36a8ab6724e5a4f19912c2596d51b477bc','controlled_code_sha256':hashes,'original_frozen_parent_artifacts_verified':True,'old_sealed_ledgers_verified':True,'model_thread_id':next(r['thread_id'] for r in trace if r['type']=='thread.started'),'actual_completed_model_tool_calls':Counter(c['tool'] for c in calls),'model_final_usage_visibility':'Child final said service did not expose tokens; actual CLI turn.completed usage is archived here by host after the turn. Never replace the raw model final.'})
 no_strict=not any(r['observed']['artillery_kill'] is not None and len(r['observed']['protected_arrivals'])==2 and any(subset_delta(parent_events[p],r['observed'])['strict_subset'] for p in ['A','B']) for r in rows)
 assert no_strict
 chosen_result=next(r for r in summaries if r['candidate_id']=='candidate-016')
 state.update(stopped=True,status='COMPLETED_FIVE_ASTRA_ROUNDS_NO_WIN',closure_reason='One real Astra/low session finished five rounds and independently reran selected directional branch. No strict leak-set improvement; unused budget sealed.')
 write(BASE/'batch_state.json',state)
 write(BASE/'final_budget_v1.json',{'check':{'max':500,'used':24,'remaining':476},'candidate':{'max':100,'used':18,'remaining':82},'simulation':{'max':100,'used':19,'remaining':81},'rounds':{'max':5,'used':5},'CLI':{'max':1,'used':1},'closed':True,'no_transfer':True})
 write(BASE/'closeout_v1.json',{'batch':'R118','status':'COMPLETED_FIVE_ASTRA_ROUNDS_NO_WIN','counts':counts,'best_new_no_regression':chosen_result,'independent_verification':independent,'round_counts':{n:dict(Counter(r['status'] for r in state['variants'] if r['round']==n)) for n in range(1,6)},'strict_subset_with_artillery_and_two_arrivals_found':False,'best_complete':'M70 eight-ID fixed simulator WIN stays frozen; seven-or-fewer complete WIN UNKNOWN','raw_tactical_final':'session/codex_cli/codex_final_message.txt','host_tactical_design':False,'push':False})
 print({'status':'verified and closed','model_search_requests':len(searches),'PASS_payloads_deep_equal':len(checked),'real_completed_reservations':len(reservations),'counts':counts})
if __name__=='__main__':main()
