"""Deterministic, scope-aware cache decisions. No inference or network client.

A completed but unaccepted response is retained for review, not served as truth
and not silently submitted for another inference. Storage locking and atomic
submission are the caller's responsibility; this module is not a job scheduler.
"""
import hashlib
import json
import copy
import math
import re


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def contract_key(contract):
    required = {'workspace_id', 'source_sha256', 'input_sha256', 'source_pages',
        'parser_recipe', 'schema_sha256', 'instructions_sha256', 'function',
        'version', 'mode', 'citations', 'confidence_scores', 'postprocessor',
        'validation_scope', 'validation_revision'}
    if set(contract) != required:
        raise ValueError('Cache contract must include exactly the versioned semantic fields')
    if contract['workspace_id'] != 'example-workspace':
        raise ValueError('Cache is pinned to the experiment workspace')
    for field in ('source_sha256', 'input_sha256', 'schema_sha256', 'instructions_sha256'):
        if not re.fullmatch(r'[0-9a-f]{64}', contract[field]):
            raise ValueError(f'Invalid {field}')
    if contract['function'] != 'ai_extract' or contract['mode'] != 'precision' or contract['version'] != '2.1':
        raise ValueError('Precision v2.1 is required')
    pages = contract['source_pages']
    if not isinstance(pages, list) or not pages or any(type(p) is not int or p < 1 for p in pages):
        raise ValueError('Physical source pages must be explicit')
    if pages != sorted(set(pages)):
        raise ValueError('Source page map must be unique and sorted')
    for field in ('parser_recipe', 'postprocessor', 'validation_scope', 'validation_revision'):
        if not isinstance(contract[field], str) or not contract[field]:
            raise ValueError(f'Missing {field}')
    if type(contract['citations']) is not bool or type(contract['confidence_scores']) is not bool:
        raise ValueError('Metadata options must be booleans')
    return digest(contract)


def decide(contract, entry, now_epoch):
    """Choose reuse/review/resume/miss without executing any inferred action."""
    key = contract_key(contract)
    if entry is None or entry.get('contract_key') != key:
        return {'action': 'miss', 'key': key, 'ai_calls': 0}
    state = entry.get('state')
    if state in ('PENDING', 'RUNNING') and entry.get('statement_id'):
        return {'action': 'resume', 'statement_id': entry['statement_id'], 'ai_calls': 0}
    if state != 'SUCCEEDED':
        return {'action': 'review', 'reason': 'unsuccessful_or_unknown_state', 'ai_calls': 0}
    if 'response' not in entry or entry.get('response_sha256') != digest(entry['response']):
        return {'action': 'review', 'reason': 'response_integrity_failure', 'ai_calls': 0}
    validation = entry.get('validation') or {}
    if (validation.get('accepted') is not True
            or validation.get('scope') != contract['validation_scope']
            or validation.get('revision') != contract['validation_revision']
            or validation.get('response_sha256') != entry['response_sha256']
            or not validation.get('evidence_id')):
        return {'action': 'review', 'reason': 'validation_not_accepted_for_requested_scope', 'ai_calls': 0}
    deadline = validation.get('expires_epoch')
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= now_epoch:
        return {'action': 'review', 'reason': 'validation_expired_or_unbounded', 'ai_calls': 0}
    return {'action': 'reuse', 'response': copy.deepcopy(entry['response']), 'ai_calls': 0}
