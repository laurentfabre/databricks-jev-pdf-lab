"""Synthetic text and SQL emulator only; no PDFs, network or real-data assembly."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from span_reorder import inspect_preservation, sql_expression, validate


def fixture():
    source = 'A甲BéC'
    candidate = 'C\nA甲Bé甲'
    plan = {'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'source_characters':5,'source_bytes':8,'repeated_ranges':[[1,2]],
        'pieces':[{'start':4,'stop':5},{'separator':'\n'},{'start':0,'stop':4},{'start':1,'stop':2}],
        'expected_characters':7,'expected_bytes':12}
    return source,candidate,plan


class SpanReorderTests(unittest.TestCase):
    def setUp(self): self.source,self.candidate,self.plan=fixture()
    def reject(self):
        with self.assertRaises(ValueError): validate(self.plan)
    def test_complete_preservation(self):
        result=inspect_preservation(self.source,self.candidate,self.plan)
        self.assertTrue(result['all_source_characters_preserved'])
        self.assertFalse(result['quality_accepted']); self.assertFalse(result['semantic_equivalence_proven'])
    def test_sql_unicode_offsets(self):
        db=sqlite3.connect(':memory:')
        db.create_function('concat',-1,lambda *parts: ''.join(parts))
        actual=db.execute('SELECT '+sql_expression(self.plan)+' FROM (SELECT ? AS input_text)',(self.source,)).fetchone()[0]
        self.assertEqual(actual,self.candidate); db.close()
    def test_exact_sql(self):
        self.assertEqual(sql_expression(self.plan),
            'concat(substring(input_text,5,1),char(10),substring(input_text,1,4),substring(input_text,2,1))')
    def test_mapping(self):
        rows=validate(self.plan)
        self.assertEqual(rows[-1],{'start':6,'stop':7,'source_start':1,'source_stop':2})
    def test_inputs_not_mutated(self):
        before=deepcopy(self.plan); inspect_preservation(self.source,self.candidate,self.plan)
        self.assertEqual(before,self.plan)
    def test_gap(self): self.plan['pieces'][2]['stop']=3; self.reject()
    def test_unregistered_repeat(self): self.plan['repeated_ranges']=[]; self.reject()
    def test_missing_repeat(self): self.plan['pieces'].pop(); self.reject()
    def test_empty_piece(self): self.plan['pieces'][0]['stop']=4; self.reject()
    def test_negative(self): self.plan['pieces'][2]['start']=-1; self.reject()
    def test_bool_offset(self): self.plan['pieces'][0]['start']=True; self.reject()
    def test_large_offset(self): self.plan['pieces'][0]['stop']=6; self.reject()
    def test_unsupported_literal(self): self.plan['pieces'][1]['separator']='invented'; self.reject()
    def test_extra_key(self): self.plan['pieces'][0]['extra']=True; self.reject()
    def test_overlapping_repeat(self): self.plan['repeated_ranges'].append([1,3]); self.reject()
    def test_length(self): self.plan['expected_characters']=8; self.reject()
    def test_column_injection(self):
        with self.assertRaises(ValueError): sql_expression(self.plan,'input_text); DROP TABLE x')
    def test_stale_hash(self):
        self.plan['source_sha256']='0'*64
        with self.assertRaises(ValueError): inspect_preservation(self.source,self.candidate,self.plan)
    def test_changed_candidate(self):
        with self.assertRaises(ValueError): inspect_preservation(self.source,self.candidate.replace('C','X'),self.plan)
    def test_wrong_byte_length(self):
        self.plan['expected_bytes']=7
        with self.assertRaises(ValueError): inspect_preservation(self.source,self.candidate,self.plan)


if __name__=='__main__': unittest.main()
