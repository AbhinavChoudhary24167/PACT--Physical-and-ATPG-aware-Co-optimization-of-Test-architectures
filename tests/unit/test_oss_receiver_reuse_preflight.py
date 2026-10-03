"""Cached scientific outcomes require immutable provenance and frozen settings."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_oss_receiver_reuse_preflight as preflight


def route():
    report = dict(status='QUALIFIED', DRC_errors=0)
    execution = dict(exit_code=0, timed_out=False,
        command=['make', 'GRT_SEED=11', 'NUM_CORES=2', 'OPENROAD_EXE=/usr/bin/openroad'])
    return report, execution, 'OpenROAD frozen\n[INFO ORD-0030] Using 2 thread(s).\n', 'frozen'


def test_recorded_frozen_route_can_be_reused():
    assert preflight.route_policy(*route())['eligible'] is True


def test_historical_four_thread_route_is_excluded_without_grandfathering():
    report, execution, stdout, version = route()
    execution['command'].remove('NUM_CORES=2')
    result = preflight.route_policy(report, execution, stdout.replace('2 thread', '4 thread'), version)
    assert result['eligible'] is False
    assert result['observed_threads'] == [4]
    assert 'THREAD_COUNT_NOT_FROZEN_2' in result['reasons']


def test_absent_num_cores_cannot_be_inferred_from_log_only():
    args = route()
    args[1]['command'].remove('NUM_CORES=2')
    assert preflight.route_policy(*args)['eligible'] is False


@pytest.mark.parametrize('setting', ('GRT_SEED=11', 'OPENROAD_EXE=/usr/bin/openroad'))
def test_missing_seed_or_fixed_backend_prevents_reuse(setting):
    args = route()
    args[1]['command'].remove(setting)
    assert preflight.route_policy(*args)['eligible'] is False


def test_inconsistent_logged_thread_count_prevents_reuse():
    report, execution, stdout, version = route()
    assert preflight.route_policy(report, execution, stdout.replace('2 thread', '4 thread'), version)['eligible'] is False


def test_different_historical_backend_version_prevents_reuse():
    report, execution, stdout, _ = route()
    assert preflight.route_policy(report, execution, stdout, 'different')['eligible'] is False


def test_sealed_parent_hash_disagreement_is_a_hard_failure(tmp_path):
    catalog = {}
    preflight.add_expected(catalog, tmp_path / 'file', 'a'*64, 'parent1')
    with pytest.raises(ValueError, match='seals disagree'):
        preflight.add_expected(catalog, tmp_path / 'file', 'b'*64, 'parent2')


def fixture(tmp_path, monkeypatch, eligible):
    files = {}
    for name in ('report', 'execution', 'stdout', 'archive'):
        path = tmp_path / name
        path.write_text(name)
        files[name] = preflight.binding(path)
    candidate = dict(files, eligible=eligible)
    receipt = dict(route_candidates={preflight.key(tmp_path / 'report'): candidate},
        expected_bindings={preflight.key(item['path']): item for item in files.values()})
    monkeypatch.setattr(preflight, 'require_preflight', lambda: receipt)
    return receipt, files


def test_recorded_ineligible_cache_is_skipped_without_changing_it(tmp_path, monkeypatch):
    _, files = fixture(tmp_path, monkeypatch, False)
    assert preflight.cached_route_eligible(files['report']['path']) is False
    assert Path(files['report']['path']).read_text() == 'report'


def test_changed_ineligible_cache_still_hard_fails_integrity(tmp_path, monkeypatch):
    _, files = fixture(tmp_path, monkeypatch, False)
    Path(files['report']['path']).write_text('changed')
    with pytest.raises(ValueError, match='sealed artifact changed'):
        preflight.cached_route_eligible(files['report']['path'])


def test_uncatalogued_cache_cannot_be_reused(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, True)
    with pytest.raises(ValueError, match='outside the eligibility catalog'):
        preflight.cached_route_eligible(tmp_path / 'unknown')


def test_changed_measurement_summary_cannot_be_rebound_as_historical(tmp_path, monkeypatch):
    _, files = fixture(tmp_path, monkeypatch, True)
    Path(files['stdout']['path']).write_text('changed summary')
    with pytest.raises(ValueError, match='sealed artifact changed'):
        preflight.checked_cached_binding(files['stdout']['path'])
