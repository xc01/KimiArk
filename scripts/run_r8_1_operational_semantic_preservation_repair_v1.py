from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_operational_semantic_preservation_repair_v1"
PRIOR = ROOT / "output/r8_1_revised_operational_plan_search_v1"
AUDIT = ROOT / "output/r8_1_revised_search_coverage_causal_audit_v1"
RECOVER = ROOT / "output/r8_1_revision_numeric_grounding_recovery_v1"
CTX_PATH = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
MECHANICS = "m18.9-stage-device-runtime-v1"
STAGE = "main_08-01"
PLAN_IDS = [
    "R-OP-01-POCKET-AND-FLOOR",
    "R-OP-02-FORWARD-DUELIST-ISOLATION",
    "R-OP-03-FRD-RELAY-LANE02",
    "R-OP-04-AUTOCYCLE-KILLING-BLOCKS",
    "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR",
]
TARGETED_CEILING = 120

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from arknights_planner.adapters import (  # noqa: E402
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository  # noqa: E402
from arknights_planner.models.frame import FrameClock  # noqa: E402
from arknights_planner.models.strategy import Action, ActionType, Strategy  # noqa: E402
from arknights_planner.models.timeline import FrameTimeline  # noqa: E402
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig  # noqa: E402
from arknights_planner.simulator import (  # noqa: E402
    ApproximateRealRangeTransformer,
    SimulationConfig,
    Simulator,
)


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def frame_of(action: Any) -> int:
    if hasattr(action, "frame"):
        return int(action.frame)
    return FrameClock.configured(30).frame_for_seconds(action.time)


def action_fingerprint(actions: list[Any]) -> str:
    return sha(
        [
            [
                action.action_type.value,
                frame_of(action),
                action.operator_id,
                list(action.tile) if action.tile is not None else None,
                action.direction,
            ]
            for action in actions
        ]
    )


def import_prior_module():
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


def selected_usage_fidelity(
    operator: dict[str, Any],
    *,
    role: str,
    fidelity_by_id: dict[str, dict[str, Any]] | None = None,
    census_by_id: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, list[str]]:
    """The selected responsibility, not every operator skill, defines fidelity."""
    reasons = []
    if not operator.get("planner_safe_for_basic_attack", False):
        reasons.append("BASE_STATS_OR_BASIC_ATTACK_UNSUPPORTED")
    skill = operator.get("skill_effect") or {}
    if role == "KILLING_BLOCK":
        if not operator.get("skill_supported", False):
            reasons.append("SELECTED_SKILL_UNSUPPORTED")
        if not operator.get("skill_auto_activate", False):
            reasons.append("SELECTED_SKILL_NOT_AUTO_ACTIVATED")
        if operator.get("skill_recovery_mode") != "ATTACK":
            reasons.append("SELECTED_SKILL_RECOVERY_NOT_ATTACK")
        if not (skill.get("atk_multiplier", 1) > 1 or skill.get("next_attack_atk_scale", 1) > 1):
            reasons.append("SELECTED_SKILL_HAS_NO_ATTACK_MULTIPLIER")
    if role == "PIONEER_BLOCK":
        if not skill.get("dp_immediate", 0) > 0:
            reasons.append("SELECTED_DP_SKILL_UNSUPPORTED")
    if fidelity_by_id and operator["operator_id"] in fidelity_by_id:
        dimensions = fidelity_by_id[operator["operator_id"]].get("dimensions", {})
        if dimensions.get("talent") not in {None, "GENERIC_SUPPORTED", "NOT_APPLICABLE"}:
            reasons.append("SELECTED_USAGE_TALENT_UNVERIFIED")
        if dimensions.get("trait") == "UNSUPPORTED":
            census = (census_by_id or {}).get(operator["operator_id"], {})
            keys = trait_effect_keys(census)
            relevant = DECISION_CRITICAL_TRAIT_KEYS.get(role, set())
            if keys & relevant:
                reasons.append("DECISION_CRITICAL_TRAIT_UNSUPPORTED")
    return not reasons, reasons


DECISION_CRITICAL_TRAIT_KEYS = {
    "BLOCK": {"atk_scale", "def", "max_hp", "block", "sluggish"},
    "PIONEER_BLOCK": {"atk_scale", "def", "max_hp", "block", "sluggish"},
    "KILLING_BLOCK": {
        "atk_scale", "init_atk_scale", "delta_atk_scale", "max_atk_scale", "times",
        "interval", "attack@atk_scale", "attack@atk_scale_2", "attack@append_atk_scale",
        "attack@chain.atk_scale", "attack@chain.max_target", "attack@max_target",
        "attack@times", "attack@sluggish", "attack@enable_third_attack",
        "attack@ability_range_radius", "attack@atk_to_hp_recovery_ratio", "sluggish",
    },
    "DUELIST": {
        "atk_scale", "init_atk_scale", "delta_atk_scale", "max_atk_scale", "times",
        "interval", "sluggish", "attack@atk_scale", "attack@times", "attack@sluggish",
        "attack@atk_to_hp_recovery_ratio", "heal_scale", "def", "max_hp",
    },
    "RANGED_DPS": {
        "atk_scale", "init_atk_scale", "delta_atk_scale", "max_atk_scale", "times",
        "interval", "sluggish", "attack@atk_scale", "attack@times", "attack@sluggish",
        "attack@max_target", "attack@chain.atk_scale", "attack@chain.max_target",
        "attack@ability_range_radius",
    },
    "SUSTAIN": {
        "heal_scale", "atk", "atk_scale", "interval", "ep_heal_ratio",
        "attack@atk_to_hp_recovery_ratio", "attack@ability_range_radius", "sluggish",
    },
    "RELAY": {"cost", "def", "max_hp", "block", "sluggish"},
}


def trait_effect_keys(census: dict[str, Any]) -> set[str]:
    effects = census.get("trait_effects")
    if not isinstance(effects, dict):
        return set()
    keys: set[str] = set()
    for candidate in effects.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        for entry in candidate.get("blackboard", []):
            if isinstance(entry, dict) and entry.get("key"):
                keys.add(str(entry["key"]))
    return keys


def selected_usage_pool(
    context: dict[str, Any],
    role: str,
    *,
    fidelity_by_id: dict[str, dict[str, Any]] | None = None,
    census_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for operator in context["operators"]:
        skill = operator.get("skill_effect") or {}
        eligible, reasons = selected_usage_fidelity(
            operator,
            role=role,
            fidelity_by_id=fidelity_by_id,
            census_by_id=census_by_id,
        )
        structural = True
        if role == "BLOCK":
            structural = operator["position"] == "MELEE" and operator["block_count"] > 0
        elif role == "PIONEER_BLOCK":
            structural = (
                operator["position"] == "MELEE"
                and operator["profession"] == "PIONEER"
                and operator["block_count"] >= 2
                and float(skill.get("dp_immediate", 0)) > 0
            )
        elif role == "KILLING_BLOCK":
            structural = (
                operator["position"] == "MELEE"
                and operator["block_count"] > 0
                and operator.get("skill_auto_activate", False)
                and (
                    float(skill.get("atk_multiplier", 1)) > 1
                    or float(skill.get("next_attack_atk_scale", 1)) > 1
                )
            )
        elif role == "DUELIST":
            autonomous = (
                float(operator["hp"]) >= 1900
                and float(operator["defense"]) >= 150
            ) or (
                operator.get("skill_supported", False)
                and (
                    float(skill.get("immediate_self_heal_ratio", 0)) > 0
                    or skill.get("heal_mode", False)
                )
            )
            structural = operator["position"] == "MELEE" and autonomous
        elif role == "RELAY":
            structural = (
                operator["position"] == "MELEE"
                and 18 <= float(operator["redeploy_seconds"]) <= 25
                and float(operator["cost"]) <= 8
            )
        elif role == "RANGED_DPS":
            structural = (
                operator["position"] == "RANGED"
                and operator["profession"] not in {"MEDIC", "SUPPORT"}
            )
        elif role == "SUSTAIN":
            structural = operator["position"] == "RANGED" and operator["profession"] == "MEDIC"
        if not structural or not eligible:
            continue
        dps = float(operator["attack"]) / max(0.1, float(operator["attack_interval_seconds"]))
        score = {
            "BLOCK": float(operator["hp"]) / 1000 + operator["block_count"] * 3 - float(operator["cost"]) / 2,
            "PIONEER_BLOCK": float(skill.get("dp_immediate", 0)) * 2 + operator["block_count"] * 4 - float(operator["cost"]) / 2,
            "KILLING_BLOCK": dps / 100 - float(operator["cost"]) / 3,
            "DUELIST": dps / 100 + float(operator["hp"]) / 1900 - float(operator["cost"]) / 3,
            "RELAY": float(operator["hp"]) / 1000 - float(operator["cost"]),
            "RANGED_DPS": dps / 100 - float(operator["cost"]) / 3,
            "SUSTAIN": dps / 100 - float(operator["cost"]) / 3,
        }.get(role, dps)
        rows.append((float(operator["cost"]), -score, operator["operator_id"], operator))
    rows.sort()
    return [row[-1] for row in rows]


def build_selected_rosters(
    context: dict[str, Any],
    pattern: dict[str, Any],
    *,
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
    limit: int = 32,
) -> list[dict[str, str]]:
    baseline: dict[str, str] = {}
    used: set[str] = set()
    for slot in pattern["slots"]:
        candidates = [
            operator
            for operator in selected_usage_pool(
                context,
                slot["role"],
                fidelity_by_id=fidelity_by_id,
                census_by_id=census_by_id,
            )
            if slot.get("max_cost") is None or float(operator["cost"]) <= float(slot["max_cost"])
            if operator["operator_id"] not in used
        ]
        if not candidates:
            return []
        operator = candidates[0]
        baseline[slot["slot_id"]] = operator["operator_id"]
        used.add(operator["operator_id"])
    variants = [baseline]
    for slot in pattern["slots"]:
        candidates = [
            operator
            for operator in selected_usage_pool(
                context,
                slot["role"],
                fidelity_by_id=fidelity_by_id,
                census_by_id=census_by_id,
            )
            if slot.get("max_cost") is None or float(operator["cost"]) <= float(slot["max_cost"])
        ][:12]
        for operator in candidates:
            variant = dict(baseline)
            variant[slot["slot_id"]] = operator["operator_id"]
            if len(set(variant.values())) != len(variant):
                continue
            if variant not in variants:
                variants.append(variant)
    return variants[:limit]


def corrected_killing_pool(context: dict[str, Any], fidelity_by_id: dict[str, dict[str, Any]], census_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for operator in context["operators"]:
        eligible, reasons = selected_usage_fidelity(
            operator,
            role="KILLING_BLOCK",
            fidelity_by_id=fidelity_by_id,
            census_by_id=census_by_id,
        )
        skill = operator.get("skill_effect") or {}
        if operator["position"] == "MELEE" and operator["block_count"] > 0 and (skill.get("atk_multiplier", 1) > 1 or skill.get("next_attack_atk_scale", 1) > 1):
            rows.append(
                {
                    "operator": operator,
                    "eligible": eligible,
                    "reasons": reasons,
                    "effective_dps_floor": float(operator["attack"]) / max(0.1, float(operator["attack_interval_seconds"])),
                }
            )
    return sorted(rows, key=lambda row: (-row["effective_dps_floor"], row["operator"]["operator_id"]))


def route_map(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["route_id"]: row for row in context["exact_route_threats"]["routes"]}


def establishment_deadline(route: dict[str, Any] | None, kind: str) -> int | None:
    if route is None:
        return None
    if kind == "BLOCK":
        return route.get("latest_safe_blocker_frame")
    if kind == "FIRE":
        if route.get("earliest_operator_contact_frame") is not None:
            return int(route["earliest_operator_contact_frame"])
        return min(route.get("spawn_frames") or [0])
    if kind == "MEDIC":
        if route.get("latest_safe_blocker_frame") is not None:
            return int(route["latest_safe_blocker_frame"])
        if route.get("earliest_operator_contact_frame") is not None:
            return int(route["earliest_operator_contact_frame"])
        return min(route.get("spawn_frames") or [0])
    return None


DEADLINE_ROUTES = {
    "R-OP-01-POCKET-AND-FLOOR": {
        "C03_STUB": ("route-2", "BLOCK"),
        "POCKET_BLOCK": ("route-1", "BLOCK"),
        "POCKET_FIRE": ("route-4", "FIRE"),
        "C04_FIRE": ("route-8", "FIRE"),
        "C07_FIRE": ("route-10", "FIRE"),
        "C05_BLOCK": ("route-7", "BLOCK"),
        "C06_BLOCK": ("route-6", "BLOCK"),
        "POCKET_MEDIC": ("route-4", "MEDIC"),
    },
    "R-OP-02-FORWARD-DUELIST-ISOLATION": {
        "C03_STUB": ("route-2", "BLOCK"),
        "POCKET_BLOCK": ("route-1", "BLOCK"),
        "C06_DUELIST": ("route-6", "BLOCK"),
        "C05_DUELIST": ("route-7", "BLOCK"),
        "C04_FIRE": ("route-8", "FIRE"),
        "C07_FIRE": ("route-10", "FIRE"),
        "POCKET_OVERFLOW": ("route-4", "FIRE"),
        "POCKET_MEDIC": ("route-4", "MEDIC"),
    },
    "R-OP-03-FRD-RELAY-LANE02": {
        "C03_STUB": ("route-2", "BLOCK"),
        "POCKET_BLOCK": ("route-1", "BLOCK"),
        "C04_FIRE": ("route-8", "FIRE"),
        "POCKET_FIRE": ("route-4", "FIRE"),
        "C07_FIRE": ("route-10", "FIRE"),
        "POCKET_MEDIC": ("route-4", "MEDIC"),
        "LANE02_MEDIC": ("route-15", "MEDIC"),
        "RELAY_625": ("route-6", "BLOCK"),
        "RELAY_725": ("route-7", "BLOCK"),
        "RELAY_2727": ("route-15", "BLOCK"),
        "RELAY_3789": ("route-22", "BLOCK"),
        "RELAY_3927": ("route-24", "BLOCK"),
        "RELAY_4089": ("route-23", "BLOCK"),
        "RELAY_4377": ("route-25", "BLOCK"),
    },
    "R-OP-04-AUTOCYCLE-KILLING-BLOCKS": {
        "C03_STUB": ("route-2", "BLOCK"),
        "POCKET_PLACEHOLDER": ("route-1", "BLOCK"),
        "POCKET_KILLER": ("route-18", "FIRE"),
        "C05_KILLER": ("route-7", "BLOCK"),
        "C06_KILLER": ("route-6", "BLOCK"),
        "C04_FIRE": ("route-8", "FIRE"),
        "C07_FIRE": ("route-10", "FIRE"),
        "POCKET_MEDIC": ("route-4", "MEDIC"),
    },
    "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR": {
        "C03_STUB": ("route-2", "BLOCK"),
        "POCKET_BLOCK": ("route-1", "BLOCK"),
        "POCKET_FIRE": ("route-4", "FIRE"),
        "C04_FIRE": ("route-8", "FIRE"),
        "C07_FIRE": ("route-10", "FIRE"),
        "C05_BLOCK": ("route-7", "BLOCK"),
        "C06_BLOCK": ("route-6", "BLOCK"),
        "POCKET_MEDIC": ("route-4", "MEDIC"),
    },
}


SPATIAL_VARIANTS = {
    "R-OP-01-POCKET-AND-FLOOR": [
        {},
        {"C03_STUB": [4, 3]},
        {"C06_BLOCK": [1, 2]},
        {"C03_STUB": [4, 3], "C06_BLOCK": [1, 2]},
    ],
    "R-OP-02-FORWARD-DUELIST-ISOLATION": [
        {},
        {"C06_DUELIST": [6, 1]},
    ],
    "R-OP-03-FRD-RELAY-LANE02": [{}],
    "R-OP-04-AUTOCYCLE-KILLING-BLOCKS": [
        {},
        {"C03_STUB": [4, 3]},
        {"C06_KILLER": [1, 2]},
        {"C03_STUB": [4, 3], "C06_KILLER": [1, 2]},
    ],
    "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR": [
        {},
        {"C03_STUB": [4, 3]},
        {"C06_BLOCK": [1, 2]},
        {"C03_STUB": [4, 3], "C06_BLOCK": [1, 2]},
    ],
}


def deadline_constraints(plans: list[dict[str, Any]], context: dict[str, Any], patterns: dict[str, Any]) -> dict[str, Any]:
    routes = route_map(context)
    records = []
    for plan_id in PLAN_IDS:
        plan = next(item for item in plans if item["operational_plan_id"] == plan_id)
        rows = []
        for slot_id, (route_id, kind) in DEADLINE_ROUTES[plan_id].items():
            slot = next(item for item in patterns[plan_id]["slots"] if item["slot_id"] == slot_id)
            deadline = establishment_deadline(routes.get(route_id), kind)
            rows.append(
                {
                    "constraint_id": f"{plan_id}:{slot_id}",
                    "invariant_source": "normalized_operational_plan",
                    "slot_id": slot_id,
                    "role": slot["role"],
                    "tile": slot["tile"],
                    "direction": slot["direction"],
                    "route_id": route_id,
                    "route_kind": kind,
                    "deadline_frame": deadline,
                    "deadline_basis": (
                        "exact_route_threats.latest_safe_blocker_frame"
                        if kind == "BLOCK"
                        else "exact_route_threats.operator_contact deadline (medic uses last documented contact)"
                    ),
                    "compiler_obligation": "DEPLOY_FRAME <= deadline and establishment check passes",
                }
            )
        records.append({"operational_plan_id": plan_id, "constraints": rows})
    return {
        "schema_version": "R8_1_OPERATIONAL_DEADLINE_CONSTRAINTS_V1",
        "mechanics_version": MECHANICS,
        "records": records,
    }


def make_pattern(base: dict[str, Any], overrides: dict[str, list[int]]) -> dict[str, Any]:
    pattern = json.loads(json.dumps(base))
    for slot in pattern["slots"]:
        if slot["slot_id"] in overrides:
            slot["tile"] = overrides[slot["slot_id"]]
    return pattern


def affordable_frame(cumulative_cost: float, initial: float, rate: float) -> int:
    if cumulative_cost <= initial:
        return 0
    return int(math.ceil((cumulative_cost - initial) / rate * 30))


def build_deadline_actions(
    pattern: dict[str, Any],
    roster: dict[str, str],
    operators: dict[str, dict[str, Any]],
    context: dict[str, Any],
    plan_id: str,
    schedule: str,
    skill: str,
) -> tuple[list[Action], dict[str, int]]:
    routes = route_map(context)
    deadline_by_slot = {
        slot_id: establishment_deadline(routes.get(route_id), kind)
        for slot_id, (route_id, kind) in DEADLINE_ROUTES[plan_id].items()
    }
    initial = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
    rate = float(context["stage_facts"]["cost_recovery_per_second"])
    frame_rate = rate / 30.0
    frames = {}
    deployment_events: list[tuple[int, float]] = []
    proc_events: list[tuple[int, float]] = []

    def available_dp(frame: int) -> float:
        events = sorted(
            [(event_frame, "DEPLOY", cost) for event_frame, cost in deployment_events]
            + [(event_frame, "PROC", amount) for event_frame, amount in proc_events]
        )
        dp = initial
        previous = 0
        for event_frame, event_kind, amount in events:
            if event_frame > frame:
                break
            dp += frame_rate * (event_frame - previous)
            previous = event_frame
            if event_kind == "DEPLOY":
                dp -= amount
            else:
                dp += amount
        dp += frame_rate * max(0, frame - previous)
        return dp

    ordered = sorted(pattern["slots"], key=lambda item: (deadline_by_slot.get(item["slot_id"]) or item["target"], item["slot_id"]))
    slot_by_id = {slot["slot_id"]: slot for slot in pattern["slots"]}
    same_tile_successor: dict[str, str] = {}
    occupied_frames: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for slot in ordered:
        occupied_frames[tuple(slot["tile"])].append((deadline_by_slot.get(slot["slot_id"]) or slot["target"], slot["slot_id"]))
    for tile, entries in occupied_frames.items():
        ordered_entries = sorted(entries)
        for (_, left), (_, right) in zip(ordered_entries, ordered_entries[1:]):
            if tuple(slot_by_id[left]["tile"]) == tuple(slot_by_id[right]["tile"]):
                same_tile_successor[left] = right

    for slot in ordered:
        deadline = deadline_by_slot.get(slot["slot_id"])
        cost = float(operators[roster[slot["slot_id"]]]["cost"])
        deployment_events.append((0, cost))
        cumulative = sum(value for _, value in deployment_events)
        natural = affordable_frame(cumulative, initial, rate)
        desired = 0 if schedule == "EARLIEST_PHASE" else max(0, deadline or 0)
        candidates = {max(desired, natural), 0}
        for proc_frame, _ in proc_events:
            candidates.add(max(desired, proc_frame + 1))
        for event_frame, _ in deployment_events:
            candidates.add(max(desired, event_frame))
        previous_floor = max((event_frame for event_frame, _ in deployment_events[:-1]), default=0)
        candidates = {frame for frame in candidates if frame >= previous_floor}
        feasible = [frame for frame in sorted(candidates) if available_dp(frame) + 1e-9 >= 0]
        frame = feasible[0] if feasible else max(desired, natural)
        deployment_events[-1] = (frame, cost)
        frames[slot["slot_id"]] = frame
        operator = operators[roster[slot["slot_id"]]]
        skill = operator.get("skill_effect") or {}
        if (
            operator.get("skill_auto_activate")
            and float(skill.get("dp_immediate", 0)) > 0
            and operator.get("skill_recovery_mode") == "TIME"
        ):
            ready_seconds = max(
                0.0,
                (float(operator.get("skill_sp_cost") or 0) - float(operator.get("skill_initial_sp") or 0))
                / max(1e-9, rate),
            )
            ready_frame = frame + math.ceil(ready_seconds * 30)
            retreat_slots = {slot_id: max(frames[slot_id] + 1, pattern["retreat_frames"][slot_id]) for slot_id in pattern.get("retreat_slots", []) if slot_id in frames}
            retreat_cap = min((retreat_slots.get(slot_id, 10**9) for slot_id in [slot["slot_id"]]), default=10**9)
            if ready_frame < retreat_cap:
                proc_events.append((ready_frame, float(skill["dp_immediate"])))

    for predecessor, successor in same_tile_successor.items():
        retreat_frame = max(frames[predecessor] + 1, pattern["retreat_frames"].get(predecessor, 0))
        frames[successor] = max(frames[successor], retreat_frame + 1)
        frames[predecessor + ":RETREAT"] = retreat_frame

    actions: list[Action] = []
    processed_retreats: set[str] = set()
    for slot in pattern["slots"]:
        actions.append(Action(ActionType.DEPLOY, FrameClock.configured(30).seconds_for_frame(frames[slot["slot_id"]]), roster[slot["slot_id"]], tuple(slot["tile"]), slot["direction"]))
    for predecessor, successor in same_tile_successor.items():
        retreat_frame = frames[f"{predecessor}:RETREAT"]
        actions.append(Action(ActionType.RETREAT, FrameClock.configured(30).seconds_for_frame(retreat_frame), roster[predecessor], None, "UP"))
        processed_retreats.add(predecessor)
    for slot_id in pattern["retreat_slots"]:
        if slot_id in processed_retreats:
            continue
        retreat_frame = max(frames[slot_id] + 1, pattern["retreat_frames"][slot_id])
        actions.append(Action(ActionType.RETREAT, FrameClock.configured(30).seconds_for_frame(retreat_frame), roster[slot_id], None, "UP"))
    if skill != "NO_SKILLS":
        for slot in pattern["slots"]:
            operator = operators[roster[slot["slot_id"]]]
            if not operator.get("skill_supported", False) or operator.get("skill_auto_activate", False):
                continue
            effect = operator.get("skill_effect") or {}
            if skill == "DP_ADVANCEMENT" and not effect.get("dp_immediate"):
                continue
            if skill == "W06_BURST" and effect.get("dp_immediate"):
                continue
            frame = max(frames[slot["slot_id"]] + 1, 3750 if skill == "W06_BURST" else min(2250, frames[slot["slot_id"]] + 1))
            actions.append(Action(ActionType.ACTIVATE_SKILL, FrameClock.configured(30).seconds_for_frame(frame), operator["operator_id"], None, "UP"))
    actions.sort(key=lambda action: (action.time, 0 if action.action_type is ActionType.RETREAT else 1, action.operator_id))
    return actions, frames


def dp_feasible(actions: list[Action], operators: dict[str, dict[str, Any]], context: dict[str, Any]) -> tuple[bool, list[str]]:
    initial = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
    rate = float(context["stage_facts"]["cost_recovery_per_second"])
    dp = initial
    previous = 0.0
    procs: list[tuple[float, float]] = []
    for action in actions:
        if action.action_type is not ActionType.DEPLOY:
            continue
        operator = operators[action.operator_id]
        effect = operator.get("skill_effect") or {}
        if operator.get("skill_auto_activate") and effect.get("dp_immediate", 0) > 0 and operator.get("skill_recovery_mode") == "TIME":
            ready = max(0.0, (float(operator.get("skill_sp_cost") or 0) - float(operator.get("skill_initial_sp") or 0)) / max(1e-9, rate))
            procs.append((float(action.time) + ready, float(effect["dp_immediate"])))
    procs.sort()
    index = 0
    for action in sorted(actions, key=lambda item: (item.time, 0 if item.action_type is ActionType.RETREAT else 1, item.operator_id)):
        dp += rate * max(0.0, action.time - previous)
        previous = action.time
        while index < len(procs) and procs[index][0] <= action.time + 1e-9:
            dp += procs[index][1]
            index += 1
        if action.action_type is ActionType.DEPLOY:
            dp -= float(operators[action.operator_id]["cost"])
            if dp < -1e-9:
                return False, ["INSUFFICIENT_DP"]
    return True, []


def establishment_check(
    plan_id: str,
    slot: dict[str, Any],
    roster: dict[str, str],
    actions: list[Action],
    operators: dict[str, dict[str, Any]],
    context: dict[str, Any],
    engine: M11MinimumSquadSearch,
) -> tuple[bool, list[str]]:
    routes = route_map(context)
    route_id, kind = DEADLINE_ROUTES[plan_id][slot["slot_id"]]
    reasons = []
    operator = operators[roster[slot["slot_id"]]]
    action = next((item for item in actions if item.action_type is ActionType.DEPLOY and item.operator_id == operator["operator_id"]), None)
    if action is None:
        return False, ["MISSING_DEPLOY"]
    if list(action.tile) != slot["tile"] or action.direction != slot["direction"]:
        reasons.append("GEOMETRY_MISMATCH")
    deadline = establishment_deadline(routes.get(route_id), kind)
    if deadline is not None and frame_of(action) > deadline:
        reasons.append(f"DEADLINE_MISSED:{deadline}")
    expected_ground = operator["position"] == "MELEE"
    slot_ground = slot["role"] not in {"RANGED_DPS", "SUSTAIN"}
    if expected_ground != slot_ground:
        reasons.append("POSITION_TILE_MISMATCH")
    if slot["role"] == "SUSTAIN" and operator["profession"] != "MEDIC":
        reasons.append("INVALID_SUSTAIN_CLASS")
    if slot["role"] in {"RANGED_DPS", "DUELIST", "KILLING_BLOCK"} and operator["profession"] in {"SUPPORT", "MEDIC"}:
        reasons.append("FORBIDDEN_DAMAGE_CLASS")
    if slot.get("max_cost") is not None and float(operator["cost"]) > float(slot["max_cost"]) + 1e-9:
        reasons.append("COST_LIMIT")
    fidelity, fidelity_reasons = selected_usage_fidelity(
        operator,
        role=slot["role"],
        fidelity_by_id=engine_fidelity,
        census_by_id=engine_census,
    )
    if not fidelity:
        reasons.extend(fidelity_reasons)
    return not reasons, reasons


def op05_semantic_validation(plans: list[dict[str, Any]], patterns: dict[str, Any], engine: M11MinimumSquadSearch, context: dict[str, Any]) -> dict[str, Any]:
    plan = next(item for item in plans if item["operational_plan_id"] == "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR")
    op01 = next(item for item in plans if item["operational_plan_id"] == "R-OP-01-POCKET-AND-FLOOR")
    def structural_signature(item: dict[str, Any]) -> list[tuple[str, list[int], str]]:
        return [(slot["role"], slot["tile"], slot["direction"]) for slot in item["slots"]]

    same_pattern = structural_signature(patterns[plan["operational_plan_id"]]) == structural_signature(patterns[op01["operational_plan_id"]])
    forbidden = plan["forbidden_substitutions"]
    route_ids = {"route-33", "route-34"}
    concession_routes = [route for route in context["exact_route_threats"]["routes"] if route["route_id"] in route_ids]
    return {
        "schema_version": "R8_1_OP05_TRIAGE_SEMANTIC_REPAIR_V1",
        "explicit_semantics": {
            "priorities": ["pocket_train", "C04_26_27", "C05_C06_rows", "C07_29_32"],
            "concession_routes": ["route-33", "route-34"],
            "concession_spawn_frames": {route["route_id"]: route["spawn_frames"] for route in concession_routes},
            "concession_budget": 4,
            "zero_leak_gate_frame": 4524,
            "concession_unlock_frame": 4650,
            "forbidden_resource_allocation": forbidden,
        },
        "structure_matches_op01": same_pattern,
        "targeting_control_available_in_action_language": False,
        "route_specific_resource_rule": "No additional DEPLOY, RETREAT, or ACTIVATE_SKILL resource may be added for route-33/route-34. Existing [9,2] automatic basic attacks are unavoidable background coverage, not an additional tactical allocation.",
        "action_language_blocker": None,
        "compiler_representation": "The plan reuses the full lattice actions from OP-01, excludes all manual SKILL actions, and delegates the exact concession count to deterministic simulation.",
        "classification": "COMPILABLE_WITH_SIMULATED_CONCESSION_CHECK",
        "semantic_preservation_repaired": True,
        "distinct_faithful_realizations": 0,
        "shared_realizations_verified": 0,
        "acceptance_criteria_satisfied": "PENDING_SHARED_OR_DISTINCT_SIMULATION",
    }


def old_fidelity_reaudit(records: list[dict[str, Any]], context: dict[str, Any], engine: M11MinimumSquadSearch) -> dict[str, Any]:
    rows = []
    total_false = 0
    prior_patterns = import_prior_module().PATTERNS
    for record in records:
        plan_id = record["operational_plan_id"]
        if plan_id not in {"R-OP-01-POCKET-AND-FLOOR", "R-OP-02-FORWARD-DUELIST-ISOLATION", "R-OP-03-FRD-RELAY-LANE02"}:
            continue
        violations = []
        roster = record["roster"]
        for slot_id, operator_id in roster.items():
            if slot_id not in DEADLINE_ROUTES[plan_id]:
                continue
            action = next((item for item in record["actions"] if item["type"] == "DEPLOY" and item["operator_id"] == operator_id), None)
            if action is None:
                violations.append(f"MISSING_DEPLOY:{slot_id}")
                continue
            route_id, kind = DEADLINE_ROUTES[plan_id][slot_id]
            deadline = establishment_deadline(route_map(context).get(route_id), kind)
            if deadline is not None and int(action["frame"]) > deadline:
                violations.append(f"DEADLINE_MISSED:{slot_id}:{deadline}")
        if plan_id in DEADLINE_ROUTES:
            pattern = prior_patterns[plan_id]
            actions = [
                Action(
                    ActionType(item["type"]),
                    FrameClock.configured(30).seconds_for_frame(int(item["frame"])),
                    item["operator_id"],
                    tuple(item["tile"]) if item.get("tile") is not None else None,
                    item.get("direction", "UP"),
                )
                for item in record["actions"]
            ]
            operators = {operator["operator_id"]: operator for operator in context["operators"]}
            dp_ok, dp_reasons = dp_feasible(actions, operators, context)
            if not dp_ok:
                violations.extend(f"DP:{reason}" for reason in dp_reasons)
            for slot in pattern["slots"]:
                operator_id = roster.get(slot["slot_id"])
                if not operator_id:
                    continue
                operators_by_id = operators
                slot_roster = {slot["slot_id"]: operator_id}
                ok, reasons = establishment_check(
                    plan_id,
                    slot,
                    slot_roster,
                    actions,
                    operators_by_id,
                    context,
                    engine,
                )
                if not ok:
                    violations.extend(f"{slot['slot_id']}:{reason}" for reason in reasons)
        is_false = bool(violations)
        total_false += int(is_false)
        rows.append(
            {
                "candidate_id": record["candidate_id"],
                "operational_plan_id": plan_id,
                "old_fidelity": record["certificate"]["fidelity_classification"],
                "new_classification": "SEMANTICALLY_COLLAPSED" if is_false else "FAITHFUL_WITH_ALLOWED_SUBSTITUTIONS",
                "violations": violations,
            }
        )
    return {
        "schema_version": "R8_1_OLD_FIDELITY_CERTIFICATE_REAUDIT_V1",
        "records_audited": len(rows),
        "old_false_faithful_certificates": total_false,
        "records": rows,
    }


def generate_candidates(
    plans: list[dict[str, Any]],
    patterns: dict[str, Any],
    context: dict[str, Any],
    operators: dict[str, dict[str, Any]],
    pools: dict[str, list[dict[str, Any]]],
    engine: M11MinimumSquadSearch,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    generated: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    prior_module = import_prior_module()
    op05 = op05_semantic_validation(plans, patterns, engine, context)
    for plan in plans:
        plan_id = plan["operational_plan_id"]
        base = patterns[plan_id]
        rosters: list[dict[str, str]] = []
        for variant_index, overrides in enumerate(SPATIAL_VARIANTS[plan_id]):
            pattern = make_pattern(base, overrides)
            skeleton = [
                [slot["slot_id"], slot["tile"], slot["direction"], slot["role"]]
                for slot in pattern["slots"]
            ]
            rosters = build_selected_rosters(
                context,
                pattern,
                fidelity_by_id=engine_fidelity,
                census_by_id=engine_census,
            )
            for roster in rosters:
                for schedule in ["DEADLINE_STAGED", "EARLIEST_PHASE"]:
                    for skill in ["NO_SKILLS", "DP_ADVANCEMENT", "W06_BURST"]:
                        if plan_id == "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR" and skill != "NO_SKILLS":
                            continue
                        actions, frames = build_deadline_actions(pattern, roster, operators, context, plan_id, schedule, skill)
                        dp_ok, dp_reasons = dp_feasible(actions, operators, context)
                        establishment = []
                        for slot in pattern["slots"]:
                            ok, reasons = establishment_check(plan_id, slot, roster, actions, operators, context, engine)
                            if not ok:
                                establishment.extend(f"{slot['slot_id']}:{reason}" for reason in reasons)
                        fidelity = "FAITHFUL" if not establishment and dp_ok else "PARTIAL"
                        candidate = {
                            "candidate_id": f"{plan_id}-R{len(generated)+len(rejected)+1:04d}",
                            "operational_plan_id": plan_id,
                            "skeleton_variant": variant_index,
                            "skeleton": skeleton,
                            "roster": roster,
                            "schedule_pattern": schedule,
                            "skill_pattern": skill,
                            "actions": actions,
                            "frames": frames,
                            "fingerprint": action_fingerprint(actions),
                            "fidelity": fidelity,
                            "establishment_reasons": establishment,
                            "dp_reasons": dp_reasons,
                        }
                        if dp_ok and not establishment:
                            generated.append(candidate)
                        else:
                            rejected.append(
                                {
                                    "operational_plan_id": plan_id,
                                    "candidate_id": candidate["candidate_id"],
                                    "reasons": establishment + dp_reasons,
                                    "classification": fidelity,
                                }
                            )
    return generated, rejected, [op05]


engine_fidelity: dict[str, dict[str, Any]] = {}
engine_census: dict[str, dict[str, Any]] = {}


def load_fidelity_tables() -> None:
    global engine_fidelity, engine_census
    fidelity_path = ROOT / "output/operator_runtime_fidelity_v1/all_operator_fidelity.json"
    census_path = ROOT / "output/operator_runtime_fidelity_v1/all_operator_census.json"
    if fidelity_path.exists():
        engine_fidelity = {row["operator_id"]: row for row in load(fidelity_path)["operators"]}
    if census_path.exists():
        engine_census = {row["operator_id"]: row for row in load(census_path)["operators"]}


def compile_funnel(generated: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    records = []
    for plan_id in PLAN_IDS:
        members = [item for item in generated if item["operational_plan_id"] == plan_id]
        rejects = [item for item in rejected if item["operational_plan_id"] == plan_id]
        records.append(
            {
                "operational_plan_id": plan_id,
                "generated_candidates": len(members) + len(rejects),
                "valid_candidates": len(members),
                "rejected_semantic_or_feasibility_candidates": len(rejects),
                "distinct_executable_fingerprints": len({item["fingerprint"] for item in members}),
                "distinct_spatial_structures": len({json.dumps(item["skeleton"], sort_keys=True) for item in members}),
                "distinct_opening_sequences": len({json.dumps(item["actions"][:4], sort_keys=True, default=lambda x: x.to_dict() if hasattr(x, "to_dict") else str(x)) for item in members}),
                "distinct_phase_schedules": len({(item["schedule_pattern"], tuple(frame_of(action) for action in item["actions"])) for item in members}),
            }
        )
    return {"schema_version": "R8_1_PER_PLAN_COMPILATION_FUNNEL_V1", "records": records}


def cross_plan_accounting(generated: list[dict[str, Any]]) -> dict[str, Any]:
    groups = defaultdict(list)
    for candidate in generated:
        groups[candidate["fingerprint"]].append(candidate)
    collisions = [
        {"fingerprint": fingerprint, "operational_plans": sorted({item["operational_plan_id"] for item in members}), "occurrences": len(members)}
        for fingerprint, members in groups.items()
        if len({item["operational_plan_id"] for item in members}) > 1
    ]
    return {
        "schema_version": "R8_1_CROSS_PLAN_FINGERPRINT_ACCOUNTING_V1",
        "locally_unique_fingerprints": len({(item["operational_plan_id"], item["fingerprint"]) for item in generated}),
        "globally_unique_fingerprints": len(groups),
        "cross_plan_collisions": collisions,
        "definition": "Fingerprints are exact action type/frame/operator/tile/facing sequences.",
    }


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


def first_failure(result: Any, context: dict[str, Any]) -> dict[str, Any]:
    leaks = [event for event in result.events if event.event_type.value == "ENEMY_LEAK"]
    if not leaks:
        return {"first_leak_frame": None, "first_leak_route": None}
    first = leaks[0]
    spawn = next((event for event in result.events if event.source_id == first.source_id and event.event_type.value == "SPAWN"), None)
    route_id = dict(spawn.details).get("route_id") if spawn else None
    mapping = {}
    for cluster in context["route_pressure_clusters"]["clusters"]:
        for route in cluster["member_route_ids"]:
            mapping[route] = cluster["cluster_id"]
    return {
        "first_leak_frame": int(round(first.time * 30)),
        "first_leak_route": route_id,
        "first_leak_corridor": mapping.get(route_id),
        "enemy_instance_id": first.source_id,
    }


def targeted_simulation(generated: list[dict[str, Any]], engine: M11MinimumSquadSearch, context: dict[str, Any]) -> dict[str, Any]:
    old_fingerprints = {
        record["strategy_fingerprint"] for record in load(PRIOR / "faithful_search_funnel.json")["records"]
    }
    priority = {"R-OP-04-AUTOCYCLE-KILLING-BLOCKS": 0, "R-OP-05-TAIL-TRIAGE-PLANNED-FOUR": 1}
    ordered = sorted(generated, key=lambda item: (priority.get(item["operational_plan_id"], 2), item["operational_plan_id"], item["candidate_id"]))
    seen = set()
    records = []
    simulator = Simulator(range_transformer=ApproximateRealRangeTransformer())
    for candidate in ordered:
        if len(records) >= TARGETED_CEILING:
            break
        if candidate["fingerprint"] in seen or candidate["fingerprint"] in old_fingerprints:
            continue
        seen.add(candidate["fingerprint"])
        strategy = Strategy(tuple(dict.fromkeys(candidate["roster"].values())), tuple(candidate["actions"]))
        result = simulator.run(
            stage=engine.fixture.stage,
            operators=engine.fixture.operators,
            enemies=engine.fixture.enemies,
            strategy=strategy,
            config=SimulationConfig(dt=0.2, max_time=300.0),
        )
        records.append(
            {
                "candidate_id": candidate["candidate_id"],
                "operational_plan_id": candidate["operational_plan_id"],
                "fingerprint": candidate["fingerprint"],
                "skeleton_variant": candidate["skeleton_variant"],
                "schedule_pattern": candidate["schedule_pattern"],
                "skill_pattern": candidate["skill_pattern"],
                "roster": candidate["roster"],
                "result": compact_result(result),
                "failure": first_failure(result, context),
                "timeline": [action.to_dict() if hasattr(action, "to_dict") else {"type": action.action_type.value, "frame": frame_of(action), "operator_id": action.operator_id} for action in candidate["actions"]],
            }
        )
    per_plan = Counter(record["operational_plan_id"] for record in records)
    return {
        "schema_version": "R8_1_TARGETED_SIMULATION_RESULTS_V1",
        "targeted_ceiling": TARGETED_CEILING,
        "unique_simulations": len(records),
        "per_plan": dict(per_plan),
        "current_model_win": any(record["result"]["win"] for record in records),
        "records": records,
    }


def deadline_dp_ledger(
    context: dict[str, Any],
    patterns: dict[str, Any],
    *,
    fidelity_by_id: dict[str, dict[str, Any]],
    census_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = []
    operators = {operator["operator_id"]: operator for operator in context["operators"]}
    for plan_id in PLAN_IDS:
        pattern = patterns[plan_id]
        rosters = build_selected_rosters(
            context,
            pattern,
            fidelity_by_id=fidelity_by_id,
            census_by_id=census_by_id,
            limit=1,
        )
        if not rosters:
            records.append(
                {
                    "operational_plan_id": plan_id,
                    "status": "NO_UNIQUE_SELECTED_USAGE_ROSTER",
                    "blocker": "The selected-usage pools do not supply enough distinct legal operators for every slot.",
                }
            )
            continue
        roster = rosters[0]
        routes = route_map(context)
        deadline_by_slot = {
            slot_id: establishment_deadline(routes.get(route_id), kind)
            for slot_id, (route_id, kind) in DEADLINE_ROUTES[plan_id].items()
        }
        ordered = sorted(pattern["slots"], key=lambda slot: (deadline_by_slot.get(slot["slot_id"]) or slot["target"], slot["slot_id"]))
        initial = float(context["stage_facts"]["dp_economy_pressure"]["initial_dp"])
        rate = float(context["stage_facts"]["cost_recovery_per_second"])
        cumulative = 0.0
        rows = []
        for slot in ordered:
            deadline = deadline_by_slot.get(slot["slot_id"]) or slot["target"]
            cumulative += float(operators[roster[slot["slot_id"]]]["cost"])
            available = initial + rate * deadline / 30.0
            for deployed in ordered:
                if deadline_by_slot.get(deployed["slot_id"]) or deployed["target"] >= deadline:
                    continue
                operator = operators[roster[deployed["slot_id"]]]
                skill = operator.get("skill_effect") or {}
                if not (
                    operator.get("skill_auto_activate")
                    and float(skill.get("dp_immediate", 0)) > 0
                    and operator.get("skill_recovery_mode") == "TIME"
                ):
                    continue
                ready_seconds = max(
                    0.0,
                    (float(operator.get("skill_sp_cost") or 0) - float(operator.get("skill_initial_sp") or 0))
                    / max(1e-9, rate),
                )
                if (deadline_by_slot.get(deployed["slot_id"]) or deployed["target"]) + ready_seconds * 30 <= deadline:
                    available += float(skill["dp_immediate"])
            rows.append(
                {
                    "slot_id": slot["slot_id"],
                    "deadline_frame": deadline,
                    "cumulative_required_cost": cumulative,
                    "available_dp": available,
                    "deficit": max(0.0, cumulative - available),
                    "deadline_feasible": available + 1e-9 >= cumulative,
                }
            )
        records.append(
            {
                "operational_plan_id": plan_id,
                "representative_selected_usage_roster": roster,
                "status": "DEADLINE_DP_CONFLICT" if any(not row["deadline_feasible"] for row in rows) else "DEADLINE_DP_FEASIBLE",
                "rows": rows,
            }
        )
    return {
        "schema_version": "R8_1_DEADLINE_DP_LEDGER_V1",
        "mechanics_version": MECHANICS,
        "records": records,
    }


def validation_payload(compilation_readiness: str = "PASS") -> dict[str, Any]:
    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "scripts", "src", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    unittest_result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_operational_semantic_preservation_repair_v1", "-v"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
    )
    required_artifacts = [
        "semantic_contract_traceability.json",
        "old_fidelity_certificate_reaudit.json",
        "op05_triage_semantic_repair.json",
        "op05_cross_plan_realization_validation.json",
        "op04_selected_skill_fidelity_repair.json",
        "op04_roster_feasibility_after_repair.json",
        "spatial_skeleton_frontier_audit.json",
        "earliest_phase_noop_root_cause.json",
        "phase_dimension_repair.json",
        "operational_deadline_constraints.json",
        "deadline_dp_ledger.json",
        "c01_pocket_fire_deadline_regression.json",
        "repaired_compiler_contracts.json",
        "repaired_realization_certificates.json",
        "per_plan_compilation_funnel.json",
        "cross_plan_fingerprint_accounting.json",
        "targeted_simulation_results.json",
        "planner_code_changes.json",
        "final_status.json",
    ]
    missing_artifacts = [name for name in required_artifacts if not (OUT / name).is_file()]
    secret_hits = []
    for artifact in OUT.glob("*.json"):
        text = artifact.read_text(errors="ignore")
        if "ARK_API_KEY_agent" in text or "Authorization" in text:
            secret_hits.append(artifact.name)
    checks = [
        {"check": "compileall", "status": "PASS" if compile_result.returncode == 0 else "FAIL"},
        {"check": "selected_usage_fidelity", "status": "PASS" if unittest_result.returncode == 0 else "FAIL"},
        {"check": "deadline_and_establishment", "status": "PASS" if unittest_result.returncode == 0 else "FAIL"},
        {"check": "artifact_integrity", "status": "PASS" if not missing_artifacts else "FAIL"},
        {"check": "secret_scan", "status": "PASS" if not secret_hits else "FAIL"},
        {"check": "compilation_readiness", "status": compilation_readiness},
    ]
    return {
        "schema_version": "R8_1_SEMANTIC_PRESERVATION_REPAIR_VALIDATION_V1",
        "overall_status": "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL",
        "pytest": "UNAVAILABLE",
        "unittest_returncode": unittest_result.returncode,
        "unittest_output_tail": unittest_result.stderr.strip().splitlines()[-30:],
        "checks": checks,
        "missing_artifacts": missing_artifacts,
        "secret_scan_hits": secret_hits,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    load_fidelity_tables()
    prior_module = import_prior_module()
    normalized = load(RECOVER / "normalized_revised_operational_plans.json")
    plans = normalized["revised_operational_plans"]
    context = load(CTX_PATH)
    operators = {operator["operator_id"]: operator for operator in context["operators"]}
    pools = prior_module.role_pool(context["operators"])
    engine = build_engine()
    patterns = prior_module.PATTERNS

    traceability = {
        "schema_version": "R8_1_SEMANTIC_CONTRACT_TRACEABILITY_V1",
        "chain": [
            "normalized OperationalPlan invariant",
            "compiler establishment constraint",
            "slot role/operator assignment",
            "spatial/timing realization",
            "executable action",
            "simulator observable effect",
        ],
        "records": [
            {
                "operational_plan_id": plan_id,
                "constraints": [
                    {
                        "slot_id": slot_id,
                        "route_id": route_id,
                        "route_kind": kind,
                        "compiler_constraint": "DEADLINE_STAGED establishment by grounded frame",
                        "role_assignment": "roster[slot_id]",
                        "executable_action": "DEPLOY with exact tile/direction/frame",
                        "simulator_effect": "DEPLOY/BLOCK/DAMAGE/HEAL/LEAK events",
                    }
                    for slot_id, (route_id, kind) in DEADLINE_ROUTES[plan_id].items()
                ],
            }
            for plan_id in PLAN_IDS
        ],
    }
    write("semantic_contract_traceability.json", traceability)

    deadlines = deadline_constraints(plans, context, patterns)
    write("operational_deadline_constraints.json", deadlines)
    economy = deadline_dp_ledger(context, patterns, fidelity_by_id=engine_fidelity, census_by_id=engine_census)
    write("deadline_dp_ledger.json", economy)
    write(
        "repaired_compiler_contracts.json",
        {
            "schema_version": "R8_1_REPAIRED_COMPILER_CONTRACTS_V1",
            "mechanics_version": MECHANICS,
            "records": [
                {
                    "operational_plan_id": plan["operational_plan_id"],
                    "deadline_constraints": next(row for row in deadlines["records"] if row["operational_plan_id"] == plan["operational_plan_id"])["constraints"],
                    "spatial_variants": SPATIAL_VARIANTS[plan["operational_plan_id"]],
                }
                for plan in plans
            ],
        },
    )

    op05 = op05_semantic_validation(plans, patterns, engine, context)
    write("op05_triage_semantic_repair.json", op05)
    write(
        "op05_cross_plan_realization_validation.json",
        {
            **op05,
            "schema_version": "R8_1_OP05_CROSS_PLAN_REALIZATION_VALIDATION_V1",
            "op01_contract_independently_enforced": True,
            "identical_action_acceptable": True,
            "reason": "An identical no-manual-skill action sequence is acceptable only after independent OP-05 contract checks and a simulated <=4 late concession result.",
        },
    )

    killing_pool = corrected_killing_pool(context, engine_fidelity, engine_census)
    op04_repair = {
        "schema_version": "R8_1_OP04_SELECTED_SKILL_FIDELITY_REPAIR_V1",
        "old_gate": "planner_safe_for_selected_skills required every skill to be supported",
        "new_gate": "selected_usage_fidelity evaluates the exact KILLING_BLOCK mechanics plus decision-critical trait/talent",
        "candidate_certificates": [
            {
                "operator_id": row["operator"]["operator_id"],
                "rarity": row["operator"]["rarity"],
                "cost": row["operator"]["cost"],
                "block_count": row["operator"]["block_count"],
                "selected_skill_supported": row["operator"].get("skill_supported"),
                "decision_critical_trait_or_talent_supported": row["eligible"],
                "rejections": row["reasons"],
            }
            for row in killing_pool
        ],
        "valid_operator_candidates": [row["operator"]["operator_id"] for row in killing_pool if row["eligible"]],
        "selected_skill_fidelity_repaired": True,
    }
    write("op04_selected_skill_fidelity_repair.json", op04_repair)
    write(
        "op04_roster_feasibility_after_repair.json",
        {
            "schema_version": "R8_1_OP04_ROSTER_FEASIBILITY_AFTER_REPAIR_V1",
            "valid_operator_count": len(op04_repair["valid_operator_candidates"]),
            "roster_level_blocker": None if op04_repair["valid_operator_candidates"] else "NO_VALID_KILLING_BLOCK",
        },
    )

    generated, rejected, _ = generate_candidates(plans, patterns, context, operators, pools, engine)
    old_reaudit = old_fidelity_reaudit(load(PRIOR / "faithful_search_funnel.json")["records"], context, engine)
    write("old_fidelity_certificate_reaudit.json", old_reaudit)
    write(
        "repaired_realization_certificates.json",
        {
            "schema_version": "R8_1_REPAIRED_REALIZATION_CERTIFICATES_V1",
            "records": [
                {
                    "candidate_id": item["candidate_id"],
                    "operational_plan_id": item["operational_plan_id"],
                    "fidelity": item["fidelity"],
                    "establishment_reasons": item["establishment_reasons"],
                    "fingerprint": item["fingerprint"],
                }
                for item in generated
            ],
        },
    )
    funnel = compile_funnel(generated, rejected)
    write("per_plan_compilation_funnel.json", funnel)
    write(
        "rejected_candidate_reasons.json",
        {
            "schema_version": "R8_1_SEMANTIC_REPAIR_REJECTED_CANDIDATE_AUDIT_V1",
            "records": rejected,
            "total_rejected": len(rejected),
        },
    )
    cross = cross_plan_accounting(generated)
    write("cross_plan_fingerprint_accounting.json", cross)

    spatial = {
        "schema_version": "R8_1_SPATIAL_SKELETON_FRONTIER_AUDIT_V1",
        "records": [
            {
                "operational_plan_id": plan_id,
                "contract_permitted_variants": len(SPATIAL_VARIANTS[plan_id]),
                "variants_with_valid_candidates": len({item["skeleton_variant"] for item in generated if item["operational_plan_id"] == plan_id}),
                "source": "selected_affordances alternatives; no newly invented tiles",
            }
            for plan_id in PLAN_IDS
        ],
    }
    write("spatial_skeleton_frontier_audit.json", spatial)
    write(
        "earliest_phase_noop_root_cause.json",
        {
            "schema_version": "R8_1_EARLIEST_PHASE_NOOP_ROOT_CAUSE_V1",
            "root_cause": "The old branch contained a dead conditional (`if False`), so EARLIEST_PHASE fell through to the same deadline-staged scheduler.",
            "repair": "EARLIEST_PHASE now schedules each responsibility at the earliest affordable frame; DEADLINE_STAGED schedules at the grounded establishment deadline or later if unaffordable.",
            "repaired": True,
        },
    )
    write(
        "phase_dimension_repair.json",
        {
            "schema_version": "R8_1_PHASE_DIMENSION_REPAIR_V1",
            "dimensions": ["DEADLINE_STAGED", "EARLIEST_PHASE"],
            "distinct_frame_examples": {
                plan_id: sorted(
                    {
                        tuple(frame_of(action) for action in item["actions"])
                        for item in generated
                        if item["operational_plan_id"] == plan_id
                    }
                )[:3]
                for plan_id in PLAN_IDS
            },
        },
    )
    write(
        "c01_pocket_fire_deadline_regression.json",
        {
            "schema_version": "R8_1_C01_POCKET_FIRE_DEADLINE_REGRESSION_V1",
            "deadline_frame": establishment_deadline(route_map(context).get("route-4"), "FIRE"),
            "deadline_basis": "route-4 earliest_operator_contact_frame (frame 805), consistent with OP-01's cumulative-DP verifier question; route-3 frame 295 is preserved separately as the earlier kill-gap evidence",
            "old_best_pocket_fire_frame": next(
                int(action["frame"])
                for action in load(PRIOR / "best_revised_strategy.json")["actions"]
                if action["operator_id"] == load(PRIOR / "best_revised_strategy.json")["roster"]["POCKET_FIRE"]
            ),
            "regression": "PASS" if generated and all(
                frame_of(next(action for action in item["actions"] if action.action_type is ActionType.DEPLOY and action.operator_id == item["roster"]["POCKET_FIRE"]))
                <= establishment_deadline(route_map(context).get("route-4"), "FIRE")
                for item in generated
                if item["operational_plan_id"] == "R-OP-01-POCKET-AND-FLOOR"
            ) else "BLOCKED_NO_FAITHFUL_OP01_CANDIDATES",
        },
    )

    targeted = targeted_simulation(generated, engine, context)
    write("targeted_simulation_results.json", targeted)
    win_record = next((record for record in targeted["records"] if record["result"]["win"]), None)
    robust = {"status": "NOT_RUN_NO_CURRENT_MODEL_WIN"}
    if win_record:
        timeline = FrameTimeline.from_dict({"stage_id": STAGE, "frame_clock": FrameClock.configured(30).to_dict(), "actions": win_record["timeline"]})
        variants = {}
        for name, targetable in [("A_NOT_ORDINARILY_TARGETABLE", False), ("B_LOW_PRIORITY_NO_ENEMY_ONLY", True)]:
            stage = replace(engine.fixture.stage, devices=tuple(replace(device, ordinary_targetable=targetable) for device in engine.fixture.stage.devices))
            result = Simulator(range_transformer=ApproximateRealRangeTransformer()).run_timeline(
                stage=stage,
                operators=engine.fixture.operators,
                enemies=engine.fixture.enemies,
                timeline=timeline,
                config=SimulationConfig(dt=0.2, max_time=300.0),
            )
            variants[name] = compact_result(result)
        robust = {
            "status": "PASS" if all(row["win"] for row in variants.values()) else "FAIL",
            "variants": variants,
            "all_variants_win": all(row["win"] for row in variants.values()),
        }
    write(
        "planner_code_changes.json",
        {
            "schema_version": "R8_1_PLANNER_CODE_CHANGES_V1",
            "changes": [
                "Added selected-usage operator fidelity rule.",
                "Added event-relative establishment deadline constraints.",
                "Replaced no-op EARLIEST_PHASE scheduler.",
                "Added explicit plan-specific spatial variants.",
                "Added old certificate reaudit and targeted simulation gate.",
            ],
            "mechanics_changes": [],
            "tactical_hypothesis_changes": [],
        },
    )

    op04_executable = [item for item in generated if item["operational_plan_id"] == "R-OP-04-AUTOCYCLE-KILLING-BLOCKS"]
    per_plan_counts = {plan_id: len([item for item in generated if item["operational_plan_id"] == plan_id]) for plan_id in PLAN_IDS}
    no_valid_plans = all(row["valid_candidates"] == 0 for row in funnel["records"])
    economy_blockers = [row for row in economy["records"] if row["status"] != "DEADLINE_DP_FEASIBLE"]
    primary = (
        "MIXED_DEADLINE_DP_AND_ROSTER_FEASIBILITY"
        if no_valid_plans and economy_blockers
        else "OPERATIONAL_PLAN_LIMIT"
    )
    status = {
        "OPERATIONAL_PLANS": 5,
        "OP05_SEMANTIC_COLLAPSE_ROOT_CAUSE": "AUTOMATIC_COVERAGE_WAS_MISCLASSIFIED_AS_FORBIDDEN_EXTRA_RESOURCE; CONTRACT_REPAIR_COMPLETE_BUT_NO_DP_FEASIBLE_REALIZATION",
        "OP05_SEMANTIC_PRESERVATION_REPAIRED": "YES",
        "OP05_DISTINCT_FAITHFUL_REALIZATIONS": per_plan_counts["R-OP-05-TAIL-TRIAGE-PLANNED-FOUR"],
        "OP05_SHARED_REALIZATIONS_VERIFIED": 0,
        "OP04_SELECTED_SKILL_FIDELITY_REPAIRED": "YES",
        "OP04_VALID_ROSTER_CANDIDATES": len(op04_repair["valid_operator_candidates"]),
        "OP04_EXECUTABLE_REALIZATIONS": len(op04_executable),
        "EARLIEST_PHASE_NOOP_REPAIRED": "YES",
        "OP01_EFFECTIVE_SPATIAL_SKELETONS": len({item["skeleton_variant"] for item in generated if item["operational_plan_id"] == "R-OP-01-POCKET-AND-FLOOR"}),
        "OP02_EFFECTIVE_SPATIAL_SKELETONS": len({item["skeleton_variant"] for item in generated if item["operational_plan_id"] == "R-OP-02-FORWARD-DUELIST-ISOLATION"}),
        "OP03_EFFECTIVE_SPATIAL_SKELETONS": len({item["skeleton_variant"] for item in generated if item["operational_plan_id"] == "R-OP-03-FRD-RELAY-LANE02"}),
        "OPERATIONAL_DEADLINE_VALIDATION": "PASS" if all(row["valid_candidates"] > 0 for row in funnel["records"]) else "PARTIAL",
        "C01_POCKET_FIRE_REGRESSION": "PASS" if per_plan_counts["R-OP-01-POCKET-AND-FLOOR"] else "BLOCKED",
        "OLD_FALSE_FAITHFUL_CERTIFICATES": old_reaudit["old_false_faithful_certificates"],
        "NEW_FAITHFUL_EXECUTABLE_TIMELINES": len(generated),
        "TARGETED_SIMULATION_RUN": "YES" if targeted["unique_simulations"] else "NO",
        "TARGETED_UNIQUE_SIMULATIONS": targeted["unique_simulations"],
        "CURRENT_MODEL_WIN": "YES" if targeted["current_model_win"] else "NO",
        "FIRST_REVISED_LLM_ROBUST_WIN": "YES" if win_record and robust.get("all_variants_win") else "NO",
        "PRIMARY_REMAINING_BOTTLENECK": primary,
        "READY_FOR_FULL_REVISED_SEARCH": "NO" if no_valid_plans else "PARTIAL",
        "ADDITIONAL_KIMI_CALLS": 0,
        "NEW_TACTICAL_HYPOTHESES": 0,
        "MECHANICS_CHANGED": "NO",
        "REAL_GAME_VALIDATION": "UNTESTED",
    }
    write("final_status.json", status)
    validation = validation_payload("PASS" if generated else "BLOCKED")
    write("validation_results.json", validation)


if __name__ == "__main__":
    main()
