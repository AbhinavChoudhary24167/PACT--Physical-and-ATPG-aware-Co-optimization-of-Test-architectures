"""The route adapter must honor eligibility without hiding integrity failures."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
import pact_oss_receiver_stage_a as stage


@pytest.fixture
def cache(tmp_path,monkeypatch):
    folder=tmp_path/'results/pact_candidate_stateful/routes/s5378/arch'
    folder.mkdir(parents=True)
    archive=folder/'5_2_route.odb.gz'
    archive.write_bytes(b'previous immutable routed archive')
    report=folder/'route_result.json'
    report.write_text(json.dumps(dict(status='QUALIFIED',architecture_sha256='arch',
        routed_odb_gzip_sha256=stage.binding(archive)['sha256'])))
    monkeypatch.setattr(stage,'ROOT',tmp_path)
    return report


def test_eligible_route_cache_is_reused_after_the_seal_guard(cache,monkeypatch):
    calls=[]
    def eligible(path):
        calls.append(path)
        return True
    monkeypatch.setitem(sys.modules,'pact_oss_receiver_reuse_preflight',SimpleNamespace(cached_route_eligible=eligible))
    result=stage.old_route('s5378','arch')
    assert result['reused'] is True and calls==[cache]


def test_ineligible_threading_cache_is_skipped_for_fresh_common_routing(cache,monkeypatch):
    monkeypatch.setitem(sys.modules,'pact_oss_receiver_reuse_preflight',SimpleNamespace(cached_route_eligible=lambda path:False))
    assert stage.old_route('s5378','arch') is None


def test_changed_sealed_route_evidence_hard_fails_instead_of_being_skipped(cache,monkeypatch):
    def changed(path):
        raise ValueError('historically sealed route changed')
    monkeypatch.setitem(sys.modules,'pact_oss_receiver_reuse_preflight',SimpleNamespace(cached_route_eligible=changed))
    with pytest.raises(ValueError,match='sealed route changed'):
        stage.old_route('s5378','arch')
