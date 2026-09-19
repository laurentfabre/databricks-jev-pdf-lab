from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from citation_span_review import citation_intervals, literal_support


class SpanReviewTests(unittest.TestCase):
    def proof(self, text, spans, literal, ids=None, scopes=None):
        meta = {'chunk_type': 'span', 'citations': [
            {'id': i, 'start': a, 'stop': b} for i, (a, b) in enumerate(spans)]}
        field = {'citation_ids': list(range(len(spans))) if ids is None else ids}
        return literal_support(field, meta, text, literal, scopes)

    def test_adjacent_spans_cover_split_literal(self):
        self.assertTrue(self.proof('Alpha soup', [(0, 6), (6, 10)], 'Alpha soup')['supported'])

    def test_gap_never_bridged(self):
        self.assertFalse(self.proof('Alpha soup', [(0, 5), (6, 10)], 'Alpha soup')['supported'])

    def test_unrelated_region_cannot_supply_value(self):
        self.assertFalse(self.proof('12.50 tax; 12.50 soup', [(0, 9)], '12.50', scopes=[[10, 20]])['supported'])

    def test_overlaps_merge_without_duplication(self):
        proof = self.proof('Alpha soup', [(0, 7), (5, 10)], 'Alpha soup')
        self.assertEqual(proof['intervals'], [[0, 10]])
        self.assertTrue(proof['supported'])

    def test_order_does_not_change_coverage(self):
        self.assertTrue(self.proof('Alpha soup', [(6, 10), (0, 6)], 'Alpha soup', ids=[1, 0])['supported'])

    def test_unicode_offsets_are_characters(self):
        self.assertTrue(self.proof('🌿 Café', [(0, 3), (3, 6)], 'Café')['supported'])
        self.assertFalse(self.proof('🌿 Café', [(0, 9)], 'Café')['valid'])

    def test_invalid_bounds(self):
        for spans in ([(-1, 4)], [(0, 20)], [(3, 3)], [(4, 2)], [(True, 3)], [(0, 3.0)]):
            self.assertFalse(self.proof('Alpha', spans, 'Alpha')['valid'])

    def test_unknown_id(self):
        self.assertFalse(self.proof('Alpha', [(0, 5)], 'Alpha', ids=[2])['valid'])

    def test_boolean_id_rejected(self):
        self.assertFalse(self.proof('Alpha', [(0, 5)], 'Alpha', ids=[False])['valid'])

    def test_duplicate_metadata_id_rejected(self):
        meta = {'chunk_type': 'span', 'citations': [{'id': 0, 'start': 0, 'stop': 5}] * 2}
        self.assertFalse(literal_support({'citation_ids': [0]}, meta, 'Alpha', 'Alpha')['valid'])

    def test_repeated_field_id_does_not_add_coverage(self):
        self.assertFalse(self.proof('Alpha soup', [(0, 5)], 'Alpha soup', ids=[0, 0])['supported'])

    def test_missing_citations(self):
        self.assertFalse(self.proof('Alpha', [(0, 5)], 'Alpha', ids=[])['valid'])

    def test_empty_needle(self):
        self.assertFalse(self.proof('Alpha', [(0, 5)], '')['valid'])

    def test_unsupported_type(self):
        self.assertFalse(literal_support({'citation_ids': [0]}, {'chunk_type': 'bbox'}, 'Alpha', 'Alpha')['valid'])

    def test_original_unchanged(self):
        field = {'value': 'Alpha', 'citation_ids': [1, 0]}
        meta = {'chunk_type': 'span', 'citations': [{'id': 0, 'start': 0, 'stop': 2}, {'id': 1, 'start': 2, 'stop': 5}]}
        before = deepcopy((field, meta))
        literal_support(field, meta, 'Alpha', 'Alpha')
        self.assertEqual((field, meta), before)

    def test_scope_cannot_be_bridged(self):
        self.assertFalse(self.proof('Alpha soup', [(0, 10)], 'Alpha soup', scopes=[[0, 5], [5, 10]])['supported'])

    def test_invalid_scope(self):
        self.assertFalse(self.proof('Alpha', [(0, 5)], 'Alpha', scopes=[[0, 8]])['valid'])

    def test_all_occurrences_recorded(self):
        self.assertEqual(self.proof('A A', [(0, 3)], 'A')['occurrences'], [[0, 1], [2, 3]])


if __name__ == '__main__':
    unittest.main()
