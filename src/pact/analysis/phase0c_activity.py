"""Exact logical shift toggles and labelled fanout-weighted activity proxies."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
import re

import numpy as np
from scipy.ndimage import convolve
from scipy.sparse import csr_matrix

from pact.physical.grid_metrics import placement_grid
from pact.scan.model import ScanArchitecture
from pact.scan.phase0c import parallel_schedule
from pact.scan.validate import validate_scan


def direct_sink_weights(placed_verilog: Path, ff_q_nets: Mapping[str, str]) -> dict[str, int]:
    """Count direct netlist sink terminals; this is not capacitance or power.

    A floor of one represents the scan FF's obligatory observable Q state.
    Output pin names are excluded. Buffering makes this a local fanout proxy,
    rather than total transitive load.
    """
    source = placed_verilog.read_text(encoding="utf-8")
    output_pins = {"Q", "QN", "Z", "ZN", "Y", "CO", "SO"}
    counts: Counter[str] = Counter()
    for instance in re.finditer(r"\b[A-Za-z_][\w$]*\s+[A-Za-z_][\w$]*\s*\((.*?)\)\s*;", source, re.DOTALL):
        for pin, net in re.findall(r"\.([A-Za-z_][\w$]*)\s*\(\s*([^()\s]+)\s*\)", instance.group(1)):
            if pin not in output_pins:
                counts[net] += 1
    return {name: max(1, counts[net]) for name, net in ff_q_nets.items()}


def _kernel() -> np.ndarray:
    kernel = np.zeros((1, 3, 3), dtype=float)
    for row in range(-1, 2):
        for col in range(-1, 2):
            kernel[0, row + 1, col + 1] = 1 / (1 + abs(row) + abs(col))
    return kernel


def parallel_activity_metrics(arch: ScanArchitecture, patterns: Sequence[Mapping[str, int]],
                              weights: Mapping[str, int], grid_sizes: tuple[int, ...] = (8, 16, 32)) -> dict:
    validate_scan(arch)
    names = tuple(sorted(c.name for c in arch.cells))
    if set(weights) != set(names) or any(type(v) is not int or v < 1 for v in weights.values()):
        raise ValueError("Positive integer direct-sink weights required for all FFs")
    if not patterns:
        raise ValueError("No ATPG patterns")
    index = {name: i for i, name in enumerate(names)}
    chain_indices = [np.asarray([index[name] for name in chain.cells], dtype=np.int32) for chain in arch.chains]
    weight_array = np.asarray([weights[name] for name in names], dtype=np.float64)
    coordinates = {c.name: c for c in arch.cells}
    grids = {}
    for size in grid_sizes:
        if size not in (8, 16, 32):
            raise ValueError("Unsupported grid")
        grid = placement_grid(arch.cells, size)
        bins = [np.ravel_multi_index(grid.bin_for(coordinates[name].x_um, coordinates[name].y_um),
                                     (size, size)) for name in names]
        mapping = csr_matrix((np.ones(len(names)), (bins, np.arange(len(names)))),
                             shape=(size * size, len(names)))
        occupancy = np.bincount(bins, minlength=size * size).reshape(size, size)
        grids[size] = (mapping, occupancy)
    state = np.zeros(len(names), dtype=np.uint8)
    all_counts = []
    weighted_counts = []
    cumulative = {size: np.zeros((size, size), dtype=np.float64) for size in grid_sizes}
    peak_h = {size: 0.0 for size in grid_sizes}
    peak_heff = {size: 0.0 for size in grid_sizes}
    peak_bin = {size: 0.0 for size in grid_sizes}
    kernel = _kernel()
    total = 0
    clock_count = 0
    for pattern in patterns:
        schedule = parallel_schedule(arch, pattern)
        batch = np.empty((len(schedule), len(names)), dtype=np.uint8)
        for cycle, inputs in enumerate(schedule):
            after = state.copy()
            for ci, indices in enumerate(chain_indices):
                after[indices[1:]] = state[indices[:-1]]
                after[indices[0]] = inputs[ci]
            batch[cycle] = state ^ after
            state = after
        if any(int(state[index[name]]) != bit for name, bit in pattern.items()):
            raise AssertionError("ATPG target not loaded")
        counts = batch.sum(axis=1).astype(np.float64)
        weighted = batch @ weight_array
        all_counts.extend(counts.tolist())
        weighted_counts.extend(weighted.tolist())
        total += int(counts.sum())
        clock_count += len(schedule)
        for size, (mapping, occupancy) in grids.items():
            bin_counts = (mapping @ batch.T).T.reshape(-1, size, size)
            effective = (mapping @ (batch * weight_array).T).T.reshape(-1, size, size)
            cumulative[size] += bin_counts.sum(axis=0)
            peak_bin[size] = max(peak_bin[size], float(bin_counts.max()))
            density = np.divide(bin_counts, occupancy, out=np.zeros_like(bin_counts), where=occupancy > 0)
            peak_h[size] = max(peak_h[size], float(convolve(density, kernel, mode="constant").max()))
            peak_heff[size] = max(peak_heff[size], float(convolve(effective, kernel, mode="constant").max()))
    return {
        "pattern_count": len(patterns), "parallel_shift_clock_count": clock_count,
        "initial_state": "zero", "between_pattern_state": "carry_loaded_no_capture_model",
        "total_shift_toggles": total,
        "peak_simultaneous_toggles": max(all_counts),
        "p95_simultaneous_toggles": float(np.percentile(all_counts, 95)),
        "p99_simultaneous_toggles": float(np.percentile(all_counts, 99)),
        "weighted_total": float(sum(weighted_counts)),
        "weighted_peak": max(weighted_counts),
        "weight_definition": "max(1, direct sink terminal count on placed Q net); dimensionless proxy",
        "grids": {str(size): {
            "peak_bin_toggle": peak_bin[size],
            "H_density": peak_h[size],
            "H_eff": peak_heff[size],
            "cumulative_bin_toggles": cumulative[size].tolist(),
        } for size in grid_sizes},
    }
