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
    value=dict(status='PASS',relevant_existing_integration_tests=3,new_upstream_tests=0,tests_after=tests,
        binary_before_immutable_commit=dict(path='historical-validation-binary',sha256='a'*64))
    write(receipt,value)
    return receipt,value


def test_native_regressions_have_separate_count_and_precommit_binary_scope(native):
    result=report.native_test_accounting(native[0])
    assert result['existing_native_tests_passed']==3 and result['new_upstream_tests']==0
    assert result['binary_at_test_execution']['sha256']=='a'*64
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
