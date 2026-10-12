from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


class RoadblockPrefabEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]
        self.output_dir = self.root / "output/r8_1_roadblock_prefab_evidence_v2"
        self.evidence = json.loads(
            (self.output_dir / "roadblock_prefab_evidence.json").read_text(encoding="utf-8")
        )
        self.extraction = json.loads(
            (self.output_dir / "roadblock_prefab_extraction.json").read_text(encoding="utf-8")
        )
        self.manifest = json.loads((self.output_dir / "manifest.json").read_text(encoding="utf-8"))

    def test_manifest_hashes_cover_all_extracted_artifacts(self) -> None:
        self.assertEqual(
            {item["path"] for item in self.manifest["files"]},
            {
                "roadblock_navigation_disasm.txt",
                "roadblock_prefab_evidence.json",
                "roadblock_prefab_extraction.json",
                "provenance.txt",
            },
        )
        for item in self.manifest["files"]:
            path = self.output_dir / item["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])

    def test_decode_attempts_are_bounded_and_lz4ak_succeeds(self) -> None:
        attempts = self.extraction["decode_attempts"]
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0]["method"], "UNITYPY_DEFAULT")
        self.assertEqual(attempts[0]["exception_type"], "NotImplementedError")
        self.assertEqual(attempts[1]["method"], "ARKNIGHTS_LZ4AK_FLAG_4")
        self.assertEqual(attempts[1]["status"], "SUCCESS")

    def test_exact_roadblock_tile_options_are_recorded(self) -> None:
        root = self.extraction["prefab"]["root_component"]["fields"]
        mode = self.extraction["prefab"]["mode_component"]["fields"]
        self.assertEqual(root["_rewriteTileOptions"], 1)
        self.assertEqual(mode["_keepCurrentPassableMask"], 1)
        self.assertEqual(mode["_tileOptions"]["passableMask"], 0)
        self.assertEqual(mode["_tileOptions"]["overrideObstacleLikeMoveCost"], 1)
        self.assertEqual(root["_filterTag"], ["tap_roadblock"])

    def test_ordinary_walk_is_not_hardened_to_a_full_obstacle(self) -> None:
        ordinary_walk = self.evidence["ordinary_walk_navigation"]
        self.assertEqual(ordinary_walk["passable_mask"], "UNCHANGED_BY_KEEP_CURRENT_PASSABLE_MASK")
        self.assertEqual(
            ordinary_walk["avoid_obstacle_like_reachable"],
            "FALSE_IF_AVOID_OBSTACLE_LIKE_IS_TRUE",
        )
        self.assertEqual(ordinary_walk["default_route_generation_effect"], "UNKNOWN")

    def test_unresolved_semantics_remain_unknown(self) -> None:
        self.assertEqual(self.evidence["civilian_talulah_blocking"], "UNKNOWN")
        self.assertEqual(self.evidence["cross_version_applicability"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
