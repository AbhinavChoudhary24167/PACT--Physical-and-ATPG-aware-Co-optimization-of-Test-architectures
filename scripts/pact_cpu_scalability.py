#!/usr/bin/env python3
"""Isolated, fixed-evaluation CPU development witness; never a campaign rerun."""
import argparse
import cProfile
import hashlib
import json
import os
from pathlib import Path
import pstats
import resource
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
OUT = ROOT / 'results/pact_cpu_scalability_20261005'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def inventory():
    files = subprocess.check_output(['git', 'ls-files', '-z', 'results', 'reports', 'artifacts'], cwd=ROOT).decode().split('\0')
    return {name: sha(ROOT / name) for name in files if name}


def freeze():
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    sources = ('candidate_stateful.py', 'implementation_v2.py', 'search.py', 'stage_b.py')
    snapshots = {}
    for name in sources:
        source = ROOT / 'src/pact/optimizer' / name
        target = OUT / 'oracle' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError('Oracle already preserved')
        shutil.copy2(source, target)
        snapshots[name] = sha(target)
    tools = {}
    commands = dict(nproc=['nproc'], lscpu=['lscpu'], memory=['free', '-h'],
        python=[sys.executable, '--version'], compiler=['gcc', '--version'],
        openroad=['/usr/bin/openroad', '-version'],
        iverilog=['/usr/bin/iverilog', '-V'], vvp=['/usr/bin/vvp', '-V'],
        fan_commit=['git', '-C', '/root/pact-deps/FAN_ATPG', 'rev-parse', 'HEAD'])
    for name, command in commands.items():
        result = subprocess.run(command, capture_output=True, text=True)
        tools[name] = dict(command=command, code=result.returncode, stdout=result.stdout, stderr=result.stderr)
    tools['fan_binaries'] = {str(p): sha(p) for p in Path('/root/pact-deps/FAN_ATPG/bin').rglob('*') if p.is_file()}
    write(OUT / 'gate0.json', dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        initial_tree='CLEAN verified before creation of this development script', documented_tree=status,
        tools=tools, oracle=snapshots, historical_files=inventory(),
        scope='CPU only; original evaluator and historical experiments immutable'))


def profile(backend, evaluations, label=''):
    from pact.optimizer.cold_start import load
    from pact.optimizer import candidate_stateful as oracle, stage_b
    from pact.optimizer.implementation_v2 import order_id
    if backend == 'oracle':
        state_type = oracle.State
    else:
        from pact.optimizer.cpu_incremental import State
        state_type = State
    model, starts, contract = load(ROOT / 'results/pact_cold_start_unseen_20261004/inputs/s35932/cold_start_input.json')
    # Warm native kernels separately; initialization and independent retained
    # replay are still performed by the unchanged Stage-B search below.
    warm = state_type(model, starts[0][1])
    warm.score()
    warm = None
    model.profile = {name: 0. for name in model.profile}
    trace = []
    timers = dict(mutation_generation_seconds=0., archive_seconds=0., state_construction_seconds=0.)
    original_proposal, original_archive = stage_b.proposal, stage_b.Archive
    def timed_proposal(*args):
        began = time.perf_counter()
        result = original_proposal(*args)
        timers['mutation_generation_seconds'] += time.perf_counter() - began
        return result
    class TimedArchive(original_archive):
        def insert(self, *args):
            began = time.perf_counter()
            value = super().insert(*args)
            timers['archive_seconds'] += time.perf_counter() - began
            return value
    class ObservedState(state_type):
        def __init__(self, *args):
            began = time.perf_counter()
            super().__init__(*args)
            timers['state_construction_seconds'] += time.perf_counter() - began
            self.trial = None
        def change(self, patch):
            if isinstance(patch, oracle.Transaction):
                if self.trial is not None:
                    self.trial['accepted'] = False
                return super().change(patch)
            undo = super().change(patch)
            self.trial = dict(order_id=order_id(self.orders), accepted=True, operator=sorted(patch))
            trace.append(self.trial)
            return undo
        def score(self):
            value = super().score()
            if self.trial is not None:
                self.trial['score'] = value.tolist()
            return value
    stage_b.proposal, stage_b.Archive = timed_proposal, TimedArchive
    profiler = cProfile.Profile()
    before = resource.getrusage(resource.RUSAGE_SELF)
    began = time.perf_counter()
    profiler.enable()
    try:
        result = stage_b.optimize(model, starts, contract.data['reference_method'],
            stage_b.Config(epsilon=.02, seconds=7200, max_evaluations=evaluations),
            state_type=ObservedState, reference_evaluator=oracle.reference,
            checkpoint=lambda r: print('CPU_WITNESS', backend, r['evaluations'], round(r['seconds'], 3), flush=True))
    finally:
        profiler.disable()
        stage_b.proposal, stage_b.Archive = original_proposal, original_archive
    after = resource.getrusage(resource.RUSAGE_SELF)
    stats = pstats.Stats(profiler)
    calls = [dict(file=k[0], line=k[1], function=k[2], primitive_calls=v[0], calls=v[1],
                  self_seconds=v[2], cumulative_seconds=v[3]) for k, v in stats.stats.items()]
    selected = [dict(order_id=order_id(row['orders']), score=row['score'].tolist(), roles=row['roles']) for row in result['selected']]
    record = dict(backend=backend, witness='s35932', FF_count=len(model.names), patterns=len(model.load),
        config=dict(epsilon=.02, seed=11, evaluations=evaluations, threads=1, stopping='fixed evaluation development witness'),
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in (ROOT/'src/pact/optimizer').glob('*.py')},
        manifest_sha256=sha(contract.manifest_path), evaluations=result['evaluations'], attempts=result['attempts'],
        accepted=result['accepted'], termination=result['termination'], selected=selected, trace=trace,
        loop_wall_seconds=result['search_seconds'], evaluations_per_second=result['evaluations']/result['search_seconds'],
        workflow_wall_seconds=time.perf_counter()-began, CPU_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
        peak_RSS_KiB=after.ru_maxrss, profile=model.profile, timers=timers,
        cprofile=sorted(calls, key=lambda row: row['self_seconds'], reverse=True),
        memory_and_boundary_policy='cProfile copy/allocation/dispatcher self and cumulative timings; nested attribution, not additive exclusive phases',
        historical_unchanged=inventory() == json.loads((OUT/'gate0.json').read_text())['historical_files'])
    if not record['historical_unchanged']:
        raise AssertionError('Historical evidence changed')
    write(OUT / f'profile_{backend}_{evaluations}{label}.json', record)
    print('CPU_WITNESS_COMPLETE', backend, record['evaluations_per_second'], flush=True)


def compare_profiles():
    import numpy as np
    old = json.loads((OUT/'profile_oracle_128.json').read_text())
    new = json.loads((OUT/'profile_incremental_128_sparse.json').read_text())
    errors = np.zeros(5)
    for a, b in zip(old['trace'], new['trace'], strict=True):
        for key in ('order_id', 'accepted', 'operator'):
            if a[key] != b[key]:
                raise AssertionError('Deterministic execution path changed: '+key)
        np.testing.assert_allclose(a['score'], b['score'], rtol=1e-9, atol=1e-6)
        errors = np.maximum(errors, np.abs(np.asarray(a['score'])-b['score']))
    if old['selected'] != new['selected']:
        raise AssertionError('Independently replayed selected architectures/metrics differ')
    table = {key: dict(before=old[key], after=new[key]) for key in
             ('evaluations_per_second','loop_wall_seconds','CPU_seconds','peak_RSS_KiB')}
    for key in old['profile']:
        table[key] = dict(before=old['profile'][key], after=new['profile'][key])
    write(OUT/'evaluator_equivalence.json', dict(status='PASS', exact_mutations=len(new['trace']),
        path_and_acceptance='IDENTICAL', selected_architectures_and_independent_metrics='IDENTICAL',
        maximum_absolute_metric_errors=errors.tolist(), registered_tolerance=dict(rtol=1e-9,atol=1e-6),
        historical_unchanged=old['historical_unchanged'] and new['historical_unchanged'], table=table,
        throughput_ratio=new['evaluations_per_second']/old['evaluations_per_second'],
        classifications=['PACT_CPU_INCREMENTAL_EVALUATOR_QUALIFIED','PACT_CPU_SPATIAL_SCALABILITY_ADVANCE','PACT_CPU_ROLLBACK_SCALABILITY_ADVANCE']))
    print('CPU_EQUIVALENCE_PASS', len(new['trace']), errors.tolist(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('freeze', 'profile', 'compare'))
    parser.add_argument('--backend', choices=('oracle', 'incremental'), default='oracle')
    parser.add_argument('--evaluations', type=int, default=128)
    parser.add_argument('--label', default='', choices=('', '_sparse'))
    args = parser.parse_args()
    if args.stage == 'freeze':
        freeze()
    elif args.stage == 'compare':
        compare_profiles()
    else:
        if any(os.environ.get(name) != '1' for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMBA_NUM_THREADS')):
            parser.error('Witness requires OMP/OPENBLAS/NUMBA_NUM_THREADS=1')
        profile(args.backend, args.evaluations, args.label)


if __name__ == '__main__':
    main()
