from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pact_gate09_measure as measure


def test_exact_capacity_keeps_floor_and_blocks_trace_dimensions_that_do_not_fit(monkeypatch):
    gib = 1024**3
    protocol = dict(resource_policy=dict(C_minimum_free_bytes=6*gib,
        D_minimum_floor_bytes=25*gib, D_existing_scratch_requirement_bytes=20*gib))
    monkeypatch.setattr(measure.shutil, 'disk_usage', lambda path: (100*gib, 74*gib, 26*gib))
    small = measure.capacity(protocol, dict(nets=100, cycles=100))
    assert small['status'] == 'PASS'
    assert small['volumes']['D']['minimum_free_bytes'] >= 25*gib
    with pytest.raises(RuntimeError, match='PACT_GATE09_BLOCKED_CAPACITY'):
        measure.capacity(protocol, dict(nets=50000, cycles=50000))


def test_exact_capacity_cannot_relax_registered_floor(monkeypatch):
    gib = 1024**3
    protocol = dict(resource_policy=dict(C_minimum_free_bytes=6*gib,
        D_minimum_floor_bytes=24*gib, D_existing_scratch_requirement_bytes=20*gib))
    monkeypatch.setattr(measure.shutil, 'disk_usage', lambda path: (100*gib, 0, 100*gib))
    with pytest.raises(ValueError, match='cannot be reduced'):
        measure.capacity(protocol)
