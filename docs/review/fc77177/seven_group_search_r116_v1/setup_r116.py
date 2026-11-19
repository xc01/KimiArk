from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R115 = ROOT / "docs/review/fc77177/seven_group_search_v1"
BASE = Path(__file__).resolve().parent


def load(path: Path):
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def plan(payload: dict) -> dict:
    return payload["revised_operational_plans"][0]


def main() -> None:
    if BASE.exists() and any(path.name != "setup_r116.py" for path in BASE.iterdir()):
        raise RuntimeError("R116 path already has content; choose the next unused batch number")
    BASE.mkdir(parents=True, exist_ok=True)
    r115_ledger = load(R115 / "candidate_ledger_v1.json")
    r115_budget = load(R115 / "simulation_budget_v1.json")
    assert r115_ledger["session_id"] == "r115-seven-group-search"
    assert (r115_ledger["used_check_calls"], r115_ledger["used_candidates"], r115_budget["started_stage_simulations"]) == (133, 97, 99)

    source_base = R115 / "input_bundle/base_payload.json"
    source_context = R115 / "input_bundle/llm_evidence_context.json"
    schema = R115 / "input_bundle/revision_output_schema.json"
    baseline = load(source_base)
    complementary = load(R115 / "session/candidates/candidate-089/source/llm_structured_output.json")
    baseline_plan = plan(baseline)
    complement_plan = plan(complementary)
    assert baseline_plan["operational_plan_id"] == "R114_SEVEN_PARAM_SEARCH_084_MELREDEPLOY_45_DOWN"
    assert complement_plan["operational_plan_id"] == "R115_GROUP_FRONTIER_BOUNDARY2047"
    assert len(set(baseline_plan["selected_low_star_operator_ids"])) == 7
    assert len(set(complement_plan["selected_low_star_operator_ids"])) == 7

    parents = BASE / "parents"
    parents.mkdir()
    shutil.copyfile(source_base, parents / "baseline_payload.json")
    shutil.copyfile(R115 / "session/candidates/candidate-089/source/llm_structured_output.json", parents / "complementary_payload.json")
    base_context = load(source_context)
    registry = {
        "schema_version": "R116_PARENT_REGISTRY_V1",
        "selection": "Both independently supported 29-kill/four-leak branches are equal starting points.",
        "parents": [
            {"name": "baseline", "plan_id": baseline_plan["operational_plan_id"], "source": "R115 immutable input bundle", "payload_sha256": digest(parents / "baseline_payload.json"), "known_leaks": ["#2", "#7", "#11", "#13"]},
            {"name": "complementary", "plan_id": complement_plan["operational_plan_id"], "source": "R115 independently reverified candidate-089", "payload_sha256": digest(parents / "complementary_payload.json"), "known_leaks": ["#1", "#6", "#10", "#12"]},
        ],
        "r115_source_counts_immutable": {"checks": 133, "candidates": 97, "simulations": 99, "remaining_simulations_not_transferred": 1},
    }
    save(BASE / "parent_registry_v1.json", registry)
    for name, payload in [("baseline", baseline), ("complementary", complementary)]:
        context = copy.deepcopy(base_context)
        parent_plan = plan(payload)
        context["previous_plan_to_revise"] = copy.deepcopy(parent_plan)
        context["previous_plan_id"] = parent_plan["operational_plan_id"]
        context["parent_identity_manifest"] = {
            "path": "parent_registry_v1.json",
            "selection_policy": "Both user-designated R115 branches are peer parents; each candidate names its actual parent.",
            "candidate_plan_ids": [baseline_plan["operational_plan_id"], complement_plan["operational_plan_id"]],
        }
        save(BASE / "input_bundle" / f"{name}_context.json", context)
    shutil.copyfile(BASE / "input_bundle/baseline_context.json", BASE / "input_bundle/llm_evidence_context.json")
    shutil.copyfile(schema, BASE / "input_bundle/revision_output_schema.json")
    shutil.copyfile(parents / "baseline_payload.json", BASE / "input_bundle/base_payload.json")

    session_id = "r116-seven-operator-search"
    config = load(R115 / "session_config_v1.json")
    config.update({
        "session_id": session_id,
        "plan_label": "R116",
        "plan_id_prefix": "R116_",
        "model": "gpt-6.2-sol",
        "reasoning_effort": "medium",
        "max_real_cli_starts": 0,
        "session_root": str(BASE / "session"),
        "facts_source_dir": str(BASE / "input_bundle"),
        "candidate_ledger_path": str(BASE / "candidate_ledger_v1.json"),
        "budget_path": str(BASE / "simulation_budget_v1.json"),
        "authorization_config_path": str(BASE / "model_authorization_v1.json"),
        "max_check_calls": 500,
        "max_candidates": 100,
    })
    save(BASE / "session_config_v1.json", config)
    save(BASE / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "provider": "openai", "model": "gpt-6.2-sol", "reasoning_effort": "medium", "features_apps": False,
        "model_calls_authorized": 0, "model_calls_used": 0,
        "candidate_generation": "HOST_DETERMINISTIC_PARAMETER_SEARCH_NO_MODEL",
        "budget_boundary": "New R116 ledger: 500 production checks, 100 frozen PASS candidates, 100 complete simulations including final independent verification; no R115 balance transfer.",
        "real_cli_starts": {"authorized_real_cli_starts": 0, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False},
    })
    save(BASE / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2", "session_id": session_id,
        "stage_id": "main_08-07", "max_check_calls": 500, "used_check_calls": 0,
        "max_candidates": 100, "used_candidates": 0, "checks": [], "attempts": [],
    })
    save(BASE / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1", "stage_id": "main_08-07",
        "max_stage_simulations": 100, "prior_stage_simulations": 0, "started_stage_simulations": 0,
    })
    save(BASE / "search_state.json", {
        "batch_id": "R116", "round": 0, "closed": False, "model_calls": 0, "tactical_cli_starts": 0,
        "variants": [], "parent_selection_log": [],
    })

    import sys
    sys.path.insert(0, str(R115))
    import search_batch as sb
    sb.BASE = BASE
    known = {}
    for directory in [
        "real_tool_closed_loop_seven_param_search_r112c2_v1",
        "real_tool_closed_loop_seven_param_search_084_v2_v1",
        "real_tool_closed_loop_seven_param_search_084_fang45_v1",
    ]:
        for path in (ROOT / "docs/review/fc77177" / directory).glob("session/candidates/*/simulation/plan_snapshot.json"):
            frozen = sb.read(path)
            if "action_timeline" in frozen:
                known[sb.action_key(frozen)] = str(path.relative_to(ROOT))
    for path in (R115 / "session/candidates").glob("candidate-*/simulation/plan_snapshot.json"):
        frozen = sb.read(path)
        if "action_timeline" in frozen:
            known[sb.action_key(frozen)] = str(path.relative_to(ROOT))
    save(BASE / "old_action_index.json", known)
    print(json.dumps({
        "batch": "R116", "session_id": session_id, "parent_ids": registry["parents"],
        "checks": 0, "candidates": 0, "simulations": 0,
        "config_paths_match_new_batch": all(str(BASE) in str(config[key]) for key in ["session_root", "facts_source_dir", "candidate_ledger_path", "budget_path", "authorization_config_path"]),
        "r115_ledger_modified": False, "old_action_hashes_indexed": len(known),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
