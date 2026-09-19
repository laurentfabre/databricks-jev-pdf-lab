"""Find structural shared-row hypotheses, never semantic ownership or acceptance.

Supported grammar: one rectangular HTML table, paired name/euro-price columns,
optional same-column translations, a full-width heading, then unpriced rows.
All returned evidence uses exact source character spans. Layout alone cannot
distinguish preparation choices from notices or unrelated headings. No I/O.
"""
import hashlib
from html import unescape
import re
import unicodedata

from table_compaction import pack_tables


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def plain(html):
    return ' '.join(unescape(re.sub(r'<[^>]*>', ' ', html)).split())


def price(text):
    amount = r'(?:0|[1-9][0-9]*)(?:[.,][0-9]{2})?'
    return bool(re.fullmatch(r'(?:' + amount + r'\s*€|€\s*' + amount + r')', text))


def money_hint(text):
    return bool(re.search(r'[€$£¥]|\b(?:EUR|USD|GBP|CHF)\b', text))


def marker(text):
    inner = text[1:-1] if text.startswith('(') and text.endswith(')') else text
    return len(inner) == 1 and (inner.isalpha() or unicodedata.category(inner) in ('So', 'Sk'))


def cells(content):
    packet = pack_tables(content)
    if len(packet['tables']) != 1:
        raise ValueError('Multiple tables require separate scope')
    rows, cursor = [], len('<table>')
    for row in packet['tables'][0]:
        cursor += len('<tr>')
        values, column = [], 0
        for cell in row:
            if isinstance(cell, str):
                opening, inner = '<td>', cell
            elif 'th' in cell:
                opening, inner = '<th>', cell['th']
            else:
                opening, inner = cell['open'], cell['html']
            matched = re.fullmatch(r'<(td|th)(?:\s+colspan=(?:"([1-9][0-9]*)"|\'([1-9][0-9]*)\'|([1-9][0-9]*)))?>', opening)
            if not matched:
                raise ValueError('Unsupported cell attributes or row spans')
            span = int(next((v for v in matched.groups()[1:] if v is not None), '1'))
            if span > 64:
                raise ValueError('Unsupported table width')
            start = cursor + len(opening)
            stop = start + len(inner)
            if content[start:stop] != inner:
                raise ValueError('Source span mismatch')
            values.append({'column': column, 'colspan': span, 'start': start,
                           'stop': stop, 'html': inner, 'text': plain(inner)})
            cursor = stop + len('</' + matched[1] + '>')
            column += span
        if not values:
            raise ValueError('Empty row')
        rows.append(values)
        cursor += len('</tr>')
    if cursor + len('</table>') != len(content):
        raise ValueError('Table boundary mismatch')
    widths = {sum(c['colspan'] for c in row) for row in rows}
    if len(widths) != 1 or not 2 <= next(iter(widths)) <= 64:
        raise ValueError('Ragged or unsupported table width')
    return rows, next(iter(widths))


def owner_columns(row, width):
    if len(row) != width or width % 2 or any(c['colspan'] != 1 for c in row):
        return []
    owners = list(range(0, width, 2))
    if not all(row[c]['text'] and not money_hint(row[c]['text'])
               and price(row[c + 1]['text']) for c in owners):
        return []
    return owners


def scan(content):
    """Emit inspectable candidates only; a nonconditional heading also matches.

    Missing candidate means this narrow grammar did not find one, never that
    the document has no conditional facts. Text projections aid detection only;
    raw HTML spans are retained for copying and independent source review.
    """
    if not isinstance(content, str):
        raise ValueError('Expected source string')
    result = {'source_sha256': sha(content), 'status': 'scanned', 'candidates': [],
              'quality_accepted': False, 'semantic_ownership_established': False}
    try:
        rows, width = cells(content)
    except ValueError as error:
        return dict(result, status='unsupported', reason=str(error))
    result.update(row_count=len(rows), width=width)
    for heading_index, heading_row in enumerate(rows):
        if not (len(heading_row) == 1 and heading_row[0]['colspan'] == width
                and heading_row[0]['text'] and not money_hint(heading_row[0]['text'])):
            continue
        owner_index = heading_index - 1
        continuations = []
        owners = []
        while owner_index >= 0:
            row = rows[owner_index]
            owners = owner_columns(row, width)
            if owners:
                break
            # Translation row: one label for every possible paired owner,
            # no prices/markers/other-column text. Ambiguous rows stop search.
            if not (width % 2 == 0 and len(row) == width
                    and all(c['colspan'] == 1 for c in row)
                    and all(row[c]['text'] and not money_hint(row[c]['text'])
                            and not marker(row[c]['text']) and not row[c+1]['text']
                            for c in range(0, width, 2))):
                break
            continuations.append(owner_index)
            owner_index -= 1
        if not owners:
            continue
        children, boundary = [], {'row': len(rows), 'reason': 'table_end'}
        for child_index in range(heading_index + 1, len(rows)):
            row = rows[child_index]
            if any(money_hint(c['text']) for c in row):
                boundary = {'row': child_index, 'reason': 'price_or_currency_boundary'}
                break
            if len(row) == 1 and row[0]['colspan'] == width:
                boundary = {'row': child_index, 'reason': 'full_width_boundary'}
                break
            if not (len(row) == width and all(c['colspan'] == 1 for c in row)
                    and row[0]['text'] and not marker(row[0]['text'])
                    and all(not c['text'] or marker(c['text']) for c in row[1:])):
                boundary = {'row': child_index, 'reason': 'ambiguous_or_empty_row'}
                break
            children.append({'row': child_index, 'label': row[0],
                             'literal_markers': [c for c in row[1:] if c['text']]})
        if not children:
            continue
        result['candidates'].append({
            'heading_row': heading_index, 'heading': heading_row[0],
            'owner_row': owner_index,
            'owners': [{'column': c, 'label': rows[owner_index][c],
                        'price': rows[owner_index][c+1],
                        'continuations': [rows[r][c] for r in sorted(continuations)]} for c in owners],
            'children': children, 'boundary': boundary,
            'ownership_hypothesis': 'each_child_shared_by_each_preceding_priced_owner',
            'semantic_review_required': True, 'quality_accepted': False})
    return result
