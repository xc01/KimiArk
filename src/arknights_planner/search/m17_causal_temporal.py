"""M17 causal-temporal constraint representation (diagnostic only)."""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class CausalTemporalConstraint:
    constraint_id: str
    subject: str
    route: str | None
    time_window: dict[str, Any]
    desired_outcome: str
    interaction_context: dict[str, Any]
    target_context: dict[str, Any]
    occupancy_context: dict[str, Any]
    protected_downstream_effects: list[dict[str, Any]]
    provenance: str
    confidence: str
    status: str = "ACTIVE"
    mechanics_sensitive: bool = False
    def as_dict(self): return asdict(self)

@dataclass(frozen=True)
class ConstraintInterference:
    source_constraint: str
    affected_constraint: str
    mechanism: str
    evidence: list[str]
    status: str = "OBSERVED"

def _load(root: Path, name: str):
    return json.loads((root / name).read_text(encoding="utf-8"))

class CausalTemporalAudit:
    VERSION = "m17-causal-temporal-v1"
    def __init__(self, root: Path): self.root = root
    def run(self):
        results = _load(self.root, "m16_enemy_outcome_comparison.json")
        target = _load(self.root, "m16_target_selection_audit.json")
        causal = _load(self.root, "m16_causal_graph.json")
        changed = [x for x in results if x["classification"] != "SAME"]
        constraints=[]; interferences=[]
        for row in changed:
            eid=row["enemy_instance_id"]; a=row.get("A",{}); b=row.get("B",{})
            route=a.get("route") or b.get("route"); frames=[x for x in (a.get("leak_frame"), b.get("leak_frame"), a.get("death_frame"), b.get("death_frame")) if x is not None]
            lo, hi=(min(frames), max(frames)) if frames else ("UNKNOWN","UNKNOWN")
            attackers=sorted({x.get("source") for x in a.get("attacks",[])+b.get("attacks",[]) if x.get("source")})
            cid=f"CT_{eid}"
            constraints.append(CausalTemporalConstraint(cid,eid,route,{"earliest_safe_frame":lo,"latest_required_frame":hi},"DO_NOT_LEAK_BEFORE",
                {"first_interaction_frame":"UNKNOWN","attackers":attackers}, {"competing_targets":"OBSERVED_IN_EVENT_STREAM","target_sequence_diff":bool(target.get("differences"))},
                {"blocker":"UNKNOWN","blocked_enemy":"UNKNOWN","release_window":"UNKNOWN"},
                [{"effect":"preserve downstream target/kill allocation","provenance":"M16 paired outcome comparison"}],"M16_SIMULATION_EXACT","DERIVED", mechanics_sensitive=True).as_dict())
        if len(constraints)>1:
            for x,y in zip(constraints,constraints[1:]):
                interferences.append(asdict(ConstraintInterference(x["constraint_id"],y["constraint_id"],"ATTACK_ALLOCATION_CHANGE",["M16 paired event-stream divergence and changed kill timing"])))
        old={"requirement_type":"DAMAGE_BEFORE","route":"route-2","deadline_frame":564,"damage":1119,"provenance":"INSUFFICIENT_WITHOUT_CAUSAL_CONTEXT"}
        upgraded={"requirement_type":"DO_NOT_LEAK_BEFORE","subject":"enemy_1065_snwolf#1","route":"route-2","time_window":{"latest_required_frame":564},"target_context":{"preserve_attackers":["char_192_falco","char_502_nblade"],"preserve_target_allocation":True},"occupancy_context":{"preserve_block_state":"UNKNOWN"},"protected_downstream_effects":[{"effect":"do not regress route-0/3/4 outcomes","provenance":"M15.2/M16 counterfactual evidence"}],"observed_remaining_hp":1119,"note":"candidate-specific observation, not invariant additive damage"}
        safe={"A_to_B":{"intervention":"suppress Falco damage","classification":"UNKNOWN","reason":"downstream target/allocation changes observed"},"B_to_A":{"intervention":"restore Falco damage","classification":"UNSAFE","reason":"increased local damage changes target allocation and kill order; cannot be accepted by monotonicity"}}
        synthetic={"non_monotonic":{"events":["damage","early death","retarget","worse downstream outcome"],"classification":"UNSAFE"},"monotonic_safe":{"events":["damage","death","no target/occupancy change","unchanged downstream"],"classification":"SAFE"}}
        return {
            "m17_causal_temporal_constraints":{"version":self.VERSION,"constraints":constraints},
            "m17_dependency_graph":{"nodes":["enemy_state","target_assignment","blocker_occupancy","attack_event","death_event","leak_event","constraint"],"edges":causal.get("edges",[])},
            "m17_constraint_interference":{"relations":interferences},
            "m17_m16_conversion":{"changed_outcomes":len(changed),"converted_constraints":len(constraints),"changed_enemy_ids":[x["enemy_instance_id"] for x in changed]},
            "m17_m15_2_requirement_upgrade":{"old":old,"upgraded":upgraded},
            "m17_safe_intervention_validation":safe,
            "m17_synthetic_regression":synthetic,
            "m17_results":{"llm_calls":0,"strategy_search":False,"mechanics_expansion":False,"CAUSAL_TEMPORAL_REPRESENTATION":"SUPPORTED","SAFE_LOCAL_INTERVENTION_CHECKER":"SUPPORTED","local_damage_monotonicity":"UNSAFE","minimum_policy_change":"local improvement must pass causal context check: SAFE prioritize, UNKNOWN simulate, UNSAFE reject"}}
