"""Exact shift transition propagation and sparse activity accumulation.

A transition injected at the chain head moves one position per clock until
it leaves the tail. Initial adjacent-state boundaries behave identically.
No N_ff x cycles state history or FF-pair matrix is constructed. Waveform
input inspection is O(K*T + P*N); propagation is O(E), bins O(B*T_active).
"""
from __future__ import annotations
import numpy as np
from pact.analysis.phase2a_shift import local_windows
from pact.analysis.phase2b_scoring import score_packed as reference_packed_evaluator


def chain_indices(arch):
    names=sorted(c.name for c in arch.cells)
    index={n:i for i,n in enumerate(names)}
    chains=[np.array([index[n] for n in c.cells],dtype=np.int64) for c in arch.chains]
    flat=np.concatenate(chains) if chains else np.array([],dtype=np.int64)
    if not chains or any(len(c)==0 for c in chains) or sorted(flat.tolist())!=list(range(len(names))):
        raise ValueError('Chains must partition the FF inventory')
    return names,chains


def pattern_inputs(arch, patterns, final_unload=False):
    """Lazy SI cycles with EXACT existing leading-padding/tail-first policy."""
    names,chains=chain_indices(arch);longest=max(map(len,chains))
    for pattern in patterns:
        if set(pattern)!=set(names) or any(type(v) is not int or v not in (0,1) for v in pattern.values()):
            raise ValueError('One binary bit per FF required')
        streams=[(0,)*(longest-len(c.cells))+tuple(pattern[n] for n in reversed(c.cells)) for c in arch.chains]
        yield from zip(*streams)
    if final_unload:
        for _ in range(longest):yield (0,)*len(chains)


def shift_events(chains, inputs, initial=None):
    """Yield (zero-based cycle, unique FF indices) for nonempty transitions.

    Chains index the sorted FF inventory. ``inputs`` can be streamed; initial
    state is optional (zero by default). Every-cycle clocks include empty
    activity cycles, but those cycles do not reach the accumulator.
    """
    chains=[np.asarray(c,dtype=np.int64) for c in chains]
    flat=np.concatenate(chains) if chains else np.array([],dtype=np.int64)
    n=len(flat)
    if not chains or any(not len(c) for c in chains) or sorted(flat.tolist())!=list(range(n)):
        raise ValueError('Invalid chain partition')
    state=np.zeros(n,dtype=np.uint8) if initial is None else np.asarray(initial)
    if state.shape!=(n,) or np.any((state!=0)&(state!=1)):raise ValueError('Invalid initial state')
    head=[int(state[c[0]]) for c in chains]
    # Before the first edge, internal differences already specify its events.
    active=[np.flatnonzero(state[c[1:]]!=state[c[:-1]])+1 for c in chains]
    for cycle,values in enumerate(inputs):
        if len(values)!=len(chains) or any(v not in (0,1) for v in values):raise ValueError('Invalid SI cycle')
        changed=[]
        for j,(c,value) in enumerate(zip(chains,values)):
            positions=active[j]
            if value!=head[j]:positions=np.concatenate((np.array([0],dtype=np.int64),positions))
            head[j]=int(value)
            if len(positions):changed.append(c[positions])
            following=positions+1
            active[j]=following[following<len(c)]
        if changed:yield cycle,np.concatenate(changed)


def packed_events(packed,n_ff):
    """Independent proof adapter only; production never decodes packed traces."""
    for cycle,row in enumerate(packed):
        ids=np.flatnonzero(np.unpackbits(row)[:n_ff])
        if len(ids):yield cycle,ids


def event_driven_evaluator(events,n_ff,weights,bins,n_cycles,validate=True):
    """Accumulate a strictly cycle-ordered stream; one event per FF per edge.

    ``validate=False`` is for the internally guaranteed shift_events producer;
    public/untrusted event streams default to uniqueness/range validation.
    Total is the identical counts dot weights used by the packed reference.
    A cycle/window witness uses the earliest exact maximum (row-major windows).
    """
    weights=np.asarray(weights,dtype=float);bins=np.asarray(bins)
    if weights.shape!=(n_ff,) or not np.all(np.isfinite(weights)) or np.any(weights<0):raise ValueError('Invalid weights')
    if bins.shape!=(n_ff,) or bins.dtype.kind not in 'iu' or np.any((bins<0)|(bins>=100)):raise ValueError('Invalid bins')
    if n_cycles<0 or int(n_cycles)!=n_cycles:raise ValueError('Invalid cycle count')
    counts=np.zeros(n_ff,dtype=np.int64);peak=0.;witness=[0,0,0] if n_cycles else None
    previous=-1;active_cycles=0
    for cycle,ids in events:
        ids=np.asarray(ids)
        if not isinstance(cycle,(int,np.integer)) or not previous<cycle<n_cycles:raise ValueError('Invalid event cycle order')
        if ids.ndim!=1 or ids.dtype.kind not in 'iu':raise ValueError('Invalid event indices')
        if validate and (np.any((ids<0)|(ids>=n_ff)) or len(np.unique(ids))!=len(ids)):raise ValueError('Duplicate/out-of-range event')
        previous=cycle
        if not len(ids):continue
        active_cycles+=1;counts[ids]+=1
        sums=np.bincount(bins[ids],weights=weights[ids],minlength=100)
        windows=local_windows(sums.reshape(1,10,10))[0]
        index=int(windows.argmax());value=float(windows.flat[index])
        if value>peak:peak=value;witness=[int(cycle),index//9,index%9]
    return dict(total=float(counts@weights),local_peak=peak,peak_location=witness,
                event_count=int(counts.sum()),active_cycles=active_cycles),counts


def packed_peak_witness(packed,n_ff,weights,bins,chunk_size=1024):
    """Independent dense proof of the earliest peak cycle/window identity."""
    weights=np.asarray(weights);bins=np.asarray(bins);peak=0.;witness=[0,0,0] if len(packed) else None
    for start in range(0,len(packed),chunk_size):
        toggle=np.unpackbits(packed[start:start+chunk_size],axis=1)[:,:n_ff]
        sums=np.zeros((len(toggle),100))
        for b in range(100):
            keep=np.flatnonzero(bins==b)
            if len(keep):sums[:,b]=toggle[:,keep]@weights[keep]
        windows=local_windows(sums.reshape(-1,10,10))
        at=np.unravel_index(windows.argmax(),windows.shape);value=float(windows[at])
        if value>peak:peak=value;witness=[start+int(at[0]),int(at[1]),int(at[2])]
    return witness
