#!/usr/bin/env python3
"""Seal an observed Stage-A outcome without changing the experiment or P0."""
import argparse
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, git, read, verify, write
from pact_oss_recovery import RECOVERY, DATA, MOUNT
from pact_oss_stage_a import STAGE, RAW, gate
from pact_oss_compare import implemented_point
from pact_oss_canonicalize import csv_write


def rss(path):
    if not path.exists():
        return None
    match=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',path.read_text())
    return int(match[1]) if match else None


def markdown_table(fields, rows):
    return '\n'.join(['| '+' | '.join(fields)+' |','| '+' | '.join(['---']*len(fields))+' |']+
        ['| '+' | '.join(str(row.get(field,'')) for field in fields)+' |' for row in rows])


def seal(args):
    gate()
    verify()
    rows=list(csv.DictReader((STAGE/'implemented_metrics.csv').open()))
    selected=[r for r in rows if r['selected']=='True']
    expected_selection=read(OUT/'stage_a/P0_SELECTION.json')['selection']
    for design in DESIGNS:
        data=[r for r in selected if r['design']==design]
        if {r['method'] for r in data}!={'B0','B1','B2','B3','P0'}:
            raise ValueError('Mandatory design/method records are missing')
        if {r['architecture_hash'] for r in data if r['method']=='P0'} != set(expected_selection[design]['roles']):
            raise ValueError('Frozen P0 selected identities differ')
    complete=bool(selected) and all(implemented_point(r) is not None and
        r['measured_H4']!='' and math.isfinite(float(r['measured_H4'])) and float(r['measured_H4'])>=0 for r in selected)
    if not complete and args.classification!='PACT_STAGE_A_INCOMPLETE':
        raise ValueError('Mandatory implemented measurements are missing; Stage A must remain incomplete')
    if complete and args.classification=='PACT_STAGE_A_INCOMPLETE':
        raise ValueError('All mandatory outcomes exist; select an evidence-based completed classification')
    tests={}
    for filename in ('protocol_tests.xml','pareto_tests.xml','result_join_tests_final.xml','scientific_question_tests_final.xml'):
        suite=ET.parse(RECOVERY/filename).getroot().find('testsuite')
        tests[filename]={k:int(suite.attrib.get(k,'0')) for k in ('tests','failures','errors','skipped')}
    if any(r['failures'] or r['errors'] for r in tests.values()):
        raise ValueError('Relevant unit tests failed')
    binaries={name:read(RECOVERY/'baselines'/name/'build_result.json') for name in ('B2_openroad_10176','B3_openroad_10666')}
    qualification={name:read(RECOVERY/'baselines'/name/'qualification.json') for name in binaries}
    counts={key:0 for key in ('new_routes','qualified_new_routes','new_extractions','new_simulations','qualified_new_measurements')}
    external={}
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
    for name,build in binaries.items():
        check=binding(build['binary']['path'])
        if check['sha256']!=build['binary_sha256']:
            raise ValueError('Generator binary changed')
        external['binary/'+name]=check
        runtime.append(dict(design='all',method='B2' if name.startswith('B2') else 'B3',stage='isolated_compilation',
            elapsed_seconds=read(build['build']['path'])['elapsed_seconds'],
            peak_RSS_kbytes=rss(RECOVERY/'baselines'/name/('build_resume1.container.resource.txt' if name.startswith('B2') else 'build.container.resource.txt')),
            reused=False,source=build['build']['path']))
        for item in qualification[name]['designs'].values():
            proof=read(item['proof']['path'])
            if proof['status']!='PASS' or not proof['endpoint_geometry_unchanged']:
                raise ValueError('Generator architecture qualification no longer passes')
        for design in DESIGNS:
            folder=RECOVERY/'baselines'/name/design
            execution=read(folder/'generate.execution.json')
            runtime.append(dict(design=design,method='B2' if name.startswith('B2') else 'B3',stage='architecture_generation',
                elapsed_seconds=execution['elapsed_seconds'],peak_RSS_kbytes=rss(folder/'generator.resource.txt'),
                reused=False,source=str(folder/'generate.execution.json')))
            scratch=DATA/name/design
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
            for key in ('manifest','summary','crosscheck','functional_log','spatial_bins','VCD','simulation_manifest'):
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
    csv_write(STAGE/'runtime.csv',list(runtime[0]),runtime)
    status=dict(timestamp=datetime.now(timezone.utc).isoformat(),stage_a=args.classification,scientific=args.scientific,
        engineering='PACT_OSS_BENCHMARK_COMPLETE' if complete else 'PACT_STAGE_A_INCOMPLETE',
        OSS_benchmark_complete=complete, P0_commit=read(OUT/'stage_a/P0_FREEZE.json')['commit'],
        P0_model_changed=False,P0_search_rerun=False,P0_selection_changed=False,B1_regenerated=False,
        Stage_B='NOT_STARTED_USER_SCOPE_STAGE_A_ONLY',P1_model_complete=False,
        Stage_B_scientific_prerequisite_satisfied=complete,Stage_B_execution_authorized_by_this_task=False,
        new_ATPG_runs=0,new_placement_runs=0,new_rootcause_runs=0,**counts,
        selected_method_records=len(selected),qualified_selected_method_records=sum(implemented_point(r) is not None for r in selected),
        remaining_blockers=[{key:r.get(key) for key in ('design','method','architecture_hash','status','failure_stage','failure_reason','route_report')}
            for r in selected if implemented_point(r) is None],
        tests=tests,unit_tests_passed=sum(t['tests']-t['skipped'] for t in tests.values()),
        repeated_unit_test_executions=8,total_current_recovery_unit_test_executions=sum(t['tests'] for t in tests.values())+8,
        fixed_backend=binding('/usr/bin/openroad'),
        original_incomplete_seal=binding(OUT/'stage_a/evidence_manifest.json'),
        original_P0_selection=binding(OUT/'stage_a/P0_SELECTION.json'),
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
    for name,proof in qualification.items():
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
    a3='\n'.join(f"- {design}: B3 versus B0 `{data['A3']['B3_vs_B0']}`; "
        f"B3 strictly dominates {sum(bool(p and p['left_dominates']) for p in data['A3']['B3_vs_predeclared_P0'])} "
        f"of {sum(p is not None for p in data['A3']['B3_vs_predeclared_P0'])} assessed predeclared P0 recommendations; "
        f"{sum(p is None for p in data['A3']['B3_vs_predeclared_P0'])} comparisons remain unassessed." for design,data in questions.items())
    report='\n\n'.join([
        '# Stage-A recovery outcome',
        f"Stage A: **{args.classification}**. Scientific classification: **{args.scientific}**. Engineering: **{status['engineering']}**.",
        'The previous incomplete seal is preserved. This version uses the same three seed-11 Nangate45 designs, K=2, existing FAN workload, clocks, constraints, common routing, OpenRCX and VCD measurement. P0 remains at `9d9103027918b1d4af2b209e6d36133ad82d4a4e`, candidate_stateful depth 3. No search, ATPG, placement, root-cause rerun or P1 change occurred.',
        '## Exact builds and environment',
        '\n'.join(f"- {name}: `{build['status']}`, source `{build['commit']}`, binary SHA256 `{build['binary_sha256']}`, path `{build['binary']['path']}`." for name,build in binaries.items()),
        'Immutable Ubuntu 22.04.5 image `openroad/orfs@sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e`; GCC/G++ 11.4.0, CMake 3.31.9, SWIG 4.3.0. Independently compiled/loaded Tcl 8.6.12 development pair. Both actual CMake resolutions: SWIG `/usr/local/bin/swig`, header `/usr/include/tcl8.6/tcl.h`, include directory `/usr/include/tcl8.6`, library `/usr/lib/x86_64-linux-gnu/libtcl8.6.so`. See `../protocol/build_environment_audit.md` and each `cmake_resolved_dependencies.json` for dependency versions, paths, hashes, warnings and isolation details.',
        'B2 executes native NN followed by endpoint-inclusive FF-origin Manhattan 2-Opt, maximum 30 iterations. B3 executes capacity-aware same-domain KMeans (maximum 100 iterations), NN, directed scan-pin 2-Opt with reversal correction and direction-preserving 3-Opt over 50 nearest candidates, until strict improvement stops. Its local cost excludes external endpoints. Compiled command probes and source hashes precede benchmark generation. No PR source was patched.',
        '## Architecture qualification',markdown_table(['method','design','lengths','canonical_SHA','qualification'],quals),
        'All generator outputs preserve exact FF inventory, domains, capacity, K=2, SI/SO legality and physical endpoint geometry. Canonicalization preserves FF assignment/order. Existing B0/B1 and all frozen P0 archive identities/roles are reused.',
        '## Implemented outcomes',markdown_table(['design','method','roles','architecture','status','wire_um','E','H4','H8','Pareto'],display),
        'Wire is the full routed scan-path net-length upper bound in micrometres. E is fF·transitions; H4/H8 are fF·transitions per bin/cycle, from the unchanged all_data measurement scope. Missing values remain unknown. These are activity proxies. Setup/hold WNS/TNS and DRC/topology/functional/every-FF transition qualification are in `stage_a/implemented_metrics.csv`; timing is the existing global-route stage.',
        f"New route attempts: {counts['new_routes']}; qualified new routes: {counts['qualified_new_routes']}; new extraction attempts with receipts: {counts['new_extractions']}; new simulation attempts with receipts: {counts['new_simulations']}; qualified new measurements: {counts['qualified_new_measurements']}. Reused outcomes are explicitly marked per architecture.",
        '## Comparison and A1–A5',
        'The predeclared balanced P0 representative is in `stage_a/method_comparison.csv`. The full retained archive view, including already implemented archive evidence, is in `stage_a/pareto_front.csv`. Unknown archive points are excluded from implemented Pareto calculations. `stage_a/pairwise_comparison.csv` retains every exact wire/E/H8 delta, with no weighted score or post-outcome matching tolerance.',
        'Answers and counterexamples for A1–A5 are recorded in `stage_a/scientific_questions.json`: unique P0 nondominated architecture and coordinate contributions; balanced P0 activity/cost deltas; B3 versus B0 and predeclared P0; every lower-wire external pair and its activity deltas; known implemented archive selection misses with explicit unknown scope and causal limits. No candidate is reselected using these outcomes.',
        markdown_table(list(answers[0]),answers),
        'A2: balanced P0 minus each external baseline; negative activity deltas indicate improvement. Physical-cost differences stay explicit.',
        markdown_table(list(activity_pairs[0]),activity_pairs) if activity_pairs else 'A2: unavailable measurements.',
        'A3: '+a3,
        'A4: the left method has lower wire, or equal wire for a tie. A positive E/H8 delta is a counterexample to automatic activity improvement from lower wire.',
        markdown_table(list(physical_pairs[0]),physical_pairs) if physical_pairs else 'A4: unavailable measurements.',
        'A5: counts above cover only qualified, already implemented archive evidence. Witness architectures and cost/activity deltas are in the question JSON. A known stronger archive point demonstrates a selection miss; this comparison cannot uniquely attribute that miss to predictor incompleteness. Unmeasured points are unknown, and the frozen recommendations remain unchanged.',
        '## Tests, evidence and scope',
        f"Relevant unit tests: {status['unit_tests_passed']} passed, 0 failed. Separate design integrations: three saved-B1 endpoint checks and six actual B2/B3 architecture qualifications. Independent SWIG/Tcl C and generated-module compile/link/load proofs passed; both compiled optimizer command probes passed. Original frozen/sealed integrity checks remain valid. The versioned evidence manifest binds compact artifacts, source snapshots, exact binaries and primary raw/historical evidence.",
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
        'This directory extends the canonical inventory with B2/B3, then records common-backend routing/measurement reuse and new attempts. '
        'Architecture identities and pre-route diagnostics were hash-bound before implementation. '
        'Missing outcomes remain unknown; the Pareto front uses exact unweighted dominance in wire/E/H8. '
        'Heavy primary data stays on authorized D: storage and is file-bound by the evidence manifest. Stage B/P1 is unstarted.\n')
    artifacts={str(p.relative_to(RECOVERY)):binding(p) for p in sorted(RECOVERY.rglob('*')) if p.is_file()}
    artifacts['../protocol/build_environment_audit.md']=binding(OUT/'protocol/build_environment_audit.md')
    scripts=[p for p in sorted((ROOT/'scripts').glob('pact_oss_*.py')) if p.name not in ('pact_oss_seal_incomplete.py',)]
    sources={str(p.relative_to(ROOT)):binding(p) for p in scripts}
    sources.update({str(p.relative_to(ROOT)):binding(p) for p in sorted((ROOT/'tests/unit').glob('test_oss_*.py'))})
    write(STAGE/'evidence_manifest.json',dict(timestamp=datetime.now(timezone.utc).isoformat(),
        status='SEALED',artifacts=artifacts,benchmark_sources=sources,external_artifacts=external,
        original_incomplete_seal=status['original_incomplete_seal'],immutable_image=read(RECOVERY/'toolchain_image.json')['Id'],
        raw_storage='Authorized D: storage; no build filesystem image hash substitutes for file-level evidence',
        Stage_B='NOT_STARTED_USER_SCOPE_STAGE_A_ONLY'))
    print('STAGE_A_EVIDENCE_SEALED',len(artifacts),len(sources),len(external),args.classification,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--classification',required=True,choices=('PACT_STAGE_A_EXTERNAL_ADVANTAGE_OBSERVED',
        'PACT_STAGE_A_EXTERNAL_PARITY','PACT_STAGE_A_EXTERNAL_DISADVANTAGE','PACT_STAGE_A_MIXED','PACT_STAGE_A_INCOMPLETE'))
    parser.add_argument('--scientific',required=True)
    seal(parser.parse_args())
