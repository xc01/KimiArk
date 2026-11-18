from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
ARCHIVE = ROOT / "docs/review/fc77177"
PARENT = ARCHIVE / "real_tool_closed_loop_seven_param_search_084_v2_v1/session/candidates/candidate-038"
COMPLEMENT = ARCHIVE / "real_tool_closed_loop_seven_param_search_084_fang45_v1/session/candidates/candidate-005"
PREFIX = "R115_GROUP_"


def read(path: Path):
    if not path.exists() and path.with_name(path.name + ".gz").exists():
        path = path.with_name(path.name + ".gz")
    if path.suffix == ".gz":
        return json.loads(gzip.decompress(path.read_bytes()))
    return json.loads(path.read_text())


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(path: Path) -> str:
    if not path.exists() and path.with_name(path.name + ".gz").exists():
        return hashlib.sha256(gzip.decompress(path.with_name(path.name + ".gz").read_bytes())).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(payload: dict) -> dict:
    return payload["revised_operational_plans"][0]


def action_key(plan: dict) -> str:
    actions = [{key: action[key] for key in ("action_type", "frame", "operator_id", "tile", "direction") if key in action}
        for action in plan["action_timeline"]]
    return hashlib.sha256(canonical({"selected": sorted(plan["selected_low_star_operator_ids"]), "actions": actions})).hexdigest()


def setup() -> None:
    if (BASE / "session_config_v1.json").exists():
        return
    source = PARENT / "source"
    frozen = read(source / "llm_structured_output.json")
    baseline = selected(frozen)
    assert baseline == read(PARENT / "simulation/plan_snapshot.json")
    facts = read(source / "llm_evidence_context.json")
    facts["previous_plan_to_revise"] = copy.deepcopy(baseline)
    facts["previous_plan_id"] = baseline["operational_plan_id"]
    facts["parent_identity_manifest"] = {"path": "input_bundle/parent_identity_manifest.json", "selection_policy": "User-selected independently verified 29/4 primary parent", "candidate_plan_ids": [baseline["operational_plan_id"]]}
    write(BASE / "input_bundle/llm_evidence_context.json", facts)
    write(BASE / "input_bundle/revision_output_schema.json", read(source / "revision_output_schema.json"))
    write(BASE / "input_bundle/base_payload.json", frozen)
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in [source / "llm_structured_output.json", source / "llm_evidence_context.json", PARENT / "simulation/plan_snapshot.json", PARENT / "simulation/action_snapshot.json", PARENT / "simulation/diagnostic_events.json", COMPLEMENT / "simulation/plan_snapshot.json", COMPLEMENT / "simulation/action_snapshot.json", COMPLEMENT / "simulation/diagnostic_events.json"]}
    for name, old in [("baseline", PARENT), ("complement", COMPLEMENT)]:
        for suffix in ["plan_snapshot", "diagnostic_events"]:
            existing = old / "simulation" / (suffix + ".json")
            rerun = ARCHIVE / "real_tool_closed_loop_seven_param_search_084_fang45_v1/reverification" / ("best29_verified" if name == "baseline" else "early24") / "simulation" / (suffix + ".json")
            assert digest(existing) == digest(rerun)
    write(BASE / "input_bundle/parent_identity_manifest.json", {"parent_id": baseline["operational_plan_id"], "hashes": hashes, "independent_reverification_hashes_equal": True})
    session_id = "r115-seven-group-search"
    config = read(ARCHIVE / "real_tool_closed_loop_seven_param_search_084_fang45_v1/session_config_v1.json")
    config.update({"session_id": session_id, "plan_label": "R115_GROUP", "plan_id_prefix": PREFIX,
        "model": "gpt-6.2-astra", "reasoning_effort": "low", "max_real_cli_starts": 1,
        "session_root": str(BASE / "session"), "facts_source_dir": str(BASE / "input_bundle"),
        "candidate_ledger_path": str(BASE / "candidate_ledger_v1.json"), "budget_path": str(BASE / "simulation_budget_v1.json"),
        "authorization_config_path": str(BASE / "model_authorization_v1.json")})
    write(BASE / "session_config_v1.json", config)
    write(BASE / "model_authorization_v1.json", {"schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1", "provider": "openai",
        "model": "gpt-6.2-astra", "reasoning_effort": "low", "features_apps": False,
        "model_identifier_verification": "NOT_USED_UNVERIFIED_REQUESTED_ID; directory verification required before any tactical CLI",
        "candidate_generation": "HOST_DETERMINISTIC_PARAMETER_SEARCH_NO_MODEL",
        "budget_boundary": "500 production check calls, 100 frozen PASS candidates, 100 actual complete simulations including baseline and two independent final reruns; zero balance transfer",
        "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False}})
    write(BASE / "candidate_ledger_v1.json", {"schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2", "session_id": session_id,
        "stage_id": "main_08-07", "max_check_calls": 500, "used_check_calls": 0, "max_candidates": 100,
        "used_candidates": 0, "checks": [], "attempts": []})
    write(BASE / "simulation_budget_v1.json", {"schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1", "stage_id": "main_08-07", "max_stage_simulations": 100, "prior_stage_simulations": 0, "started_stage_simulations": 0})
    write(BASE / "search_state.json", {"variants": [], "old_dedup": {}, "model_calls": 0, "tactical_cli": 0})
    known = {}
    for directory in ["real_tool_closed_loop_seven_param_search_r112c2_v1", "real_tool_closed_loop_seven_param_search_084_v2_v1", "real_tool_closed_loop_seven_param_search_084_fang45_v1"]:
        for plan_path in (ARCHIVE / directory).glob("session/candidates/*/simulation/plan_snapshot.json"):
            plan = read(plan_path)
            if "action_timeline" in plan:
                known[action_key(plan)] = str(plan_path.relative_to(ROOT))
    write(BASE / "old_action_index.json", known)


def tool(name: str, arguments: dict, tag: str, config_path: Path | None = None) -> dict:
    config_path = config_path or BASE / "session_config_v1.json"
    messages = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": "zero-model-r115", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}]
    command = [sys.executable, str(ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"), str(config_path)]
    completed = subprocess.run(command, input="".join(json.dumps(message) + "\n" for message in messages), cwd=ROOT, text=True, capture_output=True, timeout=3600)
    write(BASE / "tool_calls" / (tag + ".json"), {"command": command, "request": messages[-1], "returncode": completed.returncode,
        "stdout": completed.stdout, "stderr": completed.stderr})
    if completed.returncode:
        raise RuntimeError(f"Production tool failed: {name} {tag}; no retry")
    response = next(json.loads(line) for line in completed.stdout.splitlines() if json.loads(line).get("id") == 1)
    if response.get("error") or response.get("result", {}).get("isError"):
        raise RuntimeError(f"MCP error: {response}")
    return response["result"]["structuredContent"]


def build(name: str, changes: list[dict], hypothesis: str) -> dict:
    payload = read(BASE / "input_bundle/base_payload.json")
    plan = selected(payload)
    parent_id = plan["operational_plan_id"]
    hypothesis_id = PREFIX + name
    plan["operational_plan_id"] = hypothesis_id
    plan["parent_hypothesis_id"] = hypothesis_id
    plan["parent_plan_id"] = parent_id
    payload["revision_hypothesis"].update({"hypothesis_id": hypothesis_id, "operational_plan_id": hypothesis_id,
        "parent_plan_id": parent_id, "tactical_hypothesis": hypothesis, "changed_responsibilities": [hypothesis]})
    payload["revised_strategic_hypotheses"][0]["hypothesis_id"] = hypothesis_id
    plan["validation_card"] = {"generator": "deterministic_group_search", "parent_id": parent_id,
        "hypothesis": hypothesis, "changes": changes, "regressions_to_observe": ["all leak IDs", "both protected arrivals", "artillery death", "#29 kill", "action errors"]}
    for change in changes:
        kind = change["type"]
        actions = plan["action_timeline"]
        if kind == "set":
            matches = [action for action in actions if action["operator_id"] == change["operator"] and action["action_type"] == change["action"] and action["frame"] == change["frame"]]
            if len(matches) != 1:
                raise RuntimeError(f"Ambiguous action match: {change}")
            matches[0].update(change["fields"])
        elif kind == "add":
            actions.append(copy.deepcopy(change["value"]))
        elif kind == "remove":
            plan["action_timeline"] = [action for action in actions if not (action["operator_id"] == change["operator"] and action["action_type"] == change["action"] and action["frame"] == change["frame"])]
        elif kind == "replace":
            for action in actions:
                if action["operator_id"] == change["operator"]:
                    action["operator_id"] = change["replacement"]
        else:
            raise RuntimeError(kind)
    plan["action_timeline"].sort(key=lambda action: action["frame"])
    plan["deployment_positions_and_directions"] = [copy.deepcopy(action) for action in plan["action_timeline"] if action["action_type"] == "DEPLOY"]
    plan["selected_low_star_operator_ids"] = sorted({action["operator_id"] for action in plan["deployment_positions_and_directions"]})
    return payload


def summarize(output: Path) -> dict:
    summary = read(output / "diagnostic_summary.json")
    events = read(output / "diagnostic_events.json")["events"]
    leaks = [{"id": event["source_id"], "frame": event["frame"]} for event in events if event["event_type"] == "ENEMY_LEAK"]
    kills = {event["target_id"]: event["frame"] for event in events if event["event_type"] == "ENEMY_DEATH" and event["details"].get("kill_counted")}
    reached = {event["source_id"]: event["frame"] for event in events if event["event_type"] == "PROTECTED_TARGET_REACHED"}
    blocks = defaultdict(list)
    hits = defaultdict(lambda: defaultdict(float))
    for event in events:
        if event["event_type"] == "BLOCK":
            blocks[event["target_id"]].append({"frame": event["frame"], "source": event["source_id"]})
        if event["event_type"] == "DAMAGE":
            hits[event["target_id"]][event["source_id"]] += event["details"].get("amount", 0)
    result = {key: value for key, value in summary["result"].items() if key != "events"}
    return {"result": result, "leaks": leaks, "kills": kills, "protected_reached": reached, "blocks": dict(blocks),
        "damage": dict(hits), "artillery_dead": "enemy_1112_emppnt#0" in kills,
        "complete_win": result["win"] and not leaks and len(reached) == 2 and result["enemies_remaining"] == 0,
        "events_path": str((output / "diagnostic_events.json").relative_to(ROOT))}


def variant(name: str, changes: list[dict], hypothesis: str, *, baseline=False) -> dict:
    state = read(BASE / "search_state.json")
    if state.get("closed"):
        raise RuntimeError("Batch is closed; no remaining balance is transferred or reused")
    if any(row["name"] == name for row in state["variants"]):
        return next(row for row in state["variants"] if row["name"] == name)
    payload = build(name, changes, hypothesis)
    key = action_key(selected(payload))
    known = read(BASE / "old_action_index.json")
    previous = next((row for row in state["variants"] if row["action_key"] == key), None)
    if previous or (key in known and not baseline):
        row = {"name": name, "status": "DEDUP_SKIPPED", "action_key": key, "previous": previous["name"] if previous else known[key], "changes": changes}
    else:
        ledger = read(BASE / "candidate_ledger_v1.json")
        budget = read(BASE / "simulation_budget_v1.json")
        if ledger["used_candidates"] >= 98 or ledger["used_check_calls"] >= 498 or budget["started_stage_simulations"] >= 98:
            raise RuntimeError("Exploration budget reached; final two slots reserved")
        check = tool("check_plan", {"plan": payload}, name + "_check")
        row = {"name": name, "changes": changes, "hypothesis": hypothesis, "action_key": key, "status": check["status"], "check": check}
        state["variants"].append(row)
        write(BASE / "search_state.json", state)
        if check["status"] == "PASS":
            simulation = tool("run_simulation", {"candidate_id": check["candidate_id"], "candidate_sha256": check["candidate_sha256"]}, name + "_run")
            row["simulation_status"] = simulation["status"]
            if simulation["status"] != "COMPLETED":
                raise RuntimeError(f"Simulation did not complete: {simulation}")
            row["observed"] = summarize(BASE / "session/candidates" / check["candidate_id"] / "simulation")
            state["variants"][-1] = row
            write(BASE / "search_state.json", state)
        print(json.dumps({"name": name, "check": row["status"], "errors": check.get("errors"),
            "leaks": row.get("observed", {}).get("leaks"), "kills": row.get("observed", {}).get("result", {}).get("enemies_killed"),
            "protected": row.get("observed", {}).get("protected_reached"), "simulations": read(BASE / "simulation_budget_v1.json")["started_stage_simulations"]}), flush=True)
        return row
    state["variants"].append(row)
    write(BASE / "search_state.json", state)
    print(json.dumps({"name": name, "status": "DEDUP_SKIPPED", "previous": row["previous"]}), flush=True)
    return row


if __name__ == "__main__":
    setup()
