#!/usr/bin/env python3
"""Check frozen functional/FF-placement gates on every retained new reference.

Reads existing routes only. Does not route, generate ATPG, simulate, or search.
"""
import gzip
import os
from pathlib import Path
import shutil
import traceback

from pact_generalization import ROOT, OUT, binding, now, read, sha, write
from pact_generalization_infrastructure import RUN, execute, external_binding
from pact_generalization_physical import LIB, prep
from pact_generalization_report import ATTEMPTS, latest_gate


def run():
    records = []
    benchmark = read(OUT/'manifests/generalization_benchmark_manifest.json')
    sources = {name: binding(ROOT/name) for name in (
        'scripts/physical_effect_export.py', 'scripts/pact_generalization_export.py',
        'scripts/pact_generalization_routed.py', 'scripts/pact_generalization_scan_masters.py',
        'scripts/pact_generalization_export_gates.py')}
    for design in benchmark['designs']:
        name = design['design']
        attempt, _, gate = latest_gate(name)
        if not gate or gate['status'] != 'INFRASTRUCTURE_QUALIFIED':
            continue
        preparation = prep(name)
        references = read(OUT/f'repair_attempts/{attempt}/baselines/{name}_references.json')['records']
        assert {r['method'] for r in references} == {'B0', 'B1', 'B2', 'B3T'}
        root = RUN/'reference_export_gates'/name
        rows = []
        for reference in references:
            assert reference['status'] == 'QUALIFIED'
            route = read(reference['provenance']['path'])
            rows.append(dict(design=name, role=reference['method'],
                architecture=reference['architecture'], routed_archive=route['archive'],
                source_placed_database=preparation['source_placed_database'],
                inputs=dict(placement=preparation['placed_def']),
                original_qualification=reference['provenance']))
        write(root/'manifest.json', dict(rows=rows, library=external_binding(LIB),
            sources=sources, created_utc=now(), scope='EXISTING_NEW_ROUTES_EXPORT_ONLY'), immutable=True)
        env = dict(os.environ, PACT_PHYSICAL_EFFECT_OUT=str(root))
        for row in rows:
            folder = root/name/row['role']
            folder.mkdir(parents=True, exist_ok=True)
            receipt = dict(design=name, method=row['role'], created_utc=now(),
                manifest=external_binding(root/'manifest.json'), inputs=row,
                status='PENDING', routing_executions=0, ATPG_executions=0,
                simulation_executions=0, PACT_search_executions=0)
            try:
                for key in ('architecture', 'routed_archive', 'source_placed_database'):
                    assert sha(row[key]['path']) == row[key]['sha256']
                with gzip.open(row['routed_archive']['path'], 'rb') as src, (folder/'routed.odb').open('wb') as dst:
                    shutil.copyfileobj(src, dst)
                receipt['execution'] = execute(['/usr/bin/openroad', '-exit', '-python',
                    ROOT/'scripts/pact_generalization_export.py', folder],
                    folder/'execution', timeout=1200, env=env)
                for result in ('topology_verification', 'functional_verification'):
                    assert read(folder/f'{result}.json')['status'] == 'PASS'
                functional = read(folder/'functional_verification.json')
                assert functional['FF_placement'] == 'exact'
                receipt.update(status='PASS', FF_placement='exact',
                    functional_sinks_and_outputs=functional['functional_sinks_and_outputs'],
                    outputs={p.name:external_binding(p) for p in folder.glob('*.json')})
            except Exception as error:
                receipt.update(status='FAILED', failure_class='PHYSICAL_BACKEND_FAIL',
                    error=str(error), traceback=traceback.format_exc())
            destination = OUT/f'physical/{name}/reference_export_gates/{row["role"]}'
            for result in ('topology_verification', 'functional_verification'):
                if (folder/f'{result}.json').exists():
                    destination.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(folder/f'{result}.json', destination/f'{result}.json')
            write(destination/'receipt.json', receipt, immutable=True)
            records.append(dict(design=name, method=row['role'], status=receipt['status'],
                receipt=binding(destination/'receipt.json')))
            print('EXPORT_GATES', name, row['role'], receipt['status'], flush=True)
    write(OUT/'physical/reference_export_gates.json', dict(
        status='PASS' if all(r['status']=='PASS' for r in records) else 'FAILED',
        scope='All 24 already-routed new references; frozen functional and exact FF placement checks',
        created_utc=now(), records=records, sources=sources), immutable=True)
    assert len(records) == 24 and all(r['status']=='PASS' for r in records)


if __name__ == '__main__':
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps',
        PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS', OMP_NUM_THREADS='1',
        OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='1')
    run()
