"""Synthetic-only bridge tests; no source documents, network or inference."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cited_field_composition import digest
from legend_bound_donor import bindings, build_view, restore_view


def fixture(count=1, symbol_key='special', meaning='Special', description='star icon',
            scope='only_when_this_preparation_is_selected_not_unconditional_parent_property'):
    string = {'type':'string'}
    pages = {'type':'array','items':{'type':'integer'}}
    schema = {'items':{'type':'array','items':{'type':'object','properties':{
        'name':string, 'details':string, 'prices':{'type':'array','items':{'type':'number'}},
        'source_pages':pages, 'dietary_markers':{'type':'array','items':string}}}},
        'dietary_allergen_legend':{'type':'array','items':{'type':'object','properties':{
            'marker':string,'meaning':string,'source_pages':pages}}}}
    prep = json.dumps({'reviewed_preparation_observation':{
        'physical_page':3,'preparation_fragments':['Maple 甲'],
        'parent_offering_fragments':[['Alpha'],['Bêta']], 'scope':scope,
        'symbols':{symbol_key:count}}}, ensure_ascii=False, separators=(',',':'))
    leg = json.dumps({'reviewed_legend_observation':{'physical_page':7,
        'marker_description':description,'meanings':['Exemple',meaning]}}, ensure_ascii=False, separators=(',',':'))
    text=prep+'\n'+leg
    a=prep.index(json.dumps(symbol_key)+':')
    b=a+len(json.dumps(symbol_key)+':'+json.dumps(count))
    scalar=lambda value,ids: {'value':value,'citation_ids':ids}
    raw={'error_message':None,'metadata':{'mode':'precision','version':'2.1','chunk_type':'span',
        'citations':[{'id':0,'start':0,'stop':len(prep)}, {'id':1,'start':a,'stop':b},
                     {'id':2,'start':len(prep)+1,'stop':len(text)}]},
        'response':{'items':[{'name':scalar('Maple 甲',[0]),'details':scalar('Maple 甲',[0]),
            'prices':[],'source_pages':[scalar(3,[0])], 'dietary_markers':[scalar(meaning,[1])]}],
            'dietary_allergen_legend':[{'marker':scalar(description,[2]),
                'meaning':scalar('Exemple / '+meaning,[2]),'source_pages':[scalar(7,[2])]}]}}
    origins=[{'start':0,'stop':len(prep),'origin':'assistant_image_review','physical_page':3,'source_group':'a'},
             {'start':len(prep),'stop':len(prep)+1,'origin':'assembly_separator'},
             {'start':len(prep)+1,'stop':len(text),'origin':'assistant_image_review','physical_page':7}]
    plan={'review':{'kind':'assistant_posthoc_source_review','independent':False,'evidence_sha256':'a'*64},
        'relations':[{'item_index':0,'marker_index':0,'legend_index':0,
            'symbol_key':symbol_key,'meaning':meaning,'marker_description':description,
            'preparation_segment_index':0,'legend_segment_index':2}]}
    args=[raw,text,schema,origins,plan]; rebind(args); return args


def rebind(args):
    raw,text,schema,origins,plan=args
    plan['bindings']=bindings(raw,text,schema,origins)
    for selection in plan['relations']:
        ii,mi,li=(selection[k] for k in ('item_index','marker_index','legend_index'))
        selection['marker_sha256']=digest(raw['response']['items'][ii]['dietary_markers'][mi])
        selection['legend_sha256']=digest(raw['response']['dietary_allergen_legend'][li])
        for role in ('preparation','legend'):
            selection[role+'_segment_sha256']=digest(origins[selection[role+'_segment_index']])


class LegendBridgeTests(unittest.TestCase):
    def setUp(self): self.args=fixture()
    def run_case(self): return build_view(*self.args)
    def reject(self):
        with self.assertRaises(ValueError): self.run_case()

    def test_bridge_only_adds_existing_references(self):
        view,audit=self.run_case()
        self.assertEqual(view['response']['items'][0]['dietary_markers'][0],
                         {'value':'Special','citation_ids':[1,2]})
        self.assertEqual(view['metadata'],self.args[0]['metadata'])
        self.assertEqual(audit['changes'][0]['added_existing_citation_ids'],[2])

    def test_inverse_and_immutability(self):
        before=deepcopy(self.args); view,audit=self.run_case()
        self.assertEqual(restore_view(view,audit),self.args[0]); self.assertEqual(before,self.args)

    def test_no_truth_confidence_or_service_claim(self):
        view,audit=self.run_case()
        self.assertFalse(view['derivation']['service_response']); self.assertFalse(audit['quality_accepted'])
        self.assertFalse(audit['semantic_mapping_automated']); self.assertEqual(audit['new_ai_calls'],0)
        self.assertEqual(audit['new_service_citations_created'],0)

    def test_false_supplied_semantics_remain_unaccepted(self):
        # Code cannot prove this deliberately dubious symbol/meaning association.
        self.args=fixture(meaning='Unrelated semantic label')
        _,audit=self.run_case(); self.assertFalse(audit['quality_accepted'])

    def test_unicode_offsets(self):
        view,audit=self.run_case(); a,b=audit['changes'][0]['symbol_span']
        self.assertEqual(self.args[1][a:b],'"special":1')
        self.assertEqual(restore_view(view,audit),self.args[0])

    def test_stale_raw(self): self.args[0]['extra']=True; self.reject()
    def test_stale_text(self): self.args[1]+=' '; self.reject()
    def test_stale_schema(self): self.args[2]['extra']={}; self.reject()
    def test_stale_origins(self): self.args[3][0]['extra']=True; self.reject()
    def test_stale_marker(self): self.args[-1]['relations'][0]['marker_sha256']='0'*64; self.reject()
    def test_stale_legend(self): self.args[-1]['relations'][0]['legend_sha256']='0'*64; self.reject()
    def test_stale_segment(self): self.args[-1]['relations'][0]['legend_segment_sha256']='0'*64; self.reject()
    def test_missing_review(self): self.args[-1]['review']={}; self.reject()
    def test_false_independence(self): self.args[-1]['review']['independent']=True; self.reject()
    def test_empty_selections(self): self.args[-1]['relations']=[]; self.reject()
    def test_duplicate_selection(self): self.args[-1]['relations']*=2; self.reject()
    def test_negative_index(self): self.args[-1]['relations'][0]['item_index']=-1; self.reject()
    def test_bool_index(self): self.args[-1]['relations'][0]['legend_index']=False; self.reject()
    def test_unknown_symbol(self): self.args[-1]['relations'][0]['symbol_key']='missing'; self.reject()
    def test_wrong_description(self): self.args[-1]['relations'][0]['marker_description']='moon icon'; self.reject()
    def test_wrong_meaning(self): self.args[-1]['relations'][0]['meaning']='Other'; self.reject()
    def test_repeated_glyph_not_a_tier(self): self.args=fixture(count=2); self.reject()
    def test_false_count_not_integer(self): self.args=fixture(count=True); self.reject()
    def test_float_count_not_integer(self): self.args=fixture(count=1.0); self.reject()
    def test_wrong_scope(self): self.args=fixture(scope='unconditional'); self.reject()

    def test_original_marker_must_cite_symbol(self):
        self.args[0]['response']['items'][0]['dietary_markers'][0]['citation_ids']=[2]
        rebind(self.args); self.reject()

    def test_incomplete_preparation_observation(self):
        self.args[0]['metadata']['citations'][0]['start']=1; rebind(self.args); self.reject()

    def test_incomplete_legend_observation(self):
        self.args[0]['metadata']['citations'][2]['start']+=1; rebind(self.args); self.reject()

    def test_origin_gap(self):
        self.args[3][1]['start']+=1; rebind(self.args); self.reject()

    def test_provisional_origin_not_enough(self):
        self.args[3][0]['origin']='provisional_image_observation'; rebind(self.args); self.reject()

    def test_wrong_legend_page(self):
        self.args[0]['response']['dietary_allergen_legend'][0]['source_pages'][0]['value']=3
        rebind(self.args); self.reject()

    def test_priced_preparation(self):
        self.args[0]['response']['items'][0]['prices']=[{'value':12,'citation_ids':[0]}]
        rebind(self.args); self.reject()

    def test_wrong_mode(self):
        self.args[0]['metadata']['mode']='standard'; rebind(self.args); self.reject()

    def test_already_linked_rejected(self):
        self.args[0]['response']['items'][0]['dietary_markers'][0]['citation_ids']=[1,2]
        rebind(self.args); self.reject()

    def test_derived_view_replay_rejected(self):
        self.args[0],_=self.run_case(); rebind(self.args); self.reject()

    def test_tampered_inverse(self):
        view,audit=self.run_case(); view['response']['items'][0]['name']['value']='changed'
        with self.assertRaises(ValueError): restore_view(view,audit)

    def test_unchanged_composer_accepts_explicit_bridge_only(self):
        from conditional_donor_composition import bindings as cb, compose, restore
        from cited_field_composition import text_hash
        view,bridge=self.run_case()
        raw,text0,schema,origins,_=self.args
        text='Alpha / Bêta / Only when selected / Maple 甲'
        base=deepcopy(raw)
        base['metadata']['citations']=[{'id':0,'start':0,'stop':len(text)}]
        template=deepcopy(raw['response']['items'][0])
        template['dietary_markers']=[]
        base['response']['items']=[]
        for name,price in [('Alpha',12),('Bêta',24)]:
            item=deepcopy(template); item['name']={'value':name,'citation_ids':[0]}
            item['prices']=[{'value':price,'citation_ids':[0]}]; base['response']['items'].append(item)
        for value in base['response']['dietary_allergen_legend'][0].values():
            for field in value if isinstance(value,list) else [value]: field['citation_ids']=[0]
        donors={'a':{'raw':view,'text':text0}}
        origin_map={'base_scopes':[{'element_id':1,'page':3,'start':0,'stop':len(text)}], 'donors':{'a':origins}}
        selection=lambda word: {'element_id':1,'start':text.index(word),'stop':text.index(word)+len(word),
                                'literal_sha256':text_hash(word)}
        plan={'review':self.args[-1]['review'],'bindings':cb(base,text,donors,schema,origin_map),
            'owners':[{'item_index':i,'physical_page':3,'name_sha256':digest(item['name']),
                       'before_sha256':digest(item['dietary_markers'])} for i,item in enumerate(base['response']['items'])],
            'relations':[{'donor':'a','item_index':0,'marker_index':0,
                'marker_sha256':digest(view['response']['items'][0]['dietary_markers'][0]),
                'heading':selection('Only when selected'),'preparation':selection('Maple 甲'),
                'reason':'Supplied synthetic review', 'evidence':{'segment_index':0,
                    'segment_sha256':digest(origins[0]),'source_group':'a','symbol_key':'special'}}]}
        result,_,audit=compose(base,text,donors,schema,origin_map,plan)
        self.assertEqual(len(audit['changes']),2); self.assertEqual(restore(result,audit),base)
        self.assertEqual(restore_view(view,bridge),raw)
        self.assertFalse(audit['quality_accepted'])
        # The unchanged service donor still fails the old literal gate.
        donors['a']['raw']=raw; plan['bindings']=cb(base,text,donors,schema,origin_map)
        plan['relations'][0]['marker_sha256']=digest(raw['response']['items'][0]['dietary_markers'][0])
        with self.assertRaisesRegex(ValueError,'Uncited marker text'):
            compose(base,text,donors,schema,origin_map,plan)


if __name__=='__main__': unittest.main()
