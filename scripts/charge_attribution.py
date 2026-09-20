"""Deterministic attribution and list pricing of already-observed usage.

No network, inference, PDF processing, invoice claims or time-based allocation.
Job-run bindings describe one cohort/run. Warehouse isolation is not implemented:
warehouse-only records stay unresolved, even if a caller supplies a claimed hash.
"""
import datetime as dt
from decimal import Decimal, localcontext
import json


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone-aware timestamps required')
    return result


def exact_decimal(value):
    if isinstance(value, (float, bool)):
        raise ValueError('Use exact decimal strings, never float currency')
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('Finite decimals required')
    return result


def component(row):
    product = row['billing_origin_product']
    if product == 'AI_FUNCTIONS':
        return {'AI_PARSE_DOCUMENT': 'parse', 'AI_EXTRACT': 'extract'}.get(row.get('ai_function'), 'other')
    return 'compute' if product in ('JOBS', 'SQL') else 'other'


def match_binding(row, bindings):
    """No invoice row is copied into multiple strategies or cases."""
    matches = []
    for binding in bindings:
        if str(row['workspace_id']) != str(binding['workspace_id']):
            continue
        metadata = row.get('usage_metadata') or {}
        key = binding['key']
        if key not in ('job_run_id', 'warehouse_id'):
            raise ValueError('Unsupported attribution key')
        if key == 'warehouse_id':
            continue
        if str(metadata.get(key)) not in binding['values']:
            continue
        matches.append(binding)
    if len(matches) != 1:
        return None, 'ambiguous_binding' if matches else 'no_verified_binding'
    return matches[0], None


def price_record(row, prices, currency='USD'):
    """Require one rate covering the entire usage interval; do not guess splits."""
    start, end = timestamp(row['usage_start_time']), timestamp(row['usage_end_time'])
    if start >= end:
        raise ValueError('Invalid usage interval')
    qty = exact_decimal(row['usage_quantity'])
    kind = row['record_type']
    if kind not in ('ORIGINAL', 'RETRACTION', 'RESTATEMENT'):
        raise ValueError('Unknown billing record type')
    if (kind == 'RETRACTION' and qty > 0) or (kind != 'RETRACTION' and qty < 0):
        raise ValueError('Invalid signed billing quantity')
    matching = [p for p in prices
        if all(row[k] == p[k] for k in ('account_id', 'sku_name', 'cloud', 'usage_unit'))
        and p['currency_code'] == currency
        and timestamp(p['price_start_time']) <= start
        and (p.get('price_end_time') is None or end <= timestamp(p['price_end_time']))]
    if len(matching) != 1:
        return None, f'price_matches_{len(matching)}'
    rate = exact_decimal(matching[0]['effective_list_rate'])
    if rate < 0:
        raise ValueError('Negative price')
    with localcontext() as ctx:
        ctx.prec = 100
        return qty * rate, None


def reconcile(rows, prices, bindings):
    """Observe signed billed usage; never infer completeness from this snapshot.

    Retraction and restatement may retain the original record_id. Deduplicate
    byte-equivalent logical rows, not record_id alone. Different corrections stay.
    """
    seen, details, totals, errors = set(), [], {}, []
    duplicate_count = 0
    for row in rows:
        identity = json.dumps(row, sort_keys=True, separators=(',', ':'))
        if identity in seen:
            duplicate_count += 1
            continue
        seen.add(identity)
        binding, bind_error = match_binding(row, bindings)
        cost, price_error = price_record(row, prices)
        detail = {'record_id': row['record_id'], 'record_type': row['record_type'],
            'component': component(row), 'cohort': binding['cohort'] if binding else None,
            'compute_path': binding['compute_path'] if binding else None,
            'binding_key': binding['key'] if binding else None,
            'usage_quantity': str(exact_decimal(row['usage_quantity'])),
            'attributable_list_usd': str(cost) if binding and cost is not None else None,
            'attribution_error': bind_error, 'pricing_error': price_error}
        details.append(detail)
        if bind_error or price_error:
            errors.append(detail)
        else:
            key = (binding['cohort'], component(row), binding['compute_path'])
            with localcontext() as ctx:
                ctx.prec = 100
                totals[key] = totals.get(key, Decimal(0)) + cost
    return {'rows': details, 'totals': [dict(zip(('cohort', 'component', 'compute_path'), key),
                observed_list_usd=str(value)) for key, value in sorted(totals.items())],
        'duplicate_rows_removed': duplicate_count,
        'unresolved_rows': len(errors), 'observed_records': len(details),
        'complete_cost': False, 'list_price_is_invoice': False,
        'missing_cost_is_zero': False}


def attribution_gate(reconciliation, requirements, *, tags_verified):
    """Prove observed attribution for the SAME compute path before expansion.

    A pass is mapping readiness only, not billing finality, quality acceptance,
    resource-creation authorization or permission to submit inference. An
    execution guard must separately require labels, a runner and a spend cap.
    """
    missing = []
    if not tags_verified:
        missing.append('query_tags_not_verified')
    if not requirements:
        missing.append('no_explicit_component_requirements')
    rows = reconciliation.get('rows', [])
    for requirement in requirements:
        matching = [r for r in rows if all(r.get(k) == requirement[k]
                    for k in ('cohort', 'component', 'compute_path'))]
        usable = [r for r in matching if r['attributable_list_usd'] is not None
                  and not r['attribution_error'] and not r['pricing_error']]
        with localcontext() as ctx:
            ctx.prec = 100
            net = sum((exact_decimal(r['attributable_list_usd']) for r in usable), Decimal(0))
        if not usable or len(usable) != len(matching) or net <= 0:
            missing.append('missing_positive_reconciled_usage:' + ':'.join(requirement[k]
                           for k in ('cohort', 'component', 'compute_path')))
    if reconciliation.get('unresolved_rows', 0):
        missing.append('unresolved_usage_rows')
    return {'mapping_ready': not missing, 'blockers': missing,
            'complete_cost': False, 'paid_execution_authorized': False}
