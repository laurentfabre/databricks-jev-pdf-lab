"""Inventory every schema field; never infer semantic correctness or absence.

Pure code, no IO or inference. Exact string coverage is a diagnostic only.
The caller supplies source scopes; this module cannot certify their fidelity.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math

from citation_span_review import literal_support
from quality_gates import unwrap

MISSING = object()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def schema_paths(schema):
    paths = []
    def visit(spec, path):
        if not isinstance(spec, dict) or spec.get('type') not in (
                'string', 'number', 'integer', 'boolean', 'array', 'object'):
            raise ValueError('Unsupported schema node')
        paths.append(path)
        if spec['type'] == 'array':
            visit(spec['items'], path+'[]')
        elif spec['type'] == 'object':
            for name, child in spec['properties'].items():
                visit(child, path+'.'+name)
    for name, spec in schema.items():
        visit(spec, name)
    return paths


def occupancy(value, kind):
    if value is MISSING:
        return 'missing'
    if value is None:
        return 'null_source_presence_unknown'
    matches = {
        'string': lambda v: isinstance(v, str),
        'number': lambda v: type(v) in (int, float) and (type(v) is int or math.isfinite(v)),
        'integer': lambda v: type(v) is int,
        'boolean': lambda v: type(v) is bool,
        'array': lambda v: isinstance(v, list),
        'object': lambda v: isinstance(v, dict),
    }
    if not matches[kind](value):
        return 'type_mismatch'
    if value == '' or value == [] or value == {}:
        return 'empty_source_presence_unknown'
    return 'present_semantics_unknown'


def audit(raw, schema, text, scopes, expected_text_sha256):
    if not isinstance(text, str) or hashlib.sha256(text.encode()).hexdigest() != expected_text_sha256:
        raise ValueError('Source text hash mismatch')
    if (not isinstance(raw, dict) or not isinstance(raw.get('response'), dict)
            or raw.get('error_message') is not None
            or not isinstance(raw.get('metadata'), dict)
            or raw['metadata'].get('mode') != 'precision'
            or raw['metadata'].get('version') != '2.1'):
        raise ValueError('Successful Precision v2.1 response required')
    if not isinstance(scopes, list) or not scopes:
        raise ValueError('Source scopes required')
    for scope in scopes:
        if (not isinstance(scope, (list, tuple)) or len(scope) != 2
                or any(type(v) is not int for v in scope)
                or not 0 <= scope[0] < scope[1] <= len(text)):
            raise ValueError('Invalid source scope')
    before = digest(raw)
    all_schema_paths = schema_paths(schema)
    rows, extras = [], []

    def visit(field, spec, path, template):
        value = MISSING if field is MISSING else unwrap(field)
        container = field
        if (isinstance(field, dict) and 'value' in field
                and set(field) <= {'value', 'citation_ids', 'confidence_score'}):
            container = field['value']
        kind = spec['type']
        state = occupancy(value, kind)
        row = {'path': path, 'schema_path': template, 'expected_type': kind,
            'occupancy': state, 'semantic_status': 'not_evaluated',
            'source_presence': 'not_evaluated', 'accepted': False}
        if kind in ('array', 'object'):
            if isinstance(value, (list, dict)):
                row['length'] = len(value)
        elif value is not MISSING:
            row['value'] = deepcopy(value)
        if kind == 'string' and isinstance(value, str) and value:
            row['source_literal_present'] = any(value in text[a:b] for a,b in scopes)
            row['literal_citation'] = literal_support(field, raw['metadata'], text, value, scopes)
        rows.append(row)
        if kind == 'object' and isinstance(value, dict):
            for name in sorted(set(value)-set(spec['properties'])):
                extras.append(path+[name])
            for name, child in spec['properties'].items():
                visit(container.get(name, MISSING), child, path+[name], template+'.'+name)
        elif kind == 'array' and isinstance(value, list):
            # Accept a citation wrapper around a whole array without lending its
            # citations to individual elements. They need independent evidence.
            for index, child in enumerate(container):
                visit(child, spec['items'], path+[index], template+'[]')

    response = raw['response']
    extras.extend([[name] for name in sorted(set(response)-set(schema))])
    for name, spec in schema.items():
        visit(response.get(name, MISSING), spec, [name], name)
    seen = {row['schema_path'] for row in rows}
    coverage = [{'schema_path': path,
        'concrete_slots': sum(row['schema_path'] == path for row in rows),
        'status': 'inventoried_not_validated' if path in seen else 'no_concrete_slot_source_presence_unknown'}
        for path in all_schema_paths]
    bases = [row for row in rows if row['schema_path'] == 'items[].prices[].basis']
    assert digest(raw) == before
    return {'raw_sha256': before, 'schema_sha256': digest(schema),
        'text_sha256': expected_text_sha256, 'source_scopes_sha256': digest(scopes),
        'rows': rows, 'schema_coverage': coverage, 'unexpected_paths': extras,
        'counts': {'concrete_slots': len(rows), 'schema_paths': len(all_schema_paths),
            'schema_paths_without_slots': len(set(all_schema_paths)-seen),
            'occupancy': dict(Counter(row['occupancy'] for row in rows)),
            'price_basis_slots': len(bases),
            'price_basis_nonempty_strings': sum(isinstance(row.get('value'), str) and bool(row['value']) for row in bases),
            'price_basis_literal_absent': sum(row.get('source_literal_present') is False for row in bases),
            'price_basis_cited_whole_literal': sum(row.get('literal_citation', {}).get('supported', False) for row in bases)},
        'quality_accepted': False, 'raw_unchanged': True, 'new_ai_calls': 0,
        'limitations': ['Empty/missing fields do not establish missing source facts or absent allergens.',
            'Exact string citation coverage is not semantic support, identity, or completeness.',
            'Unmatched strings may be reordered or bilingual; this is not an error label.',
            'Supplied source scopes are not independently validated against the PDF.',
            'Numeric, enum, and page correctness are not proved by string checks.',
            'Every schema path remains subject to source-level semantic review.']}
