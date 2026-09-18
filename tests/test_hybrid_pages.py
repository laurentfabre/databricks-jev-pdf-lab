import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from hybrid_pages import assemble, native_regions


def word(text, x=5, y=5, block=0, line=0, index=0):
    return [x, y, x + 10, y + 10, text, block, line, index]


class HybridTests(unittest.TestCase):
    def test_regions_do_not_interleave(self):
        words = [word('left', 5, 5), word('right', 70, 5, 1), word('second', 5, 20, 0, 1)]
        before = copy.deepcopy(words)
        text, audit = native_regions(words, 100, True)
        self.assertLess(text.index('second'), text.index('right'))
        self.assertEqual(audit['word_order'], [0, 2, 1])
        self.assertEqual(words, before)

    def test_same_line_word_order(self):
        text, audit = native_regions([word('B', 20), word('A', 5)], 100, False)
        self.assertTrue(text.endswith('A B'))
        self.assertEqual(audit['word_count'], 2)

    def test_crossing_boundary_rejected(self):
        with self.assertRaises(ValueError):
            native_regions([word('crossing', 45)], 100, True)

    def test_bad_geometry(self):
        for width in [0, float('nan')]:
            with self.assertRaises(ValueError): native_regions([], width, False)
        with self.assertRaises(ValueError): native_regions([word('offpage', 95)], 100, False)

    def test_all_pages_required(self):
        for pages in [[], [{'page': 2}], [{'page': 1}, {'page': 1}]]:
            with self.assertRaises(ValueError): assemble(pages, 2)

    def test_empty_native_rejected(self):
        with self.assertRaises(ValueError):
            assemble([{'page': 1, 'method': 'native_layout', 'words': [], 'width': 100, 'split': False}], 1)

    def test_unreviewed_fallback_rejected(self):
        with self.assertRaises(ValueError):
            assemble([{'page': 1, 'method': 'retained_managed', 'elements': []}], 1)

    def test_cross_page_element_rejected(self):
        p = {'page': 1, 'method': 'retained_managed', 'reviewed_image_sha256': 'test',
             'elements': [{'id': 1, 'type': 'text', 'bbox': [{'page_id': 1}], 'content': 'wrong page'}]}
        with self.assertRaises(ValueError): assemble([p], 1)

    def test_blank_element_needs_empty_page_review(self):
        p = {'page': 1, 'method': 'retained_managed', 'reviewed_image_sha256': 'test',
             'elements': [{'id': 1, 'type': 'figure', 'bbox': [{'page_id': 0}], 'content': ''}]}
        with self.assertRaises(ValueError): assemble([p], 1)

    def test_empty_reviewed_page_not_dropped(self):
        p = {'page': 1, 'method': 'retained_managed', 'reviewed_image_sha256': 'test',
             'reviewed_no_required_text': True, 'elements': []}
        text, audit = assemble([p], 1)
        self.assertEqual(text, '[SOURCE PAGE 1]\n')
        self.assertEqual(audit[0]['physical_page'], 1)

    def test_offsets_and_source_literals(self):
        pages = [{'page': n, 'method': 'native_layout', 'words': [word('60-minute')],
                  'width': 100, 'split': False} for n in (1, 2)]
        text, audit = assemble(pages, 2)
        for record in audit:
            self.assertTrue(text[record['start']:record['end']].startswith(f"[SOURCE PAGE {record['physical_page']}]"))
        self.assertEqual(text.count('60-minute'), 2)

    def test_reserved_page_label_rejected(self):
        p = {'page': 1, 'method': 'native_layout', 'words': [word('[SOURCE PAGE 6]')],
             'width': 100, 'split': False}
        with self.assertRaises(ValueError): assemble([p], 1)

    def test_unknown_route_rejected(self):
        with self.assertRaises(ValueError): assemble([{'page': 1, 'method': 'skip'}], 1)


if __name__ == '__main__': unittest.main()
