from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
from time import time
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_llm_tactical_context_v1"
RECON = ROOT / "output/r8_1_tactical_requirement_reconstruction_v1"
COUPLING = ROOT / "output/r8_1_assignment_spatial_timing_coupling_v1"
FIDELITY = ROOT / "output/operator_runtime_fidelity_v1/all_operator_fidelity.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def compact_operator_summary(engine, fidelity_by_id: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for operator_id, operator in sorted(engine.fixture.operators.items()):
        stats = operator.phases[0].stats_max
        skill = operator.synthetic_skill
        fidelity = fidelity_by_id.get(operator_id, {})
        rows.append({
            "operator_id": operator_id,
            "rarity": int(operator.star_rarity.value or 0),
            "profession": operator.profession.value,
            "position": operator.position.value,
            "cost": float(stats.cost.value or 0),
            "block_count": int(stats.block_count.value or 0),
            "hp": float(stats.max_hp.value or 0),
            "attack": float(stats.atk.value or 0),
            "defense": float(stats.defense.value or 0),
            "resistance": float(stats.magic_resistance.value or 0),
            "attack_interval_seconds": float(stats.attack_interval.value or 0),
            "redeploy_seconds": float(operator.redeploy_time.value or 0),
            "attack_range_cells": sorted([list(cell) for cell in (operator.attack_range or ())]),
            "skill_supported": skill is not None,
            "skill_auto_activate": bool(skill and skill.auto_activate),
            "skill_recovery_mode": skill.recovery_mode.value if skill else None,
            "skill_initial_sp": float(skill.initial_sp) if skill else None,
            "skill_sp_cost": float(skill.sp_cost) if skill else None,
            "skill_effect": asdict(skill.effect) if skill else None,
            "planner_safe_for_basic_attack": fidelity.get("planner_safe_for_basic_attack"),
            "planner_safe_for_selected_skills": fidelity.get("planner_safe_for_selected_skills"),
            "operator_fidelity_overall": fidelity.get("overall"),
        })
    return rows


def build_context() -> tuple[dict[str, Any], dict[str, Any]]:
    from arknights_planner.adapters import (
        ApproximateRealSimulationAdapter,
        RealSimulationApproximationPolicy,
    )
    from arknights_planner.gamedata import GameDataRepository
    from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig
    from arknights_planner.search.stage_understanding import StageUnderstandingAnalyzer

    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    pool = adapter.all_executable_phase_zero_configurations()
    engine = M11MinimumSquadSearch(
        adapter=adapter,
        stage_id_or_code="main_08-01",
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        operator_pool=pool,
        config=M11SearchConfig(
            beam_width=1,
            placement_options_per_operator=12,
            max_squad_size=12,
            max_teams=1,
        ),
    )
    understanding = StageUnderstandingAnalyzer().analyze(engine.fixture)
    fidelity_payload = load(FIDELITY)
    fidelity_by_id = {item["operator_id"]: item for item in fidelity_payload["operators"]}

    clusters_payload = load(RECON / "route_pressure_clusters.json")
    windows_payload = load(RECON / "pressure_windows.json")
    static_atoms_payload = load(RECON / "tactical_requirement_atoms.json")
    threat_payload = load(COUPLING / "early_threat_model.json")
    experiment_payload = load(RECON / "representative_requirement_experiment.json")
    coupling_final = load(COUPLING / "final_status.json")

    stage = engine.fixture.stage
    coverage_candidates = []
    for opportunity in sorted(
        understanding.coverage_opportunities,
        key=lambda item: (-len(item.route_ids), item.tile),
    ):
        if opportunity.tile_kind != "HIGH_GROUND":
            continue
        coverage_candidates.append({
            "tile": list(opportunity.tile),
            "route_ids": list(opportunity.route_ids),
            "route_count": len(opportunity.route_ids),
            "shared": bool(opportunity.shared),
            "operator_count_compatible_with_tile": len(opportunity.operator_ids),
            "covered_cells": sorted([list(cell) for cell in opportunity.covered_cells]),
        })

    prior_failures = {
        "formal_search_902_timelines": {
            "best": coupling_final["NEW_BEST"],
            "first_leak_seconds": coupling_final.get("NEW_BEST", {}).get("time_survived") and None,
            "observed_leak_routes": threat_payload["observed_fresh_best_leak_routes"],
        },
        "representative_requirement_experiment": experiment_payload["summary"],
    }
    # The old formal artifact exposed first-leak time in its failure diagnosis; preserve it explicitly.
    formal_raw = load(COUPLING / "full_search_raw.json")
    prior_failures["formal_search_902_timelines"]["first_leak_seconds"] = formal_raw["generation1"]["failure_diagnosis"]["first_leak_time"]

    context = {
        "schema_version": "R8_1_LLM_TACTICAL_CONTEXT_V1",
        "architecture_contract": {
            "llm_owns": ["StageUnderstanding", "TacticalRequirements", "tactical interpretation", "PlanHypotheses", "failure interpretation", "high-level revision"],
            "deterministic_owns": ["facts", "exact values", "legal enumeration", "feasibility", "lowering", "simulation", "counterexamples"],
            "static_requirement_atoms_are_prior_analysis_not_truth": True,
            "exact_frames_and_costs_may_be_reused_but_not_invented": True,
            "no_per_timeline_or_per_frame_llm_calls": True,
        },
        "target": {"stage_id": stage.stage_id, "stage_code": stage.code.value, "mechanics_version": "m18.9-stage-device-runtime-v1"},
        "stage_facts": {
            "map_dimensions": list(understanding.map_dimensions),
            "initial_cost": understanding.initial_dp,
            "cost_recovery_per_second": understanding.dp_per_second,
            "deployment_limit": understanding.deployment_limit,
            "squad_size_limit": understanding.squad_size_limit,
            "life_points": stage.initial_life,
            "spawn_count": understanding.spawn_count,
            "deployable_ground_tiles": sorted([list(item) for item in understanding.deployable_ground]),
            "deployable_high_ground_tiles": sorted([list(item) for item in understanding.deployable_high_ground]),
            "enemy_archetypes": [asdict(item) for item in understanding.enemy_archetypes],
            "physical_pressure": understanding.physical_pressure,
            "arts_pressure": understanding.arts_pressure,
            "blocking_pressure": understanding.blocking_pressure,
            "sustain_pressure": understanding.sustain_pressure,
            "dp_economy_pressure": understanding.dp_economy_pressure,
            "provenance": understanding.provenance,
            "approximations": list(understanding.approximations),
        },
        "route_pressure_clusters": clusters_payload,
        "pressure_windows": windows_payload,
        "exact_route_threats": {
            "frame_clock": threat_payload["frame_clock"],
            "routes": threat_payload["routes"],
            "provenance": threat_payload["provenance"],
        },
        "candidate_interception_regions": [
            {
                "cluster_id": cluster["cluster_id"],
                "route_ids": cluster["member_route_ids"],
                "tiles": [item["tile"] for item in cluster["candidate_interception_regions"]],
            }
            for cluster in clusters_payload["clusters"]
        ],
        "candidate_shared_coverage_regions": coverage_candidates,
        "stage_devices": [
            {
                "device_id": device.device_id,
                "template_id": device.template_id,
                "tile": list(device.tile),
                "hp": device.hp,
                "defense": device.defense,
                "resistance": device.magic_resistance,
                "taunt_level": device.taunt_level,
                "ordinary_targetable": device.ordinary_targetable,
                "faction": device.faction,
            }
            for device in stage.devices
        ],
        "prior_static_requirement_atoms": {
            "status": "ANALYSIS_ONLY_NOT_TACTICAL_TRUTH",
            "atoms": static_atoms_payload["atoms"],
        },
        "prior_simulator_failures": prior_failures,
        "operators": compact_operator_summary(engine, fidelity_by_id),
    }

    request_payload = {
        "task": (
            "Construct a structured R8-1 StageUnderstanding and TacticalRequirements, then generate 6-12 materially "
            "different PlanHypotheses. Use deterministic facts and source-backed values only. Semantic concepts may omit "
            "exact coordinates; deterministic lowering will enumerate legal realizations. Do not invent frames, costs, "
            "stats, ranges, tile legality, enemy mechanics, or unsupported tactics."
        ),
        "output_contract": {
            "return_only_json": True,
            "top_level_keys": ["stage_understanding", "tactical_requirements", "plan_hypotheses"],
            "stage_understanding_required_keys": ["observations", "interpretations", "tactical_assumptions"],
            "tactical_requirement_fields": [
                "requirement_id", "family", "clusters", "pressure_windows", "where", "when", "why",
                "capability", "necessity", "shareable", "evidence_refs",
            ],
            "necessity_values": ["HARD", "CONDITIONAL", "OPTIONAL"],
            "plan_hypothesis_fields": [
                "hypothesis_id", "summary", "reasoning", "target_cardinality", "tactical_archetype",
                "required_capabilities", "preferred_operator_ids", "alternative_operator_ids",
                "placement_intents", "deployment_order", "skill_use_intents", "retreat_redeploy_intents",
                "operator_responsibilities", "confidence",
            ],
            "hypothesis_count": {"minimum": 6, "maximum": 12},
            "diversity_requirement": "Hypotheses must differ in tactical thesis or formation evolution, not only operator choices.",
        },
        "deterministic_context": context,
    }
    return context, request_payload


def provider_configuration() -> dict[str, str]:
    return {
        "OPENAI_API_KEY": "PRESENT" if os.getenv("OPENAI_API_KEY") else "ABSENT",
        "OPENAI_BASE_URL": "PRESENT" if os.getenv("OPENAI_BASE_URL") else "ABSENT",
        "OPENAI_MODEL": "PRESENT" if os.getenv("OPENAI_MODEL") else "ABSENT",
        "ARK_MODEL_ID": "PRESENT" if os.getenv("ARK_MODEL_ID") else "ABSENT",
    }


def one_llm_call(request_payload: dict[str, Any], *, timeout_seconds: float = 60.0) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    endpoint = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL") or os.getenv("ARK_MODEL_ID")
    api_key = os.getenv("OPENAI_API_KEY")
    missing = [name for name, value in (
        ("OPENAI_API_KEY", api_key), ("OPENAI_BASE_URL", endpoint),
        ("OPENAI_MODEL/ARK_MODEL_ID", model),
    ) if not value]
    if missing:
        return None, {
            "status": "REAL_LLM_BLOCKED_BY_ENVIRONMENT",
            "calls_attempted": 0,
            "missing_configuration": missing,
            "configuration": provider_configuration(),
            "note": "No alternative endpoint or model was guessed; no fabricated LLM output was created.",
        }
    system = (
        'Return ONLY machine-readable JSON with top-level keys "stage_understanding", "tactical_requirements", and '
        '"plan_hypotheses". Use supplied deterministic facts only. Do not simulate or select exact deployment frames.'
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(request_payload, ensure_ascii=False)}],
        "temperature": 0,
        "stream": False,
    }).encode()
    request = Request(endpoint.rstrip("/") + "/chat/completions", data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
    }, method="POST")
    started = time()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
        envelope = json.loads(raw.decode())
        content = envelope["choices"][0]["message"]["content"]
        if content.strip().startswith("```"):
            content = content.strip().removeprefix("```").split("\n", 1)[-1].rsplit("```", 1)[0]
        payload = json.loads(content)
        return payload, {
            "status": "SUCCESS",
            "calls_attempted": 1,
            "elapsed_seconds": time() - started,
            "model": model,
            "endpoint": endpoint,
        }
    except Exception as exc:
        return None, {
            "status": "REAL_LLM_CALL_FAILED",
            "calls_attempted": 1,
            "elapsed_seconds": time() - started,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "configuration": provider_configuration(),
        }


def validate_llm_output(context: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
    from arknights_planner.agent.tactical import PlanHypothesis, hypothesis_schema_diagnostics

    if payload is None:
        return {"status": "NOT_RUN", "reason": "No real LLM payload was returned."}
    errors: list[str] = []
    hypotheses_raw = payload.get("plan_hypotheses")
    if not isinstance(hypotheses_raw, list) or not 6 <= len(hypotheses_raw) <= 12:
        errors.append("PLAN_HYPOTHESIS_COUNT_OUT_OF_RANGE")
    parsed_hypotheses = []
    schema_diagnostics = hypothesis_schema_diagnostics({"hypotheses": hypotheses_raw or []})
    for index, item in enumerate(hypotheses_raw or []):
        try:
            parsed_hypotheses.append(PlanHypothesis.from_dict(item).to_dict() if hasattr(PlanHypothesis, "to_dict") else asdict(PlanHypothesis.from_dict(item)))
        except Exception as exc:
            errors.append(f"HYPOTHESIS_{index}_SCHEMA_ERROR:{exc}")
    known_operators = {item["operator_id"] for item in context["operators"]}
    known_routes = {route_id for item in context["exact_route_threats"]["routes"] for route_id in [item["route_id"]]}
    known_clusters = {item["cluster_id"] for item in context["route_pressure_clusters"]["clusters"]}
    known_windows = {item["window_id"] for item in context["pressure_windows"]["windows"]}
    for index, hypothesis in enumerate(parsed_hypotheses):
        for field in ("preferred_operator_ids", "alternative_operator_ids", "deployment_order"):
            unknown = sorted(set(hypothesis.get(field, ())) - known_operators)
            if unknown:
                errors.append(f"HYPOTHESIS_{index}_{field}_UNKNOWN_OPERATORS:{','.join(unknown)}")
        if len(set(hypothesis.get("deployment_order", ()))) != len(hypothesis.get("deployment_order", ())):
            errors.append(f"HYPOTHESIS_{index}_DUPLICATE_DEPLOYMENT_ORDER")
    for index, requirement in enumerate(payload.get("tactical_requirements", []) if isinstance(payload.get("tactical_requirements"), list) else []):
        unknown_clusters = sorted(set(requirement.get("clusters", ())) - known_clusters)
        unknown_windows = sorted(set(requirement.get("pressure_windows", ())) - known_windows)
        unknown_routes = sorted(set(requirement.get("route_ids", ())) - known_routes)
        if unknown_clusters:
            errors.append(f"REQUIREMENT_{index}_UNKNOWN_CLUSTERS:{','.join(unknown_clusters)}")
        if unknown_windows:
            errors.append(f"REQUIREMENT_{index}_UNKNOWN_WINDOWS:{','.join(unknown_windows)}")
        if unknown_routes:
            errors.append(f"REQUIREMENT_{index}_UNKNOWN_ROUTES:{','.join(unknown_routes)}")
        if requirement.get("necessity") not in {"HARD", "CONDITIONAL", "OPTIONAL"}:
            errors.append(f"REQUIREMENT_{index}_INVALID_NECESSITY")
        if not requirement.get("evidence_refs"):
            errors.append(f"REQUIREMENT_{index}_MISSING_EVIDENCE_REFS")
    understanding = payload.get("stage_understanding")
    if not isinstance(understanding, dict) or not all(
        isinstance(understanding.get(key), list) and understanding.get(key)
        for key in ("observations", "interpretations", "tactical_assumptions")
    ):
        errors.append("STAGE_UNDERSTANDING_MISSING_SEMANTIC_SECTIONS")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "hypothesis_schema_diagnostics": schema_diagnostics,
        "accepted_hypotheses": parsed_hypotheses,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    context, request_payload = build_context()
    write("deterministic_context.json", context)
    write("architecture_audit.json", {
        "audit_version": "LLM_TACTICAL_REASONING_ARCHITECTURE_REALIGNMENT_V1",
        "principle": "LLM owns tactical intent and revision; deterministic code owns facts, enumeration, verification, lowering, and simulation.",
        "records": [
            {"component": "arknights_planner/search/stage_understanding.py:derive_tactical_requirements", "classification": "MOVE_TO_LLM_REASONING", "reason": "Hard-coded requirement semantics become static tactical rules."},
            {"component": "arknights_planner/search/tactical_demand.py:build_tactical_requirement_atoms", "classification": "MOVE_TO_LLM_REASONING", "reason": "Cluster/window analysis is factual, but the function also selects requirement families and necessity."},
            {"component": "arknights_planner/search/top_down.py:DeterministicHypothesisGenerator.generate_hypotheses", "classification": "MOVE_TO_LLM_REASONING", "reason": "Chooses tactical archetypes and formation intent; deterministic enumeration should not own this."},
            {"component": "arknights_planner/search/tactical_realizability.py:TacticalRealizabilityAnalyzer._revise_hypothesis", "classification": "MOVE_TO_LLM_REASONING", "reason": "Automatically revises tactical intent; should instead return contradictions for LLM revision."},
            {"component": "arknights_planner/search/tactical_demand.py:build_route_pressure_clusters", "classification": "KEEP_AS_ANALYSIS", "reason": "Groups routes using exact waypoint geometry; output is a fact."},
            {"component": "arknights_planner/search/tactical_demand.py:build_pressure_windows", "classification": "KEEP_AS_ANALYSIS", "reason": "Groups expanded spawn timing using measured stage facts."},
            {"component": "arknights_planner/search/operator_assignment.py:OperatorAssignmentEngine.assign", "classification": "KEEP_AS_VERIFIER", "reason": "Enumerates operator-capability mappings for supplied requirements; should not create requirements."},
            {"component": "arknights_planner/search/temporal_assignment.py:build_temporal_assignment_frontier", "classification": "KEEP_AS_VERIFIER", "reason": "Checks temporal, DP, overload, and coverage feasibility."},
            {"component": "arknights_planner/search/responsibility_feasibility.py", "classification": "KEEP_AS_VERIFIER", "reason": "Provides exact route/geometry/deadline certificates."},
            {"component": "arknights_planner/search/spatial_timing.py:generate_skeletons", "classification": "KEEP_AS_VERIFIER", "reason": "Enumerates legal semantic spatial realizations."},
            {"component": "arknights_planner/search/spatial_timing.py:generate_timing_candidates", "classification": "KEEP_AS_VERIFIER", "reason": "Enumerates bounded event-relative timing candidates."},
            {"component": "arknights_planner/simulator/simulator.py", "classification": "KEEP_AS_VERIFIER", "reason": "Executes and emits exact runtime counterexamples; does not own strategy."},
        ],
    })
    write("llm_request_payload.json", request_payload)
    llm_payload, call_summary = one_llm_call(request_payload)
    write("llm_call_summary.json", call_summary)
    if llm_payload is not None:
        write("llm_structured_output.json", llm_payload)
    grounding = validate_llm_output(context, llm_payload)
    write("grounding_validation.json", grounding)
    write("final_status.json", {
        "milestone": "R8_1_LLM_TACTICAL_CONTEXT_V1",
        "target": "main_08-01 / R8-1",
        "architecture_audit_complete": True,
        "deterministic_context_complete": True,
        "llm_call_attempted": call_summary.get("calls_attempted", 0) > 0,
        "llm_call_status": call_summary.get("status"),
        "llm_output_accepted": grounding.get("status") == "PASS",
        "tactical_search_run": False,
        "stop_rule_reached": True,
    })


if __name__ == "__main__":
    main()
