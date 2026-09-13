from __future__ import annotations

from pact.physical.grid_metrics import Grid, spatial_activity
from pact.physical.scan_wirelength import scan_wirelength
from pact.physical.extract_placement import extract_def_scan_cells
from pact.scan.model import ScanArchitecture
from pact.test.shift_simulator import simulate_shift


def test_grid_bin_assignment() -> None:
    grid = Grid(0, 0, 10, 10, 2)
    assert grid.bin_for(0, 0) == (0, 0)
    assert grid.bin_for(5, 5) == (1, 1)
    assert grid.bin_for(10, 10) == (1, 1)


def test_scan_wirelength_manual(tiny_arch: ScanArchitecture) -> None:
    result = scan_wirelength(tiny_arch)
    assert result["total_scan_hpwl_um"] == 6
    assert result["mean_scan_edge_um"] == 2
    assert result["max_scan_edge_um"] == 3


def test_spatial_activity_counts(tiny_arch: ScanArchitecture) -> None:
    trace = simulate_shift(tiny_arch, [{"a": 1, "b": 0, "c": 0, "d": 0}])
    result = spatial_activity(trace, tiny_arch.cells, Grid(0, 0, 4, 2, 2))
    assert result["peak_bin_toggle"] == 1
    assert sum(sum(row) for row in result["cumulative_bin_toggles"]) == 1


def test_extract_def_placement(tmp_path) -> None:
    path = tmp_path / "placed.def"
    path.write_text("UNITS DISTANCE MICRONS 1000 ;\nCOMPONENTS 2 ;\n- a DFF + PLACED ( 1000 2000 ) N ;\n- b DFF + FIXED ( 3000 4000 ) FS ;\nEND COMPONENTS\n", encoding="utf-8")
    cells = extract_def_scan_cells(path, {"a", "b"}, "clk")
    assert [(c.name, c.x_um, c.y_um) for c in cells] == [("a", 1, 2), ("b", 3, 4)]
