from __future__ import annotations

import unittest
from pathlib import Path

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig
from arknights_planner.search.operator_assignment import OperatorAssignmentEngine
from arknights_planner.search.responsibility_feasibility import build_early_threat_model
from arknights_planner.search.stage_understanding import (
    StageUnderstandingAnalyzer,
    derive_tactical_requirements,
)
from arknights_planner.search.temporal_assignment import (
    build_temporal_assignment_frontier,
    derive_early_pressure_responsibilities,
    derive_simultaneity_constraints,
    derive_temporal_responsibilities,
    detect_role_overloads,
    expand_hypotheses_with_assignments,
)
from arknights_planner.search.top_down import DeterministicHypothesisGenerator


ROOT = Path(__file__).resolve().parents[1]


class TemporalAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repository = GameDataRepository(ROOT / "data/ArknightsGameData")
        adapter = ApproximateRealSimulationAdapter(repository)
        engine = M11MinimumSquadSearch(
            adapter=adapter,
            stage_id_or_code="main_08-01",
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
            operator_pool=adapter.all_executable_phase_zero_configurations(),
            config=M11SearchConfig(
                beam_width=1,
                placement_options_per_operator=12,
                max_squad_size=12,
                max_teams=1,
            ),
        )
        cls.engine = engine
        cls.understanding = StageUnderstandingAnalyzer().analyze(engine.fixture)
        cls.requirements = derive_tactical_requirements(cls.understanding)
        cls.assignment = OperatorAssignmentEngine().assign(
            cls.understanding,
            cls.requirements,
            engine.fixture.operators,
            max_cardinality=12,
            team_size_policy="FEASIBILITY_FIRST",
        )
        cls.frontier = build_temporal_assignment_frontier(
            cls.understanding,
            cls.requirements,
            cls.assignment,
            engine.fixture.operators,
            OperatorAssignmentEngine(),
            deployment_limit=cls.understanding.deployment_limit,
        )

    def test_early_pressure_uses_route_contact_not_spawn_time_alone(self):
        early = derive_early_pressure_responsibilities(self.understanding, self.requirements)
        self.assertTrue(early)
        first = early[0]
        self.assertGreater(first.latest_safe_deployment_time, first.start_time)

    def test_early_threat_model_includes_observed_leak_routes(self):
        early = derive_early_pressure_responsibilities(self.understanding, self.requirements)
        observed_routes = {"route-1", "route-10", "route-11", "route-34"}
        threat = build_early_threat_model(
            self.engine,
            self.understanding,
            early_window=early[0],
            observed_leak_routes=observed_routes,
        )

        self.assertTrue(observed_routes <= {item.route_id for item in threat.routes})

    def test_frontier_preserves_temporal_responsibilities_and_fingerprints(self):
        self.assertTrue(self.frontier)
        for row in self.frontier:
            self.assertTrue(row.temporal_responsibilities)
            self.assertEqual(
                len({item.semantic_fingerprint for item in self.frontier}),
                len(self.frontier),
            )
            self.assertTrue(set(item.requirement_id for item in row.temporal_responsibilities))

    def test_dp_risk_is_flagged_without_discarding_uncertain_assignments(self):
        risky = [row for row in self.frontier if not row.opening_dp_feasibility.feasible]
        self.assertTrue(risky)
        self.assertTrue(any(row.feasible for row in risky))
        self.assertTrue(all("OPENING_DP_RISK" in row.precheck_warnings for row in risky))

    def test_deployment_order_prefers_low_cost_openers(self):
        row = self.frontier[0]
        costs = [
            float(self.engine.fixture.operators[item].phases[0].stats_max.cost.value or 0)
            for item in row.deployment_order[:self.understanding.deployment_limit]
        ]
        self.assertEqual(costs, sorted(costs))

    def test_simultaneity_and_overload_audit_are_deterministic(self):
        responsibilities = derive_temporal_responsibilities(
            self.understanding,
            self.requirements,
        )
        constraints = derive_simultaneity_constraints(responsibilities)
        overloads = detect_role_overloads(responsibilities)
        self.assertEqual(
            constraints,
            derive_simultaneity_constraints(responsibilities),
        )
        self.assertEqual(
            overloads,
            detect_role_overloads(responsibilities),
        )

    def test_hypotheses_bind_to_distinct_assignment_frontier(self):
        context = {
            "stage_understanding": self.understanding.to_dict(),
            "tactical_requirements": [item.to_dict() for item in self.requirements],
            "operator_assignment": self.assignment.to_dict(),
        }
        base = DeterministicHypothesisGenerator().generate_hypotheses(context, max_hypotheses=8)
        expanded = expand_hypotheses_with_assignments(
            base,
            self.assignment,
            max_hypotheses=8,
            frontier=self.frontier,
        )
        self.assertEqual(len(base), len(expanded))
        self.assertGreaterEqual(
            len({item.deployment_order for item in expanded}),
            2,
        )


if __name__ == "__main__":
    unittest.main()
