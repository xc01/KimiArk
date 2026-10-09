from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_r8_1_plan_a_opening_witness_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("plan_a_opening_witness", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class PlanAOpeningWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_module().build(write_artifacts=False)

    def test_no_witness_is_reported_without_simulation(self):
        status = self.result["final_status"]
        self.assertEqual("NO_FAITHFUL_WITNESS_SCOPED_CONFLICT", status["status"])
        self.assertIsNone(status["witness"])
        self.assertEqual(0, status["stage_prefix_simulations"])
        self.assertEqual(0, status["faithful_complete_combinations"])
        self.assertEqual(0, status["kimi_calls"])
        self.assertEqual(0, status["new_operational_plans"])

    def test_bounded_frontier_stays_within_budget(self):
        frontier = self.result["frontier"]
        self.assertLessEqual(max(frontier["candidate_counts"].values()), 3)
        self.assertLessEqual(frontier["structural_combinations_if_ignoring_gate"], 16)
        self.assertEqual(0, frontier["faithful_complete_combinations"])

    def test_snhunt_difference_is_explained_not_hidden(self):
        audit = self.result["frontier"]["snhunt_audit"]
        self.assertEqual(21, audit["current_pool_size"])
        self.assertEqual(22, audit["missing_table_pool_size"])
        self.assertEqual(["char_4211_snhunt"], audit["missing_table_only_operator_ids"])
        self.assertFalse(audit["present_in_current_pool"])
        self.assertIn("DECISION_CRITICAL_TRAIT_ATK_SCALE_UNSUPPORTED", audit["rejection_reasons"])

    def test_anchor_candidates_fail_plan_capability_or_geometry(self):
        records = [row for row in self.result["frontier"]["candidates"] if row["slot_id"] == "A03_MERGED_ANCHOR"]
        self.assertEqual(3, len(records))
        for record in records:
            self.assertFalse(record["capability_checks"]["meets_damage_floor"])
        self.assertEqual(
            {"char_4100_caper": True, "char_103_angel": False, "char_365_aprl": False},
            {row["operator_id"]: row["geometry"]["any_direction_satisfies_all_required_tiles"] for row in records},
        )

    def test_blocker_traits_and_duelist_gates_block_all_opening_candidates(self):
        records = self.result["frontier"]["candidates"]
        self.assertIn(
            "TRAIT_DESCRIPTION_INDICATES_BLOCK_0_UNTIL_SKILL",
            next(row for row in records if row["operator_id"] == "char_445_wscoot")["qualification_blockers"],
        )
        for row in records:
            if row["slot_id"] in {"A04_C05_DUELIST", "A05_C06_DUELIST"}:
                self.assertIn("DECISION_CRITICAL_TRAIT_UNSUPPORTED", row["qualification_blockers"])

    def test_dp_ledger_keeps_refund_hypothetical(self):
        ledger = self.result["ledger"]
        self.assertFalse(ledger["is_witness"])
        self.assertEqual("UNKNOWN", ledger["confirmed_retreat_refund"]["status"])
        self.assertEqual("NO_REFUND", ledger["confirmed_retreat_refund"]["simulator_behavior"])
        self.assertAlmostEqual(0.7, ledger["conditions"]["A05_WITH_FULL_COST_REFUND_DEFICIT"])
        self.assertAlmostEqual(5.7, ledger["conditions"]["A05_WITHOUT_REFUND_DEFICIT"])

    def test_scoped_conflicts_do_not_claim_global_infeasibility(self):
        conflicts = self.result["final_status"]["scoped_conflicts"]
        self.assertTrue(conflicts)
        self.assertNotIn("GLOBAL_PLAN_INFEASIBLE", {row["classification"] for row in conflicts})
        self.assertEqual("PASS", self.result["validation"]["status"])

    def test_missing_generator_is_explicit_provenance_unknown(self):
        module = load_module()
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            with patch.object(module, "GENERATION_CODE", Path(folder) / "absent.py"):
                provenance = module.fidelity_provenance()
        self.assertEqual("MISSING_FROM_CHECKOUT", provenance["generation_code_provenance"]["current_local_code"]["status"])
        self.assertFalse(provenance["generation_code_provenance"]["original_version_confirmed"])

    def test_multihit_diagnostic_is_not_a_damage_bound(self):
        module = load_module()
        operator = {"attack": 100, "attack_interval_seconds": 1,
                    "skill_sp_cost": 1, "skill_effect": {
                        "next_attack_atk_scale": 2, "next_attack_hit_count": 2}}
        # Simulator cycle: one normal attack gains SP, next skill attack has
        # two separate hits, each paying DEF. 50 + 2*150 over two seconds.
        cycle_damage_per_second = (50 + 2 * 150) / 2
        self.assertNotEqual(cycle_damage_per_second, module.effective_dps(operator, defense=50))
        for row in self.result["frontier"]["candidates"]:
            if row["slot_id"] == "A03_MERGED_ANCHOR":
                self.assertEqual("DIAGNOSTIC_APPROXIMATION_NOT_DAMAGE_BOUND", row["capability_checks"]["evidence_status"])
                self.assertNotIn("ANCHOR_EFFECTIVE_DPS_BELOW_PLAN_FLOOR", row["qualification_blockers"])

    def test_cost_cap_ledger_does_not_prove_candidate_deficit(self):
        # Existing tested caper costs 12, rather than the ledger's 15 cap.
        self.assertAlmostEqual(2.3, 10 + 729 / 30 + 5 - (5 + 8 + 12 + 6 + 6))
        self.assertEqual("COST_CAP_EXAMPLE_NOT_ECONOMIC_LOWER_BOUND", self.result["ledger"]["evidence_status"])
        self.assertTrue(any("COND_ROUTE6" in row for row in self.result["ledger"]["limitations"]))


if __name__ == "__main__":
    unittest.main()
