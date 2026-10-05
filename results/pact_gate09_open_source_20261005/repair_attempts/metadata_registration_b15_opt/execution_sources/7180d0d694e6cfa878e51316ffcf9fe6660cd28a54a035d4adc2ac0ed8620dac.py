#!/usr/bin/env python3
"""Extend qualified exact measurement registry to preregistered Gate-09 methods.

The original reference harness and every completed receipt remain unchanged.
Only lookup of common qualified artifact rows and campaign metadata differ.
"""
import argparse
import inspect
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_measure as frozen


def namespace():
    result = dict(frozen.__dict__, __file__=__file__)
    old = "    record = next(row for row in admission.read(meta / f'baselines/{design}_references.json')['records']\n                  if row['method'] == method)\n"
    new = "    registry = meta / f'baselines/{design}_references.json' if method in ('B0', 'B1', 'B2', 'B3T') else meta / f'baselines/{design}_{method}.json'\n    records = admission.read(registry)\n    record = next(row for row in records['records'] if row['method'] == method) if 'records' in records else records\n"
    row = inspect.getsource(frozen.reference_row)
    if row.count(old) != 1:
        raise ValueError('Qualified artifact lookup bridge no longer matches')
    exec(compile(row.replace(old, new, 1), '<Gate09-common-artifact-registry>', 'exec'), result)
    for function, expression in ((frozen.prepare, "method.startswith('CS_C')"),
                                 (frozen.worker, "args.method.startswith('CS_C')")):
        source = inspect.getsource(function)
        if source.count('PACT_search_started=False') != 1:
            raise ValueError('Qualified campaign metadata bridge no longer matches')
        source = source.replace('PACT_search_started=False', 'PACT_search_started='+expression, 1)
        exec(compile(source, '<Gate09-common-measurement-metadata>', 'exec'), result)
    # run() calls prepare indirectly through worker globals, and reference_row
    # through prepare globals. Rebind its identical source without editing it.
    exec(compile(inspect.getsource(frozen.run), '<Gate09-identical-CPU-run>', 'exec'), result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--method', choices=('B0', 'B1', 'B2', 'B3T', 'B4', 'B5', 'CS_C1', 'CS_C2', 'CS_C3'), required=True)
    parser.add_argument('--source-admission', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    args = parser.parse_args()
    result = namespace()['worker'](args)
    raise SystemExit(0 if result['completed'] else 2)
