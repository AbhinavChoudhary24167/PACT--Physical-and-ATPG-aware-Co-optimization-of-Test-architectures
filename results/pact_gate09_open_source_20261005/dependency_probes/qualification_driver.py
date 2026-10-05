import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
ROOT = Path('/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT')
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_gate09_source_probe import require_capacity, RAW, META
from pact_experiment_receipts import atomic_write
repo = Path('/root/pact-deps/FAN_ATPG-gate09-crash-repair')
original = Path('/root/pact-deps/FAN_ATPG')
folder = RAW / 'dependency_probes/fan/combined_backend_qualification'
folder.mkdir(parents=True, exist_ok=False)
capacity = require_capacity(admission.read(admission.INTAKE))
records = []
for label, command in (
    ('compound_circuit', ['python3', str(repo / 'tests/run_compound_circuit.py'), '--mode', 'opt']),
    ('reporter_control', ['python3', str(repo / 'tests/report_fault_scan.py'), str(repo / 'bin/opt/fan'),
                           str(original / 'techlib/mod_nangate45.mdt'), str(original / 'mod_netlist/s27.v'),
                           str(original / 'pat/FAN_s27.pat')])):
    start = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (folder / (label + '.stdout.txt')).write_text(result.stdout)
    (folder / (label + '.stderr.txt')).write_text(result.stderr)
    records.append(dict(label=label, command=command, exit_code=result.returncode,
                        wall_seconds=time.perf_counter() - start, stdout=admission.binding(folder / (label + '.stdout.txt')),
                        stderr=admission.binding(folder / (label + '.stderr.txt'))))
    print(label, result.returncode, result.stdout, result.stderr[:500], flush=True)
sources = {}
for design in ('s38417', 's38584'):
    path = original / 'mod_netlist' / (design + '.v')
    types = sorted(set(re.findall(r'^\s+([A-Za-z_]\w*)\s+\w+\s*\(', path.read_text(), re.M)))
    assert all(re.match(r'^(?:AND[234]|NAND[234]|OR[234]|NOR[234]|INV|BUF|SDFF)_X\d+$', typ) for typ in types)
    sources[design] = dict(source=admission.binding(path), cell_types=types,
                          compound_cell_trigger_present=False, historical_campaign_reruns=0)
diff = admission.command(['git', '-C', str(repo), 'diff', '--exit-code', 'HEAD', '--', 'pkg', 'tests'])
source_SHA = admission.command(['git', '-C', str(repo), 'rev-parse', 'HEAD'])['stdout']
repair_SHA = admission.command(['git', '-C', str(repo), 'rev-parse', 'fix/atpg-crash-on-valid-netlist'])['stdout']
passed = len(records) == 2 and all(row['exit_code'] == 0 for row in records) and diff['exit_code'] == 0
record = dict(schema='pact_gate09_dependency_repair_qualification_v1', dependency='FAN_ATPG',
              status='QUALIFIED_GENERIC_INFRASTRUCTURE_REPAIR' if passed else 'REPAIR_QUALIFICATION_FAILED',
              upstream_SHA='26b2b36c0e9db11a4b6d9e759df6e44357121f39', circuit_repair_SHA=repair_SHA,
              reporter_original_SHA='05ac6173535418711b60ee22df391da7a4a82252', combined_SHA=source_SHA,
              branch='qualification/compound-circuit-and-scan-reports', tracked_source_diff=diff,
              binary=admission.binding(repo / 'bin/opt/fan'), library=admission.binding(original / 'techlib/mod_nangate45.mdt'),
              files={name:admission.binding(repo / name) for name in ('pkg/core/src/circuit.cpp', 'pkg/fan/src/atpg_cmd.cpp',
                      'tests/compound_circuit_test.cpp', 'tests/compound_scan.v', 'tests/run_compound_circuit.py', 'tests/report_fault_scan.py')},
              focused_tests=records, capacity=capacity, historical_impact=sources,
              scope='Circuit construction for compound-cell levels and primitive arity; qualified existing reporting repair retained',
              PACT_source_changes=0, scientific_parameters_changed=False, benchmark_specific_optimization=False,
              original_frozen_FAN=next(value for name, value in admission.read(admission.INTAKE)['frozen_tools'].items()
                                       if '/FAN_ATPG-report-repair/' in name),
              infrastructure_repair_precedes_reference_admission=True, source_reference_admission_still_pending=True,
              upstream_reporting=admission.binding(META / 'dependency_probes/FAN_upstream_reporting.json'),
              builds=[admission.binding(META / ('dependency_probes/' + name + '.json')) for name in
                      ('upstream_sanitized_build', 'repaired_sanitized_build_after_patch', 'combined_repair_optimized_build')],
              harness=admission.binding(Path(__file__)))
atomic_write(folder / 'qualification.json', record, immutable=True)
atomic_write(META / 'dependency_repairs/FAN_ATPG/qualification.json', record, immutable=True)
print(record['status'], source_SHA, flush=True)
raise SystemExit(0 if passed else 2)
