#!/usr/bin/env python3
"""Independent Icarus validation of FAN PPO plus FF test-sequence recording."""
from phase2b_common import *
import subprocess
import re
import time
import resource
import shutil
import numpy as np
from pact.test.pattern_parser import parse_fan_pat, map_ppi_patterns
from pact.scan.model import ScanArchitecture
from pact.analysis.phase2b_waveform import record_test

def validate_capture(design, pattern, source, folder):
    lib=Path('/root/pact-deps/FAN_ATPG/techlib/NangateOpenCellLibrary.v')
    lines=['module tb;', 'reg CK=0;', 'reg test_se=0;', 'reg test_si=0;']
    for name in pattern.primary_inputs: lines.append('reg '+name+';')
    connections=['.CK(CK)', '.test_se(test_se)', '.test_si(test_si)']
    connections += [f'.{n}({n})' for n in pattern.primary_inputs]
    module=re.search(r'\bmodule\s+(\w+)\s*\(',source.read_text())[1]
    lines += [f'{module} dut('+','.join(connections)+');','initial begin']
    for i,p in enumerate(pattern.patterns):
        for name,bit in zip(pattern.primary_inputs,p.pi1): lines.append(f"{name}=1'b{bit.lower()};")
        for name,bit in zip(pattern.pseudo_primary_inputs,p.ppi): lines.append(f"force dut.{name}.Q=1'b{bit};")
        lines.append('#10;')
        for name,bit in zip(pattern.pseudo_primary_inputs,p.ppo):
            if bit != 'X': lines.append(f'if (dut.{name}.D !== 1\'b{bit}) $fatal(1,"PPO mismatch pattern {i} {name}");')
        for name,bit in zip(pattern.primary_outputs,p.po1):
            if bit != 'X': lines.append(f'if (dut.{name} !== 1\'b{bit}) $fatal(1,"PO mismatch pattern {i} {name}");')
        # Clock the actual library FF while its loaded outputs remain forced,
        # then release and check the independently sampled capture state.
        lines += ['CK=1; #1;']
        for name in pattern.pseudo_primary_inputs: lines.append(f'release dut.{name}.Q;')
        lines.append('#1;')
        for name,bit in zip(pattern.pseudo_primary_inputs,p.ppo):
            if bit != 'X': lines.append(f'if (dut.{name}.Q !== 1\'b{bit}) $fatal(1,"Captured Q mismatch pattern {i} {name}");')
        lines.append('CK=0;')
    lines += ['$display("ALL_PPO_PO_PASS"); $finish;','end','endmodule']
    tb=folder/'capture_tb.v'; tb.write_text('\n'.join(lines)+'\n')
    binary=folder/'capture.vvp'
    log=folder/'capture_validation.log'
    if log.exists() and 'Captured Q mismatch' in log.read_text():
        shutil.copyfile(log,folder/'capture_sdf_wrapper_probe.log')
    commands=[['iverilog','-g2012','-DTETRAMAX','-s','tb','-o',str(binary),str(lib),str(source),str(tb)],['vvp',str(binary)]]
    output=''
    for command in commands:
        run=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        output += run.stdout
        if run.returncode: break
    log.write_text(output)
    return dict(passed=run.returncode==0 and 'ALL_PPO_PO_PASS' in output,commands=commands,
        source_path=str(source),source_sha256=file_sha256(source),library_path=str(lib),library_sha256=file_sha256(lib),
        testbench_path=str(tb),testbench_sha256=file_sha256(tb),log_path=str(log),log_sha256=file_sha256(log),
        check='Independent Icarus: force loaded Q, apply PI1 with SE=0, compare D/PPO and PO1; pulse actual library FF clock, release Q, compare captured Q/PPO. No delay/glitch claim.',
        simulation_mode='Existing library TETRAMAX macro disables SDF xbuf wrappers (including self-driven SE), retaining functional mux and sequential UDP. Default wrapper mismatch logs retained; no library edits.')

def main():
    integrity()
    rows=read(REPORT/'architecture_set.json'); designs={}; recordings=[]
    for d,q in read(OLD/'test_quality.json').items():
        pattern=parse_fan_pat(Path(q['pattern_path']))
        fields=('pi1','pi2','ppi','scan_in','po1','po2','ppo')
        audit={f:dict(empty=sum(not getattr(p,f) for p in pattern.patterns),
                      unknown=sum(getattr(p,f).count('X') for p in pattern.patterns)) for f in fields}
        folder=WORK/d;folder.mkdir(exist_ok=True)
        complete=all(not audit[f]['empty'] and not audit[f]['unknown'] for f in ('pi1','ppi','ppo'))
        validation=validate_capture(d,pattern,ROOT/f'artifacts/raw/tool_qualification/fan_atpg/benchmarks/{d}.v',folder) if complete else dict(passed=False,blocker='Unknown or absent PI/PPI/PPO')
        designs[d]=dict(fields=audit,patterns=len(pattern.patterns),complete_capture_bits=complete,validation=validation)
        if not validation['passed']: continue
        identity=read(q['identity_path'])['records']
        load=map_ppi_patterns(pattern,identity)
        mapping={r['atpg_signal']:r['physical_instance'] for r in identity}
        captures=[{mapping[n]:int(b) for n,b in zip(pattern.pseudo_primary_inputs,p.ppo)} for p in pattern.patterns]
        for row in [r for r in rows if r['design']==d]:
            arch=ScanArchitecture.from_json(Path(row['architecture_path']))
            start=time.perf_counter(); trace,bounds=record_test(arch,load,captures)
            elapsed=time.perf_counter()-start
            target=WORK/row['architecture_sha256']/'test_waveform.npz'
            np.savez_compressed(target,**trace)
            recordings.append(dict(design=d,label=row['label'],trace_path=str(target),trace_sha256=file_sha256(target),
                cycles=len(trace['modes']),capture_edges=len(bounds),boundaries=bounds,
                reconstruction_seconds=elapsed,
                shift_edges=int(np.sum(trace['modes']!='capture')),
                raw_total=int(np.unpackbits(trace['toggles_packed'],axis=1)[:,:len(trace['names'])].sum())))
        print('CAPTURE',d,validation['passed'],flush=True)
    passed=len(recordings)==len(rows)
    write(REPORT/'waveform_audit.json',dict(
        status='FF_LOAD_CAPTURE_UNLOAD_QUALIFIED' if passed else 'FULL_TEST_WAVEFORM_UNQUALIFIED',
        primary='Unchanged Phase-2A carry-loaded, initial zero, no capture, no final unload.',
        supplementary='FF-only reconstructed protocol: load, validated PPO capture, simultaneous previous-response unload/next load, final longest-chain zero-SI unload.',
        full_circuit_status='FULL_TEST_WAVEFORM_UNQUALIFIED: no timed PI/clock/SE trace or glitch/internal-cell activity.',
        peak_process_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        final_unload='Explicit zero fill protocol; not inferred tester history. All FFs clock to longest length, short-chain leading padding remains real clocks.',
        upstream_evidence='/root/pact-deps/FAN_ATPG/pkg/core/src/pattern_rw.cpp: BASIC_SCAN capture_CK writer lines 1185-1247',
        designs=designs,rows=recordings))
    integrity()

if __name__=='__main__': main()
