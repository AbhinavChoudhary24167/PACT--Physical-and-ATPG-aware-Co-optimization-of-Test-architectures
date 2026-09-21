from pathlib import Path

import pytest

from pact.scan.identity import scan_ff_instances
from pact.scan.phase0b_identity import transparent_q_buffer_aliases, verify_order_with_transparent_buffers


def test_unique_output_buffer_preserves_logical_ff_identity(tmp_path: Path):
    source = tmp_path / "source.v"
    placed = tmp_path / "placed.v"
    source.write_text("SDFF_X1 f0 (.D(d0), .SI(si), .CK(clk), .Q(q0));\n"
                      "SDFF_X1 f1 (.D(d1), .SI(q0), .CK(clk), .Q(q1));\n")
    placed.write_text("SDFF_X1 f0 (.D(d0), .SI(si), .CK(clk), .Q(net0));\n"
                      "SDFF_X1 f1 (.D(d1), .SI(q0), .CK(clk), .Q(q1));\n"
                      "BUF_X1 output0 (.A(net0), .Z(q0));\n")
    aliases = transparent_q_buffer_aliases(source, placed)
    assert aliases == {"f0": {"placed_q_net": "net0", "source_q_net": "q0",
                             "buffer_instance": "output0"}}


def test_unexplained_q_change_is_rejected(tmp_path: Path):
    source = tmp_path / "source.v"
    placed = tmp_path / "placed.v"
    source.write_text("SDFF_X1 f0 (.D(d0), .SI(si), .CK(clk), .Q(q0));\n")
    placed.write_text("SDFF_X1 f0 (.D(d0), .SI(si), .CK(clk), .Q(net0));\n")
    with pytest.raises(ValueError, match="transparent"):
        transparent_q_buffer_aliases(source, placed)


def test_buffered_scan_edge_retains_exact_order(tmp_path: Path):
    placed = tmp_path / "placed.v"
    verilog = ("SDFF_X1 f0 (.D(d0), .SI(test_si), .CK(clk), .Q(q0));\n"
               "SDFF_X1 f1 (.D(d1), .SI(net90), .CK(clk), .Q(q1));\n"
               "BUF_X1 place91 (.A(q0), .Z(net90));\n"
               "BUF_X1 scanout (.A(q1), .Z(test_so));\n")
    placed.write_text(verilog)
    ff = {record.name: record for record in scan_ff_instances(placed)}
    result = verify_order_with_transparent_buffers(("f0", "f1"), ff, verilog)
    assert result["inter_ff_buffer_edges"] == [{"edge_index": 0, "from_ff": "f0",
                                                 "to_ff": "f1", "buffer_instance": "place91"}]
    assert result["scan_output_buffer"] == "scanout"
    with pytest.raises(ValueError, match="scan edge 0"):
        verify_order_with_transparent_buffers(("f0", "f1"), ff,
                                               verilog.replace(".A(q0)", ".A(other)"))
