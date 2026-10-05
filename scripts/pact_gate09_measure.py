#!/usr/bin/env python3
"""Artifact-driven Gate-09 exact CPU reference measurement.

Reuses the qualified frozen exporter, stimulus, compact collector and analysis.
Only campaign lookup paths and the historical-only preparation guard differ.
"""
import argparse
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_reference as references
from pact_experiment_receipts import atomic_write


def capacity(protocol, dimensions=None, retained_bytes=0):
    policy = dict(protocol['resource_policy'])
    if dimensions:
        cells = dimensions['nets'] * dimensions['cycles']
        # Complete traces for B0-B5 plus at most three PACT candidates and
        # one complete uncompressed analysis cache; gzip cannot exceed this
        # bound materially, and a 512 MiB package allowance covers metadata.
        projected = retained_bytes + 10 * cells + 512 * 1024**2
        policy['D_minimum_floor_bytes'] = max(policy['D_minimum_floor_bytes'],
            policy['D_existing_scratch_requirement_bytes'] + max(5 * 1024**3, projected))
    observed = {drive: dict(zip(('total', 'used', 'free'), shutil.disk_usage('/mnt/' + drive.lower())))
                for drive in ('C', 'D')}
    result = admission.capacity(policy, observed)
    result['per_design_margin'] = dict(dimensions=dimensions, retained_bytes=retained_bytes,
        projected_remaining_bytes=projected if dimensions else None,
        rule='20 GiB + max(5 GiB, retained packages + nine projected complete traces + one complete count cache +512 MiB)',
        fixed_floor_retained=True)
    if result['status'] != 'PASS':
        raise RuntimeError('PACT_GATE09_BLOCKED_CAPACITY: ' + json.dumps(result))
    return result


def reference_row(meta, raw, design, method):
    preparation = admission.read(meta / f'physical/{design}/preparation.json')
    qualification = admission.read(meta / f'physical/{design}/presearch_qualification.json')
    if qualification['status'] != 'INFRASTRUCTURE_QUALIFIED':
        raise ValueError('Physical reference admission must complete first')
    record = next(row for row in admission.read(meta / f'baselines/{design}_references.json')['records']
                  if row['method'] == method)
    if record['status'] != 'QUALIFIED':
        raise ValueError('Only qualified routes can be measured')
    route = admission.read(record['provenance']['path'])
    row = dict(design=design, role=method, architecture=record['architecture'],
        architecture_sha256=record['architecture_hash'], routed_archive=route['archive'],
        source_placed_database=preparation['source_placed_database'],
        source_netlist=admission.binding(Path(preparation['patterns']['path']).parent / 'compatible.v'),
        SDC=preparation['SDC'], qualification=record['provenance'],
        prior_integration=record['correctness']['faults'],
        inputs=dict(patterns=preparation['patterns'], placement=preparation['placed_def'],
                    identity_map=admission.binding(raw / f'baselines/{design}/ff_identity_map.json')))
    return row, route


def prepare(design, method, source, protocol, meta, raw):
    from pact_cold_start_measure import prepare_row, execute_stage, validate_row, CELLS, LIB
    row, route = reference_row(meta, raw, design, method)
    validate_row(row)
    gate = capacity(protocol)
    root = raw / f'measurement_preparation/{design}/{method}'
    if root.exists():
        raise ValueError('Preserve prior exact preparation: ' + str(root))
    root, folder = prepare_row(row, root)
    record = dict(schema='pact_gate09_exact_preparation_v1', design=design, method=method,
        created_utc=datetime.now(timezone.utc).isoformat(), status='PENDING', capacity=gate,
        source_admission=source, manifest=admission.binding(root / 'manifest.json'),
        harness=admission.binding(Path(__file__)), PACT_search_started=False,
        routing_executions=0, extraction_executions=0, ATPG_generations=0,
        scientific_method_changes=0)
    try:
        deadline = time.perf_counter() + 1800
        os.environ['PACT_PHYSICAL_EFFECT_OUT'] = str(root)
        with gzip.open(row['routed_archive']['path'], 'rb') as src, (folder / 'routed.odb').open('wb') as dst:
            shutil.copyfileobj(src, dst)
        execute_stage(['/usr/bin/openroad', '-python', '-no_init', '-exit',
            ROOT / 'scripts/pact_generalization_export.py', folder], folder, 'export', deadline)
        for name in ('topology_verification', 'functional_verification'):
            if admission.read(folder / (name + '.json'))['status'] != 'PASS':
                raise ValueError('Reference export gate failed: ' + name)
        if admission.verify(route['extraction'])['status'] != 'PASS':
            raise ValueError('Qualified common extraction changed')
        shutil.copyfile(route['extraction']['path'], folder / 'extracted.spef')
        tcl = folder / 'netlist.tcl'
        tcl.write_text(f'read_liberty {LIB}\nread_db {folder}/routed.odb\n'
                       f'write_verilog {folder}/routed_raw.v\nexit\n')
        execute_stage(['/usr/bin/openroad', '-no_init', '-exit', tcl], folder, 'netlist', deadline)
        import physical_effect as frozen
        frozen.OUT = root
        mapping = admission.read(folder / 'net_mapping.json')
        frozen.repair_input_aliases(folder, mapping)
        frozen.stimulus(admission.read(root / 'manifest.json')['rows'][0], folder, mapping)
        inputs = {name: admission.binding(folder / name) for name in (
            'routed.odb', 'routed.v', 'routed_raw.v', 'stimulus.v', 'net_mapping.json',
            'cycles.json', 'extracted.spef', 'workload.json')}
        dimensions = dict(nets=len(mapping['nets']), cycles=len(admission.read(folder / 'cycles.json')))
        retained = sum(value['bytes'] for value in inputs.values())
        measured_gate = capacity(protocol, dimensions, retained)
        atomic_write(folder / 'simulation_manifest.json', dict(inputs=inputs,
            cells=admission.binding(CELLS), architecture_sha256=row['architecture_sha256'],
            simulation='Frozen Icarus -g2012 -DTETRAMAX; specify disabled; zero delay; no SDF',
            reused_common_extraction=route['extraction']), immutable=True)
        record.update(status='REFERENCE_EXPORT_AND_STIMULUS_QUALIFIED_PENDING_CPU_EXACT',
            folder=str(folder), dimensions=dimensions, retained_bytes=retained,
            activity_capacity=measured_gate,
            functional_verification=admission.binding(folder / 'functional_verification.json'),
            topology_verification=admission.binding(folder / 'topology_verification.json'),
            simulation_manifest=admission.binding(folder / 'simulation_manifest.json'))
    except Exception as error:
        record.update(status='FAILED', error=str(error), traceback=traceback.format_exc())
    atomic_write(meta / f'measurements/{design}/{method}/preparation.json', record, immutable=True)
    print('GATE09_EXACT_PREPARATION', design, method, record['status'], flush=True)
    if record['status'] == 'FAILED':
        raise SystemExit(1)


def run(design, method, protocol, meta, raw):
    import pact_cpu_activity as cpu
    from pact_cold_start_measure import validate_row
    preparation_path = meta / f'measurements/{design}/{method}/preparation.json'
    prepared = admission.read(preparation_path)
    if prepared['status'] != 'REFERENCE_EXPORT_AND_STIMULUS_QUALIFIED_PENDING_CPU_EXACT':
        raise ValueError('Qualified reference stimulus/export preparation required')
    source = Path(prepared['folder'])
    original = admission.read(source.parents[1] / 'manifest.json')
    row = original['rows'][0]
    validate_row(row)
    for value in admission.read(source / 'simulation_manifest.json')['inputs'].values():
        if admission.verify(value)['status'] != 'PASS':
            raise ValueError('Frozen simulation input changed')
    root = raw / f'exact_activity/{design}/{method}'
    folder = root / design / method

    def prepare_cpu(source_argument, purpose, regime, timeout, spef_evidence=None):
        if source_argument != source or purpose != 'GATE09_PRIMARY' or regime != 'normal' or timeout != 7200:
            raise ValueError('Unregistered Gate-09 CPU exact configuration')
        gate = capacity(protocol, prepared['dimensions'], prepared['retained_bytes'])
        if root.exists():
            raise ValueError('Preserve prior exact measurement')
        folder.mkdir(parents=True)
        for name in ('routed.v', 'net_mapping.json', 'workload.json', 'cycles.json', 'extracted.spef'):
            shutil.copyfile(source / name, folder / name)
        lines = (source / 'stimulus.v').read_text().splitlines(keepends=True)
        dumps = [line for line in lines if '$dumpfile(' in line or '$dumpvars(' in line]
        if len(dumps) != 2 or not any('$dumpvars(1,dut); $dumpvars(0,cycle_id);' in line for line in dumps):
            raise ValueError('Unsupported frozen compact collector emission contract')
        (folder / 'stimulus.v').write_text(''.join(line for line in lines if line not in dumps))
        names = sorted(admission.read(folder / 'net_mapping.json')['nets'])
        cycles = len(admission.read(folder / 'cycles.json'))
        (folder / 'counts.cfg').write_text(str(cycles) + '\n' + '\n'.join(names) + '\n')
        manifest = dict(schema='pact_cpu_exact_activity_v1', rows=[dict(row, workload=admission.binding(folder / 'workload.json'))],
            created_utc=datetime.now(timezone.utc).isoformat(), purpose=purpose,
            timeout_regime=regime, configured_timeout_seconds=timeout, regime_ceiling_seconds=7200,
            ceilings=cpu.CEILINGS, source_manifest=admission.binding(source.parents[1] / 'manifest.json'),
            frozen_simulation_manifest=admission.binding(source / 'simulation_manifest.json'),
            Gate09_preparation=admission.binding(preparation_path), source_result=None,
            source_result_reason='Prospective unseen reference; no historical exact result reused',
            inputs={name: admission.binding(folder / name) for name in (
                'routed.v', 'net_mapping.json', 'workload.json', 'cycles.json', 'extracted.spef', 'stimulus.v', 'counts.cfg')},
            sources={name: admission.binding(ROOT / name) for name in (
                'src/pact/activity/counts_vpi.cpp', 'src/pact/activity/compact.py', 'src/pact/physical_effect.py',
                'scripts/pact_cpu_activity.py', 'scripts/pact_gate09_measure.py')},
            simulation_cells=admission.binding(cpu.CELLS),
            tools={name: admission.binding('/usr/bin/' + name) for name in ('iverilog', 'vvp', 'iverilog-vpi')},
            stimulus_change='Only the two VCD emission lines removed; all functional statements retained',
            scientific_policy='Qualified frozen C*N, H4/H8 and exact complete functional/FF replay',
            resource_policy=dict(workers=1, simulator_jobs=1, physical_jobs=0, OMP_NUM_THREADS=1,
                                 OPENBLAS_NUM_THREADS=1, NUMBA_NUM_THREADS=1), capacity=gate)
        atomic_write(root / 'manifest.json', manifest, immutable=True)
        return source, root, folder, manifest

    original_execute = cpu.execute_stage
    def guarded_execute(*args, **kwargs):
        capacity(protocol, prepared['dimensions'], prepared['retained_bytes'])
        return original_execute(*args, **kwargs)
    cpu.prepare, cpu.execute_stage = prepare_cpu, guarded_execute
    cpu.OUT, cpu.RUN = meta, raw
    cpu.run(source, 'GATE09_PRIMARY', 'normal', 7200)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--method', choices=('B0', 'B1', 'B2', 'B3T'), required=True)
    parser.add_argument('--source-admission', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    args = parser.parse_args()
    design, source, protocol, _, _, _ = references.configure(args.source_admission, args.attempt, args.dependency_repair)
    if args.action == 'prepare':
        prepare(design, args.method, source, protocol, references.META, references.RAW)
    else:
        run(design, args.method, protocol, references.META, references.RAW)
