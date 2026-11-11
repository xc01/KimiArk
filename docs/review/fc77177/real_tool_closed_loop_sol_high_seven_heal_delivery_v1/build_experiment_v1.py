#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path

from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.simulator import ApproximateRealRangeTransformer


ROOT = Path(__file__).resolve().parents[4]
AUDIT = ROOT / "docs/review/fc77177/zero_model_m70_artillery_support_audit_v1"
R97 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_support_geometry_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_delivery_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-heal-delivery-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def copy_parent(source: Path, *, label: str, candidate_id: str, expected: dict | None = None) -> dict:
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
    if result["declared_plan_id"] != result["final_status_plan_id"]:
        raise RuntimeError(f"plan_id mismatch: {result}")
    if expected:
        for key in ("plan_sha256", "action_sha256", "events_gz_sha256", "events_restored_sha256"):
            if result[key] != expected[key]:
                raise RuntimeError(f"parent hash mismatch for {label}: {key}")
    return result


def covered(origin: tuple[int, int], operator_id: str, direction: str, repository: GameDataRepository, transformer: ApproximateRealRangeTransformer) -> set[tuple[int, int]]:
    operator = repository.get_operator(operator_id)
    range_id = operator.phases[-1].range_id.value
    cells = [(cell.row, cell.col) for cell in repository.get_range(range_id).cells]
    return transformer.covered_tiles(origin=origin, offsets=cells, direction=direction)


def relevant_events(events: list[dict], low: int = 1900, high: int = 2480) -> list[dict]:
    wanted = {"DEPLOY", "HEAL", "DAMAGE", "ENEMY_ABILITY_HIT", "OPERATOR_DEATH"}
    return [
        {
            "frame": event["frame"],
            "event_type": event["event_type"],
            "source_id": event.get("source_id"),
            "target_id": event.get("target_id"),
            "details": event.get("details", {}),
        }
        for event in events
        if low <= event["frame"] <= high and event["event_type"] in wanted
    ]


def fact_pack() -> dict:
    audit_index = json.loads((AUDIT / "comparison_index_v1.json").read_text())
    audit_facts = json.loads((AUDIT / "next_fact_pack_draft_v1.json").read_text())
    closeout = json.loads((R97 / "closeout_report_v1.json").read_text())
    r97_candidate = closeout["candidates"][1]
    events_path = R97 / "session/candidates/candidate-002/simulation/diagnostic_events.json.gz"
    with gzip.open(events_path, "rt") as handle:
        events = json.loads(handle.read())["events"]

    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    transformer = ApproximateRealRangeTransformer()
    hibiscus = (3, 5)
    ansel = (5, 5)
    steward = (6, 5)
    hibiscus_coverage = covered(hibiscus, "char_120_hibisc", "RIGHT", repository, transformer)
    ansel_coverage = covered(ansel, "char_212_ansel", "DOWN", repository, transformer)
    simulator_path = ROOT / "src/arknights_planner/simulator/simulator.py"
    simulator_lines = simulator_path.read_text().splitlines()

    r97_plan = json.loads((R97 / "session/candidates/candidate-002/simulation/plan_snapshot.json").read_text())
    key_ids = {"char_120_hibisc", "char_212_ansel", "char_210_stward", "enemy_1112_emppnt#0"}
    return {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_HEAL_DELIVERY_FACT_PACK_V1",
        "boundary": "Zero-model compact facts. Exact HP, complete ally-heal candidate order, continuous positions, and causal sufficiency are UNKNOWN unless directly observed.",
        "coordinates": audit_facts["coordinates"],
        "core_observation": audit_index["observed_core"],
        "r97_c2_delivery_observation": {
            "plan_id": r97_candidate["plan_id"],
            "candidate_sha256": r97_candidate["candidate_sha256"],
            "plan_sha256": r97_candidate["plan_sha256"],
            "action_sha256": r97_candidate["action_sha256"],
            "events_gz_sha256": r97_candidate["events_gz_sha256"],
            "events_restored_sha256": r97_candidate["events_restored_sha256"],
            "planned_change": r97_plan.get("validation_card", {}).get("exact_change"),
            "first_planned_deployments": {
                operator_id: deployment
                for operator_id, deployment in r97_candidate["first_planned_deployments"].items()
                if operator_id in {"char_120_hibisc", "char_212_ansel", "char_210_stward", "char_208_melan"}
            },
            "coverage": {
                "transformer": "ApproximateRealRangeTransformer",
                "hibiscus_runtime_origin": list(hibiscus),
                "hibiscus_covers_ansel_5_5": ansel in hibiscus_coverage,
                "hibiscus_covers_steward_6_5": steward in hibiscus_coverage,
                "ansel_runtime_origin": list(ansel),
                "ansel_covers_steward_6_5": steward in ansel_coverage,
                "boundary": "Geometric coverage does not imply target selection, an emitted heal, or sufficient healing.",
            },
            "window_frames": [1900, 2480],
            "relevant_events": relevant_events(events),
            "observed_delivery": {
                "ansel_to_steward_heal_2323": True,
                "hibiscus_to_steward_heal_in_window": any(
                    event["event_type"] == "HEAL"
                    and event["source_id"] == "char_120_hibisc"
                    and event["target_id"] == "char_210_stward"
                    for event in relevant_events(events)
                ),
                "hibiscus_to_ansel_heal_2390": any(
                    event["event_type"] == "HEAL"
                    and event["frame"] == 2390
                    and event["source_id"] == "char_120_hibisc"
                    and event["target_id"] == "char_212_ansel"
                    for event in relevant_events(events)
                ),
                "steward_artillery_damage": r97_candidate["observed_key_events"]["steward_artillery_damage"],
                "heals_to_steward": r97_candidate["observed_key_events"]["heals_to_steward"],
                "steward_death_2473": "char_210_stward" in r97_candidate["observed_key_events"]["unique_operator_death_ids"],
                "artillery_death": r97_candidate["observed_key_events"]["artillery_death"],
            },
            "target_selection_limit": "The ally-heal path does not emit a TARGET_SELECTION record. Full eligible-candidate list, exact HP values, and exact ratios at 2390 are UNKNOWN_LOG_LIMIT.",
        },
        "heal_target_selection_code": {
            "source_path": simulator_path.relative_to(ROOT).as_posix(),
            "source_sha256": digest(simulator_path),
            "rule_lines": [550, 553, 555, 559],
            "rule": "Eligible allies are deployed, inside the healer's effective range, and hp + epsilon < max_hp. The healer selects minimum hp/max_hp, tie-broken by operator_id. There is no manual target-selection action.",
            "rule_source_excerpt": "\n".join(simulator_lines[549:559]),
        },
        "catalog": audit_facts["catalog"],
        "audit_index": {
            "path": (AUDIT / "comparison_index_v1.json").relative_to(ROOT).as_posix(),
            "sha256": digest(AUDIT / "comparison_index_v1.json"),
        },
        "r97_closeout": {
            "path": (R97 / "closeout_report_v1.json").relative_to(ROOT).as_posix(),
            "sha256": digest(R97 / "closeout_report_v1.json"),
        },
    }


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("independent heal-delivery experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)

    audit_index = json.loads((AUDIT / "comparison_index_v1.json").read_text())
    closeout = json.loads((R97 / "closeout_report_v1.json").read_text())
    parent_by_label = {
        "R97_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_001": R97 / "session/candidates/candidate-001/simulation",
        "R97_SOL_HIGH_SEVEN_SUPPORT_GEOMETRY_002": R97 / "session/candidates/candidate-002/simulation",
    }
    parents = []
    for source in audit_index["sources"].values():
        source_dir = ROOT / source["paths"]["plan"].rsplit("/", 1)[0]
        parents.append(copy_parent(
            source_dir,
            label=f"parent_{source['plan_id']}",
            candidate_id=source["source_candidate_id"] if "source_candidate_id" in source else source.get("source_candidate_id", source["plan_id"]),
            expected={
                "plan_sha256": source["sha256"]["plan"],
                "action_sha256": source["sha256"]["action"],
                "events_gz_sha256": source["sha256"]["events_gz"],
                "events_restored_sha256": source["sha256"]["events_restored"],
            },
        ))
    for item in closeout["candidates"]:
        plan_id = item["plan_id"]
        source_dir = parent_by_label[plan_id]
        parents.append(copy_parent(
            source_dir,
            label=f"parent_{plan_id}",
            candidate_id=item["candidate_id"],
            expected={
                "plan_sha256": item["plan_sha256"],
                "action_sha256": item["action_sha256"],
                "events_gz_sha256": item["events_gz_sha256"],
                "events_restored_sha256": item["events_restored_sha256"],
            },
        ))

    identity_manifest = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_HEAL_DELIVERY_PARENT_IDENTITY_MANIFEST_V1",
        "directory_naming_policy": "Parent directory names are explicit plan IDs.",
        "lineage_policy": "Sol selects exactly one parent; successful windows from different plans may not be spliced.",
        "parent_candidates": parents,
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", identity_manifest)
    facts = fact_pack()
    write_json(BUNDLE / "heal_delivery_fact_pack_v1.json", facts)

    prior_context_path = R97 / "input_bundle/llm_evidence_context.json"
    evidence = json.loads(prior_context_path.read_text())
    evidence.pop("cold_start_task_root", None)
    evidence.pop("retry3_parent_fact_pack", None)
    evidence.pop("support_coverage_parent_fact_pack", None)
    evidence.pop("support_geometry_parent_fact_pack", None)
    evidence["revision_entry_mode"] = "PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {
        "path": "input_bundle/parent_identity_manifest_v1.json",
        "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"),
        "candidate_plan_ids": [item["declared_plan_id"] for item in parents],
        "selection_policy": "Model selects one parent and declares it in revision_hypothesis.parent_plan_id and plan parent_plan_id.",
    }
    evidence["heal_delivery_parent_fact_pack"] = {
        "path": "input_bundle/heal_delivery_fact_pack_v1.json",
        "sha256": digest(BUNDLE / "heal_delivery_fact_pack_v1.json"),
    }
    evidence["r97_next_prompt_suggestion"] = {
        "path": (R97 / "next_prompt_suggestion_v1.md").relative_to(ROOT).as_posix(),
        "sha256": digest(R97 / "next_prompt_suggestion_v1.md"),
    }
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    shutil.copyfile(R97 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")

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
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_HEAL_DELIVERY_INPUT_BUNDLE_MANIFEST_V1",
        "files": manifest_files,
    })

    config_path = DEST / "session_config_v1.json"
    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R98_SOL_HIGH_SEVEN_HEAL_DELIVERY_",
        "plan_label": "SOL_HIGH_SEVEN_HEAL_DELIVERY",
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
        "budget_boundary": "User authorized one fresh heal-delivery Sol CLI with two complete simulations; prior ledgers remain closed.",
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

M70 remains the eight-operator fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN. The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_delivery_v1/input_bundle/`. Read `heal_delivery_fact_pack_v1.json` first and verify parent hashes through `parent_identity_manifest_v1.json`. Eight audited plans are selectable parents; do not splice successful windows from different plans.

R97 C2 is the key negative evidence: Hibiscus at runtime (3,5) RIGHT geometrically covered both Ansel (5,5) and Steward (6,5), and Ansel covered Steward. But observed delivery was Hibiscus→Melantha at 2046/2132/2304, Hibiscus self-heal at 2218, Ansel→Steward 506.8 at 2323, Hibiscus→Ansel 372.6 at 2390, and no Hibiscus→Steward heal before Steward's second 910 shell/death at 2473. Steward hit artillery nine times for 2,466.09. The simulator's ally-heal rule selects the injured in-range ally with minimum HP ratio, tie-broken by operator ID; no manual target action exists. Full candidate list and exact HP at 2390 are UNKNOWN_LOG_LIMIT.

The core question is whether artillery output can be sustained through real target competition and the shell cycle until actual artillery death, without sacrificing a necessary blocker/support duty. You may reduce competing injuries, change damage timing, alter output executor/window, rotate duties, or use another concrete mechanism. Do not force Steward, dual medics, a specific tile, or a manual heal-target override. All 34 legal ordinary-mode 1-3-star IDs are open; union of selected and deployed IDs must be <=7, robots count, same-ID redeployment counts once.

Before C1, write a validation card naming the one parent and hashes, the causal change, how it alters eligible heal candidates/HP ratios/shell timing/output window rather than merely claiming coverage, and who performs opening, roadblocks, both protected routes, artillery closure, and central #21/#22/#34 duties. Include cost/skill/redeployment/sacrifice accounting, risks, refutable events, and MODEL_GAP. Coverage is not selection; a heal is not sufficiency; exact HP is UNKNOWN without records. Do not convert old frames into deadlines.

After check_plan passes, freeze the exact candidate/hash and run once. Query the earliest failure first, then the targeted heal/target/output chain. Distinguish alive, injured, eligible, selected, healed, output alive, attacked artillery, and artillery killed. Run C2 only for a materially different repair supported by C1 evidence; otherwise stop. If a complete seven-operator WIN occurs, freeze and stop; do not explore six.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and reached, every enemy settled with no active enemy, and complete settlement. Report exact kills/leaks/life, death events versus unique dead IDs, protected outcomes, key enemy settlement, action errors, configured model, visible usage, UNKNOWN_CLI_INTERNAL, and budget counts. `cached_input` is an input subset. Fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum."""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
