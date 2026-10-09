from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/operator_runtime_fidelity_v1"


def load(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


class OperatorRuntimeFidelityV1Tests(unittest.TestCase):
    def test_census_and_fidelity_are_complete_and_aligned(self) -> None:
        census = load("all_operator_census.json")
        fidelity = load("all_operator_fidelity.json")
        self.assertEqual(census["operator_count"], 305)
        self.assertEqual(fidelity["operator_count"], 305)
        self.assertEqual({item["operator_id"] for item in census["operators"]}, {item["operator_id"] for item in fidelity["operators"]})

    def test_available_low_rarity_operators_are_all_audited(self) -> None:
        audit = load("low_rarity_deep_audit.json")
        records = audit["operators"]
        self.assertTrue(audit["all_1_3_star_operators_audited"])
        self.assertEqual(len(records), 34)
        self.assertEqual(len({item["operator_id"] for item in records}), 34)
        self.assertTrue(all({"normal_attack", "trait", "talent", "skills", "overall"} <= set(item) for item in records))

    def test_low_rarity_smoke_regressions_are_deterministic(self) -> None:
        result = load("low_rarity_regression_results.json")
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["passed"], 22)

    def test_fidelity_classification_summary_matches_records(self) -> None:
        fidelity = load("all_operator_fidelity.json")
        summary = load("all_rarity_classification_summary.json")
        expected = {}
        for item in fidelity["operators"]:
            expected[item["overall"]] = expected.get(item["overall"], 0) + 1
        self.assertEqual(summary["classification_counts"], expected)
