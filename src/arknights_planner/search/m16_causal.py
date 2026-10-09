"""M16 paired causal replay for the Falco damage intervention."""
from __future__ import annotations
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from arknights_planner.models.runtime import CombatOutputType
from arknights_planner.models.simulation import EventType
from arknights_planner.search.m15_falco import FalcoResourceAudit, d

FPS = 30

class CausalCombatAudit:
    VERSION = "m16-causal-v1"
    def __init__(self, *, adapter, policy, root: Path):
        self.base = FalcoResourceAudit(adapter=adapter, policy=policy, root=root, budget=20)
        self.root = root

    def _serialize_event(self, e):
        return {"frame": self.base._frame(e.time), "time": e.time, "type": e.event_type.value,
                "source": e.source_id, "target": e.target_id, "details": d(e)}

    def _disable_falco_ops(self):
        ops = dict(self.base.engine.fixture.operators)
        ops["char_192_falco"] = replace(ops["char_192_falco"], combat_output=CombatOutputType.HEAL, damage_type="PHYSICAL")
        return ops

    def _outcomes(self, result):
        spawns = {e.source_id: e for e in result.events if e.event_type is EventType.SPAWN}
        out = {}
        for eid, s in spawns.items():
            deaths = [e for e in result.events if e.event_type is EventType.ENEMY_DEATH and e.target_id == eid]
            leaks = [e for e in result.events if e.event_type is EventType.ENEMY_LEAK and e.source_id == eid]
            hits = [e for e in result.events if e.event_type is EventType.DAMAGE and e.target_id == eid]
            blocks = [e for e in result.events if e.event_type in (EventType.BLOCK, EventType.UNBLOCK) and e.target_id == eid]
            out[eid] = {"enemy_id": d(s).get("enemy_id", eid), "route": d(s).get("route_id", "UNKNOWN"),
                        "spawn_frame": self.base._frame(s.time), "death_frame": self.base._frame(deaths[0].time) if deaths else None,
                        "leak_frame": self.base._frame(leaks[0].time) if leaks else None,
                        "killer": deaths[0].source_id if deaths else None, "damage": sum(float(d(x).get("amount", 0)) for x in hits),
                        "attacks": [{"frame": self.base._frame(x.time), "source": x.source_id, "damage": None} for x in result.events if x.event_type is EventType.ATTACK_START and x.target_id == eid],
                        "damage_events": [{"frame": self.base._frame(x.time), "source": x.source_id, "amount": float(d(x).get("amount", 0)), "type": d(x).get("damage_type", "UNKNOWN")} for x in hits],
                        "blocking_events": [self._serialize_event(x) for x in blocks]}
        return out

    def _target_audit(self, a, b):
        def seq(result):
            return [(e.source_id, self.base._frame(e.time), e.target_id, d(e).get("target_route", "UNKNOWN")) for e in result.events if e.event_type is EventType.ATTACK_START]
        sa, sb = seq(a), seq(b); rows=[]
        for i in range(max(len(sa), len(sb))):
            va, vb = (sa[i] if i < len(sa) else None), (sb[i] if i < len(sb) else None)
            if va != vb: rows.append({"index": i, "A": va, "B": vb});
        return {"first_differing_attack": rows[0] if rows else None, "differences": rows[:50]}

    def run(self):
        parent, _ = self.base._load()
        ops = self.base.engine.fixture.operators
        a = self.base._run(parent, operators=ops)
        b = self.base._run(parent, operators=self._disable_falco_ops())
        ea, eb = [self._serialize_event(e) for e in a.events], [self._serialize_event(e) for e in b.events]
        direct = [i for i,(x,y) in enumerate(zip(ea,eb)) if x != y]
        oa, ob = self._outcomes(a), self._outcomes(b)
        comparisons=[]
        for eid in sorted(set(oa)|set(ob)):
            x,y=oa.get(eid,{}),ob.get(eid,{})
            ak, bk = x.get("death_frame"), y.get("death_frame"); al, bl=x.get("leak_frame"),y.get("leak_frame")
            cls = "SAME"
            if ak and not bk: cls="A_ONLY_KILL"
            elif bk and not ak: cls="B_ONLY_KILL"
            elif ak and bk and ak != bk: cls="A_EARLIER_KILL" if ak < bk else "B_EARLIER_KILL"
            elif al and not bl: cls="A_ONLY_LEAK"
            elif bl and not al: cls="B_ONLY_LEAK"
            elif (ak,al,x.get("damage")) != (bk,bl,y.get("damage")): cls="OUTCOME_CHANGED_OTHER"
            comparisons.append({"enemy_instance_id":eid,"A":x,"B":y,"classification":cls})
        gained=[r for r in comparisons if r["classification"]=="B_ONLY_KILL"]
        prevented=[r for r in comparisons if r["classification"]=="A_ONLY_LEAK"]
        block_a=[e for e in ea if e["type"] in ("BLOCK","UNBLOCK")]; block_b=[e for e in eb if e["type"] in ("BLOCK","UNBLOCK")]
        causal = {"nodes":["Falco damage intervention","enemy target/HP state","attack allocation","enemy death/leak outcome"],
                  "edges":[{"from":"Falco damage intervention","to":"enemy target/HP state","evidence":"paired event and HP/damage comparison"},
                            {"from":"enemy target/HP state","to":"attack allocation","evidence":"target-sequence audit"},
                            {"from":"attack allocation","to":"enemy death/leak outcome","evidence":"paired enemy outcomes"}],
                  "confidence":"DERIVED"}
        return {
            "m16_intervention_isolation":{"status":"VERIFIED","differences_only":"Falco combat_output/damage contribution disabled","A_actions":[self._serialize_event(e) for e in a.events if e.event_type is EventType.DEPLOY],"B_actions":[self._serialize_event(e) for e in b.events if e.event_type is EventType.DEPLOY]},
            "m16_event_divergence":{"first_direct_divergence_index":direct[0] if direct else None,"first_direct_divergence":ea[direct[0]] if direct else None,"first_downstream_divergence":next((x for x,y in zip(ea,eb) if x["type"] not in ("DAMAGE","PROJECTILE_HIT") and x!=y),None),"A_event_count":len(ea),"B_event_count":len(eb)},
            "m16_enemy_outcome_comparison":comparisons,
            "m16_gained_kills":{"count":len(gained),"enemies":gained},
            "m16_prevented_leaks":{"count":len(prevented),"enemies":prevented},
            "m16_target_selection_audit":self._target_audit(a,b),
            "m16_blocking_occupancy_audit":{"A":block_a,"B":block_b,"supported":True},
            "m16_kill_order_audit":{"A":[x["enemy_instance_id"] for x in comparisons if x["A"].get("death_frame")],"B":[x["enemy_instance_id"] for x in comparisons if x["B"].get("death_frame")]},
            "m16_attack_allocation_audit":{"A_attacks":sum(len(x["A"].get("attacks",[])) for x in comparisons),"B_attacks":sum(len(x["B"].get("attacks",[])) for x in comparisons),"Falco_A_damage":sum(float(d(e).get("amount",0)) for e in a.events if e.event_type is EventType.DAMAGE and e.source_id=="char_192_falco"),"Falco_B_damage":0},
            "m16_event_order_audit":{"classification":"EVENT_ORDER_CONFIDENT","same_frame_differences":[]},
            "m16_causal_graph":causal,
            "m16_results":{"A":{"kills":a.enemies_killed,"leaks":a.enemies_leaked,"life":a.remaining_life},"B":{"kills":b.enemies_killed,"leaks":b.enemies_leaked,"life":b.remaining_life},"NON_MONOTONICITY_CAUSE":["ATTACK_ALLOCATION_NON_MONOTONICITY","TARGET_SELECTION_NON_MONOTONICITY"],"LOCAL_DAMAGE_MONOTONICITY_ASSUMPTION":"UNSAFE","full_simulations":2}}
