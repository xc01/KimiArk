from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_r8_1_operational_feasibility_unsat_core_audit_v1.py"


def load_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("feasibility_unsat_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OperationalFeasibilityUnsatCoreAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.repair = cls.module.import_repair_module()
        cls.repair.load_fidelity_tables()
        cls.search = cls.module.import_search_module()
        cls.context = cls.module.load(cls.module.CTX_PATH)
        normalized = cls.module.load(
            cls.module.RECOVER / "normalized_revised_operational_plans.json"
        )
        cls.plans = normalized["revised_operational_plans"]
        cls.patterns = cls.search.PATTERNS
        cls.operators = {row["operator_id"]: row for row in cls.context["operators"]}
        cls.trait_operators = cls.module.trait_aware_operators(cls.operators)
        cls.fidelity = cls.repair.engine_fidelity
        cls.census = cls.repair.engine_census

    def test_constraint_inventory_has_plan_traceable_deadlines(self) -> None:
        result = self.module.constraint_inventory(
            self.plans, self.patterns, self.context, self.repair
        )
        self.assertEqual(5, len(result["records"]))
        self.assertEqual(result["total_constraints"], sum(result["category_counts"].values()))
        for plan_record in result["records"]:
            self.assertTrue(plan_record["constraints"])
            for constraint in plan_record["constraints"]:
                self.assertIn("source", constraint)
                self.assertIn("category", constraint)
                self.assertNotEqual("COMPILER_ASSUMPTION", constraint["category"])

    def test_deadline_semantics_do_not_require_unspecified_skill_charge(self) -> None:
        result = self.module.deadline_semantics_audit(
            self.plans, self.patterns, self.context, self.repair
        )
        for row in result["records"]:
            self.assertIn(
                row["semantic_state"],
                {
                    "MUST_BE_ACTIVE",
                    "MUST_BE_ACTIVE_AND_DP_CAPABLE",
                    "MUST_BE_ACTIVE_WITH_AUTO_SKILL_SUPPORTED",
                    "MUST_HAVE_COVERAGE",
                },
            )
            if row["semantic_state"] == "MUST_BE_ACTIVE_WITH_AUTO_SKILL_SUPPORTED":
                self.assertFalse(row["skill_ready_required"])
        self.assertEqual(3, result["prior_semantic_error_count"])

    def test_minimum_cost_assignment_uses_distinct_legal_operators(self) -> None:
        rows = self.module.deadline_rows(
            "R-OP-01-POCKET-AND-FLOOR",
            self.patterns["R-OP-01-POCKET-AND-FLOOR"],
            self.repair,
            self.context,
        )
        cost, assignment = self.module.minimum_cost_assignment(
            self.context,
            rows[:3],
            trait_aware=False,
            repair=self.repair,
            fidelity_by_id=self.fidelity,
            census_by_id=self.census,
            operators=self.operators,
        )
        self.assertIsNotNone(cost)
        self.assertEqual(3, len(assignment))
        self.assertEqual(len(set(assignment.values())), len(assignment))
        expected = sum(float(self.operators[operator_id]["cost"]) for operator_id in assignment.values())
        self.assertAlmostEqual(cost, expected)

    def test_gross_dp_bound_includes_only_legally_ready_auto_dp(self) -> None:
        operator = dict(self.operators["char_272_strong"])
        initial = 10.0
        rate = 1.0
        late = self.module.gross_dp_bound(200, initial, rate, operator, 0)
        early = self.module.gross_dp_bound(10, initial, rate, operator, 0)
        self.assertGreater(late, initial + 200 * rate / 30 - 1e-9)
        self.assertAlmostEqual(initial + 10 * rate / 30, early)

    def test_optimistic_bounds_preserve_deadline_prefixes(self) -> None:
        result = self.module.optimistic_bounds(
            self.plans,
            self.patterns,
            self.context,
            self.repair,
            self.fidelity,
            self.census,
            self.operators,
            self.trait_operators,
        )
        self.assertEqual(5, len(result["records"]))
        for plan_record in result["records"]:
            for variant in plan_record["variants"]:
                statuses = [row["status"] for row in variant["prefixes"]]
                self.assertIn(
                    variant["status"],
                    {
                        "DP_INFEASIBLE",
                        "FEASIBILITY_NOT_DISPROVEN_BY_DP_BOUND",
                        "NO_DISTINCT_LEGAL_OPERATORS",
                    },
                )
                if "DP_INFEASIBLE" in statuses:
                    self.assertEqual("DP_INFEASIBLE", variant["status"])
                    self.assertIsNotNone(variant["first_infeasible_prefix"])

    def test_exact_ledger_preserves_nonnegative_dp_events(self) -> None:
        result = self.module.exact_dp_ledgers(
            self.plans,
            self.patterns,
            self.context,
            self.repair,
            self.operators,
            self.trait_operators,
            self.fidelity,
            self.census,
        )
        self.assertEqual(5, len(result["records"]))
        for plan_record in result["records"]:
            for variant in plan_record["variants"]:
                previous = 0.0
                for row in variant["ledger"]:
                    if row["event"] == "INITIAL":
                        continue
                    self.assertGreaterEqual(float(row["natural_accrual"]), -1e-9)
                    self.assertGreaterEqual(float(row["frame"]), previous - 1e-9)
                    previous = float(row["frame"])

    def test_unsat_core_reports_conflicting_set_without_false_minimality(self) -> None:
        bounds = self.module.optimistic_bounds(
            self.plans,
            self.patterns,
            self.context,
            self.repair,
            self.fidelity,
            self.census,
            self.operators,
            self.trait_operators,
        )
        inventory = self.module.constraint_inventory(
            self.plans, self.patterns, self.context, self.repair
        )
        result = self.module.unsat_cores(
            bounds,
            inventory,
            self.context,
            self.patterns,
            self.repair,
            self.fidelity,
            self.census,
            self.operators,
            self.trait_operators,
        )
        self.assertEqual(5, len(result["records"]))
        for row in result["records"]:
            if row["core_type"] == "CONFLICTING_CONSTRAINT_SET":
                self.assertEqual("CONFLICTING_CONSTRAINT_SET", row["status"])
            else:
                self.assertEqual("NO_UNSAT_CORE_FROM_DP_BOUND", row["status"])
                self.assertEqual("NONE", row["core_type"])

    def test_relaxation_sensitivity_is_diagnostic_only(self) -> None:
        bounds = self.module.optimistic_bounds(
            self.plans,
            self.patterns,
            self.context,
            self.repair,
            self.fidelity,
            self.census,
            self.operators,
            self.trait_operators,
        )
        inventory = self.module.constraint_inventory(
            self.plans, self.patterns, self.context, self.repair
        )
        cores = self.module.unsat_cores(
            bounds,
            inventory,
            self.context,
            self.patterns,
            self.repair,
            self.fidelity,
            self.census,
            self.operators,
            self.trait_operators,
        )
        result = self.module.relaxation_sensitivity(
            cores,
            self.context,
            self.patterns,
            self.repair,
            self.fidelity,
            self.census,
            self.operators,
            self.trait_operators,
        )
        self.assertTrue(result["diagnostic_only"])
        for row in result["records"]:
            for test in row["tests"]:
                self.assertFalse(test["valid_realization_without_plan_change"])

    def test_op04_and_op05_plan_specific_audits(self) -> None:
        bounds = self.module.optimistic_bounds(
            self.plans,
            self.patterns,
            self.context,
            self.repair,
            self.fidelity,
            self.census,
            self.operators,
            self.trait_operators,
        )
        op04 = self.module.op04_audit(
            self.context,
            self.repair,
            self.fidelity,
            self.census,
            self.operators,
            self.trait_operators,
        )
        op05 = self.module.op05_audit(self.plans, bounds)
        self.assertLessEqual(op04["individual_valid_operator_count"], 9)
        self.assertGreater(len(op04["operator_certificates"]), 0)
        self.assertTrue(op05["triage_contract_preserved"])
        self.assertTrue(any(check["rejected"] for check in op05["checks"]))

    def test_old_certificate_reclassification_keeps_missing_proof_distinct(self) -> None:
        result = self.module.old_certificate_reclassification()
        self.assertGreater(result["records_audited"], 0)
        self.assertEqual(result["records_audited"], sum(result["classification_counts"].values()))
        for row in result["records"]:
            flags = [row["proven_unfaithful"], row["not_sufficiently_verified"], row["indeterminate"]]
            self.assertEqual(1, sum(bool(flag) for flag in flags))
            if row["new_classification"] == "CERTIFICATE_MISSING_PROOF":
                self.assertFalse(row["proven_unfaithful"])

    def test_proven_fixes_are_regression_backed(self) -> None:
        result = self.module.proven_fixes()
        self.assertGreater(len(result["fixes"]), 0)
        for row in result["fixes"]:
            self.assertEqual("FIXED_AND_REGRESSION_TESTED", row["status"])
            self.assertTrue(all((ROOT / path).is_file() for path in row["changed_files"]))


if __name__ == "__main__":
    unittest.main()
