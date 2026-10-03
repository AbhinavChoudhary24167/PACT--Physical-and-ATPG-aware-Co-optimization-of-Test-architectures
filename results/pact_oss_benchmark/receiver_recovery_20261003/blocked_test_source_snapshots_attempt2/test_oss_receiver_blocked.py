"""Fail closed when a stopped recovery lacks its actual qualification evidence."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
from pact_oss_receiver_seal_blocked import validate_stop_state, validate_saved_observation
from pact_oss_receiver_stage_a import B3R_DISPLAY


@pytest.fixture
def evidence():
    commit, base, patch, binary = 'a'*40, 'b'*40, 'c'*64, 'd'*64
    repair = dict(repair_commit_sha=commit, upstream_base_sha=base, patch_sha256=patch)
    build = dict(commit=commit, binary_sha256=binary)
    qualification = dict(status='FAILED', method='B3R', method_display=B3R_DISPLAY,
        failed_design='s5378', source_commit=commit, upstream_base_sha=base,
        patch_sha256=patch, binary_sha256=binary, completed_designs={})
    diagnosis = dict(status='SOURCE_TOPOLOGY_BLOCKER_STOPPED', method='B3R', method_display=B3R_DISPLAY,
        design='s5378', upstream_base_sha=base, repair_commit_sha=commit, patch_sha256=patch,
        binary_sha256=binary, topology_qualification='FAIL', actual_chain_lengths=[90,89],
        actual_terminal_nets=['n2510gat','n707gat'], fixed_SO_terminates_generated_chains=False,
        FF_functional_placement_unchanged=True, additional_source_patch_applied=False,
        downstream_physical_runs=0)
    compiled = dict(status='PASS', method='B3R', method_display=B3R_DISPLAY,
        source_commit=commit, upstream_base_sha=base, repair_patch_sha256=patch, binary_sha256=binary)
    return qualification, diagnosis, build, repair, compiled


def test_observed_failure_remains_incomplete(evidence):
    result = validate_stop_state(*evidence, {'s5378'}, [])
    assert result == dict(s5378='FAILED_SCAN_OUTPUT_TOPOLOGY',
        s9234='NOT_ATTEMPTED_AFTER_STOP', s15850='NOT_ATTEMPTED_AFTER_STOP')


@pytest.mark.parametrize('change', ('status', 'completed_designs', 'binary_sha256', 'failed_design'))
def test_changed_qualification_cannot_use_stopped_seal(evidence, change):
    qualification = evidence[0]
    qualification[change] = {'status':'PASS', 'completed_designs':{'s5378':{}},
        'binary_sha256':'e'*64, 'failed_design':'s9234'}[change]
    with pytest.raises(ValueError):
        validate_stop_state(*evidence, {'s5378'}, [])


@pytest.mark.parametrize('field,value', (
    ('fixed_SO_terminates_generated_chains',True), ('additional_source_patch_applied',True),
    ('FF_functional_placement_unchanged',False), ('topology_qualification','PASS')))
def test_distinct_diagnosis_cannot_use_this_seal(evidence, field, value):
    evidence[1][field] = value
    with pytest.raises(ValueError):
        validate_stop_state(*evidence, {'s5378'}, [])


def test_physical_execution_cannot_be_hidden(evidence):
    with pytest.raises(ValueError, match='Physical work'):
        validate_stop_state(*evidence, {'s5378'}, ['route.execution.json'])


def test_extra_generation_is_not_silently_ignored(evidence):
    with pytest.raises(ValueError):
        validate_stop_state(*evidence, {'s5378','s9234'}, [])


@pytest.fixture
def observation():
    names = [f'ff_{n}' for n in range(179)]
    result = dict(optimizer_executed=False, connectivity_modified=False,
        FF_inventory_placement_functional_unchanged=True, after=dict(FF_count=179,
        sha256='e'*64, cells=dict.fromkeys(names), traces=[
            dict(chain=0,ff_count=90,ff_order=names[:90],error='CANNOT_TRACE_FIXED_SI_SO',
                 terminal_net=dict(name='n2510gat',ports=[])),
            dict(chain=1,ff_count=89,ff_order=names[90:],error='CANNOT_TRACE_FIXED_SI_SO',
                 terminal_net=dict(name='n707gat',ports=[]))]))
    diagnosis = dict(generated_ODB=dict(sha256='e'*64))
    return result, diagnosis


def test_saved_database_identity_and_complete_inventory(observation):
    validate_saved_observation(*observation)


@pytest.mark.parametrize('change', ('database', 'endpoint', 'duplicate', 'mutation'))
def test_invalid_saved_observation_is_rejected(observation, change):
    record, diagnosis = deepcopy(observation)
    if change == 'database':
        diagnosis['generated_ODB']['sha256'] = 'f'*64
    elif change == 'endpoint':
        record['after']['traces'][0]['terminal_net']['ports'] = ['test_so_0']
    elif change == 'duplicate':
        record['after']['traces'][1]['ff_order'][0] = 'ff_0'
    else:
        record['connectivity_modified'] = True
    with pytest.raises(ValueError):
        validate_saved_observation(record, diagnosis)
