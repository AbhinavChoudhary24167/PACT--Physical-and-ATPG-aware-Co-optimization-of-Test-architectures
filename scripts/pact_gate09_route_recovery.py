#!/usr/bin/env python3
"""Recover qualification of retained routes after a proven launch-path defect.

No synthesis, placement, ATPG generation, architecture generation or rerouting.
The same qualified FAN backend and frozen physical gates are required.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import resource
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_reference as reference
from pact_experiment_receipts import atomic_write


def retain_preparation(path, source, certificate, worker_path):
    old = admission.read(path)
    worker = admission.read(worker_path)
    if (old['design'] != source['design'] or old['source'] != source['mapped_netlist'] or
            old['status'] != 'PLACEMENT_READY_PENDING_REFERENCES' or set(old['gates'].values()) != {'PASS'} or
            worker['status'] != 'PLACEMENT_READY_PENDING_REFERENCES' or
            worker['common_FAN_backend'] != certificate['binary'] or
            admission.verify(worker['receipt'])['status'] != 'PASS'):
        raise ValueError('Retained preparation must use the identical admitted source and qualified backend')
    for key in ('source', 'patterns', 'placed_def', 'placed_netlist', 'config', 'SDC', 'source_placed_database'):
        if admission.verify(old[key])['status'] != 'PASS':
            raise ValueError('Retained preparation changed: ' + key)
    for key in ('ATPG_execution', 'placement_execution', 'seed_execution'):
        value = old[key]
        if value['exit_code'] or value['timed_out'] or any(
                admission.verify(value[stream])['status'] != 'PASS' for stream in ('stdout', 'stderr')):
            raise ValueError('Retained preparation execution is not qualified')
    return dict(old, retention=dict(classification='QUALIFIED_RUNTIME_MODULE_PATH_REPAIR',
        preparation=admission.binding(path), original_worker=admission.binding(worker_path),
        identical_qualified_backend=True, additional_ATPG_generations=0,
        additional_placement_executions=0, scientific_method_changes=0))


def run(args):
    started = time.perf_counter()
    if args.attempt == args.prior_attempt:
        raise ValueError('Recovery must preserve the original namespace')
    oldmeta, oldraw = reference.repair_namespace(args.prior_attempt, args.dependency_repair)
    old_records = admission.read(oldmeta / f'baselines/{args.design}_references.json')
    if {row['method'] for row in old_records['records']} != {'B0', 'B1', 'B2', 'B3T'}:
        raise ValueError('Wait for all original reference outcomes')
    lifecycle = admission.read(oldmeta / f'workers/{args.design}/references.lifecycle.json')
    if lifecycle['state'] not in ('FAILED', 'COMPLETED'):
        raise ValueError('Original reference worker is still active')
    path_probe = reference.BASE_META / 'dependency_probes/runtime_import.json'
    probe = admission.read(path_probe)
    if probe['status'] != 'QUALIFIED_GENERIC_RUNTIME_MODULE_PATH_REPAIR':
        raise ValueError('Independent runtime-path qualification required')
    os.environ['PYTHONPATH'] = str(ROOT / 'src') + ':' + str(ROOT / 'scripts')
    design, source, protocol, infrastructure, physical, certificate = reference.configure(
        args.source_admission, args.attempt, args.dependency_repair)
    if design != args.design:
        raise ValueError('Admitted design identity changed')
    meta, raw = reference.META, reference.RAW
    result_path = meta / f'workers/{design}/retained_reference_qualification.json'
    state_path = result_path.with_name('retained_reference_qualification.lifecycle.json')
    if result_path.exists() or state_path.exists():
        raise ValueError('Preserve started/completed recovery')
    record = dict(schema='pact_gate09_retained_reference_worker_v1', design=design,
        created_utc=datetime.now(timezone.utc).isoformat(), PID=os.getpid(),
        Linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        prior_attempt=args.prior_attempt, attempt=args.attempt,
        source_admission=admission.binding(args.source_admission),
        dependency_repair=admission.binding(args.dependency_repair), runtime_path_probe=admission.binding(path_probe),
        original_reference_outcomes=admission.binding(oldmeta / f'baselines/{design}_references.json'),
        harness=admission.binding(Path(__file__)), PYTHONPATH=os.environ['PYTHONPATH'],
        additional_synthesis_executions=0, additional_placement_executions=0,
        additional_ATPG_generations=0, additional_architecture_generations=0,
        additional_route_executions=0, PACT_search_started=False, scientific_method_changes=0)
    atomic_write(state_path, dict(record, state='REGISTERED'), immutable=True)
    atomic_write(result_path.with_name('retained_reference_qualification.registered.json'), dict(record, state='REGISTERED'), immutable=True)
    results = []
    try:
        preparation = retain_preparation(oldmeta / f'physical/{design}/preparation.json', source, certificate,
                                        oldmeta / f'workers/{design}/prepare.json')
        reference.register_source(design, source, protocol, args.dependency_repair)
        atomic_write(meta / f'physical/{design}/preparation.json', preparation, immutable=True)
        atomic_write(state_path, dict(record, state='STARTED'))
        atomic_write(result_path.with_name('retained_reference_qualification.started.json'), dict(record, state='STARTED'), immutable=True)
        folder = physical.baseline_folder(design)
        folder.mkdir(parents=True, exist_ok=True)
        identity_path = oldraw / f'baselines/{design}/ff_identity_map.json'
        identity = admission.read(identity_path)['records']
        shutil.copyfile(identity_path, folder / 'ff_identity_map.json')
        original_path = oldraw / f'baselines/{design}/original_workload/export.json'
        original = admission.read(original_path)
        record['retained_original_fault_export'] = admission.binding(original_path)
        for item in old_records['records']:
            method = item['method']
            row = dict(design=design, method=method, status='FAILED', source_revision=item['source_revision'],
                generator_status=item['generator_status'], prior_outcome=item,
                classification='RETAINED_ROUTE_INFRASTRUCTURE_QUALIFICATION',
                additional_route_executions=0, additional_architecture_generations=0)
            try:
                if item['generator_status'] != 'PASS':
                    raise ValueError('Original native generator failed; recovery cannot replace its outcome')
                archpath = oldraw / f'baselines/{design}/{method}' / (
                    'architecture.json' if method == 'B0' else
                    'generator/' + ('architecture.json' if method == 'B1' else 'canonical.json'))
                from pact.scan.model import ScanArchitecture
                arch = ScanArchitecture.from_json(archpath)
                variant = 'generalization_' + method
                reuse = dict(variant=str(oldraw / f'orfs/results/nangate45/{design}/{variant}'),
                    logs=str(oldraw / f'orfs/logs/nangate45/{design}/{variant}'),
                    route_execution=str(oldraw / f'baselines/{design}/{method}/physical/route/execution.json'))
                report = physical.route(design, method, archpath, preparation, reuse=reuse)
                correctness = physical.serial_correctness(design, arch, identity,
                    Path(preparation['patterns']['path']), original, folder / method / 'correctness',
                    Path(preparation['source']['path']))
                row.update(status='QUALIFIED', architecture=admission.binding(archpath),
                    architecture_hash=arch.sha256(), exact_scan_order=[list(c.cells) for c in arch.chains],
                    chain_count=len(arch.chains), routed_scan_wirelength_um=report['routed_scan_wirelength_um'],
                    timing=report['structured_metrics'], DRC=report['DRC_errors'], correctness=correctness,
                    provenance=admission.binding(folder / method / 'physical/route_result.json'))
            except Exception as error:
                row.update(failure_class='RETAINED_REFERENCE_QUALIFICATION_FAIL', error=str(error),
                           traceback=traceback.format_exc())
                atomic_write(meta / f'failures/{design}_{method}_retained_reference.json', row, immutable=True)
            results.append(row)
            atomic_write(meta / f'baselines/{design}_references.json', dict(design=design, records=results))
            print('RETAINED_REFERENCE', design, method, row['status'], row.get('error', ''), flush=True)
        selected = physical.select_reference(results)
        atomic_write(meta / f'baselines/{design}_selected.json', dict(selected,
            frozen_utc=datetime.now(timezone.utc).isoformat(),
            selection_rule=protocol['fixed_method']['reference_rule']), immutable=True)
        gate = dict(design=design, status='INFRASTRUCTURE_QUALIFIED', selected_reference=selected['method'],
            gates={key: 'PASS' for key in ('synthesis', 'scan', 'ATPG', 'topology', 'placement',
                'reference_method', 'routing', 'extraction', 'timing', 'DRC')},
            exact_activity='PENDING; PACT remains blocked', additional_route_executions=0)
        atomic_write(meta / f'physical/{design}/presearch_qualification.json', gate, immutable=True)
        record.update(status='INFRASTRUCTURE_QUALIFIED', selected_reference=selected['method'])
    except Exception as error:
        record.update(status='PACT_GATE09_REFERENCE_ADMISSION_BLOCKED', error=str(error), traceback=traceback.format_exc())
    usage, children = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    record.update(completed_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.perf_counter()-started,
        CPU_seconds=usage.ru_utime+usage.ru_stime, children_CPU_seconds=children.ru_utime+children.ru_stime,
        peak_RSS_KiB=usage.ru_maxrss, child_peak_RSS_KiB=children.ru_maxrss)
    atomic_write(result_path, record, immutable=True)
    atomic_write(state_path, dict(record, state='COMPLETED' if record['status'] == 'INFRASTRUCTURE_QUALIFIED' else 'FAILED'))
    print('GATE09_RETAINED_REFERENCE_WORKER', record['status'], flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True)
    parser.add_argument('--prior-attempt', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--source-admission', type=Path, required=True)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    raise SystemExit(0 if result['status'] == 'INFRASTRUCTURE_QUALIFIED' else 2)
