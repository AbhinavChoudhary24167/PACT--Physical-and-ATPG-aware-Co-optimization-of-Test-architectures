#!/usr/bin/env python3
"""Qualify the unchanged common input and actual native K=2 DFT generator."""
from pact.experiment_storage import experiment_root
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, verify, write

TEMP = Path(('' + str(experiment_root()) + '/tmp/pact_oss_20261003'))


def execute(command, folder, label):
    folder.mkdir(parents=True, exist_ok=True)
    record = folder / (label + '.execution.json')
    if record.exists():
        raise ValueError('Execution already recorded: ' + str(record))
    start = time.perf_counter()
    scripts = [Path(arg) for arg in command if arg.endswith('.py')]
    source_bindings = {}
    for script in scripts:
        snapshot = folder / (label + '.' + script.name)
        shutil.copy2(script, snapshot)
        source_bindings[str(script)] = binding(snapshot)
    with (folder / (label + '.stdout.log')).open('w') as stdout:
        process = subprocess.run(['/usr/bin/time', '-v', '-o', str(folder / (label + '.resource.txt')), *command],
                                 cwd=ROOT, stdout=stdout, stderr=subprocess.STDOUT, timeout=180)
    result = dict(command=command, returncode=process.returncode, seconds=time.perf_counter() - start,
                  executed_source=source_bindings,
                  timestamp=datetime.now(timezone.utc).isoformat())
    write(record, result)
    return result


def main():
    verify()
    # Recreate the historical metadata-only Liberty in scratch storage and demand
    # its already recorded hash. Historical output paths remain untouched.
    from phase0b_annotate_nangate_dft import ANNOTATION, SOURCE
    metadata = read(ROOT / 'artifacts/derived/phase0b/lib/annotation.json')
    if binding(SOURCE)['sha256'] != metadata['source_sha256']:
        raise ValueError('Original Liberty changed')
    liberty = TEMP / 'NangateOpenCellLibrary_typical_dft.lib'
    text = SOURCE.read_text()
    start = text.index('  cell (SDFF_X1) {')
    area = text.index('\n\tarea', start)
    liberty.parent.mkdir(parents=True, exist_ok=True)
    if not liberty.exists():
        liberty.write_text(text[:area] + ANNOTATION + text[area:])
    if binding(liberty)['sha256'] != metadata['output_sha256']:
        raise ValueError('Reconstructed annotation differs from historical hash')
    if not (OUT / 'protocol/dft_metadata_adapter.json').exists():
        write(OUT / 'protocol/dft_metadata_adapter.json', dict(historical_annotation=binding(ROOT / 'artifacts/derived/phase0b/lib/annotation.json'),
                                                              original_liberty=binding(SOURCE), regenerated_liberty=binding(liberty),
                                                              historical_output_hash_reproduced=True))
    for design in DESIGNS:
        folder = OUT / 'baselines/B1_openroad_native' / design
        scratch = TEMP / 'B1_openroad_native' / design
        source = TEMP / 'placed_common' / design / '3_place.odb'
        frozen = read(OUT / 'stage_a/P0_FREEZE.json')['frozen_inputs'][design]
        input_arch = Path(frozen['B0_reference']['path'])
        source.parent.mkdir(parents=True, exist_ok=True)
        if (folder / 'common_rewire.execution.json').exists():
            rewire = read(folder / 'common_rewire.execution.json')
            saved = read(folder / 'common_input.json')
            if binding(source)['sha256'] != saved['source']['sha256']:
                raise ValueError('Common source changed')
        else:
            rewire = execute(['openroad', '-python', '-no_init', '-exit', str(ROOT / 'scripts/phase0c_rewire_odb.py'),
                              '--source', frozen['3_place.odb']['path'], '--architecture', str(input_arch), '--output', str(source)],
                             folder, 'common_rewire')
        if rewire['returncode']:
            print('STOP_COMMON_REWIRE', design, flush=True)
            return 2
        if not (folder / 'common_input.json').exists():
            write(folder / 'common_input.json', dict(source=binding(source), reference=binding(input_arch),
                                                original_placed_odb=frozen['3_place.odb'],
                                                adapter=binding(ROOT / 'scripts/phase0c_rewire_odb.py')))
        attempt = 1
        label = 'native'
        while (folder / (label + '.execution.json')).exists():
            attempt += 1
            label = f'native_attempt{attempt}'
        native = execute(['openroad', '-python', '-no_init', '-exit', str(ROOT / 'scripts/pact_oss_native.py'),
                          '--design', design, '--source', str(source), '--output', str(scratch), '--liberty', str(liberty)], folder, label)
        if native['returncode']:
            print('STOP_NATIVE_QUALIFICATION', design, flush=True)
            return 2
        for name in ('architecture.json', 'qualification.json', 'generated.v'):
            shutil.copy2(scratch / name, folder / name)
        write(folder / 'generated_artifacts.json', {p.name: binding(p) for p in scratch.iterdir() if p.is_file()})
        print('NATIVE_QUALIFIED', design, read(folder / 'qualification.json')['architecture_sha256'], flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
