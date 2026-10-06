#!/usr/bin/env python3
"""Compare old/new reporters on a fixed pattern set without regenerating ATPG.

Usage: report_compound_faults.py OLD_FAN NEW_FAN LIB NETLIST PATTERNS
Requires an independent fixture that exercises internal compound-cell faults.
"""
import collections
from pathlib import Path
import re
import subprocess
import sys
import tempfile

old, new, lib, netlist, patterns = [Path(arg).resolve() for arg in sys.argv[1:]]
line = re.compile(r'^#\s+(SA[01])\s+(UD|DT|PT|AU|TI|RE|AB)\s+(.+?)\s+\[equivalent=(\d+)\]\s*$', re.M)


def report(binary, command, directory):
    script = directory / 'report.script'
    script.write_text('\n'.join((f'read_lib {lib}', f'read_netlist {netlist}',
        'build_circuit --frame 1', f'read_pattern {patterns}', 'set_fault_type saf',
        'add_fault -a', 'run_fault_sim', 'report_statistics', command, 'exit')) + '\n')
    result = subprocess.run([str(binary), '-f', str(script)], capture_output=True,
                            text=True, timeout=120, check=True)
    assert '**ERROR' not in result.stdout + result.stderr
    records = line.findall(result.stdout)
    counts = {label: int(re.search(r'^#\s+' + label + r' \([^\n]+\)\s+(\d+)', result.stdout, re.M)[1])
              for label in ('UD', 'DT', 'PT', 'AU', 'TI', 'RE', 'AB')}
    full = int(re.search(r'FU \(full\)\s+(\d+)', result.stdout)[1])
    collapsed = int(re.search(r'FU \(collapsed\)\s+(\d+)', result.stdout)[1])
    return records, (counts, full, collapsed)


with tempfile.TemporaryDirectory(prefix='fan-compound-reporter-') as temporary:
    directory = Path(temporary)
    before, old_counts = report(old, 'report_fault', directory)
    after, new_counts = report(new, 'report_fault', directory)
    assert any(site.startswith('(') for _, _, site, _ in before), 'fixture does not reproduce the defect'
    assert old_counts == new_counts, 'reporting must not change weighted fault statistics'
    assert [(k, s, w) for k, s, _, w in before] == [(k, s, w) for k, s, _, w in after], 'class order/state/weight changed'
    old_identity_counts = collections.Counter((kind, site) for kind, _, site, _ in before)
    for a, b in zip(before, after):
        if not a[2].startswith('(') and old_identity_counts[(a[0], a[2])] == 1:
            assert a[2] == b[2], 'existing public fault identity changed'
        elif not a[2].startswith('(') and a[2] != b[2]:
            # The old input loop also considered the following output port,
            # falsely labeling an internal MUX input as its public output.
            assert b[2].startswith(a[2].split('/')[0] + '/') and b[2].count('/') == 2
    assert all('/' in site or '(primary input)' in site or '(primary output)' in site or
               site in ('CK', 'test_si', 'test_so', 'test_se') for _, _, site, _ in after)
    assert len({(kind, site) for kind, _, site, _ in after}) == len(after), 'duplicate identity'
    weights = collections.Counter()
    for _, state, _, weight in after:
        assert int(weight) > 0
        weights[state] += int(weight)
    counts, full, collapsed = new_counts
    assert len(after) == collapsed and sum(weights.values()) == full
    assert all(weights[state] == count for state, count in counts.items())
    detected, filtered_counts = report(new, 'report_fault -s DT', directory)
    assert filtered_counts == new_counts
    assert detected == [row for row in after if row[1] == 'DT'], 'state filtering changed identities'
    again, again_counts = report(new, 'report_fault', directory)
    assert again == after and again_counts == new_counts, 'reporting identities are not deterministic'
print('PASS complete unique compound identities; states/weights, unique public identities and filtering unchanged')
