from __future__ import annotations

import unittest
from pathlib import Path

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.operator_assignment import OperatorAssignmentEngine
from arknights_planner.search.scope import ExperimentScope
from arknights_planner.search.stage_eligibility import (
    PlannerTaskType,
    StageEligibilityAnalyzer,
    StageIneligibleError,
)
from arknights_planner.search.stage_understanding import (
    StageUnderstandingAnalyzer,
    derive_tactical_requirements,
)
from arknights_planner.search.top_down import TopDownPlanner
from arknights_planner.search.top_down_validation import TopDownValidation


ROOT = Path(__file__).resolve().parents[1]


class StageEligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = GameDataRepository(ROOT / "data/ArknightsGameData")
        cls.adapter = ApproximateRealSimulationAdapter(cls.repository)
        cls.analyzer = StageEligibilityAnalyzer()

    def test_normal_free_team_stage_is_accepted(self):
        eligibility = self.analyzer.analyze(self.repository, "main_01-01")
        task = eligibility.eligible_for(PlannerTaskType.AUTONOMOUS_TEAM_SELECTION)
        self.assertEqual(eligibility.stage_id, "main_01-01")
        self.assertEqual(eligibility.display_stage_code, "1-1")
        self.assertTrue(eligibility.free_team_selection)
        self.assertTrue(eligibility.simulator_supported)
        self.assertTrue(task.eligible)

    def test_fixed_squad_stage_is_rejected_for_team_selection(self):
        eligibility = self.analyzer.analyze(self.repository, "main_11-17")
        task = eligibility.eligible_for(PlannerTaskType.AUTONOMOUS_TEAM_SELECTION)
        self.assertEqual(eligibility.display_stage_code, "11-19")
        self.assertTrue(eligibility.fixed_squad)
        self.assertTrue(eligibility.preset_deployed_units)
        self.assertTrue(eligibility.forced_operators)
        self.assertFalse(task.eligible)
        self.assertIn("FIXED_SQUAD", task.rejection_reasons)
        self.assertIn("PRESET_DEPLOYED_UNITS", task.rejection_reasons)
        self.assertIn("FORCED_OPERATORS", task.rejection_reasons)

    def test_preset_unit_special_stage_is_rejected(self):
        eligibility = self.analyzer.analyze(self.repository, "main_06-15")
        task = eligibility.eligible_for(PlannerTaskType.AUTONOMOUS_TEAM_SELECTION)
        self.assertEqual(eligibility.display_stage_code, "6-17")
        self.assertTrue(eligibility.preset_deployed_units)
        self.assertTrue(eligibility.tutorial_or_story_special)
        self.assertFalse(task.eligible)
        self.assertIn("PRESET_DEPLOYED_UNITS", task.rejection_reasons)

    def test_free_team_stage_with_unsupported_mechanics_is_rejected(self):
        eligibility = self.analyzer.analyze(self.repository, "main_00-03")
        task = eligibility.eligible_for(PlannerTaskType.AUTONOMOUS_TEAM_SELECTION)
        self.assertTrue(eligibility.free_team_selection)
        self.assertFalse(eligibility.simulator_supported)
        self.assertFalse(task.eligible)
        self.assertIn("AERIAL_ROUTE_NOT_REPRESENTED", task.rejection_reasons)

    def test_internal_and_display_stage_codes_are_both_resolved(self):
        by_internal = self.analyzer.analyze(self.repository, "main_11-17")
        by_display = self.analyzer.analyze(self.repository, "11-19")
        self.assertEqual(by_internal.stage_id, by_display.stage_id)
        self.assertEqual(by_internal.display_stage_code, by_display.display_stage_code)
        self.assertEqual((by_internal.stage_id, by_internal.display_stage_code), ("main_11-17", "11-19"))

    def test_eligibility_is_task_dependent_for_fixed_squad(self):
        eligibility = self.analyzer.analyze(self.repository, "main_11-17")
        autonomous = eligibility.eligible_for(PlannerTaskType.AUTONOMOUS_TEAM_SELECTION)
        timing_semantics = eligibility.eligible_for(
            PlannerTaskType.TIMING_ONLY_PLANNING,
            require_simulator_support=False,
        )
        self.assertFalse(autonomous.eligible)
        self.assertTrue(timing_semantics.eligible)
        self.assertTrue(timing_semantics.semantic_eligible)

    def test_planner_rejects_ineligible_stage_before_operator_configuration(self):
        planner = TopDownPlanner(
            adapter=self.adapter,
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
            scope=ExperimentScope(
                stage_id="main_11-17",
                operator_pool=("char_124_kroos",),
                max_cardinality=1,
                simulation_budget=1,
                search_policy="FEASIBILITY_FIRST",
            ),
            root=ROOT,
        )

        def fail_if_called():
            raise AssertionError("eligibility gate must run before operator configuration")

        planner._configurations = fail_if_called
        with self.assertRaises(StageIneligibleError):
            planner.run()

    def test_all_executable_pool_is_not_rarity_restricted(self):
        configurations = self.adapter.all_executable_phase_zero_configurations()
        rarities = {configuration.operator_id: self.repository.get_operator(
            configuration.operator_id
        ).star_rarity.value for configuration in configurations}
        self.assertGreater(len(configurations), 200)
        self.assertTrue({4, 5, 6}.issubset(rarities.values()))

    def test_validation_builder_rejects_predefined_stage(self):
        validation = TopDownValidation(repository=self.repository, adapter=self.adapter, root=ROOT)
        _, metadata = self.repository._stage_metadata("main_11-17")
        candidate, status = validation._build_candidate("main_11-17", metadata)
        self.assertIsNone(candidate)
        self.assertEqual(status, "INELIGIBLE_FOR_AUTONOMOUS_TEAM_SELECTION")


class FeasibilityFirstAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repository = GameDataRepository(ROOT / "data/ArknightsGameData")
        adapter = ApproximateRealSimulationAdapter(repository)
        engine_fixture = adapter.build_pool_fixture(
            stage_id_or_code="main_01-01",
            configurations=adapter.m13_low_rarity_configurations(),
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        )
        cls.understanding = StageUnderstandingAnalyzer().analyze(engine_fixture)
        cls.requirements = derive_tactical_requirements(cls.understanding)
        cls.operators = engine_fixture.operators

    def test_feasibility_first_prefers_robust_teams_over_minimal_teams(self):
        engine = OperatorAssignmentEngine()
        minimal = engine.coverage_alternatives(
            self.understanding,
            self.requirements,
            self.operators,
            max_cardinality=8,
            team_size_policy="LEXICOGRAPHIC_MINIMAL",
        )
        feasibility = engine.coverage_alternatives(
            self.understanding,
            self.requirements,
            self.operators,
            max_cardinality=8,
            team_size_policy="FEASIBILITY_FIRST",
        )
        self.assertTrue(minimal)
        self.assertTrue(feasibility)
        self.assertGreaterEqual(feasibility[0].operator_count, minimal[0].operator_count)
        same_coverage = [
            item for item in feasibility
            if len(item.covered_requirement_ids) == len(feasibility[0].covered_requirement_ids)
        ]
        self.assertEqual(feasibility[0].operator_count, max(item.operator_count for item in same_coverage))


if __name__ == "__main__":
    unittest.main()
