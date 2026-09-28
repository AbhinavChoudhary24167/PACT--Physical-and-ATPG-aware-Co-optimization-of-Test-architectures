#!/usr/bin/env python3
"""Frozen nine-architecture physical experiment. No optimizer is executed."""
import argparse
import csv
import gzip
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact.scan.model import ScanArchitecture
from pact.integration.patterns import fan_workload, serialize
from pact.analysis.phase2b_reference import parse_spef

OUT = Path(os.environ.get('PACT_PHYSICAL_EFFECT_OUT', ROOT / 'reports/physical_effect'))
FLOW = Path('/root/pact-deps/OpenROAD-flow-scripts/flow')
PLATFORM = FLOW / 'platforms/nangate45'
LIB = PLATFORM / 'lib/NangateOpenCellLibrary_typical.lib'
CELLS = Path('/root/pact-deps/FAN_ATPG/techlib/NangateOpenCellLibrary.v')
RULES = PLATFORM / 'rcx_patterns.rules'

def read(p):
    return json.loads(Path(p).read_text())

def write(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def bind(p):
    return dict(path=str(p), sha256=sha(p))

def check_binding(record):
    if sha(record['path']) != record['sha256']:
        raise ValueError('Artifact hash mismatch: ' + record['path'])

def run(cmd, folder, name):
    start = time.perf_counter()
    with (folder / (name + '.log')).open('w') as f:
        result = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    write(folder / (name + '.execution.json'), dict(command=list(map(str, cmd)),
          cwd=str(ROOT), seconds=time.perf_counter()-start, returncode=result.returncode))
    if result.returncode:
        raise RuntimeError(f'{name} failed: {folder / (name + ".log")}')

def prepare():
    if (OUT / 'manifest.json').exists():
        raise ValueError('Manifest exists; use run to replay its frozen inputs')
    rows = []
    for design, start in [('s5378', 'P'), ('s9234', 'T'), ('s15850', 'P')]:
        integration = ROOT / f'reports/end_to_end/{design}/integration_v1'
        qualified = read(integration / 'manifest.json')
        block = 's9234f' if design == 's9234' else design
        original = FLOW / f'results/nangate45/{block}/phase0b_s11_B0'
        for role in (start, 'J50', 'PACT'):
            folder = OUT / design / role
            folder.mkdir(parents=True, exist_ok=True)
            if role == 'PACT':
                ap = integration / 'scan_topology_after.json'
                handoff = read(integration / 'physical_handoff.json')
                archive, report = ROOT / handoff['archive'], ROOT / handoff['report']
            else:
                ap = ROOT / f'artifacts/derived/phase0c/{design}/s11/k2/{role}.architecture.json'
                report = ROOT / f'artifacts/raw/phase0c/physical/{design}/s11/k2/{role}/route_metrics.json'
                archive = report.parent / '5_2_route.odb.gz'
            arch = ScanArchitecture.from_json(ap)
            physical = read(report)
            assert physical['architecture_sha256'] == arch.sha256()
            assert physical.get('DRC_errors', physical.get('structured_metrics', {}).get('DRC_errors')) == 0
            assert sha(archive) == physical['routed_odb_gzip_sha256']
            inputs = {key: value for key, value in qualified['input_files'].items()
                      if key in ('identity_map', 'patterns', 'placement')}
            for value in inputs.values():
                check_binding(value)
            fan, states = fan_workload(Path(inputs['patterns']['path']),
                                      read(inputs['identity_map']['path'])['records'], arch)
            if role == 'PACT':
                workload = read(integration / 'patterns_remapped.json')
                assert workload['architecture_sha256'] == arch.sha256()
                assert sha(integration / 'patterns_remapped.json') == qualified['artifacts']['patterns_remapped.json']
            else:
                workload = dict(architecture_sha256=arch.sha256(), cycles=max(len(c.cells) for c in arch.chains),
                    patterns=[dict(pattern=s['pattern'], source_fields=s['source_fields'],
                                   load=serialize(arch,s['load_state']),
                                   unload=serialize(arch,s['response_state'],response=True)) for s in states])
            for p,s in zip(workload['patterns'], states, strict=True):
                assert p['load'] == serialize(arch,s['load_state'])
                assert p['unload'] == serialize(arch,s['response_state'],response=True)
                assert p['source_fields'] == s['source_fields']
            write(folder/'workload.json', workload)
            row = dict(design=design, role=role, physical_seed=11, K=2,
                architecture=bind(ap), scan_order_sha256=hashlib.sha256(json.dumps(
                    [(c.chain_id,list(c.cells)) for c in arch.chains],separators=(',',':')).encode()).hexdigest(),
                architecture_sha256=arch.sha256(), selected_PACT_architecture_sha256=qualified['selected_architecture_sha256'],
                routed_archive=bind(archive), source_placed_database=bind(original/'3_place.odb'),
                source_netlist=bind(ROOT/f'artifacts/raw/phase0b/placements/{design}/s11/placed.v'), SDC=bind(original/'3_place.sdc'),
                qualification=bind(report), prior_integration=bind(integration/'manifest.json'),
                workload=bind(folder/'workload.json'), inputs=inputs,
                PACT_remapped_source=bind(integration/'patterns_remapped.json') if role=='PACT' else None,
                patterns=len(states), chain_lengths=[len(c.cells) for c in arch.chains],
                shift_cycles=2*len(states)*workload['cycles'], clock_period_ns=10,
                voltage_V=None, voltage_policy='No energy or power claimed; report C*N in fF transitions',
                capture='one functional capture per pattern; excluded from measured shift windows',
                load_unload='both; separate zero-filled unload after each capture',
                routed_simulation_netlist='exported from exact ODB and hash-bound before simulation')
            rows.append(row)
    write(OUT/'manifest.json', dict(schema='pact_physical_effect_v1', base_commit=subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        tools={x:subprocess.run([x,'-V' if x=='iverilog' else '-version'],capture_output=True,text=True).stdout.splitlines()[0]
               for x in ('iverilog','openroad')},
        library=bind(LIB), simulation_cells=bind(CELLS), extraction_rules=bind(RULES), rows=rows))
    print('Frozen manifest: 9 exact routes, workloads and technology inputs', flush=True)

def ident(s):
    return '\\' + s + ' '

def stimulus(row, folder, mapping):
    arch = ScanArchitecture.from_json(Path(row['architecture']['path']))
    workload = read(row['workload']['path'])
    fan, states = fan_workload(Path(row['inputs']['patterns']['path']),
        read(row['inputs']['identity_map']['path'])['records'], arch)
    names = sorted(c.name for c in arch.cells)
    ports = mapping['ports']
    # Physical-only well tap has no signal pins in the OpenROAD netlist.
    lines = ['`timescale 1ns/1ps', 'module TAPCELL_X1; endmodule', 'module tb;', 'integer cycle_id = -1;', 'integer measured_cycles = 0;']
    for p in ports:
        lines.append(('reg ' if p['direction']=='INPUT' else 'wire ') + ident(p['name']) + ';')
    lines.append(mapping['block']+' dut('+','.join('.'+ident(p['name'])+'('+ident(p['name'])+')' for p in ports)+');')
    q = '{'+','.join('dut.'+ident(n)+'.Q' for n in names)+'}'
    def check(value, label):
        lines.append(f'if ({q} !== {len(names)}\'b{value}) begin $display("observed=%b expected={value}", {q}); $fatal(1,"{label}"); end')
    lines += ['task shift; input a; input b; begin', 'cycle_id=measured_cycles; measured_cycles=measured_cycles+1;',
              'test_si=a; test_si_1=b; #5; CK=1; #5; CK=0;', 'end endtask', 'initial begin']
    for p in ports:
        if p['direction']=='INPUT': lines.append(ident(p['name'])+"=1'b0;")
    lines += ['test_se=1; #10;', f'repeat ({workload["cycles"]}) begin #5; CK=1; #5; CK=0; end',
              '#10;', f'$dumpfile("{folder / "activity.vcd"}");', '$dumpvars(1,dut); $dumpvars(0,cycle_id);']
    cycles = []
    for index,(p,s) in enumerate(zip(workload['patterns'],states,strict=True)):
        lines.append('cycle_id=-1;')
        for name,bit in zip(fan.primary_inputs,p['source_fields']['pi1'],strict=True):
            lines.append(ident(name)+"=1'b"+bit.lower()+';')
        lines.append('test_se=1; #10;')
        for j in range(workload['cycles']):
            a,b = [p['load'][c.chain_id][j] for c in arch.chains]
            lines.append(f"shift(1'b{a},1'b{b});")
            cycles.append(dict(cycle=len(cycles),pattern=index+1,phase='load',shift=j))
        lines.append('cycle_id=-1; #1;')
        check(''.join(s['load_state'][n] for n in names),f'load pattern {index+1}')
        lines += ['test_se=0; #5; CK=1; #5; CK=0; #1;']
        check(''.join(s['response_state'][n] for n in names),f'capture pattern {index+1}')
        lines.append('test_se=1; #10;')
        for j in range(workload['cycles']):
            for ci,c in enumerate(arch.chains):
                if j<len(c.cells):
                    so='test_so' if ci==0 else 'test_so_1'
                    lines.append(f'if ({so} !== 1\'b{p["unload"][c.chain_id][j]}) $fatal(1,"unload {index+1}/{ci}/{j}");')
            lines.append("shift(1'b0,1'b0);")
            cycles.append(dict(cycle=len(cycles),pattern=index+1,phase='unload',shift=j))
        lines.append('cycle_id=-1; #10;')
    lines += [f'$display("PASS patterns={len(states)} shift_cycles=%0d load/capture/unload checked", measured_cycles);',
              '$finish; end endmodule']
    (folder/'stimulus.v').write_text('\n'.join(lines)+'\n')
    write(folder/'cycles.json', cycles)

def repair_input_aliases(folder,mapping):
    # This OpenROAD writer emits output aliases, but omits aliases for added
    # input BTerms whose names differ from their dbNet. Materialize only the
    # exact connections independently exported from the ODB.
    raw=(folder/'routed_raw.v').read_text()
    aliases=[]
    for p in mapping['ports']:
        if p['direction']=='INPUT' and p['name']!=p['net']:
            assert not re.search(r'assign\s+'+re.escape(p['net'])+r'\s*=',raw)
            aliases.append('assign '+ident(p['net'])+'= '+ident(p['name'])+';')
    assert raw.count('endmodule')==1
    (folder/'routed.v').write_text(raw.replace('endmodule','\n'.join(aliases)+'\nendmodule'))
    write(folder/'verilog_export_adapter.json',dict(raw=bind(folder/'routed_raw.v'),
        corrected=bind(folder/'routed.v'),input_aliases=aliases,
        rule='exact dbBTerm-to-dbNet connections; no topology or cell changes'))

def execute(design,resume=False):
    manifest=read(OUT/'manifest.json')
    for key in ('library','simulation_cells','extraction_rules'): check_binding(manifest[key])
    for row in manifest['rows']:
        if row['design'] != design: continue
        folder=OUT/design/row['role']
        for key in ('architecture','routed_archive','source_placed_database','source_netlist','SDC','qualification','workload','prior_integration'):
            check_binding(row[key])
        for v in row['inputs'].values(): check_binding(v)
        if resume and (folder/'activity_summary.json').exists():
            for value in read(folder/'simulation_manifest.json')['inputs'].values(): check_binding(value)
            assert sha(folder/'activity.vcd')==read(folder/'activity_summary.json')['VCD']['sha256']
            print('VERIFIED_REUSE',design,row['role'],flush=True)
            continue
        print('MEASURE',design,row['role'],flush=True)
        with gzip.open(row['routed_archive']['path'],'rb') as f, (folder/'routed.odb').open('wb') as g:
            shutil.copyfileobj(f,g)
        report=read(row['qualification']['path'])
        expected=report.get('routed_odb_sha256')
        if expected: assert sha(folder/'routed.odb')==expected
        run(['openroad','-python','-no_init','-exit',ROOT/'scripts/physical_effect_export.py',folder],folder,'export')
        tcl=f'''read_liberty {LIB}
read_db {folder/'routed.odb'}
write_verilog {folder/'routed_raw.v'}
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file {RULES} -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef {folder/'extracted.spef'}
exit
'''
        (folder/'extract.tcl').write_text(tcl)
        run(['openroad','-no_init','-exit',folder/'extract.tcl'],folder,'extract')
        mapping=read(folder/'net_mapping.json')
        repair_input_aliases(folder,mapping)
        stimulus(row,folder,mapping)
        write(folder/'simulation_manifest.json',dict(inputs={p:bind(folder/p) for p in (
            'routed.odb','routed.v','routed_raw.v','stimulus.v','net_mapping.json','cycles.json','extracted.spef','workload.json')},
            cells=bind(CELLS), architecture_sha256=row['architecture_sha256'],
            simulation='Icarus -g2012 -DTETRAMAX (vendor functional mode); specify disabled; zero delay; no SDF'))
        run(['iverilog','-g2012','-DTETRAMAX','-s','tb','-o',folder/'simulation.vvp',folder/'stimulus.v',folder/'routed.v',CELLS],folder,'compile')
        run(['vvp',folder/'simulation.vvp'],folder,'simulate')
        from pact.physical_effect import analyze
        analyze(folder)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('stage',choices=['prepare','run','analyze']); p.add_argument('--design'); p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    if args.stage=='prepare': prepare()
    elif args.stage=='run': execute(args.design,args.resume)
    else:
        from pact.physical_effect import analyze
        for row in read(OUT/'manifest.json')['rows']:
            folder=OUT/row['design']/row['role']
            if row['design']==args.design and (folder/'activity.vcd').exists(): analyze(folder)
