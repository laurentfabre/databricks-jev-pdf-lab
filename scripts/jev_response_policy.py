"""Fail closed per answer when Jev's choice contradicts its own probabilities.

Raw responses remain unchanged. This does not normalize, repair or accept them.
The only tolerated anomaly yields a code-owned visual-review route.
"""
from jev_router import MODEL, recommendations, request_hash


def review_inconsistent_choices(request, response):
    if response.get('model') != MODEL or set(response.get('answers', {})) != set(request['questions']):
        raise ValueError('Missing answers or unexpected model')
    rows = []
    for key, question in request['questions'].items():
        answer = response['answers'][key]
        one_request = {**request, 'questions': {key: question}}
        one_response = {**response, 'answers': {key: answer}}
        try:
            row = recommendations(one_request, one_response)['recommendations'][0]
            row.update(service_choice=answer['choice'], response_contract_valid=True, contract_issues=[])
        except ValueError as error:
            # All type/options/distribution checks precede this specific failure.
            if (str(error) != 'Choice is not a permitted top-probability method'
                    or answer.get('choice') not in question['criteria']
                    or 'visual_review' not in question['criteria']):
                raise
            row = {'question': key, 'candidate_method': 'visual_review',
                'service_choice': answer['choice'], 'probabilities': answer['probabilities'],
                'confidence': answer['confidence'], 'response_contract_valid': False,
                'contract_issues': ['service_choice_not_maximum_probability'],
                'dispatch_authorized': False, 'quality_accepted': False,
                'status': 'code_owned_review_due_to_invalid_service_choice'}
        rows.append(row)
    return {'request_sha256': request_hash(request), 'model': response['model'],
        'usage': response.get('usage'), 'recommendations': rows, 'savings_proven': False,
        'invalid_choice_answers': sum(not r['response_contract_valid'] for r in rows)}
