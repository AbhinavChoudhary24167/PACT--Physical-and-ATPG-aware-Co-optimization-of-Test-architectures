#!/usr/bin/env python3
"""Capacity-gated, generic source equivalence and Nangate45 mapping probe.

No PACT search, ATPG, placement, routing, or competitor result is read here.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time
import traceback

import pact_gate09_admission as admission
from pact_gate09_source import prepare, parse_bench

ROOT = admission.ROOT
LIB = Path('/root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib')
META = ROOT / 'results/pact_gate09_open_source_20261005'
RAW = Path('/mnt/d/PACT_EXPERIMENTS/results/pact_gate09_open_source_20261005')


def require_capacity(protocol):
    observed = {drive: dict(zip(('total', 'used', 'free'), shutil.disk_usage('/mnt/' + drive.lower())))
                for drive in ('C', 'D')}
    result = admission.capacity(protocol['resource_policy'], observed)
    if result['status'] != 'PASS':
        raise RuntimeError('PACT_GATE09_BLOCKED_CAPACITY: ' + json.dumps(result))
    return result


def execute_yosys(script, folder, protocol):
    gate = require_capacity(protocol)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'commands.ys').write_text(script)
    start = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    timed_out = False
    with (folder / 'stdout.txt').open('w') as out, (folder / 'stderr.txt').open('w') as err:
        process = subprocess.Popen(['/usr/bin/yosys', '-s', str(folder / 'commands.ys')], stdout=out, stderr=err,
                                   env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
        try:
            code = process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    record = dict(command=['/usr/bin/yosys', '-s', str(folder / 'commands.ys')],
                  script=admission.binding(folder / 'commands.ys'), exit_code=code, timed_out=timed_out,
                  wall_seconds=time.perf_counter() - start,
                  CPU_seconds=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                  child_peak_RSS_KiB=after.ru_maxrss, capacity=gate,
                  stdout=admission.binding(folder / 'stdout.txt'), stderr=admission.binding(folder / 'stderr.txt'))
    (folder / 'execution.json').write_text(json.dumps(record, indent=2) + '\n')
    if code or timed_out:
        raise RuntimeError('Source probe failed: ' + str(folder / 'execution.json'))
    return admission.binding(folder / 'execution.json')


def mapped_witness(mapped, model, design, adapter):
    module = mapped['modules'][design]
    flops = {name: row for name, row in module['cells'].items() if row['type'] == 'SDFF_X1'}
    expected = {row['scan_instance'] for row in adapter['source_FF_to_scan_instance']}
    if set(flops) != expected:
        raise ValueError('Mapped FF population changed')
    ports = module['ports']
    if set(ports) != set(model['inputs'] + model['outputs'] + ['CK', 'test_se', 'test_si', 'test_so']):
        raise ValueError('Mapped functional/scan port population changed')
    if any(len(row['bits']) != 1 for row in ports.values()):
        raise ValueError('Non-scalar mapped source interface')
    ppi = [f'__pact_ppi_{i:04d}' for i in range(len(model['flops']))]
    ppo = [f'__pact_ppo_{i:04d}' for i in range(len(model['flops']))]
    inports, outports = model['inputs'] + ppi, model['outputs'] + ppo
    bits = set()
    for cell in module['cells'].values():
        bits.update(bit for values in cell['connections'].values() for bit in values if isinstance(bit, int))
    bits.update(bit for row in ports.values() for bit in row['bits'] if isinstance(bit, int))
    lines = ['module gate(' + ', '.join(inports + outports) + ');', 'input ' + ', '.join(inports) + ';',
             'output ' + ', '.join(outports) + ';', 'wire ' + ', '.join(f'__pact_bit_{bit}' for bit in sorted(bits)) + ';']

    def token(bit):
        if isinstance(bit, int):
            return f'__pact_bit_{bit}'
        if bit not in ('0', '1'):
            raise ValueError('Unknown/dont-care bit in mapped functional witness')
        return "1'b" + bit

    for name in model['inputs']:
        lines.append(f'assign {token(ports[name]["bits"][0])} = {name};')
    for name in model['outputs']:
        lines.append(f'assign {name} = {token(ports[name]["bits"][0])};')
    previous = ports['test_si']['bits']
    for i, row in enumerate(adapter['source_FF_to_scan_instance']):
        cell = flops[row['scan_instance']]['connections']
        if cell['CK'] != ports['CK']['bits'] or cell['SE'] != ports['test_se']['bits'] or cell['SI'] != previous:
            raise ValueError('Mapped clock/scan chain semantics changed')
        if len(cell['D']) != 1 or len(cell['Q']) != 1 or not isinstance(cell['Q'][0], int):
            raise ValueError('Invalid mapped FF endpoint')
        lines.extend([f'assign {token(cell["Q"][0])} = {ppi[i]};',
                      f'assign {ppo[i]} = {token(cell["D"][0])};'])
        if cell.get('QN'):
            if len(cell['QN']) != 1 or not isinstance(cell['QN'][0], int):
                raise ValueError('Invalid complementary FF output')
            lines.append(f'assign {token(cell["QN"][0])} = ~{ppi[i]};')
        previous = cell['Q']
    if previous != ports['test_so']['bits']:
        raise ValueError('Mapped fixed SO does not terminate the source chain')
    for i, (name, cell) in enumerate(sorted(module['cells'].items())):
        if name in flops:
            continue
        kind = cell['type']
        if kind.startswith('$') or kind not in mapped['modules']:
            raise ValueError('Unsupported/unmapped cell in common backend: ' + kind)
        connections = []
        for pin, values in sorted(cell['connections'].items()):
            if len(values) != 1:
                raise ValueError('Non-scalar library pin')
            connections.append('.' + pin + '(' + token(values[0]) + ')')
        lines.append(f'{kind} __pact_cell_{i} (' + ', '.join(connections) + ');')
    return '\n'.join(lines + ['endmodule', '']), dict(FF_count=len(flops),
        cell_types=sorted({row['type'] for row in module['cells'].values()}),
        scan_eligible=True, source_chain_count=1, intended_chain_count=2,
        source_endpoints=['test_si', 'test_so'], clock='CK positive edge; single domain',
        unsupported_cells=[], macros=[])


def probe(design, audit_path):
    prereg = admission.read(admission.INTAKE)
    audited = admission.read(audit_path)
    if audited['provenance_status'] != 'PASS' or audited['capacity']['status'] != 'PASS':
        raise ValueError('Passing prelaunch provenance/capacity receipt required')
    if admission.verify(audited['protocol'])['status'] != 'PASS':
        raise ValueError('Preflight protocol binding changed')
    row = next(item for item in prereg['cohort'] if item['design'] == design)
    frozen_sources = {name: admission.verify(value) for name, value in prereg['frozen_sources'].items()}
    if any(value['status'] != 'PASS' for value in frozen_sources.values()):
        raise ValueError('Frozen PACT source mismatch')
    for value in row['source_files'].values():
        if admission.verify(value)['status'] != 'PASS':
            raise ValueError('Pinned source hash mismatch')
    yosys = audited['backend']['runtime_tree_observations']['Yosys_binary']
    if admission.verify(yosys)['status'] != 'PASS':
        raise ValueError('Preregistered mapping binary changed')
    physical = admission.read(ROOT / 'results/pact_cpu_scalability_20261005/spef_patch/implementation_evidence.json')
    if admission.verify(physical['bindings']['library'])['status'] != 'PASS':
        raise ValueError('Frozen Nangate45 Liberty changed')
    folder = RAW / 'sources' / design
    receipt = META / 'source_admission' / (design + '.json')
    if receipt.exists() or folder.exists():
        raise ValueError('Preserve completed or failed source probe; fresh attempt required')
    record = dict(schema='pact_gate09_source_admission_v1', design=design,
                  created_utc=datetime.now(timezone.utc).isoformat(), status='SOURCE_PROBE_STARTED',
                  protocol=admission.binding(admission.INTAKE), preflight=admission.binding(audit_path),
                  source_files=row['source_files'], adapter_source=admission.binding(ROOT / 'scripts/pact_gate09_source.py'),
                  runner_source=admission.binding(Path(__file__)), Yosys=yosys, Liberty=physical['bindings']['library'],
                  capacity=require_capacity(prereg), reference_qualified=False, PACT_search_started=False,
                  stages={}, qualification={})
    try:
        bench, blif = (admission.resolve(row['source_files'][kind]['path']) for kind in ('bench', 'blif'))
        adapter = prepare(bench, blif, design, folder)
        record['adapter'] = admission.binding(folder / 'adapter.json')
        if adapter['FF_count'] != row['source_FF_count']:
            raise ValueError('Source FF count differs from frozen intake')
        record['stages']['BENCH_BLIF_equivalence'] = execute_yosys(
            f'read_blif {folder}/blif_comb.blif\nread_verilog {folder}/bench_comb.v\n'
            'miter -equiv -flatten -make_outputs gold gate miter\nhierarchy -top miter\nopt_clean\n'
            'sat -verify -prove trigger 0\n', folder / 'next_state_equivalence', prereg)
        record['qualification']['BENCH_BLIF_next_state_equivalence'] = 'PASS_ALL_PPI_AND_FUNCTIONAL_INPUT_STATES'
        record['stages']['mapping'] = execute_yosys(
            f'read_liberty -lib {LIB}\nread_verilog {folder}/scan_input.v\nhierarchy -check -top {design}\n'
            f'proc\nopt_clean\ntechmap\nabc -liberty {LIB}\nclean\ncheck -assert\n'
            f'write_json {folder}/mapped.json\nwrite_verilog -noattr -noexpr {folder}/mapped.v\n', folder / 'mapping', prereg)
        model = parse_bench(bench.read_text())
        witness, topology = mapped_witness(admission.read(folder / 'mapped.json'), model, design, adapter)
        (folder / 'mapped_comb.v').write_text(witness)
        record['topology'] = topology
        record['stages']['mapped_equivalence'] = execute_yosys(
            f'read_liberty {LIB}\nread_verilog {folder}/bench_comb.v\nrename gate gold\nread_verilog {folder}/mapped_comb.v\n'
            'miter -equiv -flatten -make_outputs gold gate miter\nhierarchy -top miter\nflatten\nopt_clean\n'
            'sat -verify -prove trigger 0\n', folder / 'mapped_equivalence', prereg)
        record.update(status='SOURCE_MAPPED_EQUIVALENCE_QUALIFIED_PENDING_PHYSICAL_ATPG_REFERENCE',
                      mapped_netlist=admission.binding(folder / 'mapped.v'), mapped_json=admission.binding(folder / 'mapped.json'))
        record['qualification'].update(mapped_next_state='PASS_ALL_PPI_AND_FUNCTIONAL_INPUT_STATES',
                                        FF_inventory='PASS', source_scan_topology='PASS',
                                        placement='NOT_RUN', ATPG='NOT_RUN', reference='NOT_ADMITTED')
    except Exception as error:
        record.update(status='PACT_GATE09_SOURCE_ADMISSION_BLOCKED', error=str(error), traceback=traceback.format_exc())
    record['completed_utc'] = datetime.now(timezone.utc).isoformat()
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open('x') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    print(json.dumps(record, indent=2), flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.design, args.audit)
    raise SystemExit(0 if result['status'].startswith('SOURCE_MAPPED') else 2)
