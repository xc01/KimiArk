#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_duty_conflict_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-retry-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    for directory in (
        BUNDLE / "retry2_parent_candidate-002",
        BUNDLE / "duty_conflict_parent_c1",
        BUNDLE / "duty_conflict_parent_c2",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    copies = [
        (SOURCE / "input_bundle/llm_evidence_context.json", BUNDLE / "llm_evidence_context.json"),
        (SOURCE / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json"),
        (SOURCE / "input_bundle/gap_window_lineage_correction_v1.json", BUNDLE / "gap_window_lineage_correction_v1.json"),
        (SOURCE / "input_bundle/duty_conflict_fact_pack_v1.json", BUNDLE / "duty_conflict_fact_pack_v1.json"),
        (SOURCE / "closeout_report_v1.json", BUNDLE / "duty_conflict_closeout_report.json"),
        (SOURCE / "input_bundle/m70_plan_snapshot.json", BUNDLE / "m70_plan_snapshot.json"),
        (SOURCE / "input_bundle/m70_action_snapshot.json", BUNDLE / "m70_action_snapshot.json"),
        (SOURCE / "input_bundle/m70_final_status.json", BUNDLE / "m70_final_status.json"),
        (SOURCE / "input_bundle/m70_diagnostic_events.json.gz", BUNDLE / "m70_diagnostic_events.json.gz"),
        (SOURCE / "input_bundle/focused_parent_plan_snapshot.json", BUNDLE / "retry2_parent_candidate-002/plan_snapshot.json"),
        (SOURCE / "input_bundle/focused_parent_action_snapshot.json", BUNDLE / "retry2_parent_candidate-002/action_snapshot.json"),
        (SOURCE / "input_bundle/focused_parent_final_status.json", BUNDLE / "retry2_parent_candidate-002/final_status.json"),
        (SOURCE / "input_bundle/focused_parent_diagnostic_events.json.gz", BUNDLE / "retry2_parent_candidate-002/diagnostic_events.json.gz"),
        (SOURCE / "input_bundle/parent_c1/plan_snapshot.json", BUNDLE / "duty_conflict_parent_c1/plan_snapshot.json"),
        (SOURCE / "input_bundle/parent_c1/action_snapshot.json", BUNDLE / "duty_conflict_parent_c1/action_snapshot.json"),
        (SOURCE / "input_bundle/parent_c1/final_status.json", BUNDLE / "duty_conflict_parent_c1/final_status.json"),
        (SOURCE / "input_bundle/parent_c1/diagnostic_events.json.gz", BUNDLE / "duty_conflict_parent_c1/diagnostic_events.json.gz"),
        (SOURCE / "input_bundle/parent_c2/plan_snapshot.json", BUNDLE / "duty_conflict_parent_c2/plan_snapshot.json"),
        (SOURCE / "input_bundle/parent_c2/action_snapshot.json", BUNDLE / "duty_conflict_parent_c2/action_snapshot.json"),
        (SOURCE / "input_bundle/parent_c2/final_status.json", BUNDLE / "duty_conflict_parent_c2/final_status.json"),
        (SOURCE / "input_bundle/parent_c2/diagnostic_events.json.gz", BUNDLE / "duty_conflict_parent_c2/diagnostic_events.json.gz"),
    ]
    for source, target in copies:
        shutil.copyfile(source, target)

    retry2_plan_hash = digest(BUNDLE / "retry2_parent_candidate-002/plan_snapshot.json")
    retry2_action_hash = digest(BUNDLE / "retry2_parent_candidate-002/action_snapshot.json")
    retry2_events_hash = digest(BUNDLE / "retry2_parent_candidate-002/diagnostic_events.json.gz")
    parent_index = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY_PARENT_INDEX_V1",
        "primary_parent": {
            "experiment_id": "real_tool_closed_loop_astra_high_seven_breakpoint_retry2_v1",
            "candidate_id": "candidate-002",
            "plan_id": "R91_ASTRA_HIGH_SEVEN_BREAKPOINT_RETRY2_002",
            "plan_sha256": retry2_plan_hash,
            "action_sha256": retry2_action_hash,
            "events_gz_sha256": retry2_events_hash,
            "observed_result": {"kills": 24, "leaks": 9, "operator_deaths": 2, "remaining_life": -8, "simulator_win": False},
        },
        "contrasts": {
            "duty_conflict_candidate_001": {
                "source": SOURCE.relative_to(ROOT).as_posix(),
                "result": {"kills": 13, "leaks": 20, "operator_deaths": 8, "remaining_life": -19, "simulator_win": False},
                "interpretation": "Materially worse; do not inherit its opening by recency.",
            },
            "duty_conflict_candidate_002": {
                "source": SOURCE.relative_to(ROOT).as_posix(),
                "result": {"kills": 12, "leaks": 21, "operator_deaths": 8, "remaining_life": -20, "simulator_win": False},
                "interpretation": "Materially worse; do not inherit its opening by recency.",
            },
        },
        "lineage_rule": "Do not splice successful windows from different frozen plans into one verified trajectory.",
    }
    write_json(BUNDLE / "sol_retry_parent_index_v1.json", parent_index)

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
    write_json(BUNDLE / "bundle_manifest_v1.json", {"schema_version": "KIMIARK_SOL_HIGH_SEVEN_RETRY_INPUT_BUNDLE_MANIFEST_V1", "files": manifest_files})

    config_path = DEST / "session_config_v1.json"
    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R93_SOL_HIGH_SEVEN_RETRY_",
        "plan_label": "SOL_HIGH_SEVEN_RETRY",
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
        f'mcp_servers.kimiark.args=["{config_path}"]',
        "mcp_servers.kimiark.required=true",
        'mcp_servers.kimiark.default_tools_approval_mode="approve"',
        'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]',
    ]
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "budget_boundary": "User authorized one fresh Sol CLI with two complete simulations; no old balance is transferred or reset.",
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

Baseline: M70 `R8_7_GPT_M70_V1` remains the current 8-operator fixed-simulator WIN. Seven-or-fewer feasibility is UNKNOWN. The Astra duty-conflict round ended CLI 1/1, checks 4/10, candidates 2/2, simulations 2/2 with C1 13/20/-19 and C2 12/21/-20; both complete LOSS. Its CLI hit usage limit after both simulations, before turn.completed/final message, so do not treat its missing final synthesis as tactical evidence.

Primary parent is retry-2 candidate-002 `R91_ASTRA_HIGH_SEVEN_BREAKPOINT_RETRY2_002` (24/9/-2 deaths/life-8). It preserved support survival but failed roadblock clearance/protection, artillery output, and central closure. Use its exact plan/action/events as the primary source. Duty-conflict C1/C2 are only worse-regime contrasts; do not inherit their openings merely because they are newest. Do not splice successful windows across plans.

Evidence under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry_v1/input_bundle/` includes the schema, ordinary 1-3-star capability/facts, M70, retry-2 C2, and duty-conflict C1/C2 snapshots/events, plus the duty-conflict closeout and fact pack. `duty_conflict_fact_pack_v1.json` records that plan/action tiles are `[row,col]`, while DEPLOY event detail tile strings are runtime `[x,y]/[col,row]`; verify with its non-symmetric proof rather than symmetric examples.

Core question: without losing the primary parent's opening/support chain, restore roadblock/protection flow and effective artillery output, then provide actual central kills or live handoff for #21/#22/#34. You may centralize a repair on the parent or use a materially different structure if the evidence justifies it. Roster is fully open among ordinary-mode 1-3-star IDs; no mandatory keep/remove; selected and all DEPLOY IDs union <= 7; robots count; same-ID redeployment counts once.

Before the first simulation, list a short duty table for retry-2 C2: established, failed, executor, location/skill/time, and evidence. Preserve established conditions as functions, not as fixed people/tiles. State explicit effects and replacements for every dependency changed. Extract opening regression lessons from the two worse duty-conflict candidates and carry them as regression observations. Explain roadblock #4 and the western #1 release, protected-route flow, artillery target selection/effective damage, healer/support survival, and central block/kill/handoff. Do not only say "stay longer" or "heal more."

For each candidate, write a short validation card in existing explanatory fields: parent and hashes, targeted break, exact change, duties and executors, expected events/refutation windows, regression observations, risks, and `MODEL_GAP` for behavior the simulator cannot express. Old event frames belong to their frozen plans and are not universal deadlines. Continuous positions are UNKNOWN without records. Distinguish not attacking artillery, attacking another target, and no legal candidate.

After `check_plan` passes, freeze the exact returned plan/action and run once. On LOSS, query the first observable failure before the validation targets, then classify each prediction as proved, refuted, truncated-by-earlier-failure, or evidence-unknown. Check opening regressions first. Run the second candidate only with new evidence and a materially testable repair; otherwise leave it unused. Do not repeat a similar guess or force quota use. If a complete seven-operator WIN occurs, freeze and stop; do not explore six.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and safely arrived, all enemies settled with no active enemy, and complete settlement. Deaths may be useful, but do not depend on dead operators; deaths have no retreat refund and must settle released enemies, replacement timing, and cost. USER_CONFIRMED_TACTICAL_PREMISE allows attack inducement/rotation/sacrifice, but do not invent guaranteed dodges, lock times, or simulator behavior.

At the end, report exact kills/leaks/life, operator death events versus unique dead IDs, protected outcomes, key enemy settlement, remaining enemies/action errors, model configuration, visible usage, `UNKNOWN_CLI_INTERNAL`, and budget counts. `cached_input` is an input subset and must not be added to total input. Preserve fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum.
"""
    (DEST / "session/codex_cli/sol_prompt_v1.txt").parent.mkdir(parents=True, exist_ok=True)
    (DEST / "session/codex_cli/sol_prompt_v1.txt").write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
