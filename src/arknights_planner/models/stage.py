from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from .provenance import KnowledgeStatus, ValueWithSource, unknown

if TYPE_CHECKING:
    from .route import Route


@dataclass(frozen=True)
class Tile:
    x: int
    y: int
    buildable: bool
    tile_kind: str = "GROUND"  # Synthetic categories: GROUND, HIGH_GROUND, NON_DEPLOYABLE.


@dataclass(frozen=True)
class StageCoordinate:
    """A level-file coordinate retained as row/col, without x/y reinterpretation."""

    row: ValueWithSource[int | None]
    col: ValueWithSource[int | None]


@dataclass(frozen=True)
class StageTileRecord:
    tile_index: int
    tile_key: ValueWithSource[str | None]
    height_type: ValueWithSource[str | None]
    buildable_type: ValueWithSource[str | None]
    passable_mask: ValueWithSource[str | None]
    player_side_mask: ValueWithSource[str | None]


@dataclass(frozen=True)
class StageRouteData:
    route_index: int
    start_position: StageCoordinate | None
    end_position: StageCoordinate | None
    checkpoints: tuple["StageRouteCheckpointData", ...]
    raw_source_file: str


@dataclass(frozen=True)
class StageRouteCheckpointData:
    """Route checkpoint kept structurally; its type is not discarded."""

    checkpoint_type: ValueWithSource[str | None]
    time: ValueWithSource[float | int | None]
    position: StageCoordinate | None


@dataclass(frozen=True)
class StageActionData:
    action_index: int
    action_type: ValueWithSource[str | None]
    key: ValueWithSource[str | None]
    count: ValueWithSource[int | None]
    pre_delay: ValueWithSource[float | int | None]
    interval: ValueWithSource[float | int | None]
    route_index: ValueWithSource[int | None]


@dataclass(frozen=True)
class StageFragmentData:
    fragment_index: int
    pre_delay: ValueWithSource[float | int | None]
    actions: tuple[StageActionData, ...]


@dataclass(frozen=True)
class StageWaveData:
    wave_index: int
    pre_delay: ValueWithSource[float | int | None]
    post_delay: ValueWithSource[float | int | None]
    fragments: tuple[StageFragmentData, ...]


@dataclass(frozen=True)
class StageLevelStructure:
    """Level hierarchy preserved without interpreting delay accumulation."""

    map_indices: tuple[tuple[int, ...], ...]
    tile_records: tuple[StageTileRecord, ...]
    routes: tuple[StageRouteData, ...]
    waves: tuple[StageWaveData, ...]
    raw_source_file: str


@dataclass(frozen=True)
class StageMap:
    width: int
    height: int
    tiles: tuple[Tile, ...]

    def tile_at(self, coordinate: tuple[int, int]) -> Tile | None:
        return next((tile for tile in self.tiles if (tile.x, tile.y) == coordinate), None)


@dataclass(frozen=True)
class SpawnEvent:
    time: float
    enemy_id: str
    route_id: str
    count: int = 1
    interval: float = 0.0


@dataclass(frozen=True)
class BattleDevice:
    """A source-backed predeployed battle device executable by the runtime."""

    device_id: str
    template_id: str
    tile: tuple[int, int]
    hp: float
    defense: float
    magic_resistance: float
    taunt_level: int = 0
    ordinary_targetable: bool = False
    faction: str = "ENEMY"


@dataclass(frozen=True)
class Stage:
    stage_id: str
    code: ValueWithSource[str | None]
    name: ValueWithSource[str | None]
    map_width: ValueWithSource[int | None]
    map_height: ValueWithSource[int | None]
    route_count: ValueWithSource[int | None]
    wave_count: ValueWithSource[int | None]
    raw_source_file: str | None
    level_id: ValueWithSource[str | None] = unknown()
    enemy_references: tuple[tuple[str, int], ...] = ()
    spawn_action_count: ValueWithSource[int | None] = unknown()
    initial_dp: ValueWithSource[int | None] = unknown()
    deployment_limit: ValueWithSource[int | None] = unknown()
    squad_size_limit: ValueWithSource[int | None] = unknown()
    stage_map: StageMap | None = None
    routes: tuple["Route", ...] = ()
    spawn_events: tuple[SpawnEvent, ...] = ()
    initial_life: int = 0
    dp_per_second: float = 1.0
    level_structure: StageLevelStructure | None = None
    max_life_points: ValueWithSource[int | None] = unknown()
    cost_increase_time: ValueWithSource[float | int | None] = unknown()
    devices: tuple[BattleDevice, ...] = ()


@dataclass(frozen=True)
class ReconstructionField:
    field: str
    status: KnowledgeStatus
    source: str | None = None


@dataclass(frozen=True)
class StageReconstructionReport:
    stage_id: str
    fields: tuple[ReconstructionField, ...]

    @classmethod
    def unknown(cls, stage_id: str) -> "StageReconstructionReport":
        names = ("Map", "Enemy roster", "Enemy routes", "Spawn timeline", "Projectile speed", "Attack windup", "Damage frame", "Event ordering")
        return cls(stage_id, tuple(ReconstructionField(name, KnowledgeStatus.UNKNOWN) for name in names))
