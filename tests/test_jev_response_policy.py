import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from jev_router import MODEL, build_request
from jev_response_policy import review_inconsistent_choices


class JevResponsePolicyTests(unittest.TestCase):
    def setUp(self):
        self.request = build_request([{'scope': 'page', 'native_characters': 10}])
        self.answer = {'type': 'choice', 'choice': 'native_layout_precision', 'confidence': .14,
            'probabilities': {'native_text_precision': .12, 'visual_review': .36,
                              'managed_parse_precision': .17, 'native_layout_precision': .35}}

    def call(self):
        return review_inconsistent_choices(self.request, {'model': MODEL,
            'answers': {'route_0': self.answer}, 'usage': {'input_tokens':1, 'output_tokens':1}})

    def test_conflicting_choice_is_review_not_repaired(self):
        row = self.call()['recommendations'][0]
        self.assertFalse(row['response_contract_valid'])
        self.assertFalse(row['dispatch_authorized'])
        self.assertEqual(row['service_choice'], 'native_layout_precision')
        self.assertEqual(row['candidate_method'], 'visual_review')
        self.assertEqual(self.answer['choice'], 'native_layout_precision')

    def test_unknown_option_remains_fatal(self):
        self.answer['choice'] = 'unapproved'
        with self.assertRaises(ValueError):
            self.call()

    def test_valid_choice_remains_model_recommendation(self):
        self.answer['choice'] = 'visual_review'
        self.assertTrue(self.call()['recommendations'][0]['response_contract_valid'])

    def test_invalid_distribution_remains_fatal(self):
        self.answer['probabilities']['visual_review'] = .99
        with self.assertRaises(ValueError):
            self.call()
