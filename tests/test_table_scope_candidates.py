"""Synthetic-only scope grammar tests; no documents, services, or acceptance."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from table_scope_candidates import scan


def fixture(header='Choose a preparation', markers=('', 'P'), suffix=True):
    raw = '<table><tr><td>Item Alpha</td><td>12 €</td><td>Item Beta</td><td>18 €</td></tr>'
    raw += '<tr><td>Alpha translation</td><td></td><td>Beta translation</td><td></td></tr>'
    raw += '<tr><td colspan="4">' + header + '</td></tr>'
    for i, mark in enumerate(markers):
        raw += f'<tr><td>Method {i}</td><td></td><td>{mark}</td><td></td></tr>'
    if suffix:
        raw += '<tr><td>Other item</td><td></td><td></td><td>9 €</td></tr>'
    return raw + '</table>'


class TableScopeTests(unittest.TestCase):
    def test_shared_structural_group(self):
        candidate = scan(fixture())['candidates'][0]
        self.assertEqual([o['column'] for o in candidate['owners']], [0, 2])
        self.assertEqual([r['row'] for r in candidate['children']], [3, 4])
        self.assertEqual(candidate['boundary'], {'row': 5, 'reason': 'price_or_currency_boundary'})

    def test_exact_unicode_spans(self):
        raw = fixture('苗🌶 Choose a preparation').replace('Item Alpha', '甲🌿 Alpha')
        candidate = scan(raw)['candidates'][0]
        spans = [candidate['heading']]
        for owner in candidate['owners']:
            spans += [owner['label'], owner['price']] + owner['continuations']
        for row in candidate['children']:
            spans += [row['label']] + row['literal_markers']
        for span in spans:
            self.assertEqual(raw[span['start']:span['stop']], span['html'])

    def test_no_acceptance(self):
        result = scan(fixture())
        self.assertIs(result['quality_accepted'], False)
        self.assertIs(result['semantic_ownership_established'], False)
        self.assertIs(result['candidates'][0]['semantic_review_required'], True)

    def test_nonconditional_header_is_semantically_unresolved(self):
        result = scan(fixture('All prices include local taxes'))
        self.assertEqual(len(result['candidates']), 1)
        self.assertFalse(result['semantic_ownership_established'])

    def test_negated_header_not_accepted(self):
        result = scan(fixture('The methods below do NOT apply to these items'))
        self.assertEqual(len(result['candidates']), 1)
        self.assertFalse(result['quality_accepted'])

    def test_marker_not_interpreted(self):
        row = scan(fixture())['candidates'][0]['children'][1]
        self.assertEqual(row['literal_markers'][0]['text'], 'P')
        self.assertNotIn('meaning', row['literal_markers'][0])

    def test_empty_marker_is_not_safe(self):
        row = scan(fixture())['candidates'][0]['children'][0]
        self.assertEqual(row['literal_markers'], [])
        self.assertNotIn('allergen_free', row)

    def test_entities_and_breaks_retained(self):
        raw = fixture('Methods &amp; options<br>Second line')
        cell = scan(raw)['candidates'][0]['heading']
        self.assertEqual(cell['html'], 'Methods &amp; options<br>Second line')
        self.assertEqual(cell['text'], 'Methods & options Second line')

    def test_single_quote_colspan(self):
        self.assertEqual(len(scan(fixture().replace('colspan="4"', "colspan='4'"))['candidates']), 1)

    def test_unquoted_colspan(self):
        self.assertEqual(len(scan(fixture().replace('colspan="4"', 'colspan=4'))['candidates']), 1)

    def test_th_header(self):
        raw = fixture().replace('<td colspan="4">Choose a preparation</td>', '<th colspan="4">Choose a preparation</th>')
        self.assertEqual(len(scan(raw)['candidates']), 1)

    def test_inline_markup_preserved(self):
        result = scan(fixture('<b>Choose</b> a preparation'))
        self.assertIn('<b>', result['candidates'][0]['heading']['html'])

    def test_no_heading_no_hypothesis(self):
        raw = fixture().replace('<tr><td colspan="4">Choose a preparation</td></tr>', '')
        self.assertEqual(scan(raw)['candidates'], [])

    def test_no_priced_owners(self):
        raw = fixture().replace('12 €', '').replace('18 €', '')
        self.assertEqual(scan(raw)['candidates'], [])

    def test_unknown_owner_currency_abstains(self):
        self.assertEqual(scan(fixture().replace('12 €', '12 USD'))['candidates'], [])

    def test_unrecognized_number_format_abstains(self):
        self.assertEqual(scan(fixture().replace('12 €', '1 200 €'))['candidates'], [])

    def test_currency_prefix_and_decimal(self):
        self.assertEqual(len(scan(fixture().replace('12 €', '€12.50'))['candidates']), 1)

    def test_translation_side_text_abstains(self):
        raw = fixture().replace('Alpha translation</td><td>', 'Alpha translation</td><td>note')
        self.assertEqual(scan(raw)['candidates'], [])

    def test_rowspan_unsupported(self):
        self.assertEqual(scan(fixture().replace('<td>', '<td rowspan="2">', 1))['status'], 'unsupported')

    def test_style_unsupported(self):
        self.assertEqual(scan(fixture().replace('<td>', '<td class="x">', 1))['status'], 'unsupported')

    def test_ragged_unsupported(self):
        self.assertEqual(scan(fixture().replace('<td>18 €</td>', ''))['status'], 'unsupported')

    def test_malformed_unsupported(self):
        self.assertEqual(scan(fixture().replace('</table>', ''))['status'], 'unsupported')

    def test_multiple_tables_unsupported(self):
        self.assertEqual(scan(fixture() + fixture())['status'], 'unsupported')

    def test_nested_table_unsupported(self):
        self.assertEqual(scan(fixture('<table><tr><td>x</td></tr></table>'))['status'], 'unsupported')

    def test_no_children_no_candidate(self):
        self.assertEqual(scan(fixture(markers=()))['candidates'], [])

    def test_unknown_marker_stops(self):
        result = scan(fixture(markers=('', 'XX')))
        candidate = result['candidates'][0]
        self.assertEqual(len(candidate['children']), 1)
        self.assertEqual(candidate['boundary']['reason'], 'ambiguous_or_empty_row')

    def test_price_in_child_stops(self):
        result = scan(fixture(markers=('', '5 €')))
        self.assertEqual(len(result['candidates'][0]['children']), 1)

    def test_other_currency_stops(self):
        self.assertEqual(len(scan(fixture(markers=('', '$5')))['candidates'][0]['children']), 1)

    def test_parenthesized_marker_preserved(self):
        mark = scan(fixture(markers=('(V)',)))['candidates'][0]['children'][0]['literal_markers'][0]
        self.assertEqual(mark['html'], '(V)')

    def test_table_end_boundary(self):
        self.assertEqual(scan(fixture(suffix=False))['candidates'][0]['boundary']['reason'], 'table_end')

    def test_three_owners(self):
        raw = '<table><tr><td>Alpha</td><td>1€</td><td>Beta</td><td>2€</td><td>Gamma</td><td>3€</td></tr><tr><td colspan="6">Choose style</td></tr><tr><td>Style one</td><td></td><td></td><td>P</td><td></td><td></td></tr></table>'
        self.assertEqual(len(scan(raw)['candidates'][0]['owners']), 3)

    def test_one_owner(self):
        raw = '<table><tr><td>Alpha</td><td>1€</td></tr><tr><td colspan="2">Choose style</td></tr><tr><td>Style one</td><td>P</td></tr></table>'
        self.assertEqual(len(scan(raw)['candidates'][0]['owners']), 1)


if __name__ == '__main__':
    unittest.main()
