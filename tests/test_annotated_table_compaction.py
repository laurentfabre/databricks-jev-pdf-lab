from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from annotated_table_compaction import ANNOTATION_MARKER, compact_annotated_input, render, sha


class AnnotatedCompactionTests(unittest.TestCase):
    def fixture(self):
        records = [
            {'id': 0, 'type': 'title', 'physical_page': 1, 'content': 'Synthetic Garden Menu'},
            {'id': 1, 'type': 'table', 'physical_page': 2,
             'content': '<table>'+('<tr><td>Soup 🌿</td><td>12.50</td></tr>'*20)+'</table>'},
            {'id': 2, 'type': 'text', 'physical_page': 3, 'content': 'Unknown is not allergen-free.'}]
        prefix, _ = render(records, [1, 2, 3])
        text = prefix+'\n\n'+ANNOTATION_MARKER+'\nProvisional labels only.\n{"scope":"preparation_row_only"}\n'
        return text, records, [1, 2, 3]

    def test_smaller_exact_original_and_annotations(self):
        text, records, pages = self.fixture()
        before = deepcopy(records)
        candidate, audit = compact_annotated_input(text, records, pages, sha(text))
        self.assertLess(len(candidate.encode()), len(text.encode()))
        self.assertEqual(records, before)
        self.assertTrue(audit['whole_input_round_trip_exact'])
        self.assertTrue(audit['annotation_unchanged'])
        self.assertEqual(candidate.split(ANNOTATION_MARKER)[1], text.split(ANNOTATION_MARKER)[1])

    def test_scopes_match_exact_contents(self):
        text, records, pages = self.fixture()
        candidate, audit = compact_annotated_input(text, records, pages, sha(text))
        for scope, record in zip(audit['original_scopes'], records):
            self.assertEqual(text[scope['start']:scope['stop']], record['content'])
        self.assertIn('table-rows-inner-html-v1', candidate)

    def test_wrong_hash_fails(self):
        text, records, pages = self.fixture()
        with self.assertRaises(ValueError): compact_annotated_input(text, records, pages, 'bad')

    def test_changed_source_fails(self):
        text, records, pages = self.fixture()
        records[0]['content'] = 'Changed'
        with self.assertRaises(ValueError): compact_annotated_input(text, records, pages, sha(text))

    def test_missing_page_fails(self):
        text, records, _ = self.fixture()
        with self.assertRaises(ValueError): compact_annotated_input(text, records, [1, 3], sha(text))

    def test_duplicate_id_fails(self):
        text, records, pages = self.fixture()
        records[1]['id'] = 0
        with self.assertRaises(ValueError): compact_annotated_input(text, records, pages, sha(text))

    def test_extra_source_field_fails(self):
        text, records, pages = self.fixture()
        records[0]['description'] = 'Do not silently drop this.'
        with self.assertRaises(ValueError): compact_annotated_input(text, records, pages, sha(text))

    def test_annotation_boundary_required(self):
        text, records, pages = self.fixture()
        text = text.replace(ANNOTATION_MARKER, '[NOT THE ORIGINAL MARKER]')
        with self.assertRaises(ValueError): compact_annotated_input(text, records, pages, sha(text))

    def test_unmodified_non_table(self):
        text, records, pages = self.fixture()
        candidate, audit = compact_annotated_input(text, records, pages, sha(text))
        scope = audit['candidate_scopes'][-1]
        self.assertEqual(candidate[scope['start']:scope['stop']], records[-1]['content'])

    def test_unsupported_table_kept(self):
        text, records, pages = self.fixture()
        records[1]['content'] = '<table>\n<tr><td>Soup</td></tr></table>'
        prefix, _ = render(records, pages)
        text = prefix+'\n\n'+ANNOTATION_MARKER+'\nKeep all observations.'
        candidate, audit = compact_annotated_input(text, records, pages, sha(text))
        self.assertEqual(candidate, text)
        self.assertEqual(audit['table_audit'][0]['status'], 'original_unsupported')

    def test_empty_physical_page_retained(self):
        text, records, pages = self.fixture()
        records = records[:2]
        prefix, _ = render(records, pages)
        text = prefix+'\n\n'+ANNOTATION_MARKER+'\nKnown unlabelled regions stay unknown.'
        candidate, audit = compact_annotated_input(text, records, pages, sha(text))
        self.assertIn('[SOURCE PAGE 3]', candidate)
        self.assertEqual(audit['physical_pages'], [1, 2, 3])

    def test_reordered_source_does_not_reconstruct(self):
        text, records, pages = self.fixture()
        records[1]['physical_page'] = 1
        with self.assertRaises(ValueError): compact_annotated_input(text, records, pages, sha(text))


if __name__ == '__main__': unittest.main()
