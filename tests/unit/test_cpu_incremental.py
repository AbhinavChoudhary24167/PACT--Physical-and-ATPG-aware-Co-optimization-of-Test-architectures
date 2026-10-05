"""Exact numerical equivalence and complete rejected-transaction restoration."""
import hashlib
import json
import numpy as np

from pact.optimizer import candidate_stateful as oracle, stage_b
from pact.optimizer.cpu_incremental import State, transition_count, update_tile
from pact.optimizer.cpu_reference import reference as bounded_reference
from pact.optimizer.search import proposal, update_locations
from test_candidate_stateful import fixture


def snapshot(state):
    digest = hashlib.sha256()
    for value in [*state.orders, *state.ds, state.field, state.chain_of, state.position]:
        digest.update(np.ascontiguousarray(value).tobytes())
    for net, wave in sorted(state.waves.items()):
        digest.update(net.encode())
        digest.update(wave.tobytes())
    digest.update(json.dumps([state.caps, state.energy, state.endpoints, state.transitions], sort_keys=True).encode())
    digest.update(state.score().tobytes())
    return digest.hexdigest()


def test_thousands_of_all_operators_match_oracle_and_restore_bitwise():
    model, orders = fixture()
    expected, actual = oracle.State(model, orders), State(model, orders)
    reference_score = expected.score()
    neighbors = np.tile(np.arange(len(model.names)), (len(model.names), 1))
    rng = np.random.default_rng(11)
    evaluated, rejected, kinds = 0, 0, set()
    for attempt in range(4096):
        patch, kind = proposal(actual, neighbors, rng, attempt, 4)
        if patch is None:
            continue
        before = snapshot(actual)
        old_score = actual.score()
        left, right = expected.change(patch), actual.change(patch)
        expected_score, actual_score = expected.score(), actual.score()
        np.testing.assert_allclose(actual_score, expected_score, rtol=1e-9, atol=1e-6)
        np.testing.assert_allclose(actual_score, oracle.reference(model, actual.orders), rtol=1e-9, atol=1e-6)
        if evaluated % 64 == 0:
            np.testing.assert_allclose(bounded_reference(model, actual.orders), oracle.reference(model, actual.orders), rtol=1e-9, atol=1e-6)
        # Exercise the registered objective and comparison threshold as well
        # as mixed commits/rejects, including cross-chain and tail changes.
        a = stage_b.activity_score(actual_score, reference_score, (1., 1., 1.))
        b = stage_b.activity_score(expected_score, reference_score, (1., 1., 1.))
        np.testing.assert_allclose(a, b, rtol=1e-9, atol=1e-6)
        threshold = stage_b.activity_score(old_score, reference_score, (1., 1., 1.))
        assert (a < threshold - 1e-10 * max(1., abs(threshold))) == (b < threshold - 1e-10 * max(1., abs(threshold)))
        if evaluated % 3:
            expected.change(left)
            actual.change(right)
            assert snapshot(actual) == before
            rejected += 1
        else:
            update_locations(expected, patch)
            update_locations(actual, patch)
        np.testing.assert_allclose(actual.field, expected.field, rtol=1e-9, atol=1e-6)
        for net in actual.waves:
            np.testing.assert_array_equal(actual.waves[net], expected.waves[net])
        evaluated += 1
        kinds.add(kind)
    assert evaluated > 2000 and rejected > 1000
    assert kinds == {'swap', 'cross_chain_swap', '2opt', 'relocate', 'segment_exchange'}


def test_fixed_path_search_champions_and_acceptance_are_unchanged():
    model, orders = fixture()
    config = stage_b.Config(seconds=60, max_evaluations=64, lane_attempts=20)
    left = stage_b.optimize(model, [('REF', orders)], 'REF', config, state_type=oracle.State)
    right = stage_b.optimize(model, [('REF', orders)], 'REF', config, state_type=State)
    assert left['evaluations'] == right['evaluations'] == 64
    for key in ('accepted', 'attempts', 'screened_infeasible', 'termination'):
        assert left[key] == right[key]
    for a, b in zip(left['selected'], right['selected'], strict=True):
        assert a['roles'] == b['roles']
        for ao, bo in zip(a['orders'], b['orders'], strict=True):
            np.testing.assert_array_equal(ao, bo)
        np.testing.assert_allclose(a['score'], b['score'], rtol=1e-9, atol=1e-6)


def test_sparse_blocks_padding_and_zero_capacitance():
    rng = np.random.default_rng(19)
    for cycles in (1, 7, 8, 9, 12, 64):
        old, new = [np.packbits(rng.integers(0, 2, cycles*3, dtype=np.uint8), bitorder='little') for _ in range(2)]
        for oldcap, newcap in ((0., 3.), (3., 0.), (3., 3.)):
            for wave in (old, new):
                expected = rng.random((cycles, 64))
                actual = expected[:, 17].copy()
                energy = oracle.update_field(expected, old, wave, oldcap, newcap, 17)
                count = update_tile(actual, old, wave, oldcap, newcap, transition_count(old, cycles))
                assert count == transition_count(wave, cycles)
                assert energy == count*newcap
                np.testing.assert_array_equal(actual, expected[:, 17])
