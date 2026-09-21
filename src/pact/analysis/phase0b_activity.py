"""Compact exact serial-shift metrics for many Phase-0B architectures."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from scipy.ndimage import convolve
from scipy.sparse import csr_matrix

from pact.physical.grid_metrics import placement_grid
from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan


def _gini(values: np.ndarray) -> float:
    ordered = np.sort(values.flatten())
    total = float(ordered.sum())
    if total == 0:
        return 0.0
    n = len(ordered)
    return float(2 * np.dot(np.arange(1, n + 1), ordered) / (n * total) - (n + 1) / n)


def _hist_percentile(histogram: np.ndarray, percentile: float) -> float:
    total = int(histogram.sum())
    if total == 0:
        return 0.0
    position = (total - 1) * percentile / 100.0
    lo, hi = int(np.floor(position)), int(np.ceil(position))
    cumulative = histogram.cumsum()
    value_lo = int(np.searchsorted(cumulative, lo + 1))
    value_hi = int(np.searchsorted(cumulative, hi + 1))
    return float(value_lo + (position - lo) * (value_hi - value_lo))


def exact_shift_metrics(architecture: ScanArchitecture,
                        patterns: Sequence[Mapping[str, int]],
                        grid_sizes: tuple[int, ...] = (8, 16, 32)) -> dict[str, object]:
    """Vectorize the same tail-first serial load and carry-loaded state as Phase 0.

    The H8 kernel intentionally matches the saved Phase-0 implementation: a
    3x3 support with weights 1/(1+Manhattan distance), including diagonals.
    This is a shift-activity proxy, never a power or IR-drop estimate.
    """
    validate_scan(architecture)
    if len(architecture.chains) != 1:
        raise ValueError("Phase-0B fast shift metrics currently require one chain")
    order = architecture.chains[0].cells
    n = len(order)
    if any(set(pattern) != set(order) or any(type(bit) is not int or bit not in (0, 1)
                                            for bit in pattern.values()) for pattern in patterns):
        raise ValueError("Every ATPG target must contain one known bit per FF")
    toggle_bits = np.empty((len(patterns) * n, n), dtype=np.uint8)
    state = np.zeros(n, dtype=np.uint8)
    t = 0
    for pattern in patterns:
        target = np.fromiter((pattern[name] for name in order), dtype=np.uint8, count=n)
        for cycle in range(n):
            after = np.empty_like(state)
            after[0] = target[n - 1 - cycle]
            after[1:] = state[:-1]
            toggle_bits[t] = state ^ after
            state = after
            t += 1
        if not np.array_equal(state, target):
            raise AssertionError("Serial load missed the ATPG target")
    simultaneous = toggle_bits.sum(axis=1).astype(float)
    by_name = {cell.name: cell for cell in architecture.cells}
    spatial: dict[str, dict[str, object]] = {}
    if not grid_sizes or any(size not in (8, 16, 32) for size in grid_sizes):
        raise ValueError("grid_sizes must contain supported nonempty grids")
    for size in grid_sizes:
        grid = placement_grid(architecture.cells, size)
        bins = np.array([np.ravel_multi_index(grid.bin_for(by_name[name].x_um, by_name[name].y_um),
                                               (size, size)) for name in order])
        mapping = csr_matrix((np.ones(n, dtype=np.int32), (bins, np.arange(n))),
                             shape=(size * size, n))
        occupancy = np.bincount(bins, minlength=size * size).reshape(size, size)
        kernel = np.zeros((1, 3, 3), dtype=float)
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                kernel[0, dr + 1, dc + 1] = 1.0 / (1 + abs(dr) + abs(dc))
        cumulative = np.zeros((size, size), dtype=np.int64)
        histogram = np.zeros(n + 1, dtype=np.int64)
        peak_bin = 0
        peak_weighted = 0.0
        for start in range(0, t, 4096):
            per_cycle = (mapping @ toggle_bits[start:start + 4096].T).T.reshape(-1, size, size)
            cumulative += per_cycle.sum(axis=0)
            histogram += np.bincount(per_cycle.ravel(), minlength=n + 1)
            peak_bin = max(peak_bin, int(per_cycle.max()))
            densities = np.divide(per_cycle, occupancy, out=np.zeros_like(per_cycle, dtype=float),
                                  where=occupancy > 0)
            peak_weighted = max(peak_weighted, float(convolve(densities, kernel, mode="constant", cval=0.0).max()))
        spatial[str(size)] = {
            "peak_bin_toggle": peak_bin,
            "p95_bin_toggle": _hist_percentile(histogram, 95),
            "p99_bin_toggle": _hist_percentile(histogram, 99),
            "distance_weighted_hotspot": peak_weighted,
            "spatial_activity_gini": _gini(cumulative),
            "cumulative_bin_toggles": cumulative.tolist(),
        }
    return {
        "pattern_count": len(patterns), "shift_clock_count": t,
        "between_pattern_state": "carry_loaded", "initial_state": "zero",
        "total_shift_toggles": int(simultaneous.sum()),
        "peak_simultaneous_toggles": int(simultaneous.max()) if t else 0,
        "p95_simultaneous_toggles": float(np.percentile(simultaneous, 95)) if t else 0.0,
        "p99_simultaneous_toggles": float(np.percentile(simultaneous, 99)) if t else 0.0,
        "spatial_by_grid": spatial,
    }
