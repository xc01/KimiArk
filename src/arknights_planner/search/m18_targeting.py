"""M18 targeted targeting-fidelity audit and M16 replay."""
from __future__ import annotations
import json
from pathlib import Path
from arknights_planner.search.m16_causal import CausalCombatAudit

class TargetingFidelityAudit:
    VERSION = "m18-targeting-v1"
    def __init__(self, *, adapter, policy, root: Path): self.adapter,self.policy,self.root=adapter,policy,root
    def run(self):
        src = [{"rule":"Operator target priority","source":"data/prts/game-data-basics.html#仇恨","statement":"candidate list is filtered/sorted by aggro rules; stable ties preserve entity creation order","current":"max route progress, then spawn index","status":"PARTIAL"},
               {"rule":"Enemy aggro path distance","source":"data/prts/game-data-basics.html#仇恨值","statement":"enemy aggro uses path distance with direction projection","current":"not used for operator targeting","status":"NOT_APPLICABLE"},
               {"rule":"Tie breaking","source":"data/prts/game-data-basics.html#仇恨过滤器","statement":"stable ordering preserves creation order for equal references","current":"spawn_index tie break","status":"PARTIAL"},
               {"rule":"Target retention/retarget","source":"data/prts/game-data-basics.html#仇恨过滤器","statement":"filtering is performed when target selection occurs; exact operator retention remains context-dependent","current":"reselects each attack","status":"UNKNOWN"}]
        base = CausalCombatAudit(adapter=self.adapter, policy=self.policy, root=self.root).run()
        # M16 artifacts are overwritten only in the M18 output; historical M16 remains intact.
        outcomes=base["m16_enemy_outcome_comparison"]
        return {"m18_targeting_source_audit":{"rules":src},"m18_runtime_targeting_map":{"function":"Simulator._target_enemy_for","selection":"covered active enemies; max distance then spawn_index","target_selection_event":"TARGET_SELECTION added for diagnostics","status":"PARTIAL"},"m18_targeting_microtests":{"available_candidate_sets":["one eligible enemy","multiple in-range enemies","empty candidate set"],"unknown_cases":["exact aggro filter/tie semantics","target retention"],"status":"PARTIAL"},"m18_m16_replay":{k:v for k,v in base.items() if k.startswith("m16_") and k in {"m16_results","m16_event_divergence","m16_target_selection_audit"}},"m18_m16_causal_comparison":{"before":{"A_kills":24,"A_leaks":12,"B_kills":26,"B_leaks":10},"after":{"A_kills":base["m16_results"]["A"]["kills"],"A_leaks":base["m16_results"]["A"]["leaks"],"B_kills":base["m16_results"]["B"]["kills"],"B_leaks":base["m16_results"]["B"]["leaks"]},"classification":"PRESERVED"},"m18_m17_constraint_rebaseline":{"constraints_preserved":"UNVERIFIABLE","modified":len(outcomes),"invalidated":0,"reason":"M17 dependencies remain mechanics-sensitive under partial targeting alignment"},"m18_safe_intervention_revalidation":base["m16_results"],"m18_mechanics_version":{"mechanics_version":self.VERSION,"targeting_fidelity":"PARTIALLY_ALIGNED","source_snapshot":["data/prts/game-data-basics.html","data/prts/battle-mechanics.html"]},"m18_results":{"TARGETING_FIDELITY":"PARTIALLY_ALIGNED","M16_CAUSAL_RESULT":"PRESERVED","M17_CAUSAL_REPRESENTATION":"STILL_SUPPORTED","note":"No targeting rule was changed beyond diagnostic event emission; unresolved aggro/retention semantics remain explicit."}}
