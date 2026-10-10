from __future__ import annotations

import json
import hashlib
from pathlib import Path

from arknights_planner.adapters.normal_low_star import (
    debug_configuration,
    deployment_heal_all_value,
    deployment_sp_bonus,
    is_normal_mode_low_star,
    qualify_normal_mode_low_star,
)
from arknights_planner.gamedata.repository import GameDataRepository


ROOT = Path(__file__).resolve().parents[1]


def test_normal_low_star_boundary_cases_are_rejected() -> None:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    four_star = qualify_normal_mode_low_star(repository, "char_272_strong")
    reserve = qualify_normal_mode_low_star(repository, "char_607_cspec")
    assert four_star.eligible is False and "RARITY_OUTSIDE_1_TO_3" in four_star.reasons
    assert reserve.eligible is False and "NOT_NORMAL_MODE_OBTAINABLE" in reserve.reasons


def test_debug_configuration_is_exact_and_low_star_scoped() -> None:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    fang = debug_configuration(repository, "char_123_fang")
    nightblade = debug_configuration(repository, "char_502_nblade")
    assert fang["phase_index"] == 1 and fang["level"] == 55 and fang["skill_rank"] == 7
    assert nightblade["phase_index"] == 0 and nightblade["skill_rank"] is None
    assert debug_configuration(repository, "char_285_medic2")["level"] == 30
    assert is_normal_mode_low_star(repository, "char_503_rang") is True


def test_source_backed_deployment_talent_helpers_are_scoped_to_active_ranks() -> None:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    assert deployment_sp_bonus(repository, "char_121_lava") == 30.0
    assert deployment_heal_all_value(repository, "char_285_medic2") == 200.0
    assert deployment_sp_bonus(repository, "char_272_strong") == 0.0


def test_generated_catalog_covers_the_whole_normal_low_star_domain() -> None:
    facts = json.loads((ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json").read_text())
    support = json.loads((ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json").read_text())
    ids = {item["operator_id"] for item in facts["operators"]}
    assert facts["counts"] == {"normal_low_star": 34, "rarity_1": 12, "rarity_2": 5, "rarity_3": 17}
    assert all(item["qualification"]["normal_mode"] for item in facts["operators"])
    assert "char_272_strong" not in ids and "char_607_cspec" not in ids
    assert {item["operator_id"] for item in facts["operators"] if item["identity"]["rarity"] == 3} == {
        "char_120_hibisc", "char_121_lava", "char_122_beagle", "char_123_fang", "char_124_kroos",
        "char_192_falco", "char_208_melan", "char_209_ardign", "char_210_stward", "char_211_adnach",
        "char_212_ansel", "char_240_wyvern", "char_278_orchid", "char_281_popka", "char_282_catap",
        "char_283_midn", "char_284_spot",
    }
    lava = next(item for item in support["operators"] if item["operator_id"] == "char_121_lava")
    lancet = next(item for item in support["operators"] if item["operator_id"] == "char_285_medic2")
    fang = next(item for item in support["operators"] if item["operator_id"] == "char_123_fang")
    assert lava["deployment_sp_bonus"] == 30.0 and lava["overall"] == "NOT_PLANNER_SAFE"
    assert lancet["deployment_heal_all_value"] == 200.0
    assert fang["overall"] == "PLANNER_SAFE_WITH_KNOWN_LIMITS"


def test_generated_manifest_hashes_are_real() -> None:
    manifest = json.loads((ROOT / "output/normal_low_star_facts_v1/manifest.json").read_text())
    for output in manifest["outputs"]:
        path = ROOT / output["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert output["bytes"] == path.stat().st_size and output["sha256"] == digest
