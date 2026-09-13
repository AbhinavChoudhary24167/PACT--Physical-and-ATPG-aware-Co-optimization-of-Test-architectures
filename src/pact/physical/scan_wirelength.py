"""Geometric estimated scan-edge lengths, separate from routed lengths."""
from __future__ import annotations

import numpy as np

from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan


def scan_wirelength(architecture: ScanArchitecture) -> dict[str, float]:
    """Compute Manhattan lengths of cell-to-cell scan connections in microns."""
    validate_scan(architecture)
    cells = {cell.name: cell for cell in architecture.cells}
    edges: list[float] = []
    for chain in architecture.chains:
        for a, b in zip(chain.cells, chain.cells[1:]):
            first, second = cells[a], cells[b]
            edges.append(abs(first.x_um - second.x_um) + abs(first.y_um - second.y_um))
    lengths = np.asarray([len(chain.cells) for chain in architecture.chains], dtype=float)
    return {
        "total_scan_hpwl_um": float(sum(edges)),
        "mean_scan_edge_um": float(np.mean(edges)) if edges else 0.0,
        "max_scan_edge_um": float(max(edges, default=0.0)),
        "p95_scan_edge_um": float(np.percentile(edges, 95)) if edges else 0.0,
        "p99_scan_edge_um": float(np.percentile(edges, 99)) if edges else 0.0,
        "chain_length_balance": float(max(lengths) / min(lengths)),
        "num_edges": len(edges),
    }
