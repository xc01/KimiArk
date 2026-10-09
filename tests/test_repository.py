from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.provenance import KnowledgeStatus


def test_operator_reconstruction_retains_factual_paths(gamedata_root):
    repo = GameDataRepository(gamedata_root)
    operator = repo.get_operator("Test Guard")
    assert operator.operator_id == "char_test"
    assert operator.phases[0].stats_max.atk.value == 500
    assert operator.phases[0].stats_max.atk.status is KnowledgeStatus.KNOWN
    assert operator.phases[0].stats_max.atk.source_path.endswith(".atk")
    assert operator.phases[0].range_id.value == "rng_test"
    assert operator.skill_ids == ("sk_test",)
    skill = repo.get_skill("sk_test")
    assert skill.levels[0].name.value == "Test Skill"
    assert skill.levels[0].sp_cost.value == 30
    assert skill.levels[0].blackboard == (("atk", 0.5),)
    attack_range = repo.get_range("rng_test")
    assert attack_range.direction.value == 1


def test_enemy_and_stage_table_joins(gamedata_root):
    repo = GameDataRepository(gamedata_root)
    enemy = repo.get_enemy("enemy_test")
    assert enemy.name.value == "Test Slug"
    assert enemy.stats.move_speed.value == 1.0
    assert enemy.stats.weight.value == 1
    assert enemy.raw_source_file.endswith("levels/enemydata/enemy_database.json")
    stage = repo.get_stage("1-7")
    assert stage.stage_id == "main_01-07"
    assert stage.map_width.value == 3
    assert stage.map_width.status is KnowledgeStatus.DERIVABLE
    assert stage.map_height.value == 2
    assert stage.route_count.value == 1
    assert stage.enemy_references == (("enemy_test", 0),)
    assert stage.spawn_action_count.value == 1
    assert stage.initial_dp.value == 10
    report = repo.stage_reconstruction_report("1-7")
    fields = {field.field: field.status for field in report.fields}
    assert fields["Map"] is KnowledgeStatus.DERIVABLE
    assert fields["Enemy roster"] is KnowledgeStatus.KNOWN
    assert fields["Spawn events"] is KnowledgeStatus.KNOWN
    assert fields["Projectile speed"] is KnowledgeStatus.UNKNOWN
