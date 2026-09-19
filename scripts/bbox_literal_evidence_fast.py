"""E45 lookup-only version of frozen E44; outputs and semantic limits unchanged."""
from collections import Counter, defaultdict
from copy import deepcopy
import re

from bbox_literal_evidence import fragments, normalized
from bbox_page_provenance import UnsupportedResponse, bindings, box_key, digest, need
from schema_field_audit import MISSING, occupancy, schema_paths
from quality_gates import unwrap
from literal_matchers import make_matcher


def audit(raw, parsed, schema, contract, *, strategy='literal_find'):
    contains = make_matcher(strategy)
    original = bindings(raw, parsed, schema)
    need(contract.get('bindings') == original, 'Stale input/schema binding')
    need(contract.get('page_basis') == 'full_original_pdf_zero_based', 'Unsupported page basis')
    need(re.fullmatch('[0-9a-f]{64}', contract.get('source_sha256', '')) is not None,
         'Original source hash required')
    n = contract.get('physical_pages')
    need(type(n) is int and n > 0, 'Invalid page count')
    need(not parsed.get('error_status') and parsed.get('metadata', {}).get('version') == '2.0',
         'Successful parser2.0 required')
    need([p.get('id') for p in parsed['document']['pages']] == list(range(n))
         and all(type(p.get('id')) is int for p in parsed['document']['pages']), 'Incomplete original pages')
    meta = raw.get('metadata') or {}
    if (raw.get('error_message') or meta.get('mode') != 'precision' or meta.get('version') != '2.1'
            or meta.get('chunk_type') != 'bbox' or 'derivation' in raw
            or not isinstance(raw.get('response'), dict)):
        raise UnsupportedResponse('Successful unchanged Precision2.1 BBOX response required')
    page_ids = set(range(n))
    sources, geometry = [], defaultdict(set)
    ids = set()
    for index, element in enumerate(parsed['document']['elements']):
        eid = element.get('id')
        need(type(eid) is int and eid >= 0 and eid not in ids, 'Invalid/duplicate element ID')
        ids.add(eid)
        for box in element.get('bbox', []): geometry[box_key(box, page_ids)].add(index)
        source = {'index': index, 'element': deepcopy(element), 'element_sha256': digest(element)}
        try:
            source['fragments'] = fragments(element)
            source['projection_status'] = 'available'
        except (ValueError, TypeError) as error:
            source.update(fragments=[], projection_status='unknown', reason=str(error))
        sources.append(source)
    citations = {}
    try:
        pages = [p['id'] for p in meta['pages']]
        need(all(type(p) is int and p in page_ids for p in pages) and len(set(pages)) == len(pages),
             'Invalid citation page subset')
        for cite in meta['citations']:
            cid = cite['id']
            need(type(cid) is int and cid >= 0 and cid not in citations, 'Invalid/duplicate citation ID')
            need(isinstance(cite.get('bbox'), list) and cite['bbox'], 'Empty citation geometry')
            boxes = [box_key(b, page_ids) for b in cite['bbox']]
            need(all(b[0] in pages for b in boxes), 'Cited page missing from metadata')
            mapped, problems = set(), []
            for box in boxes:
                found = geometry.get(box, set())
                if len(found) != 1: problems.append('ambiguous_geometry' if found else 'unknown_geometry')
                else: mapped.update(found)
            citations[cid] = {'element_indices': sorted(mapped), 'problems': problems}
    except (KeyError, TypeError, ValueError) as error:
        raise UnsupportedResponse(str(error)) from error
    # Precompute only whitespace projections; never merge cells/elements.
    content = [(s['index'], f['cell'], f['text'], normalized(f['text']))
               for s in sources for f in s['fragments']]
    descriptions = [(s['index'], normalized(s['element']['description'])) for s in sources
                    if isinstance(s['element'].get('description'), str)]
    unknown_sources = [s['index'] for s in sources if s['projection_status'] == 'unknown']
    rows, extras, groups = [], [], defaultdict(list)
    literal_cache = {}

    def check_string(field, row):
        value = field['value']
        if value not in literal_cache:
            norm = normalized(value)
            exact = [{'element_index': i, 'cell': cell} for i, cell, text, _ in content if contains(text, value)]
            whitespace = [{'element_index': i, 'cell': cell} for i, cell, _, text in content if contains(text, norm)]
            desc = [i for i, text in descriptions if contains(text, norm)]
            literal_cache[value] = exact, whitespace, desc
        exact, whitespace, desc = literal_cache[value]
        row.update(global_exact_hits=deepcopy(exact), global_whitespace_hits=deepcopy(whitespace),
                   generated_description_hits=desc, global_projection_unknown=unknown_sources)
        cids = field.get('citation_ids')
        valid = (isinstance(cids, list) and cids and all(type(c) is int and c >= 0 for c in cids)
                 and len(set(cids)) == len(cids))
        problems, indices = [], set()
        if not valid: problems.append('missing_or_invalid_field_citations')
        else:
            for cid in cids:
                if cid not in citations: problems.append('unknown_citation_id')
                else:
                    problems.extend(citations[cid]['problems'])
                    indices.update(citations[cid]['element_indices'])
        row.update(citation_ids=deepcopy(cids), cited_element_indices=sorted(indices), citation_problems=problems)
        own = [h for h in whitespace if h['element_index'] in indices]
        row['own_content_hits'] = own
        if problems: status = 'citation_binding_unknown'
        elif own: status = 'literal_present_in_cited_content'
        elif set(unknown_sources) & indices: status = 'cited_projection_unknown'
        elif whitespace: status = 'literal_only_elsewhere_in_content'
        elif desc: status = 'literal_only_in_generated_description'
        elif unknown_sources: status = 'not_found_in_available_content_other_projections_unknown'
        else: status = 'literal_not_found_in_retained_content'
        row['literal_status'] = status
        row['own_exact_hits'] = [h for h in exact if h['element_index'] in indices]
        if not problems:
            groups[tuple(sorted(indices))].append(deepcopy(row['path']))

    def visit(field, spec, path, template):
        value = MISSING if field is MISSING else unwrap(field)
        kind = spec['type']
        container = field['value'] if isinstance(field, dict) and 'value' in field else field
        state = occupancy(value, kind)
        row = {'path': path, 'schema_path': template, 'expected_type': kind, 'occupancy': state,
               'semantic_status': 'not_evaluated', 'accepted': False, 'source_presence': 'unknown'}
        if kind in ('array', 'object'):
            if isinstance(value, (list, dict)): row['length'] = len(value)
        elif field is not MISSING:
            row['field'] = deepcopy(field)
        rows.append(row)
        if kind == 'string' and isinstance(value, str) and value.strip():
            if not isinstance(field, dict) or 'value' not in field:
                row['literal_status'] = 'scalar_wrapper_unknown'
            else: check_string(field, row)
        if kind == 'object' and isinstance(container, dict):
            extras.extend(path+[key] for key in sorted(set(container)-set(spec['properties'])))
            for name, child in spec['properties'].items():
                visit(container.get(name, MISSING), child, path+[name], template+'.'+name)
        elif kind == 'array' and isinstance(container, list):
            for i, child in enumerate(container): visit(child, spec['items'], path+[i], template+'[]')

    response = raw['response']
    extras.extend([[key] for key in sorted(set(response)-set(schema))])
    for name, spec in schema.items(): visit(response.get(name, MISSING), spec, [name], name)
    all_paths = schema_paths(schema)
    basis_rows = [r for r in rows if r['schema_path'] == 'items[].prices[].basis']
    all_used = set(i for key in groups for i in key)
    content_bytes = lambda i: len((sources[i]['element'].get('content') or '').encode())
    repeated = sum(sum(content_bytes(i) for i in key)*len(paths) for key, paths in groups.items())
    need(bindings(raw, parsed, schema) == original, 'Input mutation')
    return {'bindings': original, 'contract': deepcopy(contract), 'sources': sources, 'rows': rows,
        'groups': [{'element_indices': list(key), 'field_paths': paths} for key, paths in sorted(groups.items())],
        'schema_coverage': [{'schema_path': p, 'concrete_slots': sum(r['schema_path'] == p for r in rows)} for p in all_paths],
        'unexpected_paths': extras,
        'counts': {'concrete_slots': len(rows), 'schema_paths': len(all_paths),
            'literal_status': dict(Counter(r['literal_status'] for r in rows if 'literal_status' in r)),
            'occupancy': dict(Counter(r['occupancy'] for r in rows)),
            'price_basis_slots': len(basis_rows),
            'price_basis_literal_status': dict(Counter(r['literal_status'] for r in basis_rows if 'literal_status' in r)),
            'projection_unknown_elements': len(unknown_sources), 'shared_evidence_groups': len(groups),
            'grouped_string_fields': sum(len(v) for v in groups.values()),
            'repeated_cited_content_bytes': repeated,
            'unique_cited_content_bytes': sum(content_bytes(i) for i in all_used)},
        'raw_unchanged': True, 'quality_accepted': False, 'new_ai_calls': 0,
        'safe_to_skip_semantic_review': False, 'repairs_applied': 0,
        'limits': ['Literal hits do not prove support, ownership, complete inventory or safety.',
            'Misses include paraphrases, translation, formatting, missing parser evidence and genuine inventions.',
            'Descriptions are generated interpretations, not independently verified transcription.',
            'Table hits are cell-local but do not resolve the owning item or cross-cell relationships.',
            'Repeated/unique content bytes exclude requests, context, outputs and orchestration; not token savings.',
            'No field, citation or result is repaired or accepted.']}
