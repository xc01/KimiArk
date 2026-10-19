from __future__ import annotations

import fcntl
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


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


def prepare_evaluation(
    *, source_dir: Path, diagnostic_output_dir: Path, budget_path: Path
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
    budget = load_budget(budget_path)
    remaining = budget["max_stage_simulations"] - budget["prior_stage_simulations"] - budget["started_stage_simulations"]
    manifest = diagnostic_output_dir / "run_manifest.json"
    if manifest.exists():
        raise RuntimeError("immutable diagnostic output already exists; choose a new attempt directory")
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
        },
    }


@contextmanager
def exclusive_evaluation_lock(source_dir: Path) -> Iterator[None]:
    source_dir = within_repository(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    lock_path = source_dir / "evaluation.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another frozen-plan evaluation holds the lock") from exc
        yield
