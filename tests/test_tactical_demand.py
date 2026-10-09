from __future__ import annotations

import unittest
from pathlib import Path

from arknights_planner.adapters import (
    ApproximateRealSimulationAdapter,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig
from arknights_planner.search.stage_understanding import StageUnderstandingAnalyzer
from arknights_planner.search.tactical_demand import (
    build_failure_trace_requirement_alignment,
    build_hypothesis_requirement_certificates,
    build_pressure_transitions,
    build_pressure_windows,
    build_requirement_concurrency_graph,
    build_requirement_sharing,
    build_route_pressure_clusters,
    build_tactical_requirement_atoms,
)
from arknights_planner.agent.tactical import PlanHypothesis


ROOT = Path(__file__).resolve().parents[1]


class TacticalDemandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repository = GameDataRepository(ROOT / "data/ArknightsGameData")
        adapter = ApproximateRealSimulationAdapter(repository)
        cls.engine = M11MinimumSquadSearch(
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
        cls.understanding = StageUnderstandingAnalyzer().analyze(cls.engine.fixture)
        cls.clusters = build_route_pressure_clusters(
            cls.understanding,
            coverage_opportunities=cls.understanding.coverage_opportunities,
        )
        cls.windows = build_pressure_windows(cls.understanding, cls.clusters, cls.engine.fixture)
        cls.atoms = build_tactical_requirement_atoms(cls.understanding, cls.clusters, cls.windows)

    def test_route_rows_are_grouped_by_exact_corridor(self):
        self.assertEqual(sum(len(item.member_route_ids) for item in self.clusters), len(self.understanding.routes))
        self.assertLess(len(self.clusters), len(self.understanding.routes))
        self.assertEqual(
            len(self.clusters),
            len({item.path_signature for item in self.clusters}),
        )
        self.assertTrue(all(item.overlap_with_clusters for item in self.clusters))

    def test_pressure_windows_are_event_gap_derived(self):
        self.assertGreater(len(self.windows), 1)
        self.assertEqual(
            sum(item.enemy_count for item in self.windows),
            sum(row.count for row in self.engine.fixture.spawn_timeline),
        )
        for previous, current in zip(self.windows, self.windows[1:]):
            self.assertGreater(current.start_time, previous.start_time)
            self.assertEqual(current.previous_window_id, previous.window_id)

    def test_requirement_atoms_have_complete_scope_and_evidence(self):
        for atom in self.atoms:
            self.assertTrue(atom.clusters)
            self.assertTrue(atom.why)
            self.assertTrue(atom.evidence)
            self.assertIn(atom.necessity, {"HARD", "CONDITIONAL", "OPTIONAL"})
            self.assertIn(atom.shareable, {"NO", "MAY_SHARE_RESOURCE", "SHARE_IF_GEOMETRY_ALLOWS"})
        self.assertTrue(any(item.necessity == "HARD" for item in self.atoms))
        self.assertFalse(all(item.necessity == "HARD" for item in self.atoms))
        self.assertTrue(any(item.family == "PRECONTACT_DAMAGE" for item in self.atoms))

    def test_concurrency_and_sharing_distinguish_distinct_resources(self):
        edges = build_requirement_concurrency_graph(self.atoms)
        sharing = build_requirement_sharing(self.clusters, self.atoms)
        self.assertIn("MUST_BE_DISTINCT", {item.relation for item in edges})
        self.assertIn("SHARE_IF_GEOMETRY_ALLOWS", {item.relation for item in edges})
        self.assertTrue(sharing)
        self.assertIn("SHARED", {item["verdict"] for item in sharing})

    def test_pressure_transitions_preserve_persistence_and_new_demand(self):
        transitions = build_pressure_transitions(self.atoms, self.windows)
        self.assertEqual(len(transitions), len(self.windows) - 1)
        self.assertTrue(all(
            set(item) == {
                "from_window", "to_window", "persisting_clusters", "ending_clusters", "new_clusters",
                "persisting_requirements", "ending_requirements", "new_requirements",
                "reusable_resource_families", "stranded_resource_risk",
                "reserve_activation_opportunity", "evidence",
            }
            for item in transitions
        ))

    def test_hypothesis_certificates_reject_uncovered_hard_requirements(self):
        hypothesis = PlanHypothesis(
            hypothesis_id="incomplete",
            summary="Incomplete opening structure",
            required_capabilities=("RANGED_DPS",),
        )
        certificate = build_hypothesis_requirement_certificates((hypothesis,), self.atoms)[0]
        self.assertFalse(certificate.admissible)
        self.assertIn("A-OPENING-ECONOMY", certificate.uncovered_hard_requirements)

    def test_failure_trace_alignment_uses_stage_first_requirements(self):
        record = {
            "record_id": "test-record",
            "leak_routes": ("route-1", "route-10"),
        }
        rows = build_failure_trace_requirement_alignment(
            (record,), self.clusters, self.windows, self.atoms,
        )
        by_route = {item["route_id"]: item for item in rows[0]["route_alignments"]}
        self.assertEqual(by_route["route-1"]["status"], "REQUIREMENT_PRESENT_BUT_NOT_REALIZED")
        self.assertEqual(by_route["route-10"]["status"], "REQUIREMENT_PRESENT_BUT_NOT_REALIZED")
        self.assertEqual(by_route["route-10"]["old_model_status"], "NOT_EXPLAINED_BY_REQUIREMENT_MODEL")


if __name__ == "__main__":
    unittest.main()
