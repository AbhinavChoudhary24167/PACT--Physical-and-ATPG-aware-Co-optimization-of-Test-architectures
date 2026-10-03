#!/usr/bin/env python3
"""Execute the pinned PR's real optimizer through the frozen native adapter.

Run with the external OpenROAD binary's embedded Python. No optimizer is
reimplemented here; the only optimization command is the compiled scan_opt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pact_oss_native
import odb
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def endpoint_geometry(path, names):
    database = odb.dbDatabase.create()
    odb.read_db(database, str(path))
    block = database.getChip().getBlock()
    result = {}
    for name in names:
        term = block.findBTerm(name)
        if term is None:
            raise ValueError('Physical scan endpoint missing: ' + name)
        shapes = []
        for pin in term.getBPins():
            for box in pin.getBoxes():
                shapes.append((box.getTechLayer().getName(), box.xMin(), box.yMin(), box.xMax(), box.yMax()))
        if not shapes:
            raise ValueError('Physical scan endpoint has no geometry: ' + name)
        result[name] = sorted(shapes)
    return result


def main(args):
    proof = args.output / 'qualification.json'
    if proof.exists():
        raise ValueError('Generator evidence already exists')
    # The exact successful B1 adapter's FF/placement/SI/SO tracing is reused.
    # optimize=True executes the actual binary's scan_opt after execute_dft_plan.
    pact_oss_native.run(args.design, args.source, args.output, args.liberty, optimize=True)
    physical = endpoint_geometry(args.source, ('test_si', 'test_so', 'test_si_1', 'test_so_1'))
    generated_ports = endpoint_geometry(args.output / 'generated.odb', ('test_si_0', 'test_so_0', 'test_si_1', 'test_so_1'))
    mapped = {(name + '_0' if name in ('test_si', 'test_so') else name): shapes for name, shapes in physical.items()}
    if mapped != generated_ports:
        raise ValueError('Generator endpoint translation changed physical geometry')
    generated = ScanArchitecture.from_json(args.output / 'architecture.json')
    reference = ScanArchitecture.from_json(pact_oss_native.ROOT / f'artifacts/derived/phase0c/{args.design}/s11/k2/B0.architecture.json')
    translated = ScanArchitecture(generated.cells, tuple(ScanChain(chain.chain_id, chain.cells,
        reference.chains[index].scan_in, reference.chains[index].scan_out)
        for index, chain in enumerate(generated.chains)))
    validate_scan(translated)
    if generated.cells != translated.cells or [c.cells for c in generated.chains] != [c.cells for c in translated.chains]:
        raise ValueError('Canonical translation changed FF inventory/order/membership')
    if {c.name: c for c in translated.cells} != {c.name: c for c in reference.cells}:
        raise ValueError('Canonical FF coordinates/domains differ')
    if sorted(map(lambda c: len(c.cells), translated.chains)) != sorted(map(lambda c: len(c.cells), reference.chains)):
        raise ValueError('Chain capacity/workload cycle count differs')
    translated.to_json(args.output / 'canonical.json')
    record = json.loads(proof.read_text())
    binary = Path('/proc/self/exe').resolve()
    record.update(method=args.method, source_commit=args.commit, binary_sha256=file_hash(binary),
                  binary_path=str(binary), canonical_architecture_hash=translated.sha256(),
                  generated_architecture_hash=generated.sha256(), compiled_optimizer_command='scan_opt',
                  canonical_translation_preserves_inventory_assignment_order=True,
                  frozen_native_adapter_sha256=file_hash(pact_oss_native.__file__),
                  generator_wrapper_sha256=file_hash(__file__),
                  original_physical_endpoint_geometry=physical,
                  generated_endpoint_geometry=generated_ports,
                  endpoint_geometry_unchanged=True,
                  canonical_endpoints={c.chain_id: dict(scan_in=c.scan_in, scan_out=c.scan_out) for c in translated.chains})
    proof.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('PINNED_OSS_GENERATOR_QUALIFIED', args.method, args.design, translated.sha256(), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', required=True, choices=('B2', 'B3'))
    parser.add_argument('--commit', required=True)
    parser.add_argument('--design', required=True, choices=('s5378', 's9234', 's15850'))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--liberty', type=Path, required=True)
    main(parser.parse_args())
