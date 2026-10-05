"""A recorded scientific stop cannot be bypassed by a new timeout regime."""
import importlib.util
from pathlib import Path
import pytest


def test_scientific_stop_blocks_continuation_before_other_checks(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('cpu_gates_test',scripts/'pact_cpu_gates.py')
    gates = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gates)
    monkeypatch.setattr(gates,'OUT',tmp_path)
    (tmp_path/'scientific_stop.json').write_text('{"status":"STOPPED"}')
    with pytest.raises(ValueError,match='scientific stop'):
        gates.require_continuation_allowed()
