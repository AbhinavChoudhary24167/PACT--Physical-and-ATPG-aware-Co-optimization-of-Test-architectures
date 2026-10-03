#!/usr/bin/env python3
"""Check exposed Tcl commands and linked optimizer symbols before generation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from openroad import Design, Tech


def main(args):
    binary = Path('/proc/self/exe').resolve()
    tech = Tech()
    design = Design(tech)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command_output = args.output.with_suffix('.commands.txt')
    if args.output.exists() or command_output.exists():
        raise ValueError('Command probe evidence exists')
    # Read an explicit Tcl-produced artifact rather than relying on a Python
    # binding's return-value convention for evalTclString.
    design.evalTclString(f'''set pact_probe_handle [open {{{command_output}}} w]
foreach pact_probe_command {{scan_opt dft::scan_opt execute_dft_plan set_dft_config}} {{
  puts $pact_probe_handle "$pact_probe_command\t[info commands $pact_probe_command]"
}}
close $pact_probe_handle''')
    commands = dict(line.split('\t', 1) for line in command_output.read_text().splitlines())
    if set(commands) != {'scan_opt', 'dft::scan_opt', 'execute_dft_plan', 'set_dft_config'}:
        raise ValueError('Compiled command inventory is incomplete')
    for command, observed in commands.items():
        if not observed:
            raise ValueError('Compiled generator command is absent: ' + command)
    design.evalTclString('help scan_opt')
    required = ('dft::Dft::scanOpt()', 'dft::OptimizeScanWirelength2Opt(' if args.method=='B2' else 'dft::OptimizeScanWirelength(')
    matches = []
    process = subprocess.Popen(['nm', '-C', str(binary)], stdout=subprocess.PIPE, text=True)
    for line in process.stdout:
        if any(name in line for name in required):
            matches.append(line.strip())
    if process.wait() or any(not any(name in line for line in matches) for name in required):
        raise ValueError('Required optimizer implementation is not linked into this binary')
    if args.method=='B2':
        header = args.source / 'src/dft/src/architect/Opt.hh'
        iterations = int(re.search(r'max_iters\s*=\s*(\d+)', header.read_text())[1])
        parameters = dict(max_2opt_iterations=iterations, external_endpoints_included=True,
            cost='Symmetric FF-origin Manhattan', initialization='Native NN', command_arguments=[])
        if iterations != 30:
            raise ValueError('Pinned B2 parameter differs from audited behavior')
        parameter_files = [header, args.source / 'src/dft/src/architect/Opt.cpp']
    else:
        header = args.source / 'src/dft/src/optimizer/KMeans.hh'
        optimizer = args.source / 'src/dft/src/optimizer/Opt.cpp'
        iterations = int(re.search(r'max_iters\s*=\s*(\d+)', header.read_text())[1])
        neighbors = int(re.search(r'kMaxNeighbors\s*=\s*(\d+)', optimizer.read_text())[1])
        parameters = dict(kmeans_max_iterations=iterations, candidate_neighbors=neighbors,
            candidate_overquery=2*neighbors, capacity='Original maximum chain bit count',
            same_clock_and_edge_domains=True, initialization='Deterministic farthest point KMeans, then NN',
            local_search='Directed scan-pin 2Opt with reversal correction and direction-preserving 3Opt; strict improvement until convergence',
            external_endpoints_included=False, command_arguments=[])
        if iterations != 100 or neighbors != 50:
            raise ValueError('Pinned B3 parameter differs from audited behavior')
        parameter_files = [header, optimizer]
    parameter_files += [args.source / 'src/dft/src/Dft.cpp', args.source / 'src/dft/src/dft.tcl']
    args.output.write_text(json.dumps(dict(status='PASS', method=args.method, source_commit=args.commit,
        binary_path=str(binary), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        exposed_commands=commands, linked_implementation_symbols=matches, parameters=parameters,
        parameter_source_sha256={str(path.relative_to(args.source)):hashlib.sha256(path.read_bytes()).hexdigest() for path in parameter_files},
        interpretation='Linked symbols and immutable source verify exposed behavior; functional execution is qualified separately on all frozen designs'), indent=2, sort_keys=True)+'\n')
    print('COMPILED_OPTIMIZER_COMMAND_PROBE_PASS', args.method, flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', required=True, choices=('B2','B3'))
    parser.add_argument('--commit', required=True)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    main(parser.parse_args())
