"""Focused topology and numerical regressions for the versioned repair."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.analysis.phase2b_loads import construct_weights as legacy, hpwl, pin_loads
from pact.analysis.phase2cr_loads import construct_weights, construct_with_audit, selected_graph, CAP_PER_UM
from pact.environment import dependency_path, relocate
from pact.experiment_storage import experiment_root


@pytest.fixture
def case():
    cells = tuple(ScanCell(n,x,y,'clk') for n,x,y in [('a',0,0),('b',10,10),('c',20,20),('d',30,30)])
    a = ScanArchitecture(cells,(ScanChain('0',('a','b')),ScanChain('1',('c','d'))))
    def sink(xy,master='LOGIC',pin='A'):
        return dict(xy=xy,master=master,pin=pin)
    g = dict(stage='POST-PLACEMENT',FFs={c.name:dict(master='SDFF_X1',roots={'Q':c.name}) for c in cells},
        nets={c.name:dict(driver_xy=[c.x_um,c.y_um],sinks=[],ports=[]) for c in cells},
        transparent={'a':['so','functional']},scan_ports={'test_si':[0,1], 'test_so':[0,20],
            'test_si_1':[100,50], 'test_so_1':[0,50]},scan_endpoints={'chain0_so':dict(
            port='test_so',buffer_instance='buf',buffer_master='BUF_X1',input_pin='A',output_pin='Z',
            buffer_xy=[50,3],output_net='so',original_source_net='a',original_owner_ff='a',
            port_xy=[0,20],inherited_port_xy=[0,99])})
    g['nets']['a']['sinks']=[sink([-5,9]),sink([50,3],'BUF_X1'),sink([3,4],'INV_X1')]
    g['nets']['b']['sinks']=[sink([-4,40])]
    g['nets']['so']=dict(driver_xy=[50,3],sinks=[],ports=[])
    g['nets']['functional']=dict(driver_xy=[3,4],sinks=[sink([5,8])],ports=[])
    loads={('BUF_X1','A'):0.974659,('LOGIC','A'):2.,('SDFF_X1','SI'):1.,('INV_X1','A'):.4}
    return a,g,loads


def old_graph(g):
    return {k:deepcopy(g[k]) for k in ('stage','FFs','nets','transparent')}


def test_transfer_preserves_unrelated_sinks_and_branch(case):
    a,g,l=case; before=deepcopy(g); identity=a.canonical_dict()
    w, audit=construct_with_audit(a,g,l); s=audit['selected_graph']
    assert audit['buffer_owner']=='b' and audit['owners']['functional']=='a'
    assert s['nets']['a']['sinks']==[g['nets']['a']['sinks'][0],g['nets']['a']['sinks'][2]]
    assert s['nets']['b']['sinks'][0]==g['nets']['b']['sinks'][0]
    assert s['nets']['functional']==g['nets']['functional']
    assert g==before and a.canonical_dict()==identity
    old=legacy(a,old_graph(g),l,g['scan_ports'])
    assert w['M4_pin'][0]==pytest.approx(old['M4_pin'][0]-.974659)
    assert w['M4_pin'][1]==pytest.approx(old['M4_pin'][1]+.974659)
    assert sum(w['M4_pin'])==pytest.approx(sum(old['M4_pin']))
    assert s['transparent']['a']==['functional'] and s['transparent']['b']==['so']


def test_original_owner_is_selected_tail_no_duplicate(case):
    a,g,l=case
    a=ScanArchitecture(a.cells,(ScanChain('0',('b','a')),a.chains[1]))
    w,audit=construct_with_audit(a,g,l)
    old=legacy(a,old_graph(g),l,g['scan_ports'])
    np.testing.assert_array_equal(w['M4_pin'],old['M4_pin'])
    assert audit['buffer_owner']=='a'
    assert audit['selected_graph']['nets']['a']['sinks']==g['nets']['a']['sinks']
    assert audit['selected_graph']['transparent']==g['transparent']
    assert sum(r['net']=='so' for ff in audit['FFs'].values() for r in ff)==1


def test_geometry_reconstructed_and_no_synthetic_chain0_point(case):
    a,g,l=case; w, audit=construct_with_audit(a,g,l)
    b={r['net']:r for r in audit['FFs']['b']}
    assert b['b']['points']==[[10,10],[-4,40],[50,3]]
    assert b['b']['additions']==[]
    assert b['so']['points']==[[50,3],[0,20]]
    assert w['M5_hpwl'][1]==hpwl(b['b']['points'])+hpwl(b['so']['points'])
    # Point removal is nonlinear: unchanged extrema need not lose the branch's Manhattan length.
    old_points=[[0,0],[-5,9],[50,3],[3,4],[10,10]]
    new_points=[[0,0],[-5,9],[3,4],[10,10]]
    assert hpwl(old_points)-hpwl(new_points)!=53
    assert w['M3_load'][1]==w['M4_pin'][1]+CAP_PER_UM*w['M5_hpwl'][1]
    assert sum(r['ports'].count([0,20]) for ff in audit['FFs'].values() for r in ff)==1


def test_chain1_direct_semantics_unchanged(case):
    a,g,l=case; w,audit=construct_with_audit(a,g,l)
    old=legacy(a,old_graph(g),l,g['scan_ports'])
    for m in w:
        np.testing.assert_array_equal(w[m][2:],old[m][2:])
    assert audit['FFs']['d'][0]['additions']==[dict(xy=[0,50],master=None,pin='test_so_1')]


def test_complete_descendant_branch_transfers(case):
    a,g,l=case
    g['nets']['so']['sinks']=[dict(xy=[55,5],master='INV_X1',pin='A')]
    g['transparent']['so']=['leaf']
    g['nets']['leaf']=dict(driver_xy=[55,5],sinks=[dict(xy=[70,5],master='LOGIC',pin='A')],ports=[])
    w,audit=construct_with_audit(a,g,l)
    assert audit['owners']['so']==audit['owners']['leaf']=='b'
    old=legacy(a,old_graph(g),l,g['scan_ports'])
    assert old['M4_pin'][0]-w['M4_pin'][0]==pytest.approx(.974659+.4+2)
    assert w['M4_pin'][1]-old['M4_pin'][1]==pytest.approx(.974659+.4+2)


@pytest.mark.parametrize('where',['top','net','sink','ff','endpoint','ports'])
def test_rejects_routed_features_at_every_schema_level(case,where):
    a,g,l=case
    target={'top':g,'net':g['nets']['a'],'sink':g['nets']['a']['sinks'][0],
        'ff':g['FFs']['a'],'endpoint':g['scan_endpoints']['chain0_so'],'ports':g['scan_ports']}[where]
    target['routed_cap_ff']=12.
    with pytest.raises(ValueError): construct_weights(a,g,l)


def test_no_coefficient_override_or_reference_argument(case):
    a,g,l=case
    with pytest.raises(TypeError): construct_weights(a,g,l,reference={})
    with pytest.raises(TypeError): construct_weights(a,g,l,cap_per_um=.2)
    l['reference']=5
    with pytest.raises(ValueError): construct_weights(a,g,l)


def test_rejects_ambiguous_buffer_and_bijection(case):
    a,g,l=case
    g['nets']['a']['sinks'].append(deepcopy(g['nets']['a']['sinks'][1]))
    with pytest.raises(ValueError): construct_weights(a,g,l)
    g['nets']['a']['sinks'].pop()
    bad=ScanArchitecture(a.cells,(ScanChain('0',('a','a')),a.chains[1]))
    with pytest.raises(ValueError): construct_weights(bad,g,l)


def test_historical_frozen_weights_reproduce_exactly():
    root=Path(__file__).resolve().parents[2]
    freeze=root/'results/phase2c_repair/freeze.json'
    lib=dependency_path('OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib')
    if not freeze.exists() or not lib.exists():
        pytest.skip('Frozen external Liberty/weights unavailable; this optional gate covers historical 21-order evidence')
    l=pin_loads(lib.read_text()); f=relocate(json.loads(freeze.read_text()))
    if any(not Path(r['architecture_path']).is_file() or
           not (experiment_root()/'results/phase2b_activity_model'/r['architecture_sha256']/'predictor_weights.json').is_file()
           for r in f['architectures']):
        pytest.skip('Historical external architecture/weight set unavailable')
    for r in f['architectures']:
        a=ScanArchitecture.from_json(Path(r['architecture_path']))
        g=json.loads((root/f"results/phase2c_repair/{r['design']}.placed_graph.json").read_text())
        before=a.canonical_dict()
        old=legacy(a,old_graph(g),l,g['scan_ports'])
        p=experiment_root()/'results/phase2b_activity_model'/a.sha256()/'predictor_weights.json'
        expected=json.loads(p.read_text()); names=sorted(g['FFs'])
        for m in old:
            np.testing.assert_array_equal(old[m],[expected[m][n] for n in names])
        assert a.canonical_dict()==before and a.sha256()==r['architecture_sha256']
