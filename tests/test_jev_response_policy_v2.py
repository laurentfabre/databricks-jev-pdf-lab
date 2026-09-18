import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from jev_router import MODEL, build_request
from jev_response_policy_v2 import review_inconsistent_choices


class JevResponsePolicyV2Tests(unittest.TestCase):
    def setUp(self):
        self.request = build_request([{'scope':'page', 'native_characters':0}])
        self.answer = {'type':'choice','choice':'managed_parse_precision','confidence':.5,
            'probabilities':{'managed_parse_precision':.75, 'visual_review':.24}}

    def call(self):
        return review_inconsistent_choices(self.request, {'model':MODEL,
            'answers':{'route_0':self.answer}})['recommendations'][0]

    def test_rounded_mass_is_review_without_normalization(self):
        row = self.call()
        self.assertFalse(row['response_contract_valid'])
        self.assertEqual(row['candidate_method'], 'visual_review')
        self.assertEqual(row['probability_sum'], .99)
        self.assertEqual(row['probabilities'], self.answer['probabilities'])

    def test_unknown_option_still_fails(self):
        self.answer['choice'] = 'unapproved'
        with self.assertRaises(ValueError):
            self.call()

    def test_nan_still_fails(self):
        self.answer['probabilities']['visual_review'] = float('nan')
        with self.assertRaises(ValueError):
            self.call()
