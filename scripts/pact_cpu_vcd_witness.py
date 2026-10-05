#!/usr/bin/env python3
"""Fresh full-VCD control for compact-backend validation, in a new namespace."""
import argparse
import hashlib
import os
from pathlib import Path
import resource
import shutil
import sys
import time
import traceback
import numpy as np
from pact_cold_start_measure import execute_stage, validate_row, CELLS
from pact_generalization import ROOT, read, sha, write, now
from pact_generalization_infrastructure import external_binding
from pact.physical_effect import vcd_transitions
from pact.activity.compact import read_counts

RUN = Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cpu_scalability_20261005')
OUT = ROOT/'results/pact_cpu_scalability_20261005'


def waveform_hash(path):
    """Bind declarations and every emitted event; ignore only header date."""
    header, body = hashlib.sha256(), hashlib.sha256()
    with Path(path).open('rb') as stream:
        for line in stream:
            if line.startswith((b'$scope', b'$upscope', b'$var', b'$enddefinitions')):
                header.update(line)
            if line.startswith(b'$enddefinitions'):
                break
        else:
            raise ValueError('Incomplete VCD declarations')
        for block in iter(lambda: stream.read(1024*1024), b''):
            body.update(block)
    return header.hexdigest(), body.hexdigest()


def verify(source, folder, compact):
    identical = waveform_hash(source/'activity.vcd') == waveform_hash(folder/'activity.vcd')
    if not identical:
        names = sorted(read(source/'net_mapping.json')['nets'])
        cycles = len(read(source/'cycles.json'))
        expected,_ = vcd_transitions(folder/'activity.vcd',names,cycles)
        actual,_ = read_counts(compact/'activity.counts.gz',names,cycles)
        np.testing.assert_array_equal(expected,actual)
    write(folder/'verification.json',dict(status='PASS',full_waveform_declarations_and_event_body_identical=identical),immutable=True)


def run(source):
    began = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    source = Path(source).resolve()
    original = read(source.parents[1]/'manifest.json')
    row = next(r for r in original['rows'] if r['design'] == source.parent.name and r['role'] == source.name)
    validate_row(row)
    if read(source/'result.json')['status'] != 'QUALIFIED':
        raise ValueError('Fresh control requires qualified oracle source')
    compact = RUN/'equivalence'/row['design']/row['role']/'normal'/row['design']/row['role']
    if read(compact/'result.json')['status'] != 'QUALIFIED':
        raise ValueError('Compact equivalence must pass before this control')
    root = RUN/'fresh_vcd'/row['design']/row['role']
    folder = root/row['design']/row['role']
    if root.exists(): raise ValueError('Preserve previous full-VCD control')
    folder.mkdir(parents=True)
    if shutil.disk_usage(root).free < 20*1024**3: raise RuntimeError('20 GiB scratch reserve unavailable')
    simulation = read(source/'simulation_manifest.json')
    for item in [*simulation['inputs'].values(),simulation['cells']]:
        if sha(item['path']) != item['sha256']: raise ValueError('Frozen input changed')
    shutil.copy2(source/'routed.v',folder/'routed.v')
    stimulus = (source/'stimulus.v').read_text()
    old_trace = str(source/'activity.vcd')
    if stimulus.count(old_trace) != 1: raise ValueError('VCD output-path anchor differs')
    (folder/'stimulus.v').write_text(stimulus.replace(old_trace,str(folder/'activity.vcd')))
    write(root/'manifest.json',dict(schema='pact_cpu_fresh_vcd_control_v1',created_utc=now(),rows=[row],
        source_simulation=external_binding(source/'simulation_manifest.json'),
        source_result=external_binding(source/'result.json'),compact_equivalence=external_binding(compact/'equivalence.json'),
        stimulus=external_binding(folder/'stimulus.v'),routed=external_binding(folder/'routed.v'),
        stimulus_change='Only VCD output pathname changed; same complete stimulus and circuit',
        configured_timeout_seconds=7200,timeout_regime='normal',workers=1),immutable=True)
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1')
    deadline = began+7200
    outcome = dict(status='PENDING')
    try:
        execute_stage(['/usr/bin/iverilog','-g2012','-DTETRAMAX','-s','tb','-o',folder/'simulation.vvp',
            folder/'stimulus.v',folder/'routed.v',CELLS],folder,'compile',deadline)
        execute_stage(['/usr/bin/vvp',folder/'simulation.vvp'],folder,'simulate',deadline)
        if 'PASS patterns=' not in (folder/'simulate.log').read_text(): raise ValueError('Functional replay incomplete')
        execute_stage([sys.executable,ROOT/'scripts/pact_cpu_vcd_witness.py','--source',source,'--verify-folder',folder],folder,'verify',deadline)
        outcome.update(read(folder/'verification.json'))
        outcome.update(status='QUALIFIED',completion_status='COMPLETE',termination_reason='complete')
    except Exception as error:
        outcome.update(status='FAILED',completion_status='INCOMPLETE_OR_UNQUALIFIED',termination_reason='stage_failure',
            error=str(error),traceback=traceback.format_exc(),partial_activity_used=False)
    stages = {p.name.removesuffix('.execution.json'): read(p) for p in folder.glob('*.execution.json')}
    after = resource.getrusage(resource.RUSAGE_SELF)
    record = dict(outcome,design=row['design'],role=row['role'],created_utc=now(),
        configured_timeout_seconds=7200,timeout_regime='normal',
        transition_equivalence='EXACT (identical full emitted waveform or complete per-cycle parser comparison)',
        stages=stages,wall_seconds=time.perf_counter()-began,
        CPU_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime+sum(r['CPU_seconds'] for r in stages.values()),
        peak_RSS_KiB=max([after.ru_maxrss]+[r['peak_RSS_KiB'] for r in stages.values()]),
        simulator_seconds=stages.get('simulate',{}).get('wall_seconds'),
        trace=external_binding(folder/'activity.vcd') if (folder/'activity.vcd').exists() else None,
        trace_bytes=(folder/'activity.vcd').stat().st_size if (folder/'activity.vcd').exists() else 0,
        metrics='Identical complete counts imply the already-checked E/H4/H8 and per-source metrics' if outcome['status']=='QUALIFIED' else None)
    if any(r['timed_out'] for r in stages.values()): record['termination_reason'] = 'configured_timeout'
    write(folder/'result.json',record,immutable=True)
    write(OUT/'activity/fresh_vcd'/row['design']/row['role']/'result.json',record,immutable=True)
    print('FRESH_VCD_CONTROL_COMPLETE',row['design'],record['status'],record['simulator_seconds'],flush=True)
    if record['status'] != 'QUALIFIED': raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--verify-folder',type=Path)
    args = parser.parse_args()
    if args.verify_folder:
        row = read(args.source.parents[1]/'manifest.json')['rows'][0]
        compact = RUN/'equivalence'/row['design']/row['role']/'normal'/row['design']/row['role']
        verify(args.source,args.verify_folder,compact)
    else:
        run(args.source)
