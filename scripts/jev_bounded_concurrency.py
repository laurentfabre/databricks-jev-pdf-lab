"""Bounded metadata-only Jev scheduling; same payloads and response policy.

Round-level durable markers prohibit replay of an interrupted round. This is a
single-driver experiment runner, not a distributed exactly-once scheduler.
"""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import datetime as dt
import json
from pathlib import Path
import threading
import time

from jev_compact_router import validated_request
from jev_compact_transport import run_once
from jev_router import request_hash
from jev_transport import post_once


def page_recommendations(requests, mapping, result):
    """Bind by question ID, never by JSON object iteration/arrival order."""
    if len(requests) != len(mapping) or result['status'] != 'complete':
        raise ValueError('Complete matching inputs required')
    rows = {r['index']: r for r in result['rows']}
    if len(rows) != len(result['rows']) or set(rows) != set(range(len(requests))):
        raise ValueError('Missing or duplicated batch result')
    pages = []
    for index, (request, scope) in enumerate(zip(requests, mapping)):
        row = rows[index]
        if not row['ok'] or row['request_sha256'] != request_hash(request):
            raise ValueError('Wrong request result identity')
        recommendations = {r['question']: r for r in row['result']['recommendations']}
        if (len(recommendations) != len(row['result']['recommendations'])
                or set(recommendations) != set(request['questions'])
                or len(scope['physical_pages']) != len(request['questions'])):
            raise ValueError('Page/question cardinality mismatch')
        for ordinal, page in enumerate(scope['physical_pages']):
            question = f'route_{ordinal}'
            diagnostic = request['state']['diagnostics'][ordinal]
            if diagnostic.get('page_ordinal') != page:
                raise ValueError('Physical page mapping mismatch')
            recommendation = recommendations[question]
            if recommendation['dispatch_authorized'] or recommendation['quality_accepted']:
                raise ValueError('Recommendations cannot accept or dispatch')
            pages.append({'doc_id': scope['doc_id'], 'physical_page': page, **recommendation,
                'known_implementation_veto': scope['doc_id'] == 8 and page == 12
                    and recommendation['candidate_method'].startswith('native_')})
    if len({(p['doc_id'],p['physical_page']) for p in pages}) != len(pages):
        raise ValueError('Duplicate physical page')
    return pages


def run_round(requests, order, concurrency, directory, secret, sender=post_once):
    if type(concurrency) is not int or concurrency not in (1, 4):
        raise ValueError('Registered concurrency is one or four')
    if not isinstance(requests, list) or not 1 <= len(requests) <= 12:
        raise ValueError('One to twelve requests required')
    if (not isinstance(order, list) or any(type(i) is not int for i in order)
            or sorted(order) != list(range(len(requests)))):
        raise ValueError('Order must contain each input exactly once')
    if not isinstance(secret, str) or not secret:
        raise ValueError('Nonempty credential required')
    # Validate EVERY request before any request is allowed to start.
    payloads = [validated_request(r) for r in requests]
    hashes = [request_hash(r) for r in requests]
    if len(set(hashes)) != len(hashes) or sum(map(len, payloads)) > 600_000:
        raise ValueError('Duplicate inputs or oversized round')
    identity = {'request_sha256': hashes, 'order': order, 'concurrency': concurrency}
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    summary_path, start_path = directory/'round.json', directory/'round_started.json'
    if summary_path.exists():
        saved = json.loads(summary_path.read_text())
        if saved['identity'] != identity:
            raise ValueError('Saved round identity differs')
        return saved
    if start_path.exists():
        raise RuntimeError('Interrupted round: retain attempts; no automatic replay')
    with start_path.open('x') as stream:
        json.dump({'identity': identity, 'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'automatic_retries': 0}, stream, indent=2)
    lock = threading.Lock()
    active_http, maximum_http = 0, 0
    started = time.perf_counter()

    def worker(index):
        nonlocal active_http, maximum_http
        row = {'index': index, 'request_sha256': hashes[index],
               'worker_start_offset': time.perf_counter()-started}

        def measured_sender(payload, key):
            nonlocal active_http, maximum_http
            if payload != payloads[index]:
                raise ValueError('Wire payload changed')
            with lock:
                active_http += 1
                maximum_http = max(maximum_http, active_http)
                row['http_start_offset'] = time.perf_counter()-started
            try:
                return sender(payload, key)
            finally:
                with lock:
                    row['http_end_offset'] = time.perf_counter()-started
                    active_http -= 1

        try:
            row['result'] = run_once(requests[index], directory/'attempts', secret, measured_sender)
            # A newly registered round must not benchmark a cache read as inference.
            if row['result']['reused']:
                raise RuntimeError('Preexisting response in a new round')
            row['ok'] = True
        except Exception as error:
            row['ok'] = False
            row['error_class'] = type(error).__name__  # Never persist exception text/secret.
        row['worker_end_offset'] = time.perf_counter()-started
        return row

    rows, cursor, failed = [], 0, False
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending = set()
        while cursor < len(order) and len(pending) < concurrency:
            pending.add(pool.submit(worker, order[cursor]))
            cursor += 1
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            completed = [future.result() for future in done]
            rows.extend(completed)
            failed = failed or any(not row['ok'] for row in completed)
            # Drain in-flight requests after a failure; never schedule replacements.
            while not failed and cursor < len(order) and len(pending) < concurrency:
                pending.add(pool.submit(worker, order[cursor]))
                cursor += 1
    result = {'identity': identity, 'status': 'failed' if failed else 'complete',
              'dispatch_validate_persist_seconds': time.perf_counter()-started,
              'maximum_inflight_http': maximum_http, 'requests_started': len(rows),
              'unscheduled_indices': order[cursor:], 'rows': sorted(rows, key=lambda r: r['index']),
              'automatic_retries': 0, 'source_text_sent': False, 'downstream_calls': 0,
              'quality_accepted': False, 'end_to_end_savings_proven': False}
    with summary_path.open('x') as stream:
        json.dump(result, stream, indent=2)
    return result
