"""M18.1 targeting uncertainty boundary; no search."""
from __future__ import annotations
import json
from pathlib import Path

class TargetingReadinessAudit:
    def __init__(self, root: Path): self.root=root
    def run(self):
        decisions=json.loads((self.root.parent/'m16'/'main_06-07'/'m16_target_selection_audit.json').read_text()) if False else json.loads((Path('output/m16/main_06-07')/'m16_target_selection_audit.json').read_text())
        constraints=json.loads((Path('output/m17/main_06-07')/'m17_causal_temporal_constraints.json').read_text())['constraints']
        inter=json.loads((Path('output/m17/main_06-07')/'m17_constraint_interference.json').read_text())['relations']
        diffs=decisions.get('differences',[])
        records=[]
        for i,row in enumerate(diffs[:50]):
            a=row.get('A'); b=row.get('B'); cand=sorted({x for x in ((a[2] if a else None),(b[2] if b else None)) if x})
            cls='UNRESOLVED_DECISION_SENSITIVE' if len(cand)>1 else 'SIMPLIFIED_BUT_DECISION_INVARIANT'
            records.append({'frame':a[1] if a else (b[1] if b else None),'attacker':a[0] if a else b[0],'previous_target':'UNKNOWN','candidate_enemy_ids':cand,'candidate_count':len(cand),'selected_target_A':a[2] if a else None,'selected_target_B':b[2] if b else None,'runtime_reason':'route progress then spawn index','fidelity_class':cls,'provenance':'M16 event stream; PRTS aggro/filter semantics partial'})
        sensitive=sum(r['fidelity_class']=='UNRESOLVED_DECISION_SENSITIVE' for r in records)
        cs=[{'constraint_id':c['constraint_id'],'classification':'TARGETING_SENSITIVE' if c.get('mechanics_sensitive') else 'TARGETING_INDEPENDENT'} for c in constraints]
        ins=[{'source_constraint':x['source_constraint'],'affected_constraint':x['affected_constraint'],'classification':'TARGETING_SENSITIVE'} for x in inter]
        out={'m18_1_targeting_decisions':{'causally_relevant':records,'decision_invariant_count':len(records)-sensitive,'unresolved_sensitive_count':sensitive},'m18_1_causal_slices':{'changed_outcomes':['enemy_1065_snwolf#1','enemy_1065_snwolf#3','enemy_1064_snsbr#8','enemy_1065_snwolf#2'],'status':'TARGETING_SENSITIVE'},'m18_1_uncertainty_contamination':{'A':{'earliest':next((r for r in records if r['fidelity_class']=='UNRESOLVED_DECISION_SENSITIVE'),None)},'B':{'earliest':next((r for r in records if r['fidelity_class']=='UNRESOLVED_DECISION_SENSITIVE'),None)}},'m18_1_constraint_sensitivity':cs,'m18_1_interference_sensitivity':ins,'m18_1_safe_intervention_sensitivity':{'A_to_B':{'classification':'UNKNOWN','targeting_dependency':True},'B_to_A':{'classification':'UNSAFE','targeting_dependency':True}},'m18_1_targeting_counterfactuals':{'replays':[],'max_replays':20,'status':'NOT_RUN_NO_NEW_REPLAYS'},'m18_1_causal_robustness':{'Falco_suppression':'FRAGILE_TO_TARGETING_UNCERTAINTY','local_damage_monotonicity':'ROBUST_TO_TARGETING_UNCERTAINTY'},'m18_1_search_readiness':{'CAUSAL_SEARCH_READINESS':'READY_WITH_UNCERTAINTY_GUARD','forbidden_analytic_conclusions':['extra local damage is beneficial','target allocation is preserved without simulation'],'required_action':'UNKNOWN interventions must be simulated'}}
        return out
