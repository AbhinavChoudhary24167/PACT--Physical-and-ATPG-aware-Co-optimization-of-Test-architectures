import json
import numpy as np
import pytest
from pact.optimizer import implementation_v2 as v2
from pact.optimizer import candidate_sensitive as cs
from pact.optimizer import candidate_stateful as sf
from pact.optimizer.stateful_geometry import mmst, estimate
from pact.optimizer.search import proposal, update_locations
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def fixture(depth=3):
    arch = ScanArchitecture(tuple(ScanCell(n, float(i*2+2), float(i % 2), 'CK') for i, n in enumerate('abcde')),
        (ScanChain('c0', tuple('abc'), 'test_si_0', 'test_so_0'),
         ScanChain('c1', tuple('de'), 'test_si_1', 'test_so_1')))
    base = v2.Model(arch, [[1, 0, 1, 0, 1], [0, 1, 1, 1, 0]], [[0, 1, 0, 1, 1], [1, 0, 0, 0, 1]],
        [2]*5, [0, 0, 14, 4], [[0, 0], [0, 3]], [[14, 0], [14, 3]])
    cells, nets = {}, {}
    def cell(name, master, xy, inputs, outputs, transparent=False):
        cells[name] = dict(master=master, xy=xy, inputs=inputs, outputs=outputs, transparent=transparent)
    def net(name, source, xy, sinks=(), ports=()):
        nets[name] = dict(source=source, xy=xy,
            sinks=[dict(cell=c, pin=p, xy=cells[c]['xy'], cap=1.) for c, p in sinks],
            ports=[dict(name=p, xy=pos) for p, pos in ports])
    for i, n in enumerate('abcde'):
        cell(n, 'SDFF_X1', base.xy[i].tolist(), {}, {'Q': n+'q', 'QN': n+'n'})
    cell('inv', 'INV_X1', [3, 1], {'A': 'aq'}, {'ZN': 'iv'}, True)
    cell('cancel', 'XOR2_X1', [4, 1], {'A': 'aq', 'B': 'aq'}, {'Z': 'cancel'})
    cell('complement', 'AND2_X1', [4, 2], {'A': 'aq', 'B': 'an'}, {'Z': 'complement'})
    cell('reconverge', 'XOR2_X1', [5, 2], {'A': 'iv', 'B': 'an'}, {'Z': 'reconverge'})
    cell('g1', 'XOR2_X1', [5, 1], {'A': 'aq', 'B': 'bq'}, {'Z': 'l1'})
    cell('g2', 'AND2_X1', [6, 1], {'A': 'l1', 'B': 'cq'}, {'Z': 'l2'})
    cell('g3', 'XOR2_X1', [7, 1], {'A': 'l2', 'B': 'dq'}, {'Z': 'l3'})
    cell('g4', 'XOR2_X1', [8, 1], {'A': 'l3', 'B': 'eq'}, {'Z': 'l4'})
    cell('out', 'BUF_X1', [12, 0], {'A': 'cq'}, {'Z': 'out'}, True)
    sinkmap = {n: [] for n in ['aq', 'an', 'bq', 'bn', 'cq', 'cn', 'dq', 'dn', 'eq', 'en',
                                  'iv', 'cancel', 'complement', 'reconverge', 'l1', 'l2', 'l3', 'l4', 'out']}
    for cname, data in cells.items():
        for p, n in data['inputs'].items(): sinkmap[n].append((cname, p))
    for a, b in [('a', 'b'), ('b', 'c'), ('d', 'e')]: sinkmap[a+'q'].append((b, 'SI'))
    for cname, data in cells.items():
        for p, n in data['outputs'].items():
            ports = [('test_so_1', [14, 3])] if n == 'eq' else [('test_so', [14, 0])] if n == 'out' else []
            net(n, cname+'/'+p, data['xy'], sinkmap[n], ports)
    net('si0', 'PORT/test_si', [0, 0], [('a', 'SI')])
    net('si1', 'PORT/test_si_1', [0, 3], [('d', 'SI')])
    graph = dict(cells=cells, nets=nets, bounds=[0, 0, 14, 4],
        functions={'INV_X1/ZN': '!A', 'BUF_X1/Z': 'A', 'XOR2_X1/Z': 'A ^ B', 'AND2_X1/Z': 'A & B'})
    caprows = [dict(net=n, ground_ff=2., pin_ff=len(d['sinks'])) for n, d in nets.items()]
    sensitive = cs.Model(base, dict(rho=.1, sink=[1]*5, spatial=np.zeros((5, 64)), si_extra=[0, 0], so_extra=[1, 0]), graph['bounds'])
    model = sf.Model(sensitive, graph, caprows, {}, depth)
    return model, model.orders(arch)


def test_mmst_two_terminal_shared_and_deterministic():
    assert mmst([[0, 0], [3, 4]]) == 7
    points = [[0, 0], [3, 0], [3, 4], [0, 0]]
    assert mmst(points) == mmst(reversed(points)) == 7
    assert mmst(points) < 3+7  # retained branch reused, not independent star
    assert mmst([]) == mmst([[1, 1], [1, 1]]) == 0


def test_baseline_ground_reproduction_and_zero_span():
    model, orders = fixture()
    caps, audit = model.geometry.capacitances(orders, details=True)
    for n, row in audit.items():
        assert row['candidate_terminals'] == row['baseline_terminals']
        assert row['candidate_ground_ff'] == pytest.approx(2.)
        assert caps[n] == pytest.approx(2+model.geometry.pin[n])
    assert estimate(2, 4, 8, .1) == (4, .5, None)
    assert estimate(2, 0, 0, .1)[0] == 2
    assert estimate(2, 0, 5, .1)[0] == 2.5
    assert 'zero_span' in estimate(2, 0, 5, .1)[2]
    assert estimate(None, 5, 10, .1) == (1, None, 'missing_ground_global_scan_rho')


def test_Q_QN_reconvergence_and_logic_depth():
    model, orders = fixture()
    score, waves, field = sf.reference(model, orders, True)
    np.testing.assert_array_equal(waves['an'], 1-waves['aq'])
    assert not waves['cancel'].any()
    assert not waves['complement'].any()
    assert not waves['reconverge'].any()
    assert 'l3' in waves and 'l4' not in waves
    assert next(g for g in model.gates if g['net'] == 'iv')['depth'] == 0
    state = sf.State(model, orders)
    np.testing.assert_allclose(state.score(), score, rtol=1e-12, atol=1e-10)
    for n in waves:
        bits = np.unpackbits(state.waves[n], bitorder='little')[:model.cycles*3].reshape(-1, 3)
        np.testing.assert_array_equal(bits, waves[n])
    assert sum(state.contributions().values()) == pytest.approx(score[1])


def test_incremental_simultaneous_changes_rollback_and_all_mutations():
    model, orders = fixture()
    state = sf.State(model, orders)
    rng = np.random.default_rng(7)
    neighbors = np.tile(np.arange(5), (5, 1))
    total_cancellation = 0
    kinds = set()
    for step in range(100):
        patch, kind = proposal(state, neighbors, rng, step, 4)
        if patch is None: continue
        kinds.add(kind)
        before = state.score().copy()
        undo = state.change(patch)
        total_cancellation += model.last_mutation['cancellation_events']
        np.testing.assert_allclose(state.score(), sf.reference(model, state.orders), rtol=1e-12, atol=1e-10)
        assert not np.unpackbits(state.waves['complement'], bitorder='little')[:model.cycles*3].any()
        if step % 2:
            state.change(undo)
            np.testing.assert_allclose(state.score(), before, rtol=1e-12, atol=1e-10)
        else: update_locations(state, patch)
    assert total_cancellation > 0
    assert kinds == {'swap', 'cross_chain_swap', '2opt', 'relocate', 'segment_exchange'}


def test_changed_topology_shared_terminals_and_serialization(tmp_path):
    model, orders = fixture()
    state = sf.State(model, orders)
    old = model.geometry.capacitances(orders)
    state.change({0: (np.array([1, 2]), np.array([2, 1]))})
    new, audit = model.geometry.capacitances(state.orders, details=True)
    assert old['aq'] != new['aq']
    assert 'c/SI' in {t['id'] for t in audit['aq']['candidate_terminals']}
    assert 'b/SI' not in {t['id'] for t in audit['aq']['candidate_terminals']}
    assert 'inv/A' in {t['id'] for t in audit['aq']['candidate_terminals']}
    arch = model.architecture_from(state.orders)
    assert model.canonical_id(state.orders) == arch.sha256()
    arch.to_json(tmp_path/'arch.json')
    restored = ScanArchitecture.from_json(tmp_path/'arch.json')
    np.testing.assert_allclose(sf.reference(model, model.orders(restored)), state.score())
    assert restored.sha256() == arch.sha256()


def test_deterministic_existing_search_hooks():
    model, orders = fixture()
    cfg = v2.Config(seconds=60, max_evaluations=30, restart_interval=10, wire_allowance=2, timing_allowance=2)
    def run(): return v2.optimize(model, [('P', orders)], cfg, state_type=sf.State, reference_evaluator=sf.reference, verify_interval=10)
    a, b = run(), run()
    assert [v2.order_id(r['orders']) for r in a['archive']] == [v2.order_id(r['orders']) for r in b['archive']]
