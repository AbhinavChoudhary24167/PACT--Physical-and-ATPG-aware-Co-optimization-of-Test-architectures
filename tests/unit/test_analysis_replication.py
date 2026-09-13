from __future__ import annotations

from pact.analysis.aggregate import compare_results


def _row(design: str, name: str, wire: float, hotspot: float) -> dict:
    return {
        "design": design, "method": name, "seed": 11,
        "architecture_sha256": f"{design}-{name}",
        "scan": {"total_hpwl_um": wire},
        "test": {"peak_local_activity": 1, "spatial_by_grid": {"8": {"distance_weighted_hotspot": hotspot}}},
    }


def test_compare_cross_design_replication() -> None:
    records = [
        _row("a", "short", 1, 2), _row("a", "cool", 2, 1),
        _row("b", "short", 1, 1), _row("b", "long", 2, 2),
    ]
    summary = compare_results(records)
    assert summary["proxy_conflict_design_count"] == 1
    assert summary["proxy_conflict_replicated"] is False
    assert summary["design_summaries"]["a"]["observed_wirelength_activity_conflict"] is True
    assert summary["design_summaries"]["b"]["observed_wirelength_activity_conflict"] is False
