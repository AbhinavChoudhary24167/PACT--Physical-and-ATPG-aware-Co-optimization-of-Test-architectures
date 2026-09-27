"""Focused integration invariants; no optimizer mechanics or search campaign."""
from dataclasses import replace
import json
from pathlib import Path
import pytest

from pact.scan.model import ScanCell, ScanChain, ScanArchitecture
from pact.integration.permutation import ScanPermutation, read, write, file_hash
from pact.integration.patterns import serialize, remap_serial, export_workload, fan_workload
from pact.integration.replay import shift, verify
from pact.integration.implementation import emit, port_bindings
from pact.integration.flow import selected_result, frozen_inputs
from pact.integration.faults import parse_fault_report
from pact.integration.verify_artifacts import verify_manifest


def architecture(groups):
    names = sorted(n for g in groups for n in g)
    return ScanArchitecture(tuple(ScanCell(n, float(i), 0., 'clk') for i,n in enumerate(names)),
                            tuple(ScanChain(f'C{i}', tuple(g), f'si{i}', f'so{i}') for i,g in enumerate(groups)))


def reorder(old, groups):
    return replace(old, chains=tuple(replace(c, cells=tuple(g)) for c,g in zip(old.chains, groups)))


def row(state):
    return dict(pattern=1, source_fields=dict(pi1='1', po1='0'), load_state=state,
                response_state={n: 'X' if b == 'X' else str(1-int(b)) for n,b in state.items()})


@pytest.mark.parametrize('groups,newgroups', [
    (['abc'], ['cba']), (['ab','cd'], ['ba','dc']),
    (['ab','cd'], ['ac','bd']), (['abc','de'], ['dba','ce']),
    (['ab','cd','ef'], ['fe','dc','ba']), (['a'], ['a'])])
def test_cycle_load_unload_and_bijection(groups, newgroups):
    old = architecture(groups); new = reorder(old, newgroups)
    perm = ScanPermutation(old,new)
    state = {c.name: '01X'[i%3] for i,c in enumerate(old.cells)}
    source = [row(state)]
    original, remapped = export_workload(perm,source)
    proof, recovered = verify(old,new,original,remapped,source)
    assert proof['status'] == 'PASS' and proof['mismatches'] == 0
    assert proof['FF_states_checked'] == len(state)
    assert recovered[0]['load_state'] == state
    assert recovered[0]['response_state'] == source[0]['response_state']
    assert remap_serial(new,old,remapped['patterns'][0]['load']) == original['patterns'][0]['load']


def test_obvious_orientation_shared_clock_and_direct_so():
    old = architecture(['abc','d'])
    state = dict(a='1',b='0',c='X',d='1')
    assert serialize(old,state) == dict(C0='X01',C1='001')
    loaded, so = shift(old,dict(C0='X01',C1='001'), dict(a='0',b='1',c='1',d='X'))
    assert loaded == state
    assert so == dict(C0='110',C1='X00')  # sample before each common edge
    assert serialize(old,state,response=True) == dict(C0='X01',C1='1XX')


def test_obvious_single_chain_permutation():
    old = architecture(['abc']); new = reorder(old,['bac'])
    assert remap_serial(old,new,dict(C0='001')) == dict(C0='010')
    assert shift(new,dict(C0='010'))[0] == dict(a='1',b='0',c='0')


def test_deterministic_serialization_and_hash(tmp_path):
    old = architecture(['ab','cd']); new = reorder(old,['dc','ab'])
    p = ScanPermutation(old,new)
    p.to_json(tmp_path/'one.json'); p.to_json(tmp_path/'two.json')
    assert (tmp_path/'one.json').read_bytes() == (tmp_path/'two.json').read_bytes()
    assert len(p.payload()['old_to_new']) == len(p.payload()['new_to_old']) == 4
    ScanPermutation.verify_json(tmp_path/'one.json',old,new)
    value = read(tmp_path/'one.json'); value['old_to_new'][0]['ff'] = 'invented'
    write(tmp_path/'one.json',value)
    with pytest.raises(ValueError,match='hash/provenance'):
        ScanPermutation.verify_json(tmp_path/'one.json',old,new)


@pytest.mark.parametrize('groups', [['aa','cd'],['ab','c'],['ab','cx'],['','abcd']])
def test_duplicate_missing_invented_empty_rejected(groups):
    old = architecture(['ab','cd'])
    with pytest.raises(ValueError):
        ScanPermutation(old,reorder(old,groups))


@pytest.mark.parametrize('change', ['port','capacity','coordinates','duplicate_chain','missing_port','duplicate_inventory'])
def test_malformed_topology(change):
    old = architecture(['ab','cd'])
    if change == 'port': new = replace(old,chains=(replace(old.chains[0],scan_in='other'),old.chains[1]))
    if change == 'capacity': new = reorder(old,['a','bcd'])
    if change == 'coordinates': new = replace(old,cells=(replace(old.cells[0],x_um=999),)+old.cells[1:])
    if change == 'duplicate_chain': new = replace(old,chains=(old.chains[0],replace(old.chains[1],chain_id='C0')))
    if change == 'missing_port': new = replace(old,chains=(replace(old.chains[0],scan_out=None),old.chains[1]))
    if change == 'duplicate_inventory': new = replace(old,cells=old.cells+(old.cells[0],))
    with pytest.raises(ValueError): ScanPermutation(old,new)


@pytest.mark.parametrize('stage', ['load','unload'])
def test_independent_replay_detects_corruption(stage):
    old = architecture(['ab','cd']); new = reorder(old,['dc','ab'])
    source = [row(dict(a='1',b='0',c='1',d='0'))]
    a,b = export_workload(ScanPermutation(old,new),source)
    stream = b['patterns'][0][stage]['C0']
    b['patterns'][0][stage]['C0'] = str(1-int(stream[0]))+stream[1:]
    proof,_ = verify(old,new,a,b,source)
    assert proof['status'] == 'FAIL' and proof[stage+'_replay'] == 'FAIL'


def test_partial_and_invalid_symbols_rejected():
    a = architecture(['ab'])
    for state in (dict(a='0'),dict(a='0',b='-')):
        with pytest.raises(ValueError): serialize(a,state)
    for vectors in (dict(C0='0'),dict(C0='0Z'),dict(other='01')):
        with pytest.raises(ValueError): remap_serial(a,a,vectors)


def test_fan_x_and_unsupported_timing(tmp_path):
    a = architecture(['ab'])
    identity = [dict(logical_ff=n,physical_instance=n,atpg_signal=n,clock_domain='clk') for n in 'ab']
    p = tmp_path/'test.pat'
    p.write_text('pi |\na b |\npo\nBASIC_SCAN\n_num_of_pattern_1\n_pattern_1 1 | | 0X | | X | | X1\n')
    _, rows = fan_workload(p,identity,a)
    assert rows[0]['load_state'] == dict(a='0',b='X')
    assert rows[0]['response_state'] == dict(a='X',b='1')
    with pytest.raises(ValueError,match='Ambiguous'):
        fan_workload(p,[identity[0],identity[0]],a)
    p.write_text(p.read_text().replace('1 | |','1 | 1 |'))
    with pytest.raises(ValueError,match='unsupported sequential'):
        fan_workload(p,identity,a)


def test_patch_and_qualified_endpoint_binding(tmp_path):
    old = architecture(['ab','cd']); new = reorder(old,['dc','ab'])
    root = Path(__file__).resolve().parents[2]
    patch = emit(tmp_path,ScanPermutation(old,new),root,'direct')
    assert patch['chains'][0]['links'][0]['destination'] == dict(instance='d',pin='SI')
    assert patch['chains'][0]['links'][-1]['source'] == dict(instance='c',pin='Q')
    q = replace(old,chains=tuple(replace(c,scan_in=f'test_si_{i}',scan_out=f'test_so_{i}') for i,c in enumerate(old.chains)))
    assert port_bindings(q,'qualified') == dict(test_si_0='test_si',test_so_0='test_so',test_si_1='test_si_1',test_so_1='test_so_1')
    with pytest.raises(ValueError): port_bindings(old,'qualified')


def test_selected_hash_and_input_provenance(tmp_path):
    old = architecture(['ab']); new = reorder(old,['ba'])
    old.to_json(tmp_path/'supplied.architecture.json'); new.to_json(tmp_path/'optimized.architecture.json')
    result = dict(design='tiny',pattern_count=1,FF_count=2,K=1,
                  selected=dict(architecture_sha256=new.sha256(),metrics=dict(scan_hpwl_um=1,M3_load_local=1,M5_hpwl_local=1)),
                  recommendation_constraints=dict(wire_cap_um=1.1,M3_load_local_max=1,M5_hpwl_local_max=1),
                  physical_reference_um=1,config=dict(wire_allowance=.1))
    write(tmp_path/'result.json',result)
    assert selected_result(tmp_path,old,'tiny',1)[0] == new
    result['selected']['architecture_sha256'] = 'bad'; write(tmp_path/'result.json',result)
    with pytest.raises(ValueError,match='hash'): selected_result(tmp_path,old,'tiny',1)
    path = tmp_path/'input.txt'; path.write_text('original')
    write(tmp_path/'results/phase2c_repair/freeze.json',dict(inputs={'/historical/input.txt':file_hash(path)}))
    frozen_inputs(tmp_path,[path]); path.write_text('changed')
    with pytest.raises(ValueError,match='hash'): frozen_inputs(tmp_path,[path])


def test_fault_report_requires_evidence():
    text = '# number of faults: 5\n# SA0 DT a/Q (ff)\n# fault coverage 20.00%\n'
    faults,total,coverage = parse_fault_report(text)
    assert faults == {('SA0','a/Q (ff)')} and total == 5 and coverage == 20
    with pytest.raises(ValueError): parse_fault_report('exit 0')


def test_delivered_manifest_detects_artifact_corruption(tmp_path):
    a = architecture(['ab']); b = reorder(a,['ba'])
    a.to_json(tmp_path/'scan_topology_before.json'); b.to_json(tmp_path/'scan_topology_after.json')
    ScanPermutation(a,b).to_json(tmp_path/'scan_permutation.json')
    (tmp_path/'patterns_remapped.json').write_text('{}')
    manifest = dict(input_topology_sha256=a.sha256(),selected_architecture_sha256=b.sha256(),
                    artifacts={p.name:file_hash(p) for p in tmp_path.iterdir()})
    write(tmp_path/'manifest.json',manifest)
    assert verify_manifest(tmp_path)['status'] == 'PASS'
    (tmp_path/'patterns_remapped.json').write_text('{"tampered":true}')
    with pytest.raises(ValueError,match='Artifact hash'):
        verify_manifest(tmp_path)


def test_unload_masks_are_not_silent_fill():
    a = architecture(['ab','c']); source = [row(dict(a='0',b='X',c='1'))]
    original,remapped = export_workload(ScanPermutation(a,a),source)
    remapped['patterns'][0]['unload']['C1'] = '00'
    with pytest.raises(ValueError,match='padding'):
        verify(a,a,original,remapped,source)
