"""Fabricated fixtures only; no real files, network, SQL or model calls."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from bbox_literal_evidence import audit, contains, fragments
from bbox_page_provenance import bindings, UnsupportedResponse


def fixture():
    s = {'type': 'string'}
    schema = {'property_name': s, 'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'name': s, 'details': s, 'prices': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'basis': s, 'amount': {'type': 'number'}}}},
        'source_pages': {'type': 'array', 'items': {'type': 'integer'}},
        'allergens': {'type': 'array', 'items': s}}}}}
    scalar = lambda value, ids: {'value': value, 'citation_ids': ids}
    box = lambda p: {'page_id': p, 'coord': [1, 2, 100, 200]}
    parsed = {'metadata': {'version': '2.0'}, 'error_status': None, 'document': {
        'pages': [{'id': i} for i in range(3)], 'elements': [
            {'id': 10, 'type': 'text', 'bbox': [box(0)], 'content': 'Cabin Amber. 60 min. Café 甲. per person', 'description': None},
            {'id': 20, 'type': 'table', 'bbox': [box(1)], 'content': '<table><tr><td>Cabin Cedar</td><td>per night</td></tr><tr><td>Private</td><td>per visitor</td></tr></table>', 'description': None},
            {'id': 30, 'type': 'figure', 'bbox': [box(2)], 'content': 'Bedroom Bathroom', 'description': 'A shower in the room.'}]}}
    raw = {'error_message': None, 'metadata': {'mode': 'precision', 'version': '2.1', 'chunk_type': 'bbox',
        'pages': [{'id': i} for i in range(3)], 'citations': [{'id': c, 'bbox': [box(i)]} for i,c in enumerate([7,12,20])]},
        'response': {'property_name': scalar('Example Hotel', []), 'items': [
            {'name': scalar('Cabin Amber', [7]), 'details': scalar('Café 甲', [7]),
             'prices': [{'basis': scalar('60 min', [7]), 'amount': scalar(99, [7])}], 'source_pages': [], 'allergens': []},
            {'name': scalar('Cabin Cedar', [12]), 'details': scalar(None, []),
             'prices': [{'basis': scalar('per night', [12]), 'amount': scalar(200, [12])}], 'source_pages': [], 'allergens': []}]}}
    contract = {'bindings': bindings(raw, parsed, schema), 'source_sha256': 'a'*64,
        'physical_pages': 3, 'page_basis': 'full_original_pdf_zero_based'}
    return raw, parsed, schema, contract


class BboxLiteralEvidenceTests(unittest.TestCase):
    def setUp(self): self.args = fixture()
    def rebind(self): self.args[-1]['bindings'] = bindings(*self.args[:3])
    def run_case(self): self.rebind(); return audit(*self.args)
    def field(self): return self.args[0]['response']['items'][0]['prices'][0]['basis']
    def element(self): return self.args[1]['document']['elements'][0]
    def row(self, result=None, path=None):
        result = result or self.run_case()
        path = path or ['items', 0, 'prices', 0, 'basis']
        return next(r for r in result['rows'] if r['path'] == path)
    def status(self): return self.row()['literal_status']

    def test_exact(self):
        row = self.row()
        self.assertEqual(row['literal_status'], 'literal_present_in_cited_content')
        self.assertEqual(row['own_exact_hits'], [{'element_index': 0, 'cell': None}])
    def test_whitespace(self):
        self.element()['content'] = '60\n\tmin'
        row = self.row()
        self.assertEqual(row['literal_status'], 'literal_present_in_cited_content')
        self.assertFalse(row['own_exact_hits'])
    def test_case_preserved(self):
        self.field()['value'] = '60 MIN'
        self.assertEqual(self.status(), 'literal_not_found_in_retained_content')
    def test_unicode(self):
        self.field()['value'] = 'Café 甲'
        self.assertEqual(self.status(), 'literal_present_in_cited_content')
    def test_accents_not_folded(self):
        self.field()['value'] = 'Cafe 甲'
        self.assertEqual(self.status(), 'literal_not_found_in_retained_content')
    def test_numeric_substring_boundary(self):
        self.element()['content'] = '160 min'
        self.assertEqual(self.status(), 'literal_not_found_in_retained_content')
    def test_word_substring_boundary(self):
        self.assertFalse(contains('person', 'per'))
        self.assertFalse(contains('甲乙', '甲'))
        self.assertTrue(contains('(per person)', 'per person'))
    def test_elsewhere(self):
        self.field()['value'] = 'per night'
        self.assertEqual(self.status(), 'literal_only_elsewhere_in_content')
    def test_generated_description_not_source(self):
        self.field().update(value='shower', citation_ids=[20])
        self.assertEqual(self.status(), 'literal_only_in_generated_description')
    def test_no_acceptance_wrong_owner(self):
        self.field().update(value='per visitor', citation_ids=[12])
        result = self.run_case()
        self.assertEqual(self.row(result)['literal_status'], 'literal_present_in_cited_content')
        self.assertFalse(result['quality_accepted'])
        self.assertFalse(result['safe_to_skip_semantic_review'])
        self.assertEqual(result['repairs_applied'], 0)
    def test_cells_never_join(self):
        self.field().update(value='Private per visitor', citation_ids=[12])
        self.assertEqual(self.status(), 'literal_not_found_in_retained_content')
    def test_elements_never_join(self):
        self.field().update(value='per person Cabin Cedar', citation_ids=[7,12])
        self.assertEqual(self.status(), 'literal_not_found_in_retained_content')
    def test_inline_markup_entities(self):
        self.args[1]['document']['elements'][1]['content'] = '<table><tr><td>per <b>night</b><br>A &amp; B</td></tr></table>'
        self.field().update(value='night A & B', citation_ids=[12])
        self.assertEqual(self.status(), 'literal_present_in_cited_content')
    def test_attribute_not_evidence(self):
        self.args[1]['document']['elements'][1]['content'] = '<table><tr><td title="monthly">per night</td></tr></table>'
        self.field().update(value='monthly', citation_ids=[12])
        self.assertEqual(self.status(), 'literal_not_found_in_retained_content')
    def test_nested_table_unknown(self):
        self.args[1]['document']['elements'][1]['content'] = '<table><tr><td><table><tr><td>x</td></tr></table></td></tr></table>'
        self.field().update(value='x', citation_ids=[12])
        self.assertEqual(self.status(), 'cited_projection_unknown')
    def test_uncited_unknown_projection_limits_global_absence(self):
        self.args[1]['document']['elements'][1]['content'] = '<table>bad'
        self.field()['value'] = 'invented'
        self.assertEqual(self.status(), 'not_found_in_available_content_other_projections_unknown')
    def test_markup_outside_table_unknown(self):
        self.element()['content'] = '<span>60 min</span>'
        self.assertEqual(self.status(), 'cited_projection_unknown')
    def test_missing_citation(self):
        self.field()['citation_ids'] = []
        self.assertEqual(self.status(), 'citation_binding_unknown')
    def test_unknown_citation(self):
        self.field()['citation_ids'] = [999]
        self.assertEqual(self.status(), 'citation_binding_unknown')
    def test_duplicate_citation(self):
        self.field()['citation_ids'] = [7,7]
        self.assertEqual(self.status(), 'citation_binding_unknown')
    def test_boolean_citation(self):
        self.field()['citation_ids'] = [True]
        self.assertEqual(self.status(), 'citation_binding_unknown')
    def test_unknown_geometry(self):
        self.args[0]['metadata']['citations'][0]['bbox'][0]['coord'][2] = 101
        self.assertEqual(self.status(), 'citation_binding_unknown')
    def test_ambiguous_geometry(self):
        elem = deepcopy(self.element()); elem['id'] = 40
        self.args[1]['document']['elements'].append(elem)
        self.assertEqual(self.status(), 'citation_binding_unknown')
    def test_invalid_metadata(self):
        self.args[0]['metadata']['citations'][0]['bbox'][0]['page_id'] = 9
        with self.assertRaises(UnsupportedResponse): self.run_case()
    def test_duplicate_metadata_id(self):
        self.args[0]['metadata']['citations'].append(deepcopy(self.args[0]['metadata']['citations'][0]))
        with self.assertRaises(UnsupportedResponse): self.run_case()
    def test_stale_binding(self):
        self.field()['value'] = 'changed'
        with self.assertRaises(ValueError): audit(*self.args)
    def test_incomplete_pages(self):
        self.args[1]['document']['pages'].pop()
        with self.assertRaises(ValueError): self.run_case()
    def test_wrong_mode(self):
        self.args[0]['metadata']['mode'] = 'standard'
        with self.assertRaises(UnsupportedResponse): self.run_case()
    def test_error_result(self):
        self.args[0]['response'] = None
        with self.assertRaises(UnsupportedResponse): self.run_case()
    def test_derived_result_not_raw(self):
        self.args[0]['derivation'] = {}
        with self.assertRaises(UnsupportedResponse): self.run_case()
    def test_all_schema_paths_accounted(self):
        result = self.run_case()
        missing = [c for c in result['schema_coverage'] if c['concrete_slots'] == 0]
        self.assertEqual({c['schema_path'] for c in missing}, {'items[].allergens[]','items[].source_pages[]'})
    def test_null_not_source_absence(self):
        self.field()['value'] = None
        row = self.row()
        self.assertEqual(row['source_presence'], 'unknown')
        self.assertNotIn('literal_status', row)
    def test_missing_field_not_source_absence(self):
        del self.args[0]['response']['items'][0]['prices'][0]['basis']
        self.assertEqual(self.row()['occupancy'], 'missing')
    def test_empty_array_not_source_absence(self):
        row = self.row(path=['items',0,'allergens'])
        self.assertEqual(row['occupancy'], 'empty_source_presence_unknown')
    def test_numbers_not_validated_as_strings(self):
        row = self.row(path=['items',0,'prices',0,'amount'])
        self.assertNotIn('literal_status', row)
        self.assertFalse(row['accepted'])
    def test_group_paths_do_not_merge_facts(self):
        result = self.run_case()
        group = next(g for g in result['groups'] if g['element_indices'] == [0])
        self.assertEqual(len(group['field_paths']), 3)
        self.assertGreater(result['counts']['repeated_cited_content_bytes'], result['counts']['unique_cited_content_bytes'])
    def test_input_preserved(self):
        before = deepcopy(self.args)
        result = audit(*self.args)
        self.assertEqual(self.args, before)
        self.assertTrue(result['raw_unchanged'])
    def test_no_citation_inheritance(self):
        self.args[0]['response']['items'][0]['prices'][0]['basis'] = '60 min'
        self.assertEqual(self.status(), 'scalar_wrapper_unknown')
    def test_empty_string(self):
        self.field()['value'] = ''
        self.assertNotIn('literal_status', self.row())
    def test_duplicate_element_id_rejected(self):
        self.args[1]['document']['elements'][1]['id'] = 10
        with self.assertRaises(ValueError): self.run_case()


if __name__ == '__main__': unittest.main()
