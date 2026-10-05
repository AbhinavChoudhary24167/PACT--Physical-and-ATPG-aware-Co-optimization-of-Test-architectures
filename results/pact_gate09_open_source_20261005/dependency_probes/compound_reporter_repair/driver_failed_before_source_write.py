"""Isolated reporting-only compound-fault repair, with preserved reproducer."""
import collections
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path('/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT')
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_gate09_source_probe import require_capacity, RAW, META
from pact_experiment_receipts import atomic_write

OLD = Path('/root/pact-deps/FAN_ATPG-gate09-crash-repair')
NEW = Path('/root/pact-deps/FAN_ATPG-gate09-reporter-repair')
FOLDER = RAW / 'dependency_probes/fan/compound_reporter_repair'
OLD_SHA = '458c6889887811ce20c2970969a264c9acf5a9dd'
BRANCH = 'fix/report-compound-internal-fault-sites'


def execute(label, command, cwd=None, timeout=120):
    start = time.perf_counter()
    completed = subprocess.run(list(map(str, command)), cwd=cwd, capture_output=True,
                               text=True, timeout=timeout)
    out, err = FOLDER / (label + '.stdout.txt'), FOLDER / (label + '.stderr.txt')
    out.write_text(completed.stdout)
    err.write_text(completed.stderr)
    row = dict(command=list(map(str, command)), cwd=str(cwd) if cwd else None,
               exit_code=completed.returncode, wall_seconds=time.perf_counter() - start,
               stdout=admission.binding(out), stderr=admission.binding(err))
    atomic_write(FOLDER / (label + '.json'), row, immutable=True)
    print(label, completed.returncode, flush=True)
    return completed, row


def setup():
    FOLDER.mkdir(parents=True, exist_ok=False)
    require_capacity(admission.read(admission.INTAKE))
    old = admission.read(META / 'dependency_repairs/FAN_ATPG/qualification.json')
    assert all(admission.verify(v)['status'] == 'PASS' for v in
               [old['binary'], *old['files'].values()])
    completed, _ = execute('clone', ['git', 'clone', '--no-hardlinks', str(OLD), str(NEW)])
    completed.check_returncode()
    for label, command in [('branch', ['git', 'checkout', '-b', BRANCH, OLD_SHA]),
                           ('author', ['git', 'config', 'user.name', 'Abhinav']),
                           ('email', ['git', 'config', 'user.email', 'wellitsabhinav@users.noreply.github.com'])]:
        execute(label, command, NEW)[0].check_returncode()
    shutil.copy2(OLD / 'tests/compound_scan.v', FOLDER / 'minimal.v')
    script = FOLDER / 'minimal.script'
    script.write_text(f'read_lib {OLD}/techlib/mod_nangate45.mdt\n'
                      f'read_netlist {FOLDER}/minimal.v\n'
                      'build_circuit --frame 1\nset_fault_type saf\nadd_fault -a\n'
                      'set_static_compression on\nset_dynamic_compression on\nset_X-Fill on\n'
                      f'run_atpg\nwrite_pattern {FOLDER}/minimal.pat\n'
                      'report_statistics\nreport_fault\nexit\n')
    completed, _ = execute('minimal_before', [OLD / 'bin/opt/fan', '-f', script], OLD)
    completed.check_returncode()
    records = re.findall(r'^#\s+SA[01]\s+\w+\s+(.+?)\s+\[equivalent=', completed.stdout, re.M)
    assert any(site.startswith('(') for site in records), 'Independent minimal reproduction required'
    atomic_write(FOLDER / 'reproduction.json', dict(
        status='REPRODUCED_UNRESOLVED_INTERNAL_FAULT_IDENTITIES', upstream=old['binary'],
        fixture=admission.binding(FOLDER / 'minimal.v'), script=admission.binding(script),
        patterns=admission.binding(FOLDER / 'minimal.pat'), records=len(records),
        unresolved=sum(site.startswith('(') for site in records)), immutable=True)
    path = NEW / 'pkg/fan/src/atpg_cmd.cpp'
    text = path.read_text()
    assert text.count('Port *p = NULL;') == 1
    text = text.replace('Port *p = NULL;', 'Port *p = NULL;\n\t\t\tPort *primitivePin = NULL;')
    marker = '\t\t\t\t\t\tNet *n = pmt->getPort(i)->exNet_;'
    assert text.count(marker) == 1
    text = text.replace(marker, '\t\t\t\t\t\tprimitivePin = pmt->getPort(i);\n' + marker)
    old_input = '''\t\t\t\t\tif (pmt->getPort(i)->type_ == Port::INPUT)
\t\t\t\t\t{
\t\t\t\t\t\t++inCount;
\t\t\t\t\t}'''
    new_input = '''\t\t\t\t\tif (pmt->getPort(i)->type_ != Port::INPUT)
\t\t\t\t\t{
\t\t\t\t\t\tcontinue;
\t\t\t\t\t}
\t\t\t\t\t++inCount;'''
    assert text.count(old_input) == 1
    text = text.replace(old_input, new_input)
    marker = '\t\t\t\t\tNet *n = pmt->getPort(i)->exNet_;'
    assert text.count(marker) == 1
    text = text.replace(marker, '\t\t\t\t\tprimitivePin = pmt->getPort(i);\n' + marker)
    marker = '\t\t\tstd::cout << "(" << libc->name_ << ")";'
    assert text.count(marker) == 1
    text = text.replace(marker, '''\t\t\telse if (primitivePin)
\t\t\t{
\t\t\t\t// A compound-cell primitive pin need not reach a public cell port.
\t\t\t\t// Name the existing fault site; do not change its class or weight.
\t\t\t\tstd::cout << c->name_ << "/" << pmt->name_ << "/"
\t\t\t\t          << primitivePin->name_ << " ";
\t\t\t}
''' + marker)
    path.write_text(text)
    patch = subprocess.run(['git', 'diff', '--', 'pkg/fan/src/atpg_cmd.cpp'], cwd=NEW,
                           capture_output=True, text=True, check=True).stdout
    (FOLDER / 'compound_reporter.patch').write_text(patch)
    atomic_write(FOLDER / 'application.json', dict(
        predecessor=admission.binding(META / 'dependency_repairs/FAN_ATPG/qualification.json'),
        predecessor_SHA=OLD_SHA, branch=BRANCH, fixture=admission.binding(FOLDER / 'minimal.v'),
        repair_source=admission.binding(path), patch=admission.binding(FOLDER / 'compound_reporter.patch'),
        PACT_source_changes=0, scientific_parameters_changed=False,
        algorithm_or_fault_universe_changes=False), immutable=True)
    print('PATCH_APPLIED', flush=True)


if __name__ == '__main__':
    setup()
