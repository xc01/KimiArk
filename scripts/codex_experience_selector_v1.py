#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "KIMIARK_CODEX_EXPERIENCE_SELECTOR_V1"
STORE_SCHEMA_VERSION = "KIMIARK_CODEX_EXPERIENCE_STORE_V1"
DEFAULT_STORE = Path("output/codex_experience_selector_v1/experience_records.jsonl")
DEFAULT_CATALOG = Path("output/normal_low_star_facts_v1/normal_low_star_facts.json")

MECHANICS_VERSION = "m38b-2781-animation-speed-v1"
STAGE_ID = "main_08-07"
ARTILLERY_IDS = {"enemy_1112_emppnt#0"}
CENTRAL_IDS = {
    "enemy_1110_uamord#21", "enemy_1110_uamord#22",
    "enemy_1110_uamord#33", "enemy_1110_uamord#34",
}
PROTECTED_IDS = {"enemy_3001_upeopl#14", "enemy_3001_upeopl#3"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_events(path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    compressed = path.read_bytes()
    if not compressed.startswith(b"\x1f\x8b"):
        raise ValueError(f"not gzip: {path}")
    try:
        restored = gzip.decompress(compressed)
    except Exception as error:
        raise ValueError(f"corrupt gzip: {path}: {error}") from error
    if restored.startswith(b"\x1f\x8b"):
        raise ValueError(f"double gzip: {path}")
    try:
        payload = json.loads(restored.decode("utf-8"))
    except Exception as error:
        raise ValueError(f"invalid restored JSON: {path}: {error}") from error
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError(f"missing events array: {path}")
    return events, {
        "events_gz_sha256": sha256_bytes(compressed),
        "events_restored_sha256": sha256_bytes(restored),
        "event_count": str(len(events)),
    }


def _expected_from_closeout(candidate: dict[str, Any], plan: Path, action: Path, events: Path) -> dict[str, Any]:
    expected = {
        "plan_sha256": candidate.get("plan_sha256"),
        "action_sha256": candidate.get("action_sha256"),
        "events_gz_sha256": candidate.get("events_gz_sha256"),
        "events_restored_sha256": candidate.get("events_restored_sha256"),
    }
    actual = {
        "plan_sha256": sha256_file(plan),
        "action_sha256": sha256_file(action),
    }
    if events.suffix == ".gz":
        actual["events_gz_sha256"] = sha256_file(events)
        actual["events_restored_sha256"] = sha256_bytes(gzip.decompress(events.read_bytes()))
    return {"expected": expected, "actual": actual}


def _mismatch_report(identity: dict[str, Any]) -> list[dict[str, str]]:
    mismatches = []
    for field, expected in identity["expected"].items():
        actual = identity["actual"].get(field)
        if expected is None or actual is None:
            continue
        elif expected != actual:
            mismatches.append({"field": field, "status": "MISMATCH", "expected": expected, "actual": actual})
    return mismatches


def _deployed_operator_ids(plan: dict[str, Any]) -> set[str]:
    result = set()
    for action in plan.get("action_timeline", []):
        if action.get("action_type") == "DEPLOY" and action.get("operator_id"):
            result.add(action["operator_id"])
        if action.get("action_type") == "DEPLOY_ROBOT" and action.get("target_id"):
            result.add(action["target_id"])
    return result


def _first(values: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(values, key=lambda item: item.get("frame", 0))


def _observed_tags(observed: dict[str, Any], summary: dict[str, Any], plan: dict[str, Any]) -> set[str]:
    tags = {"CANDIDATE_ARCHIVE"}
    if summary.get("win") is True or summary.get("simulator_win") is True:
        tags.add("WIN_REFERENCE")
    if observed.get("steward_artillery_damage", {}).get("hit_count", 0):
        tags.add("ARTILLERY_OUTPUT")
    if observed.get("artillery_death"):
        tags.add("ARTILLERY_KILL")
    if observed.get("relevant_heals"):
        tags.add("SUPPORT_DELIVERY")
    if any(event.get("target_id") in PROTECTED_IDS for event in observed.get("protected_target_reached_events", [])):
        tags.add("PROTECTED_ROUTE")
    if any(event.get("target_id") in CENTRAL_IDS for event in observed.get("enemy_deaths", [])):
        tags.add("CENTRAL_INTERCEPT")
    if any("roadblock" in str(event.get("target_id", "")).lower() for event in observed.get("device_destroyed", [])):
        tags.add("ROADBLOCK_CLEARANCE")
    if _deployed_operator_ids(plan):
        tags.add("DEPLOYMENT_EVIDENCE")
    return tags


def _extract_predictions(validation_card: Any) -> list[dict[str, Any]]:
    if not isinstance(validation_card, dict):
        return []
    predictions = []
    for key in ("causal_change", "expected_events", "hypothesis", "targeted_hypothesis"):
        if key in validation_card:
            predictions.append({"field": key, "prediction": validation_card[key], "status": "MODEL_PREDICTION"})
    return predictions


def _experience_decision(candidate: dict[str, Any]) -> dict[str, Any]:
    validation_card = candidate.get("validation_card")
    if not isinstance(validation_card, dict):
        return {}
    decision = validation_card.get("experience_selector_decision_record")
    return decision if isinstance(decision, dict) else {}


def _selected_parent(candidate: dict[str, Any]) -> dict[str, Any]:
    selected = _experience_decision(candidate).get("selected_parent")
    return selected if isinstance(selected, dict) else {}


def _record_identity(record: dict[str, Any] | None) -> dict[str, str]:
    hashes = (record or {}).get("evidence_hashes", {}).get("actual", {})
    return {
        "record_plan_sha256": hashes.get("plan_sha256", "UNKNOWN"),
        "record_action_sha256": hashes.get("action_sha256", "UNKNOWN"),
    }


def _summary_from_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    summary = candidate.get("summary_result")
    if isinstance(summary, dict):
        return summary
    final_status = candidate.get("final_status")
    if isinstance(final_status, dict):
        return final_status
    return {"win": "UNKNOWN"}


def build_record(
    *,
    experiment_id: str,
    candidate_id: str,
    closeout_path: Path,
    closeout: dict[str, Any],
    candidate: dict[str, Any],
    plan_path: Path,
    action_path: Path,
    events_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = load_json(plan_path)
    identity = _expected_from_closeout(candidate, plan_path, action_path, events_path)
    events_meta, event_errors = None, []
    try:
        _, events_meta = load_events(events_path)
        identity["actual"]["events_gz_sha256"] = events_meta["events_gz_sha256"]
        identity["actual"]["events_restored_sha256"] = events_meta["events_restored_sha256"]
    except (OSError, ValueError) as error:
        event_errors.append(str(error))
    plan_id = plan.get("operational_plan_id") or candidate.get("plan_id")
    summary = _summary_from_candidate(candidate)
    observed = candidate.get("observed_key_events", {})
    selected = set(plan.get("selected_low_star_operator_ids", []))
    deployed = _deployed_operator_ids(plan)
    model = closeout.get("model", {})
    record_id = f"{plan_id}:{candidate_id}"
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "experiment_id": experiment_id,
        "candidate_id": candidate_id,
        "plan_id": plan_id,
        "stage_id": plan.get("stage_id", STAGE_ID),
        "mechanics_version": candidate.get("simulator_manifest", {}).get("mechanics_version", MECHANICS_VERSION),
        "configured_model": model.get("configured_model", "UNKNOWN"),
        "reasoning_effort": model.get("reasoning_effort", "UNKNOWN"),
        "identity_proof": "CONFIGURED_IDENTITY_ONLY",
        "code_commit_sha256": "UNKNOWN_AT_IMPORT",
        "facts_version": "UNKNOWN_AT_IMPORT",
        "controlled_code_sha256": candidate.get("controlled_code_sha256", {}),
        "facts_source_sha256": candidate.get("facts_source_sha256", {}),
        "selected_low_star_operator_ids": sorted(selected),
        "deployed_operator_ids": sorted(deployed),
        "operator_union": sorted(selected | deployed),
        "operator_union_count": len(selected | deployed),
        "same_id_redeploy_counted_once": True,
        "robots_count_toward_union": True,
        "parent_plan_id": plan.get(
            "tactical_parent_plan_id",
            plan.get("parent_plan_id", _selected_parent(candidate).get("plan_id", "UNKNOWN")),
        ),
        "normalized_action_sha256": identity["actual"].get("action_sha256", "UNKNOWN"),
        "event_observation_summary": {
            "summary_result": summary,
            "protected_target_deaths": _first(candidate.get("protected_target_deaths", []), "frame"),
            "protected_target_reached_events": _first(candidate.get("protected_target_reached_events", []), "frame"),
            "observed_key_events": observed,
            "recorded_action_errors": candidate.get("recorded_action_errors", []),
            "action_error_classification": candidate.get("action_error_classification", "UNKNOWN"),
            "event_count": int(events_meta["event_count"]) if events_meta else "UNKNOWN",
        },
        "model_predictions": _extract_predictions(candidate.get("validation_card")),
        "experience_selector_decision_record": _experience_decision(candidate),
        "validation_card_path": str(closeout_path),
        "validation_card_status": "MODEL_PREDICTION_NOT_OBSERVED_FACT",
        "responsible_paths": {
            "closeout": str(closeout_path),
            "plan_snapshot": str(plan_path),
            "action_snapshot": str(action_path),
            "diagnostic_events": str(events_path),
        },
        "evidence_hashes": identity,
        "archive_status": "VERIFIED" if not event_errors and not _mismatch_report(identity) else "IDENTITY_PROBLEM",
        "coverage_status": "FIXED_SIMULATOR_ONLY",
        "applicable_conditions": [
            "Same fixed simulator mechanics and audited archive only",
            "Observations are not proof of necessity",
        ],
        "unknown_fields": {
            "code_commit_sha256": "UNKNOWN_AT_IMPORT",
            "facts_version": "UNKNOWN_AT_IMPORT",
            "continuous_operator_positions": "UNKNOWN_UNLESS_RECORDED",
        },
    }
    record["responsibility_tags"] = sorted(_observed_tags(observed, summary, plan))
    if record["archive_status"] != "VERIFIED":
        record["retention_status"] = "REFERENCE_ONLY_IDENTITY_PROBLEM"
    else:
        record["retention_status"] = "ELIGIBLE"
    return record, {"errors": event_errors, "hash_mismatches": _mismatch_report(identity)}


def _candidate_list(closeout: dict[str, Any]) -> list[dict[str, Any]]:
    if "candidates" in closeout:
        return closeout["candidates"]
    if "candidate" in closeout:
        return [closeout["candidate"]]
    return []


def _plan_id_from_experiment(experiment_id: str) -> str:
    if experiment_id == "M70":
        return "R8_7_GPT_M70_V1"
    return experiment_id.split("real_tool_closed_loop_")[-1]


def import_default_sources(root: Path = Path(".")) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = root / "docs/review/fc77177"
    records, issues = [], []
    m70_dir = base / "m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic"
    manifest = load_json(m70_dir / "manifest.json")
    plan = load_json(m70_dir / "plan_snapshot.json")
    final_status = load_json(m70_dir / "final_status.json")
    events_path = m70_dir / "diagnostic_events.json.gz"
    identity = {
        "expected": {
            "plan_sha256": manifest.get("plan_snapshot_sha256"),
            "action_sha256": manifest.get("action_snapshot_sha256"),
            "events_gz_sha256": None,
            "events_restored_sha256": None,
        },
        "actual": {
            "plan_sha256": sha256_file(m70_dir / "plan_snapshot.json"),
            "action_sha256": sha256_file(m70_dir / "action_snapshot.json"),
        },
    }
    try:
        _, events_meta = load_events(events_path)
        identity["actual"]["events_gz_sha256"] = events_meta["events_gz_sha256"]
        identity["actual"]["events_restored_sha256"] = events_meta["events_restored_sha256"]
    except (OSError, ValueError) as error:
        issues.append({"record_id": "R8_7_GPT_M70_V1:diagnostic", "error": str(error)})
    observed = {"device_destroyed": [], "enemy_deaths": [], "protected_target_reached_events": []}
    try:
        events, _ = load_events(events_path)
        by_type: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            by_type.setdefault(event.get("event_type", ""), []).append(event)
        observed = {
            "device_destroyed": _first(by_type.get("DEVICE_DESTROYED", []), "frame"),
            "enemy_deaths": _first(by_type.get("ENEMY_DEATH", []), "frame"),
            "protected_target_reached_events": _first(by_type.get("PROTECTED_TARGET_REACHED", []), "frame"),
            "relevant_heals": [
                event for event in by_type.get("HEAL", [])
                if event.get("source_id") in {"char_212_ansel", "char_120_hibisc"}
                and event.get("target_id") in {"char_210_stward", "char_212_ansel", "char_120_hibisc"}
            ],
            "artillery_death": [event for event in by_type.get("ENEMY_DEATH", []) if event.get("target_id") in ARTILLERY_IDS],
        }
    except (OSError, ValueError) as error:
        issues.append({"record_id": "R8_7_GPT_M70_V1:diagnostic", "error": str(error)})
    selected = set(plan.get("selected_low_star_operator_ids", []))
    deployed = _deployed_operator_ids(plan)
    m70 = {
        "schema_version": SCHEMA_VERSION,
        "record_id": f"{final_status['plan_id']}:diagnostic",
        "experiment_id": "M70",
        "candidate_id": "diagnostic",
        "plan_id": final_status["plan_id"],
        "stage_id": final_status["stage_id"],
        "mechanics_version": final_status["mechanics_version"],
        "configured_model": "UNKNOWN_FROM_ARCHIVE",
        "reasoning_effort": "UNKNOWN_FROM_ARCHIVE",
        "identity_proof": "CONFIGURED_IDENTITY_ONLY",
        "code_commit_sha256": "UNKNOWN_AT_IMPORT",
        "facts_version": "UNKNOWN_AT_IMPORT",
        "controlled_code_sha256": {},
        "facts_source_sha256": {},
        "selected_low_star_operator_ids": sorted(selected),
        "deployed_operator_ids": sorted(deployed),
        "operator_union": sorted(selected | deployed),
        "operator_union_count": len(selected | deployed),
        "same_id_redeploy_counted_once": True,
        "robots_count_toward_union": True,
        "parent_plan_id": "UNKNOWN",
        "normalized_action_sha256": identity["actual"].get("action_sha256", "UNKNOWN"),
        "event_observation_summary": {"summary_result": final_status, "observed_key_events": observed},
        "model_predictions": [],
        "validation_card_path": "UNKNOWN",
        "validation_card_status": "NO_VALIDATION_CARD_IN_ARCHIVE",
        "responsible_paths": {
            "manifest": str(m70_dir / "manifest.json"),
            "plan_snapshot": str(m70_dir / "plan_snapshot.json"),
            "action_snapshot": str(m70_dir / "action_snapshot.json"),
            "diagnostic_events": str(events_path),
            "final_status": str(m70_dir / "final_status.json"),
        },
        "evidence_hashes": identity,
        "archive_status": "VERIFIED" if not issues and not _mismatch_report(identity) else "IDENTITY_PROBLEM",
        "coverage_status": "FIXED_SIMULATOR_ONLY",
        "applicable_conditions": ["Eight-ID WIN reference for K<=7 reduction only"],
        "unknown_fields": {
            "code_commit_sha256": "UNKNOWN_AT_IMPORT",
            "facts_version": "UNKNOWN_AT_IMPORT",
            "continuous_operator_positions": "UNKNOWN_UNLESS_RECORDED",
        },
    }
    m70["responsibility_tags"] = sorted(_observed_tags(observed, final_status, plan))
    m70["retention_status"] = "ELIGIBLE" if m70["archive_status"] == "VERIFIED" else "REFERENCE_ONLY_IDENTITY_PROBLEM"
    records.append(m70)

    experiment_dirs = [
        "real_tool_closed_loop_sol_high_seven_retry2_v1",
        "real_tool_closed_loop_sol_high_seven_retry3_v1",
        "real_tool_closed_loop_sol_high_seven_support_coverage_v1",
        "real_tool_closed_loop_sol_high_seven_support_geometry_v1",
        "real_tool_closed_loop_sol_high_seven_heal_delivery_v1",
        "real_tool_closed_loop_sol_high_seven_artillery_closure_v1",
        "real_tool_closed_loop_sol_high_seven_selector_integration_v1",
        "real_tool_closed_loop_sol_high_seven_selector_feedback_v1",
        "real_tool_closed_loop_sol_high_seven_artillery_platform_v1",
        "real_tool_closed_loop_sol_high_seven_c2_retreat_window_v1",
    ]
    for experiment_dir in experiment_dirs:
        exp_path = base / experiment_dir
        closeout_path = exp_path / "closeout_report_v1.json"
        if not closeout_path.exists():
            issues.append({"record_id": experiment_dir, "error": "closeout missing"})
            continue
        try:
            closeout = load_json(closeout_path)
        except (OSError, json.JSONDecodeError) as error:
            issues.append({"record_id": experiment_dir, "error": str(error)})
            continue
        for candidate in _candidate_list(closeout):
            candidate_id = candidate.get("candidate_id", "UNKNOWN")
            sim_dir = exp_path / "session/candidates" / candidate_id / "simulation"
            plan_path, action_path = sim_dir / "plan_snapshot.json", sim_dir / "action_snapshot.json"
            events_path = sim_dir / "diagnostic_events.json.gz"
            missing = [str(path) for path in (plan_path, action_path, events_path) if not path.exists()]
            if missing:
                issues.append({"record_id": f"{candidate.get('plan_id')}:{candidate_id}", "error": f"missing {missing}"})
                continue
            try:
                record, import_issue = build_record(
                    experiment_id=_plan_id_from_experiment(experiment_dir),
                    candidate_id=candidate_id,
                    closeout_path=closeout_path,
                    closeout=closeout,
                    candidate=candidate,
                    plan_path=plan_path,
                    action_path=action_path,
                    events_path=events_path,
                )
                records.append(record)
                if import_issue["errors"] or import_issue["hash_mismatches"]:
                    issues.append({"record_id": record["record_id"], **import_issue})
            except (OSError, json.JSONDecodeError, ValueError) as error:
                issues.append({"record_id": f"{candidate.get('plan_id', 'UNKNOWN')}:{candidate_id}", "error": str(error)})
    return records, issues


def validate_record(record: dict[str, Any]) -> list[str]:
    required = {
        "record_id", "plan_id", "candidate_id", "mechanics_version", "configured_model",
        "operator_union", "operator_union_count", "responsibility_tags",
        "evidence_hashes", "responsible_paths", "archive_status", "coverage_status",
    }
    errors = [f"missing {field}" for field in sorted(required - set(record))]
    if record.get("operator_union_count") != len(record.get("operator_union", [])):
        errors.append("operator_union_count mismatch")
    if record.get("coverage_status") != "FIXED_SIMULATOR_ONLY":
        errors.append("unsupported coverage_status")
    if record.get("mechanics_version") != MECHANICS_VERSION:
        errors.append("unsupported mechanics_version")
    return errors


def load_store(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at {path}:{line_number}: {error}") from error
    return records


def write_store(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


def import_idempotent(records: list[dict[str, Any]], new_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {record["record_id"]: record for record in records}
    updated = []
    for candidate in new_records:
        existing = by_id.get(candidate["record_id"])
        if existing == candidate:
            continue
        by_id[candidate["record_id"]] = candidate
        updated.append(candidate["record_id"])
    return list(by_id.values()), updated


def retain_branches(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    seen_action: dict[str, dict[str, Any]] = {}
    changes = []
    for record in records:
        if record.get("archive_status") != "VERIFIED" or record.get("mechanics_version") != MECHANICS_VERSION:
            record = dict(record)
            record["retention_status"] = "REFERENCE_ONLY"
            continue
        for tag in ("WIN_REFERENCE", "ARTILLERY_KILL", "ARTILLERY_OUTPUT", "SUPPORT_DELIVERY", "PROTECTED_ROUTE", "CENTRAL_INTERCEPT", "ROADBLOCK_CLEARANCE"):
            if tag not in record.get("responsibility_tags", []):
                continue
            key = (tag, record["record_id"])
            old = by_key.get(key)
            if old is None or _record_quality(record) > _record_quality(old):
                if old is not None and old["record_id"] != record["record_id"]:
                    changes.append(f"{tag}:{old['record_id']}->{record['record_id']}")
                by_key[key] = record
        normalized = record.get("normalized_action_sha256")
        previous = seen_action.get(normalized)
        if previous and previous["record_id"] != record["record_id"]:
            changes.append(f"DUPLICATE_ACTION:{previous['record_id']}=={record['record_id']}")
        seen_action[normalized] = record
    retained_ids = {record["record_id"] for record in by_key.values()}
    retained_ids.update(record["record_id"] for record in records if record.get("retention_status") == "REFERENCE_ONLY")
    return records, sorted(retained_ids), changes


def _record_quality(record: dict[str, Any]) -> tuple[int, int, int]:
    summary = record.get("event_observation_summary", {}).get("summary_result", {})
    win = 1 if summary.get("win") is True or summary.get("simulator_win") is True else 0
    kills = summary.get("enemies_killed", -1)
    kills = kills if isinstance(kills, int) else -1
    leaks = summary.get("enemies_leaked", 1_000_000)
    leaks = leaks if isinstance(leaks, int) else 1_000_000
    return win, kills, -leaks


def select_complementary(
    records: list[dict[str, Any]], *, k: int, target_tags: set[str], mechanics_version: str = MECHANICS_VERSION, limit: int = 4
) -> list[dict[str, Any]]:
    scored = []
    for record in records:
        if record.get("mechanics_version") != mechanics_version:
            continue
        tags = set(record.get("responsibility_tags", []))
        score = len(tags & target_tags) * 10
        if "WIN_REFERENCE" in tags:
            score += 5
        if record.get("operator_union_count", 99) <= k:
            score += 3
        if record.get("archive_status") != "VERIFIED":
            score -= 20
        if score <= 0:
            continue
        item = dict(record)
        item["selector_score"] = score
        item["selector_reason"] = sorted(tags & target_tags)
        item["parent_eligibility"] = "REFERENCE_TO_EDIT" if record.get("operator_union_count", 0) > k else "SUBMITTABLE_AFTER_VALIDATION"
        item["k_constraint"] = {"requested_k": k, "record_union_count": record.get("operator_union_count"), "must_reduce": record.get("operator_union_count", 0) > k}
        scored.append((score, record["record_id"], item))
    scored.sort(key=lambda row: (-row[0], row[1]))
    selected: list[dict[str, Any]] = []
    used_tags: set[str] = set()
    for _, _, item in scored:
        gained = set(item["responsibility_tags"]) & target_tags - used_tags
        if selected and not gained:
            continue
        selected.append(item)
        used_tags |= set(item["responsibility_tags"])
        if len(selected) >= limit:
            break
    if selected and all(item.get("operator_union_count", 99) > k for item in selected):
        fallback = next((item for _, _, item in scored if item.get("operator_union_count", 99) <= k), None)
        if fallback is not None and fallback["record_id"] not in {item["record_id"] for item in selected}:
            selected.append(fallback)
    if not selected:
        raise ValueError("no applicable records for requested mechanics/tags")
    return selected


def build_context(
    records: list[dict[str, Any]], *, goal: str, k: int, target_tags: set[str], byte_limit: int = 28_000,
    catalog_path: Path = DEFAULT_CATALOG,
) -> tuple[dict[str, Any], list[str]]:
    selected = select_complementary(records, k=k, target_tags=target_tags)
    omitted = []
    catalog_ref = {
        "path": str(catalog_path),
        "sha256": sha256_file(catalog_path) if catalog_path.exists() else "UNKNOWN",
        "requirement": "Import full legal 1-3-star capability/debug_configuration catalog through production planner",
    }
    payload = {
        "schema_version": "KIMIARK_CODEX_CONTEXT_PACKAGE_V1",
        "scope_boundary": "Fixed simulator only; no real-game, faithful, robust, probabilistic, seven-ID-impossible, or global-minimum claim",
        "goal": goal,
        "byte_limit": byte_limit,
        "requested_k": k,
        "mechanics_version": MECHANICS_VERSION,
        "catalog_reference": catalog_ref,
        "parent_candidates": [
            {
                "record_id": item["record_id"],
                "plan_id": item["plan_id"],
                "candidate_id": item["candidate_id"],
                "plan_sha256": item["evidence_hashes"]["actual"].get("plan_sha256", "UNKNOWN"),
                "action_sha256": item["evidence_hashes"]["actual"].get("action_sha256", "UNKNOWN"),
                "events_gz_sha256": item["evidence_hashes"]["actual"].get("events_gz_sha256", "UNKNOWN"),
                "responsibility_tags": item["responsibility_tags"],
                "established": [tag for tag in item["responsibility_tags"] if tag in target_tags],
                "unestablished": [tag for tag in target_tags if tag not in item["responsibility_tags"]],
                "selection_reason": item["selector_reason"],
                "parent_eligibility": item["parent_eligibility"],
                "k_constraint": item["k_constraint"],
                "evidence_paths": item["responsible_paths"],
                "model_predictions": item.get("model_predictions", []),
            }
            for item in selected
        ],
        "omitted": [],
        "failed_evidence": [
            {
                "record_id": item["record_id"],
                "summary_result": item["event_observation_summary"].get("summary_result", {}),
                "observed_key_events": item["event_observation_summary"].get("observed_key_events", {}),
            }
            for item in selected
            if not (
                item["event_observation_summary"].get("summary_result", {}).get("win") is True
                or item["event_observation_summary"].get("summary_result", {}).get("simulator_win") is True
            )
        ],
        "non_selected_records": [
            {
                "record_id": record["record_id"],
                "archive_status": record.get("archive_status"),
                "mechanics_version": record.get("mechanics_version"),
                "responsibility_tags": record.get("responsibility_tags", []),
                "reason": (
                    "MECHANICS_NOT_CURRENT" if record.get("mechanics_version") != MECHANICS_VERSION
                    else "IDENTITY_PROBLEM" if record.get("archive_status") != "VERIFIED"
                    else "NOT_COMPLEMENTARY_AFTER_SELECTED_BRANCHES"
                ),
            }
            for record in records
            if record["record_id"] not in {item["record_id"] for item in selected}
        ],
        "validation_card_template": {
            "main_parent": {"record_id": "", "plan_id": "", "plan_sha256": "", "action_sha256": ""},
            "targeted_change": "",
            "expected_observable_events": [],
            "refutation_conditions": [],
            "duty_plan": {"opening": "", "roadblocks_and_protected_routes": "", "artillery_closure": "", "central_intercept": ""},
            "cost_and_replacement": "",
            "unknown_or_model_gap": [],
        },
        "execution_boundary": [
            "Use production CONTROLLED_RUNNER and four MCP tools only",
            "No direct Simulator call; do not modify mechanics",
            "Union(selected, deployed IDs) <= K; same-ID redeployment once; robots count",
            "Tactical choices remain fully open; selector does not whitelist or blacklist roles",
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    while len(encoded) > byte_limit:
        if payload["failed_evidence"]:
            removed = payload["failed_evidence"].pop()
            omitted.append(f"failed_evidence:{removed['record_id']}")
        elif payload["parent_candidates"] and len(payload["parent_candidates"]) > 1:
            removed = payload["parent_candidates"].pop()
            omitted.append(f"parent_candidate:{removed['record_id']}")
        else:
            omitted.append("context_over_byte_limit")
            break
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    payload["omitted"] = omitted
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(encoded) > byte_limit:
        raise ValueError("context package exceeds byte limit after recording omissions")
    return payload, omitted


def context_record_ids(context: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in context.get("parent_candidates", []):
        result[item["record_id"]] = "SUGGESTED_PARENT"
    for item in context.get("failed_evidence", []):
        result[item["record_id"]] = "FAILED_EVIDENCE"
    for item in context.get("non_selected_records", []):
        result.setdefault(item["record_id"], "NOT_SELECTED")
    return result


def _deployment_rows(plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for action in plan.get("action_timeline", []):
        if action.get("action_type") == "DEPLOY" and action.get("operator_id"):
            rows.setdefault(action["operator_id"], []).append({
                "frame": action.get("frame"),
                "tile": action.get("tile"),
                "direction": action.get("direction"),
            })
    return rows


def _action_identity(plan: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (action.get("frame"), action.get("action_type"), action.get("operator_id"),
         json.dumps(action.get("tile"), sort_keys=True), action.get("direction"))
        for action in plan.get("action_timeline", [])
    ]


def build_parent_action_diff(parent_plan: dict[str, Any], candidate_plan: dict[str, Any]) -> dict[str, Any]:
    parent_id = parent_plan.get("operational_plan_id", "UNKNOWN")
    candidate_id = candidate_plan.get("operational_plan_id", "UNKNOWN")
    parent_deployments = _deployment_rows(parent_plan)
    candidate_deployments = _deployment_rows(candidate_plan)
    parent_union = set(parent_plan.get("selected_low_star_operator_ids", [])) | set(parent_deployments)
    candidate_union = set(candidate_plan.get("selected_low_star_operator_ids", [])) | set(candidate_deployments)
    changes = []
    for operator_id in sorted(parent_union | candidate_union):
        before = parent_deployments.get(operator_id, [])
        after = candidate_deployments.get(operator_id, [])
        if before == after:
            status = "UNCHANGED"
        elif before and not after:
            status = "REMOVED"
        elif after and not before:
            status = "ADDED"
        else:
            status = "CHANGED"
        if status != "UNCHANGED":
            changes.append({
                "operator_id": operator_id,
                "status": status,
                "parent_deployments": before,
                "candidate_deployments": after,
                "duty_review": "VERIFY_PREVIOUS_AND_NEW_DUTY_WITH_EVENTS_OR_STATIC_FACTS",
                "duty_failure_conclusion": "UNKNOWN_WITHOUT_RUNTIME_EVENTS",
            })
    parent_actions = _action_identity(parent_plan)
    candidate_actions = _action_identity(candidate_plan)
    return {
        "schema_version": "KIMIARK_SELECTOR_PARENT_ACTION_DIFF_V1",
        "parent_plan_id": parent_id,
        "candidate_plan_id": candidate_id,
        "parent_operator_union": sorted(parent_union),
        "candidate_operator_union": sorted(candidate_union),
        "removed_operator_ids": sorted(parent_union - candidate_union),
        "added_operator_ids": sorted(candidate_union - parent_union),
        "legal_role_set_modified_by_selector": False,
        "deployment_changes": changes,
        "same_roster": parent_union == candidate_union,
        "same_normalized_action_timeline": parent_actions == candidate_actions,
        "changed_action_count": sum(1 for before, after in zip(parent_actions, candidate_actions) if before != after) + abs(len(parent_actions) - len(candidate_actions)),
        "risk_boundary": "Advisory information only; no role restriction, hard tactical gate, or causal failure conclusion.",
    }


def build_experience_usage_audit(
    pre_context: dict[str, Any],
    post_context: dict[str, Any],
    records: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    record_by_id = {record["record_id"]: record for record in records}
    pre_ids = context_record_ids(pre_context)
    post_ids = context_record_ids(post_context)
    post_only = sorted(set(post_ids) - set(pre_ids))
    usage_rows = []
    for candidate in candidates:
        decision = candidate.get("experience_selector_decision_record", {})
        decision = _experience_decision(candidate) if not decision else decision
        for observation in decision.get("adopted_observations", []):
            record_id = observation.get("record_id")
            record = record_by_id.get(record_id)
            summary = (record or {}).get("event_observation_summary", {}).get("summary_result", {})
            usage_rows.append({
                "candidate_id": candidate.get("candidate_id"),
                "record_id": record_id,
                "pre_context_status": pre_ids.get(record_id, "ABSENT"),
                "post_context_status": post_ids.get(record_id, "ABSENT"),
                "post_run_only": record_id in post_only,
                "archive_status": (record or {}).get("archive_status", "UNKNOWN"),
                "responsibility_tags": (record or {}).get("responsibility_tags", []),
                **_record_identity(record),
                "observation": observation.get("observation", "UNKNOWN"),
                "candidate_result": {
                    "win": summary.get("win", summary.get("simulator_win", "UNKNOWN")),
                    "enemies_killed": summary.get("enemies_killed", "UNKNOWN"),
                    "enemies_leaked": summary.get("enemies_leaked", "UNKNOWN"),
                    "remaining_life": summary.get("remaining_life", "UNKNOWN"),
                },
                "store_presence": "PRESENT" if record is not None else "MISSING",
                "evidence_status": "OBSERVED_ARCHIVE_SUMMARY",
                "causal_success_claim": "NOT_PERMITTED",
            })
        for non_applicable in decision.get("non_applicable_experiences", []):
            usage_rows.append({
                "candidate_id": candidate.get("candidate_id"),
                "record_id": non_applicable.get("record_id", "UNKNOWN_NO_RECORD_ID"),
                "pre_context_status": pre_ids.get(non_applicable.get("record_id"), "UNKNOWN"),
                "post_context_status": post_ids.get(non_applicable.get("record_id"), "UNKNOWN"),
                "post_run_only": non_applicable.get("record_id") in post_only,
                "archive_status": (record_by_id.get(non_applicable.get("record_id")) or {}).get("archive_status", "UNKNOWN"),
                "responsibility_tags": (record_by_id.get(non_applicable.get("record_id")) or {}).get("responsibility_tags", []),
                **_record_identity(record_by_id.get(non_applicable.get("record_id"))),
                "observation": non_applicable.get("experience", "UNKNOWN"),
                "non_applicable_reason": non_applicable.get("why", "UNKNOWN"),
                "store_presence": "PRESENT" if non_applicable.get("record_id") in record_by_id else "MISSING_OR_UNSPECIFIED",
                "evidence_status": "VISIBLY_CLASSIFIED_NOT_APPLICABLE",
                "causal_success_claim": "NOT_PERMITTED",
            })
    return {
        "schema_version": "KIMIARK_EXPERIENCE_USAGE_AUDIT_V1",
        "pre_context_record_ids": pre_ids,
        "post_context_record_ids": post_ids,
        "post_context_only_record_ids": post_only,
        "adopted_observations": usage_rows,
        "boundary": {
            "hidden_reasoning": "UNKNOWN",
            "absence_of_citation": "NOT_PROOF_OF_NON_USE_BECAUSE_RAW_ARCHIVE_WAS_READABLE",
            "unknown_result_fields": "UNKNOWN_NOT_ZERO",
            "loss_classification": "A_GLOBAL_LOSS_IS_NOT_A_UNIFORM_REFUTATION_OF_EVERY_LOCAL_OBSERVATION",
        },
    }


def rebuild_store(source_store: Path, target_store: Path) -> dict[str, Any]:
    records, issues = import_default_sources()
    write_store(target_store, records)
    existing = load_store(source_store) if source_store.exists() else []
    rebuilt_ids = {record["record_id"] for record in records}
    missing = sorted({record.get("record_id", "UNKNOWN") for record in existing} - rebuilt_ids)
    return {"records": len(records), "issues": issues, "missing_from_rebuild": missing}


def compare_contexts(pre_context: dict[str, Any], post_context: dict[str, Any]) -> dict[str, Any]:
    pre_ids = context_record_ids(pre_context)
    post_ids = context_record_ids(post_context)
    return {
        "schema_version": "KIMIARK_CONTEXT_COMPARISON_V1",
        "pre_context_record_ids": pre_ids,
        "post_context_record_ids": post_ids,
        "post_context_only_record_ids": sorted(set(post_ids) - set(pre_ids)),
        "pre_context_only_record_ids": sorted(set(pre_ids) - set(post_ids)),
        "role_set_changed_by_context": False,
        "boundary": "Comparison is retrieval evidence, not tactical authorization or causal improvement proof.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import and select immutable KimiArk tactical candidate archives")
    commands = parser.add_subparsers(dest="command", required=True)
    import_cmd = commands.add_parser("import")
    import_cmd.add_argument("--store", type=Path, default=DEFAULT_STORE)
    import_cmd.add_argument("--report", type=Path, default=DEFAULT_STORE.with_suffix(".import_report.json"))
    select_cmd = commands.add_parser("select")
    select_cmd.add_argument("--store", type=Path, default=DEFAULT_STORE)
    select_cmd.add_argument("--goal", required=True)
    select_cmd.add_argument("--k", type=int, required=True)
    select_cmd.add_argument("--tags", nargs="+", required=True)
    select_cmd.add_argument("--output", type=Path, required=True)
    select_cmd.add_argument("--byte-limit", type=int, default=28_000)
    select_cmd.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    rebuild_cmd = commands.add_parser("rebuild-check")
    rebuild_cmd.add_argument("--source", type=Path, default=DEFAULT_STORE)
    rebuild_cmd.add_argument("--target", type=Path, required=True)
    audit_cmd = commands.add_parser("audit")
    audit_cmd.add_argument("--pre-context", type=Path, required=True)
    audit_cmd.add_argument("--post-context", type=Path, required=True)
    audit_cmd.add_argument("--store", type=Path, default=DEFAULT_STORE)
    audit_cmd.add_argument("--closeout", type=Path, required=True)
    audit_cmd.add_argument("--parent-plan", type=Path, required=True)
    audit_cmd.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "import":
        records, issues = import_default_sources()
        existing = load_store(args.store)
        merged, updated = import_idempotent(existing, records)
        write_store(args.store, merged)
        invalid = [record.get("record_id", "UNKNOWN") for record in merged if validate_record(record)]
        report = {"schema_version": STORE_SCHEMA_VERSION, "records": len(merged), "updated": updated, "issues": issues, "invalid_records": invalid}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 1 if invalid else 0
    if args.command == "select":
        payload, omitted = build_context(load_store(args.store), goal=args.goal, k=args.k, target_tags=set(args.tags), byte_limit=args.byte_limit, catalog_path=args.catalog)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "omitted": omitted}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "audit":
        pre_context = load_json(args.pre_context)
        post_context = load_json(args.post_context)
        closeout = load_json(args.closeout)
        parent_plan = load_json(args.parent_plan)
        comparisons = []
        for candidate in _candidate_list(closeout):
            candidate_id = candidate.get("candidate_id", "UNKNOWN")
            plan_path = args.closeout.parent / "session/candidates" / candidate_id / "simulation/plan_snapshot.json"
            comparisons.append(build_parent_action_diff(parent_plan, load_json(plan_path)))
        payload = {
            "schema_version": "KIMIARK_SELECTOR_FEEDBACK_AUDIT_V1",
            "context_comparison": compare_contexts(pre_context, post_context),
            "parent_action_diffs": comparisons,
            "experience_usage_audit": build_experience_usage_audit(
                pre_context, post_context, load_store(args.store), _candidate_list(closeout)
            ),
            "boundaries": {
                "selector_is_advisory": True,
                "real_model_calls_in_this_audit": 0,
                "real_simulations_in_this_audit": 0,
                "hidden_reasoning": "UNKNOWN",
                "absence_of_citation": "NOT_PROOF_OF_NON_USE_BECAUSE_RAW_ARCHIVE_WAS_READABLE",
                "loss_classification": "A_GLOBAL_LOSS_IS_NOT_A_UNIFORM_REFUTATION_OF_EVERY_LOCAL_OBSERVATION",
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "records": len(load_store(args.store))}, sort_keys=True))
        return 0
    print(json.dumps(rebuild_store(args.source, args.target), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
