"""Grid-based spatial scan-shift activity proxies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.ndimage import convolve

from pact.scan.model import ScanCell
from pact.test.shift_simulator import ShiftTrace


@dataclass(frozen=True)
class Grid:
    """Fixed placement bounds and an N-by-N grid."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float
    size: int

    def __post_init__(self) -> None:
        if self.size < 1 or self.xmax <= self.xmin or self.ymax <= self.ymin:
            raise ValueError("Grid requires positive dimensions and nonzero bounds")

    def bin_for(self, x: float, y: float) -> tuple[int, int]:
        """Assign a point; inclusive maximum edges belong to the final bin."""
        if not (self.xmin <= x <= self.xmax and self.ymin <= y <= self.ymax):
            raise ValueError("Cell lies outside grid bounds")
        col = min(self.size - 1, int((x - self.xmin) / (self.xmax - self.xmin) * self.size))
        row = min(self.size - 1, int((y - self.ymin) / (self.ymax - self.ymin) * self.size))
        return row, col


def placement_grid(cells: Iterable[ScanCell], size: int) -> Grid:
    """Create stable bounds from cells with a tiny nonzero margin."""
    cells = list(cells)
    if not cells:
        raise ValueError("Cannot grid an empty placement")
    xmin, xmax = min(c.x_um for c in cells), max(c.x_um for c in cells)
    ymin, ymax = min(c.y_um for c in cells), max(c.y_um for c in cells)
    return Grid(xmin - 1e-6, ymin - 1e-6, xmax + 1e-6, ymax + 1e-6, size)


def _gini(values: np.ndarray) -> float:
    ordered = np.sort(values.flatten())
    total = float(ordered.sum())
    if not total:
        return 0.0
    count = len(ordered)
    return float((2 * np.dot(np.arange(1, count + 1), ordered) / (count * total)) - (count + 1) / count)


def spatial_activity(trace: ShiftTrace, cells: Iterable[ScanCell], grid: Grid) -> dict[str, object]:
    """Compute bin toggles and hotspot proxies, never an IR-drop estimate."""
    cells = list(cells)
    names = {c.name for c in cells}
    if len(names) != len(cells):
        raise ValueError("Duplicate cells in placement")
    occupancy = np.zeros((grid.size, grid.size), dtype=int)
    by_name = {}
    for cell in cells:
        location = grid.bin_for(cell.x_um, cell.y_um)
        occupancy[location] += 1
        by_name[cell.name] = location
    per_cycle = np.zeros((len(trace.cycles), grid.size, grid.size), dtype=int)
    for t, cycle in enumerate(trace.cycles):
        if set(cycle.toggles) != names:
            raise ValueError("Shift trace and placement cell sets differ")
        for name, value in cycle.toggles.items():
            per_cycle[(t, *by_name[name])] += value
    flat = per_cycle.flatten().astype(float)
    densities = np.divide(per_cycle, occupancy, out=np.zeros_like(per_cycle, dtype=float), where=occupancy > 0)
    # Radius-one Manhattan kernel on per-bin density, zero outside the die.
    # The 3x3 support makes the proxy local and computationally bounded.
    kernel = np.zeros((1, 3, 3), dtype=float)
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            kernel[0, dr + 1, dc + 1] = 1.0 / (1 + abs(dr) + abs(dc))
    weighted = convolve(densities, kernel, mode="constant", cval=0.0) if len(trace.cycles) else np.zeros((0, grid.size, grid.size))
    return {
        "grid_size": grid.size,
        "peak_bin_toggle": int(flat.max()) if len(flat) else 0,
        "p95_bin_toggle": float(np.percentile(flat, 95)) if len(flat) else 0.0,
        "p99_bin_toggle": float(np.percentile(flat, 99)) if len(flat) else 0.0,
        "max_local_toggle_density": float(densities.max()) if densities.size else 0.0,
        "mean_local_toggle_density": float(densities.mean()) if densities.size else 0.0,
        "spatial_activity_gini": _gini(per_cycle.sum(axis=0)),
        "distance_weighted_hotspot": float(weighted.max()) if weighted.size else 0.0,
        "cumulative_bin_toggles": per_cycle.sum(axis=0).tolist(),
    }
