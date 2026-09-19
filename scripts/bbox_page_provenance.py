"""Derive cited physical locations, not semantic support. No I/O or inference.

Only full, unreordered original PDF parser inputs are supported. Raw responses
and all non-page fields remain unchanged; derived outputs are never accepted.
"""
from copy import deepcopy
import hashlib
import json
import math
import re

from quality_gates import unwrap


class UnsupportedResponse(ValueError):
    """A retained result cannot safely enter this narrow derivation."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def bindings(raw, parsed, schema):
    return {'raw': digest(raw), 'parsed': digest(parsed), 'schema': digest(schema)}


def box_key(box, page_ids):
    need(isinstance(box, dict) and set(box) == {'coord', 'page_id'}, 'Unsupported bbox shape')
    page, coord = box['page_id'], box['coord']
    need(type(page) is int and page in page_ids, 'Unknown bbox page')
    need(isinstance(coord, list) and len(coord) == 4
         and all(type(n) in (int, float) and math.isfinite(n) and n >= 0 for n in coord),
         'Invalid bbox coordinates')
    need(coord[0] < coord[2] and coord[1] < coord[3], 'Empty or inverted bbox')
    return page, tuple(coord)


def scalar_fields(value, spec, path):
    kind = spec['type']
    if kind == 'object':
        need(isinstance(value, dict) and set(value) == set(spec['properties']), 'Unsupported object at '+path)
        for key, child in spec['properties'].items():
            yield from scalar_fields(value[key], child, path+'.'+key)
    elif kind == 'array':
        need(isinstance(value, list), 'Nonarray at '+path)
        for i, child in enumerate(value):
            yield from scalar_fields(child, spec['items'], f'{path}[{i}]')
    else:
        need(isinstance(value, dict) and {'value', 'citation_ids'} <= set(value)
             and set(value) <= {'value', 'citation_ids', 'confidence_score'}, 'Missing scalar wrapper at '+path)
        v = value['value']
        valid = (kind == 'string' and isinstance(v, str)
                 or kind == 'integer' and type(v) is int
                 or kind == 'number' and type(v) in (int, float) and math.isfinite(v)
                 or kind == 'boolean' and type(v) is bool)
        need(v is None or valid, 'Wrong scalar type at '+path)
        ids = value['citation_ids']
        need(isinstance(ids, list) and all(type(i) is int and i >= 0 for i in ids)
             and len(set(ids)) == len(ids), 'Invalid citation IDs at '+path)
        yield path, value


def derive(raw, parsed, schema, contract):
    original = bindings(raw, parsed, schema)
    need(contract.get('bindings') == original, 'Stale input/schema binding')
    need(contract.get('page_basis') == 'full_original_pdf_zero_based', 'Unsupported input page basis')
    need(re.fullmatch('[0-9a-f]{64}', contract.get('source_sha256', '')) is not None,
         'Explicit original source hash required')
    n = contract.get('physical_pages')
    need(type(n) is int and n > 0, 'Positive physical page count required')
    need(not parsed.get('error_status') and parsed.get('metadata', {}).get('version') == '2.0',
         'Successful parser v2.0 required')
    pages = parsed.get('document', {}).get('pages', [])
    need([p.get('id') for p in pages] == list(range(n))
         and all(type(p.get('id')) is int for p in pages), 'Full original page IDs required')
    page_ids = set(range(n))
    elements = parsed['document']['elements']
    parser_boxes = {box_key(b, page_ids) for e in elements for b in e.get('bbox', [])}
    meta = raw.get('metadata') or {}
    if (raw.get('error_message') or meta.get('version') != '2.1'
            or meta.get('mode') != 'precision' or meta.get('chunk_type') != 'bbox'
            or 'derivation' in raw or not isinstance(raw.get('response'), dict)):
        raise UnsupportedResponse('Successful unchanged Precision v2.1 BBOX result required')
    try:
        meta_pages = [p['id'] for p in meta['pages']]
        need(all(type(p) is int and p in page_ids for p in meta_pages)
             and len(set(meta_pages)) == len(meta_pages), 'Invalid metadata page subset')
        citations = {}
        for citation in meta['citations']:
            cid = citation['id']
            need(type(cid) is int and cid >= 0 and cid not in citations, 'Duplicate/invalid citation ID')
            need(isinstance(citation.get('bbox'), list) and citation['bbox'], 'Empty citation bbox')
            keys = [box_key(b, page_ids) for b in citation['bbox']]
            need(all(k[0] in meta_pages for k in keys), 'Cited page absent from metadata')
            citations[cid] = keys
    except (KeyError, TypeError, ValueError) as error:
        raise UnsupportedResponse(str(error)) from error
    shadow = deepcopy(raw)
    changes, records = [], []
    for collection, anchor in [('items', 'name'), ('policies', 'text'), ('dietary_allergen_legend', 'meaning')]:
        rows = raw['response'].get(collection)
        if not isinstance(rows, list):
            raise UnsupportedResponse('Nonarray response collection: '+collection)
        record_spec = schema[collection]['items']
        need(record_spec['type'] == 'object' and 'source_pages' in record_spec['properties'],
             'Unsupported record schema')
        for index, record in enumerate(rows):
            path = f'{collection}[{index}]'
            observation = {'path': path, 'collection': collection, 'index': index,
                           'status': 'abstained', 'semantic_support': 'not_evaluated'}
            records.append(observation)
            try:
                fields = list(scalar_fields(record, record_spec, path))
                need(isinstance(record[anchor]['value'], str) and record[anchor]['value'].strip(),
                     'Missing record identity')
                page_refs, used = {}, []
                for field_path, field in fields:
                    if field_path.startswith(path+'.source_pages['):
                        continue  # Generated page claims must not justify themselves.
                    if field['value'] is None or field['value'] == '':
                        continue  # Not a claim of source absence.
                    need(field['citation_ids'], 'Uncited populated field at '+field_path)
                    locations = set()
                    for cid in field['citation_ids']:
                        need(cid in citations, 'Unknown citation at '+field_path)
                        for key in citations[cid]:
                            need(key in parser_boxes, 'Citation bbox not present in parser input')
                            physical = key[0]+1
                            locations.add(physical)
                            page_refs.setdefault(physical, set()).add(cid)
                    used.append({'path': field_path, 'citation_ids': field['citation_ids'],
                                 'physical_pages': sorted(locations)})
                need(page_refs, 'No cited record evidence')
                derived_pages = sorted(page_refs)
                observation.update(cited_physical_pages=derived_pages, fields=used,
                                   original_source_pages=deepcopy(record['source_pages']))
                if unwrap(record['source_pages']) == derived_pages:
                    observation['status'] = 'already_consistent'
                    continue
                after = [{'value': p, 'citation_ids': sorted(page_refs[p])} for p in derived_pages]
                shadow['response'][collection][index]['source_pages'] = after
                changes.append({'collection': collection, 'index': index,
                                'before': deepcopy(record['source_pages']), 'after': deepcopy(after)})
                observation['status'] = 'derived_changed'
            except (KeyError, TypeError, ValueError) as error:
                observation['reason'] = str(error)
    shadow['derivation'] = {'kind': 'cited_bbox_locations_v1', 'service_response': False,
        'raw_sha256': original['raw'], 'contract_sha256': digest(contract), 'quality_accepted': False,
        'semantic_support': 'not_proven', 'inherited_metadata_is_not_new_confidence': True}
    audit = {'bindings': original, 'contract': deepcopy(contract), 'changes': changes, 'records': records,
             'shadow_sha256': digest(shadow), 'quality_accepted': False, 'new_ai_calls': 0}
    need(restore(shadow, audit) == raw, 'Inverse failed')
    need(bindings(raw, parsed, schema) == original, 'Inputs mutated')
    return shadow, audit


def restore(shadow, audit):
    need(digest(shadow) == audit['shadow_sha256'], 'Shadow changed')
    raw = deepcopy(shadow)
    for change in audit['changes']:
        record = raw['response'][change['collection']][change['index']]
        need(record['source_pages'] == change['after'], 'Derived page field changed')
        record['source_pages'] = deepcopy(change['before'])
    raw.pop('derivation')
    need(digest(raw) == audit['bindings']['raw'], 'Raw inverse mismatch')
    return raw
