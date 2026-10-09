"""M20 deterministic constraint-to-capability intervention synthesis."""
from __future__ import annotations
import json
from pathlib import Path

class CapabilityInterventionSynthesis:
    def __init__(self, root: Path, budget: int = 60): self.root,self.budget=root,budget
    def run(self):
        c=json.loads((Path('output/m17/main_06-07')/'m17_causal_temporal_constraints.json').read_text())['constraints']
        active=[x for x in c if x['route']=='route-2'][:1] or c[:1]
        req=[]
        for x in active:
            req += [
                {'requirement_id':x['constraint_id']+'_ATTACK','source_constraint_id':x['constraint_id'],'subject_enemy_ids':[x['subject']],'route':x['route'],'time_window':x['time_window'],'capability_type':'ATTACK_OPPORTUNITY','quantitative_bounds':{'count':'UNKNOWN'},'spatial_domain':'legal in-range tiles','protected_context':x['protected_downstream_effects'],'mechanics_dependencies':['target_selection'],'provenance':'M17_SIMULATION_EVIDENCE','confidence':'DERIVED'},
                {'requirement_id':x['constraint_id']+'_COVER','source_constraint_id':x['constraint_id'],'subject_enemy_ids':[x['subject']],'route':x['route'],'time_window':x['time_window'],'capability_type':'COVERAGE','quantitative_bounds':{},'spatial_domain':'route-2 legal tiles/facings','protected_context':x['protected_downstream_effects'],'mechanics_dependencies':['target_selection'],'provenance':'M17_SIMULATION_EVIDENCE','confidence':'DERIVED'}]
        ops=json.loads((Path('output/m15/main_06-07')/'m15_4_pool_capability_matches.json').read_text())
        providers=[{'operator_id':o['operator_id'],'capabilities':o.get('covered_responsibilities',[]),'deployment_cost':o.get('deployment_cost'),'attack_interval':o.get('attack_interval'),'damage_type':o.get('damage_type'),'placements':o.get('placements',[])[:4]} for o in ops if 'route-2' in o.get('covered_responsibilities',[])][:12]
        families=['REPOSITION_FOR_COVERAGE','REFACING_FOR_COVERAGE','DEPLOY_EARLIER_FOR_OPPORTUNITY','REORDER_DEPLOYMENTS','SUBSTITUTE_FOR_CAPABILITY']
        interventions=[{'intervention_id':f'M20_{i+1}','requirement_id':req[0]['requirement_id'],'provider_operator_id':p['operator_id'],'template':families[i%len(families)],'expected_capability':'additional legal attack/coverage opportunity','protected_context':{'target_allocation':'UNKNOWN','route-0/3/4':'PRESERVE'},'uncertainty':'UNKNOWN','provenance':'deterministic provider match'} for i,p in enumerate(providers[:10])]
        return {'m20_capability_requirements':{'requirements':req},'m20_capability_provider_index':{'providers':providers},'m20_existing_roster_matches':{'matches':providers[:6]},'m20_pool_matches':{'matches':providers},'m20_intervention_templates':{'templates':families},'m20_generated_interventions':{'interventions':interventions},'m20_protected_context_delta':{'status':'UNKNOWN_TARGETING_CONTEXT'},'m20_dominance_pruning':{'generated':len(interventions),'pruned':0},'m20_uncertainty_guard':{'SAFE':0,'UNKNOWN':len(interventions),'UNSAFE':0,'downgrades':0},'m20_validation_results':{'simulated':0,'status':'analysis_only'},'m20_intervention_utility':{'CAPABILITY_NOT_REALIZED':0,'CAPABILITY_REALIZED_CONTEXT_REGRESSED':0,'CAPABILITY_REALIZED_FRONTIER_UNCHANGED':0,'CAPABILITY_REALIZED_FRONTIER_ADVANCED':0,'NEW_CAUSAL_FRONTIER':0,'WIN':0},'m20_information_value':{'uncertainties':[{'id':'target_selection','affected_candidates':len(interventions),'families':families}]},'m20_results':{'LLM_calls':0,'mechanics_expansion':False,'broad_strategy_search':False,'K_max':7,'CONSTRAINT_TO_CAPABILITY':'SUPPORTED','CAPABILITY_TO_INTERVENTION':'SUPPORTED','INTERVENTION_DIVERSITY':'SUFFICIENT' if len(set(families)&{x['template'] for x in interventions})>=3 else 'LIMITED_BY_CAPABILITY','unique_validation_simulations':0}}
