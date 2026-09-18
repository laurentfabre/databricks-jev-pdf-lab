"""Versioned compact-request transport. No changes to historical transport/code."""
import datetime as dt
import hashlib
import json
import pathlib
import time
from jev_compact_router import validated_request
from jev_router import request_hash
from jev_transport import post_once, validate_usage
from jev_response_policy_v2 import review_inconsistent_choices


def run_once(request, output_directory, secret, sender=post_once):
    payload = validated_request(request)
    digest = request_hash(request)
    directory = pathlib.Path(output_directory)/digest
    directory.mkdir(parents=True, exist_ok=True)
    response_path, start_path = directory/'response.json', directory/'started.json'
    if response_path.exists():
        envelope = json.loads(response_path.read_text())
        if envelope['request_sha256'] != digest:
            raise ValueError('Persisted request identity mismatch')
        if envelope['http_status'] != 200:
            raise RuntimeError('Prior HTTP failure retained; no automatic replay')
        result = review_inconsistent_choices(request, envelope['response'])
        validate_usage(envelope['response'])
        return result | {'http_seconds':envelope['http_seconds'],'reused':True}
    if start_path.exists():
        raise RuntimeError('Prior attempt has no response; outcome unknown, no automatic replay')
    with start_path.open('x') as stream:
        json.dump({'request_sha256':digest,'model':request['model'],
            'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'request_bytes':len(payload),'automatic_retries':0}, stream, indent=2)
    (directory/'request.json').write_bytes(payload)
    started = time.perf_counter()
    try:
        status, raw = sender(payload, secret)
    except Exception as error:
        (directory/'failure.json').write_text(json.dumps({'request_sha256':digest,
            'exception_class':type(error).__name__,'outcome':'unknown',
            'automatic_retry_allowed':False,'elapsed_seconds':time.perf_counter()-started},indent=2))
        raise RuntimeError('Jev transport failed; outcome unknown; no replay') from None
    elapsed = time.perf_counter()-started
    clean = raw.decode('utf-8', errors='replace').replace(secret,'[REDACTED]')
    try:
        response = json.loads(clean)
    except ValueError:
        response = {'invalid_json':True,'body_sha256':hashlib.sha256(raw).hexdigest()}
    envelope = {'request_sha256':digest,'http_status':status,'http_seconds':elapsed,
        'completed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'response':response}
    response_path.write_text(json.dumps(envelope,indent=2))
    if status != 200:
        raise RuntimeError(f'Jev HTTP {status}; response retained, no automatic retry')
    result = review_inconsistent_choices(request,response)
    validate_usage(response)
    (directory/'recommendations.json').write_text(json.dumps(result,indent=2))
    return result | {'http_seconds':elapsed,'reused':False}
