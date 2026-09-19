"""Fabricated dictionaries only; no document processing, SQL, network or model."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from bbox_page_provenance import UnsupportedResponse, bindings, derive, restore


def fixture():
    string = {'type': 'string'}
    pages = {'type': 'array', 'items': {'type': 'integer'}}
    schema = {
        'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'name': string, 'details': string, 'amount': {'type': 'number'},
            'tags': {'type': 'array', 'items': string}, 'source_pages': pages}}},
        'policies': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'text': string, 'source_pages': pages}}},
        'dietary_allergen_legend': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'meaning': string, 'source_pages': pages}}}}
    box = lambda page: {'coord': [1, 2, 10, 20], 'page_id': page}
    scalar = lambda value, ids: {'value': value, 'citation_ids': ids}
    parsed = {'error_status': None, 'metadata': {'version': '2.0'}, 'document': {
        'pages': [{'id': i} for i in range(3)],
        'elements': [{'id': i, 'content': 'Invented 甲 '+str(i), 'bbox': [box(i)]} for i in range(3)]}}
    raw = {'error_message': None, 'metadata': {'mode': 'precision', 'version': '2.1',
        'chunk_type': 'bbox', 'pages': [{'id': 0}, {'id': 2}],
        'citations': [{'id': 7, 'bbox': [box(0)]}, {'id': 2, 'bbox': [box(2)]}]},
        'response': {'items': [{'name': scalar('Café 甲', [7]), 'details': scalar('Example', [2]),
            'amount': scalar(0, [2]), 'tags': [], 'source_pages': [scalar(98, [7])]}],
            'policies': [{'text': scalar('Fictional policy', [2]), 'source_pages': []}],
            'dietary_allergen_legend': [{'meaning': scalar('Example marker', [7]), 'source_pages': []}]}}
    contract = {'bindings': bindings(raw, parsed, schema), 'source_sha256': 'a'*64,
                'physical_pages': 3, 'page_basis': 'full_original_pdf_zero_based'}
    return [raw, parsed, schema, contract]


class BboxPageProvenanceTests(unittest.TestCase):
    def setUp(self): self.args = fixture()
    def rebind(self): self.args[-1]['bindings'] = bindings(*self.args[:3])
    def run_case(self): return derive(*self.args)
    def item(self): return self.args[0]['response']['items'][0]
    def abstain(self):
        self.rebind(); result, audit = self.run_case()
        self.assertEqual(audit['records'][0]['status'], 'abstained')
        self.assertEqual(result['response']['items'], self.args[0]['response']['items'])
        self.assertEqual(restore(result, audit), self.args[0])
    def reject(self):
        with self.assertRaises(ValueError): self.run_case()

    def test_multifield_union_and_nonsequential_ids(self):
        result, audit = self.run_case()
        self.assertEqual(result['response']['items'][0]['source_pages'],
                         [{'value': 1, 'citation_ids': [7]}, {'value': 3, 'citation_ids': [2]}])
        self.assertEqual(len(audit['changes']), 3)
        self.assertEqual(audit['records'][0]['fields'][0]['physical_pages'], [1])

    def test_inverse_and_immutable_inputs(self):
        before = deepcopy(self.args); result, audit = self.run_case()
        self.assertEqual(self.args, before); self.assertEqual(restore(result, audit), before[0])
        self.assertEqual(result['metadata'], before[0]['metadata'])

    def test_no_semantic_acceptance(self):
        self.item()['details']['value'] = 'Deliberately false claim, still cited'
        self.rebind(); result, audit = self.run_case()
        self.assertEqual(audit['records'][0]['status'], 'derived_changed')
        self.assertFalse(audit['quality_accepted']); self.assertEqual(audit['new_ai_calls'], 0)
        self.assertFalse(result['derivation']['service_response'])
        self.assertEqual(result['derivation']['semantic_support'], 'not_proven')

    def test_already_consistent_is_unchanged(self):
        self.item()['source_pages'] = [{'value': 1, 'citation_ids': [7], 'confidence_score': .8},
                                       {'value': 3, 'citation_ids': [2]}]
        self.rebind(); result, audit = self.run_case()
        self.assertEqual(audit['records'][0]['status'], 'already_consistent')
        self.assertEqual(result['response']['items'], self.args[0]['response']['items'])

    def test_generated_page_cites_do_not_expand_union(self):
        box = self.args[1]['document']['elements'][1]['bbox'][0]
        self.args[0]['metadata']['citations'].append({'id': 88, 'bbox': [box]})
        self.args[0]['metadata']['pages'].append({'id': 1})
        self.item()['source_pages'] = [{'value': 2, 'citation_ids': [88]}]
        self.rebind(); result, _ = self.run_case()
        self.assertEqual([p['value'] for p in result['response']['items'][0]['source_pages']], [1, 3])

    def test_one_citation_spans_two_pages(self):
        self.args[0]['metadata']['citations'][0]['bbox'].append(
            deepcopy(self.args[1]['document']['elements'][2]['bbox'][0]))
        self.rebind(); result, _ = self.run_case()
        self.assertEqual(result['response']['items'][0]['source_pages'][1]['citation_ids'], [2, 7])

    def test_null_field_is_not_required(self):
        self.item()['amount'] = {'value': None, 'citation_ids': []}
        self.rebind(); _, audit = self.run_case()
        self.assertEqual(audit['records'][0]['status'], 'derived_changed')
    def test_empty_string_is_not_required(self):
        self.item()['details'] = {'value': '', 'citation_ids': []}
        self.rebind(); _, audit = self.run_case()
        self.assertEqual(audit['records'][0]['status'], 'derived_changed')
    def test_zero_is_populated(self): self.item()['amount']['citation_ids'] = []; self.abstain()
    def test_uncited_field(self): self.item()['details']['citation_ids'] = []; self.abstain()
    def test_unknown_citation(self): self.item()['details']['citation_ids'] = [55]; self.abstain()
    def test_missing_name(self): self.item()['name']['value'] = None; self.abstain()
    def test_missing_field(self): self.item().pop('details'); self.abstain()
    def test_extra_field(self): self.item()['extra'] = 'unexpected'; self.abstain()
    def test_wrong_scalar_type(self): self.item()['amount']['value'] = '2'; self.abstain()
    def test_bool_number(self): self.item()['amount']['value'] = True; self.abstain()
    def test_missing_wrapper(self): self.item()['name'] = 'Café 甲'; self.abstain()
    def test_nonarray(self): self.item()['tags'] = None; self.abstain()
    def test_duplicate_field_cite(self): self.item()['name']['citation_ids'] = [7, 7]; self.abstain()
    def test_bool_field_cite(self): self.item()['name']['citation_ids'] = [True]; self.abstain()
    def test_uncited_array_entry(self): self.item()['tags'] = [{'value': 'Tag', 'citation_ids': []}]; self.abstain()
    def test_malformed_source_pages(self): self.item()['source_pages'] = None; self.abstain()
    def test_unknown_parser_geometry(self):
        self.args[0]['metadata']['citations'][0]['bbox'][0]['coord'][2] = 11
        self.abstain()
    def test_null_array_response(self):
        self.args[0]['response']['items'] = None; self.rebind(); self.reject()
    def test_wrong_mode(self): self.args[0]['metadata']['mode'] = 'standard'; self.rebind(); self.reject()
    def test_wrong_version(self): self.args[0]['metadata']['version'] = '2.0'; self.rebind(); self.reject()
    def test_span_not_supported(self): self.args[0]['metadata']['chunk_type'] = 'span'; self.rebind(); self.reject()
    def test_service_error(self): self.args[0]['error_message'] = 'failed'; self.rebind(); self.reject()
    def test_duplicate_metadata_id(self):
        self.args[0]['metadata']['citations'][1]['id'] = 7; self.rebind(); self.reject()
    def test_negative_box(self):
        self.args[0]['metadata']['citations'][0]['bbox'][0]['coord'][0] = -1
        self.rebind(); self.reject()
    def test_inverted_box(self):
        self.args[0]['metadata']['citations'][0]['bbox'][0]['coord'][2] = 0
        self.rebind(); self.reject()
    def test_unknown_page(self):
        self.args[0]['metadata']['citations'][0]['bbox'][0]['page_id'] = 3
        self.rebind(); self.reject()
    def test_missing_metadata_page(self):
        self.args[0]['metadata']['pages'].pop(); self.rebind(); self.reject()
    def test_stale_raw(self): self.item()['name']['value'] = 'Changed'; self.reject()
    def test_stale_parser(self): self.args[1]['document']['elements'][0]['content'] = 'Changed'; self.reject()
    def test_stale_schema(self): self.args[2]['extra'] = {}; self.reject()
    def test_wrong_input_basis(self): self.args[-1]['page_basis'] = 'selected_pages'; self.reject()
    def test_incomplete_parser(self): self.args[1]['document']['pages'].pop(); self.rebind(); self.reject()
    def test_reordered_parser(self): self.args[1]['document']['pages'].reverse(); self.rebind(); self.reject()
    def test_invalid_source_hash(self): self.args[-1]['source_sha256'] = ''; self.reject()
    def test_bool_page_count(self): self.args[-1]['physical_pages'] = True; self.reject()
    def test_replay(self): self.args[0], _ = self.run_case(); self.rebind(); self.reject()
    def test_changed_shadow(self):
        result, audit = self.run_case(); result['response']['items'][0]['amount']['value'] = 1
        with self.assertRaises(ValueError): restore(result, audit)
    def test_changed_inverse(self):
        result, audit = self.run_case(); audit['changes'][0]['before'] = []
        with self.assertRaises(ValueError): restore(result, audit)


if __name__ == '__main__': unittest.main()
