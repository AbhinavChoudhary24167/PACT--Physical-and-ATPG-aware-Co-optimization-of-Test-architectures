import numpy as np
import pytest
from pact.optimizer import stage_b as sb
from pact.optimizer import candidate_stateful as sf
from test_candidate_stateful import fixture


def test_normalization_and_invalid_configuration():
    ref = np.array([10., 100., 20., 2., 40.])
    candidate = np.array([11., 80., 10., 3., 30.])
    assert sb.activity_score(candidate, ref, (2., 1., 1.)) == pytest.approx((2*.8+.75+.5)/4)
    for kwargs in ({'epsilon': -1}, {'seconds': 0}, {'weights': (0, 0, 0)},
                   {'weights': (1, float('nan'), 1)}, {'max_evaluations': 0}):
        with pytest.raises(ValueError):
            sb.Config(**kwargs)


def test_infeasible_moves_screened_without_activity_update(monkeypatch):
    class Model:
        names = ('a', 'b')
        xy = np.array([[0., 0.], [1., 1.]])
        def physical(self, orders):
            return (10. if orders[0][0] == 0 else 20.), 1.
    class State:
        changes = 0
        def __init__(self, model, orders):
            self.costs = model
            self.orders = [o.copy() for o in orders]
        def score(self):
            return np.array([self.costs.physical(self.orders)[0], 100., 20., 1., 40.])
        def change(self, patch):
            State.changes += 1
            raise AssertionError('Infeasible move reached activity evaluator')
    monkeypatch.setattr(sb, 'proposal', lambda *args: ({0: (np.array([0, 1]), np.array([1, 0]))}, 'swap'))
    orders = [np.array([0, 1], np.int32)]
    result = sb.optimize(Model(), [('B2', orders)], 'B2',
        sb.Config(epsilon=.02, stagnation_attempts=10), state_type=State,
        reference_evaluator=lambda model, orders: State(model, orders).score())
    assert result['screened_infeasible'] == 10
    assert result['evaluations'] == State.changes == 0
    assert result['termination'] == 'stagnation'
    assert len(result['selected']) == 1
    assert result['selected'][0]['roles'] == list(sb.ROLES)
    np.testing.assert_array_equal(orders[0], [0, 1])


def test_constrained_retained_candidates_match_independent_replay():
    model, orders = fixture()
    result = sb.optimize(model, [('B2', orders)], 'B2',
        sb.Config(epsilon=.10, seconds=30, max_evaluations=25, stagnation_attempts=500, lane_attempts=10))
    assert result['evaluations'] > 0
    assert 1 <= len(result['selected']) <= 4
    for row in result['selected']:
        assert row['score'][0] <= result['wire_ceiling_um'] + 1e-8
        model.validate(row['orders'])
        np.testing.assert_allclose(row['score'], sf.reference(model, row['orders']), rtol=1e-9, atol=1e-6)


def test_stage_b_preserves_reversed_capacity_start():
    from pact_stage_b import Model
    model, orders = fixture()
    model.__class__ = Model
    reversed_sizes = [np.array([0, 1]), np.array([2, 3, 4])]
    model.validate(reversed_sizes)
    score = sf.State(model, reversed_sizes).score()
    np.testing.assert_allclose(score, sf.reference(model, reversed_sizes), rtol=1e-9, atol=1e-6)
    with pytest.raises(ValueError):
        model.validate([np.array([0]), np.array([1, 2, 3, 4])])


def test_report_preserves_frozen_and_expanded_dominance():
    from pact_stage_b_report import point, relation
    baseline = dict(routed_scan_path_cost_um=100, measured_E=1000, measured_H4=20, measured_H8=10)
    candidate = dict(routed_scan_path_cost_um=99, measured_E=900, measured_H4=21, measured_H8=9)
    assert relation(point(candidate, False), point(baseline, False)) == 'dominating'
    assert relation(point(candidate), point(baseline)) == 'nondominated'
    assert relation(point(baseline), point(baseline)) == 'nondominated'
