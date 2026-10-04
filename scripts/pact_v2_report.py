"""Evidence-only comparison of new implementations with stored baselines."""
from pact.environment import python_executable
import csv
import gzip
from pathlib import Path
import shutil
import numpy as np
from pact_v2 import ROOT, DESIGNS, read, write_json, binding, METRICS
from pact.optimizer.search import dominates

PHYSICAL = ('routed_path_upper_bound_um', 'cap_weighted_ff_transitions', 'peak_local_cap_ff')


def measurement(folder, route):
    data = read(folder/'activity_summary.json')
    s = data['scopes']['all_data']
    g = s['grids']['8']
    timing = route['structured_metrics']
    return dict(total_transitions=s['transitions']['total'], peak_transitions=s['transitions']['maximum'],
        cap_weighted_ff_transitions=s['cap_weighted_ff_transitions']['total'],
        peak_cap_ff=s['cap_weighted_ff_transitions']['maximum'],
        peak_local=g['peak_per_cycle']['maximum'], peak_local_cap_ff=g['cap_peak_per_cycle']['maximum'],
        peak_local_4=s['grids']['4']['peak_per_cycle']['maximum'],
        peak_local_cap_4_ff=s['grids']['4']['cap_peak_per_cycle']['maximum'],
        routed_path_upper_bound_um=route['routed_full_scan_path_net_length_upper_bound_um'],
        setup_wns_ns=timing['setup_wns_ns'], hold_wns_ns=timing['hold_wns_ns'],
        timing_stage=timing.get('timing_stage', 'global_route'), DRC=route['DRC_errors'])


def report(out):
    historical = list(csv.DictReader((ROOT/'reports/physical_effect/comparison.csv').open()))
    manifest = read(ROOT/'reports/physical_effect/manifest.json')
    rows, designs = [], {}
    for design, start in DESIGNS.items():
        folder = out/design
        if not (folder/'search.json').exists():
            continue
        result = read(folder/'search.json')
        inputs = read(folder/'inputs.json')
        baseline_scores = {r['label']: r for r in result['baselines']}
        for old in [r for r in historical if r['design'] == design]:
            role = old['architecture']
            entry = next(r for r in manifest['rows'] if r['design'] == design and r['role'] == role)
            route = read(entry['qualification']['path'])
            measured = measurement(ROOT/'reports/physical_effect'/design/role, route)
            rows.append(dict(design=design, architecture=role, architecture_sha256=entry['architecture_sha256'],
                             new=False, status='QUALIFIED', selected_roles=[],
                             predicted=baseline_scores[role]['metrics'], measured=measured))
        for candidate in result['archive']:
            if not candidate['new']:
                continue
            sha = candidate['architecture_sha256']
            row = dict(design=design, architecture=sha[:12], architecture_sha256=sha,
                       new=True, status='PREDICTED_ONLY', selected_roles=candidate['selected_roles'],
                       provenance=candidate['label'], predicted=candidate['metrics'], measured=None)
            route_path = out/'routes'/design/sha/'route_result.json'
            if route_path.exists():
                route = read(route_path)
                row['status'] = route['status']
                row['route'] = binding(route_path)
                mp = out/'measurement'/design/sha[:12]
                if (mp/'activity_summary.json').exists():
                    row['measured'] = measurement(mp, route)
                    row['measurement'] = binding(mp/'activity_summary.json')
                    row['checks'] = {name: read(mp/(name+'.json'))['status'] for name in
                                     ('FF_transition_crosscheck', 'topology_verification', 'functional_verification')}
            rows.append(row)
        designs[design] = {k: result[k] for k in ('evaluations', 'new_unique', 'accepted', 'runtime_seconds',
            'initialization_seconds', 'search_seconds', 'wire_ceiling_um', 'timing_ceiling_um', 'config')}
        designs[design].update(parent_commit=inputs['parent_commit'], inputs=inputs['inputs'],
                              versions=inputs['versions'], chain_lengths=inputs['chain_lengths'],
                              selected=[r['architecture_sha256'] for r in result['selected']])
        # Lossless compact record of every mutation; full CSV also remains local.
        with (folder/'evaluations.csv').open('rb') as src, gzip.GzipFile(filename=str(folder/'evaluations.csv.gz'), mode='wb', mtime=0) as dst:
            shutil.copyfileobj(src, dst)
        designs[design]['evaluation_log'] = binding(folder/'evaluations.csv.gz')
    qualified = [r for r in rows if r['status'] == 'QUALIFIED' and r['measured'] and
                 r['measured']['DRC'] == 0 and r['measured']['setup_wns_ns'] >= 0 and r['measured']['hold_wns_ns'] >= 0]
    for row in rows:
        if row not in qualified:
            row['nondominated'] = None
            continue
        same = [r for r in qualified if r['design'] == row['design'] and r is not row]
        value = np.array([row['measured'][k] for k in PHYSICAL])
        row['dominated_by'] = [r['architecture'] for r in same if dominates(np.array([r['measured'][k] for k in PHYSICAL]), value)]
        row['nondominated'] = not row['dominated_by']
        row['equivalent_to_baseline'] = any(not r['new'] and np.allclose(value, [r['measured'][k] for k in PHYSICAL], rtol=1e-9, atol=1e-8) for r in same)
        row['delta_percent'] = {}
        for role in (DESIGNS[row['design']], 'J50', 'PACT'):
            base = next(r for r in same+[row] if not r['new'] and r['architecture'] == role)
            row['delta_percent'][role] = {k: 100*(row['measured'][k]/base['measured'][k]-1)
                for k in (*PHYSICAL, 'total_transitions', 'peak_transitions', 'peak_local', 'peak_local_cap_4_ff')}
    new = [r for r in rows if r['new'] and r['selected_roles']]
    found = [r for r in new if r['nondominated'] and not r.get('equivalent_to_baseline')]
    complete = len(designs) == len(DESIGNS) and all(designs[d]['selected'] for d in designs) and all(r in qualified for r in new)
    classification = ('PACT_V2_NEW_PARETO_ARCHITECTURE_FOUND' if found else 'PACT_V2_IMPLEMENTED_NO_PARETO_ADVANCE') if complete else 'PACT_V2_PHYSICAL_EVALUATION_INCOMPLETE'
    summary = dict(schema='pact_implementation_aware_v2', classification=classification,
                   measured_frontier_objectives=list(PHYSICAL), designs=designs, candidates=rows,
                   new_architectures_evaluated=sum(d['new_unique'] for d in designs.values()),
                   physically_selected=len(new), physically_measured=sum(bool(r['measured']) for r in new),
                   new_nondominated=[dict(design=r['design'], architecture=r['architecture']) for r in found])
    write_json(out/'summary.json', summary)
    # All unique generated candidates, including those rejected during search.
    fields = ['design', 'architecture_id', 'architecture_sha256', 'provenance', 'evaluation', 'legal', 'feasible',
              'chain_lengths', 'selected_roles', *METRICS, *PHYSICAL, 'total_transitions', 'peak_transitions',
              'peak_local', 'peak_local_cap_4_ff', 'setup_wns_ns', 'hold_wns_ns', 'DRC', 'status', 'nondominated']
    with (out/'comparison.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for design in designs:
            result = read(out/design/'search.json')
            by_order = {r['order_id']: r for r in result['archive']+result['baselines']}
            seen = set()
            for ev in csv.DictReader((out/design/'evaluations.csv').open()):
                oid = ev['order_id']
                if oid in seen:
                    continue
                seen.add(oid)
                candidate = by_order.get(oid, {})
                final = next((r for r in rows if r['architecture_sha256'] == candidate.get('architecture_sha256')), None)
                w.writerow(dict(ev, design=design, architecture_id=oid,
                    architecture_sha256=candidate.get('architecture_sha256', ''),
                    chain_lengths='/'.join(map(str, designs[design]['chain_lengths'])),
                    selected_roles='/'.join(candidate.get('selected_roles', [])),
                    status=final['status'] if final else 'SEARCH_EVALUATED', nondominated=final['nondominated'] if final else '',
                    **((final['measured'] or {}) if final else {})))
        for row in rows:
            if row['new']:
                continue
            w.writerow(dict(design=row['design'], architecture_id=row['architecture'],
                architecture_sha256=row['architecture_sha256'], provenance='stored_baseline', legal=True,
                status=row['status'], nondominated=row['nondominated'], **row['predicted'], **row['measured']))
    table = ['| Design | Architecture / selection | Wire estimate µm | FF weighted total | FF H8 | Max edge µm |',
             '|---|---|---:|---:|---:|---:|']
    measured = ['| Design | Architecture | Transitions | Peak/cycle | C·N total | Local peak | H8 C·N | H4 C·N | Route µm | Setup / hold ns | Nondominated |',
                '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for row in [r for r in rows if not r['new'] or r['selected_roles']]:
        p = row['predicted']
        table.append(f"| {row['design']} | {row['architecture']} {'/'.join(row['selected_roles'])} | {p[METRICS[0]]:.3f} | {p[METRICS[1]]:.3f} | {p[METRICS[2]]:.5f} | {p[METRICS[3]]:.3f} |")
        if row['measured']:
            m = row['measured']
            measured.append(f"| {row['design']} | {row['architecture']} | {m['total_transitions']:.0f} | {m['peak_transitions']:.0f} | {m[PHYSICAL[1]]:.3f} | {m['peak_local']:.0f} | {m[PHYSICAL[2]]:.5f} | {m['peak_local_cap_4_ff']:.5f} | {m[PHYSICAL[0]]:.3f} | {m['setup_wns_ns']:.6f} / {m['hold_wns_ns']:.6f} | {row['nondominated']} |")
    deltas = ['| Design | New architecture | Reference | Route Δ% | C·N Δ% | H8 Δ% | Transitions Δ% | H4 Δ% |', '|---|---|---|---:|---:|---:|---:|---:|']
    for row in new:
        for role, d in row.get('delta_percent', {}).items():
            deltas.append(f"| {row['design']} | {row['architecture']} | {role} | {d[PHYSICAL[0]]:+.3f} | {d[PHYSICAL[1]]:+.3f} | {d[PHYSICAL[2]]:+.3f} | {d['total_transitions']:+.3f} | {d['peak_local_cap_4_ff']:+.3f} |")
    spatial_ties = []
    for design in designs:
        values = [r['predicted']['spatial_peak_8_ff'] for r in rows if r['design'] == design and r['new']]
        if values and max(values)-min(values) < 1e-6:
            spatial_ties.append(design)
    tie_note = ('The retained predicted H8 values are tied for '+', '.join(spatial_ties)+
                '; the spatial selection label there does not indicate a lower predicted peak.') if spatial_ties else ''
    verification = 'Verification records are in `tests.json` and `reproducibility.json` when present.'
    if (out/'tests.json').exists() and (out/'reproducibility.json').exists():
        tests, replay = read(out/'tests.json'), read(out/'reproducibility.json')
        verification = (f"The repository suite passed {tests['repository_suite']['passed']} tests. "
            f"The final focused check passed {tests['adapter_regression_and_focused_recheck']['passed']} tests. "
            f"Independent replay reproduced {sum(r['selected_reproduced'] for r in replay)} selected candidates "
            f"and matched stored Q totals for {sum(r['stored_Q_totals_checked'] for r in replay)} FFs. "
            "See `tests.json` and `reproducibility.json`.")
    text = f'''# PACT Implementation-Aware Backend v2

**{classification}**

Generated and evaluated {summary['new_architectures_evaluated']} distinct new
architectures; selected {len(new)} for implementation and measured
{summary['physically_measured']}. The primary measured Pareto space is routed
scan-path upper bound, all-data weighted total shift activity and 8×8 weighted
local peak. Timing/DRC qualify eligibility, and every metric remains separately
reported. No scalar score determines this classification.

## Commands and inputs

Run from the repository in the existing WSL Ubuntu-24.04 environment:

```sh
export PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY={python_executable()}
for d in s5378 s9234 s15850; do
  $PY scripts/pact_v2.py search --design "$d" --seconds 180 --max-evaluations 20000 --route-limit 3
  $PY scripts/pact_v2.py route --design "$d" --route-seconds 600
  $PY scripts/pact_v2.py measure --design "$d"
done
$PY scripts/pact_v2.py report
$PY scripts/pact_v2_check.py
$PY scripts/pact_v2_seal.py
```

Search refuses to overwrite evidence; use a fresh `--output` for replay. Exact
invocations, parent commits, input hashes and Python tool versions are in each
design's `inputs.json`. Source-code hashes bind the actual search implementation.
`search.json` contains configuration, initialization/search runtime, evaluation
counts, baseline scores, the predicted frontier and selection roles. Canonical
architectures and hashes are in `architectures/`; the lossless mutation log is
`evaluations.csv.gz`. `comparison.csv` includes every distinct evaluated order,
including rejected proposals; unimplemented rows have no physical measurement.
The local uncompressed logs and large implementation artifacts are ignored.

Inputs are the stored P/T, J50 and PACT architectures, original FAN BASIC_SCAN
patterns, bijective FF mappings, frozen placement/ports and existing OpenRCX +
Liberty loads. The other physical ordering is also a seed. Old results and routes
were reused without rerunning historical experiments. New route execution records
contain exact rewire/make/verification commands and runtime. Measurement manifests
bind routed ODB, netlist, workload, library, extraction rules and simulator inputs.
The evidence seal verifies those bindings, stores compressed per-cycle/stimulus
records, and hashes the local raw waveforms, parasitics and databases without
adding them to Git.

## Predicted selection

Activity and spatial extremes plus a balanced nondominated candidate were selected
under configurable 10% wire and maximum-edge allowances; duplicates were removed.
These are estimates over direct FF Q/QN loads, not whole-network predictions.

{tie_note}

{chr(10).join(table)}

## Measured physical effects

Both load and unload are measured. The original zero-delay gate simulation,
source-localized grids, OpenRCX grounded + Liberty pin capacitance convention,
route verification and functional checks are unchanged. All shown timing values
are the existing flow's global-route estimates, not signoff. DRC and all verification
outcomes are in `summary.json` and individual route/measurement reports.

{verification}

The core objective implementation is unchanged across these runs; later CLI
edits added measurement locking and path normalization.

{chr(10).join(measured)}

## Comparison with each stored baseline

Negative changes mean reduction. Nondominance is computed against all measured
eligible old and new candidates of the same design, not just the physical start.

{chr(10).join(deltas)}

## Limitations and remaining publication work

Frozen direct FF loads omit downstream combinational toggles, buffer descendants
and candidate-specific load changes during search. Consequently a lower FF peak
does not guarantee a lower whole-network peak. Route measurements resolve that
distinction, and 4×4 results are reported without changing the primary 8×8 objective.
The timing constraint is maximum physical edge length, not a calibrated timing
predictor; actual setup/hold information is limited to the existing flow.

This is one bounded synthesis run per design at the established placement seed,
not multiseed generalization or broad validation. Publication-quality claims would
need an independently planned evaluation with more designs/placements, timing-aware
simulation or signoff where applicable, and a fuller load model if needed. None
of these results establishes watts, IR-drop or silicon reliability improvement.
'''
    (out/'README.md').write_text(text)
    print(classification, summary['new_nondominated'], flush=True)
