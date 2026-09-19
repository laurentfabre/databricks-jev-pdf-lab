"""Fabricated responses/observations only; no document, network or model access."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from conditional_donor_composition import bindings, compose, restore
from cited_field_composition import digest, text_hash


def fixture(heading='Only when selected'):
    leaf = {'type': 'string'}
    schema = {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'name': leaf, 'details': leaf, 'prices': {'type': 'array', 'items': {'type': 'number'}},
        'source_pages': {'type': 'array', 'items': {'type': 'integer'}},
        'dietary_markers': {'type': 'array', 'items': leaf}}}}, 'policy': leaf}
    def scalar(value, ids=None): return {'value': value, 'citation_ids': [0] if ids is None else ids}
    def item(name, markers, price):
        return {'name': scalar(name), 'details': scalar('Retained context'),
                'prices': [scalar(price)] if price is not None else [],
                'source_pages': [scalar(3)], 'dietary_markers': markers}
    def raw(items, length):
        return {'error_message': None, 'response': {'items': items, 'policy': scalar('Policy')},
                'metadata': {'mode': 'precision', 'version': '2.1', 'chunk_type': 'span',
                    'confidence': 0.5, 'citations': [{'id': 0, 'start': 0, 'stop': length}]}}
    text = f'Alpha 12 / Bêta 24 / {heading} / Maple 甲 / Citrus 乙 / Policy'
    base = raw([item('Alpha', [scalar('old')], 12), item('Bêta', [], 24)], len(text))
    base['derivation'] = {'kind': 'prior_derived', 'quality_accepted': False}
    donors, segments = {}, {}
    for key, label, origin in [('a','Maple 甲','provisional_image_observation'),
                               ('b','Citrus 乙','assistant_image_review')]:
        observation = {'physical_page': 3, 'symbols': {'special': 1}}
        if origin == 'provisional_image_observation':
            observation.update(source_group=key, scope='preparation_row_only', source_fragments=[label])
        else:
            observation.update(scope='only_when_this_preparation_is_selected_not_unconditional_parent_property',
                               preparation_fragments=[label], parent_offering_fragments=[['Alpha'],['Bêta']])
            observation = {'reviewed_preparation_observation': observation}
        observed = json.dumps(observation, ensure_ascii=False)
        donor_text = observed + '\nSpecial Policy'
        dr = raw([item(label, [scalar('Special', [1])], None)], len(observed))
        dr['metadata']['citations'].append({'id': 1, 'start': len(observed)+1, 'stop': len(donor_text)})
        donors[key] = {'raw': dr, 'text': donor_text}
        segments[key] = [
            {'start': 0, 'stop': len(observed), 'origin': origin, 'physical_page': 3, 'source_group': key},
            {'start': len(observed), 'stop': len(donor_text), 'origin': 'assistant_image_review', 'physical_page': 7}]
    origins = {'base': {'partial': True}, 'base_scopes': [
        {'element_id': 1, 'page': 3, 'start': 0, 'stop': len(text)}], 'donors': segments}
    def select(literal):
        a = text.index(literal)
        return {'element_id': 1, 'start': a, 'stop': a+len(literal), 'literal_sha256': text_hash(literal)}
    plan = {'review': {'kind': 'assistant_posthoc_source_review', 'independent': False,
                      'evidence_sha256': 'a'*64}, 'owners': [], 'relations': []}
    for i in range(2):
        plan['owners'].append({'item_index': i, 'physical_page': 3,
            'name_sha256': digest(base['response']['items'][i]['name']),
            'before_sha256': digest(base['response']['items'][i]['dietary_markers'])})
    for key, label in [('a','Maple 甲'), ('b','Citrus 乙')]:
        plan['relations'].append({'donor': key, 'item_index': 0, 'marker_index': 0,
            'marker_sha256': digest(donors[key]['raw']['response']['items'][0]['dietary_markers'][0]),
            'heading': select(heading), 'preparation': select(label), 'reason': 'Supplied development review',
            'evidence': {'segment_index': 0, 'segment_sha256': digest(segments[key][0]),
                         'source_group': key, 'symbol_key': 'special'}})
    args = [base, text, donors, schema, origins, plan]
    rebind(args)
    return args


def rebind(args): args[-1]['bindings'] = bindings(*args[:-1])


class ConditionalCompositionTests(unittest.TestCase):
    def setUp(self): self.args = fixture()
    def run_case(self): return compose(*self.args)
    def reject(self):
        with self.assertRaises(ValueError): self.run_case()

    def test_four_explicit_conditional_additions(self):
        result, _, audit = self.run_case()
        for i, old in enumerate(self.args[0]['response']['items']):
            after = result['response']['items'][i]['dietary_markers']
            self.assertEqual(after[:len(old['dietary_markers'])], old['dietary_markers'])
            self.assertEqual([m['value'] for m in after[len(old['dietary_markers']):]],
                ['Only when selected / Maple 甲 / Special', 'Only when selected / Citrus 乙 / Special'])
        self.assertEqual(sum(len(c['entries']) for c in audit['changes']), 4)

    def test_unselected_fields_and_metadata_exact(self):
        result, _, audit = self.run_case()
        for c in audit['changes']:
            result['response']['items'][c['item_index']]['dietary_markers'] = c['before']
        self.assertEqual(result['response'], self.args[0]['response'])
        self.assertEqual({k:v for k,v in result['metadata'].items() if k != 'citations'},
                         {k:v for k,v in self.args[0]['metadata'].items() if k != 'citations'})

    def test_inputs_immutable(self):
        saved = deepcopy(self.args); self.run_case(); self.assertEqual(saved, self.args)

    def test_exact_inverse_and_parent_lineage(self):
        result, _, audit = self.run_case()
        self.assertEqual(restore(result,audit), self.args[0])
        self.assertEqual(result['derivation']['parent_derivation'], self.args[0]['derivation'])

    def test_inverse_without_prior_lineage(self):
        del self.args[0]['derivation']; rebind(self.args)
        result, _, audit = self.run_case(); self.assertEqual(restore(result,audit), self.args[0])

    def test_rebased_spans_exact_and_namespaces_unique(self):
        result, text, audit = self.run_case()
        for row in audit['copied_citations']:
            a,b = row['original'],row['derived']
            self.assertEqual(text[b['start']:b['stop']], self.args[2][row['input']]['text'][a['start']:a['stop']])
        ids = [r['id'] for r in result['metadata']['citations']]
        self.assertEqual(len(ids), len(set(ids)))
        for block in audit['input_blocks'][1:]:
            self.assertEqual(text[block['start']:block['stop']], self.args[2][block['input']]['text'])

    def test_donor_origins_preserved(self):
        _, _, audit = self.run_case()
        self.assertEqual(audit['origins_in_original_coordinates'], self.args[4])
        self.assertEqual({e['evidence_segment']['origin'] for e in audit['changes'][0]['entries']},
                         {'provisional_image_observation','assistant_image_review'})

    def test_no_confidence_truth_or_service_claim(self):
        result, _, audit = self.run_case()
        self.assertFalse(result['derivation']['service_response'])
        self.assertFalse(audit['quality_accepted']); self.assertFalse(audit['semantic_selection_automated'])
        self.assertEqual(audit['new_ai_calls'],0); self.assertEqual(audit['new_service_citations_created'],0)
        for c in audit['changes']:
            for row in c['after'][len(c['before']):]: self.assertEqual(set(row), {'value','citation_ids'})

    def test_code_does_not_prove_conditional_semantics(self):
        # Supplied false semantics can satisfy syntax: never promote code-only success.
        self.args = fixture('Never select this as an option')
        _, _, audit = self.run_case(); self.assertFalse(audit['quality_accepted'])

    def test_stale_base(self): self.args[0]['extra'] = True; self.reject()
    def test_stale_text(self): self.args[1] += ' '; self.reject()
    def test_stale_donor(self): self.args[2]['a']['text'] += ' '; self.reject()
    def test_stale_schema(self): self.args[3]['extra'] = {}; self.reject()
    def test_stale_origins(self): self.args[4]['extra'] = True; self.reject()
    def test_stale_owner(self): self.args[-1]['owners'][0]['name_sha256'] = '0'*64; self.reject()
    def test_stale_target(self): self.args[-1]['owners'][0]['before_sha256'] = '0'*64; self.reject()
    def test_stale_marker(self): self.args[-1]['relations'][0]['marker_sha256'] = '0'*64; self.reject()
    def test_stale_evidence(self): self.args[-1]['relations'][0]['evidence']['segment_sha256'] = '0'*64; self.reject()
    def test_missing_review(self): self.args[-1]['review'] = {}; self.reject()
    def test_false_independence(self): self.args[-1]['review']['independent'] = True; self.reject()
    def test_duplicate_owner(self): self.args[-1]['owners'] *= 2; self.reject()
    def test_duplicate_relation(self): self.args[-1]['relations'] *= 2; self.reject()
    def test_wrong_owner_page(self): self.args[-1]['owners'][0]['physical_page'] = 7; self.reject()
    def test_wrong_evidence_group(self): self.args[-1]['relations'][0]['evidence']['source_group'] = 'wrong'; self.reject()
    def test_wrong_symbol(self): self.args[-1]['relations'][0]['evidence']['symbol_key'] = 'absent'; self.reject()
    def test_wrong_source_hash(self): self.args[-1]['relations'][0]['preparation']['literal_sha256'] = '0'*64; self.reject()
    def test_cross_scope(self): self.args[-1]['relations'][0]['preparation']['stop'] = 999; self.reject()

    def test_uncited_parent_source(self):
        self.args[0]['metadata']['citations'][0]['stop'] = 5; rebind(self.args); self.reject()

    def test_incomplete_observation_citation(self):
        self.args[2]['a']['raw']['metadata']['citations'][0]['start'] = 1; rebind(self.args); self.reject()

    def test_uncited_marker(self):
        self.args[2]['a']['raw']['metadata']['citations'][1]['start'] += 2; rebind(self.args); self.reject()

    def test_wrong_preparation_observation(self):
        self.args[-1]['relations'][0]['preparation'] = deepcopy(self.args[-1]['relations'][1]['preparation'])
        self.reject()

    def test_priced_donor_rejected(self):
        self.args[2]['a']['raw']['response']['items'][0]['prices'] = [{'value':12,'citation_ids':[0]}]
        rebind(self.args); self.reject()

    def test_origin_gap_rejected(self):
        self.args[4]['donors']['a'][1]['start'] += 1; rebind(self.args); self.reject()

    def test_wrong_mode_rejected(self):
        self.args[2]['a']['raw']['metadata']['mode'] = 'standard'; rebind(self.args); self.reject()

    def test_unknown_citation_rejected(self):
        self.args[2]['a']['raw']['response']['items'][0]['name']['citation_ids'] = [123]
        rebind(self.args); self.reject()

    def test_replay_rejected(self):
        result, text, _ = self.run_case(); self.args[0] = result; self.args[1] = text; self.reject()

    def test_tampered_inverse_rejected(self):
        result, _, audit = self.run_case(); result['metadata']['confidence'] = 1
        with self.assertRaises(ValueError): restore(result,audit)


if __name__ == '__main__': unittest.main()
