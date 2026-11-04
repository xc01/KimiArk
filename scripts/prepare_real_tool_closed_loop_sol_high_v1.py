#!/usr/bin/env python3
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_v1"
FACTS = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m74_open_reduction_feedback_v1/candidate_v4"
M70 = ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts"
TERRA = ROOT / "docs/review/fc77177/real_tool_closed_loop_terra_v3"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_m70_summary():
    final_status = json.loads((M70 / "attempt_01_diagnostic/final_status.json").read_text())
    plan = json.loads((M70 / "attempt_01_diagnostic/plan_snapshot.json").read_text())
    events = []
    with gzip.open(M70 / "attempt_01_diagnostic/diagnostic_events.json.gz", "rt", encoding="utf-8") as handle:
        document = json.load(handle)
    raw_events = document.get("events", [])
    for event in raw_events:
        if event.get("event_type") in {"PROJECTILE_BORN", "ENEMY_DEATH", "BLOCK", "PROTECTED_TARGET_REACHED"}:
            events.append(event)
    projectiles = [
        event for event in events
        if event.get("event_type") == "PROJECTILE_BORN"
        and 1900 <= event.get("frame", 0) <= 2100
    ]
    artillery_deaths = [
        event for event in events
        if event.get("event_type") == "ENEMY_DEATH"
        and 4200 <= event.get("frame", 0) <= 4350
    ]
    protected_reached = [
        event for event in events
        if event.get("event_type") == "PROTECTED_TARGET_REACHED"
    ]
    protected_deaths = [
        event for event in events
        if event.get("event_type") == "ENEMY_DEATH"
        and str(event.get("target_id", "")).startswith("enemy_3001_upeopl#")
    ]
    officer_34 = [
        event for event in raw_events
        if event.get("event_type") in {"BLOCK", "ENEMY_DEATH"}
        and 6500 <= event.get("frame", 0) <= 7300
    ]
    return {
        "schema_version": "KIMIARK_SOL_HIGH_BASELINE_M70_SUMMARY_V1",
        "source_plan_id": plan["operational_plan_id"],
        "roster": plan["selected_low_star_operator_ids"],
        "final_status": final_status,
        "key_observations": {
            "early_projectile_born": projectiles,
            "artillery_deaths": artillery_deaths,
            "protected_reached_events": protected_reached,
            "protected_target_death_events": protected_deaths,
            "officer_34_block_or_death_events": officer_34,
        },
    }


def make_terra_summary():
    closure = json.loads((TERRA / "closure_report_v1.json").read_text())
    return {
        "schema_version": "KIMIARK_SOL_HIGH_BASELINE_TERRA_V3_SUMMARY_V1",
        "closure_report_source_sha256": sha256(TERRA / "closure_report_v1.json"),
        "interface": closure["interface"],
        "budget": closure["budget"],
        "closure": closure["closure"],
        "candidates": [
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_sha256": candidate["candidate_sha256"],
                "revision_hypothesis": candidate["revision_hypothesis"],
                "deployed_operator_ids": candidate["deployed_operator_ids"],
                "result": candidate["result"],
                "first_leak": candidate["first_leak"],
                "first_objective_failure": candidate["first_objective_failure"],
                "operator_death_count": candidate["operator_death_count"],
                "unique_operator_death_ids": candidate["unique_operator_death_ids"],
                "protected_target_death_count": candidate["protected_target_death_count"],
                "protected_target_reached_count": candidate["protected_target_reached_count"],
            }
            for candidate in closure["candidates"]
        ],
    }


def main():
    bundle = DEST / "baseline_input_bundle"
    (DEST / "session").mkdir(parents=True, exist_ok=True)
    bundle.mkdir(parents=True)

    shutil.copyfile(FACTS / "llm_evidence_context.json", bundle / "m74_llm_evidence_context.json")
    shutil.copyfile(FACTS / "revision_output_schema.json", bundle / "m74_revision_output_schema.json")
    shutil.copyfile(M70 / "attempt_01_diagnostic/final_status.json", bundle / "m70_final_status.json")
    shutil.copyfile(M70 / "attempt_01_diagnostic/plan_snapshot.json", bundle / "m70_plan_snapshot.json")
    shutil.copyfile(
        M70 / "attempt_01_diagnostic/diagnostic_events.json.gz",
        bundle / "m70_diagnostic_events.json.gz",
    )
    shutil.copyfile(TERRA / "closure_report_v1.json", bundle / "terra_v3_closure_report.json")
    write_json(bundle / "m70_success_summary.json", make_m70_summary())
    write_json(bundle / "terra_v3_failure_summary.json", make_terra_summary())

    session_config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": "real-tool-loop-sol-high-v1",
        "stage_id": "main_08-07",
        "plan_id_prefix": "R87_REAL_TOOL_SOL_HIGH_",
        "plan_label": "REAL_TOOL_SOL_HIGH",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "features_apps": False,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "facts_source_dir": "output/r8_1_r8_7_batch_v1/main_08-07/m74_open_reduction_feedback_v1/candidate_v4",
        "session_root": "docs/review/fc77177/real_tool_closed_loop_sol_high_v1/session",
        "budget_path": "docs/review/fc77177/real_tool_closed_loop_sol_high_v1/simulation_budget_v1.json",
        "candidate_ledger_path": "docs/review/fc77177/real_tool_closed_loop_sol_high_v1/candidate_ledger_v1.json",
        "authorization_config_path": "docs/review/fc77177/real_tool_closed_loop_sol_high_v1/model_authorization_v1.json",
        "max_unique_deployed_operators": 7,
        "max_candidates": 5,
        "max_check_calls": 20,
        "simulation_timeout_seconds": 3600,
        "execution_backend": "CONTROLLED_RUNNER",
        "allow_fake_execution": False,
    }
    write_json(DEST / "session_config_v1.json", session_config)
    write_json(DEST / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": "main_08-07",
        "max_stage_simulations": 5,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(DEST / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": "real-tool-loop-sol-high-v1",
        "max_candidates": 5,
        "max_check_calls": 20,
        "used_candidates": 0,
        "used_check_calls": 0,
        "attempts": [],
        "checks": [],
    })
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "provider": "openai",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
        "extra_config_values": [
            'features.apps=false',
            f'mcp_servers.kimiark.command="{ROOT / ".venv/bin/python"}"',
            f'mcp_servers.kimiark.args=["{ROOT / "scripts/kimiark_tactical_stdio_service_v1.py"}","{DEST / "session_config_v1.json"}"]',
            'mcp_servers.kimiark.required=true',
            'mcp_servers.kimiark.default_tools_approval_mode="approve"',
            'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]',
        ],
    })
    write_json(DEST / "baseline_input_bundle/manifest.json", {
        "schema_version": "KIMIARK_REAL_TOOL_CLOSED_LOOP_SOL_HIGH_BASELINE_V1",
        "source_commit_sha256_tree": os.environ.get("KIMIARK_SOURCE_COMMIT", ""),
        "comparison_note": "Future Astra high comparison must reuse this bundle before adding Sol results.",
        "files": [],
    })
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for path in sorted(bundle.iterdir(), key=lambda item: item.name):
        if path.name == "manifest.json":
            continue
        entry = {"path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)}
        if path.suffix == ".gz":
            digest = hashlib.sha256()
            with gzip.open(path, "rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            entry["gzip_original_sha256"] = digest.hexdigest()
        manifest["files"].append(entry)
    write_json(manifest_path, manifest)

    prompt = f"""You are gpt-6.1-sol (reasoning high) in one authorized Codex CLI session for the KimiArk real tool closed loop. Work only in the current repository and use only the local MCP server named `kimiark`.

First call `get_session_status`. Confirm the model, K=7, mechanics, facts, production `CONTROLLED_RUNNER`, 20 check calls, 5 actual run candidates, and 5 complete simulations. Terra v3 ended CLI 1/1, candidate 5/5, simulation 5/5 with no WIN; no balance transfers.

The four tools are:
1. `get_session_status`: read-only status and action/event vocabulary.
2. `check_plan`: no-battle validation. Every executed or idempotent call consumes one of 20 check calls; only PASS creates and consumes one of 5 actual candidates.
3. `run_simulation`: one complete fixed-plan real simulation. STARTED failures count and never retry.
4. `query_events`: read-only event query. `ACTIVATE_SKILL` is accepted as an explicit alias for the log event `SKILL_ACTIVATE`; plan action names and event names are distinct.

Do not call any other model, agent, web service, simulator command, Python tactical search, or shell simulation. Do not modify code, mechanism, budget, authorization or result files. You may use read-only shell to inspect supplied facts. All tactical choices are yours.

Use the fixed facts in `{FACTS.relative_to(ROOT)}/llm_evidence_context.json` and `revision_output_schema.json`. Build one complete ordinary-mode 1-3-star R8-7/main_08-07 plan exactly matching that schema and its existing contract/lineage fields. New plan IDs start with `R87_REAL_TOOL_SOL_HIGH_`; use the supplied previous plan as the parent/lineage reference.

All roles are open. Do not preserve the M70 roster by default or force any removal. Compare at least three substantive structures internally, then select one: earlier kill/decompression, output-plus-tanking, retreat relay, split routes, economy/blocking/medical fusion, or another legal structure. Selected and all DEPLOY union <= 7.

Key context, not universal deadlines:
- M70 eight-person WIN used Fang, Friston-3, Midnight, Melanite, Ansel, Hibiscus, Spot, and Steward. Artillery died at 4273; both protected targets arrived.
- Melanite retreated at 2054 after the second shell locked her old position; Spot deployed later at 2341. A replacement entering the old or adjacent splash zone can still be hit.
- Steward killed artillery at 4273, retreated, returned, and killed #34 after it was actually blocked at 6596.
- Terra v3 completed five LOSS candidates: 21/12/-10, 21/12/-10, 19/14/-13, 14/19/-18, and 20/13/-11 kills/leaks/life. Its roster retained Fang, Vanilla, Midnight, Melanite, Ansel, Hibiscus, and Steward with timing/medical revisions. C1 to C2 delayed Steward's death from 3310 to 3460 but did not close the structural failure. Do not infer a model generalization or global infeasibility from these bounded results.

For each version give a short difference note in existing explanatory fields: artillery contact and sufficient kill timing, continuous shell locks and in-flight splash, medical target competition and survival, economy/refund/deployment handoff, central pressure and #34, road-clearing and protected arrival. State which parts are simulation assumptions. Death has no refund; do not depend on dead operators.

Loop autonomously:
- Check a plan. If static fails, fix the actual schema/contract/action/version issue and check again while check calls remain.
- If PASS, run the exact returned candidate/hash once.
- On LOSS, query focused event windows first, compare prediction to observation, find the earliest upstream break, then submit a substantive revision. Recheck and run while budget remains.
- Stop after a complete WIN (then the authorized ledger has no further simulation), budget exhaustion, a service failure, STARTED_UNKNOWN, or if another run cannot responsibly improve the evidence. Do not repeat the same plan merely to consume quota.

A complete WIN requires the simulator WIN, legal union <= K, zero leaks, both protected targets alive and safely arrived, and all enemies settled with no active enemy. Preserve `debug_configuration` and all execution-required fields. The full baseline snapshot is under `docs/review/fc77177/real_tool_closed_loop_sol_high_v1/baseline_input_bundle/`.
"""
    (DEST / "sol_prompt_v1.txt").write_text(prompt, encoding="utf-8")


if __name__ == "__main__":
    main()
