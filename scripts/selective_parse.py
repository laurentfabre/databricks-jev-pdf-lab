"""Lossless saved-evidence rehearsal, not a production routing/acceptance gate."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import re
import unicodedata

NATIVE = {'native_text_precision', 'native_layout_precision'}
METHODS = NATIVE | {'managed_parse_precision', 'visual_review'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def page_range(pages, count):
    if type(count) is not int or count <= 0:
        raise ValueError('Invalid document page count')
    if any(type(p) is not int or not 1 <= p <= count for p in pages) or len(pages) != len(set(pages)):
        raise ValueError('Duplicate or invalid physical page')
    pages = sorted(pages)
    groups = []
    for page in pages:
        if groups and groups[-1][-1]+1 == page:
            groups[-1].append(page)
        else:
            groups.append([page])
    return ','.join(str(g[0]) if len(g) == 1 else f'{g[0]}-{g[-1]}' for g in groups)


def parser_inventory(parsed, count):
    if parsed.get('error_status'):
        raise ValueError('Parser has retained errors')
    pages = parsed['document']['pages']
    ids = [p['id'] for p in pages]
    if any(type(p) is not int for p in ids) or sorted(ids) != list(range(count)):
        raise ValueError('Parser page IDs are not exactly the physical inventory')
    elements = parsed['document']['elements']
    seen, by_page, location = set(), {p: [] for p in range(1, count+1)}, {}
    for index, element in enumerate(elements):
        identity = element['id']
        if type(identity) is not int or identity in seen:
            raise ValueError('Invalid or duplicate element ID')
        seen.add(identity)
        if element.get('content') is not None and not isinstance(element['content'], str):
            raise ValueError('Invalid managed content')
        if element.get('description') is not None and not isinstance(element['description'], str):
            raise ValueError('Invalid managed description')
        page_ids = [box['page_id'] for box in element.get('bbox', [])]
        if any(type(p) is not int or not 0 <= p < count for p in page_ids):
            raise ValueError('Managed element has out-of-range page ID')
        physical = sorted({p+1 for p in page_ids})
        location[index] = physical
        for p in physical:
            by_page[p].append(index)
    return location, by_page


def discrepancy(native_text, elements):
    def words(value):
        return Counter(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', value).casefold()))
    content = '\n'.join(e.get('content') or '' for e in elements)
    native, managed = words(native_text), words(content)
    missing = managed-native
    reverse = native-managed
    native_numbers = Counter(re.findall(r'\d+(?:[.,]\d+)*', native_text))
    managed_numbers = Counter(re.findall(r'\d+(?:[.,]\d+)*', content))
    numbers = managed_numbers-native_numbers
    return {'managed_content_tokens': sum(managed.values()),
        'managed_tokens_not_in_native': sum(missing.values()),
        'native_tokens_not_in_managed': sum(reverse.values()),
        'managed_token_discrepancies': dict(sorted(missing.items())),
        'managed_numeric_lexemes_not_in_native': dict(sorted(numbers.items())),
        'table_elements': sum(e.get('type') == 'table' for e in elements),
        'figure_descriptions': sum(e.get('type') == 'figure' and bool(e.get('description')) for e in elements),
        'figure_description_characters': sum(len(e.get('description') or '') for e in elements if e.get('type') == 'figure'),
        'semantic_correctness': 'not_evaluated'}


def rehearse(doc_id, native_pages, parsed, routes):
    count = len(native_pages)
    if count == 0 or [p['page'] for p in native_pages] != list(range(1, count+1)):
        raise ValueError('Native pages must occur once in physical order')
    if set(routes) != set(range(1, count+1)) or any(m not in METHODS for m in routes.values()):
        raise ValueError('Routes must cover every page with known methods')
    if any(not isinstance(p.get('text'), str) or not isinstance(p.get('words'), list) for p in native_pages):
        raise ValueError('Missing native text or geometry')
    location, by_page = parser_inventory(parsed, count)
    elements = parsed['document']['elements']
    managed = {p for p, method in routes.items() if method not in NATIVE}
    vetoes = []
    if doc_id == 8 and 12 in routes and routes[12] in NATIVE:
        managed.add(12)
        vetoes.append({'physical_page': 12, 'reason': 'known_failing_whole_page_native_implementation'})
    initial = set(managed)
    while True:
        updated = managed | {p for pages in location.values() if managed.intersection(pages) for p in pages}
        if updated == managed:
            break
        managed = updated
    selected = [i for i, pages in location.items() if not pages or managed.intersection(pages)]
    selected_set = set(selected)
    included = [deepcopy(elements[i]) for i in selected]
    inventory, comparisons = [], []
    for page in native_pages:
        n = page['page']
        effective = 'managed_parse_precision' if n in managed else routes[n]
        record = {'physical_page': n, 'effective_method': effective}
        if n in managed:
            record['element_ids'] = [elements[i]['id'] for i in by_page[n]]
            assert all(i in selected_set for i in by_page[n])
        else:
            record['native'] = deepcopy(page)
        inventory.append(record)
        comparisons.append({'physical_page': n, 'proposed_method': routes[n],
            'effective_method': effective, 'original_review_unresolved': routes[n] == 'visual_review',
            **discrepancy(page['text'], [elements[i] for i in by_page[n]])})
    bundle = {'physical_page_count': count, 'pages': inventory, 'managed_elements': included,
        'managed_parser_metadata': deepcopy(parsed.get('metadata')),
        'managed_page_metadata': [deepcopy(p) for p in parsed['document']['pages'] if p['id']+1 in managed],
        'unlocated_element_ids': [elements[i]['id'] for i in selected if not location[i]],
        'scope': 'Saved-evidence rehearsal only; native views are retained alternatives, not both dispatched'}
    assert all(element == elements[index] for element, index in zip(included, selected))
    return {'bundle': bundle, 'bundle_sha256': digest(bundle), 'comparisons': comparisons,
        'proposed_native_pages': sorted(p for p, method in routes.items() if method in NATIVE),
        'managed_pages': sorted(managed), 'managed_page_range': page_range(list(managed), count),
        'native_pages': sorted(set(routes)-managed), 'cross_page_promotions': sorted(managed-initial),
        'vetoes': vetoes, 'review_pages': sorted(p for p, method in routes.items() if method == 'visual_review'),
        'managed_elements_retained': len(included), 'unlocated_elements': len(bundle['unlocated_element_ids']),
        'native_text_characters': sum(len(p['text']) for p in native_pages if p['page'] not in managed),
        'managed_content_characters': sum(len(e.get('content') or '') for e in included),
        'managed_description_characters': sum(len(e.get('description') or '') for e in included),
        'quality_accepted': False, 'new_ai_calls': 0}
