import json
from copy import deepcopy
from pathlib import Path
from compile_r8_1_lowstar_c2_plan_v1 import compile_plan
ROOT=Path(__file__).resolve().parent

def write_case(tmp_path, parsed, evidence, actions):
 plan=deepcopy(parsed['revised_operational_plans'][0])
 plan['action_timeline']=deepcopy(actions)
 plan['deployment_positions_and_directions']=deepcopy(actions)
 plan['declared_range_checks']=[]
 (tmp_path/'llm_evidence_context.json').write_text(json.dumps(evidence))
 (tmp_path/'llm_structured_output.json').write_text(json.dumps({'revised_operational_plans':[plan]}))
 return compile_plan(tmp_path)

def full_slot_case(tmp_path, third=None):
 source=ROOT/'output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli'
 evidence=json.loads((source/'llm_evidence_context.json').read_text())
 parsed=json.loads((source/'llm_structured_output.json').read_text())
 active=evidence['stage_active_facts'];blocked={tuple(x) for x in active['roadblock_tiles_col_row']}
 ground=[tuple(x) for x in active['deployable_ground_tiles_col_row'] if tuple(x) not in blocked]
 high=[tuple(x) for x in active['deployable_high_ground_tiles_col_row'] if tuple(x) not in blocked]
 choices=[('char_123_fang',ground[0]),('char_122_beagle',ground[1]),third or ('char_124_kroos',high[0])]
 actions=[{'action_type':'DEPLOY','operator_id':oid,'frame':i,'tile':[tile[1],tile[0]],'direction':'RIGHT'} for i,(oid,tile) in enumerate(choices)]
 evidence['stage_options'].update(initial_cost=99,deployment_limit=2)
 return write_case(tmp_path,parsed,evidence,actions)

def test_robot_can_deploy_when_normal_slots_full_in_complete_compiler(tmp_path):
 source=ROOT/'output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli'
 evidence=json.loads((source/'llm_evidence_context.json').read_text())
 high=[tuple(x) for x in evidence['stage_active_facts']['deployable_high_ground_tiles_col_row']]
 certificate=full_slot_case(tmp_path,('char_285_medic2',high[0]))
 conflicts=certificate['conflicts']
 assert not any('deployed_count' in c for c in conflicts),conflicts

def test_normal_operator_rejected_when_normal_slots_full_in_complete_compiler(tmp_path):
 certificate=full_slot_case(tmp_path)
 assert any(c.get('deployed_count')==2 and c.get('limit')==2 for c in certificate['conflicts']),certificate['conflicts']

def test_one_star_does_not_consume_normal_deployment_slot(tmp_path):
 source=ROOT/'output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli'
 evidence=json.loads((source/'llm_evidence_context.json').read_text())
 parsed=json.loads((source/'llm_structured_output.json').read_text())
 active=evidence['stage_active_facts'];blocked={tuple(x) for x in active['roadblock_tiles_col_row']}
 ground=[tuple(x) for x in active['deployable_ground_tiles_col_row'] if tuple(x) not in blocked]
 high=[tuple(x) for x in active['deployable_high_ground_tiles_col_row'] if tuple(x) not in blocked]
 actions=[]
 for i,(oid,tile) in enumerate([('char_123_fang',ground[0]),('char_285_medic2',high[0]),('char_122_beagle',ground[1])]):
  actions.append({'action_type':'DEPLOY','operator_id':oid,'frame':i,'tile':[tile[1],tile[0]],'direction':'RIGHT'})
 certificate=write_case(tmp_path,parsed,evidence,actions)
 assert not any('deployed_count' in c for c in certificate['conflicts']),certificate['conflicts']

def test_retreat_restores_normal_deployment_slot(tmp_path):
 source=ROOT/'output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli'
 evidence=json.loads((source/'llm_evidence_context.json').read_text())
 parsed=json.loads((source/'llm_structured_output.json').read_text())
 active=evidence['stage_active_facts'];blocked={tuple(x) for x in active['roadblock_tiles_col_row']}
 ground=[tuple(x) for x in active['deployable_ground_tiles_col_row'] if tuple(x) not in blocked]
 high=[tuple(x) for x in active['deployable_high_ground_tiles_col_row'] if tuple(x) not in blocked]
 actions=[]
 specs=[('char_123_fang',ground[0]),('char_122_beagle',ground[1]),('RETREAT',None),('char_124_kroos',high[0])]
 frame=0
 for i,(oid,tile) in enumerate(specs):
  kind='RETREAT' if oid=='RETREAT' else 'DEPLOY'
  actions.append({'action_type':kind,'operator_id':oid if oid!='RETREAT' else 'char_123_fang','frame':frame,'direction':'RIGHT',**({'tile':[tile[1],tile[0]]} if tile else {})})
  frame+=1
 certificate=write_case(tmp_path,parsed,evidence,actions)
 assert not any(c.get('deployed_count')==2 and c.get('limit')==2 for c in certificate['conflicts']),certificate['conflicts']

def test_missing_rarity_does_not_bypass_deployment_limit(tmp_path):
 source=ROOT/'output/r8_1_gpt_tactical_batch_v1/r8_1_c7_cli'
 evidence=json.loads((source/'llm_evidence_context.json').read_text())
 parsed=json.loads((source/'llm_structured_output.json').read_text())
 missing='char_missing_rarity'
 evidence['normal_low_star_catalog'].append({'operator_id':missing,'name':'Missing Rarity','identity':{'position':'RANGED'},'qualification':{'normal_mode':True},'stats':{'cost':1,'redeploy_time':70},'range':{'cells':[]},'runtime_support':{}})
 active=evidence['stage_active_facts'];blocked={tuple(x) for x in active['roadblock_tiles_col_row']}
 ground=[tuple(x) for x in active['deployable_ground_tiles_col_row'] if tuple(x) not in blocked]
 high=[tuple(x) for x in active['deployable_high_ground_tiles_col_row'] if tuple(x) not in blocked]
 choices=[('char_123_fang',ground[0]),('char_122_beagle',ground[1]),(missing,high[0])]
 actions=[{'action_type':'DEPLOY','operator_id':oid,'frame':i,'tile':[tile[1],tile[0]],'direction':'RIGHT'} for i,(oid,tile) in enumerate(choices)]
 evidence['stage_options'].update(initial_cost=99,deployment_limit=2)
 certificate=write_case(tmp_path,parsed,evidence,actions)
 reasons={r for c in certificate['conflicts'] if c.get('operator_id')==missing for r in c.get('reasons',[])}
 assert 'MISSING_OR_INVALID_RARITY' in reasons,certificate['conflicts']
 assert not any(c.get('operator_id')==missing and 'deployed_count' in c for c in certificate['conflicts']),certificate['conflicts']
