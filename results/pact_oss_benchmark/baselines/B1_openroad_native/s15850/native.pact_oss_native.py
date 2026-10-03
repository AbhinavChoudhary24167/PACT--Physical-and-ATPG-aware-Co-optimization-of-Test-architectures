#!/usr/bin/env python3
"""Observe actual native DFT ordering in a disposable, common placed database.

Run with openroad -python. No scan_replace, placement, routing, or ATPG is run.
"""
import argparse
import json
from pathlib import Path
import sys

import odb
from openroad import Design, Tech

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan


def run(design_name, source, output, liberty, optimize=False):
    reference = ScanArchitecture.from_json(ROOT / f'artifacts/derived/phase0c/{design_name}/s11/k2/B0.architecture.json')
    output.mkdir(parents=True, exist_ok=True)
    proof = output / 'qualification.json'
    if proof.exists():
        raise ValueError('Native probe already exists')
    # Rename in a standalone ODB before constructing STA's network. Renaming
    # after readDb leaves STA's cached port identities stale in this binary.
    database = odb.dbDatabase.create()
    odb.read_db(database, str(source))
    block = database.getChip().getBlock()
    expected = {c.name for c in reference.cells}
    ff = {i.getName(): i for i in block.getInsts() if i.getMaster().getName() == 'SDFF_X1'}
    if set(ff) != expected:
        raise ValueError('Source FF inventory mismatch')
    original = {n: dict(master=i.getMaster().getName(), location=list(i.getLocation()),
                        orientation=str(i.getOrient()),
                        functional={p: i.findITerm(p).getNet().getName() if i.findITerm(p).getNet() else None for p in ('D', 'CK')})
                for n, i in ff.items()}
    # The existing K=2 rewiring adapter already fixes all physical endpoint shapes.
    # Rename only chain-0 BTerms to the indexed pattern required by native DFT.
    endpoint_translation = {}
    for old, new in (('test_si', 'test_si_0'), ('test_so', 'test_so_0')):
        term = block.findBTerm(old)
        if term is None or block.findBTerm(new) is not None:
            raise ValueError('Unexpected fixed endpoint inventory')
        endpoint_translation[new] = old
        if not term.rename(new):
            raise ValueError('Could not rename native endpoint: ' + old)
    for name in ('test_si_1', 'test_so_1'):
        if block.findBTerm(name) is None:
            raise ValueError('K=2 endpoint missing: ' + name)
        endpoint_translation[name] = name
    generator_input = output / 'generator_input.odb'
    odb.write_db(database, str(generator_input))
    tech = Tech()
    tech.readLiberty(str(liberty))
    design = Design(tech)
    design.readDb(str(generator_input))
    block = design.getBlock()
    ff = {i.getName(): i for i in block.getInsts() if i.getMaster().getName() == 'SDFF_X1'}
    max_length = max(map(lambda c: len(c.cells), reference.chains))
    commands = [
        f'read_sdc /root/pact-deps/OpenROAD-flow-scripts/flow/results/nangate45/{"s9234f" if design_name == "s9234" else design_name}/phase0b_s11_B0/3_place.sdc',
        f'set_dft_config -max_chains 2 -max_length {max_length} -clock_mixing no_mix '
        '-scan_enable_name_pattern test_se -scan_in_name_pattern test_si_{} -scan_out_name_pattern test_so_{}',
        'report_dft_config', 'report_dft_plan -verbose', 'execute_dft_plan']
    if optimize:
        commands.append('scan_opt')
    for command in commands:
        print('BENCHMARK_COMMAND', command, flush=True)
        design.evalTclString(command)
    odb.write_db(design.getDb(), str(output / 'generated.odb'))
    design.evalTclString(f'write_verilog {output}/generated.v')
    current = {n: dict(master=i.getMaster().getName(), location=list(i.getLocation()),
                       orientation=str(i.getOrient()),
                       functional={p: i.findITerm(p).getNet().getName() if i.findITerm(p).getNet() else None for p in ('D', 'CK')})
               for n, i in ff.items()}
    if original != current:
        raise ValueError('Native DFT changed FF masters, placement or functional D/CK nets')
    chains = []
    for ci in range(2):
        input_name, output_name = f'test_si_{ci}', f'test_so_{ci}'
        net = block.findBTerm(input_name).getNet()
        observed = []
        seen_nets = set()
        # Native can keep a scan input/output buffer; walk transparent buffers exactly.
        while True:
            if net.getName() in seen_nets:
                raise ValueError('Scan path loop')
            seen_nets.add(net.getName())
            matches = [n for n, i in ff.items() if i.findITerm('SI').getNet() == net]
            if len(matches) > 1:
                raise ValueError('Branched native scan path')
            if matches:
                name = matches[0]
                if name in observed:
                    raise ValueError('Repeated FF')
                observed.append(name)
                net = ff[name].findITerm('Q').getNet()
                continue
            if block.findBTerm(output_name).getNet() == net:
                break
            buffers = [t.getInst() for t in net.getITerms()
                       if t.getMTerm().getName() == 'A' and t.getInst().getMaster().getName().startswith('BUF_')]
            if len(buffers) != 1:
                raise ValueError('Cannot faithfully trace native SI/SO connectivity')
            net = buffers[0].findITerm('Z').getNet()
        chains.append(ScanChain(reference.chains[ci].chain_id, tuple(observed),
                                endpoint_translation[input_name], endpoint_translation[output_name]))
    architecture = ScanArchitecture(reference.cells, tuple(chains))
    validate_scan(architecture)
    if len(architecture.chains) != 2 or sorted(map(len, (c.cells for c in architecture.chains))) != sorted(map(len, (c.cells for c in reference.chains))):
        raise ValueError('Native chain capacity changes the frozen workload cycle count')
    architecture.to_json(output / 'architecture.json')
    proof.write_text(json.dumps(dict(status='PASS', design=design_name, commands=commands,
                                    architecture_sha256=architecture.sha256(), FF_count=len(expected), K=2,
                                    chain_lengths=[len(c.cells) for c in chains], endpoint_translation=endpoint_translation,
                                    FF_placement_and_functional_inputs_unchanged=True,
                                    source=str(source), liberty='existing verified test_cell-only annotation; downstream unchanged'),
                                indent=2, sort_keys=True) + '\n')
    print('CANONICAL_NATIVE_PASS', architecture.sha256(), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--design', required=True, choices=('s5378', 's9234', 's15850'))
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--liberty', required=True, type=Path)
    parser.add_argument('--optimize', action='store_true')
    args = parser.parse_args()
    run(args.design, args.source, args.output, args.liberty, args.optimize)
