#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
AUDIT = ROOT / "docs/review/fc77177/zero_model_m70_artillery_support_audit_v1"
PRIOR_CONTEXT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_support_coverage_v1/input_bundle/llm_evidence_context.json"
PRIOR_SCHEMA = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_support_coverage_v1/input_bundle/revision_output_schema.json"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_support_geometry_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-support-geometry-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def copy_parent(source_directory: str, identity: dict) -> dict:
    destination = BUNDLE / f"parent_{identity['plan_id']}"
    destination.mkdir(parents=True, exist_ok=True)
    source = ROOT / source_directory
    for name in ("plan_snapshot.json", "action_snapshot.json", "final_status.json", "diagnostic_events.json.gz"):
        shutil.copyfile(source / name, destination / name)
    plan = json.loads((destination / "plan_snapshot.json").read_text())
    final = json.loads((destination / "final_status.json").read_text())
    result = {
        "label": destination.name,
        "source_directory": source_directory,
        "declared_plan_id": identity["plan_id"],
        "plan_snapshot_plan_id": plan.get("operational_plan_id"),
        "final_status_plan_id": final.get("plan_id"),
        "plan_sha256": digest(destination / "plan_snapshot.json"),
        "action_sha256": digest(destination / "action_snapshot.json"),
        "events_gz_sha256": digest(destination / "diagnostic_events.json.gz"),
        "events_restored_sha256": restored_digest(destination / "diagnostic_events.json.gz"),
    }
    if result["declared_plan_id"] != result["plan_snapshot_plan_id"] or result["declared_plan_id"] != result["final_status_plan_id"]:
        raise RuntimeError(f"parent identity mismatch: {result}")
    for key in ("plan_sha256", "action_sha256", "events_gz_sha256", "events_restored_sha256"):
        if result[key] != identity["sha256"][key.replace("_sha256", "")]:
            raise RuntimeError(f"parent hash mismatch for {identity['plan_id']}: {key}")
    return result


def fact_pack() -> dict:
    audit_index = json.loads((AUDIT / "comparison_index_v1.json").read_text())
    audit_facts = json.loads((AUDIT / "next_fact_pack_draft_v1.json").read_text())
    selected_keys = ("identity", "selected_low_star_operator_ids", "support_positions_and_coverage")
    comparison = {}
    for key, value in audit_facts["comparison"].items():
        observed = value["observed"]
        comparison[key] = {
            "plan_id": value["plan_id"],
            **{name: value[name] for name in selected_keys},
            "final": observed["final"],
            "artillery_shells_on_operators": observed["artillery_shells_on_operators"],
            "steward_to_artillery": observed["steward_to_artillery"],
            "heals_to_steward": observed["heals_to_steward"],
            "action_error_classification": observed["action_error_classification"],
        }
    return {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_FACT_PACK_V1",
        "boundary": "Zero-model compact facts; exact HP at arbitrary frames, continuous positions, target-choice causality, and causal sufficiency are UNKNOWN unless separately observed.",
        "coordinates": audit_facts["coordinates"],
        "core_observation": audit_index["observed_core"],
        "falsifiable_questions": audit_index["falsifiable_questions"],
        "comparison": comparison,
        "catalog": audit_facts["catalog"],
        "audit_index": {
            "path": (AUDIT / "comparison_index_v1.json").relative_to(ROOT).as_posix(),
            "sha256": digest(AUDIT / "comparison_index_v1.json"),
        },
    }


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("independent support-geometry experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)

    audit_index = json.loads((AUDIT / "comparison_index_v1.json").read_text())
    parents = [copy_parent(value["paths"]["plan"].rsplit("/", 1)[0], value) for value in audit_index["sources"].values()]
    identity_manifest = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_PARENT_IDENTITY_MANIFEST_V1",
        "directory_naming_policy": "Parent directory names are explicit plan IDs.",
        "lineage_policy": "Sol selects exactly one parent; successful windows from different plans may not be spliced.",
        "parent_candidates": parents,
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", identity_manifest)
    facts = fact_pack()
    write_json(BUNDLE / "support_geometry_fact_pack_v1.json", facts)

    evidence = json.loads(PRIOR_CONTEXT.read_text())
    evidence.pop("cold_start_task_root", None)
    evidence.pop("retry3_parent_fact_pack", None)
    evidence.pop("support_coverage_parent_fact_pack", None)
    evidence["revision_entry_mode"] = "PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {
        "path": "input_bundle/parent_identity_manifest_v1.json",
        "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"),
        "candidate_plan_ids": [item["declared_plan_id"] for item in parents],
        "selection_policy": "Model selects one parent and declares it in revision_hypothesis.parent_plan_id and plan parent_plan_id.",
    }
    evidence["support_geometry_parent_fact_pack"] = {
        "path": "input_bundle/support_geometry_fact_pack_v1.json",
        "sha256": digest(BUNDLE / "support_geometry_fact_pack_v1.json"),
    }
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    shutil.copyfile(PRIOR_SCHEMA, BUNDLE / "revision_output_schema.json")

    manifest_files = []
    for path in sorted(item for item in BUNDLE.rglob("*") if item.is_file() and item.name != "bundle_manifest_v1.json"):
        entry = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        if path.suffix == ".gz":
            entry["restored_sha256"] = restored_digest(path)
        manifest_files.append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_INPUT_BUNDLE_MANIFEST_V1",
        "files": manifest_files,
    })

    config_path = DEST / "session_config_v1.json"
    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R97_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_",
        "plan_label": "SOL_HIGH_SEVEN_SUPPORT_GEOMETRY",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "facts_source_dir": BUNDLE.as_posix(),
        "session_root": (DEST / "session").as_posix(),
        "budget_path": (DEST / "simulation_budget_v1.json").as_posix(),
        "candidate_ledger_path": (DEST / "candidate_ledger_v1.json").as_posix(),
        "authorization_config_path": (DEST / "model_authorization_v1.json").as_posix(),
        "max_unique_deployed_operators": 7,
        "max_candidates": 2,
        "max_check_calls": 10,
        "max_real_cli_starts": 1,
        "simulation_timeout_seconds": 3600,
        "execution_backend": "CONTROLLED_RUNNER",
        "allow_fake_execution": False,
    }
    write_json(config_path, config)
    write_json(DEST / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": "main_08-07",
        "max_stage_simulations": 2,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(DEST / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "max_check_calls": 10,
        "used_check_calls": 0,
        "max_candidates": 2,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    })
    extra = [
        "features.apps=false",
        f'mcp_servers.kimiark.command="{ROOT / ".venv/bin/python"}"',
        f'mcp_servers.kimiark.args=["{ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"}","{config_path}"]',
        "mcp_servers.kimiark.required=true",
        'mcp_servers.kimiark.default_tools_approval_mode="approve"',
        'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]',
    ]
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "budget_boundary": "User authorized one fresh support-geometry Sol CLI with two complete simulations; prior ledgers remain closed.",
        "provider": "openai",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "real_cli_starts": {
            "authorized_real_cli_starts": 1,
            "used_real_cli_starts": 0,
            "automatic_retry": False,
            "automatic_resume": False,
            "model_change_or_tier_change_forbidden": True,
        },
        "extra_config_values": extra,
    })

    prompt = """You are gpt-6.1-sol (reasoning high) in one authorized KimiArk Codex CLI session. Work only in the current repository and use only the local MCP server `kimiark`. First call `get_session_status` and confirm gpt-6.1-sol/high, features.apps=false, K=7, mechanics `m38b-2781-animation-speed-v1`, max_real_cli_starts 1, 10 checks, 2 candidates, and 2 complete simulations. This is an independent ledger; do not resume, transfer, or reset old budgets.

Only `get_session_status`, `check_plan`, `run_simulation`, and `query_events` are permitted. Read-only shell may inspect supplied evidence. Do not use another model/agent, web service, tactical search, or shell simulation. Do not modify code, mechanics, budgets, authorization, or result files. All tactical choices are yours.

M70 `R8_7_GPT_M70_V1` remains the 8-operator fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN. The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_support_geometry_v1/input_bundle/`. Read `support_geometry_fact_pack_v1.json` first and verify parent hashes through `parent_identity_manifest_v1.json` before relying on evidence. All six audited plans are selectable parents; do not splice successful windows from different plans.

The verified core facts are: M70's output tile runtime (7,5) is covered by both Ansel (6,5) DOWN and Hibiscus (6,2) UP; Steward hits artillery 45 times for 13,227.21 and the artillery dies at 4273. R95 C1/C2 use runtime (7,2), where Hibiscus does not cover and the relevant hit/heal sequence is unchanged. R96 C2 has both medics geometrically covering runtime (6,5) and Hibiscus actually heals Steward 372.6 at 2476, but Ansel dies at 2261 after shells lock (5,5) then (5,6); Steward still dies at 2561. These facts do not prove dual support necessary or sufficient.

Before C1, compare Q1 actual support geometry/exposure and Q2 materially different artillery closure. You may also choose another concrete evidence-supported hypothesis, including a hybrid, but it must state its causal mechanism and refutable events. Do not force dual medics, Steward, a new operator, or the M70 layout. All 34 legal ordinary-mode 1-3-star IDs are equally open. The union of selected IDs and all DEPLOY IDs must be <=7; robots count; same-ID redeployment counts once.

The validation card must identify the selected parent and hashes, the actual change, why it changes hit/heal/target/output timing, the executors and space for opening, roadblocks, both protected routes, artillery, and central #21/#22/#34, plus costs, skills, redeployment, sacrifice/release effects, regression observations, and MODEL_GAP. Coverage does not imply target selection or a heal; exact HP is UNKNOWN without records. Do not convert old frames into universal deadlines. Do not assume guaranteed dodges, preswing locks, Ansel double-heal, or favorable targeting.

After check_plan passes, freeze the exact returned candidate/hash and run once. After full settlement, query the changed chain first, then the first overall failure. Classify predictions as proved, refuted, truncated by an earlier failure, or evidence-unknown. Distinguish alive, attacked another target, no legal target, attacked artillery, and artillery killed. Artillery removal alone does not satisfy full WIN. C2 must be a materially different repair supported by C1 evidence; otherwise stop and leave it unused. If a complete seven-operator WIN occurs, freeze and stop; do not explore six.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and safely arrived, all enemies settled with no active enemy, and complete settlement. Report exact kills/leaks/life, death events versus unique dead IDs, protected outcomes, key enemy settlement, remaining enemies/action errors, configured model, visible usage, UNKNOWN_CLI_INTERNAL, and budget counts. `cached_input` is an input subset. Fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum."""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
