from pact.analysis.phase0b_activity import exact_shift_metrics
from pact.physical.grid_metrics import placement_grid, spatial_activity
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.test.activity_metrics import activity_metrics
from pact.test.shift_simulator import simulate_shift


def test_fast_exact_shift_matches_saved_serial_simulator():
    cells = tuple(ScanCell(f"f{i}", float(i), float(i % 2), "CK") for i in range(4))
    arch = ScanArchitecture(cells, (ScanChain("c0", ("f2", "f0", "f3", "f1")),))
    patterns = [{"f0": 1, "f1": 0, "f2": 0, "f3": 1},
                {"f0": 0, "f1": 1, "f2": 1, "f3": 0}]
    slow_trace = simulate_shift(arch, patterns)
    slow_total = activity_metrics(slow_trace)
    fast = exact_shift_metrics(arch, patterns)
    assert fast["total_shift_toggles"] == slow_total["total_shift_toggles"]
    assert fast["peak_simultaneous_toggles"] == slow_total["peak_simultaneous_toggles"]
    assert fast["p95_simultaneous_toggles"] == slow_total["p95_simultaneous_toggles"]
    assert fast["p99_simultaneous_toggles"] == slow_total["p99_simultaneous_toggles"]
    for size in (8, 16, 32):
        slow = spatial_activity(slow_trace, cells, placement_grid(cells, size))
        observed = fast["spatial_by_grid"][str(size)]
        for key in ("peak_bin_toggle", "p95_bin_toggle", "p99_bin_toggle",
                    "distance_weighted_hotspot", "spatial_activity_gini", "cumulative_bin_toggles"):
            assert observed[key] == slow[key]


def test_preselection_H8_only_is_identical_to_full_grid_run():
    cells = tuple(ScanCell(f"f{i}", float(i), 0.0, "CK") for i in range(3))
    arch = ScanArchitecture(cells, (ScanChain("c", ("f0", "f1", "f2")),))
    patterns = [{"f0": 1, "f1": 0, "f2": 1}, {"f0": 0, "f1": 1, "f2": 0}]
    full = exact_shift_metrics(arch, patterns)
    h8_only = exact_shift_metrics(arch, patterns, grid_sizes=(8,))
    assert h8_only["spatial_by_grid"] == {"8": full["spatial_by_grid"]["8"]}
    assert h8_only["total_shift_toggles"] == full["total_shift_toggles"]
