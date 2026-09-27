import numpy as np
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.analysis.phase2a_shift import replay, fixed_bins, local_windows


def test_hand_calculated_padding_carry_and_physical_weights(tmp_path):
    arch = ScanArchitecture(tuple(ScanCell(n,float(i),0.,'CK') for i,n in enumerate('abc')),
        (ScanChain('C00',('a','b')),ScanChain('C01',('c',))))
    # Cycle states: 100,111; next load includes a real leading pad on c: 010,000.
    # Toggles: 100,011,101,010 -> counts 1,2,2,1; weights 2,8,7,3.
    patterns = [dict(a=1,b=1,c=1),dict(a=0,b=0,c=0)]
    metric,proof = replay(arch,patterns,dict(a=2,b=3,c=5),
        dict(a=(0.,0.),b=(1.,0.),c=(2.,0.)),[0,0,10,10],tmp_path/'trace.npz')
    assert metric['raw_total']==6 and metric['raw_peak']==2
    assert metric['weighted_total']==20 and metric['weighted_peak']==8
    assert proof['cycles_replayed']==4
    assert proof['internal_scan_link_source_transitions']==2
    assert [r['transitions'] for r in proof['transitions_per_pattern']]==[3,3]
    data = np.load(tmp_path/'trace.npz')
    assert np.unpackbits(data['states_packed'],axis=1)[:,:3].tolist()==[[1,0,0],[1,1,1],[0,1,0],[0,0,0]]
    assert data['raw_per_cycle'].tolist()==[1,2,2,1]


def test_bin_boundaries_and_unweighted_local_sum():
    assert fixed_bins([(0,0),(1,1),(10,10)],[0,0,10,10]).tolist()==[0,11,99]
    bins=np.zeros((2,10,10));bins[0,0,0]=2;bins[0,1,1]=3;bins[1,9,9]=7
    local=local_windows(bins)
    assert local.shape==(2,9,9)
    assert local[0,0,0]==5 and local[1,8,8]==7
