"""Offline M14.9 tests for bounded source-backed opening-economy support."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.adapters.approximate_real import M13LoadoutPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.simulation import EventType
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.m14_fidelity import M14OpeningEconomyFidelityAudit
from arknights_planner.simulator import SimulationConfig, Simulator


def _fixture():
    repository = GameDataRepository("data/ArknightsGameData")
    adapter = ApproximateRealSimulationAdapter(repository)
    ids = ("char_123_fang", "char_240_wyvern", "char_122_beagle", "char_502_nblade", "char_282_catap")
    configurations = tuple(M13LoadoutPolicy.highest_legal().configuration(repository, item) for item in ids)
    return adapter, adapter.build_pool_fixture(stage_id_or_code="6-8", configurations=configurations, policy=RealSimulationApproximationPolicy.m11_second_quantized())


def test_source_explicit_self_cost_talent_and_time_sp_dp_patterns_are_runtime_mapped():
    _, fixture = _fixture()
    fang, vanilla, catapult = (fixture.operators[item] for item in ("char_123_fang", "char_240_wyvern", "char_282_catap"))
    assert (fang.deployment_cost_delta, catapult.deployment_cost_delta) == (-1.0, -1.0)
    assert fang.synthetic_skill is not None and fang.synthetic_skill.auto_activate is True
    assert fang.synthetic_skill.effect.dp_immediate == 6.0
    assert vanilla.synthetic_skill is not None and vanilla.synthetic_skill.auto_activate is False
    assert vanilla.synthetic_skill.effect.dp_immediate == 6.0


def test_auto_and_manual_dp_changes_are_distinct_and_source_amounts_are_applied_once():
    _, fixture = _fixture()
    simulator = Simulator()
    fang = Strategy(("char_123_fang",), (Action(ActionType.DEPLOY, 0, "char_123_fang", (4, 3), "DOWN"),))
    result = simulator.run(stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies, strategy=fang, config=SimulationConfig(dt=0.1, max_time=20.0))
    dp = [event for event in result.events if event.event_type is EventType.DP_CHANGE]
    assert [(event.time, event.source_id, dict(event.details)["amount"]) for event in dp] == [(19.0, "char_123_fang", 6.0)]

    strategy = Strategy(("char_240_wyvern", "char_122_beagle"), (
        Action(ActionType.DEPLOY, Fraction(30, 30), "char_240_wyvern", (4, 3), "DOWN"),
        Action(ActionType.ACTIVATE_SKILL, Fraction(450, 30), "char_240_wyvern"),
        Action(ActionType.DEPLOY, Fraction(450, 30), "char_122_beagle", (4, 4), "DOWN"),
    ))
    result = simulator.run(stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies, strategy=strategy, config=SimulationConfig(dt=0.1, max_time=16.0))
    beagle = [dict(event.details)["legal"] for event in result.events if event.event_type is EventType.DEPLOY and event.source_id == "char_122_beagle"]
    assert beagle == [True]
    dp = [event for event in result.events if event.event_type is EventType.DP_CHANGE]
    assert [(event.time, event.source_id, dict(event.details)["amount"]) for event in dp] == [(15.0, "char_240_wyvern", 6.0)]


def test_m14_economy_audit_keeps_blocked_coupled_dp_effects_unsupported_and_reports_nonmaterial_deadline_result():
    adapter, _ = _fixture()
    report = M14OpeningEconomyFidelityAudit(adapter=adapter, policy=RealSimulationApproximationPolicy.m11_second_quantized()).run()
    assert report["low_rarity_economy_audit"]["eligible"] == 34
    assert report["low_rarity_economy_audit"]["executable"] == 22
    relevant = report["opening_economy_relevant_operators"]
    fang = next(item for item in relevant if item["operator_id"] == "char_123_fang" and item["mechanic"] == "AUTO_GRANT_DP")
    confess = next(item for item in relevant if item["operator_id"] == "char_4188_confes")
    assert fang["runtime_supported"] is True and fang["earliest_possible_effect_frame"] == 570
    assert confess["runtime_supported"] is False
    assert report["classification"] == "FOUND_BUT_NOT_MATERIAL"
