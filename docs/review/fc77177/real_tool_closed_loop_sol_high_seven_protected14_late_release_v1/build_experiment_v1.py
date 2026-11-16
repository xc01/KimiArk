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

R106 = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1"
DEST = ROOT / "docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_v1"
BUNDLE = DEST / "input_bundle"
SESSION_ID = "real-tool-loop-sol-high-seven-protected14-late-release-v1"
GOAL = "Legal ordinary-mode 1-3-star, K<=7, complete fixed-simulator WIN; retain R106 #11/#13 and artillery closure while repairing protected #14 exposure and independently closing central armor"


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
    if len(records) != 23:
        raise RuntimeError(f"expected verified 23-record store, got {len(records)}")
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


def fact_pack(parent_identity: dict) -> dict:
    return {
        "schema_version": "KIMIARK_R107_PROTECTED14_LATE_RELEASE_FACT_PACK_V1",
        "boundary": "Observed fixed-simulator events only. No continuous positions, exact HP, complete heal candidate ordering, or causal necessity is asserted. Old frames are not universal deadlines.",
        "primary_parent_r106": {
            **parent_identity,
            "result": {"kills": 22, "leaks": 11, "remaining_life": -9, "win": False},
            "operator_union": ["char_120_hibisc", "char_123_fang", "char_210_stward", "char_212_ansel", "char_283_midn", "char_284_spot", "char_4093_frston"],
            "validated_local_success": {
                "route_11": {"block": 2738, "death": 2881, "killer": "char_123_fang"},
                "route_13": {"block": 3098, "death": 3311, "killer": "char_283_midn"},
                "steward_survival": {"eighth_910_hit": 3911, "retreat_alive": 4280},
                "artillery": {"hit_count": 45, "damage": 13227.21, "first_hit": 2161, "last_hit": 4273, "death": 4273, "leak": None},
            },
        },
        "protected_target_r106_chains": {
            "enemy_3001_upeopl#3": {
                "route": "route-2",
                "spawn": 540,
                "roadblocks": {"roadblock_3_block": 761, "roadblock_3_unblock": 2404, "roadblock_1_block": 2773, "roadblock_1_unblock": 15217},
                "damage_received": "Twelve officer hits at 1296/1356/1416 before early roadblock release, then 5460-5834, 5714-5834, and 6164-6284; no artillery-shell damage recorded.",
                "death": None,
                "reach": 15549,
                "early_failure": "NO_EARLY_FAILURE_IN_R106",
            },
            "enemy_3001_upeopl#14": {
                "route": "route-15",
                "spawn": 3030,
                "roadblock": {"block": 3251, "unblock": None, "device_destroyed": None},
                "officer_hits": [
                    {"frame": 3546, "source": "enemy_1107_uoffcr#16", "amount": 280},
                    {"frame": 3606, "source": "enemy_1107_uoffcr#16", "amount": 280},
                    {"frame": 3666, "source": "enemy_1107_uoffcr#16", "amount": 280},
                    {"frame": 3846, "source": "enemy_1107_uoffcr#18", "amount": 280},
                    {"frame": 3906, "source": "enemy_1107_uoffcr#18", "amount": 280},
                ],
                "artillery_hits": [
                    {"frame": 3611, "source": "enemy_1112_emppnt#0", "amount": 950},
                    {"frame": 3761, "source": "enemy_1112_emppnt#0", "amount": 950},
                    {"frame": 3911, "source": "enemy_1112_emppnt#0", "amount": 950},
                ],
                "death": {"frame": 3911, "source": "enemy_1112_emppnt#0", "life_delta": -1},
                "reach": None,
                "failure_chain": "Roadblock retained, five officer hits and three 950 artillery-shell hits are all observed; exact remaining HP sequence and officer target-selection reasoning are UNKNOWN.",
            },
        },
        "nearby_operators_through_4280": {
            "char_283_midn": {"deploy": 571, "kills": {"#8_unblock": 1819, "#15_unblock": 3818, "#17_unblock": 4208}, "death": 5379},
            "char_284_spot": {"deploy": 901, "blocks": {"officer_16": 3743, "officer_18": 4028}, "skills": [1352, 3303], "death": "UNKNOWN_NOT_IN_WINDOW"},
            "char_210_stward": {"deploy": 2131, "artillery_death": 4273, "retreat": 4280},
            "char_120_hibisc": {"deploy": 1740, "skills": [2642, 4143]},
            "char_212_ansel": {"deploy": 1396, "skills": [2147, 3948]},
            "boundary": "BLOCK/UNBLOCK and DEATH events are observed; planned intent and continuous positions between events are UNKNOWN.",
        },
        "central_r106_observations": {
            "enemy_1110_uamord#21": {"block": {"frame": 4646, "operator": "char_123_fang"}, "unblock": 6298, "death": None, "leak": 6697},
            "enemy_1110_uamord#22": {"block": {"frame": 4796, "operator": "char_4093_frston"}, "unblock": 6262, "death": None, "leak": 6661},
            "enemy_1110_uamord#33": {"block": None, "death": None, "leak": 6846},
            "enemy_1110_uamord#34": {"block": None, "death": None, "leak": 6996},
            "independent_validation": True,
        },
        "main_question": "Repair protected #14's observed exposure/roadblock-release chain without losing #11/#13 closure or artillery closure; central #33/#34 remains independently validated.",
    }


def main() -> None:
    if DEST.exists() and any(DEST.rglob("cli_process_attempt.json")):
        raise RuntimeError("R107 CLI already exists")
    BUNDLE.mkdir(parents=True, exist_ok=True)
    parent_sim = R106 / "session/candidates/candidate-001/simulation"
    parent_dest = BUNDLE / "parent_R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001"
    parent_dest.mkdir(parents=True, exist_ok=True)
    for name in ("plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json.gz", "final_status.json"):
        shutil.copyfile(parent_sim / name, parent_dest / name)
    shutil.copyfile(R106 / "input_bundle/llm_evidence_context.json", BUNDLE / "llm_evidence_context.json")
    shutil.copyfile(R106 / "input_bundle/revision_output_schema.json", BUNDLE / "revision_output_schema.json")
    parent_identity = {
        "lineage_policy": "User explicitly selected R106 candidate-001 as the single primary parent; R104/R105 are reference evidence only.",
        "parent_candidates": [{
            "record_id": "R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001:candidate-001",
            "declared_plan_id": "R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001",
            "final_status_plan_id": "R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001",
            "plan_sha256": digest(parent_dest / "plan_snapshot.json"),
            "action_sha256": digest(parent_dest / "action_snapshot.json"),
            "events_gz_sha256": digest(parent_dest / "diagnostic_events.json.gz"),
            "events_restored_sha256": restored_digest(parent_dest / "diagnostic_events.json.gz"),
            "operator_union_count": 7,
            "archive_status": "VERIFIED",
        }],
        "schema_version": "KIMIARK_R107_FIXED_PARENT_IDENTITY_MANIFEST_V1",
    }
    write_json(BUNDLE / "parent_identity_manifest_v1.json", parent_identity)
    write_json(BUNDLE / "r107_protected14_late_release_fact_pack_v1.json", fact_pack(parent_identity["parent_candidates"][0]))
    records, rebuild_report, context_payload, omitted = selector_context()
    context_path = BUNDLE / "experience_selector_context_v1.json"
    context_path.write_text(json.dumps(context_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    context_digest = digest(context_path)
    selector_state = {
        "schema_version": "KIMIARK_R107_SELECTOR_STATE_V1",
        "selector_code_sha256": digest(ROOT / "scripts/codex_experience_selector_v1.py"),
        "selector_store_sha256": digest(ROOT / "output/codex_experience_selector_v1/experience_records.jsonl"),
        "selector_import_report_sha256": digest(ROOT / "output/codex_experience_selector_v1/experience_records.import_report.json"),
        "rebuild_report": rebuild_report,
        "record_count": len(records),
        "goal": GOAL,
        "requested_k": 7,
        "context_sha256": context_digest,
        "context_bytes": context_path.stat().st_size,
        "context_omitted": omitted,
    }
    write_json(BUNDLE / "experience_selector_state_v1.json", selector_state)
    shutil.copyfile(ROOT / "output/codex_experience_selector_v1/experience_records.jsonl", BUNDLE / "experience_records.jsonl")
    shutil.copyfile(ROOT / "output/codex_experience_selector_v1/experience_records.import_report.json", BUNDLE / "experience_import_report_v1.json")
    manifest = {
        "schema_version": "KIMIARK_R107_INPUT_BUNDLE_MANIFEST_V1",
        "files": [],
    }
    for path in sorted(path for path in BUNDLE.rglob("*") if path.is_file() and path.name != "bundle_manifest_v1.json"):
        entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix == ".gz":
            entry["gzip_original_sha256"] = restored_digest(path)
        manifest["files"].append(entry)
    write_json(BUNDLE / "bundle_manifest_v1.json", manifest)
    print(json.dumps({"bundle": str(BUNDLE), "records": len(records), "context_bytes": selector_state["context_bytes"], "omitted": omitted, "suggested_parent_ids": [item["record_id"] for item in context_payload["parent_candidates"]]}))


if __name__ == "__main__":
    main()
