import pytest

from pact.physical.phase0b_routed_scan import summarize_routed_scan_edges


def edge(length, *, terminals=2, bterms=0, connected=True):
    return {"routed_nonvia_dbu": length, "dbu_per_um": 1000,
            "iterm_count": terminals, "bterm_count": bterms,
            "connected": connected}


def test_all_exclusive_scan_nets_are_qualified_exact():
    result = summarize_routed_scan_edges([edge(1200), edge(2100)], [1.0, 2.0])
    assert result["classification"] == "QUALIFIED_EXACT_SCAN_ONLY"
    assert result["routed_scan_net_only_length_um"] == pytest.approx(3.3)
    assert result["mixed_functional_scan_edge_count"] == 0


def test_functional_fanout_cannot_be_called_scan_only():
    result = summarize_routed_scan_edges([edge(1200), edge(4200, terminals=3)], [1.0, 2.0])
    assert result["classification"] == "SCAN_ONLY_UNAVAILABLE_MIXED_BUFFERED_OR_DISCONNECTED"
    assert result["routed_scan_net_only_length_um"] is None
    assert result["exact_exclusive_subset_length_um"] == pytest.approx(1.2)
    assert result["mixed_net_full_wirelength_upper_bound_um"] == pytest.approx(4.2)


def test_disconnected_edge_is_not_silently_dropped():
    result = summarize_routed_scan_edges([edge(1200), edge(-1, connected=False)], [1.0, 2.0])
    assert result["disconnected_or_unrouted_edge_count"] == 1
    assert result["routed_scan_net_only_length_um"] is None


def test_unique_transparent_buffer_is_counted_separately_from_disconnection():
    buffered = edge(1500, connected=False)
    buffered.update({"via_transparent_buffer": True, "buffered_full_net_upper_dbu": 3600})
    result = summarize_routed_scan_edges([edge(1200), buffered], [1.0, 2.0])
    assert result["buffered_scan_edge_count"] == 1
    assert result["disconnected_or_unrouted_edge_count"] == 0
    assert result["routed_scan_net_only_length_um"] is None
    assert result["mixed_net_full_wirelength_upper_bound_um"] == pytest.approx(3.6)
