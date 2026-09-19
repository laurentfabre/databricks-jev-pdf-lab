"""Strict literal coverage by cited character intervals; not semantic validation.

Adjacent/overlapping citations form a union. Uncited gaps never disappear.
No inference, document IO, response mutation, or implicit citation repair.
"""


def citation_intervals(field, metadata, content_length):
    if type(content_length) is not int or content_length < 0:
        raise ValueError('Invalid content length')
    if not isinstance(metadata, dict) or metadata.get('chunk_type') != 'span':
        raise ValueError('Expected span metadata')
    citations = metadata.get('citations')
    ids = field.get('citation_ids') if isinstance(field, dict) else None
    if not isinstance(citations, list) or not isinstance(ids, list) or not ids:
        raise ValueError('Missing citations')
    lookup = {}
    for citation in citations:
        if not isinstance(citation, dict) or type(citation.get('id')) is not int:
            raise ValueError('Invalid citation ID')
        ident = citation['id']
        if ident in lookup:
            raise ValueError('Duplicate citation ID')
        lookup[ident] = citation
    intervals = []
    for ident in ids:
        if type(ident) is not int or ident not in lookup:
            raise ValueError('Unknown or invalid field citation ID')
        start, stop = lookup[ident].get('start'), lookup[ident].get('stop')
        if type(start) is not int or type(stop) is not int or not 0 <= start < stop <= content_length:
            raise ValueError('Invalid citation bounds')
        intervals.append((start, stop))
    merged = []
    for start, stop in sorted(set(intervals)):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], stop)
        else:
            merged.append([start, stop])
    return merged


def literal_support(field, metadata, content, literal, scopes=None):
    """Return exact covered occurrences, not a correctness judgment.

    Scopes limit matching to original source regions. Every matched character
    must be both in one scope and in the cited interval union.
    """
    if not isinstance(content, str) or not isinstance(literal, str) or not literal:
        return {'valid': False, 'supported': False, 'error': 'Invalid content/literal'}
    try:
        intervals = citation_intervals(field, metadata, len(content))
        scopes = [[0, len(content)]] if scopes is None else scopes
        if not isinstance(scopes, list) or not scopes:
            raise ValueError('Missing source scope')
        for scope in scopes:
            if (not isinstance(scope, (list, tuple)) or len(scope) != 2
                    or any(type(x) is not int for x in scope)
                    or not 0 <= scope[0] < scope[1] <= len(content)):
                raise ValueError('Invalid source scope')
        occurrences = []
        cursor = 0
        while True:
            start = content.find(literal, cursor)
            if start < 0:
                break
            stop = start + len(literal)
            if (any(a <= start and stop <= b for a, b in scopes)
                    and any(a <= start and stop <= b for a, b in intervals)):
                occurrences.append([start, stop])
            cursor = start + 1
        return {'valid': True, 'supported': bool(occurrences),
                'intervals': intervals, 'occurrences': occurrences}
    except ValueError as error:
        return {'valid': False, 'supported': False, 'error': str(error)}
