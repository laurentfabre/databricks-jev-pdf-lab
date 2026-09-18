import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cache_contract import contract_key, decide, digest
from provenance import attach_single_page


class ProvenanceTests(unittest.TestCase):
    def fixture(self):
        text = '[SOURCE PAGE 3]\n[REGION 2]\nA wine 305€'
        raw = {'metadata': {'mode': 'precision', 'version': '2.1'}, 'error_message': None,
               'response': {'items': [{'name': {'value': 'Wine'}, 'source_pages': [4]}],
                            'policies': [], 'dietary_allergen_legend': []}}
        return raw, text, hashlib.sha256(text.encode()).hexdigest()

    def test_attach_keeps_raw_and_claims_unchanged(self):
        raw, text, sha = self.fixture()
        original = copy.deepcopy(raw)
        result, audit = attach_single_page(raw, text, sha, [3])
        self.assertEqual(result['items'][0], {'name': 'Wine', 'source_pages': [3]})
        self.assertEqual(raw, original)
        self.assertEqual(audit['semantic_support'], 'not_proven')
        self.assertEqual(len(audit['changes']), 1)

    def test_reject_multipage_or_inconsistent_map(self):
        for pages in ([3, 4], [4], [True], []):
            raw, text, sha = self.fixture()
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                attach_single_page(raw, text, sha, pages)

    def test_reject_input_tampering(self):
        raw, text, sha = self.fixture()
        with self.assertRaises(ValueError):
            attach_single_page(raw, text + ' modified', sha, [3])


class CacheTests(unittest.TestCase):
    def fixture(self):
        contract = {'workspace_id': 'example-workspace', 'source_sha256': 'a'*64,
            'input_sha256': 'b'*64, 'source_pages': [3], 'parser_recipe': 'test_fixture_v1',
            'schema_sha256': 'c'*64, 'instructions_sha256': 'd'*64,
            'function': 'ai_extract', 'version': '2.1', 'mode': 'precision',
            'citations': True, 'confidence_scores': False, 'postprocessor': 'none',
            'validation_scope': 'synthetic_fixture_only', 'validation_revision': 'v1'}
        response = {'fixture': 'NOT a hotel result'}
        sha = digest(response)
        entry = {'contract_key': contract_key(contract), 'state': 'SUCCEEDED',
            'response': response, 'response_sha256': sha,
            'validation': {'accepted': True, 'scope': 'synthetic_fixture_only',
                'revision': 'v1', 'response_sha256': sha, 'evidence_id': 'unit-test',
                'expires_epoch': 2000}}
        return contract, entry

    def test_hit_has_zero_inference_dispatch(self):
        contract, entry = self.fixture()
        result = decide(contract, entry, 1000)
        self.assertEqual(result['action'], 'reuse')
        self.assertEqual(result['ai_calls'], 0)

    def test_each_semantic_dimension_invalidates(self):
        contract, entry = self.fixture()
        changes = {'source_sha256': 'e'*64, 'input_sha256': 'e'*64,
            'schema_sha256': 'e'*64, 'instructions_sha256': 'e'*64,
            'source_pages': [4], 'parser_recipe': 'changed', 'citations': False,
            'confidence_scores': True, 'postprocessor': 'changed',
            'validation_scope': 'full_benchmark', 'validation_revision': 'v2'}
        for field, value in changes.items():
            changed = dict(contract, **{field: value})
            with self.subTest(field=field):
                self.assertEqual(decide(changed, entry, 1000)['action'], 'miss')

    def test_workspace_and_precision_cannot_change_silently(self):
        contract, entry = self.fixture()
        for field, value in [('workspace_id', 'other'), ('mode', 'fast'), ('version', '2.0')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                decide(dict(contract, **{field: value}), entry, 1000)

    def test_unaccepted_results_route_to_review_not_inference(self):
        contract, entry = self.fixture()
        entry['validation']['accepted'] = False
        result = decide(contract, entry, 1000)
        self.assertEqual(result['action'], 'review')
        self.assertEqual(result['ai_calls'], 0)

    def test_expiration_and_integrity(self):
        contract, entry = self.fixture()
        self.assertEqual(decide(contract, entry, 2000)['reason'], 'validation_expired_or_unbounded')
        entry['response']['fixture'] = 'changed'
        self.assertEqual(decide(contract, entry, 1000)['reason'], 'response_integrity_failure')

    def test_pending_statement_is_resumed(self):
        contract, entry = self.fixture()
        entry.update(state='RUNNING', statement_id='retained-id')
        result = decide(contract, entry, 1000)
        self.assertEqual(result['action'], 'resume')
        self.assertEqual(result['statement_id'], 'retained-id')

    def test_validation_bound_to_output_scope_and_revision(self):
        for field in ('scope', 'revision', 'response_sha256', 'evidence_id'):
            contract, entry = self.fixture()
            entry['validation'][field] = ''
            with self.subTest(field=field):
                self.assertEqual(decide(contract, entry, 1000)['action'], 'review')


if __name__ == '__main__':
    unittest.main()
