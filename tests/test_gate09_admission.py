"""Gate-09 admission rejects relaxed storage floors and corrupt frozen bytes."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('gate09_admission', Path(__file__).parents[1] / 'scripts/pact_gate09_admission.py')
admission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admission)


def test_fixed_capacity_and_exact_boundary():
    policy = dict(D_minimum_floor_bytes=admission.MINIMUM_D, C_minimum_free_bytes=admission.MINIMUM_C)
    observed = dict(C=dict(free=admission.MINIMUM_C), D=dict(free=admission.MINIMUM_D - 1))
    assert admission.capacity(policy, observed)['status'] == 'PACT_GATE09_BLOCKED_CAPACITY'
    observed['D']['free'] += 1
    assert admission.capacity(policy, observed)['status'] == 'PASS'
    with pytest.raises(ValueError, match='cannot be reduced'):
        admission.capacity(dict(policy, D_minimum_floor_bytes=20 * 1024**3), observed)
    assert admission.capacity(policy, {})['status'] == 'PACT_GATE09_BLOCKED_CAPACITY'


def test_frozen_file_mismatch_and_missing_evidence(tmp_path):
    path = tmp_path / 'frozen.bin'
    path.write_bytes(b'scientific input')
    original = admission.binding(path)
    assert admission.verify(original)['status'] == 'PASS'
    path.write_bytes(b'scientific inpuT')
    assert admission.verify(original)['status'] == 'HASH_MISMATCH'
    path.unlink()
    assert admission.verify(original)['status'] == 'UNAVAILABLE'


def test_receipt_overwrite_is_rejected_before_any_audit(tmp_path):
    with pytest.raises(ValueError, match='Fresh audit directory'):
        admission.audit(tmp_path)
