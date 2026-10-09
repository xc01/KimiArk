from __future__ import annotations

from dataclasses import replace

from arknights_planner.models.provenance import known
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search import BeamSearch, FailureCategory, SearchConfig, SyntheticStrategyEvaluator, analyze_failure
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage


def evaluator(stage=None):
    return SyntheticStrategyEvaluator(
        simulator=Simulator(), stage=stage or synthetic_stage(), operators=synthetic_operators(), enemies=synthetic_enemies(),
        simulation_config=SimulationConfig(dt=0.1, max_time=20.0),
    )


def search(config: SearchConfig | None = None):
    return BeamSearch(stage=synthetic_stage(), operators=synthetic_operators(), enemies=synthetic_enemies(), config=config).search()


def test_dense_score_prefers_a_near_win_over_obviously_bad_strategy():
    evalr = evaluator()
    defense = evalr.evaluate(Strategy(
        ("guard", "archer"),
        (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1), "RIGHT"), Action(ActionType.DEPLOY, 4.0, "archer", (1, 2), "UP")),
    ))
    invalid = evalr.evaluate(Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (0, 1), "RIGHT"),)))
    assert defense.result.enemies_leaked < invalid.result.enemies_leaked
    assert not defense.result.deployment_errors
    assert defense.score > invalid.score


def test_failure_analysis_classifies_observable_failures():
    evalr = evaluator()
    illegal = analyze_failure(evalr.evaluate(Strategy(("guard",), (Action(ActionType.DEPLOY, 0.0, "guard", (0, 1), "RIGHT"),))))
    assert FailureCategory.ILLEGAL_DEPLOYMENT in illegal.categories

    late = analyze_failure(evalr.evaluate(Strategy(("guard",), (Action(ActionType.DEPLOY, 8.0, "guard", (3, 1), "RIGHT"),))))
    assert FailureCategory.LEAK_BEFORE_DEFENSE in late.categories
    assert FailureCategory.POOR_DEPLOYMENT_TIMING in late.categories

    rich_stage = replace(synthetic_stage(), deployment_limit=known(3, "synthetic/test", "$.limit"))
    dp_failure = analyze_failure(evaluator(rich_stage).evaluate(Strategy(
        ("guard", "archer", "rookie"),
        (Action(ActionType.DEPLOY, 0.0, "guard", (3, 1)), Action(ActionType.DEPLOY, 0.0, "archer", (1, 2), "UP"), Action(ActionType.DEPLOY, 0.0, "rookie", (4, 1))),
    )))
    assert FailureCategory.INSUFFICIENT_DP in dp_failure.categories


def test_candidate_generation_is_deterministic_and_bounded():
    engine = BeamSearch(stage=synthetic_stage(), operators=synthetic_operators(), enemies=synthetic_enemies())
    first = engine.generate_candidates(Strategy((), ()))
    second = engine.generate_candidates(Strategy((), ()))
    assert first == second
    assert len(first) == 48


def test_search_is_deterministic_for_same_seed_and_finds_synthetic_win():
    config = SearchConfig(seed=17)
    first = search(config)
    second = search(config)
    assert first.best.result.win is True
    assert first.best.strategy == second.best.strategy
    assert first.best.score == second.best.score
    assert first.metrics.simulations_evaluated == second.metrics.simulations_evaluated
    assert first.metrics.simulations_to_first_win is not None


def test_local_timing_refinement_never_regresses_best_score():
    coarse = search(SearchConfig(refine_timing=False))
    refined = search(SearchConfig(refine_timing=True))
    assert refined.best.score >= coarse.best.score
