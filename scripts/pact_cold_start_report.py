#!/usr/bin/env python3
"""Aggregate prospective exact evidence; snapshots never announce completion."""
import argparse
import csv
from datetime import datetime, timedelta
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess

from pact_generalization import ROOT, CORE, binding, now, read, sha, write

OUT = ROOT/'results/pact_cold_start_unseen_20261004'
PREVIOUS = ROOT/'results/pact_generalization_20261004'
METRIC_SCOPE = 'all_data; ground+pin C*N; H4/H8 source-localized bins/cycle; scan WL connected scan-net upper bound'
FAULT_SCOPE = 'Complete collapsed FAN SAF target classes and equivalence multiplicities; uncollapsed members not enumerated'
TABLE_FIELDS = ('design','reference','candidate','architecture_hash','record_kind','routed_scan_wirelength_um',
    'E','H4','H8','delta_routed_WL_percent','delta_E_percent','delta_H4_percent','delta_H8_percent',
    'WNS','hold_WNS','DRC','fault_coverage','search_runtime_seconds','qualification_status','status')
SOLVER_FIELDS = ('design','FF_count','ATPG_pattern_count','target_fault_count','epsilon','seed','status',
    'registered_loop_seconds','model_setup_seconds','lane_initialization_seconds','search_loop_seconds',
    'lane_total_seconds','solver_worker_wall_seconds','solver_worker_CPU_seconds','solver_worker_peak_RSS_KiB',
    'exact_mutation_evaluations','exact_state_score_calls','independent_replays','exact_mutation_evaluations_per_second',
    'attempts','screened_infeasible','accepted_moves','rejected_exact_moves','archive_insertions',
    'initial_reference_archive_insertions','archive_size','restarts','final_stagnation_attempts',
    'stagnation_termination_events','termination','state_score_seconds','independent_replay_seconds',
    'evaluator_measured_component_seconds','lane_unattributed_seconds','solver_overhead_seconds',
    'timing_scope','source_receipt')
EVALUATOR_COMPONENTS=('scan_waveform_seconds','stateful_propagation_seconds','geometry_seconds',
    'spatial_seconds','rollback_seconds','reduction_seconds')


def local_path(raw):
    raw=str(raw)
    if raw.startswith('repo://'):
        return ROOT/raw.removeprefix('repo://')
    if os.name=='nt' and re.match(r'^/mnt/[a-z]/',raw):
        return Path(raw[5].upper()+':/'+raw[7:])
    return Path(raw)


def maybe(path):
    path=Path(path)
    return read(path) if path.exists() else None


def bound(record):
    path=local_path(record['path'])
    if not path.is_file() or sha(path)!=record['sha256']:
        raise ValueError('Evidence binding changed: '+str(path))
    return path


def verify_search_provenance(design):
    """Validate current receipts and the byte-frozen scientific sources."""
    folder=OUT/f'searches/{design}'
    config=maybe(folder/'search_configuration.json')
    summary=maybe(folder/'search_results.json')
    selection=maybe(OUT/f'selections/{design}/preselected_candidates.json')
    if config:
        package=read(bound(config['input']))
        for source in config['sources'].values():bound(source)
        if config['seed']!=11 or config['K']!=2:
            raise ValueError('Registered seed/K changed')
        expected_epsilons=(.02,.05,.10)
        if tuple(c['epsilon'] for c in config['configurations'])!=expected_epsilons:
            raise ValueError('Registered epsilon order changed')
        settings=dict(seed=11,max_evaluations=20000,stagnation_attempts=2000,lane_attempts=150,
            neighbors=16,segment=8,archive_size=16,weights=[1.,1.,1.],
            seconds=300*max(1,math.ceil(package['FF_count']/600)))
        if any(c.get(k)!=v for c in config['configurations'] for k,v in settings.items()):
            raise ValueError('Fixed scientific search configuration changed')
    if summary:
        for name in ('input','configuration','initialization'):bound(summary[name])
        for lane in summary['lanes']:bound(lane['receipt'])
    if selection:
        bound(selection['cold_start_input']);bound(selection['search_results'])
        hashes=[r['architecture_hash'] for r in selection['records']]
        if len(hashes)>3 or len(hashes)!=len(set(hashes)) or selection.get('candidate_routes_before_selection')!=0:
            raise ValueError('Frozen pre-route candidate-selection contract changed')
        for candidate in selection['records']:
            bound(candidate['architecture']);bound(candidate['search_receipt'])


def verify_frozen_core():
    path=PREVIOUS/'manifests/pact_v1_frozen_manifest.json'
    manifest=read(path)
    for record in manifest['files']:
        member=bound(record)
        if member.stat().st_size!=record['bytes']:
            raise ValueError('Frozen historical byte size differs')
    original=read(CORE/'canonical_results.json')
    if len(original['records'])!=12:
        raise ValueError('Frozen historical canonical record count differs')
    return dict(status='PASS',created_utc=now(),frozen_manifest=binding(path),
        original_files_checked=len(manifest['files']),original_canonical_records=12,
        historical_scientific_tool_executions=0,all_original_byte_hashes_unchanged=True,
        historical_core=binding(CORE/'canonical_results.json'))


def csv_text(fields, rows):
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue()


def resource_file(worker):
    if not worker:
        return {}
    command=worker.get('execution',{}).get('command',[])
    if '-o' not in command:
        return {}
    path=local_path(command[command.index('-o')+1])
    if not path.exists():
        return {}
    text=path.read_text()
    def number(label):
        match=re.search(re.escape(label)+r':\s*([0-9.]+)',text)
        return float(match[1]) if match else None
    user,system=number('User time (seconds)'),number('System time (seconds)')
    return dict(CPU_seconds=user+system if user is not None and system is not None else None,
        peak_RSS_KiB=number('Maximum resident set size (kbytes)'),resources_path=str(path))


def delta(value, reference):
    if value is None or reference is None or reference==0:
        return None
    return 100*(value/reference-1)


def relation(value, reference):
    tolerance=1e-10*max(1.,abs(reference))
    return 'improved' if value<reference-tolerance else ('regressed' if value>reference+tolerance else 'equal')


def activity_category(row, reference):
    if any(row.get(m) is None or reference.get(m) is None for m in ('E','H4','H8')):
        return None,{}
    relations={m:relation(row[m],reference[m]) for m in ('E','H4','H8')}
    values=list(relations.values())
    if all(v=='improved' for v in values):category='PACT_STRONG_IMPROVEMENT'
    elif all(v=='equal' for v in values):category='PACT_NEGLIGIBLE_BENEFIT'
    elif 'improved' not in values:category='PACT_NO_BENEFIT'
    else:category='PACT_MIXED_TRADEOFF'
    return category,relations


def terminal_design_stop(design, method):
    """Only new campaign failures/explicit stops terminate a current unit."""
    for path in (OUT/f'failures/{design}_campaign_stop.json',OUT/f'failures/{design}_stop.json'):
        stop=maybe(path)
        if stop and (stop.get('terminal') or stop.get('status') in ('PACT_EXECUTION_BLOCKED','STOPPED','FAILED')):
            if stop.get('design',design)!=design:
                raise ValueError('Explicit stop receipt design differs')
            return dict(status='PACT_EXECUTION_BLOCKED',terminal=True,
                failure_class=stop.get('failure_class','FRAMEWORK_OR_RESOURCE_POLICY'),
                failure_domain=stop.get('failure_domain','MEASUREMENT' if any(token in stop.get('stage','').upper() for token in ('MEASURE','ACTIVITY')) else 'FRAMEWORK'),
                reason=stop.get('reason',stop.get('error','Explicit independent-design stop')),
                stop_receipt=binding(path),failure=stop)
    if method:
        path=OUT/f'physical/{design}/REF_{method}/activity/result.json'
        result=maybe(path)
        if result and result.get('status')=='FAILED':
            reason=f'New independent REF_{method} exact-activity measurement failed ({result.get("failure_class","PHYSICAL_BACKEND_FAIL")})'
            if result.get('failure_class')=='RESOURCE_LIMIT' and result.get('timeout_seconds'):
                reason+=f' at the fixed {result["timeout_seconds"]}-second deadline; complete VCD and exact E/H4/H8 are unavailable'
            return dict(status='PACT_EXECUTION_BLOCKED',terminal=True,
                failure_class=result.get('failure_class','PHYSICAL_BACKEND_FAIL'),failure_domain='MEASUREMENT',
                blocker_subtype='REFERENCE_EXACT_ACTIVITY',stage='REFERENCE_EXACT_ACTIVITY',
                reason=reason+'; only this design stops independently',
                stop_receipt=binding(path),failure=result)
    return None


def initialization_evidence(design):
    """An input package or old diagnostic assertion is never a PASS receipt."""
    paths=((OUT/f'searches/{design}/initialization.json','PRODUCTION_SEARCH_INITIALIZATION'),
        (OUT/f'scalability/{design}_initialization_diagnostic.json','LOADER_ONLY_DIAGNOSTIC; optimizer not executed'))
    for path,scope in paths:
        result=maybe(path)
        if result and result.get('status')=='PASS':
            if scope.startswith('LOADER_ONLY'):
                configuration=read(bound(result['configuration']))
                package=read(bound(configuration['input']))
                for source in configuration['sources'].values():bound(source)
                if result.get('search_completed') is not False or result.get('optimizer_executions')!=0 or result.get('candidate_evaluations')!=0:
                    raise ValueError('Loader-only diagnostic claims optimizer execution')
                if result.get('start_count')!=1 or result.get('exact_roundtrip')!='PASS' or result.get('initial_architecture_hash')!=package['reference_architecture_hash']:
                    raise ValueError('Loader-only diagnostic initial architecture proof differs')
                if result.get('labels')!=[package['reference_method']]:
                    raise ValueError('Loader-only diagnostic uses an extra initial architecture')
            return dict(initialized=True,initialization_scope=scope,initialization_receipt=binding(path))
    return dict(initialized=False,initialization_scope=None,initialization_receipt=None)


def evaluator_accounting(lane):
    """Sum exclusive original timers only, within the whole optimize-call domain."""
    profile=lane.get('model_profile') or {}
    subtotal=sum(float(profile.get(name,0.)) for name in EVALUATOR_COMPONENTS)
    replay=(lane.get('instrumentation') or {}).get('independent_replay_seconds')
    runtime=lane.get('runtime_seconds')
    remainder=runtime-subtotal-replay if runtime is not None and replay is not None else None
    return dict(evaluator_measured_component_seconds=subtotal,
        evaluator_component_names=list(EVALUATOR_COMPONENTS),
        evaluator_profile_complete=all(name in profile for name in EVALUATOR_COMPONENTS),
        evaluator_subtotal_scope='Whole optimize-call lane; disjoint original forward/rollback/reduction timers; incomplete evaluator coverage',
        score_wrapper_overlap='state_score_seconds overlaps reduction_seconds and is excluded from the additive subtotal',
        independent_replay_scope='Whole optimize-call retained-endpoint replay after mutation loop; separate from model profile',
        lane_unattributed_seconds=remainder,solver_overhead_seconds=None,
        remainder_scope='Whole lane runtime minus exclusive measured components and separate replay; includes untimed State construction/restarts, evaluator allocations/setup and solver work; not solver overhead')


def reference_row(entry):
    reference=entry.get('reference')
    if reference is None:
        return None
    design=entry['design']
    path=OUT/f'references/{design}/reference_frozen.json'
    if path.exists():
        reference=read(path)
    method=reference['method']
    prior=PREVIOUS/f'physical/{design}/reference_measurement'
    result_path=prior/('result_recovered.json' if (prior/'result_recovered.json').exists() else 'result.json')
    result=maybe(result_path)
    # A separately executed new exact reference measurement takes precedence.
    for role in (method,'REF_'+method):
        new_path=OUT/f'physical/{design}/{role}/activity/result.json'
        if new_path.exists():
            result_path=new_path;result=read(new_path)
    qualified=result is not None and result.get('status')=='QUALIFIED'
    if qualified and result.get('summary'):
        bound(result['summary'])
        if result.get('architecture_sha256',reference['architecture_hash'])!=reference['architecture_hash']:
            raise ValueError('Reference activity architecture identity differs')
    statistics=reference['correctness']['statistics']
    row=dict(design=design,reference=method,candidate=method,architecture_hash=reference['architecture_hash'],
        record_kind='PROSPECTIVE_EXTERNAL_REFERENCE',FF_count=entry['FF_count'],
        ATPG_pattern_count=entry['ATPG_pattern_count'],routed_scan_wirelength_um=reference['routed_scan_wirelength_um'],
        E=result['E'] if qualified else None,H4=result['H4'] if qualified else None,H8=result['H8'] if qualified else None,
        WNS=reference['timing']['setup_wns_ns'],hold_WNS=reference['timing']['hold_wns_ns'],DRC=reference['DRC'],
        fault_coverage=100*statistics['detected']/statistics['total'],FAN_reported_coverage=statistics['coverage'],
        target_faults=statistics['total'],detected_faults=statistics['detected'],
        qualification_status='QUALIFIED' if qualified else 'ROUTED_AND_ATPG_PASS_ACTIVITY_UNAVAILABLE',
        status='REFERENCE',activity_status=result.get('status') if result else 'NOT_MEASURED',
        search_runtime_seconds=None,metric_scope=METRIC_SCOPE,fault_identity_scope=FAULT_SCOPE,
        uncollapsed_member_identity_equivalence='NOT_ENUMERATED',
        provenance=dict(reference_frozen=binding(path) if path.exists() else None,
            selected_reference=reference['selection_receipt'],qualification=reference['provenance'],
            activity=binding(result_path) if result_path.exists() else None),
        measurement_failure=result if result and not qualified else None)
    for metric,label in (('routed_scan_wirelength_um','routed_WL'),('E','E'),('H4','H4'),('H8','H8')):
        row['delta_'+label+'_percent']=0. if row[metric] is not None else None
    return row


def audit_order(design, candidate=None):
    paths=[OUT/f'references/{design}/reference_frozen.json',OUT/f'inputs/{design}/cold_start_input.json',
        OUT/f'searches/{design}/search_configuration.json',OUT/f'searches/{design}/search_results.json',
        OUT/f'selections/{design}/preselected_candidates.json']
    names=['reference_frozen','cold_start_input','search_configuration','search_results','preselected_candidates']
    stamps=[];receipts={};values={};start_proof=None
    for name,path in zip(names,paths):
        value=maybe(path)
        values[name]=value
        receipts[name]=binding(path) if value else None
        stamps.append((name,value.get('created_utc') if value else None))
    if candidate:
        snapshot_path=OUT/f'physical/{design}/selection_snapshot.json'
        execution_path=OUT/f'physical/{design}/{candidate}/rewire/execution.json'
        snapshot=maybe(snapshot_path);execution=maybe(execution_path)
        receipts.update(selection_snapshot=binding(snapshot_path) if snapshot else None,
            rewire_execution=binding(execution_path) if execution else None)
        stamps.append(('selection_snapshot',snapshot.get('created_utc') if snapshot else None))
        if snapshot:
            selection=values['preselected_candidates']
            if selection is None or bound(snapshot['selection']).resolve()!=paths[-1].resolve() or bound(snapshot['input']).resolve()!=paths[1].resolve():
                raise ValueError('Physical selection snapshot does not bind this immutable selection/input')
            if not snapshot.get('all_candidates_frozen_before_any_candidate_routing'):
                raise ValueError('Physical selection snapshot does not freeze all candidates')
            for source in snapshot['executed_sources'].values():bound(source)
            def architecture_records(records):
                return [(r['candidate'],r['architecture_hash'],sha(bound(r['architecture']))) for r in records]
            if architecture_records(snapshot['records'])!=architecture_records(selection['records']):
                raise ValueError('Physical selection snapshot changed the frozen candidate list')
        if execution:
            if snapshot is None:
                raise ValueError('Physical execution lacks an immutable selection snapshot')
            selected=next((r for r in values['preselected_candidates']['records'] if r['candidate']==candidate),None)
            command=execution.get('command',[])
            if selected is None or command.count('--architecture')!=1:
                raise ValueError('Rewire execution does not identify one preselected architecture')
            index=command.index('--architecture')+1
            if index>=len(command) or local_path(command[index]).resolve()!=bound(selected['architecture']).resolve():
                raise ValueError('Rewire execution architecture differs from immutable preselection')
            wall=execution.get('wall_seconds')
            if not isinstance(wall,(int,float)) or not math.isfinite(wall) or wall<0 or not execution.get('timestamp_utc'):
                raise ValueError('Rewire execution lacks a valid measured execution interval')
            completed=datetime.fromisoformat(execution['timestamp_utc'])
            started=completed-timedelta(seconds=wall)
            stamps.extend((('rewire_execution_start_derived',started.isoformat()),('rewire_execution_completed',completed.isoformat())))
            start_proof=dict(selection_snapshot=receipts['selection_snapshot'],rewire_execution=receipts['rewire_execution'],
                architecture=selected['architecture'],execution_start_derived_utc=started.isoformat(),
                execution_completed_utc=completed.isoformat(),wall_seconds=wall,
                start_time_basis='Reconstructed execution-interval start: immutable completion timestamp minus measured wall_seconds; not a separately recorded process-launch timestamp')
        else:
            stamps.extend((('rewire_execution_start_derived',None),('rewire_execution_completed',None)))
        for name,path in (('physical_results',OUT/f'physical/{design}/{candidate}/route_result.json'),
            ('atpg_results',OUT/f'atpg/{design}/{candidate}/atpg_result.json')):
            value=maybe(path)
            if value and value.get('status') in ('PHYSICAL_GATES_PASS','ATPG_GATES_PASS') and start_proof is None:
                raise ValueError('Successful physical/ATPG gate lacks actual preselection-before-execution proof')
            receipts[name]=binding(path) if value else None
            stamps.append((name,value.get('created_utc') if value else None))
    present=[(label,datetime.fromisoformat(stamp)) for label,stamp in stamps if stamp]
    passed=all(a[1]<=b[1] for a,b in zip(present,present[1:]))
    if not passed:
        raise ValueError('Prospective receipt execution chronology failed: '+str(stamps))
    return dict(status='PASS' if all(stamp for _,stamp in stamps) else 'PARTIAL',timestamps=dict(stamps),
        receipts=receipts,preselection_before_physical_implementation=passed if start_proof else None,
        physical_execution_start_proof=start_proof,
        aggregate_receipt_timestamps='Physical/ATPG aggregate created_utc summarizes completed stages; per-candidate completions establish gate order, while bound selection_snapshot and rewire execution interval establish preselection before implementation')


def candidate_row(entry, selected, reference, search):
    design,name=entry['design'],selected['candidate']
    pf=OUT/f'physical/{design}/{name}';af=OUT/f'atpg/{design}/{name}'
    physical=maybe(pf/'route_result.json')
    atpg=maybe(af/'atpg_result.json')
    pending=maybe(pf/'qualification_pending_activity.json')
    activity=maybe(pf/'activity/result.json')
    physical_pass=physical is not None and physical.get('status')=='PHYSICAL_GATES_PASS'
    atpg_pass=atpg is not None and atpg.get('status')=='ATPG_GATES_PASS'
    exact=activity is not None and activity.get('status')=='QUALIFIED'
    qualified=physical_pass and atpg_pass and exact
    if qualified:
        if activity['architecture_sha256']!=selected['architecture_hash'] or not activity.get('VCD_complete'):
            raise ValueError('Exact activity candidate identity/completeness differs')
        bound(activity['summary']);crosscheck=read(bound(activity['FF_transitions']))
        if crosscheck['status']!='PASS' or any(v!='PASS' for v in physical['gates'].values()):
            raise ValueError('Candidate declared qualified while an exact gate failed')
        if read(bound(atpg['faults']))['status']!='PASS' or read(bound(atpg['serial']))['status']!='PASS':
            raise ValueError('Candidate FAN or serial receipt failed')
    row=dict(design=design,reference=reference['reference'],candidate=name,record_kind='PROSPECTIVE_PACT_CANDIDATE',
        architecture_hash=selected['architecture_hash'],FF_count=entry['FF_count'],
        ATPG_pattern_count=entry['ATPG_pattern_count'],parent_reference_hash=selected['parent_reference_hash'],
        preselected_primary='balanced' in selected['route_roles'],route_roles=selected['route_roles'],
        selection_order=selected['selection_order'],seed=selected['seed'],epsilon=selected['epsilon'],
        predicted_metrics=selected['metrics'],candidate_discovery={k:v for k,v in selected.items() if k.startswith('discovered_')},
        routed_scan_wirelength_um=physical.get('routed_scan_wirelength_um') if physical_pass else None,
        WNS=physical['structured_metrics']['setup_wns_ns'] if physical_pass else None,
        hold_WNS=physical['structured_metrics']['hold_wns_ns'] if physical_pass else None,
        DRC=physical.get('DRC_errors') if physical_pass else None,
        E=activity['E'] if qualified else None,H4=activity['H4'] if qualified else None,H8=activity['H8'] if qualified else None,
        qualification_status='QUALIFIED' if qualified else 'PENDING',
        physical_gates_status='PASS' if physical_pass else (pending.get('status') if pending else 'PENDING'),
        atpg_gates_status='PASS' if atpg_pass else (pending.get('status') if pending else 'PENDING'),
        activity_status=activity.get('status') if activity else 'PENDING',
        search_runtime_seconds=search.get('wall_seconds') if search else None,
        metric_scope=METRIC_SCOPE,fault_identity_scope=FAULT_SCOPE,uncollapsed_member_identity_equivalence='NOT_ENUMERATED',
        provenance=dict(selection=binding(OUT/f'selections/{design}/preselected_candidates.json'),
            search=selected['search_receipt'],architecture=selected['architecture'],
            physical=binding(pf/'route_result.json') if physical else None,
            ATPG=binding(af/'atpg_result.json') if atpg else None,
            exact_activity=binding(pf/'activity/result.json') if activity else None))
    if atpg_pass:
        statistics=atpg['statistics']
        row.update(target_faults=statistics['total'],detected_faults=statistics['detected'],
            fault_coverage=100*statistics['detected']/statistics['total'],FAN_reported_coverage=statistics['coverage'])
    else:row['fault_coverage']=None
    for metric,label in (('routed_scan_wirelength_um','routed_WL'),('E','E'),('H4','H4'),('H8','H8')):
        row['delta_'+label+'_percent']=delta(row[metric],reference[metric])
    category,relations=activity_category(row,reference)
    row.update(activity_relations=relations,status=category or 'PENDING')
    if category=='PACT_MIXED_TRADEOFF':
        row['tradeoff_subtype']='ACTIVITY_IMPROVEMENT_WITH_REGRESSION' if 'regressed' in relations.values() else 'PARTIAL_ACTIVITY_IMPROVEMENT_NO_REGRESSION'
    if qualified and category is None:
        row.update(status='PACT_EXECUTION_BLOCKED',failure_class=(reference.get('measurement_failure') or {}).get('failure_class','REFERENCE_ACTIVITY_UNAVAILABLE'),
            blocker_subtype='REFERENCE_ACTIVITY_UNAVAILABLE')
    elif pending and pending.get('status') in ('PACT_PHYSICAL_FAILURE','PACT_TEST_CORRECTNESS_FAILURE'):
        row.update(status=pending['status'],qualification_status='FAILED',failure_class=pending.get('failure_class'),failure=pending)
    elif activity and not exact:
        row.update(status='PACT_PHYSICAL_FAILURE',qualification_status='FAILED',failure_class=activity.get('failure_class'),failure=activity)
    row['receipt_order_audit']=audit_order(design,name)
    return row


def solver_rows(entry):
    design=entry['design'];folder=OUT/'searches'/design
    summary=maybe(folder/'search_results.json');worker=maybe(OUT/f'scalability/{design}_solver_execution.json')
    resources=resource_file(worker)
    rows=[]
    for path in sorted(folder.glob('budget_*/search.json')):
        lane=read(path);config=lane['config'];instrument=lane.get('instrumentation',{})
        elapsed=lane['search_seconds'];evaluations=lane['evaluations']
        rows.append(dict(design=design,FF_count=entry['FF_count'],ATPG_pattern_count=entry['ATPG_pattern_count'],
            target_fault_count=entry['ATPG_target_fault_count'],epsilon=config['epsilon'],seed=config['seed'],
            status='LANE_COMPLETE',registered_loop_seconds=config['seconds'],
            model_setup_seconds=summary.get('model_setup_seconds') if summary else (maybe(folder/'initialization.json') or {}).get('seconds'),
            lane_initialization_seconds=lane['initialization_seconds'],search_loop_seconds=elapsed,
            lane_total_seconds=lane['runtime_seconds'],solver_worker_wall_seconds=worker.get('execution',{}).get('wall_seconds') if worker else None,
            solver_worker_CPU_seconds=resources.get('CPU_seconds'),solver_worker_peak_RSS_KiB=resources.get('peak_RSS_KiB'),
            exact_mutation_evaluations=evaluations,exact_state_score_calls=instrument.get('state_score_calls'),
            independent_replays=instrument.get('independent_replays'),exact_mutation_evaluations_per_second=evaluations/elapsed if elapsed else None,
            attempts=lane['attempts'],screened_infeasible=lane['screened_infeasible'],accepted_moves=lane['accepted'],
            rejected_exact_moves=lane.get('rejected_exact_moves',evaluations-lane['accepted']),
            archive_insertions=lane.get('archive_insertions'),initial_reference_archive_insertions=lane.get('initial_reference_archive_insertions'),
            archive_size=lane['archive_size'],restarts=lane.get('restarts'),final_stagnation_attempts=lane.get('final_stagnation_attempts'),
            stagnation_termination_events=lane.get('stagnation_termination_events'),termination=lane['termination'],
            state_score_seconds=instrument.get('state_score_seconds'),independent_replay_seconds=instrument.get('independent_replay_seconds'),
            model_profile=lane.get('model_profile'),source_receipt=binding(path)['path'],
            timing_scope='SOLVER_ONLY; lane timings exclusive by epsilon; model setup and whole-worker CPU/RSS repeat for context and must not be summed across lanes',
            **evaluator_accounting(lane)))
    return rows


def measurement_rows():
    rows=[]
    for path in sorted((OUT/'physical').glob('*/*/activity/result.json')):
        result=read(path);instrument=read(path.parent/'instrumentation.json')
        stages=instrument.get('stages',{});analysis=instrument.get('analysis') or {}
        analysis_stages=analysis.get('stages',{})
        diagnosis_path=OUT/f'scalability/measurement_{result["design"]}_terminal_diagnosis.json'
        diagnosis=maybe(diagnosis_path) if result['role'].startswith('REF_') and result['status']=='FAILED' else None
        if diagnosis and bound(diagnosis['result']).resolve()!=path.resolve():
            raise ValueError('Independent reference timeout diagnosis binds another result')
        rows.append(dict(design=result['design'],candidate=result['role'],status=result['status'],
            failure_class=result.get('failure_class'),compile=stages.get('compile'),simulation=stages.get('simulate'),
            VCD_generation=instrument.get('VCD_generation'),VCD=instrument.get('VCD'),
            VCD_parse=analysis_stages.get('vcd_parse'),VCD_parse_and_transition=analysis_stages.get('vcd_parse_and_transition'),
            transition_extraction=analysis_stages.get('transition_extraction'),
            E_computation=analysis_stages.get('E_computation_all_data'),H4_computation=analysis_stages.get('H4_computation_all_data'),
            H8_computation=analysis_stages.get('H8_computation_all_data'),
            total_wall_seconds=result['wall_seconds'],CPU_seconds=result.get('CPU_seconds'),peak_RSS_KiB=result.get('peak_RSS_KiB'),
            fixed_deadline_seconds=result.get('timeout_seconds'),error=result.get('error'),
            terminal_diagnosis=diagnosis,terminal_diagnosis_receipt=binding(diagnosis_path) if diagnosis else None,
            scope='PHYSICAL_MEASUREMENT_ONLY; exact all_data metrics; inclusive/exclusive parser spans not additive',
            result=binding(path),instrumentation=binding(path.parent/'instrumentation.json')))
    return rows


def measurement_worker_failures():
    """Measurement workers belong to the physical domain before a result is flushed."""
    rows=[]
    for path in sorted((OUT/'failures').glob('*measurement*.json')):
        value=read(path)
        if value.get('status') in ('FAILED','PACT_EXECUTION_BLOCKED','PACT_PHYSICAL_FAILURE'):
            rows.append(dict(design=value.get('design'),failure_class=value.get('failure_class'),
                failure_domain='MEASUREMENT',scope='PHYSICAL_MEASUREMENT_ONLY',receipt=binding(path),record=value))
    return rows


def collect():
    campaign=read(OUT/'manifests/campaign_preregistration.json')
    records=[];outcomes=[];scalability=[]
    for entry in campaign['designs']:
        design=entry['design'];reference=reference_row(entry)
        verify_search_provenance(design)
        input_path=OUT/f'inputs/{design}/cold_start_input.json'
        initialization=initialization_evidence(design)
        search=maybe(OUT/f'searches/{design}/search_results.json')
        selection=maybe(OUT/f'selections/{design}/preselected_candidates.json')
        worker=maybe(OUT/f'scalability/{design}_solver_execution.json')
        row=dict(design=design,FF_count=entry['FF_count'],ATPG_pattern_count=entry['ATPG_pattern_count'],
            eligible=entry['eligible'],attempted=not entry['eligible'] or input_path.exists(),
            **initialization,
            search_completed=bool(search and search.get('status')=='SEARCH_COMPLETE'),
            selected_reference=reference['reference'] if reference else None,
            primary_candidate=selection.get('primary_candidate') if selection else None,
            preselected_candidates=[r['candidate'] for r in selection['records']] if selection else [],
            status='PENDING',primary_scientific_category=None,terminal=False,zero_historical_state=True,candidates=[])
        if reference:records.append(reference)
        if not entry['eligible']:
            row.update(status='PACT_EXECUTION_BLOCKED',terminal=True,failure_class='SCAN_TOPOLOGY_FAIL',reason=entry['blocked_reason'])
        elif selection:
            candidates=[candidate_row(entry,r,reference,search) for r in selection['records']]
            row['candidates']=candidates;records.extend(candidates)
            primary=next((r for r in candidates if r['candidate']==row['primary_candidate']),None)
            if not candidates:
                row.update(status='PACT_NO_BENEFIT',terminal=True,reason='No new pre-route role champion; no candidate was routed',
                    conclusion_scope='SEARCH_NO_NEW_CANDIDATE; exact reference remains unchanged')
            elif primary:
                row.update(status=primary['status'],terminal=all(r['status']!='PENDING' for r in candidates),
                    primary_scientific_category=primary['status'] if primary['activity_relations'] else None,
                    conclusion_scope='PRESELECTED_BALANCED_PRIMARY; all retained alternatives remain in scientific counts')
                if primary.get('failure_class'):row['failure_class']=primary['failure_class']
            else:
                finished=all(r['status']!='PENDING' for r in candidates)
                row.update(status='INITIAL_REFERENCE_RETAINED' if finished else 'PENDING',
                    terminal=finished,primary_architecture='UNCHANGED_EXTERNAL_REFERENCE',
                    conclusion_scope='Balanced winner remained the frozen reference; only preselected endpoint alternatives are new candidates')
        elif worker and worker.get('status')=='FAILED':
            row.update(status='PACT_EXECUTION_BLOCKED',terminal=True,failure_class=worker.get('failure_class'),failure_domain='SOLVER',failure=worker)
        else:
            failures=[p for p in (OUT/f'failures/{design}_prepare.json',OUT/f'failures/{design}_search.json') if p.exists()]
            if failures:
                row.update(status='PACT_EXECUTION_BLOCKED',terminal=True,failure_class='FRAMEWORK_INPUT_OR_EXECUTION',failure=read(failures[-1]))
        stop=terminal_design_stop(design,reference['reference'] if reference else None)
        if entry['eligible'] and stop:
            row.update(stop)
            for candidate in row['candidates']:
                if candidate['status']=='PENDING':
                    candidate.update(status='PACT_EXECUTION_BLOCKED',qualification_status='STOPPED_BEFORE_COMPLETION',
                        failure_class=stop['failure_class'],failure_domain=stop['failure_domain'],stop_receipt=stop['stop_receipt'])
        row['qualified_candidates']=[r['candidate'] for r in row['candidates'] if r['qualification_status']=='QUALIFIED']
        row['activity_improvements']={m:any(r['activity_relations'].get(m)=='improved' for r in row['candidates']) for m in ('E','H4','H8')}
        row['all_three_improved']=any(all(r['activity_relations'].get(m)=='improved' for m in ('E','H4','H8')) for r in row['candidates'])
        row['any_candidate_mixed_tradeoff']=any(r['status']=='PACT_MIXED_TRADEOFF' for r in row['candidates'])
        row['alternative_mixed_tradeoff']=any(r['status']=='PACT_MIXED_TRADEOFF' and r['candidate']!=row['primary_candidate'] for r in row['candidates'])
        row['any_candidate_no_or_negligible_benefit']=any(r['status'] in ('PACT_NO_BENEFIT','PACT_NEGLIGIBLE_BENEFIT') for r in row['candidates'])
        outcomes.append(row);scalability.extend(solver_rows(entry))
    counts=dict(unseen_designs_registered=len(outcomes),unseen_designs_attempted=sum(r['attempted'] for r in outcomes),
        initialized_without_historical_state=sum(r['initialized'] for r in outcomes),
        searches_completed=sum(r['search_completed'] for r in outcomes),
        candidates_preselected=sum(len(r['candidates']) for r in outcomes),
        candidates_physically_qualified=sum(len(r['qualified_candidates']) for r in outcomes),
        designs_with_physically_qualified_candidate=sum(bool(r['qualified_candidates']) for r in outcomes),
        designs_improving_E=sum(r['activity_improvements']['E'] for r in outcomes),
        designs_improving_H4=sum(r['activity_improvements']['H4'] for r in outcomes),
        designs_improving_H8=sum(r['activity_improvements']['H8'] for r in outcomes),
        designs_improving_all_three=sum(r['all_three_improved'] for r in outcomes),
        designs_with_useful_activity_improvement=sum(any(r['activity_improvements'].values()) for r in outcomes),
        designs_with_mixed_or_no_improvement=sum(r['status'] in ('PACT_MIXED_TRADEOFF','PACT_NO_BENEFIT','PACT_NEGLIGIBLE_BENEFIT') for r in outcomes),
        designs_with_any_mixed_candidate=sum(r['any_candidate_mixed_tradeoff'] for r in outcomes),
        designs_with_alternative_mixed_candidate=sum(r['alternative_mixed_tradeoff'] for r in outcomes),
        designs_with_any_no_or_negligible_candidate=sum(r['any_candidate_no_or_negligible_benefit'] for r in outcomes),
        designs_blocked=sum(r['terminal'] and r['status'] in ('PACT_EXECUTION_BLOCKED','PACT_PHYSICAL_FAILURE','PACT_TEST_CORRECTNESS_FAILURE') for r in outcomes),
        designs_terminal=sum(r['terminal'] for r in outcomes))
    engineering=[binding(p) for p in sorted((OUT/'repair_attempts').rglob('*.json'))]
    return dict(schema='pact_cold_start_canonical_v1',assembled_utc=now(),campaign=binding(OUT/'manifests/campaign_preregistration.json'),
        counts=counts,prospective_unseen_records=records,design_outcomes=outcomes,solver_scalability=scalability,
        physical_measurement_scalability=measurement_rows(),measurement_worker_failures=measurement_worker_failures(),engineering_retry_evidence=engineering,
        historical_qualified_core=read(CORE/'canonical_results.json'),historical_source=binding(CORE/'canonical_results.json'),
        comparison_tolerance='1e-10*max(1,abs(reference)); exact downstream measurements only',
        useful_improvement_definition='At least one exact E/H4/H8 improvement among preselected qualified candidates; regressions and routed-wire cost remain reported',
        architecture_selection='Frozen pre-route balanced primary, E, H4, H8 roles with exact hash deduplication; at most three; no post-route reselection')


def scientific_assessment(data, sealed=False):
    if not sealed:return 'CAMPAIGN_ACTIVE_SNAPSHOT',[]
    outcomes=data['design_outcomes'];counts=data['counts'];secondary=[]
    solver_block=any(r.get('failure_class')=='RESOURCE_LIMIT' and r.get('failure_domain')=='SOLVER' for r in outcomes)
    measurement_block=any(r.get('failure_class')=='RESOURCE_LIMIT' for r in data['physical_measurement_scalability']) or any(
        r.get('failure_class')=='RESOURCE_LIMIT' for r in data.get('measurement_worker_failures',[])) or any(
        r.get('failure_class')=='RESOURCE_LIMIT' and r.get('failure_domain')=='MEASUREMENT' for r in outcomes)
    if solver_block:secondary.append('PACT_COLD_START_SOLVER_SCALABILITY_BLOCKED')
    if measurement_block:secondary.append('PACT_COLD_START_MEASUREMENT_SCALABILITY_BLOCKED')
    if counts['designs_with_physically_qualified_candidate']==0:
        primary='PACT_COLD_START_FRAMEWORK_INCOMPLETE'
    elif counts['designs_with_useful_activity_improvement']==0:
        primary='PACT_COLD_START_GENERALIZATION_NOT_SUPPORTED'
    elif counts['designs_with_mixed_or_no_improvement'] or counts['designs_improving_all_three']<counts['designs_with_physically_qualified_candidate']:
        primary='PACT_COLD_START_GENERALIZATION_MIXED'
    else:primary='PACT_COLD_START_GENERALIZATION_SUPPORTED'
    return primary,secondary


def profile_summary(data):
    grouped={}
    for row in data['solver_scalability']:
        profile=grouped.setdefault(row['design'],dict(FF_count=row['FF_count'],ATPG_pattern_count=row['ATPG_pattern_count'],components={}))
        for name,value in (row.get('model_profile') or {}).items():
            if name.endswith('_seconds'):
                profile['components'][name]=profile['components'].get(name,0.)+value
    result=[]
    for design,profile in grouped.items():
        components=profile['components']
        largest=max(components,key=components.get) if components else None
        result.append(dict(design=design,**profile,largest_observed_evaluator_component=largest,
            largest_component_seconds=components.get(largest),
            scope='Summed exclusive epsilon profile increments; partial evaluator instrumentation, not complete loop attribution'))
    return sorted(result,key=lambda row:row['FF_count'])


def solver_bottleneck_observation(data):
    large=next((r for r in data['solver_scalability'] if r['FF_count']>=600),None)
    if large is None:return None
    components=sorted(((k,v) for k,v in (large.get('model_profile') or {}).items() if k.endswith('_seconds')),
        key=lambda item:-item[1])
    small=[r['exact_mutation_evaluations_per_second'] for r in data['solver_scalability'] if r['FF_count']<600]
    return dict(design=large['design'],epsilon=large['epsilon'],FF_count=large['FF_count'],
        ATPG_pattern_count=large['ATPG_pattern_count'],exact_evaluations=large['exact_mutation_evaluations'],
        loop_seconds=large['search_loop_seconds'],evaluations_per_second=large['exact_mutation_evaluations_per_second'],
        largest_instrumented_evaluator_spans=[dict(component=k,seconds=v) for k,v in components[:2]],
        small_observed_evaluations_per_second_range=[min(small),max(small)] if small else None,
        resource_policy_failure=False,
        scope='First completed lane on a size-scaled design; observed computational profile only, not a fitted scaling law or hardware-cause attribution')


def display(value, digits=3):
    if value is None:return 'N/A'
    if isinstance(value,float):return f'{value:.{digits}f}'
    return str(value)


def reference_failure_prose(data):
    """State new independent failures separately from earlier timeout evidence."""
    lines=['Earlier campaign measurement evidence (separate from new attempts): the prior s38417 reference VVP simulation reached its fixed 1,800-second deadline before parsing or metric reductions. Its retained partial VCD and prior timeout diagnosis are diagnostic only and do not terminate a new campaign unit or supply E/H4/H8.']
    for row in data['physical_measurement_scalability']:
        if not row['candidate'].startswith('REF_') or row['status']!='FAILED':continue
        simulation=row.get('simulation') or {};diagnosis=row.get('terminal_diagnosis') or {}
        deadline=row.get('fixed_deadline_seconds') or diagnosis.get('fixed_deadline_seconds')
        reason=f'reached its independently fixed {display(deadline)}-second deadline during functional VVP simulation with integrated VCD emission' if simulation.get('timed_out') else row.get('error') or row.get('failure_class')
        vcd=row.get('VCD') or {}
        lines.append(f'New independent {row["design"]} {row["candidate"]} exact-reference attempt: FAILED/{row.get("failure_class")}; {reason}. '+
            f'Workflow wall {display(row["total_wall_seconds"])} s, CPU {display(row.get("CPU_seconds"))} s, maximum process RSS {display(row.get("peak_RSS_KiB"))} KiB; '+
            f'VVP wall {display(simulation.get("wall_seconds"))} s, CPU {display(simulation.get("CPU_seconds"))} s, process RSS {display(simulation.get("peak_RSS_KiB"))} KiB. '+
            f'VCD complete={vcd.get("complete")}, bytes={display(vcd.get("bytes"))}; parser/transition and exact E/H4/H8 stages '+
            ('were not executed.' if diagnosis.get('parser_transition_and_E_H_stages_executed') is False else 'have no qualified result.')+
            ' No partial activity value is included. Only this design stops under the independent-unit policy; the other registered units continue independently. '+
            f'Result: {row["result"]["path"]}; new terminal diagnosis: '+
            (row['terminal_diagnosis_receipt']['path'] if row.get('terminal_diagnosis_receipt') else 'unavailable')+'.')
    return lines


def markdown(data, sealed=False):
    c=data['counts'];primary,secondary=scientific_assessment(data,sealed)
    text=[f'Cold-start unseen designs attempted: {c["unseen_designs_attempted"]}',
        f'Cold-start searches completed: {c["searches_completed"]}',
        f'PACT candidates physically qualified: {c["candidates_physically_qualified"]}',
        f'Designs with useful activity improvement: {c["designs_with_useful_activity_improvement"]}',
        f'Designs with mixed/no improvement: {c["designs_with_mixed_or_no_improvement"]}',
        f'Designs blocked by infrastructure/scalability: {c["designs_blocked"]}','',
        f'Classification: `{primary}`.',
        'Milestone: `PACT_COLD_START_UNSEEN_DESIGN_CAMPAIGN_COMPLETE`.' if sealed else 'This is an active snapshot. Pending designs and candidates have no scientific outcome yet.',
        'Secondary classifications: '+(', '.join('`'+s+'`' for s in secondary) if secondary else 'none established in this report.')+'','',
        'PROSPECTIVE UNSEEN COLD-START RESULTS','',
        '| Design | Reference | PACT candidate | Δ routed WL % | ΔE % | ΔH4 % | ΔH8 % | WNS ns | DRC | Fault coverage % | Search runtime s | Status |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for row in data['prospective_unseen_records']:
        if row['record_kind']!='PROSPECTIVE_PACT_CANDIDATE':continue
        values=[row['design'],row['reference'],row['candidate'],*[display(row.get('delta_'+m+'_percent')) for m in ('routed_WL','E','H4','H8')],
            display(row['WNS']),display(row['DRC']),display(row['fault_coverage']),display(row['search_runtime_seconds']),row['status']]
        text.append('| '+' | '.join(values)+' |')
    text+=['','Negative percentages are improvements. N/A means unavailable exact data. Search estimates are kept in JSON and never substituted for measured activity. Physically qualified means route/topology/function/placement/timing/DRC, FAN identities/weights, and complete VCD FF transitions all passed.',
        'Useful activity improvement counts any exact E/H4/H8 gain above the fixed tolerance among retained candidates. It does not erase another metric regression or routed-wire increase. The design status follows its preselected balanced primary. All alternatives contribute to explicitly named any-candidate counts.','',
        '| Design | FFs | FAN patterns | Reference | Initialized | Search completed | Preselected | Qualified | Design status | Blocker reason |',
        '|---|---:|---:|---|---|---|---:|---:|---|---|']
    for r in data['design_outcomes']:
        text.append('| '+' | '.join(map(str,(r['design'],r['FF_count'],r['ATPG_pattern_count'],r['selected_reference'] or 'N/A',
            r['initialized'],r['search_completed'],len(r['preselected_candidates']),len(r['qualified_candidates']),r['status'],(r.get('reason') or r['failure_class']) if r.get('failure_class') else 'N/A')))+' |')
    text+=['',f'{c["initialized_without_historical_state"]} designs initialized with zero historical per-design state; {c["searches_completed"]} completed all registered epsilon lanes; {c["designs_with_physically_qualified_candidate"]} produced at least one exactly qualified candidate.',
        f'E improved on {c["designs_improving_E"]} designs, H4 on {c["designs_improving_H4"]}, H8 on {c["designs_improving_H8"]}, and all three on {c["designs_improving_all_three"]}. Routed cost, WNS, DRC and weighted FAN coverage accompany every available comparison above.',
        f'The opening mixed/no count describes {c["designs_with_mixed_or_no_improvement"]} preselected-primary outcomes (including completed searches with no new candidate). Separately, {c["designs_with_any_mixed_candidate"]} designs have at least one exact mixed candidate, including {c["designs_with_alternative_mixed_candidate"]} with a mixed alternative; {c["designs_with_any_no_or_negligible_candidate"]} have a no/negligible-benefit candidate. These flags can overlap useful-improvement counts and never change the primary.',
        'The minimum qualified routed scan cost among B0/B1/B2/B3T was frozen before input construction. The selected external architecture is the sole search start. No P0, prior PACT archive, precursor search, manually mapped unseen design, learned initialization or tuned weights are used. Seed 11, K=2, epsilons .02/.05/.10 and all existing operators/archive/restart settings remain fixed. Mutation-loop budgets are 300*max(1,ceil(FF/600)) seconds. s208 and s510 remain blocked by the minimum eight FFs per chain.','',
        'Solver and physical scalability','',
        'scalability/solver_scalability.csv and .json report completed epsilon lanes independently. Model setup, lane initialization, mutation loop, independent replay and full worker timing are different domains. Whole-worker CPU/RSS and model setup repeat as context in lane rows and must not be summed. Exact mutation evaluations exclude wire-screened proposals; exact state-score calls and independent replay counters are also retained. Archive admission counts include the explicitly reported initial reference insertion.',
        'The measured evaluator subtotal adds six disjoint original forward/rollback/reduction spans across the whole lane. state_score_seconds overlaps reduction_seconds and is not added again. Independent retained-candidate replay is reported separately, after the mutation loop. Whole-lane un-attributed time is the remainder after those measured components and replay; it includes untimed evaluator construction/restarts, allocations/setup and solver work. solver_overhead_seconds is unavailable. No component subtotal is subtracted from mutation-loop time to invent an overhead measurement.',
        'scalability/physical_measurement_scalability.json reports compile, VVP simulation, VCD bytes, parser/transition spans and exact E/H4/H8 reductions separately. VCD generation shares the VVP process; isolated generation time is unavailable. Parser CPU/RSS are inclusive; exclusive parse/transition wall times must not be added to their inclusive span.','',
        '| Design | FFs | Patterns | Epsilon | Exact mutations | Eval/s | Loop s | Termination |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for r in data['solver_scalability']:
        text.append('| '+' | '.join(display(r.get(k)) for k in ('design','FF_count','ATPG_pattern_count','epsilon',
            'exact_mutation_evaluations','exact_mutation_evaluations_per_second','search_loop_seconds','termination'))+' |')
    profiles=profile_summary(data)
    if profiles:
        largest=profiles[-1]
        text+=['',f'For the largest observed search ({largest["design"]}, {largest["FF_count"]} FFs, {largest["ATPG_pattern_count"]} FAN patterns), the largest instrumented evaluator component is {largest["largest_observed_evaluator_component"]}: {display(largest["largest_component_seconds"])} seconds across completed lanes. This profile covers evaluator components and does not attribute all initialization, solver overhead or independent replay time.']
    computational=solver_bottleneck_observation(data)
    if computational:
        components=', '.join(f'{r["component"]} {display(r["seconds"])} s' for r in computational['largest_instrumented_evaluator_spans'])
        small=computational['small_observed_evaluations_per_second_range']
        text+=['',f'First observed solver computational bottleneck: {computational["design"]} epsilon {computational["epsilon"]:.2f} concentrated measured evaluator time in {components}. The lane performed {computational["exact_evaluations"]} exact mutations in {display(computational["loop_seconds"])} loop seconds ({display(computational["evaluations_per_second"])} evaluations/s).'+
            (f' Completed small-design lanes ranged from {display(small[0])} to {display(small[1])} evaluations/s.' if small else '')+
            ' This observation is separate from a registered resource-policy failure. It establishes neither a scaling law nor a memory-bandwidth or other hardware cause.']
    solver_failed=[r for r in data['design_outcomes'] if r.get('failure_class')=='RESOURCE_LIMIT' and r.get('failure_domain')=='SOLVER']
    text+=['','First observed solver resource bottleneck: '+(solver_failed[0]['design']+' exceeded its registered worker policy; preserve its failure receipt.' if solver_failed else 'No solver resource bottleneck established by completed observations; limited samples do not support extrapolation.'),
        *reference_failure_prose(data),
        'Solver runtime growth is observable only through the measured FF/pattern/evaluation rows. No fitted scalability law or extrapolated FF cutoff is claimed. Sparse size coverage and workload differences prevent attributing a runtime change solely to FF count.','',
        'Execution hardware: WSL kernel 6.18.33.2, four logical cores, MemTotal 4,010,612 KiB and 8 GiB swap. Solver and physical measurement jobs may overlap. These runtimes are observations from concurrent campaign execution, not isolated scaling benchmarks.','',
        'Provenance and limits','',
        'reference_frozen -> cold_start_input -> search_configuration -> search_results -> preselected_candidates -> selection_snapshot -> per-candidate rewire -> physical -> ATPG -> final_qualification is audited by bound receipts. The immutable selection snapshot binds every retained candidate and the input; each rewire command binds its preselected architecture. Rewire execution-interval starts are reconstructed explicitly as completion timestamp minus measured wall duration, proving selection preceded implementation; they are not separately recorded process-launch timestamps. Physical/ATPG per-candidate completions establish subsequent gate order, and aggregate timestamps summarize completed gates. Every retained candidate remains in the dataset, including failures. Engineering observer repairs and failed diagnostic attempts are retained separately from scientific outcomes.',
        'The metric scope remains all_data ground-plus-pin capacitance times measured transitions. H4/H8 locate demand at sources in fixed spatial bins per cycle. Routed scan cost is the connected scan-net upper bound and can include functional branches. Search scores omit unrepresented fanins, delay/glitches and candidate resizing/buffer changes; actual route and exact activity remain authoritative. These are not watts, IR-drop, signoff power, reliability, or uncollapsed-member identity claims.','',
        'HISTORICAL QUALIFIED CORE','',
        'The s5378/s9234/s15850 core appears only in canonical/historical_qualified_core.json and this separate section. All 12 original record dictionaries and historical primary choices are copied exactly, with their original values and classifications. They were not cold-start training, seeds or runtime inputs.','',
        '| Historical design | Frozen reference | Frozen primary |', '|---|---|---|']
    historical=data['historical_qualified_core']
    for design in ('s5378','s9234','s15850'):
        ref=next(r['candidate'] for r in historical['records'] if r['design']==design and r['method'] in ('B0','B1','B2','B3T'))
        text.append(f'| {design} | {ref} | {historical["primary_candidates"][design]} |')
    return '\n'.join(text)+'\n'


def final_qualification(data):
    """Freeze terminal design outcomes after all stage artifacts are available."""
    for outcome in data['design_outcomes']:
        design=outcome['design'];path=OUT/f'canonical/{design}/final_qualification.json'
        stages={name:binding(p) if p.exists() else None for name,p in (
            ('reference_frozen',OUT/f'references/{design}/reference_frozen.json'),
            ('cold_start_input',OUT/f'inputs/{design}/cold_start_input.json'),
            ('search_configuration',OUT/f'searches/{design}/search_configuration.json'),
            ('search_results',OUT/f'searches/{design}/search_results.json'),
            ('preselected_candidates',OUT/f'selections/{design}/preselected_candidates.json'),
            ('selection_snapshot',OUT/f'physical/{design}/selection_snapshot.json'),
            ('physical_results',OUT/f'physical/{design}/physical_results.json'),
            ('atpg_results',OUT/f'atpg/{design}/atpg_results.json'))}
        record=dict(schema='pact_cold_start_final_qualification_v1',created_utc=now(),design=design,
            status=outcome['status'],terminal=outcome['terminal'],outcome=outcome,stage_receipts=stages,
            candidate_count=len(outcome['preselected_candidates']),all_preselected_candidates_retained=True,
            scientific_method_change=False)
        write(path,record,immutable=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',action='store_true');parser.add_argument('--seal',action='store_true')
    args=parser.parse_args()
    if args.seal and args.snapshot:parser.error('Choose snapshot or seal')
    data=collect();status,secondary=scientific_assessment(data,args.seal)
    data.update(status=status,secondary_classifications=secondary,
        repository_sha_at_assembly=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        repository_branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        execution_hardware=dict(WSL_kernel='6.18.33.2',logical_cores=4,MemTotal_KiB=4010612,swap_GiB=8,
            concurrent_jobs=True,isolated_scaling_benchmark=False))
    data['observed_evaluator_profiles']=profile_summary(data)
    data['first_observed_solver_computational_bottleneck']=solver_bottleneck_observation(data)
    if not args.seal:
        write(OUT/'logs/progress_snapshot.json',data)
        path=OUT/'logs/report_snapshot.md';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(markdown(data),encoding='utf-8')
        print('COLD_START_SNAPSHOT',json.dumps(data['counts'],sort_keys=True),flush=True)
        return
    if data['counts']['designs_terminal']!=data['counts']['unseen_designs_registered']:
        raise ValueError('Cannot seal while a registered design remains pending')
    # Validate all assembly before making immutable final receipts.
    destinations=[OUT/'manifests/frozen_core_verification_at_report.json',OUT/'canonical/historical_qualified_core.json',
        OUT/'canonical/prospective_unseen_canonical.json',OUT/'canonical/prospective_unseen_results.csv',
        OUT/'scalability/solver_scalability.json',OUT/'scalability/solver_scalability.csv',
        OUT/'scalability/physical_measurement_scalability.json',OUT/'cold_start_report.md',OUT/'completion.json']
    destinations += [OUT/f'canonical/{r["design"]}/final_qualification.json' for r in data['design_outcomes']]
    if any(p.exists() for p in destinations):
        raise ValueError('Preserve existing sealed artifacts; use snapshot for subsequent inspection')
    data['frozen_core_verification']=verify_frozen_core()
    report=markdown(data,True)
    write(OUT/'manifests/frozen_core_verification_at_report.json',data['frozen_core_verification'],immutable=True)
    final_qualification(data)
    write(OUT/'canonical/historical_qualified_core.json',data['historical_qualified_core'],immutable=True)
    write(OUT/'canonical/prospective_unseen_canonical.json',data,immutable=True)
    table=OUT/'canonical/prospective_unseen_results.csv'
    if table.exists():raise ValueError('Preserve existing canonical table')
    table.write_text(csv_text(TABLE_FIELDS,data['prospective_unseen_records']),encoding='utf-8')
    write(OUT/'scalability/solver_scalability.json',dict(schema='pact_cold_start_solver_scalability_v1',
        scope='SOLVER_ONLY',records=data['solver_scalability'],worker_failures=[r for r in data['design_outcomes'] if r.get('failure_class')=='RESOURCE_LIMIT' and r.get('failure_domain')=='SOLVER'],
        engineering_retries=data['engineering_retry_evidence'],timing_domains='No routing, ATPG or physical measurement included'),immutable=True)
    solver_csv=OUT/'scalability/solver_scalability.csv'
    if solver_csv.exists():raise ValueError('Preserve existing solver table')
    solver_csv.write_text(csv_text(SOLVER_FIELDS,data['solver_scalability']),encoding='utf-8')
    write(OUT/'scalability/physical_measurement_scalability.json',dict(schema='pact_cold_start_physical_measurement_scalability_v1',
        scope='PHYSICAL_MEASUREMENT_ONLY',records=data['physical_measurement_scalability'],worker_failures=data['measurement_worker_failures'],
        prior_reference_timeout=binding(OUT/'scalability/measurement_prior_timeout_diagnosis_s38417.json')
            if (OUT/'scalability/measurement_prior_timeout_diagnosis_s38417.json').exists() else None),immutable=True)
    report_path=OUT/'cold_start_report.md'
    if report_path.exists():raise ValueError('Preserve final report')
    report_path.write_text(report,encoding='utf-8')
    write(OUT/'completion.json',dict(schema='pact_cold_start_completion_v1',created_utc=now(),
        milestone='PACT_COLD_START_UNSEEN_DESIGN_CAMPAIGN_COMPLETE',status=status,
        secondary_classifications=secondary,counts=data['counts'],scientific_method_changes=0,
        repository_sha_at_assembly=data['repository_sha_at_assembly'],artifacts={name:binding(path) for name,path in (
            ('report',report_path),('canonical',OUT/'canonical/prospective_unseen_canonical.json'),('table',table),
            ('historical_core',OUT/'canonical/historical_qualified_core.json'),('solver_scalability',solver_csv))}),immutable=True)
    print('COLD_START_REPORT_SEALED',status,json.dumps(data['counts'],sort_keys=True),flush=True)


if __name__=='__main__':main()
