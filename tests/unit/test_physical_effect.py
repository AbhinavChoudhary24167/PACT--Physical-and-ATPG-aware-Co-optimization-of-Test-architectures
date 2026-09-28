import importlib.util
from pathlib import Path
import numpy as np
import pytest
from pact.physical_effect import spatial_bin, vcd_transitions, weighted

def waveform(tmp_path, tail=None):
    p=tmp_path/'test.vcd'
    p.write_text('''$timescale 1ps $end
$scope module tb $end
$var integer 32 ! cycle_id $end
$scope module dut $end
$var wire 1 a n1 $end
$var wire 1 b n2 $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
b11111111111111111111111111111111 !
0a
0b
#10
1a
b0 !
#15
1b
#20
b1 !
0a
#25
0b
#30
b11111111111111111111111111111111 !
1a
''' + (tail or ''))
    return p

def test_timestamp_cycle_mapping_and_known_energy(tmp_path):
    a,meta=vcd_transitions(waveform(tmp_path),['n1','n2'],2)
    assert a.tolist()==[[1,1],[1,1]]
    assert weighted(a,[2,3]).tolist()==[5,5]
    # At 1 V, 0.5*C*N gives 5 fJ for the known two-net example.
    assert weighted(a,[2,3]).sum()*.5==5
    assert meta['mapped_nets']==2
    b,_=vcd_transitions(waveform(tmp_path),['n1','n2'],2)
    np.testing.assert_array_equal(a,b)

def test_bin_boundaries():
    assert spatial_bin([0,0],[0,0,10,10],2)==0
    assert spatial_bin([5,5],[0,0,10,10],2)==3
    assert spatial_bin([10,10],[0,0,10,10],2)==3
    with pytest.raises(ValueError): spatial_bin([-1,5],[0,0,10,10],2)

@pytest.mark.parametrize('caps',[[None,1],[-1,2],[float('nan'),1]])
def test_missing_capacitance_rejected(caps):
    with pytest.raises(ValueError): weighted(np.ones((1,2)),caps)

def test_bad_waveform_rejected(tmp_path):
    p=waveform(tmp_path)
    with pytest.raises(ValueError,match='missing'): vcd_transitions(p,['missing'],2)
    p.write_text(p.read_text().replace('1b','xb'))
    with pytest.raises(ValueError,match='Unknown active'): vcd_transitions(p,['n1','n2'],2)
    p.write_text('$scope module tb $end\n')
    with pytest.raises(ValueError,match='Incomplete'): vcd_transitions(p,['n1'],2)

def test_hash_mismatch_rejected(tmp_path):
    path=Path(__file__).resolve().parents[2]/'scripts/physical_effect.py'
    spec=importlib.util.spec_from_file_location('physical_effect_cli',path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    f=tmp_path/'artifact'; f.write_text('original'); binding=m.bind(f)
    m.check_binding(binding)
    f.write_text('changed')
    with pytest.raises(ValueError,match='hash mismatch'): m.check_binding(binding)

def test_exact_input_alias_export(tmp_path):
    path=Path(__file__).resolve().parents[2]/'scripts/physical_effect.py'
    spec=importlib.util.spec_from_file_location('physical_effect_cli',path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    (tmp_path/'routed_raw.v').write_text('module d(input si); wire scan_net; endmodule\n')
    m.repair_input_aliases(tmp_path,{'ports':[{'direction':'INPUT','name':'si','net':'scan_net'}]})
    assert 'assign \\scan_net = \\si ;' in (tmp_path/'routed.v').read_text()
