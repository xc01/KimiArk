from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest
import copy


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_r8_1_plan_a1_bounded_validation_v1.py"
OUT = ROOT / "output/r8_1_plan_a1_bounded_validation_v1"
KIMI_OUT = ROOT / "output/r8_1_plan_a_bounded_kimi_revision_v4"


def load_module():
    spec = importlib.util.spec_from_file_location("plan_a1_bounded_validation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class PlanA1BoundedValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = None
        cls.frontier = json.loads((OUT / "bounded_candidate_frontier.json").read_text())
        cls.certificate = json.loads((OUT / "operational_certificate.json").read_text())
        cls.plan = json.loads((OUT / "revised_operational_plan.json").read_text())
        cls.validation = json.loads((OUT / "validation_results.json").read_text())
        cls.status = json.loads((OUT / "final_status.json").read_text())
        cls.completion = json.loads((KIMI_OUT / "response_completion_validation.json").read_text())
        cls.structured = json.loads((KIMI_OUT / "llm_structured_output.json").read_text())

    def test_single_completed_kimi_call_and_single_plan(self):
        self.assertTrue(self.completion["complete"])
        self.assertEqual("kimi-k3", self.completion["model"])
        self.assertEqual(1, json.loads((KIMI_OUT / "llm_call_record.json").read_text())["call_count"])
        self.assertEqual(1, len(self.structured["revised_operational_plans"]))

    def test_kimi_absorbs_counterexamples_without_frame_250_deadline(self):
        text = json.dumps(self.plan, ensure_ascii=False)
        self.assertIn("R8OP-A1-BLOCK1-COOP-ANCHOR390", text)
        self.assertIn("Frame 250 is never used", text)
        self.assertIn("wscoot", text)
        self.assertGreaterEqual(len(self.plan["changed_conflicting_assumptions"]), 5)

    def test_bounded_frontier_and_distinct_operators(self):
        self.assertLessEqual(max(self.frontier["candidate_counts"].values()), 3)
        self.assertEqual(2, len(self.frontier["combinations"]))
        self.assertTrue(all(row["distinct_live_operators"] for row in self.frontier["combinations"]))
        self.assertEqual(0, self.frontier["limits"]["stage_simulations"])

    def test_action_candidate_and_no_full_witness(self):
        actions = self.certificate["action_candidate"]["actions"]
        self.assertTrue(self.certificate["action_candidate"]["direction_complete"])
        self.assertEqual(5, len(actions))
        self.assertEqual(1, sum(row["action_type"] == "RETREAT" for row in actions))
        self.assertFalse(self.certificate["witness"]["complete_faithful_witness"])
        self.assertIn("COND_ANCHOR_TILE", " ".join(self.certificate["witness"]["reasons_not_full_witness"]))

    def test_dp_ledger_assumes_no_refund_and_omits_a05(self):
        ledger = json.loads((OUT / "dp_ledger.json").read_text())
        self.assertEqual("NOT_USED", ledger["hypothetical_refund"])
        self.assertFalse(any("A05" in row["event"] for row in ledger["rows"]))
        self.assertAlmostEqual(0.0, ledger["rows"][3]["available_dp_after"])

    def test_conditional_route3_and_geometry(self):
        damage = self.certificate["finite_window_damage"]
        cooperation = damage["talr_and_caper_cooperation"]
        self.assertLess(cooperation["route_1"]["kill_frame"], 459)
        self.assertLess(cooperation["route_3"]["kill_frame"], 941)
        self.assertLess(damage["caper_only_route_1_if_first_attack_474"]["kill_frame"], 805)
        geometry = json.loads((OUT / "geometry_certificate.json").read_text())
        self.assertTrue(next(row for row in geometry["rows"] if row["operator_id"] == "char_4100_caper")["covers_8_5"])

    def test_validation_is_not_tactical_success(self):
        self.assertEqual("PASS", self.validation["status"])
        self.assertEqual("NOT_EXECUTED_BY_THIS_VALIDATOR", self.validation["test_execution_status"])
        self.assertEqual("BOUNDED_VALIDATION_COMPLETE_CONDITIONAL_ACTION_CANDIDATE_NO_FULL_WITNESS", self.status["status"])
        self.assertFalse(self.status["faithful_witness"])

    def test_cooperation_keeps_attack_and_sp_sequence_across_handoff(self):
        module = load_module()
        trace = module.combined_sequence(module.load(module.CENSUS))
        caper = [row for route in trace.values() for row in route["events"] if row["source"] == "char_4100_caper"]
        self.assertEqual(list(range(390, 601, 30)), [row["attack_frame"] for row in caper])
        self.assertEqual(["NORMAL", "NORMAL", "NORMAL", "SKILL"] * 2, [row["kind"] for row in caper])
        self.assertEqual(194, trace["route_3"]["events"][0]["damage_after_def"])
        self.assertEqual(450, trace["route_3"]["events"][0]["attack_frame"])

    def test_changed_plan_tile_cannot_pass_unchanged_hardcoded_actions(self):
        module = load_module()
        plan = copy.deepcopy(self.plan)
        plan["deployment_positions_and_directions"][2]["tile"] = [6, 2]
        certificate = module.operational_certificate(plan, module.load(module.CENSUS))
        validation = module.validate(plan, module.candidate_frontier(), certificate)
        self.assertEqual("FAIL", validation["status"])
        self.assertFalse(validation["checks"]["selected_actions_match_plan_default_units_and_tiles"])

    def test_conditional_arithmetic_is_not_ready_for_prefix_simulation(self):
        module = load_module()
        certificate = module.operational_certificate(self.plan, module.load(module.CENSUS))
        self.assertFalse(certificate["witness"]["prefix_simulation_ready"])
        self.assertIn("COND_UPKEEP", certificate["witness"]["unresolved_execution_guards"])
        self.assertEqual("CONDITIONAL_ARITHMETIC_NOT_STAGE_EXECUTION_CERTIFICATE", certificate["finite_window_damage"]["evidence_status"])


if __name__ == "__main__":
    unittest.main()
