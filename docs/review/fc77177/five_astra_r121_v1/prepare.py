"""Independent fixed-five batch preparation; no host tactical timeline."""
import json,gzip,hashlib,copy,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
FIXED=['char_124_kroos','char_283_midn','char_210_stward','char_120_hibisc','char_192_falco']
def read(p):
 p=Path(p)
 if not p.exists():p=Path(str(p)+'.gz')
 return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 if (BASE/'session_config_v1.json').exists():raise RuntimeError('R121 exists; never reset')
 old=ROOT/'docs/review/fc77177/seven_astra_r119_v1';last=ROOT/'docs/review/fc77177/seven_vanguard_r120_v1'
 sealed=read(last/'sealed_ledger_hashes.json')
 for name in ['candidate_ledger_v1.json','simulation_budget_v1.json','batch_closed.json']:sealed[str((last/name).relative_to(ROOT))]=sha(last/name)
 for path,value in sealed.items():assert sha(ROOT/path)==value,path
 write(BASE/'sealed_ledger_hashes.json',sealed)
 registry={}
 for alias,folder,cid in [('A',old,'candidate-002'),('B',old,'candidate-007'),('C',last,'candidate-001')]:
  root=folder/'session/candidates'/cid;payload=read(root/'source/llm_structured_output.json');target=BASE/'parents'/alias
  write(target/'payload.json',payload);write(target/'plan.json',payload['revised_operational_plans'][0]);artifacts={}
  for name in ['plan_snapshot.json','action_snapshot.json','diagnostic_events.json','diagnostic_summary.json','simulation_parameters.json']:
   p=root/'simulation'/name
   if not p.exists():p=Path(str(p)+'.gz')
   raw=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()
   artifacts[name]={'path':str(p.relative_to(ROOT)),'sha256':sha(p),'uncompressed_sha256':hashlib.sha256(raw).hexdigest()}
  registry[alias]={'plan_id':payload['revised_operational_plans'][0]['operational_plan_id'],'reference_only_roster_may_exceed_five':True,'payload_copy_sha256':sha(target/'payload.json'),'artifacts':artifacts}
 template=copy.deepcopy(read(BASE/'parents/A/payload.json'));p=template['revised_operational_plans'][0]
 p.update(operational_plan_id='R121_PROTOCOL_TEMPLATE',parent_plan_id=registry['A']['plan_id'],parent_hypothesis_id='R121_PROTOCOL_TEMPLATE',action_timeline=[],deployment_positions_and_directions=[],selected_low_star_operator_ids=sorted(FIXED),validation_card={'status':'NO_TACTIC_NO_SIMULATION','purpose':'Empty schema container; Astra supplies all actions'})
 template['revision_hypothesis'].update(hypothesis_id='R121_PROTOCOL_TEMPLATE',operational_plan_id='R121_PROTOCOL_TEMPLATE',parent_plan_id=registry['A']['plan_id'],tactical_hypothesis='EMPTY PROTOCOL SCAFFOLD ONLY; Astra authors fixed-five timeline',changed_responsibilities=[])
 template['revised_strategic_hypotheses'][0]['hypothesis_id']='R121_PROTOCOL_TEMPLATE'
 write(BASE/'parents/T/payload.json',template);write(BASE/'parents/T/plan.json',p)
 registry['T']={'plan_id':p['operational_plan_id'],'payload_copy_sha256':sha(BASE/'parents/T/payload.json'),'artifacts':{},'no_events':True,'not_a_tactical_parent':'Empty protocol scaffolding, no simulated evidence'}
 write(BASE/'parent_registry_v1.json',registry)
 context=read(old/'input_bundle/template_context.json');context.update(previous_plan_id=p['operational_plan_id'],previous_plan_to_revise=p)
 context['milestone_constraints']={'max_unique_deployed_operator_ids':5,'fixed_operator_ids':sorted(FIXED),'counting_rule':'selected union every DEPLOY ID exactly fixed five'}
 context['current_batch_authority']={'batch':'R121','fixed_operator_ids':sorted(FIXED),'five_rounds':True,'roles':'Astra all tactics; host mechanics/enumeration/gates/archive','initial_reference_idea':'Plume opening, Kroos cross-lane, Midnight clearance/central, Hibiscus supports Steward artillery; suggestion only'}
 context['parent_identity_manifest']={'path':str((BASE/'parent_registry_v1.json').relative_to(ROOT)),'note':'A/B/C historical references; T empty protocol container, no battle events. No splicing evidence.'}
 for name in ['template_context.json','llm_evidence_context.json']:write(BASE/'input_bundle'/name,context)
 write(BASE/'input_bundle/revision_output_schema.json',read(old/'input_bundle/revision_output_schema.json'))
 cfg=read(old/'session_config_v1.json');cfg.update(session_id='r121-five-fixed-astra-low',plan_label='R121',plan_id_prefix='R121_',max_unique_deployed_operators=5,session_root=str(BASE/'session'),facts_source_dir=str(BASE/'input_bundle'),candidate_ledger_path=str(BASE/'candidate_ledger_v1.json'),budget_path=str(BASE/'simulation_budget_v1.json'),authorization_config_path=str(BASE/'model_authorization_v1.json'))
 write(BASE/'session_config_v1.json',cfg)
 extra=['features.apps=false',f'mcp_servers.kimiark.command="{ROOT/".venv/bin/python"}"',f'mcp_servers.kimiark.args=["{BASE/"batch_service.py"}","{BASE/"session_config_v1.json"}"]','mcp_servers.kimiark.tool_timeout_sec=1800','mcp_servers.kimiark.required=true','mcp_servers.kimiark.default_tools_approval_mode="approve"','mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events","inspect_evidence","record_round","search_variants","independent_verify"]']
 write(BASE/'model_authorization_v1.json',{'schema_version':'KIMIARK_CODEX_CLI_AUTHORIZATION_V1','provider':'openai','model':'gpt-6.2-astra','reasoning_effort':'low','features_apps':False,'extra_config_values':extra,'real_cli_starts':{'authorized_real_cli_starts':1,'used_real_cli_starts':0,'automatic_retry':False,'automatic_resume':False},'scope':'R121 fixed-five Kroos/Midnight/Steward/Hibiscus/Plume. One tactical CLI, five tactic/batch/result cycles, no host tactics, no push. Operational500check100PASS100fullsim ceiling reused from recent batches; not numeric quote from latest user.'})
 write(BASE/'candidate_ledger_v1.json',{'schema_version':'KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2','session_id':cfg['session_id'],'stage_id':cfg['stage_id'],'max_check_calls':500,'used_check_calls':0,'max_candidates':100,'used_candidates':0,'checks':[],'attempts':[]})
 write(BASE/'simulation_budget_v1.json',{'schema_version':'KIMIARK_STAGE_SIMULATION_BUDGET_V1','stage_id':cfg['stage_id'],'max_stage_simulations':100,'prior_stage_simulations':0,'started_stage_simulations':0})
 write(BASE/'batch_state.json',{'rounds':[],'variants':[],'stopped':False,'cli_started':0,'independent_runs':[]})
 write(BASE/'batch_constraints.json',{'user_goal':'R8-7 current fixed simulator full WIN','roster':sorted(FIXED),'round_definition':'Astra tactic -> batch tests -> actual evidence -> revised judgment; multiple tests per round','CLI_max':1,'round_max':5,'operational_safety_ceiling':{'check':500,'PASS_candidate':100,'actual_full_simulation':100},'ceiling_provenance':'Conservative reuse of recent batch configuration. User authorized five rounds of batch search without new numerical sim cap.','old_balances_transfer':False,'no_push':True,'head_at_start':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
 index=read(old/'old_action_index.json')
 for directory in [old,last]:
  for path in sorted((directory/'session/candidates').glob('*/simulation/plan_snapshot.json')):
   q=read(path);data={'selected':sorted(q['selected_low_star_operator_ids']),'actions':[{k:a[k] for k in ['action_type','operator_id','frame','tile','direction'] if k in a} for a in q['action_timeline']]}
   key=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();index[key]=str(path.relative_to(ROOT))
 write(BASE/'old_action_index.json',index)
 print({'batch':'R121','fixed_roster':sorted(FIXED),'new_used':{'check':0,'candidate':0,'simulation':0},'model':'gpt-6.2-astra/low','host_tactical_actions_created':0})
if __name__=='__main__':main()
