import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from table_compaction import compact_document, pack_tables, restore_tables, serialized


class TableCompactionTests(unittest.TestCase):
    def round_trip(self, raw):
        packet = pack_tables(raw)
        self.assertEqual(restore_tables(json.loads(serialized(packet))), raw)
        return packet

    def test_plain_values(self):
        self.round_trip('<table><tr><td>001.20 €</td><td>75cl</td></tr></table>')

    def test_headers_and_empty_cells(self):
        p = self.round_trip('<table><tr><th>Name</th><td></td></tr></table>')
        self.assertEqual(p['tables'], [[[{'th': 'Name'}, '']]])

    def test_adjacent_tables_separate(self):
        p = self.round_trip('<table><tr><td>A</td></tr></table><table><tr><td>B</td></tr></table>')
        self.assertEqual(len(p['tables']), 2)

    def test_spans_attributes_preserved(self):
        self.round_trip('<table><tr><th colspan="2">Amount</th></tr><tr><td rowspan="2" data-x="a>b">10</td></tr></table>')

    def test_mark_icons_and_entity_spelling(self):
        self.round_trip('<table><tr><td><mark>🌿</mark> A &amp; B &#x20ac; &#8364;</td></tr></table>')

    def test_inline_continuity(self):
        self.round_trip('<table><tr><td>pre<b>fix</b><br>next<br/>line</td></tr></table>')

    def test_whitespace_in_cells_preserved(self):
        self.round_trip('<table><tr><td> a\n\tb </td></tr></table>')

    def test_quotes_backslashes_unicode(self):
        self.round_trip('<table><tr><td>"Café" \\ 12,50</td></tr></table>')

    def test_nested_tables_rejected(self):
        with self.assertRaises(ValueError):
            pack_tables('<table><tr><td><table></table></td></tr></table>')

    def test_unclosed_inline_rejected(self):
        with self.assertRaises(ValueError):
            pack_tables('<table><tr><td><b>A</td></tr></table>')

    def test_incomplete_table_rejected(self):
        with self.assertRaises(ValueError):
            pack_tables('<table><tr><td>A</td></tr>')

    def test_optional_html_closes_not_inferred(self):
        with self.assertRaises(ValueError):
            pack_tables('<table><tr><td>A<td>B</tr></table>')

    def test_comments_rejected(self):
        with self.assertRaises(ValueError):
            pack_tables('<table><tr><td>A<!--x--></td></tr></table>')

    def test_outer_whitespace_rejected(self):
        with self.assertRaises(ValueError):
            pack_tables('<table>\n<tr><td>A</td></tr></table>')

    def test_unknown_inline_rejected(self):
        with self.assertRaises(ValueError):
            pack_tables('<table><tr><td><img src="x"></td></tr></table>')

    def test_empty_nonstring_rejected(self):
        for value in ('', None, 4):
            with self.assertRaises(ValueError):
                pack_tables(value)

    def test_bad_format_rejected(self):
        with self.assertRaises(ValueError):
            restore_tables({'format': 'unknown', 'tables': []})

    def test_noncanonical_close_rejected(self):
        with self.assertRaises(ValueError):
            pack_tables('<table><tr><td>A</TD></tr></table>')

    def test_whole_envelope_and_fallback(self):
        raw = '<table>' + '<tr><td>001</td><td>50 €</td></tr>' * 20 + '</table>'
        document = {'metadata': {'version': '2.0'}, 'error_status': [], 'document': {
            'pages': [{'id': 0}], 'elements': [
                {'id': 1, 'type': 'table', 'content': raw, 'bbox': [{'page_id': 0, 'coord': [1,2,3,4]}]},
                {'id': 2, 'type': 'figure', 'description': 'unvalidated', 'content': ''},
                {'id': 3, 'type': 'table', 'content': '<broken>'}]}}
        before = copy.deepcopy(document)
        result, audit = compact_document(document)
        self.assertEqual(document, before)
        self.assertEqual(audit[0]['status'], 'compacted')
        self.assertEqual(audit[1]['status'], 'original_unsupported')
        self.assertEqual(result['document']['elements'][1:], document['document']['elements'][1:])
        self.assertEqual(result['document']['pages'], document['document']['pages'])
        self.assertEqual(result['document']['elements'][0]['bbox'], document['document']['elements'][0]['bbox'])

    def test_size_increase_keeps_original(self):
        document = {'document': {'elements': [{'type': 'table', 'content': '<table></table>'}]}}
        result, audit = compact_document(document)
        self.assertEqual(result, document)
        self.assertEqual(audit[0]['status'], 'original_not_smaller')

    def test_ragged_duplicate_rows_not_changed(self):
        self.round_trip('<table><tr><td>A</td></tr><tr><td>A</td></tr><tr><td>A</td><td>B</td></tr></table>')


if __name__ == '__main__':
    unittest.main()
