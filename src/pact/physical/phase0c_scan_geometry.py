"""Port-aware Phase-0C FF-origin scan HPWL proxy."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pact.physical.phase0c_port_policy import frozen_def_ports
from pact.physical.scan_wirelength import scan_wirelength
from pact.scan.model import ScanArchitecture


def phase0c_scan_geometry(architecture: ScanArchitecture, frozen_def: Path) -> dict:
    internal = scan_wirelength(architecture)
    ports, dbu_per_um = frozen_def_ports(frozen_def, len(architecture.chains))
    cells = {cell.name: cell for cell in architecture.cells}
    port_edges = []
    for ci, chain in enumerate(architecture.chains):
        input_name = "test_si" if ci == 0 else f"test_si_{ci}"
        output_name = "test_so" if ci == 0 else f"test_so_{ci}"
        for name, ff_name in ((input_name, chain.cells[0]), (output_name, chain.cells[-1])):
            px, py = ports[name]
            ff = cells[ff_name]
            port_edges.append(abs(px / dbu_per_um - ff.x_um)
                              + abs(py / dbu_per_um - ff.y_um))
    ff_edges = []
    for chain in architecture.chains:
        for left, right in zip(chain.cells, chain.cells[1:]):
            a, b = cells[left], cells[right]
            ff_edges.append(abs(a.x_um - b.x_um) + abs(a.y_um - b.y_um))
    edges = ff_edges + port_edges
    if abs(sum(ff_edges) - internal["total_scan_hpwl_um"]) > 1e-6:
        raise AssertionError("FF-only HPWL does not match frozen geometry implementation")
    return {
        "total_scan_hpwl_um": float(sum(edges)),
        "internal_ff_hpwl_um": float(sum(ff_edges)),
        "port_edge_hpwl_um": float(sum(port_edges)),
        "mean_scan_edge_um": float(np.mean(edges)),
        "max_scan_edge_um": float(max(edges)),
        "p95_scan_edge_um": float(np.percentile(edges, 95)),
        "p99_scan_edge_um": float(np.percentile(edges, 99)),
        "chain_length_balance": internal["chain_length_balance"],
        "num_edges": len(edges),
        "num_ff_edges": len(ff_edges),
        "num_port_edges": len(port_edges),
        "port_centers_dbu": ports,
        "quantity_type": "port-aware FF-origin scan HPWL proxy, not routed scan length",
    }
