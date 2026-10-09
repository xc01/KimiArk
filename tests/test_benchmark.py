from __future__ import annotations

from fractions import Fraction
from dataclasses import replace
from pathlib import Path

import pytest

from arknights_planner.adapters import LowRarityBlackboardEffectInterpreter, RealSkillSupport
from arknights_planner.benchmark import (
    HumanFailureCategory, HumanValidationRecord, HumanValidationStatus,
    StrategyObjective, compare_strategies, direction_label, effective_operator_ids,
    low_rarity_census, render_human_timeline, stage_benchmark_census,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.frame import FrameClock
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.models.timeline import FrameAction, FrameTimeline, TimelineActionType
from arknights_planner.models.stage import SpawnEvent
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage
from arknights_planner.cli.plan_cli import main as plan_main
from arknights_planner.search import BenchmarkSearchConfig, BenchmarkSearchStop, SquadCardinalitySearch


@pytest.fixture(scope="module")
def repository() -> GameDataRepository:
    root = Path(__file__).resolve().parents[1] / "data/ArknightsGameData"
    if not (root / "zh_CN/gamedata/excel/character_table.json").is_file():
        pytest.skip("locally supplied ArknightsGameData is not available")
    return GameDataRepository(root)


def test_game_data_rarity_normalizes_tier_to_human_stars(repository):
    kroos = repository.get_operator("char_124_kroos")
    lancet = repository.get_operator("char_285_medic2")
    assert (kroos.rarity.value, kroos.star_rarity.value, kroos.star_rarity.status.value) == ("TIER_3", 3, "DERIVABLE")
    assert (lancet.rarity.value, lancet.star_rarity.value) == ("TIER_1", 1)


def test_low_rarity_census_filters_non_operator_templates_and_classifies_support(repository):
    census = low_rarity_census(repository)
    assert len(census) == 34
    by_id = {item.operator_id: item for item in census}
    assert by_id["char_208_melan"].support.value == "SIMPLE_SUPPORTED"
    assert by_id["char_124_kroos"].support.value != "SIMPLE_SUPPORTED"
    assert "char_999_2030" not in by_id


def test_bounded_real_manual_attack_interpreter_is_skill_pattern_not_operator_branch(repository):
    interpreter = LowRarityBlackboardEffectInterpreter()
    melantha = repository.get_skill("skcom_atk_up[1]").levels[-1]
    lava = repository.get_skill("skcom_magic_rage[1]").levels[-1]
    supported = interpreter.interpret("skcom_atk_up[1]", melantha)
    unsupported = interpreter.interpret("skcom_magic_rage[1]", lava)
    assert supported.support is RealSkillSupport.EXECUTABLE_APPROXIMATED
    assert supported.executable_effect is not None
    assert supported.executable_effect.effect.atk_multiplier == 1.5
    assert supported.executable_effect.sp_cost == 40
    assert unsupported.support is RealSkillSupport.UNSUPPORTED


def test_interpreted_real_skill_uses_existing_runtime_activation_and_duration(repository):
    interpreted = LowRarityBlackboardEffectInterpreter().interpret("skcom_atk_up[1]", repository.get_skill("skcom_atk_up[1]").levels[-1])
    operators = synthetic_operators()
    operators["archer"] = replace(operators["archer"], synthetic_skill=interpreted.executable_effect)
    # Keep the simulator alive until the 40-SP manual activation without needing a
    # fabricated real battle or enemy mechanic.
    stage = replace(synthetic_stage(), spawn_events=(SpawnEvent(100.0, "slug", "main"),))
    result = Simulator().run(
        stage=stage, operators=operators, enemies=synthetic_enemies(),
        strategy=Strategy(("archer",), (Action(ActionType.DEPLOY, 0, "archer", (1, 2), "UP"), Action(ActionType.ACTIVATE_SKILL, 40, "archer"))),
        config=SimulationConfig(dt=0.1, max_time=40.2),
    )
    activates = [event for event in result.events if event.event_type.value == "SKILL_ACTIVATE"]
    assert activates and ("legal", True) in activates[0].details


def test_objective_is_hard_win_then_count_rarity_robustness_actions_duration():
    loss = StrategyObjective(False, 1, 1, Fraction(1, 10), 1, 1.0)
    two_low = StrategyObjective(True, 2, 4, Fraction(1, 10), 1, 1.0)
    one_high = StrategyObjective(True, 1, 6, Fraction(1, 1), 20, 99.0)
    two_six = StrategyObjective(True, 2, 6, Fraction(1, 10), 1, 1.0)
    robust = StrategyObjective(True, 2, 5, Fraction(1, 10), 8, 30.0)
    fragile = StrategyObjective(True, 2, 5, Fraction(1, 2), 2, 10.0)
    few_actions = StrategyObjective(True, 2, 5, Fraction(1, 10), 7, 99.0)
    assert compare_strategies(one_high, two_low) == -1  # fewer operators wins over lower total stars
    assert compare_strategies(two_low, loss) == -1      # every WIN dominates LOSS
    assert compare_strategies(two_low, two_six) == -1   # rarity inside equal squad size
    assert compare_strategies(robust, fragile) == -1    # robustness precedes action count/duration
    assert compare_strategies(few_actions, robust) == -1


def test_redeployment_counts_once_and_human_directions_are_localized(repository):
    strategy = Strategy(("char_123_fang", "padding"), (
        Action(ActionType.DEPLOY, 0, "char_123_fang", (1, 1), "RIGHT"),
        Action(ActionType.RETREAT, 1, "char_123_fang"),
        Action(ActionType.DEPLOY, 2, "char_123_fang", (2, 1), "LEFT"),
    ))
    assert effective_operator_ids(strategy) == ("char_123_fang",)
    assert [direction_label(item) for item in ("UP", "DOWN", "LEFT", "RIGHT")] == ["↑ 上", "↓ 下", "← 左", "→ 右"]
    timeline = FrameTimeline("0-1", FrameClock.configured(30), (FrameAction(90, TimelineActionType.DEPLOY, "char_123_fang", (1, 1), "RIGHT"),))
    text = render_human_timeline(timeline=timeline, repository=repository, simulator_result="WIN")
    assert "→ 右" in text and "[3.000s]" in text
    assert "pixel" not in text.lower() and "screen" not in text.lower()


def test_validation_record_is_evidence_only_round_trip(tmp_path):
    record = HumanValidationRecord("6-1", "timeline-a", "WIN", 2, 6, HumanValidationStatus.FAIL, "leaked", 120, HumanFailureCategory.ENEMY_LEAKED)
    path = tmp_path / "validation.json"
    record.save(path)
    assert HumanValidationRecord.load(path) == record


def test_stage_benchmark_suite_is_selected_but_compatibility_is_explicit(repository):
    records = stage_benchmark_census(repository)
    assert len(records) == 9
    assert {item.chapter for item in records} == {6, 7, 8, 9, 10, 11}
    assert all(item.compatibility == "BLOCKED" for item in records)
    assert next(item for item in records if item.code == "6-1").route_count is not None
    assert next(item for item in records if item.code == "9-2").map_width is None


def test_benchmark_cli_persists_blocked_compatibility_without_running_search(repository, tmp_path, capsys):
    plan_main(["benchmark-search", "6-1", "--data-root", str(repository.root), "--output-dir", str(tmp_path)])
    output = capsys.readouterr().out
    assert "Benchmark compatibility: BLOCKED" in output
    assert "No simulator search was run" in output
    assert (tmp_path / "main_06-01" / "compatibility.json").is_file()


def test_cardinality_search_exhausts_lower_count_then_rarity_without_scalar_rewards():
    engine = SquadCardinalitySearch(rarity_by_operator={"high": 6, "low_a": 2, "low_b": 3}, config=BenchmarkSearchConfig(max_squad_size=2, max_teams=10))
    def evaluate(team):
        if team.operator_ids == ("high",):
            return StrategyObjective(True, 1, 6, Fraction(1, 2), 9, 80.0)
        if team.operator_ids == ("low_a", "low_b"):
            return StrategyObjective(True, 2, 5, Fraction(1, 100), 1, 1.0)
        return StrategyObjective(False, len(team.operator_ids), team.rarity_sum, Fraction(1, 1), 1, 1.0)
    result = engine.search(evaluate_team=evaluate)
    assert result.stop is BenchmarkSearchStop.MINIMUM_SQUAD_WITHIN_BOUNDED_DOMAIN
    assert result.best_team is not None and result.best_team.operator_ids == ("high",)
    assert result.metrics.teams_simulated == 3  # all one-operator candidates were exhausted first
