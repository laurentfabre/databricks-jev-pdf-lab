import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from quality_gates import assess_extraction, unwrap


class QualityGateTests(unittest.TestCase):
    def fixture(self):
        return {'metadata': {'mode': 'precision', 'version': '2.1'},
                'error_message': None,
                'response': {'languages': ['fr'], 'items': [{'name': {'value': 'Soup'},
                    'source_pages': [{'value': 1, 'citation_ids': []}]}],
                    'policies': [], 'dietary_allergen_legend': []}}

    def test_structural_pass_never_implies_semantic_acceptance(self):
        result = assess_extraction(self.fixture(), 7)
        self.assertEqual(result['structural_status'], 'pass')
        self.assertFalse(result['accepted'])
        self.assertEqual(result['semantic_status'], 'not_evaluated')

    def test_null_success_response_fails(self):
        result = assess_extraction({'error_message': None, 'response': {
            'items': {'value': None}}}, 19)
        self.assertIn('no_items', result['failures'])
        self.assertIn('precision_mode_not_confirmed', result['failures'])

    def test_missing_pages_fail_even_with_citations(self):
        raw = self.fixture()
        raw['response']['items'][0]['source_pages'] = []
        raw['metadata']['citations'] = [{'id': 0, 'bbox': [{'page_id': 0}]}]
        self.assertIn('explicit_page_provenance_missing', assess_extraction(raw, 7)['failures'])

    def test_invalid_pages(self):
        for pages in ([0], [8], [True], ['1']):
            with self.subTest(pages=pages):
                raw = self.fixture()
                raw['response']['items'][0]['source_pages'] = pages
                self.assertIn('explicit_page_provenance_invalid', assess_extraction(raw, 7)['failures'])

    def test_raw_result_not_mutated(self):
        raw = self.fixture()
        original = copy.deepcopy(raw)
        assess_extraction(raw, 7)
        self.assertEqual(raw, original)

    def test_missing_response(self):
        self.assertIn('response_not_object', assess_extraction({}, 7)['failures'])

    def test_real_value_property_is_not_discarded(self):
        self.assertEqual(unwrap({'value': 3, 'unit': 'cl'}), {'value': 3, 'unit': 'cl'})

    def test_service_error_never_passes(self):
        raw = self.fixture()
        raw['error_message'] = 'failed'
        self.assertEqual(assess_extraction(raw, 7)['structural_status'], 'fail')

    def test_page_inside_document_but_outside_input_fails(self):
        raw = self.fixture()
        result = assess_extraction(raw, 30, {3})
        self.assertIn('explicit_page_outside_input_scope', result['failures'])
        self.assertEqual(result['records_outside_input_pages'], 1)

    def test_allowed_input_page_passes(self):
        self.assertEqual(assess_extraction(self.fixture(), 30, {1})['structural_status'], 'pass')


if __name__ == '__main__':
    unittest.main()
