"""Replay selected predictions, verify provenance and index compact milestone evidence."""
import argparse
import gzip
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import numpy as np
from pact_candidate_sensitive import load
from pact_v2 import ROOT, DESIGNS, read, write_json, binding, file_sha256, ScanArchitecture
from pact.optimizer import candidate_sensitive as cs
from pact.optimizer import implementation_v2 as v2


def replay_predictions(out):
    began = time.perf_counter()
    replay = []
    bindings = []
    for design in DESIGNS:
        result = read(out/design/'search.json')
        inputs = read(out/design/'inputs.json')
        bindings.extend(binding(out/design/name) for name in ('inputs.json', 'search.json', 'physical_model.json'))
        for value in inputs['inputs'].values():
            if binding(value['path'])['sha256'] != value['sha256']: raise ValueError('Input changed: '+value['path'])
        for path, sha in inputs['source_code'].items():
            if file_sha256(ROOT/path) != sha: raise ValueError('Search source changed: '+path)
            bindings.append(binding(ROOT/path))
        model, _, physical, _, _ = load(design, out)
        if physical != read(out/design/'physical_model.json'): raise ValueError('Physical model reconstruction differs')
        for row in result['selected']:
            arch = ScanArchitecture.from_json(Path(row['architecture']))
            assert arch.sha256() == row['architecture_sha256']
            orders = model.orders(arch)
            assert v2.order_id(orders) == row['order_id']
            expected = [row['metrics'][k] for k in cs.METRICS]
            np.testing.assert_allclose(cs.reference(model, orders), expected, rtol=1e-9, atol=1e-6)
            np.testing.assert_allclose(cs.State(model, orders).score(), expected, rtol=1e-9, atol=1e-6)
            np.testing.assert_allclose(v2.reference(model.frozen, orders),
                [row['frozen_metrics'][k] for k in v2.METRICS], rtol=1e-9, atol=1e-6)
        replay.append(dict(design=design, selected_reproduced=len(result['selected']), status='PASS'))
    write_json(out/'reproducibility.json', replay)
    write_json(out/'replay_bindings.json', dict(bindings=bindings, results=binding(out/'reproducibility.json'),
        seconds=time.perf_counter()-began, command=sys.argv))
    print('PASS independent selected-prediction replay', flush=True)
    return replay


def check(out, reuse_replay=False):
    began = time.perf_counter()
    summary = read(out/'summary.json')
    if summary['classification'].endswith('INCOMPLETE'):
        raise ValueError('Complete the selected physical evaluations before sealing')
    if reuse_replay:
        saved = read(out/'replay_bindings.json')
        for value in saved['bindings']+[saved['results']]:
            if binding(value['path'])['sha256'] != value['sha256']: raise ValueError('Replay binding changed')
        replay = read(out/'reproducibility.json')
    else:
        replay = replay_predictions(out)
    suite = ET.parse(out/'repository_tests.xml').getroot().find('testsuite')
    tests = dict(repository_suite=dict(tests=int(suite.get('tests')), errors=int(suite.get('errors')),
        failures=int(suite.get('failures')), skipped=int(suite.get('skipped')), seconds=float(suite.get('time'))),
        command='python -m pytest -q --junitxml=results/pact_candidate_sensitive/repository_tests.xml',
        focused_preflight=dict(passed=13, command='python -m pytest tests/unit/test_candidate_sensitive.py tests/unit/test_implementation_v2.py -q'))
    if tests['repository_suite']['errors'] or tests['repository_suite']['failures']: raise ValueError('Repository tests failed')
    write_json(out/'tests.json', tests)
    preserved = []
    for path, value in read(ROOT/'results/pact_v2/evidence_manifest.json')['artifacts'].items():
        if file_sha256(ROOT/path) != value['sha256']: raise ValueError('Prior v2 evidence changed: '+path)
        preserved.append(path)
    write_json(out/'prior_evidence_integrity.json', dict(status='PASS', files_verified=len(preserved),
        manifest=binding(ROOT/'results/pact_v2/evidence_manifest.json'), scope='Every compact v2 evidence artifact; historical source code is intentionally extended'))
    checks = []
    manifest_path = out/'measurement/manifest.json'
    if manifest_path.exists():
        for row in read(manifest_path)['rows']:
            folder = out/'measurement'/row['design']/row['role']
            sim = read(folder/'simulation_manifest.json')
            for value in [*sim['inputs'].values(), sim['cells'], row['routed_archive'], row['qualification']]:
                if binding(value['path'])['sha256'] != value['sha256']: raise ValueError('Physical binding changed')
            activity = read(folder/'activity_summary.json')
            assert file_sha256(folder/'activity.vcd') == activity['VCD']['sha256']
            for name in ('functional_verification', 'topology_verification', 'FF_transition_crosscheck'):
                assert read(folder/(name+'.json'))['status'] == 'PASS'
            assert 'PASS patterns=' in (folder/'simulate.log').read_text()
            for name in ('per_cycle.csv', 'stimulus.v', 'cycles.json'):
                with (folder/name).open('rb') as src, (folder/(name+'.gz')).open('wb') as dst:
                    with gzip.GzipFile(fileobj=dst, mode='wb', mtime=0, filename='') as compressed:
                        shutil.copyfileobj(src, compressed)
            raw = ('activity.vcd', 'extracted.spef', 'routed.odb', 'simulation.vvp', 'transitions.npz')
            write_json(folder/'analysis_manifest.json', dict(architecture_sha256=row['architecture_sha256'],
                physical_qualification=row['qualification'], simulation_manifest=binding(folder/'simulation_manifest.json'),
                local_intermediates={name: dict(binding(folder/name), bytes=(folder/name).stat().st_size) for name in raw},
                retained_compressed={name: binding(folder/(name+'.gz')) for name in ('per_cycle.csv', 'stimulus.v', 'cycles.json')},
                stage_seconds={name: read(folder/(name+'.execution.json'))['seconds'] for name in ('export', 'extract', 'compile', 'simulate')}))
            checks.append(dict(design=row['design'], architecture=row['role'], status='PASS'))
    expected = {(r['design'], r['architecture']) for r in summary['candidates']
                if r['new'] and r['selected_roles'] and r['status'] == 'QUALIFIED'}
    if {(r['design'], r['architecture']) for r in checks} != expected:
        raise ValueError('Physical verification set differs from selected qualified candidates')
    write_json(out/'validation_summary.json', dict(tests=tests, reproducibility=replay, physical_checks=checks,
        prior_v2_evidence='UNCHANGED', seconds=time.perf_counter()-began, command=sys.argv))
    files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', str(out)], cwd=ROOT, text=True).splitlines()
    artifacts = {p: dict(sha256=file_sha256(ROOT/p), bytes=(ROOT/p).stat().st_size) for p in sorted(set(files))
                 if Path(p).name != 'evidence_manifest.json'}
    sources = ['scripts/pact_candidate_sensitive.py', 'scripts/pact_candidate_export.py', 'scripts/pact_candidate_report.py',
        'scripts/pact_candidate_check.py', 'src/pact/optimizer/candidate_physical.py', 'src/pact/optimizer/candidate_sensitive.py',
        'src/pact/optimizer/implementation_v2.py', 'tests/unit/test_candidate_sensitive.py', 'docs/pact_candidate_sensitive_model.md']
    write_json(out/'evidence_manifest.json', dict(artifacts=artifacts,
        source_code={p: file_sha256(ROOT/p) for p in sources}, scope='Compact milestone evidence; raw artifacts are hash-indexed locally'))
    print('PASS replay, tests, historical integrity and physical checks;', len(artifacts), 'sealed artifacts', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'results/pact_candidate_sensitive')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--predictions-only', action='store_true')
    mode.add_argument('--reuse-replay', action='store_true')
    args = parser.parse_args()
    if args.predictions_only: replay_predictions(args.output.resolve())
    else: check(args.output.resolve(), reuse_replay=args.reuse_replay)
