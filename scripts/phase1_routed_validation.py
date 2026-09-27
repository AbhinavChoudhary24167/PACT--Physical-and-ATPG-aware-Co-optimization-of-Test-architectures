#!/usr/bin/env python3
"""Frozen Phase-1 experiment adapter; no optimizer invocation or modification."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact.experiment_storage import configure_experiment_storage, guard_disk_space
from pact.phase0d.campaign import atomic_write_json as write, file_sha256
from pact.phase0d.external import run_bounded, extract_structured_metrics
from pact.phase0d.funnel import FrozenProxyContext
from pact.phase0d.pareto import nondominated
from pact.physical.phase0c_congestion import parse_grt_congestion
from pact.scan.model import ScanArchitecture

REPORT = ROOT / 'reports/phase1_routed_validation'
FLOW = Path('/root/pact-deps/OpenROAD-flow-scripts/flow')
DESIGNS = ('s9234', 's15850')
METHODS = ('B0', 'P', 'A', 'J50', 'T', 'R')
BLOCK = {'s9234': 's9234f', 's15850': 's15850'}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def command(args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()

def select(rows):
    """Exact two-objective frontier (constant third coordinate reuses Pareto utility)."""
    unique = {}
    for row in rows:
        sha = row['architecture_sha256']
        if sha in unique:
            assert all(math.isclose(a, b, abs_tol=1e-9, rel_tol=0) for a, b in
                       zip(row['objectives'], unique[sha]['objectives']))
            unique[sha]['source_runs'].extend(row['source_runs'])
        else:
            unique[sha] = dict(row, source_runs=list(row['source_runs']))
    archive = nondominated(unique.values(), key=lambda r: (*r['objectives'], 0))
    archive.sort(key=lambda r: (*r['objectives'], r['architecture_sha256']))
    low = [min(r['objectives'][i] for r in archive) for i in range(2)]
    span = [max(r['objectives'][i] for r in archive) - low[i] for i in range(2)]
    for row in archive:
        row['normalized_utopia_distance_squared'] = sum(
            ((row['objectives'][i] - low[i]) / span[i]) ** 2 if span[i] else 0
            for i in range(2))
    roles = {
        'physical_extreme': min(archive, key=lambda r: (*r['objectives'], r['architecture_sha256'])),
        'balanced': min(archive, key=lambda r: (r['normalized_utopia_distance_squared'],
                                              *r['objectives'], r['architecture_sha256'])),
        'activity_extreme': min(archive, key=lambda r: (r['objectives'][1], r['objectives'][0],
                                                     r['architecture_sha256'])),
    }
    selected = []
    for row in archive:
        selected_roles = [role for role, item in roles.items() if item is row]
        if selected_roles:
            selected.append(dict(row, selection_roles=selected_roles,
                                 rationale='Exact objective extremes or minimum squared normalized utopia distance; ties: physical, activity, SHA256.'))
    return archive, selected

def freeze(paths):
    if (REPORT / 'freeze.json').exists():
        raise RuntimeError('Experiment already frozen; refusing reselection')
    REPORT.mkdir(parents=True, exist_ok=True)
    campaign_path = ROOT / 'reports/optimizer_v2_3/campaign.json'
    campaign = read(campaign_path)
    assert campaign['classification'] == 'PACT_V2_3_PARALLEL_PARETO_ADVANCE'
    hashes = {}
    def record(path):
        path = Path(path)
        hashes[str(path)] = file_sha256(path)
    record(campaign_path)
    env = {'openroad': command(['openroad', '-version']),
           'orfs_commit': command(['git', 'rev-parse', 'HEAD'], FLOW.parent),
           'orfs_status': command(['git', 'status', '--short'], FLOW.parent),
           'uname': command(['uname', '-a']), 'python': sys.version,
           'git_commit': command(['git', 'rev-parse', 'HEAD']),
           'git_status_before': (REPORT / 'git_status_before.txt').read_text(encoding='utf-8-sig'),
           'storage': str(paths.root), 'disk': guard_disk_space(paths, estimated_bytes=2 * 1024**3)}
    assert env['openroad'].startswith('26Q2-1164-g08f67ee5ec')
    assert env['orfs_commit'] == '5e8b1450d19263f797a27c4f371b9dd19f32a3aa'
    assert not env['orfs_status']
    for relative in ('scripts/phase0c_rewire_odb.py', 'scripts/phase0d_run_route.py',
                     'scripts/phase0d_verify_routed.py', 'src/pact/physical/phase0d_routed.py',
                     'src/pact/phase0d/external.py', 'src/pact/analysis/phase0c_activity.py',
                     'src/pact/physical/phase0c_scan_geometry.py', 'src/pact/physical/phase0c_port_policy.py',
                     'config/phase0d_pilot_contract.json', 'config/phase0c_campaign.json',
                     'docs/PACT_PHASE0C_POWER_PROXY.md', 'reports/PACT_PHASE0C_REPORT.md',
                     'reports/phase0d/routed_pareto_qualification/routed_pareto_metrics.json'):
        record(ROOT / relative)
    selections, archives, baselines, quality = {}, {}, {}, {}
    for design in DESIGNS:
        context = FrozenProxyContext.load(ROOT, design, 11, 2)
        for rel in context.input_sha256:
            record(ROOT / rel)
        rows = []
        for mode in ('equal_evaluations', 'equal_wall'):
            for workers in (1, 2, 4):
                run = paths.results / 'optimizer_v2_3' / design / mode / f'w{workers}'
                result = read(run / 'result.json')
                assert result == campaign['designs'][design][mode][str(workers)]
                record(run / 'result.json')
                for row in result['archive']:
                    arch_path = run / 'architectures' / (row['architecture_sha256'] + '.architecture.json')
                    arch = ScanArchitecture.from_json(arch_path)
                    assert arch.sha256() == row['architecture_sha256']
                    record(arch_path)
                    rows.append(dict(row, source_runs=[str(run)], source_architecture=str(arch_path)))
        archives[design], selections[design] = select(rows)
        base = FLOW / f'results/nangate45/{BLOCK[design]}/phase0b_s11_B0'
        for name in ('3_place.odb', '3_place.sdc'):
            record(base / name)
        config = ROOT / ('experiments/phase0b/s15850_orfs/config.mk' if design == 's15850'
                         else 'experiments/phase0/s9234_orfs/config.mk')
        record(config)
        record(config.parent / 'constraint.sdc')
        # Replay only baseline materialization, not routing. Byte identity proves source compatibility.
        baseline_replay = paths.results / 'phase1_routed_validation' / design / 'baseline_compatibility'
        replay_odb = baseline_replay / 'P.odb'
        p_arch = ROOT / f'artifacts/derived/phase0c/{design}/s11/k2/P.architecture.json'
        execution = run_bounded(['openroad', '-python', '-no_init', '-exit',
            str(ROOT / 'scripts/phase0c_rewire_odb.py'), '--source', str(base / '3_place.odb'),
            '--architecture', str(p_arch), '--output', str(replay_odb)],
            baseline_replay, ROOT, 120, [replay_odb])
        old_rewire = read(ROOT / f'artifacts/raw/phase0c/physical/{design}/s11/k2/P/rewire/execution.json')
        assert execution['exit_code'] == 0
        expected = next(iter(old_rewire['outputs'].values()))
        assert file_sha256(replay_odb) == expected, 'Source placement materialization differs from qualified baseline'
        baselines[design] = []
        for method in METHODS:
            root = ROOT / f'artifacts/raw/phase0c/physical/{design}/s11/k2/{method}'
            route = read(root / 'route_metrics.json')
            arch_path = ROOT / f'artifacts/derived/phase0c/{design}/s11/k2/{method}.architecture.json'
            proxy_path = arch_path.with_name(f'{method}.proxy.json')
            proxy = read(proxy_path)
            arch = ScanArchitecture.from_json(arch_path)
            assert route['status'] == 'QUALIFIED' and route['DRC_errors'] == 0
            assert route['architecture_sha256'] == proxy['architecture_sha256'] == arch.sha256()
            assert route['rewire_script_sha256'] == file_sha256(ROOT / 'scripts/phase0c_rewire_odb.py')
            assert route['physical_seed'] == 11 and route['K'] == 2
            archive = root / '5_2_route.odb.gz'
            assert file_sha256(archive) == route['routed_odb_gzip_sha256']
            with gzip.open(archive, 'rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            assert digest == route['routed_odb_sha256']
            proof = read(root / 'routed_verification.json')
            assert proof['status'] == 'PASS' and proof['scan_edges'] == len(arch.cells) - 2
            for path in (arch_path, proxy_path, root / 'route_metrics.json', root / 'routed_verification.json',
                         root / 'route/execution.json', root / 'rewire/execution.json', archive,
                         root / '5_1_grt.json', root / '5_2_route.json'):
                record(path)
            baselines[design].append({'method': method, 'architecture_sha256': arch.sha256(),
                'proxy_path': str(proxy_path), 'route_path': str(root / 'route_metrics.json'),
                'reused': True, 'objectives': [proxy['scan_geometry']['total_scan_hpwl_um'],
                                             proxy['activity']['grids']['8']['H_eff']]})
        quality[design] = {'pattern_count': len(context.patterns), 'FF_count': len(context.start_architecture.cells),
            'stuck_at_coverage_percent': {'s9234': 94.14, 's15850': 94.62}[design],
            'coverage_semantics': 'Frozen FAN combinational stuck-at coverage inherited by exact PPI reconstruction; no new fault simulation.',
            'baseline_materialization_sha256': expected, 'baseline_materialization_byte_identical': True}
        record(ROOT / f'artifacts/raw/tool_qualification/fan_atpg/{design}.atpg.log')
    write(REPORT / 'environment.json', env)
    write(REPORT / 'global_archives.json', archives)
    write(REPORT / 'selected_candidates.json', selections)
    write(REPORT / 'baselines.json', baselines)
    write(REPORT / 'test_quality_reference.json', quality)
    write(REPORT / 'provenance.json', hashes)
    contract = '''# Phase-1 frozen experimental contract

Frozen before any new routing. Designs s9234 and s15850; physical seed 11; K=2.
s5378 is reference evidence only and must not be rerouted. Optimizer-v2.3 is unchanged.

Selection population: union of final retained architectures from all six qualified
v2.3 runs per design (equal evaluations and equal wall, W=1/2/4). Deduplicate by
canonical SHA256, then exact nondominance on authoritative physical proxy and H_eff8.
Physical extreme minimizes (physical,H,hash); activity extreme minimizes (H,physical,hash).
Balanced minimizes sum_i ((f_i-min_i)/(max_i-min_i))^2 over that global frontier;
zero ranges contribute zero; ties use (physical,H,hash). Overlapping roles share a
route; never substitute another point. No routed result enters selection.

Physical proxy: existing fixed FF-origin Manhattan scan-path cost, including fixed
SI/SO links. H_eff8: frozen 8x8 bin direct-sink-weighted toggle field, fixed 3x3
1/(1+Manhattan distance) kernel, peak over bins and fully clocked parallel shift
cycles. Existing FAN PPI vectors, carry-loaded/no-capture semantics, placed DEF/V,
identity mapping, weights and definitions are hash-frozen in provenance.json.
No ATPG, placement, activity database, baseline campaign, or optimizer regeneration.

Flow: qualified Nangate45 ORFS 5e8b1450d19263f797a27c4f371b9dd19f32a3aa;
OpenROAD 26Q2-1164-g08f67ee5ec in Ubuntu-24.04 WSL. Same design configs and SDCs,
seed-11 B0 3_place.odb/sdc, phase0c_rewire_odb.py, make route GRT_SEED=11,
OPENROAD_EXE=/usr/bin/openroad, YOSYS_EXE=/usr/bin/yosys. Only output locations
and variant names differ. WORK_HOME and all large/transient data use D:/PACT_EXPERIMENTS.
600-second route timeout, 120-second rewire, 90-second verification. One route
attempt per selected architecture, at most three per design, SIX total; ZERO new
baseline routes because all six compatible methods exist. Failures stay visible.

Baselines: all qualified seed-11 K=2 B0/P/A/J50/T/R routes, reused after archive
hash and structural proof checks; current P materialization must reproduce the
historical ODB hash. B0 is conventional supplied order; P physical; A activity;
J50 joint; T long-edge-risk; R randomized. B1 native is K=1 and excluded.

Primary routed objective: existing routed_full_scan_path_net_length_upper_bound_um,
paired with authoritative pre-route H_eff8. It includes shared functional branches
and may count shared net lengths per link; it is not exclusive scan wirelength.
Exact scan-only cost is reported only if available. Full-design detailed wirelength,
DRC, vias, existing congestion, timing and reported area are descriptive metrics.
Timing is GLOBAL-ROUTE timing as in the qualified flow, not signoff detailed-route STA.

Test quality: frozen coverage/pattern counts, FF bijection, K=2, minimum length 8,
maximum chain difference 2, exact parallel load/unload reconstruction and frozen
architecture identity; verify all routed scan links through transparent buffers.
Re-evaluation of selected immutable architectures is verification, never search.

Pareto survival requires a qualified PACT point nondominated against ALL compatible
baselines and not simply equal to an existing baseline objective pair. Use exact
two-objective dominance, with no weighted score. Report pairwise rank concordance
and inversions between proxy and routed path cost. Balanced usefulness requires a
distinct routed nondominated point representing a tradeoff against at least one
extreme; report otherwise. No minimum effect threshold is invented after results.

CONFIRMED requires sufficient valid comparisons, preserved test quality and routed
nondominated improvement/tradeoff on BOTH new designs. MIXED: only one supports it.
ADVANTAGE_NOT_REPLICATED: neither supports it with sufficient valid evidence.
INCOMPLETE: insufficient implementation evidence (including any missing selected
route or structural/test-quality failure). Full classification prefix is
PACT_PHASE1_MULTI_DESIGN_ROUTED_VALIDATION_ except the negative label, which is
PACT_PHASE1_MULTI_DESIGN_ROUTED_ADVANTAGE_NOT_REPLICATED.
No universal generalization, measured-power or IR-drop claim follows.
'''
    (REPORT / 'EXPERIMENT_CONTRACT.md').write_text(contract, encoding='utf-8')
    freeze_hashes = {p.name: file_sha256(p) for p in REPORT.iterdir() if p.is_file()}
    write(REPORT / 'freeze.json', {'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'files': freeze_hashes, 'maximum_new_routes': 6})
    print(json.dumps({d: [(r['selection_roles'], r['architecture_sha256'], r['objectives'])
                         for r in selections[d]] for d in DESIGNS}), flush=True)

def route(paths):
    frozen = read(REPORT / 'freeze.json')
    for name, sha in frozen['files'].items():
        assert file_sha256(REPORT / name) == sha, f'Frozen file changed: {name}'
    for path, sha in read(REPORT / 'provenance.json').items():
        assert file_sha256(Path(path)) == sha, f'Evidence changed: {path}'
    selections = read(REPORT / 'selected_candidates.json')
    assert sum(map(len, selections.values())) <= 6
    work = paths.results / 'phase1_routed_validation'
    for design in DESIGNS:
        context = FrozenProxyContext.load(ROOT, design, 11, 2)
        for selected in selections[design]:
            sha = selected['architecture_sha256']
            evidence = work / design / sha
            result_path = evidence / 'route_result.json'
            if result_path.exists():
                print(f'Reusing recorded attempt {design} {sha[:12]}', flush=True)
                continue
            guard_disk_space(paths, estimated_bytes=1024**3)
            architecture = ScanArchitecture.from_json(Path(selected['source_architecture']))
            context.evaluate(architecture, {'type': 'phase1_frozen_verification'}, work / design / 'candidates')
            candidate = work / design / 'candidates' / sha
            proxy = read(candidate / 'proxy.json')
            observed = [proxy['scan_geometry']['total_scan_hpwl_um'], proxy['activity']['grids']['8']['H_eff']]
            assert all(math.isclose(a, b, abs_tol=1e-8, rel_tol=0) for a, b in zip(observed, selected['objectives']))
            variant_name = 'phase1_s11_k2_' + sha[:12]
            variant = work / 'orfs/results/nangate45' / BLOCK[design] / variant_name
            logs = work / 'orfs/logs/nangate45' / BLOCK[design] / variant_name
            variant.mkdir(parents=True, exist_ok=True)
            base = FLOW / f'results/nangate45/{BLOCK[design]}/phase0b_s11_B0'
            arch_path = candidate / 'architecture.json'
            result = {'design': design, 'architecture_sha256': sha, 'selection_roles': selected['selection_roles'],
                      'candidate_directory': str(candidate), 'objectives': observed, 'status': 'FAILED',
                      'contract_sha256': file_sha256(REPORT / 'EXPERIMENT_CONTRACT.md')}
            rewire = run_bounded(['openroad', '-python', '-no_init', '-exit',
                str(ROOT / 'scripts/phase0c_rewire_odb.py'), '--source', str(base / '3_place.odb'),
                '--architecture', str(arch_path), '--output', str(variant / '3_place.odb')],
                evidence / 'rewire', ROOT, 120, [variant / '3_place.odb'])
            if rewire['exit_code'] != 0:
                write(result_path, dict(result, stage='REWIRE')); continue
            shutil.copy2(base / '3_place.sdc', variant / '3_place.sdc')
            config = ROOT / ('experiments/phase0b/s15850_orfs/config.mk' if design == 's15850'
                             else 'experiments/phase0/s9234_orfs/config.mk')
            # Ledger is written before launch: interrupted/failed routes cannot silently retry.
            ledger = work / 'route_attempts.json'
            attempts = read(ledger) if ledger.exists() else []
            assert sha not in [a['architecture_sha256'] for a in attempts], 'Attempt already consumed'
            assert len(attempts) < 6
            attempts.append({'design': design, 'architecture_sha256': sha,
                             'launch_utc': datetime.now(timezone.utc).isoformat()})
            write(ledger, attempts)
            print(f'ROUTE {len(attempts)}/6 {design} {selected["selection_roles"]} {sha[:12]}', flush=True)
            required = [logs / '5_1_grt.json', logs / '5_2_route.json', variant / '5_2_route.odb']
            execution = run_bounded(['make', '-o', str(variant / '3_place.odb'), '-o', str(variant / '3_place.sdc'),
                f'DESIGN_CONFIG={config}', f'FLOW_VARIANT={variant_name}', f'WORK_HOME={work / "orfs"}',
                'GRT_SEED=11', 'OPENROAD_EXE=/usr/bin/openroad', 'YOSYS_EXE=/usr/bin/yosys', 'route'],
                evidence / 'route', FLOW, 600, required, resume=False)
            result.update(route_execution=execution, rewire_execution=rewire)
            if execution['exit_code'] != 0 or not execution['required_outputs_present']:
                write(result_path, dict(result, stage='ROUTE')); continue
            for source in required[:2]:
                shutil.copy2(source, evidence / source.name)
            metrics = extract_structured_metrics(read(required[0]), read(required[1]))
            congestion = parse_grt_congestion((evidence / 'route/stdout.log').read_text(errors='replace'))
            metrics['congestion'] = congestion
            if congestion:
                metrics['global_route_overflow'] = congestion['total']['total_overflow']
            # Area is already emitted by the qualified flow; retain its original stage/key.
            metrics['reported_area'] = {k: v for k, v in read(required[0]).items() if k.endswith('__design__instance__area')}
            verify_path = evidence / 'routed_verification.json'
            verification = run_bounded(['openroad', '-python', '-no_init', '-exit',
                str(ROOT / 'scripts/phase0d_verify_routed.py'), '--routed', str(required[2]),
                '--architecture', str(arch_path), '--frozen-def', str(context.frozen_def),
                '--output', str(verify_path)], evidence / 'postroute_verify', ROOT, 90, [verify_path])
            proof = read(verify_path) if verify_path.exists() else {}
            qualified = verification['exit_code'] == 0 and proof.get('status') == 'PASS' and metrics['detailed_route_drc_errors'] == 0
            archive = evidence / '5_2_route.odb.gz'
            with required[2].open('rb') as src, archive.open('wb') as out:
                with gzip.GzipFile(filename='', fileobj=out, mode='wb', mtime=0) as dst:
                    shutil.copyfileobj(src, dst)
            result.update(status='QUALIFIED' if qualified else 'POSTROUTE_FAILED', structured_metrics=metrics,
                postroute_verification=proof, verification_execution=verification,
                routed_full_scan_path_net_length_upper_bound_um=proof.get('routed_full_scan_path_net_length_upper_bound_um'),
                exact_scan_only_routed_length_um=proof.get('exact_scan_only_total_um'),
                routed_odb_sha256=file_sha256(required[2]), routed_odb_gzip_sha256=file_sha256(archive),
                architecture_materialized_sha256=ScanArchitecture.from_json(arch_path).sha256())
            write(result_path, result)
            print(f'{design} {sha[:12]} {result["status"]}', flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('freeze', 'route'))
    args = parser.parse_args()
    paths = configure_experiment_storage()
    {'freeze': freeze, 'route': route}[args.stage](paths)

if __name__ == '__main__':
    main()
