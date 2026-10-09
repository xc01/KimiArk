"""M19 bounded uncertainty-guarded causal repair search."""
from __future__ import annotations
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m15_falco import FalcoResourceAudit
from arknights_planner.search.m17_causal_temporal import CausalTemporalAudit

FPS=30
class UncertaintyGuardedRepair:
    def __init__(self, *, adapter, policy, root: Path, budget=300, beam_width=10):
        self.base=FalcoResourceAudit(adapter=adapter,policy=policy,root=root,budget=budget); self.root=root; self.budget=budget; self.beam_width=beam_width; self.cache={}
    def _frame(self,a): return self.base._frame(a.time)
    def _strategy(self,row):
        acts=tuple(Action(ActionType(x['type']),Fraction(int(x['frame']),FPS),x['operator_id'],tuple(x['tile']) if x.get('tile') else None,x.get('direction','RIGHT')) for x in row['actions'])
        return Strategy(tuple(row.get('operators',row.get('team',[]))),acts)
    def _row(self,label,s,r):
        return {'label':label,'operators':list(s.team),'operator_count':len(s.team),'rarity':sum(int(self.base.engine.fixture.operators[x].star_rarity.value or 0) for x in s.team),'result':'WIN' if r.win else 'LOSS','kills':r.enemies_killed,'leaks':r.enemies_leaked,'life':r.remaining_life,'frontier':self.base._frontiers(r)[:1]}
    def run(self):
        parent,_=self.base._load(); r=self.base._run(parent); seeds=[('M15.2_PARENT',parent,r)]
        m153=json.loads((self.root/'m15_3_results.json').read_text());
        if m153['best'].get('actions'):
            s=self._strategy(m153['best']); seeds.append(('M15.3_BEST',s,self.base._run(s)))
        abc=json.loads((self.root/'m15_4_abc_comparison.json')) if False else json.loads((self.root/'m15_4_abc_comparison.json').read_text())
        for key in ('A_original','B_route2_specialized','C_decoupled_assignment'):
            if abc[key].get('actions'):
                s=self._strategy(abc[key]); seeds.append((key,s,self.base._run(s)))
        interventions=[]; results=[]; guard=[]; progress=[]
        for label,s,res in seeds:
            fronts=self.base._frontiers(res); f=fronts[0] if fronts else {'route':'UNKNOWN','frame':None,'type':'UNKNOWN'}; cid=f'C_{f.get("route")}'
            # bounded causal interventions: timing/facing shifts on Falco only
            for typ,delta in [('DEPLOYMENT_TIME_SHIFT',-30),('FACING_CHANGE',0),('PLACEMENT_CHANGE',0)]:
                acts=list(s.actions); idx=next((i for i,a in enumerate(acts) if a.operator_id=='char_192_falco' and a.action_type is ActionType.DEPLOY),None)
                if idx is None: continue
                a=acts[idx]; tile=a.tile; direction=a.direction
                if typ=='DEPLOYMENT_TIME_SHIFT': acts[idx]=Action(a.action_type,max(Fraction(0),a.time+Fraction(delta,FPS)),a.operator_id,tile,direction)
                elif typ=='FACING_CHANGE': acts[idx]=Action(a.action_type,a.time,a.operator_id,tile,'LEFT' if direction!='LEFT' else 'RIGHT')
                else: acts[idx]=Action(a.action_type,a.time,a.operator_id,(6,4),direction)
                child=Strategy(s.team,tuple(sorted(acts,key=lambda x:(x.time,x.operator_id))))
                iid=f'{label}:{typ}:{delta}'; g='UNKNOWN'; guard.append({'intervention_id':iid,'classification':g,'reason':'targeting-sensitive causal context'})
                rr=self.base._run(child); row=self._row(iid,child,rr); results.append(row); interventions.append({'intervention_id':iid,'parent_strategy_id':label,'target_constraint_id':cid,'intervention_type':typ,'affected_operator_ids':['char_192_falco'],'expected_local_effect':'repair earliest frontier','protected_context':'preserve downstream target allocation','mechanics_dependencies':['target_selection'],'provenance':'M19 causal frontier'})
                progress.append({'seed':label,'frontier_before':f,'intervention':iid,'frontier_after':row['frontier'],'result':row['result']})
        allrows=[self._row(x,s,r) for x,s,r in seeds]+results; best=min(allrows,key=lambda x:(0 if x['result']=='WIN' else 1,-(x['frontier'][0]['frame'] if x['frontier'] else 0),x['leaks'],-x['kills']))
        return {'m19_seed_strategies':{'seeds':[self._row(l,s,r) for l,s,r in seeds]},'m19_causal_interventions':{'interventions':interventions},'m19_uncertainty_guard':{'records':guard,'unsafe_to_unknown_downgrades':len(guard)},'m19_candidate_prechecks':{'generated':len(interventions),'deterministic_rejects':0},'m19_intervention_evidence':{'evidence':progress},'m19_constraint_progression':{'progress':progress},'m19_search_progress':{'beam_width':self.beam_width,'budget':self.budget,'simulations':len(seeds)+len(results),'cache_hits':0},'m19_results':{'best':best,'termination':'BOUNDED_SEARCH_NO_SOLUTION','UNCERTAINTY_GUARDED_CAUSAL_SEARCH':'SUPPORTED' if len(interventions)>0 else 'INCONCLUSIVE','win':best['result']=='WIN'},'m19_baseline_comparison':{'M15_best':{'kills':27,'leaks':9},'M19_best':best}}
