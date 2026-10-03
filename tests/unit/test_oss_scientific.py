"""Preserve tradeoffs and the measured scope of frozen Stage-A questions."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from pact_oss_scientific import analyze


def row(method, sha, wire, energy, hotspot, selected='True', representative='True', status='QUALIFIED'):
    return dict(design='s5378',method=method,architecture_hash=sha,routed_scan_path_cost_um=wire,
        measured_E=energy,measured_H8=hotspot,selected=selected,representative=representative,status=status,roles='balanced')


def test_partial_external_scope_cannot_claim_complete_A1():
    answer=analyze([row('B0','b0',10,10,10),row('P0','p0',9,9,9)])['s5378']
    assert answer['A1']['mandatory_external_methods_complete'] is False
    assert answer['qualified_external_methods']==['B0']


def test_lower_activity_with_more_wire_remains_an_explicit_tradeoff():
    answer=analyze([row('B3','b3',10,10,10),row('P0','p0',11,9,8)])['s5378']
    pair=answer['A2']['pairwise_deltas'][0]
    assert pair['routed_scan_path_cost_um']==1 and pair['activity_improvement']=='both'
    assert pair['left_dominates'] is False and pair['right_dominates'] is False


def test_lower_wire_can_increase_H8_in_A4():
    answer=analyze([row('B0','b0',10,10,10),row('B3','b3',9,8,11)])['s5378']
    pair=answer['A4'][0]
    assert pair['left_method']=='B3' and pair['physical_order']=='left_has_lower_wire'
    assert pair['routed_scan_path_cost_um']==-1 and pair['measured_H8']==1


def test_unmeasured_archive_does_not_become_a_selection_miss():
    answer=analyze([row('P0','balanced',10,10,10),
        row('P0','unknown',1,1,1,selected='False',representative='False',status='ACTIVITY_UNMEASURED')])['s5378']
    assert answer['A5']['implemented_archive_points']==1
    assert answer['A5']['unmeasured_archive_points']==1
    assert answer['A5']['unselected_archive_points_dominating_balanced']==[]


def test_failed_predeclared_P0_remains_an_unassessed_B3_comparison():
    answer=analyze([row('B3','b3',9,9,9),
        row('P0','failed',1,1,1,status='MEASUREMENT_FAILED')])['s5378']
    assert answer['A3']['B3_vs_predeclared_P0']==[None]
