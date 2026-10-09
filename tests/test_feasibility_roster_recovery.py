import unittest
from dataclasses import replace
from pathlib import Path

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.agent.tactical import PlanHypothesis
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig
from arknights_planner.search.operator_assignment import OperatorAssignmentEngine
from arknights_planner.search.spatial_timing import SpatialTimingSearch
from arknights_planner.search.stage_understanding import (
    StageUnderstandingAnalyzer,
    derive_tactical_requirements,
)


ROOT = Path(__file__).resolve().parents[1]


class FeasibilityRosterRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repository = GameDataRepository(ROOT / "data/ArknightsGameData")
        cls.adapter = ApproximateRealSimulationAdapter(repository)
        cls.stage = repository.get_stage("main_01-01")
        cls.configurations = cls.adapter.all_executable_phase_zero_configurations()
        cls.fixture = cls.adapter.build_pool_fixture(
            stage_id_or_code="main_01-01",
            configurations=cls.configurations,
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        )
        cls.understanding = StageUnderstandingAnalyzer().analyze(cls.fixture)
        cls.requirements = derive_tactical_requirements(cls.understanding)

    def test_squad_size_and_deployment_limit_are_separate(self):
        self.assertEqual(self.stage.squad_size_limit.value, 12)
        self.assertEqual(self.stage.deployment_limit.value, 8)
        self.assertIn("maxSlot == -1", self.stage.squad_size_limit.source_path)
        self.assertEqual(self.understanding.squad_size_limit, 12)
        self.assertEqual(self.understanding.deployment_limit, 8)

    def test_feasibility_mode_generates_five_plus_and_control_rosters(self):
        plan = OperatorAssignmentEngine().assign(
            self.understanding,
            self.requirements,
            self.fixture.operators,
            max_cardinality=12,
            team_size_policy="FEASIBILITY_FIRST",
        )
        sizes = {alternative.operator_count for alternative in plan.coverage_alternatives}
        self.assertTrue(any(size >= 5 for size in sizes))
        self.assertIn(12, sizes)
        control = [
            alternative for alternative in plan.coverage_alternatives
            if alternative.archetype == "CONTROL_CAPABILITY_RICH"
        ]
        self.assertEqual(len(control), 1)
        self.assertGreaterEqual(control[0].operator_count, 8)
        self.assertIn("capability coverage and redundancy", control[0].rationale)

    def test_unknown_squad_limit_does_not_collapse_requested_roster_bound(self):
        understanding = replace(self.understanding, squad_size_limit=0)
        plan = OperatorAssignmentEngine().assign(
            understanding,
            self.requirements,
            self.fixture.operators,
            max_cardinality=5,
            team_size_policy="FEASIBILITY_FIRST",
        )
        self.assertTrue(
            any(alternative.operator_count == 5 for alternative in plan.coverage_alternatives)
        )

    def test_larger_roster_uses_active_subset_and_retains_reserves(self):
        plan = OperatorAssignmentEngine().assign(
            self.understanding,
            self.requirements,
            self.fixture.operators,
            max_cardinality=12,
            team_size_policy="FEASIBILITY_FIRST",
        )
        control = next(
            alternative for alternative in plan.coverage_alternatives
            if alternative.archetype == "CONTROL_CAPABILITY_RICH"
        )
        engine = M11MinimumSquadSearch(
            adapter=self.adapter,
            stage_id_or_code="main_01-01",
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
            operator_pool=self.configurations,
            config=M11SearchConfig(max_squad_size=12, max_teams=1),
        )
        search = SpatialTimingSearch(engine=engine, understanding=self.understanding)
        hypothesis = PlanHypothesis(
            hypothesis_id="control-active-subset",
            summary="Control active-subset regression",
            target_cardinality=len(control.operator_ids),
            tactical_archetype=control.archetype,
            preferred_operator_ids=control.operator_ids,
            deployment_order=control.deployment_order,
        )
        outcome = search.search((hypothesis,), simulation_budget=1)
        audit = outcome.audit["hypotheses"][hypothesis.hypothesis_id]
        self.assertGreater(
            outcome.audit["hypotheses"][hypothesis.hypothesis_id]["skeleton_funnel"][
                hypothesis.hypothesis_id
            ]["returned_skeletons"],
            0,
        )
        self.assertLessEqual(len(audit["active_deployment_subset"]), 8)
        active_costs = [
            self.fixture.operators[operator_id].phases[0].stats_max.cost.value
            for operator_id in audit["active_deployment_subset"]
        ]
        self.assertEqual(active_costs, sorted(active_costs))
        if len(control.operator_ids) > 8:
            self.assertTrue(audit["reserve_operators"])
            self.assertFalse(
                set(audit["reserve_operators"]).intersection(
                    audit["active_deployment_subset"]
                )
            )
        if outcome.best is not None:
            self.assertLessEqual(len(outcome.best.strategy.team), 8)


if __name__ == "__main__":
    unittest.main()
