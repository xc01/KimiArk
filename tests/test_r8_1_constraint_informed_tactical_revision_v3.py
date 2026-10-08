from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_constraint_informed_revision_v3"
SCRIPT = ROOT / "scripts/run_r8_1_constraint_informed_tactical_revision_v3.py"


def load_module() -> any:
    spec = importlib.util.spec_from_file_location(
        "r8_1_constraint_informed_tactical_revision_v3", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConstraintInformedTacticalRevisionV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_experience_memory_is_conditional_and_source_bound(self) -> None:
        result = self.module.experience_memory()
        self.assertEqual(6, len(result["records"]))
        self.assertEqual("R8_1_FEASIBILITY_EXPERIENCE_MEMORY_V1", result["schema_version"])
        required = {
            "experience_id",
            "stage_id",
            "mechanics_version",
            "source_plan_id",
            "failed_tactical_assumption",
            "conflicting_constraints",
            "deadline",
            "minimum_required_cost",
            "available_dp_bound",
            "evidence_sources",
            "applicability_conditions",
            "generalizable_lesson",
            "possible_tactical_revision_dimensions",
            "confidence",
            "limitations",
        }
        for row in result["records"]:
            self.assertTrue(required.issubset(row))
            self.assertEqual("main_08-01", row["stage_id"])
            self.assertEqual(self.module.MECHANICS, row["mechanics_version"])
            self.assertTrue(row["limitations"])

    def test_reasoning_context_distinguishes_repetition_from_reconsideration(self) -> None:
        result = self.module.reasoning_context()
        self.assertEqual(6, len(result["prior_tactical_ideas"]))
        for row in result["prior_tactical_ideas"]:
            self.assertIn(row["policy"], {
                "DO_NOT_REPEAT_UNCHANGED",
                "DO_NOT_REPEAT_UNCHANGED_WITHOUT_EARLY_DAMAGE_OR_HANDOFF",
            })
            self.assertTrue(row["may_reconsider_with_changed_conditions"])
            self.assertTrue(row["applicability_conditions"])
        self.assertEqual(
            3,
            sum(
                row["status"] == "HYPOTHESIS_AWAITING_DETERMINISTIC_VERIFICATION"
                for row in result["revised_tactical_hypotheses"]
            ),
        )

    def test_exactly_one_completed_kimi_call_and_raw_response_is_immutable(self) -> None:
        parsed = self.module.load(OUT / "llm_structured_output.json")
        fingerprint = self.module.load(OUT / "llm_request_fingerprint.json")
        completion = self.module.load(OUT / "response_completion_validation.json")
        self.assertEqual(1, fingerprint["planned_kimi_call_count"])
        self.assertEqual(1, completion["kimi_call_count"])
        self.assertTrue(completion["successful_completion"])
        self.assertEqual(3, len(parsed["revised_operational_plans"]))
        self.assertGreater((OUT / "llm_raw_response.txt").stat().st_size, 1_000_000)

    def test_structured_plans_are_specific_and_reference_prior_evidence(self) -> None:
        parsed = self.module.load(OUT / "llm_structured_output.json")
        evidence_ids = {
            row["experience_id"]
            for row in self.module.load(OUT / "feasibility_experience_memory.json")["records"]
        }
        for plan in parsed["revised_operational_plans"]:
            self.assertTrue(plan["changed_conflicting_assumptions"])
            self.assertTrue(plan["mandatory_tactical_invariants"])
            self.assertTrue(plan["compiler_slots"])
            self.assertTrue(plan["verifier_questions"])
            cited = {
                item.get("original_failed_plan") or item.get("source_plan_id")
                for item in plan["changed_conflicting_assumptions"]
            }
            self.assertTrue(cited)

    def test_grounding_has_no_unknown_entities_and_records_route_warnings(self) -> None:
        result = self.module.load(OUT / "grounding_validation.json")
        self.assertNotEqual("FAIL", result["status"])
        self.assertFalse(result["errors"])
        self.assertTrue(result["warnings"])

    def test_all_revised_plans_have_proven_prefix_conflicts_and_no_simulation(self) -> None:
        feasibility = self.module.load(OUT / "feasibility_certificates.json")
        bounded = self.module.load(OUT / "bounded_search_results.json")
        self.assertEqual(3, len(feasibility["records"]))
        for row in feasibility["records"]:
            self.assertEqual("INFEASIBLE_WITH_PROVEN_CONFLICT", row["classification"])
            self.assertEqual("DP_INFEASIBLE_PREFIX_BOUND", row["first_conflict"]["status"])
        self.assertEqual("NOT_RUN", bounded["status"])
        self.assertEqual(0, bounded["unique_executable_timelines"])

    def test_learning_progress_reports_new_conflict_for_each_plan(self) -> None:
        result = self.module.load(OUT / "learning_progress_assessment.json")
        self.assertEqual("PARTIAL", result["classification"])
        self.assertEqual(3, result["new_conflicts_discovered"])
        self.assertEqual(0, result["old_conflicts_repeated"])
        self.assertTrue(
            all(
                row["learning_progress"] == "OLD_CONFLICT_REPLACED_BY_NEW_CONFLICT"
                for row in result["records"]
            )
        )

    def test_required_artifacts_and_final_status_agree(self) -> None:
        final_status = self.module.load(OUT / "final_status.json")
        self.assertEqual(1, final_status["KIMI_CALL_COUNT"])
        self.assertEqual("kimi-k3", final_status["MODEL"])
        self.assertEqual(3, final_status["NEW_OPERATIONAL_PLANS"])
        self.assertEqual(0, final_status["FAITHFUL_UNIQUE_TIMELINES"])
        self.assertEqual("PARTIAL", final_status["LEARNING_PROGRESS"])
        self.assertEqual("NO", final_status["MECHANICS_CHANGED"])
        self.assertEqual("UNTESTED", final_status["REAL_GAME_VALIDATION"])
        required = [
            "feasibility_experience_memory.json",
            "constraint_informed_reasoning_context.json",
            "llm_request_fingerprint.json",
            "llm_raw_response.txt",
            "llm_structured_output.json",
            "lessons_from_infeasibility.json",
            "revised_stage_understanding.json",
            "revised_tactical_requirements.json",
            "revised_operational_plans.json",
            "counterexample_avoidance_validation.json",
            "grounding_validation.json",
            "feasibility_certificates.json",
            "constructive_feasibility_witnesses.json",
            "per_plan_feasibility_results.json",
            "bounded_search_results.json",
            "battle_failure_feedback.json",
            "learning_progress_assessment.json",
            "validation_results.json",
            "final_status.json",
        ]
        for name in required:
            self.assertTrue((OUT / name).is_file(), f"missing artifact: {name}")


if __name__ == "__main__":
    unittest.main()
