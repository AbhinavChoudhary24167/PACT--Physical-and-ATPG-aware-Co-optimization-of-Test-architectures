"""Aggregate exact scan-shift cycle traces."""
from __future__ import annotations

from collections import Counter
import numpy as np

from .shift_simulator import ShiftTrace


def activity_metrics(trace: ShiftTrace) -> dict[str, object]:
    """Return total, per-cell, peak, mean, P95, and P99 toggles."""
    totals: Counter[str] = Counter()
    simultaneous = []
    for cycle in trace.cycles:
        totals.update(cycle.toggles)
        simultaneous.append(sum(cycle.toggles.values()))
    values = np.asarray(simultaneous, dtype=float)
    return {
        "total_shift_toggles": int(sum(totals.values())),
        "per_cell_toggles": dict(sorted(totals.items())),
        "peak_simultaneous_toggles": int(max(simultaneous, default=0)),
        "mean_simultaneous_toggles": float(values.mean()) if len(values) else 0.0,
        "p95_simultaneous_toggles": float(np.percentile(values, 95)) if len(values) else 0.0,
        "p99_simultaneous_toggles": float(np.percentile(values, 99)) if len(values) else 0.0,
        "shift_clock_count": len(trace.cycles),
        "between_pattern_state": trace.between_pattern_state,
    }
