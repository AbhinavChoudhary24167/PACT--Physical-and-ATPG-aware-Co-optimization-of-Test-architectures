"""The repaired-method adapters preserve provenance, selection and unknowns."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'scripts'), str(REPO / 'src')]
import pact_oss_receiver_stage_a as stage
import pact_oss_receiver_complete as complete
from pact_oss_receiver_scientific import analyze
from pact_oss_receiver_results import metric_row
from pact_oss_compare import implemented_point
import pact_oss_receiver_measure as measure
from types import SimpleNamespace


ORIGINAL = b'''unrelated_prefix\nreturn iTermLocation(findITerm(getLibertyScanIn(test_cell_)), inst_);\nreturn iTermLocation(findITerm(getLibertyScanOut(test_cell_)), inst_);\nunrelated_suffix\n'''


def digest(content):
    return hashlib.sha256(content).hexdigest()


@pytest.fixture
def repair(tmp_path):
    source = tmp_path / 'source'
    target = source / stage.REPAIRED_FILE
    target.parent.mkdir(parents=True)
    target.write_bytes(stage.receiver_correction(ORIGINAL))
    optimizer = source / 'src/dft/src/optimizer/Opt.cpp'
    optimizer.parent.mkdir(parents=True)
    optimizer.write_bytes(b'unchanged optimizer\n')
    original = tmp_path / 'original.cpp'
    original.write_bytes(ORIGINAL)
    patch = tmp_path / 'patch.diff'
    patch.write_bytes(b'only receiver qualifications\n')
    hashes = {stage.REPAIRED_FILE: digest(ORIGINAL), 'src/dft/src/optimizer/Opt.cpp': digest(optimizer.read_bytes())}
    manifest = dict(upstream_base_sha=stage.BASELINES['B3R']['upstream_base_sha'], repair_commit_sha='a'*40,
        patch_sha256=digest(patch.read_bytes()), patch=stage.binding(patch), changed_files=[stage.REPAIRED_FILE],
        changed_source_sha256={stage.REPAIRED_FILE:digest(target.read_bytes())})
    return source, manifest, hashes, original


def test_receiver_correction_only_qualifies_the_two_calls():
    expected = ORIGINAL.replace(b'findITerm(getLibertyScan', b'findITerm(db_network_->getLibertyScan')
    assert stage.receiver_correction(ORIGINAL) == expected


@pytest.mark.parametrize('member', ('getLibertyScanIn', 'getLibertyScanOut'))
def test_missing_diagnosed_call_cannot_be_repaired_blindly(member):
    with pytest.raises(ValueError, match='does not match source'):
        stage.receiver_correction(ORIGINAL.replace(member.encode(), b'unrelatedMember'))


def test_authorized_repair_and_unchanged_optimizer_pass(repair):
    stage.validate_repair(*repair)


def test_only_the_two_repaired_statements_may_use_clang_format_wrapping(repair):
    formatted=stage.receiver_correction(ORIGINAL,formatted=True)
    assert formatted.count(b'\n                       inst_);')==2
    (repair[0]/stage.REPAIRED_FILE).write_bytes(formatted)
    repair[1]['changed_source_sha256'][stage.REPAIRED_FILE]=digest(formatted)
    stage.validate_repair(*repair)


def test_other_formatting_is_not_authorized_by_targeted_statement_wrapping(repair):
    formatted=stage.receiver_correction(ORIGINAL,formatted=True).replace(b'unrelated_prefix',b'  unrelated_prefix')
    (repair[0]/stage.REPAIRED_FILE).write_bytes(formatted)
    repair[1]['changed_source_sha256'][stage.REPAIRED_FILE]=digest(formatted)
    with pytest.raises(ValueError,match='exact two receiver'):
        stage.validate_repair(*repair)


def test_wrong_upstream_parent_is_rejected(repair):
    repair[1]['upstream_base_sha']='b'*40
    with pytest.raises(ValueError, match='parent differs'):
        stage.validate_repair(*repair)


def test_repair_identity_must_differ_from_exact_base(repair):
    repair[1]['repair_commit_sha']=repair[1]['upstream_base_sha']
    with pytest.raises(ValueError, match='own immutable commit'):
        stage.validate_repair(*repair)


def test_additional_changed_file_is_rejected(repair):
    repair[1]['changed_files'].append('src/dft/src/optimizer/Opt.cpp')
    with pytest.raises(ValueError, match='unauthorized changed file'):
        stage.validate_repair(*repair)


def test_extra_source_cleanup_is_rejected(repair):
    target=repair[0]/stage.REPAIRED_FILE
    target.write_bytes(target.read_bytes()+b'// cleanup\n')
    with pytest.raises(ValueError, match='exact two receiver'):
        stage.validate_repair(*repair)


def test_any_optimizer_source_change_is_rejected(repair):
    (repair[0]/'src/dft/src/optimizer/Opt.cpp').write_bytes(b'changed optimizer\n')
    with pytest.raises(ValueError, match='additional pinned source change'):
        stage.validate_repair(*repair)


def test_changed_patch_bytes_are_rejected(repair):
    Path(repair[1]['patch']['path']).write_bytes(b'other patch\n')
    with pytest.raises(ValueError, match='Evidence changed'):
        stage.validate_repair(*repair)


def test_manifest_cannot_claim_a_different_repaired_source_hash(repair):
    repair[1]['changed_source_sha256'][stage.REPAIRED_FILE]='0'*64
    with pytest.raises(ValueError, match='source hash differs'):
        stage.validate_repair(*repair)


def selection_fixture():
    rows=list(csv.DictReader((stage.OUT/'stage_a/architecture_index.csv').open()))
    for design in stage.DESIGNS:
        for method in ('B2','B3R'):
            rows.append(dict(design=design,method=method,architecture_hash=design+method,
                selected='True',representative='True',roles='single_solution'))
    selection=stage.read(stage.OUT/'stage_a/P0_SELECTION.json')['selection']
    return rows, selection


def test_extended_method_set_reuses_all_frozen_P0_roles():
    rows, selection=selection_fixture()
    selected=complete.validate_selection(rows,selection)
    assert len(selected)==19
    assert {r['method'] for r in selected}=={'B0','B1','B2','B3R','P0'}


def test_balanced_representative_cannot_change_after_implementation():
    rows, selection=selection_fixture()
    next(r for r in rows if r['method']=='P0' and r['representative']=='True')['representative']='False'
    with pytest.raises(ValueError, match='balanced representative changed'):
        complete.validate_selection(rows,selection)


def test_frozen_selected_role_cannot_be_reassigned():
    rows, selection=selection_fixture()
    next(r for r in rows if r['method']=='P0' and r['selected']=='True')['roles']='invented_role'
    with pytest.raises(ValueError, match='roles or balanced representative'):
        complete.validate_selection(rows,selection)


def metric(method, sha, cost, E, H8, status='QUALIFIED'):
    return dict(design='s5378',method=method,architecture_hash=sha,routed_scan_path_cost_um=cost,
        measured_E=E,measured_H8=H8,selected='True',representative='True',status=status,roles='balanced')


def test_B3R_is_the_primary_external_comparison_with_honest_label():
    rows=[metric(method,method,10,10,10) for method in ('B0','B1','B2','B3R')]
    rows.append(metric('P0','P0',11,9,8))
    answer=analyze(rows)['s5378']
    assert answer['A1']['mandatory_external_methods_complete'] is True
    assert answer['A3']['B3R_vs_B0']['left_method']=='B3R'
    assert answer['A3']['B3R_vs_predeclared_P0'][0]['left_method']=='B3R'
    assert 'B3_vs_B0' not in answer['A3']
    assert answer['A2']['pairwise_deltas'][-1]['routed_scan_path_cost_um']==1


def test_unrepaired_B3_label_does_not_satisfy_amended_method_gate():
    answer=analyze([metric(method,method,10,10,10) for method in ('B0','B1','B2','B3')])['s5378']
    assert answer['A1']['mandatory_external_methods_complete'] is False
    assert answer['A3']['B3R_vs_B0'] is None


def test_failed_P0_remains_unassessed_against_B3R():
    answer=analyze([metric('B3R','r',9,9,9),metric('P0','p',1,1,1,'MEASUREMENT_FAILED')])['s5378']
    assert answer['A3']['B3R_vs_predeclared_P0']==[None]


def test_receiver_result_join_preserves_route_failure_and_method_label():
    item=metric('B3R','a',1,1,1)
    route=dict(report=dict(status='POSTROUTE_FAILED',DRC_errors=3,routed_full_scan_path_net_length_upper_bound_um=7),
        reused=False,report_binding=dict(path='route.json'))
    row=metric_row(item,route,dict(status='QUALIFIED',reused=False))
    assert row['method']=='B3R' and row['status']=='POSTROUTE_FAILED'
    assert row['measured_E'] is None and implemented_point(row) is None


def fake_tests(tmp_path, monkeypatch, cases):
    previous=tmp_path/'previous'; current=tmp_path/'current'
    (previous/'stage_a').mkdir(parents=True); current.mkdir()
    (previous/'stage_a/status.json').write_text(json.dumps(dict(tests=dict(distinct_passed=47,distinct_failed=0,executions=55))))
    (current/'receiver_adapter_tests.xml').write_text('<testsuites><testsuite>'+cases+'</testsuite></testsuites>')
    monkeypatch.setattr(complete,'PREVIOUS',previous)
    monkeypatch.setattr(complete,'RECOVERY',current)


def test_unit_accounting_separates_distinct_cases_from_executions(tmp_path,monkeypatch):
    fake_tests(tmp_path,monkeypatch,'<testcase classname="receiver" name="a"/><testcase classname="receiver" name="b"/>')
    result=complete.test_accounting()
    assert result['distinct_passed']==49 and result['executions']==57
    assert result['historical']['reused'] is True and result['current']['reused'] is False


def test_repeated_cases_cannot_inflate_new_distinct_count(tmp_path,monkeypatch):
    fake_tests(tmp_path,monkeypatch,'<testcase classname="receiver" name="a"/><testcase classname="receiver" name="a"/>')
    with pytest.raises(ValueError,match='duplicate case identities'):
        complete.test_accounting()


def test_skipped_cases_are_not_reported_as_passed(tmp_path,monkeypatch):
    fake_tests(tmp_path,monkeypatch,'<testcase classname="receiver" name="a"/><testcase classname="receiver" name="b"><skipped/></testcase>')
    result=complete.test_accounting()
    assert result['distinct_passed']==48 and result['executions']==57


def test_failed_new_test_prevents_sealing(tmp_path,monkeypatch):
    fake_tests(tmp_path,monkeypatch,'<testcase classname="receiver" name="a"><failure/></testcase>')
    with pytest.raises(ValueError,match='unit tests failed'):
        complete.test_accounting()


def test_repeat_suite_counts_executions_without_inflating_distinct_cases(tmp_path,monkeypatch):
    cases='<testcase classname="receiver" name="a"/><testcase classname="receiver" name="b"/>'
    fake_tests(tmp_path,monkeypatch,cases)
    (complete.RECOVERY/'receiver_adapter_tests_repeat.xml').write_text('<testsuites><testsuite>'+cases+'</testsuite></testsuites>')
    result=complete.test_accounting()
    assert result['distinct_passed']==49 and result['executions']==59
    assert result['current']['tests']==2 and result['current']['executions']==4


def fake_measurement_tools(tmp_path,monkeypatch,wrong=False):
    versions={'openroad':'fixed OpenROAD','iverilog':'fixed Icarus','vvp':'fixed runtime'}
    paths={}
    for name in versions:
        executable=tmp_path/name
        executable.write_bytes(name.encode())
        paths[name]=str(executable)
    monkeypatch.setattr(measure.shutil,'which',lambda name:paths[name])
    def run(args,**kwargs):
        name=Path(args[0]).name
        return SimpleNamespace(stdout=('changed Icarus' if wrong and name=='iverilog' else versions[name])+'\n',stderr='')
    monkeypatch.setattr(measure.subprocess,'run',run)
    return dict(tools={name:versions[name] for name in ('openroad','iverilog')}), paths


def test_new_measurements_record_actual_tool_paths_hashes_and_versions(tmp_path,monkeypatch):
    original,paths=fake_measurement_tools(tmp_path,monkeypatch)
    observed,binaries=measure.current_tools(original)
    assert set(binaries)=={'openroad','iverilog','vvp'}
    assert observed['iverilog']==original['tools']['iverilog']
    assert binaries['vvp']['path']==paths['vvp']
    assert binaries['iverilog']['sha256']==digest(b'iverilog')


def test_changed_Icarus_version_is_not_hidden_by_copied_manifest(tmp_path,monkeypatch):
    original,_=fake_measurement_tools(tmp_path,monkeypatch,wrong=True)
    with pytest.raises(ValueError,match='tool version changed: iverilog'):
        measure.current_tools(original)
