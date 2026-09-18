"""Deterministic mixed-page assembly; recommendations do not authorize dispatch."""
from collections import Counter, defaultdict
import hashlib
import math


def native_regions(words, width, split):
    """Order intact words by native line inside explicit, reviewed page regions."""
    if not isinstance(width, (int, float)) or not math.isfinite(width) or width <= 0:
        raise ValueError('Invalid page width')
    groups = defaultdict(list)
    for index, word in enumerate(words):
        if len(word) != 8 or not isinstance(word[4], str) or not word[4]:
            raise ValueError('Invalid word record')
        x0, y0, x1, y1 = word[:4]
        if not all(isinstance(n, (int, float)) and math.isfinite(n) for n in word[:4]):
            raise ValueError('Invalid word coordinates')
        if x1 < x0 or y1 < y0 or x0 < 0 or x1 > width:
            raise ValueError('Word outside page bounds')
        if split and x0 < width / 2 < x1:
            raise ValueError('Word crosses reviewed region boundary')
        region = int(split and x0 >= width / 2)
        groups[(region, word[5], word[6])].append((index, word))
    output, order = [], []
    for region in range(2 if split else 1):
        lines = [v for k, v in groups.items() if k[0] == region]
        lines.sort(key=lambda line: (min(w[1][1] for w in line), min(w[1][0] for w in line)))
        text_lines = []
        for line in lines:
            line.sort(key=lambda w: (w[1][0], w[1][7], w[0]))
            text_lines.append(' '.join(w[1][4] for w in line))
            order.extend(w[0] for w in line)
        output.append(f'[REGION {region + 1}]\n' + '\n'.join(text_lines))
    if sorted(order) != list(range(len(words))):
        raise ValueError('Word coverage failure')
    assert Counter(words[i][4] for i in order) == Counter(w[4] for w in words)
    return '\n\n'.join(output), {'word_count': len(words), 'word_order': order,
        'word_multiset_equal': True, 'regions': 2 if split else 1}


def assemble(pages, expected_pages):
    if not pages or [p['page'] for p in pages] != list(range(1, expected_pages + 1)):
        raise ValueError('All physical pages must occur once, in order')
    parts, audit, offset = [], [], 0
    for page in pages:
        n, method = page['page'], page['method']
        if method == 'native_layout':
            content, check = native_regions(page['words'], page['width'], page['split'])
            if not page['words']:
                raise ValueError('Empty native page requires visual review')
        elif method == 'retained_managed':
            if not page.get('reviewed_image_sha256'):
                raise ValueError('Fallback page needs a bound visual review')
            elements = page['elements']
            if any(not e.get('bbox') or any(b['page_id'] != n - 1 for b in e['bbox']) for e in elements):
                raise ValueError('Cross-page parser element requires explicit handling')
            content = '\n'.join(f"[ELEMENT {e['id']} {e['type']}]\n{e.get('content') or ''}"
                                for e in elements)
            if not any((e.get('content') or '').strip() for e in elements) and not page.get('reviewed_no_required_text'):
                raise ValueError('Unexplained empty fallback')
            check = {'element_ids': [e['id'] for e in elements],
                'reviewed_image_sha256': page['reviewed_image_sha256'],
                'reviewed_no_required_text': page.get('reviewed_no_required_text', False)}
        else:
            raise ValueError('Unknown page method')
        part = f'[SOURCE PAGE {n}]\n' + content
        if '[SOURCE PAGE ' in content:
            raise ValueError('Source contains reserved page label')
        parts.append(part)
        audit.append({'physical_page': n, 'method': method, 'start': offset,
            'end': offset + len(part), 'content_sha256': hashlib.sha256(content.encode()).hexdigest(), **check})
        offset += len(part) + 2
    text = '\n\n'.join(parts)
    return text, audit
