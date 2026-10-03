#!/usr/bin/env python3
"""Qualify immutable B2/B3 binaries and canonical K=2 outputs, sequentially."""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import shutil

from pact_oss_recovery import RECOVERY, TEMP, MOUNT, IMAGE, docker, execute, require_prerequisites
from pact_oss_benchmark import OUT, DESIGNS, binding, read, verify, write
from pact_oss_canonicalize import validate_architecture
from pact.scan.model import ScanArchitecture


def generate(method):
    from pact_oss_storage import ensure
    ensure()
    require_prerequisites()
    verify()
    annotation = read(OUT / 'protocol/dft_metadata_adapter.json')
    for key in ('original_liberty', 'regenerated_liberty'):
        if binding(annotation[key]['path'])['sha256'] != annotation[key]['sha256']:
            raise ValueError('Frozen Liberty metadata or functional source changed')
    frozen_adapter = read(OUT / 'stage_a/evidence_manifest.json')['benchmark_sources']['scripts/pact_oss_native.py']
    if binding(frozen_adapter['path'])['sha256'] != frozen_adapter['sha256']:
        raise ValueError('Qualified native adapter changed')
    name = 'B2_openroad_10176' if method == 'B2' else 'B3_openroad_10666'
    folder = RECOVERY / 'baselines' / name
    manifest = read(folder / 'build_result.json')
    if manifest['status'] != 'BUILT':
        raise ValueError('Exact pinned build is not qualified for generation')
    pin = read(OUT / 'baselines' / name / 'source_pin.json')
    binary = MOUNT / name / 'build/bin/openroad'
    if manifest['binary_sha256'] != binding(binary)['sha256'] or manifest['commit'] != pin['commit']:
        raise ValueError('Generator binary/source identity mismatch')
    sources = read(folder / 'source_manifest.json')
    for relative, expected in sources['pinned_source_blobs_checked'].items():
        path = MOUNT / name / 'source' / relative
        actual = hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
        if actual != expected:
            raise ValueError('Algorithm source changed after compilation: ' + relative)
    version_command = docker([f'/build_storage/{name}/build/bin/openroad', '-version'])
    if execute(version_command, folder, 'binary_version'):
        return 1
    if pin['commit'] not in (folder / 'binary_version.log').read_text():
        raise ValueError('Compiled binary does not report the pinned OpenROAD version')
    scratch_probe = TEMP / 'recovery_20261003' / name / 'compiled_behavior.json'
    probe = docker([f'/build_storage/{name}/build/bin/openroad', '-python', '-no_init', '-exit',
        '/workspace/scripts/pact_oss_command_probe.py', '--method', method, '--commit', pin['commit'],
        '--source', f'/build_storage/{name}/source', '--output', f'/scratch/recovery_20261003/{name}/compiled_behavior.json'])
    shutil.copy2(Path(__file__).with_name('pact_oss_command_probe.py'), folder / 'executed_command_probe.py')
    if execute(probe, folder, 'compiled_command_probe'):
        return 1
    shutil.copy2(scratch_probe, folder / 'compiled_behavior.json')
    if read(folder / 'compiled_behavior.json')['binary_sha256'] != manifest['binary_sha256']:
        raise ValueError('Compiled behavior probe used a different binary')
    output_rows, qualifications = [], {}
    for design in DESIGNS:
        common = read(OUT / 'baselines/B1_openroad_native' / design / 'common_input.json')
        source = TEMP / 'placed_common' / design / '3_place.odb'
        if binding(source)['sha256'] != common['source']['sha256']:
            raise ValueError('Qualified common generator input changed')
        scratch = TEMP / 'recovery_20261003' / name / design
        scratch.mkdir(parents=True, exist_ok=True)
        args = ['/usr/bin/time', '-v', '-o', f'/scratch/recovery_20261003/{name}/{design}/generator.resource.txt',
                f'/build_storage/{name}/build/bin/openroad', '-python', '-no_init', '-exit',
                '/workspace/scripts/pact_oss_generator.py', '--method', method, '--commit', pin['commit'],
                '--design', design, '--source', f'/scratch/placed_common/{design}/3_place.odb',
                '--output', f'/scratch/recovery_20261003/{name}/{design}',
                '--liberty', '/scratch/NangateOpenCellLibrary_typical_dft.lib']
        command = docker(args)
        mount_at = command.index('--entrypoint')
        command[mount_at:mount_at] = ['--mount', 'type=bind,source=/root/pact-deps/OpenROAD-flow-scripts/flow/results,target=/root/pact-deps/OpenROAD-flow-scripts/flow/results,readonly']
        target = folder / design
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__).with_name('pact_oss_generator.py'), target / 'executed_generator.py')
        shutil.copy2(Path(__file__).with_name('pact_oss_native.py'), target / 'frozen_native_adapter.py')
        if execute(command, target, 'generate'):
            write(folder / 'qualification.json', dict(status='FAILED', method=method, failed_design=design,
                  completed_designs=qualifications, source_commit=pin['commit'], binary_sha256=manifest['binary_sha256']))
            return 2
        for filename in ('qualification.json', 'architecture.json', 'canonical.json', 'generated.v', 'generator.resource.txt'):
            shutil.copy2(scratch / filename, target / filename)
        proof = read(target / 'qualification.json')
        if proof['binary_sha256'] != manifest['binary_sha256']:
            raise ValueError('Actual executed generator binary differs from pinned built binary')
        canonical = ScanArchitecture.from_json(target / 'canonical.json')
        reference = ScanArchitecture.from_json(Path(read(OUT / 'stage_a/P0_FREEZE.json')['frozen_inputs'][design]['B0_reference']['path']))
        validate_architecture(canonical, reference)
        if canonical.sha256() != proof['canonical_architecture_hash']:
            raise ValueError('Canonical architecture identity differs')
        qualifications[design] = dict(proof=binding(target / 'qualification.json'), canonical=binding(target / 'canonical.json'),
                                      chain_lengths=proof['chain_lengths'], architecture_hash=canonical.sha256())
        for chain in canonical.chains:
            for index, ff in enumerate(chain.cells):
                output_rows.append(dict(design=design, method=method, chain_id=chain.chain_id, chain_index=index,
                    ordered_ff_identity=ff, scan_in=chain.scan_in, scan_out=chain.scan_out, chain_length=len(chain.cells),
                    architecture_hash=canonical.sha256(), architecture_path=str(target / 'canonical.json')))
        print('QUALIFIED', method, design, proof['chain_lengths'], canonical.sha256(), flush=True)
    with (folder / 'architecture_manifest.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]))
        writer.writeheader(); writer.writerows(output_rows)
    write(folder / 'qualification.json', dict(status='PASS', method=method, source_commit=pin['commit'],
          binary_sha256=manifest['binary_sha256'], image=IMAGE, designs=qualifications,
          algorithm_source_blobs_unchanged=True, architecture_manifest=binding(folder / 'architecture_manifest.csv'),
          parameter_evidence=binding(OUT / 'protocol/algorithm_audit.json'),
          generator_liberty_metadata=binding(OUT / 'protocol/dft_metadata_adapter.json'),
          compiled_behavior=binding(folder / 'compiled_behavior.json'),
          commands='execute_dft_plan then actual compiled scan_opt; no substitute optimizer'))
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('method', choices=('B2', 'B3'))
    raise SystemExit(generate(parser.parse_args().method))
