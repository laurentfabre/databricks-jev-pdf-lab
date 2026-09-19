from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from jev_bounded_concurrency import page_recommendations, run_round
from jev_compact_router import compact_request, validated_request
from jev_router import build_request


class ConcurrencyTests(unittest.TestCase):
    def requests(self, n=8):
        return [compact_request(build_request([{'scope':'page', 'native_characters':100+i}]))
                for i in range(n)]

    def sender(self, payload, secret):
        request = json.loads(payload)
        return 200, json.dumps({'model':request['model'], 'usage':{'input_tokens':100, 'output_tokens':20},
            'answers': {key:{'type':'choice', 'choice':'visual_review', 'confidence':1,
                'probabilities': {k:int(k=='visual_review') for k in value['criteria']}}
                for key, value in request['questions'].items()}}).encode()

    def test_parallel_bound_and_stable_result_order(self):
        barrier = threading.Barrier(4)
        def send(payload, secret):
            barrier.wait(timeout=5)
            return self.sender(payload, secret)
        with tempfile.TemporaryDirectory() as folder:
            result = run_round(self.requests(), list(reversed(range(8))), 4, folder, 'dummy', send)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['maximum_inflight_http'], 4)
        self.assertEqual([r['index'] for r in result['rows']], list(range(8)))
        self.assertEqual(result['requests_started'], 8)
        self.assertFalse(result['quality_accepted'])

    def test_serial_has_one_inflight(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run_round(self.requests(3), [2,0,1], 1, folder, 'dummy', self.sender)
        self.assertEqual(result['maximum_inflight_http'], 1)
        self.assertEqual(result['requests_started'], 3)

    def test_wire_payloads_unchanged(self):
        requests, actual = self.requests(4), []
        before = deepcopy(requests)
        def send(payload, secret):
            actual.append(payload)
            return self.sender(payload, secret)
        with tempfile.TemporaryDirectory() as folder:
            run_round(requests, [0,1,2,3], 4, folder, 'dummy', send)
        self.assertCountEqual(actual, [validated_request(r) for r in requests])
        self.assertEqual(requests, before)

    def test_completed_round_never_dispatched_again(self):
        calls = []
        def send(payload, secret):
            calls.append(payload)
            return self.sender(payload, secret)
        with tempfile.TemporaryDirectory() as folder:
            first = run_round(self.requests(2), [0,1], 1, folder, 'dummy', send)
            second = run_round(self.requests(2), [0,1], 1, folder, 'dummy', send)
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 2)

    def test_interrupted_round_not_dispatched(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'round_started.json').write_text('{}')
            with self.assertRaises(RuntimeError):
                run_round(self.requests(1), [0], 1, folder, 'dummy', lambda *a:self.fail('dispatched'))

    def test_failed_round_preserved_not_retried(self):
        calls = []
        def send(*args):
            calls.append(1)
            raise TimeoutError('dummy-secret must not be retained')
        with tempfile.TemporaryDirectory() as folder:
            first = run_round(self.requests(3), [0,1,2], 1, folder, 'dummy-secret', send)
            second = run_round(self.requests(3), [0,1,2], 1, folder, 'dummy-secret', send)
            self.assertEqual(first, second)
            self.assertEqual(first['unscheduled_indices'], [1,2])
            for path in Path(folder).rglob('*.json'):
                self.assertNotIn('dummy-secret', path.read_text())
        self.assertEqual(len(calls), 1)

    def test_rate_limit_stops_further_serial_work(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run_round(self.requests(3), [0,1,2], 1, folder, 'dummy', lambda *a:(429,b'{}'))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['requests_started'], 1)

    def test_parallel_failure_drains_only_inflight(self):
        barrier = threading.Barrier(4)
        def send(*args):
            barrier.wait(timeout=5)
            return 529, b'{}'
        with tempfile.TemporaryDirectory() as folder:
            result = run_round(self.requests(), list(range(8)), 4, folder, 'dummy', send)
        self.assertEqual(result['requests_started'], 4)
        self.assertEqual(result['unscheduled_indices'], [4,5,6,7])

    def test_all_requests_validated_before_any_dispatch(self):
        requests = self.requests(3)
        requests[-1]['state']['source_text'] = 'not authorized'
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                run_round(requests, [0,1,2], 1, folder, 'dummy', lambda *a:self.fail('dispatched'))

    def test_duplicate_request_rejected(self):
        request = self.requests(1)[0]
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): run_round([request, request], [0,1], 1, folder, 'dummy', self.sender)

    def test_invalid_concurrency(self):
        with tempfile.TemporaryDirectory() as folder:
            for value in (0,2,5,True,1.0):
                with self.assertRaises(ValueError): run_round(self.requests(1), [0], value, folder, 'dummy', self.sender)

    def test_invalid_order(self):
        with tempfile.TemporaryDirectory() as folder:
            for order in ([0,0], [0], [0,True], [0,2]):
                with self.assertRaises(ValueError): run_round(self.requests(2), order, 1, folder, 'dummy', self.sender)

    def test_saved_identity_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            run_round(self.requests(2), [0,1], 1, folder, 'dummy', self.sender)
            with self.assertRaises(ValueError): run_round(self.requests(2), [1,0], 1, folder, 'dummy', self.sender)

    def test_empty_secret_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): run_round(self.requests(1), [0], 1, folder, '', self.sender)

    def test_latency_includes_transport_and_ledger(self):
        def send(payload, secret):
            time.sleep(0.005)
            return self.sender(payload, secret)
        with tempfile.TemporaryDirectory() as folder:
            result = run_round(self.requests(2), [0,1], 1, folder, 'dummy', send)
        self.assertGreaterEqual(result['dispatch_validate_persist_seconds'], 0.01)
        for row in result['rows']:
            self.assertLessEqual(row['worker_start_offset'], row['http_start_offset'])
            self.assertLessEqual(row['http_end_offset'], row['worker_end_offset'])

    def mapped(self, folder):
        request = compact_request(build_request([{'scope':'page', 'native_characters':100+i,
            'page_ordinal':i+1} for i in range(12)]))
        # Roundtrip reproduces sorted JSON ordering: route_10 before route_2.
        requests = [json.loads(validated_request(request))]
        result = run_round(requests, [0], 1, folder, 'dummy', self.sender)
        return requests, [{'doc_id':1, 'physical_pages':list(range(1,13))}], result

    def test_question_ids_not_object_order_bind_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            requests, mapping, result = self.mapped(folder)
            rows = page_recommendations(requests, mapping, result)
        self.assertEqual([(r['physical_page'],r['question']) for r in rows],
                         [(i+1,f'route_{i}') for i in range(12)])

    def test_wrong_page_mapping_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            requests, mapping, result = self.mapped(folder)
            mapping[0]['physical_pages'].reverse()
            with self.assertRaises(ValueError): page_recommendations(requests, mapping, result)

    def test_missing_batch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            requests, mapping, result = self.mapped(folder)
            result['rows'] = []
            with self.assertRaises(ValueError): page_recommendations(requests, mapping, result)


if __name__ == '__main__': unittest.main()
