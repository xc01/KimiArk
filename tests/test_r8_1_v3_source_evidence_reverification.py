from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_r8_1_v3_source_evidence_reverification_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("v3_source_reverification", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class V3SourceEvidenceReverificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_module().build()

    def test_frame_295_is_contact_not_fire_deadline(self):
        audit = self.result["audit"]
        self.assertTrue(audit["route3_contact_facts"]["agreement"])
        self.assertEqual(295, audit["route3_contact_facts"]["expected_from_deterministic_context"]["earliest_operator_contact_frame"])
        for record in audit["records"]:
            self.assertFalse(record["frame_295_semantics"]["CONTACT"]["is_establishment_deadline"])
            self.assertFalse(record["frame_295_semantics"]["FIRE"]["is_establishment_deadline"])
            self.assertEqual("UNKNOWN", record["plan_specific_fire_deadline"]["status"])

    def test_three_target_contracts_are_preserved_as_unknown_feasibility(self):
        self.assertEqual(3, self.result["audit"]["summary"]["plans_reverified"])
        self.assertEqual(0, self.result["audit"]["summary"]["constructive_witnesses"])
        self.assertEqual(0, self.result["audit"]["summary"]["simulations"])
        for record in self.result["audit"]["records"]:
            self.assertTrue(record["affordance_reference_valid"])
            self.assertGreater(record["candidate_pool_size"], 0)
            self.assertFalse(record["previous_295_prefix_conflict"]["is_plan_infeasibility_proof"])

    def test_validation_does_not_promote_diagnostic_conflict(self):
        self.assertEqual("PASS", self.result["validation"]["status"])
        self.assertTrue(self.result["validation"]["checks"]["old_conflicts_remain_diagnostic"])
        self.assertEqual("EARLIEST_OPERATOR_CONTACT_EVENT_NOT_FIRE_ESTABLISHMENT_DEADLINE", self.result["final_status"]["frame_295_classification"])


if __name__ == "__main__":
    unittest.main()
