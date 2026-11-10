#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_retry2_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_duty_conflict_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-astra-high-seven-duty-conflict-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def events(candidate: str) -> list[dict]:
    path = SOURCE / f"session/candidates/{candidate}/simulation/diagnostic_events.json.gz"
    return json.load(gzip.open(path))["events"]


def compact(events: list[dict], event_type: str, source: str | None = None, target: str | None = None) -> list[dict]:
    return [
        {"frame": item["frame"], "source_id": item.get("source_id"), "target_id": item.get("target_id"), "details": item.get("details")}
        for item in events
        if item["event_type"] == event_type and (source is None or item.get("source_id") == source) and (target is None or item.get("target_id") == target)
    ]


def main() -> None:
    (BUNDLE / "parent_c1").mkdir(parents=True, exist_ok=True)
    (BUNDLE / "parent_c2").mkdir(parents=True, exist_ok=True)
    copies = []
    for source, target in [
        (SOURCE / "input_bundle/llm_evidence_context.json", BUNDLE / "llm_evidence_context.json"),
        (SOURCE / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json"),
        (SOURCE / "input_bundle/gap_window_lineage_correction_v1.json", BUNDLE / "gap_window_lineage_correction_v1.json"),
        (SOURCE / "input_bundle/m70_plan_snapshot.json", BUNDLE / "m70_plan_snapshot.json"),
        (SOURCE / "input_bundle/m70_action_snapshot.json", BUNDLE / "m70_action_snapshot.json"),
        (SOURCE / "input_bundle/m70_final_status.json", BUNDLE / "m70_final_status.json"),
        (SOURCE / "input_bundle/m70_diagnostic_events.json.gz", BUNDLE / "m70_diagnostic_events.json.gz"),
        (SOURCE / "input_bundle/parent_focused_candidate-002/plan_snapshot.json", BUNDLE / "focused_parent_plan_snapshot.json"),
        (SOURCE / "input_bundle/parent_focused_candidate-002/action_snapshot.json", BUNDLE / "focused_parent_action_snapshot.json"),
        (SOURCE / "input_bundle/parent_focused_candidate-002/final_status.json", BUNDLE / "focused_parent_final_status.json"),
        (SOURCE / "input_bundle/parent_focused_candidate-002/diagnostic_events.json.gz", BUNDLE / "focused_parent_diagnostic_events.json.gz"),
        (SOURCE / "session/candidates/candidate-001/simulation/plan_snapshot.json", BUNDLE / "parent_c1/plan_snapshot.json"),
        (SOURCE / "session/candidates/candidate-001/simulation/action_snapshot.json", BUNDLE / "parent_c1/action_snapshot.json"),
        (SOURCE / "session/candidates/candidate-001/simulation/final_status.json", BUNDLE / "parent_c1/final_status.json"),
        (SOURCE / "session/candidates/candidate-001/simulation/diagnostic_events.json.gz", BUNDLE / "parent_c1/diagnostic_events.json.gz"),
        (SOURCE / "session/candidates/candidate-002/simulation/plan_snapshot.json", BUNDLE / "parent_c2/plan_snapshot.json"),
        (SOURCE / "session/candidates/candidate-002/simulation/action_snapshot.json", BUNDLE / "parent_c2/action_snapshot.json"),
        (SOURCE / "session/candidates/candidate-002/simulation/final_status.json", BUNDLE / "parent_c2/final_status.json"),
        (SOURCE / "session/candidates/candidate-002/simulation/diagnostic_events.json.gz", BUNDLE / "parent_c2/diagnostic_events.json.gz"),
    ]:
        shutil.copyfile(source, target)
        copies.append(target)

    e1 = events("candidate-001")
    e2 = events("candidate-002")
    facts = {
        "schema_version": "KIMIARK_SEVEN_DUTY_CONFLICT_FACT_PACK_V1",
        "boundary": "This is a zero-model evidence pack. Facts marked HYPOTHESIS are not proven conflicts. Continuous positions and HP between samples are UNKNOWN unless events prove them.",
        "coordinates": {
            "plan_action_tiles": "[row,col]",
            "deploy_event_detail": "runtime [x,y]/[col,row]",
            "non_symmetric_proof": "C1 Fang action tile [3,5] -> DEPLOY event tile '5,3'.",
        },
        "parents": {
            "C1": {
                "candidate_id": "candidate-001",
                "plan_id": "R91_ASTRA_HIGH_SEVEN_BREAKPOINT_RETRY2_001",
                "plan_sha256": digest(BUNDLE / "parent_c1/plan_snapshot.json"),
                "action_sha256": digest(BUNDLE / "parent_c1/action_snapshot.json"),
                "events_gz_sha256": digest(BUNDLE / "parent_c1/diagnostic_events.json.gz"),
                "roster_ids": ["char_123_fang", "char_4093_frston", "char_283_midn", "char_208_melan", "char_212_ansel", "char_120_hibisc", "char_210_stward"],
                "roster_names": ["芬", "Friston-3", "月见夜", "玫兰莎", "安赛尔", "芙蓉", "史都华德"],
                "final": {"kills": 24, "leaks": 9, "operator_deaths": 3, "life": -7, "win": False},
            },
            "C2": {
                "candidate_id": "candidate-002",
                "plan_id": "R91_ASTRA_HIGH_SEVEN_BREAKPOINT_RETRY2_002",
                "plan_sha256": digest(BUNDLE / "parent_c2/plan_snapshot.json"),
                "action_sha256": digest(BUNDLE / "parent_c2/action_snapshot.json"),
                "events_gz_sha256": digest(BUNDLE / "parent_c2/diagnostic_events.json.gz"),
                "roster_ids": ["char_123_fang", "char_4093_frston", "char_283_midn", "char_284_spot", "char_212_ansel", "char_120_hibisc", "char_210_stward"],
                "roster_names": ["芬", "Friston-3", "月见夜", "斑点", "安赛尔", "芙蓉", "史都华德"],
                "final": {"kills": 24, "leaks": 9, "operator_deaths": 2, "life": -8, "win": False},
            },
        },
        "observed_chains": {
            "C1_original_breakpoint": {
                "original_shared_splash_avoided": compact(e1, "ENEMY_ABILITY_HIT", "enemy_1112_emppnt#0", "char_212_ansel")[0:5],
                "steward_isolated_shell_hits": compact(e1, "ENEMY_ABILITY_HIT", "enemy_1112_emppnt#0", "char_210_stward"),
                "steward_death": compact(e1, "OPERATOR_DEATH", "char_210_stward"),
                "steward_artillery_damage_first_last": [compact(e1, "DAMAGE", "char_210_stward", "enemy_1112_emppnt#0")[0], compact(e1, "DAMAGE", "char_210_stward", "enemy_1112_emppnt#0")[-1]],
            },
            "C1_later_loss": {
                "deaths": compact(e1, "OPERATOR_DEATH"),
                "leaks": compact(e1, "ENEMY_LEAK"),
                "roadblocks_destroyed": compact(e1, "DEVICE_DESTROYED"),
                "protected_reached": compact(e1, "PROTECTED_TARGET_REACHED"),
                "protected_target_3_died": "OBJECTIVE_FAILURE@5353 names PROTECTED_TARGET_DEATH; exact killing event must be queried before causal claim.",
            },
            "C2_support_survival": {
                "operator_deaths": compact(e2, "OPERATOR_DEATH"),
                "artillery_leak": compact(e2, "ENEMY_LEAK", "enemy_1112_emppnt#0"),
                "steward_artillery_damage_first_last": [compact(e2, "DAMAGE", "char_210_stward", "enemy_1112_emppnt#0")[0], compact(e2, "DAMAGE", "char_210_stward", "enemy_1112_emppnt#0")[-1]],
                "sample_non_artillery_selections": compact(e2, "TARGET_SELECTION", "char_210_stward")[0:1] + [item for item in compact(e2, "TARGET_SELECTION", "char_210_stward") if item["frame"] == 4147],
            },
            "C2_roadblock4_failure": {
                "chain": [
                    item for item in [
                        *compact(e2, "DEVICE_DAMAGE", target="trap_020_roadblock#4"),
                        *compact(e2, "BLOCK", "trap_020_roadblock#4", "enemy_3001_upeopl#14"),
                        *compact(e2, "DEVICE_DESTROYED", target="trap_020_roadblock#4"),
                    ] if item["frame"] in (2899, 3251, 3283, 3966, 5923)
                ],
                "protected_14_death_frame": 3966,
                "roadblock4_destroyed": 5923,
                "causal_necessity": "UNKNOWN; timing overlap is observed, not proof that any single placement caused all later loss.",
            },
            "C2_central_loss": {
                "leaks": compact(e2, "ENEMY_LEAK")[0:3],
                "deaths": compact(e2, "OPERATOR_DEATH"),
                "observation": "Fang/Friston die at 4903/4920 after the artillery/enemy damage window; #21/#22 leak at 5302/5319. #34 remains in later leak set.",
            },
        },
        "resource_conflict_status": {
            "C2_steward_clearance_and_output_overlap": "HYPOTHESIS: same unit performed both artillery damage and roadblock#4 damage, but the event set does not prove one duty caused late clearance or that no different allocation works.",
            "C2_steward_target_priority_shift": "OBSERVED at sampled frames 2851 and 4147: Steward selected officers rather than artillery. This does not mean all intervening frames had no legal target.",
            "C2_support_survival_vs_protection": "OBSERVED TRADEOFF: fewer operator deaths but both protected targets failed, versus C1 with three deaths but #14 reached.",
        },
    }
    write_json(BUNDLE / "duty_conflict_fact_pack_v1.json", facts)

    manifest_files = []
    for path in sorted(BUNDLE.rglob("*")):
        if path.is_file() and path.name != "bundle_manifest_v1.json":
            entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
            if path.suffix == ".gz":
                entry["restored_sha256"] = restored_digest(path)
            manifest_files.append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", {"schema_version": "KIMIARK_SEVEN_DUTY_CONFLICT_INPUT_BUNDLE_MANIFEST_V1", "files": manifest_files})

    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1", "session_id": SESSION_ID, "stage_id": "main_08-07",
        "plan_id_prefix": "R92_ASTRA_HIGH_SEVEN_DUTY_CONFLICT_", "plan_label": "ASTRA_HIGH_SEVEN_DUTY_CONFLICT",
        "model": "gpt-6-astra", "reasoning_effort": "high", "features_apps": False, "mechanics_version": "m38b-2781-animation-speed-v1",
        "facts_source_dir": BUNDLE.as_posix(), "session_root": (DEST / "session").as_posix(),
        "budget_path": (DEST / "simulation_budget_v1.json").as_posix(), "candidate_ledger_path": (DEST / "candidate_ledger_v1.json").as_posix(),
        "authorization_config_path": (DEST / "model_authorization_v1.json").as_posix(), "max_unique_deployed_operators": 7,
        "max_candidates": 2, "max_check_calls": 10, "max_real_cli_starts": 1, "simulation_timeout_seconds": 3600,
        "execution_backend": "CONTROLLED_RUNNER", "allow_fake_execution": False,
    }
    write_json(DEST / "session_config_v1.json", config)
    write_json(DEST / "simulation_budget_v1.json", {"schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1", "stage_id": "main_08-07", "max_stage_simulations": 2, "prior_stage_simulations": 0, "started_stage_simulations": 0})
    write_json(DEST / "candidate_ledger_v1.json", {"schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2", "session_id": SESSION_ID, "max_check_calls": 10, "used_check_calls": 0, "max_candidates": 2, "used_candidates": 0, "checks": [], "attempts": []})
    cwd = ROOT
    config_path = cwd / (DEST / "session_config_v1.json")
    extra = ["features.apps=false", f'mcp_servers.kimiark.command="{cwd / ".venv/bin/python"}"', f'mcp_servers.kimiark.args=["{cwd / "scripts/kimiark_tactical_stdio_service_v1.py"}","{config_path}"]', "mcp_servers.kimiark.required=true", 'mcp_servers.kimiark.default_tools_approval_mode="approve"', 'mcp_servers.kimiark.enabled_tools=["get_session_status","check_plan","run_simulation","query_events"]']
    write_json(DEST / "model_authorization_v1.json", {"schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1", "budget_boundary": "User authorized one fresh duty-conflict CLI; no old balance is transferred or reset.", "provider": "openai", "model": "gpt-6-astra", "reasoning_effort": "high", "features_apps": False, "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True}, "extra_config_values": extra})


if __name__ == "__main__":
    main()
