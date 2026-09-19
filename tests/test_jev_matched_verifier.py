"""Fabricated fixtures only. No network, credential lookup or real source data."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shared_verifier_budget import CRITERIA, MODEL, encode, measure, packets, question_id
from jev_matched_verifier import (evaluate, run, sha, strict_json, validate_answer,
                                  validate_schedule)


def fixture():
    context = {'document':'Fabricated test text: blue cabins.'}
    records = [{'claim':{'path':['items',i,'name'], 'field':{'value':f'Cabin {i}'},
                'cited_element_indices':[0]},
                'owner':{'path':['items',i], 'record':{'name':f'Cabin {i}'}},
                'context':context} for i in range(48)]
    payloads = {l:[encode(p) for _,p in packets(records,l)] for l in ('single','shared24')}
    consent = {'model':MODEL,'destination':'https://api.typesafe.ai/v1/systemone',
        'rounds':[{'order':['single','shared24']},{'order':['shared24','single']}],
        'max_in_flight_per_arm':4,'planned_max_requests':100,
        'planned_request_bytes_including_repetitions':2*sum(len(b) for ps in payloads.values() for b in ps),
        'source_case':{'doc_id':999,'context_sha256':sha(encode(context))},'layouts':{}}
    for layout in payloads:
        m=measure(records,layout)
        consent['layouts'][layout]={'requests_per_round':m['requests'],
            'request_bytes_per_round':m['request_bytes'],'max_request_bytes':m['max_request_bytes'],
            'packets':m['manifest']}
    return records,payloads,consent


def response(payload):
    req=json.loads(payload)
    return {'model':MODEL,'answers':{q:{'type':'choice','choice':'supports','confidence':1,
        'probabilities':{k:float(k=='supports') for k in CRITERIA}} for q in req['questions']},
        'usage':{'input_tokens':len(payload)//4,'output_tokens':len(req['questions'])*10}}


def sender(payload, secret):
    return 200, encode(response(payload))


class MatchedVerifierTests(unittest.TestCase):
    def setUp(self):
        self.records,self.payloads,self.consent=fixture()
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name)/'run'
        self.ref={'rows':[{'path':r['claim']['path'],'acceptable_labels':['supports']}
                         for r in self.records],'no_jev_control':{'automatic_accept_or_delete':False}}

    def execute(self, send=sender):
        return run(self.payloads,self.consent,self.out,'synthetic-secret-only','a'*64,send)

    def test_schedule_exact_order_and_scope(self):
        schedule=validate_schedule(self.payloads,self.consent)
        self.assertEqual([(a['round'],a['layout']) for a in schedule],
                         [(1,'single'),(1,'shared24'),(2,'shared24'),(2,'single')])
        self.assertEqual(sum(len(a['packets']) for a in schedule),100)

    def test_complete_all_attempts_and_quality_not_accepted(self):
        result=self.execute()
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['attempts_consumed'],100)
        self.assertEqual(result['attempt_body_bytes_consumed'],self.consent['planned_request_bytes_including_repetitions'])
        self.assertFalse(result['quality_accepted'])
        self.assertEqual(len(list(self.out.rglob('intent.json'))),100)
        self.assertEqual(len(list(self.out.rglob('response.redacted.bin'))),100)
        self.assertTrue(all(a['maximum_inflight_http']<=4 for a in result['arms']))

    def test_corrupt_final_packet_stops_before_first_send(self):
        self.payloads['shared24'][-1]+=b' '
        with self.assertRaises(ValueError): self.execute(lambda *_:self.fail('Sent'))
        self.assertFalse(self.out.exists())

    def test_round_and_concurrency_and_limits_cannot_change(self):
        for key,value in [('model','jev-latest'),('max_in_flight_per_arm',5),
                          ('planned_max_requests',101),('planned_request_bytes_including_repetitions',2362389),
                          ('rounds',[{'order':['single']}]),('destination','https://other.invalid')]:
            with self.subTest(key=key):
                changed=deepcopy(self.consent);changed[key]=value
                with self.assertRaises(ValueError):validate_schedule(self.payloads,changed)

    def test_manifest_cardinality_order_hash_and_sizes(self):
        for key,value in [('index',1),('sha256','0'*64),('request_bytes',1),('questions',2),('question_ids',[])]:
            with self.subTest(key=key):
                changed=deepcopy(self.consent);changed['layouts']['single']['packets'][0][key]=value
                with self.assertRaises(ValueError):validate_schedule(self.payloads,changed)

    def test_changed_context_fails(self):
        self.consent['source_case']['context_sha256']='0'*64
        with self.assertRaises(ValueError):self.execute()

    def test_duplicate_claim_or_missing_packets_fails(self):
        self.payloads['single'][1]=self.payloads['single'][0]
        with self.assertRaises(ValueError):self.execute()

    def test_empty_secret_fails_before_markers(self):
        with self.assertRaises(ValueError):run(self.payloads,self.consent,self.out,'','a'*64,sender)
        self.assertFalse(self.out.exists())

    def test_intent_precedes_send(self):
        def inspect(payload,key):
            self.assertTrue(list(self.out.rglob('*_'+sha(payload)+'/intent.json')))
            return sender(payload,key)
        self.assertEqual(self.execute(inspect)['status'],'complete')

    def test_replay_of_complete_run_forbidden(self):
        self.execute()
        with self.assertRaises(RuntimeError):self.execute(lambda *_:self.fail('Replay'))

    def test_interrupted_run_forbidden(self):
        self.out.mkdir();(self.out/'started.json').write_text('{}')
        with self.assertRaises(RuntimeError):self.execute(lambda *_:self.fail('Replay'))

    def test_http_failure_drains_at_most_four(self):
        barrier=threading.Barrier(4)
        def failure(payload,key):
            barrier.wait(timeout=10)
            return 429,b'{"error":"bounded fake rate limit"}'
        result=self.execute(failure)
        self.assertEqual(result['status'],'stopped')
        self.assertEqual(result['attempts_consumed'],4)
        self.assertEqual(len(result['arms']),1)
        self.assertEqual(result['arms'][0]['maximum_inflight_http'],4)
        self.assertEqual(len(list(self.out.rglob('outcome.json'))),4)

    def test_unknown_timeout_never_retries(self):
        def timeout(*_):raise TimeoutError('synthetic-secret-only')
        result=self.execute(timeout)
        self.assertLessEqual(result['attempts_consumed'],4)
        self.assertEqual(result['status'],'stopped')
        for p in self.out.rglob('*.json'):self.assertNotIn('synthetic-secret-only',p.read_text())
        with self.assertRaises(RuntimeError):self.execute()

    def test_bad_answer_stops_schedule(self):
        def bad(payload,key):
            r=response(payload);r['answers']={};return 200,encode(r)
        result=self.execute(bad)
        self.assertEqual(result['status'],'stopped')
        self.assertLessEqual(result['attempts_consumed'],4)

    def test_response_pin_usage_and_choice_contract(self):
        req=json.loads(self.payloads['single'][0]);valid=response(self.payloads['single'][0])
        q=next(iter(req['questions']))
        variants=[]
        for k,v in [('model','jev-latest'),('answers',{}),('usage',{'input_tokens':True,'output_tokens':0}),
                    ('usage',{'input_tokens':-1,'output_tokens':0})]:
            r=deepcopy(valid);r[k]=v;variants.append(r)
        for k,v in [('type','noul'),('choice','contradicts'),('choice','unknown'),('confidence',float('nan')),
                    ('confidence',True),('probabilities',{'supports':1}),
                    ('probabilities',{k:0.3 for k in CRITERIA})]:
            r=deepcopy(valid);r['answers'][q][k]=v;variants.append(r)
        for r in variants:
            with self.subTest(response=r):
                with self.assertRaises(ValueError):validate_answer(req,r)

    def test_json_duplicate_nonfinite_and_invalid_rejected(self):
        for data in [b'{"x":1,"x":2}',b'{"x":NaN}',b'not json']:
            with self.assertRaises(ValueError):strict_json(data)

    def test_redacted_raw_error_retained_without_secret(self):
        def echoed(payload,key):return 401,('{"error":"'+key+'"}').encode()
        result=self.execute(echoed)
        self.assertEqual(result['status'],'stopped')
        for p in self.out.rglob('*'):
            if p.is_file():self.assertNotIn(b'synthetic-secret-only',p.read_bytes())
        self.assertTrue(all(r['credential_redacted'] for r in result['arms'][0]['rows'] if r['attempted']))

    def test_reference_disagreements_and_ambiguities_separate(self):
        result=self.execute()
        self.ref['rows'][0]['acceptable_labels']=['supports','insufficient_evidence']
        self.ref['rows'][1]['acceptable_labels']=['contradicts']
        review=evaluate(result,self.ref,self.records)
        for arm in review['arms']:
            self.assertEqual(arm['determinate_correct'],46)
            self.assertEqual(arm['determinate_incorrect'],1)
            self.assertEqual(arm['ambiguous_judged'],1)
        self.assertTrue(all(c['paired_claims']==48 and not c['choice_disagreements'] for c in review['comparisons']))
        self.assertFalse(review['incremental_semantic_benefit_proven'])

    def test_invalid_reference_never_silently_scores_subset(self):
        self.ref['rows'].pop()
        with self.assertRaises(ValueError):evaluate({'arms':[]},self.ref,self.records)

    def test_shared_arm_failure_prevents_second_round(self):
        def failing_shared(payload,key):
            if len(json.loads(payload)['questions'])==24:return 422,b'{"error":"fake context failure"}'
            return sender(payload,key)
        result=self.execute(failing_shared)
        self.assertEqual(result['status'],'stopped')
        self.assertEqual(len(result['arms']),2)
        self.assertTrue(49<=result['attempts_consumed']<=50)
        self.assertEqual(result['arms'][0]['status'],'complete')


if __name__=='__main__':unittest.main()
