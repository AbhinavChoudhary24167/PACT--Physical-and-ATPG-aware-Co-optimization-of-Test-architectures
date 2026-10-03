#!/usr/bin/env python3
"""Read-only integration check of translation geometry on sealed B1 databases."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pact_oss_generator import endpoint_geometry, file_hash

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path('/mnt/d/PACT_EXPERIMENTS/tmp/pact_oss_20261003')
OUT = ROOT / 'results/pact_oss_benchmark/recovery_20261003'


def main():
    destination = OUT / 'existing_B1_endpoint_geometry.json'
    if destination.exists():
        raise ValueError('Endpoint translation integration evidence already exists')
    results = {}
    for design in ('s5378', 's9234', 's15850'):
        generated = TEMP / 'B1_openroad_native' / design / 'generated.odb'
        expected = json.loads((ROOT / f'results/pact_oss_benchmark/baselines/B1_openroad_native/{design}/generated_artifacts.json').read_text())
        if file_hash(generated) != expected['generated.odb']['sha256']:
            raise ValueError('Saved qualified B1 generated ODB integrity failure')
        original = endpoint_geometry(TEMP / 'placed_common' / design / '3_place.odb', ('test_si', 'test_so', 'test_si_1', 'test_so_1'))
        actual = endpoint_geometry(generated, ('test_si_0', 'test_so_0', 'test_si_1', 'test_so_1'))
        mapped = {(name + '_0' if name in ('test_si', 'test_so') else name): shapes for name, shapes in original.items()}
        if mapped != actual:
            raise ValueError('Saved B1 translation changed endpoint geometry')
        results[design] = dict(status='PASS', original=original, translated=actual,
                               generated_odb_sha256=expected['generated.odb']['sha256'])
    destination.write_text(json.dumps(dict(status='PASS', designs=results,
        scope='Read-only existing B1 ODBs; no architecture regeneration or DFT commands',
        geometry_helper_sha256=file_hash(Path(__file__).with_name('pact_oss_generator.py')),
        fixed_backend_sha256=file_hash(Path('/proc/self/exe').resolve())), indent=2, sort_keys=True) + '\n')
    print('EXISTING_B1_ENDPOINT_GEOMETRY_PASS', len(results), flush=True)


if __name__ == '__main__':
    main()
