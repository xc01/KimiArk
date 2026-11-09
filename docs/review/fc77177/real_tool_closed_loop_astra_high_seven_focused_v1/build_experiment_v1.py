import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_recursive_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1"
SESSION_ID = "real-tool-loop-astra-high-seven-focused-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    bundle = DEST / "input_bundle"
    if not bundle.exists():
        shutil.copytree(SOURCE / "input_bundle", bundle)
    comparison = SOURCE / "zero_model_comparison_v1.json"
    shutil.copyfile(comparison, bundle / "zero_model_comparison_v1.json")
    for source, target in [
        (SOURCE / "next_prompt_suggestion_v2.md", bundle / "next_prompt_suggestion_v2.md"),
        (
            ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic/plan_snapshot.json",
            bundle / "m70_plan_snapshot.json",
        ),
        (
            ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic/action_snapshot.json",
            bundle / "m70_action_snapshot.json",
        ),
        (
            ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic/diagnostic_events.json.gz",
            bundle / "m70_diagnostic_events.json.gz",
        ),
        (
            SOURCE / "session/candidates/candidate-001/simulation/plan_snapshot.json",
            bundle / "seven_recursive_plan_snapshot.json",
        ),
        (
            SOURCE / "session/candidates/candidate-001/simulation/action_snapshot.json",
            bundle / "seven_recursive_action_snapshot.json",
        ),
        (
            SOURCE / "session/candidates/candidate-001/simulation/diagnostic_events.json.gz",
            bundle / "seven_recursive_diagnostic_events.json.gz",
        ),
    ]:
        shutil.copyfile(source, target)

    manifest = bundle / "bundle_manifest_v1.json"
    manifest_paths = sorted(path for path in bundle.rglob("*") if path.is_file() and path != manifest)
    manifest_payload = {
        "schema_version": "KIMIARK_SEVEN_FOCUSED_INPUT_BUNDLE_MANIFEST_V1",
        "files": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in manifest_paths
        ],
    }
    write_json(manifest, manifest_payload)

    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R89_ASTRA_HIGH_SEVEN_FOCUSED_",
        "plan_label": "ASTRA_HIGH_SEVEN_FOCUSED",
        "model": "gpt-6-astra",
        "reasoning_effort": "high",
        "features_apps": False,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "facts_source_dir": f"docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1/input_bundle",
        "session_root": f"docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1/session",
        "budget_path": f"docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1/simulation_budget_v1.json",
        "candidate_ledger_path": f"docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1/candidate_ledger_v1.json",
        "authorization_config_path": f"docs/review/fc77177/real_tool_closed_loop_astra_high_seven_focused_v1/model_authorization_v1.json",
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
            "budget_boundary": "New focused seven-ID experiment; no old ledger balance is transferred or reset.",
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
                f"mcp_servers.kimiark.command=\"/home/bigdata/Desktop/arknights-auto-planner/.venv/bin/python\"",
                f"mcp_servers.kimiark.args=[\"/home/bigdata/Desktop/arknights-auto-planner/scripts/kimiark_tactical_stdio_service_v1.py\",\"/home/bigdata/Desktop/arknights-auto-planner/{config_path}\"]",
                "mcp_servers.kimiark.required=true",
                "mcp_servers.kimiark.default_tools_approval_mode=\"approve\"",
                "mcp_servers.kimiark.enabled_tools=[\"get_session_status\",\"check_plan\",\"run_simulation\",\"query_events\"]",
            ],
        },
    )


if __name__ == "__main__":
    main()
