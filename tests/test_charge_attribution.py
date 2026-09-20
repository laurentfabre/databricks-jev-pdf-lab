"""Fabricated billing inputs only; no service calls or private usage records."""
import copy
from decimal import Decimal
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from charge_attribution import attribution_gate, price_record, reconcile


class ChargeAttributionTests(unittest.TestCase):
    def setUp(self):
        self.row = {'record_id': 'synthetic_1', 'record_type': 'ORIGINAL',
            'account_id': 'a', 'workspace_id': 'w', 'sku_name': 's', 'cloud': 'AWS',
            'usage_unit': 'DBU', 'usage_quantity': '2.123456789012345678',
            'usage_start_time': '2026-01-01T01:00:00Z', 'usage_end_time': '2026-01-01T02:00:00Z',
            'billing_origin_product': 'AI_FUNCTIONS', 'ai_function': 'AI_EXTRACT',
            'usage_metadata': {'job_run_id': 'run1'}}
        self.price = {'account_id': 'a', 'sku_name': 's', 'cloud': 'AWS', 'usage_unit': 'DBU',
            'currency_code': 'USD', 'price_start_time': '2026-01-01T00:00:00Z',
            'price_end_time': None, 'effective_list_rate': '0.07'}
        self.bindings = [{'workspace_id': 'w', 'key': 'job_run_id', 'values': ['run1'],
                         'cohort': 'precision', 'compute_path': 'serverless_jobs'}]
        self.need = [{'cohort': 'precision', 'component': 'extract', 'compute_path': 'serverless_jobs'}]

    def run_rows(self, rows, **kwargs):
        return reconcile(rows, kwargs.get('prices', [self.price]), kwargs.get('bindings', self.bindings))

    def test_exact_decimal(self):
        result = self.run_rows([self.row])
        self.assertEqual(result['totals'][0]['observed_list_usd'], '0.14864197523086419746')
        self.assertFalse(result['complete_cost'])

    def test_no_rows_not_free(self):
        result = self.run_rows([])
        self.assertEqual(result['totals'], [])
        self.assertFalse(result['missing_cost_is_zero'])
        self.assertFalse(attribution_gate(result, self.need, tags_verified=True)['mapping_ready'])

    def test_corrections_same_id_retained(self):
        retraction = self.row | {'record_type': 'RETRACTION', 'usage_quantity': '-2.123456789012345678'}
        restatement = self.row | {'record_type': 'RESTATEMENT', 'usage_quantity': '1'}
        result = self.run_rows([self.row, retraction, restatement, copy.deepcopy(self.row)])
        self.assertEqual(result['observed_records'], 3)
        self.assertEqual(result['duplicate_rows_removed'], 1)
        self.assertEqual(Decimal(result['totals'][0]['observed_list_usd']), Decimal('0.07'))

    def test_retracted_only_not_mapping_proof(self):
        result = self.run_rows([self.row, self.row | {'record_type': 'RETRACTION',
                               'usage_quantity': '-2.123456789012345678'}])
        self.assertFalse(attribution_gate(result, self.need, tags_verified=True)['mapping_ready'])

    def test_no_shared_warehouse_fanout(self):
        row = self.row | {'usage_metadata': {'warehouse_id': 'shared'}}
        result = self.run_rows([row], bindings=[self.bindings[0] |
                    {'key': 'warehouse_id', 'values': ['shared']}])
        self.assertEqual(result['unresolved_rows'], 1)
        self.assertIsNone(result['rows'][0]['attributable_list_usd'])

    def test_ambiguous_mapping_not_double_counted(self):
        result = self.run_rows([self.row], bindings=self.bindings + [self.bindings[0] | {'cohort': 'default'}])
        self.assertEqual(result['totals'], [])
        self.assertEqual(result['rows'][0]['attribution_error'], 'ambiguous_binding')

    def test_asserted_isolation_hash_is_not_evidence(self):
        row = self.row | {'usage_metadata': {'warehouse_id': 'shared'}}
        result = self.run_rows([row], bindings=[self.bindings[0] |
                    {'key': 'warehouse_id', 'values': ['shared'], 'isolation_evidence_sha256': 'f' * 64}])
        self.assertEqual(result['totals'], [])

    def test_workspace_scope(self):
        self.assertEqual(self.run_rows([self.row | {'workspace_id': 'elsewhere'}])['totals'], [])

    def test_rate_join_all_keys(self):
        for key in ('account_id', 'sku_name', 'cloud', 'usage_unit', 'currency_code'):
            result = self.run_rows([self.row], prices=[self.price | {key: 'other'}])
            self.assertEqual(result['rows'][0]['pricing_error'], 'price_matches_0')

    def test_ambiguous_prices_rejected(self):
        result = self.run_rows([self.row], prices=[self.price, self.price])
        self.assertEqual(result['rows'][0]['pricing_error'], 'price_matches_2')

    def test_partial_rate_interval_not_prorated(self):
        result = self.run_rows([self.row], prices=[self.price | {'price_end_time': '2026-01-01T01:30:00Z'}])
        self.assertEqual(result['totals'], [])

    def test_rate_boundary(self):
        self.assertIsNotNone(price_record(self.row, [self.price | {'price_end_time': self.row['usage_end_time']}])[0])

    def test_no_float_or_invalid_signs(self):
        for delta in ({'usage_quantity': 0.1}, {'usage_quantity': 'NaN'},
                      {'usage_quantity': '-1'}, {'record_type': 'RETRACTION'},
                      {'record_type': 'unknown'}, {'usage_end_time': self.row['usage_start_time']}):
            with self.assertRaises(ValueError):
                self.run_rows([self.row | delta])

    def test_tags_not_sufficient(self):
        result = self.run_rows([self.row])
        self.assertFalse(attribution_gate(result, self.need, tags_verified=False)['mapping_ready'])
        self.assertFalse(attribution_gate(result, [], tags_verified=True)['mapping_ready'])

    def test_mapping_ready_not_execution_permission(self):
        result = attribution_gate(self.run_rows([self.row]), self.need, tags_verified=True)
        self.assertTrue(result['mapping_ready'])
        self.assertFalse(result['paid_execution_authorized'])

    def test_different_compute_path_not_proof(self):
        result = attribution_gate(self.run_rows([self.row]), [self.need[0] | {'compute_path': 'dbsql'}], tags_verified=True)
        self.assertFalse(result['mapping_ready'])

    def test_each_component_required(self):
        result = attribution_gate(self.run_rows([self.row]), self.need + [self.need[0] | {'component': 'compute'}], tags_verified=True)
        self.assertFalse(result['mapping_ready'])
