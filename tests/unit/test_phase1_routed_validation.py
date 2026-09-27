"""Scientific selection invariants: provenance multiplicity cannot bias roles."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('phase1', Path(__file__).resolve().parents[2] / 'scripts/phase1_routed_validation.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def row(sha, x, y):
    return {'architecture_sha256': sha, 'objectives': [x, y], 'source_runs': ['run']}

def test_frontier_roles_are_duplicate_and_order_invariant():
    rows = [row('physical', 1, 10), row('balanced', 4, 4), row('activity', 10, 1), row('dominated', 5, 5)]
    archive, selected = module.select(rows)
    archive2, selected2 = module.select(list(reversed(rows)) + [rows[1]])
    assert {r['architecture_sha256'] for r in archive} == {'physical', 'balanced', 'activity'}
    roles = lambda values: {r['architecture_sha256']: r['selection_roles'] for r in values}
    assert roles(selected) == roles(selected2) == {
        'physical': ['physical_extreme'], 'balanced': ['balanced'], 'activity': ['activity_extreme']}

def test_overlapping_roles_do_not_invent_replacement_routes():
    _, selected = module.select([row('winner', 1, 1), row('worse', 2, 2)])
    assert len(selected) == 1
    assert selected[0]['selection_roles'] == ['physical_extreme', 'balanced', 'activity_extreme']
