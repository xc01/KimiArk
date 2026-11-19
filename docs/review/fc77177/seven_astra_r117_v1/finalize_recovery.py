"""Parse and verify already completed model-directed work. Never starts battles/CLI."""
import json,hashlib,collections,subprocess,sys,copy
from pathlib import Path
from prepare import ROOT,BASE,read,write,sha
import batch_service as mechanical

def main():
 state=read(BASE/'batch_state.json');ledger=read(BASE/'candidate_ledger_v1.json');budget=read(BASE/'simulation_budget_v1.json');recovery=BASE/'recovery_attempt_02'
 assert (ledger['used_check_calls'],ledger['used_candidates'],budget['started_stage_simulations'])==(45,32,33)
 assert collections.Counter(r['status'] for r in ledger['checks'])=={'PASS':32,'FAIL':13}
 assert {r['round'] for r in state['rounds']}==set(range(1,6))
 result=read(recovery/'cli_process_result.json');assert result['status']=='COMPLETED' and result['exit_code']==0
 trace=[json.loads(line) for line in (recovery/'codex_exec.jsonl').read_text().splitlines() if line.strip()]
 assert sum(r['type']=='thread.started' for r in trace)==1
 assert sum(r['type']=='turn.started' for r in trace)==1
 assert sum(r['type']=='turn.completed' for r in trace)==1
 model_requests=[r['item'] for r in trace if r['type']=='item.completed' and r.get('item',{}).get('type')=='mcp_tool_call']
 model_searches=[r['arguments'] for r in model_requests if r.get('tool')=='search_variants']
 model_rounds=[r['arguments'] for r in model_requests if r.get('tool')=='record_round']
 assert len(model_searches)==9 and len(model_rounds)==5
 write(recovery/'actual_model_search_requests.json',model_searches);write(recovery/'actual_model_round_records.json',model_rounds)
 frozen={}
 for file,expected in read(recovery/'historical_attempt_hashes.json').items():assert sha(ROOT/file)==expected;frozen[file]=expected
 for file,expected in read(BASE/'sealed_ledger_hashes.json').items():assert sha(ROOT/file)==expected;frozen[file]=expected
 for file,expected in read(recovery/'frozen_start_manifest.json')['inputs'].items():assert sha(ROOT/file)==expected;frozen[file]=expected
 write(recovery/'immutable_input_verification.json',{'status':'PASS','sha256':frozen,'scope':'Historical failed CLI attempt, sealed R115/R116 ledgers and corrected-start frozen inputs unchanged'})
 reg=read(BASE/'parent_registry_v1.json')
 for alias,data in reg.items():
  assert sha(BASE/'parents'/alias/'payload.json')==data['payload_copy_sha256']
  for a in data['artifacts'].values():assert sha(ROOT/a['path'])==a['sha256']
 outputs=[];reconstruction=[]
 for row in state['variants']:
  request=next(r for r in model_searches if row['name'].startswith(r['name']+'_'))
  # Prefix disambiguation: exact enumerated index belongs to that model-supplied name.
  request=next(r for r in model_searches if row['name'].rsplit('_',1)[0]==r['name'])
  assert request['parent']==row['parent'] and request['round']==row['round'] and request['hypothesis']==row['hypothesis']
  assert mechanical.expand(request['changes'],row['parameters'])==row['changes']
  if row['status']!='PASS':continue
  cid=row['candidate_id'];cr=BASE/'session/candidates'/cid;record=read(cr/'candidate_record.json')
  assert record['check_status']=='PASS' and record['unique_deployed_operator_count']<=7
  payload=mechanical.build(row['parent'],row['name'],row['changes'],row['hypothesis'],row['round'])
  assert payload==read(cr/'source/llm_structured_output.json'),cid
  assert payload['revised_operational_plans'][0]==read(cr/'simulation/plan_snapshot.json')
  for path,expected in record['controlled_code_sha256'].items():assert sha(ROOT/path)==expected,path
  o=row['observed'];assert row['run']['status']=='COMPLETED'
  for key in ['enemies_killed','enemies_leaked','enemies_remaining','win','remaining_life','deployment_errors']:
   assert o['result'][key]==read(cr/'simulation/diagnostic_summary.json')['result'][key]
  parent_events=mechanical.evidence_events(row['parent']);parentleaks={e['source_id'] for e in parent_events if e['event_type']=='ENEMY_LEAK'};newleaks={e['source_id'] for e in o['leaks']}
  item={k:row[k] for k in ['name','round','parent','hypothesis','parameters','changes','candidate_id','candidate_sha256','plan_id']}
  item.update(observed=o,eliminated_leaks=sorted(parentleaks-newleaks),added_leaks=sorted(newleaks-parentleaks),action_hash=sha(cr/'simulation/action_snapshot.json'),event_hash=sha(cr/'simulation/diagnostic_events.json'))
  outputs.append(item);reconstruction.append({'candidate_id':cid,'model_search_request':request['name'],'model_changes_deep_equal':True,'payload_reconstructed_deep_equal':True,'plan_frozen_equal':True})
 write(recovery/'candidate_results_v2.json',outputs)
 write(recovery/'model_provenance_verification.json',{'status':'PASS','source':'Actual completed MCP search_variants requests in the one Astra execution trace; host mechanical expansion only','records':reconstruction})
 reservations=[read(p) for directory in [BASE/'session/candidates',BASE/'reverification'] for p in directory.glob('*/simulation.simulation_reservation.json')]
 assert len(reservations)==33 and sorted(r['reservation_index'] for r in reservations)==list(range(1,34))
 assert all(r['status']=='COMPLETED' and r['result_saved'] for r in reservations)
 independent=state['independent_runs'];assert len(independent)==1 and independent[0]['candidate_id']=='candidate-021' and all(independent[0]['hash_equal'].values())
 assert independent[0]['budget_before']==32 and independent[0]['budget_after']==33
 # Preserve actual child final answer verbatim; factual evidence index is a separate derivation.
 facts={}
 for source in ['A','B','C','candidate-021','candidate-022','candidate-013']:
  ev=mechanical.evidence_events(source);focus={'enemy_1110_uamord#21','enemy_1110_uamord#22','enemy_1107_uoffcr#23','enemy_1108_uterer#27','enemy_1108_uterer#28','enemy_1108_uterer#31','enemy_1107_uoffcr#19','char_283_midn','char_123_fang','char_4093_frston','enemy_3001_upeopl#14'}
  selected=[{'raw_index':i,**e} for i,e in enumerate(ev) if e['event_type'] in ['ENEMY_LEAK','OPERATOR_DEATH','PROTECTED_TARGET_REACHED','DEVICE_DESTROYED'] or (e['event_type'] in ['BLOCK','UNBLOCK','ENEMY_DEATH','RETREAT','DEPLOY'] and (e.get('source_id') in focus or e.get('target_id') in focus))]
  if source in reg:ref=reg[source]['artifacts']['diagnostic_events.json']['path']
  else:ref=str((BASE/'session/candidates'/source/'simulation/diagnostic_events.json').relative_to(ROOT))
  facts[source]={'event_log':ref,'events':selected}
 write(recovery/'key_event_index_v2.json',facts)
 counts={'production_check':45,'static_reject':13,'static_pass_frozen_candidates':32,'real_full_simulations':33,'first_candidate_runs':32,'independent_reverification_runs':1,'rounds':5,'historical_failed_cli_processes':1,'new_explicit_recovery_cli_processes':1,'total_actual_cli_processes':2,'successful_tactical_model_sessions':1,'model':'gpt-6.2-astra','reasoning_effort':'low','features_apps':False,'usage':result.get('usage_records',[]),'internal_cli_requests':'UNKNOWN_CLI_INTERNAL'}
 best=next(r for r in outputs if r['candidate_id']=='candidate-021');secondary=next(r for r in outputs if r['candidate_id']=='candidate-022')
 state.update(stopped=True,status='COMPLETED_FIVE_MODEL_DIRECTED_ROUNDS',closure_reason='Actual Astra session completed five rounds and one independent rerun; no seven-ID WIN. No further hypothesis/candidate/simulation within this batch.',cli_started=2)
 write(BASE/'batch_state.json',state)
 write(recovery/'final_budget_v2.json',{'check':{'max':500,'used':45,'remaining':455},'candidate':{'max':100,'used':32,'remaining':68},'simulation':{'max':100,'used':33,'remaining':67},'rounds':{'max':5,'used':5},'CLI':{'historical':1,'new_explicit_authorization':1,'used_total':2,'successful_tactical_sessions':1},'no_balance_transfer':True,'closed':True})
 write(recovery/'closeout_v2.json',{'status':'COMPLETED_FIVE_MODEL_DIRECTED_ROUNDS_NO_WIN','counts':counts,'best_overall_seven':'A/B both29/4 with both protected targets arrived and artillery killed; unchanged. No new candidate dominates either.','best_new_terminal_candidate':best,'retained_complementary_candidate':secondary,'independent_reverification':independent,'model_final_verbatim':'codex_final_message.txt','actual_model_decisions':'actual_model_round_records.json','historical_failure_not_overwritten':'../startup_blocker_v1.json','result_scope':'Fixed simulator only. M70 eight-ID complete WIN best. Seven-or-fewer full WIN UNKNOWN.','no_push':True})
 print({'status':'COMPLETE','model_decisions_verified':len(model_searches),'candidates_reconstructed':len(reconstruction),'actual_unique_completed_reservations':len(reservations),'counts':counts})
if __name__=='__main__':main()
