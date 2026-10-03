#!/usr/bin/env python3
"""Additive OSS benchmark provenance; never modifies PACT models or old evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/pact_oss_benchmark'
P0_COMMIT = '9d9103027918b1d4af2b209e6d36133ad82d4a4e'
DESIGNS = ('s5378', 's9234', 's15850')
GIT = os.environ.get('PACT_BENCHMARK_GIT', 'git')


def read(path):
    return json.loads(Path(path).read_text())


def binding(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return dict(path=str(path), sha256=digest.hexdigest(), bytes=path.stat().st_size)


def write(path, value):
    path = Path(path)
    if path.exists():
        raise ValueError('Refusing to overwrite evidence: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def git(*args):
    return subprocess.check_output([GIT, *args], cwd=ROOT, text=True).strip()


def freeze():
    if git('rev-parse', 'HEAD') != P0_COMMIT:
        raise ValueError('HEAD differs from requested P0 baseline')
    production = list((ROOT / 'src/pact/optimizer').glob('*.py'))
    production += list((ROOT / 'src/pact/integration').glob('*.py'))
    production += list((ROOT / 'src/pact/scan').glob('*.py'))
    production += [ROOT / p for p in (
        'src/pact/physical_effect.py', 'scripts/pact_candidate_stateful.py',
        'scripts/pact_stateful_corpus.py', 'scripts/pact_stateful_report.py',
        'scripts/pact_candidate_sensitive.py', 'scripts/pact_candidate_report.py',
        'scripts/pact_v2.py', 'scripts/pact_solver_routes.py',
        'scripts/pact_physical_measure.py', 'scripts/phase0c_rewire_odb.py',
        'scripts/phase0d_verify_routed.py') if (ROOT / p).exists()]
    relative = [p.relative_to(ROOT).as_posix() for p in production]
    subprocess.run([GIT, 'diff', '--exit-code', P0_COMMIT, '--', *relative], cwd=ROOT, check=True)
    historical = {}
    for name in ('pact_v2', 'pact_candidate_sensitive', 'pact_candidate_stateful', 'pact_h8_rootcause'):
        for p in sorted((ROOT / 'results' / name).glob('*.json')):
            historical[p.relative_to(ROOT).as_posix()] = binding(p)
        for p in sorted((ROOT / 'results' / name).glob('*.md')):
            historical[p.relative_to(ROOT).as_posix()] = binding(p)
    # The diagnosis remains uncommitted user evidence; hash its entire compact tree.
    diagnosis = {p.relative_to(ROOT).as_posix(): binding(p)
                 for p in sorted((ROOT / 'results/pact_h8_rootcause').rglob('*')) if p.is_file()}
    inputs, budgets = {}, {}
    for design in DESIGNS:
        previous = read(ROOT / 'results/pact_candidate_stateful' / design / 'inputs.json')
        inputs[design] = {}
        for name, expected in previous['inputs'].items():
            actual = binding(expected['path'])
            if actual['sha256'] != expected['sha256']:
                raise ValueError('Frozen input changed: ' + design + '/' + name)
            inputs[design][name] = actual
        block = 's9234f' if design == 's9234' else design
        flow = Path('/root/pact-deps/OpenROAD-flow-scripts/flow')
        base = flow / f'results/nangate45/{block}/phase0b_s11_B0'
        for name in ('3_place.odb', '3_place.sdc'):
            inputs[design][name] = binding(base / name)
        inputs[design]['B0_reference'] = binding(ROOT / f'artifacts/derived/phase0c/{design}/s11/k2/B0.architecture.json')
        search = read(ROOT / 'results/pact_candidate_stateful' / design / 'search.json')
        inputs[design]['P0_search'] = binding(ROOT / 'results/pact_candidate_stateful' / design / 'search.json')
        budgets[design] = dict(config=search['config'], evaluations=search['evaluations'],
                              source='Existing frozen search; no post-route candidate selection')
    record = dict(timestamp=datetime.now(timezone.utc).isoformat(), commit=P0_COMMIT,
                  model='candidate_stateful_depth3_frozen', depth=3, K=2, placement_seed=11,
                  initial_git_status=git('status', '--short'), initial_git_log=git('log', '--oneline', '-n', '10'),
                  production_sources={p.relative_to(ROOT).as_posix(): binding(p) for p in production},
                  historical_evidence=historical, h8_diagnosis=diagnosis,
                  frozen_inputs=inputs, P0_search_resources=budgets,
                  production_diff_against_P0='PASS',
                  uncommitted_inputs='Existing README, planning, fault-identity and H8 diagnosis changes are preserved; not included in milestone commits')
    write(OUT / 'stage_a/P0_FREEZE.json', record)
    contract = dict(version=1, timestamp=record['timestamp'], P0_commit=P0_COMMIT,
                    freeze=binding(OUT / 'stage_a/P0_FREEZE.json'), designs=list(DESIGNS),
                    methods=['B0', 'B1', 'B2', 'B3', 'P0'], primary_external_baseline='B3',
                    independent_variables=['scan architecture generator', 'P0 versus P1 after Stage A'],
                    frozen=dict(K=2, placement_seed=11, ATPG='existing FAN patterns; no regeneration',
                                technology='existing Nangate45', cycles='existing load/capture/unload serialization',
                                routing='existing route_selected adapter; GRT_SEED=11, NUM_CORES=2, /usr/bin/openroad',
                                extraction='existing OpenRCX and measurement scripts', H4='existing 4x4', H8='existing 8x8',
                                attribution='whole net capacitance at source; existing spatial coordinate system'),
                    units=dict(E='fF.transitions', H4='fF.transitions per bin/cycle', H8='fF.transitions per bin/cycle', wire='um'),
                    inputs=inputs, resources=budgets,
                    P1_budget='Same mutation/exact evaluation count per design and starts as frozen P0; record initialization/reference overhead separately',
                    selection='Deterministic predicted archive physical extreme, H8 extreme, and minimax normalized-regret balanced point; canonical SHA tie break; deduplicate; balanced is method representative',
                    pareto='Minimize implemented routed full scan-path wire upper bound, E, H8 with exact dominance; no weighted score',
                    comparable_cost='Report pairwise cost deltas and nondominance; do not invent a post-outcome matching tolerance',
                    metadata_exception='Existing Liberty test_cell-only annotation may be used by generators if necessary; original functional functions/timing/C and downstream Liberty must remain unchanged',
                    endpoint_translation='Preserve generated FF identity, membership and order; explicitly map generator endpoints to common fixed physical ports without repartitioning',
                    stage_gate='Any unreproducible baseline, FF/K/translation/workload/backend mismatch stops campaign; incomplete Stage A does not authorize P1',
                    test_quality='Report stored coverage and detected count; exact fault identity is unknown unless independent set comparison passes')
    write(OUT / 'protocol/benchmark_contract.json', contract)
    policy = OUT / 'protocol/architecture_policy.md'
    policy.write_text('# Predeclared architecture selection\n\n'
                      'B0 is the already established seed-11 K=2 contiguous supplied-order reference. '
                      'B1/B2/B3 each contribute their actual single generated solution. '
                      'No K=1 native order may be split and presented as native K=2.\n\n'
                      'P0 reuses the complete frozen candidate_stateful search archive. '
                      'For P0 and future P1, retain the minimum predicted wire point, minimum predicted H8 point, '
                      'and the point minimizing the maximum normalized regret across predicted wire, E and H8. '
                      'Regret uses each retained archive dimension’s min/max; a zero range contributes zero. '
                      'Break ties by full canonical SHA256, deduplicate, and use balanced as the method representative. '
                      'Archive membership and selection precede new routes. Preserve all archive points for a complete '
                      'predicted frontier; only implemented points can enter an implemented frontier, and unimplemented '
                      'archive points must remain explicit. PACT supplies multiple solutions; OSS methods supply one.\n\n'
                      'Stage C fixes mutation evaluations to the recorded P0 count per design, uses identical starts '
                      'and seed, and records wall time and memory. No coefficients, topology thresholds, selection policy '
                      'or budgets may be chosen using Stage-A or Stage-C H8 labels.\n')
    print('P0 frozen', P0_COMMIT, 'sources', len(production), 'diagnosis artifacts', len(diagnosis), flush=True)


def verify():
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')
    count = 0
    groups = [frozen['production_sources'], frozen['historical_evidence'], frozen['h8_diagnosis']]
    groups.extend(frozen['frozen_inputs'].values())
    for group in groups:
        for name, expected in group.items():
            if binding(expected['path'])['sha256'] != expected['sha256']:
                raise ValueError('Frozen evidence changed: ' + name)
            count += 1
    print('Frozen source/input/evidence bindings PASS:', count, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('freeze', 'verify'))
    args = parser.parse_args()
    globals()[args.stage]()
