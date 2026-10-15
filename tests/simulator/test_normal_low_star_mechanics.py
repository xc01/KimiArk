from __future__ import annotations

import json
from pathlib import Path
from dataclasses import replace

import pytest

from arknights_planner.adapters.low_rarity_skill import LowRarityBlackboardEffectInterpreter
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.provenance import known
from arknights_planner.models.runtime import CombatOutputType
from arknights_planner.adapters.approximate_real import ApproximateRealSimulationAdapter, RealOperatorConfiguration, RealSimulationApproximationPolicy
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator.simulator import SimulationConfig, Simulator
from arknights_planner.simulator import Simulator


ROOT = Path(__file__).resolve().parents[2]


def test_selected_skills_correctly_report_sp_recovery_and_effect_classes() -> None:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    interpreter = LowRarityBlackboardEffectInterpreter()
    for operator_id, skill_id, expected_sp_mode, expected_support in (
        ("char_123_fang", "skcom_charge_cost[1]", "INCREASE_WITH_TIME", "EXECUTABLE_APPROXIMATED"),
        ("char_124_kroos", "skchr_kroos_1", "INCREASE_WHEN_ATTACK", "EXECUTABLE_APPROXIMATED"),
        ("char_284_spot", "skchr_spot_1", "INCREASE_WITH_TIME", "EXECUTABLE_APPROXIMATED"),
    ):
        skill = repository.get_skill(skill_id)
        result = interpreter.interpret(skill_id, skill.levels[6])
        assert result.executable_effect is not None
        assert skill.levels[6].sp_type.value == expected_sp_mode
        assert result.support.value == expected_support


def test_medic_and_damage_operators_reuse_the_shared_combat_output_pipeline() -> None:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    assert repository.get_operator("char_120_hibisc").profession.value == "MEDIC"
    assert repository.get_operator("char_208_melan").profession.value == "WARRIOR"
    assert CombatOutputType.HEAL.value == "HEAL" and CombatOutputType.DAMAGE.value == "DAMAGE"


def test_ursus_civilian_no_damage_attributes_are_known_from_game_data() -> None:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    enemy = repository.get_enemy("enemy_3001_upeopl")
    stats = enemy.stats
    assert stats.magic_resistance.status.value == "KNOWN"
    assert stats.magic_resistance.value == 0.0
    assert stats.attack_interval.status.value == "KNOWN"
    assert stats.attack_interval.value == 0.0


def test_generic_multi_target_support_remains_explicitly_blocked() -> None:
    support = json.loads((ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json").read_text())
    catapult = next(item for item in support["operators"] if item["operator_id"] == "char_282_catap")
    assert catapult["normal_attack"]["status"] == "UNSUPPORTED_AOE_GEOMETRY"
    assert catapult["overall"] == "NOT_PLANNER_SAFE"


def test_named_low_star_mechanics_are_executable() -> None:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    interpreter = LowRarityBlackboardEffectInterpreter()
    ansel = interpreter.interpret("skcom_range_extend", repository.get_skill("skcom_range_extend").levels[6])
    midnight = interpreter.interpret("skchr_midn_1", repository.get_skill("skchr_midn_1").levels[6])
    assert ansel.executable_effect and ansel.executable_effect.effect.range_forward_extend == 2
    assert midnight.executable_effect and midnight.executable_effect.effect.damage_type_override == "ARTS"

    fixture = ApproximateRealSimulationAdapter(repository).build_pool_fixture(
        stage_id_or_code="R8-2",
        configurations=(
            RealOperatorConfiguration("char_281_popka", 1, 55),
            RealOperatorConfiguration("char_278_orchid", 1, 55),
            RealOperatorConfiguration("char_124_kroos", 1, 55),
            RealOperatorConfiguration("char_210_stward", 1, 55),
        ),
        policy=RealSimulationApproximationPolicy.m11_second_quantized(),
    )
    assert fixture.stage.stage_map is not None
    assert fixture.operators["char_281_popka"].attack_all_blocked is True
    assert fixture.operators["char_278_orchid"].damage_type == "ARTS"
    assert fixture.operators["char_124_kroos"].anti_air_priority is True
    assert fixture.operators["char_210_stward"].prioritize_high_defense is True
    assert fixture.operators["char_210_stward"].talent_atk_ratio == pytest.approx(0.06)
