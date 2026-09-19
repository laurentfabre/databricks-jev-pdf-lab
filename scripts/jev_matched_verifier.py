"""E47 bounded, single-driver verifier experiment. Real execution: approved workspace only.

No retries, redirects, warmups, extraction or acceptance. The entire byte/hash
allowlist is validated before any send. Interrupted runs cannot be replayed.
Close-and-readback durable markers protect against platform notebook retries;
this is not a general distributed exactly-once implementation.
"""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import threading
import time

from shared_verifier_budget import CRITERIA, MODEL, encode, expand, question_id
from jev_transport import post_once, validate_usage

ORDER = ((1, 'single'), (1, 'shared24'), (2, 'shared24'), (2, 'single'))
MAX_ATTEMPTS = 100
MAX_BYTES = 2_362_388
CONCURRENCY = 4


def sha(data):
    return hashlib.sha256(data).hexdigest()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    body = encode(value)
    with Path(path).open('xb') as stream:
        stream.write(body)
    if Path(path).read_bytes() != body:
        raise RuntimeError('Persistence readback failed')


def strict_json(data):
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('Nonfinite JSON constant')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def validate_answer(request, response):
    if not isinstance(response, dict) or response.get('model') != MODEL:
        raise ValueError('Response model mismatch')
    answers = response.get('answers')
    if not isinstance(answers, dict) or set(answers) != set(request['questions']):
        raise ValueError('Response question set mismatch')
    def probability(value):
        return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
    for answer in answers.values():
        if not isinstance(answer, dict) or answer.get('type') != 'choice':
            raise ValueError('Expected Choice')
        probs = answer.get('probabilities')
        if (not isinstance(probs, dict) or set(probs) != set(CRITERIA)
                or not all(probability(p) for p in probs.values())
                or not probability(answer.get('confidence'))):
            raise ValueError('Invalid probabilities or confidence')
        # Four probabilities may each be rounded to two decimals by the service.
        if not math.isclose(sum(probs.values()), 1, abs_tol=0.020000001):
            raise ValueError('Probability sum outside rounding tolerance')
        choice = answer.get('choice')
        if choice not in probs or probs[choice] + 1e-12 < max(probs.values()):
            raise ValueError('Choice is not highest-probability option')
    return {'answers': answers, 'model': response['model'], 'usage': validate_usage(response)}


def validate_schedule(payloads, consent):
    """Exact metadata allowlist plus reconstruction and cross-arm identity checks."""
    if (set(payloads) != {'single', 'shared24'} or set(consent['layouts']) != set(payloads)
            or consent['model'] != MODEL
            or consent['destination'] != 'https://api.typesafe.ai/v1/systemone'
            or consent['rounds'] != [{'order':['single','shared24']}, {'order':['shared24','single']}]
            or consent['max_in_flight_per_arm'] != CONCURRENCY
            or consent['planned_max_requests'] != MAX_ATTEMPTS
            or consent['planned_request_bytes_including_repetitions'] > MAX_BYTES):
        raise ValueError('Unregistered schedule')
    all_records, schedules = {}, []
    for layout, expected_count, expected_questions in [('single',48,1),('shared24',2,24)]:
        bound = consent['layouts'][layout]
        bodies = payloads[layout]
        if (len(bodies) != expected_count or len(bound['packets']) != expected_count
                or bound['requests_per_round'] != expected_count):
            raise ValueError('Request count mismatch')
        rows, records = [], []
        for index, (body, meta) in enumerate(zip(bodies, bound['packets'])):
            if (type(body) is not bytes or meta['index'] != index
                    or sha(body) != meta['sha256'] or len(body) != meta['request_bytes']):
                raise ValueError('Packet hash/size/index mismatch')
            request = strict_json(body)
            if encode(request) != body:
                raise ValueError('Noncanonical request')
            batch = expand(request)
            ids = [question_id(record) for record in batch]
            if (len(batch) != expected_questions or ids != meta['question_ids']
                    or meta['questions'] != expected_questions):
                raise ValueError('Packet question mismatch')
            records.extend(batch)
            rows.append({'index':index, 'body':body, 'request':request, 'sha256':sha(body),
                         'request_bytes':len(body), 'question_ids':ids})
        if (sum(map(len,bodies)) != bound['request_bytes_per_round']
                or max(map(len,bodies)) != bound['max_request_bytes']
                or len({question_id(r) for r in records}) != 48):
            raise ValueError('Aggregate or duplicate claim mismatch')
        all_records[layout] = records
        for round_number, scheduled_layout in ORDER:
            if scheduled_layout == layout:
                schedules.append({'round':round_number, 'layout':layout, 'packets':rows})
    if all_records['single'] != all_records['shared24']:
        raise ValueError('Cross-arm claim/owner/context mismatch')
    if any(sha(encode(r['context'])) != consent['source_case']['context_sha256']
           for r in all_records['single']):
        raise ValueError('Frozen context mismatch')
    total_bytes = 2 * sum(len(b) for bodies in payloads.values() for b in bodies)
    if total_bytes != consent['planned_request_bytes_including_repetitions'] or total_bytes > MAX_BYTES:
        raise ValueError('Aggregate byte budget mismatch')
    return sorted(schedules, key=lambda a: ORDER.index((a['round'], a['layout'])))


def run(payloads, consent, directory, secret, reference_sha256, sender=post_once):
    started = time.perf_counter()
    schedules = validate_schedule(payloads, consent)
    if not isinstance(secret, str) or not secret or len(reference_sha256) != 64:
        raise ValueError('Credential and frozen reference required')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Never treat a partial/full prior benchmark as permission to send again.
    if any(directory.iterdir()):
        raise RuntimeError('Prior run exists; inspect retained outcomes, never replay')
    identity = {'consent_sha256':sha(encode(consent)), 'reference_sha256':reference_sha256,
        'source_case':consent['source_case'], 'order':[list(p) for p in ORDER],
        'model':MODEL, 'maximum_concurrency':CONCURRENCY, 'maximum_attempts':MAX_ATTEMPTS,
        'maximum_bytes':MAX_BYTES, 'automatic_retries':0}
    save(directory/'started.json', {'identity':identity, 'utc':utc()})
    stop = threading.Event()
    lock = threading.Lock()
    attempts = 0
    sent_bytes = 0
    arms = []
    for arm in schedules:
        if stop.is_set():
            break
        arm_dir = directory/f"r{arm['round']}_{arm['layout']}"
        arm_dir.mkdir(exist_ok=False)
        arm_start = time.perf_counter()
        save(arm_dir/'started.json', {'round':arm['round'], 'layout':arm['layout'], 'utc':utc()})
        active, maximum = 0, 0

        def worker(packet):
            nonlocal attempts, sent_bytes, active, maximum
            row = {k:packet[k] for k in ('index','sha256','request_bytes','question_ids')}
            row['worker_start_offset'] = time.perf_counter()-arm_start
            row['attempted'] = False
            target = arm_dir/f"{packet['index']:06d}_{packet['sha256']}"
            try:
                with lock:
                    if stop.is_set():
                        return row | {'ok':False, 'status':'not_admitted_after_failure'}
                    if attempts >= MAX_ATTEMPTS or sent_bytes+packet['request_bytes'] > MAX_BYTES:
                        raise ValueError('Attempt budget exhausted')
                    target.mkdir(exist_ok=False)
                    # Intent consumes allowance even if the process crashes before transmission.
                    save(target/'intent.json', identity | row | {'utc':utc(),
                        'round':arm['round'], 'layout':arm['layout'], 'outcome':'unknown'})
                    attempts += 1
                    sent_bytes += packet['request_bytes']
                    row['attempted'] = True
                    active += 1
                    maximum = max(maximum,active)
                http_start = time.perf_counter()
                row['http_start_offset'] = http_start-arm_start
                try:
                    status, raw = sender(packet['body'], secret)
                finally:
                    row['http_seconds'] = time.perf_counter()-http_start
                    row['http_end_offset'] = time.perf_counter()-arm_start
                    with lock:
                        active -= 1
                row['http_status'] = status
                if status != 200:
                    stop.set()
                # Retain raw response bytes after redacting any echoed credential.
                clean = raw.replace(secret.encode(), b'[REDACTED]')
                with (target/'response.redacted.bin').open('xb') as stream:
                    stream.write(clean)
                row['response_sha256'] = sha(raw)
                row['retained_response_sha256'] = sha(clean)
                row['response_bytes'] = len(raw)
                row['credential_redacted'] = clean != raw
                if status != 200:
                    raise ValueError('Non-success HTTP response')
                response = strict_json(clean)
                row['result'] = validate_answer(packet['request'], response)
                row['ok'] = True
                row['status'] = 'validated'
            except Exception as error:
                stop.set()
                row['ok'] = False
                row['status'] = 'failure_no_replay'
                row['error_class'] = type(error).__name__  # Never log exception/credential text.
                row['usage_unknown'] = 'result' not in row
            row['worker_end_offset'] = time.perf_counter()-arm_start
            if target.exists():
                save(target/'outcome.json', row | {'utc':utc(), 'automatic_retry_allowed':False})
            return row

        rows, cursor = [], 0
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            pending = set()
            while cursor < len(arm['packets']) and len(pending) < CONCURRENCY and not stop.is_set():
                pending.add(pool.submit(worker, arm['packets'][cursor]))
                cursor += 1
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                rows.extend(future.result() for future in done)
                # Workers set stop immediately; do not wait for scheduler observation.
                while cursor < len(arm['packets']) and len(pending) < CONCURRENCY and not stop.is_set():
                    pending.add(pool.submit(worker, arm['packets'][cursor]))
                    cursor += 1
        result = {'round':arm['round'], 'layout':arm['layout'],
            'status':'stopped' if stop.is_set() else 'complete',
            'stage_seconds':time.perf_counter()-arm_start, 'maximum_inflight_http':maximum,
            'rows':sorted(rows,key=lambda r:r['index']),
            'unscheduled_indices':list(range(cursor,len(arm['packets'])))}
        save(arm_dir/'summary.json',result)
        arms.append(result)
    result = {'identity':identity, 'status':'stopped' if stop.is_set() else 'complete',
        'attempts_consumed':attempts, 'attempt_body_bytes_consumed':sent_bytes,
        'arms':arms, 'run_seconds':time.perf_counter()-started,
        'quality_accepted':False, 'end_to_end_savings_proven':False,
        'incremental_semantic_benefit_proven':False, 'actual_billed_cost':None}
    save(directory/'summary.json', result)
    return result


def evaluate(result, reference, records):
    """Compare all available judgments; unresolved labels never enter strict accuracy."""
    ref = {tuple(r['path']):r for r in reference['rows']}
    if len(ref) != 48 or set(ref) != {tuple(r['claim']['path']) for r in records}:
        raise ValueError('Reference coverage mismatch')
    by_id = {question_id(r):ref[tuple(r['claim']['path'])] for r in records}
    outcomes, metrics = {}, []
    for arm in result['arms']:
        answers = {}
        for row in arm['rows']:
            if row['ok']:
                for qid, answer in row['result']['answers'].items():
                    if qid in answers or qid not in by_id:
                        raise ValueError('Duplicate or unknown answer')
                    answers[qid] = answer
        outcomes[(arm['round'],arm['layout'])] = answers
        judged = [{'question_id':qid, 'path':by_id[qid]['path'],
            'choice':a['choice'], 'acceptable_labels':by_id[qid]['acceptable_labels'],
            'determinate':len(by_id[qid]['acceptable_labels'])==1,
            'matches_reference_set':a['choice'] in by_id[qid]['acceptable_labels']}
            for qid,a in answers.items()]
        metrics.append({'round':arm['round'],'layout':arm['layout'],'answers':len(answers),
            'determinate_correct':sum(r['determinate'] and r['matches_reference_set'] for r in judged),
            'determinate_incorrect':sum(r['determinate'] and not r['matches_reference_set'] for r in judged),
            'ambiguous_judged':sum(not r['determinate'] for r in judged), 'judgments':judged,
            'usage':{k:sum(r['result']['usage'][k] for r in arm['rows'] if r['ok'])
                     for k in ('input_tokens','output_tokens')},
            'usage_complete':all(r['ok'] for r in arm['rows']) and arm['status']=='complete',
            'stage_seconds':arm['stage_seconds'],
            'sum_http_seconds':sum(r.get('http_seconds',0) for r in arm['rows'])})
    comparisons = []
    for left,right in [((1,'single'),(1,'shared24')),((2,'single'),(2,'shared24')),
                       ((1,'single'),(2,'single')),((1,'shared24'),(2,'shared24'))]:
        a,b = outcomes.get(left,{}),outcomes.get(right,{})
        common = sorted(set(a)&set(b))
        comparisons.append({'left':list(left),'right':list(right),'paired_claims':len(common),
            'choice_disagreements':[q for q in common if a[q]['choice'] != b[q]['choice']]})
    return {'arms':metrics,'comparisons':comparisons,'reference_is_independent':False,
        'no_jev_control':reference['no_jev_control'],'automatic_acceptance':False,
        'whole_output_accepted':False,'incremental_semantic_benefit_proven':False}
