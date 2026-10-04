#!/usr/bin/env python3
"""Verify saved evidence and replay portable inputs; no search or EDA execution."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from pact.optimizer.candidate_stateful import State, reference
from pact.optimizer.stage_b_inputs import load_bundle
from pact.scan.model import ScanArchitecture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', choices=['s5378', 's9234', 's15850'])
    args = parser.parse_args()
    manifest = ROOT / 'reports/repository_cleanup/retained_evidence_sha256.json'
    hashes = json.loads(manifest.read_text())
    normalization = json.loads((manifest.parent / 'path_metadata_normalization.json').read_text())['files']
    for relative, record in normalization.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != record['public_sha256']:
            raise ValueError('Changed portable metadata export: ' + relative)
    for relative, expected in hashes.items():
        path = ROOT / relative
        if relative in normalization:
            if expected != normalization[relative]['original_sha256']:
                raise ValueError('Original evidence binding differs: ' + relative)
            expected = normalization[relative]['public_sha256']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Missing or changed retained evidence: ' + relative)
    export = ROOT / 'results/stage_a'
    for name, expected in json.loads((export / 'checksums.json').read_text()).items():
        if hashlib.sha256((export / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Changed Stage-A export: ' + name)
        with (export / name).open(encoding='utf-8-sig') as stream:
            public = list(csv.DictReader(stream))
        source = ROOT / 'results/pact_oss_benchmark/topology_recovery_20261004/stage_a' / name
        with source.open(encoding='utf-8-sig') as stream:
            original = list(csv.DictReader(stream))
        if public != [{key: row[key] for key in public[0]} for row in original]:
            raise ValueError('Stage-A export differs from original results: ' + name)
    with (ROOT / 'results/pact_stage_b/candidate_results.csv').open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    checked = 0
    for design in ([args.design] if args.design else ['s5378', 's9234', 's15850']):
        model, starts, ref = load_bundle(ROOT / f'results/pact_stage_b/inputs/{design}.json.gz')
        if ref not in {label for label, _ in starts}:
            raise ValueError('Missing physical reference')
        for label, orders in starts:
            model.validate(orders)
            np.testing.assert_allclose(State(model, orders).score(), reference(model, orders), rtol=1e-9, atol=1e-6)
            checked += 1
        for path in sorted((ROOT / 'results/pact_stage_b/architectures').glob(design + '_C*.json')):
            architecture = ScanArchitecture.from_json(path)
            orders = model.orders(architecture)
            model.validate(orders)
            score = reference(model, orders)
            row = next(r for r in rows if r['candidate'] == path.stem)
            expected = [float(row[k]) for k in ('proxy_wire_um', 'proxy_E', 'proxy_H8', 'proxy_H4')]
            np.testing.assert_allclose(score[[0, 1, 2, 4]], expected, rtol=1e-9, atol=1e-6)
            np.testing.assert_allclose(State(model, orders).score(), score, rtol=1e-9, atol=1e-6)
            checked += 1
        print(design, 'PASS', flush=True)
    normalized = len(set(hashes) & set(normalization))
    print(f'PASS: {len(hashes)} retained evidence bindings ({len(hashes)-normalized} unchanged original hashes, '
          f'{normalized} audited portable metadata exports); {checked} architecture replays')


if __name__ == '__main__':
    main()
