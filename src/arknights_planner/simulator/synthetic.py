"""Small deterministic fixtures for simulator-only tests and demos."""
from __future__ import annotations

from arknights_planner.models.enemy import Enemy, EnemyStats
from arknights_planner.models.operator import Operator, OperatorPhase, OperatorStats
from arknights_planner.models.provenance import known
from arknights_planner.models.route import Route, Waypoint
from arknights_planner.models.runtime import CombatOutputType, SPRecoveryMode, SkillEffect, SyntheticSkill
from arknights_planner.models.stage import SpawnEvent, Stage, StageMap, Tile

_SOURCE = "synthetic/milestone_2"


def _operator(
    operator_id: str, *, cost: int, atk: int, block: int, interval: float,
    attack_range: tuple[tuple[int, int], ...], hp: int = 1000, defense: int = 0,
    position: str = "MELEE", combat_output: CombatOutputType = CombatOutputType.DAMAGE,
    skill: SyntheticSkill | None = None, redeploy_time: float = 3.0,
) -> Operator:
    stats = OperatorStats(
        max_hp=known(hp, _SOURCE, f"$.operators.{operator_id}.hp"),
        atk=known(atk, _SOURCE, f"$.operators.{operator_id}.atk"),
        defense=known(defense, _SOURCE, f"$.operators.{operator_id}.def"),
        magic_resistance=known(0, _SOURCE, f"$.operators.{operator_id}.res"),
        cost=known(cost, _SOURCE, f"$.operators.{operator_id}.cost"),
        block_count=known(block, _SOURCE, f"$.operators.{operator_id}.block"),
        attack_interval=known(interval, _SOURCE, f"$.operators.{operator_id}.interval"),
    )
    phase = OperatorPhase(0, known(1, _SOURCE, "$.phase.maxLevel"), stats, stats, known("synthetic", _SOURCE, "$.phase.rangeId"))
    return Operator(
        operator_id, known(operator_id, _SOURCE, "$.name"), known("WARRIOR", _SOURCE, "$.profession"), known("synthetic", _SOURCE, "$.branch"),
        known(1, _SOURCE, "$.rarity"), known(position, _SOURCE, "$.position"), (phase,), _SOURCE,
        attack_range=attack_range, synthetic_skill=skill, combat_output=combat_output,
        redeploy_time=known(redeploy_time, _SOURCE, f"$.operators.{operator_id}.redeploy"),
    )


def synthetic_operators() -> dict[str, Operator]:
    return {
        "guard": _operator("guard", cost=5, atk=30, block=1, interval=1.0, attack_range=((0, 0), (1, 0))),
        "archer": _operator("archer", cost=4, atk=80, block=0, interval=1.0, attack_range=((1, 0), (2, 0), (3, 0)), position="RANGED"),
        "rookie": _operator("rookie", cost=3, atk=10, block=1, interval=1.0, attack_range=((0, 0),)),
    }


def synthetic_enemies() -> dict[str, Enemy]:
    stats = EnemyStats(
        max_hp=known(100, _SOURCE, "$.enemies.slug.hp"), atk=known(10, _SOURCE, "$.enemies.slug.atk"), defense=known(0, _SOURCE, "$.enemies.slug.def"),
        magic_resistance=known(0, _SOURCE, "$.enemies.slug.res"), move_speed=known(1.0, _SOURCE, "$.enemies.slug.speed"),
        attack_interval=known(1.0, _SOURCE, "$.enemies.slug.interval"), weight=known(0, _SOURCE, "$.enemies.slug.mass"),
        life_point_reduce=known(1, _SOURCE, "$.enemies.slug.life"), block_requirement=known(1, _SOURCE, "$.enemies.slug.blockRequirement"),
    )
    return {"slug": Enemy("slug", known("Synthetic Slug", _SOURCE, "$.enemies.slug.name"), stats, _SOURCE)}


def synthetic_stage() -> Stage:
    tiles = tuple(
        Tile(
            x, y, buildable=(x, y) not in {(0, 1), (6, 1)},
            tile_kind="NON_DEPLOYABLE" if (x, y) in {(0, 1), (6, 1)} else "HIGH_GROUND" if y == 2 else "GROUND",
        )
        for y in range(3) for x in range(7)
    )
    route = Route("main", (Waypoint(0, 1), Waypoint(6, 1)))
    return Stage(
        "synthetic-1", known("SYN-1", _SOURCE, "$.code"), known("Synthetic Lane", _SOURCE, "$.name"),
        known(7, _SOURCE, "$.map.width"), known(3, _SOURCE, "$.map.height"), known(1, _SOURCE, "$.routes"), known(1, _SOURCE, "$.waves"), _SOURCE,
        initial_dp=known(10, _SOURCE, "$.options.initialCost"), deployment_limit=known(2, _SOURCE, "$.options.characterLimit"),
        stage_map=StageMap(7, 3, tiles), routes=(route,),
        spawn_events=(SpawnEvent(1.0, "slug", "main"), SpawnEvent(2.0, "slug", "main"), SpawnEvent(3.0, "slug", "main"), SpawnEvent(4.0, "slug", "main")),
        initial_life=3, dp_per_second=1.0,
    )


def runtime_operators() -> dict[str, Operator]:
    """A separate fixture requiring a blocker, DPS, healer, and manual skill."""
    burst = SyntheticSkill(
        "burst", initial_sp=0.0, sp_cost=3.0, recovery_mode=SPRecoveryMode.TIME, sp_per_second=1.0,
        duration=2.5,
        # This is deliberately a synthetic, explicit range: it covers the lane
        # below the high-ground tile while active. It is not inferred GameData.
        effect=SkillEffect(
            atk_multiplier=2.0,
            attack_interval_multiplier=0.5,
            range_override=tuple((1, offset_y) for offset_y in range(-1, 6)),
        ),
    )
    return {
        "blocker": _operator("blocker", cost=4, atk=15, block=1, interval=1.0, attack_range=((0, 0),), hp=160, defense=5),
        "dps": _operator("dps", cost=4, atk=35, block=0, interval=1.0, attack_range=((1, -1), (1, 0), (1, 1)), position="RANGED", skill=burst),
        "healer": _operator("healer", cost=3, atk=25, block=0, interval=1.0, attack_range=((1, 0),), position="RANGED", combat_output=CombatOutputType.HEAL),
    }


def runtime_enemies() -> dict[str, Enemy]:
    stats = EnemyStats(
        max_hp=known(515, _SOURCE, "$.enemies.brute.hp"), atk=known(70, _SOURCE, "$.enemies.brute.atk"), defense=known(0, _SOURCE, "$.enemies.brute.def"),
        magic_resistance=known(0, _SOURCE, "$.enemies.brute.res"), move_speed=known(1.0, _SOURCE, "$.enemies.brute.speed"),
        attack_interval=known(1.0, _SOURCE, "$.enemies.brute.interval"), weight=known(0, _SOURCE, "$.enemies.brute.mass"),
        life_point_reduce=known(1, _SOURCE, "$.enemies.brute.life"), block_requirement=known(1, _SOURCE, "$.enemies.brute.blockRequirement"),
    )
    return {"brute": Enemy("brute", known("Synthetic Brute", _SOURCE, "$.enemies.brute.name"), stats, _SOURCE)}


def runtime_stage() -> Stage:
    tiles = tuple(
        Tile(
            x, y, buildable=(x, y) not in {(0, 1), (6, 1)},
            tile_kind="NON_DEPLOYABLE" if (x, y) in {(0, 1), (6, 1)} else "HIGH_GROUND" if (x, y) in {(1, 2), (3, 2)} else "GROUND",
        )
        for y in range(3) for x in range(7)
    )
    return Stage(
        "synthetic-runtime-1", known("SYN-R1", _SOURCE, "$.code"), known("Synthetic Runtime Lane", _SOURCE, "$.name"),
        known(7, _SOURCE, "$.map.width"), known(3, _SOURCE, "$.map.height"), known(1, _SOURCE, "$.routes"), known(1, _SOURCE, "$.waves"), _SOURCE,
        initial_dp=known(12, _SOURCE, "$.options.initialCost"), deployment_limit=known(3, _SOURCE, "$.options.characterLimit"),
        stage_map=StageMap(7, 3, tiles), routes=(Route("main", (Waypoint(0, 1), Waypoint(6, 1))),),
        spawn_events=(SpawnEvent(0.0, "brute", "main"),), initial_life=1, dp_per_second=1.0,
    )
