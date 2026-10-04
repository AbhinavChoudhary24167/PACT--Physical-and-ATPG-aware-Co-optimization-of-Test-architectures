import numpy as np
import pytest
from pact.analysis.h8_rootcause import (match_architecture,source_index,compare_bins,
    decompose_net,canonical_json,write_csv,pair_classification)


def test_architecture_matching_full_design_and_hash():
    rows=[dict(design='a',architecture_sha256='1234'),dict(design='b',architecture_sha256='1234')]
    assert match_architecture('a','1234',rows) is rows[0]
    with pytest.raises(ValueError):
        match_architecture('a','123',rows)
    with pytest.raises(ValueError):
        match_architecture('a','1234',rows+[rows[0]])


def test_bin_alignment_raw_residual_and_temporal_maxima():
    p=np.zeros((2,64)); m=p.copy()
    p[0,1]=3; p[1,2]=2; m[0,1]=1; m[1,2]=5
    rows,peak=compare_bins(p,m,[0,0,8,8],[0,0,8,8])
    assert rows[1]['residual']==-2
    assert rows[2]['residual']==3
    assert rows[2]['residual_at_measured_peak_cycle']==3
    assert peak['peak_moved'] and peak['pred_peak_cycle']==0 and peak['meas_peak_cycle']==1
    assert rows[1]['predicted_rank']==1 and rows[2]['measured_rank']==1
    with pytest.raises(ValueError):
        compare_bins(p,m,[0,0,8,8],[0,0,9,8])
    with pytest.raises(ValueError):
        compare_bins(p,m[:1],[0,0,8,8],[0,0,8,8])


def test_net_attribution_exact_activity_cap_and_source_move():
    p=np.array([1,0,2]); m=np.array([2,1,0])
    parts=decompose_net(p,m,3,5,1,9,3)
    residual=np.zeros((3,64)); residual[:,1]-=p*3; residual[:,9]+=m*5
    np.testing.assert_array_equal(sum(parts.values()),residual)
    np.testing.assert_array_equal(parts['activity'][:,1],(m-p)*3)
    np.testing.assert_array_equal(parts['capacitance'][:,1],m*2)
    assert parts['geometry'].sum()==0


def test_unmatched_missing_data_is_explicit_and_invalid_cap_fails():
    p=np.array([1,0]); z=np.zeros(2)
    parts=decompose_net(None,p,None,4,None,2,2)
    assert parts['unmatched'][:,2].tolist()==[4,0]
    parts=decompose_net(p,None,4,None,2,None,2)
    assert parts['unmatched'][:,2].tolist()==[-4,0]
    assert sum(v.sum() for v in decompose_net(None,z,None,None,None,2,2).values())==0
    with pytest.raises(ValueError,match='missing capacitance'):
        decompose_net(None,p,None,None,None,2,2)
    with pytest.raises(ValueError,match='alignment'):
        decompose_net(p,p[:1],4,4,1,1,2)
    with pytest.raises(ValueError,match='Both'):
        decompose_net(None,None,None,None,None,None,2)
    with pytest.raises(ValueError,match='Invalid capacitance'):
        decompose_net(p,p,4,float('nan'),1,1,2)
    with pytest.raises(ValueError,match='source bin'):
        decompose_net(p,p,4,4,1,64,2)
    with pytest.raises(ValueError,match='Ambiguous'):
        source_index({'n':{'source':'c/Q'},'renamed':{'source':'c/Q'}})


def test_deterministic_serialization_and_pair_tolerance(tmp_path):
    assert canonical_json({'z':1,'a':None})==canonical_json({'a':None,'z':1})
    with pytest.raises(ValueError):
        canonical_json({'invalid':float('nan')})
    path=tmp_path/'rows.csv'
    write_csv(path,[{'name':'n','missing':None,'value':2}])
    first=path.read_bytes()
    write_csv(path,[{'name':'n','missing':None,'value':2}])
    assert path.read_bytes()==first and b'n,,2\n' in first
    assert pair_classification(1,2,3,2)=='reversal'
    assert pair_classification(1,1+1e-9,3,2)=='predicted_tie'
