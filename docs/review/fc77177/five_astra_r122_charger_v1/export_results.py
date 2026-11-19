"""Export existing R122 axis, DP attribution and event indices; no battles."""
from prepare import BASE,ROOT,read,write

def main():
    plan=read(BASE/'session/candidates/candidate-023/simulation/plan_snapshot.json')
    base=read(BASE/'session/candidates/candidate-002/simulation/plan_snapshot.json')
    facts=read(BASE/'input_bundle/template_context.json');names={x['operator_id']:x['name'] for x in facts['normal_low_star_catalog']}
    write(BASE/'best_frozen_plan.json',plan)
    write(BASE/'best_action_timeline.json',{'candidate_id':'candidate-023','plan_id':plan['operational_plan_id'],'mechanics':'m39-charger-kill-and-retreat-dp-v1','frames_per_second':30,'coordinates':'[row,col]','actions':plan['action_timeline']})
    lines=['frame\tseconds\toperator\taction\trow\tcol\tdirection']
    for a in plan['action_timeline']:
        tile=a.get('tile',['-','-']);lines.append('\t'.join(map(str,[a['frame'],f"{a['frame']/30:.3f}",names[a['operator_id']],a['action_type'],tile[0],tile[1],a.get('direction','-')])))
    (BASE/'BEST_AXIS_TO_COPY.tsv').write_text('\n'.join(lines)+'\n')
    changes=[{'index':i,'before':a,'after':b} for i,(a,b) in enumerate(zip(base['action_timeline'],plan['action_timeline'])) if a!=b]
    # Stable ordering shifts indices when changing frames, so exact add/remove
    # set comparison is included as the authoritative behavior delta.
    import json
    canon=lambda a:json.dumps(a,sort_keys=True,ensure_ascii=False)
    before={canon(a):a for a in base['action_timeline']};after={canon(a):a for a in plan['action_timeline']}
    write(BASE/'best_action_diff.json',{'reference':'Current m39 candidate002 (exact historical D tactical axis)','selected_unchanged':plan['selected_low_star_operator_ids']==base['selected_low_star_operator_ids'],'removed':[before[k] for k in sorted(before.keys()-after.keys())],'added':[after[k] for k in sorted(after.keys()-before.keys())],'no_new_direct_mechanism_attribution':'Diff changes withdrawal/redeployment timing as well as mechanics already fixed; cannot attribute new kill solely to DP reward'})
    rows=read(BASE/'candidate_results_v1.json')['completed'];selected=next(x for x in rows if x['candidate_id']=='candidate-023');control=next(x for x in rows if x['candidate_id']=='candidate-002')
    leaks=lambda r:{e['source_id'] for e in r['observed']['leaks']}
    assert leaks(selected)<leaks(control) and leaks(control)-leaks(selected)=={'enemy_1108_uterer#28'}
    write(BASE/'best_selection_v1.json',{'candidate_id':'candidate-023','original_selector':'Actual Astra fifth-round decision and independent_verify call','eliminated_from_m39_baseline':sorted(leaks(control)-leaks(selected)),'new_leaks':sorted(leaks(selected)-leaks(control)),'both_protected_arrived':len(selected['observed']['protected_arrivals'])==2,'full_WIN':False,'independent_verification':read(BASE/'batch_state.json')['independent_runs'][0]})
    indexed={}
    focus={'enemy_1112_emppnt#0','enemy_1107_uoffcr#11','enemy_1107_uoffcr#13','enemy_1107_uoffcr#19','enemy_1108_uterer#28','enemy_1110_uamord#21','enemy_1110_uamord#22','enemy_1110_uamord#33','enemy_1110_uamord#34','enemy_3001_upeopl#3','enemy_3001_upeopl#14'}
    for cid in ['candidate-001','candidate-002','candidate-017','candidate-023','candidate-024']:
        ev=read(BASE/'session/candidates'/cid/'simulation/diagnostic_events.json')['events']
        indexed[cid]={'event_log':str((BASE/'session/candidates'/cid/'simulation/diagnostic_events.json').relative_to(ROOT)),'events':[{'raw_index':i,**e} for i,e in enumerate(ev) if e['event_type'] in ['OPERATOR_DEATH','PROTECTED_TARGET_REACHED','DEVICE_DESTROYED','DEPLOY','RETREAT'] or e['event_type']=='DP_CHANGE' and e.get('source_id')=='char_192_falco' or e['event_type'] in ['BLOCK','DAMAGE','ENEMY_DEATH','ENEMY_LEAK'] and (e.get('source_id') in focus or e.get('target_id') in focus)]}
    write(BASE/'key_event_index_v1.json',indexed)
    state=read(BASE/'batch_state.json');rounds={}
    for n in range(1,6):
        variants=[v for v in state['variants'] if v['round']==n]
        rounds[n]={'search_checks':len(variants),'search_PASS':sum(v['status']=='PASS' for v in variants),'search_FAIL':sum(v['status']=='FAIL' for v in variants),'actual_direct_checks':3 if n==1 else 0,'actual_direct_PASS':2 if n==1 else 0,'candidate_battles':sum(v['status']=='PASS' for v in variants)+(2 if n==1 else 0),'decisions':[r for r in state['rounds'] if r['round']==n]}
    write(BASE/'round_results_v1.json',rounds)
    print({'best':'candidate-023','eliminated':'#28','new_leaks':0,'exact_axis_exported':True,'new_battles':0})
if __name__=='__main__':main()
