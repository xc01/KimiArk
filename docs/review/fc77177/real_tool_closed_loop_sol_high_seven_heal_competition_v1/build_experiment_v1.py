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

R105 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_early_protected_v1"
R104 = ROOT / "docs/review/fc77177/real_tool_closed_loop_deterministic_seven_c2_coupled_retreat_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-heal-competition-v1"
PLAN_PREFIX = "R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_"
GOAL = "Legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN; retain R105 C1 route closure while separating the observed blocker/support heal competition enough to restore the R104 artillery kill window"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def selector_context():
    store = ROOT / "output/codex_experience_selector_v1/experience_records.jsonl"
    records = selector.load_store(store)
    if len(records) != 22:
        raise RuntimeError(f"expected verified 22-record store, got {len(records)}")
    rebuild = BUNDLE / "experience_records.rebuild_check.jsonl"
    report = selector.rebuild_store(store, rebuild)
    if report["missing_from_rebuild"] or any(item.get("error") for item in report["issues"]):
        raise RuntimeError(f"selector rebuild failed: {report}")
    if selector.load_store(rebuild) != records:
        raise RuntimeError("selector rebuild is not record identical")
    payload, omitted = selector.build_context(
        records,
        goal=GOAL,
        k=7,
        target_tags={"ARTILLERY_KILL", "PROTECTED_ROUTE", "ROADBLOCK_CLEARANCE", "SUPPORT_DELIVERY", "CENTRAL_INTERCEPT"},
        byte_limit=28_000,
    )
    return records, report, payload, omitted


def fact_pack() -> dict:
    return {
        "schema_version": "KIMIARK_R106_HEAL_COMPETITION_FACT_PACK_V1",
        "boundary": "Observed fixed-simulator events and static capability facts only. Net damage is not exact HP. Old frames are not new deadlines. No operator is mandatory.",
        "primary_parent_r105_c1": {
            "record_id": "R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001:candidate-001",
            "plan_sha256": "3b8c452a9f0aaf9667f3420ecdf912290ce5c69b984895b46447410563ee5e52",
            "action_sha256": "d48eac7ffe3006947abbc6bbc89e9b517cb441643a8672e40ec78b18d20bdafb",
            "events_gz_sha256": "8d41df1f984342181719b842c9b5469682733080c4006e5f413ec499ba55e6f5",
            "events_restored_sha256": "0dbf92c86e530a9b6183394b1fa3ad2ae568aeaaa3a9e707bfecb9814c5d10cb",
            "result": {"kills": 20, "leaks": 13, "remaining_life": -12, "win": False},
            "operator_union": ["char_120_hibisc", "char_123_fang", "char_210_stward", "char_212_ansel", "char_283_midn", "char_284_spot", "char_4093_frston"],
            "validated_local_success": {
                "route_11": {"block": {"frame": 2738, "source_id": "char_4093_frston"}, "death": {"frame": 2881, "source_id": "char_123_fang"}},
                "route_14": {"block": {"frame": 3098, "source_id": "char_4093_frston"}, "death": {"frame": 3311, "source_id": "char_283_midn"}},
            },
            "validated_local_failure": {
                "steward_death": {"frame": 3911, "source_id": "char_210_stward"},
                "artillery": {"hits": 37, "damage": 10786.03, "last_hit": {"frame": 3889, "amount": 249.1}, "death": None, "leak": 5759},
                "protected_targets": {"enemy_3001_upeopl#3": {"death": 5341}, "enemy_3001_upeopl#14": {"death": 3911}},
                "central_armor_kills": 0,
            },
        },
        "reference_r104_artillery_closed": {
            "record_id": "R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001:candidate-001",
            "plan_sha256": "d91955b06f7bf4145b355152ce2bcd203b3973b469ff4889c6d6d83a1d87048b",
            "action_sha256": "816ec7a9ce93591c5c21c7fea6f811374f0df25238082b483a8a1919c9e7e847",
            "events_gz_sha256": "5b3e33285108938e844cb82cc4d7274494ac16887fd3071087d309c09c424052",
            "boundary": "Reference only; do not splice its successful window into R105 C1.",
            "artillery": {"hits": 45, "damage": 13227.21, "last_hit": {"frame": 4273, "amount": 473.29}, "death": {"frame": 4273}},
            "route_failure": {"route_11": {"leak": 3065, "block": None}, "route_14": {"leak": 3425, "block": None}},
        },
        "normalized_action_diff_r104_to_r105_c1": [
            {"index": 3, "action_type": "DEPLOY", "operator_id": "char_283_midn", "frame": 571, "r104_tile_row_col": [6, 5], "r104_direction": "DOWN", "r105_c1_tile_row_col": [1, 5], "r105_c1_direction": "UP"},
            {"index": 4, "action_type": "DEPLOY", "operator_id": "char_284_spot", "frame": 901, "r104_tile_row_col": [1, 5], "r104_direction": "RIGHT", "r105_c1_tile_row_col": [6, 5], "r105_c1_direction": "RIGHT"},
            {"index": 29, "action_type": "DEPLOY", "operator_id": "char_210_stward", "frame": 11101, "r104_tile_row_col": [2, 7], "r104_direction": "DOWN", "r105_c1_tile_row_col": [5, 7], "r105_c1_direction": "UP"},
        ],
        "shared_core_positions": {
            "char_123_fang": {"frame": 0, "tile_row_col": [3, 5], "direction": "UP", "tile_runtime_col_row": [5, 3]},
            "char_4093_frston": {"frame": 91, "tile_row_col": [4, 5], "direction": "RIGHT", "tile_runtime_col_row": [5, 4]},
            "char_212_ansel": {"frame": 1381, "tile_row_col": [5, 5], "direction": "RIGHT", "tile_runtime_col_row": [5, 5]},
            "char_120_hibisc": {"frame": 1741, "tile_row_col": [2, 6], "direction": "UP", "tile_runtime_col_row": [6, 2]},
            "char_210_stward": {"frame": 2131, "tile_row_col": [5, 7], "direction": "DOWN", "tile_runtime_col_row": [7, 5]},
        },
        "static_healer_capability": {
            "char_212_ansel": {"range_id": "3-3", "direction": "RIGHT", "attack_interval": 2.85, "skill": "skcom_range_extend", "skill_range_forward_extend": 2.0, "skill_duration_frames": 750, "sp_cost": 35},
            "char_120_hibisc": {"range_id": "3-3", "direction": "UP", "attack_interval": 2.85, "skill": "skcom_heal_up[1]", "skill_range_forward_extend": None, "skill_duration_frames": 600, "sp_cost": 30},
            "char_284_spot": {"normal_range_id": "0-1", "direction": "RIGHT", "skill": "skchr_spot_1", "skill_range_id": "x-4", "heal_mode": True, "stops_normal_attacks_while_healing": True, "skill_duration_frames": 750, "sp_cost": 40},
            "medical_target_rule": {
                "confirmed": "The confirmed ratio filter selects the lowest missing-HP-ratio target in range and excludes full HP.",
                "unknown": "Exact equal-ratio tie-break, complete candidate order at each frame, hidden SP state, and precise HP are UNKNOWN.",
            },
        },
        "heal_competition_window_2171_to_3911": {
            "r104_steward_artillery_hit_frames": [2261, 2411, 2561, 2711, 2861, 3611, 3761, 3911],
            "r105_c1_steward_artillery_hit_frames": [2261, 2411, 2561, 2711, 2861, 3611, 3761, 3911],
            "r104_steward_heals": [
                {"frame": 2327, "source": "char_212_ansel", "amount": 506.8}, {"frame": 2343, "source": "char_120_hibisc", "amount": 372.6},
                {"frame": 2413, "source": "char_212_ansel", "amount": 506.8}, {"frame": 2429, "source": "char_120_hibisc", "amount": 372.6},
                {"frame": 2515, "source": "char_120_hibisc", "amount": 61.2}, {"frame": 2585, "source": "char_212_ansel", "amount": 506.8},
                {"frame": 2601, "source": "char_120_hibisc", "amount": 372.6}, {"frame": 2757, "source": "char_212_ansel", "amount": 506.8},
                {"frame": 2773, "source": "char_120_hibisc", "amount": 433.8}, {"frame": 2861, "source": "char_212_ansel", "amount": 506.8},
                {"frame": 2945, "source": "char_120_hibisc", "amount": 403.2}, {"frame": 3611, "source": "char_212_ansel", "amount": 362.0},
                {"frame": 3633, "source": "char_120_hibisc", "amount": 372.6}, {"frame": 3697, "source": "char_212_ansel", "amount": 175.4},
                {"frame": 3761, "source": "char_120_hibisc", "amount": 372.6}, {"frame": 3783, "source": "char_212_ansel", "amount": 362.0},
                {"frame": 3847, "source": "char_120_hibisc", "amount": 175.4},
            ],
            "r105_c1_steward_heals": [
                {"frame": 2327, "source": "char_212_ansel", "amount": 506.8}, {"frame": 2343, "source": "char_120_hibisc", "amount": 372.6},
                {"frame": 2413, "source": "char_212_ansel", "amount": 506.8}, {"frame": 2429, "source": "char_120_hibisc", "amount": 372.6},
                {"frame": 2515, "source": "char_120_hibisc", "amount": 61.2}, {"frame": 2585, "source": "char_212_ansel", "amount": 506.8},
                {"frame": 2601, "source": "char_120_hibisc", "amount": 372.6}, {"frame": 2757, "source": "char_212_ansel", "amount": 506.8},
                {"frame": 2773, "source": "char_120_hibisc", "amount": 433.8}, {"frame": 2929, "source": "char_212_ansel", "amount": 362.0},
                {"frame": 2945, "source": "char_120_hibisc", "amount": 548.0}, {"frame": 3611, "source": "char_212_ansel", "amount": 362.0},
                {"frame": 3697, "source": "char_212_ansel", "amount": 362.0}, {"frame": 3783, "source": "char_212_ansel", "amount": 362.0},
                {"frame": 3869, "source": "char_212_ansel", "amount": 362.0},
            ],
            "r104_steward_heal_total": 6370.0,
            "r105_c1_steward_heal_total": 5998.0,
            "net_damage_through_3911": {
                "r104": {"artillery_damage": 7280.0, "other_damage": 0.0, "heal_total": 6370.0, "net": 910.0, "death": False},
                "r105_c1": {"artillery_damage": 7280.0, "other_damage": 0.0, "heal_total": 5998.0, "net": 1282.0, "death": True},
                "boundary": "Net damage is not exact HP or proof that exactly 372 more healing is sufficient.",
            },
            "friston_heal_comparison_through_3911": {
                "r104": {"events": 6, "total": 2097.6, "context": "Friston died at 2111."},
                "r105_c1": {"events": 17, "total": 3920.0, "context": "Friston survived and became a recurring heal target."},
            },
            "first_observed_target_divergence": [
                {"frame": 2171, "r104": {"source": "char_120_hibisc", "target": "char_212_ansel", "amount": 372.6}, "r105_c1": {"source": "char_120_hibisc", "target": "char_4093_frston", "amount": 372.6}},
                {"frame": 2241, "r104": {"source": "char_212_ansel", "target": "char_283_midn", "amount": 506.8}, "r105_c1": {"source": "char_212_ansel", "target": "char_4093_frston", "amount": 433.4}},
            ],
            "causal_status": "Heal-target diversion is observed; the claim that it was sufficient cause of the 3911 death is HYPOTHESIS, not proven.",
        },
        "independent_duties": {
            "protected_3": {"roadblock_3_is_not_protected_3": True, "r105_c1_death": 5341, "sources": ["enemy_1112_emppnt#0", "enemy_1107_uoffcr#23"], "independent_check_required": True},
            "protected_14": {"r105_c1_death": 3911, "sources": ["enemy_1112_emppnt#0", "enemy_1107_uoffcr#16", "enemy_1107_uoffcr#18"], "independent_check_required": True},
            "central_armor": {"ids": ["enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#33", "enemy_1110_uamord#34"], "r105_c1_deaths": 0, "r105_c1_leaks": {"enemy_1110_uamord#21": 5046, "enemy_1110_uamord#22": 5196, "enemy_1110_uamord#33": 6846, "enemy_1110_uamord#34": 6996}, "independent_check_required": True},
        },
    }


def prompt() -> str:
    return """You are gpt-6.1-sol (reasoning high) in one authorized KimiArk Codex CLI session. Work only in the current repository and use only the local MCP server `kimiark`. First call `get_session_status` and confirm gpt-6.1-sol/high, features.apps=false, K=7, mechanics `m38b-2781-animation-speed-v1`, max_real_cli_starts 1, 5 checks, 1 candidate, and 1 complete simulation. This is an independent ledger; do not resume, transfer, or reset old budgets.

Only `get_session_status`, `check_plan`, `run_simulation`, and `query_events` are permitted. Read-only shell may inspect supplied evidence. Do not use another model/agent, web service, tactical search, or shell simulation. Do not modify code, mechanics, budgets, authorization, or result files. All tactical choices are yours.

M70 remains the eight-operator fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN. The bundle is under `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1/input_bundle/`. Read `experience_selector_context_v1.json` first, then `r106_heal_competition_fact_pack_v1.json` and `r104_r105_c1_divergence_audit_v1.md`, and verify the single R105 C1 parent through `parent_identity_manifest_v1.json`. R105 C1 is the user-selected primary parent; R104 is a separate artillery-closed reference, not a window to splice.

The goal is legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN while retaining R105 C1's observed route closure and testing one concrete mechanism against the observed healer-target competition. C1 blocked/killed #11/#13 but Steward died@3911 after the same eighth 910 artillery hit as R104; C1 delivered 15 Steward heals totaling 5998 versus R104's 17 totaling 6370. C1 also diverted heals to Friston beginning at 2171/2241. This is observed target allocation, not proven sufficient cause of death, and the 372 net difference is not exact HP.

Before check_plan, include in `validation_card.experience_selector_decision_record`: the verified R105 C1 parent ID/hash; at most 3 concrete context observations with record IDs; experiences not applied and why; any similar prior failure and what materially changes; override reason if any; the falsifiable mechanism question; expected/refuting events. State how the concrete change affects #11/#13 interception, actual HEAL allocation to Friston/Ansel/Hibiscus/Steward, Steward damage/heal timing, artillery output until death/kill, shell exposure, protected #3/#14, roadblocks, and central #21/#22/#33/#34. Do not merely write “add healing” or claim a single heal suffices. Do not invent manual heal targeting.

All 34 legal ordinary-mode 1-3-star IDs are open; union of selected and deployed IDs must be <=7, robots count, same-ID redeployment counts once. No operator is mandatory or forbidden. Changes should be focused and may be coupled, but must not abandon route closure without a live replacement, and must not unrelatedly rebuild the whole late plan. Exact HP, full eligible-candidate order, and continuous positions are UNKNOWN where unrecorded; old frames are not new deadlines.

After check_plan passes, freeze the exact candidate/hash and run once; there is no second candidate. Query the earliest failure first, then #11/#13, HEAL recipients, Steward/artillery hits, artillery death/leak, protected targets, and central chains. A route kill alone is not artillery closure; artillery death alone is not WIN. A global LOSS does not refute an observed local hypothesis if its prerequisite remained observable.

WIN requires simulator WIN, legal union <=7, zero leaks, both protected targets alive and reached, every enemy settled with no active enemy, and complete settlement. Report exact kills/leaks/life, death events versus unique dead IDs, protected outcomes, key enemy settlement, action errors, configured model, visible usage, UNKNOWN_CLI_INTERNAL, and budget counts. `cached_input` is an input subset. Fixed-simulator scope only; do not claim real-game, faithful, robust, probabilistic WIN, seven-ID-impossible, or global minimum."""


def main() -> None:
    if (DEST / "session_config_v1.json").exists():
        raise RuntimeError("R106 experiment already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (DEST / "session/codex_cli").mkdir(parents=True, exist_ok=True)

    parent = BUNDLE / "parent_R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001"
    parent.mkdir(parents=True, exist_ok=True)
    parent_sources = R105 / "session/candidates/candidate-001/simulation"
    for name in ("plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "final_status.json"):
        shutil.copyfile(parent_sources / name, parent / name)
    shutil.copyfile(R105 / "r104_r105_c1_divergence_audit_v1.md", BUNDLE / "r104_r105_c1_divergence_audit_v1.md")
    parent_manifest = {
        "schema_version": "KIMIARK_R106_FIXED_PARENT_IDENTITY_MANIFEST_V1",
        "parent_candidates": [{
            "record_id": "R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001:candidate-001",
            "declared_plan_id": "R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001",
            "final_status_plan_id": "R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001",
            "plan_sha256": digest(parent / "plan_snapshot.json"),
            "action_sha256": digest(parent / "action_snapshot.json"),
            "events_gz_sha256": digest(parent / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(parent / "diagnostic_events.json.gz"),
            "operator_union_count": 7,
            "archive_status": "VERIFIED",
        }],
        "lineage_policy": "User explicitly selected R105 C1 as the single primary parent; R104 remains an independent artillery-closed reference.",
    }
    expected = fact_pack()["primary_parent_r105_c1"]
    actual = parent_manifest["parent_candidates"][0]
    for key in ("plan_sha256", "action_sha256", "events_gz_sha256", "events_restored_sha256"):
        if actual[key] != expected[key]:
            raise RuntimeError(f"R105 C1 parent hash mismatch: {key}")
    write_json(BUNDLE / "parent_identity_manifest_v1.json", parent_manifest)

    records, rebuild_report, context, context_omitted = selector_context()
    store_path = BUNDLE / "experience_records.jsonl"
    store_path.write_bytes((ROOT / "output/codex_experience_selector_v1/experience_records.jsonl").read_bytes())
    report_path = BUNDLE / "experience_import_report_v1.json"
    report_path.write_bytes((ROOT / "output/codex_experience_selector_v1/experience_records.import_report.json").read_bytes())
    write_json(BUNDLE / "experience_selector_state_v1.json", {
        "schema_version": "KIMIARK_EXPERIENCE_SELECTOR_STATE_V1",
        "selector_code_sha256": digest(ROOT / "scripts/codex_experience_selector_v1.py"),
        "selector_store_sha256": digest(store_path),
        "selector_import_report_sha256": digest(report_path),
        "rebuild_report": rebuild_report,
        "context_omitted": context_omitted,
        "context_bytes": len(json.dumps(context, ensure_ascii=False, sort_keys=True).encode()),
        "context_sha256": hashlib.sha256(json.dumps(context, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "selection_policy": "Deterministic tag/branch retrieval; advisory only. R105 C1 is the user-selected primary parent, not assumed to be the selector's top result.",
    })
    write_json(BUNDLE / "experience_selector_context_v1.json", context)
    write_json(BUNDLE / "r106_heal_competition_fact_pack_v1.json", fact_pack())

    evidence = json.loads((R105 / "input_bundle/llm_evidence_context.json").read_text())
    evidence.pop("r105_early_route_protected_fact_pack_v1", None)
    evidence["revision_entry_mode"] = "FIXED_PARENT_CANDIDATE_REVISION_V1"
    evidence["parent_identity_manifest"] = {
        "path": "input_bundle/parent_identity_manifest_v1.json",
        "sha256": digest(BUNDLE / "parent_identity_manifest_v1.json"),
        "candidate_plan_ids": ["R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001"],
        "selection_policy": "R105 C1 is the user-selected primary parent; R104 is evidence only.",
    }
    evidence["experience_selector_context_v1"] = {
        "path": "input_bundle/experience_selector_context_v1.json",
        "sha256": digest(BUNDLE / "experience_selector_context_v1.json"),
        "advisory_status": "SUGGESTIONS_AND_CONDITIONAL_EVIDENCE_ONLY",
    }
    evidence["r106_heal_competition_fact_pack_v1"] = {
        "path": "input_bundle/r106_heal_competition_fact_pack_v1.json",
        "sha256": digest(BUNDLE / "r106_heal_competition_fact_pack_v1.json"),
        "boundary": "Verified observed windows, static capability facts, and explicit UNKNOWN boundaries; no role is mandatory.",
    }
    evidence["r104_r105_c1_divergence_audit_v1"] = {
        "path": "input_bundle/r104_r105_c1_divergence_audit_v1.md",
        "sha256": digest(BUNDLE / "r104_r105_c1_divergence_audit_v1.md"),
        "boundary": "Observed-event audit and explicit hypothesis/UNKNOWN separation.",
    }
    evidence["experience_selector_decision_record_policy"] = {
        "maximum_context_observations_cited": 3,
        "required_fields": ["selected_parent", "adopted_observations", "non_applicable_experiences", "similar_prior_failure_change", "override_reason_if_any"],
        "placement": "validation_card.experience_selector_decision_record",
        "constraint": "Visible structured record; hidden reasoning is not required.",
    }
    write_json(BUNDLE / "llm_evidence_context.json", evidence)
    shutil.copyfile(R105 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")

    extra = [
        "mcp_servers.kimiark.command=\"/home/bigdata/Desktop/arknights-auto-planner/.venv/bin/python\"",
        "mcp_servers.kimiark.args=[\"/home/bigdata/Desktop/arknights-auto-planner/scripts/kimiark_tactical_stdio_service_v1.py\",\"/home/bigdata/Desktop/arknights-auto-planner/docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1/session_config_v1.json\"]",
        "mcp_servers.kimiark.enabled=true",
        "mcp_servers.kimiark.required=true",
        "mcp_servers.kimiark.default_tools_approval_mode=\"approve\"",
        "mcp_servers.kimiark.enabled_tools=[\"get_session_status\",\"check_plan\",\"run_simulation\",\"query_events\"]",
    ]
    write_json(DEST / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "budget_boundary": "User authorized one fresh Sol CLI with 5 checks, 1 candidate, and 1 complete simulation; prior ledgers remain closed.",
        "provider": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high", "features_apps": False,
        "real_cli_starts": {"authorized_real_cli_starts": 1, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False, "model_change_or_tier_change_forbidden": True},
        "extra_config_values": extra,
    })
    write_json(DEST / "session_config_v1.json", {
        "allow_fake_execution": False,
        "authorization_config_path": str(DEST / "model_authorization_v1.json"),
        "budget_path": str(DEST / "simulation_budget_v1.json"),
        "candidate_ledger_path": str(DEST / "candidate_ledger_v1.json"),
        "execution_backend": "CONTROLLED_RUNNER",
        "facts_source_dir": str(BUNDLE),
        "features_apps": False,
        "max_candidates": 1,
        "max_check_calls": 5,
        "max_real_cli_starts": 1,
        "max_unique_deployed_operators": 7,
        "mechanics_version": "m38b-2781-animation-speed-v1",
        "model": "gpt-6.1-sol",
        "plan_id_prefix": PLAN_PREFIX,
        "plan_label": "SOL_HIGH_SEVEN_HEAL_COMPETITION",
        "reasoning_effort": "high",
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": SESSION_ID,
        "session_root": str(DEST / "session"),
        "simulation_timeout_seconds": 3600,
        "stage_id": "main_08-07",
    })
    write_json(DEST / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": "main_08-07",
        "max_stage_simulations": 1,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write_json(DEST / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": SESSION_ID,
        "stage_id": "main_08-07",
        "max_candidates": 1,
        "used_candidates": 0,
        "attempts": [],
        "checks": [],
    })

    prompt_path = DEST / "session/codex_cli/sol_prompt_v1.txt"
    prompt_path.write_text(prompt() + "\n")

    files = [path for path in BUNDLE.rglob("*") if path.is_file() and path.name != "bundle_manifest_v1.json"]
    manifest = {
        "schema_version": "KIMIARK_R106_INPUT_BUNDLE_MANIFEST_V1",
        "files": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)} for path in sorted(files)],
    }
    write_json(BUNDLE / "bundle_manifest_v1.json", manifest)


if __name__ == "__main__":
    main()
