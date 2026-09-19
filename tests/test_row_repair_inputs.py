"""Synthetic-only exact row excerpt, scope labelling and origin tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from row_repair_inputs import build_cases, digest, row_spans, sha


def fixture():
    table = ('<table><tr><td>Alpha</td><td>12 €</td><td>Beta</td><td>24 €</td></tr>'
             '<tr><td>Alphé<br>甲</td><td></td><td>Bêta<br>乙</td><td></td></tr>'
             '<tr><td colspan="4">Choose a style</td></tr>'
             '<tr><td>Maple style</td><td></td><td>P</td><td></td></tr>'
             '<tr><td>Citrus style</td><td></td><td></td><td></td></tr>'
             '<tr><td>Gamma</td><td>36 €</td><td>Delta</td><td>48 €</td></tr></table>')
    fragments, segments = [], []
    offset = 0

    def add(fragment, origin, **attrs):
        nonlocal offset
        segments.append({'start': offset, 'stop': offset + len(fragment), 'origin': origin, **attrs})
        fragments.append(fragment); offset += len(fragment) + 1

    add('[SOURCE PAGE 3]', 'physical_page_label', physical_page=3)
    add('Main dishes', 'original_parser_text', physical_page=3, element_id=1)
    add(table, 'original_parser_text', physical_page=3, element_id=2)
    add('[SOURCE PAGE 7]', 'physical_page_label', physical_page=7)
    add('P: marker meaning. Icon: special.', 'original_parser_text', physical_page=7, element_id=3)
    add('[IMAGE OBSERVATIONS]', 'annotation_label')
    add('Provisional supplied observations; no safety inference.', 'retained_annotation_caveats')
    for row in (3, 4):
        add(json.dumps({'group': f'group{row}', 'symbols': {'special': 1}}),
            'provisional_image_observation', physical_page=3, source_group=f'group{row}')
    add('[ASSISTANT REVIEW; NOT PARSER TEXT]', 'review_label')
    add('Post-hoc non-independent review, not service confidence.', 'review_caveats')
    add(json.dumps({'reviewed_legend_observation': {'source_element_id': 3,
        'physical_page': 7, 'marker_description': 'icon', 'meanings': ['special']}}),
        'assistant_image_review', physical_page=7)
    for row, name in ((3, 'Maple style'), (4, 'Citrus style')):
        add(json.dumps({'reviewed_preparation_observation': {'physical_page': 3,
            'preparation_fragments': [name], 'parent_offering_fragments': [['Alpha','Alphé','甲'],['Beta','Bêta','乙']],
            'scope': 'only_when_this_preparation_is_selected_not_unconditional_parent_property',
            'symbols': {'special': 1}}}, ensure_ascii=False),
            'assistant_image_review', physical_page=3, source_group=f'group{row}')
    text = '\n'.join(fragments)
    provenance = {'input_sha256': {'review_enriched': sha(text)},
                  'segments': {'review_enriched': segments}}
    plan = {'bindings': {'text_sha256': sha(text), 'provenance_sha256': digest(provenance)},
        'review': {'kind': 'assistant_posthoc_selection', 'independent': False},
        'table_element_id': 2, 'parent_rows': [0,1], 'heading_row': 2,
        'context_element_ids': [1], 'legend_element_ids': [3],
        'cases': [{'case_id': 'row3', 'row': 3, 'source_group': 'group3'},
                  {'case_id': 'row4', 'row': 4, 'source_group': 'group4'}]}
    return [text, provenance, plan]


def rebind(args):
    args[1]['input_sha256']['review_enriched'] = sha(args[0])
    args[2]['bindings'] = {'text_sha256': sha(args[0]), 'provenance_sha256': digest(args[1])}


class RowRepairInputTests(unittest.TestCase):
    def run_case(self, args=None):
        args = fixture() if args is None else args
        snapshot = deepcopy(args)
        texts, audit = build_cases(*args)
        self.assertEqual(args, snapshot)
        return args, texts, audit

    def test_exact_source_spans_and_complete_output_accounting(self):
        args, texts, audit = self.run_case()
        for key, value in texts.items():
            cursor = 0
            for s in audit['cases'][key]['segments']:
                self.assertEqual(s['start'], cursor); cursor = s['stop']
                if 'source_start' in s:
                    self.assertEqual(value[s['start']:s['stop']], args[0][s['source_start']:s['source_stop']])
                    origin = args[1]['segments']['review_enriched'][s['source_segment_index']]['origin']
                    self.assertEqual(s['origin'], origin)
                else:
                    self.assertIn(s['origin'], ('assembly_label', 'assembly_separator'))
            self.assertEqual(cursor, len(value))

    def test_each_input_has_only_selected_preparation(self):
        _, texts, _ = self.run_case()
        self.assertIn('Maple style', texts['row3']); self.assertNotIn('Citrus style', texts['row3'])
        self.assertIn('Citrus style', texts['row4']); self.assertNotIn('Maple style', texts['row4'])
        for value in texts.values(): self.assertNotIn('Gamma', value)

    def test_both_parent_names_translations_and_prices_retained(self):
        _, texts, _ = self.run_case()
        for value in texts.values():
            for literal in ('Alpha', 'Alphé', '甲', 'Beta', 'Bêta', '乙', '12 €', '24 €', 'Choose a style'):
                self.assertIn(literal, value)

    def test_partial_and_conditional_caveats(self):
        _, texts, audit = self.run_case()
        for key, value in texts.items():
            self.assertIn('omitted here, not absent', value)
            self.assertIn('only_when_this_preparation_is_selected_not_unconditional_parent_property', value)
            self.assertFalse(audit['cases'][key]['full_document'])
            self.assertFalse(audit['cases'][key]['quality_accepted'])
        self.assertTrue(audit['unselected_material_still_required'])
        self.assertFalse(audit['semantic_selection_automated'])
        self.assertEqual(audit['new_ai_calls'], 0)

    def test_origin_labels_and_physical_pages(self):
        _, texts, audit = self.run_case()
        for key, value in texts.items():
            self.assertIn('[SOURCE PAGE 3]', value); self.assertIn('[SOURCE PAGE 7]', value)
            self.assertIn('[ASSISTANT REVIEW; NOT PARSER TEXT]', value)
            self.assertIn('not service confidence', value)
            reviews = [s for s in audit['cases'][key]['segments'] if s['origin'] == 'assistant_image_review']
            self.assertEqual(len(reviews), 2)

    def test_unicode_lengths_and_hashes(self):
        _, texts, audit = self.run_case()
        for key, value in texts.items():
            self.assertEqual(audit['cases'][key]['input_bytes'], len(value.encode()))
            self.assertGreater(len(value.encode()), len(value))
            self.assertEqual(audit['cases'][key]['input_sha256'], sha(value))

    def test_selected_and_omitted_row_inventory(self):
        _, _, audit = self.run_case()
        self.assertEqual(audit['cases']['row3']['selected_table_rows'], [0,1,2,3])
        self.assertEqual(audit['cases']['row3']['omitted_table_rows'], [4,5])

    def test_stale_text_rejected(self):
        args = fixture(); args[0] += ' '
        with self.assertRaisesRegex(ValueError, 'Stale'): build_cases(*args)

    def test_stale_provenance_rejected(self):
        args = fixture(); args[1]['extra'] = True
        with self.assertRaisesRegex(ValueError, 'Stale'): build_cases(*args)

    def test_changed_parent_hash_rejected(self):
        args = fixture(); args[1]['input_sha256']['review_enriched'] = '0'*64
        args[2]['bindings']['provenance_sha256'] = digest(args[1])
        with self.assertRaisesRegex(ValueError, 'enriched'): build_cases(*args)

    def test_overlap_rejected(self):
        args = fixture(); args[1]['segments']['review_enriched'][1]['start'] -= 1; rebind(args)
        with self.assertRaisesRegex(ValueError, 'accounting'): build_cases(*args)

    def test_gap_rejected(self):
        args = fixture(); args[1]['segments']['review_enriched'][1]['start'] += 1; rebind(args)
        with self.assertRaisesRegex(ValueError, 'accounting'): build_cases(*args)

    def test_unaccounted_suffix_rejected(self):
        args = fixture(); args[0] += 'suffix'; rebind(args)
        with self.assertRaisesRegex(ValueError, 'suffix'): build_cases(*args)

    def test_review_must_be_non_independent(self):
        args = fixture(); args[2]['review']['independent'] = True
        with self.assertRaisesRegex(ValueError, 'non-independent'): build_cases(*args)

    def test_duplicate_parent_rows_rejected(self):
        args = fixture(); args[2]['parent_rows'] = [0,0]
        with self.assertRaisesRegex(ValueError, 'Ordered'): build_cases(*args)

    def test_heading_cannot_be_target(self):
        args = fixture(); args[2]['cases'][0]['row'] = 2
        with self.assertRaisesRegex(ValueError, 'preparation row'): build_cases(*args)

    def test_out_of_range_row_rejected(self):
        args = fixture(); args[2]['cases'][0]['row'] = 8
        with self.assertRaisesRegex(ValueError, 'preparation row'): build_cases(*args)

    def test_duplicate_case_rejected(self):
        args = fixture(); args[2]['cases'][1]['case_id'] = 'row3'
        with self.assertRaisesRegex(ValueError, 'Distinct'): build_cases(*args)

    def test_wrong_preparation_binding_rejected(self):
        args = fixture(); args[2]['cases'][0]['source_group'], args[2]['cases'][1]['source_group'] = 'group4','group3'
        with self.assertRaisesRegex(ValueError, 'bind selected'): build_cases(*args)

    def test_missing_parent_fragment_rejected(self):
        args = fixture(); args[2]['parent_rows'] = [0]
        with self.assertRaisesRegex(ValueError, 'bind selected'): build_cases(*args)

    def test_wrong_context_page_rejected(self):
        args = fixture(); args[1]['segments']['review_enriched'][1]['physical_page'] = 2; rebind(args)
        with self.assertRaisesRegex(ValueError, 'context or legend page'): build_cases(*args)

    def test_duplicate_element_selection_rejected(self):
        args = fixture(); args[2]['legend_element_ids'] = [3,3]
        with self.assertRaisesRegex(ValueError, 'Distinct'): build_cases(*args)

    def test_unsupported_markup_rejected(self):
        for table in ('<table><tr><td rowspan="2">A</td><td>B</td></tr></table>',
                      '<table><tr><td>A</td></tr></table> trailing',
                      '<table><tr><td>A</td><td>B</td></tr><tr><td>C</td></tr></table>'):
            with self.assertRaises(ValueError): row_spans(table)

    def test_two_tables_rejected(self):
        table = '<table><tr><td>A</td><td>B</td></tr></table>'
        with self.assertRaises(ValueError): row_spans(table+table)


if __name__ == '__main__': unittest.main()
