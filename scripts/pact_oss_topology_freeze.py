#!/usr/bin/env python3
"""Freeze repaired source/parameters and preserve exact immutable executables."""
import os
from pathlib import Path
import shutil
import subprocess

from pact_oss_benchmark import OUT, binding, read, write
import pact_oss_topology as r
import pact_oss_serialization as s


def main():
    r.ensure()
    s.activate()
    qualification = read(s.FOLDER / 'qualification.json')
    repair = read(s.REPAIR / 'repair_manifest.json')
    build = read(s.FOLDER / 'build_result.json')
    if qualification['status'] != 'PASS' or build['commit'] != repair['repair_commit_sha']:
        raise ValueError('Freeze only the qualified immutable repair')
    if r.git('rev-parse', 'HEAD').strip() != build['commit'] or r.git('status', '--porcelain').strip():
        raise ValueError('Root/submodule worktrees must remain clean')
    sta = r.SOURCE / 'src/sta'
    if subprocess.check_output(['git', '-C', str(sta), 'rev-parse', 'HEAD'], text=True).strip() != repair['OpenSTA_repair_commit']:
        raise ValueError('OpenSTA revision differs')
    original = read(OUT / 'recovery_20261003/baselines/B3_openroad_10666/source_manifest.json')
    names = [name for name in original['pinned_source_blobs_checked'] if name.startswith(('src/dft/src/optimizer/', 'src/dft/src/config/'))]
    names += ['src/dft/src/architect/NNReorder.cpp', 'src/dft/src/architect/ScanChain.cpp', 'src/dft/src/dft.tcl', 'src/dft/src/dft.i', 'src/dft/src/stitch/ScanStitch.cpp']
    hashes = {}
    for name in names:
        hashes[name] = binding(r.SOURCE / name)['sha256']
        if hashes[name] != original['pinned_source_blobs_checked'][name]:
            raise ValueError('Optimizer/objective/parameter source changed: ' + name)
    raw = r.DATA / s.NAME / 'compiled_probe'
    raw.mkdir(parents=True, exist_ok=True)
    container_source = f'/build_storage/{s.NAME}/source'
    output = f'/scratch/topology_recovery_20261004/{s.NAME}/compiled_probe/compiled_behavior.json'
    command = [f'/build_storage/{s.NAME}/build/bin/openroad', '-python', '-no_init', '-exit',
        '/workspace/scripts/pact_oss_topology_probe.py', '--commit', build['commit'],
        '--source', container_source, '--output', output]
    probe = s.FOLDER / 'compiled_probe/compiled_behavior.json'
    if not probe.exists():
        if r.run(r.container(command), s.FOLDER / 'compiled_probe', 'probe'):
            raise RuntimeError('Compiled behavior probe failed')
        for name in ('compiled_behavior.json', 'compiled_behavior.commands.txt'):
            shutil.copy2(raw / name, s.FOLDER / 'compiled_probe' / name)
    if read(probe)['source_commit'] != build['commit'] or read(probe)['binary_sha256'] != build['binary_sha256']:
        raise ValueError('Existing command probe identity differs')
    executable = r.DATA / 'immutable_binaries' / build['commit'] / 'openroad'
    executable.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(r.BUILD / 'bin/openroad', executable)
    if binding(executable)['sha256'] != build['binary_sha256']:
        raise ValueError('Immutable executable copy differs')
    # The running build helper predated its direct-parent metadata correction.
    # Preserve that original receipt before correcting this non-source field.
    if build['parent_revision'] != repair['parent_revision']:
        original_receipt = s.FOLDER / 'build_result.original_parent_field.json'
        if not original_receipt.exists():
            shutil.copy2(s.FOLDER / 'build_result.json', original_receipt)
        build['parent_revision'] = repair['parent_revision']
        build['metadata_correction'] = 'Direct B3T parent is endpoint B3S, rather than the campaign B3R starting point; executable and command receipts are unchanged'
        write(s.FOLDER / 'build_result.corrected.json', build)
    write(s.FOLDER / 'source_manifest.json', dict(method='B3T', source_commit=build['commit'],
        parent_revision=repair['parent_revision'], upstream_base=r.BASE, OpenSTA_commit=repair['OpenSTA_repair_commit'],
        OpenSTA_parent=repair['OpenSTA_parent'], original_optimizer_source=binding(OUT / 'recovery_20261003/baselines/B3_openroad_10666/source_manifest.json'),
        unchanged_optimizer_objective_parameter_source_sha256=hashes,
        implementation_repairs=[read(s.ENDPOINT_REPAIR / 'repair_manifest.json'), repair],
        algorithm_changed=False, objective_changed=False, parameters_changed=False, search_space_changed=False,
        compiled_behavior=binding(s.FOLDER / 'compiled_probe/compiled_behavior.json'),
        CMakeCache=binding(s.FOLDER / 'CMakeCache.txt'), immutable_binary=binding(executable),
        build_result=binding(s.FOLDER / ('build_result.corrected.json' if (s.FOLDER / 'build_result.corrected.json').exists() else 'build_result.json')),
        qualification=binding(s.FOLDER / 'qualification.json')))
    print('B3T_IMMUTABLE_SOURCE_AND_PARAMETERS_FROZEN', build['commit'], flush=True)


if __name__ == '__main__':
    main()
