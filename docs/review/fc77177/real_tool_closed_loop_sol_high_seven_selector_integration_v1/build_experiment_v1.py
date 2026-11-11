#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import codex_experience_selector_v1 as selector

R99 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_artillery_closure_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_selector_integration_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-selector-integration-v1"
PLAN_PREFIX = "R100_SOL_HIGH_SEVEN_SELECTOR_INTEGRATION_"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def parent_destination(plan_id: str) -> Path:
    return BUNDLE / f"parent_{plan_id}"


def copy_parent(record: dict) -> dict:
    source = {key.removeprefix(""): Path(value) for key, value in record["responsible_paths"].items() if key in {"plan_snapshot", "action_snapshot", "diagnostic_events"}}
    final_status = source["plan_snapshot"].parent / "final_status.json"
    if not final_status.exists():
        final_status = R99 / "session/candidates" / record["candidate_id"] / "simulation/final_status.json"
    destination = parent_destination(record["plan_id"])
    destination.mkdir(parents=True, exist_ok=True)
    for origin in (*source.values(), final_status):
        shutil.copyfile(origin, destination / origin.name)
    plan = json.loads((destination / "plan_snapshot.json").read_text())
    final = json.loads((destination / "final_status.json").read_text())
    declared_plan_id = plan.get("operational_plan_id")
    final_plan_id = final.get("plan_id")
    if declared_plan_id != record["plan_id"] or final_plan_id != record["plan_id"]:
        raise RuntimeError(f"plan_id mismatch for {record['plan_id']}: {declared_plan_id}/{final_plan_id}")
    events_path = destination / "diagnostic_events.json.gz"
    result = {
        "record_id": record["record_id"],
        "candidate_id": record["candidate_id"],
        "declared_plan_id": declared_plan_id,
        "final_status_plan_id": final_plan_id,
        "plan_sha256": digest(destination / "plan_snapshot.json"),
        "action_sha256": digest(destination / "action_snapshot.json"),
        "events_gz_sha256": digest(events_path),
        "events_restored_sha256": restored_digest(events_path),
        "operator_union_count": record["operator_union_count"],
        "archive_status": record["archive_status"],
    }
    expected = record["evidence_hashes"]["actual"]
    for key in ("plan_sha256", "action_sha256", "events_gz_sha256", "events_restored_sha256"):
        if result[key] != expected[key]:
            raise RuntimeError(f"parent hash mismatch: {record['record_id']} {key}")
    return result


def selector_context() -> dict:
    store = ROOT / "output/codex_experience_selector_v1/experience_records.jsonl"
    records = selector.load_store(store)
    if len(records) != 12 or any(record.get("archive_status") != "VERIFIED" for record in records):
        raise RuntimeError("selector store is not the verified 12-record baseline")
    rebuild = ROOT / "output/codex_experience_selector_v1/experience_records.rebuild_check.jsonl"
    report = selector.rebuild_store(store, rebuild)
    if report["missing_from_rebuild"] or any(item.get("error") for item in report["issues"]):
        raise RuntimeError(f"selector rebuild failed: {report}")
    rebuilt = selector.load_store(rebuild)
    if rebuilt != records:
        raise RuntimeError("selector rebuild is not byte-record identical")
    payload, omitted = selector.build_context(
        records,
        goal="Legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN; current breaks include artillery closure and protected/central closure",
        k=7,
        target_tags={"ARTILLERY_KILL", "SUPPORT_DELIVERY", "PROTECTED_ROUTE", "CENTRAL_INTERCEPT"},
        byte_limit=28_000,
    )
    return {
        "records": records,
        "rebuild_report": {"records": report["records"], "missing_from_rebuild": report["missing_from_rebuild"], "issues": report["issues"]},
        "context": payload,
        "context_omitted": omitted,
        "context_bytes": len(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()),
    }


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("selector-integration experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)
    store = ROOT / "output/codex_experience_selector_v1/experience_records.jsonl"
    records = selector.load_store(store)
    parents = [copy_parent(record) for record in records]
    write_json(BUNDLE / "parent_identity_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SELECTOR_INTEGRATION_PARENT_IDENTITY_MANIFEST_V1",
        "directory_naming_policy": "Parent directory names are explicit plan IDs.",
        "lineage_policy": "Codex selects exactly one parent; successful windows from different plans may not be spliced.",
        "parent_candidates": parents,
    })
    selected = selector_context()
    selector_store_path = BUNDLE / "experience_records.jsonl"
    selector_store_path.write_bytes(store.read_bytes())
    import_report_path = BUNDLE / "experience_import_report_v1.json"
    import_report_path.write_text((ROOT / "output/codex_experience_selector_v1/experience_records.import_report.json").read_text())
    write_json(BUNDLE / "experience_selector_state_v1.json", {
        "schema_version": "KIMIARK_EXPERIENCE_SELECTOR_STATE_V1",
        "selector_code_sha256": digest(ROOT / "scripts/codex_experience_selector_v1.py"),
        "selector_store_sha256": digest(selector_store_path),
        "selector_import_report_sha256": digest(import_report_path),
        "rebuild_report": selected["rebuild_report"],
        "context_omitted": selected["context_omitted"],
        "context_bytes": selected["context_bytes"],
        "context_sha256": hashlib.sha256(json.dumps(selected["context"], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "selection_policy": "Deterministic tag/branch retrieval; advisory only; model may override with a recorded reason.",
    })
    write_json(BUNDLE / "experience_selector_context_v1.json", selected["context"])
    evidence = json.loads((R99 / "input_bundle/llm_evidence_context.json").read_text())
    evidence.pop("artillery_closure_parent_fact_pack", None)
    evidence["revision_entry_mode"] = "PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {
        "path": "input_bundle/parent_identity_manifest_v1.json",
        "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"),
        "candidate_plan_ids": [item["declared_plan_id"] for item in parents],
        "selection_policy": "Model selects one parent and declares it in revision_hypothesis.parent_plan_id and plan parent_plan_id.",
    }
    evidence["experience_selector_context_v1"] = {
        "path": "input_bundle/experience_selector_context_v1.json",
        "sha256": digest(BUNDLE / "experience_selector_context_v1.json"),
        "advisory_status": "SUGGESTIONS_AND_CONDITIONAL_EVIDENCE_ONLY",
    }
    evidence["experience_selector_decision_record_policy"] = {
        "maximum_context_observations_cited": 3,
        "required_fields": ["selected_parent", "adopted_observations", "non_applicable_experiences", "similar_prior_failure_change", "override_reason_if_any"],
        "placement": "validation_card.experience_selector_decision_record",
        "constraint": "Visible structured record; hidden reasoning is not required.",
    }
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    shutil.copyfile(R99 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")
    manifest_files = []
    for path in sorted(item for item in BUNDLE.rglob("*") if item.is_file() and item.name != "bundle_manifest_v1.json"):
        entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["restored_sha256"] = restored_digest(path)
        manifest_files.append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SELECTOR_INTEGRATION_INPUT_BUNDLE_MANIFEST_V1",
        "files": manifest_files,
    })
    config_path = DEST / "session_config_v1.json"
    write_json(config_path, {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1", "session_id": SESSION_ID, "stage_id": "main_08-07",
        "plan_id_prefix": PLAN_PREFIX, "plan_label": "SOL_HIGH_SEVEN_SELECTOR_INTEGRATION", "model": "gpt-6.1-sol", "reasoning_effort": "high", "features_apps": False,
        "mechanics_version": "m38b-2781-animation-speed-v1", "facts_source_dir": BUNDLE.as_posix(), "session_root": (DEST / "session").as_posix(),
        "budget_path": (DEST / "simulation_budget_v1.json").as_posix(), "candidate_ledger_path": (DEST / "candidate_ledger_v1.json").as_posix(),
        "authorization_config_path": (DEST / "model_authorization_v1.json").as_posix(), "max_unique_deployed_operators": 7,
        "max_candidates": 2, "max_check_calls": 10, "max_real_cli_starts": 1, "simulation_timeout_seconds": 3600,
        "execution_backend": "CONTROLLED_RUNNER", "allow_fake_execution": False,
    })
    write_json(DEST / "simulation_budget_v1.json", {"schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1", "stage_id": "main_08-07", "max_stage_simulations": 2, "prior_stage_simulations": 0, "started_stage_simulations": 0})
    write_json(DEST / "candidate_ledger_v1.json", {"schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2", "session_id": SESSION_ID, "max_check_calls": 10, "used_check_calls": 0, "max_candidates": 2, "used_candidates": 0, "checks": [], "attempts": []})
    extra = ["features.apps=false", f'mcp_servers.kimiark.command="{ROOT / ".venv/bin/python"}"', f'mcp_servers.kimiark.args=["{ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"}","{config_path}"]', "mcp_servers.kimiark.required=true", 'mcp_servers.kimiark.default_tools_approval_mode="approve"', 'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]']
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1", "budget_boundary": "User authorized one fresh selector-integration Sol CLI with two complete simulations; prior ledgers remain closed.",
        "provider": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high", "features_apps": False,
        "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True},
        "extra_config_values": extra,
    })
    prompt = """You are gpt-6.1-sol (reasoning high) in one authorized KimiArk Codex CLI session. Work only in the current repository and use only the local MCP server `kimiark`. First call `get_session_status` and confirm gpt-6.1-sol/high, features.apps=false, K=7, mechanics `m38b-2781-animation-speed-v1`, max_real_cli_starts 1, 10 checks, 2 candidates, and 2 complete simulations. This is an independent ledger; do not resume, transfer, or reset old budgets.

Only `get_session_status`, `check_plan`, `run_simulation`, and `query_events` are permitted. Read-only shell may inspect supplied evidence. Do not use another model/agent, web service, tactical search, or shell simulation. Do not modify code, mechanics, budgets, authorization, or result files. All tactical choices are yours.

This is the first real selector-integration run, not model training or RL. M70 remains the eight-operator fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN. The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_selector_integration_v1/input_bundle/`. Read `experience_selector_context_v1.json` first, then verify all twelve M70/R94-R99 parents through `parent_identity_manifest_v1.json`. The selector's parent suggestions are advisory conditional evidence. You may choose any verified parent, including one not suggested, and may override with a recorded reason.

The goal is legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN. Current unresolved concerns include artillery closure and protected/central closure. Do not claim that this integration has improved past results. Do not splice successful windows from different plans.

Before C1, add `experience_selector_decision_record` to your validation card with: selected parent ID/hash and why it is primary versus evidence reference; at most 3 concrete observations adopted from the context with their record IDs; experiences you did not apply and why; any similar/重复 failure condition and what materially changes; override reason if any; your falsifiable question and expected/refuting events. This is a visible structured decision record, not hidden chain of thought. Opening, roadblock #4 and both protected routes, artillery closure, healer survival, and central #21/#22/#33/#34 block/kill or live replacement must each be assigned.

All 34 legal ordinary-mode 1-3-star IDs are open; union of selected and deployed IDs must be <=7, robots count, same-ID redeployment counts once. No operator is mandatory or forbidden. Allowed mechanisms include faster kills, changed shell exposure, rotating output/damage duty, replacement, retreat/redeployment, and accounted sacrifice. Exact HP, full eligible-candidate order, and continuous positions are UNKNOWN where unrecorded; old frames are not new deadlines.

After check_plan passes, freeze the exact candidate/hash and run once. Query the earliest failure first, then the targeted selector-predicted chain. Distinguish alive, injured, eligible, selected, healed, output alive, attacked artillery, artillery killed, route blocked, route failed, and central held/killed. Run C2 only for a materially different repair supported by C1 evidence; otherwise stop. If a complete seven-operator WIN occurs, freeze and stop; do not explore six.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and reached, every enemy settled with no active enemy, and complete settlement. Report exact kills/leaks/life, death events versus unique dead IDs, protected outcomes, key enemy settlement, action errors, configured model, visible usage, UNKNOWN_CLI_INTERNAL, and budget counts. `cached_input` is an input subset. Fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum."""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
