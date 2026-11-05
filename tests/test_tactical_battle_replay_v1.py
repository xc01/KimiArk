from __future__ import annotations

import builtins
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "tactical_battle_replay_v1.py"
    spec = importlib.util.spec_from_file_location("tactical_battle_replay_v1_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


replay = load_module()


def event(event_type: str, frame: int, source: str | None = None, target: str | None = None, **details: object) -> dict[str, object]:
    return {
        "event_type": event_type,
        "frame": frame,
        "time": frame / 30.0,
        "source_id": source,
        "target_id": target,
        "details": details,
    }


def make_archive(tmp_path: Path, events: list[dict[str, object]], *, facts: dict[str, object] | None = None, gz: bool = False) -> ModuleType.Archive:
    events_path = tmp_path / ("diagnostic_events.json.gz" if gz else "diagnostic_events.json")
    if gz:
        import gzip

        with gzip.open(events_path, "wt", encoding="utf-8") as handle:
            json.dump({"events": events}, handle)
    else:
        events_path.write_text(json.dumps({"events": events}), encoding="utf-8")
    (tmp_path / "final_status.json").write_text(
        json.dumps({"result_classification": "TEST_ONLY", "enemies_killed": 1, "enemies_leaked": 0}),
        encoding="utf-8",
    )
    facts_path = None
    if facts is not None:
        facts_path = tmp_path / "llm_evidence_context.json"
        facts_path.write_text(json.dumps(facts), encoding="utf-8")
    return replay.load_archive(events_path, facts_path)


def map_facts() -> dict[str, object]:
    return {
        "stage_active_facts": {
            "map_size_col_row": [10, 8],
            "deployable_ground_tiles_col_row": [[3, 5], [5, 5], [5, 6]],
            "deployable_high_ground_tiles_col_row": [[2, 5]],
            "runtime_adapter_routes": [{"route_id": "route-1", "waypoints_col_row": [[0, 2], [9, 2]]}],
            "devices": [{"device_id": "trap#1", "template_id": "trap_020_roadblock", "tile_col_row": [2, 1]}],
        },
        "normal_low_star_catalog": [
            {
                "operator_id": "char_a",
                "name": "甲",
                "identity": {"profession": "GUARD", "rarity": 3},
                "stats": {"max_hp": 1000},
            }
        ],
    }


def test_real_simulator_import_is_fail_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def guard(name: str, *args: object, **kwargs: object) -> object:
        if name == "arknights_planner.simulator.simulator" or name.startswith("arknights_planner.simulator."):
            raise AssertionError("replay must not import the real Simulator")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    archive = make_archive(tmp_path, [event("SPAWN", 0, "enemy_a")])
    assert len(archive.events) == 1


def test_same_frame_event_order_is_preserved(tmp_path: Path) -> None:
    events = [
        event("TARGET_SELECTION", 10, "char_a", "enemy_a"),
        event("DEPLOY", 10, "char_a", details_tile := "5,3"),
        event("PROJECTILE_BORN", 10, "enemy_a", "char_a", locked_position=[5, 3]),
    ]
    archive = make_archive(tmp_path, events)
    assert [record.data["event_type"] for record in archive.events if record.frame == 10] == [
        "TARGET_SELECTION",
        "DEPLOY",
        "PROJECTILE_BORN",
    ]


def test_json_row_col_and_runtime_col_row_are_converted(tmp_path: Path) -> None:
    archive = make_archive(
        tmp_path,
        [event("DEPLOY", 0, "char_a", tile="5,3")],
        facts=map_facts(),
    )
    state = replay.build_state_to_frame(archive, 0)
    assert state.operators["char_a"].position == (5, 3)
    assert replay.runtime_col_row([5, 6]) == (5, 6)
    assert replay.event_row_col("5,3") == (5, 3)


def test_deploy_retreat_block_unblock_and_death(tmp_path: Path) -> None:
    archive = make_archive(
        tmp_path,
        [
            event("SPAWN", 0, "enemy_a"),
            event("DEPLOY", 1, "char_a", tile="5,3"),
            event("BLOCK", 2, "char_a", "enemy_a"),
            event("UNBLOCK", 3, "char_a", "enemy_a"),
            event("RETREAT", 4, "char_a"),
            event("SPAWN", 5, "enemy_b"),
            event("DEPLOY", 6, "char_b", tile="5,3"),
            event("OPERATOR_DEATH", 7, "char_b"),
        ],
    )
    state = replay.build_state_to_frame(archive, 2)
    assert state.enemies["enemy_a"].position == (5, 3)
    assert state.enemies["enemy_a"].position_status == "BLOCK_EVENT"
    state = replay.build_state_to_frame(archive, 3)
    assert state.enemies["enemy_a"].position is None
    state = replay.build_state_to_frame(archive, 4)
    assert not state.operators["char_a"].active
    state = replay.build_state_to_frame(archive, 7)
    assert state.operator_deaths == 1
    assert not state.operators["char_b"].active


def test_damage_heal_and_dp_unknown_are_not_zero_filled(tmp_path: Path) -> None:
    archive = make_archive(
        tmp_path,
        [
            event("SPAWN", 0, "enemy_a"),
            event("DAMAGE", 1, "char_a", "enemy_a", amount=10),
            event("DP_CHANGE", 2, "system", after=11.5),
        ],
    )
    state = replay.build_state_to_frame(archive, 1)
    assert state.enemies["enemy_a"].hp is None
    assert replay.format_number(state.enemies["enemy_a"].hp) == "?"
    state = replay.build_state_to_frame(archive, 2)
    assert state.dp == 11.5


def test_known_operator_hp_and_heal(tmp_path: Path) -> None:
    archive = make_archive(
        tmp_path,
        [
            event("DEPLOY", 0, "char_a", tile="5,3"),
            event("DAMAGE", 1, "enemy_a", "char_a", amount=200),
            event("HEAL", 2, "healer", "char_a", amount=100),
        ],
        facts=map_facts(),
    )
    state = replay.build_state_to_frame(archive, 1)
    assert state.operators["char_a"].hp == 800.0
    state = replay.build_state_to_frame(archive, 2)
    assert state.operators["char_a"].hp == 900.0


def locked_artillery_events() -> list[dict[str, object]]:
    return [
        event("DEPLOY", 0, "char_a", tile="5,6"),
        event(
            "ENEMY_ABILITY_START",
            10,
            "enemy_artillery",
            ability="enemy_1112_emppnt_artillery",
            target_position=[5, 6],
            radius=1.2,
            windup_seconds=0.333,
        ),
        event(
            "PROJECTILE_BORN",
            11,
            "enemy_artillery",
            "char_a",
            locked_position=[5, 6],
            radius=1.2,
            delay=3.0,
        ),
    ]


def test_locked_point_survives_retreat_and_marks_new_risk(tmp_path: Path) -> None:
    events = locked_artillery_events() + [
        event("RETREAT", 12, "char_a"),
        event("DEPLOY", 13, "char_b", tile="5,5"),
        event(
            "ENEMY_ABILITY_HIT",
            43,
            "enemy_artillery",
            "char_b",
            locked_position=[5, 6],
            amount=100,
        ),
    ]
    archive = make_archive(tmp_path, events, facts=map_facts())
    state = replay.build_state_to_frame(archive, 12)
    assert len(state.projectiles) == 1
    assert state.projectiles[0].locked
    assert state.projectiles[0].position == (5, 6)
    assert replay.operators_in_risk(state) == []
    state = replay.build_state_to_frame(archive, 13)
    assert ("char_b", "P01", (5, 5)) in replay.operators_in_risk(state)
    lines = replay.render_lines(archive, state, height=100, width=200)
    assert "IN_FLIGHT_RISK char_b@(5, 5)" in lines
    assert "R" in "\n".join(replay.render_grid(archive, state, "char_b"))
    state = replay.build_state_to_frame(archive, 43)
    assert state.projectiles == []


def test_tracking_and_locked_projectiles_are_distinct(tmp_path: Path) -> None:
    events = locked_artillery_events() + [
        event("PROJECTILE_BORN", 14, "char_a", "enemy_a"),
    ]
    archive = make_archive(tmp_path, events)
    state = replay.build_state_to_frame(archive, 14)
    lines = replay.projectile_lines(state)
    assert sum("LOCKED_POINT" in line for line in lines) == 1
    assert sum("TRACKING" in line for line in lines) == 1


def test_multiple_locked_projectiles_stack_without_overwrite(tmp_path: Path) -> None:
    events = [
        event("PROJECTILE_BORN", 10, "enemy_a", "char_a", locked_position=[5, 6], radius=1.0, delay=2.0),
        event("PROJECTILE_BORN", 11, "enemy_b", "char_a", locked_position=[5, 6], radius=1.0, delay=3.0),
    ]
    archive = make_archive(tmp_path, events)
    state = replay.build_state_to_frame(archive, 11)
    assert len(state.projectiles) == 2
    assert {item.projectile_id for item in state.projectiles} == {1, 2}


def test_cancel_is_not_fabricated_as_hit(tmp_path: Path) -> None:
    events = [
        event("DEPLOY", 0, "char_a", tile="5,6"),
        event(
            "ENEMY_ABILITY_START",
            1,
            "enemy_artillery",
            ability="enemy_1112_emppnt_artillery",
            target_position=[5, 6],
            radius=1.2,
            windup_seconds=0.3,
        ),
        event("ENEMY_ABILITY_CANCELLED", 2, "enemy_artillery", "char_a", reason="TARGET_UNAVAILABLE_BEFORE_PROJECTILE_CREATION"),
    ]
    archive = make_archive(tmp_path, events)
    state = replay.build_state_to_frame(archive, 2)
    assert state.casts == []
    assert state.projectiles == []


def test_normal_projectile_hit_is_removed(tmp_path: Path) -> None:
    events = [
        event("PROJECTILE_BORN", 10, "char_a", "enemy_a"),
        event("PROJECTILE_HIT", 12, "char_a", "enemy_a"),
    ]
    archive = make_archive(tmp_path, events)
    state = replay.build_state_to_frame(archive, 12)
    assert state.projectiles == []


def test_sequential_and_jump_replay_are_identical(tmp_path: Path) -> None:
    archive = make_archive(tmp_path, locked_artillery_events())
    sequential = replay.initial_state(archive)
    for record in archive.events:
        replay.apply_event(archive, sequential, record)
    jumped = replay.build_state_to_frame(archive, 11)
    assert sequential.frame == jumped.frame
    assert sequential.time == jumped.time
    assert sequential.event_index == jumped.event_index
    assert sequential.dp == jumped.dp
    assert len(sequential.projectiles) == len(jumped.projectiles)
    assert [item.__dict__ for item in sequential.projectiles] == [item.__dict__ for item in jumped.projectiles]


def test_key_event_step_matches_rebuild(tmp_path: Path) -> None:
    archive = make_archive(
        tmp_path,
        [
            event("TARGET_SELECTION", 0, "char_a"),
            event("PROJECTILE_BORN", 1, "enemy_a", locked_position=[5, 6]),
            event("TARGET_SELECTION", 2, "char_a"),
            event("ENEMY_DEATH", 3, "char_a", "enemy_a"),
        ],
    )
    state = replay.initial_state(archive)
    replay.apply_until_event(archive, state, state.event_index + 1, key_only=True)
    rebuilt = replay.build_state_to_event(archive, state.event_index)
    assert state.event_index == rebuilt.event_index
    assert state.frame == rebuilt.frame


def test_timeline_and_dump_frame_non_tty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archive = make_archive(tmp_path, locked_artillery_events())
    assert replay.main([str(archive.events_path), "--dump-frame", "11"]) == 0
    output = capsys.readouterr().out
    assert "LOCKED_POINT" in output
    assert replay.main([str(archive.events_path), "--timeline"]) == 0
    assert "PROJECTILE_BORN" in capsys.readouterr().out
    assert replay.main([str(archive.events_path)]) == 2


def test_gzip_archive_is_supported(tmp_path: Path) -> None:
    archive = make_archive(tmp_path, locked_artillery_events(), gz=True)
    state = replay.build_state_to_frame(archive, 11)
    assert state.projectiles[0].locked


def test_missing_map_reports_unknown(tmp_path: Path) -> None:
    archive = make_archive(tmp_path, [event("DEPLOY", 0, "char_a", tile="5,3")])
    lines = replay.render_lines(archive, replay.build_state_to_frame(archive, 0), height=100, width=200)
    assert any("缺少 map facts" in line for line in lines)


def test_ascii_grid_uses_dual_encoded_characters(tmp_path: Path) -> None:
    events = locked_artillery_events() + [
        event("RETREAT", 12, "char_a"),
        event("DEPLOY", 13, "char_b", tile="5,5"),
    ]
    archive = make_archive(tmp_path, events, facts=map_facts())
    state = replay.build_state_to_frame(archive, 13)
    grid = "\n".join(replay.render_grid(archive, state, "char_b", ascii_mode=True))
    assert "X" in grid
    assert "*" in grid
    assert "R" in grid


def test_operator_markers_use_first_letter_with_collision_numbers(tmp_path: Path) -> None:
    archive = make_archive(tmp_path, [])
    archive.operator_stats = {
        "char_a_fang": {},
        "char_b_frston": {},
        "char_c_midn": {},
        "char_d_melan": {},
    }
    assert replay.operator_marker(archive, "char_a_fang") == "F"
    assert replay.operator_marker(archive, "char_b_frston") == "F1"
    assert replay.operator_marker(archive, "char_c_midn") == "M"
    assert replay.operator_marker(archive, "char_d_melan") == "M1"


def test_grid_shows_operator_marker_enemy_count_and_key_monsters(tmp_path: Path) -> None:
    events = [
        event("SPAWN", 0, "enemy_1112_emppnt#0", enemy_id="enemy_1112_emppnt", route_id="route-1"),
        event("SPAWN", 1, "enemy_1110_uamord#34", enemy_id="enemy_1110_uamord", route_id="route-2"),
        event("SPAWN", 2, "enemy_normal#2", enemy_id="enemy_normal", route_id="route-3"),
        event("DEPLOY", 3, "char_a", tile="5,3"),
        event("DEPLOY", 4, "char_b", tile="5,4"),
        event("DEPLOY", 5, "char_c", tile="5,5"),
        event("BLOCK", 6, "char_a", "enemy_1112_emppnt#0"),
        event("BLOCK", 7, "char_b", "enemy_1110_uamord#34"),
        event("BLOCK", 8, "char_c", "enemy_normal#2"),
    ]
    archive = make_archive(tmp_path, events, facts=map_facts())
    state = replay.build_state_to_frame(archive, 8)
    grid = "\n".join(replay.render_grid(archive, state, None))
    assert "A1" in grid
    assert "K1" in grid
    assert "E1" in grid
    assert "A" in grid and "K" in grid


def test_filtered_and_full_event_modes(tmp_path: Path) -> None:
    archive = make_archive(
        tmp_path,
        [
            event("TARGET_SELECTION", 0, "char_a"),
            event("DEPLOY", 1, "char_b", tile="5,3"),
        ],
    )
    key_indices = replay.filtered_event_indices(archive, None, False)
    full_indices = replay.filtered_event_indices(archive, None, True)
    filtered = replay.filtered_event_indices(archive, "char_a", True)
    assert key_indices == [1]
    assert full_indices == [0, 1]
    assert filtered == [0]
