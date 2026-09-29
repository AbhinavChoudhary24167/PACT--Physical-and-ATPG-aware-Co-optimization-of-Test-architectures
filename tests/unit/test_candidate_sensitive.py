import numpy as np
import pytest
from pact.optimizer import implementation_v2 as v2
from pact.optimizer import candidate_sensitive as cs
from pact.optimizer.candidate_physical import construct, sensitivity
from pact.optimizer.search import proposal, update_locations
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def fixture():
    arch = ScanArchitecture(tuple(ScanCell(str(i), float(i+1), float(i % 2), 'CK') for i in range(5)),
        (ScanChain('a', ('0', '1', '2'), 'si0', 'so0'), ScanChain('b', ('3', '4'), 'si1', 'so1')))
    frozen = v2.Model(arch, [[1, 0, 1, 0, 1], [0, 1, 1, 1, 0]], [[0, 1, 0, 1, 1], [1, 0, 0, 0, 1]],
        [1., 2., 3., 4., 5.], [0, 0, 6, 2], [[0, 0], [0, 1]], [[6, 0], [6, 1]])
    spatial = np.zeros((5, 64))
    for i in range(5):
        spatial[i, frozen.bins[i]] = i+1
        spatial[i, 50-i] += .4*i
    physical = dict(rho=.2, sink=[1, 2, 1, 3, 2], spatial=spatial, si_extra=[.7, 0], so_extra=[.6, 0])
    model = cs.Model(frozen, physical, [0, 0, 6, 2])
    return model, model.orders(arch)


def test_candidate_E_H8_and_ports():
    model, orders = fixture()
    expected = cs.reference(model, orders)
    np.testing.assert_allclose(cs.State(model, orders).score(), expected, rtol=1e-12)
    local = cs.reference(model, orders, source_local=True)
    assert local[1] == pytest.approx(expected[1])
    assert local[2] != expected[2]
    bs, ws = model.weights(0, orders[0], np.array([0, 2]))
    assert ws[0].sum() == pytest.approx(model.static[0].sum()+2+.2*2)
    assert ws[1].sum() == pytest.approx(model.static[2].sum()+.6+.2*3)
    # Leading zero padding; SI unload begins by changing the last load bit to 0.
    si = cs.input_transitions(model, orders[1])
    assert si[0, 0].tolist() == [0, 1, 1]
    assert si[1, 1, 0] == model.load[1, orders[1][0]]


def test_incremental_successors_all_mutations_and_rejection():
    model, orders = fixture()
    state = cs.State(model, orders)
    rng = np.random.default_rng(71)
    neighbors = np.tile(np.arange(5), (5, 1))
    operators = set()
    for iteration in range(160):
        before = state.score().copy()
        patch, kind = proposal(state, neighbors, rng, iteration, 4)
        if patch is None: continue
        operators.add(kind)
        undo = state.change(patch)
        np.testing.assert_allclose(state.score(), cs.reference(model, state.orders), rtol=1e-12, atol=1e-10)
        if iteration % 2:
            state.change(undo)
            np.testing.assert_allclose(state.score(), before, rtol=1e-12, atol=1e-10)
        else: update_locations(state, patch)
    assert operators == {'swap', 'cross_chain_swap', '2opt', 'relocate', 'segment_exchange'}


def test_stationary_predecessor_load_changes():
    model, orders = fixture()
    state = cs.State(model, orders)
    previous = state.weights[0][0].sum()
    undo = state.change({0: (np.array([1, 2]), np.array([2, 1]))})
    assert state.orders[0][0] == 0
    assert previous != state.weights[0][0].sum()
    np.testing.assert_allclose(state.score(), cs.reference(model, state.orders))
    state.change(undo)
    assert state.weights[0][0].sum() == pytest.approx(previous)


def test_deterministic_replay_serialization(tmp_path):
    model, orders = fixture()
    cfg = v2.Config(seconds=60, max_evaluations=60, restart_interval=10, wire_allowance=2, timing_allowance=2)
    def run(): return v2.optimize(model, [('P', orders)], cfg, state_type=cs.State,
        reference_evaluator=cs.reference, verify_interval=10)
    a, b = run(), run()
    assert a['evaluations'] == b['evaluations'] == 60
    assert [v2.order_id(r['orders']) for r in a['archive']] == [v2.order_id(r['orders']) for r in b['archive']]
    for row in a['archive']:
        arch = model.architecture_from(row['orders'])
        arch.to_json(tmp_path/'arch.json')
        restored = ScanArchitecture.from_json(tmp_path/'arch.json')
        assert restored.sha256() == arch.sha256()
        np.testing.assert_allclose(cs.reference(model, model.orders(restored)), row['score'])


def test_frontier_selection_rejects_dominated_and_equal():
    def row(values, i, new=True):
        return dict(score=np.array(values), orders=[np.array([i])], new=new, label=str(i))
    baseline = [row([10, 10, 10], 0, False), row([12, 5, 6], 1, False)]
    candidates = [row([10, 10, 10], 2), row([13, 6, 7], 3), row([10, 9, 9], 4), row([11, 4, 7], 5)]
    selected = cs.select(candidates, baseline)
    assert {r['label'] for r in selected} == {'4', '5'}
    assert cs.select(candidates[:2], baseline) == []
    assert selected[0]['roles'] == ['predicted_dominates:0']


def test_liberty_sensitivity():
    assert sensitivity('!(A & B)') == {'A': .5, 'B': .5}
    assert sensitivity('(A ^ B)') == {'A': 1., 'B': 1.}
    assert sensitivity('!A') == {'A': 1.}
    with pytest.raises(ValueError): sensitivity('__import__(A)')


def test_mixed_Q_QN_decomposition_transparent_gate_and_port_buffers():
    arch = ScanArchitecture((ScanCell('a', 2., 0., 'CK'), ScanCell('b', 6., 0., 'CK')),
        (ScanChain('c', ('a', 'b'), 'test_si_0', 'test_so_0'),))
    model = v2.Model(arch, [[1, 0]], [[0, 1]], [4, 4], [0, 0, 10, 2], [[0, 0]], [[10, 0]])
    cells = {}
    def cell(name, x, inputs, outputs, transparent=False, master='SDFF_X1'):
        cells[name] = dict(xy=[x, 0], inputs=inputs, outputs=outputs, transparent=transparent, master=master)
    cell('a', 2, {'SI': 'si'}, {'Q': 'q', 'QN': 'qn'})
    cell('b', 6, {'SI': 'q'}, {'Q': 'qb'})
    cell('inv', 4, {'A': 'q'}, {'ZN': 'iv'}, True, 'INV_X1')
    cell('gate', 5, {'A': 'iv', 'B': 'qn'}, {'ZN': 'g'}, False, 'NAND2_X1')
    cell('out', 8, {'A': 'qb'}, {'Z': 'so'}, True, 'BUF_X1')
    nets = {}
    def net(name, source, x, sinks=(), ports=()):
        nets[name] = dict(source=source, xy=[x, 0], sinks=[dict(cell=c, pin=p, xy=cells[c]['xy'], cap=1.) for c, p in sinks],
            ports=[dict(name=p, xy=[px, 0]) for p, px in ports])
    net('si', 'PORT/test_si', 0, [('a', 'SI')])
    net('q', 'a/Q', 2, [('b', 'SI'), ('inv', 'A')])
    net('qn', 'a/QN', 2, [('gate', 'B')])
    net('iv', 'inv/ZN', 4, [('gate', 'A')])
    net('g', 'gate/ZN', 5, ports=[('result', 9)])
    net('qb', 'b/Q', 6, [('out', 'A')])
    net('so', 'out/Z', 8, ports=[('test_so', 10)])
    caprows = [dict(net=n, pin_ff=len(d['sinks']), ground_ff=2.) for n, d in nets.items()]
    graph = dict(cells=cells, nets=nets, functions={'NAND2_X1/ZN': '!(A & B)'}, bounds=[0, 0, 10, 2])
    result = construct(model, graph, caprows)
    dec = {d['net']: d for d in result['decomposition']}
    assert dec['q']['functional_ff'] == 2.  # 1 pin + 2*(2/4) wire
    assert dec['q']['removed_scan_ff'] == 2.
    assert dec['qn']['functional_ff'] == 3.
    assert dec['qb']['functional_ff'] == 0
    assert dec['so']['functional_ff'] == 0
    assert result['rho'] == 1.  # each qualified scan-only segment: 2 fF / 2 um
    assert result['so_extra'] == [1.]
    assert result['sink'] == [1., 1.]
    assert any(r['net'] == 'iv' and r['source'] == 'a' for r in result['influence'])
    assert any(r['net'] == 'g' and r['kind'] == 'one_gate_influence' for r in result['influence'])
    assert sum(r['cap_ff'] for r in result['influence'] if r['net'] == 'g') == 2.
    assert all(d['functional_ff']+d['removed_scan_ff'] == pytest.approx(d['total_ff']) for d in dec.values())
