"""Adversarial equivalence independent of event propagation internals."""
import numpy as np
import pytest
from pact.analysis.phase2c_events import (shift_events,event_driven_evaluator,
    reference_packed_evaluator,pattern_inputs,chain_indices,packed_peak_witness)
from pact.analysis.phase2a_shift import fixed_bins
from pact.scan.model import ScanArchitecture,ScanCell,ScanChain
from pact.scan.phase0c import parallel_schedule


def dense(chains,inputs,initial=None):
    n=sum(map(len,chains));state=np.zeros(n,dtype=np.uint8) if initial is None else np.array(initial,dtype=np.uint8)
    rows=[]
    for values in inputs:
        old=state.copy()
        for chain,v in zip(chains,values):
            state[chain[0]]=v
            for a,b in zip(chain,chain[1:]):state[b]=old[a]
        rows.append(state^old)
    return np.array(rows,dtype=np.uint8).reshape(-1,n)


@pytest.mark.parametrize('lengths',[(1,),(2,1),(5,3),(8,7,1)])
@pytest.mark.parametrize('mode',['zero','ones','alternate','random'])
def test_initial_padding_unload_and_every_cycle(lengths,mode):
    n=sum(lengths);chains=np.split(np.arange(n),np.cumsum(lengths)[:-1]);rng=np.random.default_rng(23)
    inputs={'zero':np.zeros((35,len(chains)),dtype=int),'ones':np.ones((35,len(chains)),dtype=int),
        'alternate':np.tile((np.arange(35)%2)[:,None],(1,len(chains))),
        'random':rng.integers(0,2,(35,len(chains)))}[mode]
    inputs=np.concatenate((inputs,np.zeros((max(lengths),len(chains)),dtype=int)))
    initial=rng.integers(0,2,n) if mode=='random' else np.zeros(n,dtype=int)
    toggle=dense(chains,inputs,initial);observed=np.zeros_like(toggle)
    for cycle,ids in shift_events(chains,inputs,initial):observed[cycle,ids]=1
    assert np.array_equal(observed,toggle)
    bins=(np.arange(n)*11)%100;weights=rng.random(n)*100
    packed=np.packbits(toggle,axis=1)
    ref,c1=reference_packed_evaluator(packed,n,weights,bins)
    got,c2=event_driven_evaluator(shift_events(chains,inputs,initial),n,weights,bins,len(inputs))
    assert np.array_equal(c1,c2)
    assert got['event_count']==int(toggle.sum())
    for k in ref:assert got[k]==pytest.approx(ref[k],rel=1e-12,abs=1e-10)
    assert got['peak_location']==packed_peak_witness(packed,n,weights,bins)


def test_patterns_repeated_states_leading_padding_and_final_unload():
    arch=ScanArchitecture(tuple(ScanCell(n,i,0,'CK') for i,n in enumerate('abc')),
        (ScanChain('0',('a','b')),ScanChain('1',('c',))))
    patterns=[dict(a=1,b=0,c=1)]*3+[dict(a=0,b=0,c=0)]
    actual=list(pattern_inputs(arch,patterns,True))
    assert actual==[v for p in patterns for v in parallel_schedule(arch,p)]+[(0,0)]*2
    assert actual[0][1]==0
    names,chains=chain_indices(arch);trace=dense(chains,actual)
    assert trace.shape==(10,3)
    assert sum(len(ids) for _,ids in shift_events(chains,actual))==int(trace.sum())


def test_boundary_bins_multiple_windows_and_tied_maxima():
    bins=fixed_bins([(0,0),(1,1),(10,10),(5,5)],[0,0,10,10])
    assert bins.tolist()==[0,11,99,55]
    events=[(0,np.array([0,1])),(2,np.array([0,1])),(3,np.array([2]))]
    got,counts=event_driven_evaluator(events,4,[2,3,5,0],bins,4)
    assert got['local_peak']==5 and got['peak_location']==[0,0,0]
    assert counts.tolist()==[2,2,1,0]


@pytest.mark.parametrize('cycles',[0,1,100])
def test_empty_constant_stream(cycles):
    got,c=event_driven_evaluator([],1,[1],np.array([99]),cycles)
    assert got['total']==got['local_peak']==got['event_count']==0
    assert got['peak_location']==([0,0,0] if cycles else None)
    assert c.tolist()==[0]


@pytest.mark.parametrize('events', [[(0,[0,0])],[(1,[0]),(0,[0])],[(4,[0])],[(0,[-1])],[(0,[1])]])
def test_reject_invalid_events(events):
    with pytest.raises(ValueError):event_driven_evaluator(events,1,[1],np.array([0]),4)


def test_load_graph_branches_multiple_sinks_and_si_so():
    # Reuse the exact existing graph API; include BUF and INV branch loads.
    from pact.analysis.phase2b_loads import construct_weights
    arch=ScanArchitecture((ScanCell('a',0,0,'CK'),ScanCell('b',3,0,'CK')),
                          (ScanChain('0',('a','b')),))
    g=dict(stage='POST-PLACEMENT',FFs={n:dict(master='FF',roots={'Q':n}) for n in 'ab'},
       nets={'a':dict(driver_xy=[0,0],ports=[],sinks=[dict(xy=[1,0],master='BUF',pin='A'),dict(xy=[0,2],master='INV',pin='A')]),
             'b':dict(driver_xy=[3,0],ports=[],sinks=[]),
             'buf':dict(driver_xy=[1,0],ports=[],sinks=[dict(xy=[2,0],master='G',pin='A')]),
             'inv':dict(driver_xy=[0,2],ports=[],sinks=[dict(xy=[0,4],master='G',pin='A')])},
       transparent={'a':['buf','inv']})
    weights=construct_weights(arch,g,{(m,p):1 for m,p in [('FF','SI'),('BUF','A'),('INV','A'),('G','A')]},{'test_so':(5,0)})
    assert weights['M4_pin'].tolist()==[5,0]
    assert weights['M5_hpwl'].tolist()==[8,2]
    for key in ['M3_load','M5_hpwl']:
        r,_=event_driven_evaluator([(0,np.array([0,1]))],2,weights[key],np.array([0,0]),1)
        assert r['total']==r['local_peak']==sum(weights[key])
