"""Synthetic-only conditional copying and chained derivation regression tests."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from projection_lineage import project_with_lineage, restore
from reviewed_field_projection import digest, source_recipe, text_hash


def fixture():
    text = 'Alpha / Beta. Choose a style. Maple style P. Citrus style P.'
    scope = [{'element_id': 9, 'page': 1, 'start': 0, 'stop': len(text)}]
    string = {'type': 'string'}
    schema = {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'name': string, 'details': string, 'dietary_markers': {'type': 'array', 'items': string},
        'allergens': {'type': 'array', 'items': string},
        'source_pages': {'type': 'array', 'items': {'type': 'integer'}}}}}}
    box = lambda value: {'value': value, 'citation_ids': [0]}
    raw = {'metadata': {'version': '2.1', 'mode': 'precision', 'chunk_type': 'span',
        'citations': [{'id': 0, 'start': 0, 'stop': len(text)}]},
        'response': {'items': [{'name': box(name), 'details': box('Retained details'),
            'dietary_markers': [], 'allergens': [], 'source_pages': [box(1)]}
            for name in ('Alpha', 'Beta')]},
        'derivation': {'kind': 'prior_composition', 'service_response': False,
            'quality_accepted': False, 'plan_sha256': 'a' * 64}}
    heading = source_recipe(text, scope, 9, 'Choose a style')
    entries = []
    for label in ('Maple style', 'Citrus style'):
        preparation = source_recipe(text, scope, 9, label)
        start = preparation['stop'] + 1
        mark = {'kind': 'source', 'element_id': 9, 'start': start, 'stop': start + 1,
                'literal_sha256': text_hash('P')}
        entries.append({'kind': 'join', 'separator': ' / ', 'parts': [heading, preparation, mark]})
    plan = {'bindings': {'raw_sha256': digest(raw), 'text_sha256': text_hash(text),
        'scopes_sha256': digest(scope), 'schema_sha256': digest(schema)},
        'review': {'kind': 'assistant_posthoc_source_review', 'independent': False,
                   'evidence_sha256': '0' * 64},
        'operations': [{'path': ['response', 'items', i, 'dietary_markers'],
            'op': 'replace', 'before_sha256': digest([]), 'physical_page': 1,
            'reason': 'Synthetic supplied conditional selection, not automatic semantics',
            'recipe': {'kind': 'array', 'items': deepcopy(entries)}} for i in (0, 1)]}
    return [raw, text, scope, schema, plan]


class ProjectionLineageTests(unittest.TestCase):
    def run_case(self, args=None):
        args = fixture() if args is None else args
        before = deepcopy(args)
        derived, audit = project_with_lineage(*args)
        self.assertEqual(args, before)
        self.assertEqual(restore(derived, audit), args[0])
        return args, derived, audit

    def test_condition_preserved_for_each_parent(self):
        _, derived, _ = self.run_case()
        for item in derived['response']['items']:
            self.assertEqual([x['value'] for x in item['dietary_markers']],
                ['Choose a style / Maple style / P', 'Choose a style / Citrus style / P'])

    def test_no_unconditional_marker(self):
        _, derived, _ = self.run_case()
        for item in derived['response']['items']:
            self.assertNotIn('P', [x['value'] for x in item['dietary_markers']])
            self.assertEqual(item['allergens'], [])

    def test_other_fields_exact(self):
        args, derived, _ = self.run_case()
        for old, new in zip(args[0]['response']['items'], derived['response']['items']):
            self.assertEqual({k:v for k,v in old.items() if k != 'dietary_markers'},
                             {k:v for k,v in new.items() if k != 'dietary_markers'})

    def test_metadata_and_citations_exact(self):
        args, derived, _ = self.run_case()
        self.assertEqual(derived['metadata'], args[0]['metadata'])
        for item in derived['response']['items']:
            for mark in item['dietary_markers']:
                self.assertEqual(mark['citation_ids'], [0])
                self.assertNotIn('confidence_score', mark)

    def test_parent_lineage_exact(self):
        args, derived, _ = self.run_case()
        self.assertEqual(derived['derivation']['parent_derivation'], args[0]['derivation'])
        self.assertEqual(derived['derivation']['parent_response_sha256'], digest(args[0]))

    def test_current_plan_not_old_plan(self):
        args, derived, audit = self.run_case()
        self.assertEqual(derived['derivation']['plan_sha256'], digest(args[-1]))
        self.assertNotEqual(derived['derivation']['plan_sha256'], args[0]['derivation']['plan_sha256'])
        self.assertNotEqual(audit['derived_sha256'], audit['projection']['shadow_sha256'])

    def test_no_acceptance_or_service_response(self):
        _, derived, audit = self.run_case()
        self.assertFalse(derived['derivation']['service_response'])
        self.assertFalse(derived['derivation']['quality_accepted'])
        self.assertFalse(audit['quality_accepted'])
        self.assertEqual(audit['new_ai_calls'], 0)
        self.assertTrue(audit['semantic_review_required'])

    def test_absent_parent_metadata_restores_absence(self):
        args = fixture(); del args[0]['derivation']
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        _, derived, audit = self.run_case(args)
        self.assertNotIn('derivation', restore(derived, audit))

    def test_null_parent_metadata_restores_null(self):
        args = fixture(); args[0]['derivation'] = None
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        _, derived, audit = self.run_case(args)
        self.assertIn('derivation', restore(derived, audit))
        self.assertIsNone(restore(derived, audit)['derivation'])

    def test_stale_parent_rejected(self):
        args = fixture(); args[0]['derivation']['plan_sha256'] = 'b' * 64
        with self.assertRaises(ValueError): project_with_lineage(*args)

    def test_changed_text_rejected(self):
        args = fixture(); args[1] += ' More.'
        with self.assertRaises(ValueError): project_with_lineage(*args)

    def test_citation_gap_rejected(self):
        args = fixture(); args[0]['metadata']['citations'][0]['stop'] = 20
        args[-1]['bindings']['raw_sha256'] = digest(args[0])
        with self.assertRaises(ValueError): project_with_lineage(*args)

    def test_wrong_page_rejected(self):
        args = fixture(); args[-1]['operations'][0]['physical_page'] = 2
        with self.assertRaises(ValueError): project_with_lineage(*args)

    def test_wrong_marker_span_rejected(self):
        args = fixture(); args[-1]['operations'][0]['recipe']['items'][0]['parts'][2]['start'] += 1
        with self.assertRaises(ValueError): project_with_lineage(*args)

    def test_unreviewed_rejected(self):
        args = fixture(); del args[-1]['review']
        with self.assertRaises(ValueError): project_with_lineage(*args)

    def test_empty_operations_rejected(self):
        args = fixture(); args[-1]['operations'] = []
        with self.assertRaises(ValueError): project_with_lineage(*args)

    def test_duplicate_target_rejected(self):
        args = fixture(); args[-1]['operations'].append(deepcopy(args[-1]['operations'][0]))
        with self.assertRaises(ValueError): project_with_lineage(*args)

    def test_derived_mutation_blocks_inverse(self):
        _, derived, audit = self.run_case(); derived['derivation']['quality_accepted'] = True
        with self.assertRaises(ValueError): restore(derived, audit)

    def test_prior_lineage_mutation_blocks_inverse(self):
        _, derived, audit = self.run_case(); audit['prior_derivation']['kind'] = 'tampered'
        with self.assertRaises(ValueError): restore(derived, audit)

    def test_plan_mismatch_blocks_inverse(self):
        _, derived, audit = self.run_case(); audit['projection']['plan_sha256'] = 'c' * 64
        with self.assertRaises(ValueError): restore(derived, audit)

    def test_replay_rejected(self):
        args, derived, _ = self.run_case(); args[0] = derived
        with self.assertRaises(ValueError): project_with_lineage(*args)


if __name__ == '__main__': unittest.main()
