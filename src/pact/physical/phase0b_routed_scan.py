"""Interpret routed scan-edge objects without conflating functional branches."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def summarize_routed_scan_edges(edges: Sequence[dict[str, Any]],
                                geometric_edges_um: Sequence[float]) -> dict[str, object]:
    if len(edges) != len(geometric_edges_um) or not edges:
        raise ValueError("Exact matching routed and geometric scan edges required")
    exact = []
    mixed = []
    buffered = []
    disconnected = []
    for edge, hpwl in zip(edges, geometric_edges_um):
        if hpwl < 0:
            raise ValueError("Negative geometric edge")
        length = edge["routed_nonvia_dbu"]
        dbu = edge["dbu_per_um"]
        if dbu <= 0 or length < 0:
            disconnected.append(edge)
            continue
        if not edge["connected"]:
            if edge.get("via_transparent_buffer") and edge.get("buffered_full_net_upper_dbu", -1) >= 0:
                buffered.append(edge["buffered_full_net_upper_dbu"] / dbu)
                continue
            disconnected.append(edge)
            continue
        route_um = length / dbu
        if edge["iterm_count"] == 2 and edge["bterm_count"] == 0:
            exact.append((route_um, hpwl))
        else:
            mixed.append((route_um, hpwl))
    all_exact = len(exact) == len(edges)
    exact_sum = sum(item[0] for item in exact)
    mixed_full_sum = sum(item[0] for item in mixed) + sum(buffered)
    exact_hpwl = sum(item[1] for item in exact)
    route_factor = exact_sum / exact_hpwl if len(exact) >= 10 and exact_hpwl > 0 else None
    modelled = (exact_sum + sum(min(upper, proxy * route_factor) for upper, proxy in mixed)
                if route_factor is not None and not disconnected and not buffered else None)
    return {
        "classification": "QUALIFIED_EXACT_SCAN_ONLY" if all_exact else "SCAN_ONLY_UNAVAILABLE_MIXED_BUFFERED_OR_DISCONNECTED",
        "routed_scan_net_only_length_um": exact_sum if all_exact else None,
        "exclusive_scan_edge_count": len(exact),
        "mixed_functional_scan_edge_count": len(mixed),
        "buffered_scan_edge_count": len(buffered),
        "disconnected_or_unrouted_edge_count": len(disconnected),
        "total_scan_edge_count": len(edges),
        "exact_exclusive_subset_length_um": exact_sum,
        "mixed_net_full_wirelength_upper_bound_um": mixed_full_sum if not disconnected else None,
        "modelled_scan_route_length_um": modelled,
        "modelled_route_factor_from_exclusive_edges": route_factor,
        "model_note": "Sensitivity estimate only: multiply mixed-edge cell-origin Manhattan length by the exclusive-net route factor and cap at the full routed mixed-net length. Never used as the primary physical objective.",
    }
