"""Three-objective implemented dominance and honest missing-data treatment."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from pact_oss_compare import implemented_point, pareto_rows


def row(method, sha, wire, energy, hotspot, design='s5378', status='QUALIFIED'):
    return dict(design=design, method=method, architecture_hash=sha, status=status,
                routed_scan_path_cost_um=wire, measured_E=energy, measured_H8=hotspot)


def test_three_objective_tradeoffs_and_exact_domination():
    rows = [row('B3', 'a', 1, 3, 3), row('P0', 'b', 2, 2, 2), row('P0', 'c', 3, 1, 1), row('B1', 'd', 3, 3, 3)]
    assert [r['implemented_nondominated'] for r in pareto_rows(rows)] == [True, True, True, False]


def test_equal_points_do_not_dominate_or_create_unique_coordinates():
    result = pareto_rows([row('B3', 'same', 1, 2, 3), row('P0', 'same', 1, 2, 3)])
    assert all(r['implemented_nondominated'] for r in result)
    assert result[1]['coordinate_unique_vs_external'] is False
    assert result[1]['architecture_unique_vs_external'] is False


def test_architecture_uniqueness_is_separate_from_coordinate_uniqueness():
    result = pareto_rows([row('B3', 'a', 1, 2, 3), row('P0', 'b', 1, 2, 3)])
    assert result[1]['architecture_unique_vs_external'] is True
    assert result[1]['coordinate_unique_vs_external'] is False


def test_designs_never_dominate_each_other():
    result = pareto_rows([row('B3', 'a', 1, 1, 1), row('P0', 'b', 10, 10, 10, design='s9234')])
    assert all(r['implemented_nondominated'] for r in result)


def test_no_outcome_tolerance_hides_a_strict_improvement():
    result = pareto_rows([row('B3', 'a', 1, 1, 1), row('P0', 'b', 1, 1, 1 + 1e-12)])
    assert result[1]['implemented_nondominated'] is False


@pytest.mark.parametrize('missing', (None, '', 'not measured', float('nan'), float('inf'), -1, False))
def test_missing_or_invalid_measurement_is_unknown_and_never_zero(missing):
    unknown = row('B3', 'a', 1, missing, 1)
    assert implemented_point(unknown) is None
    result = pareto_rows([unknown, row('P0', 'b', 10, 10, 10)])
    assert result[0]['implemented_nondominated'] is None
    assert result[0]['pareto_status'] == 'UNASSESSABLE'
    assert result[1]['implemented_nondominated'] is True


def test_physical_failure_cannot_enter_implemented_front():
    failed = row('B3', 'a', 1, 1, 1, status='POSTROUTE_FAILED')
    assert implemented_point(failed) is None
    assert pareto_rows([failed])[0]['implemented_nondominated'] is None
