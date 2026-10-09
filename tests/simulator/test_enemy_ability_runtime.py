from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.enemy import EnemyAbility
from arknights_planner.models.provenance import known
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import runtime_enemies, runtime_operators, runtime_stage
from tests.simulator.test_combat_runtime import events as filter_events


ROOT = Path(__file__).resolve().parents[2]


def deploy(operator_id: str, tile: tuple[int, int], *, time: float = 0.0, direction: str = "UP") -> Action:
    return Action(ActionType.DEPLOY, time, operator_id, tile, direction)


def test_enemy_passive_hp_regeneration_is_game_data_backed_and_event_visible():
    enemies = runtime_enemies()
    enemies["brute"] = replace(
        enemies["brute"],
        stats=replace(
            enemies["brute"].stats,
            hp_recovery_per_second=known(80.0, "gamedata/test.json", "$.hpRecoveryPerSec"),
        ),
    )
    operators = runtime_operators()
    result = Simulator().run(
        stage=runtime_stage(), operators=operators, enemies=enemies,
        strategy=Strategy(("dps",), (deploy("dps", (1, 2), direction="UP"),)),
        config=SimulationConfig(dt=0.1, max_time=1.0),
    )
    heals = [
        event for event in filter_events(result, EventType.HEAL, source="brute#0")
        if event.target_id == "brute#0"
        and event.time < 1.0
    ]
    assert [round(dict(event.details)["amount"], 9) for event in heals] == [8.0, 8.0, 8.0, 8.0, 3.0]
    assert all(dict(event.details)["reason"] == "GAME_DATA_PASSIVE_HP_REGENERATION" for event in heals)


def test_game_data_passive_regen_values_load_for_all_ch6_11_regen_enemies():
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    expected = {
        "enemy_1043_zomsbr": 80.0,
        "enemy_1043_zomsbr_2": 150.0,
        "enemy_1044_zomstr": 200.0,
        "enemy_1061_zomshd": 200.0,
    }
    for enemy_id, rate in expected.items():
        enemy = repository.get_enemy(enemy_id)
        assert enemy.stats.hp_recovery_per_second.value == rate
        assert enemy.stats.hp_recovery_per_second.source_path.endswith("attributes.hpRecoveryPerSec.m_value")


def test_snow_mage_every_second_attack_applies_exact_cold_status():
    enemies = runtime_enemies()
    cold_attack = EnemyAbility(
        ability_id="coldattack", family="EVERY_NTH_ATTACK", cooldown=10.0,
        initial_cooldown=0.0, range_radius=0.0, atk_scale=1.0, damage_type="ARTS",
        attack_count_threshold=2, status_name="COLD", status_duration=10.0,
        attack_speed_delta=-30.0,
    )
    enemies["brute"] = replace(
        enemies["brute"],
        stats=replace(enemies["brute"].stats, apply_way=known("RANGED", "test", "$.applyWay"), attack_range=known(2.0, "test", "$.range")),
        abilities=(cold_attack,),
    )
    operators = runtime_operators()
    result = Simulator().run(
        stage=runtime_stage(), operators=operators, enemies=enemies,
        strategy=Strategy(("dps",), (deploy("dps", (1, 2)),)),
        config=SimulationConfig(dt=0.1, max_time=1.1),
    )
    assert [event.time for event in filter_events(result, EventType.ENEMY_ABILITY_START, source="brute#0")] == [1.0]
    hits = filter_events(result, EventType.ENEMY_ABILITY_HIT, source="brute#0")
    assert [event.time for event in hits] == [1.0]
    assert dict(hits[0].details)["ability"] == "coldattack"
    assert abs(dict(hits[0].details)["amount"] - 70.0) < 1e-9
    statuses = filter_events(result, EventType.ENEMY_STATUS_HIT, source="brute#0")
    assert [dict(event.details)["status"] for event in statuses] == ["COLD"]
    assert [dict(event.details)["attack_speed_delta"] for event in statuses] == [-30.0]
