from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


class RoadblockWalkNavigationV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]
        self.output_dir = self.root / "output/r8_1_roadblock_walk_navigation_v3"
        self.evidence = json.loads(
            (self.output_dir / "ordinary_walk_navigation_evidence.json").read_text(encoding="utf-8")
        )
        self.manifest = json.loads((self.output_dir / "manifest.json").read_text(encoding="utf-8"))

    def test_classify_distinguishes_entry_failure_partial_and_complete(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "extract_roadblock_walk_navigation_v3",
            self.root / "scripts/extract_roadblock_walk_navigation_v3.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        self.assertEqual(
            module.classify_decodability(0, 0, 16)["classification"], "ENTRY_DECODE_FAILED"
        )
        self.assertEqual(
            module.classify_decodability(1, 4, 16)["classification"], "PARTIAL_DECODE"
        )
        self.assertEqual(
            module.classify_decodability(4, 16, 16)["classification"], "COMPLETE_DECODE"
        )

    def test_manifest_hashes_match(self) -> None:
        self.assertEqual(
            {item["path"] for item in self.manifest["files"]},
            {
                "ordinary_walk_navigation_disasm.txt",
                "ordinary_walk_navigation_evidence.json",
                "provenance.txt",
            },
        )
        for item in self.manifest["files"]:
            path = self.output_dir / item["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])

    def test_stale_v2_conclusions_are_corrected_not_repeated(self) -> None:
        navigation = self.evidence["ordinary_walk_navigation"]
        self.assertEqual(
            navigation["route_refresh_signal"],
            "moveCost change and passableMask XOR are combined into dirty bits.",
        )
        self.assertIn("cached_node.distance - queried_tile.get_moveCost() < 1000", navigation["avoid_obstacle_like"])
        self.assertIn("UNKNOWN", navigation["avoid_obstacle_like"])
        corrections = {item["old_label"]: item for item in self.evidence["corrections"]}
        self.assertEqual(corrections["NOT_TRIGGERED_FOR_UNCHANGED_WALK_FLY_MASK"]["validity"], "FALSE")
        self.assertEqual(corrections["FALSE_IF_AVOID_OBSTACLE_LIKE_IS_TRUE"]["validity"], "OVERGENERALIZED")

    def test_missing_route_to_spfa_edge_is_not_hardened(self) -> None:
        chain = {item["edge"]: item for item in self.evidence["ordinary_walk_navigation"]["chain"]}
        missing = chain["Route.ReconstructNextMap -> SPFA path generation"]
        self.assertEqual(missing["status"], "UNKNOWN_MISSING_STATIC_EDGE")
        self.assertIn("method signatures", missing["reason"])

    def test_r8_1_walk_route_scope_is_preserved(self) -> None:
        scope = self.evidence["r8_1_route_scope"]
        self.assertEqual(scope["gamedata_commit"], "0ef7f952dfd018392200157a5c79a6511ba69122")
        self.assertEqual(scope["source_motion_mode_counts"], {"WALK": 33, "E_NUM": 2})
        self.assertEqual(len(scope["walk_routes"]), 33)


if __name__ == "__main__":
    unittest.main()
