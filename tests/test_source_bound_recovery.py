from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from source_bound_recovery import derive, digest, inline_prices, text_hash
from quality_gates import unwrap


def fixture(fragment='Garden dumplings with extra saffron (+ €7.25)'):
    text = '[SOURCE PAGE 1]\n'+fragment+'\nBase price 24 EUR'
    start, stop = text.index(fragment), text.index(fragment)+len(fragment)
    box = lambda value: {'value':value,'citation_ids':[0]}
    item = {'name':box(fragment),'details':box(fragment),
            'prices':[{'amount':box(24),'currency':box('EUR'),'basis':box('portion')}],
            'source_pages':[box(1)], 'dietary_markers':[box('signature')], 'allergens':[]}
    raw = {'error_message':None, 'metadata':{'mode':'precision','version':'2.1','chunk_type':'span',
                'citations':[{'id':0,'start':start,'stop':stop}]},
           'response':{'items':[item], 'policies':[], 'dietary_allergen_legend':[]}}
    scopes = [{'element_id':0,'page':1,'start':start,'stop':len(text)}]
    groups = [{'id':'g1','physical_page':1,'element_ids':[0],'kind':'priced_item','fragments':[fragment]}]
    return raw,text,scopes,groups,text_hash(text)


class SourceBoundRecoveryTests(unittest.TestCase):
    def run_case(self, args):
        before = deepcopy(args)
        shadow,audit = derive(*args)
        self.assertEqual(args,before)
        self.assertFalse(audit['quality_accepted'])
        self.assertTrue(audit['semantic_review_required'])
        self.assertEqual(audit['raw_response_canonical_sha256'],digest(args[0]))
        return shadow,audit

    def no_change(self,args):
        shadow,audit=self.run_case(args)
        self.assertEqual(shadow,args[0])
        self.assertEqual(audit['changes'],[])
        return audit

    def test_exact_price_and_full_condition_preserved(self):
        args=fixture()
        shadow,audit=self.run_case(args)
        price=unwrap(shadow['response']['items'][0]['prices'][-1])
        self.assertEqual(price,{'amount':7.25,'currency':'EUR','basis':args[3][0]['fragments'][0]})
        self.assertEqual(len(audit['changes']),1)
        self.assertEqual(audit['candidate_occurrences'],2)

    def test_decimal_currencies_and_non_menu_syntax(self):
        for literal,amount,currency in [('(+ 8,50 EUR)','8.50','EUR'),('(+£6)','6','GBP'),
                ('(+ US$4.05)','4.05','USD'),('(+ 0 USD)','0','USD'),('(+\u00a05\u202f€)','5','EUR')]:
            args=fixture('Airport transfer after midnight '+literal)
            shadow,audit=self.run_case(args)
            price=unwrap(shadow['response']['items'][0]['prices'][-1])
            self.assertEqual((Decimal(str(price['amount'])),price['currency']),(Decimal(amount),currency))
            self.assertEqual(len(audit['changes']),1)

    def test_unsupported_money_grammar(self):
        for literal in ['(+$5)','(+ €1,234)','(+ 1.234,50 EUR)','(- €5)','(+ €1.234)','(+ 5%)','+ €8']:
            self.assertEqual(inline_prices(literal),[])

    def test_nonmatching_source_fragment(self):
        args=fixture()
        args[0]['response']['items'][0]['name']['value']='Unrelated soup'
        args[0]['response']['items'][0]['details']['value']='A copied amount (+ €7.25)'
        self.no_change(args)

    def test_details_only_support(self):
        args=fixture()
        args[0]['response']['items'][0]['name']['value']='Garden dumplings'
        shadow,audit=self.run_case(args)
        self.assertEqual(len(audit['changes']),1)
        self.assertEqual(audit['considered'][0]['candidates'][0]['source_field'],'details')

    def test_details_cannot_lend_unrelated_item_identity(self):
        args=fixture();args[0]['response']['items'][0]['name']['value']='Different noodles'
        audit=self.no_change(args)
        self.assertIn('no_cited_name_anchor',[i['reason'] for i in audit['issues']])

    def test_name_citation_cannot_be_replaced_by_details_citation(self):
        args=fixture();args[0]['response']['items'][0]['name']['citation_ids']=[]
        self.no_change(args)

    def test_name_prefix_boundary(self):
        args=fixture();args[0]['response']['items'][0]['name']['value']='Garden dumpling'
        self.no_change(args)

    def test_existing_numeric_pair_not_duplicated_or_certified(self):
        args=fixture()
        args[0]['response']['items'][0]['prices'][0]['amount']['value']=7.25
        audit=self.no_change(args)
        self.assertEqual(audit['considered'][0]['status'],'numeric_pair_already_present_basis_not_validated')

    def test_same_amount_wrong_currency_is_not_same_pair(self):
        args=fixture()
        price=args[0]['response']['items'][0]['prices'][0]
        price['amount']['value'],price['currency']['value']=7.25,'GBP'
        shadow,audit=self.run_case(args)
        self.assertEqual(len(audit['changes']),1)
        self.assertEqual(shadow['response']['items'][0]['prices'][0],price)

    def test_malformed_existing_price_abstains(self):
        for value in (True,None,'7.25',float('inf')):
            args=fixture()
            args[0]['response']['items'][0]['prices'][0]['amount']['value']=value
            if value==float('inf'):
                with self.assertRaises(ValueError):derive(*args)
            else:self.no_change(args)
        args=fixture()
        args[0]['response']['items'][0]['prices']=[None]
        self.no_change(args)

    def test_unknown_currency_abstains(self):
        args=fixture()
        args[0]['response']['items'][0]['prices'][0]['currency']['value']='unknown'
        self.no_change(args)

    def test_no_prices_array_abstains(self):
        args=fixture()
        args[0]['response']['items'][0]['prices']=None
        self.no_change(args)

    def test_empty_prices_array_allows_only_candidate_not_acceptance(self):
        args=fixture()
        args[0]['response']['items'][0]['prices']=[]
        _,audit=self.run_case(args)
        self.assertEqual(len(audit['changes']),1)

    def test_wrong_page_abstains(self):
        args=fixture()
        args[0]['response']['items'][0]['source_pages']=[{'value':2}]
        self.no_change(args)

    def test_missing_pages_abstains(self):
        args=fixture()
        args[0]['response']['items'][0]['source_pages']=[]
        self.no_change(args)

    def test_missing_citations_abstain(self):
        args=fixture()
        for field in ('name','details'):args[0]['response']['items'][0][field]['citation_ids']=[]
        self.no_change(args)

    def test_out_of_bounds_citations_abstain(self):
        args=fixture()
        args[0]['metadata']['citations'][0]['stop']=len(args[1])+1
        self.no_change(args)

    def test_uncited_gap_not_bridged(self):
        args=fixture()
        citation=args[0]['metadata']['citations'][0]
        start,stop=citation['start'],citation['stop']
        args[0]['metadata']['citations']=[{'id':0,'start':start,'stop':start+5},
                                        {'id':1,'start':start+6,'stop':stop}]
        for field in ('name','details'):args[0]['response']['items'][0][field]['citation_ids']=[0,1]
        self.no_change(args)

    def test_adjacent_citations_cover_fragment(self):
        args=fixture()
        citation=args[0]['metadata']['citations'][0]
        start,stop=citation['start'],citation['stop']
        args[0]['metadata']['citations']=[{'id':0,'start':start,'stop':start+5},
                                        {'id':1,'start':start+5,'stop':stop}]
        for field in ('name','details'):args[0]['response']['items'][0][field]['citation_ids']=[0,1]
        _,audit=self.run_case(args)
        self.assertEqual(len(audit['changes']),1)

    def test_source_scope_excludes_literal(self):
        args=fixture()
        args[2][0]['start']+=1
        self.no_change(args)

    def test_duplicate_output_ownership_abstains(self):
        args=fixture()
        args[0]['response']['items'].append(deepcopy(args[0]['response']['items'][0]))
        self.no_change(args)

    def test_ambiguous_groups_abstain(self):
        args=fixture()
        group=deepcopy(args[3][0]);group['id']='g2';args[3].append(group)
        self.no_change(args)

    def test_duplicate_group_id_rejected(self):
        args=fixture();args[3].append(deepcopy(args[3][0]))
        with self.assertRaises(ValueError):derive(*args)

    def test_cross_page_group_rejected(self):
        args=fixture();args[3][0]['physical_page']=2
        with self.assertRaises(ValueError):derive(*args)

    def test_non_priced_preparation_never_promoted(self):
        args=fixture();args[3][0]['kind']='inline_unpriced_row'
        self.no_change(args)

    def test_known_conditional_wording_abstains(self):
        for prefix in ('not available: ','optional ','formerly ','instead of '):
            self.no_change(fixture(prefix+'Garden dumplings (+ €7.25)'))

    def test_negated_output_context_abstains(self):
        args=fixture()
        for field in ('name','details'):
            args[0]['response']['items'][0][field]['value']='not available: '+args[3][0]['fragments'][0]
        self.no_change(args)

    def test_two_supplements_in_one_fragment_abstain(self):
        self.no_change(fixture('Garden dumplings with saffron (+ €7.25) and broth (+ €3)'))

    def two_fragments(self, second):
        args=list(fixture());first=args[3][0]['fragments'][0]
        text=args[1]+'\n'+second;args[1]=text;args[4]=text_hash(text)
        args[2][0]['stop']=len(text);args[3][0]['fragments'].append(second)
        args[0]['metadata']['citations'][0]['stop']=len(text)
        for field in ('name','details'):args[0]['response']['items'][0][field]['value']=first+' / '+second
        return args

    def test_different_missing_pairs_abstain(self):
        self.no_change(self.two_fragments('Garden dumplings with extra broth (+ €3)'))

    def test_alternative_same_price_fragments_remain_in_audit(self):
        args=self.two_fragments('Raviolis du jardin avec safran (+ 7,25 EUR)')
        _,audit=self.run_case(args)
        self.assertEqual(len(audit['changes']),1)
        self.assertEqual(len(audit['considered'][0]['candidates']),4)

    def test_negative_details_prevent_positive_name_transfer(self):
        args=fixture();args[0]['response']['items'][0]['details']['value']='not available'
        self.no_change(args)

    def test_wrong_input_hash_rejected(self):
        args=list(fixture());args[-1]='0'*64
        with self.assertRaises(ValueError):derive(*args)

    def test_non_precision_rejected(self):
        args=fixture();args[0]['metadata']['mode']='fast'
        with self.assertRaises(ValueError):derive(*args)

    def test_existing_metadata_and_fields_unchanged(self):
        args=fixture();shadow,audit=self.run_case(args)
        self.assertEqual(shadow['metadata'],args[0]['metadata'])
        copied=deepcopy(shadow);copied['response']['items'][0]['prices'].pop()
        self.assertEqual(copied,args[0])
        for field in shadow['response']['items'][0]['prices'][-1].values():
            self.assertEqual(set(field),{'value','citation_ids'})

    def test_shadow_derivation_idempotent(self):
        args=list(fixture());shadow,_=self.run_case(args);args[0]=shadow
        self.no_change(args)

    def test_short_fragment_not_identity(self):
        self.no_change(fixture('Side (+ €7.25)'))


if __name__=='__main__':unittest.main()
