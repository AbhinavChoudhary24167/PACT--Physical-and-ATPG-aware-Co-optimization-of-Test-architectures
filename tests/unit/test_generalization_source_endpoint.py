"""Regression for mapped scan sources driving SO directly from terminal Q."""
import importlib.util
from pathlib import Path
import sys
import pytest

SCRIPTS=Path(__file__).resolve().parents[2]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from pact_generalization_infrastructure import direct_endpoint_scan_order
from pact.scan.identity import supplied_scan_order


def netlist(tmp_path, terminal):
    path=tmp_path/'source.v'
    path.write_text(f'''module sample(input test_si, input test_se, input CK, input D, output test_so);
SDFF_X1 a (.SI(test_si),.SE(test_se),.Q(n),.D(D),.CK(CK));
SDFF_X1 b (.SI(n),.SE(test_se),.Q({terminal}),.D(D),.CK(CK));
endmodule
''')
    return path


def test_direct_output_path_is_complete(tmp_path):
    path=netlist(tmp_path,'test_so')
    with pytest.raises(ValueError,match='Scan-out endpoint'):
        supplied_scan_order(path)
    assert direct_endpoint_scan_order(path)==('a','b')


def test_disconnected_output_still_fails(tmp_path):
    with pytest.raises(ValueError,match='No complete direct'):
        direct_endpoint_scan_order(netlist(tmp_path,'unconnected'))


def test_existing_assign_path_is_unchanged(tmp_path):
    path=netlist(tmp_path,'last')
    path.write_text(path.read_text().replace('endmodule','assign test_so = last;\nendmodule'))
    assert direct_endpoint_scan_order(path)==supplied_scan_order(path)==('a','b')
