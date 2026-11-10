#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PRIOR_RETRY2 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry2_v1"
R91_PARENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_retry2_v1/session/candidates/candidate-002/simulation"
R94_PARENT = PRIOR_RETRY2 / "session/candidates/candidate-001/simulation"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry3_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-retry3-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def parent_identity(source: Path, *, label: str, candidate_id: str, plan_id: str) -> tuple[Path, dict]:
    destination = BUNDLE / label
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("plan_snapshot.json", "action_snapshot.json", "final_status.json", "diagnostic_events.json.gz"):
        shutil.copyfile(source / name, destination / name)
    plan = json.loads((destination / "plan_snapshot.json").read_text())
    action = json.loads((destination / "action_snapshot.json").read_text())
    final = json.loads((destination / "final_status.json").read_text())
    events = json.load(gzip.open(destination / "diagnostic_events.json.gz", "rt"))["events"]
    identity = {
        "label": label,
        "source_candidate_id": candidate_id,
        "declared_plan_id": plan_id,
        "plan_snapshot_plan_id": plan.get("operational_plan_id"),
        "final_status_plan_id": final.get("plan_id"),
        "plan_sha256": digest(destination / "plan_snapshot.json"),
        "action_sha256": digest(destination / "action_snapshot.json"),
        "events_gz_sha256": digest(destination / "diagnostic_events.json.gz"),
        "events_restored_sha256": restored_digest(destination / "diagnostic_events.json.gz"),
        "action_count": len(action.get("actions") or []),
        "event_count": len(events),
    }
    if identity["plan_snapshot_plan_id"] != plan_id or identity["final_status_plan_id"] != plan_id:
        raise RuntimeError(f"parent plan_id mismatch for {plan_id}")
    return destination, identity


def compact(events: list[dict], event_type: str, source: str | None = None, target: str | None = None) -> list[dict]:
    return [
        {"frame": event["frame"], "source_id": event.get("source_id"), "target_id": event.get("target_id"), "details": event.get("details")}
        for event in events
        if event["event_type"] == event_type
        and (source is None or event.get("source_id") == source)
        and (target is None or event.get("target_id") == target)
    ]


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("independent retry3 experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)

    r91_dir, r91 = parent_identity(
        R91_PARENT,
        label="parent_R91_ASTRA_HIGH_SEVEN_BREAKPOINT_RETRY2_002",
        candidate_id="candidate-002",
        plan_id="R91_ASTRA_HIGH_SEVEN_BREAKPOINT_RETRY2_002",
    )
    r94_dir, r94 = parent_identity(
        R94_PARENT,
        label="parent_R94_SOL_HIGH_SEVEN_RETRY2_001",
        candidate_id="candidate-001",
        plan_id="R94_SOL_HIGH_SEVEN_RETRY2_001",
    )
    if r91["plan_sha256"] != "15ab46944a547aa9bc28636cb4afb039f7c447da848742f4c951874d56561904" or r91["action_sha256"] != "b8704da507a611fd6f0db16d6d91d5f13a40077c1141950cbe6f0a5aaca1adf1":
        raise RuntimeError("R91 parent hash mismatch")
    if r94["plan_sha256"] != "efd06045343ebc14399fbb4ef1be1f78fd5d9e8620aa68a2a900eb3709a0ef35" or r94["action_sha256"] != "39a8131fd71e3a00365940d974a7e8ffb5a7e3cb06e8aacaa49ad0363264de62":
        raise RuntimeError("R94 parent hash mismatch")

    e91 = json.load(gzip.open(r91_dir / "diagnostic_events.json.gz", "rt"))["events"]
    e94 = json.load(gzip.open(r94_dir / "diagnostic_events.json.gz", "rt"))["events"]
    identity_manifest = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY3_PARENT_IDENTITY_MANIFEST_V1",
        "directory_naming_policy": "Directory names are explicit plan IDs; no legacy retry2_parent_candidate labels are carried forward.",
        "lineage_policy": "Sol chooses one authorized parent; successful windows from different plans may not be spliced.",
        "parent_candidates": [r91, r94],
        "removed_labels": {
            "retry2_parent_candidate-002": "Rejected because prior evidence showed it contained R89, not R91.",
        },
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", identity_manifest)

    ansel_heals_94 = compact(e94, "HEAL", "char_212_ansel")
    steward_damage_94 = compact(e94, "DAMAGE", "char_210_stward", "enemy_1112_emppnt#0")
    facts = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY3_PARENT_FACT_PACK_V1",
        "boundary": "Zero-model compact facts; continuous HP/position between samples are UNKNOWN. Observed order is not by itself proof of causality or sufficient repair.",
        "coordinates": {
            "plan_action_tiles": "[row,col]",
            "deploy_event_detail": "runtime [x,y]/[col,row]",
            "non_symmetric_proof": "R91 C2 Fang tile [3,5] -> DEPLOY event tile '5,3'.",
        },
        "parents": {
            "R91_C2": {
                **r91,
                "final": {"kills": 24, "leaks": 9, "operator_deaths": 2, "remaining_life": -8, "simulator_win": False},
                "observed": {
                    "operator_deaths": compact(e91, "OPERATOR_DEATH"),
                    "leaks": compact(e91, "ENEMY_LEAK"),
                    "protected_reached": compact(e91, "PROTECTED_TARGET_REACHED"),
                    "devices_destroyed": compact(e91, "DEVICE_DESTROYED"),
                },
            },
            "R94_C1": {
                **r94,
                "final": {"kills": 22, "leaks": 11, "operator_deaths": 6, "remaining_life": -9, "simulator_win": False},
                "observed": {
                    "operator_deaths": compact(e94, "OPERATOR_DEATH"),
                    "leaks": compact(e94, "ENEMY_LEAK"),
                    "protected_reached": compact(e94, "PROTECTED_TARGET_REACHED"),
                    "devices_destroyed": compact(e94, "DEVICE_DESTROYED"),
                    "steward_artillery_damage": steward_damage_94,
                    "ansel_heals": ansel_heals_94,
                },
            },
        },
        "comparison_question": "R91 proves support survival but leaves protection/artillery/central closure; R94 proves early clearance/#14 flow but loses support/output. Do not merge their windows.",
    }
    write_json(BUNDLE / "sol_retry3_fact_pack_v1.json", facts)

    evidence = json.loads((PRIOR_RETRY2 / "input_bundle/llm_evidence_context.json").read_text())
    evidence.pop("cold_start_task_root", None)
    evidence["revision_entry_mode"] = "PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {
        "path": "input_bundle/parent_identity_manifest_v1.json",
        "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"),
        "candidate_plan_ids": [r91["declared_plan_id"], r94["declared_plan_id"]],
        "selection_policy": "Model selects one parent and declares it in revision_hypothesis.parent_plan_id and plan parent_plan_id.",
    }
    evidence["retry3_parent_fact_pack"] = {
        "path": "input_bundle/sol_retry3_fact_pack_v1.json",
        "sha256": digest(BUNDLE / "sol_retry3_fact_pack_v1.json"),
    }
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    shutil.copyfile(PRIOR_RETRY2 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")

    manifest_files = []
    for path in sorted(path for path in BUNDLE.rglob("*") if path.is_file() and path.name != "bundle_manifest_v1.json"):
        entry = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        if path.suffix == ".gz":
            entry["restored_sha256"] = restored_digest(path)
        manifest_files.append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY3_INPUT_BUNDLE_MANIFEST_V1",
        "files": manifest_files,
    })

    config_path = DEST / "session_config_v1.json"
    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R95_SOL_HIGH_SEVEN_RETRY3_",
        "plan_label": "SOL_HIGH_SEVEN_RETRY3",
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
        "budget_boundary": "User authorized one fresh retry3 Sol CLI with two complete simulations; prior ledgers remain closed.",
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

    prompt = f"""You are gpt-6.1-sol (reasoning high) in one authorized KimiArk Codex CLI session. Work only in the current repository and use only the local MCP server `kimiark`. First call `get_session_status` and confirm gpt-6.1-sol/high, K=7, mechanics `m38b-2781-animation-speed-v1`, max_real_cli_starts 1, 10 checks, 2 candidates, and 2 complete simulations. This is an independent ledger; do not resume, transfer, or reset old budgets.

Only `get_session_status`, `check_plan`, `run_simulation`, and `query_events` are permitted. Do not use another model/agent, web service, Simulator command, tactical search, or shell simulation. You may use read-only shell to inspect supplied evidence. Do not modify code, mechanics, budgets, authorization, or result files. All tactical choices are yours.

Baseline: M70 `R8_7_GPT_M70_V1` remains the current 8-operator fixed-simulator WIN. Seven-or-fewer feasibility is UNKNOWN. Retry2 closed as a complete R94 LOSS: 22 kills, 11 leaks, 6 deaths, life -9, zero remaining enemies. It proved eastern clearance and protected #14 arrival but lost support/output. The previous R91 C2 had 24/9/-8 with support survival, but failed protection/artillery/central closure. These are different plans; do not merge their successful windows.

The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry3_v1/input_bundle/`. `parent_identity_manifest_v1.json` names two verified parent candidates by plan ID/hash:
1. `R91_ASTRA_HIGH_SEVEN_BREAKPOINT_RETRY2_002` (plan 15ab46944a547aa9bc28636cb4afb039f7c447da848742f4c951874d56561904, action b8704da507a611fd6f0db16d6d91d5f13a40077c1141950cbe6f0a5aaca1adf1)
2. `R94_SOL_HIGH_SEVEN_RETRY2_001` (plan efd06045343ebc14399fbb4ef1be1f78fd5d9e8620aa68a2a900eb3709a0ef35, action 39a8131fd71e3a00365940d974a7e8ffb5a7e3cb06e8aacaa49ad0363264de62)
There is no cold-start root in this evidence. Choose the parent based on this round's support-competition question; do not inherit R94 solely because it is newest or R91 solely because it has higher kills. Declare the same chosen plan in `revision_hypothesis.parent_plan_id` and the plan's parent field. Do not splice successful windows.

`sol_retry3_fact_pack_v1.json` has compact parent observations. In R94, Steward hit artillery 23 times (2281-3337) for 6626.06 and died 3343; Ansel healed Steward through 3239 and healed Friston at 3325. This observed order alone is not proof that the transfer was the sole or sufficient cause. Read the relevant damage, heal, skill, range, target-selection, and event-order evidence. Restore exact HP only if events allow it; otherwise mark UNKNOWN.

Core question: how can support competition be eliminated structurally, rather than by one extra heal? Consider geometry, reducing competing heal targets, faster kills, redistributing output/block/heal, or live rotation. Roster is fully open among ordinary-mode 1-3-star IDs; no mandatory keep/remove; selected and all DEPLOY IDs union <= 7; robots count; same-ID redeployment counts once. Do not equate low output with low contribution or infer retention from total healing.

Before C1, write a short validation card: parent/hash, specific causal hypothesis and uncertainty, exact change, executors for opening/protection/artillery/central, expected observable events and refutation windows, cost/skill/redeployment/sacrifice accounting, regression observations, and MODEL_GAP for unsupported behavior. If one medic remains, explain overlap coverage and skill availability; if stronger output is used, name real artillery targets and legal windows; do not treat alive or attacking another enemy as artillery closure. Deaths are allowed but have no refund; settle released enemies and replacement cost.

After `check_plan` passes, freeze the exact returned candidate/hash and run once. On LOSS, query the first observable failure before the validation targets. Distinguish support alive, output alive, actually attacking artillery, and completing a kill. Artillery removal does not replace full WIN. Use C2 only with new evidence and a materially testable repair; otherwise stop with the actual reason and leave it unused. If a complete seven-operator WIN occurs, freeze and stop; do not explore six.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and safely arrived, all enemies settled with no active enemy, and complete settlement. At the end report exact kills/leaks/life, death events versus unique dead IDs, protected outcomes, key enemy settlement, remaining enemies/action errors, configured model, visible usage, UNKNOWN_CLI_INTERNAL, and budget counts. `cached_input` is an input subset. Fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum.
"""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
