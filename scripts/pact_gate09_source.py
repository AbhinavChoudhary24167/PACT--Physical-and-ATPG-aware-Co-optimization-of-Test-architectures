#!/usr/bin/env python3
"""Strict sequential BENCH import and independent BLIF next-state witness.

This adapter adds the existing CK/test_se/test_si/test_so scan interface.
It does not change Boolean functions, DFF inventory, or optimize scan order.
Implicit BENCH DFF steps become one positive-edge CK domain. BLIF initial
values are recorded; the equivalence witness quantifies over every PPI state.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*$')
GATES = {'AND', 'NAND', 'OR', 'NOR', 'XOR', 'XNOR', 'NOT', 'BUFF', 'BUF', 'DFF'}
RESERVED = {'CK', 'test_se', 'test_si', 'test_so'}


def parse_bench(text):
    inputs, outputs, assignments = [], [], {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        port = re.fullmatch(r'(INPUT|OUTPUT)\s*\(\s*(\w+)\s*\)', line)
        if port:
            (inputs if port[1] == 'INPUT' else outputs).append(port[2])
            continue
        match = re.fullmatch(r'(\w+)\s*=\s*(\w+)\s*\(([^()]*)\)', line)
        if not match:
            raise ValueError(f'Unsupported BENCH syntax at line {number}: {line}')
        name, kind, argtext = match.groups()
        args = tuple(arg.strip() for arg in argtext.split(','))
        kind = kind.upper()
        if kind not in GATES or name in assignments or not args or any(not IDENT.fullmatch(arg) for arg in args):
            raise ValueError(f'Unsupported gate, duplicate driver or net at line {number}')
        if kind in {'NOT', 'BUF', 'BUFF', 'DFF'} and len(args) != 1:
            raise ValueError(f'Unary gate arity at line {number}')
        assignments[name] = (kind, args)
    names = set(inputs) | set(outputs) | set(assignments)
    if any(not IDENT.fullmatch(n) for n in names) or names & RESERVED or any(n.startswith('__pact_') for n in names):
        raise ValueError('Unsupported or reserved identifier collision')
    if len(inputs) != len(set(inputs)) or len(outputs) != len(set(outputs)) or set(inputs) & set(assignments):
        raise ValueError('Duplicate ports or input driven internally')
    for name, (_, args) in assignments.items():
        if any(arg not in set(inputs) | set(assignments) for arg in args):
            raise ValueError('Undriven net at ' + name)
    if any(name not in set(inputs) | set(assignments) for name in outputs):
        raise ValueError('Undriven output')
    # Reject combinational cycles without treating DFF feedback as a cycle.
    done = set(inputs) | {name for name, (kind, _) in assignments.items() if kind == 'DFF'}
    pending = set(assignments) - done
    while pending:
        ready = {name for name in pending if set(assignments[name][1]) <= done}
        if not ready:
            raise ValueError('Combinational cycle')
        done.update(ready)
        pending.difference_update(ready)
    flops = sorted(name for name, (kind, _) in assignments.items() if kind == 'DFF')
    if not flops:
        raise ValueError('Sequential design required')
    return dict(inputs=inputs, outputs=outputs, assignments=assignments, flops=flops)


def expression(kind, args):
    if kind in ('BUF', 'BUFF'):
        return args[0]
    if kind == 'NOT':
        return '~' + args[0]
    op = '&' if kind in ('AND', 'NAND') else '|' if kind in ('OR', 'NOR') else '^'
    term = '(' + (' ' + op + ' ').join(args) + ')'
    return '~' + term if kind in ('NAND', 'NOR', 'XNOR') else term


def emit_bench(model, top, scan=False):
    if not IDENT.fullmatch(top):
        raise ValueError('Invalid module identity')
    ppi = [f'__pact_ppi_{i:04d}' for i in range(len(model['flops']))]
    ppo = [f'__pact_ppo_{i:04d}' for i in range(len(model['flops']))]
    inputs = model['inputs'] + (['CK', 'test_se', 'test_si'] if scan else ppi)
    outputs = model['outputs'] + (['test_so'] if scan else ppo)
    lines = ['module ' + top + '(' + ', '.join(inputs + outputs) + ');',
             'input ' + ', '.join(inputs) + ';', 'output ' + ', '.join(outputs) + ';']
    wires = sorted(set(model['assignments']) - set(outputs))
    if wires:
        lines.append('wire ' + ', '.join(wires) + ';')
    for name, (kind, args) in model['assignments'].items():
        if kind != 'DFF':
            lines.append('assign ' + name + ' = ' + expression(kind, args) + ';')
    for i, q in enumerate(model['flops']):
        d = model['assignments'][q][1][0]
        if scan:
            si = 'test_si' if i == 0 else model['flops'][i - 1]
            lines.append(f'(* keep = 1 *) SDFF_X1 U_SCAN_{i:04d} (.D({d}), .CK(CK), .SE(test_se), .SI({si}), .Q({q}), .QN());')
        else:
            lines.extend([f'assign {q} = {ppi[i]};', f'assign {ppo[i]} = {d};'])
    if scan:
        lines.append('assign test_so = ' + model['flops'][-1] + ';')
    return '\n'.join(lines + ['endmodule', ''])


def blif_witness(text, model):
    # Normalize continuation lines, keeping truth tables unchanged.
    logical = re.sub(r'\\\s*\n', ' ', text).splitlines()
    latches, retained = {}, []
    ports = {}
    for raw in logical:
        line = raw.split('#', 1)[0].strip()
        fields = line.split()
        if not fields:
            continue
        tag = fields[0]
        if tag == '.model':
            continue
        if tag in ('.inputs', '.outputs'):
            if tag in ports:
                raise ValueError('Multiple BLIF port declarations')
            ports[tag] = fields[1:]
        elif tag == '.latch':
            if len(fields) != 4 or fields[2] in latches or fields[3] not in ('0', '1', '2', '3'):
                raise ValueError('Only implicit-step BLIF DFFs supported')
            latches[fields[2]] = dict(D=fields[1], initial=fields[3])
        elif tag == '.end':
            continue
        elif tag.startswith('.') and tag != '.names':
            raise ValueError('Unsupported BLIF directive: ' + tag)
        else:
            retained.append(raw)
    if set(ports.get('.inputs', [])) != set(model['inputs']):
        raise ValueError('BENCH/BLIF functional input population differs')
    # Exporters may give a public output and its internal signal different
    # names. Accept only an explicit positive identity truth-table path, never
    # a guessed suffix/name substitution or a general logic transformation.
    buffers = {}
    for i, raw in enumerate(logical):
        fields = raw.split('#', 1)[0].split()
        if len(fields) == 3 and fields[0] == '.names':
            table = []
            for following in logical[i + 1:]:
                cube = following.split('#', 1)[0].split()
                if cube and cube[0].startswith('.'):
                    break
                if cube:
                    table.append(cube)
            if table == [['1', '1']]:
                if fields[2] in buffers:
                    raise ValueError('Duplicate BLIF identity driver')
                buffers[fields[2]] = fields[1]
    aliases = {}
    for public in ports.get('.outputs', []):
        current, path = public, [public]
        while current not in set(model['outputs']) and current in buffers:
            current = buffers[current]
            if current in path:
                raise ValueError('BLIF output alias cycle')
            path.append(current)
        if current not in model['outputs'] or current in aliases:
            raise ValueError('BENCH/BLIF functional output population differs; no bijective explicit identity alias')
        aliases[current] = dict(BLIF_port=public, identity_path=path)
    if set(aliases) != set(model['outputs']):
        raise ValueError('BENCH/BLIF functional output population differs')
    if set(latches) != set(model['flops']):
        raise ValueError('BENCH/BLIF state population differs')
    for q in model['flops']:
        if latches[q]['D'] != model['assignments'][q][1][0]:
            raise ValueError('BENCH/BLIF DFF next-state endpoint differs: ' + q)
    ppi = [f'__pact_ppi_{i:04d}' for i in range(len(model['flops']))]
    ppo = [f'__pact_ppo_{i:04d}' for i in range(len(model['flops']))]
    lines = ['.model gold', '.inputs ' + ' '.join(model['inputs'] + ppi),
             '.outputs ' + ' '.join(model['outputs'] + ppo)] + retained
    for i, q in enumerate(model['flops']):
        lines.extend([f'.names {ppi[i]} {q}', '1 1',
                      f'.names {latches[q]["D"]} {ppo[i]}', '1 1'])
    return '\n'.join(lines + ['.end', '']), latches, aliases


def prepare(bench, blif, design, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Fresh source-witness directory required')
    model = parse_bench(Path(bench).read_text())
    golden, latches, aliases = blif_witness(Path(blif).read_text(), model)
    output.mkdir(parents=True)
    for name, text in (('bench_comb.v', emit_bench(model, 'gate')),
                       ('blif_comb.blif', golden), ('scan_input.v', emit_bench(model, design, True))):
        (output / name).write_text(text)
    receipt = dict(schema='pact_gate09_source_adapter_v1', design=design,
                   status='STATIC_SOURCE_CHECK_PASS_PENDING_FORMAL_AND_MAPPING',
                   FF_count=len(model['flops']), inputs=len(model['inputs']), outputs=len(model['outputs']),
                   source_cell_histogram=dict(Counter(kind for kind, _ in model['assignments'].values())),
                   source_FF_to_scan_instance=[dict(Q=q, D=model['assignments'][q][1][0], scan_instance=f'U_SCAN_{i:04d}')
                                               for i, q in enumerate(model['flops'])],
                   source_initial_state_histogram=dict(Counter(row['initial'] for row in latches.values())),
                   functional_output_aliases=aliases,
                   adaptation=dict(clock='Single positive-edge CK; explicit physical interpretation of implicit BENCH/BLIF state steps',
                                   scan='SE=0 retains source D/Q equations; SE=1 shifts all source FFs in lexical Q-name order; original K=1 source before registered K=2 baselines',
                                   reset='No reset inserted; BLIF initial values recorded; all PPI states quantified in next-state witness',
                                   modifications='Scan/clock interface and explicit Nangate45 SDFF_X1 representation only; combinational equations unchanged'),
                   qualification=dict(next_state_equivalence=False, mapped_equivalence=False, placement=False, ATPG=False))
    (output / 'adapter.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bench', type=Path, required=True)
    parser.add_argument('--blif', type=Path, required=True)
    parser.add_argument('--design', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.bench, args.blif, args.design, args.output), indent=2))


if __name__ == '__main__':
    main()
