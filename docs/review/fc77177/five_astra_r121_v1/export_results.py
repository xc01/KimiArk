"""Export completed fixed-five evidence and exact best axis, no new battle."""
from collections import Counter
from prepare import BASE,ROOT,read,write,sha
from run_gpt_tactical_stage_diagnostic_v1 import validated_unique_deployments

def main():
    state=read(BASE/'batch_state.json')
    target=next(r for r in state['variants'] if r.get('candidate_id')=='candidate-040')
    first=next(r for r in state['variants'] if r.get('candidate_id')=='candidate-011')
    plan=read(BASE/'session/candidates/candidate-040/simulation/plan_snapshot.json')
    catalog={x['operator_id']:x for x in read(BASE/'input_bundle/template_context.json')['normal_low_star_catalog']}
    write(BASE/'best_frozen_plan.json',plan)
    write(BASE/'best_action_timeline.json',{'candidate_id':'candidate-040','plan_id':plan['operational_plan_id'],'source':'Exact frozen production snapshot, original Astra ReturnLive_0 arguments; no editorial tactical changes','frames_per_second':30,'coordinates':'[row,col]','actions':plan['action_timeline']})
    header=['frame','seconds','operator','operator_id','action_type','row','col','direction']
    lines=['\t'.join(header)]
    for a in plan['action_timeline']:
        tile=a.get('tile',['-','-'])
        lines.append('\t'.join(map(str,[a['frame'],f"{a['frame']/30:.3f}",catalog[a['operator_id']]['name'],a['operator_id'],a['action_type'],tile[0],tile[1],a.get('direction','-')])))
    (BASE/'BEST_AXIS_TO_COPY.tsv').write_text('\n'.join(lines)+'\n')
    before={e['source_id'] for e in first['observed']['leaks']};after={e['source_id'] for e in target['observed']['leaks']}
    assert after<before and before-after=={'enemy_1110_uamord#34'}
    exports={}
    important={'enemy_1108_uterer#1','enemy_1108_uterer#4','enemy_1107_uoffcr#6','enemy_1107_uoffcr#11','enemy_1107_uoffcr#13','enemy_1107_uoffcr#19','enemy_1112_emppnt#0','enemy_1110_uamord#21','enemy_1110_uamord#22','enemy_1110_uamord#33','enemy_1110_uamord#34','enemy_3001_upeopl#3','enemy_3001_upeopl#14'}
    for cid in ['candidate-004','candidate-005','candidate-011','candidate-015','candidate-027','candidate-040']:
        events=read(BASE/'session/candidates'/cid/'simulation/diagnostic_events.json')['events']
        exports[cid]={'event_log':str((BASE/'session/candidates'/cid/'simulation/diagnostic_events.json').relative_to(ROOT)),'indexed_events':[{'raw_index':i,**e} for i,e in enumerate(events) if e['event_type'] in ['OPERATOR_DEATH','PROTECTED_TARGET_REACHED','DEVICE_DESTROYED','RETREAT','DEPLOY'] or e['event_type'] in ['ENEMY_DEATH','ENEMY_LEAK','DAMAGE','BLOCK'] and (e.get('target_id') in important or e.get('source_id') in important)]}
    write(BASE/'key_event_index_v1.json',exports)
    # Reuse exact production pre-battle guard in pure fixture; no simulation.
    bad=read(BASE/'session/candidates/candidate-039/source/llm_structured_output.json')['revised_operational_plans'][0]['action_timeline']
    try:validated_unique_deployments(bad)
    except RuntimeError as error:bad_rejected=str(error)
    else:raise AssertionError('Original missing retreat should be rejected')
    assert validated_unique_deployments(plan['action_timeline'])
    write(BASE/'local_guard_fixture_v1.json',{'status':'PASS','original039_rejected':bad_rejected,'original_Astra_ReturnLive_040_accepted':True,'new_production_checks_or_battles':0,'scope':'Only thin R121 recorded-grid executor applies existing actual entry guard before reservation; production service/simulator not altered','original_failure_and_spent_reservation_preserved':True})
    rounds={}
    for n in range(1,6):
        rows=[r for r in state['variants'] if r['round']==n]
        actual=[r for r in rows if r.get('run',{}).get('status')=='COMPLETED']
        rounds[n]={'check':len(rows),'PASS':sum(r['status']=='PASS' for r in rows),'static_reject':sum(r['status']=='FAIL' for r in rows),'completed_candidate_battles':len(actual),'counted_failed_before_battle':sum(r.get('run',{}).get('status')=='FAILED_AFTER_START' for r in rows),'candidate_ids':[r.get('candidate_id') for r in actual],'true_artillery_kills':[r['candidate_id'] for r in actual if r['observed']['artillery_kill'] is not None],'both_protected_arrived':[r['candidate_id'] for r in actual if len(r['observed']['protected_arrivals'])==2]}
    write(BASE/'round_results_v1.json',rounds)
    write(BASE/'best_selection_v1.json',{'candidate_id':'candidate-040','plan_id':plan['operational_plan_id'],'actual_observed':target['observed'],'strict_change_to_independently_reproduced011':{'eliminated':sorted(before-after),'added':sorted(after-before),'both_arrived_instead_of_one':True,'all_enemies_settled_instead_of_one_protected_remaining':True},'selection':'Mechanical strict dominance among completed original Astra grid; not a post-run model tactical decision','independently_verified':state['independent_runs'][-1],'raw_model_final_remains011':'Child had exited before queued ReturnLive grid executed; no false attribution of this outcome to model feedback','model_generation_after_exit':0,'fixed_roster':sorted(plan['selected_low_star_operator_ids'])})
    print({'exported_best':'candidate-040','exact_actions':len(plan['action_timeline']),'guard_fixture':'PASS','new_battles':0})

if __name__=='__main__':main()
