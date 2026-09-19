"""Fabricated differential tests; no source documents, SQL, network or AI calls."""
from copy import deepcopy
from functools import partial
import inspect
import io
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import bbox_literal_evidence as reference
import bbox_literal_evidence_fast as candidate
from bbox_page_provenance import bindings
import literal_matchers
import test_bbox_literal_evidence as reference_tests

STRATEGIES = ('compiled_regex', 'literal_find')


class LiteralLookupTests(unittest.TestCase):
    def same(self, text, value):
        expected = reference.contains(text, value)
        for strategy in STRATEGIES:
            self.assertEqual(literal_matchers.make_matcher(strategy)(text, value), expected,
                             (strategy, text, value))

    def test_empty(self):
        for text, value in [('', ''), ('x', ''), ('', 'x')]: self.same(text, value)

    def test_word_boundaries(self):
        for text in ['160 min', '60 minutes', '60 min', '_60 min', '60 min_', '(60 min)']:
            self.same(text, '60 min')

    def test_later_occurrence(self):
        for text in ['x60 min; 60 min', '60 minutes; 60 min', '60 min_ 60 min']:
            self.same(text, '60 min')
            self.assertTrue(literal_matchers.literal_find(text, '60 min'))

    def test_overlap(self):
        self.same('xa.a.a', 'a.a')
        self.assertTrue(literal_matchers.literal_find('xa.a.a', 'a.a'))

    def test_unicode(self):
        for char in ['é', '甲', '²', '𐐀', '\u0301', '—', '_', '\u200d', '①', '🛁']:
            for value in [char, char+'a', 'a'+char, 'a']:
                for text in [char+'a', 'a'+char, char+' a', ' '+char+' ']:
                    self.same(text, value)

    def test_regex_metacharacters(self):
        for value in ['[a]', '.*', '(60)', '$5', 'a+b', '\\d', '^', '|', 'x?']:
            self.same('before '+value+' after', value)
            self.same('nothing', value)

    def test_seeded_match_equivalence(self):
        rng = random.Random(45064)
        alphabet = 'ab AB09_é甲²①𐐀🛁\u0301\u200d .,+*[]()\n\t'
        matchers = [literal_matchers.make_matcher(s) for s in STRATEGIES]
        for _ in range(4000):
            text = ''.join(rng.choices(alphabet, k=rng.randrange(60)))
            if rng.random() < 0.6 and text:
                i = rng.randrange(len(text)); value = text[i:i+rng.randrange(12)]
            else: value = ''.join(rng.choices(alphabet, k=rng.randrange(10)))
            expected = reference.contains(text, value)
            for matcher in matchers: self.assertEqual(matcher(text, value), expected, (text, value))

    def test_pattern_cached_per_value(self):
        with patch.object(literal_matchers.re, 'compile', wraps=literal_matchers.re.compile) as compile_fn:
            matcher = literal_matchers.make_matcher('compiled_regex')
            for text in ['a', 'b', ' a ', '_a']: matcher(text, 'a')
            self.assertEqual(compile_fn.call_count, 1)

    def test_cache_isolated_per_factory(self):
        with patch.object(literal_matchers.re, 'compile', wraps=literal_matchers.re.compile) as compile_fn:
            for _ in range(2): literal_matchers.make_matcher('compiled_regex')('a', 'a')
            self.assertEqual(compile_fn.call_count, 2)

    def test_unknown_strategy(self):
        with self.assertRaises(ValueError): literal_matchers.make_matcher('fuzzy')

    def test_reference_suite_both_candidates(self):
        for strategy in STRATEGIES:
            with patch.object(reference_tests, 'audit', partial(candidate.audit, strategy=strategy)):
                suite = unittest.defaultTestLoader.loadTestsFromTestCase(reference_tests.BboxLiteralEvidenceTests)
                log = io.StringIO()
                result = unittest.TextTestRunner(stream=log).run(suite)
                self.assertEqual(result.testsRun, 40)
                self.assertTrue(result.wasSuccessful(), log.getvalue())

    def test_seeded_audit_equivalence(self):
        rng = random.Random(64045)
        values = ['Cabin Amber', 'Café 甲', 'per night', 'Private per visitor', '60 min',
                  '60 MIN', '60\nmin', 'shower', 'not present', '甲乙', 'a.a']
        for _ in range(40):
            args = reference_tests.fixture()
            args[0]['response']['items'][0]['prices'][0]['basis'].update(
                value=rng.choice(values), citation_ids=rng.choice([[7], [12], [20], [7, 12], [], [999]]))
            args[-1]['bindings'] = bindings(*args[:3])
            expected = reference.audit(*args)
            for strategy in STRATEGIES: self.assertEqual(candidate.audit(*args, strategy=strategy), expected)

    def test_inputs_unchanged(self):
        args = reference_tests.fixture(); original = deepcopy(args)
        for strategy in STRATEGIES:
            candidate.audit(*args, strategy=strategy)
            self.assertEqual(args, original)

    def test_only_lookup_changes(self):
        source = inspect.getsource(candidate.audit)
        source = source.replace("def audit(raw, parsed, schema, contract, *, strategy='literal_find'):\n    contains = make_matcher(strategy)",
                                'def audit(raw, parsed, schema, contract):')
        source = source.replace("descriptions = [(s['index'], normalized(s['element']['description']))",
                                "descriptions = [(s['index'], s['element']['description'])")
        source = source.replace('desc = [i for i, text in descriptions if contains(text, norm)]',
                                'desc = [i for i, text in descriptions if contains(normalized(text), norm)]')
        self.assertEqual(source, inspect.getsource(reference.audit))


if __name__ == '__main__': unittest.main()
