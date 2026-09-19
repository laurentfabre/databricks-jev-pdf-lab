"""Lossless table-only transform for page-labelled, symbol-annotated inputs.

No evidence selection, semantic correction, PDF read, or inference. Source
records reconstruct the prefix exactly; the complete annotation suffix is opaque.
"""
from copy import deepcopy
import hashlib

from table_compaction import compact_document, restore_tables, serialized
import json

ANNOTATION_MARKER = '[ADDITIONAL IMAGE-SYMBOL OBSERVATIONS; NOT ORIGINAL PARSER TEXT]'


def sha(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()


def render(records, pages):
    if (not isinstance(pages, list) or not pages or any(type(p) is not int for p in pages)
            or pages != list(range(1, len(pages)+1))):
        raise ValueError('Complete ordered physical page inventory required')
    if not isinstance(records, list) or not records:
        raise ValueError('No source records')
    ids = []
    for record in records:
        if (set(record) != {'id', 'type', 'physical_page', 'content'}
                or type(record['id']) is not int or type(record['physical_page']) is not int
                or record['physical_page'] not in pages or not isinstance(record['type'], str)
                or not isinstance(record['content'], str)):
            raise ValueError('Invalid or ambiguous source record')
        ids.append(record['id'])
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate source element ID')
    parts, scopes, offset = [], [], 0
    for page in pages:
        label = f'[SOURCE PAGE {page}]'
        parts.append(label)
        offset += len(label)+1
        for record in records:
            if record['physical_page'] != page:
                continue
            label = f'[ELEMENT {record["id"]}; TYPE {record["type"]}]'
            parts.append(label)
            offset += len(label)+1
            scopes.append({'element_id': record['id'], 'page': page,
                           'start': offset, 'stop': offset+len(record['content'])})
            parts.append(record['content'])
            offset += len(record['content'])+1
    return '\n'.join(parts), scopes


def compact_annotated_input(text, records, pages, input_sha256):
    if not isinstance(text, str) or sha(text) != input_sha256:
        raise ValueError('Original input hash mismatch')
    original_records = deepcopy(records)
    prefix, original_scopes = render(records, pages)
    boundary = prefix+'\n\n'+ANNOTATION_MARKER+'\n'
    if not text.startswith(boundary):
        raise ValueError('Source records do not reconstruct original input')
    suffix = text[len(prefix):]
    envelope = {'document': {'elements': [
        {'id': r['id'], 'type': r['type'], 'content': r['content'],
         'bbox': [{'page_id': r['physical_page']-1}]} for r in records]}}
    candidate, audit = compact_document(envelope)
    changed_records = deepcopy(records)
    restored_records = deepcopy(records)
    for entry in audit:
        if entry['status'] == 'compacted':
            index = entry['element_index']
            encoded = candidate['document']['elements'][index]['content']
            changed_records[index]['content'] = encoded
            restored_records[index]['content'] = restore_tables(json.loads(encoded))
    candidate_prefix, candidate_scopes = render(changed_records, pages)
    restored_prefix, _ = render(restored_records, pages)
    if restored_records != records or restored_prefix+suffix != text or records != original_records:
        raise ValueError('Original source/annotation round trip failed')
    compact = candidate_prefix+suffix
    if len(compact.encode()) > len(text.encode()):
        raise ValueError('Complete candidate input grew')
    return compact, {
        'original_input_sha256': sha(text), 'candidate_input_sha256': sha(compact),
        'annotation_sha256': sha(suffix), 'annotation_characters': len(suffix),
        'original_characters': len(text), 'candidate_characters': len(compact),
        'original_bytes': len(text.encode()), 'candidate_bytes': len(compact.encode()),
        'source_element_count': len(records), 'physical_pages': list(pages),
        'table_audit': audit, 'original_scopes': original_scopes, 'candidate_scopes': candidate_scopes,
        'source_records_unchanged': records == original_records,
        'whole_input_round_trip_exact': restored_prefix+suffix == text,
        'annotation_unchanged': compact[len(candidate_prefix):] == suffix,
        'quality_accepted': False,
    }
