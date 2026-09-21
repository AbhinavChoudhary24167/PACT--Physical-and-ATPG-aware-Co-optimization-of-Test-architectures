from pact.physical.phase0b_geometry import scan_edge_distribution
from pact.physical.scan_wirelength import scan_wirelength
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def test_edge_distribution_reconstructs_existing_scan_hpwl():
    cells = (ScanCell("a", 0, 0, "CK"), ScanCell("b", 3, 4, "CK"),
             ScanCell("c", 5, 9, "CK"))
    arch = ScanArchitecture(cells, (ScanChain("c0", ("a", "b", "c")),))
    dist = scan_edge_distribution(arch)
    assert dist["edge_lengths_um"] == [7, 7]
    assert dist["scan_chain_manhattan_um"] == scan_wirelength(arch)["total_scan_hpwl_um"] == 14
