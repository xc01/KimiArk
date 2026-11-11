#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
AUDIT = ROOT / "docs/review/fc77177/zero_model_m70_artillery_support_audit_v1"
R98 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_delivery_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_closure_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-artillery-closure-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def copy_parent(source: Path, label: str, plan_id: str, candidate_id: str) -> dict:
    destination = BUNDLE / label
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("plan_snapshot.json", "action_snapshot.json", "final_status.json", "diagnostic_events.json.gz"):
        shutil.copyfile(source / name, destination / name)
    plan = json.loads((destination / "plan_snapshot.json").read_text())
    final = json.loads((destination / "final_status.json").read_text())
    result = {
        "label": label,
        "source_candidate_id": candidate_id,
        "declared_plan_id": plan["operational_plan_id"],
        "final_status_plan_id": final["plan_id"],
        "plan_sha256": digest(destination / "plan_snapshot.json"),
        "action_sha256": digest(destination / "action_snapshot.json"),
        "events_gz_sha256": digest(destination / "diagnostic_events.json.gz"),
        "events_restored_sha256": restored_digest(destination / "diagnostic_events.json.gz"),
    }
    if result["declared_plan_id"] != plan_id or result["declared_plan_id"] != result["final_status_plan_id"]:
        raise RuntimeError(f"plan_id mismatch: {result}")
    return result


def compact_events(events: list[dict], low: int, high: int) -> list[dict]:
    wanted = {"ENEMY_ABILITY_START", "ENEMY_ABILITY_HIT", "HEAL", "OPERATOR_DEATH"}
    return [
        {"frame": event["frame"], "event_type": event["event_type"], "source_id": event.get("source_id"), "target_id": event.get("target_id"), "details": event.get("details", {})}
        for event in events if low <= event["frame"] <= high and event["event_type"] in wanted
    ]


def artillery_damage(events: list[dict]) -> dict:
    hits = [event for event in events if event["event_type"] == "DAMAGE" and event.get("source_id") == "char_210_stward" and event.get("target_id") == "enemy_1112_emppnt#0"]
    return {"hit_count": len(hits), "total_amount": round(sum(event["details"]["amount"] for event in hits), 2), "first_frame": hits[0]["frame"] if hits else None, "last_frame": hits[-1]["frame"] if hits else None}


def dependency_fact_pack() -> dict:
    closeout = json.loads((R98 / "closeout_report_v1.json").read_text())
    candidate_data = {}
    for candidate_index in (1, 2):
        events_path = R98 / f"session/candidates/candidate-{candidate_index:03d}/simulation/diagnostic_events.json.gz"
        with gzip.open(events_path, "rt") as handle:
            events = json.loads(handle.read())["events"]
        item = closeout["candidates"][candidate_index - 1]
        summary = item["summary_result"]
        deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
        candidate_data[f"C{candidate_index}"] = {
            "candidate_id": f"candidate-{candidate_index:03d}", "plan_id": item["plan_id"], "plan_sha256": item["plan_sha256"], "action_sha256": item["action_sha256"],
            "kills": summary["enemies_killed"], "leaks": summary["enemies_leaked"], "life": summary["remaining_life"],
            "operator_deaths": [{"frame": event["frame"], "operator_id": event["source_id"]} for event in deaths],
            "steward_artillery_damage": artillery_damage(events), "protected_target_deaths": item["protected_target_deaths"],
            "relevant_events_1900_3600": compact_events(events, 1900, 3600),
        }
    audit_facts = json.loads((AUDIT / "next_fact_pack_draft_v1.json").read_text())
    return {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_CLOSURE_FACT_PACK_V1",
        "boundary": "Zero-model compact facts from archived events. Exact HP, complete ally-heal candidate ordering, continuous positions, and counterfactual sufficiency are UNKNOWN unless directly observed.",
        "coordinates": audit_facts["coordinates"], "catalog": audit_facts["catalog"],
        "m70_observed_reference": {"output_runtime_tile": [5, 7], "ansel_runtime_tile": [5, 6], "hibiscus_runtime_tile": [2, 6], "steward_artillery_hits": 45, "steward_artillery_damage": 13227.21, "artillery_death_frame": 4273, "claim": "OBSERVED M70 success chain, not proof that any single mechanism is necessary."},
        "r98_comparison": candidate_data,
        "r98_observed_heal_delivery": {"c2_hibiscus_to_ansel_beginning_2143": "OBSERVED", "c2_hibiscus_to_steward_3191_amount_372": "OBSERVED", "causal_sufficiency": "UNKNOWN"},
        "r98_shared_hit_comparison": {"c1_3193_hit_operators": ["char_123_fang", "char_283_midn", "char_120_hibisc"], "c2_3193_hit_operators": ["char_120_hibisc", "char_210_stward"], "target_set_changed_by_r98_structure": "OBSERVED", "whether_exposure_was_caused_by_heal_competition": "UNKNOWN"},
        "dependency_questions": ["Does each proposed repair actually change shell target set, healing recipient, output alive-window, or kill timing?", "Is artillery failure an output-window/truncation failure, or an independent failure after enough observed output?", "Can support survive without reintroducing a different protected-route or central duty failure?"],
        "model_gap": ["No manual healing-target action.", "No guaranteed dodge or favorable lock-time assumption.", "Exact arbitrary-frame HP ratios and full eligible-candidate ordering are UNKNOWN_LOG_LIMIT."],
    }


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("independent artillery-closure experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)
    r98_identity = json.loads((R98 / "input_bundle/parent_identity_manifest_v1.json").read_text())
    parents = [copy_parent(R98 / "input_bundle" / item["label"], item["label"], item["declared_plan_id"], item["source_candidate_id"]) for item in r98_identity["parent_candidates"]]
    r98_closeout = json.loads((R98 / "closeout_report_v1.json").read_text())
    for item in r98_closeout["candidates"]:
        source = R98 / f"session/candidates/{item['candidate_id']}/simulation"
        parent = copy_parent(source, f"parent_{item['plan_id']}", item["plan_id"], item["candidate_id"])
        for key in ("plan_sha256", "action_sha256", "events_gz_sha256", "events_restored_sha256"):
            if parent[key] != item[key]:
                raise RuntimeError(f"R98 parent hash mismatch: {item['plan_id']} {key}")
        parents.append(parent)
    write_json(BUNDLE / "parent_identity_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_CLOSURE_PARENT_IDENTITY_MANIFEST_V1",
        "directory_naming_policy": "Parent directory names are explicit plan IDs.",
        "lineage_policy": "Sol selects exactly one parent; successful windows from different plans may not be spliced.",
        "parent_candidates": parents,
    })
    facts = dependency_fact_pack()
    write_json(BUNDLE / "artillery_closure_fact_pack_v1.json", facts)
    evidence = json.loads((R98 / "input_bundle/llm_evidence_context.json").read_text())
    for key in ("cold_start_task_root", "retry3_parent_fact_pack", "support_coverage_parent_fact_pack", "support_geometry_parent_fact_pack", "heal_delivery_parent_fact_pack"):
        evidence.pop(key, None)
    evidence["revision_entry_mode"] = "PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {"path": "input_bundle/parent_identity_manifest_v1.json", "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"), "candidate_plan_ids": [item["declared_plan_id"] for item in parents], "selection_policy": "Model selects one parent and declares it in revision_hypothesis.parent_plan_id and plan parent_plan_id."}
    evidence["artillery_closure_parent_fact_pack"] = {"path": "input_bundle/artillery_closure_fact_pack_v1.json", "sha256": digest(BUNDLE / "artillery_closure_fact_pack_v1.json")}
    evidence["r98_closeout"] = {"path": (R98 / "closeout_report_v1.json").relative_to(ROOT).as_posix(), "sha256": digest(R98 / "closeout_report_v1.json")}
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    shutil.copyfile(R98 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")
    manifest_files = []
    for path in sorted(item for item in BUNDLE.rglob("*") if item.is_file() and item.name != "bundle_manifest_v1.json"):
        entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["restored_sha256"] = restored_digest(path)
        manifest_files.append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", {"schema_version": "KIMIARK_SOL_HIGH_SEVEN_ARTILLERY_CLOSURE_INPUT_BUNDLE_MANIFEST_V1", "files": manifest_files})
    config_path = DEST / "session_config_v1.json"
    write_json(config_path, {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1", "session_id": SESSION_ID, "stage_id": "main_08-07", "plan_id_prefix": "R99_SOL_HIGH_SEVEN_ARTILLERY_CLOSURE_", "plan_label": "SOL_HIGH_SEVEN_ARTILLERY_CLOSURE", "model": "gpt-6.1-sol", "reasoning_effort": "high", "features_apps": False, "mechanics_version": "m38b-2781-animation-speed-v1", "facts_source_dir": BUNDLE.as_posix(), "session_root": (DEST / "session").as_posix(), "budget_path": (DEST / "simulation_budget_v1.json").as_posix(), "candidate_ledger_path": (DEST / "candidate_ledger_v1.json").as_posix(), "authorization_config_path": (DEST / "model_authorization_v1.json").as_posix(), "max_unique_deployed_operators": 7, "max_candidates": 2, "max_check_calls": 10, "max_real_cli_starts": 1, "simulation_timeout_seconds": 3600, "execution_backend": "CONTROLLED_RUNNER", "allow_fake_execution": False,
    })
    write_json(DEST / "simulation_budget_v1.json", {"schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1", "stage_id": "main_08-07", "max_stage_simulations": 2, "prior_stage_simulations": 0, "started_stage_simulations": 0})
    write_json(DEST / "candidate_ledger_v1.json", {"schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2", "session_id": SESSION_ID, "max_check_calls": 10, "used_check_calls": 0, "max_candidates": 2, "used_candidates": 0, "checks": [], "attempts": []})
    extra = ["features.apps=false", f'mcp_servers.kimiark.command="{ROOT / ".venv/bin/python"}"', f'mcp_servers.kimiark.args=["{ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"}","{config_path}"]', "mcp_servers.kimiark.required=true", 'mcp_servers.kimiark.default_tools_approval_mode="approve"', 'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]']
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1", "budget_boundary": "User authorized one fresh artillery-closure Sol CLI with two complete simulations; prior ledgers remain closed.", "provider": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high", "features_apps": False,
        "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True},
        "extra_config_values": extra,
    })
    prompt = """You are gpt-6.1-sol (reasoning high) in one authorized KimiArk Codex CLI session. Work only in the current repository and use only the local MCP server `kimiark`. First call `get_session_status` and confirm gpt-6.1-sol/high, features.apps=false, K=7, mechanics `m38b-2781-animation-speed-v1`, max_real_cli_starts 1, 10 checks, 2 candidates, and 2 complete simulations. This is an independent ledger; do not resume, transfer, or reset old budgets.

Only `get_session_status`, `check_plan`, `run_simulation`, and `query_events` are permitted. Read-only shell may inspect supplied evidence. Do not use another model/agent, web service, tactical search, or shell simulation. Do not modify code, mechanics, budgets, authorization, or result files. All tactical choices are yours.

M70 remains the eight-operator fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN. The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_closure_v1/input_bundle/`. Read `artillery_closure_fact_pack_v1.json` first and verify parent hashes through `parent_identity_manifest_v1.json`. Ten verified plans are selectable parents; do not splice successful windows from different plans.

The core tradeoff is real: R98 C1 kept Steward alive to 4330 and achieved 43 artillery hits/12,504.82 damage, but Ansel died at 2743. R98 C2 delivered Hibiscus-to-Ansel support from 2143 and Hibiscus-to-Steward healing at 3191, but Steward died at 3493 with only 26 hits/7,597.55 damage. Neither plan killed artillery. The 3193 hit target set differed, but why that exposure arose is UNKNOWN. Do not treat one more heal or one final score as proof of closure.

Select one parent by plan_id/hash. Compare a repair that preserves verified duties with a materially different artillery output/damage structure. The target question is whether actual support or alternative survival can carry the artillery-output duty through to artillery death while opening, roadblocks, both protected routes, and central duties remain covered. Artillery death is only a stage result, not WIN.

Do not force dual medics, Steward, a specific tile, a manual heal-target override, or a new-character quota. All 34 legal ordinary-mode 1-3-star IDs are open; union of selected and deployed IDs must be <=7, robots count, same-ID redeployment counts once. Allowed mechanisms include faster kill timing, changed shell exposure, rotating output/damage duty, replacement, retreat/redeployment, and accounted sacrifice.

Before each candidate, write a validation card naming the one parent and hashes, the causal change, the concrete expected change to shell targets/healing/output window/kill timing, refutation events, replacement and sacrifice costs, and who performs opening, roadblocks, both protected routes, artillery closure, and central duties. Exact HP, full eligible-candidate order, and continuous positions are UNKNOWN where unrecorded. Old frames are not new deadlines.

After check_plan passes, freeze the exact candidate/hash and run once. Query the earliest failure first, then the targeted chain. Distinguish alive, injured, eligible, selected, healed, output alive, attacked artillery, artillery killed, route blocked, route failed, and central held/killed. Run C2 only for a materially different repair supported by C1 evidence; otherwise stop. If a complete seven-operator WIN occurs, freeze and stop; do not explore six.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and reached, every enemy settled with no active enemy, and complete settlement. Report exact kills/leaks/life, death events versus unique dead IDs, protected outcomes, key enemy settlement, action errors, configured model, visible usage, UNKNOWN_CLI_INTERNAL, and budget counts. `cached_input` is an input subset. Fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum."""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
