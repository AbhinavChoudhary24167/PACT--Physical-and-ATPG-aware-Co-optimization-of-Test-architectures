#!/usr/bin/env python3
"""Freeze existing qualified evidence before independent activity measurement."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact.scan.model import ScanArchitecture
from pact.test.pattern_parser import parse_fan_pat, map_ppi_patterns
from pact.phase0d.campaign import file_sha256, atomic_write_json as write
from pact.experiment_storage import configure_experiment_storage, guard_disk_space

REPORT = ROOT / 'reports/phase2a_shift_activity'
def read(p):
    return json.loads(Path(p).read_text())

def freeze():
    assert not (REPORT / 'freeze.json').exists(), 'Refusing to replace frozen selection'
    paths = configure_experiment_storage()
    guard_disk_space(paths, estimated_bytes=200 * 1024**2)
    REPORT.mkdir(parents=True, exist_ok=True)
    hashes = {}
    def record(p):
        p = Path(p)
        hashes[str(p)] = file_sha256(p)
    rows = []
    quality = {}
    def add(design, label, arch_path, proxy_path, route_path, group):
        arch_path, proxy_path, route_path = map(Path, (arch_path, proxy_path, route_path))
        arch, proxy, route = ScanArchitecture.from_json(arch_path), read(proxy_path), read(route_path)
        assert route['status'] == 'QUALIFIED'
        assert arch.sha256() == proxy['architecture_sha256'] == route['architecture_sha256']
        assert route.get('K', 2) == 2 and route.get('physical_seed', 11) == 11
        proof_path = route_path.parent / 'routed_verification.json'
        proof = read(proof_path)
        assert proof['status'] == 'PASS' and proof['scan_ff_count'] == len(arch.cells)
        archive = route_path.parent / '5_2_route.odb.gz'
        assert file_sha256(archive) == route['routed_odb_gzip_sha256']
        with gzip.open(archive, 'rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == route['routed_odb_sha256']
        for p in (arch_path, proxy_path, route_path, proof_path, archive):
            record(p)
        for rel, expected in proxy.get('input_sha256', {}).items():
            p = ROOT / rel
            assert file_sha256(p) == expected, f'Prior input changed: {p}'
            record(p)
        rows.append(dict(design=design, label=label, group=group,
            architecture_path=str(arch_path), proxy_path=str(proxy_path), route_path=str(route_path),
            proof_path=str(proof_path), odb_archive=str(archive), odb_sha256=route['routed_odb_sha256'],
            architecture_sha256=arch.sha256(), H_eff8=proxy['activity']['grids']['8']['H_eff']))

    for design in ('s5378', 's9234', 's15850'):
        base = ROOT / f'artifacts/derived/phase0c/{design}/s11/k2'
        for method in ('P', 'A', 'J50', 'T'):
            add(design, method, base / f'{method}.architecture.json', base / f'{method}.proxy.json',
                ROOT / f'artifacts/raw/phase0c/physical/{design}/s11/k2/{method}/route_metrics.json', 'baseline')
        pattern = ROOT / f'artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat'
        identity = ROOT / f'artifacts/derived/{design}/ff_identity_map.json'
        placed = ROOT / f'artifacts/raw/phase0b/placements/{design}/s11/placed.def'
        mapped = map_ppi_patterns(parse_fan_pat(pattern), read(identity)['records'])
        text = placed.read_text()
        units = int(re.search(r'UNITS DISTANCE MICRONS (\d+)', text)[1])
        die = [int(v)/units for v in re.search(r'DIEAREA\s*\(\s*(\d+)\s+(\d+)\s*\)\s*\(\s*(\d+)\s+(\d+)', text).groups()]
        # Coverage is read from the archived FAN statistics, never rerun.
        stats = ROOT / f'artifacts/raw/tool_qualification/fan_atpg/rpt/{design}_fsim.rpt'
        if not stats.exists():
            stats = ROOT / f'artifacts/raw/tool_qualification/fan_atpg/reports/{design}_fsim.rpt'
        coverage_sources = list((ROOT / 'artifacts/raw/tool_qualification/fan_atpg').rglob(f'{design}*rpt'))
        coverage = None
        for p in coverage_sources:
            source = p.read_text()
            m = re.search(r'fault coverage\s*[:=]?\s*([\d.]+)', source, re.I)
            if m:
                coverage = float(m[1]); stats = p; break
        assert coverage is not None, (design, coverage_sources)
        quality[design] = dict(pattern_path=str(pattern), identity_path=str(identity),
            placed_def=str(placed), pattern_count=len(mapped), FF_count=len(mapped[0]),
            stuck_at_coverage_percent=coverage, coverage_source=str(stats), die_bounds_um=die)
        for p in (pattern, identity, placed, stats): record(p)
    old = ROOT / 'reports/phase0d/routed_pareto_qualification/provenance.json'
    record(old)
    for c in read(old)['candidates']:
        add('s5378', c['architecture_sha256'][:12], ROOT / c['architecture_path'],
            ROOT / c['proxy_path'], ROOT / c['route_result'], 'PACT_phase0d')
    selected = ROOT / 'reports/phase1_routed_validation/selected_candidates.json'
    record(selected)
    for design, candidates in read(selected).items():
        for c in candidates:
            role = next((r for r in ('balanced', 'activity_extreme') if r in c['selection_roles']), None)
            if role:
                work = paths.results / 'phase1_routed_validation' / design
                sha = c['architecture_sha256']
                add(design, role, work / 'candidates' / sha / 'architecture.json',
                    work / 'candidates' / sha / 'proxy.json', work / sha / 'route_result.json', 'PACT_v2.3')
    for relative in ('reports/phase1_routed_validation/freeze.json',
                     'reports/phase1_routed_validation/routed_results.json',
                     'reports/optimizer_v2_3/campaign.json',
                     'reports/phase0d/routed_pareto_qualification/routed_pareto_metrics.json',
                     'src/pact/scan/model.py', 'src/pact/scan/phase0c.py',
                     'src/pact/scan/phase0d_operators.py', 'src/pact/test/pattern_parser.py',
                     'src/pact/physical/phase0d_routed.py', 'src/pact/phase0d/optimizer_v2_3.py',
                     'scripts/phase2a_freeze.py'):
        record(ROOT / relative)
    write(REPORT / 'architecture_set.json', rows)
    write(REPORT / 'test_quality.json', quality)
    write(REPORT / 'provenance.json', hashes)
    contract = '''# Phase-2A experiment contract

Frozen before new activity measurement. Question: across frozen s5378, s9234 and
s15850 architectures, does H_eff8 correctly rank or track independently reconstructed
and physically weighted post-route scan-shift switching behavior?

Seed 11, K=2; all input hashes, architecture hashes, H_eff8, pattern counts and
archived stuck-at coverage are in architecture_set.json, test_quality.json and
provenance.json. No optimization, ATPG generation, placement or route runs.
Use P/A/J50/T plus already-selected Phase-1 balanced/activity_extreme for s9234
and s15850. For s5378 include all FIVE previously qualified Phase-0D candidates,
including dominated ones, with original hash labels; no retrospective balanced
label is invented. B0/R and physical_extreme are omitted to retain the requested
focused comparison. Architecture set is immutable after measurement.

Reuse FAN parser/PPI bijection and parallel_schedule, and check against
verify_parallel_schedule for EVERY pattern with carried state and scan-out.
Start all FF states at zero; load reverse target order, shorter chain gets leading
zero padding but all FFs clock on every cycle. Carry loaded state, no capture,
no extra final unload. Record padding and first-L scan-out versus padding tail.
Do not call H_eff8/activity implementation, its weights or spatial kernel.

Physical hierarchy: use qualified extracted capacitance if present. Preliminary
inventory finds no SPEF under existing Phase-1 or ORFS Nangate45 results. Inspect
ODB RSeg/CapNode evidence too. Without qualified parasitics, the preregistered
fallback is SUM(toggle_FF * routed wire length of all unique nets driven by its
Q or QN, through BUF/CLKBUF/INV branches). Include whole actual net trees and
functional sinks, not Q-to-SI distance. Stop at nontransparent logic; do not
infer internal combinational activity. Count shared nets once; reject competing
FF owners, missing routed wires, changed coordinates/inventory, or failed scan
proofs. QN inversion preserves transition counts. Audit source pins and fanout.
No pin capacitance, layer-dependent capacitance, vias, buffer internal energy,
clock/SE/PI driven nets or coupling energy is represented by this fallback.
Call its unit micrometre-transitions, NEVER energy or power. Physical ENERGY
portion remains incomplete without qualified electrical extraction.

Spatial rule: fixed 10x10 equal bins over each frozen DEF DIEAREA, lower-inclusive
boundaries (outer maximum clamped). Assign FF-driven load to the routed FF origin,
not routed segment locations. Per cycle calculate raw and wire-weighted bin sums;
local activity is every wholly-contained 2x2 adjacent-bin sum (81 windows), equal
weights, no convolution, occupancy or fanout normalization. Peak over all cycles
and bins/windows. This localizes drivers, not distributed wire dissipation.
Report total/mean/peak/p95 cycle activity, raw and weighted spatial peaks.

Statistical plan: within-design Spearman (average tied ranks), Kendall tau-b,
secondary Pearson, and exact ascending rankings, for raw total/peak, weighted
total/peak, raw/weighted bin and 2x2 local peaks. H values rounded to 9 decimal
places solely to avoid floating point false tie distinctions. Exact two-sided
Spearman permutation p-values over all architecture-label permutations per design
are descriptive (selected architectures are not independent random samples;
multiple endpoints, no confirmatory significance claim). Pooled coefficients
use within-design mean-normalized quantities ONLY, with equal design weight;
also report pooled within-design ranks. No raw physical-scale pooling.

Pairs: s9234 T/balanced, J50/activity_extreme, A/activity_extreme;
s15850 T/balanced, J50/balanced, A/activity_extreme; s5378 P/75ea663523d9,
T/75ea663523d9, J50/1f1a3a458946, A/1f1a3a458946. Delta=PACT-baseline;
ties explicitly distinguished from correct/incorrect direction.

Classification rule before measurement: strong confirmation requires correctness,
independent physical weights, Spearman >=0.7 for weighted total AND local peak in
every design, and correct direction in every preregistered pair for both endpoints.
Failure if weighted total AND local peak have nonpositive Spearman in all three
designs. Otherwise partial/design-dependent evidence, with negative endpoints
explicitly reported. These descriptive thresholds do not imply significance.
No objective or architecture tuning follows a failed result.

Large/transient artifacts, cycle traces and extracted net inventories live only
under D:/PACT_EXPERIMENTS/results/phase2a_shift_activity. Compact reports in repo.
Focused correctness tests first, full repository regression after implementation.
'''
    (REPORT / 'EXPERIMENT_CONTRACT.md').write_text(contract)
    write(REPORT / 'freeze.json', dict(frozen_utc=datetime.now(timezone.utc).isoformat(),
        physical_seed=11, K=2, new_optimization_runs=0, new_routes=0,
        files={p.name:file_sha256(p) for p in REPORT.iterdir() if p.is_file()}))
    print(json.dumps({'architectures':len(rows), 'quality':quality}, indent=2))

if __name__ == '__main__': freeze()
