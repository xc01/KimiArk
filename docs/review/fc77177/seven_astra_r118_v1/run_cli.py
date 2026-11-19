from __future__ import annotations
import sys,os,subprocess,time,json,fcntl,hashlib
from datetime import datetime,timezone
from pathlib import Path
from prepare import ROOT,BASE,read,write,sha
sys.path.insert(0,str(ROOT/'scripts'))
import run_kimiark_real_tool_closed_loop_v1 as original
import run_r8_1_gpt_c4_codex_cli_v1 as runtime
import codex_model_authorization_v1 as validator

def main():
 output=BASE/'session/codex_cli';output.mkdir(parents=True,exist_ok=True)
 with (output/'runner.lock').open('a') as lock:
  fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  attempt=output/'cli_process_attempt.json'
  if attempt.exists():raise RuntimeError('CLI already attempted; no restart')
  ledger=read(BASE/'candidate_ledger_v1.json');budget=read(BASE/'simulation_budget_v1.json')
  assert (ledger['used_check_calls'],ledger['used_candidates'],budget['started_stage_simulations'])==(0,0,0)
  env=runtime.codex_environment();prompt=(BASE/'tactical_prompt.txt').read_text();last=output/'codex_final_message.txt'
  command=original.build_command(BASE/'model_authorization_v1.json',last)
  proof=validator.validate_cli_authorization(BASE/'model_authorization_v1.json',command,prompt_sha256=None)
  original.proxy_prestart(output)
  immutable={str(p.relative_to(ROOT)):sha(p) for p in [BASE/'tactical_prompt.txt',BASE/'session_config_v1.json',BASE/'model_authorization_v1.json',BASE/'batch_service.py',BASE/'parent_registry_v1.json',BASE/'input_bundle/template_context.json',BASE/'input_bundle/revision_output_schema.json']}
  write(output/'frozen_start_manifest.json',{'inputs':immutable,'parent_artifacts':read(BASE/'parent_registry_v1.json'),'model_directory':read(BASE/'model_directory_verification.json'),'environment_names':sorted(k for k in env if k.startswith('CODEX') or k.lower() in ['http_proxy','https_proxy','all_proxy','no_proxy']),'environment_values_archived':False,'cwd':str(ROOT),'command':command,'authorization_proof':proof})
  (output/'codex_prompt.txt').write_text(prompt)
  write(output/'codex_command.json',{'argv':command,'cwd':str(ROOT),'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'automatic_retry':False,'automatic_resume':False,'tactical_design_by':'Only this GPT-6.2 Astra low child session'})
  write(attempt,{'status':'STARTED','time':datetime.now(timezone.utc).isoformat(),'model':'gpt-6.2-astra','reasoning_effort':'low','command':command,'internal_model_request_count':'UNKNOWN_CLI_INTERNAL','attempted_cli_starts':1,'automatic_retry':False,'automatic_resume':False})
  with (output/'codex_exec.jsonl').open('w') as stdout,(output/'codex_stderr.txt').open('w') as stderr:
   started=time.monotonic();proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,text=True,env=env,cwd=ROOT)
   write(output/'process_identity.json',{'pid':proc.pid,'parent_pid':os.getpid(),'command':command,'model':'gpt-6.2-astra','reasoning_effort':'low','started_at':datetime.now(timezone.utc).isoformat()})
   state=read(BASE/'batch_state.json');state['cli_started']=1;write(BASE/'batch_state.json',state)
   proc.stdin.write(prompt);proc.stdin.close();failure=None;position=0
   while proc.poll() is None:
    time.sleep(0.4)
    with (output/'codex_exec.jsonl').open() as trace:
     trace.seek(position);lines=trace.readlines();position=trace.tell()
    for line in lines:
     try:item=json.loads(line)
     except:continue
     if item.get('type') in ['error','turn.failed']:
      message=str(item.get('message') or item.get('error') or '')
      if any(word in message.lower() for word in ['quota','capacity','403','429','routing','reconnect','timed out','timeout','failed to refresh','network','websocket']):
       failure={'reason':'EXTERNAL_SERVICE_ERROR_NO_RETRY','event':item};break
    if failure:
     proc.terminate();break
    if time.monotonic()-started>10800:failure={'reason':'AUTHORIZED_SINGLE_SESSION_WALLTIME_10800_SECONDS'};proc.terminate();break
   try:code=proc.wait(timeout=20)
   except subprocess.TimeoutExpired:proc.kill();code=proc.wait()
  trace=(output/'codex_exec.jsonl').read_text();summary=runtime.extract_events_summary(trace)
  write(output/'codex_trajectory_summary.json',summary)
  write(output/'cli_process_result.json',{'status':'BLOCKED' if failure else 'COMPLETED' if code==0 else 'FAILED','exit_code':code,'failure':failure,'duration_seconds':time.monotonic()-started,'no_restart':True,'cli_starts':1,'usage_records':summary.get('usage_records',[]),'internal_model_requests':'UNKNOWN_CLI_INTERNAL'})
  if failure:write(BASE/'blocking_condition.json',failure)
  print(json.dumps({'status':'BLOCKED' if failure else 'EXITED','exit_code':code,'failure':failure,'final_message_exists':last.exists(),'cli_starts':1},ensure_ascii=False))
if __name__=='__main__':main()
