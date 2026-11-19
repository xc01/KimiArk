from driver import *
import subprocess,difflib
from collections import Counter

def diff(a,b):
 ca=Counter(shared.canonical(x).decode() for x in a);cb=Counter(shared.canonical(x).decode() for x in b)
 return {'removed':[json.loads(x) for x,count in (ca-cb).items() for _ in range(count)],'added':[json.loads(x) for x,count in (cb-ca).items() for _ in range(count)],'stable_time_sorted':all(x['frame']<=y['frame'] for x,y in zip(b,b[1:]))}

def main():
 state=read(BASE/'search_state.json');ledger=read(BASE/'candidate_ledger_v1.json');budget=read(BASE/'simulation_budget_v1.json')
 rows=[r for r in state['variants'] if r.get('observed')]
 assert len(rows)==58 and ledger['used_check_calls']==71 and ledger['used_candidates']==58 and budget['started_stage_simulations']==60
 assert Counter(x['status'] for x in ledger['checks'])=={'PASS':58,'FAIL':13}
 r115={}
 for name in ['candidate_ledger_v1.json','simulation_budget_v1.json','search_state.json']:
  target=OLD/name;before=hashlib.sha256(subprocess.check_output(['git','show','ae0a032:'+str(target.relative_to(ROOT))])).hexdigest();assert digest(target)==before
  r115[name]={'sha256':before,'equals_ae0a032':True}
 write(BASE/'r115_immutable_verification_v1.json',r115)
 parents={}
 for nm,cid in [('baseline','candidate-001'),('complementary','candidate-089')]:
  directory=OLD/'session/candidates'/cid/'simulation'
  parents[nm]={'plan_id':selected(getparent(nm))['operational_plan_id'],'artifacts':{n:{'path':str((directory/n).relative_to(ROOT)),'raw_sha256':digest(directory/n)} for n in ['plan_snapshot.json','action_snapshot.json','diagnostic_events.json','simulation_parameters.json']}}
  for n,item in parents[nm]['artifacts'].items():
   p=ROOT/item['path'];physical=p if p.exists() else p.with_name(p.name+'.gz');assert physical.exists();blob=subprocess.check_output(['git','show','ae0a032:'+str(physical.relative_to(ROOT))]);assert hashlib.sha256(blob).hexdigest()==hashlib.sha256(physical.read_bytes()).hexdigest()
 write(BASE/'parent_event_hashes_v1.json',parents)
 controlled=read(BASE/'session/candidates/candidate-030/candidate_record.json')['controlled_code_sha256']
 for name,value in controlled.items():assert digest(ROOT/name)==value
 reconstruction=[]
 summaries=[]
 for r in rows:
  source=BASE/'session/candidates'/r['check']['candidate_id']/'source'
  payload=build(r['name'],r['parent'],r['changes'],r['hypothesis'],r['round'])
  assert payload==read(source/'llm_structured_output.json'),r['name']
  record=read(source.parent/'candidate_record.json');assert record['controlled_code_sha256']==controlled and record['unique_deployed_operator_count']<=7
  reconstruction.append({'name':r['name'],'candidate_id':r['check']['candidate_id'],'payload_deep_equal':True,'declared_parent_plan_id':r['parent_plan_id']})
  o=r['observed'];summaries.append({k:r[k] for k in ['name','round','parent','parent_plan_id','changes','hypothesis']}|{'candidate_id':r['check']['candidate_id'],'action_key':r['action_key'],'result':o['result'],'leaks':o['leaks'],'kills':o['kills'],'protected_reached':o['protected_reached'],'artillery_dead':o['artillery_dead'],'artillery_hits':o['artillery_hits'],'deaths':o['deaths'],'devices_destroyed':o['devices_destroyed'],'events_path':o['events_path']})
 write(BASE/'reconstruction_verification_v1.json',{'status':'PASS','candidates':reconstruction,'scope':'Pure payload reconstruction only; no extra check or simulation'})
 write(BASE/'variant_results_v1.json',{'completed':summaries,'rejected':[{'name':r['name'],'round':r['round'],'changes':r['changes'],'errors':r['check']['errors']} for r in state['variants'] if r['status']=='FAIL']})
 reservations=[read(p) for prefix in [BASE/'session/candidates',BASE/'reverification'] for p in prefix.glob('*/simulation.simulation_reservation.json')]
 assert len(reservations)==60 and sorted(x['reservation_index'] for x in reservations)==list(range(1,61)) and all(x['status']=='COMPLETED' and x['result_saved'] for x in reservations)
 independent=read(BASE/'independent_reverification_v1.json');assert len(independent)==2 and all(all(x['equals_original'].values()) for x in independent)
 chosen=next(r for r in rows if r['name']=='R5_SUSTAIN_H3240');candidate=BASE/'session/candidates'/chosen['check']['candidate_id'];plan=selected(read(candidate/'source/llm_structured_output.json'))
 write(BASE/'canonical_action_diff_v1.json',{nm:diff(selected(getparent(nm))['action_timeline'],plan['action_timeline']) for nm in ['baseline','complementary']})
 ev=read(ROOT/chosen['observed']['events_path'])['events'];focus={1,2,6,7,10,11,12,13,19,21,22,23,25,27,28,29,30,31,33,34,0}
 indexed=[{'index_zero_based':i,**e} for i,e in enumerate(ev) if e['event_type'] in ['DEPLOY','RETREAT','OPERATOR_DEATH','PROTECTED_TARGET_REACHED','DEVICE_DESTROYED','ENEMY_LEAK'] or e['event_type'] in ['BLOCK','ENEMY_DEATH'] and e.get('target_id') and int(e['target_id'].split('#')[-1]) in focus]
 write(BASE/'key_event_index_v1.json',{'raw_events_path':chosen['observed']['events_path'],'uncompressed_sha256':digest(ROOT/chosen['observed']['events_path']),'selected_events':indexed,'raw_all_events_not_nested':True})
 round_record(5,read(BASE/'round_5_record.json')['expected_event_change'],'31 full variants. H3240/H3340 sustained four-holder branch kills #1/#2/#6/#7/#10/#11/#12/#13 and #19, cannon4273 and both arrivals, but ends22/11 life-8. Midnight gets no heals and dies5379 to officer23; armor21/22 consume Fang/Friston and both die6130/6172. Earlier/later medic geometry exposes cannon/support; caster moved inward loses cannon output. Guard skill phase3000 kills #23 but delays roadblock3 to4081 and loses protected3,23/10 terminal. Two independent runs reproduce H3240 full hashes.','Stop at five rounds, not budget exhaustion. Most promising unexecuted structural follow-up is a timed post-artillery two-holder/output handoff that supplies armor damage and top-guard recovery; existing 70-second returns and measured heal coverage do not yet implement it. It remains worth considering, not excluded or proven feasible.')
 state['closed']={'reason':'Five distinguishable tactical hypotheses completed, including parameter tests; two independent final executions completed. No complete WIN.','rounds_completed':5,'remaining_checks':429,'remaining_candidates':42,'remaining_simulations':40,'no_balance_transfer':True}
 write(BASE/'search_state.json',state)
 stats={n:{'simulated':sum(r['round']==n for r in rows),'static_rejected':sum(r['round']==n and r['status']=='FAIL' for r in state['variants'])} for n in range(1,6)}
 close={'batch_id':'R116','head_at_start':'ae0a032499310d06c1a0bc478f7d9f5978607f7d','status':'CLOSED_FIVE_ROUNDS','counts':{'check':71,'static_pass':58,'static_reject':13,'frozen_candidates':58,'real_full_simulations':60,'candidate_runs':58,'independent_final_runs':2,'tactical_cli':0,'model_calls':0,'usage':'NOT_APPLICABLE'},'limits':{'check':500,'candidate':100,'simulation':100,'rounds':5},'round_counts':stats,'best_terminal':'R115 two peer 29-kill/four-leak branches remain best seven-ID outcomes; neither replaced','retained_new_local_branch':{'name':chosen['name'],'candidate_id':chosen['check']['candidate_id'],'plan_id':plan['operational_plan_id'],'plan_hash':digest(candidate/'simulation/plan_snapshot.json'),'actions_hash':digest(candidate/'simulation/action_snapshot.json'),'events_hash':digest(candidate/'simulation/diagnostic_events.json'),'observed':chosen['observed']},'relative_to_peers':{'baseline_eliminated':[2,7,11,13],'complementary_eliminated':[1,6,10,12],'added_to_either':[21,22,23,25,27,28,29,30,31,33,34],'role_union':'All eight early enemies, #19, cannon and both protected arrivals observed in one complete seven-ID run, independently reproduced; late armor/output regressed','historical_novelty_boundary':'This is relative to the two peer starting branches, not a claim that all early joint duties are first ever in project history'},'model_authority':{'latest_user_optional_cli':'At most one 6.2 Astra/low, not needed','actual_cli':0,'actual_model':None,'config_model_label':'Copied preference gpt-6.2-sol/medium is unused metadata; never model identity proof','features_apps':False},'r115_unchanged':True,'simulation_mechanisms_changed':False,'controlled_code_sha256':controlled,'next_question':'Can a post-cannon output/medical handoff kill armor21/22 while keeping top guard alive, without losing any of eight early kills or both arrivals? New batch required after five-round stop; not executed here.','worth_continuing':'Yes, scoped structural allocation remains unexcluded. Current five rounds neither found WIN nor prove seven-ID infeasibility.','strongest_unexecuted_alternative':'Post-cannon paired caster/healer redeployment and live guard replacement. Existing tests show70-second medical gap causes earlier Fang death4668, and caster shift5,6 dies2561; a coordinated new geometry/role solution is required, not another isolated skill-frame sweep.'}
 write(BASE/'closeout_v1.json',close)
 print({'status':'closed after5 rounds','checks':71,'candidates':58,'simulations':60,'R115_unchanged':True,'rounds':stats})
if __name__=='__main__':main()
