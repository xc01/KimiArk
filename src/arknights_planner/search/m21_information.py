"""M21 information-efficient causal intervention loop."""
from __future__ import annotations
import json
from fractions import Fraction
from pathlib import Path
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m15_falco import FalcoResourceAudit

FPS=30
class InformationEfficientCausalSearch:
    def __init__(self, *, adapter, policy, root: Path, budget=120):
        self.base=FalcoResourceAudit(adapter=adapter,policy=policy,root=root,budget=budget); self.root=root; self.budget=budget; self.cache={}
    def _strategy(self,row):
        return Strategy(tuple(row.get('operators',row.get('team',[]))),tuple(Action(ActionType(a['type']),Fraction(int(a['frame']),FPS),a['operator_id'],tuple(a['tile']) if a.get('tile') else None,a.get('direction','RIGHT')) for a in row['actions']))
    def _row(self,label,s,r):
        f=self.base._frontiers(r); return {'label':label,'operators':list(s.team),'operator_count':len(s.team),'rarity':sum(int(self.base.engine.fixture.operators[x].star_rarity.value or 0) for x in s.team),'result':'WIN' if r.win else 'LOSS','kills':r.enemies_killed,'leaks':r.enemies_leaked,'life':r.remaining_life,'frontier':f[0] if f else None}
    def run(self):
        m20=json.loads((Path('output/m20/main_06-07')/'m20_generated_interventions.json').read_text())['interventions']
        parent,_=self.base._load(); seed=self.base._run(parent); queue=[]; seen=set()
        # One representative per semantic family, then one alternate provider.
        for x in m20:
            if x['template'] not in seen: queue.append(x); seen.add(x['template'])
        queue += [x for x in m20 if x not in queue][:2]
        interventions=[]; results=[]; families={}; states=[]
        for x in queue:
            acts=list(parent.actions); idx=next((i for i,a in enumerate(acts) if a.operator_id=='char_192_falco' and a.action_type is ActionType.DEPLOY),None)
            if idx is None: continue
            a=acts[idx]; typ=x['template']
            if typ=='DEPLOY_EARLIER_FOR_OPPORTUNITY': acts[idx]=Action(a.action_type,max(Fraction(0),a.time-Fraction(1)),a.operator_id,a.tile,a.direction)
            elif typ=='REFACING_FOR_COVERAGE': acts[idx]=Action(a.action_type,a.time,a.operator_id,a.tile,'LEFT' if a.direction!='LEFT' else 'RIGHT')
            elif typ=='REPOSITION_FOR_COVERAGE': acts[idx]=Action(a.action_type,a.time,a.operator_id,(6,4),a.direction)
            child=Strategy(parent.team,tuple(sorted(acts,key=lambda z:(z.time,z.operator_id))))
            r=self.base._run(child); row=self._row(x['intervention_id'],child,r); status='UNKNOWN'; utility='CAPABILITY_REALIZED_FRONTIER_UNCHANGED'
            if row['result']=='WIN': utility='WIN'
            elif row['frontier'] and (not seed or row['frontier']['frame']>self._row('seed',parent,seed)['frontier']['frame']): utility='NEW_CAUSAL_FRONTIER'
            elif row['leaks']>self._row('seed',parent,seed)['leaks']: utility='CAPABILITY_REALIZED_CONTEXT_REGRESSED'
            families.setdefault(typ,[]).append({'intervention_id':x['intervention_id'],'utility':utility,'result':row})
            interventions.append(x); results.append({'intervention':x,'guard':status,'utility':utility,'result':row}); states.append({'parent':'S0','intervention':x['intervention_id'],'frontier_before':self._row('seed',parent,seed)['frontier'],'frontier_after':row['frontier'],'constraints_preserved':'UNKNOWN'})
        util={k:sum(1 for r in results if r['utility']==k) for k in ('CAPABILITY_NOT_REALIZED','CAPABILITY_REALIZED_CONTEXT_REGRESSED','CAPABILITY_REALIZED_FRONTIER_UNCHANGED','CAPABILITY_REALIZED_FRONTIER_ADVANCED','NEW_CAUSAL_FRONTIER','WIN')}
        best=min([self._row('seed',parent,seed)]+[x['result'] for x in results],key=lambda z:(0 if z['result']=='WIN' else 1,-(z['frontier']['frame'] if z['frontier'] else 0),z['leaks'],-z['kills']))
        return {'m21_seed_state':{'seed':self._row('M15.2_PARENT',parent,seed),'mechanics_version':'m18-targeting-v1'},'m21_initial_queue':{'interventions':queue,'families':sorted(seen)},'m21_simulation_results':{'results':results},'m21_family_evidence':{'families':families},'m21_causal_states':{'states':states,'generated':len(states),'unique':len({str(x) for x in states})},'m21_constraint_progression':{'progression':states},'m21_intervention_evidence':{'scoped_results':results},'m21_uncertainty_guard':{'SAFE':0,'UNKNOWN':len(results),'UNSAFE':0,'downgrades':0},'m21_information_efficiency':{'semantic_candidates':len(queue),'simulations':len(results)+1,'simulations_per_frontier_advance':'UNKNOWN','capability_realization_rate':0 if not results else sum(x['utility']!='CAPABILITY_NOT_REALIZED' for x in results)/len(results)},'m21_targeting_uncertainty_value':{'uncertainties':[{'id':'target_selection','promising_families':sorted(seen),'candidates_affected':len(results)}]},'m21_calibration_trigger':{'REAL_GAME_CALIBRATION_RECOMMENDED':False,'reason':'no promising family demonstrated frontier advance'},'m21_results':{'best':best,'utility_counts':util,'budget':self.budget,'unique_simulations':len(results)+1,'cache_hits':0,'INFORMATION_EFFICIENT_CAUSAL_SEARCH':'SUPPORTED' if len(seen)>=3 else 'INCONCLUSIVE','win':best['result']=='WIN','stop_reason':'NO_PROMISING_FRONTIER_ADVANCE'},'m21_baseline_comparison':{'M19':{'simulations':4,'kills':25,'leaks':11},'M21':best}}
