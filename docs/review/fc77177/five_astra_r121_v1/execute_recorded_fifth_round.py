"""Execute Astra's already-issued ReturnLive grid after wrapper false stop.

No new CLI, no new tactical choices, no reopening closed old batches. The
original local stop, failed reservation and raw final remain immutable.
Uses the same R121 ledgers and unchanged production gates. Never retries 039.
"""
import itertools,json,copy
from contextlib import redirect_stdout
import sys
from prepare import BASE,ROOT,read,write,sha
import batch_service as service
import kimiark_tactical_stdio_service_v1 as production
from run_gpt_tactical_stage_diagnostic_v1 import validated_unique_deployments

def main():
    path=BASE/'recorded_fifth_round_execution.json'
    if path.exists():raise RuntimeError('Recorded grid already attempted; no automatic restart')
    trace_path=BASE/'session/codex_cli/codex_exec.jsonl'
    trace_bytes=trace_path.read_bytes() if trace_path.exists() else __import__('gzip').decompress(Path(str(trace_path)+'.gz').read_bytes())
    trace=[json.loads(x) for x in trace_bytes.decode().splitlines() if x]
    calls=[(i,x['item']) for i,x in enumerate(trace) if x['type']=='item.completed' and x.get('item',{}).get('tool')=='search_variants' and x['item'].get('arguments',{}).get('name')=='ReturnLive']
    assert len(calls)==1
    index,call=calls[0];request=copy.deepcopy(call['arguments'])
    assert request['round']==5
    cfg=production.load_session_config(BASE/'session_config_v1.json')
    audit={'source':'Actual Astra ReturnLive request rejected only by batch_stopped after local pre-battle contract mismatch','trace_event_index':index,'trace_sha256':__import__('hashlib').sha256(trace_bytes).hexdigest(),'original_request':request,'model_decisions_added_by_host':0,'CLI_starts_added':0,'old_stop_state_retained':True,'failed_039_never_retried':True,'variants':[],'status':'STARTED'}
    write(path,audit)
    parameters=request.get('parameters',{});keys=list(parameters)
    for j,values in enumerate(itertools.product(*(parameters[k] for k in keys))):
        mapping=dict(zip(keys,values));name=request['name']+'_'+str(j)
        actions=service.expand(request.get('actions'),mapping);changes=service.expand(request.get('changes',[]),mapping)
        payload=service.build(request['parent'],name,changes,request['hypothesis'],5,actions=actions)
        # Exact same guard used at actual production entry, now before check/
        # reservation. No change of runtime rule and no tactical modification.
        validated_unique_deployments(payload['revised_operational_plans'][0]['action_timeline'])
        state=read(BASE/'batch_state.json');key=service.action_key(payload)
        if any(r.get('action_key')==key for r in state['variants']):raise RuntimeError('Would repeat frozen behavior; stop')
        parent=service.getparent(request['parent']);ctx=read(BASE/'input_bundle/template_context.json');ctx['previous_plan_id']=parent['revised_operational_plans'][0]['operational_plan_id'];ctx['previous_plan_to_revise']=parent['revised_operational_plans'][0]
        write(cfg.facts_source_dir/'llm_evidence_context.json',ctx)
        row={'name':name,'round':5,'parent':request['parent'],'hypothesis':request['hypothesis'],'parameters':mapping,'actions':actions,'changes':changes,'action_key':key,'source':'Original Astra tool grid, mechanically executed after local host wrapper refusal; no new model decision','host_execution_after_child_exit':True}
        with redirect_stdout(sys.stderr):check=service.checked_plan(cfg,{'plan':payload})
        row.update(check=check,status=check['status'])
        if check['status']=='PASS':row.update(candidate_id=check['candidate_id'],candidate_sha256=check['candidate_sha256'],plan_id=payload['revised_operational_plans'][0]['operational_plan_id'])
        state['variants'].append(row);write(BASE/'batch_state.json',state)
        if check['status']=='PASS':
            with redirect_stdout(sys.stderr):run=production.run_simulation(cfg,{'candidate_id':row['candidate_id'],'candidate_sha256':row['candidate_sha256']})
            row['run']=run
            if run['status']!='COMPLETED':audit.update(status='BLOCKED_NO_RETRY',blocker=run);write(path,audit);raise RuntimeError('Production execution failure; no retry')
            row['observed']=service.observe(row['candidate_id']);state['variants'][-1]=row;write(BASE/'batch_state.json',state)
        elif check['status']!='FAIL':audit.update(status='BLOCKED',blocker=check);write(path,audit);raise RuntimeError('Service/budget failure')
        audit['variants'].append(row);write(path,audit)
        print({'name':name,'check':check['status'],'candidate':row.get('candidate_id'),'result':row.get('observed',{}).get('result')},flush=True)
        if row.get('observed',{}).get('complete_win'):
            write(BASE/'WIN_PENDING_VERIFICATION.json',{'candidate_id':row['candidate_id'],'source':'Actual original Astra ReturnLive grid'})
            with redirect_stdout(sys.stderr):proof=service.independent_verify(cfg,{'candidate_id':row['candidate_id']})
            audit.update(status='WIN_INDEPENDENTLY_VERIFIED',verification=proof);write(path,audit);return
    audit.update(status='COMPLETED_ORIGINAL_ASTRA_GRID_NO_NEW_TACTICS')
    write(path,audit)

if __name__=='__main__':main()
