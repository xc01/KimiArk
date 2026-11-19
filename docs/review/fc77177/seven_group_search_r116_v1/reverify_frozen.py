"""Independent production re-executions, never the MCP idempotent cache."""
from __future__ import annotations
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from driver import BASE, ROOT, read, write, digest, summarize
PREFIX = 'R116_'


def main():
    sys.path.insert(0,str(ROOT/'scripts'))
    import tactical_evaluation_gate_v1 as gate
    state=read(BASE/'search_state.json')
    row=next(r for r in state['variants'] if r['name']=='R5_SUSTAIN_H3240')
    candidate=BASE/'session/candidates'/row['check']['candidate_id']
    record=read(candidate/'candidate_record.json')
    assert record['check_status']=='PASS' and record['unique_deployed_operator_count']<=7
    assert row['simulation_status']=='COMPLETED'
    for code,expected in record['controlled_code_sha256'].items():
        assert digest(ROOT/code)==expected,code
    outputs=[]
    for run_id in ['sustained_independent_a','sustained_independent_b']:
        run_root=BASE/'reverification'/run_id
        if run_root.exists():raise RuntimeError('Independent run ID exists; no automatic retry')
        budget_before=read(BASE/'simulation_budget_v1.json')['started_stage_simulations']
        if budget_before>=100:raise RuntimeError('No remaining simulation budget')
        source=run_root/'source';source.mkdir(parents=True)
        recovery={}
        for name,expected in record['frozen_inputs_sha256'].items():
            original=candidate/'source'/name
            if digest(original)==expected:shutil.copyfile(original,source/name)
            elif name=='execution_input_gate.json':
                gate_bytes=(__import__('json').dumps(row['check']['execution_input_gate'],ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()
                assert hashlib.sha256(gate_bytes).hexdigest()==expected
                (source/name).write_bytes(gate_bytes)
                recovery[name]='Original production check response in search_state.json; post-run generated gate differs'
            else:raise RuntimeError('Frozen input mismatch '+name)
            assert digest(source/name)==expected
        output=run_root/'simulation'
        evaluation=gate.prepare_evaluation(source_dir=source,diagnostic_output_dir=output,budget_path=BASE/'simulation_budget_v1.json',stage_id='main_08-07',expected_plan_id=record['plan_id'])
        assert evaluation['status']=='AUTHORIZED'
        command=[sys.executable,str(ROOT/'scripts/run_gpt_tactical_stage_session_v1.py'),'simulate','--stage-id','main_08-07','--facts-dir',str(source),'--output-dir',str(source),'--diagnostic-output-dir',str(output),'--plan-id',record['plan_id'],'--plan-label','R116','--plan-id-prefix',PREFIX,'--max-unique-deployed-operators','7','--authorization-config',str(BASE/'model_authorization_v1.json'),'--simulation-budget-path',str(BASE/'simulation_budget_v1.json')]
        write(run_root/'provenance.json',{'run_id':run_id,'candidate_id':record['candidate_id'],'candidate_sha256':record['candidate_sha256'],'frozen_inputs_sha256':record['frozen_inputs_sha256'],'recovered_inputs':recovery,'controlled_code_sha256':record['controlled_code_sha256'],'gate':evaluation,'command':command,'tactical_cli':0,'model_calls':0,'new_candidate':False,'simulation_budget_before':budget_before,'generation':'Independent execution of previously checked/frozen deterministic variant; no idempotent run call'})
        completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        (run_root/'stdout.txt').write_text(completed.stdout);(run_root/'stderr.txt').write_text(completed.stderr)
        after=read(BASE/'simulation_budget_v1.json')['started_stage_simulations']
        if completed.returncode!=0:raise RuntimeError(f'Independent simulation failed: {run_id}; no retry')
        assert after==budget_before+1
        reservation=read(output.with_name(output.name+'.simulation_reservation.json'))
        assert reservation['status']=='COMPLETED'
        hashes={name:digest(output/name) for name in ['plan_snapshot.json','action_snapshot.json','diagnostic_events.json']}
        equal={name:value==digest(candidate/'simulation'/name) for name,value in hashes.items()}
        assert all(equal.values()),equal
        observation=summarize(output)
        for name,expected in record['frozen_inputs_sha256'].items():
            if name!='execution_input_gate.json':assert digest(source/name)==expected,name
        item={'run_id':run_id,'returncode':completed.returncode,'simulation_budget_after':after,'reservation':reservation,'hashes':hashes,'equals_original':equal,'observed':observation}
        write(run_root/'verification.json',item);outputs.append(item)
        write(BASE/'independent_reverification_v1.json',outputs)
        print(__import__('json').dumps({'run_id':run_id,'actual_simulation_count':after,'hashes_equal':equal,'result':observation['result'],'leaks':observation['leaks'],'arrivals':observation['protected_reached']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
