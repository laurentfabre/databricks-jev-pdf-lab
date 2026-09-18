"""Also isolate probability mass deviations; never renormalize the raw answer.

A small deviation may be service rounding, not an incorrect semantic decision.
It still receives review under this pilot's strict arithmetic contract.
"""
from jev_response_policy import review_inconsistent_choices as review_v1
from jev_router import MODEL, request_hash


def review_inconsistent_choices(request, response):
    if response.get('model') != MODEL or set(response.get('answers', {})) != set(request['questions']):
        raise ValueError('Missing answers or unexpected model')
    rows = []
    for key, question in request['questions'].items():
        answer = response['answers'][key]
        try:
            row = review_v1({**request, 'questions': {key: question}},
                            {**response, 'answers': {key: answer}})['recommendations'][0]
        except ValueError as error:
            # Type, exact option-set and finite [0,1] checks already passed.
            if (str(error) != 'Probabilities do not sum to one'
                    or answer.get('choice') not in question['criteria']
                    or 'visual_review' not in question['criteria']):
                raise
            row = {'question': key, 'candidate_method': 'visual_review',
                'service_choice': answer['choice'], 'probabilities': answer['probabilities'],
                'confidence': answer['confidence'], 'response_contract_valid': False,
                'contract_issues': ['probability_mass_deviation_possibly_rounding'],
                'probability_sum': sum(answer['probabilities'].values()),
                'dispatch_authorized': False, 'quality_accepted': False,
                'status': 'code_owned_review_due_to_probability_mass_deviation'}
            if answer['probabilities'][answer['choice']] != max(answer['probabilities'].values()):
                row['contract_issues'].append('service_choice_not_maximum_probability')
        rows.append(row)
    return {'request_sha256': request_hash(request), 'model': response['model'],
        'usage': response.get('usage'), 'recommendations': rows, 'savings_proven': False,
        'invalid_choice_answers': sum(not r['response_contract_valid'] for r in rows)}
