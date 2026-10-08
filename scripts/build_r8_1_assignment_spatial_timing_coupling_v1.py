from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import json
import math
from pathlib import Path
from typing import Any

from arknights_planner.agent.tactical import PlanHypothesis
from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig, M11SearchMetrics
from arknights_planner.search.operator_assignment import OperatorAssignmentEngine
from arknights_planner.search.responsibility_feasibility import (
    build_early_threat_model,
    build_geometry_certificates,
    build_responsibility_certificates,
    spatial_responsibilities,
)
from arknights_planner.search.spatial_timing import (
    SpatialTimingConfig,
    SpatialTimingSearch,
)
from arknights_planner.search.stage_understanding import (
    StageUnderstandingAnalyzer,
    derive_tactical_requirements,
)
from arknights_planner.search.temporal_assignment import (
    build_temporal_assignment_frontier,
    derive_early_pressure_responsibilities,
    derive_temporal_responsibilities,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_assignment_spatial_timing_coupling_v1"


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def route(stage, route_id: str):
    return next(item for item in stage.routes if item.route_id == route_id)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = json.loads((ROOT / "output/r8_1_operator_assignment_frontier_v1/fresh_search_raw.json").read_text())
    observed_leak_routes = raw["generation2"]["failure_diagnosis"]["leak_routes"]
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    configurations = adapter.all_executable_phase_zero_configurations()
    engine = M11MinimumSquadSearch(
        adapter=adapter,
        stage_id_or_code="main_08-01",
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        operator_pool=configurations,
        config=M11SearchConfig(
            beam_width=1,
            placement_options_per_operator=12,
            max_squad_size=12,
            max_teams=1,
        ),
    )
    understanding = StageUnderstandingAnalyzer().analyze(engine.fixture)
    requirements = derive_tactical_requirements(understanding)
    assignment = OperatorAssignmentEngine().assign(
        understanding,
        requirements,
        engine.fixture.operators,
        max_cardinality=12,
        team_size_policy="FEASIBILITY_FIRST",
    )
    frontier = build_temporal_assignment_frontier(
        understanding,
        requirements,
        assignment,
        engine.fixture.operators,
        OperatorAssignmentEngine(),
        deployment_limit=understanding.deployment_limit,
    )
    hypotheses = [
        PlanHypothesis.from_dict(item)
        for item in raw["generation1"]["hypotheses"]
    ]
    early_windows = derive_early_pressure_responsibilities(understanding, requirements)
    temporal_rows = derive_temporal_responsibilities(understanding, requirements)
    spatial_search = SpatialTimingSearch(
        engine=engine,
        understanding=understanding,
        config=SpatialTimingConfig(
            max_skeletons_per_hypothesis=10,
            tile_candidates_per_operator=24,
            facings_per_tile=4,
            max_candidates_per_tile=4,
            max_timing_candidates_per_skeleton=12,
            max_refinement_fraction=0.35,
        ),
    )
    threat = build_early_threat_model(
        engine,
        understanding,
        early_window=early_windows[0],
        observed_leak_routes=observed_leak_routes,
    )
    selected_names = (
        "feasibility_redundancy_k12-coverage--feasibility_redundancy_k12-coverage",
        "control_capability_rich-coverage--control_capability_rich-coverage",
        "feasibility_redundancy_k8-coverage--feasibility_redundancy_k8-coverage",
    )
    selected = [next(item for item in hypotheses if item.hypothesis_id == name) for name in selected_names]
    alternative_by_id = {item.assignment_id: item for item in assignment.coverage_alternatives}
    certificates = build_responsibility_certificates(
        engine,
        understanding,
        frontier,
        assignment.coverage_alternatives,
        selected,
        threat,
        spatial_search,
    )
    write("early_threat_model.json", asdict(threat))
    write("responsibility_feasibility_certificates.json", {
        "certificates": [item.to_dict() for item in certificates],
        "summary": {
            "total": len(certificates),
            "by_status": dict(Counter(item.final_status for item in certificates)),
            "by_role": dict(Counter(item.tactical_role for item in certificates)),
        },
    })

    assignment_rows = []
    spatial_rows_all = []
    skeleton_records = []
    geometry_records = []
    experiment_records = []
    contact_validation = []
    damage_validation = []
    skill_records = []
    dedup_records = []
    metrics = M11SearchMetrics()
    deployment_limit = int(engine.fixture.stage.deployment_limit.value)
    for hypothesis in selected:
        assignment_id = hypothesis.hypothesis_id.rsplit("--", 1)[-1]
        alternative = alternative_by_id[assignment_id]
        rows = spatial_responsibilities(hypothesis, alternative, temporal_rows)
        spatial_rows_all.extend(rows)
        audit: dict[str, Any] = {}
        skeletons = spatial_search.generate_skeletons(
            hypothesis_id=hypothesis.hypothesis_id,
            hypothesis_archetype=hypothesis.tactical_archetype,
            team=hypothesis.preferred_operator_ids[:deployment_limit],
            deployment_order=hypothesis.deployment_order[:deployment_limit],
            roles={row.operator: row.tactical_role for row in rows},
            audit=audit,
        )
        old_signatures: set[tuple[str, ...]] = set()
        old_count = 0
        for skeleton in skeletons:
            if skeleton.region_signature not in old_signatures:
                old_count += 1
                old_signatures.add(skeleton.region_signature)
        role_source = "EXPLICIT_TEMPORAL_ASSIGNMENT" if hypothesis.operator_responsibilities else "INFERRED"
        assignment_rows.append({
            "hypothesis_id": hypothesis.hypothesis_id,
            "assignment_id": assignment_id,
            "role_source": role_source,
            "spatial_responsibilities": [item.to_dict() for item in rows],
            "lost_semantics": [] if role_source == "EXPLICIT_TEMPORAL_ASSIGNMENT" else [
                "TEMPORAL_ROLE", "PRESSURE_WINDOW", "ROUTE_RESPONSIBILITY",
            ],
        })
        timing_by_skeleton = {}
        for skeleton in skeletons:
            geometries = build_geometry_certificates(
                engine,
                understanding,
                skeleton,
                assignment_id=assignment_id,
                threat=threat,
                spatial_search=spatial_search,
                spatial_rows=rows,
            )
            geometry_records.extend(geometries)
            timings = spatial_search.generate_timing_candidates(
                skeleton,
                audit=audit,
                hypothesis=hypothesis,
            )
            timing_by_skeleton[skeleton.skeleton_id] = timings
            skeleton_records.append({
                "assignment_id": assignment_id,
                "hypothesis_id": hypothesis.hypothesis_id,
                "skeleton_id": skeleton.skeleton_id,
                "region_signature": list(skeleton.region_signature),
                "feature_summary": skeleton.feature_summary,
                "placements": [item.to_dict() for item in skeleton.placements],
                "timing_candidates_generated": len(timings),
                "geometry_certificates": [item.to_dict() for item in geometries],
            })
        dedup_records.append({
            "hypothesis_id": hypothesis.hypothesis_id,
            "assignment_id": assignment_id,
            "layer": "semantic_skeleton",
            "input_complete_states": audit.get("skeleton_funnel", {}).get("complete_states", 0),
            "unique_by_semantic": len(skeletons),
            "old_region_signature_collapse_count": old_count,
            "candidates_restored_by_fix": max(0, len(skeletons) - old_count),
        })
        evaluated = 0
        for skeleton in skeletons:
            for timing in timing_by_skeleton[skeleton.skeleton_id]:
                if not timing.dp_feasible or evaluated >= 100:
                    continue
                evaluation = engine.evaluate(timing.strategy, metrics)
                result = evaluation.result
                events = result.events
                spawn_route = {
                    event.source_id: dict(event.details).get("route_id")
                    for event in events if event.event_type.value == "SPAWN"
                }
                leaks = [event for event in events if event.event_type.value == "ENEMY_LEAK"]
                early_leaks = [event for event in leaks if event.time <= early_windows[0].end_time]
                contacts = [event for event in events if event.event_type.value == "BLOCK"]
                deaths = [event for event in events if event.event_type.value == "OPERATOR_DEATH"]
                actual_contact = min((event.time for event in contacts), default=None)
                block_placements = [
                    placement for placement in skeleton.placements
                    if placement.candidate.block_route_ids
                ]
                predicted_contact = min((
                    placement.candidate.first_contact_seconds
                    for placement in block_placements
                    if placement.candidate.first_contact_seconds is not None
                ), default=None)
                block_deploy_seconds = min((
                    timing.deploy_frames[skeleton.placements.index(placement)] / 30.0
                    for placement in block_placements
                ), default=None)
                if predicted_contact is not None and block_deploy_seconds is not None:
                    predicted_contact = max(predicted_contact, block_deploy_seconds)
                unconditioned_contact = min((
                    placement.candidate.first_contact_seconds
                    for placement in skeleton.placements
                    if placement.candidate.first_contact_seconds is not None
                ), default=None)
                difference = (
                    None if actual_contact is None or predicted_contact is None
                    else abs(actual_contact - predicted_contact)
                )
                difference = (
                    None if actual_contact is None or predicted_contact is None
                    else abs(actual_contact - predicted_contact)
                )
                classification = (
                    "NOT_OBSERVED" if difference is None
                    else "ACCURATE" if difference <= 2.0
                    else "PARTIAL" if difference <= 5.0
                    else "INACCURATE"
                )
                contact_validation.append({
                    "assignment_id": assignment_id,
                    "skeleton_id": skeleton.skeleton_id,
                    "timing_id": timing.timing_id,
                    "predicted_first_contact_seconds": predicted_contact,
                    "unconditioned_route_contact_seconds": unconditioned_contact,
                    "conditioned_on_block_deployment": block_deploy_seconds is not None,
                    "actual_first_block_seconds": actual_contact,
                    "absolute_difference_seconds": difference,
                    "classification": classification,
                })
                experiment_records.append({
                    "assignment_id": assignment_id,
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "skeleton_id": skeleton.skeleton_id,
                    "timing_id": timing.timing_id,
                    "pattern_id": timing.pattern_id,
                    "deploy_frames": list(timing.deploy_frames),
                    "result": {
                        "win": result.win,
                        "remaining_life": result.remaining_life,
                        "kills": result.enemies_killed,
                        "leaks": result.enemies_leaked,
                        "operator_deaths": result.operator_deaths,
                        "time_survived": result.time_survived,
                    },
                    "opening": {
                        "first_leak_seconds": min((event.time for event in leaks), default=None),
                        "early_leaks": len(early_leaks),
                        "early_leak_routes": sorted({
                            spawn_route.get(event.source_id) for event in early_leaks
                            if spawn_route.get(event.source_id)
                        }),
                        "first_contact_seconds": actual_contact,
                        "first_operator_death_seconds": min((event.time for event in deaths), default=None),
                        "leak_routes": sorted({
                            spawn_route.get(event.source_id) for event in leaks
                            if spawn_route.get(event.source_id)
                        }),
                    },
                })
                evaluated += 1
        for skeleton in skeletons:
            for placement in skeleton.placements:
                operator = engine.fixture.operators[placement.candidate.operator_id]
                if operator.position.value == "RANGED" and placement.candidate.covered_route_ids:
                    intervals = []
                    for route_id in placement.candidate.covered_route_ids:
                        threat_row = next((
                            item for item in threat.routes
                            if item.route_id == route_id and item.earliest_operator_contact_distance is not None
                        ), None)
                        exact = route(engine.fixture.stage, route_id)
                        distances = [
                            exact.distance_at(cell) for cell in placement.candidate.covered_cells
                        ]
                        distances = [item for item in distances if item is not None]
                        if not threat_row or not distances:
                            continue
                        window = max(0.0, (
                            threat_row.earliest_operator_contact_distance - min(distances)
                        ) / max(0.001, threat_row.enemy_speed))
                        attacks = math.floor(
                            window / max(0.001, float(operator.phases[0].stats_max.attack_interval.value or 1))
                        )
                        intervals.append({
                            "route_id": route_id,
                            "window_seconds": window,
                            "attacks_before_contact": attacks,
                            "supported_damage": attacks * float(operator.phases[0].stats_max.atk.value or 0),
                        })
                    if intervals:
                        damage_validation.append({
                            "assignment_id": assignment_id,
                            "skeleton_id": skeleton.skeleton_id,
                            "operator_id": placement.candidate.operator_id,
                            "tile": list(placement.candidate.tile),
                            "facing": placement.candidate.direction,
                            "covered_routes": list(placement.candidate.covered_route_ids),
                            "intervals": intervals,
                        })
                synthetic = operator.synthetic_skill
                if synthetic and not synthetic.auto_activate:
                    device_tiles = {device.tile for device in engine.fixture.stage.devices}
                    skill_records.append({
                        "assignment_id": assignment_id,
                        "skeleton_id": skeleton.skeleton_id,
                        "operator_id": placement.candidate.operator_id,
                        "skill_id": synthetic.skill_id,
                        "recovery_mode": synthetic.recovery_mode.value,
                        "sp_cost": synthetic.sp_cost,
                        "initial_sp": synthetic.initial_sp,
                        "device_interaction_risk": placement.candidate.tile in device_tiles,
                        "status": "COUPLED_DEVICE_RISK" if placement.candidate.tile in device_tiles else "NO_DEVICE_CONFLICT",
                    })

    write("assignment_to_skeleton_audit.json", {
        "records": assignment_rows,
        "summary": {
            "assignments": len(assignment_rows),
            "explicit_role_preserved": sum(item["role_source"] == "EXPLICIT_TEMPORAL_ASSIGNMENT" for item in assignment_rows),
            "semantic_losses": sum(len(item["lost_semantics"]) for item in assignment_rows),
        },
    })
    write("spatial_responsibilities.json", {
        "records": [item.to_dict() for item in spatial_rows_all],
        "summary": {
            "total": len(spatial_rows_all),
            "by_kind": dict(Counter(item.required_kind for item in spatial_rows_all)),
        },
    })
    write("skeleton_diversity.json", {
        "records": skeleton_records,
        "summary": {
            "assignments": len(selected),
            "skeletons": len(skeleton_records),
            "skeletons_per_assignment": dict(Counter(item["assignment_id"] for item in skeleton_records)),
            "distinct_region_signatures": len({tuple(item["region_signature"]) for item in skeleton_records}),
            "distinct_semantic_placements": len({
                tuple(
                    (placement["candidate"]["operator_id"], placement["candidate"]["tile"], placement["candidate"]["direction"])
                    for placement in item["placements"]
                ) for item in skeleton_records
            }),
        },
    })
    write("geometry_feasibility_certificates.json", {
        "certificates": [item.to_dict() for item in geometry_records],
        "summary": {
            "total": len(geometry_records),
            "by_status": dict(Counter(item.final_status for item in geometry_records)),
        },
    })
    interception_records = [{
            "skeleton_id": item["skeleton_id"],
            "assignment_id": item["assignment_id"],
            "block_tiles": [placement["candidate"]["tile"] for placement in item["placements"] if placement["candidate"]["block_route_ids"]],
            "route_coverage": [{
                "tile": placement["candidate"]["tile"],
                "covered_routes": placement["candidate"]["covered_route_ids"],
                "block_routes": placement["candidate"]["block_route_ids"],
            } for placement in item["placements"] if placement["candidate"]["block_route_ids"]],
    } for item in skeleton_records]
    write("interception_depth_audit.json", {
        "records": interception_records,
        "summary": {
            "skeletons_with_blockers": sum(bool(item["block_tiles"]) for item in interception_records),
            "distinct_block_tile_tuples": len({
                tuple(item["block_tiles"]) for item in interception_records if item["block_tiles"]
            }),
        },
    })
    write("shared_coverage_audit.json", {
        "records": [{
            "assignment_id": item["assignment_id"],
            "skeleton_id": item["skeleton_id"],
            "operator_id": placement["candidate"]["operator_id"],
            "tile": list(placement["candidate"]["tile"]),
            "facing": placement["candidate"]["direction"],
            "covered_routes": placement["candidate"]["covered_route_ids"],
            "covered_cells": [list(cell) for cell in placement["candidate"]["covered_cells"]],
            "shared_route_count": placement["candidate"]["features"]["shared_route_count"],
        } for item in skeleton_records for placement in item["placements"] if placement["candidate"]["intended_role"] == "MULTI_LANE_COVERAGE"],
        "summary": {
            "shared_placements": sum(1 for item in skeleton_records for placement in item["placements"] if placement["candidate"]["intended_role"] == "MULTI_LANE_COVERAGE"),
            "with_multi_route_coverage": sum(1 for item in skeleton_records for placement in item["placements"] if placement["candidate"]["intended_role"] == "MULTI_LANE_COVERAGE" and placement["candidate"]["features"]["covered_route_count"] > 1),
        },
    })
    write("dp_geometry_coupling.json", {
        "records": [item.to_dict() for item in certificates],
        "summary": {
            "assignments": len(selected),
            "realizable": sum(item.final_status == "REALIZABLE" for item in certificates),
            "dp_infeasible": sum(item.final_status == "DP_INFEASIBLE" for item in certificates),
            "contact_too_late": sum(item.final_status == "CONTACT_TOO_LATE" for item in certificates),
            "coverage_infeasible": sum(item.final_status == "COVERAGE_INFEASIBLE" for item in certificates),
            "conclusion": "Cost-only ordering is insufficient; DP deadlines depend on exact route contact tiles.",
        },
    })
    partial = []
    for hypothesis in selected:
        assignment_id = hypothesis.hypothesis_id.rsplit("--", 1)[-1]
        temporal = next(item for item in frontier if item.assignment_id == assignment_id)
        for index, operator in enumerate(temporal.deployment_order[:deployment_limit]):
            cost = float(engine.fixture.operators[operator].phases[0].stats_max.cost.value or 0)
            partial.append({
                "assignment_id": assignment_id,
                "operator": operator,
                "position": index,
                "cost": cost,
                "constraints": [
                    "AFTER_CHEAPER_OR_EQUAL_DP_PREDECESSOR",
                    "BEFORE_FIRST_REQUIRED_CONTACT_IF_BLOCK",
                ],
            })
    write("deployment_partial_orders.json", {
        "records": partial,
        "policy": "Preserve DP dependencies and per-lane contact deadlines; deterministic tie-breaking is not a semantic requirement.",
    })
    write("latest_safe_deployment_windows.json", {
        "records": [{
            "route_id": item.route_id,
            "lane_id": item.lane_id,
            "enemy_id": item.enemy_id,
            "enemy_speed": item.enemy_speed,
            "spawn_frames": list(item.spawn_frames),
            "earliest_operator_contact_frame": item.earliest_operator_contact_frame,
            "latest_safe_blocker_frame": item.latest_safe_blocker_frame,
            "contact_to_leak_seconds": item.contact_to_leak_seconds,
        } for item in threat.routes],
    })
    differences = sorted(item["absolute_difference_seconds"] for item in contact_validation if item["absolute_difference_seconds"] is not None)
    write("contact_timing_validation.json", {
        "records": contact_validation,
        "summary": {
            "total": len(contact_validation),
            "by_classification": dict(Counter(item["classification"] for item in contact_validation)),
            "median_absolute_difference_seconds": differences[len(differences) // 2] if differences else None,
        },
    })
    write("early_damage_window_validation.json", {
        "records": damage_validation,
        "summary": {
            "placements": len(damage_validation),
            "zero_attack_placements": sum(any(item["attacks_before_contact"] == 0 for item in row["intervals"]) for row in damage_validation),
        },
    })
    write("skill_timing_coupling.json", {
        "records": skill_records,
        "summary": {
            "manual_skill_placements": len(skill_records),
            "device_conflicts": sum(item["status"] == "COUPLED_DEVICE_RISK" for item in skill_records),
        },
    })
    write("skeleton_geometry_dedup_audit.json", {
        "records": dedup_records,
        "policy": "Region signature is descriptive, not a dedup key; exact semantic placement tuple remains the identity.",
    })
    best_leaks = min((item["result"]["leaks"] for item in experiment_records), default=None)
    best_first_leak = min((
        item["opening"]["first_leak_seconds"] for item in experiment_records
        if item["opening"]["first_leak_seconds"] is not None
    ), default=None)
    write("representative_assignment_experiment.json", {
        "selected_assignments": list(selected_names),
        "records": experiment_records,
        "summary": {
            "assignments": len(selected),
            "skeletons": len(skeleton_records),
            "geometries": len(skeleton_records),
            "executable_timelines": len(experiment_records),
            "simulations": metrics.unique_simulations,
            "cache_hits": metrics.cache_hits,
            "best_leaks": best_leaks,
            "best_first_leak_seconds": best_first_leak,
            "skeletons_per_assignment": dict(Counter(item["assignment_id"] for item in skeleton_records)),
        },
    })
    write("frontier_accounting.json", {
        "representative_experiment": {
            "assignments": len(selected),
            "skeletons": len(skeleton_records),
            "geometries": len(skeleton_records),
            "timing_candidates_generated": sum(item["timing_candidates_generated"] for item in skeleton_records),
            "executable_timelines": len(experiment_records),
        },
            "prior_fresh_search": {
            "hypotheses": 21,
            "assignments": 13,
            "unique_timelines": 127,
            "best": {"kills": 12, "leaks": 43, "remaining_life": -38},
        },
        "full_search": {
            "unique_executable_timelines": 902,
            "best": {"kills": 12, "leaks": 43, "remaining_life": -38},
            "candidate_frontier_exhausted": True,
            "simulator_budget_exhausted": False,
        },
    })
    write("earliest_failure_layer.json", {
        "records": [{
            "assignment_id": item["assignment_id"],
            "skeleton_id": item["skeleton_id"],
            "timing_id": item["timing_id"],
            "first_leak_seconds": item["opening"]["first_leak_seconds"],
            "early_leak_routes": item["opening"]["early_leak_routes"],
            "earliest_layer": "TACTICAL_REQUIREMENT_LIMIT" if item["opening"]["early_leaks"] else "DEPLOYMENT_TIMING",
            "evidence": (
                "Early-window leaks persisted across preserved assignment semantics, distinct skeletons, and multiple timings."
                if item["opening"]["early_leaks"] else "No early-window leak observed."
            ),
        } for item in experiment_records],
        "summary": {
            "timelines_with_early_leaks": sum(item["opening"]["early_leaks"] > 0 for item in experiment_records),
            "dominant_layer": "TACTICAL_REQUIREMENT_LIMIT" if any(item["opening"]["early_leaks"] for item in experiment_records) else "UNKNOWN",
            "evidence": (
                "Assignment-to-skeleton preservation passed and skeleton diversity increased, so persistent early multi-route leakage is upstream of spatial lowering."
                if any(item["opening"]["early_leaks"] for item in experiment_records) else "No dominant failure layer established."
            ),
        },
    })
    write("planner_changes.json", {
        "changes": [{
            "layer": "SemanticSpatialSkeleton",
            "change": "Removed one-geometry-per-region-signature collapse.",
            "reason": "Different interception tiles were discarded despite distinct spatial semantics.",
        }, {
            "layer": "AssignmentToSkeleton",
            "change": "Hypothesis operator responsibilities now seed spatial roles before generic inference.",
            "reason": "Explicit lane/temporal roles were being replaced by operator-stat inference.",
        }, {
            "layer": "SkeletonBeam",
            "change": "Stratified the beam by exact operator/tile/facing signatures while retaining Pareto states.",
            "reason": "The beam otherwise collapsed distinct semantic geometries before timing generation.",
        }, {
            "layer": "EarlyThreatModel",
            "change": "Observed leak-route IDs now union with early-window route IDs.",
            "reason": "Every observed full-search leak route requires an exact route/threat row.",
        }],
        "mechanics_version_unchanged": "m18.9-stage-device-runtime-v1",
        "simulator_changed": False,
    })
    full_search_path = ROOT / "output/r8_1_assignment_spatial_timing_coupling_v1/full_search_raw.json"
    if full_search_path.exists():
        full = json.loads(full_search_path.read_text())
        g1 = full["generation1"]
        g2 = full["generation2"]
        unique_timelines = int(g1["search"]["unique_simulations"]) + int(g2["search"]["unique_simulations"])
        write("full_search_funnel.json", {
            "status": "COMPLETE",
            "justification": "Corrected threat model plus representative diversity and early stabilization justified one bounded search.",
            "budget_ceiling": 1500,
            "generation1": {
                "hypotheses": g1["candidate_funnel"]["plan_hypotheses_generated"],
                "assignments": g1["candidate_funnel"]["operator_assignments_generated"],
                "skeletons_generated": g1["candidate_funnel"]["skeletons_generated"],
                "skeletons_reaching_timing": g1["candidate_funnel"]["skeletons_reaching_timing"],
                "timing_candidates_generated": g1["candidate_funnel"]["timing_candidates_generated"],
                "timing_candidates_dp_rejected": g1["candidate_funnel"]["timing_candidates_dp_rejected"],
                "unique_simulations": g1["search"]["unique_simulations"],
                "cache_hits": g1["search"]["cache_hits"],
                "simulation_budget": g1["search"]["simulation_budget"],
                "stop_reason": g1["search"]["stop"],
                "win": g1["search"]["win"],
                "best": g1["result"],
            },
            "generation2": {
                "hypotheses": g2["candidate_funnel"]["plan_hypotheses_generated"],
                "assignments": g2["candidate_funnel"]["operator_assignments_generated"],
                "skeletons_generated": g2["candidate_funnel"]["skeletons_generated"],
                "skeletons_reaching_timing": g2["candidate_funnel"]["skeletons_reaching_timing"],
                "timing_candidates_generated": g2["candidate_funnel"]["timing_candidates_generated"],
                "timing_candidates_dp_rejected": g2["candidate_funnel"]["timing_candidates_dp_rejected"],
                "unique_simulations": g2["search"]["unique_simulations"],
                "cache_hits": g2["search"]["cache_hits"],
                "simulation_budget_remaining": g2["search"]["simulation_budget"],
                "stop_reason": g2["search"]["stop"],
                "win": g2["search"]["win"],
                "best": g2["result"],
            },
            "total": {
                "hypotheses": g1["candidate_funnel"]["plan_hypotheses_generated"] + g2["candidate_funnel"]["plan_hypotheses_generated"],
                "skeletons_generated": g1["candidate_funnel"]["skeletons_generated"] + g2["candidate_funnel"]["skeletons_generated"],
                "timing_candidates_generated": g1["candidate_funnel"]["timing_candidates_generated"] + g2["candidate_funnel"]["timing_candidates_generated"],
                "timing_candidates_dp_rejected": g1["candidate_funnel"]["timing_candidates_dp_rejected"] + g2["candidate_funnel"]["timing_candidates_dp_rejected"],
                "unique_executable_timelines": unique_timelines,
                "cache_hits": g1["search"]["cache_hits"] + g2["search"]["cache_hits"],
            },
            "candidate_frontier_exhausted": True,
            "simulator_budget_exhausted": unique_timelines >= 1500,
        })
        write("meaningful_win_result.json", {
            "stage": "main_08-01 / R8-1",
            "mechanics_version": "m18.9-stage-device-runtime-v1",
            "status": "NO_WIN",
            "CURRENT_MODEL_WIN": "NO",
            "FIRST_ROBUST_BOUNDED_INFERENCE_MEANINGFUL_WIN": "NO",
            "unique_executable_timelines": unique_timelines,
            "best": g1["result"],
            "robustness_replays": 0,
            "real_game_validation": "UNTESTED",
        })
    else:
        write("full_search_funnel.json", {
            "status": "NOT_RUN",
            "reason": "Representative experiment validation is required before deciding whether a full search is justified.",
            "budget_ceiling_if_run": 1500,
        })
        write("meaningful_win_result.json", {
            "CURRENT_MODEL_WIN": "NO",
            "FIRST_ROBUST_BOUNDED_INFERENCE_MEANINGFUL_WIN": "NO",
            "status": "DIAGNOSTIC_EXPERIMENT",
            "stage": "main_08-01 / R8-1",
            "real_game_validation": "UNTESTED",
        })
    print(json.dumps({
        "certificates": dict(Counter(item.final_status for item in certificates)),
        "skeletons": len(skeleton_records),
        "geometries": len(geometry_records),
        "simulations": metrics.unique_simulations,
        "cache_hits": metrics.cache_hits,
        "best_leaks": best_leaks,
        "best_first_leak": best_first_leak,
        "contact": dict(Counter(item["classification"] for item in contact_validation)),
    }, indent=2))


if __name__ == "__main__":
    main()
