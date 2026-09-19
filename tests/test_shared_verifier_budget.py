"""Fabricated fixtures only; no network, credentials or retained document reads."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from test_bbox_literal_evidence import fixture
from bbox_literal_evidence import audit
from bbox_page_provenance import bindings, digest
from shared_verifier_budget import (CRITERIA, LAYOUTS, THRESHOLDS, encode, expand,
    measure, packet, packets, prepare, question_id, resolve)


class SharedVerifierBudgetTests(unittest.TestCase):
    def setUp(self): self.args = fixture()
    def prepared(self):
        self.args[-1]['bindings'] = bindings(*self.args[:3])
        index = audit(*self.args)
        return prepare(*self.args[:3], 'Preserve exact synthetic facts.', index, digest(index))
    def records(self): return self.prepared()['records']

    def test_all_populated_strings(self):
        self.assertEqual(self.prepared()['inventory']['selected_strings'], 6)
    def test_all_inventory_retained(self):
        p = self.prepared(); inv = p['inventory']
        self.assertEqual(inv['not_questioned_slots']+len(p['records']), inv['concrete_slots'])
        self.assertGreater(inv['not_questioned_slots'], 0)
        self.assertFalse(inv['complete_source_inventory_verified'])
    def test_null_and_empty_not_accepted_absence(self):
        inv = self.prepared()['inventory']
        self.assertIn('null_source_presence_unknown', inv['occupancy'])
        self.assertIn('empty_source_presence_unknown', inv['occupancy'])
        self.assertFalse(inv['quality_accepted'])
    def test_missing_slots_retained(self):
        del self.args[0]['response']['items'][0]['details']
        self.assertGreater(self.prepared()['inventory']['occupancy']['missing'], 0)
    def test_no_literal_pruning(self):
        self.args[0]['response']['items'][0]['name']['value'] = 'Unsupported name'
        self.assertEqual(len(self.records()), 6)
    def test_unknown_citation_kept(self):
        self.args[0]['response']['items'][0]['name']['citation_ids'] = [999]
        r = next(r for r in self.records() if r['claim']['path'] == ['items',0,'name'])
        self.assertIn('unknown_citation_id', r['claim']['citation_problems'])
    def test_scalar_wrapper_unknown_kept(self):
        self.args[0]['response']['items'][0]['name'] = 'Cabin Amber'
        r = next(r for r in self.records() if r['claim']['path'] == ['items',0,'name'])
        self.assertEqual(r['claim']['field'], 'Cabin Amber')
        self.assertEqual(r['claim']['citation_problems'], ['unmapped_scalar_wrapper'])
    def test_no_literal_status_hint_in_claim(self):
        self.assertTrue(all('literal_status' not in r['claim'] for r in self.records()))
    def test_full_owner_retained(self):
        r = next(r for r in self.records() if r['claim']['path'] == ['items',0,'prices',0,'basis'])
        self.assertEqual(r['owner'], {'path':['items',0], 'record':self.args[0]['response']['items'][0]})
    def test_root_owner(self):
        self.assertEqual(self.records()[0]['owner']['path'], ['property_name'])
    def test_language_owner_keeps_all_languages(self):
        self.args[2]['languages'] = {'type':'array','items':{'type':'string'}}
        self.args[0]['response']['languages'] = [{'value':'fr','citation_ids':[7]}, {'value':'en','citation_ids':[7]}]
        r = self.records()[-1]
        self.assertEqual(r['owner']['path'], ['languages'])
        self.assertEqual(len(r['owner']['record']), 2)
    def test_all_parser_pages_and_elements(self):
        self.assertEqual(self.records()[0]['context']['parser_document'], self.args[1]['document'])
    def test_generated_description_preserved_not_relabelled(self):
        ctx = self.records()[0]['context']
        self.assertEqual(ctx['parser_document']['elements'][2]['description'], 'A shower in the room.')
        q = next(iter(packet(self.records(), True)['questions'].values()))
        self.assertIn('not verified transcription', q['instructions']['limits'])
    def test_schema_and_instructions_kept(self):
        ctx = self.records()[0]['context']
        self.assertEqual(ctx['schema'], self.args[2])
        self.assertEqual(ctx['extraction_instructions'], 'Preserve exact synthetic facts.')
    def test_input_unchanged(self):
        before = deepcopy(self.args)
        p = self.prepared()
        for layout in LAYOUTS: measure(p['records'], layout)
        self.assertEqual(self.args, before)
    def test_output_not_aliased_to_raw(self):
        r = self.records()[1]; r['owner']['record']['name']['value'] = 'mutated'
        self.assertEqual(self.args[0]['response']['items'][0]['name']['value'], 'Cabin Amber')
    def test_serialized_roundtrip_all_layouts(self):
        records = self.records()
        for layout in LAYOUTS:
            expanded = [r for _, p in packets(records, layout) for r in expand(json.loads(encode(p)))]
            self.assertEqual(expanded, records)
    def test_same_batch_claims_repeated_shared(self):
        records = self.records()
        self.assertEqual(expand(packet(records, False)), expand(packet(records, True)))
    def test_owner_dedup_by_path_not_label(self):
        self.args[0]['response']['items'][1]['name']['value'] = 'Cabin Amber'
        p = packet(self.records(), True)
        self.assertEqual(len(p['state']['owners']), 3)
        self.assertNotEqual(p['state']['owners'][1]['path'], p['state']['owners'][2]['path'])
    def test_reject_conflicting_owner(self):
        records = deepcopy(self.records())
        records[2]['owner'] = deepcopy(records[1]['owner'])
        records[2]['owner']['record']['name']['value'] = 'conflict'
        with self.assertRaises(ValueError): packet(records, True)
    def test_reject_different_context(self):
        records = self.records(); records[-1] = deepcopy(records[-1])
        records[-1]['context']['physical_pages'] = 4
        with self.assertRaises(ValueError): packet(records, True)
    def test_reject_duplicate_question(self):
        records = self.records()
        with self.assertRaises(ValueError): packet([records[0],records[0]], False)
    def test_question_ids_stable(self):
        records = self.records()
        self.assertEqual([question_id(r) for r in records], [question_id(r) for r in reversed(list(reversed(records)))])
        self.assertEqual(set(packet(records, True)['questions']), set(packet(records, False)['questions']))
    def test_questions_have_explicit_bindings(self):
        p = packet(self.records(), True)
        for q in p['questions'].values():
            self.assertIn('`claims[', q['instructions']['claim'])
            self.assertIn('`owners[', q['instructions']['owner'])
            self.assertEqual(q['instructions']['context'], '`context`')
            self.assertEqual(q['criteria'], CRITERIA)
    def test_no_truth_threshold(self):
        self.assertEqual(set(CRITERIA), {'supports','contradicts','not_addressed','insufficient_evidence'})
        p = packet(self.records(), True)
        self.assertNotIn('threshold', json.dumps(p['questions']))
    def test_tampered_question_rejected(self):
        p = packet(self.records(), True)
        next(iter(p['questions'].values()))['instructions']['owner'] = '`owners[999]`'
        with self.assertRaises(ValueError): expand(p)
    def test_bad_owner_reference_rejected(self):
        for bad in (-1, 999, True):
            p = packet(self.records(), True); p['state']['claims'][0]['owner_index'] = bad
            with self.assertRaises(ValueError): expand(p)
    def test_extra_owner_rejected(self):
        p = packet(self.records(), True); p['state']['owners'].append(deepcopy(p['state']['owners'][0]))
        with self.assertRaises(ValueError): expand(p)
    def test_unknown_model_rejected(self):
        p = packet(self.records(), True); p['model'] = 'different'
        with self.assertRaises(ValueError): expand(p)
    def test_partitions_add_exactly(self):
        m = measure(self.records(), 'shared24')
        self.assertEqual(m['request_bytes'], m['state_bytes']+m['questions_bytes']+m['envelope_bytes'])
        self.assertEqual(m['request_bytes'], sum(p['request_bytes'] for p in m['manifest']))
    def test_utf8_not_character_budget(self):
        self.assertGreater(len(encode({'x':'甲é'})), len(encode({'x':'甲é'}).decode()))
    def test_planning_threshold_no_drop(self):
        self.args[1]['document']['elements'][0]['content'] += 'x'*(THRESHOLDS[-1]+1)
        m = measure(self.records(), 'shared24')
        self.assertEqual(m['above_planning_bytes'], {str(n):1 for n in THRESHOLDS})
        self.assertEqual(m['questions'], 6)
    def test_size_improves_on_repeated_context_fixture(self):
        records = self.records()
        self.assertLess(measure(records,'shared24')['request_bytes'], measure(records,'repeated24')['request_bytes'])
    def test_batch_limits_and_no_loss(self):
        records = self.records(); many = []
        for i in range(29):
            r = deepcopy(records[0]); r['claim']['path'] = ['synthetic',i]; many.append(r)
        for layout, expected in [('single',29),('repeated24',2),('shared24',2),('shared8',4)]:
            m = measure(many,layout); self.assertEqual((m['requests'],m['questions']), (expected,29))
    def test_metrics_not_invented(self):
        m = measure(self.records(),'shared24')
        self.assertIsNone(m['token_usage']); self.assertIsNone(m['inference_latency_seconds'])
        self.assertIsNone(m['billed_cost']); self.assertFalse(m['quality_accepted']); self.assertEqual(m['requests_sent'],0)
    def test_retention_matches_hash(self):
        saved = []; m = measure(self.records(),'shared24',lambda meta,raw:saved.append((meta,raw)))
        self.assertEqual(saved[0][0],m['manifest'][0]); self.assertEqual(len(saved[0][1]),m['request_bytes'])
    def test_empty_layout(self):
        m = measure([],'single'); self.assertEqual((m['requests'],m['questions'],m['request_bytes']), (0,0,0))
    def test_unknown_layout(self):
        with self.assertRaises(ValueError): measure(self.records(),'unknown')
    def test_stale_index(self):
        index = audit(*self.args)
        with self.assertRaises(ValueError): prepare(*self.args[:3],'test',index,'a'*64)
    def test_stale_raw_binding(self):
        index = audit(*self.args); self.args[0]['response']['property_name']['value'] = 'other'
        with self.assertRaises(ValueError): prepare(*self.args[:3],'test',index,digest(index))
    def test_index_field_mismatch(self):
        index = audit(*self.args); index['rows'][0]['field']['value'] = 'changed'
        with self.assertRaises(ValueError): prepare(*self.args[:3],'test',index,digest(index))
    def test_failed_response_abstains(self):
        raw, parsed, schema, contract = self.args; raw['response'] = None
        contract['bindings'] = bindings(raw,parsed,schema)
        index = {'bindings':contract['bindings'],'contract':contract,'document_abstention':'saved failure'}
        p = prepare(raw,parsed,schema,'test',index,digest(index))
        self.assertEqual(p['records'],[]); self.assertFalse(p['inventory']['quality_accepted'])
    def test_invalid_path(self):
        for path in ([], ['items',True], ['items',-1], ['unknown']):
            with self.assertRaises(ValueError): resolve(self.args[0]['response'],path)
    def test_no_transport_imports(self):
        import shared_verifier_budget
        tree = ast.parse(Path(shared_verifier_budget.__file__).read_text())
        imports = {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        imports |= {a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        self.assertEqual(imports, {'collections','copy','hashlib','json','bbox_page_provenance','quality_gates','schema_field_audit'})


if __name__ == '__main__': unittest.main()
