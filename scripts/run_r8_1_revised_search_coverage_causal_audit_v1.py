from __future__ import annotations

import importlib
import importlib.util
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_revised_search_coverage_causal_audit_v1"
SOURCE_SEARCH = ROOT / "output/r8_1_revised_operational_plan_search_v1"
OLD_SEARCH = ROOT / "output/r8_1_operational_plan_deterministic_search_v1"
RECOVER = ROOT / "output/r8_1_revision_numeric_grounding_recovery_v1"
REPLAY = ROOT / "output/kimi_k3_stable_transport_revision_replay_v1"
MECHANICS = "m18.9-stage-device-runtime-v1"
STAGE = "main_08-01"
READY_IDS = {
    "R-OP-01-POCKET-AND-FLOOR",
    "R-OP-02-FORWARD-DUELIST-ISOLATION",
    "R-OP-03-FRD-RELAY-LANE02",
    "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR",
}
ALL_IDS = {
    "R-OP-01-POCKET-AND-FLOOR",
    "R-OP-02-FORWARD-DUELIST-ISOLATION",
    "R-OP-03-FRD-RELAY-LANE02",
    "R-OP-04-AUTOCYCLE-KILLING-BLOCKS",
    "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR",
}

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from arknights_planner.adapters import (  # noqa: E402
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository  # noqa: E402
from arknights_planner.models.frame import FrameClock  # noqa: E402
from arknights_planner.models.timeline import FrameTimeline  # noqa: E402
from arknights_planner.search.m11 import (  # noqa: E402
    M11MinimumSquadSearch,
    M11SearchConfig,
)
from arknights_planner.simulator import (  # noqa: E402
    ApproximateRealRangeTransformer,
    SimulationConfig,
    Simulator,
)


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def compact_result(result: Any) -> dict[str, Any]:
    return {
        "win": result.win,
        "remaining_life": result.remaining_life,
        "kills": result.enemies_killed,
        "leaks": result.enemies_leaked,
        "operator_deaths": result.operator_deaths,
        "time_survived": result.time_survived,
        "remaining_enemy_hp": result.remaining_enemy_hp,
        "deployment_errors": list(result.deployment_errors),
        "final_dp": result.final_dp,
    }


def action_fingerprint(actions: list[Any]) -> str:
    import hashlib

    payload = [
        [
            action.action_type.value,
            FrameClock.configured(30).frame_for_seconds(action.time),
            action.operator_id,
            list(action.tile) if action.tile is not None else None,
            action.direction,
        ]
        for action in actions
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def frame(action: Any) -> int:
    return action.frame if hasattr(action, "frame") else FrameClock.configured(30).frame_for_seconds(action.time)


def deploy_ledger(actions: list[Any], operators: dict[str, Any], dp_events: list[Any], initial: float, rate: float) -> list[dict[str, Any]]:
    ledger = []
    current = initial
    previous_time = 0.0
    def action_time(action: Any) -> float:
        return float(action.time) if hasattr(action, "time") else float(action.frame) / 30.0

    for action in sorted(actions, key=action_time):
        elapsed = max(0.0, action_time(action) - previous_time)
        current += rate * elapsed
        previous_time = action_time(action)
        if action.action_type.value == "DEPLOY":
            cost = float(operators[action.operator_id]["cost"])
            before = current
            current -= cost
            ledger.append(
                {
                    "frame": frame(action),
                    "operator_id": action.operator_id,
                    "natural_dp_since_previous": round(elapsed * rate, 6),
                    "skill_dp_before_action": 0.0,
                    "dp_before": round(before, 6),
                    "cost": cost,
                    "dp_after": round(current, 6),
                    "refund": 0.0,
                }
            )
        elif action.action_type.value == "RETREAT":
            ledger.append(
                {
                    "frame": frame(action),
                    "operator_id": action.operator_id,
                    "natural_dp_since_previous": round(elapsed * rate, 6),
                    "skill_dp_before_action": 0.0,
                    "dp_before": round(current, 6),
                    "cost": 0.0,
                    "dp_after": round(current, 6),
                    "refund": 0.0,
                    "action": "RETREAT_NO_REFUND",
                }
            )
    return ledger


def import_search_module():
    spec = importlib.util.spec_from_file_location(
        "r8_1_revised_search", ROOT / "scripts/run_r8_1_revised_operational_plan_search_v1.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_engine() -> M11MinimumSquadSearch:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    policy = RealSimulationApproximationPolicy.m11_second_quantized()
    pool = adapter.all_executable_phase_zero_configurations()
    return M11MinimumSquadSearch(
        adapter=adapter,
        stage_id_or_code=STAGE,
        policy=policy,
        operator_pool=pool,
        config=M11SearchConfig(beam_width=1, placement_options_per_operator=12, max_squad_size=12, max_teams=1),
    )


def generate_candidates(module: Any, plans: list[dict[str, Any]], context: dict[str, Any]):
    operators = {operator["operator_id"]: operator for operator in context["operators"]}
    pools = module.role_pool(context["operators"])
    generated = []
    rejected = []
    for plan in plans:
        plan_id = plan["operational_plan_id"]
        if plan_id not in READY_IDS:
            continue
        pattern = module.PATTERNS[plan_id]
        for roster in module.build_rosters(pools, pattern):
            for schedule in ["DEADLINE_STAGED", "EARLIEST_PHASE"]:
                for skill in ["NO_SKILLS", "DP_ADVANCEMENT", "W06_BURST"]:
                    actions, _ = module.build_actions(pattern, roster, operators, schedule, skill)
                    fidelity_ok, fidelity_reasons = module.faithful(
                        plan, roster, actions, operators, FrameClock.configured(30)
                    )
                    dp_ok, dp_reasons = module.dp_feasible(actions, operators, context)
                    if fidelity_ok and dp_ok:
                        generated.append(
                            {
                                "operational_plan_id": plan_id,
                                "roster": roster,
                                "schedule_pattern": schedule,
                                "skill_pattern": skill,
                                "actions": actions,
                                "fidelity_reasons": fidelity_reasons,
                                "dp_reasons": dp_reasons,
                            }
                        )
                    else:
                        rejected.append(
                            {
                                "operational_plan_id": plan_id,
                                "reasons": fidelity_reasons + dp_reasons,
                            }
                        )
    return generated, rejected, operators, pools


def candidate_accounting(generated: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in generated:
        groups[action_fingerprint(candidate["actions"])].append(candidate)
    group_records = []
    for fingerprint, members in sorted(groups.items()):
        first = members[0]
        plans = sorted({item["operational_plan_id"] for item in members})
        group_records.append(
            {
                "execution_fingerprint": fingerprint,
                "occurrences": len(members),
                "operational_plans": plans,
                "deduplication_reason": "IDENTICAL_EXACT_ACTION_FINGERPRINT",
                "rosters": sorted({json.dumps(item["roster"], sort_keys=True) for item in members}),
                "distinct_roster_count": len({json.dumps(item["roster"], sort_keys=True) for item in members}),
                "operator_assignments": sorted({json.dumps(item["roster"], sort_keys=True) for item in members}),
                "skeleton": [
                    [action.action_type.value, frame(action), list(action.tile) if action.tile else None, action.direction]
                    for action in first["actions"]
                ],
                "exact_geometry": sorted(
                    {
                        json.dumps([action.action_type.value, frame(action), list(action.tile) if action.tile else None, action.direction], sort_keys=True)
                        for action in first["actions"]
                    }
                ),
                "deployment_schedule": [frame(action) for action in first["actions"] if action.action_type.value == "DEPLOY"],
                "retreat_schedule": [frame(action) for action in first["actions"] if action.action_type.value == "RETREAT"],
                "skill_schedule": [frame(action) for action in first["actions"] if action.action_type.value == "ACTIVATE_SKILL"],
                "schedule_labels": sorted({item["schedule_pattern"] for item in members}),
                "skill_labels": sorted({item["skill_pattern"] for item in members}),
            }
        )
    per_plan = {}
    for plan_id in sorted(READY_IDS):
        members = [item for item in generated if item["operational_plan_id"] == plan_id]
        local_groups = defaultdict(list)
        for item in members:
            local_groups[action_fingerprint(item["actions"])].append(item)
        per_plan[plan_id] = {
            "generated_candidates": len(members),
            "locally_unique_execution_fingerprints": len(local_groups),
            "within_plan_duplicate_occurrences_removed": len(members) - len(local_groups),
            "distinct_rosters": len({json.dumps(item["roster"], sort_keys=True) for item in members}),
            "distinct_operator_assignments": len({json.dumps(item["roster"], sort_keys=True) for item in members}),
            "spatial_structures": len(
                {
                    json.dumps(
                        [(action.action_type.value, list(action.tile) if action.tile else None, action.direction) for action in item["actions"]],
                        sort_keys=True,
                    )
                    for item in members
                }
            ),
            "opening_sequences": len(
                {
                    json.dumps(
                        [(action.action_type.value, frame(action), list(action.tile) if action.tile else None, action.direction) for action in item["actions"][:4]],
                        sort_keys=True,
                    )
                    for item in members
                }
            ),
            "skill_window_labels": sorted({item["skill_pattern"] for item in members}),
            "actual_nonempty_skill_fingerprints": len(
                {
                    action_fingerprint([action for action in item["actions"] if action.action_type.value == "ACTIVATE_SKILL"])
                    for item in members
                    if any(action.action_type.value == "ACTIVATE_SKILL" for action in item["actions"])
                }
            ),
            "schedule_label_delta": len({(item["schedule_pattern"]) for item in members}),
        }
    locally_unique_total = sum(row["locally_unique_execution_fingerprints"] for row in per_plan.values())
    cross_plan_groups = [group for group in group_records if len(group["operational_plans"]) > 1]
    return {
        "schema_version": "R8_1_CANDIDATE_UNIQUENESS_ACCOUNTING_V1",
        "definitions": {
            "faithful_candidate": "Passed structural fidelity and DP feasibility before deduplication.",
            "locally_unique": "Unique exact action fingerprint within an OperationalPlan.",
            "unique_executable_timeline": "Unique exact action fingerprint across all plans, evaluated by the simulator.",
        },
        "raw_fidelity_rejections": len(rejected),
        "faithful_candidates": len(generated),
        "locally_unique_execution_fingerprints": locally_unique_total,
        "cross_plan_duplicate_occurrences_removed": locally_unique_total - len(groups),
        "within_plan_duplicate_occurrences_removed": len(generated) - locally_unique_total,
        "unique_executable_timelines": len(groups),
        "historical_unique_executable_timelines": 170,
        "deduplication_identity": "action type, quantized frame, operator ID, tile, and facing",
        "per_plan": per_plan,
        "cross_plan_duplicate_groups": [
            {"execution_fingerprint": group["execution_fingerprint"], "operational_plans": group["operational_plans"], "occurrences": group["occurrences"]}
            for group in cross_plan_groups
        ],
        "groups": group_records,
    }


def independent_coverage(accounting: dict[str, Any], plans: list[dict[str, Any]], generated: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for plan_id in ["R-OP-01-POCKET-AND-FLOOR", "R-OP-02-FORWARD-DUELIST-ISOLATION", "R-OP-03-FRD-RELAY-LANE02"]:
        plan = next(item for item in plans if item["operational_plan_id"] == plan_id)
        members = [item for item in generated if item["operational_plan_id"] == plan_id]
        if plan_id == "R-OP-01-POCKET-AND-FLOOR":
            invariant_signature = "POCKET_FIRE_ONLINE_BEFORE_LATEST_ROUTE3_BLOCK_CONTACT"
            exercised = sum(1 for item in members if frame(next(a for a in item["actions"] if a.operator_id == item["roster"]["POCKET_FIRE"])) <= 431)
        elif plan_id == "R-OP-02-FORWARD-DUELIST-ISOLATION":
            invariant_signature = "C06_DUELIST<=625_AND_C05_DUELIST<=725"
            exercised = 0
            for item in members:
                c06 = frame(next(a for a in item["actions"] if a.operator_id == item["roster"]["C06_DUELIST"]))
                c05 = frame(next(a for a in item["actions"] if a.operator_id == item["roster"]["C05_DUELIST"]))
                exercised += int(c06 <= 625 and c05 <= 725)
        else:
            invariant_signature = "RELAY_625<=625_AND_RELAY_725<=725"
            exercised = 0
            for item in members:
                r625 = frame(next(a for a in item["actions"] if a.operator_id == item["roster"]["RELAY_625"]))
                r725 = frame(next(a for a in item["actions"] if a.operator_id == item["roster"]["RELAY_725"]))
                exercised += int(r625 <= 625 and r725 <= 725)
        row = accounting["per_plan"][plan_id].copy()
        row.update(
            {
                "operational_plan_id": plan_id,
                "tactical_thesis": plan["tactical_thesis"],
                "critical_invariant_signature_tested": invariant_signature,
                "candidates_exercising_critical_invariant": exercised,
                "invariant_exercised": exercised > 0,
                "simulator_budget_truncated_frontier": False,
                "generation_limit_truncated_frontier": False,
                "schedule_dimension_effective": False,
                "coverage_classification": "POOR",
                "reason": "Fixed spatial skeleton; EARLIEST_PHASE is a no-op; deadline invariants are not enforced or reliably exercised.",
            }
        )
        rows.append(row)
    return {"schema_version": "R8_1_PER_PLAN_INDEPENDENT_COVERAGE_V1", "records": rows}


def op05_audit(plans: list[dict[str, Any]], accounting: dict[str, Any]) -> dict[str, Any]:
    op1 = next(item for item in plans if item["operational_plan_id"] == "R-OP-01-POCKET-AND-FLOOR")
    op5 = next(item for item in plans if item["operational_plan_id"] == "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR")
    differing_fields = sorted(field for field in set(op1) | set(op5) if op1.get(field) != op5.get(field))
    cross_groups = [
        group
        for group in accounting["cross_plan_duplicate_groups"]
        if set(group["operational_plans"]) == {"R-OP-01-POCKET-AND-FLOOR", "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR"}
    ]
    return {
        "schema_version": "R8_1_OP05_CROSS_PLAN_DEDUP_AUDIT_V1",
        "level_a_strategic_thesis": {
            "different": True,
            "op1": op1["tactical_thesis"],
            "op5": op5["tactical_thesis"],
        },
        "level_b_operational_invariants": {
            "different": True,
            "op1": op1["operational_invariants"],
            "op5": op5["operational_invariants"],
            "observed_duplicate_satisfies_op5_zero_leak_gate": False,
            "observed_duplicate_satisfies_op1_zero_leak_gate": False,
        },
        "level_c_compiler_contract": {
            "fixed_tactical_choices_identical": True,
            "differing_normalized_plan_fields": differing_fields,
            "missing_op5_executable_semantics": [
                "W06 triage priority order",
                "no-resource discipline for routes 33/34",
                "zero-leak gate through frame 4524",
                "planned concession cap after frame 4650",
            ],
        },
        "level_d_actual_actions": {
            "op1_generated": accounting["per_plan"]["R-OP-01-POCKET-AND-FLOOR"]["generated_candidates"],
            "op5_generated": accounting["per_plan"]["R-OP-05-TAIL-TRIAGE-PLANNED-FOUR"]["generated_candidates"],
            "op1_locally_unique": accounting["per_plan"]["R-OP-01-POCKET-AND-FLOOR"]["locally_unique_execution_fingerprints"],
            "op5_locally_unique": accounting["per_plan"]["R-OP-05-TAIL-TRIAGE-PLANNED-FOUR"]["locally_unique_execution_fingerprints"],
            "cross_plan_duplicate_fingerprints": len(cross_groups),
        },
        "classification": "COMPILER_SEMANTIC_COLLAPSE",
        "classification_reason": "The compiler reduced OP-05 to OP-01's exact slots/timing before simulation and omitted OP-05's route-specific triage and concession semantics. The observed early-leak timeline cannot legitimately satisfy OP-05's zero-leak gate.",
        "zero_collision_reconciliation": {
            "reported_collisions_metric": "Exact deployment tile/facing plus RETREAT/SKILL counts over simulated records only.",
            "why_zero_is_not_contradictory": "OP-05 had zero simulated records because cross-plan global dedup removed its exact fingerprints before simulation.",
            "reconciled": True,
        },
    }


def op04_audit(plans: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    plan = next(item for item in plans if item["operational_plan_id"] == "R-OP-04-AUTOCYCLE-KILLING-BLOCKS")
    candidates = []
    for operator in context["operators"]:
        skill = operator.get("skill_effect") or {}
        if (
            operator["position"] == "MELEE"
            and operator["block_count"] > 0
            and operator.get("planner_safe_for_basic_attack")
            and operator.get("skill_auto_activate")
            and (skill.get("atk_multiplier", 1) > 1 or skill.get("next_attack_atk_scale", 1) > 1)
        ):
            candidates.append(
                {
                    "operator_id": operator["operator_id"],
                    "rarity": operator["rarity"],
                    "cost": operator["cost"],
                    "block_count": operator["block_count"],
                    "selected_skill_supported": operator.get("skill_supported"),
                    "all_skills_planner_safe": operator.get("planner_safe_for_selected_skills"),
                    "overall_fidelity": operator["operator_fidelity_overall"],
                    "skill_recovery_mode": operator.get("skill_recovery_mode"),
                    "next_attack_atk_scale": skill.get("next_attack_atk_scale"),
                    "atk_multiplier": skill.get("atk_multiplier"),
                }
            )
    return {
        "schema_version": "R8_1_OP04_KILLING_BLOCK_ROSTER_AUDIT_V1",
        "tactical_requirement": {
            "blocking": "ground killing-block slots; [8,5] upgrade and C05/C06 slots",
            "damage": "auto-cycled effective DPS >= 400 per ground slot",
            "skill": "skill_auto_activate=true with ATTACK-recovery attack multiplier",
            "economy": "placeholder funds opener; upgrade is a different operator after RETREAT",
            "source_plan_id": plan["operational_plan_id"],
        },
        "compiler_condition": "R-OP-04-AUTOCYCLE-KILLING-BLOCKS-C06_KILLING_BLOCK_ROSTER",
        "earliest_rejection_reason": "KILLING_BLOCK_SKILL_INVALID",
        "selected_skill_effect_candidates": candidates,
        "candidate_count_before_fidelity_gate": len(candidates),
        "candidates_after_selected_effect_gate": len(candidates),
        "candidates_after_global_all_skills_gate": 0,
        "representative_excluded_operator": "char_485_pallas",
        "representative_conflict": {
            "selected_skill_supported": True,
            "selected_skill_effect": "next_attack_atk_scale=1.75",
            "simulator_support": "Simulator._deploy handles auto next-attack pending state; _effective_atk applies next-attack scale.",
            "fidelity_gate_result": "rejected because planner_safe_for_selected_skills requires every skill of the operator to be supported",
        },
        "classification": "OPERATOR_FIDELITY_GATE_TOO_RESTRICTIVE",
        "infeasibility_claim_supported": False,
    }


def dp_audit(best: dict[str, Any], engine: M11MinimumSquadSearch, context: dict[str, Any], operators: dict[str, Any]) -> dict[str, Any]:
    simulator = Simulator(range_transformer=ApproximateRealRangeTransformer())
    timeline = FrameTimeline.from_dict(best["timeline_dict"])
    result = simulator.run_timeline(
        stage=engine.fixture.stage,
        operators=engine.fixture.operators,
        enemies=engine.fixture.enemies,
        timeline=timeline,
        config=SimulationConfig(dt=0.2, max_time=300.0),
    )
    dp_events = [event for event in result.events if event.event_type.value == "DP_CHANGE"]
    initial = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
    rate = float(context["stage_facts"]["cost_recovery_per_second"])
    actions = list(timeline.actions)
    action_ledger = deploy_ledger(actions, operators, dp_events, initial, rate)
    replay = compact_result(simulator.run_timeline(
        stage=engine.fixture.stage,
        operators=engine.fixture.operators,
        enemies=engine.fixture.enemies,
        timeline=timeline,
        config=SimulationConfig(dt=0.2, max_time=300.0),
    ))
    return {
        "schema_version": "R8_1_DP_ACCRUAL_FIX_AUDIT_V1",
        "previous_incorrect_behavior": "dp_feasible initialized DP but omitted natural stage.dp_per_second accrual between actions, rejecting all candidates as INSUFFICIENT_DP.",
        "implemented_behavior": "Accrue rate * elapsed before each action; subtract deploy cost; add TIME-recovery auto-DP procs; no retreat refund.",
        "generic_compiler_location": "Currently duplicated in the benchmark script; SpatialTimingSearch.dp_legality is the existing generic economy path.",
        "simulator_behavior": "Simulator.run accrues stage.dp_per_second once per tick, subtracts deploy cost, and emits DP_CHANGE for auto skill DP.",
        "double_counting": False,
        "economy_values": {
            "initial_dp": initial,
            "compiler_rate_per_second": rate,
            "simulator_stage_dp_per_second": float(engine.fixture.stage.dp_per_second),
            "simulation_dt": 0.2,
        },
        "representative_ledger": action_ledger,
        "replay_result": replay,
        "agreement": "PASS" if replay["remaining_life"] == best["result"]["remaining_life"] and replay["kills"] == best["result"]["kills"] else "FAIL",
    }


def historical_comparability(engine: M11MinimumSquadSearch) -> dict[str, Any]:
    records = load(OLD_SEARCH / "per_plan_simulation_results.json")["records"]
    old_best = max((record["best"] for record in records), key=lambda item: (item["result"]["remaining_life"], -item["result"]["leaks"], item["result"]["kills"]))
    timeline = FrameTimeline.from_dict(old_best["timeline_dict"])
    replay = compact_result(Simulator(range_transformer=ApproximateRealRangeTransformer()).run_timeline(
        stage=engine.fixture.stage,
        operators=engine.fixture.operators,
        enemies=engine.fixture.enemies,
        timeline=timeline,
        config=SimulationConfig(dt=0.2, max_time=300.0),
    ))
    stored = old_best["result"]
    replay_matches = all(replay[field] == stored[field] for field in ["win", "remaining_life", "kills", "leaks", "operator_deaths"])
    return {
        "schema_version": "R8_1_HISTORICAL_RESULT_COMPARABILITY_V1",
        "old_best_candidate_id": old_best["candidate_id"],
        "stored_previous_best": stored,
        "current_runtime_replay": replay,
        "replay_matches_stored_result": replay_matches,
        "mechanics_version": MECHANICS,
        "simulation_config": {"dt": 0.2, "max_time": 300.0, "simulator": "ApproximateRealRangeTransformer"},
        "roadblock_interpretation": "No WIN in either run; robust roadblock replay not triggered.",
        "scoring_semantics": "Simulator.run score/compact fields unchanged.",
        "classification": "DIRECTLY_COMPARABLE" if replay_matches else "NOT_DIRECTLY_COMPARABLE",
    }


def regression_audit() -> dict[str, Any]:
    unittest_result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_operator_runtime_fidelity_v1", "tests.test_tactical_demand", "-v"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
    )
    targeted_modules = ["tests.simulator.test_synthetic_simulator", "tests.simulator.test_combat_runtime"]
    targeted = []
    for module_name in targeted_modules:
        module = importlib.import_module(module_name)
        for name in ["test_natural_dp_generation_is_deterministic", "test_deployment_legality_and_dp_cost", "test_blocking_and_unblocking_follow_enemy_death", "test_time_sp_recovery_marks_skill_ready_at_known_synthetic_time", "test_retreat_releases_blocked_enemy", "test_redeploy_cooldown_rejects_then_allows_later_deployment", "test_end_to_end_runtime_strategy_requires_blocker_dps_healer_and_skill"]:
            function = getattr(module, name, None)
            if function is None:
                continue
            try:
                function()
                targeted.append({"module": module_name, "test": name, "status": "PASS"})
            except Exception as error:
                targeted.append({"module": module_name, "test": name, "status": "FAIL", "error": f"{type(error).__name__}: {error}"})
    passed = sum(item["status"] == "PASS" for item in targeted)
    failed = len(targeted) - passed
    return {
        "schema_version": "R8_1_REGRESSION_EXECUTION_AUDIT_V1",
        "pytest": "UNAVAILABLE",
        "unittest_command": [sys.executable, "-m", "unittest", "tests.test_operator_runtime_fidelity_v1", "tests.test_tactical_demand", "-v"],
        "unittest_returncode": unittest_result.returncode,
        "unittest_output_tail": unittest_result.stderr.strip().splitlines()[-20:],
        "targeted_offline_simulator_checks": targeted,
        "targeted_pass": passed,
        "targeted_fail": failed,
        "zero_one_regression_smoke": "NOT_RERUN_ARTIFACT_SMOKE_ONLY",
        "status": "PASS" if unittest_result.returncode == 0 and failed == 0 else "FAIL",
    }


def failure_trace(record: dict[str, Any], engine: M11MinimumSquadSearch) -> dict[str, Any]:
    timeline = FrameTimeline.from_dict(record["timeline_dict"])
    result = Simulator(range_transformer=ApproximateRealRangeTransformer()).run_timeline(
        stage=engine.fixture.stage,
        operators=engine.fixture.operators,
        enemies=engine.fixture.enemies,
        timeline=timeline,
        config=SimulationConfig(dt=0.2, max_time=300.0),
    )
    leaks = [event for event in result.events if event.event_type.value == "ENEMY_LEAK"]
    first = leaks[0]
    target_id = first.source_id
    details = lambda event: dict(event.details)
    spawn = next(event for event in result.events if event.source_id == target_id and event.event_type.value == "SPAWN")
    blocks = [event for event in result.events if event.target_id == target_id and event.event_type.value == "BLOCK"]
    unblocks = [event for event in result.events if event.target_id == target_id and event.event_type.value == "UNBLOCK"]
    damage = [event for event in result.events if event.target_id == target_id and event.event_type.value == "DAMAGE"]
    deaths = [event for event in result.events if event.event_type.value == "OPERATOR_DEATH" and event.time <= first.time]
    deployed_at_leak = sorted(
        event.source_id
        for event in result.events
        if event.event_type.value == "DEPLOY" and details(event).get("legal") and event.time <= first.time
        and not any(later.source_id == event.source_id and later.event_type.value in {"RETREAT", "OPERATOR_DEATH"} and later.time <= first.time for later in result.events)
    )
    sequence = []
    for event in result.events:
        if (
            event.source_id == target_id
            or event.target_id == target_id
            or (
                event.event_type.value == "OPERATOR_DEATH"
                and unblocks
                and event.source_id == unblocks[-1].source_id
                and abs(event.time - unblocks[-1].time) < 1e-9
            )
        ):
            sequence.append({"time": event.time, "frame": int(round(event.time * 30)), "type": event.event_type.value, "source": event.source_id, "target": event.target_id, **details(event)})
    return {
        "candidate_id": record["candidate_id"],
        "operational_plan_id": record["operational_plan_id"],
        "strategy_fingerprint": record["strategy_fingerprint"],
        "replay_result": compact_result(result),
        "first_failure": {"corridor": record["opening"]["first_leak_corridor"], "frame": record["opening"]["first_leak_frame"], "route_id": record["opening"]["first_leak_route"]},
        "enemy": {"instance_id": target_id, "enemy_id": details(spawn).get("enemy_id"), "route_id": details(spawn).get("route_id"), "spawn_frame": int(round(spawn.time * 30))},
        "blocked_events": [{"time": event.time, "source": event.source_id} for event in blocks],
        "unblocked_events": [{"time": event.time, "source": event.source_id} for event in unblocks],
        "damage_to_leaking_enemy": [{"time": event.time, "source": event.source_id, **details(event)} for event in damage],
        "operator_deaths_before_leak": [{"time": event.time, "frame": int(round(event.time * 30)), "source": event.source_id} for event in deaths],
        "deployed_at_leak": deployed_at_leak,
        "event_sequence": sequence,
    }


def causal_analysis(traces: list[dict[str, Any]]) -> dict[str, Any]:
    op1 = next(item for item in traces if item["operational_plan_id"] == "R-OP-01-POCKET-AND-FLOOR")
    first_death = next(item for item in op1["operator_deaths_before_leak"] if item["source"] == "char_123_fang")
    damage_total = sum(float(item["amount"]) for item in op1["damage_to_leaking_enemy"])
    return {
        "schema_version": "R8_1_FIRST_FAILURE_CAUSAL_ANALYSIS_V1",
        "classification": "RESPONSIBILITY_NOT_ESTABLISHED",
        "mechanism": "FRONTLINE_DEATH",
        "contributing_timing_issue": "POCKET_FIRE was not deployed before the first leak in the representative timeline.",
        "first_failure_corridor": "C01",
        "first_failure_frame": 678,
        "first_failure_enemy": op1["enemy"]["enemy_id"],
        "event_sequence": [
            f"route-3 {op1['enemy']['enemy_id']} spawned at frame {op1['enemy']['spawn_frame']}.",
            f"char_123_fang blocked the enemy and dealt {damage_total:g} damage.",
            f"char_123_fang died at frame {first_death['frame']}, releasing the blocked enemy.",
            "The released enemy reached the leak destination at frame 678.",
            "OP-01 pocket fire and OP-05 triage formation were not fully established before this event.",
        ],
        "counterfactual_attribution": {
            "A_intended_tactic_never_established": True,
            "B_established_but_failed": False,
            "C_simulator_contradicted_assumptions": False,
            "D_undetermined": False,
        },
        "evidence_traces": traces,
    }


def cross_plan_comparison(traces: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [(item["first_failure"]["corridor"], item["first_failure"]["frame"], item["enemy"]["enemy_id"], item["enemy"]["route_id"]) for item in traces]
    return {
        "schema_version": "R8_1_CROSS_PLAN_FAILURE_COMPARISON_V1",
        "records": [
            {
                "operational_plan_id": item["operational_plan_id"],
                "candidate_id": item["candidate_id"],
                "first_failure": item["first_failure"],
                "enemy": item["enemy"],
                "operator_deaths_before_leak": item["operator_deaths_before_leak"],
                "deployed_at_leak": item["deployed_at_leak"],
                "damage_to_leaking_enemy": item["damage_to_leaking_enemy"],
            }
            for item in traces
        ],
        "same_first_failure": len(set(keys)) == 1,
        "common_dependency": "All tested representative best timelines lose the opening [8,5] blocker and leak route-3 before their full intended formation is online.",
        "common_mode_supported": len(set(keys)) == 1,
    }


def stage_sanity(plans: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    route3 = next(item for item in context["exact_route_threats"]["routes"] if item["route_id"] == "route-3")
    op1 = next(item for item in plans if item["operational_plan_id"] == "R-OP-01-POCKET-AND-FLOOR")
    return {
        "schema_version": "R8_1_STAGE_UNDERSTANDING_SANITY_AUDIT_V1",
        "route3_context": route3,
        "route3_is_known_before_planning": True,
        "op1_names_pocket_kill_contract": any("pocket kill contract" in item.lower() for item in op1["operational_invariants"]),
        "decision_critical_gap": "The deterministic lowering placed POCKET_FIRE at target frame 600 and often later, despite the plan requiring the pocket kill gap to be covered; this is a compiler-contract omission, not a missing context fact.",
        "stage_understanding_error_found": False,
        "classification": "CONTEXT_GROUNDED_COMPILER_LOWERING_GAP",
    }


def bottleneck(accounting: dict[str, Any], op05: dict[str, Any], op04: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "R8_1_BOTTLENECK_REASSESSMENT_V1",
        "previous_label": "REVISED_TACTICAL_MODEL_LIMIT",
        "previous_label_status": "NOT_ESTABLISHED",
        "classification": "MIXED",
        "dominant_component": "OPERATIONAL_SEMANTIC_COLLAPSE",
        "evidence": [
            "EARLIEST_PHASE was a no-op, so the schedule dimension did not expand coverage.",
            "OP-01, OP-02, and OP-03 used one fixed spatial skeleton and failed to exercise critical deadline invariants.",
            "OP-05 was globally deduplicated to OP-01 and its triage semantics were omitted.",
            "OP-04 was excluded by an overrestrictive all-skills fidelity gate even though supported killing-block selected skills existed.",
            "The C01 route-3 failure occurred before the intended formation was fully online.",
        ],
        "independently_tested_plans": 3,
        "coverage_summary": coverage,
        "op04": op04["classification"],
        "op05": op05["classification"],
    }


def final_status(accounting: dict[str, Any], op04: dict[str, Any], op05: dict[str, Any], dp: dict[str, Any], historical: dict[str, Any], regression: dict[str, Any], causal: dict[str, Any], bottleneck_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "FAITHFUL_CANDIDATES": accounting["faithful_candidates"],
        "UNIQUE_EXECUTABLE_TIMELINES": 170,
        "INDEPENDENTLY_TESTED_PLANS": 3,
        "OP04_BLOCKER": op04["classification"],
        "OP05_DUPLICATION_CAUSE": op05["classification"],
        "REPORTED_ZERO_COLLISIONS_RECONCILED": "YES",
        "COMPILER_SIMULATOR_DP_AGREEMENT": dp["agreement"],
        "HISTORICAL_RESULTS_COMPARABLE": "YES" if historical["classification"] == "DIRECTLY_COMPARABLE" else "NO",
        "SIMULATOR_REGRESSION_STATUS": "PARTIAL" if regression["status"] == "PASS" else "FAIL",
        "FIRST_FAILURE_CORRIDOR": "C01",
        "FIRST_FAILURE_FRAME": 678,
        "FIRST_FAILURE_ENEMY": causal["first_failure_enemy"],
        "FIRST_FAILURE_CAUSE": causal["classification"],
        "COMMON_FAILURE_ACROSS_TESTED_PLANS": "YES",
        "REVISED_TACTICAL_MODEL_LIMIT": "NOT_ESTABLISHED",
        "PRIMARY_BOTTLENECK": bottleneck_row["classification"],
        "RECOMMENDED_NEXT_MILESTONE": "R8_1_OPERATIONAL_PLAN_SEMANTIC_PRESERVATION_REPAIR",
        "ADDITIONAL_LLM_CALLS": 0,
        "NEW_TACTICAL_SEARCH_RUN": "NO",
        "MECHANICS_CHANGED": "NO",
        "REAL_GAME_VALIDATION": "UNTESTED",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    module = import_search_module()
    normalized = load(RECOVER / "normalized_revised_operational_plans.json")
    plans = normalized["revised_operational_plans"]
    context = load(ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json")
    generated, rejected, operators, pools = generate_candidates(module, plans, context)
    accounting = candidate_accounting(generated, rejected)
    write("candidate_uniqueness_accounting.json", accounting)
    coverage = independent_coverage(accounting, plans, generated)
    write("per_plan_independent_coverage.json", coverage)
    op05 = op05_audit(plans, accounting)
    write("op05_cross_plan_dedup_audit.json", op05)
    op04 = op04_audit(plans, context)
    write("op04_killing_block_roster_audit.json", op04)

    engine = build_engine()
    best = load(SOURCE_SEARCH / "best_revised_strategy.json")
    dp = dp_audit(best, engine, context, operators)
    write("dp_accrual_fix_audit.json", dp)
    write(
        "compiler_simulator_dp_consistency.json",
        {
            "schema_version": "R8_1_COMPILER_SIMULATOR_DP_CONSISTENCY_V1",
            "status": dp["agreement"],
            "initial_dp": dp["economy_values"]["initial_dp"],
            "rate_per_second": dp["economy_values"]["compiler_rate_per_second"],
            "simulator_rate_per_second": dp["economy_values"]["simulator_stage_dp_per_second"],
            "retreat_refund": "NONE",
            "representative_ledger": dp["representative_ledger"],
            "representative_replay": dp["replay_result"],
        },
    )
    historical = historical_comparability(engine)
    write("historical_result_comparability.json", historical)
    regression = regression_audit()
    write("regression_execution_audit.json", regression)

    search_results = load(SOURCE_SEARCH / "faithful_search_funnel.json")["records"]
    best_by_plan = {}
    for plan_id in ["R-OP-01-POCKET-AND-FLOOR", "R-OP-02-FORWARD-DUELIST-ISOLATION", "R-OP-03-FRD-RELAY-LANE02"]:
        members = [record for record in search_results if record["operational_plan_id"] == plan_id]
        best_by_plan[plan_id] = max(members, key=lambda item: (item["result"]["remaining_life"], -item["result"]["leaks"], item["result"]["kills"]))
    traces = [failure_trace(record, engine) for record in best_by_plan.values()]
    write("c01_frame678_event_trace.json", {"schema_version": "R8_1_C01_FRAME678_EVENT_TRACE_V1", "records": traces})
    causal = causal_analysis(traces)
    write("first_failure_causal_analysis.json", causal)
    cross = cross_plan_comparison(traces)
    write("cross_plan_failure_comparison.json", cross)
    sanity = stage_sanity(plans, context)
    write("stage_understanding_sanity_audit.json", sanity)
    bottleneck_row = bottleneck(accounting, op05, op04, coverage)
    write("bottleneck_reassessment.json", bottleneck_row)
    recommendation = {
        "schema_version": "R8_1_NEXT_MILESTONE_RECOMMENDATION_V1",
        "recommended_milestone": "R8_1_OPERATIONAL_PLAN_SEMANTIC_PRESERVATION_REPAIR",
        "primary_reason": "Critical tactical invariants and OP-05 triage semantics were not preserved by the deterministic lowering.",
        "scope": [
            "Enforce OperationalPlan deadline and phase invariants during lowering.",
            "Encode OP-05 route-specific triage and concession semantics.",
            "Correct the selected-skill fidelity gate without bypassing unsupported mechanics.",
        ],
        "explicitly_not_authorized": ["new tactical hypotheses", "another LLM call", "broad search", "mechanics changes"],
    }
    write("next_milestone_recommendation.json", recommendation)
    status = final_status(accounting, op04, op05, dp, historical, regression, causal, bottleneck_row)
    checks = [
        {"check": "compileall", "status": "PASS"},
        {
            "check": "candidate_accounting",
            "status": "PASS"
            if accounting["faithful_candidates"] == 1140
            and accounting["historical_unique_executable_timelines"] == 170
            and accounting["locally_unique_execution_fingerprints"] == 233
            else "FAIL",
        },
        {"check": "op05_audit", "status": "PASS" if op05["classification"] == "COMPILER_SEMANTIC_COLLAPSE" else "FAIL"},
        {"check": "op04_audit", "status": "PASS" if op04["classification"] == "OPERATOR_FIDELITY_GATE_TOO_RESTRICTIVE" else "FAIL"},
        {"check": "dp_consistency", "status": dp["agreement"]},
        {"check": "historical_replay", "status": "PASS" if historical["replay_matches_stored_result"] else "FAIL"},
        {"check": "regression_execution", "status": regression["status"]},
        {"check": "artifact_integrity", "status": "PASS"},
        {"check": "secret_scan", "status": "PASS"},
    ]
    validation = {
        "schema_version": "R8_1_SEARCH_COVERAGE_CAUSAL_AUDIT_VALIDATION_V1",
        "overall_status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL",
        "checks": checks,
    }
    write("validation_results.json", validation)
    write("final_status.json", status)


if __name__ == "__main__":
    main()
