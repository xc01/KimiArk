from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tactical_evaluation_gate_v1 as gate
import tactical_experience_v1 as experience
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import ActionType
from compile_r8_1_lowstar_c2_plan_v1 import compile_plan
from run_gpt_tactical_stage_session_v1 import (
    distinct_deployed_operator_ids,
    validate_execution_input,
    validate_normal_low_star_capability_source,
    validate_open_roster_contract,
    validate_parent_hypothesis_reference,
    validate_plan_payload,
)


SERVICE_INFO = {"name": "kimiark-closed-loop-tools", "version": "1.0.0"}
PROTOCOL_VERSION = "2025-06-18"
CONFIG_SCHEMA_VERSION = "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1"
CANDIDATE_LEDGER_SCHEMA_V1 = "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V1"
CANDIDATE_LEDGER_SCHEMA_V2 = "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2"
CANDIDATE_LEDGER_SCHEMA_VERSION = CANDIDATE_LEDGER_SCHEMA_V1
SUPPORTED_CANDIDATE_LEDGER_SCHEMAS = {CANDIDATE_LEDGER_SCHEMA_V1, CANDIDATE_LEDGER_SCHEMA_V2}
CANDIDATE_RECORD_SCHEMA_VERSION = "KIMIARK_CLOSED_LOOP_CANDIDATE_RECORD_V1"
SIMULATION_REQUEST_SCHEMA_VERSION = "KIMIARK_CLOSED_LOOP_SIMULATION_REQUEST_V1"
EVENT_QUERY_SCHEMA_VERSION = "KIMIARK_CLOSED_LOOP_EVENT_QUERY_V1"
CANDIDATE_ID_RE = re.compile(r"candidate-[0-9]{3,}")
DETAIL_KEY_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}(?:\.[A-Za-z0-9_.-]{1,64})*")
MAX_EVENT_PAGE_SIZE = 200
MAX_EVENT_RESPONSE_BYTES = 1_048_576
ACTION_TYPE_NAMES = sorted(item.value for item in ActionType)
SUPPORTED_EVENT_TYPE_NAMES = sorted(item.value for item in EventType)
QUERY_EVENT_TYPE_NAMES = sorted({*SUPPORTED_EVENT_TYPE_NAMES, *experience.EVENT_ALIASES})

CONTROLLED_EXECUTION_FILES = (
    "scripts/kimiark_tactical_stdio_service_v1.py",
    "scripts/kimiark_mcp_server.py",
    "scripts/run_gpt_tactical_stage_session_v1.py",
    "scripts/run_gpt_tactical_stage_diagnostic_v1.py",
    "scripts/tactical_evaluation_gate_v1.py",
    "scripts/compile_r8_1_lowstar_c2_plan_v1.py",
)

TOOLS = [
    {
        "name": "get_session_status",
        "description": "Read a service-owned session, quotas, and the distinction between action names and event names.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "check_plan",
        "description": "No-battle contract, roster, execution-fact, and static check. Valid action_type is ACTIVATE_SKILL; valid observed event_type is SKILL_ACTIVATE. A check consumes the configured check-call budget; only PASS creates and consumes a real candidate slot.",
        "inputSchema": {
            "type": "object", "required": ["plan"],
            "properties": {"plan": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "run_simulation",
        "description": "Run one authorized complete fixed-plan simulation through the existing gate. STARTED failures count and are never retried.",
        "inputSchema": {
            "type": "object",
            "required": ["candidate_id", "candidate_sha256"],
            "properties": {
                "candidate_id": {"type": "string"},
                "candidate_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "query_events",
        "description": "Read-only deterministic query of one event type at a time. Operator HP damage may be DAMAGE or ENEMY_ABILITY_HIT; DEVICE_DAMAGE is for roadblocks/devices. No model or causal inference.",
        "inputSchema": {
            "type": "object", "required": ["candidate_id", "candidate_sha256", "event_type"],
            "properties": {
                "candidate_id": {"type": "string"},
                "candidate_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "event_type": {"type": "string", "enum": QUERY_EVENT_TYPE_NAMES},
                "source_id": {"type": ["string", "null"]},
                "target_id": {"type": ["string", "null"]},
                "earliest_frame": {"type": "integer"},
                "latest_frame": {"type": "integer"},
                "details_equal": {
                    "type": "array",
                    "items": {
                        "type": "object", "required": ["key", "value"],
                        "properties": {"key": {"type": "string"}, "value": {}},
                        "additionalProperties": False,
                    },
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                "offset": {"type": "integer", "minimum": 0},
                "aggregate": {
                    "type": "object", "required": ["field"],
                    "properties": {"field": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
    },
]


@dataclass(frozen=True)
class SessionConfig:
    path: Path
    session_id: str
    stage_id: str
    plan_id_prefix: str
    plan_label: str
    model: str
    reasoning_effort: str
    features_apps: bool
    mechanics_version: str
    facts_source_dir: Path
    session_root: Path
    budget_path: Path
    candidate_ledger_path: Path
    authorization_config_path: Path
    max_unique_deployed_operators: int
    max_candidates: int
    max_check_calls: int | None
    simulation_timeout_seconds: int
    execution_backend: str
    allow_fake_execution: bool


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def repository_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f"path outside KimiArk repository is forbidden: {value}") from exc
    return path


def safe_output_path(root: Path, *parts: str) -> Path:
    candidate = root
    for part in parts:
        if part in {".", ".."} or "/" in part or "\\" in part:
            raise RuntimeError("unsafe path component")
        candidate = candidate / part
        if candidate.is_symlink():
            raise RuntimeError("symlink escape is forbidden")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError("path traversal outside session root is forbidden") from exc
    return resolved


def atomic_write_json(path: Path, payload: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if exclusive and path.exists():
        raise RuntimeError(f"immutable output already exists: {path}")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(text, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_identifier(candidate_id: Any) -> str:
    if not isinstance(candidate_id, str) or not CANDIDATE_ID_RE.fullmatch(candidate_id):
        raise RuntimeError("invalid candidate_id")
    return candidate_id


def _required_string(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"session config {key} must be a non-empty string")
    return value


def _required_int(config: dict[str, Any], key: str, *, minimum: int) -> int:
    value = config.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise RuntimeError(f"session config {key} must be an integer >= {minimum}")
    return value


def load_session_config(path: Path) -> SessionConfig:
    config_path = repository_path(str(path))
    config = load_json(config_path)
    if not isinstance(config, dict) or config.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise RuntimeError("unsupported closed-loop session config schema")
    if config.get("features_apps") is not False:
        raise RuntimeError("features_apps must be false for this service")
    if config.get("mechanics_version") != ACTIVE_MECHANICS_VERSION:
        raise RuntimeError("configured mechanics version does not match repository active mechanics")
    paths = ("facts_source_dir", "session_root", "budget_path", "candidate_ledger_path", "authorization_config_path")
    for key in paths:
        value = _required_string(config, key)
        if key == "session_root":
            candidate_root = repository_path(value)
            if candidate_root.is_symlink():
                raise RuntimeError("session_root must not be a symlink")
            if candidate_root.exists() and not candidate_root.is_dir():
                raise RuntimeError("session_root must be a directory")
            for parent in candidate_root.parents:
                if parent.is_symlink():
                    raise RuntimeError("session_root path contains symlink")
        else:
            resolved = repository_path(value)
            if resolved.is_symlink():
                raise RuntimeError(f"session config {key} must not be a symlink")
            if key == "facts_source_dir":
                if not resolved.is_dir():
                    raise RuntimeError(f"session config {key} does not exist")
            elif not resolved.is_file():
                raise RuntimeError(f"session config {key} does not exist")
    authorization = load_json(repository_path(config["authorization_config_path"]))
    model = authorization.get("model")
    effort = authorization.get("reasoning_effort")
    if not isinstance(model, str) or not model or model != config.get("model"):
        raise RuntimeError("authorization model does not match session config")
    if not isinstance(effort, str) or not effort or effort != config.get("reasoning_effort"):
        raise RuntimeError("authorization reasoning effort does not match session config")
    if not isinstance(config.get("session_id"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", config["session_id"]):
        raise RuntimeError("invalid session_id")
    facts_source_dir = repository_path(config["facts_source_dir"])
    for name in ("llm_evidence_context.json", "revision_output_schema.json"):
        if not (facts_source_dir / name).is_file():
            raise RuntimeError(f"facts source missing {name}")
    execution_backend = config.get("execution_backend", "CONTROLLED_RUNNER")
    allow_fake_execution = config.get("allow_fake_execution", False)
    if execution_backend not in {"CONTROLLED_RUNNER", "TEST_ONLY_FAKE"}:
        raise RuntimeError("execution_backend must be CONTROLLED_RUNNER or TEST_ONLY_FAKE")
    if not isinstance(allow_fake_execution, bool):
        raise RuntimeError("allow_fake_execution must be boolean")
    if execution_backend == "TEST_ONLY_FAKE":
        if not allow_fake_execution:
            raise RuntimeError("TEST_ONLY_FAKE requires allow_fake_execution=true")
        if not str(config.get("session_id", "")).startswith("TEST_ONLY-"):
            raise RuntimeError("TEST_ONLY_FAKE session_id must begin with TEST_ONLY-")
        if not str(config.get("stage_id", "")).startswith("FAKE_TEST-"):
            raise RuntimeError("TEST_ONLY_FAKE stage_id must begin with FAKE_TEST-")
    elif allow_fake_execution:
        raise RuntimeError("allow_fake_execution is forbidden without TEST_ONLY_FAKE")
    ledger = load_candidate_ledger(repository_path(config["candidate_ledger_path"]))
    if ledger.get("session_id") != config["session_id"]:
        raise RuntimeError("candidate ledger session_id does not match session config")
    if ledger.get("max_candidates") != config.get("max_candidates"):
        raise RuntimeError("candidate ledger max_candidates does not match session config")
    if ledger.get("schema_version") == CANDIDATE_LEDGER_SCHEMA_V2:
        if config.get("max_check_calls") != ledger.get("max_check_calls"):
            raise RuntimeError("check-call ledger max_check_calls does not match session config")
    budget = gate.load_budget(repository_path(config["budget_path"]))
    if budget.get("stage_id") != config.get("stage_id"):
        raise RuntimeError("simulation budget stage_id does not match session config")
    return SessionConfig(
        path=config_path,
        session_id=config["session_id"],
        stage_id=_required_string(config, "stage_id"),
        plan_id_prefix=_required_string(config, "plan_id_prefix"),
        plan_label=_required_string(config, "plan_label"),
        model=model,
        reasoning_effort=effort,
        features_apps=False,
        mechanics_version=config["mechanics_version"],
        facts_source_dir=facts_source_dir,
        session_root=repository_path(config["session_root"]),
        budget_path=repository_path(config["budget_path"]),
        candidate_ledger_path=repository_path(config["candidate_ledger_path"]),
        authorization_config_path=repository_path(config["authorization_config_path"]),
        max_unique_deployed_operators=_required_int(config, "max_unique_deployed_operators", minimum=1),
        max_candidates=_required_int(config, "max_candidates", minimum=1),
        max_check_calls=(
            _required_int(config, "max_check_calls", minimum=1)
            if config.get("max_check_calls") is not None else None
        ),
        simulation_timeout_seconds=_required_int(config, "simulation_timeout_seconds", minimum=1),
        execution_backend=execution_backend,
        allow_fake_execution=allow_fake_execution,
    )


def file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256_path(path), "bytes": path.stat().st_size}


def controlled_code_hashes() -> dict[str, str]:
    return {name: sha256_path(ROOT / name) for name in CONTROLLED_EXECUTION_FILES}


def load_candidate_ledger(path: Path) -> dict[str, Any]:
    ledger = load_json(path)
    if not isinstance(ledger, dict) or ledger.get("schema_version") not in SUPPORTED_CANDIDATE_LEDGER_SCHEMAS:
        raise RuntimeError("unsupported candidate ledger schema")
    if not isinstance(ledger.get("session_id"), str):
        raise RuntimeError("candidate ledger session_id is missing")
    for key in ("max_candidates", "used_candidates"):
        if not isinstance(ledger.get(key), int) or isinstance(ledger.get(key), bool):
            raise RuntimeError(f"candidate ledger {key} must be an integer")
    if not isinstance(ledger.get("attempts"), list):
        raise RuntimeError("candidate ledger attempts must be an array")
    if ledger["used_candidates"] != len(ledger["attempts"]):
        raise RuntimeError("candidate ledger used_candidates and attempts count disagree")
    if ledger["schema_version"] == CANDIDATE_LEDGER_SCHEMA_V2:
        for key in ("max_check_calls", "used_check_calls"):
            if not isinstance(ledger.get(key), int) or isinstance(ledger.get(key), bool) or ledger[key] < 0:
                raise RuntimeError(f"candidate ledger {key} must be a non-negative integer")
        if ledger["max_check_calls"] < 1:
            raise RuntimeError("candidate ledger max_check_calls must be positive")
        if not isinstance(ledger.get("checks"), list):
            raise RuntimeError("candidate ledger checks must be an array")
        if ledger["used_check_calls"] != len(ledger["checks"]):
            raise RuntimeError("candidate ledger used_check_calls and checks count disagree")
    return ledger


@contextmanager
def candidate_ledger_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(path.name + ".service.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def simulation_run_lock(path: Path) -> Iterator[bool]:
    lock_path = path.with_name("simulation.run.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def compact_attempt(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": attempt.get("candidate_id"),
            "candidate_sha256": attempt.get("candidate_sha256"),
            "check_status": attempt.get("check_status"),
            "simulation_status": attempt.get("simulation_status"),
            "simulation_started_counted": attempt.get("simulation_started_counted", False),
        }
        for attempt in ledger.get("attempts", [])
    ]


def session_status(config: SessionConfig) -> dict[str, Any]:
    budget = gate.load_budget(config.budget_path)
    ledger = load_candidate_ledger(config.candidate_ledger_path)
    if ledger.get("session_id") != config.session_id:
        raise RuntimeError("candidate ledger belongs to a different session")
    remaining_simulations = max(
        0, budget["max_stage_simulations"] - budget["prior_stage_simulations"] - budget["started_stage_simulations"]
    )
    remaining_candidates = max(0, ledger["max_candidates"] - ledger["used_candidates"])
    status: dict[str, Any] = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_STATUS_V1",
        "session_id": config.session_id,
        "stage_id": budget.get("stage_id"),
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "features_apps": False,
        "mechanics_version": config.mechanics_version,
        "execution_backend": config.execution_backend,
        "allow_fake_execution": config.allow_fake_execution,
        "max_unique_deployed_operators": config.max_unique_deployed_operators,
        "budget": {**budget, "remaining_stage_simulations": remaining_simulations},
        "candidate_ledger": {
            "schema_version": ledger.get("schema_version"),
            "max_candidates": ledger["max_candidates"],
            "used_candidates": ledger["used_candidates"],
            "remaining_candidates": remaining_candidates,
            "attempts": compact_attempt(ledger),
        },
        "controlled_code_sha256": controlled_code_hashes(),
        "model_identity_proof_boundary": "Service records configured identity only; it cannot prove remote model identity.",
    }
    status["interface_vocab"] = {
        "action_type_names": ACTION_TYPE_NAMES,
        "event_type_names": SUPPORTED_EVENT_TYPE_NAMES,
        "query_event_type_aliases": dict(sorted(experience.EVENT_ALIASES.items())),
        "boundary": "DEPLOY/RETREAT/ACTIVATE_SKILL are plan actions; simulator log event_type is DEPLOY/RETREAT/SKILL_ACTIVATE.",
    }
    if ledger["schema_version"] == CANDIDATE_LEDGER_SCHEMA_V2:
        status["check_call_ledger"] = {
            "max_check_calls": ledger["max_check_calls"],
            "used_check_calls": ledger["used_check_calls"],
            "remaining_check_calls": max(0, ledger["max_check_calls"] - ledger["used_check_calls"]),
        }
    return status


def _plan_operation_id(plan: dict[str, Any]) -> Any:
    plans = plan.get("revised_operational_plans")
    if isinstance(plans, list) and len(plans) == 1 and isinstance(plans[0], dict):
        return plans[0].get("operational_plan_id")
    return None


def _selected_plan(plan: dict[str, Any]) -> dict[str, Any]:
    plans = plan.get("revised_operational_plans")
    if isinstance(plans, list) and len(plans) == 1 and isinstance(plans[0], dict):
        return plans[0]
    return {}


def _validation_layers(
    config: SessionConfig, plan: dict[str, Any], evidence: dict[str, Any], schema: dict[str, Any]
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    layered = validate_plan_payload(plan, evidence, schema)
    layered["previous_plan_id"] = evidence.get("previous_plan_id")
    layered["declared_parent_plan_id"] = experience.extract_declared_parent_plan_id(plan)
    layered["plan_parent_plan_id"] = experience.extract_parent_plan_id(plan)
    lineage = list(layered.get("lineage_errors") or [])
    lineage.extend(validate_parent_hypothesis_reference(plan))
    cold_start_root = evidence.get("cold_start_task_root")
    if isinstance(cold_start_root, dict):
        root_plan_id = cold_start_root.get("root_plan_id")
        root_experience_id = cold_start_root.get("root_experience_id")
        if not isinstance(root_plan_id, str) or not root_plan_id:
            lineage.append("cold_start_task_root.root_plan_id must be a non-empty string")
        if not isinstance(root_experience_id, str) or not root_experience_id:
            lineage.append("cold_start_task_root.root_experience_id must be a non-empty string")
        if cold_start_root.get("schema_version") != "KIMIARK_COLD_START_TASK_ROOT_V1":
            lineage.append("cold_start_task_root.schema_version must be KIMIARK_COLD_START_TASK_ROOT_V1")
        selected_plan_for_lineage = _selected_plan(plan)
        referenced_experience_ids = (
            plan.get("referenced_experience_ids")
            or selected_plan_for_lineage.get("referenced_experience_ids")
            or (plan.get("revision_hypothesis") or {}).get("referenced_experience_ids")
            or (selected_plan_for_lineage.get("revision_hypothesis") or {}).get("referenced_experience_ids")
        )
        if root_experience_id and (
            not isinstance(referenced_experience_ids, list)
            or root_experience_id not in referenced_experience_ids
        ):
            lineage.append("referenced_experience_ids must include cold_start_task_root.root_experience_id")
        declared_parent_plan_id = layered.get("declared_parent_plan_id")
        if root_plan_id and declared_parent_plan_id is None:
            lineage.append("cold_start plan must declare parent_plan_id and revision_hypothesis.parent_plan_id")
        elif root_plan_id and declared_parent_plan_id is not None:
            plan_parent_plan_id = layered.get("plan_parent_plan_id")
            if plan_parent_plan_id != declared_parent_plan_id:
                lineage.append("cold_start plan parent_plan_id and revision_hypothesis parent_plan_id must agree")
            cold_start_ledger = (
                load_candidate_ledger(config.candidate_ledger_path)
                if config.candidate_ledger_path.exists() else None
            )
            if declared_parent_plan_id == root_plan_id:
                if cold_start_ledger and cold_start_ledger.get("used_candidates", 0) > 0:
                    lineage.append("after the first run candidate, cold_start root is no longer a valid parent")
            else:
                completed_parent_plan_ids: set[str] = set()
                for attempt in (cold_start_ledger or {}).get("attempts", []):
                    if attempt.get("simulation_status") == "COMPLETED":
                        candidate_record_path = safe_output_path(
                            config.session_root,
                            "candidates",
                            str(attempt.get("candidate_id", "")),
                            "candidate_record.json",
                        )
                        if candidate_record_path.is_file():
                            candidate_record = load_json(candidate_record_path)
                            if isinstance(candidate_record.get("plan_id"), str):
                                completed_parent_plan_ids.add(candidate_record["plan_id"])
                if declared_parent_plan_id not in completed_parent_plan_ids:
                    lineage.append("cold_start revisions must reference a completed candidate plan_id in this session")
    layered["lineage_errors"] = lineage
    errors: list[str] = []
    errors.extend(f"schema: {item}" for item in layered.get("schema_errors", []))
    errors.extend(f"semantic: {item}" for item in layered.get("semantic_errors", []))
    errors.extend(f"event: {item}" for item in layered.get("event_query_errors", []))
    errors.extend(f"lineage: {item}" for item in lineage)
    operation_id = _plan_operation_id(plan)
    if not isinstance(operation_id, str) or not operation_id.startswith(config.plan_id_prefix):
        errors.append(f"operational_plan_id must identify {config.plan_label}")
    selected_plan = _selected_plan(plan)
    distinct_ids = distinct_deployed_operator_ids(selected_plan)
    if len(distinct_ids) > config.max_unique_deployed_operators:
        errors.append(
            f"distinct selected/deployed operator union has {len(distinct_ids)} IDs; "
            f"hard limit is {config.max_unique_deployed_operators}"
        )
    try:
        capability_observed = validate_normal_low_star_capability_source(evidence)
        capability_errors = [
            f"{key}: {value}" for key, value in capability_observed.items() if not value
        ]
    except Exception as exc:
        capability_errors = [f"{type(exc).__name__}: {exc}"]
    try:
        execution_errors = validate_execution_input(evidence, plan)
    except Exception as exc:
        execution_errors = [f"{type(exc).__name__}: {exc}"]
    if evidence.get("m58_open_roster_policy"):
        roster_errors = validate_open_roster_contract(plan, evidence, config.max_unique_deployed_operators)
    else:
        roster_errors = []
    execution_result = {
        "schema_version": "KIMIARK_CLOSED_LOOP_EXECUTION_INPUT_GATE_V1",
        "status": "BLOCKED_EXECUTION_INPUT" if execution_errors or capability_errors else "PASS",
        "checked_operator_ids": sorted(distinct_ids),
        "errors": [*execution_errors, *capability_errors],
        "roster_errors": roster_errors,
    }
    return layered, errors + roster_errors, execution_result


def _write_static_result(source_dir: Path, static_result: dict[str, Any] | None, error: Exception | None) -> dict[str, Any]:
    if error is not None:
        result = {"schema_version": "KIMIARK_CLOSED_LOOP_STATIC_RESULT_V1", "conflicts": [f"{type(error).__name__}: {error}"]}
    else:
        result = static_result or {"schema_version": "KIMIARK_CLOSED_LOOP_STATIC_RESULT_V1", "conflicts": ["compile_plan returned no result"]}
    atomic_write_json(source_dir / "static_compile_results.json", result)
    return result


def check_plan(config: SessionConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    plan = arguments.get("plan")
    if not isinstance(plan, dict):
        raise RuntimeError("plan must be an object")
    candidate_sha256 = sha256_bytes(canonical_json(plan).encode("utf-8"))
    with candidate_ledger_lock(config.candidate_ledger_path):
        ledger = load_candidate_ledger(config.candidate_ledger_path)
        if ledger.get("session_id") != config.session_id:
            raise RuntimeError("candidate ledger belongs to a different session")
        if ledger["schema_version"] == CANDIDATE_LEDGER_SCHEMA_V2 and ledger["used_check_calls"] >= ledger["max_check_calls"]:
            return {
                "status": "CHECK_BUDGET_EXHAUSTED", "resource": "check_calls",
                "check_call_ledger": {
                    "max_check_calls": ledger["max_check_calls"], "used_check_calls": ledger["used_check_calls"]
                },
                "check_call_counted": False, "candidate_counted": False, "simulation_started": False,
            }
        matching = [item for item in ledger.get("attempts", []) if item.get("candidate_sha256") == candidate_sha256]
        if matching:
            candidate_id = matching[0].get("candidate_id")
            validate_identifier(candidate_id)
            record = load_json(safe_output_path(config.session_root, "candidates", candidate_id, "candidate_record.json"))
            if ledger["schema_version"] == CANDIDATE_LEDGER_SCHEMA_V2:
                if ledger["used_check_calls"] >= ledger["max_check_calls"]:
                    return {"status": "CHECK_BUDGET_EXHAUSTED", "resource": "check_calls", "check_call_counted": False, "candidate_counted": False, "simulation_started": False}
                check_number = ledger["used_check_calls"] + 1
                check_id = f"check-{check_number:03d}"
                check_root = safe_output_path(config.session_root, "checks", check_id)
                if check_root.exists():
                    raise RuntimeError("check directory collision")
                check_root.mkdir(parents=True, exist_ok=True)
                atomic_write_json(check_root / "check_record.json", {
                    "schema_version": "KIMIARK_CLOSED_LOOP_CHECK_RECORD_V1", "check_call_number": check_number,
                    "kind": "IDEMPOTENT_RECHECK", "candidate_sha256": candidate_sha256,
                    "candidate_id": candidate_id, "status": "IDEMPOTENT_RECHECK",
                })
                ledger["used_check_calls"] += 1
                ledger["checks"].append({"check_id": check_id, "kind": "IDEMPOTENT_RECHECK", "candidate_sha256": candidate_sha256, "candidate_id": candidate_id, "status": "IDEMPOTENT_RECHECK"})
                atomic_write_json(config.candidate_ledger_path, ledger)
            return {"status": "IDEMPOTENT_RECHECK", "candidate_id": candidate_id, "candidate_sha256": candidate_sha256, "candidate_record": record}
        if ledger["used_candidates"] >= ledger["max_candidates"]:
            if ledger["schema_version"] == CANDIDATE_LEDGER_SCHEMA_V2:
                if ledger["used_check_calls"] < ledger["max_check_calls"]:
                    check_number = ledger["used_check_calls"] + 1
                    check_id = f"check-{check_number:03d}"
                    check_root = safe_output_path(config.session_root, "checks", check_id)
                    if check_root.exists():
                        raise RuntimeError("check directory collision")
                    check_root.mkdir(parents=True, exist_ok=True)
                    atomic_write_json(check_root / "check_record.json", {
                        "schema_version": "KIMIARK_CLOSED_LOOP_CHECK_RECORD_V1", "check_call_number": check_number,
                        "kind": "CANDIDATE_BUDGET_EXHAUSTED", "candidate_sha256": candidate_sha256,
                        "candidate_id": None, "status": "BUDGET_EXHAUSTED",
                    })
                    ledger["used_check_calls"] += 1
                    ledger["checks"].append({"check_id": check_id, "kind": "CANDIDATE_BUDGET_EXHAUSTED", "candidate_sha256": candidate_sha256, "candidate_id": None, "status": "BUDGET_EXHAUSTED"})
                    atomic_write_json(config.candidate_ledger_path, ledger)
            return {
                "status": "BUDGET_EXHAUSTED", "resource": "candidates",
                "candidate_ledger": {"max_candidates": ledger["max_candidates"], "used_candidates": ledger["used_candidates"]},
                "candidate_counted": False, "simulation_started": False,
            }
        check_id: str | None = None
        check_root: Path | None = None
        if ledger["schema_version"] == CANDIDATE_LEDGER_SCHEMA_V2:
            check_number = ledger["used_check_calls"] + 1
            check_id = f"check-{check_number:03d}"
            check_root = safe_output_path(config.session_root, "checks", check_id)
            if check_root.exists():
                raise RuntimeError("check directory collision")
            check_root.mkdir(parents=True, exist_ok=True)
            work_root = check_root
        else:
            candidate_number = ledger["used_candidates"] + 1
            candidate_id = f"candidate-{candidate_number:03d}"
            candidate_root = safe_output_path(config.session_root, "candidates", candidate_id)
            if candidate_root.exists():
                raise RuntimeError("candidate directory collision")
            candidate_root.mkdir(parents=True, exist_ok=True)
            work_root = candidate_root
        source_dir = safe_output_path(work_root, "source")
        source_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(source_dir / "llm_structured_output.json", plan)
        atomic_write_json(source_dir / "original_request.json", {"check_id": check_id, "candidate_id": None, "plan": plan})
        shutil.copyfile(config.facts_source_dir / "llm_evidence_context.json", source_dir / "llm_evidence_context.json")
        shutil.copyfile(config.facts_source_dir / "revision_output_schema.json", source_dir / "revision_output_schema.json")
        evidence = load_json(source_dir / "llm_evidence_context.json")
        schema = load_json(source_dir / "revision_output_schema.json")
        layered, errors, execution_result = _validation_layers(config, plan, evidence, schema)
        static_error: Exception | None = None
        static_result: dict[str, Any] | None = None
        try:
            static_result = compile_plan(source_dir)
        except Exception as exc:
            static_error = exc
        static_result = _write_static_result(source_dir, static_result, static_error)
        static_conflicts = static_result.get("conflicts") or []
        errors.extend(f"static: {item}" for item in static_conflicts)
        if static_error is not None:
            atomic_write_json(source_dir / "static_error.json", {"message": str(static_error)})
        validation = {
            "schema_version": "KIMIARK_CLOSED_LOOP_PLAN_VALIDATION_V1",
            "status": "PASS" if not errors else "FAIL",
            "errors": errors,
            "layers": layered,
        }
        atomic_write_json(source_dir / "llm_plan_validation.json", validation)
        atomic_write_json(source_dir / "execution_input_gate.json", execution_result)
        if not errors and execution_result["status"] != "PASS":
            errors.append("execution input gate failed")
            validation["status"] = "FAIL"
            validation["errors"] = errors
            atomic_write_json(source_dir / "llm_plan_validation.json", validation)
        check_status = "PASS" if not errors else "FAIL"
        if check_root is not None and check_status == "FAIL":
            atomic_write_json(check_root / "check_record.json", {
                "schema_version": "KIMIARK_CLOSED_LOOP_CHECK_RECORD_V1", "check_call_number": int(check_id.rsplit("-", 1)[1]),
                "kind": "FAILED_CHECK", "candidate_sha256": candidate_sha256,
                "candidate_id": None, "status": "FAIL", "errors": errors,
            })
            ledger["used_check_calls"] += 1
            ledger["checks"].append({
                "check_id": check_id, "kind": "FAILED_CHECK", "candidate_sha256": candidate_sha256,
                "candidate_id": None, "status": "FAIL", "errors": errors,
            })
            atomic_write_json(config.candidate_ledger_path, ledger)
            return {
                "status": "FAIL", "check_id": check_id, "check_call_counted": True,
                "candidate_id": None, "candidate_sha256": candidate_sha256,
                "candidate_counted": False, "simulation_started": False, "errors": errors,
                "layers": {key: value for key, value in layered.items() if isinstance(value, list)},
                "execution_input_gate": execution_result,
                "check_record_path": str((check_root / "check_record.json").relative_to(ROOT)),
            }
        if check_root is not None:
            candidate_number = ledger["used_candidates"] + 1
            candidate_id = f"candidate-{candidate_number:03d}"
            candidate_root = safe_output_path(config.session_root, "candidates", candidate_id)
            if candidate_root.exists():
                raise RuntimeError("candidate directory collision")
            shutil.copytree(check_root, candidate_root)
            atomic_write_json(candidate_root / "source" / "original_request.json", {
                "check_id": check_id, "candidate_id": candidate_id, "plan": plan,
            })
        frozen_inputs = {
            "llm_structured_output.json": file_record(source_dir / "llm_structured_output.json"),
            "llm_evidence_context.json": file_record(source_dir / "llm_evidence_context.json"),
            "revision_output_schema.json": file_record(source_dir / "revision_output_schema.json"),
            "llm_plan_validation.json": file_record(source_dir / "llm_plan_validation.json"),
            "static_compile_results.json": file_record(source_dir / "static_compile_results.json"),
            "execution_input_gate.json": file_record(source_dir / "execution_input_gate.json"),
        }
        candidate_record = {
            "schema_version": CANDIDATE_RECORD_SCHEMA_VERSION,
            "session_id": config.session_id,
            "candidate_id": candidate_id,
            "check_id": check_id,
            "candidate_sha256": candidate_sha256,
            "plan_id": _plan_operation_id(plan),
            "stage_id": config.stage_id,
            "check_status": check_status,
            "unique_deployed_operator_count": len(distinct_deployed_operator_ids(_selected_plan(plan))),
            "max_unique_deployed_operators": config.max_unique_deployed_operators,
            "frozen_inputs_sha256": {name: item["sha256"] for name, item in frozen_inputs.items()},
            "frozen_inputs": frozen_inputs,
            "facts_source_sha256": {
                "llm_evidence_context.json": sha256_path(config.facts_source_dir / "llm_evidence_context.json"),
                "revision_output_schema.json": sha256_path(config.facts_source_dir / "revision_output_schema.json"),
            },
            "controlled_code_sha256": controlled_code_hashes(),
            "simulation_status": "NOT_STARTED",
            "simulation_started_counted": False,
        }
        atomic_write_json(candidate_root / "candidate_record.json", candidate_record)
        attempt = {
            "candidate_id": candidate_id,
            "candidate_sha256": candidate_sha256,
            "check_status": check_status,
            "simulation_status": "NOT_STARTED",
            "simulation_started_counted": False,
        }
        ledger["used_candidates"] += 1
        ledger["attempts"].append(attempt)
        if check_root is not None:
            ledger["used_check_calls"] += 1
            ledger["checks"].append({
                "check_id": check_id, "kind": "PASS", "candidate_sha256": candidate_sha256,
                "candidate_id": candidate_id, "status": "PASS",
            })
        atomic_write_json(config.candidate_ledger_path, ledger)
        return {
            "status": check_status,
            "check_id": check_id,
            "check_call_counted": check_root is not None,
            "candidate_id": candidate_id,
            "candidate_sha256": candidate_sha256,
            "candidate_counted": True,
            "simulation_started": False,
            "errors": errors,
            "layers": {key: value for key, value in layered.items() if isinstance(value, list)},
            "execution_input_gate": execution_result,
            "candidate_record_path": str((candidate_root / "candidate_record.json").relative_to(ROOT)),
        }


def _load_candidate(config: SessionConfig, arguments: dict[str, Any]) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    candidate_id = validate_identifier(arguments.get("candidate_id"))
    requested_sha = arguments.get("candidate_sha256")
    if not isinstance(requested_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", requested_sha):
        raise RuntimeError("invalid candidate_sha256")
    with candidate_ledger_lock(config.candidate_ledger_path):
        ledger = load_candidate_ledger(config.candidate_ledger_path)
        if ledger.get("session_id") != config.session_id:
            raise RuntimeError("candidate ledger belongs to a different session")
        attempts = [item for item in ledger.get("attempts", []) if item.get("candidate_id") == candidate_id]
        if len(attempts) != 1:
            raise RuntimeError("candidate is not registered by this service")
        if attempts[0].get("candidate_sha256") != requested_sha:
            raise RuntimeError("candidate ledger hash mismatch")
    candidate_root = safe_output_path(config.session_root, "candidates", candidate_id)
    record_path = candidate_root / "candidate_record.json"
    if not record_path.is_file():
        raise RuntimeError("candidate has not been checked by this service")
    record = load_json(record_path)
    if record.get("session_id") != config.session_id:
        raise RuntimeError("candidate belongs to a different session")
    if record.get("candidate_sha256") != requested_sha:
        raise RuntimeError("candidate hash mismatch")
    if record.get("check_status") != "PASS":
        raise RuntimeError("only PASS candidates may run simulation")
    return candidate_root, record, record


def _verify_frozen_candidate(config: SessionConfig, candidate_root: Path, record: dict[str, Any]) -> None:
    source_dir = candidate_root / "source"
    expected = record.get("frozen_inputs_sha256") or {}
    for name, expected_sha in expected.items():
        path = source_dir / name
        if not path.is_file() or sha256_path(path) != expected_sha:
            raise RuntimeError("frozen candidate input changed after check_plan")
    current_facts = {
        "llm_evidence_context.json": sha256_path(config.facts_source_dir / "llm_evidence_context.json"),
        "revision_output_schema.json": sha256_path(config.facts_source_dir / "revision_output_schema.json"),
    }
    if current_facts != record.get("facts_source_sha256"):
        raise RuntimeError("configured facts source changed after check_plan")
    if controlled_code_hashes() != record.get("controlled_code_sha256"):
        raise RuntimeError("controlled execution code changed after check_plan")
    if config.mechanics_version != ACTIVE_MECHANICS_VERSION:
        raise RuntimeError("active mechanics changed after check_plan")


def _simulation_output_state(output_dir: Path) -> dict[str, Any]:
    reservation_path = output_dir.with_name(output_dir.name + ".simulation_reservation.json")
    attempt_path = output_dir / "simulation_attempt.json"
    manifest_path = output_dir / "manifest.json"
    summary_path = output_dir / "diagnostic_summary.json"
    if reservation_path.is_file():
        reservation = gate.load_json(reservation_path)
        complete = manifest_path.is_file() and summary_path.is_file() and attempt_path.is_file() and (
            gate.load_json(attempt_path).get("status") == "COMPLETED"
            if attempt_path.is_file() else False
        )
        status = reservation.get("status")
        if status == "COMPLETED" and complete:
            return {"status": "COMPLETED", "reservation": reservation}
        if status == "FAILED":
            outcome = gate._failure_outcome(output_dir)
            return {"status": outcome, "reservation": reservation}
        return {"status": "STARTED_UNKNOWN" if status == "RESERVED" else f"RESERVATION_{status}", "reservation": reservation}
    if output_dir.exists() and any(output_dir.iterdir()):
        return {"status": "UNKNOWN_NONEMPTY_OUTPUT"}
    return {"status": "NOT_STARTED"}


def _compact_simulation_summary(
    config: SessionConfig, summary: dict[str, Any], output_dir: Path, output: dict[str, Any]
) -> dict[str, Any]:
    result = summary.get("result") if isinstance(summary.get("result"), dict) else {}
    result_sha256 = {
        name: sha256_path(output_dir / name) for name in (
            "diagnostic_events.json", "diagnostic_summary.json", "manifest.json"
        ) if (output_dir / name).is_file()
    }
    return {
        "event_log_reference": str((output_dir / "diagnostic_events.json").relative_to(ROOT)),
        "summary_reference": str((output_dir / "diagnostic_summary.json").relative_to(ROOT)),
        "manifest_reference": str((output_dir / "manifest.json").relative_to(ROOT)),
        "result_sha256": result_sha256,
        "budget": gate.load_budget(config.budget_path),
        "result": {
            "win": result.get("win"),
            "classification": summary.get("classification"),
            "enemies_killed": result.get("enemies_killed"),
            "enemies_leaked": result.get("enemies_leaked"),
            "operator_deaths": result.get("operator_deaths"),
            "remaining_life": result.get("remaining_life"),
            "final_dp": result.get("final_dp"),
            "deployment_errors": result.get("deployment_errors"),
            "protected_target_deaths": summary.get("protected_target_deaths"),
            "protected_target_reached_events": summary.get("protected_target_reached_events"),
        },
        "status_boundary": "Static compliance and observed events are not proof of a tactical hypothesis.",
        **output,
    }


def _executor(
    config: SessionConfig, source_dir: Path, output_dir: Path, plan_id: str
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable, str(ROOT / "scripts/run_gpt_tactical_stage_session_v1.py"), "simulate",
        "--stage-id", config.stage_id,
        "--facts-dir", str(source_dir.relative_to(ROOT)),
        "--output-dir", str(source_dir.relative_to(ROOT)),
        "--diagnostic-output-dir", str(output_dir.relative_to(ROOT)),
        "--plan-id", plan_id,
        "--plan-label", config.plan_label,
        "--plan-id-prefix", config.plan_id_prefix,
        "--max-unique-deployed-operators", str(config.max_unique_deployed_operators),
        "--authorization-config", str(config.authorization_config_path.relative_to(ROOT)),
        "--simulation-budget-path", str(config.budget_path.relative_to(ROOT)),
    ]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=config.simulation_timeout_seconds)


def _fake_test_executor(
    config: SessionConfig, source_dir: Path, output_dir: Path, plan_id: str
) -> subprocess.CompletedProcess[str]:
    if config.execution_backend != "TEST_ONLY_FAKE" or not config.allow_fake_execution:
        raise RuntimeError("fake execution backend is not authorized")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise RuntimeError("fake diagnostic output directory is not empty")
    budget = gate.load_budget(config.budget_path)
    budget["started_stage_simulations"] += 1
    atomic_write_json(config.budget_path, budget)
    candidate_number = int(source_dir.parent.name.split("-")[-1])
    fake_win = candidate_number == 2
    result = {
        "FAKE_TEST": True,
        "win": fake_win,
        "enemies_killed": 2 if fake_win else 1,
        "enemies_leaked": 0 if fake_win else 1,
        "operator_deaths": [],
        "remaining_life": 3 if fake_win else 2,
        "final_dp": 10,
        "deployment_errors": [],
    }
    events = [
        {
            "frame": 100, "time": 100 / 30, "event_type": "PROJECTILE_BORN",
            "source_id": "fake_artillery", "target_id": "fake_tile",
            "details": {"FAKE_TEST": True, "legal": True},
        },
        {
            "frame": 200, "time": 200 / 30, "event_type": "DEPLOY",
            "source_id": "fake_operator", "target_id": "fake_tile",
            "details": {"FAKE_TEST": True, "legal": False},
        },
        {
            "frame": 300, "time": 300 / 30, "event_type": "OPERATOR_DEATH",
            "source_id": "fake_operator", "target_id": None,
            "details": {"FAKE_TEST": True, "legal": True},
        },
    ]
    summary = {
        "FAKE_TEST": True,
        "result": result,
        "classification": "FAKE_TEST_DIAGNOSTIC_WIN" if fake_win else "FAKE_TEST_DIAGNOSTIC_LOSS",
        "protected_target_deaths": [],
        "protected_target_reached_events": [],
    }
    atomic_write_json(output_dir / "plan_snapshot.json", {"FAKE_TEST": True, "plan_id": plan_id})
    atomic_write_json(output_dir / "action_snapshot.json", {"FAKE_TEST": True})
    atomic_write_json(output_dir / "simulation_attempt.json", {"status": "COMPLETED", "result_saved": True, "FAKE_TEST": True})
    atomic_write_json(output_dir / "diagnostic_events.json", {"FAKE_TEST": True, "events": events})
    atomic_write_json(output_dir / "diagnostic_summary.json", summary)
    atomic_write_json(output_dir / "manifest.json", {"FAKE_TEST": True, "stage_id": config.stage_id, "plan_id": plan_id})
    atomic_write_json(output_dir.with_name(output_dir.name + ".simulation_reservation.json"), {
        "FAKE_TEST": True, "status": "COMPLETED", "result_saved": True,
        "reservation_index": budget["started_stage_simulations"],
    })
    return type("CompletedProcess", (), {"returncode": 0, "stdout": "FAKE_TEST", "stderr": "FAKE_TEST"})()


def run_simulation(
    config: SessionConfig, arguments: dict[str, Any], *, executor: Callable[..., subprocess.CompletedProcess[str]] | None = None
) -> dict[str, Any]:
    candidate_root, record, _ = _load_candidate(config, arguments)
    candidate_id = record["candidate_id"]
    output_dir = safe_output_path(candidate_root, "simulation")
    plan_id = record.get("plan_id")
    if not isinstance(plan_id, str) or not plan_id:
        raise RuntimeError("candidate has no operational_plan_id")
    with simulation_run_lock(candidate_root) as acquired:
        if not acquired:
            state = _simulation_output_state(output_dir)
            return {
                "status": "IN_PROGRESS", "candidate_id": candidate_id, "state": state,
                "simulation_started_counted": state.get("status") != "NOT_STARTED",
            }
        state = _simulation_output_state(output_dir)
        if state["status"] == "COMPLETED":
            summary = gate.load_json(output_dir / "diagnostic_summary.json")
            return _compact_simulation_summary(config, summary, output_dir, {"status": "IDEMPOTENT_COMPLETED", "simulation_started_counted": True, "state": state})
        if state["status"] not in {"NOT_STARTED"}:
            simulation_started_counted = (
                "UNKNOWN" if state["status"] in {"STARTED_UNKNOWN", "UNKNOWN_NONEMPTY_OUTPUT"} or state["status"].startswith("RESERVATION_") else True
            )
            return {
                "status": state["status"], "candidate_id": candidate_id, "state": state,
                "simulation_started_counted": simulation_started_counted, "retry": False,
            }
        _verify_frozen_candidate(config, candidate_root, record)
        with candidate_ledger_lock(config.candidate_ledger_path):
            ledger = load_candidate_ledger(config.candidate_ledger_path)
            attempts = {item.get("candidate_id"): item for item in ledger.get("attempts", [])}
            attempt = attempts.get(candidate_id)
            if attempt is None:
                raise RuntimeError("candidate attempt missing from ledger")
        budget = gate.load_budget(config.budget_path)
        if budget.get("stage_id") != config.stage_id:
            raise RuntimeError("simulation budget stage mismatch")
        remaining = budget["max_stage_simulations"] - budget["prior_stage_simulations"] - budget["started_stage_simulations"]
        if remaining <= 0:
            return {"status": "BUDGET_EXHAUSTED", "resource": "simulations", "remaining_stage_simulations": 0, "simulation_started_counted": False}
        budget_started_before = budget["started_stage_simulations"]
        request_path = safe_output_path(candidate_root, "simulation_request.json")
        atomic_write_json(request_path, {
            "schema_version": SIMULATION_REQUEST_SCHEMA_VERSION,
            "session_id": config.session_id,
            "candidate_id": candidate_id,
            "candidate_sha256": record["candidate_sha256"],
            "output_dir": str(output_dir.relative_to(ROOT)),
            "mechanics_version": config.mechanics_version,
            "automatic_retry": False,
        })
        try:
            gate.prepare_evaluation(
                source_dir=candidate_root / "source", diagnostic_output_dir=output_dir,
                budget_path=config.budget_path, stage_id=config.stage_id, expected_plan_id=plan_id,
            )
        except Exception as exc:
            request = gate.load_json(request_path)
            request.update({"status": "PREFLIGHT_FAILED", "error": f"{type(exc).__name__}: {exc}", "simulation_started_counted": False})
            atomic_write_json(request_path, request)
            attempt["simulation_status"] = "PREFLIGHT_FAILED"
            attempts[candidate_id] = attempt
            ledger["attempts"] = list(attempts.values())
            atomic_write_json(config.candidate_ledger_path, ledger)
            return {"status": "PREFLIGHT_FAILED", "error": f"{type(exc).__name__}: {exc}", "simulation_started_counted": False}
        runner = executor or (_fake_test_executor if config.execution_backend == "TEST_ONLY_FAKE" else _executor)
        try:
            completed = runner(config, candidate_root / "source", output_dir, plan_id)
        except Exception as exc:
            state = _simulation_output_state(output_dir)
            simulation_started_counted = state.get("status") != "NOT_STARTED"
            request = gate.load_json(request_path)
            request.update({"status": "EXECUTION_EXCEPTION", "error": f"{type(exc).__name__}: {exc}", "output_state": state, "simulation_started_counted": simulation_started_counted})
            atomic_write_json(request_path, request)
            attempt["simulation_status"] = state["status"]
            attempt["simulation_started_counted"] = simulation_started_counted
            attempts[candidate_id] = attempt
            ledger["attempts"] = list(attempts.values())
            atomic_write_json(config.candidate_ledger_path, ledger)
            return {
                "status": "EXECUTION_EXCEPTION", "error": f"{type(exc).__name__}: {exc}",
                "output_state": state, "simulation_started_counted": simulation_started_counted, "retry": False,
                "reconciliation_required": state.get("status") == "STARTED_UNKNOWN",
            }
        state = _simulation_output_state(output_dir)
        stdout_tail = completed.stdout[-4000:]
        stderr_tail = completed.stderr[-4000:]
        budget_after = gate.load_budget(config.budget_path)
        request = gate.load_json(request_path)
        if completed.returncode == 0 and state["status"] == "COMPLETED":
            request.update({"status": "COMPLETED", "exit_code": 0, "simulation_started_counted": True})
            atomic_write_json(request_path, request)
            attempt.update({"simulation_status": "COMPLETED", "simulation_started_counted": True})
            attempts[candidate_id] = attempt
            ledger["attempts"] = list(attempts.values())
            atomic_write_json(config.candidate_ledger_path, ledger)
            summary = gate.load_json(output_dir / "diagnostic_summary.json")
            return _compact_simulation_summary(config, summary, output_dir, {"status": "COMPLETED", "exit_code": 0, "simulation_started_counted": True})
        no_start = state["status"] == "NOT_STARTED" and budget_after["started_stage_simulations"] == budget_started_before
        simulation_started_counted = not no_start
        status = "PREFLIGHT_FAILED_NO_START" if no_start else ("FAILED_AFTER_START" if completed.returncode != 0 else "FAILED_INCOMPLETE_RESULT")
        request.update({
            "status": status, "exit_code": completed.returncode,
            "stdout_tail": stdout_tail, "stderr_tail": stderr_tail,
            "output_state": state, "simulation_started_counted": simulation_started_counted, "retry": False,
        })
        atomic_write_json(request_path, request)
        attempt["simulation_status"] = state["status"] if state["status"] != "NOT_STARTED" else status
        attempt["simulation_started_counted"] = simulation_started_counted
        attempts[candidate_id] = attempt
        ledger["attempts"] = list(attempts.values())
        atomic_write_json(config.candidate_ledger_path, ledger)
        return {
            "status": status, "exit_code": completed.returncode, "output_state": state,
            "stdout_tail": stdout_tail, "stderr_tail": stderr_tail,
            "simulation_started_counted": simulation_started_counted, "retry": False,
        }


def _details_value(event: dict[str, Any], key: str) -> Any:
    parts = key.split(".")
    if key.startswith("details."):
        value: Any = event
    else:
        value = event.get("details")
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            return object()
        value = value[part]
    return value


def _aggregate_value(event: dict[str, Any], field: str) -> Any:
    if field in {"frame"}:
        return event.get(field)
    return _details_value(event, field)


def query_events(config: SessionConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    candidate_root, record, _ = _load_candidate(config, arguments)
    output_dir = candidate_root / "simulation"
    events_path = output_dir / "diagnostic_events.json"
    manifest_path = output_dir / "manifest.json"
    attempt_path = output_dir / "simulation_attempt.json"
    if not events_path.is_file():
        return {"status": "NO_REGISTERED_EVENT_LOG", "candidate_id": record.get("candidate_id"), "observation_coverage": "UNKNOWN"}
    payload = gate.load_json(events_path)
    events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(events, list):
        return {"status": "INVALID_EVENT_LOG", "observation_coverage": "UNKNOWN"}
    observation_complete = (
        manifest_path.is_file() and attempt_path.is_file()
        and gate.load_json(attempt_path).get("status") == "COMPLETED"
        and gate.load_json(attempt_path).get("result_saved") is True
    )
    event_type = arguments.get("event_type")
    if not isinstance(event_type, str) or not event_type:
        raise RuntimeError("event_type must be a non-empty string")
    if event_type not in QUERY_EVENT_TYPE_NAMES:
        return {
            "status": "INVALID_EVENT_TYPE", "error_path": "/event_type",
            "received_value": event_type, "legal_event_type": None,
            "supported_event_types": SUPPORTED_EVENT_TYPE_NAMES,
            "supported_action_aliases": dict(sorted(experience.EVENT_ALIASES.items())),
            "repair_hint": "Use a supported event_type; ACTIVATE_SKILL aliases SKILL_ACTIVATE.",
            "observation_coverage": "UNKNOWN",
        }
    normalized_event_type = experience.EVENT_ALIASES.get(event_type, event_type)
    filters: list[dict[str, Any]] = []
    for key in ("source_id", "target_id"):
        if key in arguments:
            value = arguments[key]
            if value is not None and not isinstance(value, str):
                raise RuntimeError(f"{key} must be a string or null")
            filters.append({"key": key, "value": value})
    earliest = arguments.get("earliest_frame")
    latest = arguments.get("latest_frame")
    for name, value in (("earliest_frame", earliest), ("latest_frame", latest)):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise RuntimeError(f"{name} must be an integer")
    if earliest is not None and latest is not None and earliest > latest:
        raise RuntimeError("earliest_frame exceeds latest_frame")
    detail_conditions = arguments.get("details_equal") or []
    if not isinstance(detail_conditions, list) or len(detail_conditions) > 4:
        raise RuntimeError("details_equal must contain at most four conditions")
    for condition in detail_conditions:
        if not isinstance(condition, dict) or not isinstance(condition.get("key"), str) or not DETAIL_KEY_RE.fullmatch(condition["key"]):
            raise RuntimeError("details_equal key must be a constrained dotted key")
        if not isinstance(condition.get("value"), (str, int, float, bool, type(None))):
            raise RuntimeError("details_equal value must be a primitive")
    matches: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict) or event.get("event_type") != normalized_event_type:
            continue
        if any(event.get(item["key"]) != item["value"] for item in filters):
            continue
        frame = event.get("frame")
        if not isinstance(frame, int) or isinstance(frame, bool):
            continue
        if earliest is not None and frame < earliest:
            continue
        if latest is not None and frame > latest:
            continue
        if any(_details_value(event, item["key"]) != item["value"] for item in detail_conditions):
            continue
        matches.append(event)
    limit = arguments.get("limit", 100)
    offset = arguments.get("offset", 0)
    for name, value in (("limit", limit), ("offset", offset)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeError(f"{name} must be a non-negative integer")
    if limit > MAX_EVENT_PAGE_SIZE:
        raise RuntimeError(f"limit exceeds {MAX_EVENT_PAGE_SIZE}")
    aggregate_result: dict[str, Any] | None = None
    aggregate = arguments.get("aggregate")
    if aggregate is not None:
        field = aggregate.get("field")
        if not isinstance(field, str) or not DETAIL_KEY_RE.fullmatch(field):
            raise RuntimeError("aggregate field must be a constrained key")
        values = []
        for event in matches:
            value = _aggregate_value(event, field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(value)
        aggregate_result = {
            "field": field,
            "matched_event_count": len(matches),
            "numeric_value_count": len(values),
            "unique_source_id_count": len({event.get("source_id") for event in matches}),
            "unique_target_id_count": len({event.get("target_id") for event in matches}),
            "sum": sum(values) if values else None,
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "average": sum(values) / len(values) if values else None,
            "scope": "matched events in this registered log only",
        }
    page = matches[offset:offset + limit]
    byte_budget_truncated = False
    while page and len(canonical_json(page).encode("utf-8")) > MAX_EVENT_RESPONSE_BYTES:
        page.pop()
        byte_budget_truncated = True
    return {
        "schema_version": EVENT_QUERY_SCHEMA_VERSION,
        "candidate_id": record.get("candidate_id"),
        "declared_event_type": event_type,
        "event_type": normalized_event_type,
        "event_type_alias_applied": normalized_event_type != event_type,
        "events": page,
        "pagination": {
            "offset": offset, "limit": limit, "total_matches": len(matches),
            "returned_matches": len(page),
            "next_offset": offset + limit if offset + limit < len(matches) else None,
            "truncated": offset + limit < len(matches),
            "byte_budget_truncated": byte_budget_truncated,
        },
        "response_event_bytes": len(canonical_json(page).encode("utf-8")),
        "aggregate": aggregate_result,
        "observation_coverage": "COMPLETE" if observation_complete else "UNKNOWN",
        "zero_match_status": "EVENT_NOT_OBSERVED" if not matches and observation_complete else ("UNKNOWN" if not matches else None),
        "boundary": "Raw matches may include legal:false actions; they never verify a tactical hypothesis by themselves.",
    }


HANDLERS: dict[str, Callable[[SessionConfig, dict[str, Any]], dict[str, Any]]] = {
    "get_session_status": lambda config, arguments: session_status(config),
    "check_plan": check_plan,
    "run_simulation": lambda config, arguments: run_simulation(config, arguments),
    "query_events": query_events,
}


def tool_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, sort_keys=True)}],
        "structuredContent": result,
    }


def handle_message(config: SessionConfig, message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        requested_version = (message.get("params") or {}).get("protocolVersion")
        response_version = requested_version if isinstance(requested_version, str) and requested_version else PROTOCOL_VERSION
        return {
            "jsonrpc": "2.0", "id": request_id,
            "result": {
                "protocolVersion": response_version, "serverInfo": SERVICE_INFO,
                "capabilities": {"tools": {"listChanged": False}},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "notifications/cancelled":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        try:
            if handler is None:
                result = {"error": "UNKNOWN_TOOL", "tool": name}
                is_error = True
            else:
                result = handler(config, arguments)
                is_error = False
        except Exception as exc:
            result = {"error": type(exc).__name__, "message": str(exc), "automatic_retry": False}
            is_error = True
        response = {"jsonrpc": "2.0", "id": request_id, "result": tool_result(result)}
        response["result"]["isError"] = is_error
        return response
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> None:
    parser = argparse.ArgumentParser(description="KimiArk fixed-session tactical closed-loop stdio tools")
    parser.add_argument("config", help="repository-relative session configuration JSON path")
    arguments = parser.parse_args()
    config = load_session_config(Path(arguments.config))
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
        else:
            response = handle_message(config, message)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
