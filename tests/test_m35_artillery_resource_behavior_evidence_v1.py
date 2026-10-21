from __future__ import annotations

import json
from pathlib import Path


EVIDENCE = (
    Path(__file__).resolve().parents[1]
    / "docs/review/fc77177/m35_artillery_resource_v1/artillery_resource_behavior_evidence.json"
)


def test_resource_hashes_match_decoded_hot_list() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["resource_version"] == "26-10-14-13-45-10-99469376"
    assert evidence["hot_list"]["rows_present"] == 5
    assert evidence["hot_list"]["rows_absent"] == []
    resources = {item["logical_path"]: item for item in evidence["resources"]}
    assert resources["battle/enm_pfb_6.ab"]["manifest_md5_match"] is True
    assert resources["battle/prefabs/[uc]projectiles.ab"]["manifest_md5_match"] is True
    assert resources["pkgrps/btl_pfb_fx_enemy_5.ab"]["manifest_md5_match"] is True


def test_behavior_binding_and_evidence_limits_are_explicit() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["binding_evidence"]["enemy_bundle"]["container"] == (
        "dyn/battle/prefabs/enemies/enemy_1112_emppnt.prefab"
    )
    assert evidence["binding_evidence"]["projectile_bundle"]["container"] == (
        "dyn/battle/prefabs/[uc]projectiles/projectile_enemy_emppnt.prefab"
    )
    combat = evidence["binding_evidence"]["enemy_bundle"]["combat_ability"]["fields"]
    selector = evidence["binding_evidence"]["enemy_bundle"]["target_selector"]["fields"]
    assert combat["_projectileKey"] == "projectile_enemy_emppnt"
    assert combat["_projectileDestination"] == 2
    assert selector["_postFilter"] == 4
    assert selector["_sortByTauntAtLast"] == 1
    assert evidence["source_provenance"]["build2771_resource_manifest"][
        "signature_verification"
    ] == "NOT_PERFORMED"
    assert evidence["conclusion"]["build2771_behavior_chain"] == "NOT_CLAIMED"
