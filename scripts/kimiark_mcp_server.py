from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tactical_evaluation_gate_v1 as gate
import tactical_experience_v1 as experience


SERVER_INFO = {"name": "kimiark-tactical-loop", "version": "0.1.0"}
PROTOCOL_VERSION = "2025-06-18"
MECHANISM_FACTS = {
    "mechanics_version": "m23-behavioral-mechanics-v1",
    "game_data_sha256": "0ef7f952dfd018392200157a5c79a6511ba69122",
    "win_rule": "simulator WIN requires remaining_life > 0, zero leaks, exhausted spawns and no active enemies",
    "project_perfect_target": {
        "zero_leaks": True,
        "protected_targets_zero_deaths": True,
        "protected_targets_all_reached": True,
        "operator_deaths_hard_constraint": False,
    },
    "status_boundary": "This is current-model support, not faithful-client or real-game proof.",
    "unknowns": ["exact client target priority", "exact client continuous-frame timing", "unverified stage-specific mechanics"],
}


TOOLS = [
    {
        "name": "get_mechanism_facts",
        "description": "Return current simulator mechanism boundary and objective scopes. Does not infer client behavior.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "query_applicable_experience",
        "description": "Retrieve up to three non-invalidated, condition-filtered tactical experiences.",
        "inputSchema": {
            "type": "object",
            "required": ["stage_id", "mechanics_version"],
            "properties": {
                "experience_store": {"type": "string"},
                "stage_id": {"type": "string"},
                "mechanics_version": {"type": "string"},
                "failure_category": {"type": "string"},
                "responsibility_tags": {"type": "array", "items": {"type": "string"}},
                "operator_ids": {"type": "array", "items": {"type": "string"}},
                "source_plan_id": {"type": ["string", "null"]},
                "game_data_sha256": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "check_plan_contract",
        "description": "Validate a frozen source directory with existing schema/contract and static checks.",
        "inputSchema": {
            "type": "object",
            "required": ["source_dir"],
            "properties": {"source_dir": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "prepare_frozen_plan_evaluation",
        "description": "Check immutable simulation gate, exclusive lock and persistent stage budget without running a battle.",
        "inputSchema": {
            "type": "object",
            "required": ["source_dir", "diagnostic_output_dir", "budget_path", "stage_id", "plan_id"],
            "properties": {
                "source_dir": {"type": "string"},
                "diagnostic_output_dir": {"type": "string"},
                "budget_path": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "evaluate_frozen_plan",
        "description": "Run one deterministic fixed-action simulation only after immutable, exclusive, budgeted gate approval.",
        "inputSchema": {
            "type": "object",
            "required": ["source_dir", "diagnostic_output_dir", "budget_path", "stage_id", "plan_id", "plan_label", "plan_id_prefix"],
            "properties": {
                "source_dir": {"type": "string"},
                "diagnostic_output_dir": {"type": "string"},
                "budget_path": {"type": "string"},
                "stage_id": {"type": "string"},
                "plan_id": {"type": "string"},
                "plan_label": {"type": "string"},
                "plan_id_prefix": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_status_and_feedback",
        "description": "Read a saved final status, simulation gate and compact causal feedback without replaying battle.",
        "inputSchema": {
            "type": "object",
            "required": ["source_dir"],
            "properties": {"source_dir": {"type": "string"}, "feedback_path": {"type": "string"}},
            "additionalProperties": False,
        },
    },
]


def repo_path(value: str) -> Path:
    return gate.within_repository(ROOT / value)


def tool_result(result: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, sort_keys=True)}], "structuredContent": result}


def get_mechanism_facts(arguments: dict[str, Any]) -> dict[str, Any]:
    return MECHANISM_FACTS


def query_applicable_experience(arguments: dict[str, Any]) -> dict[str, Any]:
    records = experience.load_experience_records(repo_path(arguments["experience_store"]))
    retrieved = experience.retrieve_experiences(
        records,
        stage_id=arguments["stage_id"],
        mechanics_version=arguments["mechanics_version"],
        failure_category=arguments.get("failure_category"),
        responsibility_tags=set(arguments.get("responsibility_tags") or []),
        operator_ids=set(arguments.get("operator_ids") or []),
        source_plan_id=arguments.get("source_plan_id"),
        game_data_sha256=arguments.get("game_data_sha256"),
        limit=3,
    )
    return {"schema_version": experience.EXPERIENCE_SCHEMA_VERSION, "records": retrieved, "limit": 3}


def check_plan_contract(arguments: dict[str, Any]) -> dict[str, Any]:
    source_dir = repo_path(arguments["source_dir"])
    from compile_r8_1_lowstar_c2_plan_v1 import compile_plan
    from run_gpt_tactical_stage_session_v1 import validate_plan_payload

    structured = gate.load_json(source_dir / "llm_structured_output.json")
    evidence = gate.load_json(source_dir / "llm_evidence_context.json")
    schema = gate.load_json(source_dir / "revision_output_schema.json")
    layered = validate_plan_payload(structured, evidence, schema)
    static_errors: list[str] = []
    static_result: Any = None
    try:
        static_result = compile_plan(source_dir)
        static_errors = static_result.get("conflicts") or []
    except Exception as exc:
        static_errors = [f"{type(exc).__name__}: {exc}"]
    import hashlib

    def file_sha(path: Path) -> str | None:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

    return {
        "status": "PASS" if not (
            layered["schema_errors"] + layered["semantic_errors"]
            + layered["event_query_errors"] + layered["lineage_errors"] + static_errors
        ) else "FAIL",
        "layers": {**layered, "static_errors": static_errors},
        "static_result": static_result,
        "input_sha256": {
            "llm_structured_output.json": file_sha(source_dir / "llm_structured_output.json"),
            "llm_evidence_context.json": file_sha(source_dir / "llm_evidence_context.json"),
            "revision_output_schema.json": file_sha(source_dir / "revision_output_schema.json"),
        },
    }


def prepare_frozen_plan_evaluation(arguments: dict[str, Any]) -> dict[str, Any]:
    gate_result = gate.prepare_evaluation(
        source_dir=repo_path(arguments["source_dir"]),
        diagnostic_output_dir=repo_path(arguments["diagnostic_output_dir"]),
        budget_path=repo_path(arguments["budget_path"]), stage_id=arguments["stage_id"],
        expected_plan_id=arguments["plan_id"],
    )
    return gate_result


def evaluate_frozen_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    source_dir, diagnostic_output_dir, budget_path = map(
        repo_path, (arguments["source_dir"], arguments["diagnostic_output_dir"], arguments["budget_path"])
    )
    gate_result = gate.prepare_evaluation(
        source_dir=source_dir, diagnostic_output_dir=diagnostic_output_dir, budget_path=budget_path,
        stage_id=arguments["stage_id"], expected_plan_id=arguments["plan_id"],
    )
    if gate_result["status"] != "AUTHORIZED":
        return {**gate_result, "simulation_started": False}
    command = [
        sys.executable, str(ROOT / "scripts/run_gpt_tactical_stage_session_v1.py"), "simulate",
        "--stage-id", arguments["stage_id"], "--facts-dir", str(source_dir),
        "--output-dir", str(source_dir.relative_to(ROOT)),
        "--diagnostic-output-dir", str(diagnostic_output_dir.relative_to(ROOT)),
        "--plan-id", arguments["plan_id"], "--plan-label", arguments["plan_label"],
        "--plan-id-prefix", arguments["plan_id_prefix"],
        "--simulation-budget-path", str(budget_path.relative_to(gate.ROOT)),
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        **gate_result, "simulation_started": True, "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:],
    }


def get_status_and_feedback(arguments: dict[str, Any]) -> dict[str, Any]:
    source_dir = repo_path(arguments["source_dir"])
    result: dict[str, Any] = {"source_dir": str(source_dir.relative_to(ROOT))}
    for name in ("final_status.json", "simulation_gate.json", "revision_hypothesis_evaluation.json"):
        path = source_dir / name
        result[name] = gate.load_json(path) if path.is_file() else None
    feedback_path = arguments.get("feedback_path")
    if feedback_path:
        result["feedback"] = gate.load_json(repo_path(feedback_path))
    return result


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "get_mechanism_facts": get_mechanism_facts,
    "query_applicable_experience": query_applicable_experience,
    "check_plan_contract": check_plan_contract,
    "prepare_frozen_plan_evaluation": prepare_frozen_plan_evaluation,
    "evaluate_frozen_plan": evaluate_frozen_plan,
    "get_status_and_feedback": get_status_and_feedback,
}


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": PROTOCOL_VERSION, "serverInfo": SERVER_INFO, "capabilities": {"tools": {}}}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        name, arguments = params.get("name"), params.get("arguments") or {}
        handler = HANDLERS.get(name)
        try:
            if handler is None:
                result = {"error": "UNKNOWN_TOOL", "tool": name}
                is_error = True
            else:
                result = handler(arguments)
                is_error = False
        except Exception as exc:
            result = {"error": type(exc).__name__, "message": str(exc)}
            is_error = True
        response = {"jsonrpc": "2.0", "id": request_id, "result": tool_result(result)}
        response["result"]["isError"] = is_error
        return response
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
        else:
            response = handle_message(message)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
