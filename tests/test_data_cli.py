import json

from arknights_planner.cli.data_cli import main


def test_inspect_stage_cli_outputs_reconstruction_report(gamedata_root, capsys):
    main(["--data-root", str(gamedata_root), "inspect-stage", "1-7"])
    output = json.loads(capsys.readouterr().out)
    assert output["stage_id"] == "main_01-07"
    assert any(item["field"] == "Attack windup" and item["status"] == "UNKNOWN" for item in output["fields"])


def test_data_cli_module_entrypoint(gamedata_root, capsys):
    main(["--data-root", str(gamedata_root), "inspect-operator", "char_test"])
    output = json.loads(capsys.readouterr().out)
    assert output["skill_ids"] == ["sk_test"]


def test_operator_relations_cli_traces_skill_and_range(gamedata_root, capsys):
    main(["--data-root", str(gamedata_root), "inspect-operator", "char_test", "--resolve-relations"])
    output = json.loads(capsys.readouterr().out)
    assert output["operator"]["operator_id"] == "char_test"
    assert output["skills"][0]["levels"][0]["sp_cost"]["value"] == 30
    assert output["ranges"][0]["range_id"] == "rng_test"
