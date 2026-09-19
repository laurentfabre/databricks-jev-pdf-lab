"""Fabricated span-cited objects only; no service or document access."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from cited_field_composition import bindings, compose, digest, restore


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.schema = {'name': {'type':'string'}, 'legend': {'type':'array', 'items': {
            'type':'object', 'properties': {'marker': {'type':'string'}, 'meaning': {'type':'string'}}}}}
        self.base_text, self.donor_text = '海🌿 BASE label', '苗🌶 X means option'
        def raw(name, marker, meaning):
            return {'error_message': None, 'response': {'name': {'value':name, 'citation_ids':[0]},
                'legend': [{'marker': {'value':marker,'citation_ids':[0]},
                            'meaning': {'value':meaning,'citation_ids':[1]}}]},
                'metadata': {'version':'2.1','mode':'precision','chunk_type':'span','citations':[
                    {'id':0,'start':0,'stop':3}, {'id':1,'start':4,'stop':8}]}}
        self.base, self.donor = raw('base','old','old meaning'), raw('donor','X','option')
        self.origins = {'base': {'note':'retained parser input'},
                        'donor': [{'start':0,'stop':len(self.donor_text),'origin':'assistant_image_review'}]}
        self.plan = {'review': {'kind':'supplied_field_review','independent':False,'evidence_sha256':'a'*64},
                     'fields':[{'field':'legend'}]}
        self.rebind()

    def rebind(self):
        self.plan['bindings'] = bindings(self.base, self.base_text, self.donor,
            self.donor_text, self.schema, self.origins)
        for field in self.plan['fields']:
            name = field['field']
            if name in self.base['response'] and name in self.donor['response']:
                field.update(base_sha256=digest(self.base['response'][name]),
                             donor_sha256=digest(self.donor['response'][name]))

    def run_composition(self):
        return compose(self.base,self.base_text,self.donor,self.donor_text,self.schema,self.origins,self.plan)

    def rejects(self):
        with self.assertRaises(ValueError): self.run_composition()

    def test_only_selected_values_change(self):
        result, _, _ = self.run_composition()
        self.assertEqual(result['response']['name'], self.base['response']['name'])
        self.assertEqual(result['response']['legend'][0]['meaning']['value'],'option')

    def test_original_inputs_not_mutated(self):
        before = deepcopy((self.base,self.donor,self.schema,self.origins,self.plan))
        self.run_composition()
        self.assertEqual((self.base,self.donor,self.schema,self.origins,self.plan),before)

    def test_explicitly_derived_not_service_or_accepted(self):
        result, _, audit = self.run_composition()
        self.assertIs(result['derivation']['service_response'],False)
        self.assertIs(audit['quality_accepted'],False)
        self.assertEqual(audit['new_service_citations_created'],0)

    def test_unicode_character_offsets_not_bytes(self):
        result, text, audit = self.run_composition()
        offset = audit['input_blocks'][1]['start']
        self.assertEqual(text[offset:], self.donor_text)
        for mapped in audit['copied_citations']:
            self.assertEqual(text[mapped['derived_start']:mapped['derived_stop']],
                             self.donor_text[mapped['original_start']:mapped['original_stop']])
        self.assertEqual(result['metadata']['citations'][:2],self.base['metadata']['citations'])

    def test_same_id_namespaces_do_not_collide(self):
        result, _, audit = self.run_composition()
        self.assertEqual([c['id'] for c in result['metadata']['citations']],[0,1,2,3])
        self.assertEqual(len(audit['copied_citations']),2)

    def test_origin_map_retains_annotation_status(self):
        _, _, audit = self.run_composition()
        self.assertEqual(audit['origins_in_original_input_coordinates'],self.origins)

    def test_inverse_exact(self):
        result, _, audit = self.run_composition()
        self.assertEqual(restore(result,audit), self.base)

    def test_inverse_rejects_modified_result(self):
        result, _, audit = self.run_composition()
        result['response']['name']['value'] = 'changed'
        with self.assertRaises(ValueError): restore(result,audit)

    def test_inverse_retains_prior_derivation(self):
        self.base['derivation']={'kind':'older_projection'}; self.rebind()
        result, _, audit = self.run_composition()
        self.assertEqual(restore(result,audit),self.base)

    def test_stale_text(self):
        self.donor_text += ' changed'; self.rejects()

    def test_stale_base(self):
        self.base['response']['name']['value']='changed'; self.rejects()

    def test_stale_donor(self):
        self.donor['response']['name']['value']='changed'; self.rejects()

    def test_stale_schema(self):
        self.schema['name']['description']='changed'; self.rejects()

    def test_stale_origin(self):
        self.origins['donor'][0]['origin']='original'; self.rejects()

    def test_stale_field(self):
        self.plan['fields'][0]['donor_sha256']='0'*64; self.rejects()

    def test_duplicate_selection(self):
        self.plan['fields']*=2; self.rejects()

    def test_unknown_selection(self):
        self.plan['fields'][0]['field']='metadata'; self.rejects()

    def test_empty_selection(self):
        self.plan['fields']=[]; self.rejects()

    def test_missing_review(self):
        self.plan['review']={}; self.rejects()

    def test_missing_origin(self):
        del self.origins['donor']; self.rebind(); self.rejects()

    def test_wrong_mode(self):
        self.donor['metadata']['mode']='fast'; self.rebind(); self.rejects()

    def test_wrong_version(self):
        self.donor['metadata']['version']='2.0'; self.rebind(); self.rejects()

    def test_bbox_metadata_rejected(self):
        self.donor['metadata']['chunk_type']='bbox'; self.rebind(); self.rejects()

    def test_service_error(self):
        self.donor['error_message']='failed'; self.rebind(); self.rejects()

    def test_duplicate_citation_id(self):
        self.donor['metadata']['citations'][1]['id']=0; self.rebind(); self.rejects()

    def test_boolean_citation_id(self):
        self.donor['metadata']['citations'][1]['id']=True; self.rebind(); self.rejects()

    def test_bad_bounds(self):
        self.donor['metadata']['citations'][1]['stop']=999; self.rebind(); self.rejects()

    def test_negative_bounds(self):
        self.donor['metadata']['citations'][1]['start']=-1; self.rebind(); self.rejects()

    def test_noninteger_bounds(self):
        self.donor['metadata']['citations'][1]['start']=1.5; self.rebind(); self.rejects()

    def test_unknown_reference(self):
        self.donor['response']['legend'][0]['meaning']['citation_ids']=[9]; self.rebind(); self.rejects()

    def test_empty_nonnull_citation(self):
        self.donor['response']['legend'][0]['meaning']['citation_ids']=[]; self.rebind(); self.rejects()

    def test_null_with_no_citations(self):
        self.donor['response']['legend'][0]['meaning']={'value':None,'citation_ids':[]}; self.rebind()
        result, _, _=self.run_composition()
        self.assertIsNone(result['response']['legend'][0]['meaning']['value'])

    def test_scalar_wrong_type(self):
        self.donor['response']['legend'][0]['meaning']['value']=8; self.rebind(); self.rejects()

    def test_unwrapped_scalar_rejected(self):
        self.donor['response']['legend'][0]['meaning']='value'; self.rebind(); self.rejects()

    def test_missing_schema_field(self):
        del self.donor['response']['name']; self.rebind(); self.rejects()

    def test_additional_response_field(self):
        self.donor['response']['extra']=[]; self.rebind(); self.rejects()

    def test_uncited_gap_preserved(self):
        _, text, audit=self.run_composition()
        offset=audit['input_blocks'][1]['start']
        self.assertEqual(text[offset+3:offset+4],self.donor_text[3:4])
        self.assertEqual([(r['original_start'],r['original_stop']) for r in audit['copied_citations']],[(0,3),(4,8)])

    def test_unused_donor_citations_not_imported(self):
        self.donor['metadata']['citations'].append({'id':99,'start':9,'stop':10}); self.rebind()
        result,_,audit=self.run_composition()
        self.assertEqual(len(audit['copied_citations']),2)
        self.assertEqual(len(result['metadata']['citations']),4)

    def test_multiple_fields_share_citation_mapping(self):
        self.plan['fields'].append({'field':'name'}); self.rebind()
        result,_,audit=self.run_composition()
        self.assertEqual(len(audit['copied_citations']),2)
        self.assertEqual(result['response']['name']['value'],'donor')


if __name__ == '__main__': unittest.main()
