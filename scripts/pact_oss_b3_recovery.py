#!/usr/bin/env python3
"""Build exact B3 only after all B2 canonical architectures qualify."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil

import pact_oss_recovery as recovery
from pact_oss_benchmark import OUT, DESIGNS, binding, read, write
from pact_oss_build import archive, submodules
from pact_oss_build_resolution import record

METHOD = 'B3_openroad_10666'
FOLDER = recovery.RECOVERY / 'baselines' / METHOD


def docker(args):
    temporary = recovery.MOUNT / METHOD / 'compiler_tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    command = recovery.docker(args)
    command[command.index('--entrypoint'):command.index('--entrypoint')] = [
        '--env', f'TMPDIR=/build_storage/{METHOD}/compiler_tmp']
    return command


def gate():
    from pact_oss_storage import ensure
    ensure()
    recovery.require_prerequisites()
    proof = read(recovery.RECOVERY / 'baselines/B2_openroad_10176/qualification.json')
    pin = read(OUT / 'baselines/B2_openroad_10176/source_pin.json')
    if proof['status'] != 'PASS' or set(proof['designs']) != set(DESIGNS) or proof['source_commit'] != pin['commit']:
        raise ValueError('B2 architecture qualification has not passed for all designs')
    if binding(recovery.MOUNT / 'B2_openroad_10176/build/bin/openroad')['sha256'] != proof['binary_sha256']:
        raise ValueError('Qualified B2 binary changed')
    for item in proof['designs'].values():
        if binding(item['canonical']['path'])['sha256'] != item['canonical']['sha256']:
            raise ValueError('Qualified B2 architecture changed')


def acquire():
    gate()
    pin = read(OUT / 'baselines' / METHOD / 'source_pin.json')
    source = recovery.MOUNT / METHOD / 'source'
    if source.exists():
        raise ValueError('B3 requires fresh exact source extraction')
    cache = recovery.DATA / METHOD / 'archives'
    main = archive(pin['repository'].removeprefix('https://github.com/'), pin['commit'], cache / 'source.tar.gz')
    recovery.extract(main['path'], source)
    children = submodules(pin['repository'].removeprefix('https://github.com/'), pin['commit'], source, cache / 'submodules')
    checked = {}
    for relative, expected in pin['source_files'].items():
        path = source / relative
        actual = hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
        if actual != expected['sha256']:
            raise ValueError('B3 source differs from saved pinned blob: ' + relative)
        checked[relative] = actual
    write(FOLDER / 'build_sources.json', dict(commit=pin['commit'], main_archive=main, submodules=children))
    write(FOLDER / 'source_manifest.json', dict(commit=pin['commit'], repository=pin['repository'],
        source_pin=binding(OUT / 'baselines' / METHOD / 'source_pin.json'), source_directory=str(source),
        saved_archive_and_submodule_hashes_verified=True, pinned_source_blobs_checked=checked,
        build_sources=binding(FOLDER / 'build_sources.json'), source_modifications=[]))
    # Bind the complete configuration requirements, including submodules, before
    # using the independently qualified dependency strategy for this revision.
    requirements = {}
    for path in sorted(source.rglob('CMakeLists.txt')) + sorted((source / 'cmake').glob('*.cmake')):
        requirements[str(path.relative_to(source))] = binding(path)
    original = recovery.MOUNT / 'B2_openroad_10176/source/cmake/FindTCL.cmake'
    current = source / 'cmake/FindTCL.cmake'
    if binding(original)['sha256'] != binding(current)['sha256']:
        raise ValueError('B3 Tcl finder differs; independent prerequisite probe must be extended before configuration')
    write(FOLDER / 'requirements_inventory.json', dict(files=requirements,
        independent_Tcl_finder_hash_matches_B2=True, image=recovery.IMAGE,
        prerequisite_evidence=binding(recovery.RECOVERY / 'toolchain/qualification.json')))
    print('B3_EXACT_SOURCE_ACQUIRED', pin['commit'], len(children), flush=True)


def configure():
    gate()
    source = read(FOLDER / 'source_manifest.json')
    if read(recovery.RECOVERY / 'toolchain/dependency_qualification.json')['status'] != 'PASS':
        raise ValueError('Independent dependency audit has not passed')
    build = recovery.MOUNT / METHOD / 'build'
    if build.exists():
        raise ValueError('B3 requires clean out-of-source configuration')
    args = ['cmake', '-S', f'/build_storage/{METHOD}/source', '-B', f'/build_storage/{METHOD}/build',
        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_GUI=OFF', '-DBUILD_PYTHON=ON', '-DENABLE_TESTS=OFF',
        '-DENABLE_GPU=OFF', '-DLINK_TIME_OPTIMIZATION=OFF', '-DCMAKE_C_COMPILER=/usr/bin/gcc',
        '-DCMAKE_CXX_COMPILER=/usr/bin/g++', '-DOPENROAD_VERSION=' + source['commit'],
        f'-DCMAKE_INSTALL_PREFIX=/build_storage/{METHOD}/install', '-DSWIG_EXECUTABLE=/usr/local/bin/swig',
        '-DTCL_HEADER=/usr/include/tcl8.6/tcl.h', '-DTCL_LIBRARY=/usr/lib/x86_64-linux-gnu/libtcl8.6.so',
        '-DCMAKE_PREFIX_PATH=/build_storage/toolchain;/opt/or-tools;/usr/local',
        '-DBoost_DIR=/usr/local/lib/cmake/Boost-1.89.0', '-DFETCHCONTENT_FULLY_DISCONNECTED=ON']
    shutil.copy2(__file__, FOLDER / 'configure.pact_oss_b3_recovery.py')
    rc = recovery.execute(docker(args), FOLDER, 'configure')
    if (build / 'CMakeCache.txt').exists():
        shutil.copy2(build / 'CMakeCache.txt', FOLDER / 'CMakeCache.txt')
    write(FOLDER / 'build_manifest.json', dict(status='CONFIGURED' if not rc else 'CONFIGURATION_FAILED',
        commit=source['commit'], image=recovery.IMAGE, configuration=binding(FOLDER / 'configure.execution.json'),
        source_manifest=binding(FOLDER / 'source_manifest.json'), binary_sha256=None,
        fixed_backend_unchanged=binding('/usr/bin/openroad')))
    if not rc:
        record(METHOD)
    return rc


def build():
    gate()
    manifest = read(FOLDER / 'build_manifest.json')
    if manifest['status'] != 'CONFIGURED':
        raise ValueError('B3 has not configured successfully')
    shutil.copy2(__file__, FOLDER / 'build.pact_oss_b3_recovery.py')
    args = ['/usr/bin/time', '-v', '-o', '/scratch/recovery_20261003/B3_build_container.resource.txt',
        'cmake', '--build', f'/build_storage/{METHOD}/build', '--parallel', '2', '--target', 'openroad']
    rc = recovery.execute(docker(args), FOLDER, 'build')
    resource = recovery.DATA / 'B3_build_container.resource.txt'
    if resource.exists():
        shutil.copy2(resource, FOLDER / 'build.container.resource.txt')
    binary = recovery.MOUNT / METHOD / 'build/bin/openroad'
    write(FOLDER / 'build_result.json', dict(manifest, status='BUILT' if not rc else 'COMPILATION_FAILED',
        build=binding(FOLDER / 'build.execution.json'), configuration_manifest=binding(FOLDER / 'build_manifest.json'),
        binary=binding(binary) if binary.exists() else None, binary_sha256=binding(binary)['sha256'] if binary.exists() else None))
    return rc


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('acquire', 'configure', 'build'))
    raise SystemExit(globals()[parser.parse_args().action]())
