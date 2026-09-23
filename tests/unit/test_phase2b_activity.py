"""Analytical fixtures, including leakage rejection and missing electrical data."""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from pact.analysis.phase2b_loads import pin_loads, hpwl, construct_weights
from pact.analysis.phase2b_reference import parse_spef
from pact.analysis.phase2b_scoring import score_packed
from pact.analysis.phase2b_waveform import record_test
from pact.analysis.phase2a_shift import fixed_bins
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain

ROOT=Path(__file__).resolve().parents[2]

def arch():
    return ScanArchitecture(tuple(ScanCell(n,float(i*3),0.,'CK') for i,n in enumerate('abc')),
        (ScanChain('0',('a','b')),ScanChain('1',('c',))))

def graph():
    return dict(stage='POST-PLACEMENT',FFs={n:dict(master='FF',roots={'Q':n}) for n in 'abc'},
        nets={n:dict(driver_xy=[i*3,0],sinks=[dict(xy=[i*3,4],master='G',pin='A')],ports=[])
              for i,n in enumerate('abc')},transparent={})

def test_liberty_nested_pin_loads_units_missing_and_invalid():
    lib='''capacitive_load_unit (1,pf);
    cell (G) { pin(A) { direction : input;
      capacitance : 0.002;
      timing() { table() { values("1,2"); } }
    } pin(Z) { direction : output; } }'''
    assert pin_loads(lib)=={('G','A'):2.}
    with pytest.raises(ValueError,match='Missing'): pin_loads(lib.replace('capacitance : 0.002;',''))
    with pytest.raises(ValueError,match='Invalid'): pin_loads(lib.replace('0.002','-1'))
    with pytest.raises(ValueError,match='unit'): pin_loads(lib.replace('pf','mystery'))

def test_placement_fanout_hpwl_star_and_pin_loads():
    result=construct_weights(arch(),graph(),{('G','A'):2.,('FF','SI'):1.},
        {'test_so':(10,0),'test_so_1':(10,0)})
    assert result['M2_scan'].tolist()==[3,0,0]
    assert result['M2_port'].tolist()==[3,7,4]
    assert result['M4_fanout'].tolist()==[2,1,1]
    assert result['M4_pin'].tolist()==[3,2,2]
    assert result['M5_hpwl'].tolist()==[7,11,8]
    assert result['M5_functional_hpwl'].tolist()==[4,4,4]
    assert np.allclose(result['M3_load'],result['M4_pin']+.103981*result['M5_hpwl'])
    assert hpwl([(0,0),(4,0),(2,3)])==7
    # HPWL avoids multiplying a shared trunk by number of sinks.
    g=graph();g['nets']['a']['sinks'].append(dict(xy=[0,2],master='G',pin='A'))
    updated=construct_weights(arch(),g,{('G','A'):2.,('FF','SI'):1.},{'test_so':(10,0),'test_so_1':(10,0)})
    assert updated['M5_hpwl'][0]==7 and updated['M5_star'][0]==9

@pytest.mark.parametrize('contamination', ['stage','route'])
def test_target_predictor_separation(contamination):
    g=graph()
    if contamination=='stage': g['stage']='POST-ROUTE'
    else: g['nets']['a']['routed_wirelength']=123
    with pytest.raises(ValueError): construct_weights(arch(),g,{}, {})

def test_transparent_graph_counts_once_and_rejects_shared_owners():
    g=graph();g['transparent']['a']=['branch','branch']
    g['nets']['branch']=dict(driver_xy=[0,4],sinks=[dict(xy=[0,5],master='G',pin='A')],ports=[])
    args=({('G','A'):2.,('FF','SI'):1.},{'test_so':(10,0),'test_so_1':(10,0)})
    weights=construct_weights(arch(),g,*args)
    assert weights['M4_functional_fanout'][0]==2
    g['transparent']['b']=['branch']
    with pytest.raises(ValueError,match='owners'): construct_weights(arch(),g,*args)

def test_chunked_toggles_spatial_peaks_and_determinism():
    toggle=np.array([[1,0,0],[0,1,1],[1,0,1],[0,1,0]],dtype=np.uint8)
    packed=np.packbits(toggle,axis=1)
    bins=fixed_bins([(0,0),(1,1),(10,10)],[0,0,10,10])
    a,counts=score_packed(packed,3,[2,3,5],bins,chunk_size=1)
    b,_=score_packed(packed,3,[2,3,5],bins,chunk_size=100)
    assert counts.tolist()==[2,2,2]
    assert a==b==dict(total=20.,local_peak=5.)
    with pytest.raises(ValueError): score_packed(packed,3,[1,-1,2],bins)

def test_capture_boundaries_padding_scanout_and_final_unload():
    loads=[dict(a=1,b=1,c=1),dict(a=0,b=0,c=0)]
    captures=[dict(a=0,b=1,c=1),dict(a=1,b=0,c=1)]
    trace,bounds=record_test(arch(),loads,captures)
    states=np.unpackbits(trace['states_packed'],axis=1)[:,:3]
    assert states.tolist()==[[1,0,0],[1,1,1],[0,1,1],[0,0,0],[0,0,0],[1,0,1],[0,1,0],[0,0,0]]
    assert bounds==[dict(pattern=0,load_start=0,capture_cycle=2),dict(pattern=1,load_start=3,capture_cycle=5)]
    assert trace['SO'][3].tolist()==[1,1]
    assert trace['SO'][-2:].tolist()==[[0,1],[1,0]]
    assert trace['SI'][0].tolist()==[1,0]  # real leading padding on short chain
    no_final,_=record_test(arch(),loads,captures,final_unload=False)
    assert len(no_final['modes'])==6
    assert np.array_equal(trace['toggles_packed'],record_test(arch(),loads,captures)[0]['toggles_packed'])
    with pytest.raises(ValueError): record_test(arch(),loads,captures[:1])
    captures[0]['a']='X'
    with pytest.raises(ValueError): record_test(arch(),loads,captures)

def test_spef_units_ground_coupling_and_accounting():
    text='''*C_UNIT 1 PF
*NAME_MAP
*1 netA
*D_NET *1 0.005
*CAP
1 *1:1 0.002
2 *1:1 *2:1 0.003
*RES
1 *1:1 *1:2 4.0
*END
'''
    parsed=parse_spef(text)['netA']
    assert parsed==dict(declared_ff=5.,ground_ff=2.,coupling_ff=3.,resistors=1,capacitors=2)
    with pytest.raises(ValueError,match='mismatch'): parse_spef(text.replace('0.005','0.009'))
    with pytest.raises(ValueError,match='Empty'): parse_spef('*C_UNIT 1 FF')

def test_statistics_ties_directions_and_equal_design_weights():
    sys.path.insert(0,str(ROOT/'scripts'))
    from phase2a_validate import correlations, weighted_corr
    assert correlations([1,2,3],[3,2,1])['spearman']==-1
    assert correlations([1,1,1],[1,2,3])['spearman'] is None
    assert weighted_corr([1,2,3],[1,2,3],[.5,.25,.25])['spearman']==pytest.approx(1)
    assert correlations([1,1,2],[1,2,2])['kendall_tau_b']==pytest.approx(.5)

def test_hash_gate_rejects_changed_evidence(tmp_path,monkeypatch):
    sys.path.insert(0,str(ROOT/'scripts'))
    import phase2b_common as common
    from pact.phase0d.campaign import file_sha256
    source=tmp_path/'input';source.write_text('frozen')
    prov=tmp_path/'provenance.json';prov.write_text(json.dumps({'inputs':{str(source):file_sha256(source)}}))
    (tmp_path/'freeze.json').write_text(json.dumps({'files':{'provenance.json':file_sha256(prov)}}))
    monkeypatch.setattr(common,'REPORT',tmp_path)
    common.integrity()
    source.write_text('changed')
    with pytest.raises(ValueError,match='frozen input'): common.integrity()


def test_pair_ties_and_decision_requires_every_design():
    sys.path.insert(0,str(ROOT/'scripts'))
    from phase2b_report import compare_pairs,gate,DESIGNS
    result=compare_pairs(['a','b','c'],np.array([1,1,2]),np.array([1,2,1]))
    assert result['counts']==dict(agree=0,disagree=1,both_tied=0,predictor_tied=1,target_tied=1)
    assert result['non_tied_agreement']==0
    targets=('wire_total','wire_local_peak','cap_total','cap_local_peak')
    stats={d:{m:{t:dict(spearman=.8,pairwise_non_tied_agreement=.8) for t in targets}
              for m in ('M0','M0_local','M1_H_eff8')} for d in DESIGNS}
    assert gate(stats,True)['classification']=='PACT_PHASE2B_SURROGATE_QUALIFIED'
    stats['s15850']['M0_local']['cap_local_peak']['spearman']=-.2
    assert gate(stats,True)['classification']!='PACT_PHASE2B_SURROGATE_QUALIFIED'
