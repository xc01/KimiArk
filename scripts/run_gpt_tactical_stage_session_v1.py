from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft7Validator

import run_r8_1_gpt_c4_codex_cli_v1 as codex_runner
from compile_r8_1_lowstar_c2_plan_v1 import compile_plan
from run_r8_1_low_star_full_tactical_closure_v1 import validate_operational_plan_output


ROOT = Path(__file__).resolve().parents[1]
BODY_LIMIT = 140_000
OUT = ROOT / "output/r8_1_r8_7_batch_v1/main_08-02/cli"
DIAGNOSTIC_OUT = ROOT / "output/r8_1_r8_7_batch_v1/main_08-02/diagnostic"
SOURCE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-02/facts"
STAGE_ID = "main_08-02"
PLAN_ID = "R8_2_GPT_V3"
PLAN_PREFIX = "R8_2_GPT_V3"
PLAN_LABEL = "R8-2-V3"
REVISION_SOURCE_DIR: str | None = None
DIAGNOSTIC_SUMMARY: str | None = None
TACTICAL_FEEDBACK: str | None = None
STATIC_CONFLICT_SUMMARY: str | None = None
SAVED_INPUT_DIR: str | None = None


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, exclusive: bool = False) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    else:
        path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure(arguments: argparse.Namespace) -> None:
    global OUT, DIAGNOSTIC_OUT, SOURCE, STAGE_ID, PLAN_ID, PLAN_PREFIX, PLAN_LABEL, REVISION_SOURCE_DIR, DIAGNOSTIC_SUMMARY, SAVED_INPUT_DIR
    OUT = ROOT / arguments.output_dir
    DIAGNOSTIC_OUT = ROOT / arguments.diagnostic_output_dir
    SOURCE = ROOT / arguments.facts_dir
    STAGE_ID = arguments.stage_id
    PLAN_ID = arguments.plan_id
    PLAN_PREFIX = arguments.plan_id_prefix
    PLAN_LABEL = arguments.plan_label
    REVISION_SOURCE_DIR = arguments.revision_source
    DIAGNOSTIC_SUMMARY = arguments.diagnostic_summary
    TACTICAL_FEEDBACK = arguments.tactical_feedback
    STATIC_CONFLICT_SUMMARY = arguments.static_conflict_summary
    SAVED_INPUT_DIR = arguments.saved_input_dir
    codex_runner.configure_run(
        arguments.output_dir,
        arguments.diagnostic_output_dir,
        cli_attempt=arguments.cli_attempt,
        prior_cli_starts=arguments.prior_cli_starts,
        extra_config_values=arguments.extra_config,
        reuse_saved_cli_input=False,
        source_dir=arguments.facts_dir,
        plan_id=PLAN_ID,
        plan_label=PLAN_LABEL,
        plan_id_prefix=PLAN_PREFIX,
        revision_source_plan_id="NONE_INITIAL_STAGE",
        revision_source_path="NONE",
        feedback_summary="NONE",
        feedback_events="NONE",
    )
def compact_runtime_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event.get("event_type"),
        "frame": event.get("frame"),
        "source_id": event.get("source_id"),
        "target_id": event.get("target_id"),
        "details": event.get("details"),
    }


def compact_diagnostic_feedback(path: Path) -> dict[str, Any]:
    summary = load(path)
    result = summary.get("result") or {}
    route_summaries = summary.get("event_summaries", {}).get("route_summaries") or {}
    leaking_routes = []
    clean_route_count = 0
    for route, row in sorted(route_summaries.items()):
        if row.get("leaks"):
            leaking_routes.append({
                "route": route,
                "spawn_count": row.get("spawn_count"),
                "block_count": len(row.get("blocks") or []),
                "kill_count": len(row.get("kills") or []),
                "leaks": [
                    compact_runtime_event(item)
                    for item in row["leaks"]
                ],
            })
        else:
            clean_route_count += 1
    return {
        "classification": summary.get("classification"),
        "mechanics_version": summary.get("mechanics_version"),
        "corrected_mechanism_support": summary.get("corrected_mechanism_support"),
        "civilian_operator_targetability": summary.get("civilian_operator_targetability"),
        "civilian_blocking": summary.get("civilian_blocking"),
        "result_metrics": {
            "win": result.get("win"),
            "enemies_killed": result.get("enemies_killed"),
            "enemies_leaked": result.get("enemies_leaked"),
            "operator_deaths": result.get("operator_deaths"),
            "remaining_life": result.get("remaining_life"),
            "final_dp": result.get("final_dp"),
        },
        "leaking_route_summaries": leaking_routes,
        "clean_route_count": clean_route_count,
        "objective_failures": summary.get("objective_failures") or [],
        "protected_target_reached_events": summary.get("protected_target_reached_events") or [],
        "protected_target_deaths": summary.get("protected_target_deaths") or [],
        "first_leak": (summary.get("first_failure") or {}).get("first_leak"),
        "first_objective_failure": (summary.get("first_failure") or {}).get("objective_failure"),
        "operator_death_events": [
            compact_runtime_event(event)
            for event in summary.get("event_summaries", {}).get("operator_death_events") or []
        ],
        "deployment_errors": [
            compact_runtime_event(event)
            for event in summary.get("event_summaries", {}).get("deployment_errors") or []
        ],
    }


def prepare() -> dict[str, Any]:
    codex_runner.assert_run_lock()
    budget = {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_BUDGET",
        "provider": "codex-cli-openai",
        "model": codex_runner.MODEL,
        "reasoning_effort": codex_runner.REASONING_EFFORT,
        "max_cli_process_starts": 1,
        "cli_process_starts_in_experiment": 0,
        "prior_cli_process_starts": codex_runner.PRIOR_CLI_STARTS,
        "cumulative_cli_process_starts_after_this_attempt": codex_runner.PRIOR_CLI_STARTS + 1,
        "max_operational_plans": 1,
        "new_operational_plans": 0,
        "max_stage_simulations": 1,
        "stage_simulations_started": 0,
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        "automatic_retry": False,
        "automatic_resume": False,
    }
    write_json(codex_runner.OUT / "budget_usage.json", budget)
    if SAVED_INPUT_DIR is not None:
        saved_dir = ROOT / SAVED_INPUT_DIR
        for name in ("llm_evidence_context.json", "codex_prompt.txt", "revision_output_schema.json", "evidence_completeness.json"):
            (codex_runner.OUT / name).write_bytes((saved_dir / name).read_bytes())
        evidence = load(codex_runner.OUT / "llm_evidence_context.json")
        schema = load(codex_runner.OUT / "revision_output_schema.json")
        prompt = (codex_runner.OUT / "codex_prompt.txt").read_text(encoding="utf-8")
    else:
        evidence = load(codex_runner.SOURCE / "llm_evidence_context.json")
        evidence = copy.deepcopy(evidence)
        schema = evidence["output_schema"]
        evidence["milestone"] = f"{STAGE_ID.upper()}_GPT_{PLAN_LABEL}_CODEX_CLI_V1"
        evidence["tactical_provider"] = {
            "provider": "codex-cli", "model": codex_runner.MODEL,
            "reasoning_effort": codex_runner.REASONING_EFFORT,
            "sandbox": "read-only", "compatibility": "USER_CONFIRMED_CLI_LOGIN",
        }
        evidence["codex_cli_run_policy"] = {
            "process_starts": 1, "automatic_retry": False, "automatic_resume": False,
            "source_modification": "FORBIDDEN", "stage_simulation_by_model": "FORBIDDEN",
            "readonly_query_helpers": True,
        }
        evidence["corrected_mechanism_support"] = {
            "mechanics_version": "m19.0-neutral-protected-target-v1",
            "win_rule": "remaining_life > 0, zero leaks, exhausted spawns and no active enemies",
            "neutral_faction_and_ordinary_blocking": "Ursus Civilian is neutral; ordinary operators neither attack nor block it",
            "protected_target_life_scoring": "safe arrival neither leaks nor deducts life; death deducts 1 and is not a kill",
            "roadblock_special_blocking": "roadblocks may block Ursus Civilian but are not ordinary operator blocking",
            "officer_protected_target_attack_radius": "enemy_1107_uoffcr can normally attack Ursus Civilian within 1.2",
            "unknowns": [
                "exact client target priority between operators and protected targets",
                "other protected-target families and exact continuous-frame client timing",
            ],
        }
        evidence.pop("output_schema", None)
        if REVISION_SOURCE_DIR is not None:
            revision_source = ROOT / REVISION_SOURCE_DIR
            revision_evidence = load(revision_source / "llm_evidence_context.json")
            if revision_evidence.get("stage_id") != evidence.get("stage_id"):
                raise RuntimeError("revision source belongs to a different stage")
            evidence["previous_plan_to_revise"] = load(revision_source / "llm_structured_output.json")
            evidence["prior_diagnostic_feedback"] = compact_diagnostic_feedback(ROOT / DIAGNOSTIC_SUMMARY)
            if STATIC_CONFLICT_SUMMARY:
                evidence["prior_static_feedback"] = {
                    "source": STATIC_CONFLICT_SUMMARY,
                    "result": load(ROOT / STATIC_CONFLICT_SUMMARY),
                }
            if TACTICAL_FEEDBACK:
                evidence["prior_tactical_feedback"] = load(ROOT / TACTICAL_FEEDBACK)
            evidence["roadblock_clearance_evidence"] = revision_evidence.get("roadblock_clearance_evidence")
            prior_plan_tiles = revision_evidence.get("stage_active_facts", {}).get(
                "roadblock_plan_tiles_row_col"
            )
            if prior_plan_tiles is not None:
                evidence.setdefault("stage_active_facts", {})[
                    "roadblock_plan_tiles_row_col"
                ] = prior_plan_tiles
            evidence["provenance"]["revision_source"] = {
                "path": REVISION_SOURCE_DIR,
                "relationship": "prior_simulated_candidate_not_parent_hypothesis",
                "revision_policy": "GPT decides tactical changes; deterministic checks may only reject the original fixed actions",
            }
        write_json(codex_runner.OUT / "llm_evidence_context.json", evidence)
        write_json(codex_runner.OUT / "revision_output_schema.json", schema)
        prompt = build_prompt(evidence)
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > BODY_LIMIT:
        raise RuntimeError(f"Codex prompt exceeds {BODY_LIMIT} bytes: {prompt_bytes}")
    (codex_runner.OUT / "codex_prompt.txt").write_text(prompt, encoding="utf-8")
    if SAVED_INPUT_DIR is None:
        completeness = {
            "stage_id": evidence["stage_id"] == STAGE_ID,
            "all_34_low_stars_present": len(evidence["normal_low_star_catalog"]) == 34,
            "all_17_three_stars_present": sum(
                item["identity"]["rarity"] == 3 for item in evidence["normal_low_star_catalog"]
            ) == 17,
            "routes_present": bool(evidence["source_routes"]),
            "wave_schedule_present": bool(evidence["source_wave_schedule"]),
            "runtime_status": evidence["stage_mechanism_support"]["runtime_adapter_status"],
            "prompt_bytes": prompt_bytes,
            "prompt_bytes_at_or_below_limit": prompt_bytes <= BODY_LIMIT,
        }
        if not all(completeness.values()):
            raise RuntimeError("stage evidence completeness check failed: " + json.dumps(completeness, sort_keys=True))
    else:
        completeness = load(codex_runner.OUT / "evidence_completeness.json")
        completeness["reused_saved_input"] = True
        completeness["prompt_sha256"] = sha256(codex_runner.OUT / "codex_prompt.txt")
        completeness["prompt_bytes"] = prompt_bytes
        completeness["prompt_bytes_at_or_below_limit"] = prompt_bytes <= BODY_LIMIT
    write_json(codex_runner.OUT / "evidence_completeness.json", completeness)
    write_json(codex_runner.OUT / "codex_command.json", {
        "argv": codex_runner.build_command(codex_runner.OUT / "codex_final_message.txt"),
        "stdin": "prompt", "shell": False,
        "prompt_sha256": sha256(codex_runner.OUT / "codex_prompt.txt"),
        "prompt_bytes": prompt_bytes,
        "timeout_seconds": codex_runner.CLI_TIMEOUT_SECONDS,
    })
    return {"prompt": prompt, "schema": schema, "budget": budget}


def build_prompt(evidence: dict[str, Any]) -> str:
    evidence_json = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
    active = evidence["stage_active_facts"]
    forbidden_plan_tiles = active.get("roadblock_plan_tiles_row_col")
    if not isinstance(forbidden_plan_tiles, list):
        raise RuntimeError("stage_active_facts.roadblock_plan_tiles_row_col is required")
    clearance_instruction = ""
    clearance = evidence.get("roadblock_clearance_evidence")
    if clearance:
        roadblock = clearance["roadblock_2"]
        civilian = clearance["v1_v3_common_events"]["civilian_11"]
        death = clearance["v1_v3_common_events"]["civilian_6"]["death"]
        v5 = clearance.get("v5_result_feedback")
        clearance_instruction = (
            "USER_CONFIRMED_OBSERVATION: an Ursus Civilian remains stopped at a roadblock "
            f"until that roadblock is destroyed. {roadblock['device_id']} at [row,col]={roadblock['tile_json_row_col']} "
            f"blocked civilian {civilian['spawn']}, first blocked at frame {civilian['first_roadblock_2_block']['frame']} "
            f"and remained blocked at frame {civilian['last_roadblock_2_block']['frame']}; neither prior plan selected or damaged it. "
            f"Civilian #6 died at frame {death['frame']} and cost one objective life. Decide the complete roadblock-#2 "
            "clearance responsibility (attacker, tile, direction, start, expected destroy timing) and protect/maintain the "
            "defense without extending the 600-second cap, ignoring the civilian, or forcing release. Acceptance requires "
            "roadblock damage/destruction and #11's safe PROTECTED_TARGET_REACHED. Full completion is primary; also aim for "
            "protected-target loss=0."
        )
        if v5:
            remaining = v5["remaining_perfect_completion_failure"]["civilian_6"]
            clearance_instruction += (
                f" V5 already destroyed roadblock #2 and safely reached #11, but civilian #6 died at frame "
                f"{remaining['death']['frame']} after {remaining['officer_attack_count']} officer attacks. {PLAN_LABEL} must retain the "
                "zero-leak result and change the officer-protection responsibility so every protected target arrives."
            )
    return f"""You are {codex_runner.MODEL} via the local Codex CLI, the tactical decision maker for {STAGE_ID} / {STAGE_ID.replace('main_0', 'R8-')}.
Create exactly one compact full-stage OperationalPlan {PLAN_LABEL}. Use `"operational_plan_id": "{PLAN_ID}"` exactly. The final assistant message must be exactly one JSON object matching the supplied output schema; no markdown wrapper or commentary.

You may use read-only shell commands to inspect the supplied evidence or `scripts/kimi_readonly_tools.py`. Do not create, modify or delete files. Do not run a stage simulation. Do not invoke other AI providers. Do not print credentials.

Only operators in `normal_low_star_catalog` are legal. Require `identity.rarity` 1-3 and `qualification.normal_mode == true`; exclude mode-specific reserve units. Every DEPLOY needs integer [row,col] and UP/DOWN/LEFT/RIGHT. `stage_active_facts.roadblock_tiles_col_row` is [col,row]; `stage_active_facts.roadblock_plan_tiles_row_col` is the exact JSON forbidden set. Never deploy on {json.dumps(forbidden_plan_tiles)}. WIN requires `remaining_life > 0`, zero leaks, exhausted spawns and no active enemies.

{clearance_instruction}

{"Revise the prior {STAGE_ID} candidate using the saved simulated failure evidence. Explain changed hypotheses in the plan, but do not preserve an action merely because it existed. Python/GLM will not choose tactics for you." if "prior_diagnostic_feedback" in evidence else "This is an initial {STAGE_ID} plan; do not copy R8-1 routes, deadlines, tactics or facts. Use only this stage's routes, spawn schedule, map, devices, enemies and mechanisms. Mark unresolved stage-specific mechanics UNKNOWN. You decide opening structure, route responsibilities, simultaneous blocking, fire support, healing, skills, retreats and economic order. Python/GLM will not choose tactics for you."}
{"IMPORTANT: prior_static_feedback is from the immediately preceding candidate, while prior_diagnostic_feedback may be from the earlier simulated baseline. Resolve every prior static conflict exactly without letting Python alter tactical actions." if "prior_static_feedback" in evidence else ""}
{"IMPORTANT: prior_tactical_feedback is the verified causal history. Treat failed conditional economic dependencies as survival/handoff failures, not arithmetic bugs. Preserve demonstrated improvements only when the structure that produced them remains supported; redesign the opening survival, interception, protection, and clearance responsibilities yourself." if "prior_tactical_feedback" in evidence else ""}

Use read-only helper functions when needed to verify ranges, timing or mechanics. Do not attack or block neutral civilians with ordinary operators; remember enemy officers may attack civilians and civilian death costs objective life. Do not invent device navigation, target ordering, refunds, client timing or unsupported effects. Distinguish GameData facts, current-model rules and UNKNOWN. Do not repeat evidence prose. The compact evidence JSON follows:

EVIDENCE_JSON
{evidence_json}
"""


def validate_final(parsed: Any, execution: dict[str, Any]) -> dict[str, Any]:
    evidence = load(codex_runner.OUT / "llm_evidence_context.json")
    schema = load(codex_runner.OUT / "revision_output_schema.json")
    errors: list[str] = []
    try:
        schema_errors = sorted(Draft7Validator(schema).iter_errors(parsed), key=lambda item: list(item.path))
        errors.extend(f"schema: {'/'.join(map(str, item.path)) or '<root>'}: {item.message}" for item in schema_errors)
    except Exception as exc:
        errors.append(f"schema validation unavailable: {exc}")
    errors.extend(validate_operational_plan_output(parsed, evidence))
    if isinstance(parsed, dict):
        plans = parsed.get("revised_operational_plans")
        plan = plans[0] if isinstance(plans, list) and len(plans) == 1 else {}
        hypothesis_ids = {
            row.get("hypothesis_id")
            for row in parsed.get("revised_strategic_hypotheses") or []
            if isinstance(row, dict) and row.get("hypothesis_id")
        }
        if plan.get("parent_hypothesis_id") not in hypothesis_ids:
            errors.append("parent_hypothesis_id must reference a revised_strategic_hypotheses hypothesis_id")
        if not str(plan.get("operational_plan_id", "")).startswith(PLAN_PREFIX):
            errors.append(f"operational_plan_id must identify {PLAN_LABEL}")
    validation = {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_PLAN_VALIDATION",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }
    write_json(codex_runner.OUT / "llm_plan_validation.json", validation)
    if errors:
        write_json(codex_runner.OUT / "invalid_final_plan.json.parsed", parsed, exclusive=True)
        write_json(codex_runner.OUT / "final_status.json", {
            "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_FINAL_STATUS",
            "status": "FAILED_INVALID_PLAN_NO_RETRY", "errors": errors,
            "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": codex_runner.PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise SystemExit(f"Codex {PLAN_LABEL} failed schema/contract validation: {errors}")
    write_json(codex_runner.OUT / "llm_structured_output.json", parsed)
    write_json(codex_runner.OUT / "final_status.json", {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_FINAL_STATUS",
        "status": f"GPT_{PLAN_LABEL}_RECEIVED_AND_CONTRACT_VALID",
        "cli_process_starts_in_experiment": 1,
        "cumulative_cli_process_starts": codex_runner.PRIOR_CLI_STARTS + 1,
        "new_operational_plans": 1, "stage_simulations_started": 0,
        "internal_model_request_count": "UNKNOWN_CLI_INTERNAL",
        "session_ids": execution["trajectory"]["session_ids"],
        "thread_ids": execution["trajectory"]["thread_ids"],
        "usage_records": execution["trajectory"]["usage_records"],
    })
    return validation


def run_session(runner: Callable[[str, list[str], int], dict[str, Any]] = codex_runner.run_codex_once) -> dict[str, Any]:
    prepared = prepare()
    last_message_path = codex_runner.OUT / "codex_final_message.txt"
    command = codex_runner.build_command(last_message_path)
    try:
        execution = runner(prepared["prompt"], command, codex_runner.CLI_TIMEOUT_SECONDS)
    except Exception as exc:
        write_json(codex_runner.OUT / "final_status.json", {
            "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_FINAL_STATUS",
            "status": "CLI_FAILED_NO_RETRY", "error": f"{type(exc).__name__}: {exc}",
            "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": codex_runner.PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise
    if execution["process"]["exit_code"] != 0:
        write_json(codex_runner.OUT / "final_status.json", {
            "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_FINAL_STATUS",
            "status": "CLI_FAILED_NO_RETRY", "failure": execution["process"],
            "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": codex_runner.PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise SystemExit("Codex CLI failed without retry")
    if not last_message_path.is_file():
        write_json(codex_runner.OUT / "final_status.json", {
            "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_FINAL_STATUS",
            "status": "CLI_FAILED_NO_RETRY", "error": "Codex CLI did not save --output-last-message",
            "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": codex_runner.PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise SystemExit("Codex CLI final message missing")
    final_text = last_message_path.read_text(encoding="utf-8").strip()
    last_message_path.write_text(final_text + "\n", encoding="utf-8")
    try:
        parsed = json.loads(final_text)
    except json.JSONDecodeError as exc:
        write_json(codex_runner.OUT / "llm_plan_validation.json", {
            "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_PLAN_VALIDATION",
            "status": "FAIL", "error": f"final message is not JSON: {exc}",
        })
        write_json(codex_runner.OUT / "final_status.json", {
            "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_FINAL_STATUS",
            "status": "FAILED_INVALID_PLAN_NO_RETRY", "cli_process_starts_in_experiment": 1,
            "cumulative_cli_process_starts": codex_runner.PRIOR_CLI_STARTS + 1,
            "new_operational_plans": 0, "stage_simulations_started": 0,
        })
        raise SystemExit("Codex final message is not JSON")
    validate_final(parsed, execution)
    return parsed


def static_check() -> dict[str, Any]:
    if load(codex_runner.OUT / "llm_plan_validation.json").get("status") != "PASS":
        raise RuntimeError(f"static check requires locally validated {PLAN_LABEL}")
    return compile_plan(codex_runner.OUT)


def simulate() -> dict[str, Any]:
    from run_gpt_tactical_stage_diagnostic_v1 import run_full_diagnostic

    static = load(codex_runner.OUT / "static_compile_results.json")
    if static["conflicts"]:
        write_json(codex_runner.OUT / "static_compile_execution_gate.json", {
            "status": "BLOCKED_STATIC_CONFLICT", "conflicts": static["conflicts"],
        })
        raise SystemExit(f"{PLAN_LABEL} static conflicts block diagnostic simulation")
    budget = load(codex_runner.OUT / "budget_usage.json")
    if budget["stage_simulations_started"]:
        raise RuntimeError("stage simulation budget already consumed")
    budget["stage_simulations_started"] = 1
    write_json(codex_runner.OUT / "budget_usage.json", budget)
    run_full_diagnostic(
        source=codex_runner.OUT, out=codex_runner.DIAGNOSTIC_OUT,
        stage_id=STAGE_ID, plan_id=PLAN_ID,
    )
    summary = load(codex_runner.DIAGNOSTIC_OUT / "diagnostic_summary.json")
    write_json(codex_runner.OUT / "simulation_gate.json", {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_SIMULATION_GATE",
        "status": "COMPLETED", "result_classification": summary["classification"],
        "faithful_certificate": summary["faithful_certificate"],
        "simulator_win": summary["result"]["win"],
        "real_game_win_claim": False,
    })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "session", "static_check", "simulate"])
    parser.add_argument("--stage-id", required=True)
    parser.add_argument("--facts-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--diagnostic-output-dir", required=True)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--plan-label", required=True)
    parser.add_argument("--plan-id-prefix", required=True)
    parser.add_argument("--cli-attempt", type=int, default=1)
    parser.add_argument("--prior-cli-starts", type=int, default=0)
    parser.add_argument(
        "--extra-config", action="append", default=[],
        help="additional Codex -c override, recorded with the attempt",
    )
    parser.add_argument("--revision-source")
    parser.add_argument("--diagnostic-summary")
    parser.add_argument("--tactical-feedback")
    parser.add_argument("--static-conflict-summary")
    parser.add_argument("--saved-input-dir")
    arguments = parser.parse_args()
    configure(arguments)
    if arguments.phase == "session":
        run_session()
    elif arguments.phase == "prepare":
        prepared = prepare()
        print(json.dumps({"prompt_bytes": len(prepared["prompt"].encode()), "budget": prepared["budget"]}, sort_keys=True))
    elif arguments.phase == "static_check":
        static_check()
    else:
        simulate()


if __name__ == "__main__":
    main()
