import sys,subprocess,json,time,hashlib,importlib.util
from pathlib import Path
from prepare import *
from contextlib import redirect_stdout
sys.path.insert(0,str(ROOT/'scripts'))
import run_r8_1_gpt_c4_codex_cli_v1 as runtime
import run_kimiark_real_tool_closed_loop_v1 as runner
import codex_model_authorization_v1 as auth

def main():
 env=runtime.codex_environment();cfg=read(BASE/'session_config_v1.json')
 authorization=read(BASE/'model_authorization_v1.json')
 assert not any(s.startswith('model_providers.') for s in authorization['extra_config_values'])
 catalogcmd=['codex','-c','model_provider="openai"']
 for override in authorization['extra_config_values']:catalogcmd.extend(['-c',override])
 catalogcmd.extend(['-m','gpt-6.2-astra','-c','model_reasoning_effort="low"','debug','models'])
 result=subprocess.run(catalogcmd,env=env,cwd=ROOT,capture_output=True,text=True,timeout=50)
 if result.returncode:raise RuntimeError('Directory refresh failed; do not start CLI: '+result.stderr[-1000:])
 catalog=json.loads(result.stdout);model=next((m for m in catalog['models'] if m['slug']=='gpt-6.2-astra'),None)
 if not model or 'low' not in [r['effort'] for r in model['supported_reasoning_levels']]:raise RuntimeError('Requested model/low unavailable')
 write(BASE/'model_directory_verification.json',{'time':time.time(),'command':catalogcmd,'returncode':result.returncode,'catalog_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),'model':{k:model.get(k) for k in ['slug','display_name','supported_reasoning_levels','visibility','supported_in_api']},'zero_generation':True,'scope':'Authenticated model catalog availability; not a quota/generation guarantee'})
 command=[str(ROOT/'.venv/bin/python'),str(BASE/'batch_service.py'),str(BASE/'session_config_v1.json')]
 messages=[{'jsonrpc':'2.0','id':0,'method':'initialize','params':{'protocolVersion':'2025-06-18','clientInfo':{'name':'r119-zero-model-preflight','version':'1'}}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':1,'method':'tools/list'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'get_session_status','arguments':{}}}]
 proc=subprocess.run(command,input=''.join(json.dumps(x)+'\n' for x in messages),capture_output=True,text=True,cwd=ROOT,env=env,timeout=30)
 write(BASE/'mcp_zero_model_preflight.json',{'command':command,'cwd':str(ROOT),'environment_variable_names':sorted(k for k in env if k.startswith('CODEX') or k.lower() in ['http_proxy','https_proxy','all_proxy','no_proxy']),'environment_values_recorded':False,'request':messages,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
 if proc.returncode:raise RuntimeError('MCP local handshake failure '+proc.stderr[-1500:])
 responses=[json.loads(x) for x in proc.stdout.splitlines()];status=next(r['result']['structuredContent'] for r in responses if r.get('id')==2)
 assert status['session_id']==cfg['session_id'] and status['model']=='gpt-6.2-astra' and status['reasoning_effort']=='low'
 assert (status['check_call_ledger']['used_check_calls'],status['candidate_ledger']['used_candidates'],status['budget']['started_stage_simulations'])==(0,0,0)
 write(BASE/'initial_status_v1.json',status)
 # Reuse already-authoritative V2 ledger/fake-only fixture, against a new isolated path.
 sys.path.insert(0,str(ROOT/'docs/review/fc77177/seven_group_search_v1'))
 import preflight_counting as pc
 pc.BASE=BASE;pc.main()
 assert (read(BASE/'candidate_ledger_v1.json')['used_candidates'],read(BASE/'simulation_budget_v1.json')['started_stage_simulations'])==(0,0)
 command=runner.build_command(BASE/'model_authorization_v1.json',BASE/'session/codex_cli/codex_final_message.txt')
 write(BASE/'cli_authorization_preflight.json',auth.validate_cli_authorization(BASE/'model_authorization_v1.json',command,prompt_sha256=None))
 print({'status':'PASS','new_batch_zero':True,'mcp_tool_count':len(next(r['result']['tools'] for r in responses if r.get('id')==1)),'real_model':'gpt-6.2-astra','reasoning':'low','generation_starts':0,'real_simulations':0})
if __name__=='__main__':main()
