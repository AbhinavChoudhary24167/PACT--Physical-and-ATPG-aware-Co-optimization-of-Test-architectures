"""Plot exact prospective outcomes and observed search throughput, without fits."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'scratch/cold_start_matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm


def figures(source, destination):
    data = json.loads(source.read_text())
    destination.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False})
    rows = [r for r in data['prospective_unseen_records']
            if r['record_kind'] == 'PROSPECTIVE_PACT_CANDIDATE'
            and r['qualification_status'] == 'QUALIFIED' and r['activity_relations']]
    files = []
    if rows:
        metrics = ('routed_WL', 'E', 'H4', 'H8')
        values = np.array([[r['delta_' + m + '_percent'] for m in metrics] for r in rows])
        limit = max(1., np.max(np.abs(values)))
        fig, ax = plt.subplots(figsize=(9, max(4.5, len(rows) * .43 + 1.8)))
        heat = ax.imshow(values, cmap='RdBu_r', norm=TwoSlopeNorm(0, -limit, limit), aspect='auto')
        ax.set_xticks(range(4), ['Routed scan WL', 'E', 'H4', 'H8'])
        labels = [r['design'] + ' / ' + r['candidate'] + ('  (primary)' if r['preselected_primary'] else '') for r in rows]
        ax.set_yticks(range(len(rows)), labels)
        for label, row in zip(ax.get_yticklabels(), rows):
            if row['preselected_primary']:
                label.set_fontweight('bold')
        for i in range(len(rows)):
            for j in range(4):
                ax.text(j, i, f'{values[i, j]:+.2f}%', ha='center', va='center',
                        color='white' if abs(values[i, j]) > limit * .6 else 'black')
        ax.set_title('Exact prospective tradeoffs against each frozen external reference', pad=16)
        fig.colorbar(heat, ax=ax, label='Change from reference (%)', shrink=.85)
        fig.text(.02, .025, 'Negative values improve the metric. Every retained qualified candidate is shown; primary choices were frozen before routing.', fontsize=9)
        fig.tight_layout(rect=(0, .06, 1, 1))
        for suffix in ('png', 'svg'):
            path = destination / ('exact_activity_tradeoffs.' + suffix)
            fig.savefig(path, dpi=180, bbox_inches='tight'); files.append(path)
        plt.close(fig)
    lanes = data['solver_scalability']
    designs = list(dict.fromkeys(r['design'] for r in lanes))
    if designs:
        fig, ax = plt.subplots(figsize=(10, 5))
        width = .24
        colors = ('#355C91', '#4C927D', '#A56B32')
        for offset, epsilon in enumerate((.02, .05, .10)):
            y = [next((r['exact_mutation_evaluations_per_second'] for r in lanes
                       if r['design'] == d and r['epsilon'] == epsilon), np.nan) for d in designs]
            x = np.arange(len(designs)) + (offset - 1) * width
            ax.scatter(x, y, label=f'epsilon {epsilon:.2f}', color=colors[offset], s=65)
            for location, value in zip(x, y):
                if np.isfinite(value):
                    ax.annotate(f'{value:.2f}', (location, value),
                                xytext=(0, 8), textcoords='offset points', ha='center', fontsize=8)
        labels = []
        for design in designs:
            row = next(r for r in lanes if r['design'] == design)
            labels.append(f"{design}\n{row['FF_count']:,} FFs / {row['ATPG_pattern_count']} patterns")
        ax.set_xticks(range(len(designs)), labels)
        ax.set_yscale('log'); ax.set_ylabel('Exact mutation evaluations per second (log scale)')
        ax.set_title('Observed cold-start search throughput')
        ax.legend(loc='upper right', frameon=False)
        ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True)
        ax.set_ylim(top=max(r['exact_mutation_evaluations_per_second'] for r in lanes) * 2)
        fig.text(.02, .02, 'Concurrent execution on the same host. Wire-screened proposals are excluded. No scalability fit or extrapolation.', fontsize=9)
        fig.tight_layout(rect=(0, .05, 1, 1))
        for suffix in ('png', 'svg'):
            path = destination / ('observed_solver_throughput.' + suffix)
            fig.savefig(path, dpi=180, bbox_inches='tight'); files.append(path)
        plt.close(fig)
    receipt = {'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
               'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'matplotlib_version': matplotlib.__version__, 'numpy_version': np.__version__,
               'exact_qualified_candidate_rows': len(rows), 'completed_lane_rows': len(lanes),
               'fits_or_extrapolations': 0,
               'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (destination / 'figure_provenance.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'figures': len(files), 'candidate_rows': len(rows), 'lane_rows': len(lanes)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    figures(args.source, args.output)
