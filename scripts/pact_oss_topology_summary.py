#!/usr/bin/env python3
"""Summarize measured tradeoffs; preserve frozen choices and exact comparisons."""
import csv

from pact_oss_benchmark import read
import pact_oss_topology_stage_a as stage


def main():
    pairs = list(csv.DictReader((stage.STAGE / 'pairwise_comparison.csv').open()))
    questions = read(stage.STAGE / 'scientific_questions.json')
    lines = ['# Measured Stage-A findings', '',
        'All 19 selected records are physically qualified. Twenty-seven indexed architectures are measured; three unselected P0 points remain unknown. The comparison uses the original selections and exact wire/E/H8 dominance, with no outcome-based matching threshold.', '',
        'The frozen balanced P0 representative improves E and H8 relative to repaired B3T on s5378 and s9234 at higher scan-path wire bounds. On s15850 it has lower H8, slightly higher E and higher wire. These measured tradeoffs do not establish universal dominance.', '',
        '| Design | P0 balanced vs B3T: scan wire | E | H8 |',
        '|---|---:|---:|---:|']
    for design in stage.DESIGNS:
        row = next(row for row in pairs if row['design'] == design and row['method'] == 'P0'
            and row['representative'] == 'True' and row['versus_method'] == 'B3T')
        values = [float(row[name+'_delta_percent']) for name in ('routed_scan_path_cost_um', 'measured_E', 'measured_H8')]
        lines.append('| '+design+' | '+' | '.join(f'{value:+.3f}%' for value in values)+' |')
    lines += ['', 'Lower values are better; wire denotes the full connected scan-path net-length upper bound.', '',
        'P0 supplies coordinate-unique nondominated measured points on every design: '+', '.join(
            f'{design}: {len(questions[design]["A1"]["coordinate_unique_nondominated_architectures"])}'
            for design in stage.DESIGNS)+'. This statement covers measured architectures only.', '',
        'The preselected s15850 P0 H8 extreme dominates B3T in wire, E and H8. The original balanced representative does not. A known unselected s15850 archive point also strictly dominates the balanced representative, while known unselected points on the smaller designs improve on all selected H8 values. These expose selection gaps; they do not uniquely identify H8 predictor incompleteness as their cause. No choices were changed.', '',
        'Lower routed scan cost does not guarantee lower activity: s5378 B2 has lower scan wire than B3T but higher E and H8. All global-route setup/hold endpoint violation counts and DRC counts are zero for the selected records.', '',
        'Scope: three fixed designs, seed 11, K=2 and the frozen FAN workload. E/H4/H8 are measured capacitance-weighted data-transition proxies. Detailed-route signoff timing, exact scan-only allocation on shared functional nets, missing congestion fields, and unknown archive points are not inferred.', '',
        'Upstream remains independent: both PRs were created and remain unmerged at the final snapshot. OpenSTA CLA is unsigned; Jenkins reports that the commit cannot be built. The recorded review comment is from an automated bot, not a human approval. The benchmark did not wait for these external statuses.', '']
    (stage.recovery.CAMPAIGN / 'SCIENTIFIC_SUMMARY.md').write_text('\n'.join(lines))
    print('MEASURED_SCIENTIFIC_SUMMARY_RECORDED', flush=True)


if __name__ == '__main__':
    main()
