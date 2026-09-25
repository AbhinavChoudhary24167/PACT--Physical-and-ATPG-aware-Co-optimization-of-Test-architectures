"""Focused independent reference checks for the new exact move evaluator."""
import time
import numpy as np
import pytest
pytest.importorskip('numba')
from pact.optimizer.costs import ShiftState,PlacedCosts
from pact.optimizer.io import synthetic,orders_for,architecture_from,pattern_array
from pact.optimizer.search import Config,Archive,optimize,proposal,locate,update_locations
from pact.optimizer.cli import warmup
from pact.analysis.phase2a_shift import local_windows
from pact.analysis.phase2cr_loads import construct_weights
from test_phase2cr_loads import case


def direct(patterns,orders,costs):
    n=patterns.shape[1];longest=max(map(len,orders));state=np.zeros(n,np.uint8)
    field=[]
    weight=np.zeros((n,2))
    for ci,o in enumerate(orders):
        for j,node in enumerate(o):weight[node]=costs.weight(int(node),int(o[j+1]) if j+1<len(o) else -1,ci)
    for target in patterns:
        for t in range(longest):
            before=state.copy()
            for order in orders:
                bit=0 if t<longest-len(order) else target[order[longest-1-t]]
                state[order[0]]=bit;state[order[1:]]=before[order[:-1]]
            bins=np.zeros((100,2))
            np.add.at(bins,costs.bins,(state^before)[:,None]*weight)
            field.append(bins)
        np.testing.assert_array_equal(state,target)
    return np.array(field).reshape(len(patterns),longest,100,2)


@pytest.mark.parametrize('n,k',[(4,1),(11,3),(24,2)])
def test_random_moves_match_independent_cycle_replay_and_rollback(n,k):
    arch,costs,patterns,starts,_=synthetic(n,k,5)
    state=ShiftState(costs,patterns,starts[0][1]);locate(state)
    rng=np.random.default_rng(90);neighbors=np.tile(np.arange(n),(n,1))
    original=state.field.copy();original_orders=[o.copy() for o in state.orders]
    for step in range(80):
        patch,_=proposal(state,neighbors,rng,step,8)
        if patch is None:continue
        previous=state.field.copy();undo=state.change(patch)
        expected=direct(patterns,state.orders,costs)
        np.testing.assert_allclose(state.field,expected,rtol=1e-11,atol=1e-9)
        physical=sum(costs.edge(o,ci,j) for ci,o in enumerate(state.orders) for j in range(-1,len(o)))
        assert state.physical==pytest.approx(physical,abs=1e-7)
        score=state.score()
        for q in range(2):
            bins=expected[:,:,:,q].reshape(-1,10,10)
            assert score[1+q*2]==pytest.approx(bins.sum())
            assert score[2+q*2]==pytest.approx(local_windows(bins).max())
        if step%2:
            state.change(undo)
            np.testing.assert_allclose(state.field,previous,rtol=1e-11,atol=1e-9)
        else:update_locations(state,patch)


def test_repaired_topology_weights_and_tail_transfer(case):
    arch,graph,loads=case
    costs=PlacedCosts(arch,graph,loads,[-10,-10,110,110])
    patterns=np.array([[0,1,0,1],[1,0,1,1],[1,1,0,0]],np.uint8)
    state=ShiftState(costs,patterns,orders_for(arch,costs))
    for patch in ({0:(np.array([0,1]),np.array([1,0]))},{0:(np.array([1]),np.array([3])),1:(np.array([1]),np.array([0]))}):
        state.change(patch)
        selected=architecture_from(arch,costs,state.orders)
        expected=construct_weights(selected,graph,loads)
        actual={costs.names[int(n)]:state.weights[ci][j] for ci,o in enumerate(state.orders) for j,n in enumerate(o)}
        for i,n in enumerate(sorted(costs.names)):
            np.testing.assert_allclose(actual[n],[expected['M3_load'][i],expected['M5_hpwl'][i]],rtol=1e-13,atol=1e-12)
        np.testing.assert_allclose(state.field,direct(patterns,state.orders,costs),rtol=1e-12,atol=1e-10)


def test_bounded_archive_preserves_extremes():
    archive=Archive(5)
    for i in range(30):archive.insert(np.array([i,30-i,i,30-i,i],float),[np.array([i])],'test')
    assert len(archive.rows)==5
    assert min(r['score'][0] for r in archive.rows)==0
    assert min(r['score'][1] for r in archive.rows)==1


def test_deadline_legal_outputs_and_anytime():
    warmup();arch,costs,p,starts,_=synthetic(24,2,4);checkpoints=[]
    result=optimize(costs,p,starts,Config(time_budget=.4,log_interval=.1),lambda a,r:checkpoints.append(r))
    assert result['runtime_seconds']<1.5 and result['local_evaluations']>0
    assert len(checkpoints)>=2 and result['archive']
    for row in result['archive']:
        architecture_from(arch,costs,row['orders'])
        state=ShiftState(costs,p,row['orders'])
        np.testing.assert_allclose(row['score'],state.score(),rtol=1e-9,atol=1e-6)
    values=[list(r['best'].values()) for r in checkpoints]
    assert np.all(np.diff(values,axis=0)<=1e-6)


def test_tiny_deadline_returns_supplied():
    _,costs,p,starts,_=synthetic(24,2,4)
    result=optimize(costs,p,starts,Config(time_budget=1e-12))
    assert result['status']=='BUDGET_EXHAUSTED_BEFORE_EXACT_SCORE'
    assert result['fallback_orders'] is starts[0][1]


def test_input_validation_before_uint8_cast():
    for bad in (256,-1,.5,float('nan')):
        with pytest.raises(ValueError):pattern_array([{'x':bad}],['x'])
    with pytest.raises(ValueError):Config(time_budget=float('nan'))
    with pytest.raises(ValueError):Config(wire_allowance=-1)


def test_fft_initialization_matches_direct_kernel():
    from pact.optimizer.costs import add_long_chain
    from pact.optimizer import kernels
    _,costs,p,starts,_=synthetic(2100,2,2)
    o=starts[0][1][0];d=kernels.diagonals(p,o,len(o));b=costs.bins[o]
    w=np.array([costs.weight(int(n),int(o[j+1]) if j+1<len(o) else -1,0) for j,n in enumerate(o)])
    direct_field=np.zeros((2,len(o),100,2));fft=direct_field.copy()
    kernels.add_chain(direct_field,d,b,w);add_long_chain(fft,d,b,w,None)
    np.testing.assert_allclose(fft,direct_field,rtol=1e-11,atol=1e-8)


def test_slow_checkpoints_leave_time_for_search():
    warmup();_,costs,p,starts,_=synthetic(16,2,2)
    writes=[]
    def slow_writer(rows,progress):
        writes.append(progress['evaluations'])
        time.sleep(.02)
    result=optimize(costs,p,starts,Config(time_budget=.6,log_interval=.001),slow_writer)
    assert result['local_evaluations']>50
    # Previously every move immediately rewrote a slow checkpoint.
    assert len(writes)<15
    assert result['timings']['checkpoint']>=.02*len(writes)
