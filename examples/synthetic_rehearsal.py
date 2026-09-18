"""Offline illustration only: fabricated data, no PDFs, no inference."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from jev_router import build_request
from jev_compact_router import compact_request
from selective_parse import rehearse


def main():
    native = [{'page': p, 'text': f'Synthetic room {p}',
               'words': [[0, 0, 20, 10, 'Synthetic', 0, 0, 0]]}
              for p in range(1, 4)]
    parsed = {'document': {
        'pages': [{'id': p} for p in range(3)],
        'elements': [{'id': p, 'type': 'text', 'content': f'Synthetic room {p + 1}',
                      'bbox': [{'page_id': p, 'coord': [0, 0, 20, 10]}]}
                     for p in range(3)]},
        'metadata': {'version': '2.0'}, 'error_status': None}
    routes = {1: 'native_layout_precision', 2: 'visual_review', 3: 'native_layout_precision'}
    result = rehearse(1, native, parsed, routes)
    request = compact_request(build_request([
        {'scope': 'page', 'native_characters': 16, 'page_ordinal': p}
        for p in range(1, 4)]))
    assert result['managed_page_range'] == '2'
    assert result['review_pages'] == [2] and not result['quality_accepted']
    print(json.dumps({
        'fixture': 'synthetic; not a benchmark result',
        'physical_pages_retained': result['bundle']['physical_page_count'],
        'managed_page_range': result['managed_page_range'],
        'unresolved_review_pages': result['review_pages'],
        'request_prepared_but_not_sent': len(request['questions']),
        'source_text_in_router_state': False,
        'quality_accepted': result['quality_accepted'], 'ai_calls': 0,
    }, indent=2))


if __name__ == '__main__':
    main()
