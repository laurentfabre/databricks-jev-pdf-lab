from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from reviewed_field_projection import at, digest, project, restore, source_recipe, text_hash


def fixture():
    text = 'Garden soup gluten-free. Per bowl. Made here.'
    boundary = text.index('Made here.')
    scopes = [{'element_id': 1, 'page': 1, 'start': 0, 'stop': boundary},
              {'element_id': 2, 'page': 2, 'start': boundary, 'stop': len(text)}]
    string = {'type': 'string'}
    pages = {'type': 'array', 'items': {'type': 'integer'}}
    schema = {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'name': string, 'details': string, 'dietary_markers': {'type': 'array', 'items': string},
        'prices': {'type': 'array', 'items': {'type': 'object', 'properties': {'basis': string}}},
        'source_pages': pages}}},
        'policies': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'topic': string, 'text': string, 'source_pages': pages}}}}
    box = lambda value: {'value': value, 'citation_ids': [0]}
    raw = {'error_message': None, 'metadata': {'version': '2.1', 'mode': 'precision',
        'chunk_type': 'span', 'citations': [{'id': 0, 'start': 0, 'stop': boundary},
            {'id': 1, 'start': boundary, 'stop': len(text)}]},
        'response': {'items': [{'name': box('Garden soup'), 'details': box('Garden soup'),
            'dietary_markers': [], 'prices': [{'basis': box('portion')}],
            'source_pages': [box(1)]}], 'policies': []}}
    plan = {'bindings': {'raw_sha256': digest(raw), 'text_sha256': text_hash(text),
        'scopes_sha256': digest(scopes), 'schema_sha256': digest(schema)},
        'review': {'kind': 'assistant_posthoc_source_review', 'independent': False,
                   'evidence_sha256': '0' * 64}, 'operations': []}
    return [raw, text, scopes, schema, plan]


def add(args, path, recipe, op='replace', page=1):
    args[-1]['operations'].append({'path': deepcopy(path), 'op': op, 'physical_page': page,
        'before_sha256': digest(at(args[0], path)), 'recipe': recipe,
        'reason': 'Fabricated fixture selection, not a real source judgment'})


MARKERS = ['response', 'items', 0, 'dietary_markers']
DETAILS = ['response', 'items', 0, 'details']
BASIS = ['response', 'items', 0, 'prices', 0, 'basis']


def marker_case():
    args = fixture()
    add(args, MARKERS, source_recipe(args[1], args[2], 1, 'gluten-free'), 'append')
    return args


class ReviewedFieldProjectionTests(unittest.TestCase):
    def run_case(self, args):
        original = deepcopy(args)
        shadow, audit = project(*args)
        self.assertEqual(args, original)
        self.assertEqual(restore(shadow, audit), args[0])
        self.assertEqual(shadow['metadata'], args[0]['metadata'])
        self.assertFalse(audit['quality_accepted'])
        self.assertEqual(audit['new_ai_calls'], 0)
        for change in audit['changes']:
            self.assertTrue(change['semantic_review_required'])
            self.assertFalse(change['quality_accepted'])
        return shadow, audit

    def test_copied_marker_and_inverse(self):
        shadow, audit = self.run_case(marker_case())
        self.assertEqual(at(shadow, MARKERS), [{'value': 'gluten-free', 'citation_ids': [0]}])
        self.assertNotIn('confidence_score', at(shadow, MARKERS)[0])
        self.assertEqual(len(audit['changes']), 1)

    def test_empty_plan_changes_nothing(self):
        args = fixture()
        shadow, audit = self.run_case(args)
        self.assertEqual(shadow, args[0])
        self.assertEqual(audit['changes'], [])

    def test_join_preserves_prose(self):
        args = fixture()
        add(args, DETAILS, {'kind': 'join', 'separator': '; ', 'parts': [
            {'kind': 'retain'}, source_recipe(args[1], args[2], 1, 'Per bowl.')]})
        shadow, audit = self.run_case(args)
        self.assertEqual(at(shadow, DETAILS)['value'], 'Garden soup; Per bowl.')
        self.assertEqual(audit['changes'][0]['proofs'][0]['kind'], 'retained_prose_not_revalidated')

    def test_policy_object_and_source_page(self):
        args = fixture()
        source = source_recipe(args[1], args[2], 2, 'Made here.')
        add(args, ['response', 'policies'], {'kind': 'object', 'fields': {
            'topic': source, 'text': source, 'source_pages': {'kind': 'array', 'items': [
                {'kind': 'page', 'source': source}]}}}, 'append', 2)
        shadow, _ = self.run_case(args)
        policy = shadow['response']['policies'][0]
        self.assertEqual(policy['source_pages'], [{'value': 2, 'citation_ids': [1]}])

    def test_null_requires_explicit_review(self):
        args = fixture()
        add(args, BASIS, {'kind': 'reviewed_unstated', 'review_finding': 'basis_default'})
        shadow, audit = self.run_case(args)
        self.assertEqual(at(shadow, BASIS), {'value': None, 'citation_ids': []})
        self.assertIn('not_code_proof', audit['changes'][0]['proofs'][0]['kind'])

    def test_absence_does_not_automatically_null(self):
        shadow, _ = self.run_case(fixture())
        self.assertEqual(at(shadow, BASIS)['value'], 'portion')

    def test_present_literal_cannot_be_nulled(self):
        args = fixture(); at(args[0], BASIS)['value'] = 'Per bowl'
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        add(args, BASIS, {'kind': 'reviewed_unstated', 'review_finding': 'basis_default'})
        with self.assertRaises(ValueError): project(*args)

    def test_null_cannot_clear_name(self):
        args = fixture()
        add(args, ['response', 'items', 0, 'name'],
            {'kind': 'reviewed_unstated', 'review_finding': 'basis_default'})
        with self.assertRaises(ValueError): project(*args)

    def test_missing_review_rejected(self):
        args = marker_case(); args[-1]['review'] = {}
        with self.assertRaises(ValueError): project(*args)

    def test_independent_label_claim_rejected(self):
        args = marker_case(); args[-1]['review']['independent'] = True
        with self.assertRaises(ValueError): project(*args)

    def test_review_digest_must_be_hex(self):
        args = marker_case(); args[-1]['review']['evidence_sha256'] = 'z' * 64
        with self.assertRaises(ValueError): project(*args)

    def test_stale_bindings(self):
        for key in fixture()[-1]['bindings']:
            args = marker_case(); args[-1]['bindings'][key] = 'f' * 64
            with self.subTest(key=key), self.assertRaises(ValueError): project(*args)

    def test_precondition_guard(self):
        args = marker_case(); args[-1]['operations'][0]['before_sha256'] = 'f' * 64
        with self.assertRaises(ValueError): project(*args)

    def test_review_reason_required(self):
        args = marker_case(); args[-1]['operations'][0]['reason'] = ''
        with self.assertRaises(ValueError): project(*args)

    def test_scope_cannot_be_annotation(self):
        args = marker_case(); args[-1]['operations'][0]['recipe']['element_id'] = 99
        with self.assertRaises(ValueError): project(*args)

    def test_wrong_target_page(self):
        args = marker_case(); args[-1]['operations'][0]['physical_page'] = 2
        with self.assertRaises(ValueError): project(*args)

    def test_wrong_source_page(self):
        args = marker_case()
        args[-1]['operations'][0]['recipe'] = source_recipe(args[1], args[2], 2, 'Made here.')
        with self.assertRaises(ValueError): project(*args)

    def test_literal_hash(self):
        args = marker_case(); args[-1]['operations'][0]['recipe']['literal_sha256'] = 'f' * 64
        with self.assertRaises(ValueError): project(*args)

    def test_source_selection_type_guards(self):
        for key in ('element_id', 'start', 'stop'):
            args = marker_case(); args[-1]['operations'][0]['recipe'][key] = True
            with self.subTest(key=key), self.assertRaises(ValueError): project(*args)

    def test_source_selection_crosses_element(self):
        args = marker_case(); args[-1]['operations'][0]['recipe']['stop'] = len(args[1])
        with self.assertRaises(ValueError): project(*args)

    def test_citation_gap_abstains(self):
        args = marker_case(); args[0]['metadata']['citations'][0]['stop'] = 12
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        with self.assertRaises(ValueError): project(*args)

    def test_adjacent_citations_cover(self):
        args = marker_case()
        args[0]['metadata']['citations'][0]['stop'] = 16
        args[0]['metadata']['citations'].append({'id': 2, 'start': 16, 'stop': args[2][0]['stop']})
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        shadow, _ = self.run_case(args)
        self.assertEqual(at(shadow, MARKERS)[0]['citation_ids'], [0, 2])

    def test_duplicate_citation_id_rejected(self):
        args = marker_case(); args[0]['metadata']['citations'][1]['id'] = 0
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        with self.assertRaises(ValueError): project(*args)

    def test_duplicate_scope_rejected(self):
        args = marker_case(); args[2].append(args[2][0])
        args[-1]['bindings']['scopes_sha256'] = digest(args[2])
        with self.assertRaises(ValueError): project(*args)

    def test_conflicting_operations_rejected(self):
        args = marker_case(); args[-1]['operations'].append(deepcopy(args[-1]['operations'][0]))
        with self.assertRaises(ValueError): project(*args)

    def test_parent_child_operations_rejected(self):
        args = marker_case()
        add(args, ['response', 'items', 0], {'kind': 'object', 'fields': {}})
        with self.assertRaises(ValueError): project(*args)

    def test_metadata_path_rejected(self):
        args = marker_case(); args[-1]['operations'][0]['path'] = ['metadata', 'mode']
        with self.assertRaises(ValueError): project(*args)

    def test_negative_index_rejected(self):
        args = marker_case(); args[-1]['operations'][0]['path'][2] = -1
        with self.assertRaises(ValueError): project(*args)

    def test_unknown_schema_field_rejected(self):
        args = marker_case(); args[-1]['operations'][0]['path'][-1] = 'invented'
        with self.assertRaises(ValueError): project(*args)

    def test_duplicate_append_rejected(self):
        args = marker_case()
        at(args[0], MARKERS).append({'value': 'gluten-free', 'citation_ids': [0]})
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        args[-1]['operations'][0]['before_sha256'] = digest(at(args[0], MARKERS))
        with self.assertRaises(ValueError): project(*args)

    def test_schema_type_rejects_page_as_marker(self):
        args = marker_case(); source = args[-1]['operations'][0]['recipe']
        args[-1]['operations'][0]['recipe'] = {'kind': 'page', 'source': source}
        with self.assertRaises(ValueError): project(*args)

    def test_precision_guard(self):
        args = marker_case(); args[0]['metadata']['mode'] = 'fast'
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        with self.assertRaises(ValueError): project(*args)

    def test_failed_response_guard(self):
        args = marker_case(); args[0]['error_message'] = 'failure'
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        with self.assertRaises(ValueError): project(*args)

    def test_replay_on_shadow_rejected(self):
        args = marker_case(); shadow, _ = self.run_case(args); args[0] = shadow
        with self.assertRaises(ValueError): project(*args)

    def test_inverse_tamper_rejected(self):
        shadow, audit = self.run_case(marker_case()); at(shadow, MARKERS).clear()
        with self.assertRaises(ValueError): restore(shadow, audit)

    def test_missing_literal_rejected(self):
        args = fixture()
        with self.assertRaises(ValueError): source_recipe(args[1], args[2], 1, 'invented')

    def test_ambiguous_literal_rejected(self):
        with self.assertRaises(ValueError):
            source_recipe('soup soup', [{'element_id': 1, 'start': 0, 'stop': 9}], 1, 'soup')

    def test_unicode_offsets_are_characters(self):
        recipe = source_recipe('🍲 soupe sans gluten', [{'element_id': 1, 'start': 0, 'stop': 19}],
                               1, 'sans gluten')
        self.assertEqual(recipe['start'], 8)


if __name__ == '__main__':
    unittest.main()
