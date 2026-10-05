"""VCD-equivalent timestamp collection, complete counts and exact reductions."""
import gzip
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import numpy as np
import pytest

from pact.activity.compact import metrics, read_counts
from pact.physical_effect import stats, weighted, spatial_bin, vcd_transitions


def test_both_backends_reject_switched_net_without_spef_even_with_zero_pin_cap(tmp_path, monkeypatch):
    """Isolate the frozen capacitance gate after independent FF checking."""
    from types import SimpleNamespace
    from pact import physical_effect as oracle
    from pact.activity import compact
    from pact.test import pattern_parser
    root = tmp_path/'activity'
    folder = root/'design'/'role'
    folder.mkdir(parents=True)
    def write(name, value):
        (folder/name).write_text(json.dumps(value))
    write('net_mapping.json',dict(bounds_um=[0,0,1,1],nets=dict(n=dict(
        source='dangling/Z',pin_cap_ff=0,scan_data=True,xy_um=[0,0]))))
    write('workload.json',dict(patterns=[],cycles=1))
    write('cycles.json',[dict(cycle=0,pattern=0,phase='load',shift=0)])
    write('architecture.json',dict(cells=[],chains=[]))
    write('identity.json',dict(records=[]))
    (root/'manifest.json').write_text(json.dumps(dict(rows=[dict(design='design',role='role',
        architecture=dict(path=str(folder/'architecture.json')),inputs=dict(
            identity_map=dict(path=str(folder/'identity.json')),patterns=dict(path='unused')))])))
    # n occurs in NAME_MAP but has no D_NET section, as in the large failure.
    (folder/'extracted.spef').write_text('*C_UNIT 1 FF\n*NAME_MAP\n*1 n\n*2 other\n*D_NET *2 1\n*CAP\n1 *2:1 1\n*END\n')
    (folder/'activity.vcd').write_text('$scope module tb $end\n$var integer 32 ! cycle_id $end\n'
        '$scope module dut $end\n$var wire 1 a n $end\n$upscope $end\n$upscope $end\n'
        '$enddefinitions $end\n#0\nb11111111111111111111111111111111 !\n0a\n#10\nb0 !\n1a\n#20\nb11111111111111111111111111111111 !\n')
    (folder/'activity.counts.gz').write_bytes(gzip.compress(
        b'PACTCN01'+struct.pack('<II',1,1)+struct.pack('<I',1)+b'n'+b'\x01PACTDONE'))
    monkeypatch.setattr(pattern_parser,'parse_fan_pat',lambda _:SimpleNamespace(patterns=[]))
    monkeypatch.setattr(compact,'ff_check',lambda *args:None)
    for backend in (oracle.analyze,compact.analyze):
        with pytest.raises(ValueError,match='Switched net missing SPEF: n'):
            backend(folder)
        assert not (folder/'activity_summary.json').exists()


def test_truncated_or_mismapped_counts_are_never_measurements(tmp_path):
    header = b'PACTCN01'+struct.pack('<II', 1, 2)+struct.pack('<I', 1)+b'a'
    path = tmp_path/'counts.gz'
    path.write_bytes(gzip.compress(header+b'\x01\x02'))
    with pytest.raises(ValueError, match='Incomplete'):
        read_counts(path, ['a'], 2)
    path.write_bytes(gzip.compress(header+b'\x01\x02PACTDONE'))
    counts, info = read_counts(path, ['a'], 2)
    np.testing.assert_array_equal(counts[:, 0], [1, 2])
    assert info['complete']
    with pytest.raises(ValueError, match='mapping'):
        read_counts(path, ['b'], 2)


def test_chunked_metrics_match_full_arithmetic_and_first_maximum():
    rng = np.random.default_rng(11)
    names = [f'n{i}' for i in range(33)]
    mapping = dict(bounds_um=[0, 0, 8, 8], nets={n: dict(scan_data=i%2 == 0, xy_um=[i%8, i//8]) for i, n in enumerate(names)})
    counts = rng.integers(0, 3, (2051, len(names)), dtype=np.uint8)
    counts[1023:1025] = 3  # tied maxima across the chunk boundary
    caps = rng.random(len(names))
    schedule = [dict(phase='load' if i%2 else 'unload') for i in range(len(counts))]
    actual, _, maps = metrics(counts, caps, mapping, names, schedule)
    for scope in ('scan_data','all_data'):
        selected = np.array([mapping['nets'][n]['scan_data'] or scope == 'all_data' for n in names])
        a, c = counts[:, selected], caps[selected]
        assert actual[scope]['transitions'] == stats(a.sum(axis=1))
        for key, value in stats(weighted(a,c)).items():
            np.testing.assert_allclose(actual[scope]['cap_weighted_ff_transitions'][key], value, rtol=1e-10, atol=1e-10)
        for resolution in (4,8):
            bins = np.array([spatial_bin(mapping['nets'][n]['xy_um'],mapping['bounds_um'],resolution) for n in np.asarray(names)[selected]])
            local = np.zeros((len(counts), resolution**2), np.int32)
            localcap = np.zeros_like(local, dtype=float)
            for b in range(resolution**2):
                local[:, b] = a[:, bins == b].sum(axis=1)
                localcap[:, b] = weighted(a[:, bins == b], c[bins == b])
            item = actual[scope]['grids'][str(resolution)]
            assert item['peak_per_cycle'] == stats(local.max(axis=1))
            for key, value in stats(localcap.max(axis=1)).items():
                np.testing.assert_allclose(item['cap_peak_per_cycle'][key], value, rtol=1e-10, atol=1e-10)
            ic, ib = np.unravel_index(local.argmax(),local.shape)
            ec, eb = np.unravel_index(localcap.argmax(),localcap.shape)
            assert (item['max_transition_cycle'],item['max_transition_bin']) == (ic,ib)
            assert (item['max_cap_cycle'],item['max_cap_bin']) == (ec,eb)
            assert maps[f'{scope}_{resolution}']['bins_total'] == local.sum(axis=0).tolist()


@pytest.mark.skipif(not all(shutil.which(t) for t in ('g++','iverilog','vvp')), reason='Icarus/VPI toolchain required')
def test_native_timestamp_alias_and_delta_coalescing_matches_vcd(tmp_path):
    source = Path(__file__).resolve().parents[2]/'src/pact/activity/counts_vpi.cpp'
    subprocess.run(['g++','-O2','-std=c++11','-fPIC','-shared','-I/usr/include/iverilog',str(source),'-o',str(tmp_path/'counts.vpi'),'-lz'], check=True, capture_output=True)
    stimulus = '''`timescale 1ns/1ps
module dut(input a, output alias_a, output y); assign alias_a=a; assign y=~a; endmodule
module tb; reg a=0; integer cycle_id=-1; wire alias_a,y; dut dut(a,alias_a,y);
initial begin
$dumpfile("activity.vcd"); $dumpvars(1,dut); $dumpvars(0,cycle_id);
#5; a=1; cycle_id=0; a=0; a=1;
#2; a=0;
#2; cycle_id=-1; a=1'bx;
#2; a=0;
#2; a=1; cycle_id=1;
#2; a=0;
#2; cycle_id=-1;
#2; $finish; end endmodule
'''
    (tmp_path/'stimulus.v').write_text(stimulus)
    (tmp_path/'counts.cfg').write_text('2\na\nalias_a\ny\n')
    subprocess.run(['iverilog','-g2012','-s','tb','-o',str(tmp_path/'simulation.vvp'),str(tmp_path/'stimulus.v')],check=True,capture_output=True)
    env = dict(os.environ, PACT_ACTIVITY_CONFIG=str(tmp_path/'counts.cfg'),PACT_ACTIVITY_OUTPUT=str(tmp_path/'activity.counts.gz'))
    result = subprocess.run(['vvp','-M',str(tmp_path),'-m','counts',str(tmp_path/'simulation.vvp')],cwd=tmp_path,env=env,capture_output=True,text=True,check=True)
    assert 'PACT_COUNTS_COMPLETE' in result.stdout and 'PACT_COUNTS_ERROR' not in result.stdout
    names = ['a','alias_a','y']
    actual,_ = read_counts(tmp_path/'activity.counts.gz',names,2)
    expected,_ = vcd_transitions(tmp_path/'activity.vcd',names,2)
    np.testing.assert_array_equal(actual,expected)
