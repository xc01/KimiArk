"""Read-only battle audit plus lossless archival; never starts a model or simulation."""
from __future__ import annotations
import difflib
import gzip
import hashlib
import json
import subprocess
from collections import Counter,defaultdict
from pathlib import Path
from search_batch import *


def events(path):return read(path)['events']
def suffix(enemy):return int(enemy.rsplit('#',1)[1])
def event_index(path,chosen):
    ev=events(path)
    return {'path':str(path.relative_to(ROOT)), 'uncompressed_sha256':digest(path),'events_zero_based':[{'index':i,**e} for i,e in enumerate(ev) if ((e['event_type'] in ['SPAWN','BLOCK','ENEMY_DEATH','ENEMY_LEAK'] and (e.get('source_id') in chosen or e.get('target_id') in chosen)) or e['event_type'] in ['PROTECTED_TARGET_REACHED','DEVICE_DESTROYED','OPERATOR_DEATH'] or (e['event_type'] in ['DEPLOY','RETREAT'] and e['source_id'] in ['char_123_fang','char_208_melan']))]}

def contacts(ev,enemy):
    dealt=[e for e in ev if e['event_type']=='DAMAGE' and e['target_id']==enemy]
    blocks=[e for e in ev if e['event_type']=='BLOCK' and e['target_id']==enemy]
    deaths=[e for e in ev if e['event_type']=='ENEMY_DEATH' and e['target_id']==enemy]
    spawn=[e for e in ev if e['event_type']=='SPAWN' and e['source_id']==enemy]
    return {'spawn':spawn[:1],'first_damage':dealt[:1],'first_block':blocks[:1],'death':deaths,'damage_by_source':dict(sum_damage(dealt)), 'continuous_positions':'UNKNOWN','exact_HP_history':'UNKNOWN'}

def sum_damage(ev):
    totals=defaultdict(float)
    for e in ev:totals[e['source_id']]+=e['details']['amount']
    return totals

def action_diff(a,b):
    assert len(a)==len(b)
    return [{'stable_action_index':i,'before':x,'after':y,'changed_fields':{key:{'before':x.get(key),'after':y.get(key)} for key in sorted(x.keys()|y.keys()) if x.get(key)!=y.get(key)}} for i,(x,y) in enumerate(zip(a,b)) if x!=y]


def main():
    state=read(BASE/'search_state.json');ledger=read(BASE/'candidate_ledger_v1.json');budget=read(BASE/'simulation_budget_v1.json')
    rows=[r for r in state['variants'] if r.get('observed')]
    best=next(r for r in rows if r['name']=='FRONTIER_BOUNDARY2047')
    best_root=BASE/'session/candidates'/best['check']['candidate_id']
    initial=next(r for r in rows if r['name']=='BASELINE')
    assert len(rows)==ledger['used_candidates']==97
    assert budget['started_stage_simulations']==99
    assert ledger['used_check_calls']==133
    assert len(ledger['checks'])==133
    assert Counter(x['status'] for x in ledger['checks'])=={'PASS':97,'FAIL':36}
    rebuilt=[]
    for row in rows:
        reconstructed=build(row['name'],row['changes'],row['hypothesis'])
        src=BASE/'session/candidates'/row['check']['candidate_id']/'source'
        assert read(src/'llm_structured_output.json')==reconstructed,row['name']
        record=read(src.parent/'candidate_record.json')
        assert record['unique_deployed_operator_count']<=7 and record['check_status']=='PASS'
        rebuilt.append({'name':row['name'],'candidate_id':row['check']['candidate_id'],'payload_deep_equal':True,'action_key':action_key(selected(reconstructed))})
    write(BASE/'reconstruction_verification_v1.json',{'status':'PASS','source':'Recorded changes + fixed base payload; pure reconstruction, no production check or battle','candidates':rebuilt})
    parent_manifest=read(BASE/'input_bundle/parent_identity_manifest.json')
    for path,expected in parent_manifest['hashes'].items():assert digest(ROOT/path)==expected,path
    assert digest(BASE/'session/candidates'/initial['check']['candidate_id']/'simulation/diagnostic_events.json')==digest(PARENT/'simulation/diagnostic_events.json')
    reservations=[read(p) for parent in [BASE/'session/candidates',BASE/'reverification'] for p in parent.glob('*/simulation.simulation_reservation.json')]
    assert len(reservations)==99 and sorted(r['reservation_index'] for r in reservations)==list(range(1,100))
    assert all(r['status']=='COMPLETED' and r['result_saved'] for r in reservations)
    controlled=read(best_root/'candidate_record.json')['controlled_code_sha256']
    for row in rows:
        rec=read(BASE/'session/candidates'/row['check']['candidate_id']/'candidate_record.json')
        assert rec['controlled_code_sha256']==controlled
    for path,expected in controlled.items():assert digest(ROOT/path)==expected,path
    parent_plan=read(PARENT/'simulation/plan_snapshot.json');complement_plan=read(COMPLEMENT/'simulation/plan_snapshot.json');best_plan=read(best_root/'simulation/plan_snapshot.json')
    differences={'coordinate_convention':'Plan JSON [row,col], runtime (col,row), bottom-left field; no seconds/frame conversion in changes','baseline_to_complement':action_diff(parent_plan['action_timeline'],complement_plan['action_timeline']),'baseline_to_best':action_diff(parent_plan['action_timeline'],best_plan['action_timeline']),'complement_to_best':action_diff(complement_plan['action_timeline'],best_plan['action_timeline'])}
    write(BASE/'canonical_action_diff_v1.json',differences)
    relevant_ids={'enemy_1108_uterer#1','enemy_1108_uterer#2','enemy_1107_uoffcr#6','enemy_1107_uoffcr#7','enemy_1107_uoffcr#10','enemy_1107_uoffcr#11','enemy_1107_uoffcr#12','enemy_1107_uoffcr#13','enemy_1107_uoffcr#19','enemy_1108_uterer#29','enemy_1110_uamord#21','enemy_1110_uamord#22','enemy_1110_uamord#33','enemy_1110_uamord#34','enemy_1112_emppnt#0'}
    paths={'baseline':PARENT/'simulation/diagnostic_events.json','complement':COMPLEMENT/'simulation/diagnostic_events.json','best':best_root/'simulation/diagnostic_events.json'}
    packs={name:events(path) for name,path in paths.items()}
    facts={name:{enemy:contacts(ev,enemy) for enemy in sorted(relevant_ids)} for name,ev in packs.items()}
    write(BASE/'parent_comparison_v1.json',{'frozen_identities':parent_manifest,'added_nine_complement_leaks':['#1','#6','#10','#12','#19','#21','#27','#29','#33'],'contacts':facts,'baseline_to_complement':differences['baseline_to_complement'],'boundary':'Zero contact alone is not a causal diagnosis. Event absence is over complete raw logs; continuous positions and exact HP remain UNKNOWN.'})
    index={name:event_index(path,relevant_ids) for name,path in paths.items()}
    boundary=next(r for r in rows if r['name']=='FRONTIER_BOUNDARY2048')
    index['next_frame_missed']=event_index(ROOT/boundary['observed']['events_path'],{'enemy_1107_uoffcr#19'})
    write(BASE/'key_event_index_v1.json',index)
    compact=[]
    for r in state['variants']:
        item={key:r[key] for key in ['name','status','changes','hypothesis','previous'] if key in r}
        item['declared_parent_plan_id']=parent_manifest['parent_id']
        if 'check' in r:item['candidate_id']=r['check'].get('candidate_id');item['errors']=r['check'].get('errors',[])
        if 'observed' in r:
            o=r['observed'];item.update({'leaks':o['leaks'],'result':o['result'],'protected_reached':o['protected_reached'],'artillery_dead':o['artillery_dead'],'events_path':o['events_path'],'complete_win':o['complete_win'],'early_four_killed':all(any(suffix(k)==n for k in o['kills']) for n in [2,7,11,13]),'enemy29_killed':any(suffix(k)==29 for k in o['kills'])})
        compact.append(item)
    write(BASE/'variant_results_v1.json',compact)
    # Branches are compared only among complete, both-arrival, cannon-kill, no-action-error outcomes.
    eligible=[r for r in rows if len(r['observed']['protected_reached'])==2 and r['observed']['artillery_dead'] and not r['observed']['result']['deployment_errors']]
    groups=defaultdict(list)
    for r in eligible:groups[tuple(sorted(e['id'] for e in r['observed']['leaks']))].append(r['name'])
    frontier=[]
    for leaks,names in groups.items():
        if not any(set(other)<set(leaks) for other in groups):frontier.append({'leak_ids':list(leaks),'variant_names':names})
    write(BASE/'branch_frontier_v1.json',{'selection':'Preserve nondominated leak-ID sets only within both-arrival + cannon-kill + zero-action-error results; no reward change','branches':frontier,'best_new_branch':'FRONTIER_BOUNDARY2047','best_global':'M70 eight-ID complete fixed-simulator WIN','seven_or_fewer':'UNKNOWN'})
    independent=read(BASE/'independent_reverification_v1.json')
    assert len(independent)==2 and all(all(r['equals_original'].values()) for r in independent)
    codes={str(p.relative_to(ROOT)):digest(p) for p in list((ROOT/'src/arknights_planner/simulator').glob('*.py'))+[ROOT/'src/arknights_planner/adapters/approximate_real.py']}
    write(BASE/'execution_identity_v1.json',{'head_before_batch':'618b05000aad167a4414ed8798857eda17298f42','controlled_code_sha256':controlled,'runtime_code_sha256':codes,'parameters':read(best_root/'simulation/simulation_parameters.json'),'checked_input_facts_sha256':digest(BASE/'input_bundle/llm_evidence_context.json'),'schema_sha256':digest(BASE/'input_bundle/revision_output_schema.json'),'actual_model_calls':0,'actual_tactical_cli_starts':0,'usage':'NOT_APPLICABLE','model_directory':'No tactical model required or started. Requested 6.2 Astra identifier in configuration is UNVERIFIED and not evidence of availability. No substitution or generation probe.'})
    closed={'reason':'Defined action-group search and observed-boundary refinement complete; two final independent simulations reproduced best new complementary branch. No complete WIN. No equivalent final variant run just to use the last slot.','remaining_simulations':1,'remaining_candidates':3,'remaining_checks':367,'no_balance_transfer':True}
    state['closed']=closed;write(BASE/'search_state.json',state)
    close={'schema_version':'R115_GROUP_SEARCH_CLOSEOUT_V1','generation':'HOST_DETERMINISTIC_PARAMETER_SEARCH_NO_MODEL','accounting':{'production_checks':133,'static_pass':97,'static_rejected':36,'frozen_candidates':97,'actual_complete_simulations':99,'candidate_simulations':97,'independent_final_runs':2,'reservation_indexes_unique':True,'tactical_cli':0,'model_calls':0,'model_usage':'NOT_APPLICABLE','max_check':500,'max_candidate':100,'max_simulation':100,'recorded_old_dedup_skips':sum(r['status']=='DEDUP_SKIPPED' for r in state['variants'])},'best_new':{'name':best['name'],'candidate_id':best['check']['candidate_id'],'plan_id':best_plan['operational_plan_id'],'plan_sha256':digest(best_root/'simulation/plan_snapshot.json'),'action_sha256':digest(best_root/'simulation/action_snapshot.json'),'event_sha256':digest(best_root/'simulation/diagnostic_events.json'),'observed':best['observed']},'relative_to_baseline':{'eliminated_leaks':['#2','#7','#11','#13'],'added_leaks':['#1','#6','#10','#12'],'neither_dominates':True},'relative_to_original_complement':{'eliminated_leaks':['#19','#21','#27','#29','#33'],'added_leaks':[]},'minimal_boundary_change':{'reference':'G_FANG_MELSWAP','retreat':{'before':2054,'after':2047},'return':{'before':4155,'after':4148},'frame_4148':'BLOCK #19@4148, killed@4325','frame_4149':'No BLOCK #19; leak@4475','scope':'Only this frozen trajectory; not a universal deadline'},'independent_verification':'independent_reverification_v1.json','completion':closed,'unsearched':['Other roster/geometry groups outside the recorded sampled replacements','All interactions among three or more independent changes','Exhaustive early upper-role reassignment while retaining cannon and both arrivals','Fine timing/position/direction grids outside observed transitions'],'conclusion':'No complete seven-ID WIN found. M70 eight-ID fixed-simulator WIN stays frozen; seven-or-fewer UNKNOWN.'}
    write(BASE/'closeout_v1.json',close)
    print(json.dumps({'reconstruction':'97 payloads deep-equal','reservations':'99 unique completed','checks':133,'candidates':97,'simulations':99,'frontier_sets':len(frontier),'closed':True}))

if __name__=='__main__':main()
