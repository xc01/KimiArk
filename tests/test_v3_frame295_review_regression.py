"""Synthetic adapter fixtures test proof discipline, not Arknights mechanics."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/run_r8_1_constraint_informed_tactical_revision_v3.py'


def load_module():
    spec = importlib.util.spec_from_file_location('v3_review_regression', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Frame295ProofDisciplineTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.parsed = json.loads((ROOT / 'output/r8_1_constraint_informed_revision_v3/llm_structured_output.json').read_text())

    def analyze(self, parsed=None, missing_deadline=False, empty_pool=False):
        parsed = parsed or self.parsed
        deadlines = {'route-2:BLOCK': 27, 'route-1:BLOCK': 191,
                     'route-3:FIRE': 295, 'route-3:BLOCK': 431,
                     'route-7:BLOCK': 725, 'route-6:BLOCK': 729}
        routes = {s['deadline_basis'].split(':')[0]: {'route_id': s['deadline_basis'].split(':')[0], 'spawn_frames': [1000]}
                  for p in parsed['revised_operational_plans'] for s in p['compiler_slots']}
        if missing_deadline:
            routes = {'route-2': {'spawn_frames': [27]}}
        adapter = SimpleNamespace(
            load_fidelity_tables=lambda: None,
            route_map=lambda context: routes,
            establishment_deadline=lambda route, kind: None if missing_deadline or route is None else deadlines.get(f'{route["route_id"]}:{kind}'),
        )
        costs = {'A01': 5, 'A02': 8, 'A03': 9, 'B01': 5, 'B02': 7, 'B04': 9,
                 'C01': 5, 'C02': 8, 'C03': 9}
        def pool(context, repair, slot, all_slots):
            if empty_pool:
                return []
            return [{'operator_id': slot['slot_id'], 'cost': costs.get(slot['slot_id'][:3], 6)}]
        with patch.object(self.module, 'import_repair', return_value=adapter), \
             patch.object(self.module, 'load', side_effect=lambda p: {} if p == self.module.CONTEXT else parsed), \
             patch.object(self.module, 'plan_capability_pool', side_effect=pool):
            return self.module.feasibility_analysis()

    def test_three_295_conflicts_do_not_prove_three_plan_failures(self):
        result = self.analyze()
        for row, expected_cost in zip(result['records'], [22, 21, 22]):
            self.assertEqual('FEASIBILITY_UNKNOWN', row['classification'])
            self.assertEqual(295, row['first_conflict']['deadline_frame'])
            self.assertEqual(expected_cost, row['first_conflict']['minimum_cost'])
            self.assertEqual('DP_CONFLICT_UNDER_SIMPLIFIED_ASSUMPTIONS', row['first_conflict']['status'])
            self.assertTrue(row['proof_limitations'])

    def test_lowercase_retreat_basis_is_not_lost(self):
        for row in self.analyze()['records']:
            self.assertIn('RETREAT_REFUND_AMOUNT_AND_TIMING', row['required_unverified_conditions'])

    def test_unknown_deadline_does_not_become_spawn_deadline(self):
        plan = self.parsed['revised_operational_plans'][0]
        parsed = {'revised_operational_plans': [{**plan, 'compiler_slots': plan['compiler_slots'][:1]}]}
        row = self.analyze(parsed=parsed, missing_deadline=True)['records'][0]
        self.assertEqual([], row['prefix_results'])
        self.assertIsNone(row['first_conflict'])
        self.assertEqual('FEASIBILITY_UNKNOWN', row['classification'])

    def test_empty_pool_is_not_a_numeric_dp_proof(self):
        row = self.analyze(empty_pool=True)['records'][0]
        self.assertIsNone(row['first_conflict']['minimum_cost'])
        self.assertEqual('CANDIDATE_POOL_EMPTY', row['first_conflict']['status'])
        self.assertEqual('FEASIBILITY_UNKNOWN', row['classification'])

    def test_missing_dependencies_do_not_partially_overwrite_evidence(self):
        with patch.object(self.module, 'grounding_validation', side_effect=FileNotFoundError('fixture missing context')), \
             patch.object(self.module, 'write') as writer:
            with self.assertRaises(FileNotFoundError):
                self.module.postprocess()
            writer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
