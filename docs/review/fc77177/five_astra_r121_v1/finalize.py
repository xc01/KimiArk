"""Post-CLI evidence audit only. No tactical design, checks, or battle execution."""
import gzip, hashlib, json
from collections import Counter
from pathlib import Path
from prepare import ROOT, BASE, read, write, sha
import batch_service as service

def raw(path):
    path = Path(path)
    return path.read_bytes() if path.exists() else gzip.decompress(Path(str(path) + ".gz").read_bytes())

def digest(path):
    return hashlib.sha256(raw(path)).hexdigest()

def delta(events, observed):
    before = {e["source_id"] for e in events if e["event_type"] == "ENEMY_LEAK"}
    after = {e["source_id"] for e in observed["leaks"]}
    return {"eliminated": sorted(before-after), "added": sorted(after-before), "strict_subset": after < before}

def main():
    cli = BASE / "session/codex_cli"
    result = read(cli / "cli_process_result.json")
    assert result["cli_starts"] == 1, "One actual CLI only"
    state = read(BASE / "batch_state.json")
    ledger = read(BASE / "candidate_ledger_v1.json")
    budget = read(BASE / "simulation_budget_v1.json")
    trace = [json.loads(line) for line in raw(cli / "codex_exec.jsonl").decode().splitlines() if line.strip()]
    assert sum(x["type"] == "thread.started" for x in trace) <= 1
    calls = [r["item"] for r in trace if r["type"] == "item.completed" and r.get("item", {}).get("type") == "mcp_tool_call"]
    requests = [r["arguments"] for r in calls if r["tool"] == "search_variants"]
    rounds = [r["arguments"] for r in calls if r["tool"] == "record_round"]
    write(BASE / "actual_model_search_requests.json", requests)
    write(BASE / "actual_model_round_records.json", rounds)
    for path, expected in read(BASE / "sealed_ledger_hashes.json").items():
        assert sha(ROOT / path) == expected, path
    for path, expected in read(cli / "frozen_start_manifest.json")["inputs"].items():
        assert sha(ROOT / path) == expected, path
    registry = read(BASE / "parent_registry_v1.json")
    for alias, parent in registry.items():
        assert sha(BASE / "parents" / alias / "payload.json") == parent["payload_copy_sha256"]
        for item in parent["artifacts"].values():
            assert sha(ROOT / item["path"]) == item["sha256"]
    pass_rows = [r for r in state["variants"] if r["status"] == "PASS"]
    assert len(pass_rows) == ledger["used_candidates"]
    assert len(ledger["checks"]) == ledger["used_check_calls"]
    assert ledger["used_check_calls"] <= 500 and ledger["used_candidates"] <= 100 and budget["started_stage_simulations"] <= 100
    assert len({r["round"] for r in rounds}) <= 5
    parent_events = {name: service.evidence_events(name) for name,item in registry.items() if not item.get("no_events")}
    verified = []
    summaries = []
    failed_before_battle = []
    rejected = []
    code_hashes = {}
    for r in state["variants"]:
        matching = [q for q in requests if r["name"].rsplit("_", 1)[0] == q["name"] and q["parent"] == r["parent"] and q["round"] == r["round"] and q["hypothesis"] == r["hypothesis"] and service.expand(q.get("changes", []), r["parameters"]) == r["changes"] and service.expand(q.get("actions"), r["parameters"]) == r.get("actions")]
        assert matching, "Every variant must reconstruct from actual Astra arguments"
        if r["status"] != "PASS":
            rejected.append({k:r[k] for k in ["name", "parent", "round", "parameters", "changes", "check"]})
            continue
        cid = r["candidate_id"]
        cr = BASE / "session/candidates" / cid
        payload = service.build(r["parent"], r["name"], r["changes"], r["hypothesis"], r["round"], actions=r.get("actions"))
        assert payload == read(cr / "source/llm_structured_output.json")
        if r.get("run",{}).get("status") == "COMPLETED":
            assert payload["revised_operational_plans"][0] == read(cr / "simulation/plan_snapshot.json")
        record = read(cr / "candidate_record.json")
        assert record["check_status"] == "PASS" and record["unique_deployed_operator_count"] <= 5
        assert set(payload["revised_operational_plans"][0]["selected_low_star_operator_ids"]) == service.FIXED
        assert {a["operator_id"] for a in payload["revised_operational_plans"][0]["action_timeline"]} <= service.FIXED
        for path, expected in record["controlled_code_sha256"].items():
            assert sha(ROOT/path) == expected, path
        code_hashes = record["controlled_code_sha256"]
        if r["run"]["status"] != "COMPLETED":
            assert r["candidate_id"] == "candidate-039" and r["run"]["output_state"]["status"] == "FAILED_BEFORE_START"
            verified.append({"candidate_id":cid,"model_parameters_reconstructed_deep_equal":True,"execution_status":"RESERVATION_FAILED_BEFORE_BATTLE","not_a_tactical_LOSS":True})
            failed_before_battle.append({"candidate_id":cid,"run":r["run"],"round":r["round"]})
            continue
        summary = read(cr / "simulation/diagnostic_summary.json")["result"]
        assert r["observed"]["result"] == {k:v for k,v in summary.items() if k != "events"}
        verified.append({"candidate_id":cid, "model_parameters_reconstructed_deep_equal":True, "frozen_plan_deep_equal":True, "K":record["unique_deployed_operator_count"]})
        changes = {alias:delta(events, r["observed"]) for alias,events in parent_events.items()}
        p = payload["revised_operational_plans"][0]
        summaries.append({k:r[k] for k in ["name", "round", "parent", "hypothesis", "parameters", "changes", "actions", "candidate_id", "candidate_sha256", "plan_id"]} | {"observed":r["observed"], "leak_delta_to_parents":changes, "selected":p["selected_low_star_operator_ids"], "action_hash":digest(cr/"simulation/action_snapshot.json"), "events_hash":digest(cr/"simulation/diagnostic_events.json")})
    reservations = [read(p) for root in [BASE/"session/candidates", BASE/"reverification"] for p in root.glob("*/simulation.simulation_reservation.json")]
    assert len(reservations) == budget["started_stage_simulations"]
    assert sorted(r["reservation_index"] for r in reservations) == list(range(1,len(reservations)+1))
    assert sum(r["status"] == "COMPLETED" and r.get("result_saved") for r in reservations) == 48
    assert sum(r["status"] == "FAILED" and r.get("failure_outcome") == "FAILED_BEFORE_START" for r in reservations) == 1
    independent = state["independent_runs"]
    for run in independent:
        assert run["budget_after"] == run["budget_before"] + 1
        origin = BASE/"session/candidates"/run["candidate_id"]/"simulation"
        rerun = ROOT/run["path"]
        actual = {name:digest(origin/name)==digest(rerun/name) for name in ["plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json"]}
        assert actual == run["hash_equal"] and all(actual.values())
    write(BASE/"model_provenance_verification.json", {"status":"PASS", "source":"Actual one fixed-five Astra/low thread completed MCP calls, full actions and grids model-authored; no host tactics", "candidates":verified})
    write(BASE/"candidate_results_v1.json", {"completed":summaries, "rejected":rejected,"failed_before_battle":failed_before_battle})
    usage = result["usage_records"]
    for entry in usage:
        u = entry["usage"]
        assert u.get("cached_input_tokens",0) <= u["input_tokens"]
    counts = {"production_check":ledger["used_check_calls"], "static_reject":sum(x["status"]=="FAIL" for x in ledger["checks"]), "frozen_PASS_candidates":ledger["used_candidates"], "counted_simulation_reservations":budget["started_stage_simulations"],"actual_full_simulations":48,"failed_before_battle_reservations":1, "candidate_first_runs":len(pass_rows)-1, "independent_reruns":len(independent), "rounds":len({r["round"] for r in rounds}), "real_tactical_CLI_processes":1, "model":"gpt-6.2-astra", "reasoning_effort":"low", "features_apps":False, "CLI_usage":usage, "internal_model_requests":"UNKNOWN_CLI_INTERNAL"}
    write(BASE/"execution_identity_v1.json", {"head_at_start":"20949492b19a13a48932ddf726119d42c111c33e", "controlled_code_sha256":code_hashes, "old_sealed_ledgers_verified":True, "frozen_start_inputs_verified":True, "actual_completed_model_tool_calls":Counter(x["tool"] for x in calls), "thread_ids":[x["thread_id"] for x in trace if x["type"]=="thread.started"]})
    complete = [r["candidate_id"] for r in summaries if r["observed"]["complete_win"]]
    strict = [r["candidate_id"] for r in summaries if any(r["leak_delta_to_parents"][p]["strict_subset"] for p in ["A","B"]) and r["observed"]["artillery_kill"] is not None and len(r["observed"]["protected_arrivals"])==2 and r["observed"]["enemy19_kill"] is not None and all(f"enemy_1110_uamord#{n}" in r["observed"]["kills"] for n in [21,22,33,34])]
    verified_wins = [cid for cid in complete if any(run["candidate_id"]==cid and all(run["hash_equal"].values()) for run in independent)]
    closure = "VERIFIED_FIXED_FIVE_WIN" if verified_wins else "COMPLETED_FIVE_ROUNDS_NO_FIXED_FIVE_WIN" if result["status"]=="COMPLETED" else "BLOCKED_SINGLE_CLI_NO_RETRY"
    state.update(stopped=True, status=closure, closure_reason="Five hypothesis rounds completed; recorded Astra ReturnLive request mechanically executed after local wrapper false stop, no new tactical choices/model; original failure and final preserved")
    write(BASE/"batch_state.json", state)
    write(BASE/"final_budget_v1.json", {"check":{"max":500,"used":counts["production_check"],"remaining":500-counts["production_check"]},"candidate":{"max":100,"used":counts["frozen_PASS_candidates"],"remaining":100-counts["frozen_PASS_candidates"]},"simulation":{"max":100,"used":counts["counted_simulation_reservations"],"remaining":100-counts["counted_simulation_reservations"]},"rounds":{"max":5,"used":counts["rounds"]},"CLI":{"max":1,"used":1},"closed":True,"no_transfer":True})
    write(BASE/"closeout_v1.json", {"batch":"R121","status":closure,"counts":counts,"strict_progress_candidates":strict,"fixed_roster":sorted(service.FIXED),"complete_WIN_candidates":complete,"independently_verified_WIN_candidates":verified_wins,"independent_verifications":independent,"round_counts":{n:dict(Counter(r["status"] for r in state["variants"] if r["round"]==n)) for n in range(1,6)},"raw_model_final":"session/codex_cli/codex_final_message.txt","host_tactical_design":False,"host_mechanical_execution_after_child_exit":"Exactly eight variants from actual ReturnLive tool request; independent verification mechanically selected candidate040 on strict dominance over011; no Astra feedback or post-grid model decision fabricated","push":False})
    print({"status":closure,"counts":counts,"strict_progress_candidates":strict,"fixed_roster":sorted(service.FIXED),"complete_WIN":verified_wins})

if __name__ == "__main__":
    main()
