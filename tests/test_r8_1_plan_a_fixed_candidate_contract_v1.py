from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_r8_1_plan_a_fixed_candidate_contract_v1.py"
GENERATION_CODE = ROOT / "scripts/build_operator_runtime_fidelity.py"


def load_module():
    spec = importlib.util.spec_from_file_location("plan_a_fixed_contract", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class PlanAFixedCandidateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_module().build(write_artifacts=False)

    def test_uses_only_saved_candidates_and_combinations(self):
        self.assertEqual(
            {
                "A01_C03_STUB": 1,
                "A02_C01_DAM": 1,
                "A03_MERGED_ANCHOR": 3,
                "A04_C05_DUELIST": 2,
                "A05_C06_DUELIST": 2,
            },
            self.result["candidate_counts"],
        )
        self.assertEqual(12, len(self.result["structural_combinations"]))
        self.assertLessEqual(len(self.result["structural_combinations"]), 16)

    def test_caper_finite_model_finds_route1_pass_and_route3_model_failure(self):
        contract = next(
            row for row in self.result["finite_window_damage"]["candidate_contracts"]
            if row["operator_id"] == "char_4100_caper"
        )
        self.assertEqual(780, contract["route_contracts"]["route-1"]["kill_frame"])
        self.assertTrue(contract["route_contracts"]["route-1"]["passes_deadline"])
        self.assertEqual(1140, contract["route_contracts"]["route-3"]["kill_frame"])
        self.assertFalse(contract["route_contracts"]["route-3"]["passes_deadline"])
        self.assertFalse(contract["finite_window_deadline_contract_pass"])
        self.assertEqual(250, contract["latest_first_attack_frame_if_targets_stay_on_tile"])

    def test_other_anchors_have_no_required_tile_coverage(self):
        statuses = {
            row["operator_id"]: row["evidence_status"]
            for row in self.result["finite_window_damage"]["candidate_contracts"]
        }
        self.assertEqual("NOT_APPLICABLE_NO_REQUIRED_TILE_COVERAGE", statuses["char_103_angel"])
        self.assertEqual("NOT_APPLICABLE_NO_REQUIRED_TILE_COVERAGE", statuses["char_365_aprl"])

    def test_actual_candidate_base_cost_ledger_preserves_cond_route6(self):
        caper = next(
            row for row in self.result["economy"]["branches"]
            if row["anchor_cost"] == 12.0
        )
        no_refund = caper["no_refund_current_simulator"]
        self.assertEqual(450, no_refund["anchor_deploy_frame"])
        self.assertEqual(-2.7, no_refund["a05_without_refund_dp_after"])
        self.assertEqual(2.7, no_refund["a05_without_refund_deficit_after_deployment"])
        self.assertEqual("OMIT_A05_AND_CONCEDE_ROUTE_6", no_refund["cond_route6_branch"])
        self.assertEqual("HYPOTHETICAL_NOT_SOURCE_CONFIRMED", caper["hypothetical_full_cost_refund"]["status"])

    def test_no_fixed_combination_is_claimed_faithful(self):
        self.assertFalse(self.result["final_status"]["faithful_witness"])
        self.assertTrue(all(not row["faithful_witness"] for row in self.result["structural_combinations"]))
        self.assertIn("ORIGIN_9_2_ROADBLOCK_DEPLOYMENT_LEGALITY_UNKNOWN", self.result["structural_combinations"][0]["qualification_blockers"])

    def test_historical_inputs_and_artifacts_are_preserved(self):
        provenance = self.result["source_manifest"]["inputs"]["build_operator_runtime_fidelity.py"]
        digest = hashlib.sha256(GENERATION_CODE.read_bytes()).hexdigest()
        self.assertEqual(
            "ab63a4e52f9d5ef3e6bd4c0be53af812eff67dcf9849b8200942adead50b7212",
            provenance["sha256"],
        )
        self.assertEqual(digest, provenance["sha256"])
        self.assertEqual("UNKNOWN_ORIGINAL_GENERATION_COMMIT", self.result["source_manifest"]["generation_code_is_original_table_generator"])

    def test_bounded_scope_is_preserved(self):
        self.assertEqual(0, self.result["stage_prefix_simulations"])
        self.assertEqual(0, self.result["kimi_calls"])
        self.assertEqual(0, self.result["new_operational_plans"])
        self.assertEqual("NOT_PERFORMED", self.result["tactical_revision"])
        self.assertEqual("PASS", self.result["validation"]["status"])


if __name__ == "__main__":
    unittest.main()
