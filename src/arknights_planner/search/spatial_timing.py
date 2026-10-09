"""Tactical spatial and event-relative timing generation for top-down planning."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from fractions import Fraction
from statistics import mean
from time import perf_counter
from typing import Any, Iterable

from arknights_planner.models.frame import FrameClock
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.models.timeline import FrameTimeline
from arknights_planner.agent.tactical import PlanHypothesis
from arknights_planner.search.m11 import (
    M11Evaluation,
    M11MinimumSquadSearch,
    M11SearchMetrics,
    M11SearchStop,
)
from arknights_planner.search.stage_understanding import StageUnderstanding
from arknights_planner.simulator import ApproximateRealRangeTransformer
from arknights_planner.timing import strategy_to_timeline


@dataclass(frozen=True)
class TacticalRegion:
    region_id: str
    region_type: str
    tile_kind: str
    tiles: tuple[tuple[int, int], ...]
    route_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    pressure_window_ids: tuple[str, ...]
    intended_roles: tuple[str, ...]
    rationale: str
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TileCandidate:
    operator_id: str
    tile: tuple[int, int]
    direction: str
    region_id: str
    region_type: str
    intended_role: str
    covered_route_ids: tuple[str, ...]
    covered_cells: tuple[tuple[int, int], ...]
    block_route_ids: tuple[str, ...]
    support_target_tiles: tuple[tuple[int, int], ...]
    first_contact_seconds: float | None
    features: dict[str, float]
    pareto_rank: int
    rationale: str

    @property
    def semantic_key(self) -> tuple[Any, ...]:
        return (
            self.operator_id,
            self.tile,
            self.region_type,
            self.intended_role,
            self.covered_route_ids,
            self.block_route_ids,
            self.direction,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpatialPlacement:
    candidate: TileCandidate
    relations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"candidate": self.candidate.to_dict(), "relations": self.relations}


@dataclass(frozen=True)
class SpatialSkeleton:
    skeleton_id: str
    hypothesis_id: str
    hypothesis_archetype: str
    placements: tuple[SpatialPlacement, ...]
    semantic_fingerprint: str
    region_signature: tuple[str, ...]
    feature_summary: dict[str, float]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TimingAnchor:
    operator_id: str
    event_type: str
    event_seconds: float
    anchor_frame: int
    offset_frames: int
    desired_frame: int
    earliest_frame: int
    final_frame: int
    clamped_by_dp: bool
    ordering_constraint_applied: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkillTimingAnchor:
    operator_id: str
    skill_id: str
    event_type: str
    event_seconds: float
    anchor_frame: int
    offset_frames: int
    desired_frame: int
    earliest_frame: int
    final_frame: int
    clamped_by_readiness: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TimingCandidate:
    timing_id: str
    skeleton_id: str
    hypothesis_id: str
    pattern_id: str
    deploy_frames: tuple[int, ...]
    anchors: tuple[TimingAnchor, ...]
    actions: tuple[Action, ...]
    strategy: Strategy
    semantic_fingerprint: str
    dp_feasible: bool
    rejection_reasons: tuple[str, ...]
    skill_anchors: tuple[SkillTimingAnchor, ...] = ()
    source: str = "COARSE_EVENT_RELATIVE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timing_id": self.timing_id,
            "skeleton_id": self.skeleton_id,
            "hypothesis_id": self.hypothesis_id,
            "pattern_id": self.pattern_id,
            "deploy_frames": self.deploy_frames,
            "anchors": [item.to_dict() for item in self.anchors],
            "skill_anchors": [item.to_dict() for item in self.skill_anchors],
            "semantic_fingerprint": self.semantic_fingerprint,
            "dp_feasible": self.dp_feasible,
            "rejection_reasons": self.rejection_reasons,
            "source": self.source,
        }


@dataclass(frozen=True)
class SpatialTimingConfig:
    frame_clock: FrameClock = FrameClock.configured(30, provenance="top-down spatial timing")
    skeleton_beam_width: int = 8
    max_skeletons_per_hypothesis: int = 3
    tile_candidates_per_operator: int = 12
    facings_per_tile: int = 2
    max_candidates_per_tile: int = 2
    max_timing_candidates_per_skeleton: int = 6
    max_skill_operators: int = 2
    max_skill_candidates_per_skeleton: int = 4
    refinement_offsets: tuple[int, ...] = (-30, -10, -3, 3, 10, 30)
    max_refinement_fraction: float = 0.20


@dataclass
class SpatialTimingSearchMetrics:
    regions_generated: int = 0
    tile_candidates_generated: int = 0
    tile_candidates_after_pruning: int = 0
    facing_candidates_generated: int = 0
    facing_candidates_after_deduplication: int = 0
    skeletons_generated: int = 0
    skeletons_deduplicated: int = 0
    skeletons_reaching_timing: int = 0
    timing_candidates_generated: int = 0
    timing_candidates_deduplicated: int = 0
    timing_candidates_executable_deduplicated: int = 0
    timing_candidates_dp_rejected: int = 0
    unique_frame_timelines: int = 0
    evaluations_generated: int = 0
    coarse_simulations: int = 0
    refinement_simulations: int = 0
    cache_hits: int = 0
    wall_clock_seconds: float = 0.0


@dataclass
class SpatialTimingSearchResult:
    stage_id: str
    best: M11Evaluation | None
    best_hypothesis_id: str | None
    best_skeleton: SpatialSkeleton | None
    timeline: FrameTimeline | None
    robustness_by_action: tuple[tuple[int, int, int, int], ...]
    stop: M11SearchStop
    metrics: M11SearchMetrics
    spatial_metrics: SpatialTimingSearchMetrics
    attempts: list[dict[str, Any]]
    audit: dict[str, Any]
    timing_refinement_history: list[dict[str, Any]]
    evaluation_records: tuple[dict[str, Any], ...] = ()


@dataclass
class _SkeletonState:
    placements: tuple[SpatialPlacement, ...] = ()
    used_tiles: frozenset[tuple[int, int]] = frozenset()
    feature_summary: dict[str, float] = field(default_factory=dict)


class SpatialTimingSearch:
    """Generate tactical spatial realizations before any simulator call."""

    VERSION = "spatial-timing-recovery-v1"

    def __init__(
        self,
        *,
        engine: M11MinimumSquadSearch,
        understanding: StageUnderstanding,
        config: SpatialTimingConfig | None = None,
    ):
        self.engine = engine
        self.understanding = understanding
        self.config = config or SpatialTimingConfig()
        self.transformer = ApproximateRealRangeTransformer()
        self._route_cells = self._active_route_cells()
        self._route_progress = self._active_route_progress()
        self._exact_routes = {
            route.route_id: route
            for route in self.engine.fixture.stage.routes
        }
        self._expanded_spawns = self._expanded_spawn_rows()
        self._regions = self._build_regions()
        self.last_tile_candidate_audit: dict[str, int] = {}

    def regions(self) -> tuple[TacticalRegion, ...]:
        return self._regions

    def _active_route_cells(self) -> dict[str, set[tuple[int, int]]]:
        return {
            route.route_id: set(route.cells)
            for route in self.understanding.routes
        }

    def _active_route_progress(self) -> dict[tuple[str, tuple[int, int]], float]:
        output: dict[tuple[str, tuple[int, int]], float] = {}
        for route in self.understanding.routes:
            denominator = max(1, len(route.cells) - 1)
            for index, cell in enumerate(route.cells):
                output[(route.route_id, cell)] = index / denominator
        return output

    def _block_routes_at(self, tile: tuple[int, int]) -> set[str]:
        return {
            route_id
            for route_id, route in self._exact_routes.items()
            if route.distance_at(tile) is not None
        }

    def _expanded_spawn_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for spawn in self.engine.fixture.spawn_timeline:
            enemy = self.engine.fixture.enemies[spawn.enemy_id]
            speed = float(enemy.stats.move_speed.value or 0)
            if speed <= 0:
                continue
            for index in range(int(spawn.count)):
                rows.append({
                    "time": float(spawn.time + index * spawn.interval),
                    "route_id": spawn.route_id,
                    "enemy_id": spawn.enemy_id,
                    "speed": speed,
                })
        return sorted(rows, key=lambda item: (item["time"], item["route_id"], item["enemy_id"]))

    def _build_regions(self) -> tuple[TacticalRegion, ...]:
        ground = self.understanding.deployable_ground
        high_ground = self.understanding.deployable_high_ground
        lane_by_route = {
            route.route_id: route.lane_id
            for route in self.understanding.routes
        }
        pressure_windows = self.understanding.pressure_windows
        pressure_ids = tuple(window.window_id for window in pressure_windows)
        regions: list[TacticalRegion] = []

        early_ground = tuple(
            tile for tile in ground
            if any(
                (route_id, tile) in self._route_progress
                and self._route_progress[(route_id, tile)] <= 0.35
                for route_id in self._route_cells
            )
        )
        choke_ground = tuple(
            tile for tile in ground
            if tile in self.understanding.interception_points
        )
        secondary_ground = tuple(
            tile for tile in ground
            if any(
                (route_id, tile) in self._route_progress
                and self._route_progress[(route_id, tile)] > 0.35
                for route_id in self._route_cells
            )
        )
        ground_route_ids = tuple(sorted({
            route_id
            for route_id, cells in self._route_cells.items()
            if any(tile in cells for tile in ground)
        }))
        if early_ground:
            regions.append(TacticalRegion(
                "ground-early-interception", "EARLY_TEMPORARY_INTERCEPTION", "GROUND",
                early_ground, ground_route_ids,
                tuple(sorted({lane_by_route[item] for item in ground_route_ids})), pressure_ids,
                ("EARLY_DEPLOYMENT", "BLOCK", "MELEE_DPS"),
                "Legal ground tiles on the early portion of active routes.",
                "StageUnderstanding.routes and deployable_ground",
            ))
        if choke_ground:
            regions.append(TacticalRegion(
                "ground-choke-hold", "CHOKE_POINT_BLOCK", "GROUND",
                choke_ground, ground_route_ids,
                tuple(sorted({lane_by_route[item] for item in ground_route_ids})), pressure_ids,
                ("BLOCK", "BLOCK_CAPACITY", "MELEE_DPS"),
                "Ranked route-crossing ground interception tiles.",
                "StageUnderstanding.interception_points",
            ))
        if secondary_ground:
            regions.append(TacticalRegion(
                "ground-secondary-hold", "SECONDARY_LANE_HOLD", "GROUND",
                secondary_ground, ground_route_ids,
                tuple(sorted({lane_by_route[item] for item in ground_route_ids})), pressure_ids,
                ("BLOCK", "BLOCK_CAPACITY", "MELEE_DPS"),
                "Legal ground tiles on later active-route cells.",
                "StageUnderstanding.routes and deployable_ground",
            ))

        high_ground_tiles = tuple(
            item.tile for item in self.understanding.coverage_opportunities
            if item.tile_kind == "HIGH_GROUND"
        )
        high_ground_route_ids = tuple(sorted({
            route_id
            for opportunity in self.understanding.coverage_opportunities
            for route_id in opportunity.route_ids
        }))
        if high_ground_tiles:
            regions.append(TacticalRegion(
                "high-ground-ranged-support", "RANGED_SUPPORT_COVERAGE", "HIGH_GROUND",
                tuple(dict.fromkeys(high_ground_tiles)), high_ground_route_ids,
                tuple(sorted({lane_by_route[item] for item in high_ground_route_ids})), pressure_ids,
                ("RANGED_DPS", "ARTS_DAMAGE", "HEAL", "MULTI_LANE_COVERAGE"),
                "Legal high-ground tiles with non-empty active-route coverage.",
                "StageUnderstanding.coverage_opportunities",
            ))
        shared_tiles = tuple(dict.fromkeys(
            item.tile for item in self.understanding.coverage_opportunities
            if item.shared and item.tile_kind == "HIGH_GROUND"
        ))
        if shared_tiles:
            shared_route_ids = tuple(sorted({
                route_id
                for item in self.understanding.coverage_opportunities
                if item.shared and item.tile_kind == "HIGH_GROUND"
                for route_id in item.route_ids
            }))
            regions.append(TacticalRegion(
                "high-ground-shared-coverage", "SHARED_HIGH_GROUND_COVERAGE", "HIGH_GROUND",
                shared_tiles, shared_route_ids,
                tuple(sorted({lane_by_route[item] for item in shared_route_ids})), pressure_ids,
                ("MULTI_LANE_COVERAGE", "RANGED_DPS", "ARTS_DAMAGE"),
                "Legal high-ground tiles covering multiple active routes.",
                "StageUnderstanding.coverage_opportunities.shared",
            ))
        upstream_tiles = tuple(dict.fromkeys(
            item.tile for item in self.understanding.coverage_opportunities
            if item.tile_kind == "HIGH_GROUND" and any(
                (route_id, cell) in self._route_progress
                and self._route_progress[(route_id, cell)] <= 0.4
                for route_id in item.route_ids
                for cell in item.covered_cells
            )
        ))
        if upstream_tiles:
            regions.append(TacticalRegion(
                "high-ground-upstream-interception", "UPSTREAM_RANGED_INTERCEPTION", "HIGH_GROUND",
                upstream_tiles, high_ground_route_ids,
                tuple(sorted({lane_by_route[item] for item in high_ground_route_ids})), pressure_ids,
                ("RANGED_DPS", "ARTS_DAMAGE", "MULTI_LANE_COVERAGE"),
                "High-ground coverage beginning on the early portion of active routes.",
                "StageUnderstanding.coverage_opportunities and route progress",
            ))
        return tuple(regions)

    def _compatible_regions(self, operator_id: str, role: str) -> tuple[TacticalRegion, ...]:
        operator = self.engine.fixture.operators[operator_id]
        kind = "GROUND" if operator.position.value == "MELEE" else "HIGH_GROUND"
        return tuple(region for region in self._regions if region.tile_kind == kind)

    def _first_contact(
        self,
        covered_cells: set[tuple[int, int]],
        route_ids: set[str],
    ) -> float | None:
        contacts: list[float] = []
        for row in self._expanded_spawns:
            if row["route_id"] not in route_ids:
                continue
            route = next(
                item for item in self.engine.fixture.stage.routes
                if item.route_id == row["route_id"]
            )
            distances = [route.distance_at(cell) for cell in covered_cells]
            distances = [item for item in distances if item is not None]
            if not distances:
                continue
            contacts.append(row["time"] + min(distances) / row["speed"])
        return min(contacts) if contacts else None

    def tile_candidates(
        self,
        operator_id: str,
        role: str,
    ) -> tuple[TileCandidate, ...]:
        operator = self.engine.fixture.operators[operator_id]
        all_route_cells = set().union(*self._route_cells.values()) if self._route_cells else set()
        ground_route_tiles = {
            cell
            for cells in self._route_cells.values()
            for cell in cells
            if cell in self.understanding.deployable_ground
        }
        raw: list[TileCandidate] = []
        for region in self._compatible_regions(operator_id, role):
            for tile in region.tiles:
                for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                    coverage = self.transformer.covered_tiles(
                        origin=tile,
                        offsets=operator.attack_range,
                        direction=direction,
                    )
                    covered_route_ids = {
                        route_id
                        for route_id, cells in self._route_cells.items()
                        if coverage & cells
                    }
                    block_routes = self._block_routes_at(tile)
                    support_tiles = coverage & ground_route_tiles if role == "HEAL" else set()
                    if not covered_route_ids and not block_routes and not support_tiles:
                        continue
                    relevant_cells = coverage & all_route_cells
                    first_contact = self._first_contact(
                        relevant_cells | ({tile} if block_routes else set()),
                        covered_route_ids | block_routes,
                    )
                    shared_count = sum(len(
                        self._route_cells[route_id] & coverage
                    ) > 0 for route_id in covered_route_ids) if len(covered_route_ids) > 1 else 0
                    early_count = sum(
                        self._route_progress.get((route_id, cell), 1.0) <= 0.4
                        for route_id in covered_route_ids
                        for cell in self._route_cells[route_id] & coverage
                    )
                    role_satisfaction = self._role_satisfaction(
                        role, bool(covered_route_ids), bool(block_routes),
                        len(covered_route_ids) > 1, bool(support_tiles),
                    )
                    features = {
                        "route_coverage_count": float(len(relevant_cells)),
                        "covered_route_count": float(len(covered_route_ids)),
                        "shared_route_count": float(shared_count),
                        "early_coverage_count": float(early_count),
                        "block_route_count": float(len(block_routes)),
                        "support_target_count": float(len(support_tiles)),
                        "contact_earliness_seconds": -float(first_contact if first_contact is not None else 10_000.0),
                        "role_satisfaction": float(role_satisfaction),
                        "facing_distinct_coverage": 1.0,
                    }
                    raw.append(TileCandidate(
                        operator_id, tile, direction, region.region_id, region.region_type, role,
                        tuple(sorted(covered_route_ids)), tuple(sorted(relevant_cells)),
                        tuple(sorted(block_routes)), tuple(sorted(support_tiles)),
                        first_contact, features, 0,
                        f"{region.region_type} placement with role {role}",
                    ))

        ranked = self._rank_pareto(raw)
        by_tile: dict[tuple[int, int], list[TileCandidate]] = {}
        for candidate in ranked:
            by_tile.setdefault(candidate.tile, []).append(candidate)
        selected: list[TileCandidate] = []
        for tile, rows in sorted(by_tile.items()):
            facing_groups: dict[frozenset[tuple[int, int]], list[TileCandidate]] = {}
            for row in rows:
                facing_groups.setdefault(frozenset(row.covered_cells), []).append(row)
            tile_selected: list[TileCandidate] = []
            for group in sorted(
                facing_groups.values(),
                key=lambda rows: (rows[0].pareto_rank, -rows[0].features["role_satisfaction"], rows[0].direction),
            ):
                tile_selected.extend(group[:self.config.facings_per_tile])
                if len(tile_selected) >= self.config.max_candidates_per_tile:
                    break
            selected.extend(tile_selected)
            if len(selected) >= self.config.tile_candidates_per_operator:
                break
        output = tuple(selected[:self.config.tile_candidates_per_operator])
        self._record_tile_funnel(raw, output)
        return output

    def _record_tile_funnel(self, raw: list[TileCandidate], selected: tuple[TileCandidate, ...]) -> None:
        selected_tiles = {item.tile for item in selected}
        selected_facings = {(item.tile, item.direction) for item in selected}
        self.last_tile_candidate_audit = {
            "raw_candidates": len(raw),
            "raw_facing_signatures": len({
                (item.tile, item.direction, frozenset(item.covered_cells))
                for item in raw
            }),
            "selected_candidates": len(selected),
            "selected_tiles": len(selected_tiles),
            "selected_facings": len(selected_facings),
        }

    @staticmethod
    def _role_satisfaction(
        role: str,
        covers_route: bool,
        blocks_route: bool,
        shared_coverage: bool,
        supports_target: bool,
    ) -> bool:
        if role in {"BLOCK", "BLOCK_CAPACITY"}:
            return blocks_route
        if role == "MELEE_DPS":
            return covers_route or blocks_route
        if role == "EARLY_DEPLOYMENT":
            return True
        if role == "MULTI_LANE_COVERAGE":
            return shared_coverage
        if role == "HEAL":
            return supports_target
        return covers_route

    @staticmethod
    def _rank_pareto(rows: list[TileCandidate]) -> list[TileCandidate]:
        remaining = list(rows)
        output: list[TileCandidate] = []
        rank = 0
        while remaining and rank < 8:
            dominated_indexes: set[int] = set()
            for index, candidate in enumerate(remaining):
                for other_index, other in enumerate(remaining):
                    if index == other_index:
                        continue
                    if (
                        all(other.features[key] >= candidate.features[key] for key in candidate.features)
                        and any(other.features[key] > candidate.features[key] for key in candidate.features)
                    ):
                        dominated_indexes.add(index)
                        break
            front = [
                replace(item, pareto_rank=rank)
                for index, item in enumerate(remaining)
                if index not in dominated_indexes
            ]
            if not front:
                front = [replace(item, pareto_rank=rank) for item in remaining]
                remaining = []
            else:
                remaining = [
                    item for index, item in enumerate(remaining)
                    if index in dominated_indexes
                ]
            output.extend(front)
            rank += 1
        return output

    def _skeleton_feature_summary(self, placements: tuple[SpatialPlacement, ...]) -> dict[str, float]:
        keys = placements[0].candidate.features.keys() if placements else ()
        return {
            key: sum(item.candidate.features.get(key, 0.0) for item in placements)
            for key in keys
        }

    @staticmethod
    def _pareto_front_states(states: list[_SkeletonState]) -> list[_SkeletonState]:
        front = []
        for state in states:
            dominated = any(
                all(other.feature_summary.get(key, 0.0) >= state.feature_summary.get(key, 0.0) for key in state.feature_summary)
                and any(other.feature_summary.get(key, 0.0) > state.feature_summary.get(key, 0.0) for key in state.feature_summary)
                for other in states
                if other is not state
            )
            if not dominated:
                front.append(state)
        return front

    def generate_skeletons(
        self,
        *,
        hypothesis_id: str,
        hypothesis_archetype: str,
        team: tuple[str, ...],
        deployment_order: tuple[str, ...],
        roles: dict[str, str],
        audit: dict[str, Any],
    ) -> tuple[SpatialSkeleton, ...]:
        candidates_by_operator: dict[str, tuple[TileCandidate, ...]] = {}
        tile_audits = []
        for operator_id in deployment_order:
            candidates_by_operator[operator_id] = self.tile_candidates(
                operator_id, roles.get(operator_id, "RANGED_DPS")
            )
            tile_audits.append(dict(self.last_tile_candidate_audit))
        tile_funnel = {
            key: sum(row[key] for row in tile_audits)
            for key in (
                "raw_candidates", "raw_facing_signatures", "selected_candidates",
                "selected_tiles", "selected_facings",
            )
        }
        audit.setdefault("tile_funnel", {})[hypothesis_id] = tile_funnel
        audit.setdefault("tile_candidates", {})[hypothesis_id] = {
            operator_id: [item.to_dict() for item in rows]
            for operator_id, rows in candidates_by_operator.items()
        }
        states: list[_SkeletonState] = [_SkeletonState()]
        for operator_id in deployment_order:
            next_states: list[_SkeletonState] = []
            for state in states:
                for candidate in candidates_by_operator[operator_id]:
                    if candidate.tile in state.used_tiles:
                        continue
                    placement = SpatialPlacement(candidate, self._placement_relations(candidate))
                    next_states.append(_SkeletonState(
                        (*state.placements, placement),
                        state.used_tiles | {candidate.tile},
                        self._skeleton_feature_summary((*state.placements, placement)),
                    ))
            semantic_states: dict[tuple[Any, ...], _SkeletonState] = {}
            for state in next_states:
                key = tuple(item.candidate.semantic_key for item in state.placements)
                current = semantic_states.get(key)
                if current is None or self._state_sort_key(state) < self._state_sort_key(current):
                    semantic_states[key] = state
            stratified_states: dict[tuple[str, ...], _SkeletonState] = {}
            for state in semantic_states.values():
                signature = tuple(
                    (item.candidate.operator_id, item.candidate.tile, item.candidate.direction)
                    for item in state.placements
                )
                current = stratified_states.get(signature)
                if current is None or self._state_sort_key(state) < self._state_sort_key(current):
                    stratified_states[signature] = state
            pareto_states = self._pareto_front_states(list(semantic_states.values()))
            diverse_states = list(stratified_states.values())
            for state in pareto_states:
                signature = tuple(item.candidate.region_type for item in state.placements)
                if signature not in stratified_states:
                    diverse_states.append(state)
            if len(diverse_states) > self.config.skeleton_beam_width:
                buckets: dict[tuple[str, ...], _SkeletonState] = {}
                for state in diverse_states:
                    signature = tuple(
                        (item.candidate.operator_id, item.candidate.tile, item.candidate.direction)
                        for item in state.placements
                    )
                    current = buckets.get(signature)
                    if current is None or self._state_sort_key(state) < self._state_sort_key(current):
                        buckets[signature] = state
                diverse_states = sorted(buckets.values(), key=self._state_sort_key)
            states = diverse_states[:self.config.skeleton_beam_width]
            if not states:
                break

        complete_states = [state for state in states if len(state.placements) == len(team)]
        skeletons: dict[str, SpatialSkeleton] = {}
        for state in complete_states:
            placements = state.placements
            semantic_payload = [item.candidate.semantic_key for item in placements]
            fingerprint = hashlib.sha256(
                json.dumps(semantic_payload, sort_keys=True).encode()
            ).hexdigest()
            if fingerprint in skeletons:
                continue
            region_signature = tuple(item.candidate.region_type for item in placements)
            skeletons[fingerprint] = SpatialSkeleton(
                f"skeleton-{fingerprint[:12]}", hypothesis_id, hypothesis_archetype,
                placements, fingerprint, region_signature,
                self._skeleton_feature_summary(placements),
                "Tactical region and facing relationships selected before timing search.",
            )
        output: list[SpatialSkeleton] = []
        seen_geometries: set[tuple[Any, ...]] = set()
        for skeleton in sorted(
            skeletons.values(),
            key=lambda item: (
                -sum(item.feature_summary.values()),
                item.region_signature,
                item.skeleton_id,
            ),
        ):
            geometry = tuple(
                (placement.candidate.operator_id, placement.candidate.tile, placement.candidate.direction)
                for placement in skeleton.placements
            )
            if geometry in seen_geometries:
                continue
            seen_geometries.add(geometry)
            output.append(skeleton)
            if len(output) >= self.config.max_skeletons_per_hypothesis:
                break
        audit.setdefault("skeleton_funnel", {})[hypothesis_id] = {
            "complete_states": len(complete_states),
            "deduplicated_skeletons": len(skeletons),
            "returned_skeletons": len(output),
            "returned_executable_geometries": len(seen_geometries),
            "region_signature_collapse": False,
            "candidate_geometry_fingerprints": len({
                tuple((placement.candidate.operator_id, placement.candidate.tile, placement.candidate.direction) for placement in item.placements)
                for item in skeletons.values()
            }),
        }
        return tuple(output)

    @staticmethod
    def _state_sort_key(state: _SkeletonState) -> tuple[Any, ...]:
        return (
            -sum(state.feature_summary.values()),
            tuple(item.candidate.operator_id for item in state.placements),
            tuple(item.candidate.tile for item in state.placements),
        )

    @staticmethod
    def _placement_relations(candidate: TileCandidate) -> tuple[str, ...]:
        relations = []
        if candidate.block_route_ids:
            relations.append(f"BLOCKS_ROUTES:{','.join(candidate.block_route_ids)}")
        if candidate.covered_route_ids:
            relations.append(f"COVERS_ROUTES:{','.join(candidate.covered_route_ids)}")
        if len(candidate.covered_route_ids) > 1:
            relations.append("SHARED_MULTI_ROUTE_COVERAGE")
        if candidate.region_type in {"EARLY_TEMPORARY_INTERCEPTION", "UPSTREAM_RANGED_INTERCEPTION"}:
            relations.append("EARLY_OR_UPSTREAM_INTERCEPTION")
        if candidate.support_target_tiles:
            relations.append(f"SUPPORTS_FRONTLINE_TILES:{len(candidate.support_target_tiles)}")
        return tuple(relations)

    def _frame_for_seconds(self, seconds: float) -> int:
        fps = self.config.frame_clock.frames_per_second
        if fps is None:
            raise ValueError("spatial timing requires a configured frame clock")
        return max(0, int(float(Fraction(seconds) * fps + Fraction(1, 2))))

    def _derived_timing_offsets(self) -> dict[str, tuple[int, ...]]:
        fps = float(self.config.frame_clock.frames_per_second or 30)
        windows = self.understanding.pressure_windows
        spans = [item.end_time - item.start_time for item in windows if item.end_time > item.start_time]
        span = float(mean(spans)) if spans else fps
        contact = tuple(dict.fromkeys((
            max(1, round(fps * 2.0)),
            max(1, round(fps * 1.0)),
        )))
        pressure = (max(1, round(min(fps, span * 0.10))),)
        wave = (max(1, round(min(fps, span * 0.05))),)
        stagger = (max(1, round(min(fps, span * 0.05))),)
        return {
            "CONTACT": contact,
            "PRESSURE": pressure,
            "WAVE": wave,
            "STAGGER": stagger,
        }

    def _earliest_dp_frames(self, deployment_order: tuple[str, ...]) -> dict[str, int]:
        output: dict[str, int] = {}
        spent = 0.0
        initial = float(self.engine.fixture.stage.initial_dp.value or 0)
        rate = float(self.engine.fixture.stage.dp_per_second)
        for operator_id in deployment_order:
            cost = float(
                self.engine.fixture.operators[operator_id].phases[0].stats_max.cost.value or 0
            )
            needed = max(0.0, (spent + cost - initial) / rate) if rate > 0 else 0.0
            output[operator_id] = self._frame_for_seconds(needed)
            spent += cost
        return output

    def _timing_patterns(self, skeleton: SpatialSkeleton) -> list[tuple[str, str, int]]:
        offsets = self._derived_timing_offsets()
        patterns: list[tuple[str, str, int]] = [("EARLIEST_DP", "DP_AVAILABLE", 0)]
        for offset in offsets["CONTACT"]:
            patterns.append((f"CONTACT_MINUS_{offset}", "FIRST_CONTACT", -offset))
        for offset in offsets["PRESSURE"]:
            patterns.append((f"PRESSURE_START_MINUS_{offset}", "PRESSURE_WINDOW_START", -offset))
        for offset in offsets["WAVE"]:
            patterns.append((f"WAVE_START_MINUS_{offset}", "WAVE_START", -offset))
        for offset in offsets["STAGGER"]:
            patterns.append((f"PREVIOUS_DEPLOY_PLUS_{offset}", "PREVIOUS_DEPLOY", offset))
        return patterns

    def _event_seconds(
        self,
        placement: SpatialPlacement,
        event_type: str,
        *,
        earliest_dp_frame: int,
        previous_frame: int | None,
    ) -> tuple[float, int]:
        candidate = placement.candidate
        if event_type == "DP_AVAILABLE":
            return float(self.config.frame_clock.seconds_for_frame(earliest_dp_frame)), earliest_dp_frame
        if event_type == "PREVIOUS_DEPLOY":
            frame = earliest_dp_frame if previous_frame is None else previous_frame
            return float(self.config.frame_clock.seconds_for_frame(frame)), frame

        relevant_routes = set(candidate.covered_route_ids) | set(candidate.block_route_ids)
        if event_type == "FIRST_CONTACT":
            seconds = candidate.first_contact_seconds
            if seconds is None:
                pressure = min(
                    (window.start_time for window in self.understanding.pressure_windows
                     if relevant_routes.intersection(window.route_ids)),
                    default=None,
                )
                wave = min(
                    (wave.start_time for wave in self.understanding.waves
                     if relevant_routes.intersection(wave.route_ids)),
                    default=None,
                )
                spawn = min((row["time"] for row in self._expanded_spawns if row["route_id"] in relevant_routes), default=0.0)
                seconds = pressure if pressure is not None else (wave if wave is not None else spawn)
            frame = self._frame_for_seconds(float(seconds))
            return float(seconds), frame
        if event_type == "PRESSURE_WINDOW_START":
            seconds = min(
                (window.start_time for window in self.understanding.pressure_windows
                 if relevant_routes.intersection(window.route_ids)),
                default=0.0,
            )
        elif event_type == "WAVE_START":
            seconds = min(
                (wave.start_time for wave in self.understanding.waves
                 if relevant_routes.intersection(wave.route_ids)),
                default=0.0,
            )
        elif event_type == "SKILL_READY":
            seconds = 0.0
        else:
            raise ValueError(f"unsupported timing event: {event_type}")
        frame = self._frame_for_seconds(float(seconds))
        return float(seconds), frame

    def generate_timing_candidates(
        self,
        skeleton: SpatialSkeleton,
        *,
        audit: dict[str, Any],
        hypothesis: PlanHypothesis | None = None,
    ) -> tuple[TimingCandidate, ...]:
        deployment_order = tuple(item.candidate.operator_id for item in skeleton.placements)
        earliest_dp = self._earliest_dp_frames(deployment_order)
        base_candidates: list[TimingCandidate] = []
        seen_fingerprints: set[str] = set()
        for pattern_id, event_type, offset in self._timing_patterns(skeleton):
            anchors: list[TimingAnchor] = []
            actions: list[Action] = []
            previous_frame: int | None = None
            for placement in skeleton.placements:
                operator_id = placement.candidate.operator_id
                event_seconds, anchor_frame = self._event_seconds(
                    placement,
                    event_type,
                    earliest_dp_frame=earliest_dp[operator_id],
                    previous_frame=previous_frame,
                )
                desired_frame = max(0, anchor_frame + offset)
                earliest_frame = max(0, earliest_dp[operator_id])
                final_frame = max(desired_frame, earliest_frame)
                if previous_frame is not None:
                    ordering_constraint_applied = final_frame < previous_frame + 1
                    final_frame = max(final_frame, previous_frame + 1)
                else:
                    ordering_constraint_applied = False
                clamped = final_frame > desired_frame
                anchors.append(TimingAnchor(
                    operator_id,
                    event_type,
                    event_seconds,
                    anchor_frame,
                    offset,
                    desired_frame,
                    earliest_frame,
                    final_frame,
                    clamped,
                    ordering_constraint_applied,
                    (
                        f"{event_type} event-relative intent {offset:+d} frames; "
                        "final frame preserves the desired frame unless DP or ordering legality requires a later frame"
                    ),
                ))
                actions.append(Action(
                    ActionType.DEPLOY,
                    self.config.frame_clock.seconds_for_frame(final_frame),
                    operator_id,
                    placement.candidate.tile,
                    placement.candidate.direction,
                ))
                previous_frame = final_frame
            team = tuple(dict.fromkeys(deployment_order))
            strategy = Strategy(team, tuple(actions))
            feasible, reasons = self.dp_legality(strategy)
            payload = {
                "skeleton": skeleton.semantic_fingerprint,
                "pattern": pattern_id,
                "deploy_frames": [anchors[index].final_frame for index in range(len(anchors))],
                "actions": [
                    [action.operator_id, action.tile, action.direction]
                    for action in actions
                ],
            }
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if fingerprint in seen_fingerprints:
                pattern_rows.append({"pattern_id": pattern_id, "deduplicated": True})
                continue
            seen_fingerprints.add(fingerprint)
            timing_id = f"timing-{fingerprint[:12]}"
            base_candidates.append(TimingCandidate(
                timing_id=timing_id,
                skeleton_id=skeleton.skeleton_id,
                hypothesis_id=skeleton.hypothesis_id,
                pattern_id=pattern_id,
                deploy_frames=tuple(item.final_frame for item in anchors),
                anchors=tuple(anchors),
                actions=tuple(actions),
                strategy=strategy,
                semantic_fingerprint=fingerprint,
                dp_feasible=feasible,
                rejection_reasons=reasons,
            ))

        base_candidates = base_candidates[:self.config.max_timing_candidates_per_skeleton]
        combined: list[TimingCandidate] = list(base_candidates)
        if self._skill_intent_requested(hypothesis):
            for base in base_candidates:
                combined.extend(self._skill_timing_variants(skeleton, base, hypothesis))

        candidates: list[TimingCandidate] = []
        pattern_rows: list[dict[str, Any]] = []
        combined_seen_fingerprints: set[str] = set()
        for candidate in combined:
            if candidate.semantic_fingerprint in combined_seen_fingerprints:
                pattern_rows.append({
                    "pattern_id": candidate.pattern_id,
                    "deduplicated": True,
                })
                continue
            combined_seen_fingerprints.add(candidate.semantic_fingerprint)
            candidates.append(candidate)
            pattern_rows.append({
                "timing_id": candidate.timing_id,
                "pattern_id": candidate.pattern_id,
                "deduplicated": False,
                "dp_feasible": candidate.dp_feasible,
                "rejection_reasons": list(candidate.rejection_reasons),
                "deploy_frames": list(candidate.deploy_frames),
                "desired_frames": [item.desired_frame for item in candidate.anchors],
                "earliest_dp_frames": [item.earliest_frame for item in candidate.anchors],
                "clamped_by_dp": [item.clamped_by_dp for item in candidate.anchors],
                "ordering_constraint_applied": [item.ordering_constraint_applied for item in candidate.anchors],
                "skill_anchors": [item.to_dict() for item in candidate.skill_anchors],
                "action_types": [item.action_type.value for item in candidate.actions],
            })
        audit.setdefault("timing_candidates", {})[skeleton.skeleton_id] = pattern_rows
        return tuple(candidates)

    def _skill_intent_requested(self, hypothesis: PlanHypothesis | None) -> bool:
        if hypothesis is None:
            return False
        if hypothesis.skill_use_intents:
            return True
        return any(
            item.get("capability") == "SKILL"
            or "SKILL" in str(item.get("action_intent", ""))
            for item in hypothesis.operator_responsibilities
        )

    def _skill_capable_placements(
        self,
        skeleton: SpatialSkeleton,
        hypothesis: PlanHypothesis | None,
    ) -> tuple[SpatialPlacement, ...]:
        if not self._skill_intent_requested(hypothesis):
            return ()
        role_weight = {
            "RANGED_DPS": 4.0,
            "MULTI_LANE_COVERAGE": 4.0,
            "MELEE_DPS": 3.0,
            "HEAL": 3.0,
            "BLOCK": 2.0,
            "BLOCK_CAPACITY": 2.0,
            "EARLY_DEPLOYMENT": 1.0,
        }
        rows: list[tuple[float, SpatialPlacement]] = []
        for placement in skeleton.placements:
            operator = self.engine.fixture.operators.get(placement.candidate.operator_id)
            skill = operator.synthetic_skill if operator is not None else None
            if skill is None or skill.auto_activate:
                continue
            effect_strength = (
                max(0.0, skill.effect.atk_multiplier - 1.0) * 10.0
                + abs(skill.effect.atk_additive) / 100.0
                + abs(skill.effect.block_count_delta)
                + abs(skill.effect.dp_immediate) / 10.0
            )
            score = (
                role_weight.get(placement.candidate.intended_role, 0.0)
                + effect_strength
                + len(placement.candidate.covered_route_ids) / 10.0
                + len(placement.candidate.block_route_ids) / 10.0
            )
            rows.append((score, placement))
        rows.sort(key=lambda item: (-item[0], item[1].candidate.operator_id))
        return tuple(placement for _, placement in rows[:self.config.max_skill_operators])

    def _skill_timing_variants(
        self,
        skeleton: SpatialSkeleton,
        base: TimingCandidate,
        hypothesis: PlanHypothesis | None,
    ) -> tuple[TimingCandidate, ...]:
        placements = self._skill_capable_placements(skeleton, hypothesis)
        if not placements:
            return ()
        deployment_index = {
            placement.candidate.operator_id: index
            for index, placement in enumerate(skeleton.placements)
        }
        output: list[TimingCandidate] = []
        for placement in placements:
            operator_id = placement.candidate.operator_id
            operator = self.engine.fixture.operators[operator_id]
            skill = operator.synthetic_skill
            if skill is None or operator_id not in deployment_index:
                continue
            deploy_frame = base.deploy_frames[deployment_index[operator_id]]
            deploy_seconds = self.config.frame_clock.seconds_for_frame(deploy_frame)
            relevant_routes = set(placement.candidate.covered_route_ids) | set(placement.candidate.block_route_ids)
            relevant_windows = tuple(
                window
                for window in self.understanding.pressure_windows
                if relevant_routes.intersection(window.route_ids)
            )
            pressure_window = max(
                relevant_windows or self.understanding.pressure_windows,
                key=lambda item: (item.high_risk, item.spawn_count, item.start_time),
                default=None,
            )
            first_contact = placement.candidate.first_contact_seconds
            patterns = (
                ("SKILL_READY_AFTER_DEPLOY", "SKILL_READY", deploy_seconds, 0),
                ("PRESSURE_START_MINUS_30", "PRESSURE_START", pressure_window.start_time if pressure_window else deploy_seconds, -30),
                ("PRESSURE_PEAK_MINUS_60", "PRESSURE_PEAK", (pressure_window.start_time + pressure_window.end_time) / 2.0 if pressure_window else deploy_seconds, -60),
                ("FIRST_CONTACT_MINUS_30", "FIRST_CONTACT", first_contact if first_contact is not None else deploy_seconds, -30),
            )
            for skill_pattern, event_type, event_seconds, offset in patterns:
                anchor_frame = self._frame_for_seconds(float(event_seconds))
                desired_frame = max(0, anchor_frame + offset)
                earliest_frame = self._earliest_skill_ready_frame(operator, deploy_frame)
                final_frame = max(desired_frame, earliest_frame, deploy_frame + 1)
                clamped = final_frame > desired_frame
                skill_anchor = SkillTimingAnchor(
                    operator_id,
                    skill.skill_id,
                    event_type,
                    float(event_seconds),
                    anchor_frame,
                    offset,
                    desired_frame,
                    earliest_frame,
                    final_frame,
                    clamped,
                    f"{event_type} skill intent {offset:+d}; final frame preserves desired timing unless readiness requires later",
                )
                actions = tuple((
                    *base.actions,
                    Action(
                        ActionType.ACTIVATE_SKILL,
                        self.config.frame_clock.seconds_for_frame(final_frame),
                        operator_id,
                    ),
                ))
                strategy = Strategy(base.strategy.team, actions)
                feasible, reasons = self.dp_legality(strategy)
                payload = {
                    "parent": base.semantic_fingerprint,
                    "skill_pattern": skill_pattern,
                    "operator_id": operator_id,
                    "skill_id": skill.skill_id,
                    "final_frame": final_frame,
                }
                fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                output.append(TimingCandidate(
                    timing_id=f"skill-{fingerprint[:12]}",
                    skeleton_id=skeleton.skeleton_id,
                    hypothesis_id=skeleton.hypothesis_id,
                    pattern_id=f"{base.pattern_id}:{skill_pattern}",
                    deploy_frames=base.deploy_frames,
                    anchors=base.anchors,
                    actions=actions,
                    strategy=strategy,
                    semantic_fingerprint=fingerprint,
                    dp_feasible=feasible,
                    rejection_reasons=reasons,
                    skill_anchors=(skill_anchor,),
                    source="EVENT_RELATIVE_SKILL_TIMING",
                ))
                if len(output) >= self.config.max_skill_candidates_per_skeleton:
                    return tuple(output)
        return tuple(output)

    def _earliest_skill_ready_frame(self, operator, deploy_frame: int) -> int:
        skill = operator.synthetic_skill
        if skill is None:
            return deploy_frame + 1
        remaining_sp = max(0.0, skill.sp_cost - skill.initial_sp)
        if skill.recovery_mode.value != "TIME" or skill.sp_per_second <= 0:
            return deploy_frame + 1 if remaining_sp <= 0 else 10**9
        delay_seconds = remaining_sp / skill.sp_per_second
        delay_frames = int(delay_seconds * self.config.frame_clock.frames_per_second)
        return max(deploy_frame + 1, deploy_frame + delay_frames)

    def dp_legality(self, strategy: Strategy) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        actions = list(strategy.actions)
        deploy_actions = tuple(
            action for action in actions if action.action_type is ActionType.DEPLOY
        )
        if not deploy_actions:
            return False, ("NO_DEPLOY_ACTIONS",)
        if len(set(strategy.team)) != len(strategy.team):
            reasons.append("DUPLICATE_OPERATOR")
        if set(strategy.team) != {action.operator_id for action in deploy_actions}:
            reasons.append("TEAM_ACTION_MISMATCH")

        deployed_at: dict[str, float] = {}
        redeploy_available_at: dict[str, float] = {}
        occupied_tiles: set[tuple[int, int]] = set()
        max_concurrent_deployed = 0
        cumulative_cost = 0.0
        previous_frame: int | None = None
        initial_dp = float(self.engine.fixture.stage.initial_dp.value or 0)
        rate = float(self.engine.fixture.stage.dp_per_second)
        for action in actions:
            try:
                frame = self.config.frame_clock.frame_for_seconds(action.time)
            except (TypeError, ValueError):
                reasons.append("INVALID_FRAME")
                continue
            if frame < 0:
                reasons.append("NEGATIVE_FRAME")
            if previous_frame is not None and frame < previous_frame:
                reasons.append("NON_MONOTONIC_ACTION_ORDER")
            previous_frame = frame

            operator = self.engine.fixture.operators.get(action.operator_id)
            if operator is None:
                reasons.append("UNKNOWN_OPERATOR")
                continue
            action_time = float(action.time)
            if action.action_type is ActionType.DEPLOY:
                if action.operator_id in deployed_at:
                    reasons.append("DUPLICATE_OPERATOR")
                if redeploy_available_at.get(action.operator_id, 0.0) > action_time + 1e-9:
                    reasons.append("REDEPLOY_COOLDOWN_ACTIVE")
                if action.tile in occupied_tiles:
                    reasons.append("DUPLICATE_TILE")
                required_kind = "GROUND" if operator.position.value == "MELEE" else "HIGH_GROUND"
                tile = next(
                    (item for item in self.engine.fixture.stage.stage_map.tiles
                     if (item.x, item.y) == action.tile),
                    None,
                )
                if tile is None or not tile.buildable or tile.tile_kind != required_kind:
                    reasons.append("ILLEGAL_TILE_KIND")
                cost = float(operator.phases[0].stats_max.cost.value or 0)
                cumulative_cost += cost
                if initial_dp + rate * action_time + 1e-9 < cumulative_cost:
                    reasons.append("INSUFFICIENT_DP")
                deployed_at[action.operator_id] = action_time
                if action.tile is not None:
                    occupied_tiles.add(action.tile)
                max_concurrent_deployed = max(max_concurrent_deployed, len(deployed_at))
            elif action.action_type is ActionType.ACTIVATE_SKILL:
                if action.operator_id not in deployed_at:
                    reasons.append("SKILL_BEFORE_DEPLOY")
                    continue
                skill = operator.synthetic_skill
                if skill is None:
                    reasons.append("UNSUPPORTED_SKILL")
                elif skill.auto_activate:
                    reasons.append("AUTOMATIC_SKILL_CANNOT_BE_MANUAL")
                else:
                    remaining_sp = max(0.0, skill.sp_cost - skill.initial_sp)
                    if skill.recovery_mode.value == "TIME" and skill.sp_per_second > 0:
                        ready_time = deployed_at[action.operator_id] + remaining_sp / skill.sp_per_second
                        if action_time + 1e-9 < ready_time:
                            reasons.append("INSUFFICIENT_SKILL_SP")
                    elif remaining_sp > 0:
                        reasons.append("UNSUPPORTED_SKILL_RECOVERY")
            elif action.action_type is ActionType.RETREAT:
                if action.operator_id not in deployed_at:
                    reasons.append("RETREAT_BEFORE_DEPLOY")
                    continue
                del deployed_at[action.operator_id]
                if action.tile is not None and action.tile in occupied_tiles:
                    occupied_tiles.remove(action.tile)
                redeploy_available_at[action.operator_id] = action_time + float(operator.redeploy_time.value)
            else:
                reasons.append("UNSUPPORTED_ACTION_TYPE")

        deployment_limit = int(self.engine.fixture.stage.deployment_limit.value or 0)
        if deployment_limit and max_concurrent_deployed > deployment_limit:
            reasons.append("DEPLOYMENT_LIMIT_EXCEEDED")
        return not reasons, tuple(dict.fromkeys(reasons))

    def _timing_refinement_candidates(self, candidate: TimingCandidate) -> tuple[TimingCandidate, ...]:
        output: list[TimingCandidate] = []
        for index, action in enumerate(candidate.actions):
            center = self.config.frame_clock.frame_for_seconds(action.time)
            for offset in self.config.refinement_offsets:
                frame = max(0, center + offset)
                actions = list(candidate.actions)
                actions[index] = Action(
                    action.action_type,
                    self.config.frame_clock.seconds_for_frame(frame),
                    action.operator_id,
                    action.tile,
                    action.direction,
                )
                strategy = Strategy(candidate.strategy.team, tuple(actions))
                feasible, reasons = self.dp_legality(strategy)
                deploy_frames = tuple(
                    self.config.frame_clock.frame_for_seconds(item.time)
                    for item in actions
                    if item.action_type is ActionType.DEPLOY
                )
                skill_anchors = candidate.skill_anchors
                if action.action_type is ActionType.ACTIVATE_SKILL:
                    matching_anchor = next(
                        (item for item in skill_anchors if item.operator_id == action.operator_id),
                        None,
                    )
                    if matching_anchor is not None:
                        skill_anchors = tuple(
                            replace(item, final_frame=frame) if item is matching_anchor else item
                            for item in skill_anchors
                        )
                payload = {
                    "parent": candidate.semantic_fingerprint,
                    "adjusted_action": index,
                    "offset": offset,
                    "action_types": [item.action_type.value for item in actions],
                    "action_frames": [
                        self.config.frame_clock.frame_for_seconds(item.time)
                        for item in actions
                    ],
                }
                fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                output.append(TimingCandidate(
                    timing_id=f"refine-{fingerprint[:12]}",
                    skeleton_id=candidate.skeleton_id,
                    hypothesis_id=candidate.hypothesis_id,
                    pattern_id=f"{candidate.pattern_id}:action-{index}:{offset:+d}",
                    deploy_frames=deploy_frames,
                    anchors=candidate.anchors,
                    actions=tuple(actions),
                    strategy=strategy,
                    semantic_fingerprint=fingerprint,
                    dp_feasible=feasible,
                    rejection_reasons=reasons,
                    skill_anchors=skill_anchors,
                    source="LOCAL_TIMING_REFINEMENT",
                ))
        return tuple(output)

    @staticmethod
    def _leak_routes(result) -> set[str]:
        spawn_routes = {
            event.source_id: dict(event.details).get("route_id")
            for event in result.events
            if event.event_type.value == "SPAWN"
        }
        return {
            route_id
            for event in result.events
            if event.event_type.value == "ENEMY_LEAK"
            for route_id in (spawn_routes.get(event.source_id),)
            if route_id is not None
        }

    @staticmethod
    def _event_signature(result) -> tuple[tuple[Any, ...], ...]:
        return tuple(
            (
                round(event.time, 6),
                event.event_type.value,
                event.source_id,
                event.target_id,
                tuple(sorted((key, str(value)) for key, value in event.details)),
            )
            for event in result.events
        )

    @staticmethod
    def _first_event_difference(left, right) -> dict[str, Any] | None:
        for left_event, right_event in zip(left.events, right.events):
            left_row = (
                round(left_event.time, 6), left_event.event_type.value,
                left_event.source_id, left_event.target_id,
                tuple(sorted((key, str(value)) for key, value in left_event.details)),
            )
            right_row = (
                round(right_event.time, 6), right_event.event_type.value,
                right_event.source_id, right_event.target_id,
                tuple(sorted((key, str(value)) for key, value in right_event.details)),
            )
            if left_row != right_row:
                return {"parent": left_row, "refined": right_row}
        if len(left.events) != len(right.events):
            return {
                "parent_event_count": len(left.events),
                "refined_event_count": len(right.events),
            }
        return None

    def _timing_refinement_eligible(
        self,
        evaluation: M11Evaluation,
        candidate: TimingCandidate,
        skeleton: SpatialSkeleton,
    ) -> bool:
        result = evaluation.result
        if result.win or result.deployment_errors:
            return False
        if result.enemies_killed <= 0:
            return False
        skeleton_routes = {
            route_id
            for placement in skeleton.placements
            for route_id in (*placement.candidate.covered_route_ids, *placement.candidate.block_route_ids)
        }
        if not self._leak_routes(result).intersection(skeleton_routes):
            return False
        deploy_times = [action.time for action in evaluation.strategy.actions]
        leaks = [event.time for event in result.events if event.event_type.value == "ENEMY_LEAK"]
        first_leak = min(leaks, default=None)
        return first_leak is not None and deploy_times and first_leak < max(deploy_times)

    def _best_candidate(
        self,
        rows: list[tuple[M11Evaluation, TimingCandidate, SpatialSkeleton]],
    ) -> tuple[M11Evaluation, TimingCandidate, SpatialSkeleton] | None:
        return min(rows, key=lambda row: row[0].dense_rank) if rows else None

    def _executable_timeline_fingerprint(self, strategy: Strategy) -> str:
        payload = tuple(
            (
                action.action_type.value,
                action.operator_id,
                action.tile,
                action.direction,
                self.config.frame_clock.frame_for_seconds(action.time),
            )
            for action in strategy.actions
        )
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _responsibility_execution_audit(
        hypothesis: PlanHypothesis,
        active_order: tuple[str, ...],
        reserves: tuple[str, ...],
        hypothesis_audit: dict[str, Any],
        best: TimingCandidate | None,
        frame_clock: FrameClock,
    ) -> list[dict[str, Any]]:
        best_skeleton_id = best.skeleton_id if best is not None else None
        placement_source = (
            skeleton
            for skeleton in hypothesis_audit.get("skeletons", ())
            if skeleton.get("skeleton_id") == best_skeleton_id
        ) if best_skeleton_id else hypothesis_audit.get("skeletons", ())
        placements = {
            placement["candidate"]["operator_id"]: placement
            for skeleton in placement_source
            for placement in skeleton.get("placements", ())
        }
        deploy_frames: dict[str, set[int]] = {}
        best_frames: dict[str, int] = {}
        best_actions: dict[str, list[dict[str, Any]]] = {}
        if best is not None:
            for operator_id, frame in zip(active_order, best.deploy_frames):
                best_frames[operator_id] = int(frame)
            for action in best.actions:
                best_actions.setdefault(action.operator_id, []).append({
                    "action_type": action.action_type.value,
                    "frame": frame_clock.frame_for_seconds(action.time),
                    "tile": action.tile,
                    "direction": action.direction,
                })
        for rows in hypothesis_audit.get("timing_candidates", {}).values():
            for row in rows:
                if row.get("deduplicated", False):
                    continue
                for operator_id, frame in zip(
                    hypothesis_audit.get("active_deployment_subset", ()),
                    row.get("deploy_frames", ()),
                ):
                    deploy_frames.setdefault(operator_id, set()).add(int(frame))
        output = []
        links = hypothesis.operator_responsibilities or tuple(
            {"operator_id": operator_id} for operator_id in hypothesis.preferred_operator_ids
        )
        for link in links:
            operator_id = link.get("operator_id")
            placement = placements.get(operator_id)
            frames = sorted({best_frames[operator_id]} if operator_id in best_frames else ())
            if operator_id in active_order:
                status = (
                    "DEPLOYED_IN_BEST_CANDIDATE"
                    if operator_id in best_frames and placement is not None
                    else "ACTIVE_BUT_NOT_DEPLOYED_IN_BEST_CANDIDATE"
                )
                unused_reason = (
                    None
                    if operator_id in best_frames and placement is not None
                    else "missing best-candidate spatial placement or deploy action"
                )
            elif operator_id in reserves:
                status = "INTENTIONAL_RESERVE_NOT_DEPLOYED"
                unused_reason = "deployment-limit reserve retained in roster evidence"
            else:
                status = "NOT_LOWERED"
                unused_reason = "operator was not in the active subset or declared reserve set"
            output.append({
                **link,
                "execution_status": status,
                "unused_reason": unused_reason,
                "spatial_placement": placement,
                "deploy_frames": frames,
                "reachable_deploy_frames": sorted(deploy_frames.get(operator_id, ())),
                "best_candidate_actions": best_actions.get(operator_id, []),
                "activate_skill_frames": sorted(
                    action["frame"]
                    for action in best_actions.get(operator_id, ())
                    if action["action_type"] == "ACTIVATE_SKILL"
                ),
                "retreat_frames": sorted(
                    action["frame"]
                    for action in best_actions.get(operator_id, ())
                    if action["action_type"] == "RETREAT"
                ),
            })
        return output

    def search(
        self,
        hypotheses: Iterable[PlanHypothesis],
        *,
        simulation_budget: int,
    ) -> SpatialTimingSearchResult:
        if simulation_budget <= 0:
            raise ValueError("spatial timing search requires a positive simulation budget")
        started = perf_counter()
        metrics = M11SearchMetrics()
        spatial_metrics = SpatialTimingSearchMetrics(regions_generated=len(self._regions))
        audit: dict[str, Any] = {
            "regions": [region.to_dict() for region in self._regions],
            "hypotheses": {},
        }
        attempts: list[dict[str, Any]] = []
        coarse_rows: list[tuple[M11Evaluation, TimingCandidate, SpatialSkeleton]] = []
        evaluation_records: list[dict[str, Any]] = []
        seen_timing: set[str] = set()
        seen_executable_timelines: set[str] = set()

        for hypothesis in hypotheses:
            full_team = tuple(dict.fromkeys(hypothesis.preferred_operator_ids))
            deployment_order = tuple(
                operator_id for operator_id in hypothesis.deployment_order
                if operator_id in full_team
            ) or full_team
            deployment_limit = int(self.engine.fixture.stage.deployment_limit.value or 0)
            active_priority_order = deployment_order
            if self._skill_intent_requested(hypothesis):
                skill_priority_ids = tuple(
                    operator_id
                    for operator_id in deployment_order
                    if (
                        self.engine.fixture.operators[operator_id].synthetic_skill is not None
                        and not self.engine.fixture.operators[operator_id].synthetic_skill.auto_activate
                    )
                )[:self.config.max_skill_operators]
                active_priority_order = tuple(dict.fromkeys((*skill_priority_ids, *deployment_order)))
            if deployment_limit > 0:
                selected_order = tuple(dict.fromkeys(active_priority_order[:deployment_limit]))
            else:
                selected_order = tuple(dict.fromkeys(active_priority_order))
            active_order = tuple(sorted(
                selected_order,
                key=lambda operator_id: (
                    float(self.engine.fixture.operators[operator_id].phases[0].stats_max.cost.value or 0),
                    -float(self.engine.fixture.operators[operator_id].phases[0].stats_max.atk.value or 0),
                    operator_id,
                ),
            ))
            team = tuple(active_order)
            reserves = tuple(
                operator_id for operator_id in full_team
                if operator_id not in team
            )
            roles: dict[str, str] = {}
            role_priority = (
                "BLOCK_CAPACITY", "BLOCK", "MULTI_LANE_COVERAGE", "RANGED_DPS",
                "MELEE_DPS", "HEAL", "EARLY_DEPLOYMENT", "ARTS_DAMAGE", "SKILL",
            )
            for link in hypothesis.operator_responsibilities:
                capability = link.get("capability")
                operator_id = link.get("operator_id")
                if capability not in role_priority or not operator_id or operator_id in roles:
                    continue
                roles[operator_id] = "BLOCK" if capability == "BLOCK_CAPACITY" else capability
            for operator_id in deployment_order:
                operator = self.engine.fixture.operators[operator_id]
                block_count = int(operator.phases[0].stats_max.block_count.value or 0)
                shared_coverage = any(
                    operator_id in opportunity.operator_ids and opportunity.shared
                    for opportunity in self.understanding.coverage_opportunities
                )
                if operator_id in roles and operator.profession.value == "MEDIC" and roles[operator_id] not in {"HEAL"}:
                    roles[operator_id] = "HEAL"
                elif operator_id in roles:
                    pass
                elif operator.profession.value == "MEDIC":
                    roles[operator_id] = "HEAL"
                elif operator.position.value == "MELEE":
                    roles[operator_id] = "BLOCK" if block_count > 0 else "MELEE_DPS"
                elif shared_coverage:
                    roles[operator_id] = "MULTI_LANE_COVERAGE"
                else:
                    roles[operator_id] = "RANGED_DPS"

            hypothesis_audit: dict[str, Any] = {
                "roles": roles,
                "full_roster": list(full_team),
                "active_deployment_subset": list(team),
                "reserve_operators": list(reserves),
                "deployment_limit": deployment_limit,
            "active_subset_policy": (
                    "preserve explicit temporal assignment roles, promote at most max_skill_operators manual supported-skill "
                    "operators when skill intent exists, select the first deployment_limit entries, then apply a deterministic "
                    "cost ordering only as a DP-feasibility order"
            ),
            }
            hypothesis_timing_candidates = 0
            hypothesis_unique_simulations = 0
            skeletons = self.generate_skeletons(
                hypothesis_id=hypothesis.hypothesis_id,
                hypothesis_archetype=hypothesis.tactical_archetype,
                team=team,
                deployment_order=active_order,
                roles=roles,
                audit=hypothesis_audit,
            )
            tile_funnel = hypothesis_audit["tile_funnel"][hypothesis.hypothesis_id]
            skeleton_funnel = hypothesis_audit["skeleton_funnel"][hypothesis.hypothesis_id]
            spatial_metrics.tile_candidates_generated += tile_funnel["raw_candidates"]
            spatial_metrics.tile_candidates_after_pruning += tile_funnel["selected_candidates"]
            spatial_metrics.facing_candidates_generated += tile_funnel["raw_facing_signatures"]
            spatial_metrics.facing_candidates_after_deduplication += tile_funnel["selected_facings"]
            spatial_metrics.skeletons_generated += skeleton_funnel["complete_states"]
            spatial_metrics.skeletons_deduplicated += len(skeletons)
            spatial_metrics.skeletons_reaching_timing += len(skeletons)
            hypothesis_audit["skeletons"] = [item.to_dict() for item in skeletons]
            hypothesis_rows: list[tuple[M11Evaluation, TimingCandidate, SpatialSkeleton]] = []
            for skeleton in skeletons:
                if metrics.unique_simulations >= simulation_budget:
                    break
                timing = self.generate_timing_candidates(
                    skeleton,
                    audit=hypothesis_audit,
                    hypothesis=hypothesis,
                )
                spatial_metrics.timing_candidates_generated += len(timing)
                hypothesis_timing_candidates += len(timing)
                unique_timing = tuple(
                    item for item in timing
                    if not (item.semantic_fingerprint in seen_timing or seen_timing.add(item.semantic_fingerprint))
                )
                spatial_metrics.timing_candidates_deduplicated += len(unique_timing)
                for candidate in unique_timing:
                    if metrics.unique_simulations >= simulation_budget:
                        break
                    if not candidate.dp_feasible:
                        spatial_metrics.timing_candidates_dp_rejected += 1
                        continue
                    executable_fingerprint = self._executable_timeline_fingerprint(candidate.strategy)
                    if executable_fingerprint in seen_executable_timelines:
                        spatial_metrics.timing_candidates_executable_deduplicated += 1
                        continue
                    seen_executable_timelines.add(executable_fingerprint)
                    spatial_metrics.evaluations_generated += 1
                    unique_before = metrics.unique_simulations
                    evaluation = self.engine.evaluate(candidate.strategy, metrics)
                    if metrics.unique_simulations > unique_before:
                        hypothesis_unique_simulations += 1
                        spatial_metrics.unique_frame_timelines += 1
                    spatial_metrics.coarse_simulations = metrics.unique_simulations
                    hypothesis_rows.append((evaluation, candidate, skeleton))
                    coarse_rows.append((evaluation, candidate, skeleton))
                    evaluation_records.append({
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "skeleton_id": skeleton.skeleton_id,
                        "timing_id": candidate.timing_id,
                        "strategy_fingerprint": self._executable_timeline_fingerprint(candidate.strategy),
                        "team": list(candidate.strategy.team),
                        "actions": [
                            {
                                "type": action.action_type.value,
                                "operator_id": action.operator_id,
                                "tile": list(action.tile) if action.tile is not None else None,
                                "direction": action.direction,
                            }
                            for action in candidate.strategy.actions
                        ],
                        "result": {
                            "win": evaluation.result.win,
                            "remaining_life": evaluation.result.remaining_life,
                            "kills": evaluation.result.enemies_killed,
                            "leaks": evaluation.result.enemies_leaked,
                            "operator_deaths": evaluation.result.operator_deaths,
                            "time_survived": evaluation.result.time_survived,
                        },
                        "source": "COARSE",
                    })
                    if evaluation.result.win:
                        break
                if metrics.unique_simulations >= simulation_budget or any(row[0].result.win for row in hypothesis_rows):
                    break
            best = self._best_candidate(hypothesis_rows)
            hypothesis_audit["operator_responsibility_execution"] = self._responsibility_execution_audit(
                hypothesis,
                team,
                reserves,
                hypothesis_audit,
                best[1] if best else None,
                self.config.frame_clock,
            )
            attempts.append({
                "hypothesis_id": hypothesis.hypothesis_id,
                "tactical_archetype": hypothesis.tactical_archetype,
                "team": list(team),
                "roles": roles,
                "skeletons_generated": len(skeletons),
                "timing_candidates_generated": hypothesis_timing_candidates,
                "evaluations_generated": len(hypothesis_rows),
                "unique_simulations": hypothesis_unique_simulations,
                "win": bool(best and best[0].result.win),
                "best": {
                    "skeleton_id": best[1].skeleton_id,
                    "timing_id": best[1].timing_id,
                    "pattern_id": best[1].pattern_id,
                    "result": {
                        "win": best[0].result.win,
                        "remaining_life": best[0].result.remaining_life,
                        "kills": best[0].result.enemies_killed,
                        "leaks": best[0].result.enemies_leaked,
                        "deployment_errors": list(best[0].result.deployment_errors),
                    },
                } if best else None,
            })
            audit["hypotheses"][hypothesis.hypothesis_id] = hypothesis_audit
            if any(row[0].result.win for row in hypothesis_rows):
                break

        coarse_used = metrics.unique_simulations
        refinement_history: list[dict[str, Any]] = []
        if not any(row[0].result.win for row in coarse_rows):
            max_refinement = min(
                simulation_budget - coarse_used,
                int((coarse_used * self.config.max_refinement_fraction) / (1.0 - self.config.max_refinement_fraction)),
            )
            candidates = sorted(
                (row for row in coarse_rows if self._timing_refinement_eligible(*row)),
                key=lambda row: row[0].dense_rank,
            )
            for evaluation, candidate, skeleton in candidates:
                if metrics.unique_simulations - coarse_used >= max_refinement:
                    break
                for refined in self._timing_refinement_candidates(candidate):
                    if metrics.unique_simulations - coarse_used >= max_refinement:
                        break
                    if not refined.dp_feasible or refined.semantic_fingerprint in seen_timing:
                        continue
                    seen_timing.add(refined.semantic_fingerprint)
                    executable_fingerprint = self._executable_timeline_fingerprint(refined.strategy)
                    if executable_fingerprint in seen_executable_timelines:
                        spatial_metrics.timing_candidates_executable_deduplicated += 1
                        continue
                    seen_executable_timelines.add(executable_fingerprint)
                    unique_before = metrics.unique_simulations
                    refined_evaluation = self.engine.evaluate(refined.strategy, metrics)
                    if metrics.unique_simulations > unique_before:
                        metrics.refinement_simulations += 1
                        spatial_metrics.unique_frame_timelines += 1
                    spatial_metrics.refinement_simulations = metrics.refinement_simulations
                    timeline_changed = (
                        self._executable_timeline_fingerprint(candidate.strategy)
                        != self._executable_timeline_fingerprint(refined.strategy)
                    )
                    event_difference = self._first_event_difference(
                        evaluation.result,
                        refined_evaluation.result,
                    )
                    refinement_history.append({
                        "parent_timing_id": candidate.timing_id,
                        "timing_id": refined.timing_id,
                        "pattern_id": refined.pattern_id,
                        "parent_deploy_frames": list(candidate.deploy_frames),
                        "deploy_frames": list(refined.deploy_frames),
                        "parent_skill_anchors": [item.to_dict() for item in candidate.skill_anchors],
                        "skill_anchors": [item.to_dict() for item in refined.skill_anchors],
                        "timeline_changed": timeline_changed,
                        "status": (
                            "REFINEMENT_SURVIVED_TO_TIMELINE"
                            if timeline_changed
                            else "REFINEMENT_NORMALIZED_AWAY"
                        ),
                        "simulator_effect": (
                            "EVENT_STREAM_CHANGED"
                            if event_difference is not None
                            else "NO_EVENT_STREAM_CHANGE"
                        ),
                        "first_event_difference": event_difference,
                        "result": {
                            "win": refined_evaluation.result.win,
                            "remaining_life": refined_evaluation.result.remaining_life,
                            "kills": refined_evaluation.result.enemies_killed,
                            "leaks": refined_evaluation.result.enemies_leaked,
                        },
                    })
                    coarse_rows.append((refined_evaluation, refined, skeleton))
                    evaluation_records.append({
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "skeleton_id": skeleton.skeleton_id,
                        "timing_id": refined.timing_id,
                        "strategy_fingerprint": self._executable_timeline_fingerprint(refined.strategy),
                        "team": list(refined.strategy.team),
                        "actions": [
                            {
                                "type": action.action_type.value,
                                "operator_id": action.operator_id,
                                "tile": list(action.tile) if action.tile is not None else None,
                                "direction": action.direction,
                            }
                            for action in refined.strategy.actions
                        ],
                        "result": {
                            "win": refined_evaluation.result.win,
                            "remaining_life": refined_evaluation.result.remaining_life,
                            "kills": refined_evaluation.result.enemies_killed,
                            "leaks": refined_evaluation.result.enemies_leaked,
                            "operator_deaths": refined_evaluation.result.operator_deaths,
                            "time_survived": refined_evaluation.result.time_survived,
                        },
                        "source": "REFINEMENT",
                    })
                    if refined_evaluation.result.win:
                        break
                if any(row[0].result.win for row in coarse_rows):
                    break

        best = self._best_candidate(coarse_rows)
        metrics.wall_clock_seconds = perf_counter() - started
        spatial_metrics.cache_hits = metrics.cache_hits
        spatial_metrics.wall_clock_seconds = metrics.wall_clock_seconds
        timeline = None
        if best is not None:
            timeline = strategy_to_timeline(
                best[0].strategy,
                stage_id=self.engine.fixture.stage.stage_id,
                frame_clock=self.config.frame_clock,
                simulator_mode="APPROXIMATE_REAL",
                approximation_policy_version=self.engine.policy.cache_identity,
            )
        stop = M11SearchStop.BEST_FOUND_UNDER_BUDGET if best and best[0].result.win else M11SearchStop.NO_WIN_FOUND
        return SpatialTimingSearchResult(
            stage_id=self.engine.fixture.stage.stage_id,
            best=best[0] if best else None,
            best_hypothesis_id=best[1].hypothesis_id if best else None,
            best_skeleton=best[2] if best else None,
            timeline=timeline,
            robustness_by_action=(),
            stop=stop,
            metrics=metrics,
            spatial_metrics=spatial_metrics,
            attempts=attempts,
            audit=audit,
            timing_refinement_history=refinement_history,
            evaluation_records=tuple(evaluation_records),
        )
