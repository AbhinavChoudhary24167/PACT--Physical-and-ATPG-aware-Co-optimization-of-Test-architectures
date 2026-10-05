"""Minimal shared-net receiver regression; no benchmark-specific optimization."""
from pathlib import Path
import shutil
import subprocess
import sys
from gate09_fan_report_repair import ROOT, OLD, NEW, FOLDER, execute
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_gate09_source_probe import META
from pact_experiment_receipts import atomic_write


def regression(label):
    binary = FOLDER / (label + '_mux_test')
    execute(label + '_compile', ['g++', '-std=c++11', '-O3', '-I' + str(NEW / 'include'),
        NEW / 'tests/compound_mux_test.cpp', '-L' + str(NEW / 'lib/opt'),
        '-lcore', '-linterface', '-lcommon', '-o', binary], NEW)[0].check_returncode()
    outcomes = []
    for test in ('arity', 'truth'):
        completed, record = execute(label + '_' + test, [binary, NEW / 'techlib/mod_nangate45.mdt',
            NEW / 'tests/compound_mux.v', test], NEW)
        outcomes.append(record)
    return outcomes


def patch():
    for name in ('compound_mux.v', 'compound_mux_test.cpp'):
        shutil.copy2(META / 'dependency_probes' / name, NEW / 'tests' / name)
    before = regression('shared_net_before')
    assert all(row['exit_code'] != 0 for row in before), 'Both arity and functional defect must reproduce'
    path = NEW / 'pkg/core/src/circuit.cpp'
    text = path.read_text()
    marker = '\t\t\tcircuitGates_[gateID].faninVector_.push_back(faninID);'
    assert text.count(marker) == 1
    text = text.replace(marker, '''\t\t\telse
\t\t\t{
\t\t\t\t// A different receiver on this net is not a driving fanin.
\t\t\t\tcontinue;
\t\t\t}
''' + marker)
    path.write_text(text)
    patch_text = subprocess.run(['git', 'diff', '--', 'pkg/core/src/circuit.cpp'], cwd=NEW,
                                capture_output=True, text=True, check=True).stdout
    (FOLDER / 'shared_net_connectivity.patch').write_text(patch_text)
    atomic_write(FOLDER / 'shared_net_reproduction.json', dict(
        status='REPRODUCED_EXTRA_FANIN_AND_WRONG_MUX_TRUTH_TABLE', regressions=before,
        fixture=admission.binding(NEW / 'tests/compound_mux.v'),
        patch=admission.binding(FOLDER / 'shared_net_connectivity.patch'),
        completed_b14_ATPG_workload='NOT_REUSABLE_AFTER_CONFIRMED_FUNCTIONAL_CONSTRUCTION_DEFECT',
        PACT_source_changes=0, scientific_parameters_changed=False,
        repair_scope='Ignore non-driving receiver pins when constructing primitive fanins'), immutable=True)


if __name__ == '__main__':
    if sys.argv[1] == 'patch':
        patch()
    else:
        rows = regression('shared_net_after')
        assert all(row['exit_code'] == 0 for row in rows)
