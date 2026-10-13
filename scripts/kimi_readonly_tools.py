from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from arknights_planner.simulator.range import ApproximateRealRangeTransformer


ROOT = Path(__file__).resolve().parents[1]
DATA_VERSION = "GameData 0ef7f952dfd018392200157a5c79a6511ba69122"
MECHANICS_VERSION = "m18.9-stage-device-runtime-v1"
NORMAL_LOW_STAR_FACTS = ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json"
EVIDENCE_CONTEXT = ROOT / "output/r8_1_low_star_full_tactical_closure_v2/llm_evidence_context.json"

MECHANIC_TOPICS = {
    "coordinates_and_direction",
    "range_template",
    "skill_sp_recovery_during_effect",
    "current_damage_formula",
    "current_simulator_win_rule",
    "r8_1_stage_facts",
    "affordance_catalog",
}

TOOL_NAMES = {"query_mechanic", "query_range_coverage", "check_timing_constraints"}

TOOLS_SCHEMA = [
    {
        "type": "function",
        "name": "query_mechanic",
        "description": "Read one whitelisted mechanic or runtime rule. Returns UNKNOWN instead of guessing.",
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "query_range_coverage",
        "description": "Compute the configured range at one declared position and direction. Does not optimize positions or change directions.",
        "parameters": {
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "configuration": {"type": "object", "additionalProperties": True},
                "tile": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "direction": {"type": "string"},
                "targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "tile": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                        },
                        "required": ["label", "tile"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["operator_id", "configuration", "tile", "direction", "targets"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "check_timing_constraints",
        "description": "Check declared SP, DP and deployment assumptions. It does not simulate battle or propose tactics.",
        "parameters": {
            "type": "object",
            "properties": {
                "skill_activations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "operator_id": {"type": "string"},
                            "frame": {"type": "integer", "minimum": 0},
                            "assume_ready": {"type": "boolean"},
                        },
                        "required": ["operator_id", "frame", "assume_ready"],
                        "additionalProperties": False,
                    },
                },
                "dp_ledger": {
                    "type": "object",
                    "properties": {
                        "initial_dp": {"type": "number", "minimum": 0},
                        "entries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "entry_id": {"type": "string"},
                                    "frame": {"type": "integer", "minimum": 0},
                                    "delta": {"type": "number"},
                                    "label": {"type": "string"},
                                    "evidence_status": {"type": "string"},
                                },
                                "required": ["frame", "delta", "label", "evidence_status"],
                                "additionalProperties": False,
                            },
                        },
                        "same_frame_order": {"type": "string", "enum": ["UNKNOWN", "DECLARED_LEDGER_ORDER"]},
                    },
                    "required": ["initial_dp", "entries"],
                    "additionalProperties": False,
                },
                "deployment_conditions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "operator_id": {"type": "string"},
                            "frame": {"type": "integer", "minimum": 0},
                            "tile": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                            "declared_cost": {"type": "number", "minimum": 0},
                            "payment_entry_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                        },
                        "required": ["operator_id", "frame", "tile", "declared_cost"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["skill_activations", "dp_ledger", "deployment_conditions"],
            "additionalProperties": False,
        },
    },
]

BASE_RULE_CARD = {
    "schema_version": "R8_1_READONLY_BASE_RULE_CARD_V1",
    "rules": {
        "coordinates": "OperationalPlan/action JSON tile is [row,col]. Runtime tile is (x=col,y=row), converted as (col,row).",
        "range_orientation": "GameData range offsets are stored for RIGHT. ApproximateRealRangeTransformer rotates them in bottom-left field coordinates.",
        "time_sp_recovery": "Current public low-rarity runtime advances time-SP by 1.0 SP/s only while inactive. SP is paused while a skill is active.",
        "damage": "Current formula layer: physical max(0.05A,A-D); arts max(0.05A,0.01A*(100-RES)); attack interval T0/(clamp(S,10,600)/100).",
        "simulator_win": "Current Simulator wins when no enemy leaks, the spawn schedule is exhausted, and no active enemies remain.",
        "economy": "Natural DP and provided ledger deltas are model calculations. Refunds, skill DP and merchant upkeep are only valid with their stated evidence and conditions.",
        "unknown": "Exact client timing, active roadblock ordinary-WALK navigation, target priority and unsupported effects remain UNKNOWN unless supplied evidence says otherwise.",
    },
    "sources": [
        "scripts/kimi_readonly_tools.py",
        "scripts/kimi_responses_transport.py",
        "src/arknights_planner/simulator/range.py",
        "src/arknights_planner/simulator/combat_rules.py",
        "src/arknights_planner/simulator/simulator.py",
    ],
}


def json_tile_to_runtime(value: Any, label: str = "tile") -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, int) for item in value):
        raise ValueError(f"{label} must be integer [row,col]")
    row, col = value
    return col, row


def runtime_tile_to_json(value: tuple[int, int]) -> list[int]:
    return [value[1], value[0]]


class ReadOnlyQueryEngine:
    def __init__(self, facts_path: Path = NORMAL_LOW_STAR_FACTS, evidence_path: Path = EVIDENCE_CONTEXT):
        facts = json.loads(facts_path.read_text(encoding="utf-8"))
        rows = facts.get("operators") if isinstance(facts, dict) else facts
        self.operators = {row["operator_id"]: row for row in rows}
        self.evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.range_transformer = ApproximateRealRangeTransformer()

    def _base(self, evidence_status: str) -> dict[str, Any]:
        return {
            "data_version": DATA_VERSION,
            "mechanics_version": MECHANICS_VERSION,
            "evidence_status": evidence_status,
            "applicability": "R8-1 ordinary-mode 1-3 star debug configuration under the current public runtime.",
            "unknowns": [],
        }

    def _operator(self, operator_id: str) -> dict[str, Any]:
        row = self.operators.get(operator_id)
        if row is None:
            raise ValueError(f"unknown operator {operator_id}")
        qualification = row.get("qualification") or {}
        if qualification.get("normal_mode") is not True or not 1 <= row["identity"]["rarity"] <= 3:
            raise ValueError(f"operator is outside ordinary 1-3 star domain: {operator_id}")
        return row

    def _declared_configuration_matches(self, row: dict[str, Any], declared: Any) -> bool:
        expected = row.get("debug_configuration")
        if not isinstance(expected, dict) or not isinstance(declared, dict):
            return False
        if row.get("qualification", {}).get("eligible_for_debug") is not True:
            return False
        if expected.get("legal_for_debug") is not True:
            return False
        required_keys = ["rarity", "phase_index", "level", "potential_level", "trust"]
        if expected.get("skill_level_index") is not None:
            required_keys.append("skill_level_index")
        if any(key not in declared for key in required_keys):
            return False
        if any(declared.get(key) != expected.get(key) for key in required_keys):
            return False
        derived_skill_rank = (
            None
            if expected.get("skill_level_index") is None
            else int(expected["skill_level_index"]) + 1
        )
        for key, value in (
            ("skill_level_index", expected.get("skill_level_index")),
            ("skill_rank", derived_skill_rank),
            ("required_potential_rank", expected.get("required_potential_rank")),
        ):
            if key in declared and declared.get(key) != value:
                return False
        return True

    def _skill(self, row: dict[str, Any]) -> dict[str, Any] | None:
        return (row.get("skills") or [None])[0]

    def query_mechanic(self, arguments: dict[str, Any]) -> dict[str, Any]:
        topic = arguments.get("topic")
        if not isinstance(topic, str) or topic not in MECHANIC_TOPICS:
            return {**self._base("UNKNOWN"), "topic": topic, "status": "UNKNOWN", "result": None, "unknowns": ["topic is not in the whitelist"]}
        if topic == "coordinates_and_direction":
            result = {"json_tile": "[row,col]", "runtime_tile": "(x=col,y=row)", "conversion": "(col,row)", "legal_directions": ["UP", "DOWN", "LEFT", "RIGHT"]}
            sources = ["scripts/kimi_readonly_tools.py", "scripts/run_r8_1_low_star_full_tactical_closure_v1.py"]
            unknowns = []
        elif topic == "range_template":
            result = {"storage": "RIGHT-relative [row,col] offsets", "rotation_source": "src/arknights_planner/simulator/range.py", "transformer": "ApproximateRealRangeTransformer"}
            sources = ["data/ArknightsGameData/zh_CN/gamedata/excel/range_table.json", "src/arknights_planner/simulator/range.py"]
            unknowns = ["exact client orientation/geometric rounding is not independently verified here"]
        elif topic == "skill_sp_recovery_during_effect":
            result = {"supported_mode": "INCREASE_WITH_TIME", "recovery_while_active": False, "recovery_per_second": 1.0, "attack_sp_mode": "INCREASE_WHEN_ATTACK"}
            sources = ["src/arknights_planner/simulator/simulator.py", "src/arknights_planner/adapters/low_rarity_skill.py"]
            unknowns = ["exact client windup, integer rounding and SP timing are UNKNOWN"]
        elif topic == "current_damage_formula":
            result = {
                "physical": "max(0.05A, A-D)",
                "arts": "max(0.05A, 0.01A*(100-RES))",
                "attack_interval": "T0/(clamp(attackSpeed,10,600)/100)",
                "modifier_pipeline": "direct add, direct multiplier, final add, final multiplier",
            }
            sources = ["data/prts/game-data-basics.html", "data/prts/battle-mechanics.html", "src/arknights_planner/simulator/combat_rules.py"]
            unknowns = ["damage modifiers, talent effects and exact client rounding are outside this bounded formula"]
        elif topic == "r8_1_stage_facts":
            active = self.evidence.get("stage_active_facts") or {}
            result = {
                "stage_id": self.evidence.get("stage_id"),
                "stage_options": self.evidence.get("stage_options"),
                "map_size_col_row": active.get("map_size_col_row"),
                "roadblock_tiles_col_row": active.get("roadblock_tiles_col_row"),
                "route_count": len(active.get("runtime_adapter_routes") or []),
                "deployable_ground_count": len(active.get("deployable_ground_tiles_col_row") or []),
                "deployable_high_ground_count": len(active.get("deployable_high_ground_tiles_col_row") or []),
                "coordinate_conventions": active.get("coordinate_conventions"),
            }
            sources = ["output/r8_1_low_star_full_tactical_closure_v2/llm_evidence_context.json", "scripts/run_r8_1_low_star_full_tactical_closure_v1.py"]
            unknowns = ["route pressure, client navigation and exact wait/block timing remain model or UNKNOWN facts"]
        else:
            result = {"win_if": ["enemies_leaked == 0", "all spawn events consumed", "active_enemies is empty"], "loss_or_non_win": "otherwise"}
            sources = ["src/arknights_planner/simulator/simulator.py:711"]
            unknowns = ["stage-specific completion boundaries must be checked against a concrete run"]
            if topic == "affordance_catalog":
                result = {
                    "normal_low_star_operator_count": len(self.operators),
                    "three_star_count": sum(row.get("identity", {}).get("rarity") == 3 for row in self.operators.values()),
                    "support_counts": self.evidence.get("normal_low_star_support_counts"),
                    "supported_mechanics": self.evidence.get("simulation_domain", {}).get("supported_mechanics"),
                    "omitted_or_unknown_mechanics": self.evidence.get("simulation_domain", {}).get("omitted_or_unknown_mechanics"),
                }
                sources = ["output/normal_low_star_facts_v1/normal_low_star_facts.json", "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json", "output/r8_1_low_star_full_tactical_closure_v2/llm_evidence_context.json"]
                unknowns = ["per-operator support details require the source catalog; a summary does not upgrade unsupported mechanics"]
        return {**self._base("CONFIRMED_FROM_CODE_GAMEDATA_OR_CURRENT_RUNTIME"), "topic": topic, "status": "SUPPORTED", "result": result, "sources": sources, "unknowns": unknowns}

    def query_range_coverage(self, arguments: dict[str, Any]) -> dict[str, Any]:
        row = self._operator(arguments.get("operator_id"))
        if not self._declared_configuration_matches(row, arguments.get("configuration")):
            raise ValueError("declared configuration does not match the selected debug configuration")
        origin = json_tile_to_runtime(arguments.get("tile"), "tile")
        direction = arguments.get("direction")
        if direction not in {"UP", "DOWN", "LEFT", "RIGHT"}:
            raise ValueError("direction must be UP, DOWN, LEFT or RIGHT")
        range_fact = row.get("range") or {}
        range_id = range_fact.get("range_id")
        offsets = tuple((int(item[0]), int(item[1])) for item in range_fact.get("cells") or [])
        covered = self.range_transformer.covered_tiles(origin=origin, offsets=offsets, direction=direction)
        target_rows = []
        for target in arguments.get("targets") or []:
            runtime_target = json_tile_to_runtime(target.get("tile"), f"target {target.get('label')}")
            target_rows.append({
                "label": target.get("label"),
                "tile_json_row_col": runtime_tile_to_json(runtime_target),
                "tile_runtime_col_row": list(runtime_target),
                "covered": runtime_target in covered,
            })
        return {
            **self._base("CONFIRMED_FROM_GAMEDATA_AND_CURRENT_RUNTIME_TRANSFORMER"),
            "operator_id": row["operator_id"],
            "configuration": row.get("debug_configuration"),
            "range_id": range_id,
            "range_source": range_fact.get("source_path"),
            "origin_json_row_col": arguments.get("tile"),
            "origin_runtime_col_row": list(origin),
            "direction": direction,
            "covered_tiles_json_row_col": sorted(runtime_tile_to_json(tile) for tile in covered),
            "targets": target_rows,
            "sources": [
                range_fact.get("source_path"),
                "data/ArknightsGameData/zh_CN/gamedata/excel/range_table.json",
                "src/arknights_planner/simulator/range.py",
            ],
            "limitations": ["This is coverage geometry only; it does not prove target acquisition, blocking, damage or kill timing."],
        }

    def check_timing_constraints(self, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._base("CONDITIONAL_MODEL_CALCULATION")
        result.update({"status": "SUPPORTED_WITH_CONDITIONS", "skill_checks": [], "dp_checks": [], "deployment_checks": [], "conflicts": []})
        activations = sorted(arguments.get("skill_activations") or [], key=lambda item: (str(item.get("operator_id")), int(item.get("frame", 0))))
        grouped: dict[str, list[dict[str, Any]]] = {}
        for activation in activations:
            row = self._operator(activation.get("operator_id"))
            grouped.setdefault(row["operator_id"], []).append(activation)
        for operator_id, rows in grouped.items():
            fact = self._operator(operator_id)
            skill = self._skill(fact)
            if skill is None:
                result["conflicts"].append({"operator_id": operator_id, "conflict": "NO_SKILL_AT_DECLARED_CONFIGURATION"})
                continue
            if skill.get("sp_type") != "INCREASE_WITH_TIME":
                result["skill_checks"].append({"operator_id": operator_id, "status": "UNKNOWN", "reason": f"unsupported SP type {skill.get('sp_type')}"})
                continue
            cost = float(skill.get("sp_cost"))
            duration_frames = round(float(skill.get("duration") or 0.0) * 30.0)
            first = rows[0]
            first_frame = int(first.get("frame"))
            if first.get("assume_ready") is not True:
                result["conflicts"].append({"operator_id": operator_id, "frame": first_frame, "conflict": "FIRST_ACTIVATION_NOT_DECLARED_READY"})
                active_until = first_frame + duration_frames
            else:
                active_until = first_frame + duration_frames
                result["skill_checks"].append({"operator_id": operator_id, "frame": first_frame, "status": "ASSUMPTION_ACCEPTED", "active_until_frame": active_until})
            previous_until = active_until
            for activation in rows[1:]:
                frame = int(activation.get("frame"))
                earliest_ready = previous_until + round((cost - 0.0) * 30.0)
                check = {"operator_id": operator_id, "frame": frame, "earliest_ready_frame": earliest_ready, "sp_cost": cost, "recovery_rate_sp_per_second": 1.0}
                if frame < earliest_ready:
                    check["status"] = "CONFLICT"
                    result["conflicts"].append({**check, "conflict": "SP_NOT_READY_AT_DECLARED_FRAME"})
                else:
                    check["status"] = "PASS_WITH_CONDITIONS"
                    result["skill_checks"].append(check)
                previous_until = frame + duration_frames if frame >= earliest_ready else previous_until
        ledger = arguments.get("dp_ledger") or {}
        same_frame_order = ledger.get("same_frame_order", "UNKNOWN")
        ledger_entries = sorted(ledger.get("entries") or [], key=lambda item: int(item.get("frame", 0)))
        for index, entry in enumerate(ledger_entries):
            if isinstance(entry, dict) and entry.get("entry_id") is None:
                entry["entry_id"] = f"entry-{index}"
        balance = float(ledger.get("initial_dp") or 0.0)
        for entry in ledger_entries:
            balance += float(entry.get("delta"))
            check = {"frame": int(entry.get("frame")), "delta": float(entry.get("delta")), "label": entry.get("label"), "evidence_status": entry.get("evidence_status"), "balance": balance}
            result["dp_checks"].append(check)
            if balance < -1e-9:
                check["status"] = "CONFLICT"
                result["conflicts"].append({**check, "conflict": "DECLARED_DP_LEDGER_NEGATIVE"})
        for condition in arguments.get("deployment_conditions") or []:
            operator = self._operator(condition.get("operator_id"))
            tile = json_tile_to_runtime(condition.get("tile"), "deployment tile")
            active = self.evidence.get("stage_active_facts") or {}
            roadblocks = {tuple(item) for item in active.get("roadblock_tiles_col_row") or []}
            ground = {tuple(item) for item in active.get("deployable_ground_tiles_col_row") or []}
            high = {tuple(item) for item in active.get("deployable_high_ground_tiles_col_row") or []}
            position = operator.get("identity", {}).get("position")
            legal = (tile in ground if position == "MELEE" else tile in high if position == "RANGED" else False)
            frame = int(condition.get("frame"))
            declared_cost = float(condition.get("declared_cost"))
            source_cost = float(operator.get("stats", {}).get("cost"))
            entries_at_or_before = [entry for entry in ledger_entries if int(entry.get("frame", 0)) <= frame]
            entries_at_frame = [entry for entry in entries_at_or_before if int(entry.get("frame", 0)) == frame]
            payment_entry_ids = condition.get("payment_entry_ids") or []
            amount_matching_entries = [
                entry for entry in entries_at_frame
                if abs(float(entry.get("delta", 0.0)) + declared_cost) <= 1e-9
            ]
            matching_entries = [
                entry for entry in entries_at_frame
                if entry in amount_matching_entries and operator["operator_id"] in str(entry.get("label", ""))
            ]
            if payment_entry_ids:
                linked_entries = [entry for entry in entries_at_frame if entry.get("entry_id") in payment_entry_ids]
                payment_link = "LINKED_BY_ENTRY_ID" if len(linked_entries) == 1 and len(payment_entry_ids) == 1 else "UNKNOWN"
                if linked_entries and any(abs(float(entry.get("delta", 0.0)) + declared_cost) > 1e-9 for entry in linked_entries):
                    payment_link = "UNKNOWN"
            elif len(matching_entries) == 1:
                linked_entries = matching_entries
                payment_link = "MATCHING_OPERATOR_LABEL_AND_AMOUNT"
            elif amount_matching_entries:
                linked_entries = []
                payment_link = "UNKNOWN"
            else:
                linked_entries = []
                payment_link = "DEPLOYMENT_CHECK_APPLIES_COST"
            unlinked_same_frame_entries = [entry for entry in entries_at_frame if entry not in linked_entries]
            if payment_link not in {"LINKED_BY_ENTRY_ID", "MATCHING_OPERATOR_LABEL_AND_AMOUNT", "DEPLOYMENT_CHECK_APPLIES_COST"} or (
                linked_entries and same_frame_order != "DECLARED_LEDGER_ORDER"
            ):
                pre_payment_balance = "UNKNOWN"
                post_payment_balance = "UNKNOWN"
            elif linked_entries:
                linked_index = ledger_entries.index(linked_entries[0])
                pre_payment_balance = float(ledger.get("initial_dp") or 0.0) + sum(
                    float(entry.get("delta", 0.0)) for entry in ledger_entries[:linked_index]
                )
                post_payment_balance = pre_payment_balance - declared_cost
            elif unlinked_same_frame_entries:
                pre_payment_balance = "UNKNOWN"
                post_payment_balance = "UNKNOWN"
            else:
                pre_payment_balance = float(ledger.get("initial_dp") or 0.0) + sum(
                    float(entry.get("delta", 0.0)) for entry in entries_at_or_before if entry not in linked_entries
                )
                post_payment_balance = pre_payment_balance - declared_cost
            check = {
                "operator_id": operator["operator_id"], "frame": frame,
                "tile_json_row_col": runtime_tile_to_json(tile), "tile_runtime_col_row": list(tile),
                "position": position, "tile_legal_for_position": legal,
                "declared_cost": declared_cost, "fact_cost": source_cost,
                "same_frame_order": same_frame_order,
                "payment_link": payment_link,
                "dp_balance_before_cost": pre_payment_balance,
                "dp_balance_after_cost": post_payment_balance,
            }
            if tile in roadblocks:
                check["status"] = "CONFLICT"
                result["conflicts"].append({**check, "conflict": "ACTIVE_PREDEFINED_DEVICE_TILE"})
            elif not legal:
                check["status"] = "CONFLICT"
                result["conflicts"].append({**check, "conflict": "TILE_NOT_ACTIVE_DEPLOYABLE_FOR_POSITION"})
            elif declared_cost != source_cost:
                check["status"] = "UNKNOWN"
                result["unknowns"].append(f"declared cost differs from fact cost for {operator['operator_id']}; potential/talent effects require explicit evidence")
                result["deployment_checks"].append(check)
            else:
                if pre_payment_balance == "UNKNOWN":
                    check["status"] = "UNKNOWN"
                    result["unknowns"].append(
                        f"same-frame DP deduction order is UNKNOWN for {operator['operator_id']} at frame {frame}"
                    )
                    result["deployment_checks"].append(check)
                elif pre_payment_balance + 1e-9 < declared_cost:
                    result["conflicts"].append({**check, "conflict": "DECLARED_LEDGER_CANNOT_PAY_COST"})
                    check["status"] = "CONFLICT"
                    result["deployment_checks"].append(check)
                else:
                    check["status"] = "PASS_WITH_CONDITIONS"
                    result["deployment_checks"].append(check)
        result["proof_status"] = "NOT_A_BATTLE_FEASIBILITY_PROOF"
        result["limitations"] = ["Survival, auto-trigger, refund, skill income and enemy interactions are only as valid as the supplied assumptions."]
        return result

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in TOOL_NAMES:
            raise ValueError(f"unknown tool {name}")
        handlers = {
            "query_mechanic": self.query_mechanic,
            "query_range_coverage": self.query_range_coverage,
            "check_timing_constraints": self.check_timing_constraints,
        }
        return handlers[name](arguments)


def source_mapping(paths: list[str]) -> dict[str, Any]:
    rows = {}
    for relative in paths:
        path = ROOT / relative
        rows[relative] = {"exists": path.is_file(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None}
    return {"schema_version": "R8_1_READONLY_TOOL_SOURCE_MAPPING_V1", "sources": rows}
