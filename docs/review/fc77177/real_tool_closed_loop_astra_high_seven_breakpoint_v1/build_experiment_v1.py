#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1"
SEVEN_RECURSIVE = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_recursive_v1"
M70 = ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-astra-high-seven-breakpoint-v1"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def copy_events(source: Path, target: Path) -> dict[str, Any]:
    shutil.copyfile(source, target)
    return {"bytes": target.stat().st_size, "sha256": digest(target), "restored_sha256": restored_digest(target)}


def compact_events(path: Path, frames: tuple[int, int], source_id: str | None = None) -> list[dict[str, Any]]:
    payload = json.loads(gzip.decompress(path.read_bytes())) if path.suffix == ".gz" else json.loads(path.read_bytes())
    events = payload["events"] if isinstance(payload, dict) else payload
    result = []
    for event in events:
        if not frames[0] <= event["frame"] <= frames[1]:
            continue
        if source_id and event.get("source_id") != source_id:
            continue
        if event["event_type"] in {"ATTACK_WINDUP", "TARGET_SELECTION", "DEVICE_TARGET_SELECTION"}:
            continue
        result.append(event)
    return result


def main() -> None:
    (BUNDLE / "parent_focused_candidate-002").mkdir(parents=True, exist_ok=True)
    (BUNDLE / "seven_recursive_candidate-001").mkdir(parents=True, exist_ok=True)
    copies = [
        (SOURCE / "input_bundle/llm_evidence_context.json", BUNDLE / "llm_evidence_context.json"),
        (SOURCE / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json"),
        (M70 / "plan_snapshot.json", BUNDLE / "m70_plan_snapshot.json"),
        (M70 / "action_snapshot.json", BUNDLE / "m70_action_snapshot.json"),
        (M70 / "final_status.json", BUNDLE / "m70_final_status.json"),
        (SOURCE / "input_bundle/zero_model_comparison_v1.json", BUNDLE / "seven_recursive_comparison_v1.json"),
        (SEVEN_RECURSIVE / "session/candidates/candidate-001/simulation/plan_snapshot.json", BUNDLE / "seven_recursive_candidate-001/plan_snapshot.json"),
        (SEVEN_RECURSIVE / "session/candidates/candidate-001/simulation/action_snapshot.json", BUNDLE / "seven_recursive_candidate-001/action_snapshot.json"),
        (SEVEN_RECURSIVE / "session/candidates/candidate-001/simulation/final_status.json", BUNDLE / "seven_recursive_candidate-001/final_status.json"),
        (SOURCE / "session/candidates/candidate-002/simulation/plan_snapshot.json", BUNDLE / "parent_focused_candidate-002/plan_snapshot.json"),
        (SOURCE / "session/candidates/candidate-002/simulation/action_snapshot.json", BUNDLE / "parent_focused_candidate-002/action_snapshot.json"),
        (SOURCE / "session/candidates/candidate-002/simulation/final_status.json", BUNDLE / "parent_focused_candidate-002/final_status.json"),
        (SOURCE / "closeout_report_v1.json", BUNDLE / "focused_closeout_report_v1.json"),
    ]
    for source, target in copies:
        shutil.copyfile(source, target)
    event_copies = [
        (SOURCE / "input_bundle/m70_diagnostic_events.json.gz", BUNDLE / "m70_diagnostic_events.json.gz"),
        (SEVEN_RECURSIVE / "session/candidates/candidate-001/simulation/diagnostic_events.json.gz", BUNDLE / "seven_recursive_candidate-001/diagnostic_events.json.gz"),
        (SOURCE / "session/candidates/candidate-002/simulation/diagnostic_events.json.gz", BUNDLE / "parent_focused_candidate-002/diagnostic_events.json.gz"),
    ]
    event_hashes = {str(target.relative_to(BUNDLE)): copy_events(source, target) for source, target in event_copies}

    seven_events_path = BUNDLE / "seven_recursive_candidate-001/diagnostic_events.json.gz"
    focused_events_path = BUNDLE / "parent_focused_candidate-002/diagnostic_events.json.gz"
    focused_breakpoint = compact_events(focused_events_path, (2437, 2595))
    gap_correction = {
        "schema_version": "KIMIARK_SEVEN_BREAKPOINT_GAP_LINEAGE_CORRECTION_V1",
        "boundary": "The named output-gap windows belong to seven-recursive candidate-001, not focused candidate-002. Focused candidate-002 is an independent 2443-2593 death lineage.",
        "seven_recursive_candidate_001": {
            "events_path": BUNDLE / "seven_recursive_candidate-001/diagnostic_events.json.gz" and "input_bundle/seven_recursive_candidate-001/diagnostic_events.json.gz",
            "events_sha256": event_hashes["seven_recursive_candidate-001/diagnostic_events.json.gz"]["sha256"],
            "events_restored_sha256": event_hashes["seven_recursive_candidate-001/diagnostic_events.json.gz"]["restored_sha256"],
            "window_2917_3361": {
                "ordinary_attack_frames": [2917, 2965, 3013, 3061, 3109, 3157],
                "no_candidate_frames": list(range(3205, 3361)),
                "artillery_attack_resumes": 3361,
                "conclusion": "Not a whole-window stop. Attacks continue through 3157, NO_CANDIDATE is 3205-3360, and the artillery is struck at 3361.",
            },
            "window_4225_4705": {
                "ordinary_attack_frames": [4225, 4273, 4321, 4369, 4417, 4465, 4513, 4561, 4609, 4657, 4705],
                "targets": ["enemy_1112_emppnt#0", "enemy_1107_uoffcr#19", "enemy_1107_uoffcr#20", "enemy_1110_uamord#21"],
                "conclusion": "Continuous 48-frame attacks; targeting changes within the window. Continuous positions are UNKNOWN.",
            },
        },
        "focused_candidate_002_breakpoint": {
            "events_path": "input_bundle/parent_focused_candidate-002/diagnostic_events.json.gz",
            "events_sha256": event_hashes["parent_focused_candidate-002/diagnostic_events.json.gz"]["sha256"],
            "events_restored_sha256": event_hashes["parent_focused_candidate-002/diagnostic_events.json.gz"]["restored_sha256"],
            "events_2437_2595": focused_breakpoint,
            "observed_summary": [
                "ENEMY_ABILITY_HIT at 2443: Ansel 891 and Steward 910, both locked_position [7,5].",
                "HEAL at 2443: Ansel heals Steward 506.8.",
                "Steward DAMAGE to artillery at 2449, 2497, 2545.",
                "ENEMY_ABILITY_HIT at 2593: Ansel 891 and Steward 910, both locked_position [7,5].",
                "Steward OPERATOR_DEATH at 2593; no death is projected for Ansel in this window.",
            ],
            "conclusion": "This is an independent Steward/support exposure and splash-survival question. Do not merge it with seven-recursive 2917-3361 or 4225-4705.",
        },
        "coordinate_correction": {
            "plan_action_tiles": "[row,col]",
            "json_tile_to_runtime": "converts [row,col] to runtime (col,row)",
            "deploy_event_detail_tile_string": "runtime [x,y] / [col,row]",
            "non_symmetric_example": "Fang action tile [3,5] becomes DEPLOY event tile '5,3'.",
        },
    }
    write_json(BUNDLE / "gap_window_lineage_correction_v1.json", gap_correction)

    manifest_files = []
    for path in sorted(BUNDLE.rglob("*")):
        if path.is_file():
            entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
            if path.suffix == ".gz":
                entry["restored_sha256"] = restored_digest(path)
            manifest_files.append(entry)
    manifest = {
        "schema_version": "KIMIARK_SEVEN_BREAKPOINT_INPUT_BUNDLE_MANIFEST_V1",
        "files": manifest_files,
    }
    write_json(BUNDLE / "bundle_manifest_v1.json", manifest)

    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R89_ASTRA_HIGH_SEVEN_BREAKPOINT_",
        "plan_label": "ASTRA_HIGH_SEVEN_BREAKPOINT",
        "model": "gpt-6-astra",
        "reasoning_effort": "high",
        "features_apps": False,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "facts_source_dir": "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_v1/input_bundle",
        "session_root": "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_v1/session",
        "budget_path": "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_v1/simulation_budget_v1.json",
        "candidate_ledger_path": "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_v1/candidate_ledger_v1.json",
        "authorization_config_path": "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_v1/model_authorization_v1.json",
        "max_unique_deployed_operators": 7,
        "max_candidates": 2,
        "max_check_calls": 10,
        "max_real_cli_starts": 1,
        "simulation_timeout_seconds": 3600,
        "execution_backend": "CONTROLLED_RUNNER",
        "allow_fake_execution": False,
    }
    write_json(DEST / "session_config_v1.json", config)
    write_json(
        DEST / "simulation_budget_v1.json",
        {
            "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
            "stage_id": "main_08-07",
            "max_stage_simulations": 2,
            "prior_stage_simulations": 0,
            "started_stage_simulations": 0,
        },
    )
    write_json(
        DEST / "candidate_ledger_v1.json",
        {
            "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
            "session_id": SESSION_ID,
            "max_check_calls": 10,
            "used_check_calls": 0,
            "max_candidates": 2,
            "used_candidates": 0,
            "checks": [],
            "attempts": [],
        },
    )
    config_path = (DEST / "session_config_v1.json").relative_to(ROOT).as_posix()
    write_json(
        DEST / "model_authorization_v1.json",
        {
            "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
            "budget_boundary": "New seven-breakpoint experiment; user prompt authorizes one fresh CLI; no old ledger balance is transferred or reset.",
            "provider": "openai",
            "model": "gpt-6-astra",
            "reasoning_effort": "high",
            "features_apps": False,
            "real_cli_starts": {
                "authorized_real_cli_starts": 1,
                "used_real_cli_starts": 0,
                "automatic_retry": False,
                "automatic_resume": False,
                "model_change_or_tier_change_forbidden": True,
            },
            "extra_config_values": [
                "features.apps=false",
                f"mcp_servers.kimiark.command=\"{ROOT / '.venv/bin/python'}\"",
                f"mcp_servers.kimiark.args=[\"{ROOT / 'scripts/kimiark_tactical_stdio_service_v1.py'}\",\"{ROOT / config_path}\"]",
                "mcp_servers.kimiark.required=true",
                "mcp_servers.kimiark.default_tools_approval_mode=\"approve\"",
                "mcp_servers.kimiark.enabled_tools=[\"get_session_status\",\"check_plan\",\"run_simulation\",\"query_events\"]",
            ],
        },
    )


if __name__ == "__main__":
    main()
