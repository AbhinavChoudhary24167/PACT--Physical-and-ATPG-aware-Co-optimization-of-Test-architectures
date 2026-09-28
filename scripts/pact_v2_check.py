"""Verify saved new architectures and baseline FF replay against stored evidence.

Read-only with respect to all historical files; no simulation or route campaign.
"""
import argparse
import csv
from pathlib import Path
import time
import numpy as np
from pact_v2 import ROOT, DESIGNS, load, read, write_json, reference, ScanArchitecture, METRICS, file_sha256


def check(output):
    results = []
    for design, role in DESIGNS.items():
        started = time.perf_counter()
        model, starts, _, _ = load(design)
        search = read(output/design/'search.json')
        inputs = read(output/design/'inputs.json')
        for value in inputs['inputs'].values():
            if file_sha256(Path(value['path'])) != value['sha256']:
                raise ValueError('Search input changed: '+value['path'])
        _, counts = reference(model, starts[0][1], True)
        totals = counts.sum(axis=(0, 1, 2))
        old = list(csv.DictReader((ROOT/'reports/physical_effect'/design/role/'net_activity_capacitance.csv').open()))
        recorded = {r['source']: int(r['transitions']) for r in old}
        for i, name in enumerate(model.names):
            if int(totals[i]) != recorded[name+'/Q']:
                raise ValueError('Stored Q transition count disagrees: '+name)
        baseline_hashes = {model.architecture_from(o).sha256() for _, o in starts}
        for row in search['selected']:
            arch = ScanArchitecture.from_json(Path(row['architecture']))
            if arch.sha256() != row['architecture_sha256'] or arch.sha256() in baseline_hashes:
                raise ValueError('Selected architecture is changed or not new')
            score = reference(model, model.orders(arch))
            np.testing.assert_allclose(score, [row['metrics'][k] for k in METRICS], rtol=1e-12, atol=1e-7)
            if score[0] > search['wire_ceiling_um']+1e-8 or score[3] > search['timing_ceiling_um']+1e-8:
                raise ValueError('Selected architecture violates constraints')
        results.append(dict(design=design, status='PASS', stored_Q_totals_checked=len(model.names),
                            selected_reproduced=len(search['selected']), seconds=time.perf_counter()-started))
        print('REPLAY_CHECK', results[-1], flush=True)
    write_json(output/'reproducibility.json', results)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT/'results/pact_v2')
    check(p.parse_args().output.resolve())
