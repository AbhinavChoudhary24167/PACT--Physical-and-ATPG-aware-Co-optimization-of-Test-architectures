"""Chunked stable-state scoring independent of predictor construction."""
import numpy as np
from pact.analysis.phase2a_shift import fixed_bins, local_windows


def score_packed(packed, n_ff, weights, bins, chunk_size=1024):
    weights = np.asarray(weights, dtype=float)
    if weights.shape != (n_ff,) or not np.all(np.isfinite(weights)) or np.any(weights < 0):
        raise ValueError('Invalid weights')
    counts = np.zeros(n_ff, dtype=np.int64)
    peak = 0.
    for start in range(0, len(packed), chunk_size):
        toggle = np.unpackbits(packed[start:start+chunk_size], axis=1)[:,:n_ff]
        counts += toggle.sum(axis=0, dtype=np.int64)
        # No N_ff squared matrix; one sparse bin membership per FF.
        sums = np.zeros((len(toggle),100))
        for b in range(100):
            keep = np.flatnonzero(bins == b)
            if len(keep): sums[:,b] = toggle[:,keep] @ weights[keep]
        peak = max(peak, float(local_windows(sums.reshape(-1,10,10)).max()))
    return dict(total=float(counts @ weights), local_peak=peak), counts
