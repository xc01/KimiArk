"""Completed-model and production-evidence verification only; no new battle."""
import json,gzip,hashlib
from pathlib import Path
from collections import Counter
from prepare import ROOT,BASE,read,write,sha,FIXED
import batch_service as service

def raw(path):
    path=Path(path)
    return path.read_bytes() if path.exists() else gzip.decompress(Path(str(path)+'.gz').read_bytes())
def digest(path):return hashlib.sha256(raw(path)).hexdigest()
def main():
    cli=BASE/'session/codex_cli';result=read(cli/'cli_process_result.json')
    assert result['exit_code']==0 and result['cli_starts']==1 and result['status']=='COMPLETED'
    trace=[json.loads(x) for x in raw(cli/'codex_exec.jsonl').decode().splitlines() if x]
    assert all(sum(x['type']==t for x in trace)==1 for t in ['thread.started','turn.started','turn.completed'])
    calls=[x['item'] for x in trace if x['type']=='item.completed' and x.get('item',{}).get('type')=='mcp_tool_call']
    searches=[x['arguments'] for x in calls if x.get('tool')=='search_variants']
    decisions=[x['arguments'] for x in calls if x.get('tool')=='record_round']
    directs=[x['arguments']['plan'] for x in calls if x.get('tool')=='check_plan']
    assert {d['round'] for d in decisions}==set(range(1,6))
    write(BASE/'actual_model_search_requests.json',searches)
    write(BASE/'actual_model_round_records.json',decisions)
    write(BASE/'actual_model_direct_submissions.json',directs)
    ledger=read(BASE/'candidate_ledger_v1.json');budget=read(BASE/'simulation_budget_v1.json');state=read(BASE/'batch_state.json')
    assert (ledger['used_check_calls'],ledger['used_candidates'],budget['started_stage_simulations'])==(39,32,33)
    assert Counter(x['status'] for x in ledger['checks'])=={'PASS':32,'FAIL':7}
    for path,expected in read(BASE/'sealed_ledger_hashes.json').items():assert sha(ROOT/path)==expected,path
    for path,expected in read(cli/'frozen_start_manifest.json')['inputs'].items():assert sha(ROOT/path)==expected,path
    for path,expected in read(BASE/'mechanic_patch_identity.json')['files_sha256'].items():assert sha(ROOT/path)==expected,path
    registry=read(BASE/'parent_registry_v1.json')
    for alias,entry in registry.items():
        assert sha(BASE/'parents'/alias/'payload.json')==entry['payload_copy_sha256']
        for item in entry['artifacts'].values():assert sha(ROOT/item['path'])==item['sha256']
    proven=[];outcomes=[];allkeys=[]
    for entry in ledger['attempts']:
        cid=entry['candidate_id'];cr=BASE/'session/candidates'/cid
        payload=read(cr/'source/llm_structured_output.json');plan=payload['revised_operational_plans'][0]
        actual=read(cr/'simulation/plan_snapshot.json');assert actual==plan
        assert set(plan['selected_low_star_operator_ids'])==set(FIXED)
        assert {a['operator_id'] for a in plan['action_timeline']}<=set(FIXED)
        key=service.action_key(plan);assert key not in allkeys;allkeys.append(key)
        variant=next((r for r in state['variants'] if r.get('candidate_id')==cid),None)
        if variant is None:
            assert any(payload==direct for direct in directs),'Direct production payload missing real model source'
            provenance={'candidate_id':cid,'source':'EXACT_ACTUAL_ASTRA_DIRECT_check_plan_PAYLOAD','deep_equal':True,'round':1}
        else:
            assert any(q['name']==variant['name'].rsplit('_',1)[0] and q['round']==variant['round'] and q['parent']==variant['parent'] and q['hypothesis']==variant['hypothesis'] and service.expand(q.get('changes',[]),variant['parameters'])==variant['changes'] and service.expand(q.get('actions'),variant['parameters'])==variant.get('actions') for q in searches)
            reconstructed=service.build(variant['parent'],variant['name'],variant['changes'],variant['hypothesis'],variant['round'],actions=variant.get('actions'))
            assert reconstructed==payload
            provenance={'candidate_id':cid,'source':'ACTUAL_ASTRA_SEARCH_GRID_MECHANICALLY_EXPANDED','deep_equal':True,'round':variant['round']}
        record=read(cr/'candidate_record.json');assert record['check_status']=='PASS' and record['unique_deployed_operator_count']==5
        for path,expected in record['controlled_code_sha256'].items():assert sha(ROOT/path)==expected,path
        assert entry['simulation_status']=='COMPLETED'
        observation=service.observe(cid)
        if variant:assert observation==variant['observed']
        outcomes.append({'candidate_id':cid,'plan_id':plan['operational_plan_id'],'parent_plan_id':plan['parent_plan_id'],'model_source':provenance,'observed':observation,'plan_sha256':digest(cr/'simulation/plan_snapshot.json'),'actions_sha256':digest(cr/'simulation/action_snapshot.json'),'events_sha256':digest(cr/'simulation/diagnostic_events.json')})
        proven.append(provenance)
    reservations=[read(p) for directory in [BASE/'session/candidates',BASE/'reverification'] for p in directory.glob('*/simulation.simulation_reservation.json')]
    assert sorted(r['reservation_index'] for r in reservations)==list(range(1,34)) and all(r['status']=='COMPLETED' and r['result_saved'] for r in reservations)
    assert len(state['independent_runs'])==1
    rerun=state['independent_runs'][0]
    assert rerun['candidate_id']=='candidate-023' and rerun['budget_before']==32 and rerun['budget_after']==33
    independent=ROOT/rerun['path'];origin=BASE/'session/candidates/candidate-023/simulation'
    equality={name:digest(independent/name)==digest(origin/name) for name in ['plan_snapshot.json','action_snapshot.json','diagnostic_events.json']}
    assert all(equality.values()) and equality==rerun['hash_equal']
    baseline=[]
    for cid,alias in [('candidate-001','E'),('candidate-002','D')]:
        candidate_plan=read(BASE/'session/candidates'/cid/'simulation/plan_snapshot.json');oldplan=read(BASE/'parents'/alias/'plan.json')
        assert candidate_plan['action_timeline']==oldplan['action_timeline']
        oldevents=read(ROOT/registry[alias]['artifacts']['diagnostic_events.json']['path'])['events']
        events=service.evidence_events(cid) if any(r.get('candidate_id')==cid for r in state['variants']) else read(BASE/'session/candidates'/cid/'simulation/diagnostic_events.json')['events']
        event_types={'ENEMY_DEATH','ENEMY_LEAK','PROTECTED_TARGET_REACHED','OPERATOR_DEATH','DEVICE_DESTROYED'}
        project=lambda ev:[(e['event_type'],e['frame'],e.get('source_id'),e.get('target_id'),e['details']) for e in ev if e['event_type'] in event_types]
        assert project(events)==project(oldevents)
        baseline.append({'candidate_id':cid,'old_reference':alias,'actions_exact_equal':True,'combat_terminal_key_events_deep_equal':True,'actual_protocol_parent':candidate_plan['parent_plan_id'],'validation_card_parent':candidate_plan.get('validation_card',{}).get('parent_id'),'raw_baseline_parent_mismatch_preserved':cid=='candidate-002','note':'D action baseline uses E outer parent accepted by production; not claim exact D lineage. Tactical actions are exact D and not spliced.','new_plume_DP_events':[{'raw_index':i,**e} for i,e in enumerate(events) if e['event_type']=='DP_CHANGE' and e.get('source_id')=='char_192_falco']})
    write(BASE/'baseline_replay_comparison.json',baseline)
    write(BASE/'model_provenance_verification.json',{'status':'PASS','real_model':'gpt-6.2-astra/low','CLI':1,'candidates':proven,'host_tactical_design':False,'baseline_lineage_caveat':'candidate002 exact D actions but outer protocol parent E; raw output retained'})
    write(BASE/'candidate_results_v1.json',{'completed':outcomes,'rejected_checks':[r for r in ledger['checks'] if r['status']=='FAIL']})
    usage=result['usage_records']
    assert all(r['usage'].get('cached_input_tokens',0)<=r['usage']['input_tokens'] for r in usage)
    counts={'production_check':39,'static_or_contract_reject':7,'PASS_frozen_candidates':32,'actual_complete_simulations':33,'candidate_runs':32,'independent_reruns':1,'rounds':5,'tactical_CLI':1,'model':'gpt-6.2-astra','reasoning':'low','features_apps':False,'CLI_usage':usage,'internal_model_requests':'UNKNOWN_CLI_INTERNAL'}
    state.update(stopped=True,status='COMPLETED_FIVE_ROUNDS_NO_FIXED_FIVE_WIN',closure_reason='Five real Astra hypothesis cycles completed; current best023 independently verified; no external blocker or restart')
    write(BASE/'batch_state.json',state)
    write(BASE/'closeout_v1.json',{'batch':'R122','mechanics':'m39-charger-kill-and-retreat-dp-v1','counts':counts,'best_candidate':'candidate-023','best_observed':next(x for x in outcomes if x['candidate_id']=='candidate-023'),'independent_verification':rerun,'WIN':False,'old_m38b_results':'Historical only; originals and ledgers preserved','host_tactical_design':False,'baseline_lineage_caveat':baseline[1],'no_push':True})
    write(BASE/'final_budget_v1.json',{'check':{'max':500,'used':39,'remaining':461},'candidate':{'max':100,'used':32,'remaining':68},'simulation':{'max':100,'used':33,'remaining':67},'rounds':{'max':5,'used':5},'CLI':{'max':1,'used':1},'closed':True,'no_transfer':True})
    print({'status':'VERIFIED_AND_CLOSED','check':39,'candidate':32,'fullsim':33,'CLI':1,'rounds':5,'WIN':False})
if __name__=='__main__':main()
