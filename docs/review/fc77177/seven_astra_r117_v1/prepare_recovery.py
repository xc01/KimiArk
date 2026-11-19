from __future__ import annotations
import sys,subprocess,json,hashlib,time,copy
from pathlib import Path
from prepare import ROOT,BASE,read,write,sha
sys.path.insert(0,str(ROOT/'scripts'))
import run_r8_1_gpt_c4_codex_cli_v1 as runtime
import run_kimiark_real_tool_closed_loop_v1 as old_runner
import codex_model_authorization_v1 as validator

def main():
 recovery=BASE/'recovery_attempt_02'
 if recovery.exists():raise RuntimeError('Recovery attempt already prepared; inspect instead of repeat')
 recovery.mkdir()
 original=read(BASE/'session/codex_cli/cli_process_result.json')
 assert original['exit_code']==1
 ledger=read(BASE/'candidate_ledger_v1.json');budget=read(BASE/'simulation_budget_v1.json')
 assert (ledger['used_check_calls'],ledger['used_candidates'],budget['started_stage_simulations'])==(0,0,0)
 proof={str(p.relative_to(ROOT)):sha(p) for p in (BASE/'session/codex_cli').glob('*') if p.is_file() and not p.name.endswith('.lock')}
 write(recovery/'historical_attempt_hashes.json',proof)
 auth=read(BASE/'model_authorization_v1.json');auth['extra_config_values']=[s for s in auth['extra_config_values'] if not s.startswith('model_providers.openai.')]
 assert all(not s.startswith('model_providers.') for s in auth['extra_config_values'])
 auth['real_cli_starts']={'authorized_real_cli_starts':2,'used_real_cli_starts':1,'prior_failed_attempts':1,'new_explicitly_authorized_recovery_starts':1,'automatic_retry':False,'automatic_resume':False}
 auth['recovery_authorization_source']='User: 那你改一下不就好了 — explicit repair-and-restart continuation after R117 local parser failure. Preserve CLI1 historical, permit one new corrected process, no battle-budget reset.'
 cfg=read(BASE/'session_config_v1.json');cfg['authorization_config_path']=str(recovery/'model_authorization_v2.json');cfg['max_real_cli_starts']=2
 auth['extra_config_values']=[s.replace(str(BASE/'session_config_v1.json'),str(recovery/'session_config_v2.json')) for s in auth['extra_config_values']]
 write(recovery/'model_authorization_v2.json',auth);write(recovery/'session_config_v2.json',cfg)
 env=runtime.codex_environment()
 # Official no-generation catalog command loads the same actual CLI config overrides.
 cmd=['codex','-c','model_provider="openai"']
 for value in auth['extra_config_values']:cmd.extend(['-c',value])
 cmd.extend(['-m','gpt-6.2-astra','-c','model_reasoning_effort="low"','debug','models'])
 result=subprocess.run(cmd,capture_output=True,text=True,env=env,cwd=ROOT,timeout=50)
 write(recovery/'cli_config_parse_preflight.json',{'command':cmd,'returncode':result.returncode,'stderr':result.stderr,'stdout_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),'zero_generation':True})
 if result.returncode:raise RuntimeError('Corrected same-config official parse failed; no tactical start: '+result.stderr[-1000:])
 catalog=json.loads(result.stdout);model=next(m for m in catalog['models'] if m['slug']=='gpt-6.2-astra')
 assert 'low' in [e['effort'] for e in model['supported_reasoning_levels']]
 write(recovery/'model_directory_v2.json',{'time':time.time(),'model':{k:model.get(k) for k in ['slug','display_name','supported_reasoning_levels','visibility']},'parser_preflight':'cli_config_parse_preflight.json','generation_or_quota_guarantee':False})
 servicecmd=[str(ROOT/'.venv/bin/python'),str(BASE/'batch_service.py'),str(recovery/'session_config_v2.json')]
 req=[{'jsonrpc':'2.0','id':0,'method':'initialize','params':{'protocolVersion':'2025-06-18','clientInfo':{'name':'r117-explicit-corrected-attempt','version':'2'}}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':1,'method':'tools/list'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'get_session_status','arguments':{}}}]
 proc=subprocess.run(servicecmd,input=''.join(json.dumps(r)+'\n' for r in req),capture_output=True,text=True,cwd=ROOT,env=env,timeout=30)
 write(recovery/'mcp_preflight_v2.json',{'command':servicecmd,'requests':req,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'environment_names':sorted(k for k in env if k.startswith('CODEX') or k.lower() in ['http_proxy','https_proxy','all_proxy','no_proxy']),'sensitive_values_not_archived':True})
 if proc.returncode:raise RuntimeError('Corrected MCP preflight failed')
 responses=[json.loads(s) for s in proc.stdout.splitlines()];status=next(r['result']['structuredContent'] for r in responses if r.get('id')==2)
 assert (status['check_call_ledger']['used_check_calls'],status['candidate_ledger']['used_candidates'],status['budget']['started_stage_simulations'])==(0,0,0)
 write(recovery/'zero_budget_confirmed.json',status)
 realcmd=old_runner.build_command(recovery/'model_authorization_v2.json',recovery/'codex_final_message.txt')
 write(recovery/'command_authorized.json',validator.validate_cli_authorization(recovery/'model_authorization_v2.json',realcmd,prompt_sha256=None))
 # Prior fake counting fixture already passed; reuse it without another test or battle.
 assert read(BASE/'counting_preflight_v1.json')['status']=='PASS'
 state=read(BASE/'batch_state.json');write(recovery/'prior_blocked_state.json',state)
 state.update(stopped=False,status='AUTHORIZED_RECOVERY_PENDING',recovery_explicit_user_authorization='那你改一下不就好了',historical_cli_starts=1,additional_authorized_cli_starts=1)
 state['prior_blocker']=state.pop('blocker',None);write(BASE/'batch_state.json',state)
 for p,expected in proof.items():assert sha(ROOT/p)==expected,p
 print({'corrected_config_parse':'PASS','MCP':'PASS','check':0,'candidate':0,'simulations':0,'historical_cli_starts':1,'new_cli_authorized':1,'model':'gpt-6.2-astra','effort':'low'})
if __name__=='__main__':main()
