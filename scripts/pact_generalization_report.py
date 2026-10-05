#!/usr/bin/env python3
"""Assemble measured evidence without treating unexecuted searches as outcomes."""
import argparse
import csv
import io
import json
from pathlib import Path
import re
import subprocess
from pact_generalization import ROOT,OUT,CORE,binding,now,read,sha,write
from pact_generalization_infrastructure import RUN,DESIGNS,external_binding
from pact_generalization_measure import selected
from pact_generalization_physical import select_reference,prep

ATTEMPTS=('sized_scan_cells_repaired','buffer_traversal_repaired','functional_identity_repaired','runtime_paths_repaired')
SCALABILITY_FIELDS=('design','FF_count','chain_count','ATPG_pattern_count','target_fault_count',
    'epsilon','seed','total_exact_candidate_evaluations','accepted_moves','rejected_moves',
    'archive_insertions','stagnation_events','restart_count','wall_seconds','CPU_seconds',
    'peak_RSS_KiB','evaluations_per_second','evaluator_seconds','solver_overhead_seconds',
    'candidate_selection_seconds','physical_qualification_seconds')


def latest_gate(design):
    for attempt in ATTEMPTS:
        path=OUT/f'repair_attempts/{attempt}/physical/{design}/presearch_qualification.json'
        if path.exists():
            return attempt,path,read(path)
    return None,None,None


def resources(path):
    text=Path(path).read_text()
    def number(label):
        match=re.search(re.escape(label)+r':\s*([0-9.]+)',text)
        return float(match[1]) if match else None
    user,system=number('User time (seconds)'),number('System time (seconds)')
    return dict(CPU_seconds=user+system if user is not None and system is not None else None,
        peak_RSS_KiB=number('Maximum resident set size (kbytes)'))


def collect():
    benchmark=read(OUT/'manifests/generalization_benchmark_manifest.json')
    outcomes=[]
    refs=[]
    measured=[]
    for design in benchmark['designs']:
        name=design['design']
        attempt,path,gate=latest_gate(name)
        row=dict(design=name,FF_count=design['FF_count'],chain_count=2,
            ATPG_pattern_count=design['ATPG_pattern_count'],target_fault_count=design['ATPG_target_fault_count'],
            PACT_status='PACT_EXECUTION_BLOCKED',PACT_searches_executed=0,
            primary_candidate=None,alternative_candidates=[],primary_activity_category=None,
            solver_runtime_seconds=None,exact_evaluation_count=None)
        if gate and gate['status']=='INFRASTRUCTURE_QUALIFIED':
            ref=selected(name)
            records_path=OUT/f'repair_attempts/{attempt}/baselines/{name}_references.json'
            records=read(records_path)['records']
            selection_records=[]
            for item in records:
                compatible=dict(item)
                if 'generator_status' not in item and item['status']=='QUALIFIED':
                    if item['method']!='B0':
                        generation=Path(item['architecture']['path']).parents[1]/'generation/execution.json'
                        assert read(generation)['exit_code']==0 and not read(generation)['timed_out']
                    compatible['generator_status']='PASS'
                selection_records.append(compatible)
            winner=select_reference(selection_records)
            assert winner['architecture_hash']==ref['architecture_hash'] and winner['method']==ref['method']
            assert sha(ref['architecture']['path'])==ref['architecture']['sha256']
            assert all(value=='PASS' for value in gate['gates'].values())
            row.update(infrastructure_status='INFRASTRUCTURE_QUALIFIED',selected_reference=ref['method'],
                reference_attempt=attempt,qualification=binding(path),
                failure_class='TOOL_BUG',blocker_subtype='UNSEEN_INPUT_INITIALIZATION',
                reason='Frozen Stage-B requires an absent historical P0 warm start; no new-design construction rule is frozen')
            reference_path=OUT/f'repair_attempts/{attempt}/baselines/{name}_selected.json'
            compact={key:ref[key] for key in ('design','method','architecture','architecture_hash',
                'routed_scan_wirelength_um','timing','DRC','status','source_revision','provenance','frozen_utc')}
            compact.update(qualification=binding(path),selection_receipt=binding(reference_path),
                all_references=binding(records_path),reference_attempt=attempt,
                correctness=ref['correctness'],
                methods=[{key:r.get(key) for key in ('method','status','generator_status',
                    'routed_scan_wirelength_um','failure_class','error')} for r in selection_records])
            export_gate=OUT/f'physical/{name}/reference_export_gates/{ref["method"]}/receipt.json'
            if export_gate.exists():
                assert read(export_gate)['status']=='PASS'
                compact['functional_and_FF_placement_qualification']=binding(export_gate)
            refs.append(compact)
            folder=OUT/f'physical/{name}/reference_measurement'
            receipt=folder/('result_recovered.json' if (folder/'result_recovered.json').exists() else 'result.json')
            if receipt.exists():
                result=read(receipt)
                row['reference_measurement_status']=result['status']
                if result['status']=='FAILED':
                    row['reference_measurement_failure']=dict(failure_class=result['failure_class'],
                        receipt=binding(receipt),wall_seconds=result.get('execution',{}).get('wall_seconds'),
                        localized_stage=read(OUT/f'failures/{name}_measurement_localization.json').get('localized_stage')
                            if (OUT/f'failures/{name}_measurement_localization.json').exists() else None)
                if result['status']=='QUALIFIED':
                    assert result['selected_reference']==ref['method']
                    assert sha(result['summary']['path'])==result['summary']['sha256']
                    route=read(ref['provenance']['path'])
                    statistics=ref['correctness']['statistics']
                    measured.append(dict(design=name,candidate=ref['method'],method=ref['method'],
                        record_kind='NEW_EXTERNAL_REFERENCE_ONLY',FF_count=design['FF_count'],
                        chain_count=2,ATPG_pattern_count=design['ATPG_pattern_count'],
                        target_faults=statistics['total'],detected_faults=statistics['detected'],
                        fault_coverage=100*statistics['detected']/statistics['total'],
                        FAN_reported_coverage=statistics['coverage'],architecture_hash=ref['architecture_hash'],
                        routed_scan_wirelength_um=ref['routed_scan_wirelength_um'],
                        E=result['E'],H4=result['H4'],H8=result['H8'],
                        WNS=ref['timing']['setup_wns_ns'],hold_WNS=ref['timing']['hold_wns_ns'],
                        DRC_count=0,qualification_status='QUALIFIED',correctness_status='PASS',
                        gates=dict(gate['gates'],functional='PASS',FF_transition_crosscheck='PASS'),
                        deltas_percent=dict(E=0.,H4=0.,H8=0.,routed_scan_wirelength_um=0.),
                        solver_runtime_seconds=None,exact_evaluation_count=None,
                        physical_runtime_seconds=route['route_wall_seconds']+result['wall_seconds'],
                        route_wall_seconds=route['route_wall_seconds'],measurement_wall_seconds=result['wall_seconds'],
                        measurement_resources=resources(folder/'resources.txt'),
                        metric_scope=read(CORE/'canonical_results.json')['records'][0]['metric_scope'],
                        fault_identity_scope=read(CORE/'canonical_results.json')['records'][0]['fault_identity_scope'],
                        uncollapsed_member_identity_equivalence='NOT_ENUMERATED',
                        provenance=dict(reference=binding(reference_path),measurement=binding(receipt),
                            measurement_summary=result['summary'],faults=ref['correctness']['faults'])))
            else:
                row['reference_measurement_status']='NOT_STARTED_CAMPAIGN_STOPPED'
                row['reference_measurement_reason']='Further full simulations stopped after the measured s38417 resource limit; no partial/proxy activity substituted'
        else:
            preparation=prep(name)
            row.update(infrastructure_status=preparation['status'],
                failure_class=preparation.get('failure_class','PHYSICAL_BACKEND_FAIL'),
                reason=preparation.get('error','Reference qualification has not completed'))
            if gate:
                row.update(infrastructure_status=gate['status'],reason=gate.get('error',row['reason']),
                    qualification=binding(path))
            failures=[]
            for attempt_name in ATTEMPTS:
                failure=OUT/f'repair_attempts/{attempt_name}/failures/{name}_reference_preparation.json'
                if failure.exists():
                    failures.append(binding(failure))
                    row['reason']=read(failure)['error']
                    row['failure_class']=read(failure)['failure_class']
                    break
            row['failures']=failures
        outcomes.append(row)
    return outcomes,refs,measured


def canonical_reference_records(refs,measured,outcomes):
    """Include routed/extracted references with explicitly unavailable activity."""
    activities={r['design']:r for r in measured}
    outcome_by_name={r['design']:r for r in outcomes}
    records=[]
    for reference in refs:
        name=reference['design']
        if name in activities:
            records.append(activities[name])
            continue
        outcome=outcome_by_name[name]
        statistics=reference['correctness']['statistics']
        route=read(reference['provenance']['path'])
        records.append(dict(design=name,candidate=reference['method'],method=reference['method'],
            record_kind='NEW_ROUTED_EXTRACTED_REFERENCE_ACTIVITY_UNAVAILABLE',
            FF_count=outcome['FF_count'],chain_count=2,ATPG_pattern_count=outcome['ATPG_pattern_count'],
            target_faults=statistics['total'],detected_faults=statistics['detected'],
            fault_coverage=100*statistics['detected']/statistics['total'],
            FAN_reported_coverage=statistics['coverage'],architecture_hash=reference['architecture_hash'],
            routed_scan_wirelength_um=reference['routed_scan_wirelength_um'],E=None,H4=None,H8=None,
            WNS=reference['timing']['setup_wns_ns'],hold_WNS=reference['timing']['hold_wns_ns'],
            DRC_count=reference['DRC'],qualification_status='ROUTED_EXTRACTED_REFERENCE_ACTIVITY_UNAVAILABLE',
            correctness_status='FAN_PASS; ACTIVITY_FF_TRANSITION_CHECK_UNAVAILABLE',
            activity_status=outcome['reference_measurement_status'],
            gates=dict(topology='PASS',functional='PASS',FF_placement='PASS',routing='PASS',
                extraction='PASS',timing='PASS',DRC='PASS',FAN='PASS',FF_transition_crosscheck='UNAVAILABLE'),
            deltas_percent=dict(E=None,H4=None,H8=None,routed_scan_wirelength_um=0.),
            solver_runtime_seconds=None,exact_evaluation_count=None,
            route_wall_seconds=route['route_wall_seconds'],measurement_wall_seconds=None,
            metric_scope=read(CORE/'canonical_results.json')['records'][0]['metric_scope'],
            fault_identity_scope=read(CORE/'canonical_results.json')['records'][0]['fault_identity_scope'],
            uncollapsed_member_identity_equivalence='NOT_ENUMERATED',
            provenance=dict(reference=reference['selection_receipt'],
                functional_and_FF_placement=reference['functional_and_FF_placement_qualification'],
                faults=reference['correctness']['faults'])))
    return records


def preflight(outcomes,refs,measured):
    gates_path=OUT/'physical/reference_export_gates.json'
    gates=read(gates_path)
    assert gates['status']=='PASS' and len(gates['records'])==4*len(refs)==24
    for item in gates['records']:
        assert item['status']=='PASS'
        receipt_path=ROOT/item['receipt']['path'].removeprefix('repo://')
        assert sha(receipt_path)==item['receipt']['sha256']
        receipt=read(receipt_path)
        assert receipt['status']=='PASS' and receipt['FF_placement']=='exact'
        for name in ('topology_verification.json','functional_verification.json'):
            assert sha(receipt_path.parent/name)==receipt['outputs'][name]['sha256']
        assert all(receipt[key]==0 for key in ('routing_executions','ATPG_executions',
            'simulation_executions','PACT_search_executions'))
    new_rows=canonical_reference_records(refs,measured,outcomes)
    assert len(outcomes)==8 and len(new_rows)==6 and len(measured)==4
    assert {r['design'] for r in new_rows}=={r['design'] for r in refs}
    assert sum(r['E'] is None for r in new_rows)==2
    assert all(r['PACT_searches_executed']==0 for r in outcomes)
    original=read(CORE/'canonical_results.json')
    for row in original['records']+new_rows:
        assert set(('E','H4','H8','routed_scan_wirelength_um'))<=set(row['deltas_percent'])
    return new_rows


def csv_text(fields,rows):
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=fields,lineterminator='\n',extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def table_fields(fields):
    additional=('correctness_status','solver_runtime_seconds','exact_evaluation_count','record_scope',
        'qualification_status','activity_status','PACT_status','primary_candidate','alternative_candidates')
    return list(fields)+[name for name in additional if name not in fields]


def physical_timings():
    benchmark={r['design']:r for r in read(OUT/'manifests/generalization_benchmark_manifest.json')['designs']}
    rows=[]
    for folder in sorted(RUN.glob('baseline*')):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob('**/execution.json')):
            parts=path.relative_to(RUN).parts
            if len(parts)<4 or parts[1] not in benchmark:
                continue
            data=read(path)
            info=benchmark[parts[1]]
            rows.append(dict(design=parts[1],FF_count=info['FF_count'],ATPG_pattern_count=info['ATPG_pattern_count'],
                attempt=parts[0],method=parts[2],stage='/'.join(parts[3:-1]) or 'FAN_original_workload',
                wall_seconds=data.get('wall_seconds',data.get('runtime_seconds')),
                CPU_seconds=None,peak_RSS_KiB=None,exit_code=data.get('exit_code'),
                timed_out=data.get('timed_out'),provenance=external_binding(path)))
    for r in collect()[2]:
        rows.append(dict(design=r['design'],FF_count=r['FF_count'],ATPG_pattern_count=r['ATPG_pattern_count'],
            attempt='final_reference_measurement',method=r['method'],stage='extraction_simulation_activity_analysis',
            wall_seconds=r['measurement_wall_seconds'],**r['measurement_resources'],exit_code=0,timed_out=False,
            provenance=r['provenance']['measurement']))
    for design in DESIGNS:
        path=OUT/f'physical/{design}/reference_measurement/result.json'
        if not path.exists():
            continue
        failed=read(path)
        if failed['status']=='FAILED' and failed.get('failure_class')=='RESOURCE_LIMIT':
            data=failed['execution']
            info=benchmark[design]
            rows.append(dict(design=design,FF_count=info['FF_count'],ATPG_pattern_count=info['ATPG_pattern_count'],
                attempt='reference_measurement_resource_limit',method=failed['selected_reference'],
                stage='incomplete_physical_metric_measurement',wall_seconds=data['wall_seconds'],
                CPU_seconds=None,peak_RSS_KiB=None,exit_code=data['exit_code'],timed_out=data['timed_out'],
                provenance=binding(path)))
    write(OUT/'physical_qualification_timings.json',dict(schema='pact_generalization_physical_timing_v1',
        scope='PHYSICAL_ONLY; all retained attempts, including failed stages; no solver timing',
        records=rows,updated_utc=now(),missing_resource_policy='Unavailable CPU/RSS is null; wall time is never substituted for solver cost'))
    (OUT/'physical_qualification_timings.csv').write_text(csv_text(('design','FF_count','ATPG_pattern_count',
        'attempt','method','stage','wall_seconds','CPU_seconds','peak_RSS_KiB','exit_code','timed_out'),rows))
    return rows


def readable_report(status,counts,outcomes,refs,measured):
    by_name={r['design']:r for r in measured}
    freeze=read(OUT/'manifests/pact_v1_frozen_manifest.json')
    verification=read(OUT/'manifests/freeze_verification.json')
    current=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    changes=subprocess.check_output(['git','diff','--name-only',freeze['repository_sha']],cwd=ROOT,text=True).splitlines()
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    untracked += [str((OUT/name).relative_to(ROOT)).replace('\\','/') for name in (
        'generalization_report.md','completion.json','repository_changes.txt','repository_state_at_report.json')]
    commits=subprocess.check_output(['git','log','--reverse','--format=%h %s',freeze['repository_sha']+'..HEAD'],cwd=ROOT,text=True)
    (OUT/'repository_changes.txt').write_text('\n'.join(sorted(set(changes+untracked)))+'\n')
    write(OUT/'repository_state_at_report.json',dict(starting_SHA=freeze['repository_sha'],
        SHA_at_report_assembly=current,branch='experiment/generalization-scalability-20261004',
        commits=commits.splitlines(),changed_files=sorted(set(changes+untracked)),
        ending_SHA_note='The final response supplies the commit containing this report; a commit cannot embed its own SHA'),immutable=True)
    lines=[f'# {status}', '',
        'The forward campaign is blocked by the fixed-budget physical-metric simulation resource limit and, independently, '
        'by the missing unseen-design P0 initialization contract before PACT search. '
        'No new PACT candidate was evaluated, preselected, routed, or qualified. '
        'Generalization benefit and solver runtime/memory scaling therefore remain unmeasured.', '',
        '## Frozen core', '',
        f'- Tag: `{freeze["tag"]}` at `{freeze["repository_sha"]}`.',
        f'- Integrity: `{verification["status"]}`; no historical search, routing, ATPG, or extraction was rerun.',
        '- [Exact manifest](manifests/pact_v1_frozen_manifest.json), [integrity receipt](manifests/freeze_verification.json), '
        'and [additive provenance relocations](manifests/pact_v1_frozen_relocated_manifest.json).',
        '- All original canonical dictionaries and the original primary CSV byte prefix remain unchanged. '
        'The relocated bindings recover identical bytes from retained evidence/Git without editing historical receipts.', '',
        '## Preregistered unseen set', '',
        f'Selected {counts["selected"]}; infrastructure-qualified {counts["infrastructure_qualified"]}; '
        f'references with qualified extracted activity {counts["references_with_activity_measurements"]}; '
        'new PACT designs completed end-to-end: 0.', '',
        'All eight available unused mapped circuits were selected before outcomes from the pinned FAN ISCAS89 source set. '
        'They span 6–1,728 FFs and 21–145 patterns. No selected circuit was removed after outcomes. '
        'The available unseen set has a gap between 29 and 1,426 FFs; it supplies no new medium-size circuit.', '',
        '| Design | FFs | Patterns | Infrastructure | Reference | PACT outcome |',
        '|---|---:|---:|---|---|---|']
    for r in outcomes:
        lines.append(f'| {r["design"]} | {r["FF_count"]} | {r["ATPG_pattern_count"]} | '
            f'{r["infrastructure_status"]} | {r.get("selected_reference","—")} | PACT_EXECUTION_BLOCKED |')
    lines += ['', '`s208` and `s510` hit the unchanged requirement of at least eight FFs per chain with K=2. '
        'Their ATPG receipts are retained. K and the guard were preserved.', '',
        '## External references', '',
        'Each available reference was selected as the minimum qualified routed scan cost among B0/B1/B2/B3T. '
        'The two long-buffer-path failures on s38417 were repaired before final reference selection, using retained routes. '
        'Earlier provisional/failing receipts are preserved. '
        '[Selection and all-method provenance](baselines/generalization_baselines.json).', '',
        '| Design | Reference | Routed scan WL (µm) | E (fF transitions) | H4 | H8 | WNS (ns) | DRC | Fault coverage (%) |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in refs:
        activity=by_name.get(r['design'])
        values=[f'{activity[k]:.10g}' if activity else 'unavailable' for k in ('E','H4','H8')]
        statistics=r['correctness']['statistics']
        coverage=f'{100*statistics["detected"]/statistics["total"]:.10g}'
        lines.append(f'| {r["design"]} | {r["method"]} | {r["routed_scan_wirelength_um"]:.10g} | '
            + ' | '.join(values)+f' | {r["timing"]["setup_wns_ns"]:.10g} | {r["DRC"]} | {coverage} |')
    lines += ['', 'These rows are external references. Primary and alternative PACT candidates, and their changes '
        'in WL/E/H4/H8, are unavailable because no search started. '
        'The original three-design PACT rows and legitimate alternatives remain in '
        '[canonical results](canonical/generalization_canonical_results.json) and '
        '[the full table](canonical/generalization_results_table.csv). '
        '[The primary comparison CSV](canonical/generalization_primary_comparison.csv) retains the original bytes as its prefix.', '',
        '## Qualification and repairs', '',
        'Qualified new references retain topology, exact FF inventory/placement, routing, extraction, timing reporting, '
        'zero DRC, serial replay, and FAN correctness gates. All 24 retained reference routes pass the frozen functional '
        'source/parity and exact FF-placement export checks. [All-reference gate receipts](physical/reference_export_gates.json). '
        'Completed activity measurements additionally check complete FF transition agreement. '
        'FAN comparisons cover the complete collapsed target classes, equivalence '
        'weights, detected collapsed classes, weighted full/detected counts, patterns, and coverage. '
        'Uncollapsed class-member identities are not enumerated.', '',
        'Engineering repairs were isolated on repair branches and integrated only after focused regressions: '
        'direct scan-output endpoint recovery; existing runtime paths; reporting-field lookup; '
        'functional FF identity through Q-net renaming; and replacing the arbitrary eight-buffer traversal limit '
        'with a finite graph bound; and recognizing SDFF_X2 only after proving its frozen-library state/pin functions '
        'identical to SDFF_X1. No FF identities were dropped. The optimizer, metrics, objective, operators, and frozen files were preserved. '
        'The traversal repair changes only its guard expression; before/after gate, WL, functional verification, '
        'and net/capacitance mapping outputs are exactly equal on a previously passing unseen design. '
        'Nineteen focused regression tests passed. A reporting-only schema repair removed a duplicate CSV heading; '
        'all 18 row dictionaries and protected canonical/core hashes stayed unchanged. '
        '[Table schema receipt](repair_attempts/table_schema_repaired/qualification.json).', '',
        '## Initialization blocker and scientific conclusion', '',
        'The frozen loader raises `KeyError("s1196")` because its design table and artifact lookups cover only the '
        'historical three circuits. Its Stage-B starts also require a measured representative P0 from an earlier '
        'stateful search archive. That archive depends on prior candidate-sensitive/v2 selections and an earlier '
        'working-PACT architecture. The repository contains sealed historical endpoints, rather than a complete '
        'unseen-input construction rule. [Bound dependency audit](searches/initialization_audit.json); '
        '[reproduced loader failure](failures/frozen_initialization_contract.json).', '',
        'The unresolved protocol must specify the precursor physical-input role, initial working-PACT seed and budget, '
        'qualification/seed propagation through the precursor stages, and how those stages fit the per-design routing limit. '
        'No P0 was omitted, substituted, or synthesized under an invented rule.', '',
        'New primary candidates improving E, H4, H8, or all three: **not measured**. '
        'Mixed outcomes and negligible-benefit outcomes: **not measured**. '
        'No scientific support or rejection of PACT generalization can be inferred from this dataset.', '',
        'The s38417 B2 reference passed structural, functional, routing, timing, DRC, extraction, and FAN gates, '
        'but its Icarus simulation exceeded the fixed 1,800-second measurement limit. Export, extraction, and compilation '
        'had completed; simulation and FF-transition/activity analysis had not. The partial VCD is retained by hash and '
        'excluded from every activity result. [Localized resource failure](failures/s38417_measurement_localization.json). '
        'This is an observed resource block under the campaign budget, rather than evidence against the PACT objective. '
        'Other reference routing ran concurrently; the observed wall time is not an isolated solver benchmark.', '',
        'The s38584 full activity simulation was not started after this resource stop. Its four existing references '
        'completed routing, extraction, FAN, functional and FF-placement qualification. The canonical table includes '
        'its B3T reference and the s38417 B2 reference with null E/H4/H8, an explicit activity-unavailable status, '
        'and no PACT benefit or proxy values.', '',
        '## Scalability', '',
        'Solver: `PACT_SCALABILITY_NOT_MEASURED`. Physical metrics: `PHYSICAL_METRIC_SCALABILITY_BLOCKED_AT_s38417`. '
        'Exact candidate evaluations, solver CPU/RSS, evaluations/s, evaluator time, '
        'overhead, stagnation/restarts, and candidate-selection time have no new observations. '
        '[The scalability JSON](scalability_results.json) has an empty search dataset; '
        '[the CSV](scalability_results.csv) contains its header only. '
        'Measured route and reference activity times/resources are separate physical-stage records. '
        'No scaling model or size-of-impracticality claim is supported.', '',
        'The preregistered search remains seed 11, K=2, epsilon 0.02/0.05/0.10, balanced weights (1,1,1), '
        '20,000 maximum evaluations, and the fixed runtime rule 300×max(1,ceil(FF/600)) seconds. '
        'Neighborhood, segment, archive, lane, and stagnation settings remain frozen. '
        '[Exact configuration](searches/exact_configuration.json).']
    if measured:
        times=[r['measurement_wall_seconds'] for r in measured]
        memory=[r['measurement_resources']['peak_RSS_KiB'] for r in measured]
        lines += ['',f'Qualified reference activity measurement wall time: {min(times):.3f}–{max(times):.3f} s; '
            f'maximum RSS across those subprocess trees: {min(memory)/1024:.3f}–{max(memory)/1024:.3f} MiB. '
            'These observations include extraction, simulation, and activity analysis; they are separate from solver cost.']
    lines += ['', '## Measurement scope', '',
        'Routed scan WL remains the connected scan-path net-length upper bound, including shared functional branches. '
        'E remains ground-plus-pin capacitance times transitions; H4/H8 remain source-localized peak bins per cycle '
        'over all data nets. These measurements do not establish watts, IR drop, signoff timing, or silicon reliability. '
        'The hotspot definitions were preserved and no ablation was run.', '',
        '## Repository and retained evidence', '',
        f'Starting SHA: `{freeze["repository_sha"]}`. Branch: `experiment/generalization-scalability-20261004`. '
        f'Commit at report assembly: `{current}`. The final response identifies the commit containing the report.', '',
        '[Commit/file inventory](repository_state_at_report.json); [changed files](repository_changes.txt). '
        'Heavy new inputs, tools already present, routed databases, SPEFs, VCDs, and detailed execution logs remain at '
        '`D:\\PACT_EXPERIMENTS\\results\\pact_generalization_20261004`; repository receipts bind them by exact hash. '
        'No duplicate installation or temporary build tree was committed.', '', '```text',commits.rstrip(),'```', '',
        '## Remaining work', '',
        'Resolve a reproducible unseen-design P0 construction protocol that retains frozen warm-start semantics, '
        'and the localized physical-metric simulation resource limit with evidence that preserves measurement semantics. '
        'Then run the preregistered searches, preselect at most three distinct candidates per design before route, '
        'qualify every selected candidate, and collect solver-only scalability data. '
        'The present artifacts are a reproducible blocked campaign checkpoint, not a completed generalization result.', '']
    (OUT/'generalization_report.md').write_text('\n'.join(lines),encoding='utf-8')


def report(seal=False,check=False):
    outcomes,refs,measured=collect()
    if check:
        new_rows=preflight(outcomes,refs,measured)
        print('REPORT_PREFLIGHT_PASS',len(outcomes),len(refs),len(measured),len(new_rows),flush=True)
        return
    physical_timings()
    counts=dict(selected=len(outcomes),infrastructure_qualified=len(refs),
        references_with_activity_measurements=len(measured),new_PACT_searches_executed=0,
        new_PACT_candidates_preselected=0,new_PACT_designs_completed_end_to_end=0)
    summary=dict(schema='pact_generalization_campaign_progress_v1',updated_utc=now(),counts=counts,
        outcomes=outcomes,scientific_conclusion='NOT_MEASURED',computational_scalability='PACT_SCALABILITY_NOT_MEASURED')
    if not seal:
        write(OUT/'logs/progress_snapshot.json',summary)
        print(json.dumps(counts),flush=True)
        return
    # This report handles the reproduced initialization blocker, not PACT runs.
    assert not list((OUT/'searches').glob('*/budget_*/search.json'))
    assert read(OUT/'failures/frozen_initialization_contract.json')['PACT_searches_executed']==0
    new_rows=preflight(outcomes,refs,measured)
    resource_blockers=[r['design'] for r in outcomes if r.get('reference_measurement_failure',{}).get('failure_class')=='RESOURCE_LIMIT']
    status='PACT_V1_GENERALIZATION_BLOCKED_BY_SCALABILITY' if resource_blockers else 'PACT_V1_GENERALIZATION_BLOCKED_BY_INITIALIZATION'
    write(OUT/'baselines/generalization_baselines.json',dict(schema='pact_generalization_baselines_v1',
        status='PRESEARCH_REFERENCES_RECORDED',selection_rule='minimum qualified routed scan cost among B0/B1/B2/B3T before PACT search',
        created_utc=now(),records=refs,all_design_outcomes=outcomes,
        PACT_searches_started=False,functional_and_FF_placement_gates=binding(OUT/'physical/reference_export_gates.json')),immutable=True)
    write(OUT/'searches/selected_candidate_manifest.json',dict(schema='pact_generalization_candidate_selection_v1',
        status='NOT_EXECUTED_INITIALIZATION_BLOCKED',records=[],design_outcomes=outcomes,
        configuration=binding(OUT/'searches/exact_configuration.json'),
        blocker=binding(OUT/'failures/frozen_initialization_contract.json')),immutable=True)
    write(OUT/'scalability_results.json',dict(schema='pact_generalization_scalability_v1',records=[],
        classification='PACT_SCALABILITY_NOT_MEASURED',classification_scope='SOLVER_ONLY',executed_search_count=0,
        physical_metric_resource_blockers=resource_blockers,
        reason='The frozen loader fails before model/search initialization; physical stage time is recorded separately',
        blocked_designs=outcomes,physical_reference_measurements=[{k:r[k] for k in ('design',
            'route_wall_seconds','measurement_wall_seconds','measurement_resources')} for r in measured]),immutable=True)
    (OUT/'scalability_results.csv').write_text(csv_text(SCALABILITY_FIELDS,[]))
    write(OUT/'canonical/design_outcomes.json',summary|dict(status=status),immutable=True)
    original=read(CORE/'canonical_results.json')
    canonical=dict(schema='pact_generalization_canonical_results_v1',status=status,created_utc=now(),
        frozen_core=binding(CORE/'canonical_results.json'),frozen_record_count=len(original['records']),
        frozen_core_status=original['status'],frozen_core_primary_candidates=original['primary_candidates'],
        frozen_core_primary_selection_reason=original['primary_selection_reason'],
        frozen_search_records=original['searches'],
        records=original['records']+new_rows,design_outcomes=outcomes,
        new_PACT_primary_candidates={},new_PACT_alternative_candidates={},
        counts=counts,scientific_conclusion='No new PACT outcome is available; reference activity is not evidence of PACT benefit',
        computational_scalability='PACT_SCALABILITY_NOT_MEASURED')
    canonical['physical_metric_resource_blockers']=resource_blockers
    assert canonical['records'][:len(original['records'])]==original['records']
    write(OUT/'canonical/generalization_canonical_results.json',canonical,immutable=True)
    old_csv=(CORE/'primary_comparison.csv').read_bytes()
    fields=next(csv.reader(io.StringIO(old_csv.decode())))
    added=[{key:r.get(key) for key in fields}|{
        'delta_routed_scan_wirelength_um_percent':0.,'delta_E_percent':r['deltas_percent']['E'],
        'delta_H4_percent':r['deltas_percent']['H4'],'delta_H8_percent':r['deltas_percent']['H8']}
        for r in new_rows]
    addition=csv_text(fields,added).split('\n',1)[1].encode()
    target=OUT/'canonical/generalization_primary_comparison.csv'
    target.write_bytes(old_csv+addition)
    assert target.read_bytes().startswith(old_csv)
    metadata=[dict(design=r['design'],candidate=r['candidate'],correctness_status='PASS',
        solver_runtime_seconds=r.get('search_runtime_seconds',r.get('runtime',{}).get('search_seconds')),
        exact_evaluation_count=r.get('candidates_evaluated'),record_scope='FROZEN_CORE_UNCHANGED') for r in original['records']]
    metadata += [dict(design=r['design'],candidate=r['candidate'],correctness_status=r['correctness_status'],
        solver_runtime_seconds=None,exact_evaluation_count=None,record_scope=r['record_kind'],
        qualification_status=r['qualification_status'],activity_status=r.get('activity_status','QUALIFIED'),
        PACT_status='PACT_EXECUTION_BLOCKED',primary_candidate=None,alternative_candidates=[]) for r in new_rows]
    write(OUT/'canonical/table_context.json',dict(records=metadata,
        note='Original canonical dictionaries and primary CSV prefix are unchanged; appended rows are qualified external references, without PACT comparisons'),immutable=True)
    full_rows=[]
    for r,context in zip(canonical['records'],metadata):
        full_rows.append(dict(r,**context,
            delta_routed_scan_wirelength_um_percent=r['deltas_percent']['routed_scan_wirelength_um'],
            delta_E_percent=r['deltas_percent']['E'],delta_H4_percent=r['deltas_percent']['H4'],
            delta_H8_percent=r['deltas_percent']['H8']))
    (OUT/'canonical/generalization_results_table.csv').write_text(csv_text(table_fields(fields),full_rows))
    readable_report(status,counts,outcomes,refs,measured)
    write(OUT/'completion.json',dict(status=status,created_utc=now(),counts=counts,
        core_freeze_status=read(OUT/'manifests/freeze_verification.json')['status'],
        repository_sha_at_assembly=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        scientific_method_changes=0,computational_scalability='PACT_SCALABILITY_NOT_MEASURED',
        computational_scalability_scope='SOLVER_ONLY',physical_metric_resource_blockers=resource_blockers,
        required_next_action='Resolve the unseen-design P0 construction protocol while preserving frozen warm-start semantics',
        artifacts={str(p.relative_to(OUT)):binding(p) for p in (OUT/'baselines/generalization_baselines.json',
            OUT/'searches/selected_candidate_manifest.json',OUT/'scalability_results.json',OUT/'scalability_results.csv',
            OUT/'canonical/generalization_canonical_results.json',target)}),immutable=True)
    print(status,json.dumps(counts),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seal',action='store_true')
    p.add_argument('--check',action='store_true',help='Validate final assembly without writing completion artifacts')
    a=p.parse_args()
    report(a.seal,a.check)
