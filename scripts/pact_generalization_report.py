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

ATTEMPTS=('buffer_traversal_repaired','functional_identity_repaired','runtime_paths_repaired')
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
                methods=[{key:r.get(key) for key in ('method','status','generator_status',
                    'routed_scan_wirelength_um','failure_class','error')} for r in records])
            refs.append(compact)
            folder=OUT/f'physical/{name}/reference_measurement'
            receipt=folder/('result_recovered.json' if (folder/'result_recovered.json').exists() else 'result.json')
            if receipt.exists():
                result=read(receipt)
                row['reference_measurement_status']=result['status']
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


def csv_text(fields,rows):
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=fields,lineterminator='\n',extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def report(seal=False):
    outcomes,refs,measured=collect()
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
    status='PACT_V1_GENERALIZATION_BLOCKED_BY_INITIALIZATION'
    write(OUT/'baselines/generalization_baselines.json',dict(schema='pact_generalization_baselines_v1',
        status='PRESEARCH_REFERENCES_RECORDED',selection_rule='minimum qualified routed scan cost among B0/B1/B2/B3T before PACT search',
        created_utc=now(),records=refs,all_design_outcomes=outcomes,
        PACT_searches_started=False),immutable=True)
    write(OUT/'searches/selected_candidate_manifest.json',dict(schema='pact_generalization_candidate_selection_v1',
        status='NOT_EXECUTED_INITIALIZATION_BLOCKED',records=[],design_outcomes=outcomes,
        configuration=binding(OUT/'searches/exact_configuration.json'),
        blocker=binding(OUT/'failures/frozen_initialization_contract.json')),immutable=True)
    write(OUT/'scalability_results.json',dict(schema='pact_generalization_scalability_v1',records=[],
        classification='PACT_SCALABILITY_NOT_MEASURED',executed_search_count=0,
        reason='The frozen loader fails before model/search initialization; physical stage time is recorded separately',
        blocked_designs=outcomes,physical_reference_measurements=[{k:r[k] for k in ('design',
            'route_wall_seconds','measurement_wall_seconds','measurement_resources')} for r in measured]),immutable=True)
    (OUT/'scalability_results.csv').write_text(csv_text(SCALABILITY_FIELDS,[]))
    write(OUT/'canonical/design_outcomes.json',summary|dict(status=status),immutable=True)
    original=read(CORE/'canonical_results.json')
    canonical=dict(schema='pact_generalization_canonical_results_v1',status=status,created_utc=now(),
        frozen_core=binding(CORE/'canonical_results.json'),frozen_record_count=len(original['records']),
        records=original['records']+measured,design_outcomes=outcomes,
        new_PACT_primary_candidates={},new_PACT_alternative_candidates={},
        counts=counts,scientific_conclusion='No new PACT outcome is available; reference activity is not evidence of PACT benefit',
        computational_scalability='PACT_SCALABILITY_NOT_MEASURED')
    assert canonical['records'][:len(original['records'])]==original['records']
    write(OUT/'canonical/generalization_canonical_results.json',canonical,immutable=True)
    old_csv=(CORE/'primary_comparison.csv').read_bytes()
    fields=next(csv.reader(io.StringIO(old_csv.decode())))
    added=[{key:r.get(key) for key in fields}|{
        'delta_routed_scan_wirelength_um_percent':0.,'delta_E_percent':0.,'delta_H4_percent':0.,'delta_H8_percent':0.}
        for r in measured]
    addition=csv_text(fields,added).split('\n',1)[1].encode()
    target=OUT/'canonical/generalization_primary_comparison.csv'
    target.write_bytes(old_csv+addition)
    assert target.read_bytes().startswith(old_csv)
    metadata=[dict(design=r['design'],candidate=r['candidate'],correctness_status='PASS',
        solver_runtime_seconds=r.get('runtime',{}).get('search_seconds'),
        exact_evaluation_count=None,record_scope='FROZEN_CORE_UNCHANGED') for r in original['records']]
    metadata += [dict(design=r['design'],candidate=r['candidate'],correctness_status='PASS',
        solver_runtime_seconds=None,exact_evaluation_count=None,record_scope='NEW_EXTERNAL_REFERENCE_ONLY') for r in measured]
    write(OUT/'canonical/table_context.json',dict(records=metadata,
        note='Original canonical dictionaries and primary CSV prefix are unchanged; appended rows are qualified external references, without PACT comparisons'),immutable=True)
    write(OUT/'completion.json',dict(status=status,created_utc=now(),counts=counts,
        core_freeze_status=read(OUT/'manifests/freeze_verification.json')['status'],
        repository_sha_at_assembly=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        scientific_method_changes=0,computational_scalability='PACT_SCALABILITY_NOT_MEASURED',
        required_next_action='Resolve the unseen-design P0 construction protocol while preserving frozen warm-start semantics',
        artifacts={str(p.relative_to(OUT)):binding(p) for p in (OUT/'baselines/generalization_baselines.json',
            OUT/'searches/selected_candidate_manifest.json',OUT/'scalability_results.json',OUT/'scalability_results.csv',
            OUT/'canonical/generalization_canonical_results.json',target)}),immutable=True)
    print(status,json.dumps(counts),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seal',action='store_true')
    a=p.parse_args()
    report(a.seal)
