#!/usr/bin/env python3
"""Seal an observed Stage-A outcome without changing the experiment or P0."""
from pact.experiment_storage import experiment_root
import argparse
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, git, read, verify, write
from pact_oss_receiver_stage_a import RECOVERY, PREVIOUS, DATA, STAGE, RAW, BASELINES, METHODS, B3R_DISPLAY, gate, checked, method_display
from pact_oss_compare import implemented_point
from pact_oss_canonicalize import csv_write


def validate_selection(rows, selection):
    selected=[row for row in rows if row['selected']=='True']
    if len(rows)!=30 or len(selected)!=19:
        raise ValueError('Extended canonical/selected record counts differ')
    for design in DESIGNS:
        data=[row for row in selected if row['design']==design]
        if {row['method'] for row in data}!=METHODS:
            raise ValueError('Mandatory design/method records are missing')
        if any(sum(row['method']==method for row in data)!=1 for method in METHODS-{'P0'}):
            raise ValueError('An external method does not have exactly one selected record')
        p0=[row for row in data if row['method']=='P0']
        expected=selection[design]['roles']
        if {row['architecture_hash'] for row in p0}!=set(expected):
            raise ValueError('Frozen P0 selected identities differ')
        for row in p0:
            roles=expected[row['architecture_hash']]
            if set(row['roles'].split(';'))!=set(roles) or (row['representative']=='True')!=('balanced' in roles):
                raise ValueError('Frozen P0 roles or balanced representative changed')
    return selected


def rss(path):
    if not path.exists():
        return None
    match=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',path.read_text())
    return int(match[1]) if match else None


def markdown_table(fields, rows):
    def display(value):
        return B3R_DISPLAY if value=='B3R' else str(value)
    return '\n'.join(['| '+' | '.join(fields)+' |','| '+' | '.join(['---']*len(fields))+' |']+
        ['| '+' | '.join(display(row.get(field,'')) for field in fields)+' |' for row in rows])


def compilation_runtime(method, build):
    """Separate the full validation compile from the final incremental build."""
    final=Path(build['build']['path'])
    paths=[]
    if method=='B3R':
        for name,stage in (('narrow_receiver_target','receiver_repair_narrow_target'),
                           ('build_repair_validation','receiver_repair_full_build_validation')):
            path=final.parent/(name+'.execution.json')
            if path.exists():
                paths.append((path,stage))
    paths.append((final,'final_immutable_commit_incremental_build' if method=='B3R' else 'historical_exact_compilation'))
    result=[]
    for path,stage in paths:
        execution=read(path)
        result.append(dict(design='all',method=method,stage=stage,
            elapsed_seconds=execution['elapsed_seconds'],
            peak_RSS_kbytes=rss(path.with_name(path.name.replace('.execution.json','.container.resource.txt'))),
            reused=method=='B2',source=str(path)))
    return result


def native_test_accounting(path):
    receipt=read(path)
    checked(receipt['binary_before_immutable_commit'])
    names={'scan_opt_sky130','place_sort_sky130','one_cell_sky130'}
    if receipt['status']!='PASS' or receipt['relevant_existing_integration_tests']!=3 or set(receipt['tests_after'])!=names:
        raise ValueError('The three native DFT regression tests have not passed')
    executions={}
    for name,test in receipt['tests_after'].items():
        if test['status']!='PASS':
            raise ValueError('Native DFT regression failed: '+name)
        checked(test['execution'])
        if read(test['execution']['path'])['returncode']!=0:
            raise ValueError('Native DFT regression execution failed: '+name)
        executions[name]=test['execution']
    return dict(status='PASS',existing_native_tests_passed=3,new_upstream_tests=receipt['new_upstream_tests'],
        receipt=binding(path),executions=executions,
        binary_at_test_execution=receipt['binary_before_immutable_commit'],
        scope='Native tests ran on the repair-validation binary before the DCO-signed immutable commit; final binary is independently exercised by compiled-command and frozen-design qualification.')


def reuse_accounting():
    from pact_oss_receiver_reuse_preflight import require_preflight
    receipt=require_preflight()
    candidates=receipt['route_candidates']
    eligible=sum(item['eligible'] for item in candidates.values())
    exclusions=[dict(report=path,design=item['design'],architecture_sha256=item['architecture_sha256'],
        observed_threads=item['observed_threads'],explicit_NUM_CORES_2=item['explicit_NUM_CORES_2'],reasons=item['reasons'])
        for path,item in candidates.items() if not item['eligible']]
    if eligible!=receipt['eligible_route_candidates'] or len(exclusions)!=receipt['excluded_route_candidates'] or len(receipt['expected_bindings'])!=receipt['historical_binding_checks']:
        raise ValueError('Cache eligibility accounting differs from its verified receipt')
    return dict(status=receipt['status'],meaning=receipt['meaning'],
        historical_binding_checks=receipt['historical_binding_checks'],eligible_route_candidates=eligible,
        excluded_route_candidates=len(exclusions),excluded_routes=exclusions,environment=receipt['environment'],
        cache_exclusions_preserved=receipt['cache_exclusions_preserved'],
        receipt=binding(RECOVERY/'reuse_preflight/eligibility.json'),
        missing_or_ineligible_selected_cache='Fresh routing of the unchanged canonical architecture with GRT_SEED=11, NUM_CORES=2 and the fixed backend',
        measurement_reuse='Only exact routed-archive bytes plus all frozen workload/input/functional/FF checks permit reuse')


def contribution_accounting(path=None):
    path=Path(path) if path else BASELINES['B3R']['folder']/'repair/github_contribution.json'
    related='https://github.com/The-OpenROAD-Project/OpenROAD/pull/10666'
    if not path.exists():
        return dict(status='PENDING_NOT_CLAIMED_SUBMITTED',PR_opened=False,PR_URL=None,
            target_repository=None,target_branch=None,related_original_PR=related,receipt=None,
            scope='No upstream contribution receipt exists at capture time; an opened PR is not claimed')
    record=read(path)
    url=record.get('PR_URL') or record.get('pr_url') or record.get('pull_request_url')
    related_record=record.get('related_original_PR',record.get('related_original_pr',related))
    if isinstance(related_record,dict):
        related_record=related_record.get('url',related_record.get('PR_URL',related))
    if not isinstance(related_record,str) or not related_record.startswith('https://'):
        related_record=related
    return dict(status=record.get('status','RECORDED_SUBMISSION_STATE_UNSPECIFIED'),PR_opened=bool(url),PR_URL=url,
        PR_number=record.get('PR_number',record.get('pr_number')),
        target_repository=record.get('target_repository'),target_branch=record.get('target_branch'),
        related_original_PR=related_record,
        CI_status_at_capture=record.get('CI_status',record.get('ci_status',record.get('ci_status_at_capture'))),capture_time=record.get('capture_time_utc',record.get('timestamp')),
        receipt=binding(path),scope='Submission state at capture time; benchmark does not wait for CI, review or merge',details=record)


def test_accounting():
    """Count distinct adapter cases separately from reused historical runs."""
    old = read(PREVIOUS / 'stage_a/status.json')['tests']
    receipts, identities, passed, executions = {}, set(), set(), 0
    for xml in sorted(RECOVERY.glob('receiver_adapter_tests*.xml')):
        cases = list(ET.parse(xml).getroot().iter('testcase'))
        names = [(case.attrib.get('classname', ''), case.attrib['name']) for case in cases]
        if not cases or len(set(names)) != len(names):
            raise ValueError('New adapter test receipt has no cases or duplicate case identities')
        failures = sum(case.find('failure') is not None for case in cases)
        errors = sum(case.find('error') is not None for case in cases)
        if failures or errors:
            raise ValueError('Relevant receiver adapter unit tests failed')
        passed.update(name for name,case in zip(names,cases) if case.find('skipped') is None)
        identities.update(names)
        executions += len(cases)
        receipts[xml.name] = dict(tests=len(cases), failures=failures, errors=errors,
            skipped=sum(case.find('skipped') is not None for case in cases), XML=binding(xml))
    if not identities or old['distinct_failed']:
        raise ValueError('Relevant receiver adapter unit tests failed')
    return dict(historical=dict(distinct_passed=old['distinct_passed'], distinct_failed=old['distinct_failed'],
                    executions=old['executions'], reused=True, status=binding(PREVIOUS / 'stage_a/status.json')),
                current=dict(tests=len(identities), failures=0, errors=0, skipped=len(identities-passed),
                    executions=executions, reused=False, receipts=receipts, cases=sorted(identities)),
                distinct_passed=old['distinct_passed']+len(passed),
                distinct_failed=old['distinct_failed'], executions=old['executions']+executions)


def seal(args):
    gate()
    verify()
    rows=list(csv.DictReader((STAGE/'implemented_metrics.csv').open()))
    expected_selection=read(OUT/'stage_a/P0_SELECTION.json')['selection']
    selected=validate_selection(rows, expected_selection)
    complete=bool(selected) and all(implemented_point(r) is not None and
        r['measured_H4']!='' and math.isfinite(float(r['measured_H4'])) and float(r['measured_H4'])>=0 for r in selected)
    if not complete and args.classification!='PACT_STAGE_A_INCOMPLETE':
        raise ValueError('Mandatory implemented measurements are missing; Stage A must remain incomplete')
    if complete and args.classification=='PACT_STAGE_A_INCOMPLETE':
        raise ValueError('All mandatory outcomes exist; select an evidence-based completed classification')
    tests=test_accounting()
    native_tests=native_test_accounting(args.native_tests or BASELINES['B3R']['folder']/'repair/tests.json')
    reuse=reuse_accounting()
    contribution=contribution_accounting()
    binaries={method:read(spec['folder']/'build_result.json') for method,spec in BASELINES.items()}
    qualification={method:read(spec['folder']/'qualification.json') for method,spec in BASELINES.items()}
    repair=read(BASELINES['B3R']['folder']/'repair/repair_manifest.json')
    amendment=binding(OUT/'protocol/amendment_B3_source_repair.md')
    counts={key:0 for key in ('new_routes','qualified_new_routes','new_extractions','new_simulations','qualified_new_measurements')}
    external={'native_tests/precommit_binary':native_tests['binary_at_test_execution'],
              'native_tests/receipt':native_tests['receipt'],'protocol/B3_source_repair_amendment':amendment}
    if contribution['receipt']:
        external['upstream/contribution']=contribution['receipt']
    runtime=[]
    historical=read(ROOT/'results/pact_candidate_stateful/summary.json')['designs']
    for design in DESIGNS:
        native=OUT/'baselines/B1_openroad_native'/design
        executions=[p for p in native.glob('native*.execution.json') if read(p)['returncode']==0]
        if len(executions)!=1:
            raise ValueError('Historical B1 success receipt is ambiguous')
        execution=read(executions[0])
        runtime.extend([
            dict(design=design,method='B0',stage='historical_reference',elapsed_seconds=None,peak_RSS_kbytes=None,
                reused=True,source=str(OUT/'stage_a/architecture_index.csv')),
            dict(design=design,method='B1',stage='architecture_generation',elapsed_seconds=execution['seconds'],
                peak_RSS_kbytes=rss(executions[0].with_name(executions[0].name.replace('.execution.json','.resource.txt'))),
                reused=True,source=str(executions[0])),
            dict(design=design,method='P0',stage='original_frozen_search',elapsed_seconds=historical[design]['total_seconds'],
                peak_RSS_kbytes=historical[design]['peak_RSS_MiB']*1024,reused=True,source=str(ROOT/'results/pact_candidate_stateful/summary.json'))])
    for method,build in binaries.items():
        spec=BASELINES[method]
        name=spec['name']
        folder=spec['folder']
        check=binding(build['binary']['path'])
        if check['sha256']!=build['binary_sha256']:
            raise ValueError('Generator binary changed')
        external['binary/'+name]=check
        runtime.extend(compilation_runtime(method,build))
        for item in qualification[method]['designs'].values():
            proof=read(item['proof']['path'])
            if proof['status']!='PASS' or not proof['endpoint_geometry_unchanged']:
                raise ValueError('Generator architecture qualification no longer passes')
        for design in DESIGNS:
            generated=folder/design
            execution=read(generated/'generate.execution.json')
            runtime.append(dict(design=design,method=method,stage='architecture_generation',
                elapsed_seconds=execution['elapsed_seconds'],peak_RSS_kbytes=rss(generated/'generator.resource.txt'),
                reused=method=='B2',source=str(generated/'generate.execution.json')))
            scratch=Path(('' + str(experiment_root()) + '/tmp/pact_oss_20261003'))/('recovery_20261003' if method=='B2' else 'receiver_recovery_20261003')/name/design
            for path in sorted(scratch.iterdir()):
                if path.is_file():
                    external['generator/'+name+'/'+design+'/'+path.name]=binding(path)
    for design in DESIGNS:
        routes=read(STAGE/'routes'/(design+'.json'))
        counts['new_routes']+=routes['new_route_attempts']
        counts['qualified_new_routes']+=routes['qualified_new_routes']
        measurements=read(STAGE/'measurements'/(design+'.json'))
        for sha,item in measurements['records'].items():
            if not item.get('reused') and item['status']=='QUALIFIED':
                counts['qualified_new_measurements']+=1
            if item.get('folder'):
                folder=Path(item['folder'])
                for filename,key in (('extract.execution.json','new_extractions'),('simulate.execution.json','new_simulations')):
                    if not item.get('reused') and (folder/filename).exists():
                        counts[key]+=1
            # Historical primary measurement evidence stays at its original path.
            for key in ('manifest','summary','crosscheck','functional_log','spatial_bins','VCD','simulation_manifest','topology','functional'):
                if key in item:
                    if binding(item[key]['path'])['sha256']!=item[key]['sha256']:
                        raise ValueError('Measurement evidence changed')
                    external['measurement/'+design+'/'+sha+'/'+key]=item[key]
        for sha,item in routes['records'].items():
            for key in ('report_binding','archive'):
                if item.get(key):
                    if binding(item[key]['path'])['sha256']!=item[key]['sha256']:
                        raise ValueError('Route evidence changed')
                    external['route/'+design+'/'+sha+'/'+key]=item[key]
            report=item['report']
            labels=','.join(sorted({r['method'] for r in rows if r['design']==design and r['architecture_hash']==sha}))
            runtime.append(dict(design=design,method=labels+' '+sha[:12],stage='common_route',
                elapsed_seconds=report.get('route_wall_seconds'),peak_RSS_kbytes=None,
                reused=item['reused'],source=item['report_binding']['path']))
    for path in sorted(RAW.rglob('*')):
        if path.is_file():
            external['new_raw/'+str(path.relative_to(RAW))]=binding(path)
    # Bind the acquired source archives and independent prerequisite artifacts
    # as files, while avoiding the mutable 16-GiB mounted build filesystem.
    already_bound={item['path'] for item in external.values()}
    for path in sorted(DATA.rglob('*')):
        if path.is_file() and path.name!='build-storage.ext4' and str(path) not in already_bound:
            external['recovery_raw/'+str(path.relative_to(DATA))]=binding(path)
    for entry in runtime:
        codes, *suffix = entry['method'].split(' ',1)
        entry['method_display'] = ', '.join(method_display(code) for code in codes.split(',')) + (' '+suffix[0] if suffix else '')
    csv_write(STAGE/'runtime.csv',list(runtime[0]),runtime)
    status=dict(timestamp=datetime.now(timezone.utc).isoformat(),stage_a=args.classification,scientific=args.scientific,
        engineering='PACT_OSS_BENCHMARK_COMPLETE' if complete else 'PACT_STAGE_A_INCOMPLETE',
        OSS_benchmark_complete=complete, P0_commit=read(OUT/'stage_a/P0_FREEZE.json')['commit'],
        P0_model_changed=False,P0_search_rerun=False,P0_selection_changed=False,B1_regenerated=False,
        Stage_B='NOT_STARTED_USER_SCOPE_STAGE_A_ONLY',Stage_C='NOT_STARTED_USER_SCOPE_STAGE_A_ONLY',P1_model_complete=False,
        Stage_B_scientific_prerequisite_satisfied=complete,Stage_B_execution_authorized_by_this_task=False,
        new_ATPG_runs=0,new_placement_runs=0,new_rootcause_runs=0,**counts,
        selected_method_records=len(selected),qualified_selected_method_records=sum(implemented_point(r) is not None for r in selected),
        remaining_blockers=[{key:r.get(key) for key in ('design','method','architecture_hash','status','failure_stage','failure_reason','route_report')}
            for r in selected if implemented_point(r) is None],
        tests=tests,unit_tests_passed=tests['distinct_passed'],
        native_DFT_regression_tests=native_tests,native_DFT_regression_tests_passed=3,
        reuse_preflight=reuse,upstream_contribution=contribution,protocol_amendment=amendment,
        new_adapter_unit_tests_passed=tests['current']['tests']-tests['current']['skipped'],
        historical_unit_executions_reused=tests['historical']['executions'],
        current_recovery_unit_test_executions=tests['current']['executions'],
        total_campaign_unit_test_executions=tests['executions'],
        fixed_backend=binding('/usr/bin/openroad'),
        original_incomplete_seal=binding(OUT/'stage_a/evidence_manifest.json'),
        original_P0_selection=binding(OUT/'stage_a/P0_SELECTION.json'),
        original_source_failure=binding(PREVIOUS/'baselines/B3_openroad_10666/compilation_blocker.json'),
        previous_recovery_seal=binding(PREVIOUS/'stage_a/evidence_manifest.json'),
        B2='EXACT_PINNED_BUILD_AND_ARCHITECTURES_REUSED',B3R='MINIMAL_RECEIVER_REPAIR_BUILT_AND_QUALIFIED',
        method_legend={method:method_display(method) for method in sorted(METHODS)},
        B3R_upstream_base_sha=repair['upstream_base_sha'],B3R_repair_commit_sha=repair['repair_commit_sha'],
        B3R_patch_sha256=repair['patch_sha256'],new_architecture_generations=len(DESIGNS),
        Git_status_before_commit=git('status','--short'),Git_HEAD_before_commit=git('rev-parse','HEAD'))
    write(STAGE/'status.json',status)
    display=[]
    fronts={(r['design'],r['method'],r['architecture_hash']):r['pareto_status']
        for r in csv.DictReader((STAGE/'pareto_front.csv').open())}
    for r in selected:
        display.append(dict(design=r['design'],method=r['method'],roles=r['roles'],architecture=r['architecture_hash'][:12],
            status=r['status'],wire_um=r['routed_scan_path_cost_um'],E=r['measured_E'],H4=r['measured_H4'],H8=r['measured_H8'],
            Pareto=fronts[(r['design'],r['method'],r['architecture_hash'])]))
    quals=[]
    for method,proof in qualification.items():
        for design,item in proof['designs'].items():
            quals.append(dict(method=proof['method'],design=design,lengths='/'.join(map(str,item['chain_lengths'])),
                canonical_SHA=item['architecture_hash'],qualification='PASS'))
    questions=read(STAGE/'scientific_questions.json')
    answers=[]
    activity_pairs=[]
    physical_pairs=[]
    for design,data in questions.items():
        a1=data['A1']
        answers.append(dict(design=design,A1_unique_P0_nondominated='/'.join(s[:12] for s in a1['unique_nondominated_architectures']) or 'none',
            A1_coordinate_unique='/'.join(s[:12] for s in a1['coordinate_unique_nondominated_architectures']) or 'none',
            external_methods_complete=a1['mandatory_external_methods_complete'],
            A5_known_unselected_dominators=len(data['A5']['unselected_archive_points_dominating_balanced']),
            A5_known_unselected_lower_H8=len(data['A5']['unselected_archive_points_with_lower_H8_than_all_measured_selected']),
            unknown_P0_archive_points=data['A5']['unmeasured_archive_points']))
        for pair in data['A2']['pairwise_deltas']:
            activity_pairs.append(dict(design=design,baseline=pair['right_method'],wire_delta_um=pair['routed_scan_path_cost_um'],
                E_delta=pair['measured_E'],H8_delta=pair['measured_H8'],P0_activity_improvement=pair['activity_improvement']))
        for pair in data['A4']:
            physical_pairs.append(dict(design=design,left=pair['left_method'],right=pair['right_method'],
                wire_delta_um=pair['routed_scan_path_cost_um'],E_delta=pair['measured_E'],H8_delta=pair['measured_H8']))
    a3='\n'.join(f"- {design}: B3R versus B0 `{data['A3']['B3R_vs_B0']}`; "
        f"B3R strictly dominates {sum(bool(p and p['left_dominates']) for p in data['A3']['B3R_vs_predeclared_P0'])} "
        f"of {sum(p is not None for p in data['A3']['B3R_vs_predeclared_P0'])} assessed predeclared P0 recommendations; "
        f"{sum(p is None for p in data['A3']['B3R_vs_predeclared_P0'])} comparisons remain unassessed." for design,data in questions.items())
    report='\n\n'.join([
        '# Stage-A recovery outcome',
        f"Stage A: **{args.classification}**. Scientific classification: **{args.scientific}**. Engineering: **{status['engineering']}**.",
        'Method legend: B0 — original/reference; B1 — native OpenROAD; B2 — exact PR #10176; '+B3R_DISPLAY+'; P0 — frozen PACT candidate_stateful depth 3. B3R is a separately identified derivative, while exact B3 retains its source-build failure.',
        'The previous incomplete seal is preserved. This version uses the same three seed-11 Nangate45 designs, K=2, existing FAN workload, clocks, constraints, common routing, OpenRCX and VCD measurement. P0 remains at `9d9103027918b1d4af2b209e6d36133ad82d4a4e`, candidate_stateful depth 3. No search, ATPG, placement, root-cause rerun or P1 change occurred.',
        'The formally recorded repair and corrected external-baseline identities are in the [B3 source-repair protocol amendment](../protocol/amendment_B3_source_repair.md).',
        '## Exact builds and environment',
        '\n'.join(f"- {method_display(method)}: `{build['status']}`, source `{build['commit']}`, binary SHA256 `{build['binary_sha256']}`, path `{build['binary']['path']}`; reused: {method=='B2'}." for method,build in binaries.items()),
        f"Original exact B3 `{repair['upstream_base_sha']}` retains its source-build failure and sealed diagnostics. B3R uses repair commit `{repair['repair_commit_sha']}`, patch SHA256 `{repair['patch_sha256']}`. Only the two missing `db_network_->` receiver qualifications in `{','.join(repair['changed_files'])}` differ. Exact B2 had already built and qualified all three architectures; its record and binary are reused. The source repair is engineering provenance and contributes no PACT advantage.",
        'Immutable Ubuntu 22.04.5 image `openroad/orfs@sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e`; GCC/G++ 11.4.0, CMake 3.31.9, SWIG 4.3.0. Independently compiled/loaded Tcl 8.6.12 development pair. Both actual CMake resolutions: SWIG `/usr/local/bin/swig`, header `/usr/include/tcl8.6/tcl.h`, include directory `/usr/include/tcl8.6`, library `/usr/lib/x86_64-linux-gnu/libtcl8.6.so`. Dependency versions, paths, hashes and isolation details are in the [historical environment audit](../protocol/build_environment_audit.md), [exact B2 CMake resolution](../recovery_20261003/baselines/B2_openroad_10176/cmake_resolved_dependencies.json), and [B3R final CMake resolution](baselines/B3R_openroad_10666_repaired/configure_final.dependency_resolution.json).',
        'B2 executes native NN followed by endpoint-inclusive FF-origin Manhattan 2-Opt, maximum 30 iterations. B3R preserves B3 capacity-aware same-domain KMeans (maximum 100 iterations), NN, directed scan-pin 2-Opt with reversal correction and direction-preserving 3-Opt over 50 nearest candidates, until strict improvement stops. Its local cost excludes external endpoints. Compiled command probes and source hashes precede benchmark generation. The receiver correction changes no algorithm parameters or cost/ordering semantics.',
        'Compilation accounting separates the narrow receiver target, full repair-validation build, and final immutable-commit incremental build. The final incremental build time alone is not the cost of producing the repaired executable; exact B2 compilation is historical reuse. Full per-stage resource receipts remain bound.',
        markdown_table(['method','stage','elapsed_seconds','peak_RSS_kbytes','reused'],[entry for entry in runtime if entry['stage'] in ('historical_exact_compilation','receiver_repair_narrow_target','receiver_repair_full_build_validation','final_immutable_commit_incremental_build')]),
        f"Upstream contribution state at capture: **{contribution['status']}**. Opened PR recorded: **{contribution['PR_opened']}**. "+
        (f"[Contribution PR]({contribution['PR_URL']}). " if contribution['PR_URL'] else 'No opened PR URL is recorded. ')+
        f"Target repository/branch: `{contribution['target_repository'] or 'not recorded'}:{contribution['target_branch'] or 'not recorded'}`; related implementation: [OpenROAD PR #10666]({contribution['related_original_PR']}). "+
        'Submission state and target are captured from the contribution receipt. CI/review/merge completion does not gate the benchmark.',
        '## Architecture qualification',markdown_table(['method','design','lengths','canonical_SHA','qualification'],quals),
        'All generator outputs preserve exact FF inventory, domains, capacity, K=2, SI/SO legality and physical endpoint geometry. Canonicalization preserves FF assignment/order. Existing B0/B1 and all frozen P0 archive identities/roles are reused.',
        f"Historical cache eligibility audit: **{reuse['status']}**, {reuse['historical_binding_checks']} sealed binding checks; {reuse['eligible_route_candidates']} eligible and {reuse['excluded_route_candidates']} excluded route candidates. The eligibility PASS confirms the audit completed; it does not qualify the excluded caches. Their original data and seals remain preserved. [Eligibility evidence](reuse_preflight/eligibility.json) records each exclusion, observed thread count and missing explicit two-core command. Missing or ineligible selected caches are freshly routed from the unchanged canonical architecture under the common seed-11, two-core flow. An old measurement is reused only when exact routed-archive bytes and all measurement checks match. Actual new attempts and qualified outcomes are counted below.",
        '## Implemented outcomes',markdown_table(['design','method','roles','architecture','status','wire_um','E','H4','H8','Pareto'],display),
        'Wire is the full routed scan-path net-length upper bound in micrometres. E is fF·transitions; H4/H8 are fF·transitions per bin/cycle, from the unchanged all_data measurement scope. Missing values remain unknown. These are activity proxies. Setup/hold WNS/TNS and DRC/topology/functional/every-FF transition qualification are in `stage_a/implemented_metrics.csv`; timing is the existing global-route stage.',
        f"New route attempts: {counts['new_routes']}; qualified new routes: {counts['qualified_new_routes']}; new extraction attempts with receipts: {counts['new_extractions']}; new simulation attempts with receipts: {counts['new_simulations']}; qualified new measurements: {counts['qualified_new_measurements']}. Reused outcomes are explicitly marked per architecture.",
        '## Comparison and A1–A5',
        'The predeclared balanced P0 representative is in `stage_a/method_comparison.csv`. The full retained archive view, including already implemented archive evidence, is in `stage_a/pareto_front.csv`. Unknown archive points are excluded from implemented Pareto calculations. `stage_a/pairwise_comparison.csv` retains every exact wire/E/H8 delta, with no weighted score or post-outcome matching tolerance.',
        'Answers and counterexamples for A1–A5 are recorded in `stage_a/scientific_questions.json`: unique P0 nondominated architecture and coordinate contributions; balanced P0 activity/cost deltas; B3R versus B0 and predeclared P0; every lower-wire external pair and its activity deltas; known implemented archive selection misses with explicit unknown scope and causal limits. No candidate is reselected using these outcomes.',
        markdown_table(list(answers[0]),answers),
        'A2: balanced P0 minus each external baseline; negative activity deltas indicate improvement. Physical-cost differences stay explicit.',
        markdown_table(list(activity_pairs[0]),activity_pairs) if activity_pairs else 'A2: unavailable measurements.',
        'A3: '+a3,
        'A4: the left method has lower wire, or equal wire for a tie. A positive E/H8 delta is a counterexample to automatic activity improvement from lower wire.',
        markdown_table(list(physical_pairs[0]),physical_pairs) if physical_pairs else 'A4: unavailable measurements.',
        'A5: counts above cover only qualified, already implemented archive evidence. Witness architectures and cost/activity deltas are in the question JSON. A known stronger archive point demonstrates a selection miss; this comparison cannot uniquely attribute that miss to predictor incompleteness. Unmeasured points are unknown, and the frozen recommendations remain unchanged.',
        '## Tests, evidence and scope',
        f"Relevant unit tests: {status['unit_tests_passed']} distinct passed, 0 failed; {status['new_adapter_unit_tests_passed']} new adapter cases, and {tests['historical']['distinct_passed']} distinct historical cases reused ({tests['historical']['executions']} historical executions). Current adapter executions: {status['current_recovery_unit_test_executions']}. Separate design integrations: three saved-B1 endpoint checks, three reused exact-B2 architecture qualifications and three actual B3R qualifications. Independent SWIG/Tcl C and generated-module compile/link/load proofs remain qualified; the exact B2 command probe is reused and B3R is checked separately. The versioned evidence manifest binds compact artifacts, source snapshots, exact binaries and primary raw/historical evidence.",
        'Native DFT regressions are counted separately: three existing tests (`scan_opt_sky130`, `place_sort_sky130`, `one_cell_sky130`) passed on the precommit repair-validation binary; no new upstream tests were added. Their command/log bindings and binary-at-execution hash are in [native test evidence](baselines/B3R_openroad_10666_repaired/repair/tests.json). Final immutable-binary command availability and all three architecture qualifications are separate runtime checks.',
        f"Stage-B scientific prerequisite satisfied: {complete}. Stage B remains unstarted and this task does not authorize P1. Original FAN coverage/detected-count evidence remains in the historical `stage_a/test_quality_summary.json`; no new fault identity-set equivalence is claimed.",
        'The recovery commit is made after sealing. Its SHA and final Git status are recorded in a separate commit receipt, preserving the evidence manifest and prior history.',
    ])+'\n'
    target=RECOVERY/'FINAL_REPORT.md'
    if target.exists():
        raise ValueError('Versioned final report already exists')
    target.write_text(report)
    (STAGE/'README.md').write_text('# Versioned Stage-A benchmark\n\n'
        f"Classification: `{args.classification}`. See `../FINAL_REPORT.md` for the exact builds, qualification, implemented tables and A1–A5.\n\n"
        'The original incomplete seal, P0 freeze and predicted-only selection remain unchanged. '
        'This directory extends the canonical inventory with reused exact B2 and repaired B3R, then records common-backend routing/measurement reuse and new attempts. '
        'Architecture identities and pre-route diagnostics were hash-bound before implementation. '
        'Missing outcomes remain unknown; the Pareto front uses exact unweighted dominance in wire/E/H8. '
        'Heavy primary data stays on authorized D: storage and is file-bound by the evidence manifest. Stage B/P1 is unstarted.\n')
    artifacts={str(p.relative_to(RECOVERY)):binding(p) for p in sorted(RECOVERY.rglob('*')) if p.is_file()}
    artifacts['../protocol/build_environment_audit.md']=binding(OUT/'protocol/build_environment_audit.md')
    for path in sorted((OUT/'protocol').glob('amendment*.md')):
        artifacts['../protocol/'+path.name]=binding(path)
    scripts=[p for p in sorted((ROOT/'scripts').glob('pact_oss_*.py')) if p.name not in ('pact_oss_seal_incomplete.py',)]
    sources={str(p.relative_to(ROOT)):binding(p) for p in scripts}
    sources.update({str(p.relative_to(ROOT)):binding(p) for p in sorted((ROOT/'tests/unit').glob('test_oss_*.py'))})
    write(STAGE/'evidence_manifest.json',dict(timestamp=datetime.now(timezone.utc).isoformat(),
        status='SEALED',artifacts=artifacts,benchmark_sources=sources,external_artifacts=external,
        original_incomplete_seal=status['original_incomplete_seal'],previous_recovery_seal=status['previous_recovery_seal'],
        immutable_image=read(PREVIOUS/'toolchain_image.json')['Id'],
        raw_storage='Authorized D: storage; no build filesystem image hash substitutes for file-level evidence',
        Stage_B='NOT_STARTED_USER_SCOPE_STAGE_A_ONLY'))
    print('STAGE_A_EVIDENCE_SEALED',len(artifacts),len(sources),len(external),args.classification,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--classification',required=True,choices=('PACT_STAGE_A_EXTERNAL_ADVANTAGE_OBSERVED',
        'PACT_STAGE_A_EXTERNAL_PARITY','PACT_STAGE_A_EXTERNAL_DISADVANTAGE','PACT_STAGE_A_MIXED','PACT_STAGE_A_INCOMPLETE'))
    parser.add_argument('--scientific',required=True)
    parser.add_argument('--native-tests',type=Path,help='Native three-test receipt; default is B3R repair/tests.json')
    seal(parser.parse_args())
