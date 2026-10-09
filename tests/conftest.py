from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def gamedata_root(tmp_path: Path) -> Path:
    excel = tmp_path / "zh_CN/gamedata/excel"
    levels = tmp_path / "zh_CN/gamedata/levels/obt"
    enemydata = tmp_path / "zh_CN/gamedata/levels/enemydata"
    excel.mkdir(parents=True)
    levels.mkdir(parents=True)
    enemydata.mkdir(parents=True)
    (excel / "character_table.json").write_text(json.dumps({
        "char_test": {
            "name": "Test Guard", "profession": "WARRIOR", "subProfessionId": "centurion", "rarity": 5, "position": "MELEE",
            "phases": [{"rangeId": "rng_test", "maxLevel": 50, "attributesKeyFrames": [
                {"level": 1, "data": {"maxHp": 1000, "atk": 300, "def": 100, "magicResistance": 0, "cost": 15, "blockCnt": 2, "baseAttackTime": 1.0, "respawnTime": 70}},
                {"level": 50, "data": {"maxHp": 1500, "atk": 500, "def": 200, "magicResistance": 0, "cost": 15, "blockCnt": 2, "baseAttackTime": 1.0, "respawnTime": 70}},
            ]}], "skills": [{"skillId": "sk_test", "unlockCond": {"phase": "PHASE_0", "level": 1}}],
        },
    }), encoding="utf-8")
    (excel / "skill_table.json").write_text(json.dumps({"sk_test": {"skillId": "sk_test", "hidden": False, "levels": [{
        "name": "Test Skill", "rangeId": None, "skillType": "MANUAL", "durationType": "NONE", "duration": 20.0,
        "spData": {"spType": "INCREASE_WITH_TIME", "maxChargeTime": 1, "spCost": 30, "initSp": 5},
        "blackboard": [{"key": "atk", "value": 0.5, "valueStr": None}],
    }]}}), encoding="utf-8")
    (excel / "range_table.json").write_text(json.dumps({"rng_test": {"direction": 1, "grids": []}}), encoding="utf-8")
    (excel / "enemy_handbook_table.json").write_text(json.dumps({"enemyData": {
        "enemy_test": {"enemyId": "enemy_test", "name": "Test Slug", "description": "Fixture only"},
    }}), encoding="utf-8")
    (enemydata / "enemy_database.json").write_text(json.dumps({"enemies": [{"Key": "enemy_test", "Value": [{"level": 0, "enemyData": {
        "name": {"m_defined": True, "m_value": "Test Slug"},
        "attributes": {
            "maxHp": {"m_defined": True, "m_value": 1000}, "atk": {"m_defined": True, "m_value": 100},
            "def": {"m_defined": True, "m_value": 20}, "magicResistance": {"m_defined": True, "m_value": 0},
            "moveSpeed": {"m_defined": True, "m_value": 1.0}, "baseAttackTime": {"m_defined": True, "m_value": 1.5},
            "massLevel": {"m_defined": True, "m_value": 1},
        }, "lifePointReduce": {"m_defined": True, "m_value": 1},
    }}]}]}), encoding="utf-8")
    (excel / "stage_table.json").write_text(json.dumps({"stages": {"main_01-07": {
        "stageId": "main_01-07", "levelId": "Obt/Main/level_main_01-07", "code": "1-7", "name": "Test Stage",
    }}}), encoding="utf-8")
    for filename in ("battle_equip_table.json", "gamedata_const.json"):
        (excel / filename).write_text("{}", encoding="utf-8")
    main_levels = tmp_path / "zh_CN/gamedata/levels/obt/main"
    main_levels.mkdir()
    (main_levels / "level_main_01-07.json").write_text(json.dumps({
        "levelId": "Obt/Main/level_main_01-07", "mapData": {"map": [[0, 1, 2], [3, 4, 5]], "tiles": []},
        "routes": [{"startPosition": {"row": 0, "col": 0}}], "waves": [{"fragments": [{"actions": [{"actionType": "SPAWN", "key": "enemy_test", "count": 1}]}]}],
        "enemyDbRefs": [{"useDb": True, "id": "enemy_test", "level": 0, "overwrittenData": None}],
        "options": {"initialCost": 10, "characterLimit": 8},
    }), encoding="utf-8")
    return tmp_path
