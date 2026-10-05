"""Prospective reference freeze must fail closed on unresolved generators."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from pact_generalization_physical import select_reference


def records():
    return [dict(method=m,status='QUALIFIED',generator_status='PASS',routed_scan_wirelength_um=w)
            for m,w in zip(('B0','B1','B2','B3T'),(80,70,60,50))]


def test_minimum_qualified_routed_cost():
    rows=records()
    rows[3]['status']='FAILED'
    assert select_reference(rows)['method']=='B2'


def test_missing_generator_blocks_provisional_selection():
    rows=records()
    rows[2].update(status='FAILED',generator_status='FAIL')
    with pytest.raises(ValueError,match='Unresolved'):
        select_reference(rows)


def test_no_qualified_reference_blocks_search():
    rows=records()
    for row in rows:
        row['status']='FAILED'
    with pytest.raises(ValueError,match='No permitted'):
        select_reference(rows)
