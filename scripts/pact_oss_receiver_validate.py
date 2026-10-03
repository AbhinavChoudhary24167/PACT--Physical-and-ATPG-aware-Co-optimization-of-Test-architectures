#!/usr/bin/env python3
"""Validate, DCO-commit and identify only the authorized B3R receiver repair."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

import pact_oss_receiver_build as build
from pact_oss_benchmark import binding, read, write


def formatting():
    build.gate()
    before=(build.SOURCE/build.FILE).read_bytes()
    executable=shutil.which('clang-format-18')
    if not executable:
        raise ValueError('Independent WSL clang-format-18 prerequisite is unavailable')
    version=subprocess.check_output([executable,'--version'],text=True).strip()
    label='receiver_clang_format_attempt4'
    shutil.copy2(__file__,build.FOLDER/(label+'.pact_oss_receiver_validate.py'))
    rc=build.execute([executable,'-i','--lines=106:111',str(build.SOURCE/build.FILE)],label)
    after=(build.SOURCE/build.FILE).read_bytes()
    original=build.original.RECOVERY/'baselines'/build.OLD/'diagnostics'/build.FILE
    expected=original.read_bytes()
    for member in ('getLibertyScanIn','getLibertyScanOut'):
        expression=f'findITerm({member}(test_cell_)), inst_);'.encode()
        formatted=f'findITerm(db_network_->{member}(test_cell_)),\n                       inst_);'.encode()
        if expected.count(expression)!=1:
            raise ValueError('Formatting does not start from the unique receiver-only repair')
        expected=expected.replace(expression,formatted)
    if after!=expected:
        (build.SOURCE/build.FILE).write_bytes(before)
        raise ValueError('Formatter changes exceed line wrapping of the two repaired statements; original narrow patch restored')
    build.run_git('diff','--check')
    if build.run_git('diff','--numstat').strip()!='4\t2\t'+build.FILE:
        raise ValueError('Formatted patch exceeds two receiver additions with immediate line wrapping')
    for filename in ('patch.diff','patch_proposal.json'):
        target=build.REPAIR/('preformat_'+filename)
        if not target.exists():
            shutil.copy2(build.REPAIR/filename,target)
    (build.REPAIR/'patch.diff').write_text(build.run_git('diff','--no-ext-diff','--binary'))
    proposal=read(build.REPAIR/'patch_proposal.json')
    proposal.update(patch=binding(build.REPAIR/'patch.diff'),patch_sha256=binding(build.REPAIR/'patch.diff')['sha256'],
        changed_lines=dict(additions=4,deletions=2),changed_source_sha256={build.FILE:binding(build.SOURCE/build.FILE)['sha256']},
        formatting='Only default clang-format line wrapping of the two changed return statements')
    write(build.REPAIR/'patch_proposal_formatted.json',proposal)
    write(build.REPAIR/'formatting.json',dict(status='PASS' if not rc else 'FAIL',
        formatter=binding(executable),version=version,execution=binding(build.FOLDER/(label+'.execution.json')),
        policy='WSL formatter provisioned independently; immutable build image unchanged; only lines 106:111 checked',
        receiver_only_patch_plus_immediate_line_wrapping=True,semantic_tokens_unchanged_by_formatting=True,
        patch=binding(build.REPAIR/'patch.diff')))
    return rc


def tests():
    build.gate()
    for label in ('narrow_receiver_target','build_repair_validation'):
        if read(build.FOLDER/(label+'.execution.json'))['returncode']:
            raise ValueError('Required repaired target has not built: '+label)
    records={}
    for name in ('scan_opt_sky130','place_sort_sky130','one_cell_sky130'):
        output=build.DATA/'DFT_regressions'/name
        output.mkdir(parents=True,exist_ok=True)
        args=['/usr/bin/env',f'OPENROAD_EXE=/build_storage/{build.OLD}/build/bin/openroad',
            'TEST_NAME='+name,'TEST_EXT=tcl','TEST_TYPE=tcl','TEST_CHECK_LOG=True','TEST_CHECK_PASSFAIL=False',
            f'RESULTS_DIR=/scratch/receiver_recovery_20261003/DFT_regressions/{name}',
            '/bin/bash',f'/build_storage/{build.OLD}/source/test/regression_test.sh']
        command=build.docker(args)
        position=command.index('--entrypoint')
        command[position:position]=['--workdir',f'/build_storage/{build.OLD}/source/src/dft/test']
        shutil.copy2(__file__,build.FOLDER/('test_'+name+'.pact_oss_receiver_validate.py'))
        rc=build.execute(command,'test_'+name)
        records[name]=dict(status='PASS' if not rc else 'FAIL',execution=binding(build.FOLDER/('test_'+name+'.execution.json')),
            raw_output={path.name:binding(path) for path in sorted(output.iterdir()) if path.is_file()})
        target=build.REPAIR/'tests'/name
        target.mkdir(parents=True,exist_ok=True)
        for path in output.iterdir():
            if path.is_file(): shutil.copy2(path,target/path.name)
    saved_binary=build.DATA/'validation_binary/openroad'
    saved_binary.parent.mkdir(parents=True,exist_ok=True)
    if saved_binary.exists():
        raise ValueError('Preserve the existing precommit validation binary')
    shutil.copy2(build.BUILD/'bin/openroad',saved_binary)
    write(build.REPAIR/'tests.json',dict(status='PASS' if all(r['status']=='PASS' for r in records.values()) else 'FAIL',
        tests_before='Original pinned B3 compilation failed at both location accessor calls; no executable existed',
        before_build=binding(build.original.RECOVERY/'baselines'/build.OLD/'build_result.json'),
        tests_after=records, relevant_existing_integration_tests=len(records), new_upstream_tests=0,
        direct_compile_regression_guard='dft_cells_lib target, followed by full openroad target',
        intended_algorithm='Unchanged B3 KMeans/NN/directed 2Opt/3Opt; exact B2 remains unchanged',
        binary_before_immutable_commit=binding(saved_binary)))
    (build.REPAIR/'test.log').write_text('\n'.join(name+' '+row['status'] for name,row in records.items())+'\n')
    return 0 if all(r['status']=='PASS' for r in records.values()) else 1


def commit():
    build.gate()
    if read(build.REPAIR/'tests.json')['status']!='PASS' or read(build.REPAIR/'formatting.json')['status']!='PASS':
        raise ValueError('Focused test or formatting validation has not passed')
    if build.run_git('rev-parse','HEAD').strip()!=build.BASE or build.run_git('diff','--numstat').strip()!='4\t2\t'+build.FILE:
        raise ValueError('Repair parent or diff exceeds the authorized patch')
    build.run_git('diff','--check')
    build.run_git('add','--',build.FILE)
    build.run_git('commit','-s','-m','dft: qualify dbNetwork member calls in scan optimization')
    sha=build.run_git('rev-parse','HEAD').strip()
    if build.run_git('rev-parse','HEAD^').strip()!=build.BASE:
        raise ValueError('DCO repair commit has the wrong parent')
    record=read(build.REPAIR/'patch_proposal_formatted.json')
    trailer='Signed-off-by: '+record['identity']['name']+' <'+record['identity']['email']+'>'
    message=build.run_git('log','-1','--format=%B')
    if trailer not in message:
        raise ValueError('Configured contributor DCO sign-off is missing')
    patch=build.run_git('diff','HEAD^','HEAD','--no-ext-diff','--binary')
    if hashlib.sha256(patch.encode()).hexdigest()!=record['patch_sha256']:
        raise ValueError('Committed patch differs from the tested patch')
    record.update(repair_commit_sha=sha,DCO_signed_off_by=trailer,DCO_verified=True,
        reason='Only missing object receivers for existing dbNetwork APIs in B3 scan-pin location accessors',
        tests_before=read(build.REPAIR/'tests.json')['tests_before'], tests_after=binding(build.REPAIR/'tests.json'),
        original_pinned_failure=binding(build.original.RECOVERY/'baselines'/build.OLD/'compilation_blocker.json'),
        Git_status_after_commit=build.run_git('status','--short'),Git_log_full=build.run_git('log','-1','--format=full'),
        Git_show_stat=build.run_git('show','--stat','HEAD'),Git_show=build.run_git('show','HEAD'),
        algorithm_semantics_changed=False,method_display='B3R — PR #10666 + minimal compile repair')
    write(build.REPAIR/'repair_manifest.json',record)
    old=read(build.original.RECOVERY/'baselines'/build.OLD/'source_manifest.json')
    write(build.FOLDER/'source_manifest.json',dict(upstream_base_sha=build.BASE,repair_commit_sha=sha,
        patch_sha256=record['patch_sha256'],source_directory=str(build.SOURCE),
        source_modifications=[build.FILE],pinned_source_blobs_checked=old['pinned_source_blobs_checked'],
        changed_source_sha256=record['changed_source_sha256'],repair_manifest=binding(build.REPAIR/'repair_manifest.json'),
        original_exact_source_manifest=binding(build.original.RECOVERY/'baselines'/build.OLD/'source_manifest.json')))
    print('B3R_DCO_SIGNED_REPAIR_COMMIT',sha,record['patch_sha256'],flush=True)
    return 0


def record():
    build.gate()
    repair=read(build.REPAIR/'repair_manifest.json')
    for label in ('configure_final','build_final'):
        if read(build.FOLDER/(label+'.execution.json'))['returncode']:
            raise ValueError('Final immutable repair build has not passed')
    if build.run_git('rev-parse','HEAD').strip()!=repair['repair_commit_sha'] or build.run_git('status','--short'):
        raise ValueError('Repair checkout differs from its immutable DCO commit')
    rc=build.execute(build.docker([f'/build_storage/{build.OLD}/build/bin/openroad','-version']),'binary_version_final')
    if rc or repair['repair_commit_sha'] not in (build.FOLDER/'binary_version_final.log').read_text():
        raise ValueError('Final binary does not report the actual repaired revision')
    binary=binding(build.BUILD/'bin/openroad')
    write(build.REPAIR/'patch_evolution.json',dict(status='PASS',upstream_base_sha=build.BASE,
        initial_proposal=binding(build.REPAIR/'patch_proposal.json'),
        preserved_initial_patch=binding(build.REPAIR/'preformat_patch.diff'),
        final_proposal=binding(build.REPAIR/'patch_proposal_formatted.json'),
        final_patch=binding(build.REPAIR/'patch.diff'),formatting=binding(build.REPAIR/'formatting.json'),
        explanation='Initial draft patch/proposal were superseded before sealing. The preserved initial patch resolves its historical SHA; the final patch adds only immediate clang-format line wrapping to the same two receiver insertions. No other source change.'))
    write(build.FOLDER/'build_environment_adjustment.json',dict(status='PASS',
        failed_initial_configuration=binding(build.FOLDER/'configure_repair_validation.execution.json'),
        successful_validation_configuration=binding(build.FOLDER/'successful_configuration.json'),
        successful_final_configuration=binding(build.FOLDER/'successful_configuration_final.json'),
        original_source_and_build_changed=False,
        derivative_source_bind='Writable only in the independent derivative overlay for CMake generated Version.hh; all tracked main source and recursive submodule differences are separately checked at each build gate',
        submodule_identity_proof=binding(build.REPAIR/'submodule_git_metadata.json'),
        formatting=binding(build.REPAIR/'formatting.json'),
        immutable_image_changed=False,known_source_repair=build.FILE))
    write(build.FOLDER/'build_result.json',dict(status='BUILT',commit=repair['repair_commit_sha'],upstream_base_sha=build.BASE,
        binary=binary,binary_sha256=binary['sha256'],build=binding(build.FOLDER/'build_final.execution.json'),
        configuration=binding(build.FOLDER/'configure_final.execution.json'),source_manifest=binding(build.FOLDER/'source_manifest.json'),
        provisional_build_validation=binding(build.FOLDER/'build_repair_validation.execution.json'),
        actual_cmake_resolution=binding(build.FOLDER/'configure_final.dependency_resolution.json'),
        copied_exact_base_build_cache=binding(build.REPAIR/'build_cache_reuse.json'),
        build_environment_adjustment=binding(build.FOLDER/'build_environment_adjustment.json'),
        image=build.original.IMAGE,method_display='B3R — PR #10666 + minimal compile repair'))
    print('B3R_IMMUTABLE_BINARY_REPRODUCED',repair['repair_commit_sha'],binary['sha256'],flush=True)
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('format','tests','commit','record'))
    args=parser.parse_args()
    raise SystemExit({'format':formatting,'tests':tests,'commit':commit,'record':record}[args.action]())
