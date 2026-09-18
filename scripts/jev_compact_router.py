"""Factor repeated instructions into shared state; retain metadata-only boundary."""
import json
from jev_router import build_request, METHODS
from jev_transport import validated_request as validate_original


def compact_request(original):
    validate_original(original)
    prefix = 'For `diagnostics[0]`, '
    policy = original['questions']['route_0']['instructions']
    assert policy.startswith(prefix)
    policy = policy[len(prefix):]
    state = {**original['state'], 'method_definitions':dict(METHODS), 'selection_policy':policy}
    questions = {}
    for i, (key, question) in enumerate(original['questions'].items()):
        assert question['instructions'] == f'For `diagnostics[{i}]`, ' + policy
        questions[key] = {'type':'choice', 'instructions':
            f'For `diagnostics[{i}]`, apply `selection_policy` using `method_definitions` '
            'and `constraints`. Choose only one of this question\'s criteria keys.',
            'criteria':{option:None for option in question['criteria']}}
    return {'model':original['model'],'state':state,'questions':questions}


def validated_request(request):
    state = request['state']
    expected = compact_request(build_request(state['diagnostics'], state.get('document_context')))
    if request != expected:
        raise ValueError('Payload differs from strict compact metadata-only contract')
    return json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()
