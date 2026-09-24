"""Independent shift measurements. No objective, fanout weight or kernel imports."""
from __future__ import annotations
import hashlib
import numpy as np
from scipy.sparse import csr_matrix
from pact.scan.phase0c import parallel_schedule, verify_parallel_schedule


def fixed_bins(coordinates, bounds, size=10):
    xy = np.asarray(coordinates, dtype=float)
    x0, y0, x1, y1 = bounds
    assert x1 > x0 and y1 > y0
    assert np.all(xy >= [x0,y0]) and np.all(xy <= [x1,y1])
    ij = np.minimum(size-1, np.floor((xy-[x0,y0])/[x1-x0,y1-y0]*size).astype(int))
    return ij[:,1]*size+ij[:,0]


def local_windows(bins):
    """Each wholly contained 2x2 window; no smoothing or kernel weights."""
    return bins[:,:-1,:-1]+bins[:,1:,:-1]+bins[:,:-1,1:]+bins[:,1:,1:]


def replay(arch, patterns, weights, coordinates, bounds, trace_path=None):
    names = sorted(c.name for c in arch.cells)
    assert set(names) == set(weights) == set(coordinates)
    index = {n:i for i,n in enumerate(names)}
    indices = [np.array([index[n] for n in chain.cells]) for chain in arch.chains]
    lengths = [len(i) for i in indices]
    n, longest = len(names), max(lengths)
    weight = np.array([weights[n] for n in names], dtype=float)
    assert np.all(np.isfinite(weight)) and np.all(weight >= 0)
    bins = fixed_bins([coordinates[n] for n in names],bounds)
    mapping = csr_matrix((np.ones(n),(bins,np.arange(n))),shape=(100,n))
    state = np.zeros(n,dtype=np.uint8)
    raw_cycles, weighted_cycles, packed_states, packed_toggles, input_bits = [],[],[],[],[]
    per_pattern = []
    ff_totals = np.zeros(n,dtype=np.int64)
    bin_total = np.zeros((10,10)); weighted_bin_total = bin_total.copy()
    peaks = {k:dict(value=-1,cycle=None,bin_yx=None) for k in
             ('raw_bin_peak','weighted_bin_peak','raw_local_peak','weighted_local_peak')}
    digest = hashlib.sha256()
    offset = 0
    for pi, target in enumerate(patterns):
        initial = {name:int(state[i]) for i,name in enumerate(names)}
        verified = verify_parallel_schedule(arch,target,initial)
        schedule = parallel_schedule(arch,target)
        batch = np.empty((longest,n),dtype=np.uint8)
        states = np.empty_like(batch)
        out = [[] for _ in indices]
        for t, inputs in enumerate(schedule):
            before = state.copy()
            for j,chain in enumerate(indices):
                out[j].append(int(before[chain[-1]]))
                state[chain[0]] = inputs[j]
                state[chain[1:]] = before[chain[:-1]]
            batch[t] = before ^ state
            states[t] = state
        assert out == verified['scan_out']
        assert {name:int(state[i]) for i,name in enumerate(names)} == dict(target)
        digest.update(states.tobytes())
        counts = batch.sum(axis=1,dtype=np.int64)
        weighted = batch @ weight
        raw_cycles.extend(counts.tolist()); weighted_cycles.extend(weighted.tolist())
        packed_states.append(np.packbits(states,axis=1)); packed_toggles.append(np.packbits(batch,axis=1))
        input_bits.extend(schedule)
        ff_totals += batch.sum(axis=0,dtype=np.int64)
        raw_bins = (mapping @ batch.T).T.reshape(-1,10,10)
        weighted_bins = (mapping @ (batch*weight).T).T.reshape(-1,10,10)
        bin_total += raw_bins.sum(axis=0); weighted_bin_total += weighted_bins.sum(axis=0)
        fields = dict(raw_bin_peak=raw_bins, weighted_bin_peak=weighted_bins,
                      raw_local_peak=local_windows(raw_bins),weighted_local_peak=local_windows(weighted_bins))
        for key, field in fields.items():
            loc = np.unravel_index(field.argmax(),field.shape)
            value = float(field[loc])
            if value > peaks[key]['value']:
                peaks[key] = dict(value=value,cycle=offset+int(loc[0]),bin_yx=[int(loc[1]),int(loc[2])])
        per_pattern.append(dict(pattern_index=pi,first_cycle=offset,last_cycle=offset+longest-1,
            transitions=int(counts.sum()),weighted_switching=float(weighted.sum()),
            padding_cycles_per_chain=[longest-l for l in lengths],
            scan_out_first_L_matches_initial=True,padding_tail_matches_verifier=True))
        offset += longest
    raw, weighted = np.asarray(raw_cycles), np.asarray(weighted_cycles)
    if trace_path is not None:
        np.savez_compressed(trace_path,names=np.asarray(names),states_packed=np.concatenate(packed_states),
            toggles_packed=np.concatenate(packed_toggles),SI=np.asarray(input_bits,dtype=np.uint8),
            raw_per_cycle=raw,weighted_per_cycle=weighted,pattern_start=np.arange(len(patterns))*longest,
            FF_bins=bins, FF_wire_weights_um=weight)
    internal = [index[n] for chain in arch.chains for n in chain.cells[:-1]]
    metrics = dict(raw_total=int(raw.sum()),raw_mean=float(raw.mean()),raw_peak=int(raw.max()),
        raw_p95=float(np.percentile(raw,95)),weighted_total=float(weighted.sum()),
        weighted_mean=float(weighted.mean()),weighted_peak=float(weighted.max()),
        weighted_p95=float(np.percentile(weighted,95)),**{k:v['value'] for k,v in peaks.items()},
        peak_locations=peaks,raw_cumulative_bins=bin_total.tolist(),weighted_cumulative_bins=weighted_bin_total.tolist())
    proof = dict(status='PASS',patterns_replayed=len(patterns),cycles_replayed=len(raw),FF_count=n,
        chain_lengths=lengths,initial_state='zero',between_patterns='carry_loaded_no_capture_model',
        all_pattern_loads_and_scan_out_match_existing_verifier=True,
        total_FF_transitions=int(raw.sum()),transitions_per_pattern=per_pattern,
        mean_transitions_per_shift_cycle=float(raw.mean()),state_trace_sha256=digest.hexdigest(),
        FF_transition_totals=dict(zip(names,map(int,ff_totals))),
        internal_scan_link_source_transitions=int(ff_totals[internal].sum()),
        scan_link_semantics='Post-clock stable Q transition on each internal link, transparent paths; no glitch/timing inference.',
        trace_encoding='Sorted FF names; numpy.packbits big-endian, ignore final byte padding; states AFTER each shift edge, initial all-zero; cycles zero-based.')
    return metrics, proof
