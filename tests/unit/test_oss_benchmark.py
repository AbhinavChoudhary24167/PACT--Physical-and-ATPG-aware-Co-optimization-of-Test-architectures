"""Scientific protocol checks for selection and identity-preserving translation."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from pact_oss_canonicalize import select, validate_architecture
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def archive():
    return [dict(architecture_sha256=name, metrics=dict(wire_um=w, E_stateful_ff=e, H8_stateful_ff=h))
            for name, w, e, h in [('a', 1., 3., 3.), ('b', 2., 2., 2.), ('c', 3., 1., 1.)]]


def reference():
    cells = tuple(ScanCell(n, i, i, 'CK') for i, n in enumerate('abcd'))
    return ScanArchitecture(cells, (ScanChain('C00', ('a', 'b'), 'test_si_0', 'test_so_0'),
                                    ScanChain('C01', ('c', 'd'), 'test_si_1', 'test_so_1')))


def test_prediction_extremes_and_balanced_representative():
    assert select(archive()) == {'a': ['physical_extreme'], 'c': ['H8_extreme'], 'b': ['balanced']}


def test_selection_ignores_measurements_and_archive_iteration_order():
    rows = archive()
    for i, row in enumerate(rows):
        row['measured_H8'] = 1e9 * (i + 1)
        row['selected_roles'] = ['historically_routed']
    assert select(rows[::-1]) == select(archive())


def test_balanced_selection_is_invariant_to_units():
    rows = archive()
    for row in rows:
        row['metrics']['E_stateful_ff'] *= 1e6
        row['metrics']['H8_stateful_ff'] *= .001
    assert select(rows) == select(archive())


def test_ties_deduplicate_and_use_canonical_hash():
    rows = archive()
    rows[1]['metrics'] = rows[0]['metrics'].copy()
    assert select(rows)['a'] == ['physical_extreme', 'balanced']
    assert 'b' not in select(rows)


def test_legal_order_change_preserves_frozen_population_and_capacity():
    old = reference()
    new = ScanArchitecture(old.cells, (ScanChain('C00', ('c', 'a'), 'test_si_0', 'test_so_0'),
                                       ScanChain('C01', ('d', 'b'), 'test_si_1', 'test_so_1')))
    validate_architecture(new, old)
    assert new.sha256() != old.sha256()


@pytest.mark.parametrize('failure', ('placement', 'K', 'capacity', 'endpoints', 'duplicate'))
def test_reject_confounding_changes(failure):
    old = reference()
    cells, chains = old.cells, old.chains
    if failure == 'placement':
        cells = (ScanCell('a', 99., 99., 'CK'), *old.cells[1:])
    elif failure == 'K':
        chains = (ScanChain('C00', tuple('abcd'), 'test_si_0', 'test_so_0'),)
    elif failure == 'capacity':
        chains = (ScanChain('C00', tuple('abc'), 'test_si_0', 'test_so_0'), ScanChain('C01', ('d',), 'test_si_1', 'test_so_1'))
    elif failure == 'endpoints':
        chains = (ScanChain('C00', ('a', 'b'), 'different_si', 'test_so_0'), old.chains[1])
    else:
        chains = (ScanChain('C00', ('a', 'a'), 'test_si_0', 'test_so_0'), old.chains[1])
    with pytest.raises(ValueError):
        validate_architecture(ScanArchitecture(cells, chains), old)
