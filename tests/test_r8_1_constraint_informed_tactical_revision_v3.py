from __future__ import annotations

import importlib.util
import gzip
import hashlib
import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/r8_1_constraint_informed_revision_v3"
EVIDENCE = ROOT / "output/r8_1_deadline_295_reclassification_v1"
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
        raw_path = OUT / "llm_raw_response.txt"
        compressed_path = EVIDENCE / "llm_raw_response.txt.gz"
        if raw_path.is_file():
            self.assertGreater(raw_path.stat().st_size, 1_000_000)
        else:
            self.assertTrue(compressed_path.is_file())

    def test_compressed_llm_call_record_matches_original_hash(self) -> None:
        manifest = self.module.load(EVIDENCE / "llm_raw_response_manifest.json")
        compressed_path = ROOT / manifest["delivered_path"]
        self.assertTrue(compressed_path.is_file())
        self.assertEqual(manifest["compression"], "gzip")
        self.assertEqual(
            hashlib.sha256(compressed_path.read_bytes()).hexdigest(),
            manifest["delivered_sha256"],
        )
        with gzip.open(compressed_path, "rb") as handle:
            restored = handle.read()
        self.assertEqual(len(restored), manifest["original_bytes"])
        self.assertEqual(
            hashlib.sha256(restored).hexdigest(),
            manifest["original_sha256"],
        )

    def test_deadline_295_is_reclassified_as_contact_event_not_hard_deadline(self) -> None:
        result = self.module.load(EVIDENCE / "deadline_295_reclassification.json")
        self.assertEqual(
            "DERIVED_EARLIEST_OPERATOR_CONTACT_EVENT_NOT_PROVEN_ESTABLISHMENT_DEADLINE",
            result["corrected_classification"],
        )
        self.assertFalse(result["is_confirmed_hard_deadline"])
        self.assertFalse(result["replacement_deadline_invented"])
        self.assertTrue(result["original_artifacts_preserved"])
        self.assertIn(
            "R8OP-A-MERGED-ANCHOR-REFUND-LATTICE:A03_MERGED_ANCHOR:295",
            result["affected_previous_conflicts"],
        )
        self.assertIn(
            "R8OP-B-UPSTREAM-DAM-AND-RELAY:B04_POCKET_FIRE:295",
            result["affected_previous_conflicts"],
        )
        self.assertIn(
            "R8OP-C-DELAYED-KILLING-BLOCK-EVOLUTION:C03_MERGED_ANCHOR:295",
            result["affected_previous_conflicts"],
        )

    def test_route3_contact_evidence_recomputes_from_gamedata(self) -> None:
        result = self.module.load(EVIDENCE / "route3_contact_evidence.json")
        level = self.module.load(EVIDENCE / "gamedata/level_main_08-01.json")
        enemy = self.module.load(EVIDENCE / "gamedata/enemy_1107_uoffcr.json")
        fragment = next(
            fragment
            for wave in level["waves"]
            for fragment in wave.get("fragments", [])
            if any(
                action.get("actionType") == "SPAWN"
                and action.get("routeIndex") == 3
                and action.get("key") == "enemy_1107_uoffcr"
                for action in fragment.get("actions", [])
            )
        )
        action = next(
            action
            for action in fragment["actions"]
            if action.get("actionType") == "SPAWN"
            and action.get("routeIndex") == 3
            and action.get("key") == "enemy_1107_uoffcr"
        )
        spawn_seconds = (
            float(level["waves"][0].get("preDelay", 0))
            + float(fragment.get("preDelay", 0))
            + float(action.get("preDelay", 0))
        )
        speed = float(
            enemy["enemies"][0]["Value"][0]["enemyData"]["attributes"]["moveSpeed"]["m_value"]
        )
        contact_frame = math.ceil(
            spawn_seconds * 30 + result["earliest_operator_contact_distance"] / speed * 30
        )
        latest_frame = math.ceil(
            spawn_seconds * 30 + result["latest_interception_distance"] / speed * 30
        )
        self.assertEqual(240, result["spawn_frame"])
        self.assertEqual(295, contact_frame)
        self.assertEqual(431, latest_frame)

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
        self.assertTrue((EVIDENCE / "llm_raw_response_manifest.json").is_file())
        self.assertTrue((EVIDENCE / "llm_raw_response.txt.gz").is_file())


if __name__ == "__main__":
    unittest.main()
