"""Deterministic evidence checks; never a substitute for semantic validation.

Applies TypeSafe's code-owned verification pattern without calling a hosted model.
"""
from typing import Any


def unwrap(value: Any) -> Any:
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    if isinstance(value, dict):
        if 'value' in value and set(value) <= {'value', 'citation_ids', 'confidence_score'}:
            return unwrap(value['value'])
        return {k: unwrap(v) for k, v in value.items()}
    return value


def assess_extraction(raw: dict, expected_pages: int, allowed_source_pages=None) -> dict:
    """Report structural failures while explicitly leaving semantic checks open."""
    failures = []
    if raw.get('error_message'):
        failures.append('service_error')
    metadata = raw.get('metadata') or {}
    if metadata.get('version') != '2.1':
        failures.append('version_not_confirmed')
    if metadata.get('mode') != 'precision':
        failures.append('precision_mode_not_confirmed')
    clean = unwrap(raw.get('response'))
    if not isinstance(clean, dict):
        clean = {}
        failures.append('response_not_object')
    arrays = ('languages', 'items', 'policies', 'dietary_allergen_legend')
    for key in arrays:
        if not isinstance(clean.get(key), list):
            failures.append(f'{key}_not_array')
    items = clean.get('items') if isinstance(clean.get('items'), list) else []
    if not items:
        failures.append('no_items')
    missing_pages = 0
    invalid_pages = 0
    outside_input_pages = 0
    for key in ('items', 'policies', 'dietary_allergen_legend'):
        records = clean.get(key) if isinstance(clean.get(key), list) else []
        for record in records:
            if not isinstance(record, dict):
                failures.append(f'{key}_record_not_object')
                continue
            pages = record.get('source_pages')
            if not isinstance(pages, list) or not pages:
                missing_pages += 1
            elif any(type(p) is not int or not 1 <= p <= expected_pages for p in pages):
                invalid_pages += 1
            elif allowed_source_pages is not None and not set(pages) <= set(allowed_source_pages):
                outside_input_pages += 1
    if missing_pages:
        failures.append('explicit_page_provenance_missing')
    if invalid_pages:
        failures.append('explicit_page_provenance_invalid')
    if outside_input_pages:
        failures.append('explicit_page_outside_input_scope')
    return {
        'structural_status': 'fail' if failures else 'pass',
        'failures': sorted(set(failures)),
        'records_missing_source_pages': missing_pages,
        'records_with_invalid_source_pages': invalid_pages,
        'records_outside_input_pages': outside_input_pages,
        'semantic_status': 'not_evaluated',
        'source_inventory_status': 'not_evaluated',
        'accepted': False,
    }
