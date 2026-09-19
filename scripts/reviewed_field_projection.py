"""Execute explicit reviewed selections, not semantic discovery or acceptance.

Pure functions; no I/O or inference. Real plans and returned audits contain
source/output values and must stay inside their approved data boundary.
"""
from copy import deepcopy
import hashlib
import math

from citation_span_review import literal_support
from quality_gates import unwrap
from source_bound_recovery import digest


def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def at(value, path):
    for key in path:
        if isinstance(value, list):
            if type(key) is not int or not 0 <= key < len(value):
                raise ValueError('Invalid array path')
        elif isinstance(value, dict):
            if not isinstance(key, str) or key not in value:
                raise ValueError('Invalid object path')
        else:
            raise ValueError('Path crosses a scalar')
        value = value[key]
    return value


def field_spec(schema, path):
    if not isinstance(path, list) or len(path) < 2 or path[0] != 'response':
        raise ValueError('Only response fields may change')
    spec = {'type': 'object', 'properties': schema}
    for key in path[1:]:
        if spec['type'] == 'object' and isinstance(key, str) and key in spec['properties']:
            spec = spec['properties'][key]
        elif spec['type'] == 'array' and type(key) is int and key >= 0:
            spec = spec['items']
        else:
            raise ValueError('Path is not in the frozen schema')
    return spec


def validate_value(node, spec):
    value, kind = unwrap(node), spec['type']
    if value is None and kind not in ('object', 'array'):
        return
    if kind == 'object':
        if not isinstance(value, dict) or set(value) != set(spec['properties']):
            raise ValueError('Object fields differ from schema')
        for key, child in spec['properties'].items():
            validate_value(value[key], child)
    elif kind == 'array':
        if not isinstance(value, list):
            raise ValueError('Array required')
        for child in value:
            validate_value(child, spec['items'])
    else:
        valid = {'string': isinstance(value, str), 'boolean': type(value) is bool,
            'integer': type(value) is int,
            'number': type(value) in (int, float) and (type(value) is int or math.isfinite(value))}
        if not valid.get(kind, False):
            raise ValueError('Scalar type mismatch')


def source_recipe(text, scopes, element_id, literal):
    """Resolve a caller-selected literal; uniqueness is not semantic identity."""
    matches = [s for s in scopes if s['element_id'] == element_id]
    if len(matches) != 1 or not isinstance(literal, str) or not literal:
        raise ValueError('One element and a nonempty literal required')
    scope = matches[0]
    fragment = text[scope['start']:scope['stop']]
    start = fragment.find(literal)
    if start < 0 or fragment.find(literal, start + 1) >= 0:
        raise ValueError('Selected literal missing or ambiguous')
    start += scope['start']
    return {'kind': 'source', 'element_id': element_id, 'start': start,
            'stop': start + len(literal), 'literal_sha256': text_hash(literal)}


def project(raw, text, scopes, schema, plan):
    before_hash = digest(raw)
    bindings = {'raw_sha256': before_hash, 'text_sha256': text_hash(text),
                'scopes_sha256': digest(scopes), 'schema_sha256': digest(schema)}
    if plan.get('bindings') != bindings:
        raise ValueError('Stale or wrong input/schema/scope binding')
    review = plan.get('review', {})
    if (review.get('kind') != 'assistant_posthoc_source_review'
            or review.get('independent') is not False
            or not isinstance(review.get('evidence_sha256'), str)
            or len(review['evidence_sha256']) != 64
            or any(c not in '0123456789abcdef' for c in review['evidence_sha256'])):
        raise ValueError('Explicit bounded review provenance required')
    metadata = raw.get('metadata', {})
    if (raw.get('error_message') is not None or metadata.get('version') != '2.1'
            or metadata.get('mode') != 'precision' or metadata.get('chunk_type') != 'span'):
        raise ValueError('Successful span-cited Precision v2.1 response required')
    by_element = {}
    for scope in scopes:
        if (type(scope.get('element_id')) is not int or scope['element_id'] in by_element
                or type(scope.get('page')) is not int or scope['page'] < 1
                or type(scope.get('start')) is not int or type(scope.get('stop')) is not int
                or not 0 <= scope['start'] < scope['stop'] <= len(text)):
            raise ValueError('Invalid original-source scope')
        by_element[scope['element_id']] = scope
    if not by_element:
        raise ValueError('Missing source scopes')
    validate_value(raw['response'], {'type': 'object', 'properties': schema})
    citations = metadata.get('citations', [])
    if not isinstance(citations, list):
        raise ValueError('Missing citations')
    seen_ids = set()
    for cite in citations:
        if (type(cite.get('id')) is not int or cite['id'] in seen_ids
                or type(cite.get('start')) is not int or type(cite.get('stop')) is not int
                or not 0 <= cite['start'] < cite['stop'] <= len(text)):
            raise ValueError('Invalid or duplicate citation')
        seen_ids.add(cite['id'])
    operations = plan.get('operations')
    if not isinstance(operations, list):
        raise ValueError('Operations must be an explicit list')
    paths = []
    for op in operations:
        path = op['path']
        field_spec(schema, path)
        if any(path[:len(p)] == p or p[:len(path)] == path for p in paths):
            raise ValueError('Conflicting/overlapping operations')
        paths.append(path)
    shadow, changes = deepcopy(raw), []
    for op in operations:
        path, spec = op['path'], field_spec(schema, op['path'])
        old = at(raw, path)
        if digest(old) != op.get('before_sha256') or not op.get('reason'):
            raise ValueError('Changed precondition or missing review reason')
        page = op.get('physical_page')
        if type(page) is not int or page < 1:
            raise ValueError('Explicit physical page required')
        if path[:2] == ['response', 'items']:
            if len(path) < 4 or unwrap(at(raw, path[:3]).get('source_pages')) != [page]:
                raise ValueError('Target item page disagreement')
        proofs = []

        def compile_recipe(recipe):
            kind = recipe.get('kind')
            if kind == 'source':
                scope = by_element.get(recipe.get('element_id'))
                a, b = recipe.get('start'), recipe.get('stop')
                if (type(recipe.get('element_id')) is not int or scope is None or scope['page'] != page
                        or type(a) is not int or type(b) is not int
                        or not scope['start'] <= a < b <= scope['stop']):
                    raise ValueError('Source selection crosses scope/page')
                literal = text[a:b]
                if text_hash(literal) != recipe.get('literal_sha256'):
                    raise ValueError('Source literal changed')
                ids = [c['id'] for c in citations if c['start'] < b and a < c['stop']]
                result = literal_support({'value': literal, 'citation_ids': ids}, metadata,
                                         text, literal, [[a, b]])
                if not result['supported']:
                    raise ValueError('Selected source literal has uncited gaps')
                proofs.append({'kind': 'literal_coverage_not_semantics', 'element_id': scope['element_id'],
                    'physical_page': page, 'span': [a, b], 'literal_sha256': text_hash(literal),
                    'citation_ids': ids})
                return {'value': literal, 'citation_ids': ids}
            if kind == 'join':
                separator = recipe.get('separator')
                parts = [compile_recipe(p) for p in recipe.get('parts', [])]
                if (separator not in (' / ', '; ', '\n') or not parts
                        or any(not isinstance(p, dict) or not isinstance(p.get('value'), str) for p in parts)):
                    raise ValueError('String sources and declared separator required')
                return {'value': separator.join(p['value'] for p in parts),
                        'citation_ids': sorted({i for p in parts for i in p['citation_ids']})}
            if kind == 'retain':
                if not isinstance(old, dict) or not isinstance(old.get('value'), str):
                    raise ValueError('Retain only the current string field')
                ids = old.get('citation_ids')
                if not isinstance(ids, list) or any(type(i) is not int or i not in seen_ids for i in ids):
                    raise ValueError('Invalid retained citation IDs')
                proofs.append({'kind': 'retained_prose_not_revalidated', 'sha256': digest(old)})
                return {'value': old['value'], 'citation_ids': deepcopy(ids)}
            if kind == 'page':
                source = compile_recipe(recipe['source'])
                return {'value': page, 'citation_ids': source['citation_ids']}
            if kind == 'object':
                return {key: compile_recipe(value) for key, value in recipe['fields'].items()}
            if kind == 'array':
                return [compile_recipe(value) for value in recipe['items']]
            if kind == 'reviewed_unstated':
                previous = unwrap(old)
                if (recipe.get('review_finding') != 'basis_default' or spec['type'] != 'string'
                        or path[-1] != 'basis' or op['op'] != 'replace'
                        or not isinstance(previous, str) or not previous
                        or any(previous in text[s['start']:s['stop']] for s in scopes)):
                    raise ValueError('No explicitly reviewed absent basis literal')
                proofs.append({'kind': 'assistant_absence_judgment_not_code_proof',
                    'review_finding': recipe['review_finding'], 'previous_literal': previous})
                return {'value': None, 'citation_ids': []}
            raise ValueError('Unsupported recipe')

        value = compile_recipe(op['recipe'])
        if op['op'] == 'replace':
            validate_value(value, spec)
            new = value
        elif op['op'] == 'append' and spec['type'] == 'array' and isinstance(old, list):
            validate_value(value, spec['items'])
            if unwrap(value) in unwrap(old):
                raise ValueError('Duplicate append')
            new = deepcopy(old) + [value]
        else:
            raise ValueError('Unsupported operation or target')
        if new == old:
            raise ValueError('No-op selection')
        at(shadow, path[:-1])[path[-1]] = new
        changes.append({'path': path, 'op': op['op'], 'reason': op['reason'],
            'before': deepcopy(old), 'after': deepcopy(new), 'proofs': proofs,
            'semantic_review_required': True, 'quality_accepted': False})
    validate_value(shadow['response'], {'type': 'object', 'properties': schema})
    assert shadow['metadata'] == raw['metadata'] and digest(raw) == before_hash
    audit = {'bindings': bindings, 'plan_sha256': digest(plan), 'review': deepcopy(review),
        'shadow_sha256': digest(shadow), 'changes': changes, 'new_ai_calls': 0,
        'semantic_selection': 'supplied_posthoc_assistant_review_not_automated',
        'raw_unchanged': True, 'metadata_unchanged': True, 'quality_accepted': False,
        'limits': ['Exact citation coverage does not prove identity, meaning, completeness or source fidelity.',
            'Null selections rely on a supplied absence judgment, not literal matching alone.',
            'Retained prose and untouched fields are not revalidated.',
            'New fields use existing span IDs; no new service confidence or citation is invented.']}
    assert digest(restore(shadow, audit)) == before_hash
    return shadow, audit


def restore(shadow, audit):
    if digest(shadow) != audit['shadow_sha256']:
        raise ValueError('Projected output changed before reversal')
    raw = deepcopy(shadow)
    for change in reversed(audit['changes']):
        path = change['path']
        if at(raw, path) != change['after']:
            raise ValueError('Inverse precondition changed')
        at(raw, path[:-1])[path[-1]] = deepcopy(change['before'])
    if digest(raw) != audit['bindings']['raw_sha256']:
        raise ValueError('Inverse hash mismatch')
    return raw
