"""Source-backed Chapter 6-11 stage mechanics fidelity.

This layer is deliberately independent of enemy fidelity.  A stage with fully
modelled enemies can still contain predeployed devices, branch scripts, or
targetable objects that change the battlefield.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MECHANIC_FAMILIES = (
    "STATIC_DEVICE",
    "DESTRUCTIBLE_DEVICE",
    "PATH_BLOCKER",
    "DYNAMIC_ROUTE_OBSTACLE",
    "ALLIED_UNIT",
    "NEUTRAL_UNIT",
    "PROTECTION_OBJECTIVE",
    "SPECIAL_LIFE_POINT_RULE",
    "PREDEPLOYED_ENTITY",
    "SCRIPTED_SPAWN",
    "SCRIPTED_ROUTE_CHANGE",
    "ENVIRONMENTAL_DAMAGE_TILE",
    "BUFF_DEBUFF_TILE",
    "MOVEMENT_TILE",
    "DEPLOYMENT_RESTRICTION",
    "SPECIAL_TARGET_PRIORITY",
    "STAGE_TIMER_EVENT",
    "GLOBAL_STAGE_EFFECT",
    "SPECIAL_GOAL_RULE",
    "STATUS_APPLICATION",
    "ON_DEATH",
    "SPAWN_ENTITY",
    "OTHER",
)

FIDELITY_RANK = {
    "EXACT": 6,
    "HIGH": 5,
    "GENERIC_SUPPORTED": 4,
    "SAFE_WITH_KNOWN_APPROXIMATION": 3,
    "SAFE_WITH_BOUNDED_INFERENCE": 3,
    "PARTIAL": 2,
    "UNSUPPORTED": 1,
    "UNKNOWN": 0,
    "NOT_APPLICABLE": 6,
    "INACTIVE_IN_THIS_STAGE": 6,
}

COMPLETE_RANK = {
    "HIGH_FIDELITY_PLANNING_SAFE": 4,
    "SAFE_WITH_KNOWN_APPROXIMATIONS": 3,
    "SAFE_WITH_BOUNDED_INFERENCE": 3,
    "PARTIAL_STAGE_RUNTIME": 2,
    "BLOCKED_STAGE_RUNTIME": 1,
}
RANK_COMPLETE = {value: key for key, value in COMPLETE_RANK.items()}


@dataclass(frozen=True)
class StageMechanic:
    """One observed stage mechanic with direct source provenance."""

    mechanic_id: str
    family: str
    status: str
    decision_criticality: str
    source_file: str
    source_path: str
    evidence: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StageMechanicsFidelity:
    stage_id: str
    display_stage_code: str | None
    mechanics: tuple[StageMechanic, ...]
    dimensions: dict[str, str]
    overall: str
    reason_codes: tuple[str, ...]
    source_file: str

    @property
    def families(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(mechanic.family for mechanic in self.mechanics))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "display_stage_code": self.display_stage_code,
            "mechanics": [item.to_dict() for item in self.mechanics],
            "mechanic_families": list(self.families),
            "dimensions": self.dimensions,
            "overall": self.overall,
            "reason_codes": list(self.reason_codes),
            "source_file": self.source_file,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageMechanicsFidelity":
        return cls(
            stage_id=payload["stage_id"],
            display_stage_code=payload.get("display_stage_code"),
            mechanics=tuple(StageMechanic(**item) for item in payload["mechanics"]),
            dimensions=dict(payload["dimensions"]),
            overall=payload["overall"],
            reason_codes=tuple(payload["reason_codes"]),
            source_file=payload["source_file"],
        )


@dataclass(frozen=True)
class CompleteStageFidelity:
    stage_id: str
    display_stage_code: str | None
    eligibility: str
    enemy_fidelity: str
    stage_mechanics_fidelity: str
    complete_fidelity: str
    capping_layer: str
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DEVICE_RULES = {
    "trap_020_roadblock": (
        ("STATIC_DEVICE", "PARTIAL"),
        ("DESTRUCTIBLE_DEVICE", "PARTIAL"),
        ("PATH_BLOCKER", "INACTIVE_IN_THIS_STAGE"),
        ("PREDEPLOYED_ENTITY", "PARTIAL"),
    ),
    "trap_011_ore": (
        ("STATIC_DEVICE", "PARTIAL"),
        ("STAGE_TIMER_EVENT", "PARTIAL"),
        ("GLOBAL_STAGE_EFFECT", "PARTIAL"),
        ("PREDEPLOYED_ENTITY", "PARTIAL"),
    ),
    "trap_010_frosts": (
        ("STATIC_DEVICE", "PARTIAL"),
        ("STAGE_TIMER_EVENT", "PARTIAL"),
        ("STATUS_APPLICATION", "PARTIAL"),
        ("PREDEPLOYED_ENTITY", "PARTIAL"),
    ),
    "trap_043_dupilr": (
        ("STATIC_DEVICE", "PARTIAL"),
        ("DESTRUCTIBLE_DEVICE", "PARTIAL"),
        ("DYNAMIC_ROUTE_OBSTACLE", "PARTIAL"),
        ("PATH_BLOCKER", "PARTIAL"),
        ("PREDEPLOYED_ENTITY", "PARTIAL"),
    ),
    "trap_086_larva": (
        ("STATIC_DEVICE", "PARTIAL"),
        ("DESTRUCTIBLE_DEVICE", "PARTIAL"),
        ("ON_DEATH", "PARTIAL"),
        ("SPAWN_ENTITY", "PARTIAL"),
        ("PREDEPLOYED_ENTITY", "PARTIAL"),
    ),
}


class StageMechanicsAnalyzer:
    """Read direct stage evidence without interpreting enemy composition."""

    VERSION = "stage-mechanics-fidelity-v1"
    _GENERIC_TILE_KEYS = frozenset({
        "tile_forbidden", "tile_wall", "tile_floor", "tile_ground", "tile_tensi",
        "tile_hilli", "tile_reed", "tile_end", "tile_start", "tile_hole",
        "tile_fence", "tile_fence_bound", "tile_tense", "tile_rexef",
        "tile_refined", "tile_flyland", "tile_road",
    })

    def analyze(self, repository, stage_id_or_code: str) -> StageMechanicsFidelity:
        stage_id, metadata, path, payload = repository.get_stage_level_document(stage_id_or_code)
        source_file = str(path)
        characters = repository._table("character_table.json")
        predefines = payload.get("predefines") or {}
        mechanics: list[StageMechanic] = []
        has_destructible = False
        has_targetable = False
        has_branch = False
        has_special_tile = False

        for character in predefines.get("characterInsts") or []:
            key = (character.get("inst") or {}).get("characterKey")
            mechanics.append(StageMechanic(
                f"predeployed-character:{character.get('alias', key)}", "PREDEPLOYED_ENTITY", "PARTIAL",
                "LIKELY_RELEVANT", source_file, "$.predefines.characterInsts",
                "Level JSON explicitly predeploys a character.",
                {"character_key": key, "position": character.get("position"), "alias": character.get("alias")},
            ))

        for index, token in enumerate(predefines.get("tokenInsts") or []):
            alias = token.get("alias")
            character_key = (token.get("inst") or {}).get("characterKey")
            position = token.get("position") or {}
            source_path = f"$.predefines.tokenInsts[{index}]"
            raw_character = characters.get(character_key, {})
            rules = _DEVICE_RULES.get(character_key, (("STATIC_DEVICE", "PARTIAL"), ("PREDEPLOYED_ENTITY", "PARTIAL")))
            if any(family in {"DESTRUCTIBLE_DEVICE"} for family, _ in rules):
                has_destructible = True
                has_targetable = True
            dependent_units_present = False
            if character_key == "trap_020_roadblock":
                dependent_units_present = any(
                    (action.get("key") or "").startswith("enemy_3001_upeopl")
                    or (action.get("key") or "").startswith("enemy_3002_ftrtal")
                    for wave in payload.get("waves") or []
                    for fragment in wave.get("fragments") or []
                    for action in fragment.get("actions") or []
                )
            for family, status in rules:
                if family == "PATH_BLOCKER":
                    criticality = "ACTIVE_AND_DECISION_CRITICAL" if dependent_units_present else "PRESENT_BUT_INACTIVE_IN_STAGE_CONTEXT"
                    status = "PARTIAL" if dependent_units_present else "NOT_APPLICABLE"
                else:
                    criticality = "ACTIVE_AND_LIKELY_RELEVANT"
                if family in {"STATIC_DEVICE", "DESTRUCTIBLE_DEVICE"} and status != "NOT_APPLICABLE":
                    status = "SAFE_WITH_KNOWN_APPROXIMATION"
                mechanics.append(StageMechanic(
                    f"predeployed-token:{alias}:{family}", family, status, criticality,
                    source_file, source_path,
                    f"Level JSON predeploys {character_key}; character_table.json supplies the trap attributes and description.",
                    {
                        "token_key": character_key,
                        "alias": alias,
                        "source_position": position,
                        "canonical_position": self._canonical_position(position, payload),
                        "name": raw_character.get("name"),
                        "description": raw_character.get("description"),
                        "phase_attributes": (raw_character.get("phases") or [{}])[0].get("attributesKeyFrames", [{}])[0].get("data"),
                        "dependent_units_present": dependent_units_present,
                        "context_activation": criticality,
                        "planner_relevance": (
                            "ACTIVE"
                            if criticality.startswith("ACTIVE_")
                            else "INACTIVE" if criticality == "PRESENT_BUT_INACTIVE_IN_STAGE_CONTEXT" else "UNKNOWN"
                        ),
                    },
                ))

        branch_count = len(payload.get("branches") or {})
        if branch_count:
            has_branch = True
            mechanics.append(StageMechanic(
                "stage-branch-script", "SCRIPTED_SPAWN", "PARTIAL", "LIKELY_RELEVANT",
                source_file, "$.branches",
                f"Level JSON defines {branch_count} branch phase objects with explicit SPAWN actions.",
                {"branch_count": branch_count, "context_activation": "ACTIVE_AND_LIKELY_RELEVANT"},
            ))

        map_data = payload.get("mapData") or {}
        special_tiles = sorted({
            tile.get("tileKey") for tile in map_data.get("tiles") or []
            if isinstance(tile, dict) and tile.get("tileKey") not in self._GENERIC_TILE_KEYS
        })
        if special_tiles:
            has_special_tile = True
            mechanics.append(StageMechanic(
                "special-map-tiles", "OTHER", "PARTIAL", "LIKELY_RELEVANT",
                source_file, "$.mapData.tiles[*].tileKey",
                "Level JSON contains non-generic tile keys; semantics are not inferred in this analyzer.",
                {"tile_keys": special_tiles, "context_activation": "UNKNOWN_ACTIVATION"},
            ))

        reason_codes = []
        if has_targetable:
            reason_codes.append("DEVICE_DESTRUCTIBILITY_INSTANTIATED_LOW_PRIORITY_TARGETING_IS_BOUNDED_INFERENCE")
        if has_branch:
            reason_codes.append("BRANCH_SCRIPT_NOT_EVALUATED")
        if has_special_tile:
            reason_codes.append("SPECIAL_TILE_SEMANTICS_NOT_MODELED")
        if not reason_codes:
            reason_codes.append("NO_STAGE_MECHANIC_BEYOND_SUPPORTED_ROUTES_AND_OPTIONS")

        dimensions = {
            "devices": (
                "SAFE_WITH_BOUNDED_INFERENCE"
                if has_targetable
                else "PARTIAL" if any(item.family in {"STATIC_DEVICE", "DESTRUCTIBLE_DEVICE"} for item in mechanics) else "NOT_APPLICABLE"
            ),
            "environment": "PARTIAL" if has_special_tile else "NOT_APPLICABLE",
            "routing": (
                "PARTIAL"
                if any(
                    item.family in {"DYNAMIC_ROUTE_OBSTACLE", "SCRIPTED_ROUTE_CHANGE"}
                    or (item.family == "PATH_BLOCKER" and item.decision_criticality in {"DECISION_CRITICAL", "LIKELY_RELEVANT"})
                    for item in mechanics
                )
                else "GENERIC_SUPPORTED"
            ),
            "allied_neutral_units": "NOT_APPLICABLE",
            "objective_rules": "PARTIAL" if any(item.family in {"PROTECTION_OBJECTIVE", "SPECIAL_LIFE_POINT_RULE", "SPECIAL_GOAL_RULE"} for item in mechanics) else "NOT_APPLICABLE",
            "scripted_events": "PARTIAL" if has_branch else "NOT_APPLICABLE",
            "deployment_constraints": "EXACT",
            "targetable_objects": "SAFE_WITH_BOUNDED_INFERENCE" if has_targetable else "NOT_APPLICABLE",
            "predeployed_entities": (
                "SAFE_WITH_BOUNDED_INFERENCE"
                if has_targetable
                else "PARTIAL" if any(item.family == "PREDEPLOYED_ENTITY" for item in mechanics) else "NOT_APPLICABLE"
            ),
            "global_effects": "NOT_APPLICABLE",
        }
        relevant = [value for value in dimensions.values() if value not in {"NOT_APPLICABLE", "INACTIVE_IN_THIS_STAGE"}]
        if any(value in {"PARTIAL", "UNSUPPORTED", "UNKNOWN"} for value in relevant):
            overall = "PARTIAL"
        elif any(value == "SAFE_WITH_KNOWN_APPROXIMATION" for value in relevant):
            overall = "SAFE_WITH_KNOWN_APPROXIMATION"
        elif any(value == "SAFE_WITH_BOUNDED_INFERENCE" for value in relevant):
            overall = "SAFE_WITH_BOUNDED_INFERENCE"
        else:
            overall = "EXACT"

        return StageMechanicsFidelity(
            stage_id=stage_id,
            display_stage_code=metadata.get("code"),
            mechanics=tuple(mechanics),
            dimensions=dimensions,
            overall=overall,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            source_file=source_file,
        )

    @staticmethod
    def _canonical_position(position: dict[str, Any] | None, payload: dict[str, Any]) -> tuple[int, int] | None:
        if not isinstance(position, dict) or "row" not in position or "col" not in position:
            return None
        rows = (payload.get("mapData") or {}).get("map") or []
        if not isinstance(rows, list) or not rows:
            return None
        return (int(position["col"]), len(rows) - 1 - int(position["row"]))


def combine_complete_stage_fidelity(
    *,
    eligibility_simulator_supported: bool,
    enemy_fidelity: str,
    stage_mechanics: StageMechanicsFidelity,
) -> CompleteStageFidelity:
    """Cap fidelity by the weakest evidence layer; no numeric averaging."""
    enemy_rank = COMPLETE_RANK.get({
        "BLOCKED": "BLOCKED_STAGE_RUNTIME",
        "PARTIAL": "PARTIAL_STAGE_RUNTIME",
        "BASIC_COMBAT_SAFE": "SAFE_WITH_KNOWN_APPROXIMATIONS",
        "FULL_RUNTIME_SAFE": "HIGH_FIDELITY_PLANNING_SAFE",
    }.get(enemy_fidelity, "BLOCKED_STAGE_RUNTIME"))
    if not eligibility_simulator_supported:
        mechanics_rank = COMPLETE_RANK["BLOCKED_STAGE_RUNTIME"]
        reason_codes = ("STAGE_INELIGIBLE_FOR_SIMULATION",)
    else:
        mechanics_rank = COMPLETE_RANK["BLOCKED_STAGE_RUNTIME"]
        reasons: list[str] = []
        if stage_mechanics.overall == "EXACT":
            mechanics_rank = COMPLETE_RANK["HIGH_FIDELITY_PLANNING_SAFE"]
        elif stage_mechanics.overall == "SAFE_WITH_KNOWN_APPROXIMATION":
            mechanics_rank = COMPLETE_RANK["SAFE_WITH_KNOWN_APPROXIMATIONS"]
            reasons.append("STAGE_MECHANICS_SAFE_WITH_KNOWN_APPROXIMATION")
        elif stage_mechanics.overall == "SAFE_WITH_BOUNDED_INFERENCE":
            mechanics_rank = COMPLETE_RANK["SAFE_WITH_BOUNDED_INFERENCE"]
            reasons.append("STAGE_MECHANICS_SAFE_WITH_BOUNDED_INFERENCE")
        else:
            mechanics_rank = COMPLETE_RANK["PARTIAL_STAGE_RUNTIME"]
            reasons.extend(stage_mechanics.reason_codes)
        reason_codes = tuple(reasons)
    final_rank = min(enemy_rank, mechanics_rank)
    layer = "STAGE_MECHANICS_FIDELITY" if mechanics_rank < enemy_rank else (
        "ENEMY_FIDELITY" if enemy_rank < mechanics_rank else "BOTH_LAYERS"
    )
    return CompleteStageFidelity(
        stage_id=stage_mechanics.stage_id,
        display_stage_code=stage_mechanics.display_stage_code,
        eligibility="SIMULATOR_SUPPORTED" if eligibility_simulator_supported else "NOT_SIMULATOR_SUPPORTED",
        enemy_fidelity=enemy_fidelity,
        stage_mechanics_fidelity=stage_mechanics.overall,
        complete_fidelity=RANK_COMPLETE[final_rank],
        capping_layer=layer,
        reason_codes=reason_codes,
    )
