#!/usr/bin/env python3
"""Seal the observed B3R qualification failure without crossing its stage gate."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import shutil

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, git, read, write
from pact_oss_canonicalize import csv_write
from pact_oss_receiver_stage_a import (
    RECOVERY, PREVIOUS, DATA, STAGE, RAW, BASELINES, B3R_DISPLAY,
    checked, method_display, validate_baseline,
)
from pact_oss_receiver_generate import prerequisites, validate_runtime_identity
from pact_oss_receiver_complete import (
    test_accounting, native_test_accounting, reuse_accounting,
    contribution_accounting, compilation_runtime, markdown_table, rss,
)

FOLDER = BASELINES['B3R']['folder']
DIAGNOSIS = FOLDER / 's5378/diagnostics/independent_diagnosis.json'
STOP = 'B3R_GENERATED_SCAN_OUTPUT_TOPOLOGY_FAILED'


def validate_stop_state(qualification, diagnosis, build, repair, compiled, attempted, physical_files):
    """A failed partial output is neither a canonical baseline nor a full result."""
    expected = dict(status='FAILED', method='B3R', method_display=B3R_DISPLAY,
        failed_design='s5378', source_commit=repair['repair_commit_sha'],
        upstream_base_sha=repair['upstream_base_sha'], patch_sha256=repair['patch_sha256'],
        binary_sha256=build['binary_sha256'])
    for name, value in expected.items():
        if qualification.get(name) != value:
            raise ValueError('Observed stopped qualification identity differs: ' + name)
    if qualification.get('completed_designs') != {} or set(attempted) != {'s5378'}:
        raise ValueError('Stopped recovery must preserve one failed attempt and no qualified B3R design')
    if physical_files:
        raise ValueError('Physical work crossed the failed B3R qualification gate')
    validate_runtime_identity(compiled, build, repair)
    evidence = dict(status='SOURCE_TOPOLOGY_BLOCKER_STOPPED', method='B3R', method_display=B3R_DISPLAY,
        design='s5378', upstream_base_sha=repair['upstream_base_sha'],
        repair_commit_sha=repair['repair_commit_sha'], patch_sha256=repair['patch_sha256'],
        binary_sha256=build['binary_sha256'], topology_qualification='FAIL',
        actual_chain_lengths=[90, 89], actual_terminal_nets=['n2510gat', 'n707gat'],
        fixed_SO_terminates_generated_chains=False, FF_functional_placement_unchanged=True,
        additional_source_patch_applied=False, downstream_physical_runs=0)
    for name, value in evidence.items():
        if diagnosis.get(name) != value:
            raise ValueError('Independent stopped-topology diagnosis differs: ' + name)
    return {design: ('FAILED_SCAN_OUTPUT_TOPOLOGY' if design == 's5378' else 'NOT_ATTEMPTED_AFTER_STOP')
            for design in DESIGNS}


def historical_integrity():
    from pact_oss_verify import audit as original_audit
    original_audit()
    previous = read(PREVIOUS / 'stage_a/evidence_manifest.json')
    count = 0
    for group in ('artifacts', 'benchmark_sources', 'external_artifacts'):
        for item in previous[group].values():
            checked(item)
            count += 1
    if count != 530:
        raise ValueError('Prior recovery seal count differs from the preserved milestone')
    return dict(status='PASS', previous_recovery_bindings=count, original_frozen_bindings=454,
        original_sealed_bindings=122, original_canonical_architectures=24,
        previous_recovery_seal=binding(PREVIOUS / 'stage_a/evidence_manifest.json'),
        original_incomplete_seal=binding(OUT / 'stage_a/evidence_manifest.json'))


def validate_saved_observation(observation, diagnosis):
    after = observation['after']
    traces = after['traces']
    if (observation.get('optimizer_executed') is not False
            or observation.get('connectivity_modified') is not False
            or observation.get('FF_inventory_placement_functional_unchanged') is not True
            or after['FF_count'] != 179 or len(traces) != 2):
        raise ValueError('Saved-ODB diagnostic scope or FF invariants differ')
    if after['sha256'] != diagnosis['generated_ODB']['sha256']:
        raise ValueError('Saved-ODB observation describes a different generated database')
    names = []
    for ci, (trace, size, tail) in enumerate(zip(traces, (90, 89), ('n2510gat', 'n707gat'))):
        if (trace['chain'] != ci or trace['ff_count'] != size or len(trace['ff_order']) != size
                or trace['error'] != 'CANNOT_TRACE_FIXED_SI_SO'
                or trace['terminal_net']['name'] != tail or trace['terminal_net']['ports']):
            raise ValueError('Saved-ODB scan-tail evidence differs from the observed blocker')
        names.extend(trace['ff_order'])
    if len(set(names)) != 179 or set(names) != set(after['cells']):
        raise ValueError('Saved-ODB paths do not cover every FF exactly once')


def check_blocked_evidence():
    build, repair = prerequisites()
    import pact_oss_receiver_build as receiver_build
    receiver_build.gate()
    if (receiver_build.run_git('rev-parse', 'HEAD').strip() != repair['repair_commit_sha']
            or receiver_build.run_git('status', '--short')):
        raise ValueError('Stopped derivative differs from its immutable receiver-only commit')
    qualification = read(FOLDER / 'qualification.json')
    checked(qualification['compiled_behavior'])
    compiled = read(qualification['compiled_behavior']['path'])
    diagnosis = read(DIAGNOSIS)
    attempted = {design for design in DESIGNS if (FOLDER / design / 'generate.execution.json').exists()}
    physical = [str(path) for path in RAW.rglob('*') if path.is_file()] if RAW.exists() else []
    states = validate_stop_state(qualification, diagnosis, build, repair, compiled, attempted, physical)
    for design in DESIGNS:
        if (FOLDER / design / 'canonical.json').exists():
            raise ValueError('A failed B3R output cannot be sealed as a canonical architecture')
    execution = read(FOLDER / 's5378/generate.execution.json')
    checked(execution['log'])
    if execution['returncode'] == 0:
        raise ValueError('Failed architecture attempt unexpectedly reports success')
    text = (FOLDER / 's5378/generate.log').read_text()
    if '[INFO DFT-0016] Optimized 2 scan chain(s).' not in text or 'Cannot faithfully trace native SI/SO connectivity' not in text:
        raise ValueError('Observed generation failure log differs from the endpoint stop')
    for name in ('generated_ODB', 'generated_verilog', 'saved_ODB_observation', 'read_execution'):
        checked(diagnosis[name])
    if read(diagnosis['read_execution']['path'])['returncode'] != 0:
        raise ValueError('Independent saved-ODB read did not succeed')
    validate_saved_observation(read(diagnosis['saved_ODB_observation']['path']), diagnosis)
    for item in diagnosis.get('source_evidence', {}).values():
        checked(item)
    checked(build['actual_cmake_resolution'])
    actual_resolution = read(build['actual_cmake_resolution']['path'])
    if actual_resolution['status'] != 'PASS' or actual_resolution['source_version'] != repair['repair_commit_sha']:
        raise ValueError('Final CMake prerequisite resolution has not passed')
    checked(actual_resolution['actual_cmake_cache'])
    return dict(build=build, repair=repair, qualification=qualification, compiled=compiled,
        diagnosis=diagnosis, design_states=states, historical=historical_integrity())


def unknown_metrics(previous):
    rows = []
    for original in previous:
        row = dict(original)
        if row['method'] == 'B3':
            row.update(method='B3R', architecture_hash='',
                status='FAILED_SCAN_OUTPUT_TOPOLOGY' if row['design']=='s5378' else 'NOT_ATTEMPTED_AFTER_STOP')
        else:
            row['status'] = 'NOT_IMPORTED_AFTER_B3R_QUALIFICATION_STOP'
        row['method_display'] = method_display(row['method'])
        for name in ('routed_scan_path_cost_um', 'measured_E', 'measured_H4', 'measured_H8'):
            row[name] = None
        row['Pareto'] = 'UNASSESSABLE'
        rows.append(row)
    if len(rows)!=19 or {row['method'] for row in rows}!={'B0','B1','B2','B3R','P0'}:
        raise ValueError('Stopped method table differs from the fixed proposed method set')
    return rows


def seal():
    if (STAGE/'evidence_manifest.json').exists() or (RECOVERY/'FINAL_REPORT.md').exists():
        raise ValueError('Preserve the existing blocked recovery seal and report')
    observed = check_blocked_evidence()
    build, repair = observed['build'], observed['repair']
    b2 = validate_baseline('B2', BASELINES['B2'])
    tests = test_accounting()
    superseded_tests = RECOVERY/'blocked_harness_attempt1_superseded.json'
    if superseded_tests.exists():
        superseded = read(superseded_tests)
        for key in ('XML', 'first_execution', 'initial_fixture_snapshot', 'corrected_fixture', 'successful_XML'):
            checked(superseded[key])
        tests['superseded_fixture_attempt'] = dict(receipt=binding(superseded_tests),
            tests=superseded['tests'], failed=superseded['failed'], passed=superseded['passed'],
            reason=superseded['reason'])
        tests['executions_including_superseded_fixture_attempt'] = tests['executions'] + superseded['tests']
    native = native_test_accounting(FOLDER/'repair/tests.json')
    native['scope'] = ('Three native DFT tests passed on the preserved precommit validation binary. '
        'The final immutable binary passes its compiled-command probe but fails s5378 architecture qualification; '
        's9234/s15850 are not attempted.')
    reuse = reuse_accounting()
    contribution = contribution_accounting(RECOVERY/'upstream/github_contribution.json')
    if contribution['PR_opened']:
        details = contribution['details']
        if details['commit_sha']!=repair['repair_commit_sha'] or details['base_sha']!=repair['upstream_base_sha'] or details['patch_sha256']!=repair['patch_sha256']:
            raise ValueError('Upstream contribution differs from the benchmark receiver repair')
    description_edit = RECOVERY/'upstream/pull_request_commit_scope_edit.json'
    if description_edit.exists():
        edited = read(description_edit)
        for key in ('revised_body', 'metadata_before', 'metadata_after', 'helper', 'previous_edit_receipt'):
            checked(edited[key])
        if (edited['status'] != 'UPDATED_AND_VERIFIED' or edited['updated_fields'] != ['body']
                or edited['head_sha_after'] != repair['repair_commit_sha']
                or edited['base_sha_after'] != repair['upstream_base_sha']
                or edited['commit_amended'] or edited['source_patch_changed']):
            raise ValueError('PR wording update changed the immutable receiver repair')
        contribution['latest_description_edit'] = binding(description_edit)
        contribution['description_scope'] = 'Compilation issue and two receiver qualifications only'
    amendment = OUT/'protocol/amendment_B3_source_repair.md'
    if not amendment.exists():
        raise ValueError('The factual receiver-repair amendment is required before sealing')
    known=list(csv.DictReader((PREVIOUS/'stage_a/architecture_index.csv').open()))
    ff_rows=list(csv.DictReader((PREVIOUS/'stage_a/architecture_manifest.csv').open()))
    if len(known)!=27 or len(ff_rows)!=8252 or any(row['method'] in ('B3','B3R') for row in known):
        raise ValueError('Partial canonical inventory differs or fabricates failed B3R')
    for row in known:
        row['method_display']=method_display(row['method'])
    for row in ff_rows:
        row['method_display']=method_display(row['method'])
    metrics=unknown_metrics(list(csv.DictReader((PREVIOUS/'stage_a/implemented_metrics.csv').open())))
    csv_write(STAGE/'architecture_index.csv',list(known[0]),known)
    csv_write(STAGE/'architecture_manifest.csv',list(ff_rows[0]),ff_rows)
    csv_write(STAGE/'implemented_metrics.csv',list(metrics[0]),metrics)
    csv_write(STAGE/'method_comparison.csv',list(metrics[0]),[row for row in metrics if row['representative']=='True'])
    csv_write(STAGE/'pareto_front.csv',list(metrics[0]),metrics)
    shutil.copy2(PREVIOUS/'stage_a/pre_route_metrics.csv',STAGE/'pre_route_metrics.csv')
    write(STAGE/'scientific_questions.json',{design:{question:dict(status='UNASSESSABLE',
        reason='Mandatory B3R canonical qualification failed; no physical outcomes were imported or executed')
        for question in ('A1','A2','A3','A4','A5')} for design in DESIGNS})
    b2_build=read(BASELINES['B2']['folder']/'build_result.json')
    runtime=compilation_runtime('B2',b2_build)+compilation_runtime('B3R',build)
    attempt=read(FOLDER/'s5378/generate.execution.json')
    runtime.append(dict(design='s5378',method='B3R',stage='failed_architecture_qualification',
        elapsed_seconds=attempt['elapsed_seconds'],peak_RSS_kbytes=rss(DATA/BASELINES['B3R']['name']/'s5378/generator.resource.txt'),
        reused=False,source=str(FOLDER/'s5378/generate.execution.json')))
    for row in runtime:
        row['method_display']=method_display(row['method'])
    csv_write(STAGE/'runtime.csv',list(runtime[0]),runtime)
    status=dict(timestamp=datetime.now(timezone.utc).isoformat(),stage_a='PACT_STAGE_A_INCOMPLETE',
        scientific='PACT_BENCHMARK_INCONCLUSIVE',engineering='PACT_STAGE_A_INCOMPLETE',OSS_benchmark_complete=False,
        stop_condition=STOP,blocker=binding(DIAGNOSIS),B3R='BUILD_PASS_COMMAND_PASS_ARCHITECTURE_QUALIFICATION_FAILED',
        B3R_method_display=B3R_DISPLAY,B3R_design_qualification=observed['design_states'],
        B3R_upstream_base_sha=repair['upstream_base_sha'],B3R_repair_commit_sha=repair['repair_commit_sha'],
        B3R_patch_sha256=repair['patch_sha256'],B3R_binary_sha256=build['binary_sha256'],
        B2='EXACT_PINNED_BUILD_AND_ALL_THREE_QUALIFICATIONS_REUSED_UNCHANGED',B3='EXACT_PINNED_COMPILATION_FAILURE_PRESERVED',
        proposed_methods=['B0','B1','exact B2',B3R_DISPLAY,'frozen P0'],
        qualified_canonical_architectures=len(known),ordered_FF_records=len(ff_rows),selected_method_records=len(metrics),
        qualified_selected_method_records=0,B3R_canonical_architectures=0,new_architecture_generation_attempts=1,
        new_architecture_generations=0,new_routes=0,new_extractions=0,new_simulations=0,new_ATPG_runs=0,
        new_placement_runs=0,new_rootcause_runs=0,P0_commit=read(OUT/'stage_a/P0_FREEZE.json')['commit'],
        P0_model_changed=False,P0_search_rerun=False,P0_selection_changed=False,B1_regenerated=False,
        additional_source_patch_applied=False,downstream_physical_outcomes_imported=False,
        Stage_B='NOT_STARTED_STAGE_A_STOP_CONDITION',Stage_C='NOT_STARTED_STAGE_A_STOP_CONDITION',P1_model_complete=False,
        Stage_B_scientific_prerequisite_satisfied=False,Stage_B_execution_authorized_by_this_task=False,
        tests=tests,unit_tests_passed=tests['distinct_passed'],new_adapter_unit_tests_passed=tests['current']['tests']-tests['current']['skipped'],
        native_DFT_regression_tests=native,native_DFT_regression_tests_passed=3,
        cache_reuse_preflight=reuse,upstream_contribution=contribution,
        fixed_backend=binding('/usr/bin/openroad'),original_P0_selection=binding(OUT/'stage_a/P0_SELECTION.json'),
        original_incomplete_seal=observed['historical']['original_incomplete_seal'],
        previous_recovery_seal=observed['historical']['previous_recovery_seal'],historical_integrity=observed['historical'],
        pre_route_scope='Original 24-architecture diagnostics preserved; no new scoring or B3R canonical output',
        Git_HEAD_before_commit=git('rev-parse','HEAD'),Git_status_before_commit=git('status','--short'))
    write(STAGE/'status.json',status)
    qualification_rows=[dict(design=design,method='B2',chain_lengths='/'.join(map(str,b2['designs'][design]['chain_lengths'])),status='PASS') for design in DESIGNS]
    qualification_rows += [dict(design=design,method='B3R',chain_lengths='unavailable; no qualified canonical output',status=state) for design,state in observed['design_states'].items()]
    report='\n\n'.join([
        '# Receiver-repair recovery stopped at architecture qualification',
        '**PACT_STAGE_A_INCOMPLETE**. Scientific classification: **PACT_BENCHMARK_INCONCLUSIVE**.',
        'The proposed method set remains B0 / B1 / exact B2 / '+B3R_DISPLAY+' / frozen P0. B3R builds and its compiled-command probe passes, but its actual s5378 output fails fixed SI/SO topology qualification. This is an additional source-behavior blocker beyond the authorized compile repair. No further source repair or endpoint adaptation is applied. s9234 and s15850 are not attempted after the stop.',
        '## Exact repair, builds and validation',
        f"Exact B2 remains `{b2_build['commit']}`, binary SHA256 `{b2_build['binary_sha256']}`, with all three existing qualifications unchanged. Exact B3 `{repair['upstream_base_sha']}` retains its failed build as provenance. B3R is repair commit `{repair['repair_commit_sha']}`, patch SHA256 `{repair['patch_sha256']}`, final binary SHA256 `{build['binary_sha256']}` at `{build['binary']['path']}`. Only the two missing `db_network_->` receiver qualifications and their immediate clang-format wrapping differ. Algorithm sources, ordering rules, KMeans/NN/directed 2-Opt/3-Opt costs, parameters and intended endpoint semantics are unchanged.",
        'Actual final CMake resolution passes: SWIG 4.3.0 `/usr/local/bin/swig`; Tcl development header 8.6.12 `/usr/include/tcl8.6/tcl.h`, include `/usr/include/tcl8.6`, and runtime-linked library 8.6.12 `/usr/lib/x86_64-linux-gnu/libtcl8.6.so`; interpreter `/usr/bin/tclsh`. Independent C compile/link/runtime and SWIG-module compile/link/load proofs precede configuration. A Tcl interpreter alone was not accepted. The exact cache, paths, hashes and versions are bound in `baselines/B3R_openroad_10666_repaired/configure_final.dependency_resolution.json`; GCC/G++ 11.4.0 and CMake 3.31.9 run in the preserved immutable Ubuntu 22.04.5 toolchain image.',
        markdown_table(['method','stage','elapsed_seconds','peak_RSS_kbytes','reused'],runtime),
        f"Native DFT tests: three PASS (`scan_opt_sky130`, `place_sort_sky130`, `one_cell_sky130`) on the preserved precommit validation binary `{native['binary_at_test_execution']['sha256']}`. No new upstream test was added. The final immutable binary's command probe confirms native KMeans (100 iterations), NN, directed 2-Opt and direction-preserving 3-Opt over 50 nearest candidates, with external endpoints excluded from local optimization cost. Command availability and small regressions do not establish all-design benchmark qualification.",
        '## Observed qualification blocker',
        'The actual command log reports spatial preclustering of 179 cells across two chains (capacity 90), then `Optimized 2 scan chain(s).` The frozen adapter subsequently raises `Cannot faithfully trace native SI/SO connectivity`. A separate read-only saved-ODB inspection and an independent generated-Verilog graph find internal FF paths of 90 and 89 ending on `n2510gat` and `n707gat` without the fixed scan-output ports. The fixed SO outputs remain attached to interior Q nets. FF inventory, master, position, orientation and functional D/CK connections remain unchanged. The richer diagnosis also records any metadata-versus-ODB order discrepancy separately. The failed generated ODB/Verilog are preserved as raw diagnostic evidence; neither is canonicalized, translated into a qualifying architecture, or physically implemented.',
        markdown_table(['design','method','chain_lengths','status'],qualification_rows),
        'The partial canonical inventory contains only the original 24 B0/B1/P0 records and three exact-B2 records: 27 architectures and 8,252 ordered FF rows. B3R contributes zero qualified canonical architectures. The seven predeclared P0 selected identities and roles remain frozen at `9d9103027918b1d4af2b209e6d36133ad82d4a4e`, candidate_stateful depth 3; B1 is not regenerated.',
        '## Physical outcomes and scientific scope',
        'New routing, extraction, simulation, ATPG, placement and root-cause runs: **0**. No historical physical results are imported past the failed mandatory qualification gate. All 19 proposed selected-method records retain unknown routed wire, E, H4 and H8; all Pareto and representative rows are unassessable. A1–A5 remain unassessed. This incomplete attempt establishes no P0 advantage, parity or disadvantage and no valid B3R comparison.',
        f"Cache eligibility preflight verified {reuse['historical_binding_checks']} historical bindings, with {reuse['eligible_route_candidates']} eligible route candidates and {reuse['excluded_route_candidates']} preserved ineligible phase0c caches. The excluded caches used four threads and lacked explicit NUM_CORES=2; no grandfathering or rerouting occurred after the qualification stop. The fixed backend and current ORFS `{reuse['environment']['ORFS_commit']}` are verified, with clean tracked ORFS files.",
        '## Upstream contribution, evidence and Git',
        f"The minimal compile repair was submitted as [{contribution['PR_URL']}]({contribution['PR_URL']}) against `{contribution['target_repository']}:{contribution['target_branch']}`, with the same immutable repair commit used locally, and relates to original PR #10666. CI at capture: `{contribution['CI_status_at_capture']}`; passing CI, review or merge is not claimed. The benchmark does not wait for upstream review. The additional topology diagnosis is documented locally; no additional source fix or upstream comment is sent.",
        f"Final relevant unit cases: {tests['distinct_passed']} distinct PASS, zero unresolved failures ({tests['executions']} valid-suite executions including recorded reruns). Of these, {tests['historical']['distinct_passed']} historical cases ({tests['historical']['executions']} executions) are reused; {tests['current']['tests']-tests['current']['skipped']} new receiver cases are passed. An initial synthetic test fixture omitted its required commit field: that superseded 27-case attempt had five failures and 22 passes. Its XML, execution, initial fixture and corrected successful 27-case run are preserved separately in `blocked_harness_attempt1_superseded.json`; they do not change benchmark output or source. Three native DFT regressions, the compiled command probe, three unchanged exact-B2 qualifications, and one failed B3R s5378 attempt are counted separately. Original checks verify 454 frozen bindings, 122 sealed bindings and 24 original canonical identities; the prior recovery's 530 file bindings remain intact.",
        'The new seal binds compact artifacts, source snapshots, the exact patch, provisional/final binaries, prerequisite and build receipts, failed raw ODB/Verilog and file-level D: data. The historical seals and user edits remain preserved. The formal [source-repair amendment](../protocol/amendment_B3_source_repair.md) records the compile-only derivative and its independent qualification stop. A separate milestone commit receipt will record the actual recovery commit without rewriting this seal.',
        'Stage B/P1 and Stage C remain unstarted. Stage A is not complete or sealed as a completed benchmark; this is a sealed incomplete recovery attempt. Continuing would require a separately authorized source-behavior change with new provenance and qualification.',
    ])+'\n'
    (RECOVERY/'FINAL_REPORT.md').write_text(report)
    (STAGE/'README.md').write_text('# Incomplete receiver-repair recovery\n\n'
        'B3R builds, then fails actual s5378 SI/SO topology qualification. s9234/s15850 are unattempted. '
        'See [report](../FINAL_REPORT.md). The 27 known canonical architectures exclude B3R; all physical outcomes are unknown. '
        'No additional source patch or Stage-B/P1 work occurred.\n')
    external={'B3R_final_binary':checked(build['binary']), 'B3R_validation_binary':checked(native['binary_at_test_execution']),
        'B2_exact_binary':checked(b2_build['binary'])}
    source=Path(repair['source_path'])
    for relative in read(FOLDER/'source_manifest.json')['pinned_source_blobs_checked']:
        path=source/relative
        if path.is_file() and not path.is_symlink():
            external['B3R/source/'+relative]=binding(path)
    for path in sorted(DATA.rglob('*')):
        if path.is_file() and path.name!='build-storage.ext4':
            external['receiver_raw/'+str(path.relative_to(DATA))]=binding(path)
    artifacts={str(path.relative_to(RECOVERY)):binding(path) for path in sorted(RECOVERY.rglob('*')) if path.is_file()}
    artifacts['../protocol/amendment_B3_source_repair.md']=binding(amendment)
    sources={str(path.relative_to(ROOT)):binding(path) for path in sorted((ROOT/'scripts').glob('pact_oss_*.py'))}
    sources.update({str(path.relative_to(ROOT)):binding(path) for path in sorted((ROOT/'tests/unit').glob('test_oss_*.py'))})
    write(STAGE/'evidence_manifest.json',dict(timestamp=datetime.now(timezone.utc).isoformat(),status='SEALED_INCOMPLETE',
        classification='PACT_STAGE_A_INCOMPLETE',scientific='PACT_BENCHMARK_INCONCLUSIVE',stop_condition=STOP,
        artifacts=artifacts,benchmark_sources=sources,external_artifacts=external,
        original_incomplete_seal=status['original_incomplete_seal'],previous_recovery_seal=status['previous_recovery_seal'],
        Stage_B=status['Stage_B'],storage='Authorized D: data; file-level bindings exclude the mutable filesystem image'))
    print('B3R_QUALIFICATION_BLOCKED_RECOVERY_SEALED',len(artifacts),len(sources),len(external),flush=True)


if __name__=='__main__':
    seal()
