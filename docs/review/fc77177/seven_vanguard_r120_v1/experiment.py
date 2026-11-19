"""Two host-authored deterministic vanguard substitutions, no model calls.

Natural-DP timing repair uses the existing pure compiler ledger; all actual
checks/freezes/full battles use unchanged production service/gates.
"""
import copy, gzip, hashlib, json, sys
from pathlib import Path
from contextlib import redirect_stdout

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import kimiark_tactical_stdio_service_v1 as production
import compile_r8_1_lowstar_c2_plan_v1 as compiler

def read(path):
    path = Path(path)
    if not path.exists():path = Path(str(path) + ".gz")
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())

def write(path, value):
    path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def synchronize(plan):
    plan["action_timeline"].sort(key=lambda a:a["frame"])
    plan["deployment_positions_and_directions"] = [copy.deepcopy(a) for a in plan["action_timeline"] if a["action_type"] == "DEPLOY"]
    plan["selected_low_star_operator_ids"] = sorted({a["operator_id"] for a in plan["deployment_positions_and_directions"]})

def initialize():
    if (BASE/"session_config_v1.json").exists():raise RuntimeError("R120 already initialized; never reopen/reset")
    old = ROOT/"docs/review/fc77177/seven_astra_r119_v1"
    old118 = ROOT/"docs/review/fc77177/seven_astra_r118_v1"
    assert read(old/"batch_state.json")["stopped"]
    payload = read(old/"session/candidates/candidate-002/source/llm_structured_output.json")
    parent = payload["revised_operational_plans"][0]
    write(BASE/"parent_payload.json",payload)
    write(BASE/"parent_identity.json",{"plan_id":parent["operational_plan_id"],"source":str((old/"session/candidates/candidate-002").relative_to(ROOT)),"HEAD":__import__("subprocess").check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"hashes":{str(p.relative_to(ROOT)):sha(p) for p in [old/"session/candidates/candidate-002/source/llm_structured_output.json",old/"session/candidates/candidate-002/simulation/action_snapshot.json",old/"session/candidates/candidate-002/simulation/diagnostic_events.json.gz",old/"session/candidates/candidate-002/simulation/simulation_parameters.json"]}})
    sealed = read(old/"sealed_ledger_hashes.json")
    sealed.update({str((old/name).relative_to(ROOT)):sha(old/name) for name in ["candidate_ledger_v1.json","simulation_budget_v1.json","batch_state.json"]})
    write(BASE/"sealed_ledger_hashes.json",sealed)
    context = read(old/"input_bundle/template_context.json")
    context.update(previous_plan_id=parent["operational_plan_id"],previous_plan_to_revise=parent)
    context["current_experiment_provenance"]={"generator":"HOST_AUTHORED_DETERMINISTIC_VARIANT","model_calls":0,"user_request":"试一下别的先锋","parent":"R119 candidate-002","scope":"One Plume and one Yato alternative with necessary natural-DP and skill timing; max2 actual battles, no old balance transfer"}
    write(BASE/"input_bundle/llm_evidence_context.json",context)
    write(BASE/"input_bundle/revision_output_schema.json",read(old/"input_bundle/revision_output_schema.json"))
    cfg = read(old/"session_config_v1.json")
    cfg.update(session_id="r120-deterministic-other-vanguards",plan_label="R120",plan_id_prefix="R120_",model="DETERMINISTIC_NO_MODEL",reasoning_effort="low",max_real_cli_starts=0,max_candidates=2,max_check_calls=10,session_root=str(BASE/"session"),facts_source_dir=str(BASE/"input_bundle"),candidate_ledger_path=str(BASE/"candidate_ledger_v1.json"),budget_path=str(BASE/"simulation_budget_v1.json"),authorization_config_path=str(BASE/"execution_authorization.json"))
    write(BASE/"execution_authorization.json",{"schema_version":"KIMIARK_CODEX_CLI_AUTHORIZATION_V1","provider":"deterministic-script-no-model","model":"DETERMINISTIC_NO_MODEL","reasoning_effort":"low","features_apps":False,"extra_config_values":[],"real_cli_starts":{"authorized_real_cli_starts":0,"used_real_cli_starts":0},"generation_source":"HOST_AUTHORED_DETERMINISTIC_VARIANT","scope":"No CLI or model generation. Service identity fields are legacy gate metadata, never an actual model session. User requested other vanguards; conservative two-variant scope."})
    write(BASE/"session_config_v1.json",cfg)
    write(BASE/"candidate_ledger_v1.json",{"schema_version":"KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2","session_id":cfg["session_id"],"stage_id":cfg["stage_id"],"max_check_calls":10,"used_check_calls":0,"max_candidates":2,"used_candidates":0,"checks":[],"attempts":[]})
    write(BASE/"simulation_budget_v1.json",{"schema_version":"KIMIARK_STAGE_SIMULATION_BUDGET_V1","stage_id":cfg["stage_id"],"max_stage_simulations":2,"prior_stage_simulations":0,"started_stage_simulations":0})
    write(BASE/"user_request_and_scope.json",{"request":"试一下别的先锋","inferred_conservative_scope":{"model_CLI":0,"model_generation":0,"production_check_max":10,"candidate_max":2,"complete_simulation_max":2},"alternatives":["翎羽 char_192_falco","夜刀 char_502_nblade"],"no_push":True,"old_balance_transfer":False,"why_not_fang":"Already covered by R118 reference; current parent is independently rerun Vanilla variant."})
    print({"initialized":"R120","used":{"check":0,"candidate":0,"simulation":0},"model":0})

def derive(operator, label):
    payload = copy.deepcopy(read(BASE/"parent_payload.json"))
    plan = payload["revised_operational_plans"][0]
    parent_id=plan["operational_plan_id"];new="R120_"+label
    hypothesis = "Replace Vanilla with "+label+"; preserve opening tile/direction and repair only natural-DP deficits and dependent skill timing. Observe actual block/kill and regressions, no assumed kill-DP."
    plan.update(operational_plan_id=new,parent_plan_id=parent_id,parent_hypothesis_id=new)
    payload["revision_hypothesis"].update(hypothesis_id=new,operational_plan_id=new,parent_plan_id=parent_id,tactical_hypothesis=hypothesis,changed_responsibilities=[hypothesis])
    payload["revised_strategic_hypotheses"][0]["hypothesis_id"]=new
    actions=[]
    for original in plan["action_timeline"]:
        a=copy.deepcopy(original)
        if a["operator_id"]=="char_240_wyvern":
            if a["action_type"]=="ACTIVATE_SKILL":continue
            a["operator_id"]=operator
        actions.append(a)
    if operator=="char_192_falco":
        for frame in [1382,3483,5584,7685]:
            actions.append({"action_type":"ACTIVATE_SKILL","operator_id":operator,"frame":frame})
    plan["action_timeline"]=actions
    synchronize(plan)
    facts=read(BASE/"input_bundle/llm_evidence_context.json")
    catalog={x["operator_id"]:x for x in facts["normal_low_star_catalog"]}
    supports={key:row["runtime_support"] for key,row in catalog.items()}
    repairs=[]
    # Pure static cost arithmetic, not parameter/battle search. Each deficit
    # deterministically delays only that deployment to natural-DP sufficiency.
    for _ in range(30):
        ledger=compiler.build_dp_ledger(plan,catalog,supports,BASE/"input_bundle")
        failures=ledger.get("conflicts") or []
        if not failures:break
        issue=failures[0]
        if issue.get("conflict")!="INSUFFICIENT_DP":raise RuntimeError("Non-DP static issue requires explicit inspection: "+str(issue))
        import math
        old_frame=issue["frame"];op=issue["operator_id"]
        delay=max(1,math.ceil((issue["cost"]-issue["balance_before"])*30-1e-7)+1)
        matching=[a for a in actions if a["action_type"]=="DEPLOY" and a["operator_id"]==op and a["frame"]==old_frame]
        assert len(matching)==1
        matching[0]["frame"]+=delay
        next_deploy=min((a["frame"] for a in actions if a["operator_id"]==op and a["action_type"]=="DEPLOY" and a is not matching[0] and a["frame"]>old_frame),default=10**9)
        for a in actions:
            if a["operator_id"]==op and a["action_type"]=="ACTIVATE_SKILL" and old_frame<a["frame"]<next_deploy:a["frame"]+=delay
        repairs.append({"issue":issue,"deployment_delay_frames":delay,"coupling":"All manual skills of same deployment generation shifted equally; other roles unchanged"})
        synchronize(plan)
    else:raise RuntimeError("Cost repair did not terminate")
    plan["validation_card"]={"generator":"HOST_AUTHORED_DETERMINISTIC_VARIANT","model_generation":False,"parent_plan_id":parent_id,"parent_payload_sha256":sha(BASE/"parent_payload.json"),"hypothesis":hypothesis,"static_cost_repairs":repairs,"known_risks":["Plume block1 versus Vanilla block2; Yato lower damage/no skill","No Vanilla DP: later supports can change cannon/healing chain","Plume kill-DP unsupported/not assumed; only actual existing runtime rules used","Same initial tile is a limited replacement test, not all possible openings"],"regression_checks":["full leaked ID set","11/13","roadblock4","artillery actual death/no leak","protected3/14 separately","19","central21/22/33/34","all action errors/deaths"]}
    return payload,repairs,ledger

def observe(cid):
    root=BASE/"session/candidates"/cid/"simulation"
    events=read(root/"diagnostic_events.json")["events"]
    result=read(root/"diagnostic_summary.json")["result"]
    return {"result":{k:v for k,v in result.items() if k!="events"},"kills":{e["target_id"]:e["frame"] for e in events if e["event_type"]=="ENEMY_DEATH" and e["details"].get("kill_counted")},"leaks":[{"raw_index":i,**e} for i,e in enumerate(events) if e["event_type"]=="ENEMY_LEAK"],"arrivals":[e for e in events if e["event_type"]=="PROTECTED_TARGET_REACHED"],"protected_deaths":[e for e in events if e["event_type"]=="ENEMY_DEATH" and e["details"].get("life_delta",0)<0],"operator_deaths":[e for e in events if e["event_type"]=="OPERATOR_DEATH"],"devices_destroyed":[e for e in events if e["event_type"]=="DEVICE_DESTROYED"]}

def execute():
    if (BASE/"execution_started.json").exists():raise RuntimeError("Already started; never retry automatically")
    cfg=production.load_session_config(BASE/"session_config_v1.json")
    status=production.session_status(cfg)
    assert (status["check_call_ledger"]["used_check_calls"],status["candidate_ledger"]["used_candidates"],status["budget"]["started_stage_simulations"])==(0,0,0)
    write(BASE/"initial_status.json",status)
    write(BASE/"execution_started.json",{"model_calls":0,"CLI_starts":0,"production_backend":"CONTROLLED_RUNNER","alternatives":2,"no_retry":True})
    rows=[]
    for operator,label in [("char_192_falco","Plume"),("char_502_nblade","Yato")]:
        payload,repairs,ledger=derive(operator,label)
        target=BASE/"derived"/label
        write(target/"payload.json",payload);write(target/"static_DP_derivation.json",{"repairs":repairs,"ledger":ledger})
        with redirect_stdout(sys.stderr):check=production.check_plan(cfg,{"plan":payload})
        write(target/"production_check.json",check)
        row={"label":label,"operator":operator,"generation":"HOST_AUTHORED_DETERMINISTIC_VARIANT","check":check,"repairs":repairs}
        if check["status"]=="PASS":
            with redirect_stdout(sys.stderr):run=production.run_simulation(cfg,{"candidate_id":check["candidate_id"],"candidate_sha256":check["candidate_sha256"]})
            row["run"]=run
            if run["status"]!="COMPLETED":
                write(BASE/"blocked.json",row);raise RuntimeError("Production execution failed; no retry")
            row["observed"]=observe(check["candidate_id"])
        elif check["status"]!="FAIL":
            write(BASE/"blocked.json",row);raise RuntimeError("Budget/service failure, stop")
        rows.append(row);write(BASE/"results.json",rows)
        print({"label":label,"check":check["status"],"candidate":check.get("candidate_id"),"result":row.get("observed",{}).get("result"),"errors":check.get("errors",[])},flush=True)
    for path,expected in read(BASE/"sealed_ledger_hashes.json").items():assert sha(ROOT/path)==expected,path
    write(BASE/"final_status.json",production.session_status(cfg))
    write(BASE/"batch_closed.json",{"closed":True,"reason":"Two requested deterministic vanguard alternatives finished; no broader search","model":0,"CLI":0,"no_transfer":True,"no_push":True})

if __name__=="__main__":
    {"prepare":initialize,"execute":execute}[sys.argv[1]]()
