#!/usr/bin/env python3
"""Frozen generator plus independent read-only ODB/Verilog/metadata checks."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pact_oss_generator import main as generate
from pact_oss_receiver_connectivity import observe
import odb


def pins(path):
    database = odb.dbDatabase.create()
    odb.read_db(database, str(path))
    block = database.getChip().getBlock()
    instances = {}
    terms = {}
    for inst in block.getInsts():
        name = inst.getName()
        instances[name] = (inst.getMaster().getName(), list(inst.getLocation()), str(inst.getOrient()))
        for term in inst.getITerms():
            pin = term.getMTerm().getName()
            if inst.getMaster().getName() == 'SDFF_X1' and pin in ('SI', 'SE'):
                continue
            terms[name + '/' + pin] = term.getNet().getName() if term.getNet() else None
    return instances, terms


def verilog_paths(path):
    text = path.read_text()
    cells = {}
    for name, body in re.findall(r'\bSDFF_X1\s+(\S+)\s*\((.*?)\);', text, re.S):
        cells[name] = dict(re.findall(r'\.(\w+)\s*\(\s*([^()]+?)\s*\)', body))
    aliases = dict(re.findall(r'\bassign\s+(\S+)\s*=\s*(\S+)\s*;', text))
    def resolve(net):
        seen = set()
        while net in aliases:
            if net in seen:
                raise ValueError('Verilog alias cycle')
            seen.add(net)
            net = aliases[net]
        return net
    consumers = {}
    for name, item in cells.items():
        consumers.setdefault(resolve(item['SI']), []).append(name)
    buffers = {}
    for name, body in re.findall(r'\bBUF_\w+\s+(\S+)\s*\((.*?)\);', text, re.S):
        item = dict(re.findall(r'\.(\w+)\s*\(\s*([^()]+?)\s*\)', body))
        buffers.setdefault(resolve(item['A']), []).append(resolve(item['Z']))
    paths = []
    for ci in range(2):
        net, so = resolve(f'test_si_{ci}'), resolve(f'test_so_{ci}')
        order, seen = [], set()
        while True:
            if net in seen:
                raise ValueError('Verilog path cycle')
            seen.add(net)
            matches = consumers.get(net, [])
            if matches:
                if len(matches) != 1:
                    raise ValueError('Verilog scan fork')
                order.append(matches[0])
                net = resolve(cells[matches[0]]['Q'])
            elif net == so:
                break
            elif len(buffers.get(net, [])) == 1:
                net = buffers[net][0]
            else:
                raise ValueError('Verilog fixed SO is unreachable')
        paths.append(order)
    if Counter(n for chain in paths for n in chain) != Counter(iter(cells)):
        raise ValueError('Verilog membership/duplicate/orphan failure')
    return paths


def main(args):
    generate(args)
    before = args.output / 'generator_input.odb'
    after = args.output / 'generated.odb'
    observation = observe(after)
    traces = observation['traces']
    if any(t['error'] for t in traces):
        raise ValueError('Saved ODB topology failure')
    physical = [t['ff_order'] for t in traces]
    metadata = {m['name']: list(reversed(m['list_iteration'])) for m in observation['scan_metadata']}
    for i, chain in enumerate(physical):
        if metadata[f'chain_{i}'] != chain:
            raise ValueError('Metadata order differs from ODB order')
    verilog = verilog_paths(args.output / 'generated.v')
    if physical != verilog:
        raise ValueError('Verilog order differs from ODB order')
    if pins(before) != pins(after):
        raise ValueError('Functional fanout/unrelated nets/master/placement/orientation changed')
    counts = Counter(n for chain in physical for n in chain)
    if set(counts) != set(observation['cells']) or any(v != 1 for v in counts.values()):
        raise ValueError('ODB duplicate/orphan membership')
    canonical = json.loads((args.output / 'canonical.json').read_text())
    if [c['cells'] for c in canonical['chains']] != physical:
        raise ValueError('Canonical order differs from independently observed graph')
    proof = json.loads((args.output / 'qualification.json').read_text())
    binary = Path('/proc/self/exe').resolve()
    if proof['binary_sha256'] != hashlib.sha256(binary.read_bytes()).hexdigest():
        raise ValueError('Executing binary identity differs')
    record = dict(status='PASS', method=args.method, design=args.design, source_commit=args.commit,
        binary_sha256=proof['binary_sha256'], FF_count=len(counts), K=2,
        chain_lengths=[len(chain) for chain in physical],
        SI='PASS', internal_connectivity='PASS', SO='PASS',
        exact_membership_once=True, no_cycles_forks_orphans=True,
        metadata_ODB_Verilog_agreement=True,
        metadata_convention='Reverse of dbScanList iteration is logical SI-to-SO order',
        FF_master_placement_orientation_D_CK_Q_QN_functional_fanout_and_unrelated_nets_unchanged=True,
        endpoint_geometry_unchanged=proof['endpoint_geometry_unchanged'],
        chains=physical, endpoint_nets={name: item['name'] for name, item in observation['ports'].items()},
        source_ODB_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),
        generated_ODB_sha256=hashlib.sha256(after.read_bytes()).hexdigest(),
        generated_Verilog_sha256=hashlib.sha256((args.output / 'generated.v').read_bytes()).hexdigest())
    (args.output / 'semantic_qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('NATIVE_ENDPOINT_AND_REPRESENTATION_QUALIFICATION_PASS', args.design, record['chain_lengths'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', required=True, choices=('B3S','B3T'))
    parser.add_argument('--commit', required=True)
    parser.add_argument('--design', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--liberty', type=Path, required=True)
    main(parser.parse_args())
