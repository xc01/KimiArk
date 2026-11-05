#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from build_review_v1 import key_enemy_summary, operator_damage, roadblock_summary


def event(event_type: str, frame: int, source_id: str | None = None, target_id: str | None = None, amount: float | None = None):
    details = {} if amount is None else {"amount": amount}
    return {"event_type": event_type, "frame": frame, "source_id": source_id, "target_id": target_id, "details": details}


class ReadOnlyReviewFixtureTest(unittest.TestCase):
    def test_operator_damage_separates_ability_hit_from_ordinary_damage(self):
        events = [
            event("DAMAGE", 100, "enemy_a", "char_a", 120.0),
            event("ENEMY_ABILITY_HIT", 200, "enemy_a", "char_a", 891.0),
            event("HEAL", 300, "char_b", "char_a", 500.0),
            event("OPERATOR_DEATH", 400, None, "char_a"),
        ]
        result = operator_damage(events, "char_a")
        self.assertEqual(result["ordinary_damage_total"], 120.0)
        self.assertEqual(result["ability_damage_total"], 891.0)
        self.assertEqual(result["heal_total"], 500.0)
        self.assertEqual(len(result["events"]), 4)

    def test_roadblock_summary_ignores_unrelated_events_and_handles_null_ids(self):
        events = [
            event("DEVICE_DAMAGE", 10, "char_a", "trap_020_roadblock#4", 100.0),
            event("DEVICE_DESTROYED", 20, "char_a", "trap_020_roadblock#4"),
            event("DAMAGE", 30, "enemy_a", "enemy_3001_upeopl#3", 950.0),
            event("SPAWN", 40, None, None),
        ]
        result = roadblock_summary(events)
        self.assertEqual(result["damage"]["trap_020_roadblock#4"]["damage_total"], 100.0)
        self.assertEqual(result["destroyed_frames"], {"trap_020_roadblock#4": 20})

    def test_roadblock_and_protected_target_are_distinct_entities(self):
        events = [
            event("BLOCK", 10, "trap_020_roadblock#3", "enemy_3001_upeopl#3"),
            event("DAMAGE", 20, "enemy_a", "enemy_3001_upeopl#3", 950.0),
        ]
        roadblocks = roadblock_summary(events)
        self.assertEqual(roadblocks["damage"], {})
        key_enemies = key_enemy_summary(events)
        self.assertIn("enemy_1110_uamord#21", key_enemies)


if __name__ == "__main__":
    unittest.main()
