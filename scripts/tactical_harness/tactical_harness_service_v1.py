#!/usr/bin/env python3
"""Reusable KimiArk tactical-experiment harness: thin transport over the production closed loop.

The harness owns no tactics and no simulator. It forwards check/run/query to
``kimiark_tactical_stdio_service_v1`` and adds:

* batch preparation state (rounds, variants, parents, budgets) from ``prepare_harness.py``;
* Astra-facing search over Astra-authored change sets with budget pre-flight and truncation;
* evidence reads over archived raw events, plans, catalogs, mechanics KB and experience store;
* split teaching records (user quote / Astra interpretation / simulation observation);
* verbatim teacher-prompt intake with sha256 delivery audit.

No model call happens here. ``TEST_ONLY_FAKE`` batches use the production fake executor.
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import itertools
import json
import math
import sys
import time
import uuid
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import kimiark_tactical_stdio_service_v1 as production
import tactical_experience_v1 as tactical_experience
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION
from run_gpt_tactical_stage_diagnostic_v1 import validated_unique_deployments

STATE_SCHEMA = "KIMIARK_TACTICAL_HARNESS_BATCH_STATE_V1"
CONSTRAINTS_SCHEMA = "KIMIARK_TACTICAL_HARNESS_CONSTRAINTS_V1"
MAX_COMBINATIONS_PER_CALL = 60
MAX_PREVIEW_ROWS = 20
KB_PATH = ROOT / "data/mechanics_kb/kb_entries_v1.json"
STAGE_PROFILES_PATH = ROOT / "scripts/tactical_harness/stage_profiles_v1.json"
EXPERIENCE_STORE = ROOT / "output/codex_experience_selector_v1/experience_records.jsonl"
EXPERIENCE_MECHANICS_VERSION = "m38b-2781-animation-speed-v1"

BASE: Path | None = None
CONFIG: production.SessionConfig | None = None


def canon(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read(path: Path):
    path = Path(path)
    if not path.exists() and Path(str(path) + ".gz").exists():
        import gzip

        return json.loads(gzip.decompress(Path(str(path) + ".gz").read_bytes()))
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def append_jsonl(path: Path, row) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canon(row) + "\n")


def base_dir() -> Path:
    assert BASE is not None
    return BASE


def batch_state() -> dict:
    return read(base_dir() / "batch_state.json")


def save_state(state: dict) -> None:
    write(base_dir() / "batch_state.json", state)


def batch_constraints() -> dict:
    return read(base_dir() / "batch_constraints.json")


def session_config() -> production.SessionConfig:
    assert CONFIG is not None
    return CONFIG


def action_key(payload: dict) -> str:
    plan = payload["revised_operational_plans"][0] if "revised_operational_plans" in payload else payload
    material = {
        "selected": sorted(plan.get("selected_low_star_operator_ids") or []),
        "actions": [
            {k: a[k] for k in ("action_type", "operator_id", "frame", "tile", "direction") if k in a}
            for a in plan.get("action_timeline") or []
        ],
    }
    return hashlib.sha256(canon(material).encode("utf-8")).hexdigest()


def get_parent(name: str) -> dict:
    registry = read(base_dir() / "parent_registry_v1.json")
    for alias, item in registry.items():
        if name in (alias, item.get("plan_id")):
            return read(base_dir() / "parents" / alias / "payload.json")
    for row in batch_state()["variants"]:
        if name in (row.get("name"), row.get("candidate_id"), row.get("plan_id")) and row.get("candidate_id"):
            return read(base_dir() / "session" / "candidates" / row["candidate_id"] / "source/llm_structured_output.json")
    raise RuntimeError(f"unknown actual parent: {name!r}")


def resolve_plan(name: str) -> dict:
    return get_parent(name)["revised_operational_plans"][0]


def parent_events(name: str):
    registry = read(base_dir() / "parent_registry_v1.json")
    for alias, item in registry.items():
        if name in (alias, item.get("plan_id")):
            path = base_dir() / "parents" / alias / "events.json"
            if path.is_file():
                return read(path).get("events") or []
            return None
    for row in batch_state()["variants"]:
        if name in (row.get("name"), row.get("candidate_id"), row.get("plan_id")) and row.get("candidate_id"):
            path = base_dir() / "session" / "candidates" / row["candidate_id"] / "simulation/diagnostic_events.json"
            return read(path).get("events") or [] if path.is_file() else None
    raise RuntimeError(f"no event source for {name!r}")


def derive_evidence(name: str) -> tuple[dict, dict]:
    """Archive and return the per-parent derived execution context (never overwrite a parent's own file)."""
    template = read(base_dir() / "input_bundle" / "template_context.json")
    context = copy.deepcopy(template)
    plan = resolve_plan(name)
    context["previous_plan_id"] = plan.get("operational_plan_id")
    context["previous_plan_to_revise"] = plan
    archive = base_dir() / "input_bundle" / "evidence_by_parent" / f"{name}.json"
    write(archive, context)
    record = {
        "parent": name,
        "plan_id": plan.get("operational_plan_id"),
        "archive_path": str(archive.relative_to(ROOT)),
        "archive_sha256": sha(archive),
        "template_sha256": sha(base_dir() / "input_bundle" / "template_context.json"),
        "template_context_sha256": sha(base_dir() / "input_bundle" / "template_context.json"),
    }
    append_jsonl(base_dir() / "input_bundle" / "evidence_derivations_v1.jsonl", {**record, "at": time.time()})
    return context, record


def install_evidence(context: dict) -> None:
    write(session_config().facts_source_dir / "llm_evidence_context.json", context)


def remaining_budget() -> dict:
    cfg = session_config()
    budget = read(cfg.budget_path)
    ledger = read(cfg.candidate_ledger_path)
    check_remaining = None
    if ledger.get("schema_version") == "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2":
        check_remaining = max(0, ledger["max_check_calls"] - ledger["used_check_calls"])
    return {
        "check_remaining": check_remaining,
        "candidate_remaining": max(0, ledger["max_candidates"] - ledger["used_candidates"]),
        "simulation_remaining": max(
            0,
            budget["max_stage_simulations"] - budget["prior_stage_simulations"] - budget["started_stage_simulations"],
        ),
        "reserved_simulations": int(batch_constraints().get("reserved_for_independent_verification", 0) or 0),
    }


def status(_config, _args) -> dict:
    state = batch_state()
    constraints = batch_constraints()
    status_payload = production.session_status(session_config())
    budget = remaining_budget()
    recorded_rounds = sorted({row["round"] for row in state["rounds"]})
    status_payload.update(
        {
            "harness_schema_version": "KIMIARK_TACTICAL_HARNESS_STATUS_V1",
            "roster_mode": constraints.get("roster_mode"),
            "fixed_operator_ids": constraints.get("fixed_operator_ids"),
            "harness_round_max": constraints.get("round_max"),
            "rounds_recorded": recorded_rounds,
            "rounds_remaining": max(0, int(constraints.get("round_max", 5)) - len(recorded_rounds)),
            "parent_choices": {k: v.get("plan_id") for k, v in read(base_dir() / "parent_registry_v1.json").items()},
            "variants_attempted": len(state["variants"]),
            "variant_status_counts": {
                key: sum(1 for row in state["variants"] if row.get("status") == key)
                for key in sorted({row.get("status") for row in state["variants"]})
            },
            "remaining_harness_budget": budget,
            "teaching_record_count": len(state.get("teaching_records") or []),
            "teacher_prompts": len(_read_jsonl(base_dir() / "teaching" / "teacher_prompts_v1.jsonl")),
            "teacher_message_ids": [row.get("message_id") for row in _read_jsonl(base_dir() / "teaching" / "teacher_prompts_v1.jsonl")],
            "frozen_candidates": _frozen_candidate_states(state),
            "batch_stopped": bool(state.get("stopped")),
            "blocker": state.get("blocker"),
            "independent_runs": state.get("independent_runs") or [],
        }
    )
    return status_payload


def _frozen_candidate_states(state: dict) -> list[dict]:
    rows = []
    for row in state.get("variants") or []:
        candidate_id = row.get("candidate_id")
        if not candidate_id:
            continue
        try:
            probe = candidate_execution_state(candidate_id)
            rows.append({"candidate_id": candidate_id, "name": row.get("name"), "state": probe.get("status")})
        except Exception as exc:  # noqa: BLE001 - status must never crash on a probe fault
            rows.append({"candidate_id": candidate_id, "name": row.get("name"), "state": "PROBE_ERROR", "error": str(exc)})
    return rows


def checked_plan(_config, arguments: dict) -> dict:
    plan = (arguments.get("plan") or {}).get("revised_operational_plans")
    if not isinstance(plan, list) or len(plan) != 1:
        return {"status": "INPUT_REJECTED_BEFORE_PRODUCTION_CHECK", "errors": ["plan must contain exactly one revised_operational_plans item"], "check_call_counted": False, "candidate_counted": False, "simulation_started": False}
    selected = plan[0]
    try:
        validated_unique_deployments(selected.get("action_timeline") or [])
    except RuntimeError as exc:
        return {"status": "INPUT_REJECTED_BEFORE_PRODUCTION_CHECK", "errors": [str(exc)], "check_call_counted": False, "candidate_counted": False, "simulation_started": False}
    constraints = batch_constraints()
    ids = set(selected.get("selected_low_star_operator_ids") or []) | {
        a["operator_id"] for a in selected.get("action_timeline") or [] if a.get("action_type") == "DEPLOY"
    }
    if constraints.get("roster_mode") == "fixed":
        fixed = set(constraints.get("fixed_operator_ids") or [])
        if ids != fixed:
            return {
                "status": "INPUT_REJECTED_BEFORE_PRODUCTION_CHECK",
                "errors": [f"fixed roster gate: deployed union {sorted(ids)} != {sorted(fixed)}"],
                "check_call_counted": False,
                "candidate_counted": False,
                "simulation_started": False,
            }
    return production.check_plan(session_config(), arguments)


def run_simulation(_config, arguments: dict) -> dict:
    return production.run_simulation(session_config(), arguments)


def query_events(_config, arguments: dict) -> dict:
    return production.query_events(session_config(), arguments)


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds")


def _new_message_id(prefix: str = "msg") -> str:
    return f"{prefix}-{uuid.uuid5(uuid.NAMESPACE_URL, f'{ROOT}:{base_dir()}:{time.time_ns()}:{uuid.uuid4()}')}"

def load_stage_profile(stage_id: str) -> dict:
    profiles = read(STAGE_PROFILES_PATH)
    row = profiles.get("profiles", {}).get(stage_id)
    if row is None:
        return {"stage_id": stage_id, "configured": False, "reason": "no per-stage acceptance profile"}
    return {**row, "configured": True, "profile_sha256": sha(STAGE_PROFILES_PATH)}


def _completion_evidence(result: dict) -> dict:
    """Separate explicit terminal evidence from missing fields; never coerce None to PASS."""
    explicit_zero = isinstance(result.get("enemies_remaining"), int) and result["enemies_remaining"] == 0
    missing = [key for key in ("win", "enemies_leaked", "enemies_remaining") if key not in result]
    deployment_errors = result.get("deployment_errors")
    return {
        "win": result.get("win"),
        "enemies_leaked": result.get("enemies_leaked"),
        "enemies_remaining": result.get("enemies_remaining"),
        "enemies_remaining_explicit_zero": explicit_zero,
        "missing_fields": missing,
        "deployment_errors_present": bool(deployment_errors),
    }


def observe(candidate_id: str) -> dict:
    """Extract generic, evidence-backed observations only. Per-stage acceptance is separate."""
    directory = base_dir() / "session" / "candidates" / candidate_id / "simulation"
    summary = read(directory / "diagnostic_summary.json")
    events = read(directory / "diagnostic_events.json").get("events") or []
    result = {k: v for k, v in (summary.get("result") or {}).items() if k != "events"}
    kills = {
        e["target_id"]: {"frame": e["frame"], "source_id": e.get("source_id")}
        for e in events
        if e.get("event_type") == "ENEMY_DEATH" and (e.get("details") or {}).get("kill_counted")
    }
    leaks = [
        {
            "enemy_id": e.get("source_id") or e.get("target_id"),
            "frame": e["frame"],
            "amount": (e.get("details") or {}).get("amount"),
        }
        for e in events
        if e.get("event_type") == "ENEMY_LEAK"
    ]
    # Production R8-7 archives put the arriving protected entity in source_id.
    arrivals = [
        {"target_id": e.get("source_id") or e.get("target_id"), "frame": e["frame"]}
        for e in events
        if e.get("event_type") == "PROTECTED_TARGET_REACHED"
    ]
    deaths = [
        {"operator_id": e.get("source_id"), "frame": e["frame"]}
        for e in events
        if e.get("event_type") == "OPERATOR_DEATH"
    ]
    artifact_projection = bool(result.get("FAKE_TEST"))
    leak_ids_confirmed = None if artifact_projection else sorted(
        str(x["enemy_id"]) for x in leaks if x.get("enemy_id")
    )
    arrival_ids = {a["target_id"] for a in arrivals if a.get("target_id")}
    arrival_duplicates = sorted(
        tid for tid in arrival_ids if sum(1 for a in arrivals if a.get("target_id") == tid) > 1
    )
    profile = load_stage_profile(session_config().stage_id)
    required = profile.get("protected_targets") if profile.get("configured") else []
    required_ids = [row["target_id"] for row in required or []]
    missing_arrivals = [item for item in required_ids if item not in arrival_ids]
    completion = _completion_evidence(result)
    acceptance = evaluate_stage_acceptance(
        profile=profile, completion=completion, result=result,
        arrival_ids=arrival_ids, artifact_projection=artifact_projection, arrivals=arrivals,
    )
    return {
        "result": result,
        "leaks": leaks,
        "leak_ids": leak_ids_confirmed,
        "leak_ids_available": leak_ids_confirmed is not None,
        "kills": kills,
        "protected_arrivals": arrivals,
        "protected_arrival_duplicate_ids": arrival_duplicates,
        "protected_arrival_distinct_count": len(arrival_ids),
        "operator_deaths": deaths,
        "artillery_kill": kills.get(profile.get("artillery")) if profile.get("configured") else None,
        "key_enemy_kills": {
            enemy_id: kills.get(enemy_id)
            for enemy_id, _ in (profile.get("key_enemies") or {}).items()
        } if profile.get("configured") else {},
        "stage_acceptance": acceptance,
        "complete_win": acceptance["status"] == "COMPLETE_WIN",
        "complete_win_boundary": acceptance["boundary"],
        "artifact_projection": artifact_projection,
        "artifact_win": bool(result.get("win")),
        "event_log": str((directory / "diagnostic_events.json").relative_to(ROOT)),
        "summary_log": str((directory / "diagnostic_summary.json").relative_to(ROOT)),
    }


def evaluate_stage_acceptance(*, profile: dict, completion: dict, result: dict, arrival_ids: set, artifact_projection: bool, arrivals: list | None = None) -> dict:
    """Generic evidence + per-stage declarations => COMPLETE_WIN / NOT_WIN / INSUFFICIENT_EVIDENCE.

    ``failures`` are definite contradictions (a typed loss, a nonzero leak/remaining count).
    ``gaps`` are missing evidence (absent fields, unobserved arrivals) that cannot prove OR disprove a win.
    A run with any definite failure is NOT_WIN even if other fields are missing; only runs with no
    failure and no gap are COMPLETE_WIN.
    """
    stage_id = profile.get("stage_id") or session_config().stage_id
    if artifact_projection:
        return {
            "status": "ARTIFACT_PROJECTION_NOT_REAL_WIN",
            "stage_id": stage_id,
            "failures": [],
            "gaps": ["artifact projection cannot certify a real fixed-simulator WIN"],
            "boundary": "TEST_ONLY_FAKE output cannot certify a real fixed-simulator WIN, regardless of typed win/enemies_remaining.",
            "evidence": completion,
        }
    if not profile.get("configured"):
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "stage_id": stage_id,
            "failures": [],
            "gaps": ["stage acceptance profile is not configured; generic evidence cannot certify a complete WIN"],
            "evidence": completion,
            "boundary": "Only per-stage declarations can certify a complete WIN.",
        }
    required_ids = [row["target_id"] for row in (profile.get("protected_targets") or [])]
    failures: list[str] = []
    gaps: list[str] = list(completion.get("missing_fields") or [])

    if "win" in (result or {}):
        if result.get("win") is not True:
            failures.append("production simulator did not report win=true")
    if completion.get("enemies_leaked") is not None and completion.get("enemies_leaked") != 0:
        failures.append(f"enemies_leaked={completion.get('enemies_leaked')!r}")
    if completion.get("enemies_leaked") is None and profile.get("requires_zero_leaks", True):
        gaps.append("enemies_leaked field is missing; zero leaks cannot be confirmed")
    if completion.get("enemies_remaining") is not None and not completion.get("enemies_remaining_explicit_zero"):
        if profile.get("requires_enemies_remaining_zero", True):
            failures.append(f"enemies_remaining={completion.get('enemies_remaining')!r} (must be exactly 0)")
    elif profile.get("requires_enemies_remaining_zero", True) and completion.get("enemies_remaining") is None:
        gaps.append("enemies_remaining field is missing; it must be explicitly 0")
    if completion.get("deployment_errors_present"):
        failures.append("deployment_errors is non-empty")

    arrival_counts: dict[str, int] = {}
    for arrival in (arrivals or []):
        tid = arrival.get("target_id")
        if tid:
            arrival_counts[tid] = arrival_counts.get(tid, 0) + 1
    for item in required_ids:
        if item not in arrival_ids:
            gaps.append(f"required protected target not observed arrived: {item}")
    if len(arrival_ids) < len(set(required_ids)):
        gaps.append("distinct required protected-target arrivals are missing")
    for item, count in arrival_counts.items():
        if count > 1:
            failures.append(f"duplicate arrival for the same protected target does not satisfy a distinct target: {item}")

    if failures:
        status = "NOT_WIN"
    elif gaps:
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "COMPLETE_WIN"
    return {
        "status": status,
        "stage_id": stage_id,
        "failures": failures,
        "gaps": gaps,
        "reasons": [*failures, *gaps],
        "required_protected_target_ids": required_ids,
        "observed_arrival_ids": sorted(arrival_ids),
        "evidence": completion,
        "boundary": "A complete WIN requires the production simulator win, explicit zero leaks/remaining, and each declared protected target to arrive by its own distinct ID.",
    }


def baseline_leaks(parent: str):
    try:
        events = parent_events(parent)
    except RuntimeError:
        return None
    if events is None:
        return None
    return sorted(
        str(e.get("source_id") or e.get("target_id"))
        for e in events
        if e.get("event_type") == "ENEMY_LEAK" and (e.get("source_id") or e.get("target_id"))
    )


def expand(value, params):
    if isinstance(value, str) and value.startswith("$") and value[1:] in params:
        return params[value[1:]]
    if isinstance(value, list):
        return [expand(v, params) for v in value]
    if isinstance(value, dict):
        return {k: expand(v, params) for k, v in value.items()}
    return value


def build_payload(parent: str, name: str, changes, hypothesis: str, round_number: int, actions=None) -> dict:
    prefix = session_config().plan_id_prefix
    payload = copy.deepcopy(get_parent(parent))
    plan = payload["revised_operational_plans"][0]
    parent_id = plan["operational_plan_id"]
    new_id = prefix + name
    plan.update(operational_plan_id=new_id, parent_plan_id=parent_id, parent_hypothesis_id=new_id)
    payload["revision_hypothesis"].update(
        hypothesis_id=new_id,
        operational_plan_id=new_id,
        parent_plan_id=parent_id,
        tactical_hypothesis=hypothesis,
        changed_responsibilities=[hypothesis],
    )
    payload["revised_strategic_hypotheses"][0]["hypothesis_id"] = new_id
    plan["validation_card"] = {
        "generator": "ASTRA_AUTHORED_SEARCH_RANGE_MECHANICALLY_ENUMERATED",
        "round": round_number,
        "parent_id": parent_id,
        "hypothesis": hypothesis,
        "model_supplied_changes": copy.deepcopy(changes),
        "original_model": session_config().model,
        "reasoning_effort": session_config().reasoning_effort,
        "regression_observe": [
            "all leaked enemy IDs",
            "artillery actual kill",
            "both protected arrivals",
            "#19",
            "operator deaths",
            "static/action errors",
            "active enemies at end",
        ],
    }
    if actions is not None:
        plan["action_timeline"] = copy.deepcopy(actions)
    for change in changes:
        timeline = plan["action_timeline"]
        kind = change.get("type")
        if kind in ("set", "remove"):
            matches = [
                a
                for a in timeline
                if a.get("operator_id") == change.get("operator")
                and a.get("action_type") == change.get("action")
                and a.get("frame") == change.get("frame")
            ]
            if len(matches) != 1:
                raise RuntimeError(f"ambiguous exact action match: {canon(change)}")
            if kind == "set":
                matches[0].update(change.get("fields") or {})
            else:
                timeline.remove(matches[0])
        elif kind == "add":
            timeline.append(copy.deepcopy(change.get("value")))
        elif kind == "replace":
            for action in timeline:
                if action.get("operator_id") == change.get("operator"):
                    action["operator_id"] = change.get("replacement")
        else:
            raise RuntimeError(f"unknown change type: {kind!r}")
    plan["action_timeline"].sort(key=lambda a: a["frame"])
    plan["deployment_positions_and_directions"] = [
        copy.deepcopy(a) for a in plan["action_timeline"] if a.get("action_type") == "DEPLOY"
    ]
    for required in ("selected_low_star_operator_ids",):
        if not plan.get(required):
            raise RuntimeError(f"parent plan lacks {required}")
    return payload


RECOVERABLE_CHECK_STATUSES = {
    "FAIL",
    "INPUT_REJECTED_BEFORE_PRODUCTION_CHECK",
}
FATAL_CHECK_STATUSES = {
    "CHECK_BUDGET_EXHAUSTED",
    "BUDGET_EXHAUSTED",
    "SERVICE_UNAVAILABLE",
}
BUDGET_CHECK_STATUSES = {"CHECK_BUDGET_EXHAUSTED", "BUDGET_EXHAUSTED"}
LEDGER_FAULT_MARKERS = (
    "candidate ledger belongs to a different session",
    "candidate ledger",
    "ledger does not match",
    "used_candidates and attempts count disagree",
    "directory collision",
)


def classify_check_fault(exc: Exception) -> dict:
    """Separate a ledger/consistency fault from an unavailable service, by the real message."""
    message = f"{type(exc).__name__}: {exc}"
    lowered = str(exc).lower()
    if any(marker in str(exc) or marker in lowered for marker in LEDGER_FAULT_MARKERS):
        return {"kind": "ledger_inconsistency", "fatal": True, "error": message}
    return {"kind": "check_service_fault", "fatal": True, "error": message}


def fatal_stop_kind(status: str) -> str:
    if status in BUDGET_CHECK_STATUSES:
        return "check_budget_exhausted"
    return "check_blocked"


def plan_grid(params: dict) -> tuple[list[str], int, dict]:
    """Validate a parameter grid and compute its size without allocating the product."""
    names = list(params)
    if not names:
        return [], 1, {"dimensions": 0, "sizes": {}}
    sizes = {}
    total = 1
    for name in names:
        values = params[name]
        if not isinstance(values, (list, tuple)):
            raise RuntimeError(f"parameter {name!r} must be a list of values")
        sizes[name] = len(values)
        total *= len(values)
    return names, total, {"dimensions": len(names), "sizes": sizes}


def iter_grid(params: dict):
    """Lazily iterate the Cartesian product; never materialise the full grid."""
    names = list(params)
    axes = [params[name] for name in names]
    if not names:
        yield ()
        return
    yield from itertools.product(*axes)


def _preview_rows(params: dict, name_prefix: str, cap: int) -> list[dict]:
    rows = []
    for index, values in enumerate(iter_grid(params)):
        if index >= cap:
            break
        rows.append({"index": index, "name": f"{name_prefix}_{index}", "parameters": dict(zip(list(params), values))})
    return rows


def payload_candidate_sha256(payload: dict) -> str:
    """Hash exactly as production.check_plan does, so ledger reconciliation matches."""
    material = production.canonical_json(payload).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def frozen_candidate_by_sha(payload_sha: str) -> dict | None:
    """Find an already-frozen candidate in the production ledger by its authoritative hash."""
    ledger = read(session_config().candidate_ledger_path)
    for attempt in ledger.get("attempts") or []:
        if attempt.get("candidate_sha256") == payload_sha and attempt.get("check_status") == "PASS":
            return attempt
    return None


def candidate_execution_state(candidate_id: str) -> dict:
    """Read the production ledger + on-disk reservation to classify a frozen candidate."""
    cfg = session_config()
    ledger = read(cfg.candidate_ledger_path)
    attempts = [row for row in ledger.get("attempts", []) if row.get("candidate_id") == candidate_id]
    if len(attempts) != 1:
        return {"status": "UNKNOWN_LEDGER", "reason": f"ledger has {len(attempts)} attempts for {candidate_id}"}
    attempt = attempts[0]
    output_dir = base_dir() / "session" / "candidates" / candidate_id / "simulation"
    try:
        disk = production._simulation_output_state(output_dir)
    except Exception as exc:  # noqa: BLE001 - surface, do not guess
        return {"status": "UNKNOWN_DISK_STATE", "reason": f"{type(exc).__name__}: {exc}", "attempt": attempt}
    disk_status = disk.get("status")
    if disk_status == "COMPLETED":
        return {"status": "COMPLETED", "attempt": attempt, "disk": disk}
    if disk_status == "NOT_STARTED":
        return {"status": "NOT_STARTED", "attempt": attempt, "disk": disk}
    return {"status": "UNKNOWN_STARTED", "attempt": attempt, "disk": disk}


def _record_leak_delta(row: dict, parent_leaks) -> None:
    observed = row.get("observed") or {}
    if parent_leaks is not None and observed.get("leak_ids_available"):
        row["leak_delta"] = {
            "parent_leaks": parent_leaks,
            "variant_leaks": observed["leak_ids"],
            "resolved": sorted(set(parent_leaks) - set(observed["leak_ids"])),
            "new": sorted(set(observed["leak_ids"]) - set(parent_leaks)),
        }


def _resume_or_reuse(row: dict, *, results: list, counters: dict, state: dict, parent_leaks=None) -> str:
    """Reconcile an existing frozen candidate from its real execution state, not the action key.

    COMPLETED -> reuse the stored result; NOT_STARTED -> re-run the same frozen candidate;
    anything ambiguous (STARTED_UNKNOWN / non-empty output / ledger mismatch) -> stop and report.
    """
    candidate = row.get("candidate_id")
    probe = candidate_execution_state(candidate)
    if probe["status"] == "COMPLETED":
        row["observed"] = observe(candidate)
        row["resumed_from"] = "completed_result_reused"
        _record_leak_delta(row, parent_leaks)
        counters["reused"] += 1
        save_state(state)
        results.append(_compact_row(row))
        return "REUSED"
    if probe["status"] == "NOT_STARTED":
        row["resumed_from"] = "not_started_reused_candidate"
        run = production.run_simulation(session_config(), {"candidate_id": candidate, "candidate_sha256": row["candidate_sha256"]})
        row["run"] = {k: run.get(k) for k in ("status", "simulation_started_counted", "result")}
        if run.get("status") not in ("COMPLETED", "IDEMPOTENT_COMPLETED"):
            state["stopped"] = True
            state["blocker"] = {"kind": "resume_simulation_not_completed", "candidate_id": candidate, "run": run}
            save_state(state)
            results.append(_compact_row(row))
            return "STOP"
        if run.get("status") == "COMPLETED":
            counters["real_runs"] += 1
        else:
            row["resumed_from"] = "completed_result_reused"
        row["observed"] = observe(candidate)
        _record_leak_delta(row, parent_leaks)
        counters["resumed"] += 1
        save_state(state)
        results.append(_compact_row(row))
        return "RESUMED"
    state["stopped"] = True
    state["blocker"] = {
        "kind": "interrupted_execution_unknown_result",
        "candidate_id": candidate,
        "execution_state": probe,
        "instruction": "Do not rerun blindly; inspect the reservation/attempt files and report before any further action.",
    }
    save_state(state)
    results.append({"name": row.get("name"), "candidate_id": candidate, "status": "INTERRUPTED_UNKNOWN_RESULT", "execution_state": probe})
    return "STOP"


def _compact_row(row: dict) -> dict:
    compact = {k: row.get(k) for k in ("name", "parameters", "status", "candidate_id", "plan_id", "resumed_from") if k in row}
    if row.get("observed"):
        observed_keys = (
            "result",
            "leak_ids",
            "leak_ids_available",
            "protected_arrivals",
            "protected_arrival_distinct_count",
            "stage_acceptance",
            "artillery_kill",
            "key_enemy_kills",
            "operator_deaths",
            "complete_win",
            "artifact_projection",
            "artifact_win",
        )
        compact["observed"] = {key: row["observed"].get(key) for key in observed_keys}
    if row.get("leak_delta"):
        compact["leak_delta"] = row["leak_delta"]
    if row.get("check") and row["check"].get("errors"):
        compact["errors"] = row["check"]["errors"]
    if row.get("input_error"):
        compact["input_error"] = row["input_error"]
    return compact


def search_variants(_config, arguments: dict) -> dict:
    state = batch_state()
    constraints = batch_constraints()
    round_number = int(arguments["round"])
    round_max = int(constraints.get("round_max", 5))
    if state.get("stopped"):
        raise RuntimeError("batch stopped; read status.blocker and report instead of retrying")
    if not 1 <= round_number <= round_max:
        raise RuntimeError(f"round must be within 1..{round_max}")
    if round_number not in {row["round"] for row in state["rounds"]}:
        raise RuntimeError("record the Astra hypothesis for this round with record_round first")

    teacher_message_id = arguments.get("teacher_message_id")
    if teacher_message_id is not None:
        if not any(row.get("message_id") == teacher_message_id for row in teacher_messages()):
            raise RuntimeError(f"unknown teacher_message_id: {teacher_message_id!r}; record the teacher prompt first")

    params = arguments.get("parameters") or {}
    names, planned_total, grid_shape = plan_grid(params)
    if planned_total == 0:
        return {"status": "EMPTY_PARAMETER_GRID", "planned_total": 0, "grid": grid_shape}
    if planned_total > MAX_COMBINATIONS_PER_CALL:
        return {
            "status": "COMBINATION_CAP_EXCEEDED",
            "planned_total": planned_total,
            "cap": MAX_COMBINATIONS_PER_CALL,
            "grid": grid_shape,
            "note": "Narrow the range, split into several calls, or lower the grid; nothing was allocated or executed.",
        }

    budget = remaining_budget()
    reserved = budget["reserved_simulations"] if arguments.get("reserve_for_verification", True) else 0
    usable_simulations = max(0, budget["simulation_remaining"] - reserved)
    usable_checks = budget["check_remaining"]
    if usable_checks is not None and usable_checks <= 0:
        return {
            "status": "CHECK_BUDGET_EXHAUSTED",
            "planned_total": planned_total,
            "budget": budget,
            "note": "No checks left; a new batch is required before more work can be checked.",
        }
    capability = {
        "check": budget["check_remaining"] if budget["check_remaining"] is not None else "UNBOUNDED",
        "candidate": budget["candidate_remaining"],
        "simulation": budget["simulation_remaining"],
        "reserved_for_verification": reserved,
        "usable_simulations": usable_simulations,
        "planned_total": planned_total,
        "grid": grid_shape,
    }
    if arguments.get("dry_run"):
        return {
            "status": "DRY_RUN_ONLY",
            "planned_total": planned_total,
            "preview": _preview_rows(params, arguments["name"], MAX_PREVIEW_ROWS),
            "preview_truncated": planned_total > MAX_PREVIEW_ROWS,
            "capability": capability,
            "note": "Grid size computed without building the product; static rejection counts only a check.",
        }

    parent_leaks = baseline_leaks(arguments["parent"])
    results: list[dict] = []
    counters = {"attempted": 0, "dedup": 0, "static_fail": 0, "real_runs": 0, "input_rejected": 0, "reused": 0, "resumed": 0}
    stop_reason = None
    processed = 0
    for index, values in enumerate(iter_grid(params)):
        if stop_reason:
            break
        if counters["real_runs"] >= usable_simulations:
            stop_reason = "SIMULATION_BUDGET_TRUNCATED"
            break
        mapping = dict(zip(names, values))
        name = f"{arguments['name']}_{index}"
        processed += 1
        try:
            changes = expand(arguments.get("changes") or [], mapping)
            actions = expand(arguments.get("actions"), mapping)
            payload = build_payload(arguments["parent"], name, changes, arguments["hypothesis"], round_number, actions=actions)
        except Exception as exc:  # recoverable authoring/input error for this one combination
            row = {
                "name": name, "round": round_number, "parent": arguments["parent"],
                "hypothesis": arguments["hypothesis"], "parameters": mapping,
                "status": "INPUT_REJECTED_BEFORE_PRODUCTION_CHECK",
                "input_error": f"{type(exc).__name__}: {exc}",
                "teacher_message_id": teacher_message_id,
                "source": "harness build stage rejected this combination only",
            }
            counters["input_rejected"] += 1
            state["variants"].append(row)
            save_state(state)
            results.append(_compact_row(row))
            continue

        key = action_key(payload)
        known = next((r for r in state["variants"] if r.get("action_key") == key), None)
        archive_key = read(base_dir() / "old_action_index.json").get(key)
        if known or archive_key:
            counters["dedup"] += 1
            if known and known.get("candidate_id"):
                resume = _resume_or_reuse(known, results=results, counters=counters, state=state, parent_leaks=parent_leaks)
                if resume == "STOP":
                    stop_reason = "INTERRUPTED_UNKNOWN_RESULT"
                continue
            results.append({"name": name, "status": "DEDUP", "original": _compact_row(known) if known else archive_key})
            continue

        row = {
            "name": name, "round": round_number, "parent": arguments["parent"],
            "hypothesis": arguments["hypothesis"], "parameters": mapping,
            "changes": changes, "actions_replaced": actions is not None, "action_key": key,
            "teacher_message_id": teacher_message_id,
            "source": "Astra tool arguments expanded mechanically by the harness",
        }
        # A lost batch_state write-back must not buy a second slot for the same frozen plan.
        frozen = frozen_candidate_by_sha(payload_candidate_sha256(payload))
        if frozen is not None:
            row.update(
                candidate_id=frozen["candidate_id"],
                candidate_sha256=frozen["candidate_sha256"],
                plan_id=payload["revised_operational_plans"][0]["operational_plan_id"],
                status="PASS",
            )
            row["reconciled_from"] = "production_ledger_candidate_sha256"
            counters["dedup"] += 1
            resume = _resume_or_reuse(row, results=results, counters=counters, state=state, parent_leaks=parent_leaks)
            if resume == "STOP":
                stop_reason = "INTERRUPTED_UNKNOWN_RESULT"
            continue
        context, derivation = derive_evidence(arguments["parent"])
        install_evidence(context)
        row["evidence_derivation"] = derivation
        try:
            check = checked_plan(None, {"plan": payload})
        except Exception as exc:  # service/ledger fault is not a per-combination input error
            fault = classify_check_fault(exc)
            state["stopped"] = True
            state["blocker"] = {**fault, "combination": name}
            save_state(state)
            results.append({"name": name, "status": fault["kind"].upper(), "error": fault["error"]})
            stop_reason = fault["kind"].upper()
            break
        row["check"] = check
        row["status"] = check.get("status")
        status = check.get("status")
        counters["attempted"] += 1
        if status in ("PASS", "IDEMPOTENT_RECHECK"):
            row.update(
                candidate_id=check["candidate_id"],
                candidate_sha256=check["candidate_sha256"],
                plan_id=payload["revised_operational_plans"][0]["operational_plan_id"],
            )
        state["variants"].append(row)
        save_state(state)

        if status == "IDEMPOTENT_RECHECK":
            # The candidate was already frozen (e.g. the harness crashed after check_plan but before
            # writing back). Reconcile by execution state instead of aborting the whole batch.
            row["recheck_status"] = "IDEMPOTENT_RECHECK"
            row["status"] = "PASS"
            counters["dedup"] += 1
            resume = _resume_or_reuse(row, results=results, counters=counters, state=state, parent_leaks=parent_leaks)
            if resume == "STOP":
                stop_reason = "INTERRUPTED_UNKNOWN_RESULT"
            continue

        if status in FATAL_CHECK_STATUSES:
            kind = fatal_stop_kind(status)
            state["stopped"] = True
            state["blocker"] = {"kind": kind, "combination": name, "check_status": status, "check": check}
            save_state(state)
            results.append(_compact_row(row))
            stop_reason = status
            break
        if status in RECOVERABLE_CHECK_STATUSES:
            if status == "FAIL":
                counters["static_fail"] += 1
            else:
                counters["input_rejected"] += 1
            results.append(_compact_row(row))
            continue
        if status != "PASS":
            state["stopped"] = True
            state["blocker"] = {"kind": "unexpected_check_status", "combination": name, "check": check}
            save_state(state)
            results.append(_compact_row(row))
            stop_reason = status
            break

        try:
            run = production.run_simulation(
                session_config(),
                {"candidate_id": row["candidate_id"], "candidate_sha256": row["candidate_sha256"]},
            )
        except Exception as exc:  # service fault on execution
            fault = classify_check_fault(exc)
            kind = "simulation_ledger_fault" if fault["kind"] == "ledger_inconsistency" else "simulation_service_fault"
            state["stopped"] = True
            state["blocker"] = {"kind": kind, "candidate_id": row["candidate_id"], "error": fault["error"]}
            save_state(state)
            results.append(_compact_row(row))
            stop_reason = "SERVICE_FAULT"
            break
        row["run"] = {k: run.get(k) for k in ("status", "simulation_started_counted", "result")}
        if run.get("status") not in ("COMPLETED", "IDEMPOTENT_COMPLETED"):
            state["stopped"] = True
            state["blocker"] = {"kind": "simulation_not_completed", "candidate_id": row["candidate_id"], "run": run}
            save_state(state)
            results.append(_compact_row(row))
            stop_reason = "SIMULATION_NOT_COMPLETED"
            break
        if run.get("status") == "IDEMPOTENT_COMPLETED":
            # The result already existed on disk; no new simulation was started, so don't count one.
            row["resumed_from"] = "completed_result_reused"
            counters["reused"] += 1
        else:
            counters["real_runs"] += 1
        row["observed"] = observe(row["candidate_id"])
        _record_leak_delta(row, parent_leaks)
        state["variants"][-1] = row
        save_state(state)
        results.append(_compact_row(row))
        if row["observed"].get("complete_win"):
            write(base_dir() / "WIN_PENDING_VERIFICATION.json", {"candidate_id": row["candidate_id"], "name": name})
            return {
                "status": "WIN_MUST_VERIFY",
                "planned_total": planned_total,
                "counters": counters,
                "results": results,
                "capability": capability,
                "next": "call independent_verify with this candidate_id",
            }

    skipped_count = planned_total - processed
    skipped = []
    for index, values in enumerate(iter_grid(params)):
        if index < processed:
            continue
        if len(skipped) >= MAX_PREVIEW_ROWS:
            break
        skipped.append({"index": index, "parameters": dict(zip(names, values))})
    summaries = [
        row
        for row in state["variants"]
        if row.get("observed") and row["round"] == round_number and row.get("candidate_id")
    ]
    complementary: dict[str, list] = {}
    for row in summaries:
        key = str(row["observed"].get("leak_ids") or ["UNKNOWN"])
        complementary.setdefault(key, []).append(
            {
                "name": row["name"],
                "candidate_id": row["candidate_id"],
                "plan_id": row.get("plan_id"),
                "leak_delta": row.get("leak_delta"),
                "protected_arrival_distinct_count": row["observed"].get("protected_arrival_distinct_count"),
                "artillery_kill": bool(row["observed"].get("artillery_kill")),
                "stage_acceptance": (row["observed"].get("stage_acceptance") or {}).get("status"),
            }
        )
    return {
        "status": stop_reason or "COMPLETED_PARAMETER_GROUP",
        "planned_total": planned_total,
        "processed": processed,
        "counters": counters,
        "attempted": counters["attempted"],
        "dedup": counters["dedup"],
        "static_fail": counters["static_fail"],
        "real_runs": counters["real_runs"],
        "skipped_count": skipped_count,
        "skipped_preview": skipped,
        "results": results,
        "parent_leaks": parent_leaks,
        "complementary_by_leak_set": complementary,
        "capability": capability,
        "budget_after": remaining_budget(),
        "blocker": state.get("blocker"),
    }


def inspect_evidence(_config, arguments: dict) -> dict:
    kind = arguments.get("kind", "events")
    source = arguments.get("source", "A")
    if kind == "priority":
        return batch_constraints()
    if kind == "actions":
        plan = resolve_plan(source)
        return {
            "plan_id": plan.get("operational_plan_id"),
            "selected": plan.get("selected_low_star_operator_ids"),
            "actions": plan.get("action_timeline"),
            "validation_card": plan.get("validation_card"),
        }
    if kind == "plan":
        return get_parent(source)
    if kind == "outcome":
        events = parent_events(source)
        if events is None:
            return {"source": source, "status": "NO_RECORDED_EVENTS"}
        return {
            "source": source,
            "leaks": [e for e in events if e.get("event_type") == "ENEMY_LEAK"],
            "kills": [e for e in events if e.get("event_type") == "ENEMY_DEATH"],
            "deaths": [e for e in events if e.get("event_type") == "OPERATOR_DEATH"],
            "arrivals": [e for e in events if e.get("event_type") == "PROTECTED_TARGET_REACHED"],
            "devices": [e for e in events if e.get("event_type") == "DEVICE_DESTROYED"],
        }
    if kind == "facts":
        facts = read(base_dir() / "input_bundle" / "template_context.json")
        keys = arguments.get("keys") or ["stage_active_facts", "stage_options", "source_routes", "model_spawn_timeline"]
        return {k: facts.get(k) for k in keys}
    if kind == "catalog":
        catalog = read(base_dir() / "input_bundle" / "template_context.json")["normal_low_star_catalog"]
        ids = set(arguments.get("ids") or [])
        return [o for o in catalog if not ids or o["operator_id"] in ids]
    if kind == "diff":
        left = resolve_plan(source)["action_timeline"]
        right = resolve_plan(arguments.get("other", "C"))["action_timeline"]
        left_map = {canon(a): a for a in left}
        right_map = {canon(a): a for a in right}
        return {
            "source": source,
            "other": arguments.get("other", "C"),
            "only_source": [left_map[k] for k in left_map.keys() - right_map.keys()],
            "only_other": [right_map[k] for k in right_map.keys() - left_map.keys()],
        }
    if kind == "code":
        path = (ROOT / arguments["path"]).resolve()
        path.relative_to(ROOT)
        if not path.is_file() or path.suffix not in (".py", ".json", ".md"):
            raise RuntimeError("read-only code path invalid")
        lines = path.read_text(encoding="utf-8").splitlines()
        start = max(0, int(arguments.get("line", 1)) - 1)
        count = min(int(arguments.get("limit", 100)), 200)
        return {
            "path": str(path.relative_to(ROOT)),
            "first_line": start + 1,
            "lines": lines[start:start + count],
            "sha256": sha(path),
        }
    if kind == "kb":
        entries = read(KB_PATH)
        query = (arguments.get("query") or "").strip()
        topic = arguments.get("topic")
        ids = set(arguments.get("ids") or [])
        matches = []
        for entry in entries:
            if ids and entry["id"] not in ids:
                continue
            if topic and entry.get("topic") != topic:
                continue
            haystack = " ".join(
                [entry.get("id", ""), entry.get("title", ""), entry.get("summary", ""), *entry.get("details", [])]
            )
            if query and query not in haystack:
                continue
            matches.append(
                {
                    "id": entry["id"],
                    "topic": entry.get("topic"),
                    "title": entry.get("title"),
                    "summary": entry.get("summary"),
                    "details": entry.get("details"),
                    "source": entry.get("source"),
                    "source_url": entry.get("source_url"),
                    "sim_check_points": entry.get("sim_check_points"),
                    "scope": "MECHANICS_REFERENCE_REQUIRES_SIMULATOR_VERIFICATION",
                }
            )
        return {
            "kb_path": str(KB_PATH.relative_to(ROOT)),
            "kb_sha256": sha(KB_PATH),
            "query": query,
            "topic": topic,
            "total_matches": len(matches),
            "entries": matches[: int(arguments.get("limit", 10))],
            "boundary": "Mechanics references are not stage-specific facts; confirm each sim_check_point against the current simulator before relying on it.",
        }
    if kind == "experience":
        records = []
        if EXPERIENCE_STORE.is_file():
            records = [json.loads(line) for line in EXPERIENCE_STORE.read_text(encoding="utf-8").splitlines() if line.strip()]
        tags = set(arguments.get("tags") or [])
        record_ids = set(arguments.get("ids") or [])
        query = (arguments.get("query") or "").strip()
        selected = []
        for record in records:
            if record_ids and record.get("record_id") not in record_ids:
                continue
            if tags and not tags & set(record.get("responsibility_tags") or []):
                continue
            haystack = " ".join(
                str(record.get(key, ""))
                for key in ("record_id", "plan_id", "applicable_conditions")
            )
            if query and query not in haystack:
                continue
            selected.append(
                {
                    "record_id": record.get("record_id"),
                    "plan_id": record.get("plan_id"),
                    "candidate_id": record.get("candidate_id"),
                    "mechanics_version": record.get("mechanics_version"),
                    "mechanics_current": record.get("mechanics_version") == ACTIVE_MECHANICS_VERSION,
                    "selector_verdict": (
                        "CURRENT"
                        if record.get("mechanics_version") == ACTIVE_MECHANICS_VERSION
                        else "MECHANICS_NOT_CURRENT"
                    ),
                    "responsibility_tags": record.get("responsibility_tags"),
                    "operator_union": record.get("operator_union"),
                    "operator_union_count": record.get("operator_union_count"),
                    "applicable_conditions": record.get("applicable_conditions"),
                    "unknown_fields": record.get("unknown_fields"),
                    "model_predictions": record.get("model_predictions"),
                    "observed_key_events": (record.get("event_observation_summary") or {}).get("observed_key_events"),
                    "summary_result": (record.get("event_observation_summary") or {}).get("summary_result"),
                    "responsible_paths": record.get("responsible_paths"),
                    "archive_status": record.get("archive_status"),
                    "scope": "CROSS_STAGE_UNTESTED",
                }
            )
        selected.sort(key=lambda r: (not r["mechanics_current"], r["record_id"] or ""))
        return {
            "store": str(EXPERIENCE_STORE.relative_to(ROOT)),
            "store_mechanics_version": EXPERIENCE_MECHANICS_VERSION,
            "active_mechanics_version": ACTIVE_MECHANICS_VERSION,
            "total_records": len(records),
            "matched": len(selected),
            "records": selected[: int(arguments.get("limit", 6))],
            "boundary": "Archived experience is cross-stage background, not a validated rule for this batch; check mechanics_version and re-verify any borrowed action against this stage.",
        }
    events = parent_events(source)
    if events is None:
        return {"source": source, "status": "NO_RECORDED_EVENTS", "total_matches": 0, "events": []}
    types = set(arguments.get("event_types") or [])
    ids = set(arguments.get("ids") or [])
    start = int(arguments.get("earliest_frame", 0))
    end = int(arguments.get("latest_frame", 10 ** 9))
    matches = [
        (index, event)
        for index, event in enumerate(events)
        if start <= event.get("frame", -1) <= end
        and (not types or event.get("event_type") in types)
        and (not ids or {event.get("source_id"), event.get("target_id")} & ids)
    ]
    offset = int(arguments.get("offset", 0))
    limit = min(int(arguments.get("limit", 100)), 200)
    page = matches[offset:offset + limit]
    if arguments.get("aggregate"):
        totals: dict[str, int] = {}
        frames: dict[str, list[int]] = {}
        for _, event in matches:
            key = f"{event.get('source_id', '')} -> {event.get('target_id')} {event['event_type']}"
            totals[key] = totals.get(key, 0) + (event.get("details") or {}).get("amount", 0)
            frames.setdefault(key, []).append(event["frame"])
        return {
            "source": source,
            "matched": len(matches),
            "groups": {
                k: {"sum": v, "count": len(frames[k]), "first": min(frames[k]), "last": max(frames[k])}
                for k, v in totals.items()
            },
            "full_log_complete": True,
        }
    return {
        "source": source,
        "total_matches": len(matches),
        "offset": offset,
        "returned": len(page),
        "next_offset": offset + len(page) if offset + len(page) < len(matches) else None,
        "events": [{"raw_index": index, **event} for index, event in page],
        "full_log_complete": True,
    }


def record_round(_config, arguments: dict) -> dict:
    round_number = int(arguments["round"])
    round_max = int(batch_constraints().get("round_max", 5))
    if not 1 <= round_number <= round_max:
        raise RuntimeError(f"at most {round_max} rounds in this batch")
    state = batch_state()
    if state.get("stopped"):
        raise RuntimeError("batch stopped")
    row = {
        "round": round_number,
        "expected": arguments.get("expected"),
        "observed": arguments.get("observed"),
        "next_reason": arguments.get("next_reason"),
        "decision": arguments.get("decision"),
        "source": "Actual Astra tool request, retained verbatim",
        "at": time.time(),
    }
    state["rounds"].append(row)
    save_state(state)
    unique = sorted({r["round"] for r in state["rounds"]})
    return {
        "status": "RECORDED",
        "round": round_number,
        "unique_rounds": unique,
        "remaining_rounds": round_max - len(unique),
    }


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def teacher_messages() -> list[dict]:
    return _read_jsonl(base_dir() / "teaching" / "teacher_prompts_v1.jsonl")


def record_teacher_prompt(_config, arguments: dict) -> dict:
    """Save a teacher message verbatim first, with a stable ID. No rewriting."""
    text = arguments.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("teacher prompt text is required")
    payload = text.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    path = base_dir() / "teaching" / "teacher_prompts_v1.jsonl"
    existing = next((row for row in teacher_messages() if row.get("sha256") == digest), None)
    if existing is not None:
        return {
            "status": "ALREADY_RECORDED",
            "message_id": existing["message_id"],
            "sha256": digest,
            "bytes": len(payload),
            "path": str(path.relative_to(ROOT)),
            "note": "Identical text already stored; reusing the original message_id so references stay stable.",
        }
    message_id = _new_message_id("teacher")
    append_jsonl(
        path,
        {
            "message_id": message_id,
            "at": _utc_now_iso(),
            "source": arguments.get("source", "user"),
            "sha256": digest,
            "bytes": len(payload),
            "received_by": arguments.get("received_by", "tactical_side"),
            "text": text,
        },
    )
    return {
        "status": "RECORDED",
        "message_id": message_id,
        "sha256": digest,
        "bytes": len(payload),
        "path": str(path.relative_to(ROOT)),
        "next": "Reference this message_id in record_teaching so Astra's interpretation is linked to the original teacher message.",
    }


def record_teaching(_config, arguments: dict) -> dict:
    """Three separate, append-only records: teacher quote, Astra interpretation, simulation observation."""
    teaching_dir = base_dir() / "teaching"
    teacher_message_id = arguments.get("teacher_message_id")
    stored = None
    if teacher_message_id:
        stored = next((row for row in teacher_messages() if row.get("message_id") == teacher_message_id), None)
        if stored is None:
            raise RuntimeError(f"unknown teacher_message_id: {teacher_message_id!r}; record the teacher prompt first")

    quote = arguments.get("user_quote")
    provenance = "ASTRA_SUPPLIED_QUOTE_NOT_TEACHER_VERIFIED"
    quote_sha = None
    mismatch = None
    if stored is not None:
        if quote is None:
            quote = stored["text"]
            provenance = "TEACHER_VERBATIM_RESOLVED_FROM_STORED_MESSAGE"
        else:
            quote_sha = hashlib.sha256(quote.encode("utf-8")).hexdigest()
            if quote_sha == stored["sha256"]:
                provenance = "TEACHER_VERBATIM_MATCHED_STORED_MESSAGE"
            else:
                provenance = "ASTRA_QUOTE_DIVERGES_FROM_STORED_TEACHER_MESSAGE"
                mismatch = {"astra_quote_sha256": quote_sha, "stored_sha256": stored["sha256"]}
    elif quote is not None:
        quote_sha = hashlib.sha256(quote.encode("utf-8")).hexdigest()

    interpretation = arguments.get("astra_interpretation")
    observation = arguments.get("simulation_observation")
    if not (quote or stored) and not interpretation and observation is None:
        raise RuntimeError("a teaching record needs at least a teacher reference/quote, an Astra interpretation, or an observation")

    observation_ref = {
        "candidate_id": arguments.get("candidate_id"),
        "run_id": arguments.get("run_id"),
        "event_log": arguments.get("event_log"),
        "event_locator": arguments.get("event_locator"),
    }
    # A candidate id alone still has a deterministic, single event log; resolve it so the
    # observation stays locatable instead of pointing at nothing.
    if observation_ref["candidate_id"] and not observation_ref["event_log"]:
        candidate_events = base_dir() / "session/candidates" / observation_ref["candidate_id"] / "simulation/diagnostic_events.json"
        if candidate_events.is_file():
            observation_ref["event_log"] = str(candidate_events.relative_to(ROOT))
    has_obs_ref = any(value is not None for value in observation_ref.values())

    record_id = arguments.get("record_id") or _new_message_id("teaching")
    at = _utc_now_iso()
    base_record = {
        "record_id": record_id,
        "at": at,
        "round": arguments.get("round"),
        "teacher_message_id": teacher_message_id,
        "quote_provenance": provenance,
        "quote_mismatch": mismatch,
        "scope": arguments.get("scope", "THIS_STAGE_ONLY"),
        "abstract_rule": arguments.get("abstract_rule"),
        "counterexample": arguments.get("counterexample"),
        "source_capability": {
            "teacher_reference": "STORED_MESSAGE" if stored is not None else (
                "UNLINKED_QUOTE" if quote is not None else "NONE"
            ),
            "observation_located": bool(observation_ref.get("run_id") or observation_ref.get("event_locator")
                                        or observation_ref.get("event_log")),
        },
    }
    if quote is not None or stored is not None:
        append_jsonl(
            teaching_dir / "user_quotes_v1.jsonl",
            {
                "record_id": record_id, "at": at, "round": arguments.get("round"),
                "teacher_message_id": teacher_message_id, "provenance": provenance,
                "quote_sha256": quote_sha if quote_sha is not None else (stored or {}).get("sha256"),
                "quote": quote, "quote_mismatch": mismatch,
            },
        )
    if interpretation is not None:
        append_jsonl(
            teaching_dir / "astra_interpretations_v1.jsonl",
            {
                "record_id": record_id, "at": at, "round": arguments.get("round"),
                "teacher_message_id": teacher_message_id, "interpretation": interpretation,
                "author": "astra",
            },
        )
    if observation is not None or has_obs_ref:
        append_jsonl(
            teaching_dir / "observations_v1.jsonl",
            {
                "record_id": record_id, "at": at, "round": arguments.get("round"),
                **observation_ref, "observation": observation,
            },
        )
    append_jsonl(teaching_dir / "records_v1.jsonl", base_record)
    state = batch_state()
    state.setdefault("teaching_records", []).append(base_record)
    save_state(state)
    return {
        "status": "RECORDED",
        "record_id": record_id,
        "teacher_message_id": teacher_message_id,
        "quote_provenance": provenance,
        "quote_mismatch": mismatch,
        "separate_files": [
            str((teaching_dir / name).relative_to(ROOT))
            for name in ("user_quotes_v1.jsonl", "astra_interpretations_v1.jsonl", "observations_v1.jsonl")
        ],
        "rule_scope": base_record["scope"],
        "note": "Quote, interpretation and observation are appended separately; an Astra paraphrase is never labelled as the verified teacher text.",
    }


def independent_verify(_config, arguments: dict) -> dict:
    candidate = arguments["candidate_id"]
    state = batch_state()
    row = next((r for r in state["variants"] if r.get("candidate_id") == candidate), None)
    if row is None:
        raise RuntimeError("candidate is not registered in this harness batch")
    if session_config().execution_backend == "TEST_ONLY_FAKE":
        run = production.run_simulation(
            session_config(),
            {"candidate_id": candidate, "candidate_sha256": row["candidate_sha256"]},
        )
        return {
            "status": "CACHE_HIT_NOT_INDEPENDENT",
            "backend": "TEST_ONLY_FAKE",
            "observed_run_status": run.get("status"),
            "cache_hit": True,
            "counts_as_independent_verification": False,
            "reason": "The fake backend returns IDEMPOTENT_COMPLETED for an already-finished candidate; this is a cache hit, not an independent rerun.",
        }
    record = read(base_dir() / "session" / "candidates" / candidate / "candidate_record.json")
    if record.get("check_status") != "PASS":
        raise RuntimeError("only PASS candidates can be independently verified")
    for code, expected in record["controlled_code_sha256"].items():
        if sha(ROOT / code) != expected:
            raise RuntimeError(f"controlled code changed: {code}")
    run_id = f"independent-{len(state.get('independent_runs') or []) + 1}"
    target = base_dir() / "reverification" / run_id
    if target.exists():
        raise RuntimeError("independent run path already exists; no retry")
    import shutil
    import subprocess

    import tactical_evaluation_gate_v1 as gate

    source = target / "source"
    source.mkdir(parents=True)
    for name, expected in record["frozen_inputs_sha256"].items():
        original = base_dir() / "session" / "candidates" / candidate / "source" / name
        if sha(original) == expected:
            shutil.copyfile(original, source / name)
        elif name == "execution_input_gate.json":
            write(source / name, row["check"]["execution_input_gate"])
            if sha(source / name) != expected:
                raise RuntimeError("frozen input mismatch")
        else:
            raise RuntimeError(f"frozen input mismatch: {name}")
    output = target / "simulation"
    budget_before = read(session_config().budget_path)["started_stage_simulations"]
    prepared = gate.prepare_evaluation(
        source_dir=source,
        diagnostic_output_dir=output,
        budget_path=session_config().budget_path,
        stage_id=session_config().stage_id,
        expected_plan_id=record["plan_id"],
    )
    if prepared.get("status") != "AUTHORIZED":
        raise RuntimeError(f"independent verification preflight refused: {prepared}")
    command = [
        sys.executable,
        str(ROOT / "scripts/run_gpt_tactical_stage_session_v1.py"),
        "simulate",
        "--stage-id", session_config().stage_id,
        "--facts-dir", str(source.relative_to(ROOT)),
        "--output-dir", str(source.relative_to(ROOT)),
        "--diagnostic-output-dir", str(output.relative_to(ROOT)),
        "--plan-id", record["plan_id"],
        "--plan-label", session_config().plan_label,
        "--plan-id-prefix", session_config().plan_id_prefix,
        "--max-unique-deployed-operators", str(session_config().max_unique_deployed_operators),
        "--authorization-config", str(session_config().authorization_config_path.relative_to(ROOT)),
        "--simulation-budget-path", str(session_config().budget_path.relative_to(ROOT)),
    ]
    write(target / "provenance.json", {
        "candidate_id": candidate,
        "command": command,
        "gate": prepared,
        "frozen_inputs_sha256": record["frozen_inputs_sha256"],
        "budget_before": budget_before,
        "source": "Astra explicitly requested an independent rerun",
    })
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (target / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (target / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        state["stopped"] = True
        state["blocker"] = {"kind": "independent_run_failed", "run_id": run_id, "returncode": completed.returncode}
        save_state(state)
        raise RuntimeError("independent production run failed; no retry")
    budget_after = read(session_config().budget_path)["started_stage_simulations"]
    if budget_after != budget_before + 1:
        raise RuntimeError("independent run did not consume exactly one simulation")
    original = base_dir() / "session" / "candidates" / candidate / "simulation"
    equal = {
        name: sha(output / name) == sha(original / name)
        for name in ("plan_snapshot.json", "action_snapshot.json", "diagnostic_events.json")
    }
    summary = read(output / "diagnostic_summary.json")
    item = {
        "run_id": run_id,
        "candidate_id": candidate,
        "hash_equal": equal,
        "result": {k: v for k, v in (summary.get("result") or {}).items() if k != "events"},
        "budget_before": budget_before,
        "budget_after": budget_after,
        "path": str(output.relative_to(ROOT)),
        "counts_as_independent_verification": True,
    }
    if all(equal.values()) and (row.get("observed") or {}).get("complete_win"):
        state["stopped"] = True
        state["verified_win"] = candidate
    state.setdefault("independent_runs", []).append(item)
    save_state(state)
    write(target / "verification.json", item)
    return item


EXTRA_TOOLS = [
    {
        "name": "inspect_evidence",
        "description": (
            "Read-only evidence. kinds: events (raw event log with ids/frames/pagination), plan, actions, outcome, facts, "
            "catalog, diff, code, priority, kb (mechanics knowledge base), experience (archived cross-stage records). "
            "No simulation and no inference."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["events", "plan", "actions", "outcome", "facts", "catalog", "diff", "code", "priority", "kb", "experience"]},
                "source": {"type": "string"},
                "other": {"type": "string"},
                "ids": {"type": "array", "items": {"type": "string"}},
                "event_types": {"type": "array", "items": {"type": "string"}},
                "earliest_frame": {"type": "integer"},
                "latest_frame": {"type": "integer"},
                "offset": {"type": "integer"},
                "limit": {"type": "integer"},
                "aggregate": {"type": "boolean"},
                "keys": {"type": "array", "items": {"type": "string"}},
                "path": {"type": "string"},
                "line": {"type": "integer"},
                "query": {"type": "string"},
                "topic": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "record_round",
        "description": "Save one Astra question/decision round with its expected change and the evidence that will decide it.",
        "inputSchema": {
            "type": "object",
            "required": ["round"],
            "properties": {"round": {"type": "integer"}, "expected": {}, "observed": {}, "next_reason": {}, "decision": {}},
            "additionalProperties": False,
        },
    },
    {
        "name": "search_variants",
        "description": (
            "Enumerate Astra-authored change sets through the production check/freeze/run chain. "
            "A combination is (parameters Cartesian product) applied to 'changes'. "
            "Change types: set {operator, action, frame, fields}, remove {operator, action, frame}, "
            "add {value: full action}, replace {operator, replacement}. '$name' substitutes a parameter grid value. "
            "Optional 'actions' is a complete Astra-authored timeline that changes then patch. "
            "Use dry_run=true to see combination count and remaining capability before spending anything. "
            "Static rejection consumes a check only; PASS consumes one candidate; only PASS can run one simulation."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["round", "name", "parent", "hypothesis"],
            "properties": {
                "round": {"type": "integer"},
                "name": {"type": "string", "pattern": "^[A-Za-z0-9_]+$"},
                "parent": {"type": "string"},
                "hypothesis": {"type": "string"},
                "teacher_message_id": {"type": "string"},
                "changes": {"type": "array", "items": {"type": "object"}},
                "actions": {"type": "array", "items": {"type": "object"}},
                "parameters": {"type": "object", "additionalProperties": {"type": "array"}},
                "dry_run": {"type": "boolean"},
                "reserve_for_verification": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "record_teaching",
        "description": (
            "Append separate records: teacher quote (by teacher_message_id), Astra interpretation, and a simulation observation "
            "referencing a run/event. Astra paraphrases are never labelled as the verified teacher text. "
            "If teacher_message_id is given with no user_quote, the stored verbatim text is used. If both are given and differ, both are stored and the mismatch is flagged."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string"},
                "round": {"type": "integer"},
                "teacher_message_id": {"type": "string"},
                "user_quote": {"type": "string"},
                "astra_interpretation": {"type": "string"},
                "simulation_observation": {},
                "candidate_id": {"type": "string"},
                "run_id": {"type": "string"},
                "event_log": {"type": "string"},
                "event_locator": {"type": "object"},
                "abstract_rule": {"type": "string"},
                "scope": {"type": "string", "enum": ["THIS_STAGE_ONLY", "CROSS_STAGE_PENDING"]},
                "counterexample": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "record_teacher_prompt",
        "description": "Store a teacher message verbatim (first) and return a stable message_id plus sha256. Identical text reuses the original message_id. No rewriting.",
        "inputSchema": {
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}, "source": {"type": "string"}, "received_by": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "independent_verify",
        "description": "Re-execute one PASS frozen candidate with a new run id and unchanged inputs. In fake-backend mode this truthfully reports a cache hit instead of a fake independent run.",
        "inputSchema": {
            "type": "object",
            "required": ["candidate_id"],
            "properties": {"candidate_id": {"type": "string"}},
            "additionalProperties": False,
        },
    },
]

HANDLERS = {
    "inspect_evidence": inspect_evidence,
    "record_round": record_round,
    "search_variants": search_variants,
    "record_teaching": record_teaching,
    "record_teacher_prompt": record_teacher_prompt,
    "independent_verify": independent_verify,
    "get_session_status": status,
    "check_plan": checked_plan,
    "run_simulation": run_simulation,
    "query_events": query_events,
}


def tools_list() -> list[dict]:
    return production.TOOLS + EXTRA_TOOLS


def dispatch(message: dict) -> dict | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools_list()}}
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {**production.tool_result({"error": "UNKNOWN_TOOL", "tool": name}), "isError": True},
            }
        log = base_dir() / "tool_transport.jsonl"
        started = time.time()
        append_jsonl(log, {"phase": "STARTED", "at": started, "id": request_id, "tool": name, "arguments": arguments})
        try:
            with redirect_stdout(sys.stderr):
                value = handler(session_config(), arguments)
            response = {"jsonrpc": "2.0", "id": request_id, "result": production.tool_result(value)}
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": production.tool_result({"error": type(exc).__name__, "message": str(exc), "automatic_retry": False}),
            }
            response["result"]["isError"] = True
        append_jsonl(
            log,
            {"phase": "COMPLETED", "at": time.time(), "id": request_id, "tool": name, "response": response},
        )
        return response
    return production.handle_message(session_config(), message)


def main() -> None:
    global BASE, CONFIG
    if len(sys.argv) != 2:
        raise SystemExit("usage: tactical_harness_service_v1.py <batch-dir-or-session-config.json>")
    target = Path(sys.argv[1])
    if target.suffix == ".json":
        CONFIG = production.load_session_config(target)
        BASE = target.resolve().parent
    else:
        BASE = target.resolve()
        CONFIG = production.load_session_config(BASE / "session_config_v1.json")
    if not (BASE / "batch_state.json").is_file():
        raise SystemExit(f"not a prepared harness batch: {BASE}")
    state_schema = read(BASE / "batch_state.json").get("schema_version")
    if state_schema != STATE_SCHEMA:
        raise SystemExit(f"unsupported harness batch state schema: {state_schema!r}")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"parse error: {exc}"}}, ensure_ascii=False), flush=True)
            continue
        response = dispatch(message)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
