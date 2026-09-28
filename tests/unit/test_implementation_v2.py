import numpy as np
import pytest
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.optimizer.implementation_v2 import Model, State, Config, reference, optimize, order_id, select
from pact.optimizer.search import proposal, update_locations


def fixture():
    arch = ScanArchitecture(tuple(ScanCell(str(i), float(i), float(i % 2), 'CK') for i in range(5)),
                            (ScanChain('a', ('0', '1', '2'), 'si0', 'so0'), ScanChain('b', ('3', '4'), 'si1', 'so1')))
    model = Model(arch, [[1, 0, 1, 0, 1], [0, 1, 1, 1, 0]], [[0, 1, 0, 1, 1], [1, 0, 0, 0, 1]],
                  [1., 2., 3., 4., 5.], [0, 0, 5, 2], [[0, 0], [0, 1]], [[5, 0], [5, 1]])
    return model, model.orders(arch)


def test_reference_load_unload_and_weights():
    model, orders = fixture()
    score, counts = reference(model, orders, True)
    # Leading padding on short chain; first long-chain input is target FF 2.
    assert counts[0, 0, 0].tolist() == [1, 0, 0, 0, 0]
    # Capture response [0,1,0] / [1,1] unloads simultaneously to [0,0,1] / [0,1].
    assert counts[0, 1, 0].tolist() == [0, 1, 1, 1, 0]
    assert score[1] == float((counts * model.caps).sum())
    np.testing.assert_allclose(State(model, orders).score(), score, rtol=1e-12)


def test_incremental_all_operators_and_rollback():
    model, orders = fixture()
    state = State(model, orders)
    rng = np.random.default_rng(27)
    neighbors = np.tile(np.arange(5), (5, 1))
    for iteration in range(100):
        before = state.score().copy()
        patch, _ = proposal(state, neighbors, rng, iteration, 4)
        if patch is None:
            continue
        undo = state.change(patch)
        np.testing.assert_allclose(state.score(), reference(model, state.orders), rtol=1e-12, atol=1e-10)
        if iteration % 2:
            state.change(undo)
            np.testing.assert_allclose(state.score(), before, rtol=1e-12, atol=1e-10)
        else:
            update_locations(state, patch)


def test_legality_unknowns_and_serialization(tmp_path):
    model, orders = fixture()
    with pytest.raises(ValueError, match='bijection'):
        model.validate([np.array([0, 0, 2]), np.array([3, 4])])
    with pytest.raises(ValueError, match='bijection'):
        model.validate([np.array([0, 1]), np.array([2, 3, 4])])
    arch = model.architecture_from(orders)
    arch.to_json(tmp_path/'arch.json')
    assert ScanArchitecture.from_json(tmp_path/'arch.json').sha256() == arch.sha256()
    with pytest.raises(ValueError, match='binary'):
        Model(arch, [['X']*5], [[0]*5], [1]*5, [0, 0, 5, 2], [[0, 0]]*2, [[5, 1]]*2)


def test_deterministic_search_and_selection():
    model, orders = fixture()
    config = Config(seconds=30, max_evaluations=60, restart_interval=10, wire_allowance=1, timing_allowance=1)
    a = optimize(model, [('P', orders)], config)
    b = optimize(model, [('P', orders)], config)
    assert a['evaluations'] == b['evaluations'] == 60
    assert [order_id(r['orders']) for r in a['archive']] == [order_id(r['orders']) for r in b['archive']]
    assert a['new_unique'] > 0
    selected = select(a['archive'], a['baselines'][0]['score'])
    assert len(selected) <= 3
    assert len({order_id(r['orders']) for r in selected}) == len(selected)
    assert all(r['new'] for r in selected)


def test_spatial_accumulation_coarse_grid():
    model, orders = fixture()
    model.bins[:] = 0
    model.bins4[:] = 0
    score, counts = reference(model, orders, True)
    expected = (counts*model.caps).sum(axis=-1).max()
    assert score[2] == score[4] == expected
    np.testing.assert_allclose(State(model, orders).score(), score)


def test_cli_binding_accepts_serialized_path(tmp_path):
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[2]/'scripts/pact_v2.py'
    spec = importlib.util.spec_from_file_location('pact_v2_cli_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path/'architecture.json'
    path.write_text('{}')
    assert module.binding(str(path)) == module.binding(path)
