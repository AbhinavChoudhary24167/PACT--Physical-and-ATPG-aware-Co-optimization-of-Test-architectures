#!/usr/bin/env python3
"""Isolated exact activity equivalence and new large-reference continuations."""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time
import traceback
import numpy as np

from pact_cold_start_measure import execute_stage, validate_row, CELLS
from pact_generalization import ROOT, sha, read, write, now
from pact_generalization_infrastructure import external_binding
from pact.activity.compact import analyze, read_counts
from pact.physical_effect import vcd_transitions

OUT = ROOT/'results/pact_cpu_scalability_20261005'
RUN = Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cpu_scalability_20261005')
CEILINGS = dict(normal=7200, diagnostic=14400)


def prepare(source, purpose, regime, timeout):
    source = Path(source).resolve()
    original = read(source.parents[1]/'manifest.json')
    row = next(r for r in original['rows'] if r['design'] == source.parent.name and r['role'] == source.name)
    validate_row(row)
    simulation = read(source/'simulation_manifest.json')
    for item in [*simulation['inputs'].values(), simulation['cells']]:
        if sha(item['path']) != item['sha256']:
            raise ValueError('Frozen simulation input changed: '+item['path'])
    if purpose == 'equivalence' and read(source/'result.json')['status'] != 'QUALIFIED':
        raise ValueError('Equivalence requires already-qualified oracle activity')
    if purpose == 'continuation' and row['design'] not in ('s38417', 's38584'):
        raise ValueError('Continuation gate currently permits the two blocked large designs only')
    root = RUN/purpose/row['design']/row['role']/regime
    folder = root/row['design']/row['role']
    if root.exists():
        raise ValueError('Preserve existing CPU activity run: '+str(root))
    root.mkdir(parents=True)
    if shutil.disk_usage(root).free < 20*1024**3:
        raise RuntimeError('Registered 20 GiB free scratch reserve unavailable')
    folder.mkdir(parents=True)
    for name in ('routed.v', 'net_mapping.json', 'workload.json', 'cycles.json', 'extracted.spef'):
        shutil.copy2(source/name, folder/name)
    stimulus = (source/'stimulus.v').read_text()
    lines = stimulus.splitlines(keepends=True)
    dump = [line for line in lines if '$dumpfile(' in line or '$dumpvars(' in line]
    if len(dump) != 2 or not any('$dumpvars(1,dut); $dumpvars(0,cycle_id);' in line for line in dump):
        raise ValueError('Unsupported frozen VCD emission contract')
    compact_stimulus = ''.join(line for line in lines if line not in dump)
    (folder/'stimulus.v').write_text(compact_stimulus)
    names = sorted(read(folder/'net_mapping.json')['nets'])
    cycles = len(read(folder/'cycles.json'))
    (folder/'counts.cfg').write_text(str(cycles)+'\n'+'\n'.join(names)+'\n')
    row = dict(row, workload=external_binding(folder/'workload.json'))
    record = dict(schema='pact_cpu_exact_activity_v1', created_utc=now(), rows=[row],
        purpose=purpose, timeout_regime=regime, configured_timeout_seconds=timeout,
        regime_ceiling_seconds=CEILINGS[regime], ceilings=CEILINGS,
        source_manifest=external_binding(source.parents[1]/'manifest.json'),
        frozen_simulation_manifest=external_binding(source/'simulation_manifest.json'),
        source_result=external_binding(source/'result.json'),
        inputs={name: external_binding(folder/name) for name in ('routed.v','net_mapping.json','workload.json','cycles.json','extracted.spef','stimulus.v','counts.cfg')},
        sources={name: external_binding(ROOT/name) for name in ('src/pact/activity/counts_vpi.cpp','src/pact/activity/compact.py','src/pact/physical_effect.py','scripts/pact_cpu_activity.py')},
        simulation_cells=external_binding(CELLS), tools={name: external_binding('/usr/bin/'+name) for name in ('iverilog','vvp','iverilog-vpi')},
        stimulus_change='Only the two VCD emission lines removed; every functional statement retained byte-for-byte',
        scientific_policy='Unchanged frozen circuit, workload, C*N and H4/H8; full cycle counts plus successful functional simulator exit required; partial output excluded',
        resource_policy=dict(workers=1, simulator_jobs=1, physical_jobs=0, OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, NUMBA_NUM_THREADS=1))
    write(root/'manifest.json', record, immutable=True)
    return source, root, folder, record


def compare(source, folder):
    names = sorted(read(folder/'net_mapping.json')['nets'])
    cycles = len(read(folder/'cycles.json'))
    counts, _ = read_counts(folder/'activity.counts.gz', names, cycles)
    # Parse the complete full VCD again in this development comparison; do not
    # substitute old aggregates or optimizer estimates for the oracle.
    expected, _ = vcd_transitions(source/'activity.vcd', names, cycles)
    np.testing.assert_array_equal(counts, expected)
    np.testing.assert_array_equal(counts.sum(axis=0), expected.sum(axis=0))
    def numeric(left, right):
        if isinstance(left, dict):
            if left.keys() != right.keys(): raise AssertionError('Activity summary structure changed')
            for key in left: numeric(left[key], right[key])
        elif isinstance(left, (int,float)):
            np.testing.assert_allclose(left, right, rtol=1e-10, atol=1e-10)
        elif left != right:
            raise AssertionError('Activity summary metadata changed')
    numeric(read(folder/'activity_summary.json')['scopes'], read(source/'activity_summary.json')['scopes'])
    numeric(read(folder/'spatial_bins.json'), read(source/'spatial_bins.json'))
    return dict(status='PASS', complete_transition_values=counts.size, per_source_counts='EXACT',
        E_H4_H8='MATCH', all_scope_statistics_and_spatial_maps='MATCH',
        policy=dict(rtol=1e-10, atol=1e-10), full_VCD=external_binding(source/'activity.vcd'))


def run(source, purpose, regime, timeout):
    if not 0 < timeout <= CEILINGS[regime]:
        raise ValueError('Configured timeout exceeds the named regime ceiling')
    began = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    source, root, folder, manifest = prepare(source, purpose, regime, timeout)
    row = manifest['rows'][0]
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='1',
        PACT_ACTIVITY_CONFIG=str(folder/'counts.cfg'), PACT_ACTIVITY_OUTPUT=str(folder/'activity.counts.gz'))
    deadline = began+timeout
    result = dict(design=row['design'], role=row['role'], status='PENDING', purpose=purpose,
        created_utc=now(), configured_timeout_seconds=timeout, timeout_regime=regime,
        manifest=external_binding(root/'manifest.json'), architecture_sha256=row['architecture_sha256'])
    try:
        # Build in this isolated folder. No binary or object is written beside
        # the source, into the simulator installation, or into old experiments.
        command = ['/usr/bin/g++','-O2','-std=c++11','-shared','-fPIC','-I/usr/include/iverilog',
            ROOT/'src/pact/activity/counts_vpi.cpp','-o',folder/'counts.vpi','-lz']
        execute_stage(command, folder, 'build_collector', deadline)
        execute_stage(['/usr/bin/iverilog','-g2012','-DTETRAMAX','-s','tb','-o',folder/'simulation.vvp',
            folder/'stimulus.v',folder/'routed.v',CELLS], folder, 'compile', deadline)
        execute_stage(['/usr/bin/vvp','-M',folder,'-m','counts',folder/'simulation.vvp'], folder, 'simulate', deadline)
        log = (folder/'simulate.log').read_text()
        if 'PACT_COUNTS_COMPLETE' not in log or 'PASS patterns=' not in log or 'PACT_COUNTS_ERROR' in log:
            raise ValueError('Simulator did not complete both counts and functional checks')
        execute_stage([sys.executable,ROOT/'scripts/pact_cpu_activity.py','--analyze-folder',folder], folder, 'analyze', deadline)
        summary = read(folder/'activity_summary.json')
        if read(folder/'FF_transition_crosscheck.json')['status'] != 'PASS':
            raise ValueError('FF transition cross-check failed')
        if purpose == 'equivalence':
            execute_stage([sys.executable,ROOT/'scripts/pact_cpu_activity.py','--compare-folder',folder,'--source',source], folder, 'equivalence', deadline)
            result['equivalence'] = read(folder/'equivalence.json')
        data = summary['scopes']['all_data']
        result.update(status='QUALIFIED', E=data['cap_weighted_ff_transitions']['total'],
            H4=data['grids']['4']['cap_peak_per_cycle']['maximum'], H8=data['grids']['8']['cap_peak_per_cycle']['maximum'],
            complete=True, termination_reason='complete_functional_replay_and_exact_count_analysis')
    except Exception as error:
        result.update(status='FAILED', complete=False, error=str(error), traceback=traceback.format_exc(),
            termination_reason='stage_failure_or_incomplete_activity', partial_activity_used=False)
    stages = {p.name.removesuffix('.execution.json'): read(p) for p in folder.glob('*.execution.json')}
    if any(r['timed_out'] for r in stages.values()): result['termination_reason'] = 'configured_timeout'
    after = resource.getrusage(resource.RUSAGE_SELF)
    result.update(completed_utc=now(), stages=stages, wall_seconds=time.perf_counter()-began,
        CPU_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime+sum(r['CPU_seconds'] for r in stages.values()),
        peak_RSS_KiB=max([after.ru_maxrss]+[r['peak_RSS_KiB'] for r in stages.values()]),
        simulator_seconds=stages.get('simulate',{}).get('wall_seconds'),
        trace_bytes=(folder/'activity.counts.gz').stat().st_size if (folder/'activity.counts.gz').exists() else 0,
        output_folder=str(folder), resource_scope='Sequential child CPU sum plus launcher; maximum process RSS, not simultaneous sum')
    write(folder/'result.json', result, immutable=True)
    receipt = OUT/'activity'/purpose/row['design']/row['role']/regime
    receipt.mkdir(parents=True, exist_ok=False)
    for name in ('result.json','activity_summary.json','FF_transition_crosscheck.json','equivalence.json'):
        if (folder/name).exists(): shutil.copy2(folder/name, receipt/name)
    shutil.copy2(root/'manifest.json', receipt/'manifest.json')
    print('CPU_ACTIVITY_COMPLETE', row['design'], row['role'], result['status'], result['wall_seconds'], result['trace_bytes'], flush=True)
    if result['status'] != 'QUALIFIED': raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--purpose', choices=('equivalence','continuation'), default='equivalence')
    parser.add_argument('--regime', choices=tuple(CEILINGS), default='normal')
    parser.add_argument('--timeout', type=float)
    parser.add_argument('--analyze-folder', type=Path)
    parser.add_argument('--compare-folder', type=Path)
    args = parser.parse_args()
    if args.analyze_folder: analyze(args.analyze_folder)
    elif args.compare_folder: write(args.compare_folder/'equivalence.json', compare(args.source,args.compare_folder), immutable=True)
    elif args.source: run(args.source,args.purpose,args.regime,CEILINGS[args.regime] if args.timeout is None else args.timeout)
    else: parser.error('--source or --analyze-folder required')


if __name__ == '__main__': main()
