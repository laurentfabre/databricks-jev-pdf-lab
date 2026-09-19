"""Synthetic raw-envelope abstention regressions; no real documents or calls."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_bbox_literal_evidence import fixture
from bbox_literal_evidence import audit
from bbox_page_provenance import bindings,digest
from shared_verifier_budget import prepare as original
from shared_verifier_budget_v2 import prepare


class AbstentionRegressionTests(unittest.TestCase):
    def setUp(self): self.raw,self.parsed,self.schema,self.contract = fixture()
    def rejected(self):
        self.contract['bindings'] = bindings(self.raw,self.parsed,self.schema)
        return {'bindings':self.contract['bindings'],'contract':self.contract,
            'document_abstention':'Successful unchanged Precision2.1 BBOX response required',
            'rows':[],'sources':[],'counts':{},'quality_accepted':False,'raw_unchanged':True,'new_ai_calls':0}
    def run_case(self,index=None):
        index = self.rejected() if index is None else index
        return prepare(self.raw,self.parsed,self.schema,'Synthetic instructions',index,digest(index))
    def test_missing_mode_with_object_response(self):
        self.raw['metadata'].pop('mode'); self.assertEqual(self.run_case()['records'],[])
    def test_null_mode_with_object_response(self):
        self.raw['metadata']['mode'] = None; self.assertEqual(self.run_case()['records'],[])
    def test_missing_chunk_type(self):
        self.raw['metadata'].pop('chunk_type'); self.assertFalse(self.run_case()['inventory']['quality_accepted'])
    def test_metadata_null(self):
        self.raw['metadata'] = None; self.assertEqual(self.run_case()['inventory']['selected_strings'],0)
    def test_wrong_version(self):
        self.raw['metadata']['version'] = '2.0'; self.assertEqual(self.run_case()['records'],[])
    def test_derived_result(self):
        self.raw['derivation'] = {}; self.assertEqual(self.run_case()['records'],[])
    def test_null_response(self):
        self.raw['response'] = None; self.assertEqual(self.run_case()['records'],[])
    def test_service_error(self):
        self.raw['error_message'] = 'synthetic error'; self.assertEqual(self.run_case()['records'],[])
    def test_unexplained_abstention_rejected(self):
        with self.assertRaises(ValueError): self.run_case()
    def test_success_unchanged(self):
        index = audit(self.raw,self.parsed,self.schema,self.contract)
        self.assertEqual(self.run_case(index),original(self.raw,self.parsed,self.schema,'Synthetic instructions',index,digest(index)))
    def test_stale_binding_rejected(self):
        self.raw['metadata'].pop('mode'); index=self.rejected(); self.raw['response']['property_name']['value']='changed'
        with self.assertRaises(ValueError): self.run_case(index)
    def test_nonempty_abstention_rejected(self):
        self.raw['metadata'].pop('mode'); index=self.rejected(); index['rows']=[{}]
        with self.assertRaises(ValueError): self.run_case(index)
    def test_no_mutation(self):
        self.raw['metadata'].pop('mode'); before=deepcopy(self.raw); self.run_case(); self.assertEqual(self.raw,before)


if __name__ == '__main__': unittest.main()
