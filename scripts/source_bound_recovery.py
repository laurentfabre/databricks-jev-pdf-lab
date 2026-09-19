"""Propose and shadow-copy cited inline prices; never assert semantic acceptance.

No IO/inference. Source grouping is supplied by the caller, not validated here as
semantic truth. Original responses and existing fields are never mutated.
"""
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from citation_span_review import literal_support
from quality_gates import unwrap

SPACE = r'[ \u00a0\u202f]*'
NUMBER = r'\d+(?:[.,]\d{1,2})?'
CURRENCY = r'(?:EUR|GBP|USD|€|£|US\$)'
PLUS_PRICE = re.compile(r'\(\+' + SPACE + r'(?:(?P<prefix>' + CURRENCY + r')' + SPACE
    + r'(?P<pnumber>' + NUMBER + r')|(?P<snumber>' + NUMBER + r')' + SPACE
    + r'(?P<suffix>' + CURRENCY + r'))' + SPACE + r'\)')
CAUTION = re.compile(r'\b(?:not|no|never|formerly|instead|perhaps|possibly|may|might|'
                     r'option|optional|unavailable|except|unless)\b', re.I)
CURRENCIES = {'€':'EUR', 'EUR':'EUR', '£':'GBP', 'GBP':'GBP', 'USD':'USD', 'US$':'USD'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def inline_prices(fragment):
    """Exact narrow grammar only. Bare $, grouped numbers and signs abstain."""
    values = []
    for match in PLUS_PRICE.finditer(fragment):
        amount = Decimal((match['pnumber'] or match['snumber']).replace(',', '.'))
        currency = CURRENCIES[match['prefix'] or match['suffix']]
        values.append({'amount_decimal':str(amount), 'currency':currency,
                       'literal':match[0], 'relative_span':[match.start(),match.end()]})
    return values


def price_pairs(item):
    prices = item.get('prices')
    if not isinstance(prices, list):
        raise ValueError('Missing structured prices array')
    pairs = []
    for price in prices:
        if not isinstance(price, dict):
            raise ValueError('Malformed structured price')
        amount, currency = unwrap(price.get('amount')), unwrap(price.get('currency'))
        if isinstance(amount, bool) or not isinstance(amount, (int, float, Decimal)):
            raise ValueError('Malformed structured amount')
        try:
            number = Decimal(str(amount))
        except InvalidOperation as error:
            raise ValueError('Malformed structured amount') from error
        if not number.is_finite() or currency not in set(CURRENCIES.values()):
            raise ValueError('Malformed or unsupported structured price')
        pairs.append((number, currency))
    return pairs


def derive(raw, text, scopes, groups, input_sha256):
    """Return shadow raw response and hash-bound audit. Every edit needs review.

    Existing amount/currency equality suppresses additions, but does not validate
    the existing basis. Same-price multilingual alternatives are retained for review.
    """
    if not isinstance(text, str) or text_hash(text) != input_sha256:
        raise ValueError('Input hash mismatch')
    original_hash = digest(raw)
    if (not isinstance(raw.get('response'), dict)
            or not isinstance(raw['response'].get('items'), list)
            or raw.get('error_message') is not None
            or raw.get('metadata', {}).get('mode') != 'precision'
            or raw.get('metadata', {}).get('version') != '2.1'):
        raise ValueError('Successful Precision v2.1 response required')
    source_scopes = {}
    for scope in scopes:
        if (type(scope.get('element_id')) is not int or type(scope.get('page')) is not int
                or scope['page'] < 1 or scope['element_id'] in source_scopes
                or type(scope.get('start')) is not int or type(scope.get('stop')) is not int
                or not 0 <= scope['start'] < scope['stop'] <= len(text)):
            raise ValueError('Invalid/duplicate source scope')
        source_scopes[scope['element_id']] = scope
    if not source_scopes or len({g['id'] for g in groups}) != len(groups):
        raise ValueError('Missing scopes or duplicate group IDs')
    for group in groups:
        if (not isinstance(group.get('fragments'), list) or not group['fragments']
                or any(not isinstance(f, str) or not f for f in group['fragments'])
                or not group.get('element_ids') or len(set(group['element_ids'])) != len(group['element_ids'])
                or any(e not in source_scopes or source_scopes[e]['page'] != group['physical_page']
                       for e in group['element_ids'])):
            raise ValueError('Invalid source group or cross-page scope')
    items = raw['response']['items']
    if any(not isinstance(item, dict) for item in items):
        raise ValueError('Malformed item')
    by_item, issues = {}, []
    for index, item in enumerate(items):
        candidates = []
        name = unwrap(item.get('name'))
        details = unwrap(item.get('details'))
        if any(isinstance(v,str) and CAUTION.search(v) for v in (name,details)):
            issues.append({'item':index,'reason':'conditional_or_negative_output_context'})
            by_item[index] = []
            continue
        for group in groups:
            if group.get('kind') != 'priced_item':
                continue
            for fragment in group['fragments']:
                found = inline_prices(fragment)
                if not found or sum(c.isalpha() for c in fragment) < 8:
                    continue
                for field_name in ('name','details'):
                    field = item.get(field_name)
                    prose = unwrap(field)
                    if not isinstance(prose, str) or fragment not in prose:
                        continue
                    if CAUTION.search(fragment) or CAUTION.search(prose):
                        issues.append({'item':index, 'group_id':group['id'], 'reason':'conditional_or_negative_wording'})
                        continue
                    proof = literal_support(field, raw['metadata'], text, fragment,
                        [[source_scopes[e]['start'],source_scopes[e]['stop']] for e in group['element_ids']])
                    if not proof['valid'] or len(proof.get('occurrences',[])) != 1:
                        issues.append({'item':index, 'group_id':group['id'], 'reason':'missing_or_ambiguous_literal_citation'})
                        continue
                    # A details mention is not an item identity. Require a cited
                    # whole name variant at the start of the same source fragment.
                    variants = name.split(' / ') if isinstance(name,str) else []
                    anchors = [v for v in variants if sum(c.isalpha() for c in v) >= 8
                        and fragment.startswith(v) and (len(v)==len(fragment)
                            or not fragment[len(v)].isalnum())]
                    anchors = [v for v in anchors if literal_support(item.get('name'), raw['metadata'],
                        text, v, [proof['occurrences'][0]])['supported']]
                    if not anchors:
                        issues.append({'item':index,'group_id':group['id'],'reason':'no_cited_name_anchor'})
                        continue
                    if unwrap(item.get('source_pages')) != [group['physical_page']]:
                        issues.append({'item':index, 'group_id':group['id'], 'reason':'physical_page_disagreement'})
                        continue
                    if len(found) != 1:
                        issues.append({'item':index, 'group_id':group['id'], 'reason':'multiple_prices_in_fragment'})
                        continue
                    candidate = {**found[0], 'item':index, 'group_id':group['id'],
                        'physical_page':group['physical_page'], 'source_field':field_name,
                        'basis_literal':fragment, 'source_span':proof['occurrences'][0],
                        'name_anchors':anchors,
                        'citation_ids':deepcopy(field['citation_ids'])}
                    candidate['candidate_id'] = digest(candidate)
                    candidates.append(candidate)
        by_item[index] = candidates
    owners = Counter(g for candidates in by_item.values() for g in {c['group_id'] for c in candidates})
    shadow, changes, considered = deepcopy(raw), [], []
    for index, candidates in by_item.items():
        if not candidates:
            continue
        status = {'item':index, 'candidates':candidates, 'status':'review_only'}
        considered.append(status)
        if len({c['group_id'] for c in candidates}) != 1 or any(owners[c['group_id']] != 1 for c in candidates):
            status['reason'] = 'ambiguous_group_or_output_ownership'
            continue
        try:
            existing = price_pairs(items[index])
        except ValueError as error:
            status['reason'] = str(error)
            continue
        missing = [c for c in candidates if (Decimal(c['amount_decimal']),c['currency']) not in existing]
        if not missing:
            status['status'] = 'numeric_pair_already_present_basis_not_validated'
            continue
        if len({(Decimal(c['amount_decimal']),c['currency']) for c in missing}) != 1:
            status['reason'] = 'multiple_missing_pairs'
            continue
        selected = sorted(missing, key=lambda c:(-len(c['basis_literal']), c['candidate_id']))[0]
        number = Decimal(selected['amount_decimal'])
        # JSON numbers are exact for these bounded cents after decimal roundtrip.
        value = int(number) if number == number.to_integral_value() else float(number)
        if Decimal(str(value)) != number:
            status['reason'] = 'json_number_would_lose_precision'
            continue
        price = {k:{'value':v,'citation_ids':deepcopy(selected['citation_ids'])} for k,v in
            (('amount',value),('currency',selected['currency']),('basis',selected['basis_literal']))}
        target = shadow['response']['items'][index]['prices']
        change = {'item':index,'path':f'response.items[{index}].prices[{len(target)}]',
            'selected_candidate_id':selected['candidate_id'], 'price':deepcopy(price),
            'source_span':selected['source_span'],'physical_page':selected['physical_page'],
            'semantic_review_required':True,'quality_accepted':False}
        target.append(price)
        changes.append(change)
        status['status'] = 'shadow_addition_requires_semantic_review'
    assert digest(raw) == original_hash
    audit = {'input_sha256':input_sha256, 'raw_response_canonical_sha256':original_hash,
        'scopes_sha256':digest(scopes),'groups_sha256':digest(groups),
        'shadow_response_canonical_sha256':digest(shadow), 'items_scanned':len(items),
        'items_with_candidates':len(considered), 'candidate_occurrences':sum(len(c) for c in by_item.values()),
        'changes':changes, 'considered':considered, 'issues':issues,
        'raw_response_unchanged':True,'existing_fields_unchanged':True,
        'semantic_review_required':True,'quality_accepted':False,'new_ai_calls':0,
        'limits':['Full-fragment citation coverage is not semantic correctness.',
            'Supplied source grouping/translation equivalence is a caller hypothesis.',
            'Same amount/currency suppresses additions but does not establish correct basis or completeness.',
            'Known wording filter is incomplete; unknown negation/conditions require semantic review.',
            'No dietary markers, allergens, policies, page fields, or existing values are repaired.',
            'Shadow fields inherit existing citation IDs, not model confidence or new service citations.']}
    return shadow, audit
