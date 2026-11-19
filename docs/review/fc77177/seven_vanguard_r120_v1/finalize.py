"""Parse existing two runs and verify counts/hashes; never executes a battle."""
import hashlib
from experiment import BASE, ROOT, read, write, sha

def main():
    rows=read(BASE/"results.json")
    assert len(rows)==2 and {r["label"] for r in rows}=={"Plume","Yato"}
    old=ROOT/"docs/review/fc77177/seven_astra_r119_v1/session/candidates/candidate-002/simulation"
    parent_events=read(old/"diagnostic_events.json")["events"]
    parent_plan=read(BASE/"parent_payload.json")["revised_operational_plans"][0]
    parent_leaks={e["source_id"] for e in parent_events if e["event_type"]=="ENEMY_LEAK"}
    indices={}
    comparisons=[]
    for row in rows:
        cid=row["check"]["candidate_id"]
        root=BASE/"session/candidates"/cid
        plan=read(root/"simulation/plan_snapshot.json")
        assert plan==read(BASE/"derived"/row["label"]/"payload.json")["revised_operational_plans"][0]
        assert set(plan["selected_low_star_operator_ids"])=={a["operator_id"] for a in plan["action_timeline"] if a["action_type"]=="DEPLOY"} and len(plan["selected_low_star_operator_ids"])==7
        record=read(root/"candidate_record.json")
        assert record["check_status"]=="PASS"
        assert row["run"]["status"]=="COMPLETED" # immutable candidate record may retain pre-run NOT_STARTED
        for name,expected in record["controlled_code_sha256"].items():assert sha(ROOT/name)==expected,name
        events=read(root/"simulation/diagnostic_events.json")["events"]
        leaks={e["source_id"] for e in events if e["event_type"]=="ENEMY_LEAK"}
        shots=[{"raw_index":i,**e} for i,e in enumerate(events) if e["event_type"]=="DAMAGE" and e.get("source_id")=="char_210_stward" and e.get("target_id")=="enemy_1112_emppnt#0"]
        actual_damage=sum(e["details"]["amount"] for e in shots)
        comparison={"label":row["label"],"candidate_id":cid,"old_leaks_eliminated":sorted(parent_leaks-leaks),"new_leaks":sorted(leaks-parent_leaks),"artillery_steward_hit_count":len(shots),"artillery_steward_actual_damage":round(actual_damage,8),"first_last_steward_hit":shots[:1]+shots[-1:],"observed":row["observed"],"tactical_provenance":"HOST_AUTHORED_DETERMINISTIC_VARIANT","model_calls":0}
        if row["label"]=="Yato":
            comparison["artillery_HP_before_retreat"]={"value":round(13000-actual_damage,8),"status":"CODE_AND_ALL_DAMAGE_DERIVED_NOT_DIRECT_HP_SNAPSHOT","not_a_WIN_prediction":True}
        comparisons.append(comparison)
        focus={"enemy_1108_uterer#2","enemy_1107_uoffcr#7","enemy_1107_uoffcr#11","enemy_1107_uoffcr#13","enemy_1112_emppnt#0","enemy_3001_upeopl#3","enemy_3001_upeopl#14","trap_020_roadblock#4"}
        indices[cid]=[{"raw_index":i,**e} for i,e in enumerate(events) if e["event_type"] in ["OPERATOR_DEATH","PROTECTED_TARGET_REACHED","ENEMY_LEAK"] or e["event_type"] in ["BLOCK","ENEMY_DEATH","DEVICE_DESTROYED","DAMAGE","ENEMY_ABILITY_HIT"] and (e.get("source_id") in focus or e.get("target_id") in focus)]
    for name,expected in read(BASE/"sealed_ledger_hashes.json").items():assert sha(ROOT/name)==expected,name
    ledger=read(BASE/"candidate_ledger_v1.json");budget=read(BASE/"simulation_budget_v1.json")
    assert (ledger["used_check_calls"],ledger["used_candidates"],budget["started_stage_simulations"])==(2,2,2)
    reservations=[read(p) for p in (BASE/"session/candidates").glob("*/simulation.simulation_reservation.json")]
    assert sorted(r["reservation_index"] for r in reservations)==[1,2]
    assert all(r["status"]=="COMPLETED" and r["result_saved"] for r in reservations)
    write(BASE/"comparison_v1.json",{"parent":"R119 candidate-002","parent_result":"LOSS29/4 both protected arrived artillery killed","variants":comparisons,"no_new_best":True,"independent_retests":0,"model_calls":0,"CLI":0,"model_usage":"NOT_APPLICABLE"})
    write(BASE/"key_event_index_v1.json",indices)
    write(BASE/"verification_v1.json",{"status":"PASS","checks":2,"static_rejects":0,"PASS_candidates":2,"actual_completed_reservations":2,"model_calls":0,"CLI_starts":0,"old_ledgers_unchanged":True,"frozen_plans_equal_derived":True,"K":7,"independent_retests":0,"production_gate":"CONTROLLED_RUNNER","audit_new_battles":0})
    print({"verified":True,"check":2,"candidate":2,"simulation":2,"model":0,"CLI":0})

if __name__=="__main__":main()
