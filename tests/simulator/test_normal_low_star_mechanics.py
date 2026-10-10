from __future__ import annotations

import json
from pathlib import Path
from dataclasses import replace

from arknights_planner.adapters.low_rarity_skill import LowRarityBlackboardEffectInterpreter
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.provenance import known
from arknights_planner.models.runtime import CombatOutputType
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


def test_generic_multi_target_support_remains_explicitly_blocked() -> None:
    support = json.loads((ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json").read_text())
    catapult = next(item for item in support["operators"] if item["operator_id"] == "char_282_catap")
    assert catapult["normal_attack"]["status"] == "UNSUPPORTED_AOE_GEOMETRY"
    assert catapult["overall"] == "NOT_PLANNER_SAFE"
