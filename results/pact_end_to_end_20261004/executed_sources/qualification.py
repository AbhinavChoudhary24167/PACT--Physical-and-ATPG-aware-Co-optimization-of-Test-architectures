"""Fail-closed FAN correctness gate on its frozen collapsed SAF universe.

FAN's full fault counts weight collapsed classes by equivalent_. Complete
class identities and weights are compared; individual members of equivalence
classes are not exported by FAN and are not claimed to have been enumerated.
"""
from pathlib import Path
import re
import subprocess
import time

from .faults import parse_statistics
from .permutation import file_hash, write
from pact.test.pattern_parser import parse_fan_pat

STATES = ('UD', 'DT', 'PT', 'AU', 'TI', 'RE', 'AB')


def parse_export(text):
    statistics = parse_statistics(text)
    collapsed = re.search(r'FU \(collapsed\)\s+(\d+)', text)
    declared = re.search(r'number of faults:\s*(\d+)', text)
    if collapsed is None or declared is None:
        raise ValueError('Missing complete FAN universe dimensions')
    records = []
    for kind, state, identity, weight in re.findall(
            r'^#\s+(SA[01])\s+(UD|DT|PT|AU|TI|RE|AB)\s+(.+?)\s+\[equivalent=(\d+)\]\s*$', text, re.M):
        if (identity.startswith('(') or
            not ('/' in identity or '(primary input)' in identity or
                 '(primary output)' in identity or identity in ('CK','test_si','test_so','test_se'))):
            raise ValueError('Unresolved fault site: '+identity)
        if int(weight) <= 0:
            raise ValueError('Nonpositive fault equivalence weight')
        records.append(dict(identity=kind+' '+identity, state=state, equivalent=int(weight)))
    identities = [r['identity'] for r in records]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate fault identity')
    if not len(records) == int(collapsed[1]) == int(declared[1]):
        raise ValueError('Partial fault universe export')
    if sum(r['equivalent'] for r in records) != statistics['total']:
        raise ValueError('Fault universe weight differs from FU full')
    if sum(r['equivalent'] for r in records if r['state'] == 'DT') != statistics['detected']:
        raise ValueError('Detected identity weights differ from DT count')
    for state in STATES:
        row = re.search(re.escape(state)+r' \([^\n]+\)\s+(\d+)', text)
        if row is None or sum(r['equivalent'] for r in records if r['state'] == state) != int(row[1]):
            raise ValueError('Fault-state export differs from statistics: '+state)
    return dict(schema='pact_fan_collapsed_fault_export_v1', statistics=statistics,
        collapsed_faults=len(records), records=sorted(records,key=lambda r:r['identity']),
        identity_scope='Complete collapsed SAF target classes plus equivalence multiplicities on the same original functional circuit/library; uncollapsed member identities are not enumerated')


def compare_exports(original, candidate):
    old = {r['identity']:r['equivalent'] for r in original['records']}
    new = {r['identity']:r['equivalent'] for r in candidate['records']}
    a = {r['identity'] for r in original['records'] if r['state'] == 'DT'}
    b = {r['identity'] for r in candidate['records'] if r['state'] == 'DT'}
    lost, added = sorted(a-b), sorted(b-a)
    universe_pass = old == new
    counts_pass = original['statistics'] == candidate['statistics']
    identity_pass = universe_pass and not lost and not added
    return dict(status='PASS' if counts_pass and identity_pass else 'FAIL',
        ATPG='ATPG_PASS' if universe_pass else 'ATPG_FAIL',
        FAULT_COVERAGE='FAULT_COVERAGE_PASS' if counts_pass else 'FAULT_COVERAGE_FAIL',
        FAULT_IDENTITY='FAULT_IDENTITY_PASS' if identity_pass else 'FAULT_IDENTITY_FAIL',
        fault_universe_equal=universe_pass, lost_faults=lost, unexpected_faults=added,
        detected_collapsed_classes=len(b), identity_scope=candidate['identity_scope'],
        uncollapsed_member_identity_equivalence='NOT_ENUMERATED',
        original=original['statistics'], candidate=candidate['statistics'])


def simulate(executable, library, netlist, patterns, output, *, details=True, timeout=180):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    paths = [Path(p).resolve() for p in (executable, library, netlist, patterns)]
    if any(not p.is_file() for p in paths):
        raise FileNotFoundError('FAN input/tool missing')
    if any(re.search(r'\s|["\r\n]', str(p)) for p in paths):
        raise ValueError('FAN requires paths without whitespace/quotes')
    executable, library, netlist, patterns = paths
    script = output/'replay.script'
    commands = [f'read_lib {library}', f'read_netlist {netlist}', 'build_circuit --frame 1',
        f'read_pattern {patterns}', 'set_fault_type saf', 'add_fault -a',
        'run_fault_sim', 'report_statistics']
    if details:
        commands.append('report_fault')
    script.write_text('\n'.join(commands+['exit'])+'\n', encoding='utf-8')
    began = time.perf_counter()
    run = subprocess.run([str(executable),'-f',str(script.resolve())],
        cwd=executable.parents[2], capture_output=True,text=True,timeout=timeout)
    elapsed = time.perf_counter()-began
    (output/'stdout.txt').write_text(run.stdout,encoding='utf-8')
    (output/'stderr.txt').write_text(run.stderr,encoding='utf-8')
    write(output/'execution.json',dict(command=[str(executable),'-f',str(script.resolve())],
        exit_code=run.returncode,runtime_seconds=elapsed,
        bindings={key:dict(path=str(p),sha256=file_hash(p)) for key,p in zip(
            ('executable','library','netlist','patterns','script'),paths+[script])}))
    if run.returncode or '**ERROR' in run.stdout+run.stderr:
        raise ValueError('FAN replay failed; inspect '+str(output))
    export = parse_export(run.stdout) if details else dict(statistics=parse_statistics(run.stdout))
    if export['statistics']['patterns'] != len(parse_fan_pat(patterns).patterns):
        raise ValueError('FAN did not simulate every supplied pattern')
    write(output/'export.json',export)
    return export
