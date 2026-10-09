"""Auditable inventory of the simulator's basic-combat knowledge boundary.

This is deliberately an inventory, not a second rules engine.  A project
implementation being absent must never be reported as an unknown game rule.
PRTS verification is tracked independently so public-source evidence can be
attached without rewriting the simulator's implementation-status reporting.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


PRTS_GAME_DATA = "https://prts.wiki/w/%E6%B8%B8%E6%88%8F%E6%95%B0%E6%8D%AE%E5%9F%BA%E7%A1%80"
PRTS_BATTLE = "https://prts.wiki/w/%E4%BD%9C%E6%88%98%E6%9C%BA%E5%88%B6"


@dataclass(frozen=True)
class MechanicAuditRecord:
    mechanic: str
    prts_sources: tuple[str, ...]
    prts_evidence_status: str
    project_status: str
    implementation_locations: tuple[str, ...]
    prts_consistency: str
    gaps: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def basic_mechanic_audit() -> tuple[MechanicAuditRecord, ...]:
    """Return the source-separated audit required before rules expansion.

    ``PRTS_PENDING_ACCESS`` means only that this execution environment could
    not retrieve the public page.  It never means that the game rule is
    unknown.  Existing project behavior is intentionally labelled separately.
    """
    pending = "VERIFIED_LOCAL_PRTS_SNAPSHOT"
    unverified = "CONSISTENT_FOR_IMPLEMENTED_SUBSET"
    sim = "src/arknights_planner/simulator/simulator.py"
    runtime = "src/arknights_planner/models/runtime.py"
    skill = "src/arknights_planner/adapters/low_rarity_skill.py"
    return (
        MechanicAuditRecord("属性计算", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "PARTIAL", (sim, runtime, "src/arknights_planner/simulator/combat_rules.py"), unverified,
                            ("four-stage helper exists for scalar attributes, but runtime does not yet attach typed modifier collections")),
        MechanicAuditRecord("Buff/Debuff叠加", (PRTS_BATTLE,), pending, "PARTIAL", (sim, runtime, "src/arknights_planner/simulator/combat_rules.py"), unverified,
                            ("typed modifier phases and source-order/event-order collection remain absent")),
        MechanicAuditRecord("物理伤害", (PRTS_BATTLE,), pending, "IMPLEMENTED_SOURCE_FORMULA", (sim, "src/arknights_planner/simulator/combat_rules.py"), "CONSISTENT_WITH_LOCAL_PRTS_FORMULA",
                            ("ON_* modifier and 伤判 layers remain outside the formula helper")),
        MechanicAuditRecord("法术伤害", (PRTS_BATTLE,), pending, "IMPLEMENTED_SOURCE_FORMULA", (sim, "src/arknights_planner/simulator/combat_rules.py"), "CONSISTENT_WITH_LOCAL_PRTS_FORMULA",
                            ("ON_* modifier and 伤判 layers remain outside the formula helper")),
        MechanicAuditRecord("真实伤害", (PRTS_BATTLE,), pending, "IMPLEMENTED_FORMULA_HELPER_NOT_RUNTIME", ("src/arknights_planner/simulator/combat_rules.py",), "FORMULA_ONLY",
                            ("operator/enemy runtime has no TRUE damage output mapping")),
        MechanicAuditRecord("防御/法抗", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "PARTIAL", (sim,), unverified,
                            ("base DEF/RES are used; full attribute modifier collection is absent")),
        MechanicAuditRecord("固定与百分比穿透", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "FORMULA_SUPPORTED_RUNTIME_FIELDS_UNUSED_BY_ADAPTER", (sim, "src/arknights_planner/models/simulation.py"), "FORMULA_ONLY",
                            ("GameData model/adapters do not yet populate penetration fields")),
        MechanicAuditRecord("最低伤害规则", (PRTS_GAME_DATA,), pending, "IMPLEMENTED_SOURCE_FORMULA", ("src/arknights_planner/simulator/combat_rules.py",), "CONSISTENT_WITH_LOCAL_PRTS_FORMULA",
                            ("full fixed-point rounding behavior is not modeled")),
        MechanicAuditRecord("攻击速度", (PRTS_GAME_DATA,), pending, "IMPLEMENTED_SOURCE_FORMULA", (sim, "src/arknights_planner/simulator/combat_rules.py"), "CONSISTENT_WITH_LOCAL_PRTS_FORMULA",
                            ("GameData ATTACK_SPEED is not yet populated into all runtime loadouts")),
        MechanicAuditRecord("攻击间隔", (PRTS_GAME_DATA,), pending, "PARTIAL", (sim, runtime, "src/arknights_planner/simulator/combat_rules.py"), unverified,
                            ("baseAttackTime conversion is implemented; windup/recovery/animation timing absent")),
        MechanicAuditRecord("技力回复", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "PARTIAL", (sim, runtime), unverified,
                            ("time-SP only; attack/defense recovery explicitly unsupported", "no SP recover ratio/modifiers")),
        MechanicAuditRecord("技能持续与触发", (PRTS_BATTLE,), pending, "PARTIAL", (sim, skill), unverified,
                            ("bounded time-SP manual/automatic finite effects", "no generic trigger/skill effect interpreter")),
        MechanicAuditRecord("治疗/生命回复", (PRTS_BATTLE,), pending, "PARTIAL", (sim,), unverified,
                            ("single-target ATK-based direct heal capped at missing HP", "no regeneration, overheal/shield conversion, or full targeting rules")),
        MechanicAuditRecord("护盾/屏障/闪避/抵挡", (PRTS_BATTLE,), pending, "NOT_IMPLEMENTED", (), "NOT_APPLICABLE_UNTIL_IMPLEMENTED",
                            ("no shield, barrier, evasion, or damage-block state",)),
        MechanicAuditRecord("脆弱/庇护/增伤/减伤", (PRTS_BATTLE,), pending, "NOT_IMPLEMENTED", (), "NOT_APPLICABLE_UNTIL_IMPLEMENTED",
                            ("no output-damage or received-damage modifier layer",)),
        MechanicAuditRecord("伤判优先级", (PRTS_BATTLE,), pending, "NOT_IMPLEMENTED", (sim,), "CONFLICTS_WITH_LOCAL_PRTS",
                            ("runtime tick order is not the PRTS ON_CALCULATE_DAMAGE -> ON_AFTER_OUTPUT_DAMAGE modifier pipeline",)),
        MechanicAuditRecord("索敌与仇恨", (PRTS_BATTLE,), pending, "IMPLEMENTED_APPROXIMATION", (sim,), "CONFLICTS_WITH_LOCAL_PRTS",
                            ("operator path-distance ordering omits PRTS special/second priority and taunt ordering", "enemy nearest-target approximation conflicts with PRTS block -> special -> taunt -> earliest ordering")),
        MechanicAuditRecord("阻挡", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "PARTIAL", (sim,), unverified,
                            ("route-tile block count and unblock on death/retreat", "no block requirement, forced movement, or full collision priority")),
        MechanicAuditRecord("位移、重量和力度", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "NOT_IMPLEMENTED", (), "NOT_APPLICABLE_UNTIL_IMPLEMENTED",
                            ("weight is loaded for enemies but unused; no force/displacement",)),
        MechanicAuditRecord("状态抗性", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "NOT_IMPLEMENTED", (), "NOT_APPLICABLE_UNTIL_IMPLEMENTED",
                            ("no status duration/resistance runtime",)),
        MechanicAuditRecord("元素损伤", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "NOT_IMPLEMENTED", (), "NOT_APPLICABLE_UNTIL_IMPLEMENTED",
                            ("no elemental damage, threshold, or resistance runtime",)),
        MechanicAuditRecord("时间、帧和事件顺序", (PRTS_GAME_DATA, PRTS_BATTLE), pending, "PARTIAL", (sim, "src/arknights_planner/models/frame.py"), "CONFLICTS_WITH_LOCAL_PRTS",
                            ("integer external timeline converts to configured seconds", "synthetic tick order differs from PRTS modifier pipeline; client logic FPS, windup/recovery, and projectile timing remain unimplemented")),
    )


def basic_mechanic_audit_report() -> dict:
    rows = basic_mechanic_audit()
    return {
        "purpose": "separate PRTS evidence, project implementation, and unresolved project scope",
        "prts_access": "LOCAL_SNAPSHOT_AVAILABLE",
        "records": [row.to_dict() for row in rows],
    }
