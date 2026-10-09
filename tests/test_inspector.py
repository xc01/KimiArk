from arknights_planner.gamedata import GameDataInspector


def test_repository_inventory_and_table_shape(gamedata_root):
    inspector = GameDataInspector(gamedata_root)
    report = inspector.repository_report()
    assert report["exists"] is True
    assert report["directories"]["zh_CN/gamedata/excel"] is True
    assert report["expected_tables"]["character_table.json"] is True
    inspection = inspector.inspect_table("character_table.json")
    assert inspection.exists is True
    assert inspection.json_kind == "object"
    assert inspection.item_count == 1
    assert inspection.top_level_keys == ("char_test",)


def test_missing_repository_is_reported_not_guessed(tmp_path):
    report = GameDataInspector(tmp_path / "missing").repository_report()
    assert report["exists"] is False
    assert report["json_file_count"] == 0
