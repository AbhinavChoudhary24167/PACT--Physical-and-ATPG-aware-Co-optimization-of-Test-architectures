#!/usr/bin/env python3
"""Reuse qualified activity evidence or invoke the frozen physical-effect flow."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import traceback
import subprocess

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, write
from pact_oss_receiver_stage_a import STAGE, RAW, gate, exclusive
from pact.scan.model import ScanArchitecture
from pact.integration.patterns import fan_workload, serialize


def check(item):
    if binding(item['path'])['sha256'] != item['sha256']:
        raise ValueError('Measurement input integrity mismatch: ' + item['path'])


def verify_measurement(manifest_path, row, route):
    manifest = read(manifest_path)
    historical = not Path(manifest_path).resolve().is_relative_to(RAW.resolve())
    if historical:
        from pact_oss_receiver_reuse_preflight import checked_cached_binding
        checked_cached_binding(manifest_path)
        checked_cached_binding(row['qualification']['path'])
    original_manifest = read(ROOT / 'reports/physical_effect/manifest.json')
    if manifest['tools']['openroad'] != original_manifest['tools']['openroad']:
        raise ValueError('Historical measurement used a different OpenROAD backend version')
    if manifest['tools']['iverilog'] != original_manifest['tools']['iverilog']:
        raise ValueError('Measurement used a different Icarus version')
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')['frozen_inputs'][row['design']]
    for actual, expected in ((row['source_placed_database'], frozen['3_place.odb']), (row['SDC'], frozen['3_place.sdc'])):
        if actual['sha256'] != expected['sha256']:
            raise ValueError('Measurement physical source differs from the frozen contract')
    for key in ('patterns', 'identity_map', 'placement'):
        if row['inputs'][key]['sha256'] != frozen[key]['sha256']:
            raise ValueError('Measurement workload or placement differs from the frozen contract')
    for key in ('library', 'simulation_cells', 'extraction_rules'):
        check(manifest[key])
        original = original_manifest[key]
        if manifest[key]['sha256'] != original['sha256']:
            raise ValueError('Historical measurement used different technology inputs')
    for key in ('architecture', 'routed_archive', 'source_placed_database', 'source_netlist', 'SDC',
                'qualification', 'workload', 'prior_integration'):
        check(row[key])
    for item in row['inputs'].values():
        check(item)
    if row['routed_archive']['sha256'] != route['archive']['sha256']:
        raise ValueError('Measurement is bound to a different routed database')
    architecture = ScanArchitecture.from_json(Path(row['architecture']['path']))
    if architecture.sha256() != row['architecture_sha256']:
        raise ValueError('Measurement architecture identity differs')
    folder = manifest_path.parent / row['design'] / row['role']
    if historical:
        for filename in ('activity_summary.json', 'FF_transition_crosscheck.json', 'simulation_manifest.json',
                         'simulate.log', 'topology_verification.json', 'functional_verification.json'):
            checked_cached_binding(folder / filename)
    simulation = read(folder / 'simulation_manifest.json')
    if simulation['architecture_sha256'] != architecture.sha256():
        raise ValueError('Simulation architecture identity differs')
    for item in simulation['inputs'].values():
        check(item)
    check(simulation['cells'])
    summary = read(folder / 'activity_summary.json')
    if binding(folder / 'activity.vcd')['sha256'] != summary['VCD']['sha256']:
        raise ValueError('Measured VCD changed')
    crosscheck = read(folder / 'FF_transition_crosscheck.json')
    for filename in ('topology_verification.json', 'functional_verification.json'):
        if read(folder / filename)['status'] != 'PASS':
            raise ValueError('Physical topology/functional qualification failed: ' + filename)
    for filename in ('export.execution.json', 'extract.execution.json', 'compile.execution.json', 'simulate.execution.json'):
        if read(folder / filename)['returncode'] != 0:
            raise ValueError('Measurement execution did not succeed: ' + filename)
    if crosscheck['status'] != 'PASS' or 'PASS patterns=' not in (folder / 'simulate.log').read_text():
        raise ValueError('Functional or every-FF transition qualification has not passed')
    workload = read(row['workload']['path'])
    _, states = fan_workload(Path(row['inputs']['patterns']['path']), read(row['inputs']['identity_map']['path'])['records'], architecture)
    expected = dict(architecture_sha256=architecture.sha256(), cycles=max(len(c.cells) for c in architecture.chains),
        patterns=[dict(pattern=s['pattern'], source_fields=s['source_fields'], load=serialize(architecture, s['load_state']),
                       unload=serialize(architecture, s['response_state'], response=True)) for s in states])
    if workload != expected or summary['shift_cycles'] != 2 * len(states) * expected['cycles']:
        raise ValueError('Measurement workload differs from the frozen FAN serialization')
    if summary['patterns'] != len(states) or crosscheck['cycles'] != summary['shift_cycles'] or crosscheck['FF_cycle_values_checked'] != summary['shift_cycles'] * len(architecture.cells):
        raise ValueError('Every-FF crosscheck has incomplete workload coverage')
    return dict(status='QUALIFIED', folder=str(folder), manifest=binding(manifest_path),
        summary=binding(folder / 'activity_summary.json'), crosscheck=binding(folder / 'FF_transition_crosscheck.json'),
        functional_log=binding(folder / 'simulate.log'), spatial_bins=binding(folder / 'spatial_bins.json'),
        VCD=binding(folder / 'activity.vcd'), simulation_manifest=binding(folder / 'simulation_manifest.json'),
        topology=binding(folder / 'topology_verification.json'), functional=binding(folder / 'functional_verification.json'))


def current_tools(original):
    observed, binaries = {}, {}
    for name in ('openroad', 'iverilog', 'vvp'):
        executable = shutil.which(name)
        if not executable:
            raise ValueError('Frozen measurement executable is unavailable: ' + name)
        result = subprocess.run([executable, '-version' if name == 'openroad' else '-V'], text=True, capture_output=True, check=True)
        lines = (result.stdout + result.stderr).splitlines()
        version = next((line for line in lines if line.strip()), '')
        if name in original['tools'] and version != original['tools'][name]:
            raise ValueError('Measurement tool version changed: ' + name)
        observed[name] = version
        binaries[name] = dict(binding(executable), reported_version=version)
    return observed, binaries


def prior(design, sha, route):
    manifests = [ROOT / 'results' / ns / 'measurement/manifest.json'
        for ns in ('pact_candidate_stateful', 'pact_candidate_sensitive', 'pact_v2')]
    manifests.append(ROOT / 'reports/physical_effect/manifest.json')
    for path in manifests:
        if not path.exists():
            continue
        for row in read(path)['rows']:
            if row['design'] != design or row['architecture_sha256'] != sha:
                continue
            folder = path.parent / design / row['role']
            if not (folder / 'activity_summary.json').exists():
                continue
            if row['routed_archive']['sha256'] != route['archive']['sha256']:
                continue
            result = verify_measurement(path, row, route)
            return dict(result, reused=True)
    return None


def measure_unlocked(design):
    gate()
    import physical_effect as pe
    # The existing flow invokes openroad by name during extraction/export.
    # Make that name resolve to the independently verified fixed backend.
    os.environ['PATH'] = '/usr/bin:' + os.environ['PATH']
    if shutil.which('openroad') != '/usr/bin/openroad':
        raise ValueError('Measurement backend does not resolve to /usr/bin/openroad')
    records, attempts = {}, 0
    routes = read(STAGE / 'routes' / (design + '.json'))['records']
    rows = [r for r in csv.DictReader((STAGE / 'architecture_index.csv').open()) if r['design'] == design]
    original = read(ROOT / 'reports/physical_effect/manifest.json')
    observed_tools, runtime_binaries = current_tools(original)
    for item in rows:
        sha = item['architecture_hash']
        if sha in records or sha not in routes:
            continue
        route = routes[sha]
        if route['report']['status'] != 'QUALIFIED':
            records[sha] = dict(status='PHYSICAL_QUALIFICATION_FAILED', reused=False)
            continue
        reused = prior(design, sha, route)
        if reused:
            records[sha] = reused
            print('QUALIFIED_MEASUREMENT_REUSE', design, sha[:12], flush=True)
            continue
        if item['selected'] != 'True':
            continue
        folder = RAW / 'measurement' / sha / design / sha[:12]
        folder.mkdir(parents=True, exist_ok=True)
        root = folder.parents[1]
        manifest_path = root / 'manifest.json'
        if manifest_path.exists():
            raise ValueError('Measurement attempt already exists; preserve its outcome')
        architecture = ScanArchitecture.from_json(Path(item['architecture_path']))
        row = next(r.copy() for r in original['rows'] if r['design'] == design and r['role'] in ('P', 'T'))
        _, states = fan_workload(Path(row['inputs']['patterns']['path']), read(row['inputs']['identity_map']['path'])['records'], architecture)
        workload = dict(architecture_sha256=sha, cycles=max(len(c.cells) for c in architecture.chains),
            patterns=[dict(pattern=s['pattern'], source_fields=s['source_fields'], load=serialize(architecture, s['load_state']),
                           unload=serialize(architecture, s['response_state'], response=True)) for s in states])
        write(folder / 'workload.json', workload)
        order = hashlib.sha256(json.dumps([(c.chain_id, list(c.cells)) for c in architecture.chains], separators=(',', ':')).encode()).hexdigest()
        row.update(role=sha[:12], architecture=binding(item['architecture_path']), architecture_sha256=sha,
            scan_order_sha256=order, selected_PACT_architecture_sha256=sha, routed_archive=route['archive'],
            qualification=route['report_binding'], workload=binding(folder / 'workload.json'),
            PACT_remapped_source=None, chain_lengths=[len(c.cells) for c in architecture.chains])
        manifest = {k: v for k, v in original.items() if k != 'rows'}
        manifest.update(schema='pact_oss_receiver_stage_a_physical_effect_v1', rows=[row],
            tools=observed_tools, runtime_binaries=runtime_binaries, fixed_backend=binding('/usr/bin/openroad'))
        write(manifest_path, manifest)
        pe.OUT = root
        os.environ['PACT_PHYSICAL_EFFECT_OUT'] = str(root)
        attempts += 1
        receipt = STAGE / 'measurement_attempts' / design / sha
        receipt.mkdir(parents=True, exist_ok=True)
        snapshots = {}
        for relative in ('scripts/pact_oss_receiver_measure.py', 'scripts/physical_effect.py', 'scripts/physical_effect_export.py', 'src/pact/physical_effect.py'):
            destination = receipt / Path(relative).name
            shutil.copy2(ROOT / relative, destination)
            snapshots[relative] = binding(destination)
        try:
            pe.execute(design, resume=False)
            result = verify_measurement(manifest_path, row, route)
            records[sha] = dict(result, reused=False, executed_sources=snapshots)
        except Exception as error:
            records[sha] = dict(status='MEASUREMENT_FAILED', reused=False, error=str(error),
                traceback=traceback.format_exc(), folder=str(folder), manifest=binding(manifest_path), executed_sources=snapshots)
            print('MEASUREMENT_FAILED', design, sha[:12], str(error), flush=True)
        # Preserve compact evidence locally, while all large raw data stays on D:.
        for filename in ('activity_summary.json', 'FF_transition_crosscheck.json', 'spatial_bins.json',
                         'topology_verification.json', 'functional_verification.json',
                         'simulation_manifest.json', 'simulate.log', 'export.execution.json', 'extract.execution.json',
                         'compile.execution.json', 'simulate.execution.json'):
            if (folder / filename).exists():
                shutil.copy2(folder / filename, receipt / filename)
    write(STAGE / 'measurements' / (design + '.json'), dict(design=design, records=records,
        new_measurement_attempts=attempts, fixed_backend=binding('/usr/bin/openroad'), new_ATPG_runs=0))
    print('STAGE_A_MEASUREMENTS_RECORDED', design, 'new', attempts, flush=True)


def measure(design):
    with exclusive(RAW / 'measurement' / design, 'measure'):
        return measure_unlocked(design)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--design', required=True, choices=DESIGNS)
    raise SystemExit(measure(parser.parse_args().design))
