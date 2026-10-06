import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pact_gate09_route_recovery as recovery


def test_recovery_cannot_overwrite_prior_namespace():
    with pytest.raises(ValueError, match='preserve the original namespace'):
        recovery.run(SimpleNamespace(attempt='prior', prior_attempt='prior'))


def test_retained_atpg_cannot_be_reused_with_a_different_qualified_backend(tmp_path):
    source = dict(design='b14_opt', mapped_netlist=dict(path='mapped.v', sha256='same'))
    preparation = dict(design='b14_opt', source=source['mapped_netlist'],
        status='PLACEMENT_READY_PENDING_REFERENCES', gates=dict(ATPG='PASS', placement='PASS'))
    worker = dict(status='PLACEMENT_READY_PENDING_REFERENCES',
                  common_FAN_backend=dict(path='old_fan', sha256='old'))
    old, completed = tmp_path / 'preparation.json', tmp_path / 'worker.json'
    old.write_text(json.dumps(preparation))
    completed.write_text(json.dumps(worker))
    with pytest.raises(ValueError, match='identical admitted source and qualified backend'):
        recovery.retain_preparation(old, source, dict(binary=dict(path='new_fan', sha256='new')), completed)
