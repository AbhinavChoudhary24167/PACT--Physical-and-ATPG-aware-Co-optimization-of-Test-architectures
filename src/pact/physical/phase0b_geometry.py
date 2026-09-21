"""Explicit scan Manhattan distance and edge-length distribution."""
from __future__ import annotations

from pact.scan.model import ScanArchitecture


def scan_edge_distribution(architecture: ScanArchitecture) -> dict[str, object]:
    cells = {cell.name: cell for cell in architecture.cells}
    edges = []
    for chain in architecture.chains:
        for source, dest in zip(chain.cells, chain.cells[1:]):
            a, b = cells[source], cells[dest]
            edges.append(abs(a.x_um - b.x_um) + abs(a.y_um - b.y_um))
    return {"scan_chain_manhattan_um": float(sum(edges)),
            "edge_lengths_um": edges,
            "edge_length_definition": "Manhattan distance between placed scan FF instance origins"}
