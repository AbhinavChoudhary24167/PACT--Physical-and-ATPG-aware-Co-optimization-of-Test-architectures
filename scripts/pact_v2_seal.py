"""Verify and index new physical evidence using existing milestone conventions."""
import argparse
import gzip
from pathlib import Path
import shutil
import subprocess
from pact_v2 import ROOT, read, write_json, binding, file_sha256


def seal(out):
    manifest = read(out/'measurement/manifest.json')
    summary = read(out/'summary.json')
    if summary['classification'] == 'PACT_V2_PHYSICAL_EVALUATION_INCOMPLETE':
        raise ValueError('Physical evaluation is incomplete')
    checks = []
    for row in manifest['rows']:
        folder = out/'measurement'/row['design']/row['role']
        simulation = read(folder/'simulation_manifest.json')
        for value in [*simulation['inputs'].values(), simulation['cells'], row['routed_archive'], row['qualification']]:
            if file_sha256(Path(value['path'])) != value['sha256']:
                raise ValueError('Bound artifact changed: '+value['path'])
        activity = read(folder/'activity_summary.json')
        if file_sha256(folder/'activity.vcd') != activity['VCD']['sha256']:
            raise ValueError('Waveform changed')
        for name in ('functional_verification', 'topology_verification', 'FF_transition_crosscheck'):
            if read(folder/(name+'.json'))['status'] != 'PASS':
                raise ValueError('Verification did not pass: '+name)
        if 'PASS patterns=' not in (folder/'simulate.log').read_text():
            raise ValueError('Functional workload replay did not pass')
        for name in ('per_cycle.csv', 'stimulus.v', 'cycles.json'):
            with (folder/name).open('rb') as src, (folder/(name+'.gz')).open('wb') as dst:
                with gzip.GzipFile(fileobj=dst, mode='wb', mtime=0, filename='') as compressed:
                    shutil.copyfileobj(src, compressed)
        local = ('activity.vcd', 'extracted.spef', 'routed.odb', 'simulation.vvp', 'transitions.npz')
        write_json(folder/'analysis_manifest.json', dict(
            architecture_sha256=row['architecture_sha256'], physical_qualification=row['qualification'],
            local_intermediates={name: dict(binding(folder/name), bytes=(folder/name).stat().st_size) for name in local},
            retained_compressed={name: binding(folder/(name+'.gz')) for name in ('per_cycle.csv', 'stimulus.v', 'cycles.json')},
            simulation_manifest=binding(folder/'simulation_manifest.json'),
            stage_seconds={name: read(folder/(name+'.execution.json'))['seconds'] for name in ('export', 'extract', 'compile', 'simulate')},
            generation=f'python scripts/pact_v2.py measure --design {row["design"]} --output {out}'))
        checks.append(dict(design=row['design'], architecture=row['role'], status='PASS',
                           FF_cycle_values_checked=read(folder/'FF_transition_crosscheck.json')['FF_cycle_values_checked']))
    write_json(out/'validation_summary.json', dict(physical_checks=checks,
        tests=read(out/'tests.json'), selected_reproducibility=read(out/'reproducibility.json'),
        final_classification=summary['classification']))
    files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', str(out)], cwd=ROOT, text=True).splitlines()
    evidence = {p: dict(sha256=file_sha256(ROOT/p), bytes=(ROOT/p).stat().st_size)
                for p in sorted(set(files)) if Path(p).name != 'evidence_manifest.json'}
    sources = ['src/pact/optimizer/implementation_v2.py', 'src/pact/optimizer/search.py',
               'scripts/pact_v2.py', 'scripts/pact_v2_report.py', 'scripts/pact_v2_check.py', 'scripts/pact_v2_seal.py',
               'scripts/pact_solver_routes.py', 'scripts/physical_effect.py', 'scripts/physical_effect_export.py',
               'src/pact/physical_effect.py', 'tests/unit/test_implementation_v2.py']
    write_json(out/'evidence_manifest.json', dict(artifacts=evidence,
               source_code={p: file_sha256(ROOT/p) for p in sources},
               scope='Compact new milestone artifacts; local raw files indexed in per-candidate analysis manifests'))
    print('SEALED', len(evidence), 'artifacts;', len(checks), 'new physical implementations', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT/'results/pact_v2')
    seal(p.parse_args().output.resolve())
