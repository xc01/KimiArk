from __future__ import annotations

from dataclasses import dataclass

from .provenance import ValueWithSource, unknown


@dataclass(frozen=True)
class RangeCell:
    """A range-table grid offset exactly as stored (row/col, not x/y)."""

    row: int
    col: int
    row_provenance: ValueWithSource[int | None] = unknown()
    col_provenance: ValueWithSource[int | None] = unknown()


@dataclass(frozen=True)
class AttackRange:
    range_id: str
    direction: ValueWithSource[int | None]
    cells: tuple[RangeCell, ...]
    raw_source_file: str


@dataclass(frozen=True)
class BlackboardParameter:
    """A raw skill blackboard entry with individual source locations."""

    key: ValueWithSource[str | None]
    value: ValueWithSource[float | int | str | None]


@dataclass(frozen=True)
class SkillLevel:
    level_index: int
    name: ValueWithSource[str | None]
    range_id: ValueWithSource[str | None]
    skill_type: ValueWithSource[str | None]
    duration_type: ValueWithSource[str | None]
    sp_type: ValueWithSource[str | None]
    sp_cost: ValueWithSource[float | int | None]
    initial_sp: ValueWithSource[float | int | None]
    max_charge_time: ValueWithSource[int | None]
    duration: ValueWithSource[float | None]
    blackboard: tuple[tuple[str, float | int | str | None], ...]
    blackboard_parameters: tuple[BlackboardParameter, ...] = ()


@dataclass(frozen=True)
class Skill:
    skill_id: str
    hidden: ValueWithSource[bool | None]
    levels: tuple[SkillLevel, ...]
    raw_source_file: str
