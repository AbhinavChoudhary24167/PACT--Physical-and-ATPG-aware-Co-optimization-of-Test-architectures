"""A killed or incomplete lane must retain evidence without becoming completed."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.fixture
def receipts(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'scripts'))
    return importlib.import_module('pact_experiment_receipts')


def test_receipt_replace_and_exclusive_creation_preserve_evidence(tmp_path,receipts):
    target=tmp_path/'receipt.json'
    receipts.atomic_write(target,dict(state='REGISTERED'),immutable=True)
    with pytest.raises(FileExistsError):
        # Atomic publication cannot overwrite an existing immutable receipt.
        temporary=tmp_path/'source'
        temporary.write_text('{}')
        os.link(temporary,target)
    with pytest.raises(ValueError,match='Immutable'):
        receipts.atomic_write(target,dict(state='COMPLETED'),immutable=True)
    assert json.loads(target.read_text())==dict(state='REGISTERED')
    receipts.atomic_write(target,dict(state='STARTED'))
    assert json.loads(target.read_text())==dict(state='STARTED')
    assert not list(tmp_path.glob('*.tmp'))


def test_partial_lane_and_signal_exit_cannot_be_reported_as_complete(tmp_path,receipts):
    lifecycle=receipts.LaneReceipts(tmp_path,dict(configuration_hash='frozen',input_hashes={'reference':'cold'}))
    lifecycle.transition(.02,'REGISTERED')
    lifecycle.transition(.02,'STARTED')
    lifecycle.transition(.02,'CHECKPOINTED',last_checkpoint={'evaluations':97})
    with pytest.raises(ValueError,match='Completion requires'):
        lifecycle.transition(.02,'COMPLETED')
    lifecycle.interrupt_active('signal_9_cause_not_established',-9)
    row=json.loads((tmp_path/'budget_0.02/lifecycle.json').read_text())
    assert row['state']=='FAILED' and row['exit_code']==-9
    assert row['last_checkpoint']=={'evaluations':97}
    assert row['configuration_hash']=='frozen' and row['input_hashes']=={'reference':'cold'}
    assert 'OOM' not in row['completion_reason']
    assert len(list((tmp_path/'budget_0.02/events').glob('*.json')))==4
    with pytest.raises(ValueError,match='Terminal'):
        lifecycle.transition(.02,'COMPLETED',completion_receipt={'sha256':'x'})


def test_measured_timeout_preserves_checkpoint_and_not_started_lanes(tmp_path,receipts):
    lifecycle=receipts.LaneReceipts(tmp_path,{})
    for epsilon in (.02,.05,.10):lifecycle.transition(epsilon,'REGISTERED')
    lifecycle.transition(.02,'STARTED')
    lifecycle.transition(.02,'CHECKPOINTED',last_checkpoint={'sha256':'preserved'})
    lifecycle.interrupt_active('worker_ceiling_timeout',-15,timed_out=True)
    row=json.loads((tmp_path/'budget_0.02/lifecycle.json').read_text())
    assert row['state']=='INTERRUPTED' and row['timed_out']
    assert row['last_checkpoint']=={'sha256':'preserved'}
    assert json.loads((tmp_path/'budget_0.05/lifecycle.json').read_text())['state']=='REGISTERED'


def test_completed_lane_survives_a_later_worker_failure(tmp_path,receipts):
    lifecycle=receipts.LaneReceipts(tmp_path,{})
    lifecycle.transition(.02,'REGISTERED')
    lifecycle.transition(.02,'STARTED')
    completed=lifecycle.transition(.02,'COMPLETED',completion_receipt={'sha256':'complete'},exit_code=0)
    lifecycle.interrupt_active('subsequent_failure',1)
    assert json.loads((tmp_path/'budget_0.02/lifecycle.json').read_text())==completed
