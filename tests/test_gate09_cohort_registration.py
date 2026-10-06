import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pact_gate09_cohort_reference_registered as launch
import pact_gate09_cohort_resume as resume
import pytest


def test_new_design_can_use_qualified_dependency_without_prior_failure_and_existing_evidence_stays_bound(tmp_path, monkeypatch):
    base, meta = tmp_path / 'original', tmp_path / 'new'
    monkeypatch.setattr(launch.frozen, 'BASE_META', base)
    monkeypatch.setattr(launch.frozen, 'META', meta)
    source_dir = tmp_path / 'source'
    source_dir.mkdir()
    (source_dir / 'adapter.json').write_text('{}')
    certificate = tmp_path / 'repair.json'
    certificate.write_text('{}')
    source = dict(topology=dict(FF_count=449), mapped_netlist=dict(path=str(source_dir / 'mapped.v'),sha256='fixed'))
    protocol = dict(cohort=[dict(design='new_design')],fixed_method=dict(reference_rule='frozen'),cohort_order=['new_design'])
    register = launch.registration_adapter()
    register('new_design', source, protocol, certificate)
    first = json.loads((meta / 'manifests/new_design_reference_preparation.json').read_text())
    assert first['original_failed_preparation'] is None
    assert first['designs'][0]['source_file'] == source['mapped_netlist']
    assert first['dependency_repair']['path'] == str(certificate)
    monkeypatch.setattr(launch.frozen, 'META', tmp_path / 'existing')
    prior = base / 'physical/new_design/preparation.json'
    prior.parent.mkdir(parents=True)
    prior.write_text('{}')
    launch.registration_adapter()('new_design', source, protocol, certificate)
    second = json.loads((tmp_path / 'existing/manifests/new_design_reference_preparation.json').read_text())
    assert second['original_failed_preparation']['path'] == str(prior)
    assert second['designs'] == first['designs']


def test_capacity_resume_reuses_only_identical_backend_and_unchanged_preparation(tmp_path,monkeypatch):
    source_file=tmp_path / 'mapped.v'
    source_file.write_text('fixed mapped source')
    source_binding=resume.admission.binding(source_file)
    source_path=tmp_path / 'source.json'
    source_path.write_text(json.dumps(dict(mapped_netlist=source_binding)))
    meta=tmp_path / 'meta'
    prep_path=meta / 'physical/b15_opt/preparation.json'
    prep_path.parent.mkdir(parents=True)
    prep=dict(status='PLACEMENT_READY_PENDING_REFERENCES',source=source_binding)
    for key in ('patterns','placed_def','placed_netlist','source_placed_database','SDC','config'):
        artifact=tmp_path / key
        artifact.write_text('fixed '+key)
        prep[key]=resume.admission.binding(artifact)
    prep_path.write_text(json.dumps(prep))
    backend=dict(path='qualified fan',sha256='same backend',bytes=1)
    repair=dict(binary=backend,combined_SHA='same repair')
    monkeypatch.setattr(resume.references,'qualified_dependency',lambda _:repair)
    worker=dict(status=prep['status'],source_admission=resume.admission.binding(source_path),
        common_FAN_backend=backend,qualified_repair_source_SHA='same repair',receipt=resume.admission.binding(prep_path))
    worker_path=meta / 'workers/b15_opt/prepare.json'
    worker_path.parent.mkdir(parents=True)
    worker_path.write_text(json.dumps(worker))
    assert resume.require_same_preparation(meta,source_path,Path('certificate'))['sha256']==worker['receipt']['sha256']
    repair['combined_SHA']='different generation backend'
    with pytest.raises(ValueError,match='differs'):
        resume.require_same_preparation(meta,source_path,Path('certificate'))
    repair['combined_SHA']='same repair'
    (tmp_path / 'patterns').write_text('changed workload')
    with pytest.raises(ValueError,match='artifact changed'):
        resume.require_same_preparation(meta,source_path,Path('certificate'))
