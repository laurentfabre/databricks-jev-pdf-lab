import copy
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from selective_parse import discrepancy, page_range, rehearse


def fixture(n=3):
    native = [{'page': p, 'text': f'Room {p} 45.5 m2', 'words': [[1, 2, 3, 4, 'Room', 0, 0, 0]]} for p in range(1, n+1)]
    parsed = {'document': {'pages': [{'id': p} for p in range(n)], 'elements': [
        {'id': p, 'type': 'text', 'content': f'Room {p+1} 45.5 m2', 'bbox': [{'page_id': p, 'coord': [0, 0, 9, 9]}]}
        for p in range(n)]}, 'error_status': None, 'metadata': {'version': '2.0'}}
    return native, parsed, {p: 'native_layout_precision' for p in range(1, n+1)}


class SelectiveParseTests(unittest.TestCase):
    def test_ranges_original_one_based(self):
        self.assertEqual(page_range([7, 1, 5, 6, 3], 8), '1,3,5-7')
        self.assertEqual(page_range([], 3), '')

    def test_bad_ranges(self):
        for pages in ([0], [True], [4], [1, 1], [1.0]):
            with self.assertRaises(ValueError): page_range(pages, 3)

    def test_native_exact_and_inputs_unmodified(self):
        native, parsed, routes = fixture()
        before = copy.deepcopy((native, parsed, routes))
        r = rehearse(1, native, parsed, routes)
        self.assertEqual([p['native'] for p in r['bundle']['pages']], native)
        self.assertEqual((native, parsed, routes), before)
        self.assertEqual(r['managed_pages'], [])
        self.assertFalse(r['quality_accepted'])

    def test_managed_all_retains_exact_elements(self):
        n, p, r = fixture()
        r = {k: 'managed_parse_precision' for k in r}
        out = rehearse(1, n, p, r)
        self.assertEqual(out['bundle']['managed_elements'], p['document']['elements'])
        self.assertEqual(out['managed_page_range'], '1-3')

    def test_cross_page_transitive_closure(self):
        n, p, r = fixture()
        p['document']['elements'][0]['bbox'].append({'page_id': 1})
        p['document']['elements'][1]['bbox'].append({'page_id': 2})
        r[1] = 'managed_parse_precision'
        out = rehearse(1, n, p, r)
        self.assertEqual(out['cross_page_promotions'], [2, 3])
        self.assertEqual(len(out['bundle']['managed_elements']), 3)

    def test_review_not_resolved(self):
        n, p, r = fixture()
        r[2] = 'visual_review'
        out = rehearse(1, n, p, r)
        self.assertEqual(out['review_pages'], [2])
        self.assertTrue(out['comparisons'][1]['original_review_unresolved'])

    def test_unlocated_is_retained_unresolved(self):
        n, p, r = fixture()
        p['document']['elements'][1]['bbox'] = []
        out = rehearse(1, n, p, r)
        self.assertEqual(out['bundle']['unlocated_element_ids'], [1])
        self.assertEqual(out['bundle']['managed_elements'], [p['document']['elements'][1]])

    def test_duplicate_managed_pages(self):
        n, p, r = fixture()
        p['document']['pages'][1]['id'] = 0
        with self.assertRaises(ValueError): rehearse(1, n, p, r)

    def test_duplicate_element_ids(self):
        n, p, r = fixture()
        p['document']['elements'][1]['id'] = 0
        with self.assertRaises(ValueError): rehearse(1, n, p, r)

    def test_bad_bbox_ids(self):
        for bad in (-1, 3, True, '0'):
            n, p, r = fixture()
            p['document']['elements'][0]['bbox'][0]['page_id'] = bad
            with self.assertRaises(ValueError): rehearse(1, n, p, r)

    def test_native_or_route_missing_page_rejected(self):
        n, p, r = fixture()
        with self.assertRaises(ValueError): rehearse(1, n[:-1], p, r)
        del r[2]
        with self.assertRaises(ValueError): rehearse(1, n, p, r)

    def test_unknown_route_rejected(self):
        n, p, r = fixture()
        r[1] = 'guess'
        with self.assertRaises(ValueError): rehearse(1, n, p, r)

    def test_parser_errors_rejected(self):
        n, p, r = fixture()
        p['error_status'] = [{'page_id': 1}]
        with self.assertRaises(ValueError): rehearse(1, n, p, r)

    def test_known_native_implementation_veto(self):
        n, p, r = fixture(12)
        out = rehearse(8, n, p, r)
        self.assertEqual(out['managed_pages'], [12])
        self.assertEqual(out['vetoes'][0]['physical_page'], 12)

    def test_disagreement_is_not_semantic_label(self):
        out = discrepancy('A room 45.5 m2', [{'type': 'figure', 'content': 'A suite 46.5 m2', 'description': 'pool'}])
        self.assertEqual(out['managed_numeric_lexemes_not_in_native'], {'46.5': 1})
        self.assertEqual(out['figure_descriptions'], 1)
        self.assertEqual(out['semantic_correctness'], 'not_evaluated')

    def test_repeated_word_multiplicity(self):
        out = discrepancy('room', [{'type': 'text', 'content': 'room room'}])
        self.assertEqual(out['managed_token_discrepancies'], {'room': 1})


if __name__ == '__main__': unittest.main()
