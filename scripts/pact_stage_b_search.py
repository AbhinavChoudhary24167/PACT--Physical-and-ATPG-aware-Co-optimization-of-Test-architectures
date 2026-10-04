#!/usr/bin/env python3
"""Run constrained Stage-B search from a portable input bundle."""
import argparse
from dataclasses import asdict
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from pact.optimizer import stage_b as solver
from pact.optimizer.candidate_stateful import METRICS
from pact.optimizer.stage_b_inputs import load_bundle
from pact.optimizer.io import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=300.)
    parser.add_argument('--max-evaluations', type=int, default=20000)
    parser.add_argument('--stagnation-attempts', type=int, default=2000)
    parser.add_argument('--epsilons', type=float, nargs='+', default=[.02, .05, .10])
    parser.add_argument('--weights', type=float, nargs=3, default=[1., 1., 1.])
    args = parser.parse_args()
    model, starts, reference = load_bundle(args.input)
    for epsilon in args.epsilons:
        folder = args.output/f'budget_{epsilon:.2f}'
        if (folder/'search.json').exists():
            raise ValueError('Search evidence exists; use a new output namespace')
        config = solver.Config(epsilon=epsilon, seconds=args.seconds,
            max_evaluations=args.max_evaluations, stagnation_attempts=args.stagnation_attempts,
            weights=tuple(args.weights))
        result = solver.optimize(model, starts, reference, config)
        for category in ('selected', 'baselines'):
            packaged = []
            for i, row in enumerate(result[category]):
                name = f'{category}_{i+1}'
                arch = model.architecture_from(row['orders']).canonical_dict()
                write_json(folder/'architectures'/f'{name}.json', arch)
                packaged.append({k: v for k, v in row.items() if k not in ('orders', 'score')} | dict(
                    architecture=f'architectures/{name}.json',
                    chain_sizes=list(map(len, row['orders'])),
                    metrics=dict(zip(METRICS, map(float, row['score'])))))
            result[category] = packaged
        result['reference_score'] = np.asarray(result['reference_score']).tolist()
        result['config'] = asdict(config)
        write_json(folder/'search.json', result)
        print(epsilon, result['evaluations'], result['termination'], flush=True)


if __name__ == '__main__':
    main()
