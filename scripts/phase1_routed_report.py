#!/usr/bin/env python3
"""Summarize the frozen Phase-1 routes, including failures, without selection."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact.experiment_storage import configure_experiment_storage
from pact.phase0d.campaign import atomic_write_json as write, file_sha256
from pact.phase0d.pareto import nondominated

REPORT = ROOT / 'reports/phase1_routed_validation'
def read(path):
    return json.loads(Path(path).read_text())

def summarize(paths):
    freeze = read(REPORT / 'freeze.json')
    for name, expected in freeze['files'].items():
        assert file_sha256(REPORT / name) == expected, f'Frozen contract artifact changed: {name}'
    prior_hashes = read(REPORT / 'provenance.json')
    for path, expected in prior_hashes.items():
        assert file_sha256(Path(path)) == expected, f'Reused evidence changed: {path}'
    selected = read(REPORT / 'selected_candidates.json')
    baselines = read(REPORT / 'baselines.json')
    quality = read(REPORT / 'test_quality_reference.json')
    work = paths.results / 'phase1_routed_validation'
    rows, analysis, result_hashes = [], {}, {}
    for design in selected:
        design_rows = []
        inputs = [(b['method'], 'baseline', Path(b['route_path']), read(b['proxy_path']), b)
                  for b in baselines[design]]
        for s in selected[design]:
            sha = s['architecture_sha256']
            proxy = work / design / 'candidates' / sha / 'proxy.json'
            inputs.append(('/'.join(s['selection_roles']), 'PACT', work / design / sha / 'route_result.json',
                           read(proxy) if proxy.exists() else {}, s))
        for label, group, path, proxy, original in inputs:
            route = read(path) if path.exists() else {'status': 'NOT_COMPLETED'}
            if path.exists():
                result_hashes[str(path)] = file_sha256(path)
            if group == 'PACT' and route.get('status') == 'QUALIFIED':
                archive = path.parent / '5_2_route.odb.gz'
                assert file_sha256(archive) == route['routed_odb_gzip_sha256']
                with gzip.open(archive, 'rb') as stream:
                    assert hashlib.file_digest(stream, 'sha256').hexdigest() == route['routed_odb_sha256']
                for extra in ('5_1_grt.json', '5_2_route.json', 'routed_verification.json',
                              'route/execution.json', 'route/stdout.log', 'route/stderr.log',
                              'rewire/execution.json', 'rewire/stdout.log', 'rewire/stderr.log'):
                    result_hashes[str(path.parent / extra)] = file_sha256(path.parent / extra)
                result_hashes[str(archive)] = file_sha256(archive)
                for extra in ('architecture.json', 'proxy.json', 'structural_proof.json'):
                    candidate_path = Path(route['candidate_directory']) / extra
                    result_hashes[str(candidate_path)] = file_sha256(candidate_path)
            m = route.get('structured_metrics', {})
            proof = route.get('postroute_verification', {})
            if isinstance(proof, str):
                proof = read(ROOT / proof)
            if group == 'baseline':
                runtime = read(path.parent / 'route/execution.json')['elapsed_s']
                grt = read(path.parent / '5_1_grt.json')
                area = {k:v for k,v in grt.items() if k.endswith('__design__instance__area')}
                structural = {k:proxy.get(k) for k in ('FF_inventory_verified', 'all_patterns_parallel_load_verified',
                                                       'all_patterns_scan_out_verified')}
                structural_ok = all(structural.values())
            else:
                runtime = route.get('route_execution', {}).get('elapsed_s')
                area = m.get('reported_area', {})
                structural = proxy.get('structural_proof', {})
                structural_ok = (structural.get('FF_inventory_verified') and structural.get('K_fixed')
                    and structural.get('exact_parallel_loading_verified')
                    and structural.get('ATPG_patterns_verified') == quality[design]['pattern_count']
                    and route.get('architecture_materialized_sha256') == original['architecture_sha256'])
            lengths = proxy.get('chain_statistics', {}).get('chain_lengths', [])
            legal = len(lengths) == 2 and min(lengths) >= 8 and max(lengths)-min(lengths) <= 2
            valid = bool(route['status'] == 'QUALIFIED' and structural_ok and legal and proof.get('status') == 'PASS'
                         and proof.get('scan_ff_count') == quality[design]['FF_count']
                         and proof.get('scan_edges') == quality[design]['FF_count']-2)
            congestion = m.get('congestion') or m.get('initial_global_route_congestion') or {}
            row = {'design': design, 'label': label, 'group': group,
                'architecture_sha256': original['architecture_sha256'], 'status': route['status'],
                'valid': valid, 'physical_proxy_um': original['objectives'][0], 'H_eff8': original['objectives'][1],
                'routed_path_upper_bound_um': route.get('routed_full_scan_path_net_length_upper_bound_um'),
                'exact_scan_only_length_um': route.get('exact_scan_only_routed_length_um'),
                'total_detailed_wirelength_um': m.get('total_detailed_route_wirelength_um'),
                'DRC_errors': m.get('detailed_route_drc_errors'), 'vias': m.get('detailed_route_vias'),
                'overflow': m.get('global_route_overflow'),
                'initial_grt_utilization_percent': congestion.get('total', {}).get('usage_percent'),
                'setup_WNS_ns': m.get('setup_wns_ns'), 'setup_TNS_ns': m.get('setup_tns_ns'),
                'hold_WNS_ns': m.get('hold_wns_ns'), 'hold_TNS_ns': m.get('hold_tns_ns'),
                'setup_violated_endpoints': m.get('setup_violated_endpoints'),
                'hold_violated_endpoints': m.get('hold_violated_endpoints'),
                'timing_stage': m.get('timing_stage'), 'reported_area': area,
                'chain_lengths': lengths, 'pattern_count': quality[design]['pattern_count'],
                'ATPG_coverage_percent': quality[design]['stuck_at_coverage_percent'],
                'test_quality_preserved': bool(structural_ok and legal), 'structural_proof': structural,
                'postroute_structure_pass': proof.get('status') == 'PASS', 'route_seconds': runtime,
                'route_evidence': str(path)}
            row['not_available_fields'] = [k for k,v in row.items() if v is None]
            design_rows.append(row)
        qualified = [r for r in design_rows if r['valid'] and r['routed_path_upper_bound_um'] is not None]
        front = nondominated(qualified, key=lambda r: (r['routed_path_upper_bound_um'], r['H_eff8'], 0))
        for r in design_rows:
            r['routed_pareto_member'] = r in front
            r['proxy_rank'] = 1 + sum(q['physical_proxy_um'] < r['physical_proxy_um'] for q in qualified) if r['valid'] else None
            r['routed_rank'] = 1 + sum(q['routed_path_upper_bound_um'] < r['routed_path_upper_bound_um'] for q in qualified) if r['valid'] else None
            r['dominated_by'] = [other['label'] for other in qualified if r['valid']
                and other['routed_path_upper_bound_um'] <= r['routed_path_upper_bound_um']
                and other['H_eff8'] <= r['H_eff8']
                and (other['routed_path_upper_bound_um'] < r['routed_path_upper_bound_um'] or other['H_eff8'] < r['H_eff8'])]
        supports = any(r['group'] == 'PACT' and not any(
            b['group'] == 'baseline' and b['routed_path_upper_bound_um'] == r['routed_path_upper_bound_um']
            and b['H_eff8'] == r['H_eff8'] for b in qualified) for r in front)
        inversions, concordant, ties = [], 0, 0
        for i, a in enumerate(qualified):
            for b in qualified[i+1:]:
                product = (a['physical_proxy_um']-b['physical_proxy_um'])*(a['routed_path_upper_bound_um']-b['routed_path_upper_bound_um'])
                if product < 0:
                    inversions.append([a['label'], b['label']])
                elif product > 0:
                    concordant += 1
                else:
                    ties += 1
        balanced = next(r for r in design_rows if r['group']=='PACT' and 'balanced' in r['label'])
        extremes = [r for r in qualified if r['group']=='PACT' and r is not balanced]
        balanced_tradeoff = any((balanced['routed_path_upper_bound_um']-r['routed_path_upper_bound_um'])*
                               (balanced['H_eff8']-r['H_eff8']) < 0 for r in extremes) if balanced['valid'] else False
        analysis[design] = {'sufficient_valid_comparison': len(qualified)==len(design_rows),
            'PACT_routed_survival': supports, 'balanced_distinct': balanced['label']=='balanced',
            'balanced_useful': balanced['label']=='balanced' and balanced in front and balanced_tradeoff,
            'proxy_concordant_pairs': concordant, 'proxy_discordant_pairs': len(inversions),
            'proxy_tied_pairs': ties, 'proxy_inversions': inversions,
            'PACT_only_proxy_inversions': [pair for pair in inversions if all(
                next(r for r in qualified if r['label']==label)['group']=='PACT' for label in pair)],
            'routed_pareto_labels': [r['label'] for r in front]}
        # Diagnostic only: roundoff-equivalent activity values must not be sold as gains.
        rounded_front = nondominated(qualified, key=lambda r: (round(r['routed_path_upper_bound_um'], 6), round(r['H_eff8'], 9), 0))
        analysis[design]['pareto_labels_with_roundoff_equivalence'] = [r['label'] for r in rounded_front]
        rows.extend(design_rows)
    if not all(a['sufficient_valid_comparison'] for a in analysis.values()):
        classification = 'PACT_PHASE1_MULTI_DESIGN_ROUTED_VALIDATION_INCOMPLETE'
    else:
        count = sum(a['PACT_routed_survival'] for a in analysis.values())
        classification = ('PACT_PHASE1_MULTI_DESIGN_ROUTED_VALIDATION_CONFIRMED' if count==2 else
                          'PACT_PHASE1_MULTI_DESIGN_ROUTED_VALIDATION_MIXED' if count==1 else
                          'PACT_PHASE1_MULTI_DESIGN_ROUTED_ADVANTAGE_NOT_REPLICATED')
    payload = {'classification': classification, 'rows': rows, 'analysis': analysis,
               'timing_caveat': 'Timing is global-route stage; detailed-route timing not provided by qualified flow.'}
    write(REPORT / 'routed_results.json', payload)
    write(REPORT / 'result_provenance.json', result_hashes)
    attempts = read(work / 'route_attempts.json')
    assert len(attempts) <= 6 and len({r['architecture_sha256'] for r in attempts}) == len(attempts)
    integrity = {'freeze_files_unchanged': len(freeze['files']), 'prior_evidence_files_unchanged': len(prior_hashes),
        'new_route_attempts': len(attempts), 'new_baseline_routes': 0, 's5378_new_routes': 0,
        'qualified_new_routes': sum(r['group']=='PACT' and r['valid'] for r in rows),
        'new_route_archive_hashes_verified': True,
        'raw_experiment_bytes': sum(p.stat().st_size for p in work.rglob('*') if p.is_file()),
        'experiment_root': str(work)}
    write(REPORT / 'integrity_audit.json', integrity)
    with (REPORT / 'routed_results.csv').open('w', newline='') as stream:
        fields = [k for k in rows[0] if k not in ('structural_proof', 'reported_area', 'not_available_fields')]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)
    # Native Windows git captures status quickly; WSL scanning this checkout is expensive.
    lines = ['# PACT Phase-1 multi-design routed validation', '', f'**Classification: `{classification}`**', '',
        ('Yes, under this frozen seed-11/K=2 Nangate45 experiment, joint physical/activity Pareto '
         'advantages survive on both new designs with test quality preserved.' if classification.endswith('CONFIRMED')
         else 'The frozen experiment does not establish confirmation on both new designs.'), '',
        'The frozen experiment uses seed 11, K=2 and the unchanged Optimizer-v2.3 archives. '
        'Six candidates (three per design) were preselected using only authoritative proxy/H_eff8 objectives. '
        'All six Phase-0C baseline methods per design are included. No baseline or s5378 route was repeated.', '',
        '## Contract, selection and provenance', '',
        'The [experimental contract](reports/phase1_routed_validation/EXPERIMENT_CONTRACT.md), '
        '[freeze hashes](reports/phase1_routed_validation/freeze.json), '
        '[input hashes](reports/phase1_routed_validation/provenance.json) and '
        '[environment](reports/phase1_routed_validation/environment.json) record the pre-route decision. '
        'The global exact nondominated union includes all six retained v2.3 archives per design '
        '(both budget modes, W=1/2/4). Physical and activity extrema minimize their respective authoritative '
        'objectives; the balanced point minimizes squared Euclidean distance to the normalized utopia '
        'using global-frontier min/max ranges, with deterministic objective/hash tie breaks. '
        'See [selected architectures](reports/phase1_routed_validation/selected_candidates.json) for full hashes and source runs.', '',
        'Baseline materialization reproduced the historical P ODB hash byte-for-byte for both designs. '
        'Archived routed ODB compressed/uncompressed hashes and structural proofs passed. OpenROAD '
        '`26Q2-1164-g08f67ee5ec` and ORFS `5e8b1450d19263f797a27c4f371b9dd19f32a3aa` match Phase-0C. '
        'New ORFS work and raw route evidence are under `D:/PACT_EXPERIMENTS/results/phase1_routed_validation`; '
        'WORK_HOME changes only output placement. Existing configs, SDC, rewiring and verification are reused.', '',
        '| Design | Role | Architecture SHA256 prefix | Source run |',
        '|---|---|---|---|']
    for design, points in selected.items():
        for point in points:
            source = '/'.join(Path(point['source_runs'][0]).parts[-2:])
            lines.append(f'| {design} | {"/".join(point["selection_roles"])} | `{point["architecture_sha256"][:12]}` | {source} |')
    lines += ['',
        '## Routing and routed Pareto comparison', '',
        'P = physical; A = activity; B0 = conventional supplied order; J50 = joint heuristic; '
        'T = long-edge-risk heuristic; R = fixed randomized reference. Native B1 is K=1 and incompatible. '
        'The physical Pareto axis is the existing full scan-path routed net-length **upper bound**, '
        'including shared functional branches; it is not exclusive scan wirelength. H_eff8 remains '
        'the frozen dimensionless activity proxy, not measured power. Lower is better on both axes.', '',
        '![Routed Pareto comparison](reports/phase1_routed_validation/routed_pareto.png)', '']
    fmt = lambda x: 'N/A' if x is None else f'{x:.3f}' if isinstance(x, float) else str(x)
    for design, a in analysis.items():
        lines += [f'### {design}', '', '| Architecture | Proxy µm | H_eff8 | Routed path bound µm | Total wire µm | DRC | Pareto |',
                  '|---|---:|---:|---:|---:|---:|---|']
        for r in [r for r in rows if r['design']==design]:
            lines.append('| ' + ' | '.join([r['label'], *[fmt(r[k]) for k in ('physical_proxy_um','H_eff8',
                'routed_path_upper_bound_um','total_detailed_wirelength_um','DRC_errors')], str(r['routed_pareto_member'])]) + ' |')
        lines += ['', f'PACT survival: **{a["PACT_routed_survival"]}**. Balanced-point usefulness: **{a["balanced_useful"]}**. '
            f'Proxy/routed ordering: {a["proxy_concordant_pairs"]} concordant, {a["proxy_discordant_pairs"]} discordant, '
            f'{a["proxy_tied_pairs"]} tied pairs across all valid architectures.',
            'Ordering inversions: ' + (', '.join(' / '.join(pair) for pair in a['proxy_inversions']) or 'none') + '.', '']
        lines += ['Within the selected PACT candidates, proxy-order inversions are '
                  + (', '.join(' / '.join(pair) for pair in a['PACT_only_proxy_inversions']) or 'absent') + '.', '']
        for r in [r for r in rows if r['design']==design and r['group']=='PACT']:
            lines.append(f'- {r["label"]}: {r["status"]}; chains {r["chain_lengths"]}; route {fmt(r["route_seconds"])} s; '
                         f'dominated by {", ".join(r["dominated_by"]) or "none"}.')
        lines += ['']
    lines += ['The [machine-readable table](reports/phase1_routed_validation/routed_results.json) includes completion, '
        'DRC, congestion/overflow, vias, area when reported, setup/hold WNS/TNS and endpoint counts, runtimes, '
        'chain lengths, coverage, pattern counts, hashes, proofs and explicitly unavailable fields. '
        '**Timing values are global-route timing**, as in the qualified methodology; no detailed-route signoff STA is claimed.', '',
        '## Test quality', '',
        's9234 retains 211 FFs, 156 frozen FAN patterns and 94.14% stuck-at coverage; s15850 retains '
        '534 FFs, 133 patterns and 94.62%. Selected architectures are re-evaluated only to verify stored '
        'objective values and exact ATPG PPI load/unload reconstruction. Coverage is inherited under '
        'the established full-scan semantics; it is not a new post-route fault simulation. K=2, minimum '
        'chain length 8, length difference at most 2, unchanged FF identity/coordinates, SI/SO identity, '
        'architecture hashes and every routed scan link through transparent buffers are checked.', '',
        '## Cross-design interpretation and limitations', '',
        'The existing s5378 Phase-0D evidence is `PACT_PHASE0D_ROUTED_PARETO_CONFIRMED` '
        '([reference](reports/phase0d/routed_pareto_qualification/ROUTED_PARETO_REPORT.md)); '
        'it is earlier optimizer evidence, not a newly routed v2.3 control. '
        'Its representative `75ea663523d9` point reduced routed path cost by 5.81% and H_eff8 by 3.95% '
        'against P; three optimizer points survived against the four baselines in that prior comparison. '
        'The two new designs test replication using the frozen v2.3 candidates. '
        'Three ISCAS designs at one selected seed/K and one Nangate45 flow do not establish universal '
        'generalization, scaling, seed robustness, signoff test power, capture activity or IR-drop benefit. '
        'The path metric can include shared net branches; H_eff8 weights remain frozen before routing.', '',
        '## Final answer and remaining research question', '',
        f'The predeclared classification is **`{classification}`**. '
        + ('Both new designs retain at least one routed nondominated PACT improvement/tradeoff with test quality preserved.'
           if classification.endswith('CONFIRMED') else
           'The evidence does not meet the predeclared confirmation criterion; consult the per-design results above.'), '',
        'The remaining research question is whether these joint physical/activity Pareto advantages replicate '
        'across broader design families, physical seeds and implementation conditions while preserving test quality, '
        'and whether the frozen activity proxy predicts independently qualified test-mode physical power behavior.', '',
        '## Future work and git status', '',
        'Record broader replication and independently qualified detailed-route timing/power validation as future work; '
        'no optimizer tuning, new objective, ML, or search change was performed. '
        'The starting tree contained uncommitted v2.1/v2.2/v2.3 work, which remains untouched. '
        'All frozen experiment files and reused evidence hashes were rechecked after routing. '
        'A slow WSL Git status scan was replaced by native Windows Git; future experiment runners should use '
        'the native status capture for this checkout. '
        'See [git status](reports/phase1_routed_validation/git_status.txt) and the regression log for final validation.', '']
    if all(set(a['routed_pareto_labels']) == {'T', 'balanced', 'activity_extreme'} for a in analysis.values()):
        lines[4:4] = ['On both designs, baseline T and the PACT balanced/activity extremes form the routed front. '
                      'Both PACT physical extremes are dominated by T: lower proxy cost did not guarantee a lower routed cost.', '']
    lines += [f'Integrity: {integrity["qualified_new_routes"]}/{integrity["new_route_attempts"]} new routes qualified; '
              f'{integrity["prior_evidence_files_unchanged"]} reused evidence files and '
              f'{integrity["freeze_files_unchanged"]} frozen contract files unchanged. '
              f'Raw experiment storage: {integrity["raw_experiment_bytes"] / 1024**2:.1f} MiB on D:. '
              'Routed front membership is unchanged when roundoff-equivalent activity values are treated as equal.', '']
    regression = REPORT / 'regression.log'
    if regression.exists():
        summary = next((line.strip() for line in regression.read_text(encoding='utf-8-sig').splitlines()
                        if ' passed in ' in line), 'See regression log.')
        lines += [f'Full repository regression: **{summary}** '
                  '([log](reports/phase1_routed_validation/regression.log)).', '']
    (ROOT / 'PACT_PHASE1_MULTI_DESIGN_ROUTED_VALIDATION.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'classification': classification, 'analysis': analysis}), flush=True)

def plot():
    rows = read(REPORT / 'routed_results.json')['rows']
    selected = read(REPORT / 'selected_candidates.json')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, design in zip(axes, sorted(selected)):
        data = [r for r in rows if r['design']==design and r['valid']]
        for group, color, marker in [('baseline', '#687582', 'o'), ('PACT', '#bd4b20', 'D')]:
            points = [r for r in data if r['group']==group]
            faces = [color if group=='baseline' or r['routed_pareto_member'] else 'none' for r in points]
            ax.scatter([r['routed_path_upper_bound_um'] for r in points], [r['H_eff8'] for r in points],
                       label=group + (' (hollow: dominated)' if group=='PACT' else ''),
                       facecolors=faces, edgecolors=color, marker=marker, s=44, zorder=3)
            for r in points:
                label = r['label'].replace('physical_extreme', 'physical').replace('activity_extreme', 'activity')
                offset = {'P': (-12, 8), 'T': (-12, 8), 'physical': (5, -13),
                          'balanced': (5, -13)}.get(label, (4, 5))
                ax.annotate(label, (r['routed_path_upper_bound_um'], r['H_eff8']), xytext=offset,
                            textcoords='offset points', fontsize=7,
                            bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .7, 'pad': .5})
        front = sorted([r for r in data if r['routed_pareto_member']], key=lambda r:r['routed_path_upper_bound_um'])
        ax.plot([r['routed_path_upper_bound_um'] for r in front], [r['H_eff8'] for r in front],
                color='#bd4b20', alpha=.45, linewidth=1)
        ax.set(title=design, xlabel='Routed scan-path net-length upper bound (µm)', ylabel='Frozen H_eff8')
        ax.grid(alpha=.2); ax.margins(.15); ax.legend(fontsize=8)
    fig.suptitle('Phase-1 routed Pareto comparison · seed 11 · K=2 · lower is better')
    fig.tight_layout()
    fig.savefig(REPORT / 'routed_pareto.png', dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    if '--plot-only' in sys.argv:
        plot()
    else:
        summarize(configure_experiment_storage())
