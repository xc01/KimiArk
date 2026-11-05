from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "docs/review/fc77177/m70_vs_astra_c3_comparison_v1/build_comparison_v1.py"


def _module():
    spec = importlib.util.spec_from_file_location("m70_vs_c3_comparison", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_operator_damage_distinguishes_and_totals_deduplicated_categories() -> None:
    module = _module()
    events = [
        {"event_type": "DAMAGE", "source_id": "enemy", "target_id": "op", "details": {"amount": 10}},
        {"event_type": "ENEMY_ABILITY_HIT", "source_id": "enemy", "target_id": "op", "details": {"amount": 910}},
        {"event_type": "DAMAGE", "source_id": "op", "target_id": "enemy", "details": {"amount": 20}},
        {"event_type": "ENEMY_ABILITY_HIT", "source_id": "op", "target_id": "enemy", "details": {"amount": 30}},
    ]
    stats = module.operator_stats(events, ["op"])
    assert stats[0]["normal_damage_taken"] == 10
    assert stats[0]["ability_damage_taken"] == 910
    assert stats[0]["damage_taken_total"] == 920
    assert stats[0]["normal_damage_dealt"] == 20
    assert stats[0]["ability_damage_dealt"] == 30
    assert stats[0]["damage_dealt_total"] == 50


def test_artillery_shells_preserve_distinct_locked_positions() -> None:
    module = _module()
    events = [
        {
            "event_type": "ENEMY_ABILITY_START", "frame": 2043, "source_id": "enemy_1112_emppnt#0",
            "details": {"target_position": [5, 6]},
        },
        {
            "event_type": "PROJECTILE_BORN", "frame": 2053, "source_id": "enemy_1112_emppnt#0",
            "target_id": "char_208_melan", "details": {"locked_position": [5, 6]},
        },
        {
            "event_type": "ENEMY_ABILITY_START", "frame": 2193, "source_id": "enemy_1112_emppnt#0",
            "details": {"target_position": [6, 5]},
        },
        {
            "event_type": "PROJECTILE_BORN", "frame": 2203, "source_id": "enemy_1112_emppnt#0",
            "target_id": "char_212_ansel", "details": {"locked_position": [6, 5]},
        },
    ]
    shells = module.artillery_shells(events)
    assert [shell["projectile_born"][0]["details"]["locked_position"] for shell in shells] == [[5, 6], [6, 5]]
