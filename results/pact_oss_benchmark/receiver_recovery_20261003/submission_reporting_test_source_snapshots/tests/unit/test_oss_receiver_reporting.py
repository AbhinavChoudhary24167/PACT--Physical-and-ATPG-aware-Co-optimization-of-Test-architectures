"""Reports retain the repaired identity, full build cost and native test scope."""
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
import pact_oss_receiver_complete as report


def write(path, value):
    path.write_text(json.dumps(value))


def test_all_table_method_fields_show_the_full_repaired_label():
    table=report.markdown_table(['method','baseline','left','right'],[
        dict(method='B3R',baseline='B3R',left='B3R',right='B2')])
    assert table.count(report.B3R_DISPLAY)==3
    assert '| B2 |' in table


def test_full_validation_compile_and_incremental_final_build_are_separate(tmp_path):
    for label,time in (('narrow_receiver_target',1),('build_repair_validation',1200),('build_final',3)):
        write(tmp_path/(label+'.execution.json'),dict(elapsed_seconds=time,returncode=0))
    entries=report.compilation_runtime('B3R',dict(build=dict(path=str(tmp_path/'build_final.execution.json'))))
    assert [e['stage'] for e in entries]==[
        'receiver_repair_narrow_target','receiver_repair_full_build_validation','final_immutable_commit_incremental_build']
    assert [e['elapsed_seconds'] for e in entries]==[1,1200,3]
    assert all(e['reused'] is False for e in entries)


def test_exact_B2_build_runtime_remains_historical_reuse(tmp_path):
    path=tmp_path/'build_resume1.execution.json'
    write(path,dict(elapsed_seconds=5213,returncode=0))
    entries=report.compilation_runtime('B2',dict(build=dict(path=str(path))))
    assert len(entries)==1 and entries[0]['reused'] is True
    assert entries[0]['stage']=='historical_exact_compilation'


@pytest.fixture
def native(tmp_path):
    tests={}
    for name in ('scan_opt_sky130','place_sort_sky130','one_cell_sky130'):
        execution=tmp_path/(name+'.execution.json')
        write(execution,dict(returncode=0,command=['openroad','-exit',name+'.tcl']))
        tests[name]=dict(status='PASS',execution=report.binding(execution),raw_output='PASS')
    receipt=tmp_path/'tests.json'
    binary=tmp_path/'preserved_precommit_binary'
    binary.write_bytes(b'validated native regression executable')
    value=dict(status='PASS',relevant_existing_integration_tests=3,new_upstream_tests=0,tests_after=tests,
        binary_before_immutable_commit=report.binding(binary))
    write(receipt,value)
    return receipt,value


def test_native_regressions_have_separate_count_and_precommit_binary_scope(native):
    result=report.native_test_accounting(native[0])
    assert result['existing_native_tests_passed']==3 and result['new_upstream_tests']==0
    assert result['binary_at_test_execution']['sha256']==native[1]['binary_before_immutable_commit']['sha256']
    assert 'before the DCO-signed immutable commit' in result['scope']


def test_native_failure_cannot_be_reported_as_three_passes(native):
    native[1]['tests_after']['scan_opt_sky130']['status']='FAILED'
    write(native[0],native[1])
    with pytest.raises(ValueError,match='regression failed'):
        report.native_test_accounting(native[0])


def test_native_count_requires_all_three_expected_tests(native):
    del native[1]['tests_after']['one_cell_sky130']
    write(native[0],native[1])
    with pytest.raises(ValueError,match='three native DFT'):
        report.native_test_accounting(native[0])


def test_native_test_execution_receipt_is_hash_verified(native):
    execution=Path(native[1]['tests_after']['scan_opt_sky130']['execution']['path'])
    write(execution,dict(returncode=1))
    with pytest.raises(ValueError,match='Evidence changed'):
        report.native_test_accounting(native[0])


def test_missing_upstream_receipt_cannot_claim_an_opened_PR(tmp_path):
    result=report.contribution_accounting(tmp_path/'not_submitted.json')
    assert result['status']=='PENDING_NOT_CLAIMED_SUBMITTED'
    assert result['PR_opened'] is False and result['PR_URL'] is None
    assert result['receipt'] is None
    assert result['related_original_PR'].endswith('/pull/10666')


def test_upstream_submission_fields_and_receipt_are_reported_without_waiting(tmp_path):
    path=tmp_path/'github_contribution.json'
    value=dict(status='OPENED',PR_URL='https://github.com/mwsoli/OpenROAD/pull/1',PR_number=1,
        target_repository='mwsoli/OpenROAD',target_branch='dft/scan-chain-optimizer',
        related_original_PR=dict(url='https://github.com/The-OpenROAD-Project/OpenROAD/pull/10666'),
        CI_status='PENDING',capture_time_utc='2026-10-03T16:00:00Z')
    write(path,value)
    result=report.contribution_accounting(path)
    assert result['status']=='OPENED' and result['PR_opened'] is True
    assert result['PR_URL']==value['PR_URL'] and result['target_repository']==value['target_repository']
    assert result['target_branch']==value['target_branch'] and result['CI_status_at_capture']=='PENDING'
    assert result['related_original_PR']==value['related_original_PR']['url']
    assert result['receipt']==report.binding(path)


@pytest.fixture
def eligibility(tmp_path,monkeypatch):
    import pact_oss_receiver_reuse_preflight as preflight
    root=tmp_path/'recovery'
    path=root/'reuse_preflight/eligibility.json'
    path.parent.mkdir(parents=True)
    common=dict(design='s5378',architecture_sha256='a'*64,observed_threads=[2],
        explicit_NUM_CORES_2=True,reasons=[])
    value=dict(status='PASS',meaning='Eligibility audit completed; excluded caches stay excluded',
        route_candidates={'eligible':dict(common,eligible=True),
            'excluded':dict(common,eligible=False,observed_threads=[4],explicit_NUM_CORES_2=False,
                reasons=['THREAD_COUNT_NOT_FROZEN_2'])},
        eligible_route_candidates=1,excluded_route_candidates=1,historical_binding_checks=2,
        expected_bindings={'one':{},'two':{}},environment={'ORFS_tracked_diff':'CLEAN'},
        cache_exclusions_preserved=True)
    write(path,value)
    monkeypatch.setattr(report,'RECOVERY',root)
    monkeypatch.setattr(preflight,'require_preflight',lambda:value)
    return path,value


def test_reuse_report_derives_actual_counts_and_preserves_exclusion_policy(eligibility):
    result=report.reuse_accounting()
    assert result['historical_binding_checks']==2
    assert result['eligible_route_candidates']==1 and result['excluded_route_candidates']==1
    assert result['excluded_routes'][0]['observed_threads']==[4]
    assert result['excluded_routes'][0]['explicit_NUM_CORES_2'] is False
    assert result['cache_exclusions_preserved'] is True
    assert 'NUM_CORES=2' in result['missing_or_ineligible_selected_cache']
    assert result['receipt']==report.binding(eligibility[0])


def test_reuse_report_rejects_receipt_counts_inconsistent_with_candidates(eligibility):
    eligibility[1]['eligible_route_candidates']=2
    with pytest.raises(ValueError,match='Cache eligibility accounting differs'):
        report.reuse_accounting()
