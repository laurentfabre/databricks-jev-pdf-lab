"""Compile exact span recipes; inspect preservation, never certify semantics.

No I/O, models, or document reassembly. Local tests use fabricated text only.
Real transforms execute in the approved SQL workspace. Inspection compares
retained artifacts without rerunning their transformation.
"""
import hashlib
import re


def need(condition, message):
    if not condition:
        raise ValueError(message)


def validate(plan):
    n = plan.get('source_characters')
    need(type(n) is int and n > 0, 'Positive source character count required')
    repeated = plan.get('repeated_ranges')
    need(isinstance(repeated, list), 'Explicit repeated ranges required')
    spans, edges = [], {0, n}
    for pair in repeated:
        need(isinstance(pair, list) and len(pair) == 2, 'Invalid repeated interval')
        a, b = pair
        need(type(a) is int and type(b) is int and 0 <= a < b <= n, 'Invalid repeated bounds')
        need(not any(a < d and c < b for c,d in spans), 'Overlapping repeated ranges')
        spans.append((a,b)); edges.update((a,b))
    pieces = plan.get('pieces')
    need(isinstance(pieces, list) and pieces, 'Nonempty recipe required')
    ranges, mapping, cursor = [], [], 0
    for piece in pieces:
        need(isinstance(piece, dict), 'Invalid piece')
        if set(piece) == {'separator'}:
            need(piece['separator'] == '\n', 'Only a newline separator is permitted')
            mapping.append({'start':cursor,'stop':cursor+1,'origin':'assembly_separator'})
            cursor += 1
        else:
            need(set(piece) == {'start','stop'}, 'Unexpected source piece fields')
            a,b = piece['start'],piece['stop']
            need(type(a) is int and type(b) is int and 0 <= a < b <= n, 'Invalid source bounds')
            ranges.append((a,b)); edges.update((a,b))
            mapping.append({'start':cursor,'stop':cursor+b-a,'source_start':a,'source_stop':b})
            cursor += b-a
    edges = sorted(edges)
    for a,b in zip(edges,edges[1:]):
        expected = 2 if any(c <= a and b <= d for c,d in spans) else 1
        count = sum(c <= a and b <= d for c,d in ranges)
        need(count == expected, 'Unaccounted gap or repetition')
    need(cursor == plan.get('expected_characters'), 'Wrong expected output length')
    return mapping


def sql_expression(plan, column='input_text'):
    validate(plan)
    need(isinstance(column, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', column),
         'Only an unqualified SQL column identifier is permitted')
    pieces = ['char(10)' if 'separator' in p else
              f"substring({column},{p['start']+1},{p['stop']-p['start']})"
              for p in plan['pieces']]
    return 'concat(' + ','.join(pieces) + ')'


def inspect_preservation(source, candidate, plan):
    mapping = validate(plan)
    need(isinstance(source, str) and isinstance(candidate, str), 'Text inputs required')
    need(hashlib.sha256(source.encode()).hexdigest() == plan.get('source_sha256'), 'Stale source')
    need(len(source) == plan['source_characters'], 'Source length mismatch')
    need(len(source.encode()) == plan.get('source_bytes'), 'Source byte length mismatch')
    need(len(candidate) == plan['expected_characters'], 'Candidate length mismatch')
    need(len(candidate.encode()) == plan.get('expected_bytes'), 'Candidate byte length mismatch')
    for row in mapping:
        expected = '\n' if row.get('origin') == 'assembly_separator' else source[row['source_start']:row['source_stop']]
        need(candidate[row['start']:row['stop']] == expected, 'Copied source slice changed')
    return {'candidate_sha256':hashlib.sha256(candidate.encode()).hexdigest(),
        'mapping':mapping, 'all_source_characters_preserved':True,
        'repeated_ranges':plan['repeated_ranges'], 'quality_accepted':False,
        'semantic_equivalence_proven':False}
