"""Compare only new routed implementations with the preserved measured v2 frontier."""
import csv
import gzip
from pathlib import Path
import numpy as np
from pact_v2 import ROOT, DESIGNS, read, write_json, binding
from pact_v2_report import PHYSICAL, measurement
from pact.optimizer.search import dominates
from pact.optimizer.candidate_sensitive import METRICS


def qualified(row):
    m = row.get('measured')
    return bool(row['status'] == 'QUALIFIED' and m and m['DRC'] == 0 and
        m['setup_wns_ns'] >= 0 and m['hold_wns_ns'] >= 0 and
        (not row['new'] or all(row.get('checks', {}).get(k) == 'PASS' for k in
            ('FF_transition_crosscheck', 'topology_verification', 'functional_verification'))))


def report(out):
    previous = read(ROOT/'results/pact_v2/summary.json')
    rows, designs = [], {}
    for design in DESIGNS:
        folder = out/design
        if not (folder/'search.json').exists(): continue
        result = read(folder/'search.json')
        inputs = read(folder/'inputs.json')
        predicted = {r['architecture_sha256']: r for r in result['baselines']}
        for old in previous['candidates']:
            if old['design'] != design or not old['measured']: continue
            r = predicted[old['architecture_sha256']]
            rows.append(dict(design=design, architecture=old['architecture'], architecture_sha256=old['architecture_sha256'],
                new=False, status=old['status'], measured=old['measured'], predicted=r['metrics'],
                frozen=r['frozen_metrics'], source_local_H8_ff=r['source_local_H8_ff'],
                selected_roles=[], prior_nondominated=old['nondominated'], provenance='stored_v2_milestone'))
        for r in result['archive']:
            if not r['new']: continue
            sha = r['architecture_sha256']
            row = dict(design=design, architecture=sha[:12], architecture_sha256=sha, new=True,
                status='PREDICTED_ONLY', measured=None, predicted=r['metrics'], frozen=r['frozen_metrics'],
                source_local_H8_ff=r['source_local_H8_ff'], selected_roles=r['selected_roles'], provenance=r['label'])
            route_path = out/'routes'/design/sha/'route_result.json'
            if route_path.exists():
                route = read(route_path)
                row['status'], row['route'] = route['status'], binding(route_path)
                mp = out/'measurement'/design/sha[:12]
                if (mp/'activity_summary.json').exists():
                    row['measured'] = measurement(mp, route)
                    row['measurement'] = binding(mp/'activity_summary.json')
                    row['checks'] = {k: read(mp/(k+'.json'))['status'] for k in
                        ('FF_transition_crosscheck', 'topology_verification', 'functional_verification')}
            rows.append(row)
        designs[design] = {k: result[k] for k in ('evaluations', 'new_unique', 'accepted', 'runtime_seconds',
            'initialization_seconds', 'model_setup_seconds', 'search_seconds', 'total_seconds',
            'evaluations_per_second', 'milliseconds_per_evaluation', 'peak_RSS_MiB', 'profile',
            'wire_ceiling_um', 'timing_ceiling_um', 'config', 'selection_rule')}
        old_search = read(ROOT/'results/pact_v2'/design/'search.json')
        prior_ids = {r['order_id'] for r in old_search['archive']+old_search['baselines']}
        prior_log = ROOT/'results/pact_v2'/design/'evaluations.csv.gz'
        with gzip.open(prior_log, 'rt') as f:
            prior_ids.update(r['order_id'] for r in csv.DictReader(f))
        with gzip.open(folder/'evaluations.csv.gz', 'rt') as f:
            evaluated = list(csv.DictReader(f))
        unique = {r['order_id'] for r in evaluated}
        designs[design]['new_to_prior_evaluated_corpus'] = len(unique-prior_ids)
        designs[design]['previously_evaluated_orders'] = len(unique & prior_ids)
        designs[design]['prior_evaluation_log'] = binding(prior_log)
        designs[design]['mutation_loop_seconds'] = float(evaluated[-1]['seconds'])
        designs[design]['mutation_loop_ms_per_evaluation'] = 1000*float(evaluated[-1]['seconds'])/len(evaluated)
        for r in result['selected']:
            if r['order_id'] in prior_ids: raise ValueError('Selected architecture already evaluated by v2')
        physical = read(folder/'physical_model.json')
        designs[design].update(inputs=binding(folder/'inputs.json'), physical_model=binding(folder/'physical_model.json'),
            calibration_samples=len(physical['calibration']['samples']), wire_cap_ff_per_um=physical['rho'],
            selected=[r['architecture_sha256'] for r in result['selected']],
            evaluation_log=binding(folder/'evaluations.csv.gz'))
    eligible = [r for r in rows if qualified(r)]
    for row in rows:
        row['qualified'] = qualified(row)
        row['nondominated'] = None
        row['extends_existing_v2_frontier'] = False
        if not row['qualified']: continue
        same = [r for r in eligible if r['design'] == row['design'] and r is not row]
        vector = np.array([row['measured'][k] for k in PHYSICAL])
        row['dominated_by'] = [r['architecture'] for r in same if dominates(np.array([r['measured'][k] for k in PHYSICAL]), vector)]
        row['nondominated'] = not row['dominated_by']
        historical = [r for r in same if not r['new']]
        row['extends_existing_v2_frontier'] = bool(row['new'] and row['nondominated'] and not any(
            np.allclose(vector, [r['measured'][k] for k in PHYSICAL], rtol=1e-9, atol=1e-8) for r in historical))
        row['relative_to_stored'] = {r['architecture']: {k: 100*(row['measured'][k]/r['measured'][k]-1)
            for k in PHYSICAL} for r in historical}
    selected = [r for r in rows if r['new'] and r['selected_roles']]
    found = [r for r in selected if r['extends_existing_v2_frontier']]
    complete = len(designs) == 3 and all(r['status'] != 'PREDICTED_ONLY' for r in selected) and all(
        r['measured'] is not None or r['status'] != 'QUALIFIED' for r in selected)
    classification = 'PACT_CANDIDATE_SENSITIVE_PHYSICAL_EVALUATION_INCOMPLETE'
    if complete:
        classification = 'PACT_CANDIDATE_SENSITIVE_NEW_FRONTIER_FOUND' if found else 'PACT_CANDIDATE_SENSITIVE_MODEL_WORKING_NO_NEW_FRONTIER'
    # Relative changes compare like-for-like within each predictor's scale.
    for row in selected:
        row['prediction_diagnostics'] = []
        if not row['measured']: continue
        for old in [r for r in rows if r['design'] == row['design'] and not r['new'] and r['prior_nondominated']]:
            diagnostic = dict(reference=old['architecture'])
            for key, f, c, actual in [('E', 'activity_ff_transitions', 'candidate_E_ff', PHYSICAL[1]),
                                       ('H8', 'spatial_peak_8_ff', 'propagated_H8_ff', PHYSICAL[2])]:
                frozen = 100*(row['frozen'][f]/old['frozen'][f]-1)
                candidate = 100*(row['predicted'][c]/old['predicted'][c]-1)
                measured = 100*(row['measured'][actual]/old['measured'][actual]-1)
                diagnostic[key] = dict(frozen_delta_percent=frozen, candidate_delta_percent=candidate,
                    actual_delta_percent=measured, frozen_error_percentage_points=abs(frozen-measured),
                    candidate_error_percentage_points=abs(candidate-measured))
            row['prediction_diagnostics'].append(diagnostic)
    summary = dict(schema='pact_candidate_sensitive_v1', classification=classification,
        prior_milestone=binding(ROOT/'results/pact_v2/summary.json'), measured_frontier_objectives=list(PHYSICAL),
        designs=designs, candidates=rows, selected=len(selected), physically_measured=sum(bool(r['measured']) for r in selected),
        new_nondominated=[dict(design=r['design'], architecture=r['architecture']) for r in found],
        interpretation='Paired prediction deltas diagnose the selected set only; this is not a causal comparison with a fresh frozen-model search.')
    write_json(out/'summary.json', summary)
    fields = ['design', 'architecture', 'architecture_sha256', 'provenance', 'new', 'selected_roles', 'status',
        'frozen_E_ff', 'candidate_E_ff', 'actual_E_ff', 'frozen_H8_ff', 'propagated_H8_ff', 'source_local_H8_ff',
        'actual_H8_ff', 'wire_um', *PHYSICAL, 'total_transitions', 'peak_transitions', 'peak_local',
        'peak_local_4', 'peak_local_cap_4_ff', 'setup_wns_ns', 'hold_wns_ns', 'DRC', 'qualified',
        'nondominated', 'extends_existing_v2_frontier']
    with (out/'comparison.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
        for r in rows:
            m = r['measured'] or {}
            writer.writerow(dict(r, selected_roles='/'.join(r['selected_roles']), **r['predicted'], **m,
                frozen_E_ff=r['frozen']['activity_ff_transitions'], actual_E_ff=m.get(PHYSICAL[1]),
                frozen_H8_ff=r['frozen']['spatial_peak_8_ff'], actual_H8_ff=m.get(PHYSICAL[2])))
    lines = ['# PACT candidate-sensitive physical model', '', '**'+classification+'**', '',
        'One bounded synthesis per design, one established placement/workload regime. Prior measured evidence is reused unchanged.', '',
        '| Design | New architectures | Evaluations/s | ms/evaluation | Peak RSS MiB | Wire fF/um | Samples | Selected |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for d, r in designs.items():
        lines.append(f"| {d} | {r['new_to_prior_evaluated_corpus']} | {r['evaluations_per_second']:.2f} | {r['milliseconds_per_evaluation']:.3f} | {r['peak_RSS_MiB']:.1f} | {r['wire_cap_ff_per_um']:.6f} | {r['calibration_samples']} | {len(r['selected'])} |")
    lines += ['', '## Selected predictions and measurements', '',
        '| Design | Hash | Frozen E | New E | Measured C·N | Frozen H8 | Propagated H8 | Measured H8 | Route um | Extends v2 frontier |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    def number(value): return 'pending' if value is None else f'{value:.4f}'
    for r in selected:
        m = r['measured'] or {}
        vals = [r['frozen']['activity_ff_transitions'], r['predicted']['candidate_E_ff'], m.get(PHYSICAL[1]),
            r['frozen']['spatial_peak_8_ff'], r['predicted']['propagated_H8_ff'], m.get(PHYSICAL[2]), m.get(PHYSICAL[0])]
        lines.append('| '+r['design']+' | '+r['architecture']+' | '+' | '.join(map(number, vals))+' | '+str(r['extends_existing_v2_frontier'])+' |')
    lines += ['', '## Selection and interpretation', '']
    for r in selected:
        lines.append(f"- {r['design']} `{r['architecture']}`: {', '.join(r['selected_roles'])}; {r['status']}.")
    lines += ['', '## Measured frontier changes', '',
        '| Design | New point | Prior frontier reference | Route delta % | C·N delta % | H8 delta % |',
        '|---|---|---|---:|---:|---:|']
    for r in found:
        for old in [v for v in rows if v['design'] == r['design'] and not v['new'] and v['prior_nondominated']]:
            delta = r['relative_to_stored'][old['architecture']]
            lines.append(f"| {r['design']} | {r['architecture']} | {old['architecture']} | "+
                ' | '.join(f'{delta[k]:+.4f}' for k in PHYSICAL)+' |')
    lines += ['', '## Prediction behavior on the selected pairs', '',
        'The following compares the ordering of the two selected candidates within each design. A correct ordering on two points is only a diagnostic; it is not a validation campaign.', '',
        '| Design | Metric | Frozen pair ordering | Candidate-sensitive pair ordering |',
        '|---|---|---|---|']
    for design in designs:
        pair = [r for r in selected if r['design'] == design and r['measured']]
        if len(pair) != 2: continue
        a, b = pair
        for label, f, c, actual in [('E', 'activity_ff_transitions', 'candidate_E_ff', PHYSICAL[1]),
                                   ('H8', 'spatial_peak_8_ff', 'propagated_H8_ff', PHYSICAL[2])]:
            observed = np.sign(a['measured'][actual]-b['measured'][actual])
            def ordering(x, y):
                if np.isclose(x, y, rtol=1e-9, atol=1e-8): return 'tied'
                return 'correct' if np.sign(x-y) == observed else 'reversed'
            lines.append(f"| {design} | {label} | {ordering(a['frozen'][f], b['frozen'][f])} | {ordering(a['predicted'][c], b['predicted'][c])} |")
    lines += ['', 'Improved electrical coverage and a newly measured frontier point do not guarantee better ranking. In particular, replacing a tied frozen H8 estimate with distinct values is useful information only when the ordering survives physical implementation. Remaining ranking errors must be preserved alongside successful frontier extensions.']
    lines += ['', 'All supplied measured architectures, including the strongest v2 candidates, were rescored with the new model before selection. Only genuinely new predicted nondominated points were eligible; the quota was a maximum.', '',
        'New architecture counts above exclude every order in the entire previous v2 evaluation log, not just the starting seeds. Every selected order is also verified absent from that prior corpus. Search JSON retains its original seed-relative unique count. Runtime rates in the table include final reference checks; summary JSON also gives mutation-loop-only cost.', '',
        'The CSV records both predictors and every measured metric for retained candidates and stored measured references. Per-design compressed logs record every evaluated order hash, parent hash, operator, feasibility, acceptance and score. Summary JSON includes paired relative prediction errors against each prior frontier point; smaller error on this selected sample does not establish general predictive validity or isolate the effect of the model from search stochasticity.', '',
        'The electrical model partitions actual Liberty input pins exactly and apportions shared extracted ground capacitance by functional/total HPWL. Candidate scan load is the measured median scan-only ground capacitance per Manhattan micrometre times candidate edge length, plus actual SI/port-buffer input capacitance. Transparent descendants and one combinational level use precomputed spatial influence; the latter uses normalized uniform Boolean sensitivity. No new fitted proxy, random workload, ATPG run, physical seed sweep or timing model is introduced.', '',
        'See `docs/pact_candidate_sensitive_model.md` for equations, limitations and implementation. Search/route/measurement commands, hashes, versions, configuration and runtimes are bound in the per-design and per-candidate manifests. The historical physical measurement implementation is unchanged.', '',
        'Remaining bottlenecks are shared-route geometry, candidate buffer insertion/resizing, input-state correlation and switching beyond the first combinational level. A next implementation milestone should improve bounded state-aware cone propagation and shared-net geometry using these selected implementations as diagnostics, preserving the existing route budget.']
    (out/'README.md').write_text('\n'.join(lines)+'\n')
    print(classification, summary['new_nondominated'], flush=True)
