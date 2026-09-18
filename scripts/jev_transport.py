"""Single-attempt, hash-bound Jev transport; invoked only inside the approved Databricks workspace.

No auto-retries, redirects, extraction dispatch, or credential persistence.
An attempt without a retained response blocks replay because its outcome is unknown.
"""
import datetime as dt
import hashlib
import http.client
import json
import pathlib
import time

from jev_router import build_request, recommendations, request_hash


def validated_request(request):
    state = request['state']
    rebuilt = build_request(state['diagnostics'], state.get('document_context'))
    if request != rebuilt:
        raise ValueError('Payload differs from the strict metadata-only routing contract')
    return json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def validate_usage(response):
    usage = response.get('usage')
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                        for k in ('input_tokens', 'output_tokens')):
        raise ValueError('Missing/invalid service-reported token usage')
    return {k: usage[k] for k in ('input_tokens', 'output_tokens')}


def post_once(payload, secret):
    connection = http.client.HTTPSConnection('api.typesafe.ai', timeout=45)
    try:
        connection.request('POST', '/v1/systemone', body=payload,
                           headers={'Authorization': 'Bearer ' + secret, 'Content-Type': 'application/json'})
        response = connection.getresponse()
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('Response exceeds bounded limit')
        return response.status, body
    finally:
        connection.close()


def run_once(request, output_directory, secret, sender=post_once, response_policy=recommendations):
    payload = validated_request(request)
    digest = request_hash(request)
    directory = pathlib.Path(output_directory) / digest
    directory.mkdir(parents=True, exist_ok=True)
    response_path = directory / 'response.json'
    start_path = directory / 'started.json'
    if response_path.exists():
        envelope = json.loads(response_path.read_text())
        if envelope['request_sha256'] != digest:
            raise ValueError('Persisted request identity mismatch')
        if envelope['http_status'] != 200:
            raise RuntimeError('Prior HTTP failure retained; no automatic replay')
        result = response_policy(request, envelope['response'])
        validate_usage(envelope['response'])
        return result | {'http_seconds': envelope['http_seconds'], 'reused': True}
    if start_path.exists():
        raise RuntimeError('Prior attempt has no response; outcome unknown, no automatic replay')
    # Exclusive marker is written before the network call. A crash cannot authorize a retry.
    with start_path.open('x') as f:
        json.dump({'request_sha256': digest, 'model': request['model'],
                   'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'request_bytes': len(payload), 'automatic_retries': 0}, f, indent=2)
    (directory / 'request.json').write_bytes(payload)
    started = time.perf_counter()
    try:
        status, raw = sender(payload, secret)
    except Exception as error:
        (directory / 'failure.json').write_text(json.dumps({
            'request_sha256': digest, 'exception_class': type(error).__name__,
            'outcome': 'unknown', 'automatic_retry_allowed': False,
            'elapsed_seconds': time.perf_counter() - started}, indent=2))
        raise RuntimeError('Jev transport failed; retained unknown-outcome marker; no replay') from None
    elapsed = time.perf_counter() - started
    # Never retain a credential echoed by a remote error response.
    clean = raw.decode('utf-8', errors='replace').replace(secret, '[REDACTED]')
    try:
        response = json.loads(clean)
    except ValueError:
        response = {'invalid_json': True, 'body_sha256': hashlib.sha256(raw).hexdigest()}
    envelope = {'request_sha256': digest, 'http_status': status, 'http_seconds': elapsed,
                'completed_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'response': response}
    response_path.write_text(json.dumps(envelope, indent=2))
    if status != 200:
        raise RuntimeError(f'Jev HTTP {status}; response retained, no automatic retry')
    result = response_policy(request, response)
    validate_usage(response)
    (directory / 'recommendations.json').write_text(json.dumps(result, indent=2))
    return result | {'http_seconds': elapsed, 'reused': False}
