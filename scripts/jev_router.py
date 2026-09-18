"""Metadata-only Jev candidate routing contract. No networking or dispatch.

The caller must obtain explicit endpoint/data-boundary approval before sending
any request. A valid Jev response is a recommendation, never quality acceptance.
"""
import hashlib
import json
import math

MODEL = 'jev-1.13.0'
NUMERIC_FIELDS = frozenset(('page_count', 'native_characters', 'image_placements',
    'image_count', 'font_count', 'fonts_embedded', 'fonts_to_unicode',
    'drawing_paths', 'replacement_fraction', 'largest_image_pixels', 'page_ordinal',
    'word_count', 'image_coverage_fraction', 'native_chars_per_square_inch',
    'left_word_fraction', 'right_word_fraction', 'center_gutter_word_fraction',
    'pages_without_native_text', 'pages_with_images'))
BOOLEAN_FIELDS = frozenset(('native_text_available', 'image_present',
    'visual_fact_risk', 'column_layout_risk', 'table_alignment_risk',
    'cross_page_context_risk', 'source_readable'))
METHODS = {
    'native_text_precision': 'Extract embedded text without image decode, then fixed Precision extraction. '
        'Candidate for simple live-text layouts; cannot recover raster-only or visual facts.',
    'native_layout_precision': 'Extract embedded text with columns/table geometry and preserved context, '
        'then fixed Precision extraction. Layout recovery needs source validation.',
    'managed_parse_precision': 'Managed document parsing/OCR, then fixed Precision extraction. '
        'Retain page mappings; parsing alone does not guarantee icons or diagrams survive.',
    'visual_review': 'Preserve the page and obtain additional in-workspace visual evidence/review. '
        'Use when symbols/diagrams or insufficient diagnostics make automated methods unreliable.',
}


def safe_record(record):
    allowed = NUMERIC_FIELDS | BOOLEAN_FIELDS | {'scope'}
    if set(record) - allowed:
        raise ValueError('Disallowed field: content, URLs, names and arbitrary strings cannot enter router state')
    if record.get('scope') not in ('document', 'page'):
        raise ValueError('scope must be document or page')
    result = {'scope': record['scope']}
    for key in sorted(set(record) - {'scope'}):
        value = record[key]
        if value is None:
            result[key] = None  # unknown is not zero or false
        elif key in NUMERIC_FIELDS:
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Expected nonnegative finite numeric diagnostic')
            if key.endswith('_fraction') and value > 1:
                raise ValueError('Invalid fraction')
            result[key] = value
        elif type(value) is not bool:
            raise ValueError('Expected boolean diagnostic, not text')
        else:
            result[key] = value
    return result


def eligible_methods(record):
    methods = dict(METHODS)
    if record.get('source_readable') is False:
        return {'visual_review': METHODS['visual_review']}
    if record.get('native_text_available') is False or record.get('native_characters') == 0:
        methods.pop('native_text_precision')
        methods.pop('native_layout_precision')
    if record.get('visual_fact_risk') is True:
        methods.pop('native_text_precision', None)
        methods.pop('native_layout_precision', None)
    if record.get('column_layout_risk') is True or record.get('table_alignment_risk') is True:
        methods.pop('native_text_precision', None)
    return methods


def build_request(records, document_context=None):
    if not 1 <= len(records) <= 32:
        raise ValueError('Use bounded batches of 1–32 diagnostics; retain document context separately')
    safe = [safe_record(record) for record in records]
    state = {'diagnostics': safe,
        'constraints': {'extraction_mode': 'precision', 'schema': 'unchanged',
                        'all_source_pages_required': True,
                        'missing_diagnostics_mean': 'unknown, not false',
                        'purpose': 'candidate method selection, not factual extraction or acceptance'}}
    if document_context is not None:
        context = safe_record(document_context)
        if context['scope'] != 'document':
            raise ValueError('Document context must have document scope')
        state['document_context'] = context
    questions = {}
    for i, record in enumerate(safe):
        methods = eligible_methods(record)
        if len(methods) == 1:
            raise ValueError('Only one eligible method; resolve deterministically without Jev')
        questions[f'route_{i}'] = {'type': 'choice',
            'instructions': f'For `diagnostics[{i}]`, select the most promising allowed preprocessing '
                'method for complete, faithful structured extraction. Minimize avoidable work only '
                'subject to quality. Do not interpret sparse text as proof that a page is empty, '
                'or lack of ToUnicode as proof of failed extraction. Preserve table/column relationships '
                'and cross-page context. Structural metadata cannot prove visual or semantic completeness. '
                'Choose visual_review if the available evidence is insufficient. This is a proposed '
                'experiment route: do not infer unmeasured prices, latency or cost savings.',
            'criteria': methods}
    return {'model': MODEL, 'state': state, 'questions': questions}


def request_hash(request):
    return hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def recommendations(request, response):
    if response.get('model') != MODEL:
        raise ValueError('Unexpected/unpinned Jev model version')
    if set(response.get('answers', {})) != set(request['questions']):
        raise ValueError('Missing or extra answers')
    result = []
    for key, question in request['questions'].items():
        answer = response['answers'][key]
        probabilities = answer.get('probabilities', {})
        if answer.get('type') != 'choice' or set(probabilities) != set(question['criteria']):
            raise ValueError('Answer options differ from permitted methods')
        values = [*probabilities.values(), answer.get('confidence')]
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError('Invalid probability or confidence')
        if abs(sum(probabilities.values()) - 1) > 0.001:
            raise ValueError('Probabilities do not sum to one')
        chosen = answer.get('choice')
        if chosen not in probabilities or probabilities[chosen] != max(probabilities.values()):
            raise ValueError('Choice is not a permitted top-probability method')
        result.append({'question': key, 'candidate_method': chosen,
            'probabilities': probabilities, 'confidence': answer['confidence'],
            'dispatch_authorized': False, 'quality_accepted': False,
            'status': 'recommendation_only_pending_target_domain_validation'})
    return {'request_sha256': request_hash(request), 'model': response['model'],
            'usage': response.get('usage'), 'recommendations': result,
            'savings_proven': False}
