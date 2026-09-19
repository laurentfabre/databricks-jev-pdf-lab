"""Label reviewed projections honestly while preserving exact parent recovery.

Wraps the frozen projection engine; no new selection, truth claim, I/O or AI.
The inner audit describes its intermediate response. The outer audit describes
the new lineage-labelled result. Real audit values must remain private.
"""
from copy import deepcopy

from reviewed_field_projection import digest, project, restore as restore_projection


def project_with_lineage(raw, text, scopes, schema, plan):
    if not plan.get('operations'):
        raise ValueError('A new derivation requires explicit field operations')
    intermediate, projection = project(raw, text, scopes, schema, plan)
    derived = deepcopy(intermediate)
    parent_present = 'derivation' in raw
    parent = deepcopy(raw.get('derivation'))
    derived['derivation'] = {
        'kind': 'reviewed_field_projection',
        'service_response': False,
        'quality_accepted': False,
        'plan_sha256': digest(plan),
        'parent_response_sha256': digest(raw),
        'parent_derivation_present': parent_present,
        'parent_derivation': parent,
        'semantic_selection': 'supplied_posthoc_assistant_review_not_automated',
        'inherited_metadata_is_not_new_service_confidence': True,
    }
    audit = {
        'projection': projection,
        'prior_derivation_present': parent_present,
        'prior_derivation': deepcopy(parent),
        'derived_sha256': digest(derived),
        'new_ai_calls': 0,
        'quality_accepted': False,
        'semantic_review_required': True,
    }
    if restore(derived, audit) != raw:
        raise ValueError('Lineage inverse differs from parent')
    return derived, audit


def restore(derived, audit):
    if digest(derived) != audit['derived_sha256']:
        raise ValueError('Derived output changed before reversal')
    lineage = derived.get('derivation', {})
    projection = audit['projection']
    if (lineage.get('service_response') is not False
            or lineage.get('quality_accepted') is not False
            or lineage.get('kind') != 'reviewed_field_projection'
            or lineage.get('plan_sha256') != projection['plan_sha256']
            or lineage.get('parent_response_sha256') != projection['bindings']['raw_sha256']
            or type(audit['prior_derivation_present']) is not bool
            or lineage.get('parent_derivation_present') != audit['prior_derivation_present']
            or lineage.get('parent_derivation') != audit['prior_derivation']):
        raise ValueError('Lineage/audit disagreement')
    intermediate = deepcopy(derived)
    if audit['prior_derivation_present']:
        intermediate['derivation'] = deepcopy(audit['prior_derivation'])
    else:
        del intermediate['derivation']
    return restore_projection(intermediate, projection)
