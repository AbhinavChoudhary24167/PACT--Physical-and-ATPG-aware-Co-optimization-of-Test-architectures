#!/usr/bin/env python3
"""Resume the frozen physical flow with qualified B3T and exact B2 bindings."""
import argparse
import csv
import os
from pathlib import Path

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, write
from pact_oss_canonicalize import csv_write, validate_architecture
from pact.scan.model import ScanArchitecture
from pact.physical.phase0c_port_policy import frozen_def_ports
import pact_oss_topology as recovery
import pact_oss_serialization
pact_oss_serialization.activate()
import pact_oss_receiver_stage_a as stage

STAGE = recovery.CAMPAIGN / 'stage_a'
RAW = recovery.DATA / 'stage_a'
B2 = OUT / 'recovery_20261003/baselines/B2_openroad_10176'


def checked(item):
    if binding(item['path'])['sha256'] != item['sha256']:
        raise ValueError('Frozen binding changed: ' + item['path'])


def display(method):
    return 'B3T — PR #10666 + R0 compile + R1 endpoint/metadata + R1 Verilog input-alias repairs' if method == 'B3T' else method


def gate():
    recovery.ensure()
    from pact_oss_receiver_reuse_preflight import require_preflight, environment
    require_preflight()
    environment()
    contract = read(OUT / 'protocol/benchmark_contract.json')
    checked(contract['freeze'])
    b2 = read(B2 / 'qualification.json')
    if b2['status'] != 'PASS' or b2['source_commit'] != '6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf':
        raise ValueError('Frozen exact B2 is not qualified')
    build = read(recovery.FOLDER / 'build_result.json')
    checked(build['binary'])
    qualification = read(recovery.FOLDER / 'qualification.json')
    if qualification['status'] != 'PASS' or qualification['source_commit'] != build['commit'] or qualification['binary_sha256'] != build['binary_sha256']:
        raise ValueError('B3T all-design gate is incomplete')
    if recovery.git('rev-parse', 'HEAD').strip() != build['commit'] or recovery.git('diff', '--ignore-submodules', '--name-only').strip():
        raise ValueError('B3T source is no longer immutable')
    for d in DESIGNS:
        for q in (b2, qualification):
            checked(q['designs'][d]['canonical'])
            checked(q['designs'][d]['proof'])
    if (STAGE / 'selection_receipt.json').exists():
        for item in read(STAGE / 'selection_receipt.json')['bindings'].values():
            checked(item)
    return contract


def configure_modules():
    stage.STAGE, stage.RAW = STAGE, RAW
    stage.gate, stage.method_display = gate, display
    import pact_oss_receiver_measure as measure
    measure.STAGE, measure.RAW, measure.gate = STAGE, RAW, gate
    import pact_oss_receiver_results as results
    results.STAGE, results.gate, results.method_display = STAGE, gate, display
    return measure, results


def prepare():
    gate()
    rows = list(csv.DictReader((OUT / 'stage_a/architecture_index.csv').open()))
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')
    for method, folder in (('B2', B2), ('B3T', recovery.FOLDER)):
        q = read(folder / 'qualification.json')
        for design in DESIGNS:
            item = q['designs'][design]
            architecture = ScanArchitecture.from_json(Path(item['canonical']['path']))
            rows.append(dict(design=design, method=method, architecture_hash=architecture.sha256(),
                architecture_path=item['canonical']['path'], roles='single_solution', selected='True',
                representative='True', status='CANONICAL_QUALIFIED', FF_count=len(architecture.cells), K=2,
                predicted_E='', predicted_H8='', predicted_H4=''))
    manifest, diagnostics = [], []
    for row in rows:
        row['method_display'] = display(row['method'])
        inputs = frozen['frozen_inputs'][row['design']]
        a = ScanArchitecture.from_json(Path(row['architecture_path']))
        reference = ScanArchitecture.from_json(Path(inputs['B0_reference']['path']))
        validate_architecture(a, reference)
        if a.sha256() != row['architecture_hash']:
            raise ValueError('Frozen architecture identity changed')
        ports, unit = frozen_def_ports(Path(inputs['placement']['path']), 2)
        xy = {c.name: (c.x_um, c.y_um) for c in a.cells}
        wire = endpoints = 0.
        for c in a.chains:
            wire += sum(abs(xy[x][0]-xy[y][0])+abs(xy[x][1]-xy[y][1]) for x,y in zip(c.cells,c.cells[1:]))
            si = 'test_si' if c.scan_in == 'test_si_0' else c.scan_in
            so = 'test_so' if c.scan_out == 'test_so_0' else c.scan_out
            endpoints += sum(abs(xy[c.cells[0]][axis]-ports[si][axis]/unit)+abs(xy[c.cells[-1]][axis]-ports[so][axis]/unit) for axis in (0,1))
            for i, ff in enumerate(c.cells):
                manifest.append(dict(row, chain_id=c.chain_id, chain_index=i, ordered_ff_identity=ff,
                                     scan_in=c.scan_in, scan_out=c.scan_out, chain_length=len(c.cells)))
        lengths = [len(c.cells) for c in a.chains]
        diagnostics.append(dict(row, scan_hpwl_um=wire, port_inclusive_scan_hpwl_um=wire+endpoints,
            maximum_chain_length=max(lengths), minimum_chain_length=min(lengths), chain_imbalance=max(lengths)-min(lengths),
            estimated_scan_path_length_um=wire+endpoints))
    if len(rows) != 30 or len(manifest) != 9176 or sum(r['selected']=='True' for r in rows) != 19:
        raise ValueError('Frozen Stage-A inventory differs')
    csv_write(STAGE / 'architecture_index.csv', list(rows[0]), rows)
    csv_write(STAGE / 'architecture_manifest.csv', list(manifest[0]), manifest)
    csv_write(STAGE / 'pre_route_metrics.csv', list(diagnostics[0]), diagnostics)
    inputs = {'original_selection': OUT / 'stage_a/P0_SELECTION.json',
              'original_architectures': OUT / 'stage_a/architecture_index.csv',
              'reuse_eligibility': OUT / 'receiver_recovery_20261003/reuse_preflight/eligibility.json',
              'B2': B2 / 'qualification.json', 'B3T': recovery.FOLDER / 'qualification.json',
              'contract': OUT / 'protocol/benchmark_contract.json'}
    inputs.update({name: STAGE / (name+'.csv') for name in ('architecture_index','architecture_manifest','pre_route_metrics')})
    write(STAGE / 'selection_receipt.json', dict(status='PACT_STAGE_A_RESUMED',
        bindings={key: binding(path) for key,path in inputs.items()}, selected_method_records=19,
        canonical_architectures=30, selected_P0=7, new_search_runs=0, B0_B1_B2_P0_regenerated=False,
        backend='/usr/bin/openroad', technology='Nangate45', ORFS_revision='5e8b1450d19263f797a27c4f371b9dd19f32a3aa',
        NUM_CORES=2, GRT_SEED=11, frozen_route_and_measurement_adapters_reused=True))
    print('PACT_STAGE_A_RESUMED', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare','route','measure','collect'))
    parser.add_argument('--design', choices=DESIGNS)
    args = parser.parse_args()
    os.environ.setdefault('PACT_BENCHMARK_GIT', 'git')
    measure, results = configure_modules()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'route':
        stage.route(args.design)
    elif args.action == 'measure':
        measure.measure(args.design)
    else:
        results.collect()
