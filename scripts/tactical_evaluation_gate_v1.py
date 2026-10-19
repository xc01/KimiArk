from __future__ import annotations

import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import tactical_experience_v1 as experience


GATE_SCHEMA_VERSION = "KIMIARK_FROZEN_PLAN_EVALUATION_GATE_V1"
BUDGET_SCHEMA_VERSION = "KIMIARK_STAGE_SIMULATION_BUDGET_V1"
ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_budget(path: Path) -> dict[str, Any]:
    budget = load_json(path)
    if budget.get("schema_version") != BUDGET_SCHEMA_VERSION:
        raise RuntimeError(f"unsupported simulation budget schema: {budget.get('schema_version')!r}")
    required = {"stage_id", "max_stage_simulations", "started_stage_simulations", "prior_stage_simulations"}
    missing = sorted(required - set(budget))
    if missing:
        raise RuntimeError(f"simulation budget missing fields: {missing}")
    if not all(isinstance(budget[key], int) and not isinstance(budget[key], bool) for key in required if key != "stage_id"):
        raise RuntimeError("simulation budget counters must be integers")
    return budget


def within_repository(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f"path outside KimiArk repository is forbidden: {path}") from exc
    return resolved


def _expected_protected_target_count(evidence_path: Path) -> int | None:
    try:
        evidence = load_json(evidence_path)
    except (OSError, json.JSONDecodeError):
        return None
    events = ((evidence.get("model_spawn_timeline") or {}).get("events") or [])
    counts = [
        int(event.get("count", 1)) for event in events
        if isinstance(event, dict) and isinstance(event.get("enemy_id"), str)
        and event["enemy_id"].startswith("enemy_3001_upeopl")
    ]
    return sum(counts) if counts else None


def prepare_evaluation(
    *, source_dir: Path, diagnostic_output_dir: Path, budget_path: Path,
    stage_id: str | None = None, expected_plan_id: str | None = None,
) -> dict[str, Any]:
    source_dir, diagnostic_output_dir, budget_path = map(within_repository, (source_dir, diagnostic_output_dir, budget_path))
    plan_validation_path = source_dir / "llm_plan_validation.json"
    static_path = source_dir / "static_compile_results.json"
    structured_path = source_dir / "llm_structured_output.json"
    required = [plan_validation_path, static_path, structured_path]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"frozen evaluation inputs missing: {missing}")
    if load_json(plan_validation_path).get("status") != "PASS":
        raise RuntimeError("frozen plan must pass schema/contract validation before evaluation")
    static = load_json(static_path)
    if static.get("conflicts"):
        raise RuntimeError("static conflicts block frozen-plan evaluation")
    structured = load_json(structured_path)
    actual_plan_id = experience.extract_operational_plan_id(structured)
    if expected_plan_id is not None and actual_plan_id != expected_plan_id:
        raise RuntimeError(
            f"frozen plan identity mismatch: expected {expected_plan_id!r}, observed {actual_plan_id!r}"
        )
    budget = load_budget(budget_path)
    if stage_id is not None and budget["stage_id"] != stage_id:
        raise RuntimeError(f"budget stage mismatch: budget={budget['stage_id']!r}, requested={stage_id!r}")
    if budget["started_stage_simulations"] > budget["max_stage_simulations"]:
        raise RuntimeError("simulation budget reservation counter exceeds authorization")
    remaining = budget["max_stage_simulations"] - budget["prior_stage_simulations"] - budget["started_stage_simulations"]
    if diagnostic_output_dir.exists():
        if not diagnostic_output_dir.is_dir():
            raise RuntimeError("diagnostic output path must be a directory")
        if any(diagnostic_output_dir.iterdir()):
            raise RuntimeError("non-empty diagnostic output directory already exists; choose a new attempt directory")
    manifest = diagnostic_output_dir / "manifest.json"
    if manifest.exists():
        raise RuntimeError("immutable diagnostic output already exists; choose a new attempt directory")
    evidence_path = source_dir / "llm_evidence_context.json"
    expected_protected_target_count = _expected_protected_target_count(evidence_path)
    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "status": "AUTHORIZED" if remaining > 0 else "BUDGET_EXHAUSTED",
        "remaining_stage_simulations": max(0, remaining),
        "source_dir": str(source_dir.relative_to(ROOT)),
        "diagnostic_output_dir": str(diagnostic_output_dir.relative_to(ROOT)),
        "immutable_rule": "existing diagnostic manifests may not be overwritten",
        "inputs": {
            "plan_validation_sha256": sha256(plan_validation_path),
            "static_compile_results_sha256": sha256(static_path),
            "structured_output_sha256": sha256(structured_path),
            "evidence_context_sha256": sha256(evidence_path),
        },
        "budget_sha256": sha256(budget_path),
        "expected_plan_id": actual_plan_id,
        "stage_id": budget["stage_id"],
        "expected_protected_target_count": expected_protected_target_count,
    }


@contextmanager
def exclusive_evaluation_lock(*paths: Path) -> Iterator[None]:
    paths = tuple(within_repository(path) for path in paths)
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    lock_path = paths[0].with_suffix(".evaluation.lock")
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another frozen-plan evaluation holds the lock") from exc
        yield


def _write_reservation(path: Path, record: dict[str, Any], status: str) -> None:
    record = {**record, "status": status}
    text = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


@contextmanager
def consume_evaluation(
    *, source_dir: Path, diagnostic_output_dir: Path, budget_path: Path,
    stage_id: str | None = None, expected_plan_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    source_dir, diagnostic_output_dir, budget_path = map(within_repository, (source_dir, diagnostic_output_dir, budget_path))
    with exclusive_evaluation_lock(budget_path, source_dir, diagnostic_output_dir):
        gate_result = prepare_evaluation(
            source_dir=source_dir, diagnostic_output_dir=diagnostic_output_dir,
            budget_path=budget_path, stage_id=stage_id, expected_plan_id=expected_plan_id,
        )
        if gate_result["status"] != "AUTHORIZED":
            yield gate_result
            return
        budget = load_budget(budget_path)
        budget["started_stage_simulations"] += 1
        temporary = budget_path.with_name(budget_path.name + ".tmp")
        temporary.write_text(json.dumps(budget, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, budget_path)
        diagnostic_output_dir.mkdir(parents=True, exist_ok=True)
        reservation_path = diagnostic_output_dir.with_name(
            diagnostic_output_dir.name + ".simulation_reservation.json"
        )
        reservation = {
            "schema_version": "KIMIARK_STAGE_SIMULATION_RESERVATION_V1",
            "stage_id": budget["stage_id"],
            "source_dir": str(source_dir.relative_to(ROOT)),
            "diagnostic_output_dir": str(diagnostic_output_dir.relative_to(ROOT)),
            "budget_sha256_before_reserve": gate_result["budget_sha256"],
            "reservation_index": budget["started_stage_simulations"],
        }
        _write_reservation(reservation_path, reservation, "RESERVED")
        try:
            yield gate_result
        except BaseException as exc:
            _write_reservation(reservation_path, reservation, "FAILED", )
            reservation_path.with_suffix(".error.txt").write_text(
                f"{type(exc).__name__}: {exc}\n", encoding="utf-8"
            )
            raise
        else:
            _write_reservation(reservation_path, reservation, "COMPLETED")


def mark_reservation_completed(diagnostic_output_dir: Path) -> None:
    reservation_path = within_repository(diagnostic_output_dir) / "simulation_reservation.json"
    if reservation_path.is_file():
        record = load_json(reservation_path)
        if record.get("status") == "RESERVED":
            _write_reservation(reservation_path, record, "COMPLETED")
