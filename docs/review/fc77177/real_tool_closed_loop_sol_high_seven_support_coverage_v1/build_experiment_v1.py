#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PRIOR_RETRY3 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry3_v1"
M70_PARENT = ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic"
R91_PARENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_breakpoint_retry2_v1/session/candidates/candidate-002/simulation"
R94_PARENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_retry2_v1/session/candidates/candidate-001/simulation"
R95_C1_PARENT = PRIOR_RETRY3 / "session/candidates/candidate-001/simulation"
R95_C2_EVIDENCE = PRIOR_RETRY3 / "session/candidates/candidate-002/simulation"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_support_coverage_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-support-coverage-v1"


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


def events_between(events: list[dict], low: int, high: int) -> list[dict]:
    return [event for event in events if low <= event["frame"] <= high]


def covered_tiles(origin: tuple[int, int], offsets: tuple[tuple[int, int], ...], direction: str) -> set[tuple[int, int]]:
    rotations = {
        "RIGHT": lambda row, col: (col, row),
        "DOWN": lambda row, col: (row, -col),
        "LEFT": lambda row, col: (-col, -row),
        "UP": lambda row, col: (-row, col),
    }
    return {(origin[0] + rotations[direction](row, col)[0], origin[1] + rotations[direction](row, col)[1]) for row, col in offsets}


def support_coverage() -> dict:
    medic_offsets = tuple((row, col) for row in (-1, 0, 1) for col in range(0, 4))
    steward_offsets = tuple((row, col) for row in (-1, 0, 1) for col in range(0, 4))
    hibiscus = covered_tiles((3, 5), medic_offsets, "RIGHT")
    ansel_base = covered_tiles((6, 5), medic_offsets, "DOWN")
    ansel_skill = ansel_base | covered_tiles((6, 5), tuple((row, col) for row in (-1, 0, 1) for col in (4, 5)), "DOWN")
    steward = covered_tiles((7, 2), steward_offsets, "UP")
    return {
        "transformer": "ApproximateRealRangeTransformer",
        "plan_action_tile_to_runtime_tile": "run_full_diagnostic converts plan tile [a,b] to runtime (b,a); DEPLOY event detail is the runtime tile.",
        "non_symmetric_proof": "R95 Steward plan/action tile [2,7] becomes runtime tile (7,2), shown in DEPLOY event detail as '7,2'.",
        "hibiscus": {
            "plan_tile": [5, 3],
            "runtime_origin": [3, 5],
            "direction": "RIGHT",
            "base_skill_range_cells": [[-1, 0], [-1, 1], [-1, 2], [-1, 3], [0, 0], [0, 1], [0, 2], [0, 3], [1, 0], [1, 1], [1, 2], [1, 3]],
            "effective_coverage_runtime": sorted(hibiscus),
            "covers_r95_steward_runtime_7_2": (7, 2) in hibiscus,
        },
        "ansel": {
            "plan_tile": [5, 6],
            "runtime_origin": [6, 5],
            "direction": "DOWN",
            "base_coverage_runtime": sorted(ansel_base),
            "skill_forward_extend": 2,
            "skill_coverage_runtime": sorted(ansel_skill),
            "covers_r95_steward_runtime_7_2_base": (7, 2) in ansel_base,
            "covers_r95_steward_runtime_7_2_skill": (7, 2) in ansel_skill,
        },
        "steward": {
            "plan_tile": [2, 7],
            "runtime_origin": [7, 2],
            "direction": "UP",
            "base_coverage_runtime": sorted(steward),
        },
    }


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("independent support-coverage experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)

    m70_dir, m70 = parent_identity(
        M70_PARENT,
        label="parent_R8_7_GPT_M70_V1",
        candidate_id="attempt_01_diagnostic",
        plan_id="R8_7_GPT_M70_V1",
    )
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
    r95_c1_dir, r95_c1 = parent_identity(
        R95_C1_PARENT,
        label="parent_R95_SOL_HIGH_SEVEN_RETRY3_001",
        candidate_id="candidate-001",
        plan_id="R95_SOL_HIGH_SEVEN_RETRY3_001",
    )
    r95_c2_dir, r95_c2 = parent_identity(
        R95_C2_EVIDENCE,
        label="evidence_R95_SOL_HIGH_SEVEN_RETRY3_002",
        candidate_id="candidate-002",
        plan_id="R95_SOL_HIGH_SEVEN_RETRY3_002",
    )
    if r95_c1["plan_sha256"] != "61354112963ed25e1efb725456a68aa5faaebb3c677039b9e7b3582be2453237" or r95_c1["action_sha256"] != "1e48691413403bb703aad9fe3159a839e23a56e1f8ce28b112cfc2fe39ffeee8":
        raise RuntimeError("R95 C1 parent hash mismatch")
    if r95_c2["plan_sha256"] != "146cbdee4f5674c2fac1bf7e0f8d101046410873a0ca51b9c9129a9dfda9eac5" or r95_c2["action_sha256"] != "d2713ef9e11baee1ac9ca7c22ba50387b2a42383bb28c78d4af51a39d2dd4342":
        raise RuntimeError("R95 C2 evidence hash mismatch")

    e70 = json.load(gzip.open(m70_dir / "diagnostic_events.json.gz", "rt"))["events"]
    e91 = json.load(gzip.open(r91_dir / "diagnostic_events.json.gz", "rt"))["events"]
    e94 = json.load(gzip.open(r94_dir / "diagnostic_events.json.gz", "rt"))["events"]
    e95_c1 = json.load(gzip.open(r95_c1_dir / "diagnostic_events.json.gz", "rt"))["events"]
    e95_c2 = json.load(gzip.open(r95_c2_dir / "diagnostic_events.json.gz", "rt"))["events"]
    identity_manifest = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SUPPORT_COVERAGE_PARENT_IDENTITY_MANIFEST_V1",
        "directory_naming_policy": "Parent directory names are explicit plan IDs; R95 C2 is retained only as evidence, not as a selectable parent.",
        "lineage_policy": "Sol chooses one authorized parent; successful windows from different plans may not be spliced.",
        "parent_candidates": [r95_c1, r94, r91, m70],
        "evidence_only_candidates": [r95_c2],
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", identity_manifest)

    r95_support_summaries = {}
    for label, events in (("R95_C1", e95_c1), ("R95_C2", e95_c2)):
        damage = compact(events, "DAMAGE", "char_210_stward", "enemy_1112_emppnt#0")
        r95_support_summaries[label] = {
            "steward_artillery_damage": {
                "hit_count": len(damage),
                "total_amount": sum(event["details"]["amount"] for event in damage),
                "first_frame": damage[0]["frame"],
                "last_frame": damage[-1]["frame"],
                "damage_events": damage,
            },
            "ansel_heals_to_steward": compact(events, "HEAL", "char_212_ansel", "char_210_stward"),
            "hibiscus_heals_to_steward": compact(events, "HEAL", "char_120_hibisc", "char_210_stward"),
            "support_heals_in_2700_3043": [
                event for event in events_between(events, 2700, 3043)
                if event["event_type"] == "HEAL" and event.get("source_id") in {"char_120_hibisc", "char_212_ansel"}
            ],
            "artillery_events_in_2700_3043": [
                event for event in events_between(events, 2700, 3043)
                if event.get("source_id") == "enemy_1112_emppnt#0"
                and event["event_type"] in {"ENEMY_ABILITY_START", "PROJECTILE_BORN", "ENEMY_ABILITY_HIT"}
            ],
            "operator_deaths": compact(events, "OPERATOR_DEATH"),
            "leaks": compact(events, "ENEMY_LEAK"),
            "protected_reached": compact(events, "PROTECTED_TARGET_REACHED"),
            "protected_target_deaths": [event for event in events if event["event_type"] == "ENEMY_DEATH" and event["details"].get("life_delta", 0) < 0],
        }
    facts = {
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SUPPORT_COVERAGE_PARENT_FACT_PACK_V1",
        "boundary": "Zero-model compact facts; exact HP at arbitrary frames, continuous positions, and causal sufficiency are UNKNOWN unless separately observed.",
        "coordinates": {
            "plan_action_tiles": "[row,col]",
            "deploy_event_detail": "runtime [x,y]/[col,row]",
            "non_symmetric_proof": "R91 C2 Fang tile [3,5] -> DEPLOY event tile '5,3'.",
        },
        "r95_support_observation": r95_support_summaries,
        "parent_candidates": {
            "R95_C1": r95_c1,
            "R94_C1": r94,
            "R91_C2": r91,
            "M70": m70,
        },
        "support_coverage": support_coverage(),
        "comparison_question": "R95 C1 preserves early clearance/#14 flow but repeats Steward death; R94 proves early clearance but loses support/output; R91 preserves support but fails closure; M70 is the eight-ID WIN baseline. Do not merge windows.",
    }
    write_json(BUNDLE / "support_coverage_fact_pack_v1.json", facts)

    evidence = json.loads((PRIOR_RETRY3 / "input_bundle/llm_evidence_context.json").read_text())
    evidence.pop("cold_start_task_root", None)
    evidence.pop("retry3_parent_fact_pack", None)
    evidence["revision_entry_mode"] = "PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {
        "path": "input_bundle/parent_identity_manifest_v1.json",
        "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"),
        "candidate_plan_ids": [item["declared_plan_id"] for item in identity_manifest["parent_candidates"]],
        "selection_policy": "Model selects one parent and declares it in revision_hypothesis.parent_plan_id and plan parent_plan_id.",
    }
    evidence["support_coverage_parent_fact_pack"] = {
        "path": "input_bundle/support_coverage_fact_pack_v1.json",
        "sha256": digest(BUNDLE / "support_coverage_fact_pack_v1.json"),
    }
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    shutil.copyfile(PRIOR_RETRY3 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")

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
        "schema_version": "KIMIARK_SOL_HIGH_SEVEN_SUPPORT_COVERAGE_INPUT_BUNDLE_MANIFEST_V1",
        "files": manifest_files,
    })

    config_path = DEST / "session_config_v1.json"
    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "plan_id_prefix": "R96_SOL_HIGH_SEVEN_SUPPORT_COVERAGE_",
        "plan_label": "SOL_HIGH_SEVEN_SUPPORT_COVERAGE",
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
        "budget_boundary": "User authorized one fresh support-coverage Sol CLI with two complete simulations; prior ledgers remain closed.",
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

Baseline: M70 `R8_7_GPT_M70_V1` remains the current 8-operator fixed-simulator WIN. Seven-or-fewer feasibility is UNKNOWN. This round targets a concrete support-coverage failure, not another general roster sweep.

The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_support_coverage_v1/input_bundle/`. `parent_identity_manifest_v1.json` names four verified selectable parents: R95 C1, R94 C1, R91 C2, and M70. R95 C2 is copied as evidence only and must not be treated as a parent. Read `support_coverage_fact_pack_v1.json` first; verify plan/action/event hashes before relying on them. Choose a parent because its already-proved duties best fit the issue; state plan ID, plan hash, action hash, and selection reason. Do not splice successful windows from different plans.

Verified R95 observation: in both versions Steward deploys@2071 at plan/action tile [2,7] facing UP. The adapter converts that to runtime tile (7,2). Steward first effectively hits artillery@2281, last hits@3001, totaling 16 hits and 4658.17 damage. The common failure sequence is shell ability start@2793/projectile born@2803 with locked_position [7,2]; hit@2893 for 910; second shell start@2943/projectile born@2953 with the same lock; Ansel heals Steward 506.8@2959; hit@3043 for 910 with same-frame Steward death. Hbiscus deploys at plan tile [5,3] facing RIGHT (C1@1960, C2@2055) and never heals Steward. Coverage calculation says Hbiscus does not cover runtime (7,2); no Hbiscus-to-Steward HEAL is observed. Ansel at plan tile [5,6]/runtime (6,5), DOWN, does cover runtime (7,2) even before skill forward extension. Exact HP at arbitrary frames is UNKNOWN; do not infer it from heal totals or claim that a particular extra heal is sufficient.

Core question: change the actual exposure/support/output sequence rather than merely increasing total healing. Compare support geometry outside the artillery splash, a support that truly covers the caster and is available during the shell cadence, changing artillery-output placement/entry/retreat timing, replacing sustained caster presence, or faster artillery closure. These are exploration directions, not mandatory designs. You may also choose another evidence-supported approach.

Roster is fully open among ordinary-mode 1-3-star IDs; no mandatory keep/remove, fixed core, or new-character quota. The union of selected and all DEPLOY IDs must be <=7; robots count; same-ID redeployment counts once. Do not equate low output with low contribution or infer retention from total healing. Old frames are observations of their frozen plans, not universal deadlines.

Before C1, write a short validation card: parent/hash, specific causal hypothesis and uncertainty, exact change, executors for opening/protection/artillery/central, expected different support/shell/attack events and refutation windows, cost/skill/redeployment/sacrifice accounting, regression observations, and MODEL_GAP. A support change must name the actual beneficiary and available coverage window; a retreat/replacement must settle cost, SP, downtime, released enemies, and replacement exposure. Deaths are allowed but have no refund.

After `check_plan` passes, freeze the exact returned candidate/hash and run once. On LOSS, query first the changed support/shell/output sequence, then the first overall failure. Distinguish support alive, output alive, actually attacking artillery, and completing a kill. Artillery removal does not replace full WIN. Use C2 only when C1 supplies materially new evidence and a concrete, testable repair; if the support/shell/attack sequence did not change, explain why the change failed to propagate rather than repeating an equivalent heal tweak. Stop without forcing the second run if no valid repair exists. If a complete seven-operator WIN occurs, freeze and stop; do not explore six.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and safely arrived, all enemies settled with no active enemy, and complete settlement. At the end report exact kills/leaks/life, death events versus unique dead IDs, protected outcomes, key enemy settlement, remaining enemies/action errors, configured model, visible usage, UNKNOWN_CLI_INTERNAL, and budget counts. `cached_input` is an input subset. Fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum.
"""
    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
