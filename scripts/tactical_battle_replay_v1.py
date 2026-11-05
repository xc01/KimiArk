#!/usr/bin/env python3
from __future__ import annotations

import argparse
import curses
import gzip
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


FRAME_RATE = 30.0
DEFAULT_SPEED = 0.25
GRID_CELL_WIDTH = 5
KEY_EVENT_TYPES = {
    "DEPLOY",
    "RETREAT",
    "OPERATOR_DEATH",
    "SKILL_ACTIVATE",
    "SKILL_END",
    "BLOCK",
    "UNBLOCK",
    "ENEMY_ABILITY_START",
    "PROJECTILE_BORN",
    "ENEMY_ABILITY_CANCELLED",
    "ENEMY_ABILITY_HIT",
    "ENEMY_DEATH",
    "ENEMY_LEAK",
    "DEVICE_DAMAGE",
    "DEVICE_DESTROYED",
    "PROTECTED_TARGET_REACHED",
    "OBJECTIVE_FAILURE",
}


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    with path.open("rt", encoding="utf-8") as handle:
        return json.load(handle)


def discover_events(path: Path) -> Path:
    if path.is_file():
        return path
    if not path.is_dir():
        raise FileNotFoundError(f"replay path does not exist: {path}")
    candidates = sorted(path.glob("diagnostic_events.json.gz")) + sorted(path.glob("diagnostic_events.json"))
    if len(candidates) != 1:
        names = ", ".join(item.name for item in candidates) or "none"
        raise ValueError(f"ambiguous or missing event archive in {path}: {names}")
    return candidates[0]


def unique_file(directory: Path, name: str) -> Path | None:
    candidates = [directory / name]
    if (directory / f"{name}.gz").is_file():
        candidates.append(directory / f"{name}.gz")
    found = [candidate for candidate in candidates if candidate.is_file()]
    return found[0] if len(found) == 1 else None


def event_row_col(value: Any) -> tuple[int, int] | None:
    if isinstance(value, str) and "," in value:
        parts = value.split(",")
        if len(parts) == 2:
            try:
                col, row = (int(part.strip()) for part in parts)
                return (col, row)
            except ValueError:
                return None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        try:
            first, second = (int(item) for item in value)
        except (TypeError, ValueError):
            return None
        return (first, second)
    return None


def runtime_col_row(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        return None
    try:
        col, row = (int(item) for item in value)
    except (TypeError, ValueError):
        return None
    return (col, row)


@dataclass(frozen=True)
class EventRecord:
    index: int
    frame: int
    time: float
    data: dict[str, Any]


@dataclass
class Unit:
    unit_id: str
    name: str
    kind: str
    active: bool = False
    position: tuple[int, int] | None = None
    position_status: str = "UNKNOWN"
    hp: float | None = None
    max_hp: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Cast:
    source_id: str
    ability: str
    target_id: str | None
    target_position: tuple[int, int] | None
    radius: float | None
    start_frame: int
    windup_seconds: float | None


@dataclass
class Projectile:
    projectile_id: int
    source_id: str
    target_id: str | None
    position: tuple[int, int] | None
    radius: float | None
    born_frame: int
    born_time: float
    hit_time: float | None
    locked: bool
    ability: str | None = None


@dataclass
class ReplayState:
    frame: int = -1
    time: float | None = None
    event_index: int = -1
    dp: float | None = None
    life: int | None = None
    kills: int = 0
    leaks: int = 0
    protected_reached: int = 0
    operator_deaths: int = 0
    devices_destroyed: int = 0
    operators: dict[str, Unit] = field(default_factory=dict)
    enemies: dict[str, Unit] = field(default_factory=dict)
    casts: list[Cast] = field(default_factory=list)
    projectiles: list[Projectile] = field(default_factory=list)
    last_target_selection: dict[str, dict[str, Any]] = field(default_factory=dict)
    recent_hit: dict[str, int] = field(default_factory=dict)
    display_frame: int | None = None


@dataclass
class Archive:
    events_path: Path
    events: tuple[EventRecord, ...]
    facts: dict[str, Any] | None
    facts_path: Path | None
    manifest: dict[str, Any] | None
    final_status: dict[str, Any] | None
    map_cols: int | None = None
    map_rows: int | None = None
    ground: set[tuple[int, int]] = field(default_factory=set)
    high_ground: set[tuple[int, int]] = field(default_factory=set)
    route_cells: dict[str, set[tuple[int, int]]] = field(default_factory=dict)
    device_tiles: dict[str, tuple[int, int]] = field(default_factory=dict)
    operator_names: dict[str, str] = field(default_factory=dict)
    operator_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def load_events(path: Path) -> tuple[EventRecord, ...]:
    payload = load_json(path)
    raw = payload.get("events", []) if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        raise ValueError(f"events file must contain a list or {{'events': [...]}}: {path}")
    records = []
    for index, event in enumerate(raw):
        if not isinstance(event, dict) or "frame" not in event:
            raise ValueError(f"invalid event at index {index}: expected object with frame")
        records.append(
            EventRecord(
                index=index,
                frame=int(event["frame"]),
                time=float(event.get("time", index / FRAME_RATE)),
                data=event,
            )
        )
    return tuple(records)


def locate_facts(events_path: Path, explicit: Path | None, manifest: dict[str, Any] | None) -> Path | None:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"facts file does not exist: {explicit}")
        return explicit
    for directory in (events_path.parent, events_path.parent.parent):
        candidate = unique_file(directory, "llm_evidence_context.json")
        if candidate is not None:
            return candidate
    source = manifest.get("source") if manifest else None
    if isinstance(source, str) and source:
        candidate = Path(source) / "llm_evidence_context.json"
        if candidate.is_file():
            return candidate
    return None


def load_archive(path: Path, facts_path: Path | None) -> Archive:
    events_path = discover_events(path)
    directory = events_path.parent
    action_path = unique_file(directory, "action_snapshot.json")
    plan_path = unique_file(directory, "plan_snapshot.json")
    manifest_path = unique_file(directory, "manifest.json")
    final_path = unique_file(directory, "final_status.json")
    manifest = load_json(manifest_path) if manifest_path else None
    final_status = load_json(final_path) if final_path else None
    resolved_facts = locate_facts(events_path, facts_path, manifest if isinstance(manifest, dict) else None)
    facts = load_json(resolved_facts) if resolved_facts else None
    archive = Archive(
        events_path=events_path,
        events=load_events(events_path),
        facts=facts if isinstance(facts, dict) else None,
        facts_path=resolved_facts,
        manifest=manifest if isinstance(manifest, dict) else None,
        final_status=final_status if isinstance(final_status, dict) else None,
    )
    load_map(archive, facts)
    load_catalog(archive, facts)
    if not archive.events:
        archive.warnings.append("event archive is empty")
    return archive


def load_map(archive: Archive, facts: dict[str, Any] | None) -> None:
    if not facts:
        archive.warnings.append("map facts unavailable; map panel will be empty")
        return
    active = facts.get("stage_active_facts", {})
    if not isinstance(active, dict):
        return
    size = runtime_col_row(active.get("map_size_col_row"))
    if size:
        archive.map_cols, archive.map_rows = size
    archive.ground = {tuple(item) for item in active.get("deployable_ground_tiles_col_row", []) if len(item) == 2}
    archive.high_ground = {tuple(item) for item in active.get("deployable_high_ground_tiles_col_row", []) if len(item) == 2}
    for route in active.get("runtime_adapter_routes", []):
        if isinstance(route, dict):
            archive.route_cells[str(route.get("route_id"))] = {
                tuple(item) for item in route.get("waypoints_col_row", []) if len(item) == 2
            }
    for device in active.get("devices", []):
        if isinstance(device, dict) and device.get("device_id"):
            position = runtime_col_row(device.get("tile_col_row"))
            if position:
                archive.device_tiles[str(device["device_id"])] = position


def load_catalog(archive: Archive, facts: dict[str, Any] | None) -> None:
    if not facts:
        return
    catalog = facts.get("normal_low_star_catalog", [])
    if not isinstance(catalog, list):
        return
    for entry in catalog:
        if not isinstance(entry, dict) or not entry.get("operator_id"):
            continue
        operator_id = str(entry["operator_id"])
        archive.operator_names[operator_id] = str(entry.get("name") or operator_id)
        archive.operator_stats[operator_id] = entry


def operator_from_catalog(archive: Archive, unit_id: str) -> Unit:
    entry = archive.operator_stats.get(unit_id, {})
    identity = entry.get("identity", {}) if isinstance(entry, dict) else {}
    stats = entry.get("stats", {}) if isinstance(entry, dict) else {}
    max_hp = stats.get("max_hp") if isinstance(stats.get("max_hp"), (int, float)) else None
    return Unit(
        unit_id=unit_id,
        name=archive.operator_names.get(unit_id, unit_id),
        kind="OPERATOR",
        hp=max_hp,
        max_hp=max_hp,
        metadata={
            "profession": identity.get("profession", "UNKNOWN"),
            "rarity": identity.get("rarity", "UNKNOWN"),
            "stats": stats,
            "marker": operator_marker(archive, unit_id),
        },
    )


def operator_marker(archive: Archive, unit_id: str) -> str:
    ordered_ids = sorted(archive.operator_stats)
    suffix = unit_id.rsplit("_", 1)[-1]
    first_letter = next((char for char in suffix.upper() if char.isalpha()), "O")
    same_prefix = [item for item in ordered_ids if item.rsplit("_", 1)[-1].upper().startswith(first_letter)]
    if unit_id not in same_prefix:
        return first_letter
    ordinal = same_prefix.index(unit_id)
    return first_letter if ordinal == 0 else f"{first_letter}{ordinal}"


def key_enemy_kind(unit: Unit) -> str | None:
    enemy_id = str(unit.metadata.get("enemy_id", ""))
    unit_id = unit.unit_id
    if enemy_id == "enemy_1112_emppnt" or "artillery" in unit_id:
        return "ARTILLERY"
    if unit_id.endswith("#34"):
        return "KEY_34"
    return None


def initial_state(archive: Archive) -> ReplayState:
    state = ReplayState()
    final_status = archive.final_status
    if isinstance(final_status, dict) and isinstance(final_status.get("remaining_life"), (int, float)):
        state.life = None
    return state


def apply_event(archive: Archive, state: ReplayState, record: EventRecord) -> None:
    event = record.data
    event_type = str(event.get("event_type", ""))
    source_id = event.get("source_id")
    target_id = event.get("target_id")
    details = event.get("details", {})
    if not isinstance(details, dict):
        details = {}
    state.frame = record.frame
    state.time = record.time
    state.event_index = record.index

    if event_type == "SPAWN":
        unit = Unit(
            unit_id=str(source_id),
            name=str(source_id),
            kind="ENEMY",
            active=True,
            metadata={"enemy_id": details.get("enemy_id", "UNKNOWN"), "route_id": details.get("route_id", "UNKNOWN")},
        )
        state.enemies[str(source_id)] = unit
        key_kind = key_enemy_kind(unit)
        if key_kind:
            unit.metadata["key_kind"] = key_kind
    elif event_type == "DEPLOY":
        position = event_row_col(details.get("tile"))
        legal = details.get("legal", True)
        if legal and position:
            unit = operator_from_catalog(archive, str(source_id))
            unit.active = True
            unit.position = position
            unit.position_status = "EVENT"
            state.operators[str(source_id)] = unit
    elif event_type in {"RETREAT", "OPERATOR_DEATH"}:
        unit = state.operators.get(str(source_id))
        if unit:
            unit.active = False
            unit.position = None
            unit.position_status = "UNKNOWN"
            if event_type == "OPERATOR_DEATH":
                state.operator_deaths += 1
    elif event_type == "DAMAGE":
        amount = details.get("amount")
        unit = state.operators.get(str(target_id)) or state.enemies.get(str(target_id))
        if unit and isinstance(amount, (int, float)) and unit.hp is not None:
            unit.hp = (unit.hp if unit.hp is not None else 0.0) - float(amount)
        if unit:
            state.recent_hit[str(target_id)] = record.frame
    elif event_type == "HEAL":
        amount = details.get("amount")
        unit = state.operators.get(str(target_id)) or state.enemies.get(str(target_id))
        if unit and isinstance(amount, (int, float)) and unit.hp is not None:
            unit.hp = min(unit.max_hp, unit.hp + float(amount)) if unit.max_hp is not None else unit.hp + float(amount)
    elif event_type == "BLOCK":
        holder = state.operators.get(str(source_id))
        enemy = state.enemies.get(str(target_id))
        if enemy:
            enemy.metadata["blocked_by"] = source_id
            if holder and holder.position:
                enemy.position = holder.position
                enemy.position_status = "BLOCK_EVENT"
            elif str(source_id) in archive.device_tiles:
                enemy.position = archive.device_tiles[str(source_id)]
                enemy.position_status = "BLOCK_EVENT"
    elif event_type == "UNBLOCK":
        enemy = state.enemies.get(str(target_id))
        if enemy:
            enemy.metadata.pop("blocked_by", None)
            enemy.position = None
            enemy.position_status = "UNKNOWN"
    elif event_type == "DP_CHANGE":
        after = details.get("after")
        state.dp = float(after) if isinstance(after, (int, float)) else None
    elif event_type == "ENEMY_DEATH":
        enemy = state.enemies.get(str(target_id))
        if enemy:
            enemy.active = False
            enemy.position = None
        state.enemies.pop(str(target_id), None)
        state.kills += 1
    elif event_type == "ENEMY_LEAK":
        enemy = state.enemies.pop(str(target_id), None)
        if enemy:
            enemy.active = False
        state.leaks += 1
    elif event_type == "PROTECTED_TARGET_REACHED":
        enemy = state.enemies.pop(str(target_id), None)
        if enemy:
            enemy.active = False
        state.protected_reached += 1
    elif event_type == "DEVICE_DESTROYED":
        state.devices_destroyed += 1
    elif event_type == "TARGET_SELECTION":
        state.last_target_selection[str(source_id)] = {
            "target": target_id,
            "candidates": details.get("candidate_ids", []),
            "rule": details.get("rule", "UNKNOWN"),
        }
    elif event_type == "ENEMY_ABILITY_START":
        ability = str(details.get("ability", "UNKNOWN"))
        state.casts.append(
            Cast(
                source_id=str(source_id),
                ability=ability,
                target_id=str(target_id) if target_id else None,
                target_position=runtime_col_row(details.get("target_position")),
                radius=float(details["radius"]) if isinstance(details.get("radius"), (int, float)) else None,
                start_frame=record.frame,
                windup_seconds=float(details["windup_seconds"]) if isinstance(details.get("windup_seconds"), (int, float)) else None,
            )
        )
    elif event_type == "PROJECTILE_BORN":
        position = runtime_col_row(details.get("locked_position"))
        locked = position is not None
        ability = next((item.ability for item in reversed(state.casts) if item.source_id == source_id), None)
        if ability:
            state.casts = [item for item in state.casts if not (item.source_id == source_id and item.ability == ability)]
        state.projectiles.append(
            Projectile(
                projectile_id=len(state.projectiles) + 1,
                source_id=str(source_id),
                target_id=str(target_id) if target_id else None,
                position=position,
                radius=float(details["radius"]) if isinstance(details.get("radius"), (int, float)) else None,
                born_frame=record.frame,
                born_time=record.time,
                hit_time=record.time + float(details["delay"]) if isinstance(details.get("delay"), (int, float)) else None,
                locked=locked,
                ability=ability,
            )
        )
    elif event_type in {"ENEMY_ABILITY_CANCELLED"}:
        reason = details.get("reason", "UNKNOWN")
        cancel_ability = str(details.get("ability", "UNKNOWN"))
        state.casts = [
            item
            for item in state.casts
            if not (item.source_id == source_id and (item.ability == cancel_ability or cancel_ability == "UNKNOWN"))
        ]
        if reason in {"TARGET_UNAVAILABLE_BEFORE_PROJECTILE_CREATION", "SOURCE_UNAVAILABLE"}:
            pass
    elif event_type == "ENEMY_ABILITY_HIT":
        locked_position = runtime_col_row(details.get("locked_position"))
        amount = details.get("amount")
        unit = state.operators.get(str(target_id)) or state.enemies.get(str(target_id))
        if unit and isinstance(amount, (int, float)):
            unit.hp = (unit.hp if unit.hp is not None else 0.0) - float(amount)
        if unit:
            state.recent_hit[str(target_id)] = record.frame
        if locked_position:
            matches = [
                item
                for item in state.projectiles
                if item.source_id == source_id and item.locked and item.position == locked_position
            ]
            if matches:
                state.projectiles.remove(matches[0])
        state.casts = [item for item in state.casts if item.source_id != source_id]
    elif event_type == "PROJECTILE_HIT":
        matches = [item for item in state.projectiles if item.source_id == source_id and item.target_id == target_id]
        if matches:
            state.projectiles.remove(matches[0])
    return


def build_state_to_frame(archive: Archive, frame: int | None = None, event_limit: int | None = None) -> ReplayState:
    state = initial_state(archive)
    for record in archive.events:
        if frame is not None and record.frame > frame:
            break
        if event_limit is not None and record.index > event_limit:
            break
        apply_event(archive, state, record)
    return state


def format_number(value: Any, digits: int = 1) -> str:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return f"{float(value):.{digits}f}"
    return "?"


def compact_event(record: EventRecord) -> str:
    event = record.data
    details = event.get("details", {}) if isinstance(event.get("details"), dict) else {}
    fields = []
    for key in ("tile", "ability", "amount", "kind", "locked_position", "target_position", "radius", "delay", "reason", "skill", "rule"):
        if key in details:
            fields.append(f"{key}={details[key]}")
    if event.get("legal") is False:
        fields.append("legal=false")
    source = event.get("source_id") or "-"
    target = event.get("target_id") or "-"
    suffix = " " + " ".join(fields) if fields else ""
    return f"[{record.frame:05d} {record.time:8.3f}s] {event.get('event_type', 'UNKNOWN')} {source} -> {target}{suffix}"


def euclidean(a: tuple[int, int], b: tuple[int, int]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def is_key_event(record: EventRecord) -> bool:
    event_type = str(record.data.get("event_type"))
    if event_type not in KEY_EVENT_TYPES:
        return False
    if event_type == "PROJECTILE_BORN":
        details = record.data.get("details", {}) if isinstance(record.data.get("details"), dict) else {}
        return "locked_position" in details
    return True


def key_events(archive: Archive) -> list[EventRecord]:
    return [record for record in archive.events if is_key_event(record)]


def artillery_records(archive: Archive) -> list[EventRecord]:
    result = []
    for record in archive.events:
        if str(record.data.get("event_type")) not in {"ENEMY_ABILITY_START", "PROJECTILE_BORN", "ENEMY_ABILITY_HIT"}:
            continue
        details = record.data.get("details", {}) if isinstance(record.data.get("details"), dict) else {}
        ability = str(details.get("ability", ""))
        if "artillery" in ability.lower() or "emppnt" in str(record.data.get("source_id", "")).lower():
            result.append(record)
    return result


def unit_panel(archive: Archive, state: ReplayState, selected_id: str | None) -> list[str]:
    if not selected_id:
        return ["选中: 无（Tab 切换，/ 过滤）"]
    unit = state.operators.get(selected_id) or state.enemies.get(selected_id)
    if not unit:
        return [f"选中: {selected_id}", "状态: 未激活或未生成"]
    target = state.last_target_selection.get(selected_id, {})
    lines = [
        f"选中: {unit.name} ({unit.unit_id})",
        f"类型: {unit.kind}  状态: {'激活' if unit.active else '未激活'}",
        f"位置: {unit.position if unit.position else '?'}  依据: {unit.position_status}",
        f"HP: {format_number(unit.hp)} / {format_number(unit.max_hp)}",
    ]
    if unit.kind == "ENEMY":
        key = key_enemy_kind(unit)
        marker = {"ARTILLERY": "炮兵", "KEY_34": "#34"}.get(key or "", "")
        lines.append(f"地图标记: {unit.metadata.get('marker', '?')}" + (f"（{marker}）" if marker else ""))
        lines.append(f"路线: {unit.metadata.get('route_id', '?')}  阻挡: {unit.metadata.get('blocked_by', '?')}")
    else:
        lines.append(f"职业/星: {unit.metadata.get('profession', '?')} / {unit.metadata.get('rarity', '?')}")
        lines.append(f"索敌: {target.get('target') or '?'}  规则: {target.get('rule', '?')}")
        lines.append("索敌不是攻击承诺；锁定见弹体面板。")
    return lines


def projectile_lines(state: ReplayState) -> list[str]:
    if not state.projectiles and not state.casts:
        return ["在途弹体/锁定: 无"]
    lines = []
    for cast in state.casts:
        position = cast.target_position or "?"
        eta = "?" if cast.windup_seconds is None else f"{cast.windup_seconds:.3f}s(前摇)"
        lines.append(f"CASTING {cast.source_id} {cast.ability} point={position} {eta}")
    for projectile in state.projectiles:
        mode = "LOCKED_POINT" if projectile.locked else "TRACKING"
        position = projectile.position or "?"
        eta = "?" if projectile.hit_time is None else f"{max(0.0, projectile.hit_time - (state.time or projectile.born_time)):.3f}s"
        lines.append(f"P{projectile.projectile_id:02d} {mode} {projectile.source_id}->{projectile.target_id or '?'} point={position} r={format_number(projectile.radius)} hit={eta}")
    risks = operators_in_risk(state)
    if risks:
        lines.append("IN_FLIGHT_RISK " + " ".join(f"{unit_id}@{position}" for unit_id, _, position in risks))
    return lines


def operators_in_risk(state: ReplayState) -> list[tuple[str, str, tuple[int, int] | None]]:
    result: list[tuple[str, str, tuple[int, int] | None]] = []
    for projectile in state.projectiles:
        if not projectile.locked or projectile.position is None or projectile.radius is None:
            continue
        for unit in state.operators.values():
            if not unit.active or unit.position is None:
                continue
            if euclidean(unit.position, projectile.position) <= projectile.radius:
                result.append((unit.unit_id, f"P{projectile.projectile_id:02d}", unit.position))
    return result
def status_panel(archive: Archive, state: ReplayState) -> list[str]:
    final = archive.final_status or {}
    display_frame = state.display_frame if state.display_frame is not None else max(0, state.frame)
    next_record = archive.events[state.event_index + 1] if state.event_index + 1 < len(archive.events) else None
    next_text = ""
    if next_record is not None and state.display_frame is not None:
        remaining = max(0, next_record.frame - state.display_frame)
        next_text = f"  下一事件 f{next_record.frame}({remaining / FRAME_RATE:.1f}s)"
    return [
        f"帧: {display_frame}  时间: {format_number(state.time, 3)}s  事件: {state.event_index + 1}/{len(archive.events)}{next_text}",
        f"生命: {format_number(state.life, 0)}  DP: {format_number(state.dp)}  击杀: {state.kills}  漏怪: {state.leaks}",
        f"保护到达: {state.protected_reached}  干员死亡: {state.operator_deaths}  装置破坏: {state.devices_destroyed}",
        f"归档终局: {final.get('result_classification', 'UNKNOWN')}  击杀: {final.get('enemies_killed', '?')}  漏怪: {final.get('enemies_leaked', '?')}",
    ]


def render_grid(archive: Archive, state: ReplayState, selected_id: str | None, ascii_mode: bool = False) -> list[str]:
    if archive.map_cols is None or archive.map_rows is None:
        return ["地图: ?（缺少 map facts）"]
    terrain: dict[tuple[int, int], str] = {}
    for position in archive.route_cells.values():
        for cell in position:
            terrain[cell] = "."
    for cell in archive.ground:
        terrain[cell] = "+"
    for cell in archive.high_ground:
        terrain[cell] = "^"
    for cell in archive.device_tiles.values():
        terrain[cell] = "#"
    grids: dict[tuple[int, int], str] = {}
    operator_cells: dict[tuple[int, int], str] = {}
    enemy_cells: dict[tuple[int, int], str] = {}
    priority: dict[tuple[int, int], int] = {}

    def put(position: tuple[int, int], char: str, rank: int) -> None:
        if rank >= priority.get(position, -1):
            grids[position] = char
            priority[position] = rank

    for cast in state.casts:
        if cast.target_position:
            put(cast.target_position, "?" if not ascii_mode else "?", 4)
    risk_ids = {item[0] for item in operators_in_risk(state)}
    for projectile in state.projectiles:
        if projectile.position:
            put(projectile.position, "X" if projectile.locked else "o", 6)
        if projectile.position and projectile.radius is not None and projectile.locked:
            col, row = projectile.position
            radius_int = math.floor(projectile.radius)
            for dy in range(-radius_int - 1, radius_int + 2):
                for dx in range(-radius_int - 1, radius_int + 2):
                    cell = (col + dx, row + dy)
                    if 0 <= dx and 0 <= dy and euclidean(cell, projectile.position) <= projectile.radius:
                        put(cell, "*", 3)
    enemies_by_position: dict[tuple[int, int], list[Unit]] = {}
    for unit in state.enemies.values():
        if not unit.active or unit.position is None:
            continue
        enemies_by_position.setdefault(unit.position, []).append(unit)
    for position, enemies in enemies_by_position.items():
        key_kind = next((kind for kind in (key_enemy_kind(unit) for unit in enemies) if kind), None)
        prefix = {"ARTILLERY": "A", "KEY_34": "K"}.get(key_kind or "", "E")
        count = min(len(enemies), 9) if len(enemies) < 10 else 0
        enemy_cells[position] = f"{prefix}{count if count else '+'}"
    for unit in state.operators.values():
        if not unit.active or unit.position is None:
            continue
        operator_cells[unit.position] = str(unit.metadata.get("marker", "O"))
    for unit in list(state.operators.values()) + list(state.enemies.values()):
        if not unit.active or unit.position is None:
            continue
        if state.recent_hit.get(unit.unit_id, -99) >= state.frame - 6:
            put(unit.position, "!!", 9)
        elif unit.unit_id in risk_ids:
            put(unit.position, "R·", 8)
        elif selected_id and unit.unit_id == selected_id:
            put(unit.position, "@·", 8)
    header = "col " + "".join(f"{col:02d}  " for col in range(archive.map_cols))
    lines = [header]
    lines.append("图例: 干员=首字母+序号 E普通 A炮兵 K#34 R风险 !实际受击 数字=已知怪数")
    for row in range(archive.map_rows):
        cells = []
        for col in range(archive.map_cols):
            position = (col, row)
            if position in grids:
                cell = grids[position]
            else:
                left = operator_cells.get(position, "··")
                right = enemy_cells.get(position, "··")
                cell = f"{left}{right}"
            cells.append(f"{cell:<{GRID_CELL_WIDTH}}")
        lines.append(f"r{row:1d}  " + "".join(cells))
    return lines


def filtered_event_indices(archive: Archive, filter_id: str | None, full_mode: bool) -> list[int]:
    selected = []
    for record in archive.events:
        event_type = str(record.data.get("event_type"))
        if not full_mode and event_type not in KEY_EVENT_TYPES:
            continue
        details = record.data.get("details", {}) if isinstance(record.data.get("details"), dict) else {}
        if not full_mode and event_type == "PROJECTILE_BORN" and "locked_position" not in details:
            continue
        if filter_id and filter_id not in {str(record.data.get("source_id")), str(record.data.get("target_id"))}:
            continue
        selected.append(record.index)
    return selected


def render_lines(
    archive: Archive,
    state: ReplayState,
    *,
    selected_id: str | None = None,
    filter_id: str | None = None,
    full_events: bool = False,
    ascii_mode: bool = False,
    width: int = 110,
    height: int = 28,
    event_offset: int = 0,
) -> list[str]:
    lines = [f"KimiArk Tactical Battle Replay V1  {archive.events_path.name}"]
    lines.extend(status_panel(archive, state))
    grid = render_grid(archive, state, selected_id, ascii_mode)
    lines.append("-- MAP --")
    lines.extend(grid)
    lines.append("-- LOCK / PROJECTILE --")
    lines.extend(projectile_lines(state))
    lines.extend(unit_panel(archive, state, selected_id))
    if filter_id:
        lines.append(f"过滤: {filter_id}")
    indices = filtered_event_indices(archive, filter_id, full_events)
    if indices:
        current_pos = next((pos for pos, index in enumerate(indices) if index > state.event_index), len(indices))
        start = max(0, min(event_offset, len(indices) - 1))
        end = min(len(indices), max(start + max(3, height - len(lines) - 3), start + 1))
        if event_offset == 0:
            end = min(len(indices), max(3, height - len(lines) - 3))
        start = max(0, min(event_offset, len(indices) - 1))
        end = min(len(indices), start + max(3, height - len(lines) - 3))
        if indices and 0 <= current_pos < len(indices):
            end = min(len(indices), max(start + 3, current_pos + 3))
        for index in indices[start:end]:
            lines.append(compact_event(archive.events[index]))
        lines.append(f"事件流: {start + 1}-{end}/{len(indices)}  h=帮助 f=过滤 F=完整/关键 n=下一事件 N=下一关键事件")
    else:
        lines.append("事件流: 无匹配事件")
    return [line if len(line) <= width else line[:width] for line in lines[:height]]


def dump_frame(archive: Archive, frame: int) -> None:
    state = build_state_to_frame(archive, frame=frame)
    for line in render_lines(archive, state, height=1000, width=10000):
        print(line)


def print_timeline(archive: Archive, maximum: int | None) -> None:
    for record in key_events(archive):
        if maximum is not None and record.index >= maximum:
            break
        print(compact_event(record))


def init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    pairs = [
        (1, curses.COLOR_CYAN, -1),
        (2, curses.COLOR_GREEN, -1),
        (3, curses.COLOR_YELLOW, -1),
        (4, curses.COLOR_RED, -1),
        (5, curses.COLOR_MAGENTA, -1),
        (6, curses.COLOR_BLUE, -1),
        (7, curses.COLOR_WHITE, -1),
        (8, curses.COLOR_BLACK, curses.COLOR_YELLOW),
    ]
    for index, foreground, background in pairs:
        curses.init_pair(index, foreground, background)


def add_line(screen: Any, row: int, text: str, color: int = 0, highlight: bool = False) -> None:
    height, width = screen.getmaxyx()
    if row >= height:
        return
    screen.move(row, 0)
    screen.clrtoeol()
    value = text[: max(0, width - 1)]
    attrs = curses.color_pair(color) | (curses.A_REVERSE if highlight else 0)
    try:
        screen.addstr(row, 0, value, attrs)
    except curses.error:
        pass


def prompt(screen: Any, title: str) -> str:
    height, width = screen.getmaxyx()
    add_line(screen, height - 1, f"{title}（Enter确认，空取消）", 1)
    curses.echo()
    try:
        value = screen.getstr(height - 1, len(title) + 14, 80).decode("utf-8", "replace").strip()
    finally:
        curses.noecho()
    return value


def draw_ui(screen: Any, archive: Archive, state: ReplayState, ui: dict[str, Any]) -> None:
    lines = render_lines(
        archive,
        state,
        selected_id=ui.get("selected_id"),
        filter_id=ui.get("filter_id"),
        full_events=ui.get("full_events", False),
        ascii_mode=ui.get("ascii_mode", False),
        event_offset=int(ui.get("event_offset", 0)),
    )
    if ui.get("show_help"):
        lines.extend(
            [
                "帮助: 空格暂停 n下一事件 N下一关键 s回退 +/-速度 g跳帧 0开头 Tab选中",
                "图例: ?施法点 X固定落点 *风险范围 R风险干员 o跟踪弹 !实际受击",
                "单位: O干员 E已知敌人 @选中 #路障/装置 +地面 ^高台 .路线",
            ]
        )
    screen.erase()
    for row, line in enumerate(lines):
        color = 1
        if line.startswith("--"):
            color = 6
        elif "LOCKED_POINT" in line:
            color = 4
        elif "CASTING" in line:
            color = 5
        elif line.startswith(("DAMAGE", "HEAL", "ENEMY_ABILITY_HIT")):
            color = 3
        add_line(screen, row, line, color)
    mode = "低动画" if ui.get("low_motion") else "动画"
    playback = "暂停" if ui.get("paused") else "播放"
    speed = float(ui.get("speed", DEFAULT_SPEED))
    add_line(screen, 0, f"KimiArk Replay V1  {playback} 速度:{speed:g}x {mode} n单帧 N关键 s回退", 7, highlight=True)
    screen.refresh()


def apply_until_event(archive: Archive, state: ReplayState, start_index: int, *, key_only: bool = False, backwards: bool = False) -> None:
    if backwards:
        if start_index <= 0:
            state.frame = -1
            state.time = None
            state.event_index = -1
            return
        target = start_index - 1
        while target >= 0 and key_only and not is_key_event(archive.events[target]):
            target -= 1
        replacement = build_state_to_event(archive, target)
        copy_state(replacement, state)
        return
    index = start_index
    while index < len(archive.events):
        record = archive.events[index]
        if key_only and not is_key_event(record):
            index += 1
            continue
        apply_event(archive, state, record)
        return


def build_state_to_event(archive: Archive, event_index: int) -> ReplayState:
    state = initial_state(archive)
    for record in archive.events[: event_index + 1]:
        apply_event(archive, state, record)
    return state


def copy_state(source: ReplayState, target: ReplayState) -> None:
    for key, value in source.__dict__.items():
        if isinstance(value, list):
            setattr(target, key, list(value))
        elif isinstance(value, dict):
            setattr(target, key, dict(value))
        else:
            setattr(target, key, value)


def run_curses(screen: Any, archive: Archive, jump_frame: int | None, ascii_mode: bool, low_motion: bool, color_enabled: bool = True) -> None:
    ui_color_enabled = color_enabled
    curses.curs_set(0)
    screen.nodelay(True)
    screen.keypad(True)
    has_color = curses.has_colors() and not ascii_mode and ui_color_enabled
    if has_color:
        init_colors()
    state = build_state_to_frame(archive, 0 if jump_frame is None else jump_frame)
    ui: dict[str, Any] = {
        "paused": True,
        "speed": DEFAULT_SPEED,
        "low_motion": low_motion,
        "ascii_mode": ascii_mode,
        "full_events": False,
        "filter_id": None,
        "selected_id": None,
        "event_offset": 0,
    }
    artillery_indices = [record.index for record in artillery_records(archive)]
    last_tick = time.monotonic()
    final_frame = archive.events[-1].frame if archive.events else 0
    clock_frame = 0.0
    while True:
        state.display_frame = int(clock_frame)
        draw_ui(screen, archive, state, ui)
        try:
            key = screen.getch()
        except curses.error:
            key = -1
        if key in (ord("q"), 27):
            return
        elif key in (ord(" "), curses.KEY_HOME):
            ui["paused"] = not ui["paused"]
            if key == curses.KEY_HOME:
                state = build_state_to_frame(archive, 0)
                clock_frame = float(state.frame)
        elif key in (ord("+"), curses.KEY_RIGHT):
            ui["speed"] = min(4.0, ui["speed"] * 2.0)
        elif key in (ord("-"), curses.KEY_LEFT):
            ui["speed"] = max(0.25, ui["speed"] / 2.0)
        elif key in (ord("n"), curses.KEY_DOWN):
            apply_until_event(archive, state, state.event_index + 1, key_only=False)
            ui["paused"] = True
            clock_frame = float(state.frame)
        elif key == ord("N"):
            apply_until_event(archive, state, state.event_index + 1, key_only=True)
            ui["paused"] = True
            clock_frame = float(state.frame)
        elif key == ord("s"):
            apply_until_event(archive, state, state.event_index + 1, key_only=True, backwards=True)
            ui["paused"] = True
            clock_frame = float(state.frame)
        elif key == ord("g"):
            value = prompt(screen, "跳转帧")
            try:
                state = build_state_to_frame(archive, int(value))
                clock_frame = float(state.frame)
            except ValueError:
                pass
        elif key == ord("/"):
            value = prompt(screen, "过滤单位ID")
            ui["filter_id"] = value or None
            ui["selected_id"] = ui["filter_id"]
        elif key == ord("c"):
            ui["filter_id"] = None
        elif key == ord("0"):
            state = build_state_to_frame(archive, 0)
            clock_frame = float(state.frame)
        elif key in (9, curses.KEY_STAB):
            candidates = [unit.unit_id for unit in state.operators.values() if unit.active]
            candidates += [unit.unit_id for unit in state.enemies.values() if unit.active]
            if candidates:
                current = ui.get("selected_id")
                ui["selected_id"] = candidates[(candidates.index(current) + 1) % len(candidates)] if current in candidates else candidates[0]
        elif key == ord("f"):
            ui["full_events"] = not ui["full_events"]
        elif key == ord("h"):
            ui["show_help"] = not ui.get("show_help", False)
        elif key == ord("l"):
            ui["low_motion"] = not ui["low_motion"]
        elif key == ord("k"):
            target = next(
                (
                    record.index
                    for record in archive.events
                    if record.index > state.event_index
                    and record.data.get("event_type") == "ENEMY_DEATH"
                    and "emppnt" in str(record.data.get("target_id", ""))
                ),
                None,
            )
            if target is not None:
                state = build_state_to_event(archive, target)
                clock_frame = float(state.frame)
        elif key == ord("a"):
            ui["ascii_mode"] = not ui["ascii_mode"]
        elif key == ord("1"):
            first_death = next((record.index for record in archive.events if record.data.get("event_type") == "OPERATOR_DEATH"), None)
            if first_death is not None:
                state = build_state_to_event(archive, first_death)
                clock_frame = float(state.frame)
        elif key == ord("2"):
            first_leak = next((record.index for record in archive.events if record.data.get("event_type") == "ENEMY_LEAK"), None)
            if first_leak is not None:
                state = build_state_to_event(archive, first_leak)
                clock_frame = float(state.frame)
        elif key == ord("3"):
            target = next((index for index in artillery_indices if index > state.event_index), None)
            if target is not None:
                state = build_state_to_event(archive, target)
                clock_frame = float(state.frame)
        elif key == ord("4"):
            target = next(
                (
                    record.index
                    for record in archive.events
                    if record.index > state.event_index and record.data.get("event_type") in {"PROTECTED_TARGET_REACHED", "DEVICE_DESTROYED"}
                ),
                None,
            )
            if target is not None:
                state = build_state_to_event(archive, target)
                clock_frame = float(state.frame)
        elif key == ord("5") and ui.get("selected_id"):
            unit_id = ui["selected_id"]
            target = next(
                (
                    record.index
                    for record in archive.events
                    if record.index > state.event_index
                    and unit_id in {record.data.get("source_id"), record.data.get("target_id")}
                    and record.data.get("event_type") in {"TARGET_SELECTION", "ENEMY_ABILITY_START", "PROJECTILE_BORN", "DAMAGE", "ENEMY_ABILITY_HIT", "HEAL"}
                ),
                None,
            )
            if target is not None:
                state = build_state_to_event(archive, target)
                clock_frame = float(state.frame)

        now = time.monotonic()
        if not ui["paused"]:
            clock_frame += (now - last_tick) * FRAME_RATE * float(ui["speed"])
            clock_frame = min(clock_frame, float(final_frame))
            if ui.get("low_motion"):
                apply_until_event(archive, state, state.event_index + 1, key_only=True)
                ui["paused"] = True
                clock_frame = float(state.frame)
            else:
                target_frame = int(clock_frame)
                while state.event_index + 1 < len(archive.events) and archive.events[state.event_index + 1].frame <= target_frame:
                    apply_event(archive, state, archive.events[state.event_index + 1])
                if clock_frame >= final_frame:
                    ui["paused"] = True
        last_tick = now
        time.sleep(0.02)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only KimiArk diagnostic event replay")
    parser.add_argument("replay", type=Path, help="diagnostic_events.json[.gz] or its diagnostic directory")
    parser.add_argument("--facts", type=Path, help="llm_evidence_context.json[.gz]; auto-discovered when unambiguous")
    parser.add_argument("--dump-frame", type=int, help="print one replay state and exit")
    parser.add_argument("--timeline", action="store_true", help="print compact key-event timeline and exit")
    parser.add_argument("--max-events", type=int, help="limit --timeline output")
    parser.add_argument("--jump-frame", type=int, help="initial TTY frame")
    parser.add_argument("--no-color", action="store_true", help="disable colors")
    parser.add_argument("--ascii", action="store_true", help="prefer ASCII and disable color")
    parser.add_argument("--low-motion", action="store_true", help="one event per key/tick mode")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    archive = load_archive(args.replay, args.facts)
    if args.dump_frame is not None:
        dump_frame(archive, args.dump_frame)
        return 0
    if args.timeline:
        print_timeline(archive, args.max_events)
        return 0
    if args.no_color or args.ascii:
        pass
    if not sys.stdout.isatty():
        print("TTY required for interactive replay. Use --dump-frame FRAME or --timeline.", file=sys.stderr)
        return 2
    try:
        curses.wrapper(
            run_curses,
            archive,
            args.jump_frame,
            args.ascii,
            args.low_motion,
            not args.no_color,
        )
    except curses.error as error:
        print(f"terminal replay failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
