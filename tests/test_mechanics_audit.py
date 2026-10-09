from arknights_planner.simulator import basic_mechanic_audit_report
from arknights_planner.simulator import ModifierPipeline, arts_damage, attack_interval, elemental_damage, physical_damage, true_damage


def test_basic_mechanics_audit_separates_prts_access_from_project_implementation():
    report = basic_mechanic_audit_report()
    assert report["prts_access"] == "LOCAL_SNAPSHOT_AVAILABLE"
    rows = {row["mechanic"]: row for row in report["records"]}
    assert rows["物理伤害"]["project_status"] == "IMPLEMENTED_SOURCE_FORMULA"
    assert rows["真实伤害"]["project_status"] == "IMPLEMENTED_FORMULA_HELPER_NOT_RUNTIME"
    assert rows["攻击速度"]["prts_evidence_status"] == "VERIFIED_LOCAL_PRTS_SNAPSHOT"
    assert all(row["prts_sources"] for row in rows.values())


def test_local_prts_formula_helpers_match_saved_source_formulas():
    assert physical_damage(100.0, 150.0) == 5.0
    assert physical_damage(100.0, 50.0, penetration_ratio=0.2, penetration_flat=10.0) == 68.0
    assert arts_damage(100.0, 50.0) == 50.0
    assert arts_damage(100.0, 50.0, penetration_ratio=0.2, penetration_flat=10.0) == 68.0
    assert elemental_damage(100.0, 50.0) == 50.0
    assert true_damage(100.0) == 100.0
    assert attack_interval(1.0, 200.0) == 0.5
    assert ModifierPipeline(direct_add=10, direct_multiplier_add=.5, final_add=5, final_multiplier=.8).apply(100) == 136.0
