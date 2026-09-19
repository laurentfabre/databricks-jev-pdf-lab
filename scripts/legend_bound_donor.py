"""Explicit reviewed symbol/legend bridge over retained evidence. No I/O or AI.

Only a labelled derived donor view receives extra references to existing service
spans. No values, spans, raw response or frozen composer are altered. Supplied
semantic mappings remain review judgments, never facts proven by these checks.
"""
from copy import deepcopy
import json
import re

from cited_field_composition import citations, digest, need, text_hash, validate
from citation_span_review import literal_support
from quality_gates import unwrap


def bindings(raw, text, schema, origins):
    return {'raw': digest(raw), 'text': text_hash(text), 'schema': digest(schema),
            'origins': digest(origins)}


def build_view(raw, text, schema, origins, plan):
    expected = bindings(raw, text, schema, origins)
    need(plan.get('bindings') == expected, 'Stale donor/schema/origin binding')
    review = plan.get('review', {})
    need(review.get('kind') == 'assistant_posthoc_source_review'
         and review.get('independent') is False
         and re.fullmatch('[0-9a-f]{64}', review.get('evidence_sha256', '')) is not None,
         'Explicit bound non-independent review required')
    need('derivation' not in raw, 'Expected unchanged service donor, not a derived view')
    spec = {'type': 'object', 'properties': schema}
    validate(raw['response'], spec, citations(raw, text))
    cursor = 0
    for segment in origins:
        a, b = segment.get('start'), segment.get('stop')
        need(type(a) is int and type(b) is int and a == cursor and a < b <= len(text)
             and isinstance(segment.get('origin'), str), 'Incomplete origin map')
        cursor = b
    need(cursor == len(text), 'Incomplete origin suffix')
    selected = plan.get('relations')
    need(isinstance(selected, list) and selected, 'Explicit bridge selections required')
    seen, changes = set(), []
    view = deepcopy(raw)

    def origin(selection, role):
        index = selection.get(role + '_segment_index')
        need(type(index) is int and 0 <= index < len(origins), 'Invalid ' + role + ' origin')
        segment = origins[index]
        need(digest(segment) == selection.get(role + '_segment_sha256'), 'Changed ' + role + ' origin')
        need(segment['origin'] == 'assistant_image_review'
             and type(segment.get('physical_page')) is int and segment['physical_page'] > 0,
             'Expected page-bound assistant image review')
        return segment

    def covered(ids, segment):
        a, b = segment['start'], segment['stop']
        need(literal_support({'citation_ids': ids}, raw['metadata'], text,
                             text[a:b], [[a,b]])['supported'], 'Incomplete cited observation')

    for selection in selected:
        ii, mi, li = (selection.get(k) for k in ('item_index','marker_index','legend_index'))
        need(all(type(i) is int and i >= 0 for i in (ii,mi,li)), 'Invalid field selection')
        need(ii < len(raw['response']['items'])
             and li < len(raw['response']['dietary_allergen_legend']), 'Selection outside response')
        item = raw['response']['items'][ii]
        need(mi < len(item['dietary_markers']) and (ii,mi) not in seen, 'Invalid or duplicate marker')
        seen.add((ii,mi))
        marker = item['dietary_markers'][mi]
        legend = raw['response']['dietary_allergen_legend'][li]
        need(digest(marker) == selection.get('marker_sha256')
             and digest(legend) == selection.get('legend_sha256'), 'Changed selected fields')
        prep, leg = origin(selection, 'preparation'), origin(selection, 'legend')
        need(item['prices'] == [] and unwrap(item['source_pages']) == [prep['physical_page']],
             'Expected unpriced preparation on observed page')
        need(unwrap(legend['source_pages']) == [leg['physical_page']], 'Legend page mismatch')
        ids = sorted(set(item['name']['citation_ids'] + item['details']['citation_ids']
                         + marker['citation_ids']))
        covered(ids, prep)
        observation = json.loads(text[prep['start']:prep['stop']]).get('reviewed_preparation_observation', {})
        need(observation.get('physical_page') == prep['physical_page']
             and observation.get('scope') ==
             'only_when_this_preparation_is_selected_not_unconditional_parent_property'
             and observation.get('preparation_fragments')
             and observation.get('parent_offering_fragments'), 'Wrong preparation review scope')
        key = selection.get('symbol_key')
        need(isinstance(key, str) and key, 'Explicit symbol key required')
        count = observation.get('symbols', {}).get(key)
        need(type(count) is int and count == 1, 'Selected symbol missing or count unsupported')
        # The key/count itself must appear in the original marker citations,
        # not merely in another item's details or a supplied legend.
        needle = re.escape(json.dumps(key)) + r'\s*:\s*1(?=\s*[,}])'
        matches = list(re.finditer(needle, text[prep['start']:prep['stop']]))
        need(len(matches) == 1, 'Ambiguous symbol key occurrence')
        a, b = prep['start']+matches[0].start(), prep['start']+matches[0].end()
        need(literal_support(marker, raw['metadata'], text, text[a:b], [[a,b]])['supported'],
             'Symbol key/count is not cited by the selected marker')
        legend_ids = sorted(set(legend['marker']['citation_ids'] + legend['meaning']['citation_ids']))
        covered(legend_ids, leg)
        meaning = json.loads(text[leg['start']:leg['stop']]).get('reviewed_legend_observation', {})
        label, description = selection.get('meaning'), selection.get('marker_description')
        need(isinstance(label, str) and label and marker['value'] == label
             and isinstance(description, str) and description
             and meaning.get('physical_page') == leg['physical_page']
             and meaning.get('marker_description') == description == legend['marker']['value']
             and isinstance(meaning.get('meanings'), list)
             and label in meaning['meanings']
             and legend['meaning']['value'] == ' / '.join(meaning['meanings']),
             'Legend label/description/meaning mismatch')
        need(literal_support(legend['meaning'], raw['metadata'], text, label,
                             [[leg['start'],leg['stop']]])['supported'], 'Uncited legend meaning')
        after = deepcopy(marker)
        after['citation_ids'] = sorted(set(marker['citation_ids'] + legend_ids))
        need(after['citation_ids'] != marker['citation_ids'], 'Bridge already present; no replay')
        view['response']['items'][ii]['dietary_markers'][mi] = after
        changes.append({'item_index': ii, 'marker_index': mi, 'legend_index': li,
                        'before': deepcopy(marker), 'after': deepcopy(after), 'symbol_key': key,
                        'marker_description': description, 'meaning': label,
                        'symbol_span': [a,b], 'preparation_origin': deepcopy(prep),
                        'legend_origin': deepcopy(leg), 'added_existing_citation_ids':
                        sorted(set(after['citation_ids'])-set(marker['citation_ids']))})
    view['derivation'] = {'kind': 'reviewed_symbol_legend_bridge', 'service_response': False,
        'quality_accepted': False, 'raw_response_sha256': digest(raw), 'plan_sha256': digest(plan),
        'semantic_mapping': 'supplied_posthoc_assistant_review_not_automated',
        'new_service_citations_created': 0, 'inherited_metadata_is_not_new_service_confidence': True}
    validate(view['response'], spec, citations(view, text))
    audit = {'bindings': expected, 'review': deepcopy(review), 'plan_sha256': digest(plan),
        'changes': changes, 'view_sha256': digest(view), 'new_ai_calls': 0,
        'quality_accepted': False, 'semantic_mapping_automated': False,
        'new_service_citations_created': 0}
    need(restore_view(view, audit) == raw, 'Bridge inverse mismatch')
    need(bindings(raw, text, schema, origins) == expected, 'Inputs mutated')
    return view, audit


def restore_view(view, audit):
    need(digest(view) == audit['view_sha256'], 'Derived donor changed')
    raw = deepcopy(view)
    for change in audit['changes']:
        markers = raw['response']['items'][change['item_index']]['dietary_markers']
        need(markers[change['marker_index']] == change['after'], 'Changed bridge field')
        markers[change['marker_index']] = deepcopy(change['before'])
    raw.pop('derivation')
    need(digest(raw) == audit['bindings']['raw'], 'Raw donor inverse mismatch')
    return raw
