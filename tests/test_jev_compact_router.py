import copy
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from jev_router import build_request, MODEL, METHODS
from jev_compact_router import compact_request, validated_request
from jev_compact_transport import run_once


class CompactRouterTests(unittest.TestCase):
    def setUp(self):
        self.original = build_request([{'scope':'page','native_characters':0},
            {'scope':'page','native_characters':1500,'column_layout_risk':True}],
            {'scope':'document','page_count':2,'table_alignment_risk':None})
        self.request = compact_request(self.original)

    def test_metadata_context_and_constraints_exact(self):
        self.assertEqual({k:self.request['state'][k] for k in self.original['state']},self.original['state'])
        self.assertEqual(self.request['state']['method_definitions'],METHODS)
        self.assertIn('Structural metadata cannot prove',self.request['state']['selection_policy'])

    def test_all_option_sets_and_page_references_preserved(self):
        for i, key in enumerate(self.original['questions']):
            self.assertEqual(set(self.request['questions'][key]['criteria']),set(self.original['questions'][key]['criteria']))
            self.assertIn(f'`diagnostics[{i}]`',self.request['questions'][key]['instructions'])

    def test_full_batch_is_smaller(self):
        original = build_request([{'scope':'page','native_characters':1500}]*32)
        self.assertLess(len(validated_request(compact_request(original))),len(json.dumps(original).encode())/2)

    def test_extra_source_text_blocked(self):
        for location in ('state','diagnostic','question','policy'):
            request = copy.deepcopy(self.request)
            if location=='state': request['state']['source_text']='private'
            elif location=='diagnostic': request['state']['diagnostics'][0]['text']='private'
            elif location=='question': request['questions']['route_0']['instructions']+='private'
            else: request['state']['selection_policy']+='private'
            with self.assertRaises(ValueError): validated_request(request)

    def test_nonmetadata_input_blocked(self):
        original = copy.deepcopy(self.original)
        original['state']['diagnostics'][0]['native_characters']='secret text'
        with self.assertRaises(ValueError): compact_request(original)

    def response(self):
        return {'model':MODEL,'usage':{'input_tokens':100,'output_tokens':10},'answers':{
            key:{'type':'choice','choice':'visual_review','confidence':1,
                'probabilities':{option:int(option=='visual_review') for option in q['criteria']}}
            for key,q in self.request['questions'].items()}}

    def test_retained_response_prevents_repeat(self):
        calls=[]
        def send(payload,secret):
            calls.append(1)
            return 200,json.dumps(self.response()).encode()
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(run_once(self.request,folder,'dummy',send)['reused'])
            self.assertTrue(run_once(self.request,folder,'dummy',send)['reused'])
            self.assertEqual(len(calls),1)

    def test_unknown_outcome_never_retried(self):
        calls=[]
        def send(payload,secret):
            calls.append(1)
            raise TimeoutError()
        with tempfile.TemporaryDirectory() as folder:
            for _ in range(2):
                with self.assertRaises(RuntimeError): run_once(self.request,folder,'dummy',send)
            self.assertEqual(len(calls),1)

    def test_http_error_redacted_and_not_retried(self):
        calls=[]
        def send(payload,secret):
            calls.append(1)
            return 401,json.dumps({'error':secret}).encode()
        with tempfile.TemporaryDirectory() as folder:
            for _ in range(2):
                with self.assertRaises(RuntimeError): run_once(self.request,folder,'dummy-secret',send)
            self.assertEqual(len(calls),1)
            for path in pathlib.Path(folder).rglob('*.json'):
                self.assertNotIn('dummy-secret',path.read_text())

if __name__=='__main__': unittest.main()
