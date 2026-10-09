"""Replay preserved 6-8 strategies after a combat-mechanics rebaseline.

This module deliberately performs no candidate generation or optimization.  It
only turns preserved frame actions back into the configured approximate-real
runtime and records the resulting evidence.
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.models.simulation import EventType, SimulationEvent, SimulationResult
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import ApproximateRealRangeTransformer, InstantProjectileModel, SimulationConfig, Simulator
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION


UNAVAILABLE = "UNAVAILABLE_NOT_PERSISTED"
FPS = 30


def _details(event: SimulationEvent | None) -> dict[str, Any]:
    return dict(event.details) if event else {}


def _frame(time: float) -> int:
    return round(time * FPS)


@dataclass(frozen=True)
class PreservedStrategy:
    name: str
    source: str
    old: dict[str, Any]
    team: tuple[str, ...] = ()
    actions: tuple[dict[str, Any], ...] = ()

    @property
    def available(self) -> bool:
        return bool(self.actions)


class MechanicsRebaseline:
    """A read-only replay of M13--M15.1 historical candidate artifacts."""

    VERSION = "mechanics-rebaseline-v1"

    def __init__(self, *, adapter: ApproximateRealSimulationAdapter, policy: RealSimulationApproximationPolicy, artifact_root: Path):
        self.adapter = adapter
        self.policy = policy
        self.artifact_root = artifact_root
        configurations = adapter.m13_low_rarity_configurations()
        self.fixture = adapter.build_pool_fixture(stage_id_or_code="6-8", configurations=configurations, policy=policy)
        self.simulator = Simulator(range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel())
        self.config = SimulationConfig(dt=0.2, max_time=300.0)

    def _read(self, relative: str) -> dict[str, Any]:
        return json.loads((self.artifact_root / relative).read_text(encoding="utf-8"))

    @staticmethod
    def _old_metrics(row: dict[str, Any], *, frontier_key: str = "earliest_failure_frontier") -> dict[str, Any]:
        frontier = row.get(frontier_key) or row.get("failure_frontier") or {}
        return {
            "result": row.get("result", UNAVAILABLE),
            "kills": row.get("kills", UNAVAILABLE),
            "leaks": row.get("leaks", UNAVAILABLE),
            "remaining_life": row.get("remaining_life", UNAVAILABLE),
            "attacks": row.get("attacks", UNAVAILABLE),
            "damage_events": row.get("damage_events", UNAVAILABLE),
            "total_damage": row.get("total_damage", UNAVAILABLE),
            "first_failure_frontier": {
                "frame": frontier.get("frame", row.get("first_failure_frame", row.get("first_leak_frame", UNAVAILABLE))),
                "route": (frontier.get("routes") or [frontier.get("route", UNAVAILABLE)])[0],
                "failure_type": frontier.get("failure_type", "EARLY_LEAK" if row.get("first_leak_frame") is not None else UNAVAILABLE),
            },
        }

    def preserved_strategies(self) -> tuple[PreservedStrategy, ...]:
        m14 = self._read("m14/main_06-07/opening_economy_full_battle_results.json")["best"]
        m15 = self._read("m15/main_06-07/m15_results.json")["best"]
        m151 = self._read("m15/main_06-07/m15_1_results.json")
        control = self._read("m15/main_06-07/m15_1_unguided_control.json")["result"]
        missing = {
            "result": "NO_WIN_FOUND", "kills": UNAVAILABLE, "leaks": UNAVAILABLE,
            "remaining_life": UNAVAILABLE, "attacks": UNAVAILABLE, "damage_events": UNAVAILABLE,
            "total_damage": UNAVAILABLE, "first_failure_frontier": {"frame": UNAVAILABLE, "route": UNAVAILABLE, "failure_type": UNAVAILABLE},
        }
        return (
            PreservedStrategy("M13_BEST_HISTORICAL", "output/benchmarks/main_06-07/search_summary.json", missing),
            PreservedStrategy("M14_7_BEST", "output/m14/main_06-07/opening_economy_full_battle_results.json", self._old_metrics(m14), tuple(m14["team"]), tuple(m14["actions"])),
            PreservedStrategy("M15_BEST_PARENT", "output/m15/main_06-07/m15_results.json", self._old_metrics(m15), tuple(m15["team"]), tuple(m15["actions"])),
            PreservedStrategy("M15_1_GUIDED_BEST", "output/m15/main_06-07/m15_1_results.json", self._old_metrics(m151["guided"]), tuple(m151["guided"]["operators"]), tuple(m151["guided"]["actions"])),
            PreservedStrategy("M15_1_CONTROL_BEST", "output/m15/main_06-07/m15_1_unguided_control.json", self._old_metrics(control), tuple(control["operators"]), tuple(control["actions"])),
        )

    @staticmethod
    def _strategy(item: PreservedStrategy) -> Strategy:
        actions = tuple(
            Action(ActionType(row["type"]), int(row["frame"]) / FPS, row["operator_id"],
                   tuple(row["tile"]) if row.get("tile") is not None else None, row.get("direction", "RIGHT"))
            for row in item.actions
        )
        return Strategy(item.team, actions)

    def _frontier(self, result: SimulationResult) -> dict[str, Any] | None:
        leak = next((event for event in result.events if event.event_type is EventType.ENEMY_LEAK), None)
        if leak is None:
            return None
        spawns = {event.source_id: event for event in result.events if event.event_type is EventType.SPAWN}
        spawn = spawns.get(leak.source_id)
        return {
            "frame": _frame(leak.time), "route": _details(spawn).get("route_id", "UNKNOWN"),
            "failure_type": "EARLY_LEAK" if _frame(leak.time) <= 900 else "ROUTE_UNCOVERED",
            "enemy_id": _details(spawn).get("enemy_id", "UNKNOWN"), "enemy_instance_id": leak.source_id,
        }

    def _metrics(self, result: SimulationResult, team: tuple[str, ...]) -> dict[str, Any]:
        sources = set(team)
        attacks = [event for event in result.events if event.event_type is EventType.ATTACK_START and event.source_id in sources]
        damage = [event for event in result.events if event.event_type is EventType.DAMAGE and event.source_id in sources]
        return {
            "result": "WIN" if result.win else "LOSS", "kills": result.enemies_killed, "leaks": result.enemies_leaked,
            "remaining_life": result.remaining_life, "attacks": len(attacks), "damage_events": len(damage),
            "total_damage": sum(float(_details(event).get("amount", 0.0)) for event in damage),
            "first_failure_frontier": self._frontier(result),
            "target_selection_summary": self._target_selection_summary(result),
        }

    @staticmethod
    def _target_selection_summary(result: SimulationResult) -> dict[str, Any]:
        selections = [event for event in result.events if event.event_type is EventType.TARGET_SELECTION]
        rules: dict[str, int] = {}
        targets: set[str] = set()
        for event in selections:
            details = _details(event)
            rule = str(details.get("rule", "UNKNOWN"))
            rules[rule] = rules.get(rule, 0) + 1
            if event.target_id:
                targets.add(event.target_id)
        return {
            "selection_events": len(selections),
            "distinct_targets": len(targets),
            "rules": rules,
            "first_selection": {
                "frame": _frame(selections[0].time),
                "source": selections[0].source_id,
                "target": selections[0].target_id,
                "rule": str(_details(selections[0]).get("rule", "UNKNOWN")),
            } if selections else None,
        }

    @staticmethod
    def _fingerprint(item: PreservedStrategy) -> str:
        payload = {"team": list(item.team), "actions": list(item.actions)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _classify(old: dict[str, Any], new: dict[str, Any], *, available: bool) -> str:
        if not available:
            return "HISTORICAL_STRATEGY_NOT_PERSISTED"
        prior, current = old["first_failure_frontier"], new["first_failure_frontier"]
        if current is None:
            return "RESOLVED"
        # A historical report that omitted a field cannot prove a changed
        # frontier. Compare only the old dimensions that were persisted.
        route_matches = prior["route"] == UNAVAILABLE or prior["route"] == current["route"]
        type_matches = prior["failure_type"] == UNAVAILABLE or prior["failure_type"] == current["failure_type"]
        if prior["frame"] == current["frame"] and route_matches and type_matches:
            return "PRESERVED"
        if isinstance(prior["frame"], int) and current["frame"] < prior["frame"]:
            return "REPLACED_BY_EARLIER_FAILURE"
        return "MOVED"

    def _enemy_trace(self, result: SimulationResult, *, route: str, historical_frame: int) -> dict[str, Any]:
        spawns = [event for event in result.events if event.event_type is EventType.SPAWN and _details(event).get("route_id") == route]
        leaks = {event.source_id: event for event in result.events if event.event_type is EventType.ENEMY_LEAK}
        deaths = {event.target_id: event for event in result.events if event.event_type is EventType.ENEMY_DEATH}
        # Select the same route's instance closest to the historical frontier; this
        # remains meaningful even if the PRTS formulas moved its terminal frame.
        candidate = min(spawns, key=lambda event: abs(_frame((leaks.get(event.source_id) or deaths.get(event.source_id) or event).time) - historical_frame))
        instance = candidate.source_id
        spawn_data = _details(candidate); enemy_id = str(spawn_data.get("enemy_id", "UNKNOWN"))
        enemy = self.fixture.enemies.get(enemy_id)
        attacks = [event for event in result.events if event.event_type is EventType.ATTACK_START and event.target_id == instance]
        damage = [event for event in result.events if event.event_type is EventType.DAMAGE and event.target_id == instance]
        terminal = leaks.get(instance) or deaths.get(instance)
        total = sum(float(_details(event).get("amount", 0.0)) for event in damage)
        hp = float(enemy.stats.max_hp.value) if enemy and enemy.stats.max_hp.value is not None else None
        return {
            "historical_frontier_frame": historical_frame, "enemy_instance_id": instance, "enemy_id": enemy_id,
            "spawn_frame": _frame(candidate.time), "max_hp": hp,
            "defense": float(enemy.stats.defense.value) if enemy and enemy.stats.defense.value is not None else None,
            "magic_resistance": float(enemy.stats.magic_resistance.value) if enemy and enemy.stats.magic_resistance.value is not None else None,
            "first_interaction_frame": _frame(attacks[0].time) if attacks else None,
            "attack_frames": [_frame(event.time) for event in attacks], "attackers": sorted({event.source_id for event in attacks}),
            "damage_hits": [{"frame": _frame(event.time), "attacker": event.source_id, "damage_type": _details(event).get("kind", "UNKNOWN"), "damage": _details(event).get("amount", 0.0)} for event in damage],
            "total_received_damage": total, "hp_at_terminal": max(0.0, hp - total) if hp is not None else None,
            "terminal": "ENEMY_DEATH" if instance in deaths else "ENEMY_LEAK" if instance in leaks else "ACTIVE_AT_END",
            "terminal_frame": _frame(terminal.time) if terminal else None,
        }

    def run(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        replayed: dict[str, SimulationResult] = {}
        for item in self.preserved_strategies():
            if not item.available:
                rows.append({"strategy": item.name, "source": item.source, "replay_status": "HISTORICAL_STRATEGY_NOT_PERSISTED", "old": item.old, "new": None, "frontier_classification": "HISTORICAL_STRATEGY_NOT_PERSISTED"})
                continue
            result = self.simulator.run(stage=self.fixture.stage, operators=self.fixture.operators, enemies=self.fixture.enemies, strategy=self._strategy(item), config=self.config)
            replayed[item.name] = result
            current = self._metrics(result, item.team)
            rows.append({
                "strategy": item.name,
                "source": item.source,
                "replay_status": "REPLAYED_CURRENT_PRTS_RUNTIME",
                "mechanics_version": ACTIVE_MECHANICS_VERSION,
                "strategy_fingerprint": self._fingerprint(item),
                "team": list(item.team),
                "old": item.old,
                "new": current,
                "frontier_classification": self._classify(item.old, current, available=True),
                "actions": list(item.actions),
            })
        traces = {
            "m15_route_2_frame_366_enemy": self._enemy_trace(replayed["M15_BEST_PARENT"], route="route-2", historical_frame=366),
            "m15_1_route_2_frame_564_enemy": self._enemy_trace(replayed["M15_1_GUIDED_BEST"], route="route-2", historical_frame=564),
        }
        classifications = [row["frontier_classification"] for row in rows if row["replay_status"] == "REPLAYED_CURRENT_PRTS_RUNTIME"]
        compatibility = "COMPATIBLE" if len(rows) == len(classifications) and all(item == "PRESERVED" for item in classifications) else "PARTIALLY_COMPATIBLE"
        if classifications and all(item in {"MOVED", "RESOLVED", "REPLACED_BY_EARLIER_FAILURE"} for item in classifications):
            compatibility = "INVALIDATED"
        return {
            "mechanics_rebaseline": {"version": self.VERSION, "stage": self.fixture.stage.stage_id, "mode": "APPROXIMATE_REAL", "replay_only": True, "active_mechanics_version": ACTIVE_MECHANICS_VERSION, "current_mechanics": ["PRTS physical/Arts damage", "PRTS penetration", "PRTS 5 percent minimum physical/Arts damage", "PRTS attack speed", "PRTS ATK additive-before-multiplicative"], "strategies": rows},
            "mechanics_rebaseline_frontiers": {"historical_frontier_traces_under_current_mechanics": traces, "note": "The former M15.1 2031-damage requirement is not reused; trace values above are current-runtime evidence."},
            "mechanics_rebaseline_comparison": {"HISTORICAL_BASELINE_COMPATIBILITY": compatibility, "replayed_strategy_count": len(classifications), "unreplayable_strategy_count": len(rows) - len(classifications), "frontier_classifications": {row["strategy"]: row["frontier_classification"] for row in rows}},
        }
