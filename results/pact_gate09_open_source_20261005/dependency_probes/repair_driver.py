import json
from pathlib import Path
import shutil
import sys
ROOT = Path('/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT')
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_gate09_source_probe import RAW
from pact_experiment_receipts import atomic_write
repo = Path('/root/pact-deps/FAN_ATPG-gate09-crash-repair')
folder = RAW / 'dependency_probes/fan/compound_circuit_repair'
folder.mkdir(parents=True, exist_ok=True)
assert not (folder / 'application.json').exists()
original_binary = repo / 'bin/dbg/fan'
preserved = folder / 'upstream_sanitized_fan'
if not preserved.exists():
    shutil.copy2(original_binary, preserved)
assert admission.binding(original_binary)['sha256'] == admission.binding(preserved)['sha256']
source = repo / 'pkg/core/src/circuit.cpp'
text = source.read_text()
old = '''\tif ((int)top->getNCell() > 0)
\t{
\t\tcircuitLvl_ = circuitGates_[cellIndexToGateIndex_[top->getNCell() - 1]].numLevel_ + 2;
\t}'''
new = '''\t// A library cell can contain several primitives with different levels.
\t// Keep PO/PPO after every driver, including primitives in earlier cells.
\tcircuitLvl_ = 2;
\tfor (int i = 0; i < numPI_ + numPPI_ + numComb_; ++i)
\t{
\t\tif (circuitGates_[i].numLevel_ + 2 > circuitLvl_)
\t\t{
\t\t\tcircuitLvl_ = circuitGates_[i].numLevel_ + 2;
\t\t}
\t}'''
assert text.count(old) == 1
text = text.replace(old, new)
begin = text.index('void Circuit::determineGateType(')
end = text.index('// Function   [ Circuit::createCircuitPO ]', begin)
section = text[begin:end]
assert section.count('cell->getNPort()') == 16
section = section.replace('cell->getNPort()', 'pmt->getNPort()')
text = text[:begin] + section + text[end:]
source.write_text(text)
patch = admission.command(['git', '-C', str(repo), 'diff', '--', 'pkg/core/src/circuit.cpp'])
(folder / 'compound_circuit.patch').write_text(patch['stdout'] + '\n')
record = dict(schema='pact_gate09_dependency_repair_application_v1', dependency='FAN_ATPG',
              parent_SHA=admission.command(['git', '-C', str(repo), 'rev-parse', 'HEAD']),
              repair_branch='fix/atpg-crash-on-valid-netlist', source=admission.binding(source),
              patch=admission.binding(folder / 'compound_circuit.patch'),
              upstream_diagnostic_binary_preserved=admission.binding(preserved),
              original_binary=admission.binding(original_binary),
              diagnostic_driver_failure='First driver copied upstream executable then failed before source mutation: AttributeError for missing helper; resumed with explicit hash verification',
              reason='Generic compound-cell circuit levels and primitive arity; no search, fault-model, compression, workload or benchmark optimization changes',
              PACT_source_changes=0, qualified=False)
atomic_write(folder / 'application.json', record, immutable=True)
atomic_write(ROOT / 'results/pact_gate09_open_source_20261005/dependency_probes/fan_compound_repair_application.json', record, immutable=True)
print(json.dumps(record, indent=2), flush=True)
