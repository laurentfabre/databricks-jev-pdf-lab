"""Compose explicitly selected fields from retained, span-cited Precision results.

This is exact execution of supplied review, not automatic semantic selection.
The result is explicitly derived, never a new service response. Its citations
address a composite of the exact two original input strings; the audit retains
each citation's original namespace and each input's original provenance map.
No IO, inference, fuzzy matching, generated values or semantic acceptance.
"""
from copy import deepcopy
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def citations(raw, text):
    need(isinstance(raw, dict) and isinstance(text, str), 'Invalid response/input')
    need(not raw.get('error_message'), 'Service error')
    metadata = raw.get('metadata', {})
    need(metadata.get('mode') == 'precision' and metadata.get('version') == '2.1'
         and metadata.get('chunk_type') == 'span', 'Expected Precision 2.1 span citations')
    rows = metadata.get('citations')
    need(isinstance(rows, list), 'Missing citation table')
    lookup = {}
    for row in rows:
        need(isinstance(row, dict), 'Invalid citation')
        ident, start, stop = row.get('id'), row.get('start'), row.get('stop')
        need(type(ident) is int and ident >= 0 and ident not in lookup, 'Invalid/duplicate citation ID')
        need(type(start) is int and type(stop) is int and 0 <= start < stop <= len(text),
             'Invalid character span')
        lookup[ident] = row
    return lookup


def validate(value, spec, lookup):
    kind = spec.get('type')
    if kind == 'array':
        need(isinstance(value, list), 'Expected array')
        for child in value:
            validate(child, spec['items'], lookup)
    elif kind == 'object':
        need(isinstance(value, dict) and set(value) == set(spec['properties']), 'Object schema mismatch')
        for key, child in value.items():
            validate(child, spec['properties'][key], lookup)
    else:
        need(kind in ('string', 'number', 'integer', 'boolean', 'enum'), 'Unknown scalar type')
        need(isinstance(value, dict) and 'value' in value and 'citation_ids' in value,
             'Expected cited scalar')
        ids = value['citation_ids']
        need(isinstance(ids, list) and all(type(i) is int and i in lookup for i in ids),
             'Missing/unknown citation reference')
        scalar = value['value']
        if scalar is None:
            return
        need(bool(ids), 'Non-null scalar has no citations')
        valid = {
            'string': isinstance(scalar, str),
            'number': type(scalar) in (float, int),
            'integer': type(scalar) is int,
            'boolean': type(scalar) is bool,
            'enum': scalar in spec.get('labels', []),
        }[kind]
        need(valid, 'Scalar schema mismatch')
        digest(scalar)  # Reject non-finite numbers.


def scalar_fields(value):
    if isinstance(value, list):
        for child in value:
            yield from scalar_fields(child)
    elif isinstance(value, dict):
        if 'value' in value and 'citation_ids' in value:
            yield value
        else:
            for child in value.values():
                yield from scalar_fields(child)


def bindings(base, base_text, donor, donor_text, schema, origins):
    return {'base': digest(base), 'base_text': text_hash(base_text),
            'donor': digest(donor), 'donor_text': text_hash(donor_text),
            'schema': digest(schema), 'origins': digest(origins)}


def compose(base, base_text, donor, donor_text, schema, origins, plan):
    """Replace selected root schema fields, preserving every other response field.

    Root selection deliberately avoids heuristic item matching. Callers supply
    complete reviewed subtrees; partial or conflicting selection must abstain.
    Origins are retained in their own input coordinates, never relabelled.
    """
    need(isinstance(schema, dict) and schema, 'Missing schema')
    need(isinstance(origins, dict) and set(origins) == {'base', 'donor'}, 'Missing input origins')
    need(isinstance(plan, dict), 'Invalid plan')
    expected = bindings(base, base_text, donor, donor_text, schema, origins)
    need(plan.get('bindings') == expected, 'Stale input/schema/origin binding')
    review = plan.get('review', {})
    need(review.get('kind') == 'supplied_field_review' and review.get('independent') is False
         and isinstance(review.get('evidence_sha256'), str)
         and len(review['evidence_sha256']) == 64
         and all(c in '0123456789abcdef' for c in review['evidence_sha256']), 'Missing explicit review binding')
    base_ids, donor_ids = citations(base, base_text), citations(donor, donor_text)
    root_spec = {'type': 'object', 'properties': schema}
    validate(base.get('response'), root_spec, base_ids)
    validate(donor.get('response'), root_spec, donor_ids)
    selections = plan.get('fields')
    need(isinstance(selections, list) and selections, 'No selected fields')
    seen = set()
    for selection in selections:
        need(isinstance(selection, dict), 'Invalid field selection')
        field = selection.get('field')
        need(isinstance(field, str) and field in schema and field not in seen, 'Invalid/duplicate field')
        seen.add(field)
        need(selection.get('base_sha256') == digest(base['response'][field])
             and selection.get('donor_sha256') == digest(donor['response'][field]), 'Stale field binding')
    # Use Unicode character counts, not UTF-8 bytes. No deduplication, whitespace
    # normalization, citation widening or disappearing uncited gaps.
    separator = '\n\n[DERIVED COMPOSITION: SECOND RETAINED INPUT; NOT A NEW MODEL INPUT]\n'
    offset = len(base_text) + len(separator)
    composite = base_text + separator + donor_text
    result = deepcopy(base)
    all_used = {i for field in seen for scalar in scalar_fields(donor['response'][field])
                for i in scalar['citation_ids']}
    next_id = max(base_ids, default=-1) + 1
    mapping, copied = {}, []
    for index, old_id in enumerate(sorted(all_used)):
        old = donor_ids[old_id]
        new = deepcopy(old)
        new.update(id=next_id+index, start=old['start']+offset, stop=old['stop']+offset)
        need(composite[new['start']:new['stop']] == donor_text[old['start']:old['stop']],
             'Citation text changed')
        result['metadata']['citations'].append(new)
        mapping[old_id] = new['id']
        copied.append({'input': 'donor', 'original_id': old_id, 'derived_id': new['id'],
                       'original_start': old['start'], 'original_stop': old['stop'],
                       'derived_start': new['start'], 'derived_stop': new['stop'],
                       'cited_text_sha256': text_hash(donor_text[old['start']:old['stop']])})
    before = {}
    for selection in selections:
        field = selection['field']
        before[field] = deepcopy(base['response'][field])
        value = deepcopy(donor['response'][field])
        for scalar in scalar_fields(value):
            scalar['citation_ids'] = [mapping[i] for i in scalar['citation_ids']]
        result['response'][field] = value
    result['derivation'] = {'kind': 'reviewed_field_composition', 'service_response': False,
                            'quality_accepted': False, 'plan_sha256': digest(plan)}
    validate(result['response'], root_spec, citations(result, composite))
    audit = {'version': 1, 'bindings': expected, 'plan_sha256': digest(plan),
        'review': deepcopy(review), 'selected_fields': [r['field'] for r in selections],
        'origins_in_original_input_coordinates': deepcopy(origins),
        'input_blocks': [
            {'input': 'base', 'start': 0, 'stop': len(base_text), 'sha256': text_hash(base_text)},
            {'input': 'donor', 'start': offset, 'stop': len(composite), 'sha256': text_hash(donor_text)}],
        'base_citations_unchanged': True, 'copied_citations': copied,
        'before_fields': before, 'before_metadata': deepcopy(base['metadata']),
        'before_derivation_present': 'derivation' in base,
        'before_derivation': deepcopy(base.get('derivation')),
        'derived_sha256': digest(result), 'composite_text_sha256': text_hash(composite),
        'quality_accepted': False, 'semantic_selection_automated': False,
        'new_service_citations_created': 0}
    need(restore(result, audit) == base, 'Inverse does not recover base')
    return result, composite, audit


def restore(result, audit):
    need(digest(result) == audit['derived_sha256'], 'Derived result changed')
    restored = deepcopy(result)
    restored['response'].update(deepcopy(audit['before_fields']))
    restored['metadata'] = deepcopy(audit['before_metadata'])
    if audit['before_derivation_present']:
        restored['derivation'] = deepcopy(audit['before_derivation'])
    else:
        restored.pop('derivation', None)
    need(digest(restored) == audit['bindings']['base'], 'Inverse binding mismatch')
    return restored
