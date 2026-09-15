from pathlib import Path

from pact.physical.phase0c_port_policy import port_centers
from pact.physical.phase0c_scan_geometry import phase0c_scan_geometry
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def test_added_ports_avoid_existing_functional_edge_pins():
    existing = [("test_si", 171830, 51660), ("test_so", 140, 114380),
                ("functional_right", 171830, 103180),
                ("functional_left", 140, 137900)]
    ports = port_centers((0, 0, 171970, 171970), existing, 4)
    assert ports["test_so"][1] == 85820
    assert abs(ports["test_si_2"][1] - 103180) >= 1120
    assert abs(ports["test_so_3"][1] - 137900) >= 1120
    assert all((y - 140) % 560 == 0 for name, (_, y) in ports.items()
               if name != "test_si")


def test_scan_hpwl_includes_fixed_port_to_ff_edges(tmp_path: Path):
    placed = tmp_path / "placed.def"
    placed.write_text("""UNITS DISTANCE MICRONS 2000 ;
DIEAREA ( 0 0 ) ( 20000 20000 ) ;
PINS 2 ;
    - test_si + NET test_si + DIRECTION INPUT + USE SIGNAL
      + PORT + LAYER metal5 ( -140 -140 ) ( 140 140 )
        + PLACED ( 19860 5180 ) N ;
    - test_so + NET test_so + DIRECTION OUTPUT + USE SIGNAL
      + PORT + LAYER metal5 ( -140 -140 ) ( 140 140 )
        + PLACED ( 140 15180 ) N ;
END PINS
""")
    cells = (ScanCell("a", 2.0, 2.0, "CK"), ScanCell("b", 4.0, 2.0, "CK"))
    arch = ScanArchitecture(cells, (ScanChain("C00", ("a", "b")),))
    result = phase0c_scan_geometry(arch, placed)
    assert result["internal_ff_hpwl_um"] == 2.0
    assert result["num_ff_edges"] == 1
    assert result["num_port_edges"] == 2
    assert result["total_scan_hpwl_um"] > result["internal_ff_hpwl_um"]
