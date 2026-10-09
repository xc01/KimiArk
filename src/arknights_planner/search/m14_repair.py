"""M14.5 bounded feasibility-first repair around preserved R1/R4 priors.

This is deliberately not a roster or cardinality enumerator.  It mutates two
known full-team tactical structures locally and lets the deterministic simulator
rank LOSS progress only while looking for a first WIN.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.simulation import EventType, SimulationResult
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m11 import M11Evaluation, M11MinimumSquadSearch, M11SearchConfig, M11SearchMetrics
from arknights_planner.search.m14_ground import CardinalityAuditTeam, _operator_capabilities, ground_cardinality_audit
from arknights_planner.timing import strategy_to_timeline


@dataclass(frozen=True)
class RepairCandidate:
    source_hypothesis: str
    mutation: str
    strategy: Strategy
    result: SimulationResult


def _details(event) -> dict:
    return dict(event.details)


def _first_event(result: SimulationResult, kind: EventType):
    return next((event for event in result.events if event.event_type is kind), None)


def _first_leak_frame(result: SimulationResult, engine: M11MinimumSquadSearch) -> int:
    event = _first_event(result, EventType.ENEMY_LEAK)
    return engine.config.frame_clock.frame_for_seconds(event.time) if event else 10**9


def _loss_rank(candidate: RepairCandidate, engine: M11MinimumSquadSearch) -> tuple:
    """Diagnostic ordering only. It is never the benchmark's final objective."""
    result = candidate.result
    return (
        0 if result.win else 1,
        result.enemies_leaked,
        -result.enemies_killed,
        -_first_leak_frame(result, engine),
        -result.remaining_life,
        result.operator_deaths,
        tuple((action.operator_id, action.time, action.tile, action.direction) for action in candidate.strategy.actions),
    )


def _strategy_key(strategy: Strategy) -> tuple:
    return tuple((action.action_type.value, action.operator_id, action.time, action.tile, action.direction) for action in strategy.actions)


def _operator_actions(strategy: Strategy) -> tuple[Action, ...]:
    return tuple(action for action in strategy.actions if action.action_type is ActionType.DEPLOY)


def _leak_analysis(source: str, evaluation: M11Evaluation, engine: M11MinimumSquadSearch) -> dict:
    result = evaluation.result
    spawn_by_instance = {event.source_id: event for event in result.events if event.event_type is EventType.SPAWN}
    damage_by_target: dict[str, list] = {}
    attacks_by_target: dict[str, list] = {}
    blocks_by_target: dict[str, list] = {}
    for event in result.events:
        if event.event_type is EventType.DAMAGE and event.target_id:
            damage_by_target.setdefault(event.target_id, []).append(event)
        elif event.event_type is EventType.ATTACK_START and event.target_id:
            attacks_by_target.setdefault(event.target_id, []).append(event)
        elif event.event_type in {EventType.BLOCK, EventType.UNBLOCK} and event.target_id:
            blocks_by_target.setdefault(event.target_id, []).append(event)
    leaks = []
    for event in (item for item in result.events if item.event_type is EventType.ENEMY_LEAK):
        spawn = spawn_by_instance.get(event.source_id)
        spawn_data = _details(spawn) if spawn else {}
        enemy_id = spawn_data.get("enemy_id")
        enemy = engine.fixture.enemies.get(enemy_id) if enemy_id else None
        received = sum(float(_details(item).get("amount", 0)) for item in damage_by_target.get(event.source_id, ()) if item.source_id in engine.fixture.operators)
        hp = float(enemy.stats.max_hp.value) if enemy and enemy.stats.max_hp.value is not None else None
        leaks.append({
            "enemy_instance_id": event.source_id,
            "enemy_id": enemy_id or "UNKNOWN",
            "spawn_frame": engine.config.frame_clock.frame_for_seconds(spawn.time) if spawn else None,
            "route_id": spawn_data.get("route_id", "UNKNOWN"),
            "leak_frame": engine.config.frame_clock.frame_for_seconds(event.time),
            "damage_received": received,
            "hp_at_leak": max(0.0, hp - received) if hp is not None else "UNKNOWN",
            "attackers": sorted({item.source_id for item in attacks_by_target.get(event.source_id, ()) if item.source_id in engine.fixture.operators}),
            "block_contact_history": [{"frame": engine.config.frame_clock.frame_for_seconds(item.time), "event": item.event_type.value, "operator_id": item.source_id} for item in blocks_by_target.get(event.source_id, ())],
        })
    groups: dict[tuple, int] = {}
    for item in leaks:
        hp_bucket = "UNKNOWN" if item["hp_at_leak"] == "UNKNOWN" else f"{int(float(item['hp_at_leak']) // 500) * 500}-{int(float(item['hp_at_leak']) // 500) * 500 + 499}"
        key = (item["route_id"], item["enemy_id"], f"{item['leak_frame'] // 300 * 10}-{item['leak_frame'] // 300 * 10 + 9}s", hp_bucket)
        groups[key] = groups.get(key, 0) + 1
    legal_deploys = [event for event in result.events if event.event_type is EventType.DEPLOY and _details(event).get("legal") is True]
    first_leak = _first_event(result, EventType.ENEMY_LEAK)
    first_death = _first_event(result, EventType.OPERATOR_DEATH)
    first_attack = next((event for event in result.events if event.event_type is EventType.ATTACK_START and event.source_id in engine.fixture.operators), None)
    first_spawn = _first_event(result, EventType.SPAWN)
    frontline = next((event for event in legal_deploys if engine.fixture.operators[event.source_id].position.value == "MELEE"), None)
    early = bool(first_leak and (frontline is None or first_leak.time < frontline.time))
    return {
        "source_hypothesis": source,
        "leaked_enemies": leaks,
        "groups": [{"route_id": key[0], "enemy_id": key[1], "time_bucket": key[2], "hp_at_leak_bucket": key[3], "count": value} for key, value in sorted(groups.items())],
        "first_divergence": {
            "first_leak_frame": engine.config.frame_clock.frame_for_seconds(first_leak.time) if first_leak else None,
            "first_operator_death_frame": engine.config.frame_clock.frame_for_seconds(first_death.time) if first_death else None,
            "first_overloaded_blocker": "UNKNOWN (runtime emits no rejected-block event)",
            "first_route_losing_coverage": "UNKNOWN (runtime does not emit coverage state)",
            "first_idle_dps_window": {"from_frame": engine.config.frame_clock.frame_for_seconds(first_spawn.time) if first_spawn else None, "to_frame": engine.config.frame_clock.frame_for_seconds(first_attack.time) if first_attack else None} if first_spawn and first_attack else "UNKNOWN",
            "early_leak_before_frontline": early,
        },
        "dominant_failure": "EARLY_FRONTLINE_OR_DEPLOYMENT_SEQUENCE" if early else "MIXED_OR_UNKNOWN",
    }


class M14LocalRepairSearch:
    """Small beam/hill-climb confined to two preserved tactical structures."""
    def __init__(self, *, adapter: ApproximateRealSimulationAdapter, hypotheses, policy: RealSimulationApproximationPolicy, budget: int = 1500, beam_width: int = 8):
        self.adapter, self.hypotheses, self.policy = adapter, tuple(hypotheses), policy
        self.budget, self.beam_width = budget, beam_width
        configurations = adapter.m13_low_rarity_configurations()
        self.configurations = {item.operator_id: item for item in configurations}
        self.engine = M11MinimumSquadSearch(
            adapter=adapter, stage_id_or_code="6-8", policy=policy, operator_pool=configurations,
            config=M11SearchConfig(max_squad_size=7, max_teams=1, placement_options_per_operator=24, beam_width=2),
        )
        self.metrics = M11SearchMetrics()
        self.generated = 0
        self.structural_rejections = 0
        self.mutation_attempts = {name: 0 for name in ("team", "spatial", "facing", "order", "timing", "skill", "retreat")}
        self.mutation_counts = {name: 0 for name in ("team", "spatial", "facing", "order", "timing", "skill", "retreat")}

    def _static_legal(self, strategy: Strategy) -> bool:
        deployments = _operator_actions(strategy)
        if len({item.operator_id for item in deployments}) != len(deployments) or len({item.tile for item in deployments}) != len(deployments):
            return False
        dp = float(self.engine.fixture.stage.initial_dp.value or 0)
        previous = 0.0
        for action in deployments:
            if action.time < previous:
                return False
            operator = self.engine.fixture.operators.get(action.operator_id)
            if operator is None or self.engine.simulator._deployment_tile_reason(operator, self.engine.fixture.stage, action.tile):
                return False
            dp += self.engine.fixture.stage.dp_per_second * (action.time - previous)
            previous = action.time
            cost = float(operator.phases[0].stats_max.cost.value or 0)
            if dp + 1e-9 < cost:
                return False
            dp -= cost
        return len(deployments) <= int(self.engine.fixture.stage.deployment_limit.value or 0)

    def _reschedule(self, actions: tuple[Action, ...]) -> Strategy:
        dp = float(self.engine.fixture.stage.initial_dp.value or 0)
        rate = float(self.engine.fixture.stage.dp_per_second)
        current_seconds = 0.0
        rebuilt = []
        for action in actions:
            operator = self.engine.fixture.operators[action.operator_id]
            cost = float(operator.phases[0].stats_max.cost.value or 0)
            required = max(0.0, (cost - dp) / rate) if rate > 0 else 0.0
            current_frame = ceil((current_seconds + required) * float(self.engine.config.frame_clock.frames_per_second))
            seconds = self.engine.config.frame_clock.seconds_for_frame(current_frame)
            dp += rate * (float(seconds) - current_seconds)
            dp -= cost
            rebuilt.append(Action(ActionType.DEPLOY, seconds, action.operator_id, action.tile, action.direction))
            # Preserve a Fraction at the strategy/frame boundary. A full
            # one-second separation is conservative and frame-exact.
            current_seconds = float(seconds) + 1.0
        return Strategy(tuple(action.operator_id for action in rebuilt), tuple(rebuilt))

    def _focus_indices(self, candidate: RepairCandidate) -> tuple[int, ...]:
        failure = _first_leak_frame(candidate.result, self.engine)
        limit = failure + 180
        indices = tuple(index for index, action in enumerate(candidate.strategy.actions) if action.action_type is ActionType.DEPLOY and self.engine.config.frame_clock.frame_for_seconds(action.time) <= limit)
        return indices or tuple(index for index, action in enumerate(candidate.strategy.actions) if action.action_type is ActionType.DEPLOY)[:1]

    def _spatial_options(self, operator_id: str, occupied: set[tuple[int, int]], current: Action) -> tuple:
        distinct = []
        seen = set()
        for option in self.engine.deployment_options():
            if option.operator_id != operator_id or option.tile in occupied or (option.tile, option.direction) == (current.tile, current.direction):
                continue
            if option.tile in seen:
                continue
            distinct.append(option); seen.add(option.tile)
            if len(distinct) == 2:
                break
        return tuple(distinct)

    def _replacement_ids(self, operator_id: str, strategy: Strategy, source_hypothesis) -> tuple[str, ...]:
        current = self.engine.fixture.operators[operator_id]
        current_caps = set(_operator_capabilities(self.adapter, operator_id))
        candidates = list(source_hypothesis.alternative_operator_ids) + sorted(self.configurations)
        out = []
        for candidate in candidates:
            if candidate in strategy.team or candidate not in self.configurations:
                continue
            other = self.engine.fixture.operators[candidate]
            if other.position != current.position:
                continue
            caps = set(_operator_capabilities(self.adapter, candidate))
            if not (caps & current_caps) and not (current.position.value == "MELEE" and "EARLY_DEPLOYMENT" in caps):
                continue
            out.append(candidate)
        return tuple(dict.fromkeys(out))[:2]

    def _mutations(self, candidate: RepairCandidate, source_hypothesis) -> tuple[tuple[str, Strategy], ...]:
        deploys = _operator_actions(candidate.strategy)
        focus = self._focus_indices(candidate)
        out: list[tuple[str, Strategy]] = []
        # Swap only adjacent steps, plus an evidence-driven ground-first repair.
        for index in range(len(deploys) - 1):
            revised = list(deploys); revised[index], revised[index + 1] = revised[index + 1], revised[index]
            out.append(("order", self._reschedule(tuple(revised))))
        ground_first = tuple(sorted(deploys, key=lambda item: (self.engine.fixture.operators[item.operator_id].position.value != "MELEE", deploys.index(item))))
        if ground_first != deploys:
            out.append(("order", self._reschedule(ground_first)))
        for index in focus:
            action = deploys[index]
            frame = self.engine.config.frame_clock.frame_for_seconds(action.time)
            for delta in (-90, -30, -10, 10, 30, 90):
                changed = list(deploys); changed[index] = Action(ActionType.DEPLOY, self.engine.config.frame_clock.seconds_for_frame(max(0, frame + delta)), action.operator_id, action.tile, action.direction)
                out.append(("timing", Strategy(candidate.strategy.team, tuple(sorted(changed, key=lambda item: item.time)))))
            occupied = {item.tile for offset, item in enumerate(deploys) if offset != index}
            for option in self._spatial_options(action.operator_id, occupied, action):
                changed = list(deploys); changed[index] = Action(ActionType.DEPLOY, action.time, action.operator_id, option.tile, option.direction)
                out.append(("spatial", Strategy(candidate.strategy.team, tuple(changed))))
            for option in (item for item in self.engine.deployment_options() if item.operator_id == action.operator_id and item.tile == action.tile and item.direction != action.direction):
                changed = list(deploys); changed[index] = Action(ActionType.DEPLOY, action.time, action.operator_id, action.tile, option.direction)
                out.append(("facing", Strategy(candidate.strategy.team, tuple(changed))))
                break
            for replacement in self._replacement_ids(action.operator_id, candidate.strategy, source_hypothesis):
                changed = list(deploys); changed[index] = Action(ActionType.DEPLOY, action.time, replacement, action.tile, action.direction)
                out.append(("team", self._reschedule(tuple(changed))))
        # A supported manual time-SP skill may be activated only after its
        # source-backed readiness point. The R1/R4 prose does not require one.
        for action in deploys:
            skill = self.engine.fixture.operators[action.operator_id].synthetic_skill
            if skill is None:
                continue
            ready = self.engine.config.frame_clock.frame_for_seconds(action.time) + ceil(max(0.0, skill.sp_cost - skill.initial_sp) / skill.sp_per_second * float(self.engine.config.frame_clock.frames_per_second))
            for frame in (ready, ready + 90):
                out.append(("skill", Strategy(candidate.strategy.team, tuple(sorted((*deploys, Action(ActionType.ACTIVATE_SKILL, self.engine.config.frame_clock.seconds_for_frame(frame), action.operator_id)), key=lambda item: item.time)))))
        return tuple(out)

    def _evaluate(self, source: str, mutation: str, strategy: Strategy) -> RepairCandidate | None:
        self.generated += 1
        self.mutation_attempts[mutation] += 1
        if not self._static_legal(strategy):
            self.structural_rejections += 1
            return None
        before = self.metrics.unique_simulations
        evaluation = self.engine._evaluate(strategy, self.metrics)
        if self.metrics.unique_simulations > before:
            self.mutation_counts[mutation] += 1
        return RepairCandidate(source, mutation, strategy, evaluation.result)

    def _select_diverse(self, candidates: list[RepairCandidate]) -> list[RepairCandidate]:
        selected = []
        seen = set()
        for candidate in sorted(candidates, key=lambda item: _loss_rank(item, self.engine)):
            failure_bucket = _first_leak_frame(candidate.result, self.engine) // 90
            fingerprint = (tuple(sorted(candidate.strategy.team)), tuple((item.tile, item.direction) for item in candidate.strategy.actions if item.action_type is ActionType.DEPLOY), failure_bucket)
            if fingerprint in seen:
                continue
            seen.add(fingerprint); selected.append(candidate)
            if len(selected) == self.beam_width:
                break
        return selected

    def run(self) -> dict:
        audit_teams, _ = ground_cardinality_audit(self.hypotheses, self.adapter)
        parents = [item for item in audit_teams if item.variant == "FULL" and item.hypothesis_id in {"R1", "R4"}]
        initial: list[RepairCandidate] = []
        leak_analysis = []
        parent_simulations = 0
        for item in parents:
            outcome = self.engine.search_ordered_fixed_team(item.operators, item.deployment_order)
            parent_simulations += outcome.metrics.unique_simulations
            if outcome.best is None:
                continue
            candidate = RepairCandidate(item.hypothesis_id, "initial", outcome.best.strategy, outcome.best.result)
            initial.append(candidate)
            leak_analysis.append(_leak_analysis(item.hypothesis_id, outcome.best, self.engine))
        frontier = self._select_diverse(initial)
        best = min(frontier, key=lambda item: _loss_rank(item, self.engine)) if frontier else None
        progress = [self._row(item, parent_simulations, "initial") for item in frontier]
        visited = {_strategy_key(item.strategy) for item in frontier}
        no_improvement = 0
        local_neighborhood_exhausted = False
        iteration = 0
        hypothesis_by_id = {item.hypothesis_id: item for item in self.hypotheses}
        while frontier and parent_simulations + self.metrics.unique_simulations < self.budget and no_improvement < 300 and iteration < 12:
            iteration += 1
            children: list[RepairCandidate] = []
            for parent in frontier:
                for mutation, strategy in self._mutations(parent, hypothesis_by_id[parent.source_hypothesis]):
                    key = _strategy_key(strategy)
                    if key in visited:
                        continue
                    visited.add(key)
                    if parent_simulations + self.metrics.unique_simulations >= self.budget:
                        break
                    before = self.metrics.unique_simulations
                    child = self._evaluate(parent.source_hypothesis, mutation, strategy)
                    unique_delta = self.metrics.unique_simulations - before
                    if child:
                        children.append(child)
                        if best is None or _loss_rank(child, self.engine) < _loss_rank(best, self.engine):
                            best = child
                            progress.append(self._row(child, parent_simulations + self.metrics.unique_simulations, f"iteration-{iteration}"))
                            no_improvement = 0
                        else:
                            no_improvement += unique_delta
            if best and best.result.win:
                break
            frontier = self._select_diverse(children + frontier)
            if not children:
                local_neighborhood_exhausted = True
                break
        total_unique = parent_simulations + self.metrics.unique_simulations
        result_rows = [self._row(item, None, item.mutation) for item in sorted(frontier + ([best] if best and best not in frontier else []), key=lambda item: _loss_rank(item, self.engine))]
        winner_timeline = None
        winner_robustness = ()
        if best and best.result.win:
            evaluation = self.engine._evaluate(best.strategy, self.metrics)
            winner_robustness = self.engine._robustness(evaluation, self.metrics)
            winner_timeline = strategy_to_timeline(best.strategy, stage_id=self.engine.fixture.stage.stage_id,
                                                   frame_clock=self.engine.config.frame_clock,
                                                   simulator_mode="APPROXIMATE_REAL",
                                                   approximation_policy_version="m11-second-quantized-v1").to_dict()
            total_unique = parent_simulations + self.metrics.unique_simulations
        return {
            "parents": [self._row(item, None, "initial") for item in initial],
            "leak_analysis": leak_analysis,
            "progress": progress,
            "final_best": self._row(best, total_unique, "final") if best else None,
            "frontier": result_rows,
            "metrics": {"llm_calls": 0, "unique_simulations": total_unique, "cache_hits": self.metrics.cache_hits, "candidates_generated": self.generated, "structural_rejections": self.structural_rejections, "mutation_attempts": self.mutation_attempts, "mutation_simulations": self.mutation_counts, "budget": self.budget, "iterations": iteration},
            "plateau": {"status": "WIN_FOUND" if best and best.result.win else ("PLATEAU" if local_neighborhood_exhausted or no_improvement >= 300 else "SEARCH_BOUND_REACHED"), "evaluations_since_last_improvement": no_improvement, "dominant_failure": "EARLY_FRONTLINE_OR_DEPLOYMENT_SEQUENCE" if best and _first_leak_frame(best.result, self.engine) <= 336 else "MIXED_OR_UNKNOWN"},
            "winner_timeline": winner_timeline,
            "winner_robustness": winner_robustness,
        }

    def _row(self, candidate: RepairCandidate | None, evaluation: int | None, label: str) -> dict | None:
        if candidate is None:
            return None
        result = candidate.result
        return {"source_hypothesis": candidate.source_hypothesis, "mutation": candidate.mutation, "label": label,
                "result": "WIN" if result.win else "LOSS", "operators": candidate.strategy.team,
                "operator_count": len(candidate.strategy.team), "rarity": sum(int(self.adapter.repository.get_operator(item).star_rarity.value or 0) for item in candidate.strategy.team),
                "actions": [{"type": item.action_type.value, "frame": self.engine.config.frame_clock.frame_for_seconds(item.time), "operator_id": item.operator_id, "tile": item.tile, "direction": item.direction} for item in candidate.strategy.actions],
                "kills": result.enemies_killed, "leaks": result.enemies_leaked, "remaining_life": result.remaining_life,
                "attacks": sum(event.event_type is EventType.ATTACK_START and event.source_id in self.engine.fixture.operators for event in result.events),
                "damage_events": sum(event.event_type is EventType.DAMAGE and event.source_id in self.engine.fixture.operators for event in result.events),
                "first_leak_frame": None if _first_leak_frame(result, self.engine) == 10**9 else _first_leak_frame(result, self.engine),
                "first_operator_death_frame": self.engine.config.frame_clock.frame_for_seconds(event.time) if (event := _first_event(result, EventType.OPERATOR_DEATH)) else None,
                "termination_frame": self.engine.config.frame_clock.frame_for_seconds(result.time_survived), "evaluation": evaluation}
