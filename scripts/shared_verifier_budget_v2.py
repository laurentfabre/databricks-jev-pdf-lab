"""Preserve hash-bound abstention for every unsupported raw envelope shape.

All successful-response preparation and packet construction remain frozen v1.
"""
from bbox_page_provenance import bindings, digest, need
from shared_verifier_budget import prepare as original_prepare


def prepare(raw, parsed, schema, instructions, indexed, expected_index_sha256):
    if 'document_abstention' not in indexed:
        return original_prepare(raw,parsed,schema,instructions,indexed,expected_index_sha256)
    need(digest(indexed) == expected_index_sha256, 'Stale index digest')
    need(bindings(raw,parsed,schema) == indexed['bindings'] == indexed['contract']['bindings'], 'Stale source binding')
    need(isinstance(instructions,str) and bool(instructions.strip()), 'Instructions required')
    meta = raw.get('metadata') or {}
    # Match the original E44 envelope rejection, not just the service-error field.
    unsupported = (raw.get('error_message') or meta.get('mode') != 'precision'
        or meta.get('version') != '2.1' or meta.get('chunk_type') != 'bbox'
        or 'derivation' in raw or not isinstance(raw.get('response'),dict))
    need(unsupported, 'Unexplained whole-response abstention')
    need(indexed['rows'] == [] and indexed['sources'] == [] and indexed['counts'] == {}
         and indexed['quality_accepted'] is False and indexed['raw_unchanged'] is True
         and indexed['new_ai_calls'] == 0, 'Invalid retained abstention')
    return {'records': [], 'inventory': {'document_abstention':indexed['document_abstention'],
        'selected_strings':0,'concrete_slots':0,'quality_accepted':False}}
