import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pact_gate09_cohort_reference_registered as launch


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
