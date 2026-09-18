import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from jev_router import MODEL, build_request
from jev_transport import run_once, validated_request, validate_usage


class JevTransportTests(unittest.TestCase):
    def setUp(self):
        self.request = build_request([{'scope': 'page', 'native_characters': 0}])
        self.response = {'model': MODEL, 'answers': {'route_0': {
            'type': 'choice', 'choice': 'visual_review', 'confidence': 1,
            'probabilities': {'visual_review': 1, 'managed_parse_precision': 0}}},
            'usage': {'input_tokens': 17, 'output_tokens': 5}}

    def test_success_is_reused_without_network(self):
        calls = []
        def sender(payload, secret):
            calls.append(1)
            return 200, json.dumps(self.response).encode()
        with tempfile.TemporaryDirectory() as directory:
            first = run_once(self.request, directory, 'test-credential', sender)
            second = run_once(self.request, directory, 'test-credential', sender)
            self.assertFalse(first['reused'])
            self.assertTrue(second['reused'])
            self.assertEqual(len(calls), 1)

    def test_timeout_never_replayed(self):
        calls = []
        def sender(payload, secret):
            calls.append(1)
            raise TimeoutError('do not print credential')
        with tempfile.TemporaryDirectory() as directory:
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    run_once(self.request, directory, 'test-credential', sender)
            self.assertEqual(len(calls), 1)

    def test_http_error_redacted_and_never_replayed(self):
        calls = []
        def sender(payload, secret):
            calls.append(1)
            return 401, json.dumps({'message': secret}).encode()
        with tempfile.TemporaryDirectory() as directory:
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    run_once(self.request, directory, 'test-credential', sender)
            self.assertEqual(len(calls), 1)
            for path in pathlib.Path(directory).rglob('*.json'):
                self.assertNotIn('test-credential', path.read_text())

    def test_any_extra_content_or_changed_question_refused(self):
        self.request['state']['private_name'] = 'not allowed'
        with self.assertRaises(ValueError):
            validated_request(self.request)
        del self.request['state']['private_name']
        self.request['questions']['route_0']['instructions'] += 'extra'
        with self.assertRaises(ValueError):
            validated_request(self.request)

    def test_usage_is_not_inferred(self):
        for usage in (None, {}, {'input_tokens': True, 'output_tokens': 0},
                      {'input_tokens': -1, 'output_tokens': 0}):
            with self.assertRaises(ValueError):
                validate_usage({'usage': usage})



if __name__ == '__main__':
    unittest.main()
