from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from schema_field_audit import audit, occupancy, schema_paths, MISSING


def fixture():
    text = 'Garden soup per bowl'
    box = lambda value: {'value': value, 'citation_ids': [0]}
    schema = {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'name': {'type': 'string'}, 'prices': {'type': 'array', 'items': {'type': 'object',
        'properties': {'amount': {'type': 'number'}, 'basis': {'type': 'string'}}}},
        'allergens': {'type': 'array', 'items': {'type': 'string'}}}}}}
    raw = {'error_message': None, 'metadata': {'mode': 'precision', 'version': '2.1',
        'chunk_type': 'span', 'citations': [{'id': 0, 'start': 0, 'stop': len(text)}]},
        'response': {'items': [{'name': box('Garden soup'),
        'prices': [{'amount': box(8), 'basis': box('per bowl')}], 'allergens': []}]}}
    return [raw, schema, text, [[0, len(text)]], hashlib.sha256(text.encode()).hexdigest()]


class SchemaFieldAuditTests(unittest.TestCase):
    def run_case(self, args):
        before = deepcopy(args)
        result = audit(*args)
        self.assertEqual(args, before)
        self.assertFalse(result['quality_accepted'])
        self.assertTrue(all(not r['accepted'] and r['semantic_status']=='not_evaluated' for r in result['rows']))
        return result

    def test_all_paths_accounted(self):
        args = fixture(); result = self.run_case(args)
        self.assertEqual([r['schema_path'] for r in result['schema_coverage']], schema_paths(args[1]))
        self.assertEqual(result['counts']['schema_paths_without_slots'], 1)

    def test_literal_coverage_not_acceptance(self):
        result = self.run_case(fixture())
        self.assertEqual(result['counts']['price_basis_cited_whole_literal'], 1)

    def test_empty_allergens_not_safety(self):
        result = self.run_case(fixture())
        row = next(r for r in result['rows'] if r['schema_path']=='items[].allergens')
        self.assertEqual(row['occupancy'], 'empty_source_presence_unknown')
        self.assertEqual(row['source_presence'], 'not_evaluated')

    def test_missing_field_not_absent_source(self):
        args=fixture(); del args[0]['response']['items'][0]['name']
        row=next(r for r in self.run_case(args)['rows'] if r['schema_path']=='items[].name')
        self.assertEqual(row['occupancy'],'missing')

    def test_null_is_separate(self):
        args=fixture();args[0]['response']['items'][0]['name']['value']=None
        result=self.run_case(args)
        self.assertEqual(result['counts']['occupancy']['null_source_presence_unknown'],1)

    def test_invented_default_is_unmatched_not_automatically_wrong(self):
        args=fixture();args[0]['response']['items'][0]['prices'][0]['basis']['value']='portion'
        result=self.run_case(args)
        self.assertEqual(result['counts']['price_basis_literal_absent'],1)

    def test_bilingual_join_is_also_unmatched_not_automatically_wrong(self):
        args=fixture();args[0]['response']['items'][0]['prices'][0]['basis']['value']='per bowl / par bol'
        self.assertEqual(self.run_case(args)['counts']['price_basis_literal_absent'],1)

    def test_annotation_only_is_not_original_source(self):
        args=fixture();args[3]=[[0,11]]
        result=self.run_case(args)
        self.assertEqual(result['counts']['price_basis_cited_whole_literal'],0)
        self.assertEqual(result['counts']['price_basis_literal_absent'],1)

    def test_uncited_literal(self):
        args=fixture();args[0]['metadata']['citations'][0]['stop']=11
        result=self.run_case(args)
        self.assertEqual(result['counts']['price_basis_literal_absent'],0)
        self.assertEqual(result['counts']['price_basis_cited_whole_literal'],0)

    def test_missing_array_keeps_schema_descendants(self):
        args=fixture();del args[0]['response']['items']
        result=self.run_case(args)
        self.assertEqual(result['counts']['concrete_slots'],1)
        self.assertEqual(result['counts']['schema_paths_without_slots'],len(schema_paths(args[1]))-1)

    def test_type_mismatch(self):
        args=fixture();args[0]['response']['items']='not an array'
        self.assertEqual(self.run_case(args)['counts']['occupancy'],{'type_mismatch':1})

    def test_boolean_is_not_numeric(self):
        self.assertEqual(occupancy(True,'number'),'type_mismatch')
        self.assertEqual(occupancy(True,'integer'),'type_mismatch')

    def test_infinite_number_rejected(self):
        self.assertEqual(occupancy(float('inf'),'number'),'type_mismatch')

    def test_unexpected_fields_recorded(self):
        args=fixture();args[0]['response']['extra']=1;args[0]['response']['items'][0]['extra']=2
        self.assertEqual(self.run_case(args)['unexpected_paths'],[['extra'],['items',0,'extra']])

    def test_array_wrapper_does_not_lend_citations(self):
        args=fixture();args[0]['response']['items'][0]['allergens']={'value':['soup'],'citation_ids':[0]}
        row=next(r for r in self.run_case(args)['rows'] if r['schema_path']=='items[].allergens[]')
        self.assertFalse(row['literal_citation']['valid'])

    def test_source_hash_guard(self):
        args=fixture();args[-1]='0'*64
        with self.assertRaises(ValueError):audit(*args)

    def test_object_wrapper_preserves_leaf_citations(self):
        args=fixture();item=args[0]['response']['items'][0]
        args[0]['response']['items'][0]={'value':item,'citation_ids':[99]}
        result=self.run_case(args)
        self.assertNotIn('missing',result['counts']['occupancy'])
        self.assertEqual(result['counts']['price_basis_cited_whole_literal'],1)

    def test_citation_gap_remains_uncovered(self):
        args=fixture();args[0]['metadata']['citations']=[{'id':0,'start':0,'stop':15},
            {'id':1,'start':16,'stop':len(args[2])}]
        args[0]['response']['items'][0]['prices'][0]['basis']['citation_ids']=[0,1]
        self.assertEqual(self.run_case(args)['counts']['price_basis_cited_whole_literal'],0)

    def test_adjacent_citations_cover_literal(self):
        args=fixture();args[0]['metadata']['citations']=[{'id':0,'start':0,'stop':15},
            {'id':1,'start':15,'stop':len(args[2])}]
        args[0]['response']['items'][0]['prices'][0]['basis']['citation_ids']=[0,1]
        self.assertEqual(self.run_case(args)['counts']['price_basis_cited_whole_literal'],1)

    def test_precision_guard(self):
        args=fixture();args[0]['metadata']['mode']='fast'
        with self.assertRaises(ValueError):audit(*args)

    def test_failed_response_guard(self):
        args=fixture();args[0]['error_message']='failure'
        with self.assertRaises(ValueError):audit(*args)

    def test_scopes_guard(self):
        for scopes in ([], [[-1,3]], [[0,99]], [[True,3]], [[3,3]]):
            args=fixture();args[3]=scopes
            with self.assertRaises(ValueError):audit(*args)

    def test_unsupported_schema_fails_closed(self):
        args=fixture();args[1]['other']={'type':'unknown'}
        with self.assertRaises(ValueError):audit(*args)


if __name__=='__main__':unittest.main()
