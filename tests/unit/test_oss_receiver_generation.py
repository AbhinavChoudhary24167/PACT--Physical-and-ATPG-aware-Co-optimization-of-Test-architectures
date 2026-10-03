"""Generation must execute the immutable repaired binary with honest identity."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
from pact_oss_receiver_generate import (
    BASELINES, DISPLAY, REPAIRED_FILE, validate_build_identity, validate_runtime_identity,
)


@pytest.fixture
def evidence():
    commit = 'a'*40
    base = BASELINES['B3R']['upstream_base_sha']
    patch = 'b'*64
    binary = 'c'*64
    build = dict(status='BUILT',commit=commit,upstream_base_sha=base,
        binary=dict(path='independent/B3R/build/bin/openroad',sha256=binary),binary_sha256=binary)
    repair = dict(upstream_base_sha=base,repair_commit_sha=commit,patch_sha256=patch,changed_files=[REPAIRED_FILE])
    source = dict(upstream_base_sha=base,repair_commit_sha=commit,patch_sha256=patch)
    runtime = dict(status='PASS',method='B3R',method_display=DISPLAY,source_commit=commit,
        upstream_base_sha=base,repair_patch_sha256=patch,binary_sha256=binary)
    return build,repair,source,runtime


def test_final_build_and_runtime_proofs_agree(evidence):
    build,repair,source,runtime=evidence
    assert validate_build_identity(build,repair,source)==repair['repair_commit_sha']
    validate_runtime_identity(runtime,build,repair)


@pytest.mark.parametrize('status',('CONFIGURED','COMPILATION_FAILED','PROVISIONAL'))
def test_unfinished_build_cannot_start_architecture_generation(evidence,status):
    build,repair,source,_=evidence
    build['status']=status
    with pytest.raises(ValueError,match='immutable final B3R build result'):
        validate_build_identity(build,repair,source)


def test_uncommitted_validation_version_cannot_generate(evidence):
    build,repair,source,_=evidence
    repair['repair_commit_sha']='746c-B3R-uncommitted'
    with pytest.raises(ValueError,match='immutable repair commit'):
        validate_build_identity(build,repair,source)


def test_exact_original_B3_is_not_presented_as_repaired(evidence):
    build,repair,source,_=evidence
    repair['repair_commit_sha']=repair['upstream_base_sha']
    with pytest.raises(ValueError,match='cannot be labeled as exact B3'):
        validate_build_identity(build,repair,source)


def test_source_patch_must_match_repair_patch(evidence):
    build,repair,source,_=evidence
    source['patch_sha256']='f'*64
    with pytest.raises(ValueError,match='exact receiver patch'):
        validate_build_identity(build,repair,source)


@pytest.mark.parametrize('key,value',(
    ('status','FAILED'),('method','B3'),('source_commit','d'*40),
    ('binary_sha256','e'*64),('repair_patch_sha256','f'*64),('upstream_base_sha','0'*40),
))
def test_actual_runtime_identity_cannot_disagree_with_build(evidence,key,value):
    build,repair,_,runtime=evidence
    runtime[key]=value
    with pytest.raises(ValueError,match='runtime identity differs: '+key):
        validate_runtime_identity(runtime,build,repair)
