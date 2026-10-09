"""M15 constraint-guided, feasibility-first planner for the 6-8 benchmark.

This is deliberately a bounded repair planner, not a roster enumerator: source
facts create initial route constraints, partial plans satisfy those constraints,
and each simulator failure adds at most one evidence-backed next constraint.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from fractions import Fraction
from math import ceil
from time import perf_counter

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.benchmark import render_human_timeline
from arknights_planner.models.simulation import EventType, SimulationResult
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig, M11SearchMetrics
from arknights_planner.simulator import SimulationConfig
from arknights_planner.timing import strategy_to_timeline


class FailureType(str, Enum):
    EARLY_LEAK = "EARLY_LEAK"
    DAMAGE_INSUFFICIENT = "DAMAGE_INSUFFICIENT"
    OPERATOR_DEATH = "OPERATOR_DEATH"
    ROUTE_UNCOVERED = "ROUTE_UNCOVERED"
    DP_INFEASIBLE = "DP_INFEASIBLE"
    DEPLOYMENT_ILLEGAL = "DEPLOYMENT_ILLEGAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FailureFrontier:
    frame: int
    failure_type: FailureType
    routes: tuple[str, ...]
    enemy_ids: tuple[str, ...]
    affected_operator_ids: tuple[str, ...]
    relevant_tiles: tuple[tuple[int, int], ...]
    required_capabilities: tuple[str, ...]
    dp_state: str
    deployment_slots: int | None
    evidence: tuple[str, ...]
    confidence: str


@dataclass(frozen=True)
class TacticalConstraint:
    constraint_id: str
    constraint_type: str
    routes: tuple[str, ...]
    deadline_frame: int
    required_capabilities: tuple[str, ...]
    relevant_tiles: tuple[tuple[int, int], ...]
    hard_deadline: bool
    provenance: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class AssignedPlacement:
    constraint_id: str
    operator_id: str
    tile: tuple[int, int]
    direction: str
    covered_routes: tuple[str, ...]


@dataclass(frozen=True)
class PartialStrategy:
    assignments: tuple[AssignedPlacement, ...] = ()
    satisfied_constraints: tuple[str, ...] = ()
    constraints: tuple[TacticalConstraint, ...] = ()
    actions: tuple[Action, ...] = ()
    frozen_prefix: tuple[tuple[str, int, str, tuple[int, int] | None, str | None], ...] = ()
    frozen_until_frame: int = 0


@dataclass
class M15Metrics:
    constraints_generated: int = 0
    assignments_considered: int = 0
    dp_infeasible_assignments: int = 0
    spatially_infeasible_assignments: int = 0
    structural_rejections: int = 0
    unique_simulations: int = 0
    cache_hits: int = 0
    prefix_freezes: int = 0
    prefix_invalidations: int = 0
    candidates_generated: int = 0


def _action_key(action: Action, engine: M11MinimumSquadSearch) -> tuple[str, int, str, tuple[int, int] | None, str | None]:
    return action.action_type.value, engine.config.frame_clock.frame_for_seconds(action.time), action.operator_id, action.tile, action.direction


class ConstraintGuidedFeasibilityPlanner:
    """Bounded TEAM → constrained placement → event-relative timing planner."""

    VERSION = "m15-constraint-guided-feasibility-v1"

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter,
                 policy: RealSimulationApproximationPolicy, beam_width: int = 12,
                 simulation_budget: int = 2000, max_cardinality: int = 7):
        self.adapter, self.policy = adapter, policy
        self.beam_width, self.simulation_budget, self.max_cardinality = beam_width, simulation_budget, max_cardinality
        self.configurations = {item.operator_id: item for item in adapter.m13_low_rarity_configurations()}
        self.engine = M11MinimumSquadSearch(
            adapter=adapter, stage_id_or_code="6-8", policy=policy,
            operator_pool=tuple(self.configurations.values()),
            config=M11SearchConfig(max_squad_size=max_cardinality, max_teams=1,
                                   placement_options_per_operator=64, beam_width=beam_width,
                                   simulation_config=SimulationConfig(dt=0.2, max_time=300.0)),
        )
        self.metrics = M15Metrics()
        self.sim_metrics = M11SearchMetrics()
        self.progress: list[dict] = []
        self.frontiers: list[dict] = []
        self.prefix_history: list[dict] = []
        self.rejections: list[dict] = []
        self.constraints: list[TacticalConstraint] = []

    @staticmethod
    def _route_cells(route) -> tuple[tuple[int, int], ...]:
        out: list[tuple[int, int]] = []
        for first, second in zip(route.waypoints, route.waypoints[1:]):
            steps = max(1, ceil(max(abs(second.x - first.x), abs(second.y - first.y))))
            for step in range(steps + 1):
                item = (round(first.x + (second.x - first.x) * step / steps), round(first.y + (second.y - first.y) * step / steps))
                if not out or item != out[-1]:
                    out.append(item)
        return tuple(out)

    def _first_spawn(self, route_id: str):
        return next(item for item in self.engine.fixture.stage.spawn_events if item.route_id == route_id)

    def _entry_frame(self, route, spawn, tile: tuple[int, int]) -> int | None:
        distance = route.distance_at(tile)
        if distance is None:
            return None
        enemy = self.engine.fixture.enemies[spawn.enemy_id]
        waits = sum(wait.duration for wait in route.waits if wait.distance < distance)
        return ceil((spawn.time + distance / float(enemy.stats.move_speed.value) + waits) * 30.0)

    def initial_constraints(self) -> tuple[TacticalConstraint, ...]:
        """Derive the two initial central-lane interaction deadlines from routes."""
        routes = {item.route_id: item for item in self.engine.fixture.stage.routes}
        ground = {tile.coordinate for tile in self.engine.fixture.tile_mappings if tile.simulator_category == "GROUND"}
        constraints: list[TacticalConstraint] = []
        for route_id in ("route-0", "route-2"):
            route, spawn = routes[route_id], self._first_spawn(route_id)
            cells = self._route_cells(route)
            # The first deployable path tile at/after 40% path progress is a
            # deterministic central defense band, not a per-stage tile hack.
            candidates = [(route.distance_at(cell), cell) for cell in cells if cell in ground and route.distance_at(cell) is not None]
            _, tile = next((item for item in candidates if item[0] >= route.length * 0.4), candidates[-1])
            deadline = self._entry_frame(route, spawn, tile)
            constraints.append(TacticalConstraint(
                f"INITIAL_INTERACT_{route_id}", "INTERACT_WITH_ROUTE_BEFORE", (route_id,), deadline or 0,
                ("BLOCK_OR_RANGED_COVERAGE",), (tile,), True, "DERIVED",
                (f"first {route_id} spawn reaches central deployable route tile {tile} at frame {deadline}",),
            ))
        self.metrics.constraints_generated += len(constraints)
        return tuple(constraints)

    def _effective_cost(self, operator_id: str) -> float:
        operator = self.engine.fixture.operators[operator_id]
        return max(0.0, float(operator.phases[0].stats_max.cost.value or 0) + operator.deployment_cost_delta)

    def _capabilities(self, operator_id: str) -> tuple[str, ...]:
        op = self.engine.fixture.operators[operator_id]
        stats = op.phases[0].stats_max
        caps: set[str] = set()
        if op.position.value == "MELEE" and int(stats.block_count.value or 0) > 0:
            caps.add("BLOCK")
        if op.combat_output.value == "DAMAGE":
            caps.add("DAMAGE")
        if op.damage_type == "ARTS":
            caps.add("ARTS_DPS")
        if op.combat_output.value == "HEAL":
            caps.add("HEALING")
        if op.synthetic_skill and op.synthetic_skill.effect.dp_immediate:
            caps.add("DP_ECONOMY")
        if self._effective_cost(operator_id) <= 10:
            caps.add("CHEAP_OPENING")
        return tuple(sorted(caps))

    def _placement_value(self, operator_id: str) -> float:
        """A feasibility ordering feature, never a final strategy score."""
        op = self.engine.fixture.operators[operator_id]
        stats = op.phases[0].stats_max
        atk = float(stats.atk.value or 0)
        interval = max(.1, float(stats.attack_interval.value or 1.0))
        value = atk / interval if op.combat_output.value == "DAMAGE" else atk / interval * .35
        value += 110.0 * int(stats.block_count.value or 0) if op.position.value == "MELEE" else 0.0
        value += 35.0 if op.damage_type == "ARTS" else 0.0
        return value

    def _damage_value(self, operator_id: str) -> float:
        op = self.engine.fixture.operators[operator_id]
        stats = op.phases[0].stats_max
        if op.combat_output.value != "DAMAGE":
            return 0.0
        value = float(stats.atk.value or 0) / max(.1, float(stats.attack_interval.value or 1.0))
        return value + (35.0 if op.damage_type == "ARTS" else 0.0)

    def _unsatisfied_constraints(self, partial: PartialStrategy) -> tuple[TacticalConstraint, ...]:
        satisfied = set(partial.satisfied_constraints)
        return tuple(item for item in partial.constraints if item.constraint_id not in satisfied)

    def _placement_candidates(self, partial: PartialStrategy, constraint: TacticalConstraint,
                              active_constraints: tuple[TacticalConstraint, ...] = ()) -> list[AssignedPlacement]:
        """Return placements for ``constraint`` and expose useful shared coverage.

        A deployment which ranges over a second unresolved route is allowed to
        satisfy that second route too.  The M14.8 geometry audit established
        this is possible for the parallel early corridors, so treating the two
        opening constraints as independent assignments would be an artificial
        constraint of the planner rather than of the stage.
        """
        transformer = self.engine.simulator.range_transformer
        routes = {item.route_id: item for item in self.engine.fixture.stage.routes}
        active_constraints = active_constraints or (constraint,)
        active_routes = tuple(dict.fromkeys(route_id for item in active_constraints for route_id in item.routes))
        used_ops = {item.operator_id for item in partial.assignments}; used_tiles = {item.tile for item in partial.assignments}
        all_candidates: list[tuple[tuple, AssignedPlacement]] = []
        for operator_id, op in self.engine.fixture.operators.items():
            if operator_id in used_ops:
                continue
            if constraint.constraint_type == "PROVIDE_DAMAGE_BEFORE" and op.combat_output.value != "DAMAGE":
                continue
            if constraint.constraint_type == "INTERACT_WITH_ROUTE_BEFORE" and not (
                (op.position.value == "MELEE" and int(op.phases[0].stats_max.block_count.value or 0) > 0)
                or op.combat_output.value == "DAMAGE"
            ):
                continue
            required_kind = "GROUND" if op.position.value == "MELEE" else "HIGH_GROUND"
            for tile in self.engine.fixture.stage.stage_map.tiles:
                if not tile.buildable or tile.tile_kind != required_kind or (tile.x, tile.y) in used_tiles:
                    continue
                for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
                    covered = transformer.covered_tiles(origin=(tile.x, tile.y), offsets=op.attack_range, direction=direction)
                    covered_routes = []
                    for route_id in active_routes:
                        route = routes[route_id]
                        blocks = op.position.value == "MELEE" and route.distance_at((tile.x, tile.y)) is not None
                        ranges = bool(covered & set(self._route_cells(route)))
                        if blocks or ranges:
                            covered_routes.append(route_id)
                    self.metrics.assignments_considered += 1
                    if not covered_routes or not set(constraint.routes).intersection(covered_routes):
                        self.metrics.spatially_infeasible_assignments += 1
                        continue
                    assignment = AssignedPlacement(constraint.constraint_id, operator_id, (tile.x, tile.y), direction, tuple(covered_routes))
                    # This is only a beam-ordering heuristic.  Feasibility
                    # benefits from retaining credible damage/blocking power;
                    # cost remains a tie-breaker rather than forcing the
                    # cheapest roster before a simulator WIN exists.
                    utility = self._damage_value(operator_id) if constraint.constraint_type == "PROVIDE_DAMAGE_BEFORE" else self._placement_value(operator_id)
                    rank = (-len(covered_routes), -utility,
                            self._effective_cost(operator_id), operator_id, assignment.tile, direction)
                    all_candidates.append((rank, assignment))
        # Remove exact spatial duplicates whose direction has no different
        # covered required route, retaining a deterministic representative.
        unique: dict[tuple, tuple[tuple, AssignedPlacement]] = {}
        for rank, assignment in all_candidates:
            key = (assignment.operator_id, assignment.tile, assignment.covered_routes)
            unique.setdefault(key, (rank, assignment))
        selected: list[AssignedPlacement] = []
        per_operator: dict[str, int] = {}
        for _, assignment in sorted(unique.values(), key=lambda item: item[0]):
            if per_operator.get(assignment.operator_id, 0) >= 2:
                continue
            selected.append(assignment); per_operator[assignment.operator_id] = per_operator.get(assignment.operator_id, 0) + 1
            if len(selected) == 16:
                break
        return selected

    def _schedule(self, assignments: tuple[AssignedPlacement, ...]) -> tuple[Action, ...] | None:
        """Exact frame DP schedule including already-supported DP skill events."""
        dp = float(self.engine.fixture.stage.initial_dp.value or 0)
        rate = float(self.engine.fixture.stage.dp_per_second)
        cursor = 0
        actions: list[Action] = []
        pending: list[tuple[int, str, float, bool]] = []  # frame, operator, amount, auto
        deployed: set[str] = set()
        for assigned in assignments:
            operator = self.engine.fixture.operators[assigned.operator_id]
            cost = self._effective_cost(assigned.operator_id)
            start = cursor + (1 if actions else 0)
            while True:
                natural = start + (ceil(max(0.0, cost - (dp + rate * (start - cursor) / 30.0)) / rate * 30.0) if rate else 10**9)
                available = sorted(item for item in pending if item[0] >= cursor)
                if available and available[0][0] <= natural:
                    frame, source, amount, automatic = available[0]
                    dp += rate * (frame - cursor) / 30.0 + amount; cursor = frame
                    pending.remove(available[0])
                    if not automatic:
                        actions.append(Action(ActionType.ACTIVATE_SKILL, Fraction(frame, 30), source))
                    start = frame
                    continue
                frame = natural; dp += rate * (frame - cursor) / 30.0; cursor = frame
                break
            if frame < 0 or dp + 1e-9 < cost:
                self.metrics.dp_infeasible_assignments += 1
                return None
            dp -= cost
            actions.append(Action(ActionType.DEPLOY, Fraction(frame, 30), assigned.operator_id, assigned.tile, assigned.direction))
            deployed.add(assigned.operator_id)
            skill = operator.synthetic_skill
            if skill and skill.effect.dp_immediate:
                ready = frame + ceil(max(0.0, skill.sp_cost - skill.initial_sp) * 30.0)
                pending.append((ready, assigned.operator_id, skill.effect.dp_immediate, skill.auto_activate))
        return tuple(sorted(actions, key=lambda item: (item.time, 0 if item.action_type is ActionType.ACTIVATE_SKILL else 1, item.operator_id)))

    def _satisfies_deadline(self, actions: tuple[Action, ...], assignment: AssignedPlacement, constraint: TacticalConstraint) -> bool:
        deploy = next(item for item in actions if item.action_type is ActionType.DEPLOY and item.operator_id == assignment.operator_id)
        return self.engine.config.frame_clock.frame_for_seconds(deploy.time) <= constraint.deadline_frame

    def _expand(self, partial: PartialStrategy, constraint: TacticalConstraint) -> list[PartialStrategy]:
        children: list[PartialStrategy] = []
        all_constraints = partial.constraints
        if constraint.constraint_id not in {item.constraint_id for item in all_constraints}:
            all_constraints = (*all_constraints, constraint)
        active = tuple(item for item in all_constraints if item.constraint_id not in set(partial.satisfied_constraints))
        for assigned in self._placement_candidates(partial, constraint, active):
            scheduled = self._schedule((*partial.assignments, assigned))
            if scheduled is None or (constraint.hard_deadline and not self._satisfies_deadline(scheduled, assigned, constraint)):
                self.metrics.dp_infeasible_assignments += 1
                continue
            deploy_frame = self.engine.config.frame_clock.frame_for_seconds(next(
                item.time for item in scheduled
                if item.action_type is ActionType.DEPLOY and item.operator_id == assigned.operator_id
            ))
            newly_satisfied = tuple(
                item.constraint_id for item in active
                if set(item.routes).intersection(assigned.covered_routes)
                and (not item.hard_deadline or deploy_frame <= item.deadline_frame)
            )
            if constraint.constraint_id not in newly_satisfied:
                self.metrics.dp_infeasible_assignments += 1
                continue
            frozen_prefix, frozen_until = partial.frozen_prefix, partial.frozen_until_frame
            if frozen_prefix:
                prefix = tuple(_action_key(item, self.engine) for item in scheduled if self.engine.config.frame_clock.frame_for_seconds(item.time) <= partial.frozen_until_frame)
                if prefix != frozen_prefix:
                    # A new pre-frontier deployment changes DP consumption and
                    # therefore invalidates the formerly successful prefix.
                    # It is a legitimate repair for an early leak, not an
                    # impossible candidate.  Drop the freeze explicitly and
                    # let the simulator re-verify the rebuilt opening.
                    self.metrics.prefix_invalidations += 1
                    self.prefix_history.append({"event": "INVALIDATED", "reason": "new assignment introduced or rescheduled an action inside frozen prefix", "constraint": constraint.constraint_id})
                    frozen_prefix, frozen_until = (), 0
            self.metrics.candidates_generated += 1
            children.append(PartialStrategy((*partial.assignments, assigned),
                                            tuple(dict.fromkeys((*partial.satisfied_constraints, *newly_satisfied))),
                                            all_constraints, scheduled,
                                            frozen_prefix, frozen_until))
        return children

    def _partial_rank(self, partial: PartialStrategy) -> tuple:
        coverage = sum(len(item.covered_routes) for item in partial.assignments)
        power = sum(self._placement_value(item.operator_id) for item in partial.assignments)
        return (-coverage, -power, len(partial.assignments),
                tuple((item.operator_id, item.tile, item.direction) for item in partial.assignments))

    def _select_partials(self, candidates: list[PartialStrategy]) -> list[PartialStrategy]:
        seen: dict[tuple[str, ...], int] = {}; out = []
        for item in sorted(candidates, key=self._partial_rank):
            key = tuple(sorted(entry.operator_id for entry in item.assignments))
            # Retain at most two spatial skeletons per team fingerprint while
            # preventing timing-near duplicates from consuming the whole beam.
            if seen.get(key, 0) >= 2:
                continue
            seen[key] = seen.get(key, 0) + 1; out.append(item)
            if len(out) == self.beam_width:
                break
        return out

    def _frontier(self, partial: PartialStrategy, result: SimulationResult) -> FailureFrontier:
        spawns = {event.source_id: event for event in result.events if event.event_type is EventType.SPAWN}
        leak = next((event for event in result.events if event.event_type is EventType.ENEMY_LEAK), None)
        if leak:
            spawned = spawns.get(leak.source_id); details = dict(spawned.details) if spawned else {}
            route = str(details.get("route_id", "UNKNOWN")); enemy = str(details.get("enemy_id", "UNKNOWN"))
            frame = self.engine.config.frame_clock.frame_for_seconds(leak.time)
            already = any(route in assigned.covered_routes for assigned in partial.assignments)
            kind = "PROVIDE_DAMAGE_BEFORE" if already else "INTERACT_WITH_ROUTE_BEFORE"
            capabilities = ("DAMAGE",) if already else ("BLOCK_OR_RANGED_COVERAGE",)
            return FailureFrontier(frame, FailureType.EARLY_LEAK if frame <= 900 else FailureType.ROUTE_UNCOVERED,
                                   (route,), (enemy,), (), (), capabilities, "UNKNOWN",
                                   int(self.engine.fixture.stage.deployment_limit.value or 0) - len(partial.assignments),
                                   (f"enemy {enemy} leaked on {route} at frame {frame}", f"derived repair constraint {kind}"), "DERIVED")
        death = next((event for event in result.events if event.event_type is EventType.OPERATOR_DEATH), None)
        if death:
            frame = self.engine.config.frame_clock.frame_for_seconds(death.time)
            return FailureFrontier(frame, FailureType.OPERATOR_DEATH, (), (), (death.source_id or "UNKNOWN",), (),
                                   ("HEALING_OR_SURVIVABILITY",), "UNKNOWN", None,
                                   (f"operator {death.source_id} died at frame {frame}",), "EXACT")
        return FailureFrontier(self.engine.config.frame_clock.frame_for_seconds(result.time_survived), FailureType.DAMAGE_INSUFFICIENT,
                               (), (), (), (), ("DAMAGE",), "UNKNOWN", None,
                               ("simulation ended without WIN, leak, or operator-death event",), "UNKNOWN")

    def _constraint_from_frontier(self, frontier: FailureFrontier, iteration: int) -> TacticalConstraint:
        return TacticalConstraint(
            f"FRONTIER_{iteration}_{frontier.failure_type.value}_{'_'.join(frontier.routes) or 'GLOBAL'}_{frontier.frame // 30}",
            "PROVIDE_DAMAGE_BEFORE" if frontier.required_capabilities == ("DAMAGE",) else "INTERACT_WITH_ROUTE_BEFORE",
            frontier.routes, frontier.frame, frontier.required_capabilities, frontier.relevant_tiles,
            False, frontier.confidence, frontier.evidence,
        )

    def _evaluate(self, partial: PartialStrategy) -> tuple[SimulationResult, FailureFrontier]:
        evaluation = self.engine._evaluate(Strategy(tuple(item.operator_id for item in partial.assignments), partial.actions), self.sim_metrics)
        result = evaluation.result; frontier = self._frontier(partial, result)
        self.metrics.unique_simulations = self.sim_metrics.unique_simulations; self.metrics.cache_hits = self.sim_metrics.cache_hits
        return result, frontier

    def _result_rank(self, item: tuple[PartialStrategy, SimulationResult, FailureFrontier]) -> tuple:
        partial, result, frontier = item
        rarity = sum(int(self.engine.fixture.operators[x.operator_id].star_rarity.value or 0) for x in partial.assignments)
        return (0 if result.win else 1, -frontier.frame, result.enemies_leaked, -result.enemies_killed,
                -result.remaining_life, len(partial.assignments), rarity)

    def _freeze(self, partial: PartialStrategy, frontier: FailureFrontier) -> PartialStrategy:
        boundary = max(0, frontier.frame - 30)
        prefix = tuple(_action_key(item, self.engine) for item in partial.actions if self.engine.config.frame_clock.frame_for_seconds(item.time) <= boundary)
        if prefix and prefix != partial.frozen_prefix:
            self.metrics.prefix_freezes += 1
            self.prefix_history.append({"event": "FROZEN", "until_frame": boundary, "actions": list(prefix), "failure_frame": frontier.frame})
            return replace(partial, frozen_prefix=prefix, frozen_until_frame=boundary)
        return partial

    def _row(self, partial: PartialStrategy, result: SimulationResult, frontier: FailureFrontier, iteration: int) -> dict:
        return {
            "iteration": iteration, "team": [item.operator_id for item in partial.assignments],
            "operator_count": len(partial.assignments),
            "rarity": sum(int(self.engine.fixture.operators[item.operator_id].star_rarity.value or 0) for item in partial.assignments),
            "actions": [{"type": item.action_type.value, "operator_id": item.operator_id,
                         "frame": self.engine.config.frame_clock.frame_for_seconds(item.time), "tile": item.tile, "direction": item.direction} for item in partial.actions],
            "result": "WIN" if result.win else "LOSS", "kills": result.enemies_killed, "leaks": result.enemies_leaked,
            "remaining_life": result.remaining_life, "first_failure_frame": frontier.frame,
            "failure_frontier": self._frontier_dict(frontier), "final_dp": result.final_dp,
        }

    @staticmethod
    def _frontier_dict(item: FailureFrontier) -> dict:
        return {"frame": item.frame, "failure_type": item.failure_type.value, "routes": list(item.routes),
                "enemy_ids": list(item.enemy_ids), "affected_operator_ids": list(item.affected_operator_ids),
                "relevant_tiles": list(item.relevant_tiles), "required_capabilities": list(item.required_capabilities),
                "dp_state": item.dp_state, "deployment_slots": item.deployment_slots,
                "evidence": list(item.evidence), "confidence": item.confidence}

    @staticmethod
    def _constraint_dict(item: TacticalConstraint) -> dict:
        return {"constraint_id": item.constraint_id, "constraint_type": item.constraint_type, "routes": list(item.routes),
                "deadline_frame": item.deadline_frame, "required_capabilities": list(item.required_capabilities),
                "relevant_tiles": list(item.relevant_tiles), "hard_deadline": item.hard_deadline,
                "provenance": item.provenance, "evidence": list(item.evidence)}

    def run(self) -> dict:
        started = perf_counter()
        initial = self.initial_constraints()
        self.constraints = list(initial)
        frontier = [PartialStrategy(constraints=initial)]
        # Satisfy the earliest unresolved opening constraint, while allowing
        # one placement to satisfy both initial routes.  This is a constrained
        # set-cover step, not roster enumeration.
        for _ in range(len(initial)):
            children: list[PartialStrategy] = []
            for partial in frontier:
                unresolved = self._unsatisfied_constraints(partial)
                if not unresolved:
                    children.append(partial)
                    continue
                constraint = min(unresolved, key=lambda item: (item.deadline_frame, item.constraint_id))
                children.extend(self._expand(partial, constraint))
            frontier = self._select_partials(children)
            if not frontier or all(not self._unsatisfied_constraints(item) for item in frontier):
                break
        evaluated: list[tuple[PartialStrategy, SimulationResult, FailureFrontier]] = []
        seen_constraint_ids = {item.constraint_id for item in initial}
        # The final iteration must evaluate K=max_cardinality after expanding
        # a K-1 partial; otherwise K=7 would never be simulated.
        for iteration in range(1, self.max_cardinality + 1):
            if not frontier or self.metrics.unique_simulations >= self.simulation_budget:
                break
            round_results: list[tuple[PartialStrategy, SimulationResult, FailureFrontier]] = []
            for partial in frontier:
                if self.metrics.unique_simulations >= self.simulation_budget:
                    break
                result, failed = self._evaluate(partial)
                frozen = self._freeze(partial, failed)
                round_results.append((frozen, result, failed)); evaluated.append((frozen, result, failed))
                self.frontiers.append({"iteration": iteration, **self._frontier_dict(failed)})
                if result.win:
                    break
            if not round_results:
                break
            best_round = min(round_results, key=self._result_rank)
            self.progress.append({"iteration": iteration, "simulations": len(round_results),
                                  "best": self._row(*best_round, iteration)})
            if best_round[1].win:
                break
            expansions: list[PartialStrategy] = []
            for partial, result, failed in sorted(round_results, key=self._result_rank):
                if len(partial.assignments) >= self.max_cardinality:
                    continue
                constraint = self._constraint_from_frontier(failed, iteration)
                if constraint.constraint_id in seen_constraint_ids:
                    self.rejections.append({"iteration": iteration, "reason": "repeated failure-frontier constraint", "constraint": self._constraint_dict(constraint)})
                    continue
                seen_constraint_ids.add(constraint.constraint_id); self.metrics.constraints_generated += 1
                self.constraints.append(constraint)
                expansions.extend(self._expand(partial, constraint))
            frontier = self._select_partials(expansions)
        if not evaluated:
            best = None
        else:
            best = min(evaluated, key=self._result_rank)
        self.metrics.unique_simulations = self.sim_metrics.unique_simulations; self.metrics.cache_hits = self.sim_metrics.cache_hits
        best_row = self._row(*best, len(self.progress)) if best else None
        timeline = human = robustness = None
        if best and best[1].win:
            best_partial, result, _ = best
            timeline_object = strategy_to_timeline(Strategy(tuple(item.operator_id for item in best_partial.assignments), best_partial.actions),
                                                   stage_id=self.engine.fixture.stage.stage_id, frame_clock=self.engine.config.frame_clock,
                                                   simulator_mode="APPROXIMATE_REAL", approximation_policy_version=self.policy.cache_identity[0])
            robustness = self.engine._robustness(self.engine._evaluate(Strategy(tuple(item.operator_id for item in best_partial.assignments), best_partial.actions), self.sim_metrics), self.sim_metrics)
            timeline = timeline_object.to_dict()
            human = render_human_timeline(timeline=timeline_object, repository=self.adapter.repository, simulator_result="WIN",
                                          robustness=str(robustness), approximation_warnings=self.engine.fixture.approximations_used)
        comparison = {"m14_best": {"kills": 27, "leaks": 9, "first_leak_frame": 366, "remaining_life": -6},
                      "m15_best": best_row,
                      "classification": ("INCONCLUSIVE" if best_row is None else
                                         "IMPROVED" if best_row["result"] == "WIN" or best_row["kills"] > 27 or best_row["leaks"] < 9 else
                                         "MATCHED" if best_row["kills"] == 27 and best_row["leaks"] == 9 else "REGRESSED")}
        return {
            "m15_stage_constraints": {"stage": self.engine.fixture.stage.stage_id, "initial_constraints": [self._constraint_dict(item) for item in initial],
                                        "all_constraints": [self._constraint_dict(item) for item in self.constraints],
                                        "operator_pool": sorted(self.configurations), "max_cardinality": self.max_cardinality, "beam_width": self.beam_width,
                                        "simulation_budget": self.simulation_budget, "llm_calls": 0},
            "m15_search_progress": self.progress,
            "m15_failure_frontiers": self.frontiers,
            "m15_assignment_stats": {**self.metrics.__dict__, "rejections": self.rejections},
            "m15_prefix_history": self.prefix_history,
            "m15_results": {"best": best_row, "termination": "WIN_FOUND" if best and best[1].win else "NO_WIN_FOUND_BOUNDED", "simulator_elapsed_seconds": perf_counter() - started,
                            "timeline": timeline, "robustness": robustness, "human_timeline": human},
            "m15_baseline_comparison": comparison,
        }
