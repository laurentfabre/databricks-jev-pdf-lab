"""Reversible HTML table wrappers; not an extraction or semantic validator.

Unsupported markup stays unchanged. Cells retain raw inner HTML; no entity,
whitespace, number, unit, attribute, icon or relationship normalization occurs.
"""
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
import re

FORMAT = 'table-rows-inner-html-v1'


def serialized(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class StrictTables(HTMLParser):
    INLINE = {'b', 'strong', 'i', 'em', 'span', 'sup', 'sub', 'u', 'small', 'mark'}

    def __init__(self, original):
        super().__init__(convert_charrefs=False)
        self.original = original
        self.line_starts = [0] + [m.end() for m in re.finditer('\n', original)]
        self.stack, self.tables = [], []
        self.cell = None

    def raw_end(self):
        line, column = self.getpos()
        start = self.line_starts[line-1] + column
        end = self.original.find('>', start)
        if end < 0:
            raise ValueError('Incomplete closing tag')
        return self.original[start:end+1]

    def append_inner(self, value):
        if self.cell is None:
            raise ValueError('Text or unsupported whitespace outside a cell')
        self.cell['parts'].append(value)

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text()
        if tag == 'table' and not self.stack and raw == '<table>':
            self.tables.append([])
        elif tag == 'tr' and self.stack == ['table'] and raw == '<tr>':
            self.tables[-1].append([])
        elif tag in ('td', 'th') and self.stack == ['table', 'tr']:
            self.cell = {'tag': tag, 'open': raw, 'parts': []}
        elif self.cell is not None and tag in self.INLINE | {'br'}:
            self.append_inner(raw)
            if tag == 'br':
                return
        else:
            raise ValueError('Unsupported table structure or opening tag')
        self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if self.cell is None or tag != 'br':
            raise ValueError('Unsupported self-closing tag')
        self.append_inner(self.get_starttag_text())

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise ValueError('Unbalanced table or inline markup')
        raw = self.raw_end()
        if tag in ('table', 'tr', 'td', 'th'):
            if raw != f'</{tag}>':
                raise ValueError('Noncanonical structural closing tag')
            if tag in ('td', 'th'):
                inner = ''.join(self.cell['parts'])
                opening = self.cell['open']
                if opening == '<td>':
                    cell = inner
                elif opening == '<th>':
                    cell = {'th': inner}
                else:
                    cell = {'open': opening, 'html': inner}
                self.tables[-1][-1].append(cell)
                self.cell = None
        else:
            self.append_inner(raw)
        self.stack.pop()

    def handle_data(self, value):
        if value:
            self.append_inner(value)

    def handle_entityref(self, name):
        self.append_inner('&' + name + ';')

    def handle_charref(self, name):
        self.append_inner('&#' + name + ';')

    def handle_comment(self, data):
        raise ValueError('Comments require original HTML')

    def handle_decl(self, decl):
        raise ValueError('Declarations require original HTML')

    def handle_pi(self, data):
        raise ValueError('Processing instructions require original HTML')

    def unknown_decl(self, data):
        raise ValueError('Unknown declarations require original HTML')


def restore_tables(packet):
    if not isinstance(packet, dict) or set(packet) != {'format', 'tables'} or packet['format'] != FORMAT:
        raise ValueError('Invalid compact table format')
    if not isinstance(packet['tables'], list) or not packet['tables']:
        raise ValueError('Missing table list')
    out = []
    for table in packet['tables']:
        if not isinstance(table, list):
            raise ValueError('Invalid rows')
        out.append('<table>')
        for row in table:
            if not isinstance(row, list):
                raise ValueError('Invalid cells')
            out.append('<tr>')
            for cell in row:
                if isinstance(cell, str):
                    opening, inner, tag = '<td>', cell, 'td'
                elif isinstance(cell, dict) and set(cell) == {'th'} and isinstance(cell['th'], str):
                    opening, inner, tag = '<th>', cell['th'], 'th'
                elif (isinstance(cell, dict) and set(cell) == {'open', 'html'}
                      and isinstance(cell['open'], str) and isinstance(cell['html'], str)):
                    opening, inner = cell['open'], cell['html']
                    match = re.match(r'<(td|th)(?=\s|>)', opening, re.I)
                    if not match or not opening.endswith('>'):
                        raise ValueError('Invalid cell opening')
                    tag = match[1].lower()
                else:
                    raise ValueError('Invalid cell')
                out.append(opening + inner + f'</{tag}>')
            out.append('</tr>')
        out.append('</table>')
    return ''.join(out)


def pack_tables(content):
    if not isinstance(content, str):
        raise ValueError('Table content must be a string')
    parser = StrictTables(content)
    parser.feed(content)
    parser.close()
    if parser.stack or parser.cell is not None or not parser.tables:
        raise ValueError('Incomplete or missing table')
    packet = {'format': FORMAT, 'tables': parser.tables}
    if restore_tables(packet) != content:
        raise ValueError('Exact round trip failed; preserve original')
    return packet


def compact_document(original):
    """Keep whole parser envelope and content; transform only smaller tables."""
    candidate, restored = deepcopy(original), deepcopy(original)
    audit = []
    for index, element in enumerate(original['document']['elements']):
        if element.get('type') != 'table':
            continue
        raw = element.get('content')
        record = {'element_index': index, 'element_id': element.get('id'),
                  'page_ids': [b['page_id'] for b in element.get('bbox', [])],
                  'status': 'original', 'quality_accepted': False}
        if isinstance(raw, str):
            record.update(original_sha256=digest(raw), original_characters=len(raw),
                          original_bytes=len(raw.encode('utf-8')))
        try:
            packet = pack_tables(raw)
            encoded = serialized(packet)
            decoded = restore_tables(json.loads(encoded))
            if decoded != raw:
                raise ValueError('Serialized round trip failed')
            record.update(round_trip_exact=True, table_count=len(packet['tables']),
                          row_count=sum(len(t) for t in packet['tables']),
                          cell_count=sum(len(r) for t in packet['tables'] for r in t),
                          candidate_characters=len(encoded), candidate_bytes=len(encoded.encode('utf-8')),
                          candidate_sha256=digest(encoded))
            if (record['candidate_bytes'] < record['original_bytes']
                    and len(serialized(encoded).encode('utf-8')) < len(serialized(raw).encode('utf-8'))):
                candidate['document']['elements'][index]['content'] = encoded
                restored['document']['elements'][index]['content'] = decoded
                record['status'] = 'compacted'
            else:
                record['status'] = 'original_not_smaller'
        except ValueError as error:
            record.update(status='original_unsupported', error=str(error), round_trip_exact=None)
        audit.append(record)
    if restored != original:
        raise ValueError('Whole-document round trip failed')
    # Verify restoration from the actual candidate, not just the per-cell intermediates.
    independent = deepcopy(candidate)
    for record in audit:
        if record['status'] == 'compacted':
            element = independent['document']['elements'][record['element_index']]
            element['content'] = restore_tables(json.loads(element['content']))
    if independent != original:
        raise ValueError('Candidate envelope changed')
    return candidate, audit
