from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


class RoadblockNavigationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]
        self.evidence_path = self.root / "output/r8_1_roadblock_navigation_evidence_v1/roadblock_navigation_evidence.json"
        self.evidence = json.loads(self.evidence_path.read_text(encoding="utf-8"))

    def test_raw_evidence_hashes_match_manifest(self) -> None:
        for record in self.evidence["raw_evidence_files"]:
            path = self.evidence_path.parent / record["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_roadblock_navigation_effect_remains_unknown(self) -> None:
        self.assertEqual(self.evidence["current_model_conclusion"]["roadblock_navigation_effect"], "UNKNOWN")
        self.assertEqual(
            self.evidence["current_model_conclusion"]["full_obstacle_variant"],
            "HYPOTHESIS_NOT_CLIENT_FACT",
        )
        self.assertEqual(
            self.evidence["current_model_conclusion"]["conditional_civilian_talulah_variant"],
            "HYPOTHESIS_NOT_CLIENT_FACT",
        )

    def test_generic_client_chain_is_separate_from_roadblock_payload(self) -> None:
        confirmed_ids = {item["claim_id"] for item in self.evidence["confirmed_from_code"]}
        self.assertIn("TOKEN_CAN_PROVIDE_TILE_OPTIONS", confirmed_ids)
        self.assertIn("TOKEN_FINISH_HAS_RESTORE_PATH", confirmed_ids)
        unknown_ids = {item["claim_id"] for item in self.evidence["unknown_or_unresolved"]}
        self.assertIn("ROADBLOCK_PREFAB_REWRITE_TILE_OPTIONS", unknown_ids)
        self.assertIn("ROADBLOCK_EFFECT_ON_ORDINARY_WALK_NAVIGATION", unknown_ids)


if __name__ == "__main__":
    unittest.main()
