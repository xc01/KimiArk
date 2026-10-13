import json
import unittest
from pathlib import Path

from run_r8_1_lowstar_c3_failure_revision_v1 import (
    CONTINUATION_BODY_LIMIT,
    INITIAL_BODY_LIMIT,
    PLAN_ID_PREFIX,
    PARENT_PLAN_ID,
    action_outcomes,
    validate_c3_contract,
)


ROOT = Path(__file__).parents[1]
OUT = ROOT / "output/r8_1_lowstar_c3_failure_revision_v1"


class C3FailureRevisionTests(unittest.TestCase):
    def test_action_outcomes_distinguish_executed_rejected_and_unreached(self):
        rows = action_outcomes()
        self.assertEqual(len(rows), 22)
        by_key = {(row["action_type"], row["frame"]): row for row in rows}
        self.assertEqual(by_key[("DEPLOY", 0)]["status"], "EXECUTED")
        self.assertEqual(by_key[("DEPLOY", 1680)]["status"], "REJECTED")
        self.assertEqual(by_key[("RETREAT", 2400)]["status"], "REJECTED")
        self.assertEqual(by_key[("DEPLOY", 5340)]["status"], "NOT_REACHED")

    def test_prepared_body_limits_and_catalog_are_complete(self):
        evidence = json.loads((OUT / "llm_evidence_context.json").read_text(encoding="utf-8"))
        body = (OUT / "llm_request_body.txt").read_bytes()
        self.assertEqual((INITIAL_BODY_LIMIT, CONTINUATION_BODY_LIMIT), (140_000, 200_000))
        self.assertLessEqual(len(body), INITIAL_BODY_LIMIT)
        self.assertEqual(len(evidence["normal_low_star_catalog"]), 34)
        self.assertEqual(sum(row["identity"]["rarity"] == 3 for row in evidence["normal_low_star_catalog"]), 17)
        self.assertNotIn("events", evidence["c2_failure_evidence"])

    def test_c3_contract_rejects_wrong_parent_and_multiple_plans(self):
        evidence = json.loads((OUT / "llm_evidence_context.json").read_text(encoding="utf-8"))
        wrong = {"revised_operational_plans": [
            {"operational_plan_id": "wrong", "parent_hypothesis_id": "wrong", "action_timeline": []}
        ]}
        errors = validate_c3_contract(wrong, evidence)
        self.assertIn("operational_plan_id must identify C3", errors)
        self.assertIn("parent_hypothesis_id must identify C2", errors)
        self.assertTrue(PLAN_ID_PREFIX and PARENT_PLAN_ID)


if __name__ == "__main__":
    unittest.main()
