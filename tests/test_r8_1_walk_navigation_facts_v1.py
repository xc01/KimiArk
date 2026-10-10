from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "output/r8_1_walk_navigation_facts_v1/walk_navigation_facts.json"
ADAPTER_CHECK = ROOT / "output/r8_1_walk_navigation_facts_v1/adapter_conversion_check.json"


class WalkNavigationFactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FACTS.is_file():
            raise unittest.SkipTest("run scripts/build_r8_1_walk_navigation_facts_v1.py first")
        cls.facts = json.loads(FACTS.read_text(encoding="utf-8"))
        cls.adapter_check = json.loads(ADAPTER_CHECK.read_text(encoding="utf-8")) if ADAPTER_CHECK.is_file() else None

    def test_terrain_paths_do_not_cross_fly_only_interiors(self):
        routes = self.facts["routes"]
        self.assertTrue(all(item["fly_only_interior_consistent"] for item in routes.values()))
        self.assertEqual(routes["route-3"]["terrain_spfa_waypoints_col_row"], [[1, 1], [9, 1]])

    def test_route2_repeated_cell_traversals_are_preserved(self):
        route = self.facts["routes"]["route-2"]
        traversals = {tuple(item["tile"]): item["route_distances"] for item in route["terrain_spfa_cell_traversals"]}
        self.assertEqual(traversals[(4, 3)], [0.0, 2.0, 4.0])
        self.assertEqual(traversals[(3, 3)], [1.0, 3.0])

    def test_roadblock_effect_is_reported_unknown_not_hardened(self):
        self.assertEqual(self.facts["status_classification"]["roadblock_navigation_effect"], "UNKNOWN")
        self.assertIn(
            "conditional_roadblock_as_full_obstacle_routes",
            self.facts,
        )

    def test_public_adapter_matches_terrain_spfa_facts(self):
        if self.adapter_check is None or self.adapter_check.get("status") != "PASS":
            self.skipTest("adapter conversion evidence was not generated")
        for route_id, converted in self.adapter_check["converted_routes"].items():
            static = self.facts["routes"][route_id]
            self.assertEqual(converted["waypoints_col_row"], static["terrain_spfa_waypoints_col_row"])
            self.assertEqual(converted["length"], static["terrain_spfa_length"])
