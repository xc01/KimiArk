from __future__ import annotations

import argparse
import copy
import json
import os
from collections import Counter
import re
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft7Validator

import run_r8_1_gpt_c4_codex_cli_v1 as codex_runner
from compile_r8_1_lowstar_c2_plan_v1 import compile_plan
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION
from run_r8_1_low_star_full_tactical_closure_v1 import validate_operational_plan_output
import tactical_experience_v1 as experience
import tactical_evaluation_gate_v1 as gate


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
EXPERIENCE_STORE_PATH: str | None = None
BRANCH_STATE_PATH: str | None = None
MAX_UNIQUE_DEPLOYED_OPERATORS: int | None = None
AUTHORIZATION_CONFIG_PATH = ROOT / "docs/review/fc77177/m27_model_authorization_v1.json"
SIMULATION_BUDGET_PATH = ROOT / "docs/review/fc77177/m28_simulation_budget_v1.json"


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
    global OUT, DIAGNOSTIC_OUT, SOURCE, STAGE_ID, PLAN_ID, PLAN_PREFIX, PLAN_LABEL
    global REVISION_SOURCE_DIR, DIAGNOSTIC_SUMMARY, TACTICAL_FEEDBACK, STATIC_CONFLICT_SUMMARY
    global SAVED_INPUT_DIR, EXPERIENCE_STORE_PATH, BRANCH_STATE_PATH
    global MAX_UNIQUE_DEPLOYED_OPERATORS, AUTHORIZATION_CONFIG_PATH, SIMULATION_BUDGET_PATH
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
    EXPERIENCE_STORE_PATH = arguments.experience_store
    BRANCH_STATE_PATH = arguments.branch_state
    MAX_UNIQUE_DEPLOYED_OPERATORS = arguments.max_unique_deployed_operators
    AUTHORIZATION_CONFIG_PATH = ROOT / arguments.authorization_config
    SIMULATION_BUDGET_PATH = ROOT / arguments.simulation_budget_path
    authorization = load(ROOT / arguments.authorization_config)
    codex_runner.MODEL = authorization["model"]
    codex_runner.REASONING_EFFORT = authorization["reasoning_effort"]
    codex_runner.AUTHORIZATION_CONFIG_PATH = AUTHORIZATION_CONFIG_PATH
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


def distinct_deployed_operator_ids(plan: dict[str, Any]) -> set[str]:
    distinct = set(plan.get("selected_low_star_operator_ids") or [])
    distinct.update(
        action.get("operator_id")
        for action in plan.get("action_timeline") or []
        if isinstance(action, dict) and action.get("action_type") == "DEPLOY"
    )
    return distinct


def roster_prompt_instruction(max_unique: int) -> str:
    return (
        f"HARD ROSTER LIMIT: the union of selected_low_star_operator_ids and every DEPLOY action "
        f"operator_id must contain at most {max_unique} distinct IDs. Remove unused listed operators "
        "before emitting the plan; retreat/redeploy and hidden aliases do not avoid the count."
    )


def ensure_saved_prompt_roster_limit(prompt: str, max_unique: int) -> tuple[str, bool]:
    expected_instruction = roster_prompt_instruction(max_unique)
    if "HARD ROSTER LIMIT:" in prompt:
        if expected_instruction not in prompt:
            raise RuntimeError("saved prompt contains a conflicting hard roster limit")
        return prompt, False
    return f"{expected_instruction}\n\n{prompt}", True


def resolve_milestone_constraints(evidence: dict[str, Any], *, saved_input: bool = False) -> dict[str, Any]:
    configured_limit = MAX_UNIQUE_DEPLOYED_OPERATORS
    saved_limit_value = (evidence.get("milestone_constraints") or {}).get("max_unique_deployed_operator_ids")
    saved_limit = saved_limit_value if isinstance(saved_limit_value, int) else None
    if saved_input and configured_limit is None and saved_limit is not None:
        raise RuntimeError(
            "saved input contains a roster limit; pass the same --max-unique-deployed-operators explicitly"
        )
    if saved_input and configured_limit is not None and saved_limit is not None and configured_limit != saved_limit:
        raise RuntimeError(
            f"roster-limit conflict: configured={configured_limit}, saved_input={saved_limit}"
        )
    if not saved_input:
        evidence.pop("milestone_constraints", None)
    effective_limit = configured_limit if configured_limit is not None else saved_limit if saved_input else None
    if effective_limit is not None:
        evidence["milestone_constraints"] = {
            "max_unique_deployed_operator_ids": effective_limit,
            "counting_rule": "The union of selected_low_star_operator_ids and every DEPLOY action operator_id is counted; retreat and redeploy do not reduce distinct-operator count.",
        }
    source = (
        "CONFIGURED_ARGUMENT" if configured_limit is not None
        else "SAVED_INPUT" if saved_input and saved_limit is not None
        else "NONE"
    )
    resolution = {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_MILESTONE_CONSTRAINT_RESOLUTION",
        "configured_limit": configured_limit,
        "saved_input_limit": saved_limit if saved_input else None,
        "effective_limit": effective_limit,
        "source": source,
        "conflict_policy": "FAIL_ON_CONFLICT" if saved_input else "CONFIGURED_ARGUMENT_OVERRIDES_BASE_FACTS",
    }
    if saved_input:
        saved_path = ROOT / SAVED_INPUT_DIR / "llm_evidence_context.json"
        resolution["saved_input_evidence_sha256"] = sha256(saved_path)
        resolution["saved_input_prompt_sha256"] = sha256(ROOT / SAVED_INPUT_DIR / "codex_prompt.txt")
    return resolution


def validate_plan_payload(parsed: Any, evidence: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    schema_errors = [
        f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in sorted(Draft7Validator(schema).iter_errors(parsed), key=lambda item: list(item.absolute_path))
    ]
    semantic_errors: list[str] = []
    if isinstance(parsed, dict):
        from run_r8_1_low_star_full_tactical_closure_v1 import validate_operational_plan_output

        semantic_errors.extend(validate_operational_plan_output(parsed, evidence))
    else:
        semantic_errors.append("response is not a JSON object")

    event_query_errors: list[str] = []
    revision = parsed.get("revision_hypothesis") if isinstance(parsed, dict) else None
    if isinstance(revision, dict) and "expected_first_observable_event" in revision:
        query = experience.normalize_event_query(revision["expected_first_observable_event"])
        if query["status"] != "VALID_QUERY":
            event_query_errors.append(f"{query.get('reason')}: {query.get('event_type_declared') or query.get('event_type')}")

    plans = parsed.get("revised_operational_plans") if isinstance(parsed, dict) else None
    plan = plans[0] if isinstance(plans, list) and len(plans) == 1 and isinstance(plans[0], dict) else None
    previous_plan_id = experience.extract_operational_plan_id(evidence.get("previous_plan_to_revise"))
    declared_parent_plan_id = experience.extract_declared_parent_plan_id(parsed)
    plan_parent_plan_id = experience.extract_parent_plan_id(plan)
    lineage_errors: list[str] = []
    if previous_plan_id and plan_parent_plan_id and previous_plan_id != plan_parent_plan_id:
        lineage_errors.append("previous plan operational_plan_id does not match declared parent_plan_id")
    if plan_parent_plan_id and declared_parent_plan_id and plan_parent_plan_id != declared_parent_plan_id:
        lineage_errors.append("plan parent_plan_id and revision_hypothesis parent_plan_id disagree")
    return {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_LAYERED_PLAN_VALIDATION",
        "schema_errors": schema_errors,
        "semantic_errors": semantic_errors,
        "event_query_errors": event_query_errors,
        "lineage_errors": lineage_errors,
        "previous_plan_id": previous_plan_id,
        "declared_parent_plan_id": declared_parent_plan_id,
        "plan_parent_plan_id": plan_parent_plan_id,
    }


def compact_diagnostic_feedback(path: Path) -> dict[str, Any]:
    summary = load(path)
    final_status_path = path.with_name("final_status.json")
    source_plan_id = summary.get("plan_id")
    if not source_plan_id and final_status_path.is_file():
        source_plan_id = load(final_status_path).get("plan_id")
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
        "source_plan_id": source_plan_id or "UNKNOWN_SOURCE_PLAN",
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
        "objective_failures": (summary.get("objective_failures") or [])[:2],
        "objective_failure_summary": {
            "count": len(summary.get("objective_failures") or []),
            "reason_counts": dict(sorted(Counter(
                row.get("reason") for row in summary.get("objective_failures") or []
            ).items())),
            "full_failure_timeline_source": "SAVED_DIAGNOSTIC_EVENTS",
        },
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


def build_static_feedback(revision_source: Path, static_summary_path: Path) -> dict[str, Any]:
    structured = load(revision_source / "llm_structured_output.json")
    plans = structured.get("revised_operational_plans") or []
    candidate = plans[0] if len(plans) == 1 else {}
    static = load(static_summary_path)
    if static.get("schema_version") == "GPT_TACTICAL_STAGE_SESSION_V1_PLAN_VALIDATION":
        return {
            "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_SCHEMA_CONTRACT_FEEDBACK",
            "source": str(static_summary_path),
            "source_plan_id": static.get("source_plan_id") or candidate.get("operational_plan_id"),
            "simulation_status": "NO_SIMULATION",
            "errors": static.get("errors") or [],
            "action_order_rule": "action_timeline must be nondecreasing by frame; same-frame actions retain their intended execution order",
            "required_plan_sections": [
                "deployment_positions_and_directions",
                "formation_structure",
                "pressure_window_responsibilities",
                "skill_intents",
                "mandatory_tactical_invariants",
            ],
        }
    deployment_checks = (static.get("checks") or {}).get("deployment") or []
    dp_ledger = static.get("dp_ledger") or {}
    ledger_entries = dp_ledger.get("entries") or []
    conflicts = []
    for conflict in static.get("conflicts") or []:
        action_index = next(
            (
                check.get("action_index")
                for check in deployment_checks
                if check.get("operator_id") == conflict.get("operator_id")
                and check.get("frame") == conflict.get("frame")
            ),
            next(
                (
                    index
                    for index, action in enumerate(candidate.get("action_timeline") or [])
                    if action.get("operator_id") == conflict.get("operator_id")
                    and action.get("frame") == conflict.get("frame")
                ),
                None,
            ),
        )
        conflict_frame = conflict.get("frame")
        previous_economic_events = [] if conflict.get("reason") == "SP_NOT_READY" else [
            {
                "event": row.get("event"),
                "frame": row.get("frame"),
                "operator_id": row.get("operator_id"),
                "delta": row.get("delta"),
                "balance_before": row.get("balance_before"),
                "balance_after": row.get("balance_after"),
                "status": row.get("status"),
                "source": row.get("source"),
            }
            for row in ledger_entries
            if row.get("frame") is not None
            and conflict_frame is not None
            and row["frame"] < conflict_frame
            and row.get("event") in {
                "NATURAL_DP", "AUTO_SKILL_DP_INCOME", "SKILL_DP_INCOME",
                "DEPLOY_COST", "DEPLOY_COST_REJECTED",
            }
        ]
        conflicts.append({
            "candidate_plan_id": candidate.get("operational_plan_id"),
            "action_index": action_index,
            "conflict": conflict.get("reason") or conflict.get("conflict"),
            "frame": conflict_frame,
            "operator_id": conflict.get("operator_id"),
            "required_value": conflict.get("required_sp") if conflict.get("required_sp") is not None else conflict.get("cost"),
            "available_value": conflict.get("available_sp_model") if conflict.get("available_sp_model") is not None else conflict.get("balance_before"),
            "previous_economic_events": previous_economic_events,
            "conditional_income_sources": (dp_ledger.get("automatic_skill_income_model") or {}).get(
                "conditions"
            ) or [],
            "battle_result_status": "NO_SIMULATION",
        })
    return {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_STATIC_CONFLICT_FEEDBACK",
        "source": str(static_summary_path),
        "source_plan_id": candidate.get("operational_plan_id"),
        "simulation_status": "NO_SIMULATION",
        "conflicts": conflicts,
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
        constraint_resolution = resolve_milestone_constraints(evidence, saved_input=True)
        prompt = (codex_runner.OUT / "codex_prompt.txt").read_text(encoding="utf-8")
        effective_limit = constraint_resolution["effective_limit"]
        if effective_limit is not None:
            prompt, prompt_regenerated = ensure_saved_prompt_roster_limit(prompt, effective_limit)
            constraint_resolution["prompt_regenerated"] = prompt_regenerated
            write_json(codex_runner.OUT / "llm_evidence_context.json", evidence)
        else:
            if "HARD ROSTER LIMIT:" in prompt:
                raise RuntimeError("saved prompt contains a hard roster limit but no configured or evidence limit")
            constraint_resolution["prompt_regenerated"] = False
    else:
        evidence = load(codex_runner.SOURCE / "llm_evidence_context.json")
        evidence = copy.deepcopy(evidence)
        schema = evidence["output_schema"]
        for redundant_policy_key in (
            "authoritative_policy",
            "codex_cli_run_policy",
            "hard_policy",
            "normal_low_star_support_counts",
        ):
            evidence.pop(redundant_policy_key, None)
        evidence["milestone"] = f"{STAGE_ID.upper()}_GPT_{PLAN_LABEL}_CODEX_CLI_V1"
        constraint_resolution = resolve_milestone_constraints(evidence, saved_input=False)
        evidence["tactical_provider"] = {
            "provider": "codex-cli", "model": codex_runner.MODEL,
            "reasoning_effort": codex_runner.REASONING_EFFORT,
            "sandbox": "read-only", "compatibility": "USER_CONFIRMED_CLI_LOGIN",
        }
        evidence["mechanics_version"] = ACTIVE_MECHANICS_VERSION
        evidence["codex_cli_run_policy"] = {
            "process_starts": 1, "automatic_retry": False, "automatic_resume": False,
            "source_modification": "FORBIDDEN", "stage_simulation_by_model": "FORBIDDEN",
            "readonly_query_helpers": True,
        }
        evidence["corrected_mechanism_support"] = {
            "mechanics_version": ACTIVE_MECHANICS_VERSION,
            "win_rule": "remaining_life > 0, zero leaks, exhausted spawns and no active enemies",
            "neutral_faction_and_ordinary_blocking": "Ursus Civilian is neutral; ordinary operators neither attack nor block it",
            "protected_target_life_scoring": "safe arrival neither leaks nor deducts life; death deducts 1 and is not a kill",
            "roadblock_special_blocking": "PRTS-backed 0.4472 roadblock radius blocks Ursus Civilian and release occurs on destruction; it is not ordinary operator blocking",
            "officer_protected_target_attack_radius": "enemy_1107_uoffcr can normally attack Ursus Civilian within 1.2",
            "stage_move_multiplier": "applied once to enemy raw move speed",
            "fragment_or_wave_wait": "checkpoint time is used as the wait duration in the current model",
            "disappear_appear": "enemy is hidden between source DISAPPEAR and APPEAR_AT_POS; exact client visibility and target rules remain UNKNOWN",
            "artillery_candidate_timeline": "Cast starts cooldown and selection; with no slowdown, OnAttack creates the fixed-point projectile about cast+0.333333 seconds, and the hit is about creation+3.0 seconds. This is 2.7.81 candidate evidence, not build-2771 equality.",
            "medical_candidate_scope": "The confirmed ratio filter selects the lowest missing-HP-ratio in range and excludes full HP; exact equal-ratio tie-break remains UNKNOWN.",
            "protected_target_candidate_scope": "Neutral-promotion before hatred sorting is confirmed for the 2.7.81 selector; exact hatred values and all tie-breaks remain UNKNOWN.",
            "unknowns": [
                "build-2771 equivalence",
                "interruption and mid-cast attack-time rescheduling",
                "ordinary/special mutual exclusion",
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
            parent_plan = evidence["previous_plan_to_revise"]
            if isinstance(parent_plan, dict) and isinstance(parent_plan.get("revised_operational_plans"), list) and len(parent_plan["revised_operational_plans"]) == 1:
                parent_candidate = parent_plan["revised_operational_plans"][0]
                evidence["previous_plan_to_revise"] = {
                    key: parent_candidate[key]
                    for key in (
                        "operational_plan_id", "parent_hypothesis_id", "tactical_thesis",
                        "selected_low_star_operator_ids", "deployment_positions_and_directions",
                        "formation_structure", "formation_transitions", "corridor_responsibilities",
                        "pressure_window_responsibilities", "skill_intents",
                    )
                    if key in parent_candidate
                }
                evidence["provenance"]["parent_plan_complete_artifact"] = str(
                    (revision_source / "llm_structured_output.json").relative_to(ROOT)
                )
            if DIAGNOSTIC_SUMMARY is None:
                prior_diagnostic = {
                    "source_plan_id": experience.extract_operational_plan_id(parent_plan) or "UNKNOWN_SOURCE_PLAN",
                    "classification": "STATIC_BLOCKED_NO_SIMULATION",
                    "result_metrics": {"win": None, "enemies_killed": None, "enemies_leaked": None, "operator_deaths": None, "remaining_life": None, "final_dp": None},
                    "objective_failure_summary": {"count": 0, "reason_counts": {}},
                }
            else:
                prior_diagnostic = compact_diagnostic_feedback(ROOT / DIAGNOSTIC_SUMMARY)
                prior_diagnostic.pop("leaking_route_summaries", None)
            evidence["prior_diagnostic_feedback"] = prior_diagnostic
            if TACTICAL_FEEDBACK:
                evidence["prior_tactical_feedback"] = load(ROOT / TACTICAL_FEEDBACK)
            if STATIC_CONFLICT_SUMMARY:
                evidence["prior_static_feedback"] = build_static_feedback(
                    revision_source, ROOT / STATIC_CONFLICT_SUMMARY
                )
                if evidence.get("prior_tactical_feedback"):
                    evidence["prior_static_feedback"]["battle_feedback_source_plan_id"] = (
                        evidence["prior_tactical_feedback"].get("source_plan_id")
                    )
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
        if EXPERIENCE_STORE_PATH is not None:
            records = experience.load_experience_records(ROOT / EXPERIENCE_STORE_PATH)
            battle_feedback = evidence.get("prior_tactical_feedback") if isinstance(evidence.get("prior_tactical_feedback"), dict) else None
            feedback_text = json.dumps({"feedback": battle_feedback, "prior_diagnostic": evidence.get("prior_diagnostic_feedback")}, ensure_ascii=False)
            responsibility_tags = {
                tag for tag, needles in {
                    "artillery_survival": ("artillery", "emppnt"),
                    "healing": ("heal", "medic", "ansel", "lancet", "hibiscus"),
                    "protected_target": ("protected_target", "civilian", "upeopl"),
                    "roadblock_clearance": ("roadblock", "trap_020"),
                    "opening_survival": ("opening", "first_leak", "operator_deaths"),
                    "source_operator_survival": ("operator_death", "absent source operator"),
                }.items()
                if any(needle in feedback_text.lower() for needle in needles)
            } or {"stage_strategy"}
            relevant_operator_ids = set(re.findall(r"char_[a-z0-9_]+", feedback_text))
            prior_plan = evidence.get("previous_plan_to_revise")
            prior_plan_candidate = prior_plan.get("revised_operational_plans", [{}])[0] if isinstance(prior_plan, dict) and isinstance(prior_plan.get("revised_operational_plans"), list) else prior_plan
            relevant_operator_ids.update(
                value for value in (prior_plan_candidate or {}).get("selected_low_star_operator_ids") or []
                if isinstance(value, str)
            )
            prior_invalid_plan_id = next(
                (
                    feedback.get("source_plan_id")
                    for feedback in (battle_feedback, evidence.get("prior_static_feedback"))
                    if isinstance(feedback, dict) and feedback.get("source_plan_id")
                ),
                None,
            )
            contract_experiences = experience.retrieve_experiences(
                records, stage_id=STAGE_ID, mechanics_version=ACTIVE_MECHANICS_VERSION,
                failure_category="CONTRACT_INVALID", responsibility_tags={"contract"},
                source_plan_id=prior_invalid_plan_id,
                game_data_sha256=evidence.get("gamedata_commit"), limit=1,
            )
            battle_experiences = experience.retrieve_experiences(
                records, stage_id=STAGE_ID, mechanics_version=ACTIVE_MECHANICS_VERSION,
                failure_category="LEGAL_BATTLE_LOSS", responsibility_tags=responsibility_tags,
                operator_ids=relevant_operator_ids, source_plan_id=(
                    battle_feedback.get("source_plan_id") if isinstance(battle_feedback, dict) else None
                ),
                game_data_sha256=evidence.get("gamedata_commit"),
                limit=3 - len(contract_experiences),
            )
            retrieved = experience.retrieve_experiences(
                contract_experiences + battle_experiences, stage_id=STAGE_ID,
                mechanics_version=ACTIVE_MECHANICS_VERSION,
                game_data_sha256=evidence.get("gamedata_commit"), limit=3,
            )
            evidence["tactical_experience"] = {
                "schema_version": experience.EVENT_QUERY_SCHEMA_VERSION,
                "retrieval_limit": 3,
                "records": retrieved,
                "usage_policy": [
                    "Treat each record as conditional evidence, not a universal deadline.",
                    "Do not infer a tactical failure from a contract-invalid candidate.",
                    "A different mechanics version is REQUIRES_REVALIDATION, not current fact.",
                    "A VERIFIED prediction only confirms its declared observable event; it does not prove the full plan.",
                ],
            }
            evidence.pop("m24_tactical_revision_input", None)
            evidence.pop("roadblock_clearance_evidence", None)
        else:
            feedback = evidence.get("prior_tactical_feedback")
            evidence["tactical_experience"] = {
                "schema_version": experience.EVENT_QUERY_SCHEMA_VERSION,
                "retrieval_limit": 0,
                "records": [{
                    "experience_id": feedback.get("schema_version") if isinstance(feedback, dict) else "CURRENT_FEEDBACK",
                    "scope": {"stage_id": STAGE_ID, "mechanics_version": ACTIVE_MECHANICS_VERSION},
                    "evidence_status": feedback.get("evidence_status") if isinstance(feedback, dict) else "UNKNOWN",
                    "source": feedback.get("source_manifest") if isinstance(feedback, dict) else None,
                    "summary": "Current M38b replay feedback is the available conditional evidence; do not reference unregistered plan IDs as experience IDs.",
                }],
                "usage_policy": [
                    "Use only experience_id values listed in records.",
                    "Treat this record as conditional evidence, not a universal deadline.",
                    "A VERIFIED prediction only confirms its declared observable event; it does not prove the full plan.",
                ],
            }
        schema = experience.add_revision_hypothesis_schema(schema)
        write_json(codex_runner.OUT / "llm_evidence_context.json", evidence)
        write_json(codex_runner.OUT / "revision_output_schema.json", schema)
        prompt = build_prompt(evidence, schema)
    write_json(codex_runner.OUT / "milestone_constraints_resolution.json", constraint_resolution)
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


def build_prompt(evidence: dict[str, Any], schema: dict[str, Any] | None = None) -> str:
    prompt_only_metadata = {"codex_cli_run_policy", "decision_task", "provenance", "tactical_provider"}
    prompt_evidence = {key: value for key, value in evidence.items() if key not in prompt_only_metadata}
    stage_support = copy.deepcopy(prompt_evidence.get("stage_mechanism_support"))
    if isinstance(stage_support, dict):
        for row in stage_support.get("enemy_semantics") or []:
            if isinstance(row, dict):
                for field in ("counts_as_kill", "counts_as_leak", "death_life_point_reduce", "is_friendly"):
                    if isinstance(row.get(field), dict):
                        row[field] = {
                            key: value for key, value in row[field].items()
                            if key not in {"source_file", "source_path"}
                        }
        prompt_evidence["stage_mechanism_support"] = stage_support
    evidence_json = json.dumps(prompt_evidence, ensure_ascii=False, separators=(",", ":"))
    schema_json = json.dumps(schema or {}, ensure_ascii=False, separators=(",", ":"))
    schema_required = schema.get("required") if schema else []
    plan_schema = ((schema or {}).get("properties") or {}).get("revised_operational_plans", {}).get("items", {})
    plan_required = plan_schema.get("required") if plan_schema else []
    revision_required = (((schema or {}).get("properties") or {}).get("revision_hypothesis", {}) or {}).get("required", [])
    active = evidence["stage_active_facts"]
    forbidden_plan_tiles = active.get("roadblock_plan_tiles_row_col")
    if not isinstance(forbidden_plan_tiles, list):
        raise RuntimeError("stage_active_facts.roadblock_plan_tiles_row_col is required")
    protected_spawn_rows = [
        event for event in ((evidence.get("model_spawn_timeline") or {}).get("events") or [])
        if isinstance(event, dict) and isinstance(event.get("enemy_id"), str)
        and event["enemy_id"].startswith("enemy_3001_upeopl")
    ]
    expected_protected_target_count = sum(int(event.get("count", 1)) for event in protected_spawn_rows)
    roster_instruction = ""
    max_unique = evidence.get("milestone_constraints", {}).get("max_unique_deployed_operator_ids")
    if isinstance(max_unique, int):
        roster_instruction = (
            f"HARD ROSTER LIMIT: the union of selected_low_star_operator_ids and every DEPLOY action "
            f"operator_id must contain at most {max_unique} distinct IDs. Remove unused listed operators "
            "before emitting the plan; retreat/redeploy and hidden aliases do not avoid the count.\n\n"
        )
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

Only operators in `normal_low_star_catalog` are legal. Require `identity.rarity` 1-3 and `qualification.normal_mode == true`; exclude mode-specific reserve units. Every DEPLOY needs integer [row,col] and UP/DOWN/LEFT/RIGHT. `stage_active_facts.roadblock_tiles_col_row` is [col,row]; `stage_active_facts.roadblock_plan_tiles_row_col` is the exact JSON forbidden set. Never deploy on {json.dumps(forbidden_plan_tiles)}. WIN requires `remaining_life > 0`, zero leaks, exhausted spawns and no active enemies. Project acceptance additionally requires zero leaks, zero protected-target deaths, and all {expected_protected_target_count} expected protected targets safely reaching their objectives; operator deaths are recorded separately and are not automatically forbidden.

    {clearance_instruction}

    {roster_instruction}

MANDATORY OUTPUT CONTRACT
- Root required fields: {json.dumps(schema_required)}.
- revised_operational_plans[0] required fields: {json.dumps(plan_required)}.
- revision_hypothesis required fields: {json.dumps(revision_required)}.
- referenced_experience_ids must be a subset of evidence.tactical_experience.records[*].experience_id.
- mandatory_tactical_invariants entries must be objects, not strings.
- battle_phases must explain each phase goal, start/completion condition, duties, survival dependencies, handoffs and the consequence of that phase failing.
- parent_hypothesis_id must equal one of revised_strategic_hypotheses[*].hypothesis_id.
- action_timeline frames must be nondecreasing.

{"Revise the prior {STAGE_ID} candidate using the saved simulated failure evidence. Explain changed hypotheses in the plan, but do not preserve an action merely because it existed. Python/GLM will not choose tactics for you." if "prior_diagnostic_feedback" in evidence else "This is an initial {STAGE_ID} plan; do not copy R8-1 routes, deadlines, tactics or facts. Use only this stage's routes, spawn schedule, map, devices, enemies and mechanisms. Mark unresolved stage-specific mechanics UNKNOWN. You decide opening structure, route responsibilities, simultaneous blocking, fire support, healing, skills, retreats and economic order. Python/GLM will not choose tactics for you."}
{"IMPORTANT: prior_static_feedback is from the immediately preceding candidate and has battle_result_status=NO_SIMULATION. prior_diagnostic_feedback and prior_tactical_feedback come from their separately recorded source_plan_id values, not from the unexecuted static candidate. Resolve every prior static conflict exactly without letting Python alter tactical actions." if "prior_static_feedback" in evidence else ""}
{"IMPORTANT: prior_tactical_feedback is the verified causal history. Treat failed conditional economic dependencies as survival/handoff failures, not arithmetic bugs. Preserve demonstrated improvements only when the structure that produced them remains supported; redesign the opening survival, interception, protection, and clearance responsibilities yourself." if "prior_tactical_feedback" in evidence else ""}

Use read-only helper functions when needed to verify ranges, timing or mechanics. Do not attack or block neutral civilians with ordinary operators; remember enemy officers may attack civilians and civilian death costs objective life. Do not invent device navigation, target ordering, refunds, client timing or unsupported effects. Distinguish GameData facts, current-model rules and UNKNOWN. Do not repeat evidence prose. The compact evidence JSON follows:

EVIDENCE_JSON
{evidence_json}

OUTPUT_SCHEMA_JSON
{schema_json}
"""


def validate_final(parsed: Any, execution: dict[str, Any]) -> dict[str, Any]:
    evidence = load(codex_runner.OUT / "llm_evidence_context.json")
    schema = load(codex_runner.OUT / "revision_output_schema.json")
    errors: list[str] = []
    layered = validate_plan_payload(parsed, evidence, schema)
    errors.extend(f"schema: {error}" for error in layered["schema_errors"])
    errors.extend(f"semantic: {error}" for error in layered["semantic_errors"])
    errors.extend(f"event: {error}" for error in layered["event_query_errors"])
    errors.extend(f"lineage: {error}" for error in layered["lineage_errors"])
    if isinstance(parsed, dict):
        hypothesis = parsed.get("revision_hypothesis")
        if isinstance(hypothesis, dict):
            plans = parsed.get("revised_operational_plans")
            plan = plans[0] if isinstance(plans, list) and len(plans) == 1 else {}
            if hypothesis.get("operational_plan_id") != plan.get("operational_plan_id"):
                errors.append("revision_hypothesis.operational_plan_id must match revised_operational_plans[0]")
            experience_ids = {
                record.get("experience_id")
                for record in (evidence.get("tactical_experience") or {}).get("records") or []
            }
            missing_references = sorted(set(hypothesis.get("referenced_experience_ids") or []) - experience_ids)
            if missing_references:
                errors.append(f"revision_hypothesis references unavailable experiences: {missing_references}")
            expected = hypothesis.get("expected_first_observable_event") or {}
            if expected and expected.get("latest_frame", 0) < expected.get("earliest_frame", 0):
                errors.append("expected_first_observable_event latest_frame precedes earliest_frame")
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
        configured_limit = MAX_UNIQUE_DEPLOYED_OPERATORS
        evidence_limit_value = (evidence.get("milestone_constraints") or {}).get("max_unique_deployed_operator_ids")
        evidence_limit = evidence_limit_value if isinstance(evidence_limit_value, int) else None
        if configured_limit is not None and evidence_limit is not None and configured_limit != evidence_limit:
            errors.append(
                f"roster-limit conflict: configured={configured_limit}, evidence={evidence_limit}"
            )
        effective_limit = configured_limit if configured_limit is not None else evidence_limit
        if effective_limit is not None:
            distinct = distinct_deployed_operator_ids(plan)
            if len(distinct) > effective_limit:
                errors.append(
                    f"distinct selected/deployed operator union has {len(distinct)} IDs; hard limit is {effective_limit}"
                )
    validation = {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_PLAN_VALIDATION",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "layers": layered,
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
        if BRANCH_STATE_PATH is not None:
            branch_path = ROOT / BRANCH_STATE_PATH
            parent_plan_id = layered["previous_plan_id"] or "UNKNOWN_PARENT_PLAN"
            branch_state = experience.update_branch_state(load(branch_path), {
                "candidate_id": PLAN_ID,
                "parent_plan_id": parent_plan_id or "UNKNOWN_PARENT_PLAN",
                "operational_plan_id": PLAN_ID,
                "classification": "A_CONTRACT_INVALID",
                "stage_id": STAGE_ID,
                "mechanics_version": ACTIVE_MECHANICS_VERSION,
                "objective_scope": {"win": False},
                "revision_hypothesis": parsed.get("revision_hypothesis") or {},
                "validation_status": "FAIL",
                "errors": errors,
                "invalid_plan_artifact_sha256": sha256(codex_runner.OUT / "invalid_final_plan.json.parsed"),
            })
            write_json(branch_path, branch_state)
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
    result = compile_plan(codex_runner.OUT)
    if result.get("conflicts") and BRANCH_STATE_PATH is not None:
        branch_path = ROOT / BRANCH_STATE_PATH
        branch_state = experience.update_branch_state(load(branch_path), {
            "candidate_id": PLAN_ID,
            "parent_plan_id": experience.extract_parent_plan_id(load(codex_runner.OUT / "llm_structured_output.json")) or "UNKNOWN_PARENT_PLAN",
            "operational_plan_id": PLAN_ID,
            "classification": "B_STATIC_CONFLICT",
            "stage_id": STAGE_ID,
            "mechanics_version": ACTIVE_MECHANICS_VERSION,
            "objective_scope": {"win": False},
            "revision_hypothesis": (load(codex_runner.OUT / "llm_structured_output.json") or {}).get("revision_hypothesis") or {},
            "static_conflicts": result["conflicts"],
        })
        write_json(branch_path, branch_state)
    return result


def load_or_init_branch_state(path: Path) -> dict[str, Any]:
    if path.is_file():
        return load(path)
    return {
        "schema_version": experience.BRANCH_SCHEMA_VERSION,
        "stage_id": STAGE_ID,
        "frozen_baselines": {},
        "candidates": [],
    }


def simulate() -> dict[str, Any]:
    from run_gpt_tactical_stage_diagnostic_v1 import run_full_diagnostic

    static = load(codex_runner.OUT / "static_compile_results.json")
    if static["conflicts"]:
        write_json(codex_runner.OUT / "static_compile_execution_gate.json", {
            "status": "BLOCKED_STATIC_CONFLICT", "conflicts": static["conflicts"],
        })
        raise SystemExit(f"{PLAN_LABEL} static conflicts block diagnostic simulation")
    with gate.consume_evaluation(
        source_dir=codex_runner.OUT, diagnostic_output_dir=codex_runner.DIAGNOSTIC_OUT,
        budget_path=SIMULATION_BUDGET_PATH, stage_id=STAGE_ID, expected_plan_id=PLAN_ID,
    ) as evaluation_gate:
        if evaluation_gate["status"] != "AUTHORIZED":
            return evaluation_gate
        run_full_diagnostic(
            source=codex_runner.OUT, out=codex_runner.DIAGNOSTIC_OUT,
            stage_id=STAGE_ID, plan_id=PLAN_ID,
        )
    summary = load(codex_runner.DIAGNOSTIC_OUT / "diagnostic_summary.json")
    events = load(codex_runner.DIAGNOSTIC_OUT / "diagnostic_events.json").get("events") or []
    parsed = load(codex_runner.OUT / "llm_structured_output.json")
    plans = parsed.get("revised_operational_plans") if isinstance(parsed, dict) else None
    plan = plans[0] if isinstance(plans, list) and len(plans) == 1 and isinstance(plans[0], dict) else None
    manifest_path = codex_runner.DIAGNOSTIC_OUT / "manifest.json"
    attempt_path = codex_runner.DIAGNOSTIC_OUT / "simulation_attempt.json"
    observation_complete = (
        manifest_path.is_file() and attempt_path.is_file()
        and load(attempt_path).get("status") == "COMPLETED"
        and load(attempt_path).get("result_saved") is True
    )
    hypothesis_evaluation = experience.evaluate_revision_hypothesis(
        parsed, events, observation_complete=observation_complete
    )
    runtime_action_errors = summary.get("result", {}).get("deployment_errors") or []
    evidence = load(codex_runner.OUT / "llm_evidence_context.json")
    parent_plan = evidence.get("previous_plan_to_revise")
    parent_plan_id = experience.extract_operational_plan_id(parent_plan) or "UNKNOWN_PARENT_PLAN"
    expected_protected_target_count = evaluation_gate["expected_protected_target_count"]
    protected_result = {
        "win": summary["result"]["win"],
        "enemies_leaked": summary["result"].get("enemies_leaked"),
        "protected_target_deaths": len(summary.get("protected_target_deaths") or []),
        "protected_targets_reached": len(summary.get("protected_target_reached_events") or []),
    }
    scope = experience.objective_scope(
        protected_result, expected_protected_target_count=expected_protected_target_count
    )
    write_json(codex_runner.OUT / "revision_hypothesis_evaluation.json", hypothesis_evaluation)
    write_json(codex_runner.OUT / "simulation_gate.json", {
        "schema_version": "GPT_TACTICAL_STAGE_SESSION_V1_SIMULATION_GATE",
        "status": "COMPLETED", "result_classification": summary["classification"],
        "faithful_certificate": summary["faithful_certificate"],
        "simulator_win": summary["result"]["win"],
        "objective_scope": scope,
        "runtime_action_errors": runtime_action_errors,
        "targeting_variant_results": "NOT_EVALUATED_UNLESS_SEPARATELY_FROZEN",
        "faithful_certificate_status": summary["faithful_certificate"].get("status") if isinstance(summary.get("faithful_certificate"), dict) else "UNKNOWN",
        "real_game_status": "NOT_PLAYED",
        "real_game_win_claim": False,
        "revision_hypothesis_evaluation": hypothesis_evaluation,
    })
    if BRANCH_STATE_PATH is not None:
        branch_path = ROOT / BRANCH_STATE_PATH
        branch_state = experience.update_branch_state(load_or_init_branch_state(branch_path), {
            "candidate_id": PLAN_ID,
            "parent_plan_id": parent_plan_id,
            "operational_plan_id": PLAN_ID,
            "classification": experience.classify_candidate(
                validation=load(codex_runner.OUT / "llm_plan_validation.json"),
                static_conflicts=static.get("conflicts") or [],
                simulation_gate=load(codex_runner.OUT / "simulation_gate.json"),
            ),
            "stage_id": STAGE_ID,
            "mechanics_version": ACTIVE_MECHANICS_VERSION,
            "objective_scope": scope,
            "revision_hypothesis": parsed.get("revision_hypothesis") or {},
            "hypothesis_evaluation": hypothesis_evaluation,
            "plan_snapshot_sha256": sha256(codex_runner.DIAGNOSTIC_OUT / "plan_snapshot.json"),
            "action_snapshot_sha256": sha256(codex_runner.DIAGNOSTIC_OUT / "action_snapshot.json"),
            "action_count": len(plan.get("action_timeline") or []) if isinstance(plan, dict) else None,
            "result": {
                "win": summary["result"]["win"],
                "enemies_killed": summary["result"].get("enemies_killed"),
                "enemies_leaked": summary["result"].get("enemies_leaked"),
                "operator_deaths": summary["result"].get("operator_deaths"),
                "runtime_action_errors": runtime_action_errors,
                "protected_target_deaths": len(summary.get("protected_target_deaths") or []),
                "protected_targets_reached": len(summary.get("protected_target_reached_events") or []),
            },
        })
        write_json(branch_path, branch_state)
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
    parser.add_argument("--experience-store")
    parser.add_argument("--branch-state")
    parser.add_argument("--max-unique-deployed-operators", type=int)
    parser.add_argument("--authorization-config", default=str(AUTHORIZATION_CONFIG_PATH))
    parser.add_argument("--simulation-budget-path", default=str(SIMULATION_BUDGET_PATH))
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
