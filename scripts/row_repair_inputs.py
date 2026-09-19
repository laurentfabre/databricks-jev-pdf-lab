"""Exact excerpts from a retained, origin-labelled repair input. No I/O or AI.

Selections are supplied development judgments, not semantic inference. Output
is explicitly partial; omitted material remains required in the full task.
Real strings, origin maps and plans must stay in their approved data boundary.
"""
from copy import deepcopy
import hashlib
import json
import re

from table_scope_candidates import cells


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def digest(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False))


def row_spans(table):
    rows, _ = cells(table)  # Frozen strict grammar; no normalization.
    matches = list(re.finditer(r'<tr>.*?</tr>', table, re.DOTALL))
    if (len(matches) != len(rows)
            or '<table>' + ''.join(m[0] for m in matches) + '</table>' != table):
        raise ValueError('Rows do not reconstruct the exact table')
    return [(m.start(), m.end()) for m in matches]


def build_cases(text, provenance, plan):
    snapshot = deepcopy((text, provenance, plan))
    if plan.get('bindings') != {'text_sha256': sha(text), 'provenance_sha256': digest(provenance)}:
        raise ValueError('Stale input or provenance binding')
    if provenance['input_sha256']['review_enriched'] != sha(text):
        raise ValueError('Retained enriched input mismatch')
    if plan.get('review') != {'kind': 'assistant_posthoc_selection', 'independent': False}:
        raise ValueError('Explicit non-independent selection required')
    segments = provenance['segments']['review_enriched']
    cursor = 0
    for index, segment in enumerate(segments):
        a, b = segment['start'], segment['stop']
        if (type(a) is not int or type(b) is not int or a != cursor
                or not 0 <= a < b <= len(text) or not isinstance(segment.get('origin'), str)):
            raise ValueError('Invalid retained segment accounting')
        cursor = b + 1
        if index < len(segments) - 1 and text[b:b+1] != '\n':
            raise ValueError('Retained segment gap is not a newline')
    if not segments or cursor - 1 != len(text):
        raise ValueError('Unaccounted retained suffix')

    def unique(predicate):
        found = [(i, s) for i, s in enumerate(segments) if predicate(s)]
        if len(found) != 1:
            raise ValueError('Expected one retained segment')
        return found[0]

    def source(ident):
        return unique(lambda s: s['origin'] == 'original_parser_text' and s.get('element_id') == ident)

    def whole(pair):
        return text[pair[1]['start']:pair[1]['stop']]

    table_pair = source(plan['table_element_id'])
    table = whole(table_pair)
    spans = row_spans(table)
    parents, heading = plan['parent_rows'], plan['heading_row']
    if (not isinstance(parents, list) or not parents or any(type(r) is not int for r in parents)
            or parents != sorted(set(parents)) or type(heading) is not int
            or not 0 <= min(parents) <= max(parents) < heading < len(spans)):
        raise ValueError('Ordered parent rows before heading required')
    context_ids = plan['context_element_ids']
    legend_ids = plan['legend_element_ids']
    identifiers = context_ids + [plan['table_element_id']] + legend_ids
    if (not context_ids or not legend_ids or any(type(i) is not int for i in identifiers)
            or len(set(identifiers)) != len(identifiers)):
        raise ValueError('Distinct explicit source context required')
    source_page = table_pair[1]['physical_page']
    legend_pages = {source(i)[1]['physical_page'] for i in legend_ids}
    if (any(source(i)[1]['physical_page'] != source_page for i in context_ids)
            or len(legend_pages) != 1 or source_page in legend_pages):
        raise ValueError('Invalid context or legend page')
    legend_page = next(iter(legend_pages))
    cases = plan['cases']
    if (not cases or len({c['case_id'] for c in cases}) != len(cases)
            or len({c['source_group'] for c in cases}) != len(cases)
            or len({c['row'] for c in cases}) != len(cases)):
        raise ValueError('Distinct explicit cases required')
    results, audits = {}, {}
    for case in cases:
        target = case['row']
        if (not re.fullmatch(r'[a-z][a-z0-9_]*', case['case_id']) or type(target) is not int
                or not heading < target < len(spans)):
            raise ValueError('Unsupported case or preparation row')
        selected_rows = parents + [heading, target]
        reviewed = unique(lambda s: s['origin'] == 'assistant_image_review'
                          and s.get('source_group') == case['source_group'])
        observation = json.loads(whole(reviewed))['reviewed_preparation_observation']
        row_text = table[slice(*spans[target])]
        parent_text = ''.join(table[slice(*spans[r])] for r in parents)
        if (reviewed[1]['physical_page'] != source_page
                or observation['physical_page'] != source_page
                or observation['scope'] != 'only_when_this_preparation_is_selected_not_unconditional_parent_property'
                or not observation['preparation_fragments']
                or not observation['parent_offering_fragments']
                or any(f not in row_text for f in observation['preparation_fragments'])
                or any(f not in parent_text for fs in observation['parent_offering_fragments'] for f in fs)):
            raise ValueError('Review does not bind selected source fragments')
        fragments, mapped = [], []
        offset = 0

        def emit(fragment, origin, **attrs):
            nonlocal offset
            if not fragment:
                raise ValueError('Empty excerpt fragment')
            fragments.append(fragment)
            mapped.append({'start': offset, 'stop': offset + len(fragment), 'origin': origin, **attrs})
            offset += len(fragment)

        def newline():
            if fragments:
                emit('\n', 'assembly_separator')

        def label(value):
            newline(); emit(value, 'assembly_label')

        def copy(pair, relative=None, new_line=True, **attrs):
            index, segment = pair
            a, b = segment['start'], segment['stop']
            if relative is not None:
                a, b = a + relative[0], a + relative[1]
            if not segment['start'] <= a < b <= segment['stop']:
                raise ValueError('Copy outside retained source segment')
            if new_line:
                newline()
            extra = {k: v for k, v in segment.items() if k not in ('start', 'stop', 'origin')}
            emit(text[a:b], segment['origin'], source_segment_index=index,
                 source_start=a, source_stop=b, **extra, **attrs)

        label('[PARTIAL SOURCE EXCERPT: one selected preparation row with parent context. '
              'Other preparation choices and other document facts are omitted here, not absent. '
              'The complete source remains required outside this repair input.]')
        copy(unique(lambda s: s['origin'] == 'physical_page_label' and s.get('physical_page') == source_page))
        for ident in context_ids:
            label(f'[ELEMENT {ident}]'); copy(source(ident))
        label(f'[ELEMENT {plan["table_element_id"]}; PARTIAL TABLE: both parents, shared heading and one selected row; other rows omitted]')
        copy(table_pair, (0, len('<table>')))
        for r in selected_rows:
            copy(table_pair, spans[r], new_line=False, source_table_row=r)
        copy(table_pair, (len(table)-len('</table>'), len(table)), new_line=False)
        copy(unique(lambda s: s['origin'] == 'physical_page_label' and s.get('physical_page') == legend_page))
        for ident in legend_ids:
            label(f'[ELEMENT {ident}]'); copy(source(ident))
        for origin in ('annotation_label', 'retained_annotation_caveats'):
            copy(unique(lambda s: s['origin'] == origin))
        copy(unique(lambda s: s['origin'] == 'provisional_image_observation'
                    and s.get('source_group') == case['source_group']))
        for origin in ('review_label', 'review_caveats'):
            copy(unique(lambda s: s['origin'] == origin))
        legend_review = [(i, s) for i, s in enumerate(segments)
                         if s['origin'] == 'assistant_image_review' and 'source_group' not in s]
        if not legend_review:
            raise ValueError('Missing legend review')
        for pair in legend_review:
            row = json.loads(whole(pair))['reviewed_legend_observation']
            if row['source_element_id'] not in legend_ids or row['physical_page'] != legend_page:
                raise ValueError('Legend review outside selected source')
            copy(pair)
        copy(reviewed)
        result = ''.join(fragments)
        # Each copied interval is exact and retains its original evidence kind.
        for s in mapped:
            if 'source_start' in s:
                assert result[s['start']:s['stop']] == text[s['source_start']:s['source_stop']]
        results[case['case_id']] = result
        audits[case['case_id']] = {'segments': mapped, 'selected_table_rows': selected_rows,
            'omitted_table_rows': [r for r in range(len(spans)) if r not in selected_rows],
            'source_group': case['source_group'], 'input_sha256': sha(result),
            'input_bytes': len(result.encode('utf-8')), 'input_characters': len(result),
            'quality_accepted': False, 'full_document': False, 'automatic_selection': False}
    assert (text, provenance, plan) == snapshot
    return results, {'parent_input_sha256': sha(text), 'parent_provenance_sha256': digest(provenance),
        'plan_sha256': digest(plan), 'cases': audits, 'new_ai_calls': 0,
        'semantic_selection_automated': False, 'unselected_material_still_required': True,
        'quality_accepted': False}
