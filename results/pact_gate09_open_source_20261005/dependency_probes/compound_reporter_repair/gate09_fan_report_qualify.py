"""Build/qualify a generic FAN reporter repair, retaining each stage outcome."""
from pathlib import Path
import shutil
import sys

from gate09_fan_report_repair import ROOT, OLD, NEW, FOLDER, OLD_SHA, BRANCH, execute
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_gate09_source_probe import require_capacity, META, RAW
from pact_experiment_receipts import atomic_write


def core_build():
    require_capacity(admission.read(admission.INTAKE))
    saved = FOLDER / 'reporter_source_preserved_before_core_build.cpp'
    shutil.copy2(NEW / 'pkg/fan/src/atpg_cmd.cpp', saved)
    original_reporter = admission.command(['git', '-C', str(NEW), 'show', OLD_SHA + ':pkg/fan/src/atpg_cmd.cpp'])
    assert original_reporter['exit_code'] == 0
    # Restore only the saved uncommitted reporter change for an isolated core build.
    (NEW / 'pkg/fan/src/atpg_cmd.cpp').write_text(original_reporter['stdout'] + '\n')
    execute('core_branch', ['git', 'branch', '-m', 'fix/shared-compound-net-drivers'], NEW)[0].check_returncode()
    execute('core_stage', ['git', 'add', 'pkg/core/src/circuit.cpp', 'tests/compound_mux.v',
        'tests/compound_mux_test.cpp'], NEW)[0].check_returncode()
    execute('core_commit', ['git', 'commit', '-m', 'Ignore receiver pins when building shared compound-net fanins'], NEW)[0].check_returncode()
    completed, record = execute('core_optimized_build', ['make', '-j1', 'install', 'MODE=opt'], NEW, timeout=600)
    completed.check_returncode()
    snapshot = FOLDER / 'core_fixed_reporter_opt'
    shutil.copy2(NEW / 'bin/opt/fan', snapshot)
    atomic_write(FOLDER / 'core_build_binding.json', dict(execution=record,
        binary=admission.binding(snapshot), source_SHA=admission.command(['git', '-C', str(NEW), 'rev-parse', 'HEAD'])['stdout'],
        core_source=admission.binding(NEW / 'pkg/core/src/circuit.cpp'),
        reporter_source=admission.binding(NEW / 'pkg/fan/src/atpg_cmd.cpp'),
        preserved_reporter_patch=admission.binding(saved)), immutable=True)
    print('CORE_BUILD_PRESERVED', flush=True)


def final_build():
    require_capacity(admission.read(admission.INTAKE))
    reporter = NEW / 'pkg/fan/src/atpg_cmd.cpp'
    reporter.write_bytes((FOLDER / 'reporter_source_preserved_before_core_build.cpp').read_bytes())
    reporter.chmod(0o644)
    for name in ('compound_mux.v', 'compound_mux_test.cpp', 'report_compound_faults.py'):
        (NEW / 'tests' / name).chmod(0o644)
    completed, record = execute('connectivity_reporter_rebuilt', ['make', '-j1', 'install', 'MODE=opt'], NEW, timeout=600)
    completed.check_returncode()
    atomic_write(FOLDER / 'final_rebuilt_binding.json', dict(execution=record,
        binary=admission.binding(NEW / 'bin/opt/fan'), source=admission.binding(NEW / 'pkg/fan/src/atpg_cmd.cpp')),
        immutable=True)


def build():
    require_capacity(admission.read(admission.INTAKE))
    shutil.copy2(META / 'dependency_probes/report_compound_faults.py', NEW / 'tests/report_compound_faults.py')
    completed, record = execute('optimized_build', ['make', '-j1', 'install', 'MODE=opt'], NEW, timeout=600)
    completed.check_returncode()
    atomic_write(FOLDER / 'build_binding.json', dict(execution=record, binary=admission.binding(NEW / 'bin/opt/fan'),
        source=admission.binding(NEW / 'pkg/fan/src/atpg_cmd.cpp')), immutable=True)


def qualify():
    capacity = require_capacity(admission.read(admission.INTAKE))
    predecessor_path = META / 'dependency_repairs/FAN_ATPG/qualification.json'
    predecessor = admission.read(predecessor_path)
    records = []
    commands = [
        ('compound_circuit', ['python3', NEW / 'tests/run_compound_circuit.py', '--mode', 'opt']),
        ('reporter_control', ['python3', NEW / 'tests/report_fault_scan.py', NEW / 'bin/opt/fan',
            OLD / 'techlib/mod_nangate45.mdt', OLD / 'mod_netlist/s27.v', '/root/pact-deps/FAN_ATPG/pat/FAN_s27.pat']),
        ('compound_reporter', ['python3', NEW / 'tests/report_compound_faults.py', FOLDER / 'core_fixed_reporter_opt', NEW / 'bin/opt/fan',
            OLD / 'techlib/mod_nangate45.mdt', FOLDER / 'minimal.v', FOLDER / 'minimal.pat']),
        ('b14_failed_probe', ['python3', NEW / 'tests/report_compound_faults.py', FOLDER / 'core_fixed_reporter_opt', NEW / 'bin/opt/fan',
            OLD / 'techlib/mod_nangate45.mdt', RAW / 'sources/b14_opt/blif_output_aliases/mapped.v',
            RAW / 'repair_attempts/fan_compound_circuit/inputs/b14_opt/patterns.pat'])]
    for label, command in commands:
        completed, record = execute('qualified_' + label, command, NEW)
        records.append(dict(record, label=label))
        completed.check_returncode()
    for label in ('arity', 'truth'):
        row = admission.read(FOLDER / ('shared_net_after_' + label + '.json'))
        assert row['exit_code'] == 0
        records.append(dict(row, label='shared_net_' + label))
    execute('stage', ['git', 'add', 'pkg/fan/src/atpg_cmd.cpp', 'tests/report_compound_faults.py',
                     'tests/compound_mux.v', 'tests/compound_mux_test.cpp'], NEW)[0].check_returncode()
    execute('commit', ['git', 'commit', '-m', 'Fix reporting of compound-cell internal primitive fault sites'], NEW)[0].check_returncode()
    SHA = admission.command(['git', '-C', str(NEW), 'rev-parse', 'HEAD'])['stdout']
    diff = admission.command(['git', '-C', str(NEW), 'diff', '--exit-code', 'HEAD', '--', 'pkg', 'tests'])
    assert diff['exit_code'] == 0
    assert all(admission.verify(v)['status'] == 'PASS' for v in [predecessor['binary'], *predecessor['files'].values()])
    files = {name: admission.binding(NEW / name) for name in [*predecessor['files'], 'tests/report_compound_faults.py',
        'tests/compound_mux.v', 'tests/compound_mux_test.cpp']}
    record = dict(predecessor, schema='pact_gate09_dependency_repair_qualification_v3',
        predecessor=admission.binding(predecessor_path), combined_SHA=SHA, branch='fix/shared-compound-net-drivers',
        reporter_repair_SHA=SHA, reporter_predecessor_SHA=OLD_SHA, binary=admission.binding(NEW / 'bin/opt/fan'),
        files=files, focused_tests=records, tracked_source_diff=diff, capacity=capacity,
        scope='Qualified primitive level/arity repair plus driving-only shared-net fanins and resolved internal fault names',
        ATPG_generation_algorithm_changed=False, fault_universe_changed=True,
        fault_universe_correction='Remove spurious fanins introduced by treating receiver pins as drivers; SAF model unchanged',
        reporting_only_relative_to_predecessor=False, preparation_reuse_permitted=False,
        circuit_connectivity_repair=True,
        builds=[*predecessor['builds'], admission.binding(FOLDER / 'build_binding.json'),
                admission.binding(FOLDER / 'core_build_binding.json'), admission.binding(FOLDER / 'final_rebuilt_binding.json')],
        minimal_reproduction=admission.binding(FOLDER / 'reproduction.json'),
        patch=admission.binding(FOLDER / 'compound_reporter.patch'),
        connectivity_patch=admission.binding(FOLDER / 'shared_net_connectivity.patch'),
        connectivity_reproduction=admission.binding(FOLDER / 'shared_net_reproduction.json'),
        harness=admission.binding(Path(__file__)))
    atomic_write(FOLDER / 'qualification.json', record, immutable=True)
    atomic_write(META / 'dependency_repairs/FAN_ATPG/compound_reporter_qualification.json', record, immutable=True)
    print('QUALIFIED_GENERIC_INFRASTRUCTURE_REPAIR', SHA, flush=True)


if __name__ == '__main__':
    {'build': build, 'core_build': core_build, 'final_build': final_build, 'qualify': qualify}[sys.argv[1]]()
