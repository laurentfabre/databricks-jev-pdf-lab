"""Attach known input provenance in code without claiming semantic support."""
import copy
import hashlib
import re

from quality_gates import unwrap


def attach_single_page(raw, input_text, input_sha256, original_pages):
    """Return a derived business record and audit; never modify the raw response.

    Only a one-original-page input is eligible. An output's claims can still be
    unsupported even after their processing origin is attached correctly.
    """
    if hashlib.sha256(input_text.encode()).hexdigest() != input_sha256:
        raise ValueError('Input hash does not match retained routing evidence')
    if len(original_pages) != 1 or type(original_pages[0]) is not int or original_pages[0] < 1:
        raise ValueError('Exactly one original physical page is required')
    labels = {int(p) for p in re.findall(r'^\[SOURCE PAGE (\d+)\]$', input_text, re.M)}
    if labels != set(original_pages):
        raise ValueError('Source page labels disagree with input provenance')
    metadata = raw.get('metadata') or {}
    if raw.get('error_message') or metadata.get('mode') != 'precision' or metadata.get('version') != '2.1':
        raise ValueError('Cannot derive a successful Precision response')
    clean = copy.deepcopy(unwrap(raw.get('response')))
    if not isinstance(clean, dict):
        raise ValueError('Response is not an object')
    changes = []
    for field in ('items', 'policies', 'dietary_allergen_legend'):
        if not isinstance(clean.get(field), list):
            raise ValueError(f'{field} is not an array')
        for index, item in enumerate(clean[field]):
            if not isinstance(item, dict):
                raise ValueError(f'{field} record is not an object')
            old = item.get('source_pages')
            if old != original_pages:
                changes.append({'path': f'{field}[{index}].source_pages',
                    'previous': old, 'assigned': list(original_pages)})
            item['source_pages'] = list(original_pages)
    return clean, {'method': 'single_physical_input_page_v1',
        'input_sha256': input_sha256, 'original_pages': list(original_pages),
        'changes': changes, 'semantic_support': 'not_proven',
        'raw_response_unchanged': True}
