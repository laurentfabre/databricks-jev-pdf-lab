"""Exact execution of supplied parent/preparation/marker selections. No I/O or AI.

This is a narrow development control, not semantic discovery. Existing service
citations are rebased, never widened or invented. Origin maps and supplied review
bind evidence; they cannot establish its truth. Real outputs/audits are private.
"""
from copy import deepcopy
import json

from cited_field_composition import citations, digest, need, text_hash, validate
from citation_span_review import literal_support
from quality_gates import unwrap


def bindings(base, text, donors, schema, origins):
    return {'base': digest(base), 'base_text': text_hash(text), 'schema': digest(schema),
            'donors': {key: {'raw': digest(d['raw']), 'text': text_hash(d['text'])}
                       for key, d in sorted(donors.items())}, 'origins': digest(origins)}


def compose(base, text, donors, schema, origins, plan):
    expected = bindings(base, text, donors, schema, origins)
    need(plan.get('bindings') == expected, 'Stale input/schema/origin binding')
    review = plan.get('review', {})
    evidence_hash = review.get('evidence_sha256')
    need(review.get('kind') == 'assistant_posthoc_source_review'
         and review.get('independent') is False and isinstance(evidence_hash, str)
         and len(evidence_hash) == 64 and all(c in '0123456789abcdef' for c in evidence_hash),
         'Explicit non-independent review required')
    need(isinstance(donors, dict) and donors and set(origins.get('donors', {})) == set(donors),
         'Missing donor origins')
    root_spec = {'type': 'object', 'properties': schema}
    base_ids = citations(base, text)
    validate(base['response'], root_spec, base_ids)
    donor_ids = {}
    for key, donor in donors.items():
        need(isinstance(key, str) and key.isidentifier(), 'Invalid donor name')
        donor_ids[key] = citations(donor['raw'], donor['text'])
        validate(donor['raw']['response'], root_spec, donor_ids[key])
        cursor = 0
        for segment in origins['donors'][key]:
            a, b = segment.get('start'), segment.get('stop')
            need(type(a) is int and type(b) is int and a == cursor
                 and a < b <= len(donor['text']) and isinstance(segment.get('origin'), str),
                 'Incomplete donor origin accounting')
            cursor = b
        need(cursor == len(donor['text']), 'Incomplete donor origin suffix')
    scopes = {}
    for scope in origins.get('base_scopes', []):
        ident, a, b, page = (scope.get(k) for k in ('element_id', 'start', 'stop', 'page'))
        need(type(ident) is int and ident not in scopes and type(a) is int and type(b) is int
             and 0 <= a < b <= len(text) and type(page) is int and page > 0, 'Invalid base scope')
        scopes[ident] = scope
    need(scopes, 'Missing base source scopes')
    owners, relations = plan.get('owners'), plan.get('relations')
    need(isinstance(owners, list) and owners and isinstance(relations, list) and relations,
         'Explicit owners and relations required')
    owner_indices, relation_keys = set(), set()
    for relation in relations:
        key = relation.get('donor')
        item_index, marker_index = relation.get('item_index'), relation.get('marker_index')
        need(key in donors and type(item_index) is int and type(marker_index) is int,
             'Invalid donor selection')
        identity = (key, item_index, marker_index)
        need(identity not in relation_keys, 'Duplicate relation selection')
        relation_keys.add(identity)
    need({r['donor'] for r in relations} == set(donors), 'Unused donor input')
    pending, used = [], {key: set() for key in donors}

    def supported(raw, source, ids, start, stop, message):
        need(type(start) is int and type(stop) is int and 0 <= start < stop <= len(source), message)
        need(literal_support({'value': source[start:stop], 'citation_ids': ids},
                             raw['metadata'], source, source[start:stop], [[start, stop]])['supported'], message)

    for owner in owners:
        index, page = owner.get('item_index'), owner.get('physical_page')
        need(type(index) is int and 0 <= index < len(base['response']['items'])
             and index not in owner_indices and type(page) is int and page > 0, 'Invalid/duplicate owner')
        owner_indices.add(index)
        parent = base['response']['items'][index]
        need(digest(parent['name']) == owner.get('name_sha256')
             and digest(parent['dietary_markers']) == owner.get('before_sha256'), 'Owner binding changed')
        need(unwrap(parent['source_pages']) == [page], 'Owner physical page mismatch')
        parent_ids = sorted(set(parent['name']['citation_ids'] + parent['details']['citation_ids']))
        entries = []
        for relation in relations:
            need(isinstance(relation.get('reason'), str) and relation['reason'], 'Missing review reason')
            parts, source_proofs, source_ids = [], [], set()
            for role in ('heading', 'preparation'):
                selection = relation[role]
                scope = scopes.get(selection.get('element_id'))
                a, b = selection.get('start'), selection.get('stop')
                need(scope is not None and scope['page'] == page and type(a) is int and type(b) is int
                     and scope['start'] <= a < b <= scope['stop'], 'Source selection crosses scope/page')
                need(text_hash(text[a:b]) == selection.get('literal_sha256'), 'Source literal changed')
                ids = [i for i in parent_ids if base_ids[i]['start'] < b and a < base_ids[i]['stop']]
                supported(base, text, ids, a, b, 'Uncited parent source component')
                parts.append(text[a:b]); source_ids.update(ids)
                source_proofs.append({'role': role, 'span': [a,b], 'citation_ids': ids,
                                      'literal_sha256': text_hash(text[a:b]), 'element_id': scope['element_id']})
            key = relation['donor']; donor = donors[key]
            di, mi = relation['item_index'], relation['marker_index']
            need(0 <= di < len(donor['raw']['response']['items']), 'Invalid donor item index')
            item = donor['raw']['response']['items'][di]
            need(0 <= mi < len(item['dietary_markers']), 'Invalid marker index')
            marker = item['dietary_markers'][mi]
            need(digest(marker) == relation.get('marker_sha256'), 'Marker binding changed')
            need(unwrap(item['source_pages']) == [page] and item['prices'] == [],
                 'Expected unpriced preparation on the owner page')
            need(isinstance(marker['value'], str) and marker['value'], 'Nonempty marker required')
            # Marker wording needs literal support in its own cited evidence.
            need(literal_support(marker, donor['raw']['metadata'], donor['text'],
                                 marker['value'])['supported'], 'Uncited marker text')
            ids = sorted(set(item['name']['citation_ids'] + item['details']['citation_ids']
                             + marker['citation_ids']))
            evidence = relation['evidence']; si = evidence.get('segment_index')
            segments = origins['donors'][key]
            need(type(si) is int and 0 <= si < len(segments), 'Invalid evidence segment')
            segment = segments[si]
            need(digest(segment) == evidence.get('segment_sha256'), 'Evidence segment changed')
            need(segment.get('source_group') == evidence.get('source_group')
                 and isinstance(segment.get('source_group'), str)
                 and segment.get('physical_page') == page, 'Evidence group/page mismatch')
            a, b = segment['start'], segment['stop']
            supported(donor['raw'], donor['text'], ids, a, b, 'Incomplete cited preparation observation')
            observation = json.loads(donor['text'][a:b])
            if segment['origin'] == 'provisional_image_observation':
                need(observation.get('source_group') == segment['source_group']
                     and observation.get('scope') == 'preparation_row_only', 'Wrong provisional scope')
                fragments = observation.get('source_fragments', [])
            else:
                need(segment['origin'] == 'assistant_image_review', 'Unsupported observation origin')
                observation = observation['reviewed_preparation_observation']
                need(observation.get('scope') ==
                     'only_when_this_preparation_is_selected_not_unconditional_parent_property',
                     'Wrong conditional review scope')
                fragments = observation.get('preparation_fragments', [])
            symbol = observation.get('symbols', {}).get(evidence.get('symbol_key'))
            need(observation.get('physical_page') == page and parts[1] in fragments
                 and type(symbol) is int and symbol == 1, 'Observation lacks selected preparation/symbol')
            value = ' / '.join(parts + [marker['value']])
            need(value not in unwrap(parent['dietary_markers'])
                 and value not in [e['value'] for e in entries], 'Duplicate conditional entry')
            used[key].update(ids)
            entries.append({'value': value, 'base_ids': sorted(source_ids), 'donor_ids': ids,
                'donor': key, 'donor_item': di, 'marker_index': mi,
                'source_components': source_proofs, 'evidence_segment': deepcopy(segment),
                'symbol_key': evidence['symbol_key'], 'reason': relation['reason']})
        pending.append({'item_index': index, 'entries': entries})
    result, composite = deepcopy(base), text
    copied, blocks, mappings = [], [{'input': 'base', 'start': 0, 'stop': len(text),
                                    'sha256': text_hash(text)}], {}
    next_id = max(base_ids, default=-1) + 1
    for key in sorted(donors):
        separator = '\n\n[DERIVED RETAINED DONOR BLOCK; NOT A NEW MODEL INPUT]\n'
        offset = len(composite) + len(separator)
        composite += separator + donors[key]['text']
        blocks.append({'input': key, 'start': offset, 'stop': len(composite),
                       'sha256': text_hash(donors[key]['text'])})
        mappings[key] = {}
        for old_id in sorted(used[key]):
            old = donor_ids[key][old_id]; new = deepcopy(old)
            new.update(id=next_id, start=offset+old['start'], stop=offset+old['stop'])
            need(composite[new['start']:new['stop']] == donors[key]['text'][old['start']:old['stop']],
                 'Rebased citation changed')
            result['metadata']['citations'].append(new)
            mappings[key][old_id] = next_id; next_id += 1
            copied.append({'input': key, 'original': deepcopy(old), 'derived': deepcopy(new)})
    changes = []
    for operation in pending:
        index = operation['item_index']; old = base['response']['items'][index]['dietary_markers']
        new = deepcopy(old)
        for entry in operation['entries']:
            ids = entry['base_ids'] + [mappings[entry['donor']][i] for i in entry['donor_ids']]
            new.append({'value': entry['value'], 'citation_ids': sorted(set(ids))})
        result['response']['items'][index]['dietary_markers'] = new
        changes.append({'item_index': index, 'before': deepcopy(old), 'after': deepcopy(new),
                        'entries': operation['entries']})
    result['derivation'] = {'kind': 'reviewed_conditional_donor_composition', 'service_response': False,
        'quality_accepted': False, 'plan_sha256': digest(plan), 'parent_response_sha256': digest(base),
        'parent_derivation_present': 'derivation' in base, 'parent_derivation': deepcopy(base.get('derivation')),
        'semantic_selection': 'supplied_posthoc_assistant_review_not_automated',
        'inherited_metadata_is_not_new_service_confidence': True}
    validate(result['response'], root_spec, citations(result, composite))
    audit = {'bindings': expected, 'plan_sha256': digest(plan), 'review': deepcopy(review),
        'origins_in_original_coordinates': deepcopy(origins), 'input_blocks': blocks,
        'changes': changes, 'copied_citations': copied, 'before_metadata': deepcopy(base['metadata']),
        'before_derivation_present': 'derivation' in base, 'before_derivation': deepcopy(base.get('derivation')),
        'derived_sha256': digest(result), 'composite_text_sha256': text_hash(composite),
        'new_ai_calls': 0, 'new_service_citations_created': 0, 'quality_accepted': False,
        'semantic_selection_automated': False, 'literal_checks_do_not_prove_semantic_support': True}
    need(restore(result, audit) == base, 'Inverse mismatch')
    need(bindings(base, text, donors, schema, origins) == expected, 'Inputs mutated')
    return result, composite, audit


def restore(result, audit):
    need(digest(result) == audit['derived_sha256'], 'Derived output changed')
    restored = deepcopy(result)
    for change in audit['changes']:
        index = change['item_index']
        need(restored['response']['items'][index]['dietary_markers'] == change['after'], 'Inverse changed field')
        restored['response']['items'][index]['dietary_markers'] = deepcopy(change['before'])
    restored['metadata'] = deepcopy(audit['before_metadata'])
    if audit['before_derivation_present']:
        restored['derivation'] = deepcopy(audit['before_derivation'])
    else:
        restored.pop('derivation', None)
    need(digest(restored) == audit['bindings']['base'], 'Inverse base mismatch')
    return restored
