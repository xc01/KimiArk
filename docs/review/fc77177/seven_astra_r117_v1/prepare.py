import json,gzip,hashlib,copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
def read(p):
 p=Path(p)
 if not p.exists() and p.with_name(p.name+'.gz').exists():p=p.with_name(p.name+'.gz')
 return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def write(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 if (BASE/'session_config_v1.json').exists():raise RuntimeError('Existing R117; never reset')
 old115=ROOT/'docs/review/fc77177/seven_group_search_v1';old116=ROOT/'docs/review/fc77177/seven_group_search_r116_v1'
 registry={}
 for alias,folder,cid in [('A',old115,'candidate-001'),('B',old115,'candidate-089'),('C',old116,'candidate-030')]:
  cr=folder/'session/candidates'/cid;payload=read(cr/'source/llm_structured_output.json');plan=payload['revised_operational_plans'][0]
  target=BASE/'parents'/alias;target.mkdir(parents=True)
  write(target/'payload.json',payload);write(target/'plan.json',plan)
  entry={'plan_id':plan['operational_plan_id'],'candidate_root':str(cr.relative_to(ROOT)),'payload_copy_sha256':sha(target/'payload.json'),'artifacts':{}}
  for name in ['plan_snapshot.json','action_snapshot.json','diagnostic_events.json','diagnostic_summary.json','simulation_parameters.json']:
   p=cr/'simulation'/name
   if not p.exists():p=p.with_name(p.name+'.gz')
   raw=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()
   entry['artifacts'][name]={'path':str(p.relative_to(ROOT)),'sha256':sha(p),'uncompressed_sha256':hashlib.sha256(raw).hexdigest()}
  registry[alias]=entry
  summary=read(cr/'simulation/diagnostic_summary.json');ev=read(cr/'simulation/diagnostic_events.json')['events']
  write(target/'outcomes.json',{'terminal':{k:v for k,v in summary['result'].items() if k!='events'},'leaks':[e for e in ev if e['event_type']=='ENEMY_LEAK'],'deaths':[e for e in ev if e['event_type']=='OPERATOR_DEATH'],'protected_arrivals':[e for e in ev if e['event_type']=='PROTECTED_TARGET_REACHED'],'devices_destroyed':[e for e in ev if e['event_type']=='DEVICE_DESTROYED']})
 write(BASE/'parent_registry_v1.json',registry)
 write(BASE/'sealed_ledger_hashes.json',{str((directory/name).relative_to(ROOT)):sha(directory/name) for directory in [old115,old116] for name in ['candidate_ledger_v1.json','simulation_budget_v1.json','search_state.json']})
 context=read(old116/'input_bundle/baseline_context.json');context['previous_plan_id']=registry['A']['plan_id'];context['previous_plan_to_revise']=read(BASE/'parents/A/plan.json')
 context['parent_identity_manifest']={'path':str((BASE/'parent_registry_v1.json').relative_to(ROOT)),'candidate_plan_ids':[v['plan_id'] for v in registry.values()],'selection_policy':'A/B four-leak and C joint early22/11 are peer evidence choices; Astra chooses actual parent.'}
 for n in ['template_context.json','llm_evidence_context.json']:write(BASE/'input_bundle'/n,context)
 write(BASE/'input_bundle/revision_output_schema.json',read(old116/'input_bundle/revision_output_schema.json'))
 cfg=read(old116/'session_config_v1.json');cfg.update(session_id='r117-astra-low-five-rounds',plan_label='R117',plan_id_prefix='R117_',model='gpt-6.2-astra',reasoning_effort='low',max_real_cli_starts=1,session_root=str(BASE/'session'),facts_source_dir=str(BASE/'input_bundle'),candidate_ledger_path=str(BASE/'candidate_ledger_v1.json'),budget_path=str(BASE/'simulation_budget_v1.json'),authorization_config_path=str(BASE/'model_authorization_v1.json'))
 write(BASE/'session_config_v1.json',cfg)
 extra=['features.apps=false',f'mcp_servers.kimiark.command="{ROOT/".venv/bin/python"}"',f'mcp_servers.kimiark.args=["{BASE/"batch_service.py"}","{BASE/"session_config_v1.json"}"]','mcp_servers.kimiark.required=true','mcp_servers.kimiark.default_tools_approval_mode="approve"','mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events","inspect_evidence","record_round","search_variants","independent_verify"]']
 write(BASE/'model_authorization_v1.json',{'schema_version':'KIMIARK_CODEX_CLI_AUTHORIZATION_V1','provider':'openai','model':'gpt-6.2-astra','reasoning_effort':'low','features_apps':False,'extra_config_values':extra,'real_cli_starts':{'authorized_real_cli_starts':1,'used_real_cli_starts':0,'automatic_retry':False,'automatic_resume':False},'scope':'Latest R117 authority including supplemental correction. One sustained tactical CLI,500check/100PASS/100fullsim incl independent verification,max5 hypotheses. Host cannot design tactics. No push.'})
 write(BASE/'candidate_ledger_v1.json',{'schema_version':'KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2','session_id':cfg['session_id'],'stage_id':cfg['stage_id'],'max_check_calls':500,'used_check_calls':0,'max_candidates':100,'used_candidates':0,'checks':[],'attempts':[]})
 write(BASE/'simulation_budget_v1.json',{'schema_version':'KIMIARK_STAGE_SIMULATION_BUDGET_V1','stage_id':cfg['stage_id'],'max_stage_simulations':100,'prior_stage_simulations':0,'started_stage_simulations':0})
 write(BASE/'batch_state.json',{'rounds':[],'variants':[],'stopped':False,'cli_started':0,'independent_runs':[]})
 write(BASE/'user_authorization.json',{'batch':'R117','check_max':500,'candidate_max':100,'simulation_max':100,'round_max':5,'cli_max':1,'model':'gpt-6.2-astra','effort':'low','features_apps':False,'supplement':'Post-artillery output/top healing is only hypothesis; do not assume rescuing Midnight rescues leaks. Consider borrowing small interception into A/B or restoring late C, or model-chosen third path. Evaluate leak IDs and artillery/protected/#19 separately.','old_balances_transfer':False,'push':False})
 print({'batch':'R117','counts':{'check':0,'candidate':0,'simulation':0},'parents':{k:v['plan_id'] for k,v in registry.items()},'model':'gpt-6.2-astra/low'})
if __name__=='__main__':main()
