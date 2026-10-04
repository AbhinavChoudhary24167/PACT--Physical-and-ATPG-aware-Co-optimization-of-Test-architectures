#!/usr/bin/env python3
"""Measure artifact-driven loader initialization without search or physical work."""
import argparse
import builtins
import os
from pathlib import Path
import resource
import shutil
import sys
import time
import traceback

from pact_generalization import ROOT, binding, now, read, write
from pact_generalization_infrastructure import execute, external_binding
from pact.optimizer.cold_start import load
from pact.scan.model import ScanArchitecture

OUT = ROOT/'results/pact_cold_start_unseen_20261004'
RUN = Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cold_start_unseen_20261004')
SOURCES = (
    'scripts/pact_cold_start_initialization_diagnostic.py', 'src/pact/optimizer/cold_start.py',
    'src/pact/optimizer/stage_b_inputs.py', 'src/pact/optimizer/implementation_v2.py',
    'src/pact/optimizer/candidate_sensitive.py', 'src/pact/optimizer/candidate_physical.py',
    'src/pact/optimizer/candidate_stateful.py', 'src/pact/optimizer/stateful_geometry.py',
    'src/pact/integration/patterns.py', 'src/pact/scan/model.py',
)
FORBIDDEN = ('s5378', 's9234', 's15850', '/results/pact_stage_b/', '/reports/end_to_end/',
             '/results/pact_end_to_end_20261004/', '/reports/v2/')


class ReadAudit:
    """Observe loader reads and reject access to historical experiment state."""
    def __init__(self):
        self.paths, self.rejected = set(), []

    def check(self, path, mode):
        if isinstance(path, int) or not isinstance(path, (str, bytes, os.PathLike)):
            return
        if not ('r' in mode or '+' in mode):
            return
        path = os.fsdecode(path).replace('\\', '/')
        self.paths.add(path)
        if any(value in path.lower() for value in FORBIDDEN):
            self.rejected.append(path)
            raise AssertionError('Historical state access prohibited: '+path)

    def __enter__(self):
        self.original_builtin = builtins.open
        self.original_path = Path.open
        audit = self
        def builtin(path, mode='r', *args, **kwargs):
            audit.check(path, mode)
            return audit.original_builtin(path, mode, *args, **kwargs)
        def path_open(path, mode='r', *args, **kwargs):
            audit.check(path, mode)
            return audit.original_path(path, mode, *args, **kwargs)
        builtins.open, Path.open = builtin, path_open
        return self

    def __exit__(self, *args):
        builtins.open, Path.open = self.original_builtin, self.original_path


def worker(manifest, folder):
    began = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    audit = ReadAudit()
    record = dict(scope='LOADER_ONLY; no search, mutation, selection, routing or activity measurement',
        started_utc=now(), manifest=external_binding(manifest), status='PENDING')
    try:
        with audit:
            model, starts, contract = load(manifest)
            arch = contract.initial_architecture
            arch.to_json(folder/'initial_architecture_roundtrip.json')
            loaded = ScanArchitecture.from_json(folder/'initial_architecture_roundtrip.json')
            assert loaded.canonical_dict() == arch.canonical_dict()
            assert loaded.sha256() == arch.sha256() == contract.data['reference_architecture_hash']
            assert len(starts) == 1 and starts[0][0] == contract.data['reference_method']
            initial = model.architecture_from(starts[0][1])
            assert initial.sha256() == arch.sha256()
            assert not audit.rejected
        record.update(status='PASS', design=contract.design, initial_architecture_hash=arch.sha256(),
            exact_roundtrip='PASS', roundtrip=external_binding(folder/'initial_architecture_roundtrip.json'),
            start_count=len(starts), labels=[label for label, _ in starts],
            model=model.metadata, FF_count=len(arch.cells), ATPG_pattern_count=len(model.load),
            initialization_from_external_reference_only=True)
    except Exception as error:
        record.update(status='FAILED', failure_class='FRAMEWORK_BLOCKER',
            error=str(error), traceback=traceback.format_exc())
    after = resource.getrusage(resource.RUSAGE_SELF)
    record.update(completed_utc=now(), wall_seconds=time.perf_counter()-began,
        CPU_seconds=(after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime),
        peak_RSS_KiB=after.ru_maxrss, historical_state_accesses=len(audit.rejected),
        forbidden_historical_reads=audit.rejected, audited_read_paths=sorted(audit.paths),
        optimizer_executions=0, candidate_evaluations=0, routing_executions=0,
        ATPG_executions=0, simulation_executions=0)
    write(folder/'worker_result.json', record, immutable=True)
    print('LOADER_DIAGNOSTIC', record.get('design'), record['status'], flush=True)


def run(manifest):
    manifest = Path(manifest).resolve()
    data = read(manifest)
    design = data['design']
    if not design or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in design):
        raise ValueError('Unsafe design artifact name')
    folder = RUN/'initialization_diagnostic'/design
    folder.mkdir(parents=True, exist_ok=True)
    config_path = OUT/f'scalability/{design}_initialization_diagnostic_configuration.json'
    config = dict(schema='pact_cold_start_initialization_diagnostic_v1', design=design,
        created_utc=now(), input=binding(manifest), sources={s: binding(ROOT/s) for s in SOURCES},
        scope='LOADER_ONLY; no search, mutation, selection, routing or activity measurement',
        timeout_seconds=1800, solver_threads=1, scratch_minimum_free_GiB=20,
        initial_architecture='Frozen strongest qualified external reference only',
        historical_read_guard=list(FORBIDDEN), prerequisite_activity_measurement=False)
    write(config_path, config, immutable=True)
    result = dict(design=design, configuration=binding(config_path), created_utc=now(),
        scope=config['scope'], status='PENDING', search_completed=False)
    try:
        if shutil.disk_usage(RUN).free < 20*1024**3:
            raise RuntimeError('Registered minimum free scratch reserve is 20 GiB')
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='1')
        result['execution'] = execute(['/usr/bin/time', '-v', '-o', folder/'resources.txt', sys.executable,
            ROOT/'scripts/pact_cold_start_initialization_diagnostic.py', '--manifest', manifest,
            '--worker', '--folder', folder], folder/'execution', timeout=1800, env=env)
        result.update(read(folder/'worker_result.json'))
        result['worker_result'] = external_binding(folder/'worker_result.json')
        result['resources'] = external_binding(folder/'resources.txt')
    except Exception as error:
        execution_path = folder/'execution/execution.json'
        execution = read(execution_path) if execution_path.exists() else None
        limited = (execution and (execution['timed_out'] or execution['exit_code'] in (-9, 137))) or 'scratch reserve' in str(error)
        result.update(status='FAILED', failure_class='RESOURCE_LIMIT' if limited else 'FRAMEWORK_BLOCKER',
            error=str(error), traceback=traceback.format_exc(), execution=execution)
    result['completed_utc'] = now()
    write(OUT/f'scalability/{design}_initialization_diagnostic.json', result, immutable=True)
    if result['status'] != 'PASS':
        write(OUT/f'failures/{design}_initialization_diagnostic.json', result, immutable=True)
    print('INITIALIZATION_DIAGNOSTIC', design, result['status'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--folder', type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.manifest, args.folder)
    else:
        run(args.manifest)


if __name__ == '__main__':
    main()
